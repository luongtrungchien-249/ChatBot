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
from typing import Protocol

from config import get_settings
from infra.logger import get_logger

from .cost_meter import record_embedding

_log = get_logger()

#: Phai KHOP cot VECTOR(n) trong db/migrations. Lech thi Postgres tu choi luc INSERT.
#: main/container.py kiem tra dieu nay luc khoi dong.
DIMENSIONS = 1024

_MODEL = "text-embedding-3-large"


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

#: USD / 1M token. text-embedding-3-large, 06/09/2026.
PRICE_PER_MILLION = 0.13


class OpenAiEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        from openai import AsyncOpenAI

        # EMBEDDING_API_KEY chi can khi nha cung cap embedding KHAC nha cung cap LLM.
        # Voi OpenAI thi cung mot khoa, nen khong bat nguoi dung dien hai lan.
        settings = get_settings()
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            max_retries=EMBED_MAX_RETRIES,
            timeout=EMBED_TIMEOUT_S,
        )

        started = time.monotonic()
        response = await client.embeddings.create(
            model=_MODEL,
            input=texts,
            # Cat ve dung so chieu cua cot. text-embedding-3-* duoc huan luyen theo
            # kieu Matryoshka nen cat bot chieu chi mat rat it chat luong — khac han
            # viec cat mot vector thuong.
            dimensions=DIMENSIONS,
        )
        latency_ms = int((time.monotonic() - started) * 1000)

        # L6: moi loi goi ra ngoai deu duoc do cost. Thieu buoc nay thi tien embedding
        # KHONG nam trong chot chan DAILY_BUDGET_USD — va L3 embed o moi tin nhan,
        # nen do la mot dong chi khong ai nhin thay.
        tokens = response.usage.total_tokens if response.usage else 0
        await record_embedding(
            model=_MODEL,
            tokens=tokens,
            cost_usd=tokens * PRICE_PER_MILLION / 1_000_000,
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

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [_hash_vector(t) for t in texts]


def _hash_vector(text: str, dimensions: int = DIMENSIONS) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    raw = [(digest[i % len(digest)] - 128) / 128.0 for i in range(dimensions)]
    norm = math.sqrt(sum(v * v for v in raw)) or 1.0
    return [v / norm for v in raw]


_embedder: EmbedderPort | None = None


def get_embedder() -> EmbedderPort:
    """Chon theo EMBEDDING_PROVIDER. Day la NOI DUY NHAT quyet dinh dung ban nao.

    Tao LUOI luc goi dau tien, khong phai luc import: doc config ngay khi import
    module bien moi lan `import` thanh mot cho co the chet vi thieu bien moi truong,
    ke ca trong test khong dung toi embedding.
    """
    global _embedder
    if _embedder is None:
        provider = get_settings().EMBEDDING_PROVIDER.lower()
        if provider == "openai":
            _embedder = OpenAiEmbedder()
        else:
            _log.warning(
                "EMBEDDING_PROVIDER khong phai 'openai' — dung embedder GIA. "
                "Fact van luu duoc nhung chong trung va truy xuat theo y nghia se VO NGHIA.",
                provider=provider,
            )
            _embedder = FakeEmbedder()
    return _embedder
