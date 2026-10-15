from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import HTTPException, Request

from adapters.web import routes
from adapters.web.auth import WebIdentity
from agents.domain.thread import ThreadScope
from agents.ports.memory import DeleteReport
from infra.thread_lifecycle import ThreadBusyError
from main import thread_admin


class _Redis:
    def __init__(self) -> None:
        self.deleted: tuple[object, ...] = ()

    async def scan_iter(self, *, match: str) -> AsyncIterator[bytes]:
        assert match == "forget:web:t1:*"
        yield b"forget:web:t1:u1"

    async def delete(self, *keys: object) -> int:
        self.deleted = keys
        return len(keys)


async def test_xoa_postgres_truoc_va_don_dung_redis_bytes(monkeypatch: Any) -> None:
    redis = _Redis()
    calls: list[tuple[ThreadScope, str]] = []

    async def fake_delete(scope: ThreadScope, mode: str) -> DeleteReport:
        calls.append((scope, mode))
        return DeleteReport(1, 1, 1, 1)

    monkeypatch.setattr(thread_admin, "delete_thread", fake_delete)
    monkeypatch.setattr(thread_admin, "get_redis", lambda: redis)
    scope = ThreadScope("web", "t1")

    report = await thread_admin.delete_thread_data(scope, "all_data")

    assert report == DeleteReport(1, 1, 1, 1)
    assert calls == [(scope, "all_data")]
    assert redis.deleted == (
        "ctx:web:t1", "cancel:web:t1", "web:final:t1", b"forget:web:t1:u1"
    )


async def test_redis_hong_khong_bao_postgres_chua_xoa(monkeypatch: Any) -> None:
    report = DeleteReport(2, 1, 0, 1)

    async def fake_delete(_scope: ThreadScope, _mode: str) -> DeleteReport:
        return report

    monkeypatch.setattr(thread_admin, "delete_thread", fake_delete)
    monkeypatch.setattr(thread_admin, "get_redis", lambda: (_ for _ in ()).throw(ConnectionError()))

    assert await thread_admin.delete_thread_data(ThreadScope("web", "t1"), "conversation") == report


def _request() -> Request:
    return Request({"type": "http", "client": ("127.0.0.1", 1234), "headers": []})


async def test_hai_route_goi_dung_mode(monkeypatch: Any) -> None:
    calls: list[tuple[ThreadScope, str]] = []

    async def handler(scope: ThreadScope, mode: str) -> None:
        calls.append((scope, mode))

    monkeypatch.setattr(routes, "_delete_handler", handler)

    async def owner(_scope: ThreadScope, _user_id: str) -> bool:
        return True

    monkeypatch.setattr(routes, "is_owner", owner)
    identity = WebIdentity("u1", "User", frozenset({"user"}), "test")

    conversation = await routes.delete_thread(
        "t1",
        _request(),
        identity,
    )
    all_data = await routes.delete_all_thread_data(
        "t2",
        _request(),
        identity,
    )

    assert conversation.status_code == all_data.status_code == 204
    assert calls == [
        (ThreadScope("web", "t1"), "conversation"),
        (ThreadScope("web", "t2"), "all_data"),
    ]


async def test_busy_delete_retourne_409_pas_un_faux_204(monkeypatch: Any) -> None:
    async def handler(_scope: ThreadScope, _mode: str) -> None:
        raise ThreadBusyError()

    async def owner(_scope: ThreadScope, _user: str) -> bool:
        return True

    monkeypatch.setattr(routes, "_delete_handler", handler)
    monkeypatch.setattr(routes, "is_owner", owner)
    identity = WebIdentity("u", "User", frozenset({"user"}), "test")
    with pytest.raises(HTTPException) as error:
        await routes.delete_all_thread_data("t", _request(), identity)
    assert error.value.status_code == 409


def test_scan_glob_escaped_scope() -> None:
    assert thread_admin._glob_literal("forget:web:thread*[x]?:") == r"forget:web:thread\*\[x\]\?:"
