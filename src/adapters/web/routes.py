"""L5: adapter chi lam 4 viec — verify -> chuan hoa -> enqueue -> gui tra loi.

Khong goi LLM, khong tu chay pipeline.
"""

import json
import re
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from agents.domain.thread import ThreadScope
from agents.policy.output_guard import kiem_dau_ra
from agents.ports.memory import DeleteMode
from config import get_settings
from infra.cancel import request_cancel
from infra.db import fetch, transaction
from infra.dedupe import claim
from infra.logger import get_logger
from infra.metrics import prometheus_text
from infra.queue import enqueue_reply
from infra.thread_lifecycle import ThreadBusyError, lock_web_thread

from .access import claim_new_or_check_owner, is_owner
from .auth import WebIdentity, require_identity, require_metrics_access
from .normalize import normalize_web_input, web_channel_key, web_final_key

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

DeleteHandler = Callable[[ThreadScope, DeleteMode], Awaitable[object]]
_delete_handler: DeleteHandler | None = None


def configure_delete_handler(handler: DeleteHandler) -> None:
    global _delete_handler
    _delete_handler = handler


async def _delete(scope: ThreadScope, mode: DeleteMode) -> None:
    if _delete_handler is None:
        raise RuntimeError("delete handler chua duoc cau hinh")
    try:
        await _delete_handler(scope, mode)
    except ThreadBusyError:
        raise HTTPException(
            status_code=409, detail="thread dang duoc xu ly; thu xoa lai sau"
        ) from None


Identity = Annotated[WebIdentity, Depends(require_identity)]
_THREAD_ID_PATTERN = r"^[A-Za-z0-9_-]{1,200}$"


def _web_scope(thread_id: str) -> ThreadScope:
    # Redis keys use colon delimiters; reject ambiguous delimiters/glob patterns
    # at the untrusted Web boundary, without changing legacy non-Web scopes.
    if re.fullmatch(_THREAD_ID_PATTERN, thread_id) is None:
        raise HTTPException(status_code=422, detail="threadId khong hop le")
    return ThreadScope("web", thread_id)


async def _require_owner(thread_id: str, identity: WebIdentity) -> ThreadScope:
    scope = _web_scope(thread_id)
    if not await is_owner(scope, identity.user_id):
        raise HTTPException(status_code=404, detail="thread khong ton tai")
    return scope


def require_localhost(request: Request) -> None:
    client = request.client.host if request.client else None
    if client not in _LOCAL_ADDRESSES:
        _log.warning("tu choi truy cap khong phai localhost", ip=client)
        raise HTTPException(status_code=403, detail="chi cho phep truy cap tu localhost")


def require_operator(request: Request) -> None:
    """Nhu require_localhost, nhung nhan them dia chi MANG RIENG.

    Vi sao phai noi long DUNG cho nay: Prometheus chay trong mot container khac va
    goi toi `api:3000` qua mang cua compose, nen dia chi den la 172.x — khong phai
    loopback. Voi require_localhost thi no bi 403 va toan bo dashboard Grafana trong
    rong, ma khong co dong log nao noi vi sao. Da tra gia: bug nay ton tai ngay tu
    luc viet /metrics, va chi lo ra khi goi thu tu mot IP khac 127.0.0.1.

    Vi sao van khong mo han: dieu kien la `not is_global` — chan moi dia chi DINH
    TUYEN DUOC TU INTERNET. Cong 3000 trong ops/docker-compose.yml lai chi publish
    tren 127.0.0.1, nen tu ngoai may khong ai cham toi duoc; day la lop thu hai.

    Dung `is_global` chu khong `is_private`: `is_private` cua Python con bao True cho
    ca cac dai TAI LIEU (203.0.113.0/24, 2001:db8::/32) — dung no thi dieu kien noi
    mot dang va lam mot neo. `is_global` noi dung dieu ta muon chan.

    KHONG dung cho cac route khac. Chung doc va XOA duoc hoi thoai; /metrics thi chi
    doc so lieu tong hop, khong co noi dung tin nhan nao.
    """
    client = request.client.host if request.client else None
    if client in _LOCAL_ADDRESSES:
        return
    try:
        cong_khai = ip_address(client or "").is_global
    except ValueError:
        # Khong doc duoc dia chi thi CHAN. Khong biet la ai thi khong cho vao.
        cong_khai = True
    if cong_khai:
        _log.warning("tu choi truy cap /metrics tu dia chi cong khai", ip=client)
        raise HTTPException(status_code=403, detail="chi cho phep tu localhost hoac mang rieng")


class ChatBody(BaseModel):
    thread_id: str = Field(
        min_length=1, max_length=200, pattern=_THREAD_ID_PATTERN, alias="threadId"
    )
    text: str = Field(min_length=1, max_length=28_800)


class RenameBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@router.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


