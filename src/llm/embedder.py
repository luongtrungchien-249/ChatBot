"""Embedding — dung cho L3 (memory_fact) va sau nay cho L4 (RAG).

QUYET DINH 06/09/2026: nha cung cap la OpenAI, `text-embedding-3-large` voi tham so
`dimensions=1024`.

Vi sao chot duoc bay gio trong khi D3/D5 con de mo: hai quyet dinh do noi ve RAG —
o day can BENCHMARK tren tai lieu that va can them mot nha cung cap RERANK (OpenAI
khong co rerank). L3 thi khac: fact la nhung cau ngan, khong co buoc rerank, va
rang buoc cung `VECTOR(1024)` thi `text-embedding-3-large` dap ung dung bang tham
so `dimensions`. Dung chung API key da co, khong them nha cung cap nao.

Doi nha cung cap sau nay = viet lai MOT file nay. Gia phai tra la nhung fact da luu
phai embed lai — re, vi fact la vai chuc dong chu khong phai vai nghin chunk.

Ban `fake` ton tai de test va de chay dev khong ton tien. No la HASH XAC DINH, khong
phai so ngau nhien: cung mot chuoi luon cho cung mot vector, nen cac test ve trung
lap va mau thuan van co nghia.
"""

import hashlib
import math
import time
from dataclasses import dataclass
from typing import Any, Protocol

from config import get_settings
from infra.logger import get_logger

from .cost_meter import record_embedding
from .models import EMBEDDING_PRICES

_log = get_logger()

#: Mac dinh khi .env khong noi gi. Phai KHOP cot VECTOR(n) trong db/migrations —
#: lech thi Postgres tu choi luc INSERT, va main/container.py chan tu luc khoi dong.
DIMENSIONS = 1024

#: Mac dinh. Gia tri THAT lay tu EMBEDDING_MODEL trong .env — xem _config().
DEFAULT_MODEL = "text-embedding-3-large"


