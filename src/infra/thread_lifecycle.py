"""Serialize Web writers with deletion; reject work queued before deletion."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from agents.domain.thread import ThreadScope

from .db import fetch, transaction


class ThreadBusyError(Exception):
    """A worker or another lifecycle operation currently owns the Web thread."""


async def lock_web_thread(connection: Any, scope: ThreadScope) -> None:
    if scope.platform != "web":
        return
    acquired = await connection.fetchval(
        "SELECT pg_try_advisory_xact_lock(hashtextextended($1, 0))",
        f"web-write:{scope.thread_id}",
    )
    if not acquired:
        raise ThreadBusyError("thread is currently being processed; retry after it finishes")


async def generation_for(scope: ThreadScope) -> int:
    if scope.platform != "web":
        raise ValueError("generation only applies to Web threads")
    rows = await fetch(
        """INSERT INTO web_thread_generation(thread_id) VALUES($1)
           ON CONFLICT(thread_id) DO UPDATE SET thread_id=EXCLUDED.thread_id
           RETURNING generation""",
        scope.thread_id,
    )
    return int(rows[0]["generation"])


async def read_web_generation(scope: ThreadScope) -> int:
    if scope.platform != "web":
        raise ValueError("generation only applies to Web threads")
    rows = await fetch(
        "SELECT generation FROM web_thread_generation WHERE thread_id=$1", scope.thread_id
    )
    return int(rows[0]["generation"]) if rows else 0


@asynccontextmanager
async def web_job_guard(scope: ThreadScope, expected: int) -> AsyncIterator[bool]:
    if scope.platform != "web":
        yield True
        return
    # Hold only the advisory lock, no row write, while the pipeline writes through
    # its normal repository connections. This avoids self-blocking maintenance enqueue.
    async with transaction() as connection:
        await lock_web_thread(connection, scope)
        current = await connection.fetchval(
            "SELECT generation FROM web_thread_generation WHERE thread_id=$1", scope.thread_id
        )
        yield current is not None and int(current) == expected
