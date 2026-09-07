"""Stage 6: ghi tin vao Postgres (nguon that), cache Redis chi la he qua.

Ghi TRUOC khi goi model: neu model loi thi cau hoi cua nguoi dung van con trong
lich su. Nguoc lai se mat cau hoi moi lan API hong.
"""

from ...domain.message import InboundMessage, scope_of
from ...domain.thread import ThreadScope
from ...ports.memory import MemoryPort, NewMessage


async def persist_inbound(memory: MemoryPort, msg: InboundMessage) -> None:
    await memory.append(
        scope_of(msg),
        NewMessage(
            message_id=msg.message_id,
            sender_id=msg.sender_id,
            sender_name=msg.sender_name,
            text=msg.text,
            is_group=msg.is_group,
            reply_to_id=msg.reply_to.id if msg.reply_to else None,
            from_bot=False,
        ),
    )


async def persist_outbound(
    memory: MemoryPort,
    scope: ThreadScope,
    in_reply_to_id: str,
    bot_name: str,
    text: str,
    is_group: bool,
) -> None:
    """Ghi cau tra loi cua bot.

    message_id lay tu tin goc + hau to: mot cau hoi sinh ra dung mot cau tra loi,
    nen khoa nay vua duy nhat vua tu chong trung khi job retry.

    `is_group` lay tu tin GOC chu khong dat cung False: cot do mo ta cuoc hoi thoai,
    khong mo ta nguoi gui. Ghi sai thi mot thread nhom co nua so dong bao la khong
    phai nhom, va bat ky truy van nao loc theo cot do cung doc ra mot nua su that.
    """
    await memory.append(
        scope,
        NewMessage(
            message_id=f"{in_reply_to_id}:bot",
            sender_id="bot",
            sender_name=bot_name,
            text=text,
            is_group=is_group,
            reply_to_id=in_reply_to_id,
            from_bot=True,
        ),
    )
