"""L1 — 15 tin gan nhat.

POSTGRES LA NGUON THAT, REDIS CHI LA CACHE DOC. Day la ban sua loi mat du lieu cua
ke hoach goc (ARCHITECTURE.md section 6.1): ke hoach cu de Redis giu tin chua nen
voi TTL 2h, nen mot nhom im lang qua dem la mat sach.

Cache truot thi doc lai DB — khong mat gi, chi cham hon mot chut.
"""

import json
from datetime import datetime
from typing import Any

from agents.domain.message import StoredMessage
from agents.domain.thread import ThreadScope, thread_subject, user_subject
from agents.ports.memory import Fact, NewFact, NewMessage
from infra.db import fetch
from infra.logger import get_logger
from infra.redis_client import aw, get_redis

from . import fact_repo
from .summary_repo import get_summary

_CACHE_TTL_SECONDS = 7_200  # 2h, xem section 6.5
_CACHE_MAX_ENTRIES = 50

#: Yeu cau xoa dang cho xac nhan. 5 phut, xem ARCHITECTURE.md section 6.2.
_PENDING_FORGET_TTL_SECONDS = 300

_log = get_logger()


def _ctx_key(scope: ThreadScope) -> str:
    return f"ctx:{scope.platform}:{scope.thread_id}"


def _pending_key(scope: ThreadScope, actor_id: str) -> str:
    """Khoa theo CA thread lan nguoi go lenh: mot cai "dong y" trong nhom nay khong
    duoc dung nham yeu cau cua nguoi khac, hay cua chinh minh o nhom khac.
    """
    return f"forget:{scope.platform}:{scope.thread_id}:{actor_id}"


def _to_stored(row: Any) -> StoredMessage:
    return StoredMessage(
        sender_id=row["sender_id"],
        sender_name=row["sender_name"],
        text=row["text"],
        created_at=row["created_at"],
        from_bot=row["from_bot"],
    )


def _encode(msg: StoredMessage) -> str:
    return json.dumps(
        {
            "sender_id": msg.sender_id,
            "sender_name": msg.sender_name,
            "text": msg.text,
            "created_at": msg.created_at.isoformat(),
            "from_bot": msg.from_bot,
        }
    )


def _decode(raw: str) -> StoredMessage:
    data = json.loads(raw)
    return StoredMessage(
        sender_id=data["sender_id"],
        sender_name=data["sender_name"],
        text=data["text"],
        created_at=datetime.fromisoformat(data["created_at"]),
        from_bot=data["from_bot"],
    )


