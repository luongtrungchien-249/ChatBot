import uuid
from typing import Any

import pytest

from agents.domain.thread import ThreadScope
from infra.db import execute, fetch
from infra.redis_client import aw, get_redis
from main.thread_admin import delete_thread_data
from memory.repository import thread_repo
from memory.repository.thread_repo import delete_thread


async def _seed(scope: ThreadScope) -> None:
    suffix = uuid.uuid4().hex
    await execute(
        """INSERT INTO inbound_message
             (platform, message_id, thread_id, sender_id, sender_name, text, is_group, from_bot)
           VALUES ($1,$2,$3,'u','User','secret',false,false)""",
        scope.platform,
        suffix,
        scope.thread_id,
    )
    await execute(
        """INSERT INTO thread_summary(platform, thread_id, summary)
           VALUES ($1,$2,'summary')""",
        scope.platform,
        scope.thread_id,
    )
    await execute(
        """INSERT INTO thread_meta(platform, thread_id, title)
           VALUES ($1,$2,'title')""",
        scope.platform,
        scope.thread_id,
    )
    vector = "[" + ",".join(["0"] * 1024) + "]"
    await execute(
        """INSERT INTO memory_fact
             (platform, thread_id, subject_id, content, embedding, source, confidence, created_by)
           VALUES ($1,$2,'user:u','remembered',$3::vector,'explicit',1,'u')""",
        scope.platform,
        scope.thread_id,
        vector,
    )


async def _counts(scope: ThreadScope) -> tuple[int, int, int, int]:
    rows = await fetch(
        """SELECT
          (SELECT count(*) FROM inbound_message WHERE platform=$1 AND thread_id=$2) messages,
          (SELECT count(*) FROM thread_summary WHERE platform=$1 AND thread_id=$2) summaries,
          (SELECT count(*) FROM memory_fact WHERE platform=$1 AND thread_id=$2) facts,
          (SELECT count(*) FROM thread_meta WHERE platform=$1 AND thread_id=$2) metadata""",
        scope.platform,
        scope.thread_id,
    )
    row = rows[0]
    return tuple(int(row[name]) for name in ("messages", "summaries", "facts", "metadata"))  # type: ignore[return-value]


async def test_conversation_giu_fact_va_khong_cham_thread_khac(postgres_san_sang: None) -> None:
    target = ThreadScope("web", f"delete-{uuid.uuid4().hex}")
    other = ThreadScope("web", f"keep-{uuid.uuid4().hex}")
    await _seed(target)
    await _seed(other)

    report = await delete_thread(target, "conversation")

    assert report.messages == report.summaries == report.metadata == 1
    assert report.facts == 0
    assert await _counts(target) == (0, 0, 1, 0)
    assert await _counts(other) == (1, 1, 1, 1)
    await delete_thread(target, "all_data")
    await delete_thread(other, "all_data")


async def test_all_data_idempotent(postgres_san_sang: None) -> None:
    scope = ThreadScope("web", f"delete-all-{uuid.uuid4().hex}")
    await _seed(scope)

    first = await delete_thread(scope, "all_data")
    second = await delete_thread(scope, "all_data")

    assert (first.messages, first.summaries, first.facts, first.metadata) == (1, 1, 1, 1)
    assert (second.messages, second.summaries, second.facts, second.metadata) == (0, 0, 0, 0)
    assert await _counts(scope) == (0, 0, 0, 0)


async def test_transaction_rollback_neu_xoa_fact_hong_giua_chung(
    postgres_san_sang: None, monkeypatch: Any
) -> None:
    scope = ThreadScope("web", f"delete-rollback-{uuid.uuid4().hex}")
    await _seed(scope)
    original = thread_repo.hard_delete_scope  # type: ignore[attr-defined]

    async def delete_then_fail(connection: Any, target: ThreadScope) -> int:
        await original(connection, target)
        raise RuntimeError("loi gia lap sau khi xoa fact")

    monkeypatch.setattr(thread_repo, "hard_delete_scope", delete_then_fail)

    with pytest.raises(RuntimeError, match="loi gia lap"):
        await delete_thread(scope, "all_data")

    assert await _counts(scope) == (1, 1, 1, 1)
    monkeypatch.setattr(thread_repo, "hard_delete_scope", original)
    await delete_thread(scope, "all_data")


async def test_service_don_cache_va_yeu_cau_quen_dang_cho(
    postgres_san_sang: None, redis_san_sang: None
) -> None:
    scope = ThreadScope("web", f"delete-cache-{uuid.uuid4().hex}")
    await _seed(scope)
    redis = get_redis()
    ctx = f"ctx:web:{scope.thread_id}"
    cancel = f"cancel:web:{scope.thread_id}"
    pending = f"forget:web:{scope.thread_id}:u1"
    await aw(redis.mset({ctx: "secret", cancel: "1", pending: '["fact-id"]'}))

    await delete_thread_data(scope, "all_data")

    assert await aw(redis.exists(ctx, cancel, pending)) == 0
