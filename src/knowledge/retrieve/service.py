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

from agents.domain.knowledge import RetrievedChunk
from config import get_settings
from infra.logger import get_logger

from .fusion import reciprocal_rank_fusion
from .search import CANDIDATES_PER_SIDE, ChunkRow, lexical_search, vector_search

_log = get_logger()

#: Sau hop nhat con bay nhieu truoc khi dua sang rerank. Rerank tinh tien theo so
#: van ban, va cross-encoder cham hon vector search vai lan.
FUSION_TOP = 10


class HybridKnowledge:
    """Kho tri thuc lai (hybrid)."""

    async def search(self, query: str, k: int) -> list[RetrievedChunk]:
        if not query.strip():
            return []

        # Song song: hai duong doc lap, chay tuan tu la cong thang do tre cua ca hai
        # vao duong phan hoi ma khong duoc gi.
        #
        # return_exceptions=True vi mot duong chet khong duoc lam hong ca lan tim:
        # vector con chay thi van tra loi duoc, chi kem hon.
        vector_hits, lexical_hits = await asyncio.gather(
            vector_search(query, CANDIDATES_PER_SIDE),
            lexical_search(query, CANDIDATES_PER_SIDE),
            return_exceptions=True,
        )

        rows: dict[int, ChunkRow] = {}
        rankings: list[list[int]] = []
        for name, hits in (("vector", vector_hits), ("lexical", lexical_hits)):
            if isinstance(hits, BaseException):
                _log.error("mot duong tim that bai, dung duong con lai", duong=name, err=str(hits))
                continue
            rankings.append([h.chunk_id for h in hits])
            rows.update({h.chunk_id: h for h in hits})

        if not rows:
            return []

        fused = reciprocal_rank_fusion(rankings)[:FUSION_TOP]
        candidates = [rows[r.chunk_id] for r in fused]
        return await self._rerank(query, candidates, k)

    async def _rerank(
        self, query: str, candidates: list[ChunkRow], k: int
    ) -> list[RetrievedChunk]:
        from llm.reranker import get_reranker

        min_score = get_settings().RERANK_MIN_SCORE
        try:
            hits = await get_reranker().rerank(query, [c.content for c in candidates], k)
        except Exception as error:
            # Rerank hong thi giu nguyen thu tu RRF va CAT theo k. Khong tra ve rong:
            # rong nghia la "khong co trong tai lieu", tuc la noi doi ve mot su co
            # ha tang. Bo qua nguong o day va ghi log to — day la che do suy giam,
            # phai nhin thay duoc.
            _log.error("rerank that bai — dung thu tu RRF, KHONG loc nguong", err=str(error))
            return [_to_chunk(c, score=0.0) for c in candidates[:k]]

        kept = [
            _to_chunk(candidates[h.index], score=h.score)
            for h in hits
            if h.index < len(candidates) and h.score >= min_score
        ]
        if not kept and hits:
            _log.info(
                "co ket qua nhung deu duoi nguong — coi nhu khong tim thay",
                diem_cao_nhat=max(h.score for h in hits),
                nguong=min_score,
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
    )


knowledge = HybridKnowledge()
