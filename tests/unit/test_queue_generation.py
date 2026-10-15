from typing import Any
from unittest.mock import AsyncMock

from adapters.web.normalize import normalize_web_input
from infra import queue


async def test_web_job_envelope_capture_generation(monkeypatch: Any) -> None:
    msg = normalize_web_input("t", "question", user_id="u", display_name="U")
    redis = AsyncMock()
    monkeypatch.setattr(queue, "generation_for", AsyncMock(return_value=7))
    monkeypatch.setattr(queue, "get_queue", AsyncMock(return_value=redis))
    await queue.enqueue_reply(msg)
    assert redis.enqueue_job.await_args is not None
    payload = redis.enqueue_job.await_args.args[1]
    assert payload["_thread_generation"] == 7
    assert queue.from_payload(payload) == msg


async def test_maintenance_job_id_separe_generations(monkeypatch: Any) -> None:
    redis = AsyncMock()
    monkeypatch.setattr(queue, "generation_for", AsyncMock(side_effect=[7, 8]))
    monkeypatch.setattr(queue, "get_queue", AsyncMock(return_value=redis))
    await queue.enqueue_summarize("web", "t")
    await queue.enqueue_summarize("web", "t")
    calls = redis.enqueue_job.await_args_list
    assert calls[0].kwargs["_job_id"] == "sum-web-t-g7"
    assert calls[1].kwargs["_job_id"] == "sum-web-t-g8"
