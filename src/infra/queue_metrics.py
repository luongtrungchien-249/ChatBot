"""Read ARQ enqueue timestamps, not retry/deferred sorted-set scores."""

import asyncio
import time
from dataclasses import dataclass

from arq.constants import job_key_prefix
from arq.jobs import deserialize_job_raw

from .queue import get_queue

_MAX_JOBS = 10_000
_BATCH = 500


@dataclass(frozen=True, slots=True)
class QueueAge:
    oldest_seconds: float | None
    complete: bool


async def queue_age(queue_name: str) -> QueueAge:
    """Bound work per scrape; omit age instead of inventing zero on gaps.

    In-progress/deferred jobs remain included, like cp_queue_depth. Redis must
    have the same trusted/private write boundary as ARQ workers: ARQ's own
    serializer can use pickle. No IDs, args or payloads are logged/exported.
    """
    try:
        async with asyncio.timeout(2):
            queue = await get_queue()
            identifiers = await queue.zrange(queue_name, 0, _MAX_JOBS)
            if len(identifiers) > _MAX_JOBS:
                return QueueAge(None, False)
            if not identifiers:
                return QueueAge(0.0, True)
            earliest: int | None = None
            for start in range(0, len(identifiers), _BATCH):
                keys = [
                    job_key_prefix + key.decode()
                    if isinstance(key, bytes)
                    else job_key_prefix + key
                    for key in identifiers[start : start + _BATCH]
                ]
                payloads = await queue.mget(keys)
                for payload in payloads:
                    if payload is None:
                        # Job may have finished during this non-atomic snapshot.
                        return QueueAge(None, False)
                    *_, enqueue_ms = deserialize_job_raw(
                        payload,
                        deserializer=queue.job_deserializer,
                    )
                    if type(enqueue_ms) is not int or enqueue_ms < 0:
                        return QueueAge(None, False)
                    earliest = enqueue_ms if earliest is None else min(earliest, enqueue_ms)
            if earliest is None:
                return QueueAge(None, False)
            return QueueAge(max(0.0, time.time() - earliest / 1000), True)
    except Exception:
        return QueueAge(None, False)
