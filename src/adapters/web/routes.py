"""L5: adapter chi lam 4 viec — verify -> chuan hoa -> enqueue -> gui tra loi.

Khong goi LLM, khong tu chay pipeline.
"""

import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from agents.domain.thread import ThreadScope
from config import get_settings
from infra.cancel import request_cancel
from infra.db import execute, fetch
from infra.dedupe import claim
from infra.logger import get_logger
from infra.queue import enqueue_reply
from infra.redis_client import aw, get_redis

from .normalize import normalize_web_input, web_channel_key

_log = get_logger()
router = APIRouter(prefix="/api")

#: Template va tep tinh nam TRONG goi, khong o thu muc rieng ngoai repo: chung
#: thuoc ve adapter web y het routes.py, va di theo goi khi dong goi.
WEB_ROOT = Path(__file__).resolve().parent

#: D17: chi localhost. Chua co auth, nen mo ra ngoai la ai trong mang cung dot duoc
#: ngan sach. Kiem tra o tang route chu khong chi dua vao bind address — mot reverse
#: proxy dat truoc se lam bind address vo nghia.
_LOCAL_ADDRESSES = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1"})

_HEARTBEAT_SECONDS = 20


def require_localhost(request: Request) -> None:
    client = request.client.host if request.client else None
    if client not in _LOCAL_ADDRESSES:
        _log.warning("tu choi truy cap khong phai localhost", ip=client)
        raise HTTPException(status_code=403, detail="chi cho phep truy cap tu localhost")


class ChatBody(BaseModel):
    thread_id: str = Field(min_length=1, alias="threadId")
    text: str = Field(min_length=1)


class RenameBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@router.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/threads")
async def list_threads(request: Request) -> list[dict[str, Any]]:
    """Danh sach hoi thoai cho sidebar. Doc tu Postgres, khong phai localStorage."""
    require_localhost(request)
    rows = await fetch(
        """SELECT DISTINCT ON (m.thread_id)
                  m.thread_id,
                  first_value(m.text)       OVER w AS last_text,
                  first_value(m.created_at) OVER w AS last_at,
                  count(*)                  OVER (PARTITION BY m.thread_id) AS message_count,
                  t.title
             FROM inbound_message m
             LEFT JOIN thread_meta t
                    ON t.platform = m.platform AND t.thread_id = m.thread_id
            WHERE m.platform = 'web'
           WINDOW w AS (PARTITION BY m.thread_id ORDER BY m.created_at DESC)
            ORDER BY m.thread_id, last_at DESC"""
    )
    threads = [
        {
            "threadId": r["thread_id"],
            # Ten nguoi dat thang tin nhan cuoi. Chua dat thi hien tin cuoi lam nhan tam.
            "title": r["title"],
            "lastText": r["last_text"],
            "lastAt": r["last_at"].isoformat(),
            "messageCount": r["message_count"],
        }
        for r in rows
    ]
    return sorted(threads, key=lambda t: str(t["lastAt"]), reverse=True)


@router.get("/threads/{thread_id}/messages")
async def list_messages(thread_id: str, request: Request) -> list[dict[str, Any]]:
    require_localhost(request)
    rows = await fetch(
        """SELECT text, from_bot, created_at
             FROM inbound_message
            WHERE platform = 'web' AND thread_id = $1
            ORDER BY created_at""",
        thread_id,
    )
    return [
        {"text": r["text"], "fromBot": r["from_bot"], "at": r["created_at"].isoformat()}
        for r in rows
    ]


@router.post("/chat", status_code=202)
async def post_chat(body: ChatBody, request: Request) -> dict[str, Any]:
    """Tra 202 ngay roi thoi — cau tra loi ve qua SSE. Khong cho LLM o day."""
    require_localhost(request)
    msg = normalize_web_input(body.thread_id, body.text)

    # Lop chong trung thu nhat: SET NX atomic.
    if not await claim(msg.platform, msg.message_id):
        return {"duplicate": True}

    await enqueue_reply(msg)
    _log.info("da xep hang cau hoi tu web", trace_id=msg.trace_id, thread_id=msg.thread_id)
    return {"messageId": msg.message_id, "traceId": msg.trace_id}


@router.post("/threads/{thread_id}/stop", status_code=202)
async def stop_thread(thread_id: str, request: Request) -> dict[str, bool]:
    """Nguoi dung bam dung. Chi dat co — worker doc no o dau moi vong ReAct.

    Khong giet job: huy giua mot request dang bay van bi tinh tien ma khong duoc gi,
    va se de lai job o trang thai nua voi. Dung o ranh gioi vong la sach hon.
    """
    require_localhost(request)
    await request_cancel(ThreadScope(platform="web", thread_id=thread_id))
    _log.info("nguoi dung yeu cau dung", thread_id=thread_id)
    return {"stopping": True}


@router.patch("/threads/{thread_id}")
async def rename_thread(thread_id: str, body: RenameBody, request: Request) -> dict[str, str]:
    """Doi ten hoi thoai. Ten do nguoi dat, khong phai tom tat do model sinh."""
    require_localhost(request)
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title rong")

    await execute(
        """INSERT INTO thread_meta (platform, thread_id, title)
           VALUES ('web', $1, $2)
           ON CONFLICT (platform, thread_id)
           DO UPDATE SET title = EXCLUDED.title, updated_at = now()""",
        thread_id,
        title,
    )
    return {"threadId": thread_id, "title": title}


@router.delete("/threads/{thread_id}", status_code=204)
async def delete_thread(thread_id: str, request: Request) -> Response:
    """Xoa ca hoi thoai. Postgres la nguon that nen xoa o day la xoa that."""
    require_localhost(request)
    await execute(
        "DELETE FROM inbound_message WHERE platform = 'web' AND thread_id = $1", thread_id
    )
    await execute("DELETE FROM thread_meta WHERE platform = 'web' AND thread_id = $1", thread_id)
    # Cache L1 phai xoa theo, neu khong hoi thoai da xoa van song trong Redis 2 tieng.
    await aw(get_redis().delete(f"ctx:web:{thread_id}"))
    _log.info("da xoa hoi thoai", thread_id=thread_id)
    return Response(status_code=204)


async def _sse_stream(thread_id: str) -> AsyncIterator[str]:
    """Moi ket noi mot Redis client rieng.

    O che do subscribe, redis-py khong chay duoc lenh nao khac tren cung connection.
    """
    subscriber: Redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    pubsub = subscriber.pubsub()
    await pubsub.subscribe(web_channel_key(thread_id))

    try:
        yield ": connected\n\n"
        last_ping = time.monotonic()
        while True:
            # get_message(timeout=1) tra None sau moi giay khi khong co gi. Do KHONG
            # phai "het gio heartbeat" — coi no la vay se ban ping moi giay, lam ngap
            # ket noi va che mat su kien that.
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)

            if message is not None:
                data = message.get("data")
                if isinstance(data, str):
                    yield f"data: {data}\n\n"
                continue

            if time.monotonic() - last_ping >= _HEARTBEAT_SECONDS:
                # Giu ket noi song qua proxy hay cat idle.
                yield ": ping\n\n"
                last_ping = time.monotonic()
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()  # type: ignore[no-untyped-call]  # redis-py chua chu ky
        await subscriber.aclose()


@router.get("/stream/{thread_id}")
async def stream(thread_id: str, request: Request) -> StreamingResponse:
    require_localhost(request)
    return StreamingResponse(
        _sse_stream(thread_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
