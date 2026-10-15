"""Duong tim day du, mot ham.

    vector (top 20)  ─┐
                      ├─ RRF k=60 ─ top 10 ─ rerank ─ top 3-5 + nguong
    lexical (top 20) ─┘

Tra ve RONG nghia la "khong tim thay trong tai lieu", KHONG phai loi — dung hop
dong cua cong cu. Do la cai cho phep bot noi thang thay vi lay kien thuc
chung ra thay the roi de nguoi dung tuong do la noi dung tai lieu cua ho.

Cache embedding cau hoi: `emb:{sha256}` TTL 24h (section 6.5). Trong mot nhom,
cung mot cau hoi duoc go lai rat nhieu.
"""

import asyncio
import math
from dataclasses import dataclass
from typing import Any

from agents.domain.knowledge import RetrievedChunk
from agents.domain.thread import ThreadScope
from config import get_settings
from infra.logger import get_logger
from knowledge.provenance import KnowledgeProvenanceError
from llm.embedder import shared_query_embeddings

from .fusion import reciprocal_rank_fusion
from .search import CANDIDATES_PER_SIDE, ChunkRow, lexical_search, vector_search

_log = get_logger()

#: Sau hop nhat con bay nhieu truoc khi dua sang rerank. Rerank tinh tien theo so
#: van ban, va cross-encoder cham hon vector search vai lan.
FUSION_TOP = 10


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    #: Candidates existed but the configured relevance filter kept none.
    filtered: bool = False
    retrieval_degraded: bool = False
    rerank_degraded: bool = False


class RetrievalUnavailableError(RuntimeError):
    """A missing retrieval branch means absence cannot be established safely."""

    def __init__(self, *, rerank_degraded: bool = False) -> None:
        super().__init__("Tra cuu tai lieu dang gian doan; chua the ket luan khong co dap an.")
        self.rerank_degraded = rerank_degraded


