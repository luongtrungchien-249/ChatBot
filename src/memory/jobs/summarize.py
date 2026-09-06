"""Job nen hoi thoai cu thanh mot ban tom tat (L2).

Chay TREN HANG DOI `maintenance`, khong phai `reply`. Mot job nen ton mot lan goi
model va vai giay; de chung o cung hang doi voi duong tra loi — noi worker chay
max_jobs=1 — la mot cau hoi cua nguoi dung phai xep hang sau mot viec nen.

Nguong: 30 tin chua nen thi nen 15 tin CU NHAT. Giu lai 15 tin de cua so L1 luon
con du du lieu; nen sach thi lan hoi sau bot mat hoan toan ngu canh gan.
"""

import uuid

from agents.domain.thread import ThreadScope
from agents.ports.llm import CallContext
from agents.prompt.instructions import SUMMARIZE_INSTRUCTION
from infra.logger import get_logger
from llm.models import MODELS
from llm.openai_client import llm
from memory.repository.summary_repo import (
    PendingMessage,
    commit_summary,
    count_pending,
    get_summary,
    oldest_pending,
    render_for_summary,
    render_previous,
)

#: Du 30 tin chua nen thi moi chay. Duoi nguong nay, nen la tra tien cho mot viec
#: ma cua so L1 dang lam tot roi.
THRESHOLD = 30

#: Moi lan nen 15 tin, dung bang cua so L1 (section 6.1).
BATCH = 15

#: Nen de quy lam thong tin troi dan. Ke hoach goc da chi ra cam bay "sau 5-6 lan
#: nen summary bat dau sai lech" nhung khong de xuat cach phat hien. Day la cach:
#: dem the he, va keu len khi vuot.
DRIFT_WARN_GENERATIONS = 6

_log = get_logger()


async def summarize_thread(
    scope: ThreadScope, trace_id: str | None = None
) -> list[PendingMessage]:
    """Tra ve LO vua duoc nen. Rong = chua du nguong, khong lam gi.

    Tra ve lo chu khong phai True/False de cho goi chuyen tiep sang viec trich fact
    (L3 implicit) tren DUNG lo do: khong can them cot danh dau "da trich chua", va
    moi tin duoc xet dung mot lan.

    "Khong lam gi" la duong chay pho bien nhat: stage 15 xep hang job nay sau MOI
    luot, va phan lon luot thi thread chua du 30 tin.
    """
    trace = trace_id or str(uuid.uuid4())
    log = _log.bind(trace_id=trace, thread_id=scope.thread_id)

    pending = await count_pending(scope)
    if pending < THRESHOLD:
        log.debug("chua du nguong nen", pending=pending, threshold=THRESHOLD)
        return []

    batch = await oldest_pending(scope, BATCH)
    if not batch:
        return []

    previous = await get_summary(scope)
    if previous is not None and previous.gen_count >= DRIFT_WARN_GENERATIONS:
        # Khong dung lai — mot ban tom tat troi van hon khong co gi. Nhung phai
        # nhin thay duoc, vi day la loi khong bao gio tu bao.
        log.warning(
            "ban tom tat da nen de quy nhieu lan, thong tin co the da troi",
            gen_count=previous.gen_count,
            msg_count=previous.msg_count,
        )

    text = await llm.cheap(
        system=SUMMARIZE_INSTRUCTION,
        input=render_previous(previous) + render_for_summary(batch),
        max_tokens=MODELS["summarize"].max_tokens,
        route="summarize",
        # sender_id 'system': usage_log khai cot nay NOT NULL, va viec nen khong do
        # mot nguoi dung cu the gay ra. Loc theo gia tri nay la biet ngay bao nhieu
        # tien di vao viec nen.
        ctx=CallContext(scope=scope, sender_id="system", trace_id=trace),
    )

    if not text.strip():
        # Model tra rong (het cap cho phan reasoning). KHONG danh dau `summarized`:
        # danh dau ma khong co ban tom tat la xoa 15 tin nhan vinh vien.
        log.error("model tra ban tom tat rong — giu nguyen tin, se thu lai luot sau")
        return []

    await commit_summary(scope, text.strip(), [m.message_id for m in batch], previous)
    log.info("da nen hoi thoai", nen=len(batch), con_lai=pending - len(batch))
    return batch