class EmbedderPort(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Nhieu chuoi mot lan goi: mot vong mang cho ca lo, khong phai moi chuoi mot vong."""
        ...


#: Timeout cho MOT lan goi. Embedding la lenh ngan; 20s da rat rong.
#:
#: Phai dat TUONG MINH: mac dinh cua SDK dai va bien dong, va lan goi nay nam TREN
#: duong phan hoi — L3 embed cau hoi o moi tin nhan. Da troi that: bo test do lac
#: loi vi APITimeoutError, va vi khong co timeout rieng nen khong cach nao chinh.
EMBED_TIMEOUT_S = 20.0

#: Embedding la phep toan THUAN: cung dau vao ra cung ket qua, khong co tac dung phu.
#: Nen retry o day an toan tuyet doi — khac han mot lan goi sinh van ban.
EMBED_MAX_RETRIES = 2

@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    model: str
    dimensions: int
    price_per_million: float


def embedding_config() -> EmbeddingConfig:
    """Doc EMBEDDING_MODEL / EMBEDDING_DIM tu .env.

    Ban truoc HARDCODE ca hai o day trong khi config/schema.py van bat buoc khai
    chung. Doi EMBEDDING_MODEL trong .env khong doi gi het — dung loai lech im lang
    ma L7 sinh ra de tranh.

    Model khong co trong EMBEDDING_PRICES thi NEM ngay: chay tiep nghia la usage_log
    ghi cost_usd theo gia cua mot model khac, va chot chan DAILY_BUDGET_USD dem theo
    con so sai.
    """
    settings = get_settings()
    model = settings.EMBEDDING_MODEL or DEFAULT_MODEL
    price = EMBEDDING_PRICES.get(model)
    if price is None:
        raise RuntimeError(
            f"EMBEDDING_MODEL={model!r} khong co trong EMBEDDING_PRICES (llm/models.py). "
            "Them gia cua no vao do truoc, neu khong usage_log se ghi sai tien."
        )
    return EmbeddingConfig(
        model=model, dimensions=settings.EMBEDDING_DIM, price_per_million=price
    )


#: MOT client dung chung cho ca process, khong phai mot client moi moi lan goi.
#:
#: BUG DA DO DUOC (07/09/2026). Ban truoc dung `AsyncOpenAI(...)` ngay trong `embed()`,
#: tuc la moi lan embed lai dung mot pool ket noi moi va bat tay TLS lai tu dau.
#: `usage_log` cho thay hau qua: p50 328ms va p90 1202ms — binh thuong — nhung 96 tren
#: 1493 lan (6,4%) vuot 19s, va cham nhat la 41s CHO MOT INPUT 8 TOKEN. Do khong phai
#: API cham; do la mot lan bat tay treo den het timeout 20s roi duoc `max_retries` thu
#: lai, thanh ra 40s.
#:
#: Duong nay chay o MOI tin nhan (L3 tim fact), nen 6% do nam thang tren duong phan hoi.
#: llm/openai_client.py da giu client o bien module tu dau; cho nay bi bo sot.
_client: Any = None


def _get_client() -> Any:
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        # EMBEDDING_API_KEY chi can khi nha cung cap embedding KHAC nha cung cap LLM.
        # Voi OpenAI thi cung mot khoa, nen khong bat nguoi dung dien hai lan.
        _client = AsyncOpenAI(
            api_key=get_settings().OPENAI_API_KEY,
            max_retries=EMBED_MAX_RETRIES,
            timeout=EMBED_TIMEOUT_S,
        )
    return _client


class OpenAiEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        config = embedding_config()

        started = time.monotonic()
        response = await _get_client().embeddings.create(
            model=config.model,
            input=texts,
            # Cat ve dung so chieu cua cot. text-embedding-3-* duoc huan luyen theo
            # kieu Matryoshka nen cat bot chieu chi mat rat it chat luong — khac han
            # viec cat mot vector thuong.
            dimensions=config.dimensions,
        )
        latency_ms = int((time.monotonic() - started) * 1000)

        # L6: moi loi goi ra ngoai deu duoc do cost. Thieu buoc nay thi tien embedding
        # KHONG nam trong chot chan DAILY_BUDGET_USD — va L3 embed o moi tin nhan,
        # nen do la mot dong chi khong ai nhin thay.
        tokens = response.usage.total_tokens if response.usage else 0
        await record_embedding(
            model=config.model,
            tokens=tokens,
            cost_usd=tokens * config.price_per_million / 1_000_000,
            latency_ms=latency_ms,
        )

        # API tra ve theo dung thu tu dau vao, nhung khong dam bao — sap lai cho chac.
        ordered = sorted(response.data, key=lambda d: d.index)
        return [d.embedding for d in ordered]


class FakeEmbedder:
    """Hash xac dinh, KHONG phai so ngau nhien.

    Cung mot chuoi -> cung mot vector, nen test ve trung lap ("cosine > 0,9 thi bo")
    van kiem duoc dieu no dinh kiem. Vector ngau nhien se lam cac test do thanh
    tung xu.

    Khong mang y nghia ngu nghia: hai cau CUNG Y nhung khac chu se ra hai vector
    khong lien quan. Do la ly do `fake` chi dung cho test va dev, khong bao gio cho
    du lieu that.
    """

    def __init__(self, dimensions: int = DIMENSIONS) -> None:
        # Nhan so chieu tu ngoai chu khong lay hang so: bo test tra ve vector 1024
        # chieu trong khi cot la VECTOR(512) thi INSERT hong, ma trieu chung lai
        # trong nhu loi migration.
        self._dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [_hash_vector(t, self._dimensions) for t in texts]


def _hash_vector(text: str, dimensions: int = DIMENSIONS) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    raw = [(digest[i % len(digest)] - 128) / 128.0 for i in range(dimensions)]
    norm = math.sqrt(sum(v * v for v in raw)) or 1.0
    return [v / norm for v in raw]


#: Cache vector cua MOT chuoi ngan (cau hoi, mau `quen`). Section 6.5: TTL 24h.
#:
#: Duong nay chay o MOI TIN NHAN: L3 embed cau hoi de tim fact, va RAG embed no lan
#: nua de tim tai lieu. Trong mot nhom, cung mot cau hoi duoc go lai rat nhieu.
#:
#: Do 07/09/2026 bang `cli stats`: route `embed` co p95 = 19,9s tren tran timeout 20s.
#: Cache khong chi tiet kiem tien — no bo hang mot vong mang ra khoi duong phan hoi.
#:
#: Khoa bam CA ten model va so chieu: doi model ma dung chung khoa la doc ra vector
#: cua model cu, va ket qua sai mot cach hoan toan im lang.
_QUERY_CACHE_TTL_SECONDS = 86_400


async def embed_query(text: str) -> list[float]:
    """Vector cua mot chuoi, co cache Redis. Redis hong thi embed lai."""
    import hashlib
    import json

    from infra.redis_client import aw, get_redis

    config = embedding_config()
    digest = hashlib.sha256(f"{config.model}:{config.dimensions}:{text}".encode()).hexdigest()
    key = f"emb:{digest}"

    try:
        cached = await aw(get_redis().get(key))
        if cached:
            vector: list[float] = json.loads(cached)
            if len(vector) == config.dimensions:
                return vector
    except Exception as error:
        _log.warning("doc cache embedding that bai, embed lai", err=str(error))

    fresh = (await get_embedder().embed([text]))[0]
    try:
        await aw(get_redis().set(key, json.dumps(fresh), ex=_QUERY_CACHE_TTL_SECONDS))
    except Exception as error:
        _log.warning("khong ghi duoc cache embedding, bo qua", err=str(error))
    return fresh


_embedder: EmbedderPort | None = None


def get_embedder() -> EmbedderPort:
    """Chon theo EMBEDDING_PROVIDER. Day la NOI DUY NHAT quyet dinh dung ban nao.

    Tao LUOI luc goi dau tien, khong phai luc import: doc config ngay khi import
    module bien moi lan `import` thanh mot cho co the chet vi thieu bien moi truong,
    ke ca trong test khong dung toi embedding.
    """
    global _embedder
    if _embedder is None:
        settings = get_settings()
        provider = settings.EMBEDDING_PROVIDER.lower()
        if provider == "openai":
            _embedder = OpenAiEmbedder()
        else:
            _log.warning(
                "EMBEDDING_PROVIDER khong phai 'openai' — dung embedder GIA. "
                "Fact van luu duoc nhung chong trung va truy xuat theo y nghia se VO NGHIA.",
                provider=provider,
            )
            _embedder = FakeEmbedder(dimensions=settings.EMBEDDING_DIM)
    return _embedder
