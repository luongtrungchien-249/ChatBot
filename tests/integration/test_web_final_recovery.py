import asyncio
import json
import uuid

from adapters.web.normalize import web_final_key
from adapters.web.routes import _event_is_current, _sse_stream
from adapters.web.send import web_channel
from agents.domain.thread import ThreadScope
from infra.db import execute
from infra.redis_client import aw, get_redis
from memory.repository.thread_repo import delete_thread


async def test_subscribe_before_snapshot_recovers_final_with_duplicate_id(
    redis_san_sang: None, postgres_san_sang: None,
) -> None:
    scope = ThreadScope("web", "recovery-" + uuid.uuid4().hex)
    stream = _sse_stream(scope.thread_id)
    try:
        assert await anext(stream) == ": connected\n\n"
        await web_channel.send(scope, "public final", reply_to="request-1")
        replay = await asyncio.wait_for(anext(stream), 2)
        assert json.loads(replay.removeprefix("data: "))["reply_to"] == "request-1"
        assert json.loads((await anext(stream)).removeprefix("data: ")) == {"type": "ready"}
        live = await asyncio.wait_for(anext(stream), 2)
        assert live == replay  # UI must deduplicate the subscription/snapshot overlap.
        ttl = await aw(get_redis().ttl(web_final_key(scope.thread_id)))
        assert 0 < ttl <= 300
    finally:
        await stream.aclose()
        await aw(get_redis().delete(web_final_key(scope.thread_id)))


async def test_reconnect_recovers_final_published_without_subscribers(
    redis_san_sang: None, postgres_san_sang: None,
) -> None:
    scope = ThreadScope("web", "reconnect-" + uuid.uuid4().hex)
    await web_channel.send(scope, "already sent", "request-2")
    stream = _sse_stream(scope.thread_id)
    try:
        await anext(stream)
        event = json.loads((await anext(stream)).removeprefix("data: "))
        assert event["text"] == "already sent" and event["reply_to"] == "request-2"
    finally:
        await stream.aclose()
        await aw(get_redis().delete(web_final_key(scope.thread_id)))


async def test_failed_cache_cleanup_cannot_resurrect_deleted_final(
    redis_san_sang: None, postgres_san_sang: None,
) -> None:
    scope = ThreadScope("web", "deleted-cache-" + uuid.uuid4().hex)
    await web_channel.send(scope, "deleted public final", "request-3")
    # Delete PostgreSQL only, intentionally leaving Redis to model cleanup failure.
    await delete_thread(scope, "conversation")
    stream = _sse_stream(scope.thread_id)
    try:
        cached = await aw(get_redis().get(web_final_key(scope.thread_id)))
        assert cached is not None
        assert not await _event_is_current(scope.thread_id, cached)
        assert not await _event_is_current(scope.thread_id, '{"type":"final","text":"legacy"}')
        await anext(stream)
        assert json.loads((await anext(stream)).removeprefix("data: ")) == {"type": "ready"}
    finally:
        await stream.aclose()
        await aw(get_redis().delete(web_final_key(scope.thread_id)))
        await execute("DELETE FROM web_thread_generation WHERE thread_id=$1", scope.thread_id)
