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

import asyncio
import math
import re
import time
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, Protocol

import httpx

from config import get_settings
from infra.http import get_http
from infra.logger import get_logger

from .cost_meter import record_rerank

_log = get_logger()

#: Cohere va Voyage cung nhan query/documents va tra index/score, KHONG cung thang diem.
#: Lua chon chi phi thap 2026-10-05: voyage/rerank-3-lite. Chua benchmark corpus that;
#: khong tu bat runtime hoac dung threshold lexical cu de nghiem thu provider moi.
_COHERE_ENDPOINT = "https://api.cohere.com/v2/rerank"
_VOYAGE_ENDPOINT = "https://api.voyageai.com/v1/rerank"
_TIMEOUT_S = 15.0
# Official list prices verified 2026-10-05; free credits are NOT assumed.
# https://docs.voyageai.com/docs/pricing
VOYAGE_PRICES = {"rerank-3-lite": 0.02, "rerank-3": 0.05}
_MAX_VOYAGE_TOKENS = 600_000
_PLACEHOLDER_KEYS = {"", "fake", "dev", "test", "dummy", "placeholder", "changeme", "none"}


class RerankBudgetExceededError(RuntimeError):
    """Benchmark's reserved list-price budget would be exceeded before the call."""


class RerankHttpError(RuntimeError):
    """Only safe status metadata; never retain response, body, headers, or key."""

    def __init__(self, provider: str, status_code: int) -> None:
        self.provider = provider
        self.status_code = status_code
        super().__init__(f"{provider} rerank HTTP {status_code}")


def is_placeholder_key(key: str) -> bool:
    return key.strip().lower() in _PLACEHOLDER_KEYS


def _require_key(key: str) -> None:
    if is_placeholder_key(key):
        raise ValueError("Rerank provider needs its own API key; placeholder rejected")


def _validated_hits(raw: Any, document_count: int, top_n: int) -> list["RerankHit"]:
    if not isinstance(raw, list) or not 0 < len(raw) <= min(top_n, document_count):
        raise ValueError("Invalid rerank results")
    hits: list[RerankHit] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Invalid rerank result")
        index, score = item.get("index"), item.get("relevance_score")
        if (
            type(index) is not int
            or not 0 <= index < document_count
            or isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
            or not 0 <= score <= 1
        ):
            raise ValueError("Invalid rerank index or score")
        hits.append(RerankHit(index, float(score)))
    if len({hit.index for hit in hits}) != len(hits) or any(
        left.score < right.score for left, right in pairwise(hits)
    ):
        raise ValueError("Duplicate or unordered rerank results")
    return hits


@dataclass(frozen=True, slots=True)
class RerankHit:
    #: Chi so trong danh sach dua vao. Cho goi tu anh xa nguoc ve doan van cua minh.
    index: int
    score: float


class RerankerPort(Protocol):
    #: Diem tra ve co phai DO LIEN QUAN da hieu chuan khong.
    #:
    #: Cross-encoder that: True — diem so sanh duoc voi mot nguong co dinh.
    #: Ban du phong: False — diem la ti le TU TRUNG, mot dai luong khac han.
    #: Cho goi dung co nay de biet co duoc phep dung diem de LOC hay khong;
    #: dung nham thi cau hoi tieng Viet tren tai lieu tieng Anh se bi loai
    #: sach du tang vector da tim dung chunk.
    diem_dang_tin: bool

    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[RerankHit]:
        """Xep lai `documents` theo do tra loi duoc `query`.

        Tra ve TOI DA `top_n` phan tu, da sap giam dan theo diem. KHONG loc theo
        nguong o day — loc la quyet dinh cua cho goi, va cho goi can nhin thay diem
        cao nhat de biet "khong tim thay" khac "co nhung diem thap".
        """
        ...


class CohereReranker:
    diem_dang_tin = True

    def __init__(self, *, model: str | None = None, api_key: str | None = None) -> None:
        self._model = model
        self._api_key = api_key

    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[RerankHit]:
        if not documents:
            return []

        key, model = self._api_key, self._model
        if key is None or model is None:
            settings = get_settings()
            key = key if key is not None else settings.RERANK_API_KEY
            model = model if model is not None else settings.RERANK_MODEL
        _require_key(key)
        started = time.monotonic()
        response = await get_http().post(
            _COHERE_ENDPOINT,
            headers={"Authorization": f"Bearer {key}"},
            timeout=_TIMEOUT_S,
            follow_redirects=False,
            json={
                "model": model,
                "query": query,
                "documents": documents,
                "top_n": min(top_n, len(documents)),
            },
        )

        if response.status_code != httpx.codes.OK:
            # KHONG nuot loi thanh danh sach rong: rong co nghia la "khong tim thay
            # trong tai lieu", va bot se noi dung cau do voi nguoi dung trong khi
            # tai lieu van nam nguyen trong CSDL. Cho goi phai duoc biet la HONG.
            _log.warning("rerank HTTP failed", provider="cohere", status_code=response.status_code)
            raise RerankHttpError("cohere", response.status_code)

        results: list[dict[str, Any]] = response.json().get("results") or []
        _log.debug("rerank", ms=int((time.monotonic() - started) * 1000), n=len(results))
        return [
            RerankHit(index=int(r["index"]), score=float(r["relevance_score"])) for r in results
        ]


