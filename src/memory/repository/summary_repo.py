"""L2 — tom tat cuon. Bang `thread_summary`.

Job nen chay tren `WHERE NOT summarized`, HOAN TOAN khong phu thuoc TTL cua Redis.
Day la ban sua loi mat du lieu cua ke hoach goc (ARCHITECTURE.md section 6.1): ban
cu de tin chua nen nam trong Redis TTL 2h, nen mot nhom im lang qua dem la mat sach
va L2 khong bao gio chay.
"""

from dataclasses import dataclass

from agents.domain.thread import ThreadScope
from infra.db import fetch, transaction


@dataclass(frozen=True, slots=True)
class Summary:
    text: str
    #: So tin da bi nen vao ban tom tat nay.
    msg_count: int
    #: So lan nen DE QUY. Moi lan nen lai chinh ban tom tat cu la mot the he.
    gen_count: int


@dataclass(frozen=True, slots=True)
class PendingMessage:
    message_id: str
    #: Can cho L3 implicit: fact phai gan theo ID on dinh, khong theo ten hien thi.
    #: Hai nguoi trung ten trong mot nhom la chuyen binh thuong.
    sender_id: str
    sender_name: str
    text: str
    from_bot: bool


async def get_summary(scope: ThreadScope) -> Summary | None:
    rows = await fetch(
        """SELECT summary, msg_count, gen_count
             FROM thread_summary
            WHERE platform = $1 AND thread_id = $2""",
        scope.platform,
        scope.thread_id,
    )
    if not rows:
        return None
    row = rows[0]
    return Summary(text=row["summary"], msg_count=row["msg_count"], gen_count=row["gen_count"])


async def count_pending(scope: ThreadScope) -> int:
    """So tin chua bi L2 nuot."""
    rows = await fetch(
        """SELECT count(*) AS n
             FROM inbound_message
            WHERE platform = $1 AND thread_id = $2 AND NOT summarized""",
        scope.platform,
        scope.thread_id,
    )
    return int(rows[0]["n"]) if rows else 0


async def oldest_pending(scope: ThreadScope, limit: int) -> list[PendingMessage]:
    """`limit` tin CU NHAT chua nen — tuc la nhung tin da troi ra ngoai cua so L1."""
    rows = await fetch(
        """SELECT message_id, sender_id, sender_name, text, from_bot
             FROM inbound_message
            WHERE platform = $1 AND thread_id = $2 AND NOT summarized
            ORDER BY created_at
            LIMIT $3""",
        scope.platform,
        scope.thread_id,
        limit,
    )
    return [
        PendingMessage(
            message_id=r["message_id"],
            sender_id=r["sender_id"],
            sender_name=r["sender_name"],
            text=r["text"],
            from_bot=r["from_bot"],
        )
        for r in rows
    ]


async def commit_summary(
    scope: ThreadScope, text: str, message_ids: list[str], previous: Summary | None
) -> None:
    """Ghi ban tom tat MOI va danh dau dung nhung tin da nen — TRONG MOT TRANSACTION.

    Tach hai buoc nay ra la mat du lieu theo mot trong hai huong, khong co huong nao
    chap nhan duoc:

      - Ghi tom tat xong roi hong truoc khi danh dau -> lan sau nen lai dung 15 tin
        do, noi dung bi lap trong ban tom tat.
      - Danh dau xong roi hong truoc khi ghi -> 15 tin do bien mat vinh vien: khong
        con trong L1, chua vao L2, va co `summarized` da bat nen khong ai lay lai.
    """
    if not message_ids:
        return

    async with transaction() as connection:
        await connection.execute(
            """INSERT INTO thread_summary (platform, thread_id, summary, msg_count, gen_count)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (platform, thread_id) DO UPDATE
                  SET summary = EXCLUDED.summary,
                      msg_count = EXCLUDED.msg_count,
                      gen_count = EXCLUDED.gen_count,
                      updated_at = now()""",
            scope.platform,
            scope.thread_id,
            text,
            (previous.msg_count if previous else 0) + len(message_ids),
            (previous.gen_count if previous else 0) + 1,
        )
        await connection.execute(
            """UPDATE inbound_message
                  SET summarized = TRUE
                WHERE platform = $1 AND message_id = ANY($2::text[])""",
            scope.platform,
            message_ids,
        )


def render_for_summary(messages: list[PendingMessage]) -> str:
    """Doan hoi thoai dua cho model nen.

    Giu ten nguoi gui: mot ban tom tat khong biet AI quyet dinh cai gi thi vo dung
    trong nhom. Cau tra loi cua bot ghi ro la cua bot, neu khong model se tuong do
    cung la loi nguoi dung noi.
    """
    return "\n".join(
        f"[{'Trợ lý' if m.from_bot else m.sender_name}]: {m.text}" for m in messages
    )


def render_previous(previous: Summary | None) -> str:
    if previous is None:
        return ""
    return f"<tom_tat_cu>\n{previous.text}\n</tom_tat_cu>\n\n"
