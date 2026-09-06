"""Chong trung tin nhan va chong gui tra loi hai lan.

SET NX la ATOMIC. Tuyet doi khong viet GET roi SET: hai webhook cua Meta ve cung
luc se cung thay "chua co" va bot tra loi hai lan.

Day la lop 1. Lop 2 la job_id cua hang doi, lop 3 la khoa chinh
(platform, message_id) cua bang inbound_message — song lau hon TTL Redis.
"""

from agents.domain.thread import Platform

from .redis_client import get_redis

_DEDUP_TTL_SECONDS = 600  # 10 phut, xem section 6.5
_REPLIED_TTL_SECONDS = 3600  # 1 gio


def _dedup_key(platform: Platform, message_id: str) -> str:
    return f"dedup:{platform}:{message_id}"


def _replied_key(platform: Platform, message_id: str) -> str:
    return f"replied:{platform}:{message_id}"


async def claim(platform: Platform, message_id: str) -> bool:
    """True = ban gianh duoc quyen xu ly tin nay. False = ai do da gianh truoc."""
    result = await get_redis().set(
        _dedup_key(platform, message_id), "1", ex=_DEDUP_TTL_SECONDS, nx=True
    )
    return bool(result)


async def mark_replied(platform: Platform, message_id: str) -> None:
    """Danh dau da tra loi. Phai goi TRUOC khi cho phep retry.

    Thieu co nay, mot su co 5xx bien thanh bot spam nhom — dung cai lam nguoi ta
    kick bot ra (ARCHITECTURE.md section 9).
    """
    await get_redis().set(_replied_key(platform, message_id), "1", ex=_REPLIED_TTL_SECONDS)


async def has_replied(platform: Platform, message_id: str) -> bool:
    return bool(await get_redis().exists(_replied_key(platform, message_id)) == 1)
