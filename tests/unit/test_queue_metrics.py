import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from arq.jobs import serialize_job

from infra import queue_metrics


def payload(enqueue: int) -> bytes:
    return serialize_job("handle_reply", ({"text": "private"},), {}, 1, enqueue)


@pytest.mark.parametrize(
    "scenario", ["empty", "old", "future", "missing", "invalid", "limit", "outage"]
)
async def test_original_enqueue_age_bounded_and_fail_unknown(
    monkeypatch: Any, scenario: str
) -> None:
    identifiers = [] if scenario == "empty" else [b"new", b"old-deferred"]
    if scenario == "limit":
        identifiers = [b"job"] * 10001
    queue = SimpleNamespace(
        zrange=AsyncMock(return_value=identifiers),
        mget=AsyncMock(return_value=[payload(995_000), payload(900_000)]),
        job_deserializer=None,
    )
    if scenario == "future":
        queue.mget.return_value = [payload(1001_000), payload(1002_000)]
    elif scenario == "missing":
        queue.mget.return_value = [payload(995_000), None]
    elif scenario == "invalid":
        queue.mget.return_value = [b"invalid", payload(900_000)]
    elif scenario == "outage":
        queue.zrange.side_effect = ConnectionError()
    monkeypatch.setattr(queue_metrics, "get_queue", AsyncMock(return_value=queue))
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    result = await queue_metrics.queue_age("reply")
    assert result.complete == (scenario in {"empty", "old", "future"})
    assert result.oldest_seconds == ({"empty": 0.0, "old": 100.0, "future": 0.0}.get(scenario))
    queue.zrange.assert_awaited_once_with("reply", 0, 10000)
