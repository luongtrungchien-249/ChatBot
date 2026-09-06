"""L3 implicit — bot TU trich fact tu hoi thoai.

MAC DINH TAT (`MEMORY_IMPLICIT_ENABLED=false`). Day la tinh nang de gay rac roi nhat
trong ca he thong: no ghi thong tin ve NGUOI CO TEN ma khong ai bam nut dong y.

Dieu kien tien quyet, lay tu ARCHITECTURE.md section 6.2 va plan section 9: chi bat
SAU KHI cong cu audit chay duoc. `uv run python -m main.cli memory <platform>
<thread_id>` in ra moi fact con hieu luc cua mot thread — khong nhin duoc bot da tu
ghi gi thi khong the cho phep no tu ghi.

Chay tren CUNG MOT LO ma L2 vua nen, khong co lich rieng. Ba cai loi:
  - Khong can them cot danh dau "da trich chua": co `summarized` cua L2 lam luon.
  - Moi tin duoc xet dung mot lan, khong bo sot, khong lam hai lan.
  - Chay khi doan hoi thoai da "nguoi", khong phai giua chung mot cau chuyen.
"""

from agents.domain.thread import ThreadScope, user_subject
from agents.ports.llm import CallContext
from agents.ports.memory import NewFact
from agents.prompt.instructions import EXTRACT_FACTS_INSTRUCTION
from config import get_settings
from infra.logger import get_logger
from llm.models import MODELS
from llm.openai_client import llm
from memory.repository.fact_repo import remember
from memory.repository.summary_repo import PendingMessage

#: Duoi nguong nay thi KHONG ghi. Lay tu ke hoach goc; y nghia la "model phai gan
#: nhu chac chan", chu khong phai "co ve dung".
MIN_CONFIDENCE = 0.8

#: Model bao khong co gi dang nho.
_NOTHING = "KHONG_CO"

_log = get_logger()


def render_for_extract(messages: list[PendingMessage]) -> str:
    """Chi dua tin cua NGUOI. Cau tra loi cua bot bi loai.

    Bot khong phai mot nguon su that ve nguoi dung: no doan, no dien giai, va no lap
    lai loi nguoi dung theo cach cua no. Trich fact tu chinh dau ra cua model la cach
    nhanh nhat de mot suy doan tro thanh "dieu da biet".
    """
    return "\n".join(f"[{m.sender_name}]: {m.text}" for m in messages if not m.from_bot)


def parse_line(line: str, names: dict[str, str]) -> tuple[str, str, float] | None:
    """`ten | noi dung | do tin cay` -> (subject_id, noi dung, do tin cay).

    None khi dong khong dung dinh dang, khi ten khong khop ai trong lo, hoac khi do
    tin cay khong doc duoc. Bo qua thay vi doan: mot fact gan nham nguoi con te hon
    mot fact bi bo sot.
    """
    parts = [p.strip() for p in line.split("|")]
    if len(parts) != 3:
        return None

    name, content, raw_confidence = parts
    sender_id = names.get(name.casefold())
    if sender_id is None or not content:
        return None

    try:
        confidence = float(raw_confidence)
    except ValueError:
        return None
    if not 0.0 <= confidence <= 1.0:
        return None

    return user_subject(sender_id), content, confidence


async def extract_facts(
    scope: ThreadScope, messages: list[PendingMessage], trace_id: str
) -> int:
    """Tra ve so fact da ghi. 0 khi tat, khi khong co gi, hoac khi model tra rac."""
    if not get_settings().MEMORY_IMPLICIT_ENABLED:
        return 0

    log = _log.bind(trace_id=trace_id, thread_id=scope.thread_id)
    body = render_for_extract(messages)
    if not body.strip():
        return 0

    # Ten -> sender_id, chi tu CHINH LO NAY. Model khong duoc gan fact cho mot nguoi
    # no khong thay trong doan hoi thoai vua doc.
    names = {m.sender_name.casefold(): m.sender_id for m in messages if not m.from_bot}

    try:
        raw = await llm.cheap(
            system=EXTRACT_FACTS_INSTRUCTION,
            input=body,
            max_tokens=MODELS["extract_facts"].max_tokens,
            route="extract_facts",
            ctx=CallContext(scope=scope, sender_id="system", trace_id=trace_id),
        )
    except Exception as error:
        # Trich fact la viec phu. Hong thi bo qua luot nay — KHONG duoc lam hong
        # viec nen L2 da commit xong truoc do.
        log.warning("trich fact that bai, bo qua luot nay", err=str(error))
        return 0

    text = raw.strip()
    if not text or text == _NOTHING:
        log.debug("khong co fact nao dang nho")
        return 0

    written = 0
    for line in text.splitlines():
        if not line.strip() or line.strip() == _NOTHING:
            continue

        parsed = parse_line(line, names)
        if parsed is None:
            log.warning("bo qua dong khong doc duoc tu ban trich fact", dong=line[:120])
            continue

        subject_id, content, confidence = parsed
        if confidence < MIN_CONFIDENCE:
            log.info("bo qua fact do tin cay thap", do_tin_cay=confidence, noi_dung=content[:80])
            continue

        # Di qua fact_repo nen van duoc chong trung va phat hien mau thuan y het
        # duong explicit — mot fact bot tu trich khong duoc phep de len fact nguoi
        # dung tu noi ra ma bo qua buoc do.
        await remember(
            scope,
            NewFact(
                subject_id=subject_id,
                content=content,
                source="implicit",
                confidence=confidence,
                created_by="system",
            ),
        )
        written += 1

    if written:
        log.info("da ghi fact tu dong", so_luong=written)
    return written
