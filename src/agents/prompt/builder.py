"""Render tung khoi ngu canh thanh van ban dua vao prompt."""

import re

from ..domain.knowledge import RetrievedChunk
from ..domain.message import StoredMessage
from ..ports.memory import Fact
from .budget import trim_to_budget

_TAG_LOOKALIKE = re.compile(r"</?(tai_lieu|ket_qua_cong_cu|ghi_nho)[^>]*>", re.IGNORECASE)


def sanitize(content: str) -> str:
    """Chan noi dung tu thoat khoi hop bang cach viet the dong cua chinh no.

    Khong lam buoc nay thi mot tai lieu chua `</tai_lieu>` se tu thoat ra khoi hop —
    va do chinh xac la cach nguoi ta pha. Ap cho CA ket qua cong cu (tools/guard.py),
    noi rui ro cao hon nhieu vi van ban do nguoi la soan.
    """
    return _TAG_LOOKALIKE.sub("", content)


def render_knowledge(chunks: tuple[RetrievedChunk, ...]) -> str:
    if not chunks:
        return ""
    body = "\n".join(
        f'<tai_lieu id="{c.chunk_id}" nguon="{c.doc_title}" muc="{c.section or ""}">\n'
        f"{sanitize(c.content)}\n</tai_lieu>"
        for c in chunks
    )
    return trim_to_budget(body, "knowledge").text


def render_facts(facts: tuple[Fact, ...]) -> str:
    if not facts:
        return ""
    body = "<ghi_nho>\n" + "\n".join(f"- {f.content}" for f in facts) + "\n</ghi_nho>"
    return trim_to_budget(body, "facts").text


def render_recent(messages: tuple[StoredMessage, ...], is_group: bool) -> str:
    body = "\n".join(f"[{m.sender_name}]: {m.text}" if is_group else m.text for m in messages)
    return trim_to_budget(body, "recent").text
