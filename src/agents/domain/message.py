"""Hop dong chung giua adapter va agents.

Agents khong biet Zalo hay giao dien web la gi — moi adapter chuan hoa ve dung
hinh dang nay truoc khi day vao hang doi.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from .thread import Platform, ThreadScope

AttachmentKind = Literal["image", "file", "audio", "video", "sticker", "unknown"]


@dataclass(frozen=True, slots=True)
class Attachment:
    kind: AttachmentKind
    url: str | None = None
    mime_type: str | None = None


@dataclass(frozen=True, slots=True)
class ReplyTo:
    id: str
    text: str


@dataclass(frozen=True, slots=True)
class InboundMessage:
    platform: Platform
    thread_id: str
    sender_id: str
    sender_name: str
    text: str
    is_group: bool
    mentioned_bot: bool
    message_id: str
    timestamp: int
    #: L8 — mot traceId xuyen suot moi log cua luot nay.
    trace_id: str
    reply_to: ReplyTo | None = None
    #: Giai doan 1 chua xu ly. Bot tra loi "minh chua xem duoc anh".
    #: Giu truong lai chu khong xoa, de khong co truong chet.
    attachments: tuple[Attachment, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class OutboundMessage:
    thread_id: str
    text: str
    reply_to: str | None = None


@dataclass(frozen=True, slots=True)
class StoredMessage:
    sender_id: str
    sender_name: str
    text: str
    created_at: datetime
    from_bot: bool


def scope_of(msg: InboundMessage) -> ThreadScope:
    return ThreadScope(platform=msg.platform, thread_id=msg.thread_id)
