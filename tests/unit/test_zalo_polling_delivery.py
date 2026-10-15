import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from adapters.zalo_bot import polling


async def test_enqueue_loi_van_co_the_thu_lai_cung_update(monkeypatch: Any) -> None:
    fixture = Path(__file__).resolve().parents[1] / "contract/fixtures/zalo_bot/private_text.json"
    body = json.loads(fixture.read_text(encoding="utf-8"))
    update = body.get("result", body)
    enqueue = AsyncMock(side_effect=[ConnectionError("queue down"), 1])
    monkeypatch.setattr(polling, "save_receipt", AsyncMock())
    monkeypatch.setattr(polling, "replay_pending", enqueue)

    with pytest.raises(ConnectionError):
        await polling.ingest(update, "bot-id")
    assert await polling.ingest(update, "bot-id")
    assert enqueue.await_count == 2


async def test_receipt_duoc_luu_truoc_heartbeat_loi(monkeypatch: Any) -> None:
    fixture = Path(__file__).resolve().parents[1] / "contract/fixtures/zalo_bot/private_text.json"
    body = json.loads(fixture.read_text(encoding="utf-8"))
    events: list[str] = []

    async def save(_msg: Any) -> None:
        events.append("saved")

    async def failed_heartbeat(_component: str) -> None:
        events.append("heartbeat")
        raise ConnectionError("Redis unavailable")

    monkeypatch.setattr(polling, "get_me", AsyncMock(return_value={"id": "bot-id"}))
    monkeypatch.setattr(
        polling,
        "get_updates",
        AsyncMock(side_effect=[body.get("result", body), asyncio.CancelledError()]),
    )
    monkeypatch.setattr(polling, "save_receipt", save)
    monkeypatch.setattr(polling, "replay_pending", AsyncMock(return_value=0))
    monkeypatch.setattr(polling, "heartbeat", failed_heartbeat)
    backoff = AsyncMock()
    monkeypatch.setattr(polling, "_backoff", backoff)

    with pytest.raises(asyncio.CancelledError):
        await polling.poll_forever()

    assert events == ["saved", "heartbeat"]
    backoff.assert_awaited_once()