class HybridKnowledge:
    """Kho tri thuc lai (hybrid)."""

    async def search(self, scope: ThreadScope, query: str, k: int) -> list[RetrievedChunk]:
        return (await self.search_detailed(scope, query, k)).chunks

    async def search_detailed(self, scope: ThreadScope, query: str, k: int) -> RetrievalResult:
        if k < 1:
            raise ValueError("k must be positive")
        if not query.strip():
            return RetrievalResult([])

        # Song song: hai duong doc lap, chay tuan tu la cong thang do tre cua ca hai
        # vao duong phan hoi ma khong duoc gi.
        #
        # return_exceptions=True vi mot duong chet khong duoc lam hong ca lan tim:
        # vector con chay thi van tra loi duoc, chi kem hon.
        with shared_query_embeddings():
            vector_hits, lexical_hits = await asyncio.gather(
                vector_search(scope, query, CANDIDATES_PER_SIDE),
                lexical_search(scope, query, CANDIDATES_PER_SIDE),
                return_exceptions=True,
            )

        rows: dict[int, ChunkRow] = {}
        rankings: list[list[int]] = []
        degraded = False
        for name, hits in (("vector", vector_hits), ("lexical", lexical_hits)):
            if isinstance(hits, KnowledgeProvenanceError):
                # A visible incompatible document invalidates the whole operation;
                # surviving hits cannot prove correct absence or complete evidence.
                raise RetrievalUnavailableError() from hits
            if isinstance(hits, BaseException) and not isinstance(hits, Exception):
                raise hits
            if isinstance(hits, Exception):
                degraded = True
                _log.error(
                    "mot duong tim that bai, dung duong con lai",
                    duong=name,
                    error=type(hits).__name__,
                )
                continue
            rankings.append([h.chunk_id for h in hits])
            rows.update({h.chunk_id: h for h in hits})

        if not rows:
            if degraded:
                raise RetrievalUnavailableError()
            return RetrievalResult([])

        fused = reciprocal_rank_fusion(rankings)[:FUSION_TOP]
        candidates = [rows[r.chunk_id] for r in fused]
        result = await self._rerank(query, candidates, k)
        if degraded and not result.chunks:
            raise RetrievalUnavailableError(rerank_degraded=result.rerank_degraded)
        return RetrievalResult(result.chunks, result.filtered, degraded, result.rerank_degraded)

    async def _rerank(self, query: str, candidates: list[ChunkRow], k: int) -> RetrievalResult:
        from llm.reranker import get_reranker

        reranker = get_reranker()
        settings = get_settings()
        try:
            hits = await reranker.rerank(query, [c.content for c in candidates], k)
            # Malformed provider output is an outage, not proof of no relevant documents.
            seen: set[int] = set()
            if not hits or len(hits) > min(k, len(candidates)):
                raise ValueError("invalid rerank result count")
            for hit in hits:
                if (
                    type(hit.index) is not int
                    or not 0 <= hit.index < len(candidates)
                    or hit.index in seen
                    or not math.isfinite(hit.score)
                ):
                    raise ValueError("invalid rerank index or score")
                seen.add(hit.index)
        except Exception as error:
            # Rerank hong thi giu nguyen thu tu RRF va CAT theo k. Khong tra ve rong:
            # rong nghia la "khong co trong tai lieu", tuc la noi doi ve mot su co
            # ha tang. Bo qua nguong o day va ghi log to — day la che do suy giam,
            # phai nhin thay duoc.
            _log.error(
                "rerank that bai — dung thu tu RRF, KHONG loc nguong", error=type(error).__name__
            )
            return RetrievalResult(
                [_to_chunk(c, score=0.0) for c in candidates[:k]], rerank_degraded=True
            )

        if reranker.diem_dang_tin:
            chunks = self._loc_theo_diem(hits, candidates, settings.RERANK_MIN_SCORE)
        else:
            chunks = self._loc_theo_khoang_cach(hits, candidates, settings.RAG_MAX_DISTANCE)
        return RetrievalResult(chunks, filtered=not chunks)

    @staticmethod
    def _loc_theo_diem(
        hits: list[Any], candidates: list[ChunkRow], nguong: float
    ) -> list[RetrievedChunk]:
        """Duong CHUAN: cross-encoder that, diem la do lien quan da hieu chuan."""
        kept = [_to_chunk(candidates[h.index], score=h.score) for h in hits if h.score >= nguong]
        if not kept and hits:
            _log.info(
                "co ket qua nhung deu duoi nguong — coi nhu khong tim thay",
                diem_cao_nhat=max(h.score for h in hits),
                nguong=nguong,
            )
        return kept

    @staticmethod
    def _loc_theo_khoang_cach(
        hits: list[Any], candidates: list[ChunkRow], tran: float
    ) -> list[RetrievedChunk]:
        """Duong DU PHONG: ban rerank khong phai cross-encoder.

        No cham do trung TU VUNG, khong phai do lien quan — nen no duoc quyen XEP THU
        TU nhung KHONG duoc quyen LOC. Do duoc 08/09/2026: cau hoi tieng Viet tren tai
        lieu tieng Anh dat diem toi da 0,00 vi khong tu nao trung, trong khi tang
        vector tim dung chunk o hang 1. Loc bang diem do la vut di ket qua dung, roi
        bot noi "khong tim thay" ve mot thu dang nam trong CSDL — mot loi IM LANG.

        Thay vao do lay KHOANG CACH COSINE, thu co hieu chuan ngu nghia. Do tren 14
        cau hoi tieng Viet: cau CO trong tai lieu 0,4382-0,7587, cau NGOAI tai lieu
        0,7918-0,9294 — hai phan bo tach roi.

        Chunk den tu duong BM25 khong co khoang cach (`distance is None`): GIU lai.
        Khop duoc bang tu la mot tin hieu doc lap va manh, khong can thuoc do nay.
        """
        kept: list[RetrievedChunk] = []
        for h in hits:
            row = candidates[h.index]
            if row.distance is None or row.distance <= tran:
                kept.append(_to_chunk(row, score=h.score))

        if not kept and hits:
            gan_nhat = [candidates[h.index].distance for h in hits]
            gan_nhat = [d for d in gan_nhat if d is not None]
            _log.info(
                "moi ung vien deu qua xa ve ngu nghia — coi nhu khong tim thay",
                khoang_cach_gan_nhat=round(min(gan_nhat), 4) if gan_nhat else None,
                tran=tran,
            )
        return kept


def _strip_title(section: str | None, title: str) -> str | None:
    """Bo ten tai lieu khoi dau duong dan tieu de.

    Tieu de cap mot cua tai lieu thuong CHINH LA ten tai lieu, nen trich dan day du
    doc thanh "theo So tay 2026, muc So tay 2026 > Hoan tien". Bo o day chu khong o
    luc nap: cot `section` giu duong dan THAT trong tai lieu, con day la cach hien
    thi no cho nguoi doc.
    """
    if section is None:
        return None
    if section == title:
        return None
    prefix = f"{title} > "
    return section[len(prefix) :] if section.startswith(prefix) else section


def _to_chunk(row: ChunkRow, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=str(row.chunk_id),
        doc_title=row.doc_title,
        section=_strip_title(row.section, row.doc_title),
        page=row.page,
        content=row.content,
        score=score,
        # Di kem ra ngoai chu khong dung o day roi vut di: cong cu can no de biet
        # lan tim nay co CHAC khong. Xem RetrievedChunk.distance.
        distance=row.distance,
        doc_id=row.doc_id,
        doc_version=row.doc_version,
        doc_scope=row.doc_scope,
        is_latest=row.is_latest,
    )


knowledge = HybridKnowledge()
