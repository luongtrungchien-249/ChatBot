"""Client Redis dung chung cho cache va khoa (dedupe, ratelimit, ctx, pub/sub).

Ten file la redis_client.py chu khong phai redis.py: dat trung ten goi se che mat
package `redis` that va gay ImportError vong tron.
"""

from collections.abc import Awaitable
from typing import TypeVar

from redis.asyncio import Redis

from config import get_settings

_T = TypeVar("_T")
_client: Redis | None = None


async def aw(value: Awaitable[_T] | _T) -> _T:
    """Go union `Awaitable[T] | T` cua redis-py.

    redis-py dung CHUNG mot base class cho ban dong bo va bat dong bo, nen stub khai
    kieu tra ve la union. O ban async thi luon la awaitable, nhung mypy khong biet
    dieu do. Helper nay noi ro y dinh, thay vi rai cast() khap noi.
    """
    if isinstance(value, Awaitable):
        return await value
    return value


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(
            get_settings().REDIS_URL,
            decode_responses=True,
            health_check_interval=30,
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
