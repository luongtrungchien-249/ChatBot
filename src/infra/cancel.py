"""Co huy: nguoi dung bam dung giua chung.

Phai di qua Redis chu khong phai bien trong bo nho, vi `api` va `worker` la HAI
PROCESS khac nhau — nguoi dung bam nut o api, con vong ReAct chay o worker.

TTL ngan: co nay chi co nghia trong luc mot cau hoi dang chay. Sot lai mot co cu se
lam cau hoi TIEP THEO bi huy oan, nen tha het han som con hon.
"""

from agents.domain.thread import ThreadScope

from .redis_client import get_redis

_CANCEL_TTL_SECONDS = 180


def _cancel_key(scope: ThreadScope) -> str:
    return f"cancel:{scope.platform}:{scope.thread_id}"


async def request_cancel(scope: ThreadScope) -> None:
    await get_redis().set(_cancel_key(scope), "1", ex=_CANCEL_TTL_SECONDS)


async def is_cancelled(scope: ThreadScope) -> bool:
    return bool(await get_redis().exists(_cancel_key(scope)) == 1)


async def clear_cancel(scope: ThreadScope) -> None:
    """Xoa co sau khi xu ly xong mot tin — de tin sau khong bi huy oan."""
    await get_redis().delete(_cancel_key(scope))
