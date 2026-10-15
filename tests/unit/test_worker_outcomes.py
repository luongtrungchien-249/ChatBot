import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import pytest
from arq import Retry

from adapters.web.normalize import normalize_web_input
from agents.domain.errors import UpstreamError
from agents.domain.telemetry import GenerationStats, TurnDetails
from agents.pipeline.handle_message import Failed, Handled
from infra.queue import to_payload
from main import worker


@pytest.fixture(autouse=True)
def mock_thread_guard(monkeypatch: Any) -> None:
    @asynccontextmanager
    async def guard(*args: Any) -> AsyncIterator[bool]:
        yield True

    monkeypatch.setattr(worker, "web_job_guard", guard)


async def test_nonretryable_pipeline_failure_mesure_error(monkeypatch: Any) -> None:
    msg = normalize_web_input("t", "question", user_id="u", display_name="U")
    monkeypatch.setattr(worker, "has_replied", AsyncMock(return_value=False))
    monkeypatch.setattr(worker, "clear_cancel", AsyncMock())
    monkeypatch.setattr(worker, "mark_replied", AsyncMock())
    monkeypatch.setattr(worker, "build_deps", AsyncMock(return_value=object()))
    monkeypatch.setattr(worker, "_with_runtime_hooks", lambda *args: args[0])
    monkeypatch.setattr(
        worker,
        "handle_message",
        AsyncMock(return_value=Failed(UpstreamError("llm", 401), replied=True)),
    )
    record = AsyncMock()
    monkeypatch.setattr(worker, "record_turn", record)

    await worker.handle_reply({}, to_payload(msg))

    assert record.await_args is not None
    assert record.await_args.args[2] == "error"


async def test_duplicate_job_ne_remplace_pas_mesure_terminee(monkeypatch: Any) -> None:
    msg = normalize_web_input("t", "question", user_id="u", display_name="U")
    monkeypatch.setattr(worker, "has_replied", AsyncMock(return_value=True))
    record = AsyncMock()
    monkeypatch.setattr(worker, "record_turn", record)

    await worker.handle_reply({}, to_payload(msg))

    record.assert_not_awaited()


async def test_cancelled_worker_ne_signale_pas_un_succes(monkeypatch: Any) -> None:
    msg = normalize_web_input("t", "question", user_id="u", display_name="U")
    monkeypatch.setattr(worker, "_handle_reply", AsyncMock(side_effect=asyncio.CancelledError()))
    record = AsyncMock()
    monkeypatch.setattr(worker, "record_turn", record)

    with pytest.raises(asyncio.CancelledError):
        await worker.handle_reply({}, to_payload(msg))

    assert record.await_args is not None
    assert record.await_args.args[2] == "error"


@pytest.mark.parametrize(
    "attempt,replied,should_retry", [(1, False, True), (1, True, False), (3, False, False)]
)
async def test_upstream_retry_dung_signal_arq_va_khong_gui_lap(
    monkeypatch: Any, attempt: int, replied: bool, should_retry: bool
) -> None:
    msg = normalize_web_input("t", "question", user_id="u", display_name="U")
    monkeypatch.setattr(worker, "has_replied", AsyncMock(return_value=False))
    monkeypatch.setattr(worker, "clear_cancel", AsyncMock())
    marker = AsyncMock()
    monkeypatch.setattr(worker, "mark_replied", marker)
    monkeypatch.setattr(worker, "build_deps", AsyncMock(return_value=object()))
    monkeypatch.setattr(worker, "_with_runtime_hooks", lambda *args: args[0])
    monkeypatch.setattr(
        worker,
        "handle_message",
        AsyncMock(return_value=Failed(UpstreamError("llm", 503), replied=replied)),
    )
    monkeypatch.setattr(worker, "record_turn", AsyncMock())
    if should_retry:
        with pytest.raises(Retry):
            await worker.handle_reply({"job_try": attempt}, to_payload(msg))
    else:
        await worker.handle_reply({"job_try": attempt}, to_payload(msg))
    assert marker.await_count == int(replied)


@pytest.mark.parametrize("success,attempt", [(True, 1), (False, 1), (False, 3)])
async def test_worker_preserve_details_y_compris_retry(
    monkeypatch: Any, success: bool, attempt: int
) -> None:
    msg = normalize_web_input("t", "question", user_id="u", display_name="U")
    replied = success or attempt == 3
    details = TurnDetails(
        "answer" if success else "error",
        not success and replied,
        GenerationStats("answer" if success else "error", 2, 1, 1),
    )
    result = (
        Handled(replied=True, telemetry=details)
        if success
        else Failed(UpstreamError("llm", 503), replied=replied, telemetry=details)
    )
    for name in ("clear_cancel", "mark_replied"):
        monkeypatch.setattr(worker, name, AsyncMock())
    monkeypatch.setattr(worker, "has_replied", AsyncMock(return_value=False))
    monkeypatch.setattr(worker, "build_deps", AsyncMock(return_value=object()))
    monkeypatch.setattr(worker, "_with_runtime_hooks", lambda *args: args[0])
    monkeypatch.setattr(worker, "handle_message", AsyncMock(return_value=result))
    record = AsyncMock()
    monkeypatch.setattr(worker, "record_turn", record)
    if not success and not replied:
        with pytest.raises(Retry):
            await worker.handle_reply({"job_try": attempt}, to_payload(msg))
    else:
        await worker.handle_reply({"job_try": attempt}, to_payload(msg))
    assert record.await_args is not None
    assert record.await_args.kwargs == {"details": details, "replied": replied}
