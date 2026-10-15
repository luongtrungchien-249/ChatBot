from typing import Any
from unittest.mock import AsyncMock
from urllib.parse import quote

import httpx
import pytest
from fastapi import FastAPI

from adapters.web import routes
from adapters.web.auth import WebIdentity, require_identity


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/api/threads/b/messages", None),
        ("GET", "/api/stream/b", None),
        ("PATCH", "/api/threads/b", {"title": "stolen"}),
        ("DELETE", "/api/threads/b", None),
        ("DELETE", "/api/threads/b/data", None),
        ("POST", "/api/threads/b/stop", None),
        ("POST", "/api/threads/b", None),
        ("POST", "/api/chat", {"threadId": "b", "text": "attack"}),
    ],
)
async def test_user_a_khong_truy_cap_thread_b(
    monkeypatch: Any,
    method: str,
    path: str,
    body: dict[str, str] | None,
) -> None:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[require_identity] = lambda: WebIdentity(
        "a", "User A", frozenset({"user", "operator"}), "test"
    )
    monkeypatch.setattr(routes, "is_owner", AsyncMock(return_value=False))
    monkeypatch.setattr(routes, "claim_new_or_check_owner", AsyncMock(return_value=False))
    fetch = AsyncMock(side_effect=AssertionError("content query before authorization"))
    subscribe = AsyncMock(side_effect=AssertionError("subscribe before authorization"))
    monkeypatch.setattr(routes, "fetch", fetch)
    monkeypatch.setattr(routes, "_sse_stream", subscribe)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        response = await client.request(method, path, json=body)
    assert response.status_code == 404
    fetch.assert_not_called()
    subscribe.assert_not_called()


@pytest.mark.parametrize("thread_id", ["a:b", "*", "bad[id]", "a?", "a" * 201])
async def test_web_thread_id_ne_peut_pas_manipuler_cles_redis(thread_id: str) -> None:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[require_identity] = lambda: WebIdentity(
        "a", "User A", frozenset({"user"}), "test"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        response = await client.post("/api/chat", json={"threadId": thread_id, "text": "question"})
        assert response.status_code == 422
        response = await client.post(f"/api/threads/{quote(thread_id, safe='')}")
        assert response.status_code == 422
