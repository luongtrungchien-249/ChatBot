"""Hang doi ARQ.

Ba queue TACH BIET. Khong tron: mot job ingest 10 phut khong duoc phep chan mot
cau tra loi.

FIFO theo thread
----------------
ARQ khong co khai niem "group" — tuc la khong co cach khai bao "cac job cung
thread_id phai chay tuan tu". Khong co FIFO per-thread thi hai tin lien tiep trong
mot nhom chay song song va bot TRA LOI SAI THU TU.

Giai phap: worker chay `max_jobs=1` — tuan tu toan cuc. Tran thong luong ~240
cau/gio o truong hop xau nhat (timeout 15s moi cau), trong khi muc tieu la
200-1000 cau mot NGAY. Khi nao cham tran thi tu khoa phan tan per-thread bang
Redis. Khong giai quyet som mot van de chua co.
"""

from dataclasses import asdict
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from agents.domain.message import Attachment, InboundMessage, ReplyTo
from agents.domain.thread import Platform
from config import get_settings

QUEUE_REPLY = "reply"
QUEUE_MAINTENANCE = "maintenance"
QUEUE_INGEST = "ingest"

#: Xem giai thich FIFO o docstring dau file.
REPLY_CONCURRENCY = 1

_pool: ArqRedis | None = None


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().REDIS_URL)


async def get_queue() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings())
    return _pool


def job_id_for(platform: Platform, message_id: str) -> str:
    """job_id = khoa chinh cua tin nhan. Lop chong trung thu HAI, sau SET NX o dedupe.

    Dung '-' chu KHONG dung ':' — mot so hang doi dung ':' lam phan cach khoa Redis
    va tu choi job_id chua no. Cac khoa Redis khac trong du an van dung ':' binh
    thuong; rang buoc nay chi cua rieng job_id.
    """
    return f"{platform}-{message_id}"


def to_payload(msg: InboundMessage) -> dict[str, Any]:
    """Dataclass -> dict de ARQ serialize duoc."""
    return asdict(msg)


def from_payload(data: dict[str, Any]) -> InboundMessage:
    reply_to = data.get("reply_to")
    attachments = data.get("attachments") or ()
    return InboundMessage(
        **{
            **data,
            "reply_to": ReplyTo(**reply_to) if reply_to else None,
            "attachments": tuple(Attachment(**a) for a in attachments),
        }
    )


async def enqueue_reply(msg: InboundMessage) -> None:
    queue = await get_queue()
    await queue.enqueue_job(
        "handle_reply",
        to_payload(msg),
        _job_id=job_id_for(msg.platform, msg.message_id),
        _queue_name=QUEUE_REPLY,
    )


async def enqueue_summarize(platform: Platform, thread_id: str) -> None:
    """Xep hang viec nen L2. Chay tren queue `maintenance`, KHONG phai `reply`.

    job_id theo thread: hai luot lien tiep trong cung mot nhom khong tao hai job nen.
    Chong trung o day chi la BEST-EFFORT (job da xong thi id duoc giai phong), nen
    ban than job phai chiu duoc viec chay thua — no bat dau bang mot cau COUNT va
    thoat ngay khi chua du nguong.
    """
    queue = await get_queue()
    await queue.enqueue_job(
        "handle_summarize",
        {"platform": platform, "thread_id": thread_id},
        _job_id=f"sum-{platform}-{thread_id}",
        _queue_name=QUEUE_MAINTENANCE,
    )


async def close_queue() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