#: Bao nhieu ngay du lieu cho mot lan scrape. Rong hon thi moi lan scrape quet nhieu
#: dong hon ma Grafana van tu gop theo cua so cua no.
_METRICS_WINDOW_DAYS = 1


@router.get("/metrics")
async def metrics(
    request: Request, _access: Annotated[None, Depends(require_metrics_access)]
) -> Response:
    """Phoi bay so lieu cho Prometheus/Grafana.

    Chinh sach truy cap NOI LONG hon cac route khac — xem require_operator: Prometheus
    goi tu mot container khac nen dia chi den khong phai loopback.
    """
    body = await prometheus_text(_METRICS_WINDOW_DAYS, get_settings().DAILY_BUDGET_USD)
    # Prometheus doi text/plain; version=0.0.4 la phien ban dinh dang phoi bay.
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")


@router.post("/threads/{thread_id}", status_code=201)
async def create_thread(thread_id: str, identity: Identity) -> dict[str, str]:
    if not await claim_new_or_check_owner(_web_scope(thread_id), identity.user_id):
        raise HTTPException(status_code=404, detail="thread khong ton tai")
    return {"threadId": thread_id}


@router.get("/threads")
async def list_threads(request: Request, identity: Identity) -> list[dict[str, Any]]:
    """Danh sach hoi thoai cho sidebar. Doc tu Postgres, khong phai localStorage."""
    rows = await fetch(
        """SELECT DISTINCT ON (m.thread_id)
                  m.thread_id,
                  first_value(m.text)       OVER w AS last_text,
                  first_value(m.created_at) OVER w AS last_at,
                  count(*)                  OVER (PARTITION BY m.thread_id) AS message_count,
                  t.title,
                  -- Nhan cua mot hoi thoai la CAU HOI DAU TIEN, khong phai tin cuoi.
                  --
                  -- Tin cuoi gan nhu luon la cau tra loi cua bot, va mot cau tra loi
                  -- dai ba dong thi ba mươi ky tu dau cua no khong phan biet duoc
                  -- hoi thoai nay voi hoi thoai khac. Nguoi dung nho ho DA HOI GI.
                  (SELECT q.text
                     FROM inbound_message q
                    WHERE q.platform = m.platform AND q.thread_id = m.thread_id
                      AND NOT q.from_bot
                    ORDER BY q.created_at
                    LIMIT 1) AS first_question
             FROM inbound_message m
             LEFT JOIN thread_meta t
                    ON t.platform = m.platform AND t.thread_id = m.thread_id
             JOIN web_thread_access a
                    ON a.thread_id = m.thread_id AND a.user_id = $1
            WHERE m.platform = 'web'
           WINDOW w AS (PARTITION BY m.thread_id ORDER BY m.created_at DESC)
            ORDER BY m.thread_id, last_at DESC""",
        identity.user_id,
    )
    threads = [
        {
            "threadId": r["thread_id"],
            # Ten nguoi dat thang cac nhan tu dong. Chua dat thi dung cau hoi dau tien.
            "title": r["title"],
            "question": r["first_question"],
            "lastText": kiem_dau_ra(r["last_text"]).text,
            "lastAt": r["last_at"].isoformat(),
            "messageCount": r["message_count"],
        }
        for r in rows
    ]
    return sorted(threads, key=lambda t: str(t["lastAt"]), reverse=True)


@router.get("/threads/{thread_id}/messages")
async def list_messages(
    thread_id: str, request: Request, identity: Identity
) -> list[dict[str, Any]]:
    await _require_owner(thread_id, identity)
    rows = await fetch(
        """SELECT text, from_bot, created_at, message_id, reply_to_id
             FROM inbound_message
            WHERE platform = 'web' AND thread_id = $1
            ORDER BY created_at""",
        thread_id,
    )
    public: list[dict[str, Any]] = []
    inbound_text: dict[str, str] = {}
    for row in rows:
        text = str(row["text"])
        if row["from_bot"]:
            # Protect legacy rows written before the final-output invariant existed.
            text = kiem_dau_ra(
                text, van_ban_nguoi_dung=inbound_text.get(row["reply_to_id"], "")
            ).text
        else:
            inbound_text[row["message_id"]] = text
        public.append(
            {
                "text": text, "fromBot": row["from_bot"], "at": row["created_at"].isoformat(),
                "messageId": row["message_id"], "replyTo": row["reply_to_id"],
            }
        )
    return public


