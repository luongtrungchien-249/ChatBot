"""Cong cu ma agent duoc phep goi.

tools/ goi mang ra ngoai nen la HA TANG (L1) — agents/ chi thay no qua port nay.
Luat 1 trong .importlinter cuong che dieu do.

ToolDefinition mo ta NHIEU hon ToolSpec ma API can. Phan thua (requirements,
failure_modes) khong gui len model — no o day de nguoi doc code biet cong cu nay
can khoa gi, ton bao nhieu, va hong theo kieu nao, ma khong phai mo tung file
implementation ra doc.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from .llm import CallContext, ToolCall, ToolSpec


@dataclass(frozen=True, slots=True)
class ToolRequirements:
    rate_limit: str
    cost_per_call: str
    timeout_ms: int
    #: TEN bien moi truong, khong phai gia tri. None = khong can khoa.
    api_key: str | None = None


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    #: Model doc dong nay de chon cong cu. Viet cho MODEL doc, khong phai cho nguoi.
    description: str
    parameters: dict[str, Any]
    requirements: ToolRequirements
    returns: str
    failure_modes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ToolResult:
    #: Khop voi ToolCall.id. Thieu mot cai la ca request 400.
    tool_call_id: str
    name: str
    #: Van ban dua vao prompt. Da duoc boc the va cat theo tran tang 'tool'.
    content: str
    ok: bool
    #: Cong cu chay het bao lau — de biet cong cu nao dang keo p95 len.
    latency_ms: int


class ToolPort(Protocol):
    def specs(self) -> tuple[ToolDefinition, ...]:
        """Cong cu dang THUC SU dung duoc.

        Thieu khoa API thi KHONG khai o day — de model thay mot cong cu roi goi that
        bai la cach nhanh nhat de no bia ra ket qua.
        """
        ...

    async def call_many(
        self, calls: tuple[ToolCall, ...], ctx: CallContext
    ) -> tuple[ToolResult, ...]:
        """call_many chu khong phai call: model tra nhieu tool_call trong MOT message,
        va chung phai chay dong thoi.

        Tra ve DU so ket qua, ke ca cai that bai — thieu mot tool_call_id la API 400.
        """
        ...


def to_spec(definition: ToolDefinition) -> ToolSpec:
    """Chuyen sang dang API nhan. Phan requirements khong gui len model."""
    return ToolSpec(
        name=definition.name,
        description=definition.description,
        input_schema=definition.parameters,
    )
