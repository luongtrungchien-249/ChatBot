"""ThreadScope — khoa chong ro ri memory cross-group.

Khong bao gio truyen platform + thread_id roi rac. Truyen mot object.
Ly do: khong ai quen tham so thu hai cua mot object ca.
"""

from dataclasses import dataclass
from typing import Literal

Platform = Literal["zalo_bot", "zalo_personal", "messenger", "cli", "web"]


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
