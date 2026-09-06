"""Adapter thu tu.

Mot phien chat web = mot thread_id, nen ThreadScope dung lai y nguyen — memory va
hang rao chong ro ri cross-thread ap dung cho web ma khong phai viet them dong nao.
"""

import time
import uuid
from dataclasses import dataclass
from typing import Literal, TypeAlias

from agents.domain.message import InboundMessage

WEB_SENDER_ID = "web-user"
WEB_MAX_MESSAGE_CHARS = 8_000


def web_channel_key(thread_id: str) -> str:
    """Kenh Redis pub/sub cho mot thread. api SUBSCRIBE, worker PUBLISH."""
    return f"web:out:{thread_id}"


@dataclass(frozen=True, slots=True)
class TypingEvent:
    type: Literal["typing"] = "typing"


@dataclass(frozen=True, slots=True)
class FinalEvent:
    text: str
    type: Literal["final"] = "final"


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    text: str
    type: Literal["error"] = "error"


#: Su kien day xuong SSE. UI hien duoc bot dang lam gi, khong chi cau tra loi cuoi.
#:
#: Khong stream tung token: LlmPort chua co streaming, va vong ReAct xen ke tool call
#: lam streaming roi. Doi lai, voi mot agent co cong cu thi xem no dang GOI GI con ro
#: hon xem tung chu hien ra. Su kien ReAct (thought/tool_call/observation) duoc
#: chuyen tiep nguyen dang tu stages/generate.py.
WebEvent: TypeAlias = TypingEvent | FinalEvent | ErrorEvent


def normalize_web_input(thread_id: str, text: str) -> InboundMessage:
    return InboundMessage(
        platform="web",
        thread_id=thread_id,
        sender_id=WEB_SENDER_ID,
        sender_name="Bạn",
        text=text,
        # Web la hoi thoai 1-1: khong can mention.
        is_group=False,
        mentioned_bot=True,
        message_id=str(uuid.uuid4()),
        timestamp=int(time.time() * 1000),
        trace_id=str(uuid.uuid4()),
    )
