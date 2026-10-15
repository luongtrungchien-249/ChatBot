import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from adapters.web.normalize import normalize_web_input
from agents.domain.thread import ThreadScope
from infra.db import execute
from infra.queue import to_payload
from infra.thread_lifecycle import ThreadBusyError, generation_for, web_job_guard
from main import worker
from memory.repository.thread_repo import delete_thread


async def test_delete_refuse_writer_actif_et_invalide_job_ancien(postgres_san_sang: None) -> None:
    scope = ThreadScope("web", f"lifecycle-{uuid.uuid4().hex}")
    epoch = await generation_for(scope)
    try:
        async with web_job_guard(scope, epoch) as valid:
            assert valid
            with pytest.raises(ThreadBusyError):
                await delete_thread(scope, "all_data")
            assert await generation_for(scope) == epoch
        await delete_thread(scope, "all_data")
        async with web_job_guard(scope, epoch) as valid:
            assert not valid
        current = await generation_for(scope)
        assert current == epoch + 1
        async with web_job_guard(scope, current) as valid:
            assert valid
    finally:
        await execute("DELETE FROM web_thread_generation WHERE thread_id=$1", scope.thread_id)


async def test_reply_et_maintenance_obsolete_ne_touche_pas_pipeline(
    postgres_san_sang: None, monkeypatch: Any
) -> None:
    scope = ThreadScope("web", f"stale-{uuid.uuid4().hex}")
    epoch = await generation_for(scope)
    msg = normalize_web_input(scope.thread_id, "deleted question", user_id="u", display_name="U")
    process = AsyncMock(side_effect=AssertionError("obsolete reply must not run"))
    summarize = AsyncMock(side_effect=AssertionError("obsolete maintenance must not run"))
    record = AsyncMock()
    monkeypatch.setattr(worker, "_process_reply", process)
    monkeypatch.setattr(worker, "summarize_thread", summarize)
    monkeypatch.setattr(worker, "record_turn", record)
    try:
        await delete_thread(scope, "all_data")
        await worker.handle_reply({}, {**to_payload(msg), "_thread_generation": epoch})
        await worker.handle_summarize(
            {}, {"platform": "web", "thread_id": scope.thread_id, "_thread_generation": epoch}
        )
        process.assert_not_awaited()
        summarize.assert_not_awaited()
        record.assert_not_awaited()
    finally:
        await execute("DELETE FROM web_thread_generation WHERE thread_id=$1", scope.thread_id)
