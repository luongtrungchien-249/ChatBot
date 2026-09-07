"""CONTEXT ENGINEERING — nam vung cua so ngu canh.

  [ System ] [ History ] [ Current input ] [ Tools ] [ Output ]
    policy    recent/       current task     schemas   buffer
              relevant

Nguyen tac xep: thong tin ON DINH truoc, thong tin TUOI sau. Vua hop co che chu y
cua model, vua giu duoc tien to on dinh cho prompt caching.

MOT DIEM KHAC SO DO, ghi ra day de sau nay khong ai di "sua" nham: OpenAI render
`tools` thanh mot khoi RIENG cua request, khong chen vao mang `messages`. Vi vay
"Tools nam sau Current input" dung ve mat khai niem nhung KHONG dieu khien duoc
bang thu tu mang. Vung Tools o day chi mang y nghia ke toan ngan sach.

Moi vung co tran rieng va ghi log phan bi cat. Mot lan cat la mot tin hieu bat
thuong can xem, khong phai chuyen binh thuong (xem budget.py).
"""

from dataclasses import dataclass, field

from ..domain.knowledge import RetrievedChunk
from ..domain.message import StoredMessage
from ..ports.llm import AssistantMessage, LlmMessage, UserMessage
from ..ports.logger import LoggerPort
from ..ports.memory import Fact
from .budget import CHARS_PER_TOKEN, TOKEN_BUDGET, BudgetLayer, trim_to_budget
from .builder import render_facts, render_knowledge
from .system import SYSTEM_PROMPT


@dataclass(frozen=True, slots=True)
class ContextInput:
    question: str
    is_group: bool
    #: History: L1 tin gan nhat, L2 tom tat, L3 fact.
    recent: tuple[StoredMessage, ...] = ()
    summary: str | None = None
    facts: tuple[Fact, ...] = ()
    #: Knowledge di kem History vi cung la "thong tin nen", khong phai cau hoi.
    chunks: tuple[RetrievedChunk, ...] = ()


@dataclass(frozen=True, slots=True)
class ContextEnvelope:
    #: Vung System.
    system: str
    #: Vung History + Current input, da xep dung thu tu.
    messages: tuple[LlmMessage, ...]
    #: Ke toan: moi vung cat mat bao nhieu token.
    trimmed: dict[str, int] = field(default_factory=dict)


def _fit(text: str, layer: BudgetLayer, logger: LoggerPort, trimmed: dict[str, int]) -> str:
    result = trim_to_budget(text, layer)
    if result.trimmed_tokens > 0:
        trimmed[layer] = result.trimmed_tokens
        logger.warning(
            "cat bot ngu canh — kiem tra xem tran co con hop ly khong",
            layer=layer,
            trimmed_tokens=result.trimmed_tokens,
        )
    return result.text


def conversation_turns(
    recent: tuple[StoredMessage, ...], is_group: bool, logger: LoggerPort
) -> tuple[LlmMessage, ...]:
    """L1 -> cac LUOT HOI THOAI THAT, khong phai mot khoi van ban nen.

    DAY LA CHO DA GAY RA MOT LOI NGHIEM TRONG (sua 07/09/2026).

    Ban truoc nen ca lich su vao MOT user message boc trong <hoi_thoai_gan_day>, roi
    chen mot luot assistant GIA — "Minh da doc phan thong tin nen. Ban hoi gi?" —
    truoc cau hoi hien tai. Hau qua: luot assistant NGAY TRUOC cau hoi khong bao gio
    la cau bot vua noi, ma luon la dong gia kia.

    Trong nhom, nguoi dung tra loi cau hoi lam ro cua bot bang mot tu ("arXiv", "AI").
    Tu vi tri cua model, no vua hoi "Ban hoi gi?" va nhan lai dung mot tu — nen no hoi
    lam ro lan nua. Va lan nua. Da do duoc BON luot lien tiep khong mot lan goi cong
    cu, khong mot cau tra loi.

    Te hon: chinh SYSTEM_PROMPT day model rang noi dung trong the la DU LIEU THAM
    KHAO chu khong phai chi thi. Nen cau hoi that cua bot khong nhung bi day ra xa,
    ma con bi gan nhan "chi la tai lieu".

    Gio moi luot la mot message that: nguoi dung -> `user`, bot -> `assistant`. Model
    thay dung hinh dang cua mot cuoc hoi thoai, va luot ngay truoc cau hoi la thu
    chinh no vua noi.
    """
    items = list(recent)

    # Tin cuoi cua NGUOI DUNG chinh la cau dang duoc tra loi: stage 6 (persist) chay
    # truoc stage 10 (recall), nen no da nam trong `recent`. De lai la hoi doi cau hoi.
    if items and not items[-1].from_bot:
        items.pop()
    if not items:
        return ()

    # Cat tu DAU (cu nhat) cho vua tran, khong cat giua mot tin nhan: mot luot bi cut
    # nua chung con kho hieu hon la khong co no.
    limit = int(TOKEN_BUDGET["recent"] * CHARS_PER_TOKEN)
    total = 0
    giu: list[StoredMessage] = []
    for item in reversed(items):
        total += len(item.text) + len(item.sender_name) + 4
        if total > limit and giu:
            break
        giu.append(item)
    giu.reverse()

    if len(giu) < len(items):
        logger.warning(
            "cat bot luot hoi thoai cu — kiem tra xem tran co con hop ly khong",
            layer="recent",
            da_bo=len(items) - len(giu),
        )

    turns: list[LlmMessage] = []
    for item in giu:
        if item.from_bot:
            turns.append(AssistantMessage(content=item.text))
        else:
            # Trong nhom co nhieu nguoi noi: giu ten de model biet ai hoi gi. Trong
            # hoi thoai 1-1 thi cai ten do chi la nhieu.
            name = f"[{item.sender_name}]: " if is_group else ""
            turns.append(UserMessage(content=f"{name}{item.text}"))
    return tuple(turns)


def build_context(data: ContextInput, logger: LoggerPort) -> ContextEnvelope:
    trimmed: dict[str, int] = {}
    background: list[str] = []

    # --- Vung NEN: tai lieu, ghi nho, tom tat. On dinh nhat truoc. ---
    #
    # Ba thu nay THAT SU la du lieu tham khao, nen chung o lai trong mot khoi rieng.
    # Lich su hoi thoai thi khong — xem conversation_turns().
    knowledge = render_knowledge(data.chunks)  # tu ap tran tang 'knowledge'
    if knowledge:
        background.append(knowledge)

    facts = render_facts(data.facts)  # tu ap tran tang 'facts'
    if facts:
        background.append(facts)

    if data.summary:
        summary = _fit(data.summary, "summary", logger, trimmed)
        background.append(f"<tom_tat_truoc_do>\n{summary}\n</tom_tat_truoc_do>")

    # --- Vung CURRENT INPUT: dat CUOI CUNG, sat cau tra loi nhat ---
    question = _fit(data.question, "question", logger, trimmed)

    messages: list[LlmMessage] = []
    if background:
        messages.append(UserMessage(content="\n\n".join(background)))
        messages.append(AssistantMessage(content="Mình đã đọc phần thông tin nền."))

    messages.extend(conversation_turns(data.recent, data.is_group, logger))
    messages.append(UserMessage(content=question))

    return ContextEnvelope(system=SYSTEM_PROMPT, messages=tuple(messages), trimmed=trimmed)
