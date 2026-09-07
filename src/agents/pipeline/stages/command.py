"""Stage 3: lenh quan tri memory — tra loi NGAY, khong goi model.

Dung TRUOC stage 4 (ratelimit) co chu dich: nguoi dung phai xoa duoc memory cua
chinh minh ngay ca khi dang bi rate limit. Dung "toi uu" thu tu nay.

Ba rang buoc ve quyen, lay tu ARCHITECTURE.md section 6.2:

  1. Moi nguoi chi dung toi fact ve CHINH MINH. `subject_id` suy ra tu `sender_id`
     cua tin nhan, KHONG bao gio nhan tu van ban nguoi dung go — neu khong thi go
     dung mot chuoi la xoa duoc fact cua nguoi khac.
  2. `quen <noi dung>` LIET KE roi HOI, khong xoa ngay. Soft delete khong co lenh
     khoi phuc, nen mot lan go nham la mat that.
  3. Buoc xac nhan can state. Ma xac nhan song trong Redis TTL 5 phut — cho goi
     di qua MemoryPort.stage_forget / confirm_forget.
"""

from dataclasses import dataclass
from typing import TypeAlias

from ...domain.thread import ThreadScope, user_subject
from ...policy.command import (
    Command,
    ConfirmForget,
    Forget,
    ForgetAll,
    Help,
    NoCommand,
    Remember,
    ShowMemory,
    parse_command,
)
from ...ports.memory import Fact, MemoryPort, NewFact

HELP_TEXT = (
    "Mình trả lời khi bạn nhắn kèm câu hỏi. Ngoài ra có mấy lệnh: "
    '"nhớ giúp: <nội dung>" để mình ghi nhớ, '
    '"memory" để xem mình nhớ gì về bạn trong nhóm này, '
    '"quên <nội dung>" để xoá một điều, "quên hết" để xoá tất cả.'
)

NOTHING_REMEMBERED = "Mình chưa nhớ điều gì về bạn trong nhóm này."

NOTHING_MATCHED = (
    "Mình không tìm thấy điều nào khớp với nội dung đó. "
    'Bạn gõ "memory" để xem mình đang nhớ những gì nhé.'
)

NOTHING_PENDING = 'Hiện không có yêu cầu xoá nào đang chờ. Bạn gõ "quên <nội dung>" trước nhé.'


@dataclass(frozen=True, slots=True)
class NotACommand:
    """Di tiep xuong duong ong binh thuong."""


@dataclass(frozen=True, slots=True)
class Answer:
    """Tra loi luon, khong goi model."""

    text: str


@dataclass(frozen=True, slots=True)
class DeferredWrite:
    """Lenh GHI. Phai qua ratelimit va budget guard TRUOC khi thuc hien.

    Doc (`memory`) va xoa (`quen`, `quen het`, `dong y`) chay som co chu dich:
    nguoi dung phai dung toi duoc du lieu cua chinh minh ke ca khi dang bi chan.

    `nho giup:` thi khac han — no GHI, va duong ghi fact goi embedding that o moi
    lan. De chung o stage 3 nghia la mot nguoi go `nho giup:` lien tuc se tieu tien
    ma khong qua mot chot chan nao: khong rate limit, khong ngan sach ngay.
    """

    command: Remember


@dataclass(frozen=True, slots=True)
class AskConfirm:
    """Liet ke ung vien va cho xac nhan. Cho goi tu luu `facts` lai de cho xac nhan."""

    text: str
    facts: tuple[Fact, ...]


CommandOutcome: TypeAlias = NotACommand | Answer | AskConfirm | DeferredWrite


async def run_deferred_write(
    deferred: DeferredWrite, memory: MemoryPort, scope: ThreadScope, sender_id: str
) -> str:
    """Thuc hien lenh ghi. Cho goi PHAI da chay xong stage 4 (ratelimit) va 5 (budget).

    Tach ra khoi handle_command chu khong them mot tham so co/khong: mot tham so
    boolean se bi truyen nham dung mot lan, va lan do khong ai nhan ra.
    """
    await memory.remember(
        scope,
        NewFact(
            # subject_id suy ra tu sender_id cua TIN NHAN, khong tu van ban.
            subject_id=user_subject(sender_id),
            content=deferred.command.content,
            # Nguoi dung noi thang ra: explicit, do tin cay tuyet doi. Fact do model
            # tu trich di duong khac va phai kem confidence that.
            source="explicit",
            confidence=1.0,
            created_by=sender_id,
        ),
    )
    return f"Được, mình nhớ rồi: {deferred.command.content}"


def render_facts(facts: list[Fact]) -> str:
    return "\n".join(f"{i}. {f.content}" for i, f in enumerate(facts, start=1))


async def handle_command(
    text: str, memory: MemoryPort, scope: ThreadScope, sender_id: str
) -> CommandOutcome:
    command: Command = parse_command(text)

    if isinstance(command, NoCommand):
        return NotACommand()

    if isinstance(command, Help):
        return Answer(text=HELP_TEXT)

    if isinstance(command, ConfirmForget):
        # Lay-va-xoa trong mot buoc: mot cai "dong y" chi dung duoc mot lan. Neu
        # tach doi thi go hai lan lien tiep se revoke hai lot fact khac nhau.
        count = await memory.confirm_forget(scope, sender_id, command.choices)
        if count == 0:
            return Answer(text=NOTHING_PENDING)
        return Answer(text=f"Xong, mình đã quên {count} điều.")

    # subject_id suy ra tu sender_id cua TIN NHAN, khong tu van ban. Day la cho
    # chan "nguoi X xoa fact cua nguoi Y".
    subject = user_subject(sender_id)

    if isinstance(command, Remember):
        # KHONG ghi tai day. Xem DeferredWrite: duong ghi phai di qua stage 4 va 5.
        return DeferredWrite(command=command)

    if isinstance(command, ShowMemory):
        facts = await memory.list_facts(scope, subject)
        if not facts:
            return Answer(text=NOTHING_REMEMBERED)
        return Answer(text="Mình đang nhớ về bạn:\n" + render_facts(facts))

    if isinstance(command, ForgetAll):
        facts = await memory.list_facts(scope, subject)
        if not facts:
            return Answer(text=NOTHING_REMEMBERED)
        return AskConfirm(
            text=(
                f"Bạn muốn mình quên hết {len(facts)} điều dưới đây?\n"
                + render_facts(facts)
                + '\n\nNhắn "đồng ý" để xác nhận.'
            ),
            facts=tuple(facts),
        )

    assert isinstance(command, Forget)
    matched = await memory.forget(scope, sender_id, command.pattern)
    if not matched:
        return Answer(text=NOTHING_MATCHED)
    return AskConfirm(
        text=(
            "Bạn muốn mình quên điều nào?\n"
            + render_facts(matched)
            + '\n\nNhắn "đồng ý" để mình quên tất cả những điều trên.'
        ),
        facts=tuple(matched),
    )
