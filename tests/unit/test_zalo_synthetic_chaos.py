"""Fault scenarios using the real adapter and an in-memory HTTP transport."""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from adapters.zalo_bot import api, polling, send
from agents.domain.thread import ThreadScope


@pytest.mark.parametrize("status", [429, 500])
async def test_send_retry_after_transient_error_preserves_text(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    sent: list[bytes] = []

    def transport(request: httpx.Request) -> httpx.Response:
        sent.append(request.content)
        if len(sent) == 1:
            return httpx.Response(200, json={"ok": False, "error_code": status})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": "synthetic"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        monkeypatch.setattr(api, "get_http", lambda: client)
        monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(ZALO_BOT_TOKEN="fake"))
        pause = AsyncMock()
        monkeypatch.setattr(asyncio, "sleep", pause)
        assert await api.send_message("synthetic", "unchanged text") == "synthetic"
    assert len(sent) == 2 and sent[0] == sent[1]
    pause.assert_awaited_once_with(0.5)


async def test_revoked_token_stops_send_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = 0

    def transport(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json={"ok": False, "error_code": 401})

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        monkeypatch.setattr(api, "get_http", lambda: client)
        monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(ZALO_BOT_TOKEN="fake"))
        with pytest.raises(api.ZaloApiError):
            await api.send_message("synthetic", "text")
    assert requests == 1


async def test_ambiguous_timeout_can_duplicate_remote_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Explicitly records the remaining contract limitation rather than claiming
    # receipt deduplication makes an uncertain remote send exactly-once.
    accepted: list[bytes] = []

    def transport(request: httpx.Request) -> httpx.Response:
        accepted.append(request.content)
        if len(accepted) == 1:
            raise httpx.ReadTimeout("response lost after remote commit")
        return httpx.Response(200, json={"ok": True, "result": {"message_id": "second"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        monkeypatch.setattr(api, "get_http", lambda: client)
        monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(ZALO_BOT_TOKEN="fake"))
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())
        assert await api.send_message("synthetic", "text") == "second"
    assert len(accepted) == 2


async def test_long_reply_chunks_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[str, str]] = []

    async def capture(chat_id: str, text: str) -> str:
        sent.append((chat_id, text))
        return "synthetic"

    monkeypatch.setattr(send, "send_message", capture)
    text = "Một câu thơ thử nghiệm.\n" * 220
    await send.zalo_bot_channel.send(ThreadScope("zalo_bot", "synthetic"), text)
    assert len(sent) > 1
    assert all(chat_id == "synthetic" and 0 < len(part) <= 2000 for chat_id, part in sent)
    assert "".join(part for _, part in sent) == text


async def test_each_poller_restart_replays_before_request(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    async def replay() -> int:
        events.append("replay")
        return 0

    async def receive(*_args: Any) -> None:
        events.append("request")
        raise asyncio.CancelledError()

    monkeypatch.setattr(polling, "get_me", AsyncMock(return_value={"id": "synthetic"}))
    monkeypatch.setattr(polling, "replay_pending", replay)
    monkeypatch.setattr(polling, "get_updates", receive)
    for _ in range(2):
        with pytest.raises(asyncio.CancelledError):
            await polling.poll_forever()
    assert events == ["replay", "request", "replay", "request"]
