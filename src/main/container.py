"""Dependency injection thu cong. Mot ham tra ve object — nhin la biet cai gi noi
vao cai gi. Khong dung framework DI.

`channel` KHONG nam o day: moi entrypoint tu cam kenh cua minh vao (CLI in ra
terminal, worker gui qua adapter cua tung nen tang).
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from agents.pipeline.handle_message import Deps, ReactLimits, ReplyModel
from agents.policy.access import AccessRules
from agents.ports.channel import ChannelPort
from agents.ports.knowledge import KnowledgePort, RetrievedChunk
from config import get_settings
from infra.allowlist import load_allowed_threads
from infra.db import fetch
from infra.logger import get_logger
from infra.ratelimit import rate_limit
from llm.models import MODELS
from llm.openai_client import llm
from memory.repository.fact_repo import FACT_TABLE
from memory.repository.message_repo import message_repo
from tools.registry import tool_port

#: Section 6.1 chot 15 tin gan nhat cho L1.
RECENT_LIMIT = 15


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class EmptyKnowledge:
    """TODO(giai-doan-6): knowledge/retrieve.

    Rong = "khong tim thay trong tai lieu", dung nghia hop dong cua port, nen hien
    tai khong can nhanh dac biet nao.
    """

    async def search(self, query: str, k: int) -> list[RetrievedChunk]:
        return []


@dataclass(frozen=True, slots=True)
class Container:
    """Deps dung chung, thieu dung mot thu: channel."""

    deps_without_channel: Deps


#: Hai bang co cot vector. Bang fact la L3 (dang chay), `kb_chunk` la L4 (RAG,
#: Giai doan 6). Kiem ca hai: lech o bang nao cung lam INSERT that bai luc chay.
#:
#: Ten bang fact lay tu hang so cua repository chu khong go lai o day — xem
#: memory/repository/fact_repo.py.
_VECTOR_COLUMNS = (FACT_TABLE, "kb_chunk")


async def assert_embedding_dim() -> None:
    """Chan cung: so chieu model embedding phai khop cot VECTOR(n) trong DB.

    Khong co buoc nay, loi se hien ra duoi dang "ket qua tim kiem kem" — ba tuan sau.
    """
    settings = get_settings()
    if settings.EMBEDDING_PROVIDER == "fake":
        get_logger().warning("EMBEDDING_PROVIDER=fake — bo qua kiem tra so chieu, RAG chua bat")
        return

    # atttypmod cua cot pgvector CHINH LA so chieu.
    #
    # Ban dau viet `atttypmod - 4`, chep tu quy uoc cua varchar (do dai + 4 byte
    # header). pgvector khong dung quy uoc do. Loi nay song sot rat lau vi nhanh
    # `EMBEDDING_PROVIDER=fake` o tren thoat truoc khi cham toi day — chot chan chi
    # duoc thu lan dau tien luc bat provider that, va no bao mot loi sai ve mot
    # migration khong he hong.
    for table in _VECTOR_COLUMNS:
        rows = await fetch(
            """SELECT atttypmod AS dim
                 FROM pg_attribute
                WHERE attrelid = $1::regclass AND attname = 'embedding'""",
            table,
        )
        dim = rows[0]["dim"] if rows else None
        if dim != settings.EMBEDDING_DIM:
            raise RuntimeError(
                f"So chieu embedding lech: EMBEDDING_DIM={settings.EMBEDDING_DIM} nhung cot "
                f"{table}.embedding la VECTOR({dim}). Doi so chieu la mot migration moi, "
                "khong phai doi bien moi truong."
            )


async def build_deps(channel: ChannelPort) -> Deps:
    await assert_embedding_dim()

    settings = get_settings()
    log = get_logger()

    specs = tool_port.specs()
    log.info(
        "cong cu da san sang" if specs else "khong co cong cu nao duoc bat",
        tools=[s.name for s in specs],
    )

    knowledge: KnowledgePort = EmptyKnowledge()
    reply_model = MODELS["reply"]

    return Deps(
        llm=llm,
        memory=message_repo,
        knowledge=knowledge,
        channel=channel,
        rate_limit=rate_limit,
        clock=SystemClock(),
        logger=log,
        tools=tool_port,
        access_rules=AccessRules(
            group_policy=settings.GROUP_POLICY,
            dm_policy=settings.DM_POLICY,
            # Doc lai moi luot, khong cache: `cli allow` co hieu luc ngay, khong
            # phai khoi dong lai worker. Xem infra/allowlist.py.
            allowed_threads=await load_allowed_threads(),
        ),
        bot_name=settings.BOT_MENTION_NAME,
        reply=ReplyModel(max_tokens=reply_model.max_tokens, effort=reply_model.effort),
        react=ReactLimits(
            max_iterations=settings.REACT_MAX_ITERATIONS,
            max_tool_calls=settings.REACT_MAX_TOOL_CALLS,
            deadline_ms=settings.REACT_DEADLINE_MS,
        ),
        recent_limit=RECENT_LIMIT,
    )
