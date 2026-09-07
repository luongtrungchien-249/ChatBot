"""Dependency injection thu cong. Mot ham tra ve object — nhin la biet cai gi noi
vao cai gi. Khong dung framework DI.

`channel` KHONG nam o day: moi entrypoint tu cam kenh cua minh vao (CLI in ra
terminal, worker gui qua adapter cua tung nen tang).
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from agents.domain.thread import Platform
from agents.pipeline.handle_message import Deps, ReactLimits, ReplyModel
from agents.policy.access import AccessRules
from agents.ports.channel import ChannelPort
from agents.ports.knowledge import KnowledgePort
from config import get_settings
from infra.allowlist import load_allowed_threads
from infra.db import fetch
from infra.logger import get_logger
from infra.ratelimit import rate_limit
from knowledge.retrieve.service import knowledge as hybrid_knowledge
from llm.models import MODELS
from llm.openai_client import llm
from memory.repository.fact_repo import FACT_TABLE
from memory.repository.message_repo import message_repo
from tools.knowledge_search import refresh_availability
from tools.registry import tool_port

#: Section 6.1 chot 15 tin gan nhat cho L1.
RECENT_LIMIT = 15

#: Deadline cua vong ReAct theo TUNG nen tang, mili-giay.
#:
#: Mot con so chung la sai: giao dien web co the cho lau va hien tien do tung buoc,
#: con nhom chat thi khong — mot cau tra loi ve sau hai phut la cau tra loi cho mot
#: doan hoi thoai da di qua. REACT_DEADLINE_MS trong .env la gia tri cho nen tang
#: khong khai o day.
#:
#: 45s cho Zalo la SO DO DUOC, khong phai so doan. Ban truoc dat 20s theo con so
#: "15s Zalo" trong ke hoach — nhung con so do viet TRUOC khi co cong cu nao. Mot
#: luot co tra cuu can: goi model chon cong cu (~3s) + chay cong cu (3-10s) + goi
#: model viet cau tra loi (~8-10s), tuc 15-25s cho MOT vong, va co the hai vong.
#:
#: Do tren 26 lan goi that: p50 3,2s, p90 8,7s, khong lan nao qua 10s. Nen tran
#: khong nam o tung lan goi ma o TONG vong — va 20s cat dung giua luc model dang
#: viet cau tra loi.
#:
#: Cach hong te den muc nao: het deadline khi chua co chu nao thi stages/generate.py
#: tra ve loi, va nguoi dung nhan "minh dang bi cham" sau 20 giay cho — cong voi
#: toan bo ket qua tra cuu bi vut di. Da do duoc: luot dau tien cua mot cuoc hoi
#: thoai hong nhu vay, va luot sau do mat ngu canh nen bot hoi lai lung tung.
_DEADLINE_MS: dict[Platform, int] = {
    "web": 60_000,
    "cli": 60_000,
    "zalo_bot": 45_000,
    "zalo_personal": 45_000,
}


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


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


#: assert_embedding_dim() da chay xong chua. So chieu cot la thuoc tinh cua SCHEMA,
#: no khong doi giua hai tin nhan — ma build_deps() thi chay o MOI tin, nen kiem lai
#: moi lan la hai cau truy van pg_attribute cho moi cau hoi.
_dim_checked = False

#: Da do xem kho tai lieu co gi chua. Cung ly do mot-lan nhu _dim_checked.
_kb_checked = False


async def assert_embedding_dim() -> None:
    """Chan cung: so chieu model embedding phai khop cot VECTOR(n) trong DB.

    Khong co buoc nay, loi se hien ra duoi dang "ket qua tim kiem kem" — ba tuan sau.

    Chay dung MOT lan cho moi process. Doi so chieu la mot migration moi, tuc la
    phai khoi dong lai — nen khong co truong hop nao no dung o giua doi ca.
    """
    global _dim_checked
    if _dim_checked:
        return

    settings = get_settings()
    if settings.EMBEDDING_PROVIDER == "fake":
        get_logger().warning("EMBEDDING_PROVIDER=fake — bo qua kiem tra so chieu, RAG chua bat")
        _dim_checked = True
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

    _dim_checked = True


async def build_deps(channel: ChannelPort, platform: Platform | None = None) -> Deps:
    await assert_embedding_dim()

    settings = get_settings()
    log = get_logger()

    # Cung mot lan chay duy nhat nhu assert_embedding_dim: dem chunk o moi tin nhan
    # la mot cau SQL cho moi cau hoi de tra loi mot dieu chi doi sau moi lan nap.
    global _kb_checked
    if not _kb_checked:
        _kb_checked = True
        log.info("kho tai lieu", co_tai_lieu=await refresh_availability())

    specs = tool_port.specs()
    log.info(
        "cong cu da san sang" if specs else "khong co cong cu nao duoc bat",
        tools=[s.name for s in specs],
    )

    knowledge: KnowledgePort = hybrid_knowledge
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
            deadline_ms=_DEADLINE_MS.get(platform, settings.REACT_DEADLINE_MS)
            if platform
            else settings.REACT_DEADLINE_MS,
        ),
        recent_limit=RECENT_LIMIT,
    )
