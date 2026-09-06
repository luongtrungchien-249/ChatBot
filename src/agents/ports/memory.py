"""MOI phuong thuc nhan ThreadScope o tham so DAU TIEN.

Khong duoc them overload nao bo no. Day la hang rao chong ro ri cross-group,
khong phai toi uu hoa.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from ..domain.message import StoredMessage
from ..domain.thread import ThreadScope

FactSource = Literal["explicit", "implicit"]


@dataclass(frozen=True, slots=True)
class Fact:
    id: str
    subject_id: str
    content: str
    source: FactSource
    confidence: float
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NewFact:
    subject_id: str
    content: str
    source: FactSource
    confidence: float
    created_by: str


@dataclass(frozen=True, slots=True)
class NewMessage:
    """Tin nhan can ghi vao L1. Khoa chinh la (platform, message_id)."""

    message_id: str
    sender_id: str
    sender_name: str
    text: str
    is_group: bool
    #: Cau tra loi cua bot cung phai luu, neu khong L2 tom tat se thieu mot nua hoi thoai.
    from_bot: bool
    reply_to_id: str | None = None


class MemoryPort(Protocol):
    async def append(self, scope: ThreadScope, msg: NewMessage) -> None:
        """L1: ghi Postgres (nguon that) roi day cache Redis. Trung khoa thi bo qua."""
        ...

    async def recent(self, scope: ThreadScope, limit: int) -> list[StoredMessage]: ...

    async def summary(self, scope: ThreadScope) -> str | None: ...

    async def facts(self, scope: ThreadScope, subject_id: str, query: str) -> list[Fact]: ...

    async def remember(self, scope: ThreadScope, fact: NewFact) -> None: ...

    async def forget(self, scope: ThreadScope, actor_id: str, pattern: str) -> list[Fact]:
        """Tra ve fact khop de HOI XAC NHAN truoc khi revoke. Khong xoa ngay.

        `actor_id` la NGUOI GO LENH. Cai dat phai tu suy ra subject tu day chu khong
        nhan subject tu ben ngoai — neu khong thi go dung mot chuoi la xoa duoc fact
        cua nguoi khac.
        """
        ...

    async def stage_forget(self, scope: ThreadScope, actor_id: str, fact_ids: list[str]) -> None:
        """Ghi nho yeu cau xoa DANG CHO, het han sau vai phut.

        Buoc xac nhan can state qua luot. Khong co no thi mot lan go nham la mat
        sach, ma soft delete lai khong co lenh khoi phuc.
        """
        ...

    async def confirm_forget(
        self, scope: ThreadScope, actor_id: str, choices: tuple[int, ...] = ()
    ) -> int:
        """Thuc hien yeu cau dang cho. Tra ve so fact da revoke; 0 = khong co gi cho.

        `choices` la so thu tu (bat dau tu 1) trong danh sach da liet ke; rong = tat
        ca. So nam ngoai danh sach bi bo qua thay vi nem loi — go nham mot con so
        khong duoc phep lam hong ca thao tac.

        Lay va xoa yeu cau trong MOT buoc: mot cai "dong y" chi duoc dung mot lan.
        """
        ...

    async def list_facts(self, scope: ThreadScope, subject_id: str) -> list[Fact]: ...
