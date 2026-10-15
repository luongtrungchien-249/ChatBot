"""Bien xac thuc Web: dev loopback hoac identity do reverse proxy OIDC ky."""

import asyncio
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

from config import get_settings
from infra.redis_client import aw, get_redis

_MAX_CLOCK_SKEW_SECONDS = 60
_LOOPBACK = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1"})


@dataclass(frozen=True, slots=True)
class WebIdentity:
    user_id: str
    display_name: str
    roles: frozenset[str]
    issuer: str

    def is_operator(self) -> bool:
        return bool(self.roles & {"operator", "admin"})


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="identity khong hop le")


def _canonical(
    user_id: str,
    display_name: str,
    roles: str,
    issuer: str,
    timestamp: str,
    nonce: str,
    method: str,
    raw_path: bytes,
    query: bytes,
    body: bytes,
) -> bytes:
    # JSON framing prevents ambiguous newline fields. Sign exactly what the app
    # receives AFTER proxy rewriting; query order and percent encoding matter.
    return json.dumps(
        [
            "cp-web-v2",
            user_id,
            display_name,
            roles,
            issuer,
            timestamp,
            nonce,
            method,
            raw_path.hex(),
            query.hex(),
            hashlib.sha256(body).hexdigest(),
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")


async def require_identity(request: Request) -> WebIdentity:
    settings = get_settings()
    if settings.WEB_AUTH_MODE == "dev":
        client = request.client.host if request.client else None
        if client not in _LOOPBACK:
            raise _unauthorized()
        return WebIdentity("dev-user", "Developer", frozenset({"user", "operator"}), "dev")

    user_id = request.headers.get("x-cp-user-id", "")
    display_name = request.headers.get("x-cp-display-name", "")
    roles_raw = request.headers.get("x-cp-roles", "")
    issuer = request.headers.get("x-cp-issuer", "")
    timestamp = request.headers.get("x-cp-timestamp", "")
    signature = request.headers.get("x-cp-signature", "")
    nonce = request.headers.get("x-cp-nonce", "")
    if (
        not user_id.strip()
        or len(user_id) > 200
        or len(display_name) > 120
        or len(roles_raw) > 100
        or issuer != settings.WEB_AUTH_ISSUER
        or re.fullmatch(r"[0-9a-f]{32,128}", nonce) is None
        or re.fullmatch(r"[0-9a-f]{64}", signature) is None
        or re.fullmatch(r"[0-9]{1,12}", timestamp) is None
        or any(any(ord(c) < 32 for c in v) for v in (user_id, display_name, roles_raw, issuer))
    ):
        raise _unauthorized()
    try:
        fresh = abs(int(time.time()) - int(timestamp)) <= _MAX_CLOCK_SKEW_SECONDS
    except ValueError:
        fresh = False
    expected = hmac.new(
        settings.WEB_AUTH_HEADER_SECRET.encode(),
        _canonical(
            user_id,
            display_name,
            roles_raw,
            issuer,
            timestamp,
            nonce,
            request.method,
            request.scope["raw_path"],
            request.scope["query_string"],
            await request.body(),
        ),
        hashlib.sha256,
    ).hexdigest()
    if not fresh or not hmac.compare_digest(signature.encode(), expected.encode()):
        raise _unauthorized()
    roles = frozenset(role.strip() for role in roles_raw.split(",") if role.strip())
    if not roles <= {"user", "operator", "admin"}:
        raise _unauthorized()
    # Shared across API replicas. Retain for both past and future timestamp skew;
    # never fail open on Redis loss and never log signed headers or bodies.
    nonce_key = hashlib.sha256(f"{issuer}:{nonce}".encode()).hexdigest()
    try:
        async with asyncio.timeout(2):
            accepted = await aw(
                get_redis().set(
                    f"web-auth:nonce:{nonce_key}",
                    "1",
                    nx=True,
                    ex=2 * _MAX_CLOCK_SKEW_SECONDS + 1,
                )
            )
    except Exception:
        raise HTTPException(status_code=503, detail="xac thuc tam thoi khong san sang") from None
    if not accepted:
        raise _unauthorized()
    return WebIdentity(user_id, display_name or "User", roles or frozenset({"user"}), issuer)


async def require_metrics_access(request: Request) -> None:
    token = get_settings().METRICS_SCRAPE_TOKEN
    authorization = request.headers.get("authorization", "")
    if token and hmac.compare_digest(authorization.encode(), f"Bearer {token}".encode()):
        return
    identity = await require_identity(request)
    if not identity.is_operator():
        raise HTTPException(status_code=403, detail="can quyen operator")
