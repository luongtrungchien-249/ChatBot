"""ThreadScope — khoa chong ro ri memory cross-group.

Khong bao gio truyen platform + thread_id roi rac. Truyen mot object.
Ly do: khong ai quen tham so thu hai cua mot object ca.
"""

from dataclasses import dataclass
from typing import Literal

#: Messenger da bi bo khoi pham vi (07/09/2026) — chi tich hop Zalo. Giu lai
#: `zalo_personal` vi no van la duong du phong neu Bot Platform khong du cho nhom.
Platform = Literal["zalo_bot", "zalo_personal", "cli", "web"]


@dataclass(frozen=True, slots=True)
class ThreadScope:
    platform: Platform
    thread_id: str


def scope_key(scope: ThreadScope) -> str:
    return f"{scope.platform}:{scope.thread_id}"


def user_subject(sender_id: str) -> str:
    """subject_id trong memory_fact: 'user:xxx'."""
    return f"user:{sender_id}"


def thread_subject(thread_id: str) -> str:
    """subject_id trong memory_fact: 'thread:xxx'."""
    return f"thread:{thread_id}"