@router.post("/chat", status_code=202)
async def post_chat(body: ChatBody, request: Request, identity: Identity) -> dict[str, Any]:
    """Tra 202 ngay roi thoi — cau tra loi ve qua SSE. Khong cho LLM o day."""
    scope = ThreadScope("web", body.thread_id)
    if not await claim_new_or_check_owner(scope, identity.user_id):
        raise HTTPException(status_code=404, detail="thread khong ton tai")
    msg = normalize_web_input(
        body.thread_id,
        body.text,
        user_id=identity.user_id,
        display_name=identity.display_name,
    )

    # Lop chong trung thu nhat: SET NX atomic.
    if not await claim(msg.platform, msg.message_id):
        return {"duplicate": True}

    await enqueue_reply(msg)
    _log.info("da xep hang cau hoi tu web", trace_id=msg.trace_id, thread_id=msg.thread_id)
    return {"messageId": msg.message_id, "traceId": msg.trace_id}


@router.post("/threads/{thread_id}/stop", status_code=202)
async def stop_thread(thread_id: str, request: Request, identity: Identity) -> dict[str, bool]:
    """Nguoi dung bam dung. Chi dat co — worker doc no o dau moi vong ReAct.

    Khong giet job: huy giua mot request dang bay van bi tinh tien ma khong duoc gi,
    va se de lai job o trang thai nua voi. Dung o ranh gioi vong la sach hon.
    """
    scope = await _require_owner(thread_id, identity)
    await request_cancel(scope)
    _log.info("nguoi dung yeu cau dung", thread_id=thread_id)
    return {"stopping": True}


@router.patch("/threads/{thread_id}")
async def rename_thread(
    thread_id: str, body: RenameBody, request: Request, identity: Identity
) -> dict[str, str]:
    """Doi ten hoi thoai. Ten do nguoi dat, khong phai tom tat do model sinh."""
    await _require_owner(thread_id, identity)
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title rong")

    try:
        async with transaction() as connection:
            await lock_web_thread(connection, ThreadScope("web", thread_id))
            await connection.execute(
                """INSERT INTO thread_meta (platform, thread_id, title)
                   VALUES ('web', $1, $2)
                   ON CONFLICT (platform, thread_id)
                   DO UPDATE SET title = EXCLUDED.title, updated_at = now()""",
                thread_id,
                title,
            )
    except ThreadBusyError:
        raise HTTPException(status_code=409, detail="thread dang duoc xu ly; thu lai sau") from None
    return {"threadId": thread_id, "title": title}


@router.delete("/threads/{thread_id}", status_code=204)
async def delete_thread(thread_id: str, request: Request, identity: Identity) -> Response:
    """Xoa hoi thoai nhung giu fact explicit da nho."""
    scope = await _require_owner(thread_id, identity)
    await _delete(scope, "conversation")
    _log.info("da xoa hoi thoai", thread_id=thread_id)
    return Response(status_code=204)


@router.delete("/threads/{thread_id}/data", status_code=204)
async def delete_all_thread_data(thread_id: str, request: Request, identity: Identity) -> Response:
    """Xoa vinh vien ca hoi thoai va moi fact trong thread."""
    scope = await _require_owner(thread_id, identity)
    await _delete(scope, "all_data")
    _log.info("da xoa toan bo du lieu thread", thread_id=thread_id)
    return Response(status_code=204)


async def _event_is_current(thread_id: str, payload: str) -> bool:
    from infra.thread_lifecycle import read_web_generation

    try:
        event = json.loads(payload)
    except (ValueError, TypeError):
        return False
    if not isinstance(event, dict):
        return False
    if event.get("type") != "final":
        return True
    generation = event.get("generation")
    # Redis cleanup is best effort. A stale/legacy cached final must never undo
    # deletion even when DEL failed; PostgreSQL's tombstone is authoritative.
    return type(generation) is int and generation == await read_web_generation(
        ThreadScope("web", thread_id)
    )


async def _sse_stream(thread_id: str) -> AsyncGenerator[str, None]:
    """Moi ket noi mot Redis client rieng.

    O che do subscribe, redis-py khong chay duoc lenh nao khac tren cung connection.
    """
    subscriber: Redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    pubsub = subscriber.pubsub()
    await pubsub.subscribe(web_channel_key(thread_id))

    try:
        yield ": connected\n\n"
        # Subscribe first: a final published during this read is queued too. The
        # client deduplicates replay/live delivery by reply_to, not by text.
        final = await subscriber.get(web_final_key(thread_id))
        if final and await _event_is_current(thread_id, final):
            yield f"data: {final}\n\n"
        yield 'data: {"type":"ready"}\n\n'
        last_ping = time.monotonic()
        while True:
            # get_message(timeout=1) tra None sau moi giay khi khong co gi. Do KHONG
            # phai "het gio heartbeat" — coi no la vay se ban ping moi giay, lam ngap
            # ket noi va che mat su kien that.
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)

            if message is not None:
                data = message.get("data")
                if isinstance(data, str) and await _event_is_current(thread_id, data):
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
async def stream(thread_id: str, request: Request, identity: Identity) -> StreamingResponse:
    await _require_owner(thread_id, identity)
    return StreamingResponse(
        _sse_stream(thread_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