class MessageRepository:
    """Implement phan L1 cua MemoryPort. L2/L3 se noi vao o Giai doan 7."""

    async def append(self, scope: ThreadScope, msg: NewMessage) -> None:
        # ON CONFLICT DO NOTHING: khoa chinh (platform, message_id) la lop chong trung
        # thu BA, song lau hon TTL cua Redis. Job retry khong duoc tao ban ghi thu hai.
        rows = await fetch(
            """INSERT INTO inbound_message
                 (platform, message_id, thread_id, sender_id, sender_name,
                  text, is_group, reply_to_id, from_bot)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
               ON CONFLICT (platform, message_id) DO NOTHING
               RETURNING sender_id, sender_name, text, created_at, from_bot""",
            scope.platform,
            msg.message_id,
            scope.thread_id,
            msg.sender_id,
            msg.sender_name,
            msg.text,
            msg.is_group,
            msg.reply_to_id,
            msg.from_bot,
        )
        if not rows:
            return  # da co roi, cache cung da co

        try:
            key = _ctx_key(scope)
            redis = get_redis()
            await aw(redis.lpush(key, _encode(_to_stored(rows[0]))))
            await aw(redis.ltrim(key, 0, _CACHE_MAX_ENTRIES - 1))
            await aw(redis.expire(key, _CACHE_TTL_SECONDS))
        except Exception as error:
            # Cache hong khong duoc lam hong duong ghi: nguon that da ghi xong roi.
            _log.warning("khong day duoc cache L1, bo qua", err=str(error))

    async def recent(self, scope: ThreadScope, limit: int) -> list[StoredMessage]:
        """Tra ve theo thu tu THOI GIAN TANG DAN — dung thu tu doc mot hoi thoai."""
        key = _ctx_key(scope)

        try:
            cached = await aw(get_redis().lrange(key, 0, limit - 1))
            if len(cached) >= limit:
                return [_decode(item) for item in reversed(cached)]
        except Exception as error:
            _log.warning("doc cache L1 that bai, doc thang DB", err=str(error))

        rows = await fetch(
            """SELECT sender_id, sender_name, text, created_at, from_bot
                 FROM inbound_message
                WHERE platform = $1 AND thread_id = $2
                ORDER BY created_at DESC
                LIMIT $3""",
            scope.platform,
            scope.thread_id,
            limit,
        )
        newest_first = [_to_stored(r) for r in rows]

        # Nong lai cache. Thieu buoc nay thi cache chi duoc nap boi append(), nen sau
        # moi lan khoi dong lai process (hoac sau khi TTL het) no nguoi han cho toi
        # khi du `limit` tin moi duoc ghi — nghia la gan nhu khong bao gio am.
        #
        # Thread ngan hon `limit` van doc thang DB moi lan: khong the biet tu Redis la
        # danh sach ngan vi thread it tin hay vi cache thieu. Truy van co index nen
        # chuyen do khong dang mot giao thuc danh dau "day du" rieng.
        if newest_first:
            try:
                redis = get_redis()
                pipe = redis.pipeline()
                pipe.delete(key)
                pipe.rpush(key, *[_encode(m) for m in newest_first])
                pipe.expire(key, _CACHE_TTL_SECONDS)
                await pipe.execute()
            except Exception as error:
                _log.warning("khong nong lai duoc cache L1, bo qua", err=str(error))

        return list(reversed(newest_first))

    async def summary(self, scope: ThreadScope) -> str | None:
        """L2 — ban tom tat cuon. None = thread nay chua du dai de can nen."""
        stored = await get_summary(scope)
        return stored.text if stored is not None else None

    # --- L3 ---
    # Moi phuong thuc chi uy quyen sang fact_repo. Khong co cau SQL nao cham
    # `memory_fact` o file nay — do la luat L4, va ops/guard_sql.py cuong che no.

    async def facts(self, scope: ThreadScope, subject_id: str, query: str) -> list[Fact]:
        """Fact ve NGUOI hoi, cong fact chung cua CA NHOM.

        Fact `thread:*` truoc day ghi duoc nhung khong duong nao doc ra — chung
        khong bao gio vao prompt. Gop o day chu khong them mot lan goi port nua:
        mot cau truy van, mot lan embed.

        Ca hai deu bi rang buoc boi `scope`, nen hang rao chong ro ri cross-group
        khong he noi long.
        """
        return await fact_repo.search_facts_for(
            scope, [subject_id, thread_subject(scope.thread_id)], query
        )

    async def remember(self, scope: ThreadScope, fact: NewFact) -> None:
        await fact_repo.remember(scope, fact)

    async def forget(self, scope: ThreadScope, actor_id: str, pattern: str) -> list[Fact]:
        """Tra ve fact KHOP de hoi xac nhan. KHONG revoke o day.

        `actor_id` la nguoi go lenh; ho chi duoc dung toi fact ve CHINH HO. Cho goi
        (stage 3) dung no de dung subject_id, va vi the mot nguoi khong the xoa fact
        cua nguoi khac du co go dung noi dung.
        """
        return await fact_repo.match_for_forget(scope, user_subject(actor_id), pattern)

    async def stage_forget(self, scope: ThreadScope, actor_id: str, fact_ids: list[str]) -> None:
        """Yeu cau xoa dang cho, song trong Redis va TU HET HAN.

        Redis chu khong Postgres: day la trang thai tam cua mot cuoc hoi dap, khong
        phai du lieu can ben. Va TTL la mot phan cua thiet ke — mot yeu cau xoa bi bo
        quen tu bien mat thay vi nam cho toi khi ai do go nham "dong y" ba ngay sau.
        """
        if not fact_ids:
            return
        await aw(
            get_redis().set(
                _pending_key(scope, actor_id),
                json.dumps(fact_ids),
                ex=_PENDING_FORGET_TTL_SECONDS,
            )
        )

    async def confirm_forget(
        self, scope: ThreadScope, actor_id: str, choices: tuple[int, ...] = ()
    ) -> int:
        key = _pending_key(scope, actor_id)
        # getdel: lay VA xoa trong mot lenh, atomic. GET roi DEL thi hai lan "dong y"
        # gui gan nhau deu doc duoc cung mot danh sach.
        raw = await aw(get_redis().getdel(key))
        if not raw:
            return 0
        try:
            fact_ids = [str(i) for i in json.loads(raw)]
        except (ValueError, TypeError):
            _log.error("yeu cau xoa dang cho bi hong, bo qua", thread_id=scope.thread_id)
            return 0

        if choices:
            # So ngoai danh sach thi bo qua. Nem loi o day nghia la go nham mot con
            # so se huy ca thao tac VA nuot mat yeu cau dang cho (getdel da chay roi).
            fact_ids = [fact_ids[n - 1] for n in choices if 1 <= n <= len(fact_ids)]
            if not fact_ids:
                return 0

        return await fact_repo.revoke(scope, fact_ids, revoked_by=actor_id)

    async def list_facts(self, scope: ThreadScope, subject_id: str) -> list[Fact]:
        return await fact_repo.list_facts(scope, subject_id)


message_repo = MessageRepository()
