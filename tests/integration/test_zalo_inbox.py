import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from arq import create_pool
from arq.constants import job_key_prefix, result_key_prefix

from adapters.web.normalize import normalize_web_input
from infra import zalo_inbox
from infra.db import get_pool
from infra.queue import job_id_for, redis_settings, to_payload


async def test_receipt_song_qua_enqueue_failure_va_replay_khong_trung(
    postgres_san_sang: None,
    monkeypatch: Any,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as connection:
        # Shadow only on this connection; never dispatch existing user receipts.
        await connection.execute(
            "CREATE TEMP TABLE zalo_inbox (LIKE public.zalo_inbox INCLUDING ALL)"
        )

        @asynccontextmanager
        async def isolated_transaction() -> AsyncIterator[Any]:
            async with connection.transaction():
                yield connection

        monkeypatch.setattr(zalo_inbox, "transaction", isolated_transaction)
        monkeypatch.setattr(zalo_inbox, "execute", connection.execute)
        enqueue = AsyncMock(side_effect=[ConnectionError("Redis unavailable"), None])
        monkeypatch.setattr(zalo_inbox, "enqueue_reply", enqueue)
        msg = replace(
            normalize_web_input(uuid.uuid4().hex, "private text", user_id="u", display_name="U"),
            platform="zalo_bot",
        )
        try:
            await zalo_inbox.save_receipt(msg)
            with pytest.raises(ConnectionError):
                await zalo_inbox.replay_pending()
            row = await connection.fetchrow("SELECT * FROM zalo_inbox")
            assert row["queued_at"] is None
            assert row["payload"] is not None
            assert await zalo_inbox.replay_pending() == 1
            await zalo_inbox.save_receipt(msg)
            assert await zalo_inbox.replay_pending() == 0
            row = await connection.fetchrow("SELECT * FROM zalo_inbox")
            assert row["payload"] is None
            assert row["queued_at"] is not None
            assert enqueue.await_args_list[0] == enqueue.await_args_list[1]
        finally:
            await connection.execute("DROP TABLE pg_temp.zalo_inbox")


async def test_crash_apres_enqueue_avant_commit_ne_cree_qu_un_job(
    postgres_san_sang: None, redis_san_sang: None, monkeypatch: Any
) -> None:
    queue = await create_pool(redis_settings())
    isolated_queue = f"test-inbox-{uuid.uuid4().hex}"
    msg = replace(
        normalize_web_input(uuid.uuid4().hex, "synthetic receipt", user_id="u", display_name="U"),
        platform="zalo_bot",
    )
    job_id = job_id_for(msg.platform, msg.message_id)
    pool = await get_pool()
    async with pool.acquire() as connection:
        await connection.execute(
            "CREATE TEMP TABLE zalo_inbox (LIKE public.zalo_inbox INCLUDING ALL)"
        )
        enqueue_results: list[Any] = []

        async def enqueue(receipt: Any) -> None:
            enqueue_results.append(
                await queue.enqueue_job(
                    "handle_reply", to_payload(receipt), _job_id=job_id, _queue_name=isolated_queue
                )
            )

        class CrashBeforeCommit:
            async def fetch(self, sql: str, *args: Any) -> Any:
                return await connection.fetch(sql, *args)

            async def execute(self, sql: str, *args: Any) -> Any:
                raise RuntimeError("simulated crash after Redis acceptance")

        @asynccontextmanager
        async def crash_transaction() -> AsyncIterator[Any]:
            async with connection.transaction():
                yield CrashBeforeCommit()

        @asynccontextmanager
        async def recovered_transaction() -> AsyncIterator[Any]:
            async with connection.transaction():
                yield connection

        monkeypatch.setattr(zalo_inbox, "execute", connection.execute)
        monkeypatch.setattr(zalo_inbox, "enqueue_reply", enqueue)
        monkeypatch.setattr(zalo_inbox, "transaction", crash_transaction)
        try:
            await zalo_inbox.save_receipt(msg)
            with pytest.raises(RuntimeError, match="simulated crash"):
                await zalo_inbox.replay_pending()
            assert await queue.zcard(isolated_queue) == 1
            assert await connection.fetchval("SELECT queued_at IS NULL FROM zalo_inbox")
            monkeypatch.setattr(zalo_inbox, "transaction", recovered_transaction)
            assert await zalo_inbox.replay_pending() == 1
            assert enqueue_results[0] is not None
            assert enqueue_results[1] is None  # Real ARQ deduplication, not a mock.
            assert await queue.zcard(isolated_queue) == 1
            assert await connection.fetchval("SELECT payload IS NULL FROM zalo_inbox")
        finally:
            await connection.execute("DROP TABLE pg_temp.zalo_inbox")
            # Only this test's isolated queue/job; never clear a shared queue.
            await queue.delete(isolated_queue, job_key_prefix + job_id, result_key_prefix + job_id)
            await queue.aclose()
