"""Rerank — nha cung cap THU HAI, vi OpenAI khong co API rerank.

Vi sao van can rerank khi da co vector + BM25: hai cai do tra ve thu "co lien quan",
con rerank tra ve thu "tra loi dung cau hoi". Cross-encoder doc CA cau hoi va CA
doan van cung luc nen no phan biet duoc "tai lieu noi ve hoan tien" voi "tai lieu
tra loi duoc hoan tien trong bao lau" — thu ma embedding hai phia khong lam duoc.

Nguong RERANK_MIN_SCORE la cho bot hoc cach noi "khong tim thay trong tai lieu".
Khong co no thi ket qua kem nhat cua mot lan tim vo vong van duoc dua vao prompt
nhu the no la cau tra loi.

Doi nha cung cap = viet lai MOT file nay. knowledge/ khong doi mot dong.
"""

import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from config import get_settings
from infra.http import get_http
from infra.logger import get_logger

_log = get_logger()

#: Cohere la mac dinh cho tieng Viet: model multilingual cua ho phu ~100 ngon ngu va
#: co ban dung thu khong the tin dung. Jina va Voyage deu thay the duoc — chung cung
#: nhan (query, danh sach van ban) va tra ve (chi so, diem).
#:
#: CHUA BENCHMARK tren tai lieu that. Plan section 8 doi 20 cau hoi that tren tai
#: lieu that truoc khi chot; ma tai lieu thi chua co, nen day la mot lua chon DE
#: VIET DUOC CODE, khong phai mot ket luan. Benchmark khi tai lieu ve.
_COHERE_ENDPOINT = "https://api.cohere.com/v2/rerank"
_TIMEOUT_S = 15.0


@dataclass(frozen=True, slots=True)
class RerankHit:
    #: Chi so trong danh sach dua vao. Cho goi tu anh xa nguoc ve doan van cua minh.
    index: int
    score: float


class RerankerPort(Protocol):
    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[RerankHit]:
        """Xep lai `documents` theo do tra loi duoc `query`.

        Tra ve TOI DA `top_n` phan tu, da sap giam dan theo diem. KHONG loc theo
        nguong o day — loc la quyet dinh cua cho goi, va cho goi can nhin thay diem
        cao nhat de biet "khong tim thay" khac "co nhung diem thap".
        """
        ...


class CohereReranker:
    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[RerankHit]:
        if not documents:
            return []

        settings = get_settings()
        started = time.monotonic()
        response = await get_http().post(
            _COHERE_ENDPOINT,
            headers={"Authorization": f"Bearer {settings.RERANK_API_KEY}"},
            timeout=_TIMEOUT_S,
            json={
                "model": settings.RERANK_MODEL,
                "query": query,
                "documents": documents,
                "top_n": min(top_n, len(documents)),
            },
        )

        if response.status_code != httpx.codes.OK:
            # KHONG nuot loi thanh danh sach rong: rong co nghia la "khong tim thay
            # trong tai lieu", va bot se noi dung cau do voi nguoi dung trong khi
            # tai lieu van nam nguyen trong CSDL. Cho goi phai duoc biet la HONG.
            raise RuntimeError(f"rerank tra ve {response.status_code}: {response.text[:200]}")

        results: list[dict[str, Any]] = response.json().get("results") or []
        _log.debug("rerank", ms=int((time.monotonic() - started) * 1000), n=len(results))
        return [
            RerankHit(index=int(r["index"]), score=float(r["relevance_score"])) for r in results
        ]


class LexicalOverlapReranker:
    """Ban khong can khoa: xep theo ti le tu cua cau hoi xuat hien trong doan van.

    KHONG phai cross-encoder va khong gia vo la mot cai. No ton tai de duong ong
    chay duoc, de test khong phai goi mang, va de mot nguoi chua mua khoa rerank van
    hoi duoc tai lieu cua minh — ket qua kem hon, nhung khong im lang.

    Diem tra ve nam trong [0;1] nen so sanh voi RERANK_MIN_SCORE van co nghia, du
    thang diem khac han cross-encoder. Doi lai nguong 0,35 la CHAT voi ban nay:
    it cau hoi nao lap lai 35% so tu cua no trong doan van.
    """

    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[RerankHit]:
        terms = _terms(query)
        if not terms:
            return [RerankHit(index=i, score=0.0) for i in range(min(top_n, len(documents)))]

        scored: list[RerankHit] = []
        for i, doc in enumerate(documents):
            scored.append(RerankHit(index=i, score=len(terms & _terms(doc)) / len(terms)))

        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_n]


#: Tach tu theo ky tu CHU-SO chu khong theo khoang trang.
#:
#: Do that: cau hoi "HT-2026" khong khop tai lieu chua "HT-2026-xxxx" khi tach theo
#: khoang trang — hai ben ra hai token khac nhau va diem la 0. Ma ma so van ban lai
#: dung la truong hop hybrid search ton tai de bat.
_WORD = re.compile(r"[0-9a-z]+")


def _terms(text: str) -> set[str]:
    from agents.policy.injection import fold_diacritics

    return {t for t in _WORD.findall(fold_diacritics(text).lower()) if len(t) > 1}


_reranker: RerankerPort | None = None


def get_reranker() -> RerankerPort:
    """Chon theo RERANK_PROVIDER. NOI DUY NHAT quyet dinh dung ban nao.

    Tao luoi luc goi dau tien chu khong luc import, y het llm/embedder.py: doc config
    ngay khi import bien moi lenh `import` thanh mot cho co the chet vi thieu bien
    moi truong, ke ca trong test khong dung toi rerank.
    """
    global _reranker
    if _reranker is None:
        provider = get_settings().RERANK_PROVIDER.lower()
        if provider == "cohere":
            _reranker = CohereReranker()
        else:
            _log.warning(
                "RERANK_PROVIDER khong phai 'cohere' — dung ban xep theo tu trung. "
                "Chat luong tim kiem se kem han; xem llm/reranker.py.",
                provider=provider,
            )
            _reranker = LexicalOverlapReranker()
    return _reranker
