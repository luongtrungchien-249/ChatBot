from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import httpx
from fastapi import FastAPI

from adapters.web import routes
from adapters.web.auth import WebIdentity, require_identity


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[require_identity] = lambda: WebIdentity(
        "owner", "Owner", frozenset({"user"}), "test",
    )
    return app


async def test_oversized_http_input_is_rejected_before_enqueue(monkeypatch: Any) -> None:
    enqueue = AsyncMock()
    monkeypatch.setattr(routes, "enqueue_reply", enqueue)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://localhost",
    ) as client:
        result = await client.post("/api/chat", json={"threadId": "t", "text": "x" * 28_801})
    assert result.status_code == 422
    enqueue.assert_not_awaited()


async def test_legacy_bot_secrets_are_masked_and_own_pii_uses_exact_reply(monkeypatch: Any) -> None:
    monkeypatch.setattr(routes, "is_owner", AsyncMock(return_value=True))
    now = datetime.now(UTC)
    rows = [
        {"message_id": "user-1", "reply_to_id": None, "from_bot": False,
         "text": "my email own@example.invalid", "created_at": now},
        {"message_id": "user-2", "reply_to_id": None, "from_bot": False,
         "text": "later question", "created_at": now},
        {"message_id": "bot-1", "reply_to_id": "user-1", "from_bot": True,
         "text": "own@example.invalid sk-FAKE_REVIEW_ONLY_1234567890", "created_at": now},
        {"message_id": "bot-2", "reply_to_id": "user-2", "from_bot": True,
         "text": "own@example.invalid", "created_at": now},
    ]
    monkeypatch.setattr(routes, "fetch", AsyncMock(return_value=rows))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://localhost",
    ) as client:
        result = await client.get("/api/threads/t/messages")
    assert result.status_code == 200
    messages = result.json()
    assert "sk-FAKE" not in messages[2]["text"]
    assert "own@example.invalid" in messages[0]["text"]
    assert "own@example.invalid" in messages[2]["text"]
    assert "own@example.invalid" not in messages[3]["text"]
