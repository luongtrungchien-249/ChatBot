import hashlib
import hmac
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from adapters.web import auth
from config import get_settings
from config.schema import Settings


class _Request:
    def __init__(self, headers: dict[str, str], host: str = "127.0.0.1") -> None:
        self.headers = headers
        self.client: Any = type("Client", (), {"host": host})()
        self.method = "GET"
        self.scope = {"raw_path": b"/api/threads", "query_string": b""}
        self.content = b""

    async def body(self) -> bytes:
        return self.content


@pytest.fixture(autouse=True)
def nonce_store(monkeypatch: Any) -> AsyncMock:
    redis = AsyncMock()
    redis.set.return_value = True
    monkeypatch.setattr(auth, "get_redis", lambda: redis)
    return redis


def _settings(**overrides: str) -> SimpleNamespace:
    values = {
        "WEB_AUTH_MODE": "trusted_header",
        "WEB_AUTH_ISSUER": "https://sso.example",
        "WEB_AUTH_HEADER_SECRET": "s" * 32,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _signed_headers(*, timestamp: str | None = None) -> dict[str, str]:
    values = {
        "x-cp-user-id": "user-123",
        "x-cp-display-name": "Người dùng",
        "x-cp-roles": "user,operator",
        "x-cp-issuer": "https://sso.example",
        "x-cp-timestamp": timestamp or str(int(time.time())),
        "x-cp-nonce": "a" * 32,
    }
    canonical = auth._canonical(
        values["x-cp-user-id"],
        values["x-cp-display-name"],
        values["x-cp-roles"],
        values["x-cp-issuer"],
        values["x-cp-timestamp"],
        values["x-cp-nonce"],
        "GET",
        b"/api/threads",
        b"",
        b"",
    )
    values["x-cp-signature"] = hmac.new(b"s" * 32, canonical, hashlib.sha256).hexdigest()
    return values


async def test_header_da_ky_tao_identity(monkeypatch: Any) -> None:
    monkeypatch.setattr(auth, "get_settings", _settings)

    identity = await auth.require_identity(_Request(_signed_headers()))  # type: ignore[arg-type]

    assert identity.user_id == "user-123"
    assert identity.display_name == "Người dùng"
    assert identity.is_operator()


@pytest.mark.parametrize("mutation", ["signature", "unicode_signature", "issuer", "expired"])
async def test_header_gia_hoac_replay_bi_tu_choi(monkeypatch: Any, mutation: str) -> None:
    monkeypatch.setattr(auth, "get_settings", _settings)
    headers = _signed_headers(
        timestamp=str(int(time.time()) - 600) if mutation == "expired" else None
    )
    if mutation == "signature":
        headers["x-cp-signature"] = "0" * 64
    elif mutation == "unicode_signature":
        headers["x-cp-signature"] = "chữ ký không hợp lệ"
    elif mutation == "issuer":
        headers["x-cp-issuer"] = "https://attacker.example"

    with pytest.raises(HTTPException) as error:
        await auth.require_identity(_Request(headers))  # type: ignore[arg-type]
    assert error.value.status_code == 401


async def test_dev_identity_chi_nhan_loopback(monkeypatch: Any) -> None:
    monkeypatch.setattr(auth, "get_settings", lambda: _settings(WEB_AUTH_MODE="dev"))

    assert (await auth.require_identity(_Request({}))).user_id == "dev-user"  # type: ignore[arg-type]
    with pytest.raises(HTTPException):
        await auth.require_identity(_Request({}, host="10.0.0.2"))  # type: ignore[arg-type]


@pytest.mark.parametrize("mutation", ["method", "path", "query", "body", "nonce", "roles"])
async def test_signature_bound_to_request(
    monkeypatch: Any, nonce_store: AsyncMock, mutation: str
) -> None:
    monkeypatch.setattr(auth, "get_settings", _settings)
    request = _Request(_signed_headers())
    if mutation == "method":
        request.method = "DELETE"
    elif mutation == "path":
        request.scope["raw_path"] = b"/api/threads/victim"
    elif mutation == "query":
        request.scope["query_string"] = b"mode=all_data"
    elif mutation == "body":
        request.content = b'{"text":"changed"}'
    else:
        request.headers[f"x-cp-{mutation}"] = "b" * 32 if mutation == "nonce" else "admin"
    with pytest.raises(HTTPException) as error:
        await auth.require_identity(request)  # type: ignore[arg-type]
    assert error.value.status_code == 401
    nonce_store.set.assert_not_awaited()


async def test_nonce_consumed_once_and_outage_fails_closed(
    monkeypatch: Any, nonce_store: AsyncMock
) -> None:
    monkeypatch.setattr(auth, "get_settings", _settings)
    nonce_store.set.side_effect = [True, False, ConnectionError()]
    request = _Request(_signed_headers())
    assert (await auth.require_identity(request)).user_id == "user-123"  # type: ignore[arg-type]
    for status in (401, 503):
        with pytest.raises(HTTPException) as error:
            await auth.require_identity(request)  # type: ignore[arg-type]
        assert error.value.status_code == status
    assert nonce_store.set.await_args.kwargs == {"nx": True, "ex": 121}


def test_canonical_has_unambiguous_field_framing() -> None:
    assert auth._canonical("a\nb", "c", "user", "i", "1", "n", "GET", b"/", b"", b"") != (
        auth._canonical("a", "b\nc", "user", "i", "1", "n", "GET", b"/", b"", b"")
    )


def test_production_khong_duoc_bat_dev_auth() -> None:
    values = get_settings().model_dump()
    values.update(NODE_ENV="production", WEB_AUTH_MODE="dev")

    with pytest.raises(ValidationError, match="WEB_AUTH_MODE=dev"):
        Settings(**values)


def test_trusted_header_bat_buoc_issuer_va_secret_du_dai() -> None:
    values = get_settings().model_dump()
    values.update(
        NODE_ENV="production",
        WEB_AUTH_MODE="trusted_header",
        WEB_AUTH_ISSUER="",
        WEB_AUTH_HEADER_SECRET="short",
    )

    with pytest.raises(ValidationError, match="WEB_AUTH_ISSUER"):
        Settings(**values)
