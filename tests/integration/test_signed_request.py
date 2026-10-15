import hashlib
import hmac
import time
import uuid
from types import SimpleNamespace
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Request

from adapters.web import auth
from infra.redis_client import aw, get_redis


async def test_signed_body_survives_dependency_and_nonce_shared(
    redis_san_sang: None,
    monkeypatch: Any,
) -> None:
    issuer = "synthetic-issuer"
    secret = "s" * 32
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: SimpleNamespace(
            WEB_AUTH_MODE="trusted_header",
            WEB_AUTH_ISSUER=issuer,
            WEB_AUTH_HEADER_SECRET=secret,
        ),
    )
    apps = [FastAPI(), FastAPI()]
    for app in apps:

        @app.post("/signed", dependencies=[Depends(auth.require_identity)])
        async def echo(request: Request) -> dict[str, object]:
            return {"received": await request.json()}

    nonce = uuid.uuid4().hex
    timestamp = str(int(time.time()))
    body = b'{"text":"synthetic"}'
    canonical = auth._canonical(
        "synthetic-user",
        "User",
        "user",
        issuer,
        timestamp,
        nonce,
        "POST",
        b"/signed",
        b"a=1",
        body,
    )
    headers = {
        "x-cp-user-id": "synthetic-user",
        "x-cp-display-name": "User",
        "x-cp-roles": "user",
        "x-cp-issuer": issuer,
        "x-cp-timestamp": timestamp,
        "x-cp-nonce": nonce,
        "x-cp-signature": hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest(),
        "content-type": "application/json",
    }
    key = "web-auth:nonce:" + hashlib.sha256(f"{issuer}:{nonce}".encode()).hexdigest()
    try:
        for index, app in enumerate(apps):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://test"
            ) as client:
                response = await client.post("/signed?a=1", content=body, headers=headers)
                assert response.status_code == (200 if index == 0 else 401)
                if index == 0:
                    assert response.json() == {"received": {"text": "synthetic"}}
        assert 0 < await aw(get_redis().ttl(key)) <= 121
    finally:
        await aw(get_redis().delete(key))
