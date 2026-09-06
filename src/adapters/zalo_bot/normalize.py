"""Payload Zalo -> InboundMessage. L5: adapter chi chuan hoa, khong quyet dinh gi.

Hinh dang payload (tai lieu Webhook, dung chung cho getUpdates):

    {"message": {"from": {"id", "display_name", "is_bot"},
                 "chat": {"id", "chat_type"},
                 "text", "message_id", "date"},
     "event_name": "message.text.received"}

`date` da la mili-giay, khong nhan them 1000.
"""

import uuid
from typing import Any

from agents.domain.message import InboundMessage

#: Chi su kien nay mang text. Anh/sticker/file co event_name khac.
TEXT_EVENT = "message.text.received"

#: chat_type cua nhom. Con lai la "PRIVATE" (nhan tin rieng).
GROUP_CHAT_TYPE = "GROUP"


def _mentioned_bot(message: dict[str, Any], bot_id: str) -> bool:
    """Lop 1 cua phat hien mention: truong mention trong payload.

    Zalo CHUA cong bo tai lieu cho cach nhom bieu dien mention (chat nhom dang
    Beta), nen ham nay do nhieu ten truong co the co va tra False khi khong thay
    gi. Lop 2 — regex tren text trong policy/mention.py — moi la lop lam viec
    that su hom nay; xem ghi chu o polling.py ve cach lay duoc hinh dang that.
    """
    if not bot_id:
        return False

    for key in ("mentions", "entities", "mentioned"):
        for item in message.get(key) or ():
            if not isinstance(item, dict):
                continue
            candidate = item.get("id") or (item.get("user") or {}).get("id")
            if candidate == bot_id:
                return True
    return False


def normalize_update(result: dict[str, Any], bot_id: str = "") -> InboundMessage | None:
    """`None` = khong phai tin text nen tang nay xu ly duoc.

    Im lang truoc anh/sticker la thieu sot da biet: pipeline chua co stage tra loi
    "minh chua xem duoc anh" (TODO giai-doan-6). Im lang van tot hon tra ve mot
    InboundMessage rong — cai do se roi vao nhanh "mention nhung khong co noi
    dung" va bot di dap cau huong dan vao mot buc anh.
    """
    if result.get("event_name") != TEXT_EVENT:
        return None

    message = result.get("message")
    if not isinstance(message, dict):
        return None

    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    text = message.get("text")
    chat_id = chat.get("id")
    message_id = message.get("message_id")

    if not isinstance(text, str) or not isinstance(chat_id, str) or not isinstance(message_id, str):
        return None

    # Bot khong duoc tra loi chinh minh: mot bot khac trong nhom lap lai cau tra loi
    # cua ta la du de hai bot noi chuyen voi nhau den het ngan sach.
    if sender.get("is_bot"):
        return None

    is_group = chat.get("chat_type") == GROUP_CHAT_TYPE
    return InboundMessage(
        platform="zalo_bot",
        thread_id=chat_id,
        sender_id=str(sender.get("id") or chat_id),
        sender_name=str(sender.get("display_name") or "Ẩn danh"),
        text=text,
        is_group=is_group,
        # Nhan tin rieng thi khong can mention; trong nhom de regex quyet dinh.
        mentioned_bot=not is_group or _mentioned_bot(message, bot_id),
        message_id=message_id,
        timestamp=int(message.get("date") or 0),
        trace_id=str(uuid.uuid4()),
    )