class VoyageReranker:
    """Paid cross-encoder; list-price accounting, no implicit retries or truncation.

    With a benchmark budget, reserve the API's maximum 600K billable tokens BEFORE
    each call. Replace that reservation with reported usage on success. Keep it
    after timeout/malformed usage because remote billing is then unknown.
    """

    diem_dang_tin = True

    def __init__(self, *, model: str, api_key: str, max_cost_usd: float | None = None) -> None:
        _require_key(api_key)
        if model not in VOYAGE_PRICES:
            raise ValueError("Voyage model must have a verified list price")
        if max_cost_usd is not None and (not math.isfinite(max_cost_usd) or max_cost_usd <= 0):
            raise ValueError("Rerank budget must be finite and positive")
        self._model, self._api_key = model, api_key
        self.max_cost_usd = max_cost_usd
        self.price_per_million = VOYAGE_PRICES[model]
        self.reserved_cost_usd = 0.0
        self.calls = self.measured_calls = self.total_tokens = 0
        self.estimated_cost_usd = 0.0

    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[RerankHit]:
        if not documents:
            return []
        if type(top_n) is not int or top_n <= 0 or len(documents) > 1000:
            raise ValueError("Invalid rerank document count or top_n")
        reservation = _MAX_VOYAGE_TOKENS * self.price_per_million / 1_000_000
        if (
            self.max_cost_usd is not None
            and self.reserved_cost_usd + reservation > self.max_cost_usd
        ):
            raise RerankBudgetExceededError("Rerank budget would be exceeded")
        self.reserved_cost_usd += reservation
        self.calls += 1
        started = time.monotonic()
        response = await get_http().post(
            _VOYAGE_ENDPOINT,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=_TIMEOUT_S,
            follow_redirects=False,
            json={
                "model": self._model,
                "query": query,
                "documents": documents,
                "top_k": min(top_n, len(documents)),
                "return_documents": False,
                "truncation": False,
            },
        )
        if response.status_code != httpx.codes.OK:
            _log.warning("rerank HTTP failed", provider="voyage", status_code=response.status_code)
            raise RerankHttpError("voyage", response.status_code)
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Invalid Voyage response")
        usage = payload.get("usage")
        tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
        if type(tokens) is not int or not 0 <= tokens <= _MAX_VOYAGE_TOKENS:
            raise ValueError("Voyage token usage missing or invalid")
        cost = tokens * self.price_per_million / 1_000_000
        self.reserved_cost_usd += cost - reservation
        self.estimated_cost_usd += cost
        self.measured_calls += 1
        self.total_tokens += tokens
        latency = int((time.monotonic() - started) * 1000)
        # A malformed ranking may still cost money, but is NOT a successful call.
        valid_results = False
        try:
            hits = _validated_hits(payload.get("data"), len(documents), top_n)
            valid_results = True
            return hits
        finally:
            try:
                async with asyncio.timeout(2):
                    await record_rerank(
                        model=f"voyage/{self._model}",
                        tokens=tokens,
                        cost_usd=cost,
                        latency_ms=latency,
                        ok=valid_results,
                    )
            except Exception as error:
                _log.warning("Rerank usage unavailable", error_type=type(error).__name__)
            _log.debug(
                "rerank",
                provider="voyage",
                ms=latency,
                tokens=tokens,
                estimated_cost_usd=cost,
                ok=valid_results,
            )


def build_reranker(
    provider: str, *, model: str, api_key: str, max_cost_usd: float | None = None
) -> RerankerPort:
    """Explicit benchmark overrides, without changing the application's .env."""
    if provider.lower() == "voyage":
        return VoyageReranker(model=model, api_key=api_key, max_cost_usd=max_cost_usd)
    if provider.lower() == "cohere":
        _require_key(api_key)
        return CohereReranker(model=model, api_key=api_key)
    if provider.lower() == "fake":
        return LexicalOverlapReranker()
    raise ValueError("Unsupported rerank provider")


class LexicalOverlapReranker:
    """Ban khong can khoa: xep theo ti le tu cua cau hoi xuat hien trong doan van.

    KHONG phai cross-encoder va khong gia vo la mot cai. No ton tai de duong ong
    chay duoc, de test khong phai goi mang, va de mot nguoi chua mua khoa rerank van
    hoi duoc tai lieu cua minh — ket qua kem hon, nhung khong im lang.

    Diem cua no KHONG phai do lien quan ma la ti le TU TRUNG — nen `diem_dang_tin
    = False`, va cho goi phai lay khoang cach vector lam thuoc do lien quan thay
    vi lay diem nay.

    Do duoc 08/09/2026: cau hoi tieng Viet tren tai lieu tieng Anh dat toi da
    0,00 — khong tu nao trung duoc — trong khi tang vector tim dung chunk o hang
    1. Dung diem nay de loc la vut di ket qua dung.
    """

    diem_dang_tin = False

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
        settings = get_settings()
        provider = settings.RERANK_PROVIDER.lower()
        if provider in {"cohere", "voyage"}:
            _reranker = build_reranker(
                provider, model=settings.RERANK_MODEL, api_key=settings.RERANK_API_KEY
            )
        else:
            _log.warning(
                "RERANK_PROVIDER khong phai 'cohere'/'voyage' — dung ban xep theo tu trung. "
                "Chat luong tim kiem se kem han; xem llm/reranker.py.",
                provider=provider,
            )
            _reranker = LexicalOverlapReranker()
    return _reranker
