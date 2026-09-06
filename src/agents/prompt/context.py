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

from ..domain.message import StoredMessage
from ..ports.knowledge import RetrievedChunk
from ..ports.llm import AssistantMessage, LlmMessage, UserMessage
from ..ports.logger import LoggerPort
from ..ports.memory import Fact
from .budget import BudgetLayer, trim_to_budget
from .builder import render_facts, render_knowledge, render_recent
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


def build_context(data: ContextInput, logger: LoggerPort) -> ContextEnvelope:
    trimmed: dict[str, int] = {}
    history: list[str] = []

    # --- Vung HISTORY: on dinh nhat truoc, tuoi nhat sau ---
    knowledge = render_knowledge(data.chunks)  # tu ap tran tang 'knowledge'
    if knowledge:
        history.append(knowledge)

    facts = render_facts(data.facts)  # tu ap tran tang 'facts'
    if facts:
        history.append(facts)

    if data.summary:
        summary = _fit(data.summary, "summary", logger, trimmed)
        history.append(f"<tom_tat_truoc_do>\n{summary}\n</tom_tat_truoc_do>")

    if data.recent:
        recent = render_recent(data.recent, data.is_group)
        history.append(f"<hoi_thoai_gan_day>\n{recent}\n</hoi_thoai_gan_day>")

    # --- Vung CURRENT INPUT: dat CUOI CUNG, sat cau tra loi nhat ---
    question = _fit(data.question, "question", logger, trimmed)

    # History va Current input di trong hai message tach biet: model phan biet duoc
    # "nen" voi "viec can lam bay gio". Gop lam mot thi cau hoi chim trong ngu canh.
    messages: tuple[LlmMessage, ...]
    if history:
        messages = (
            UserMessage(content="\n\n".join(history)),
            AssistantMessage(content="Mình đã đọc phần thông tin nền. Bạn hỏi gì?"),
            UserMessage(content=question),
        )
    else:
        messages = (UserMessage(content=question),)

    return ContextEnvelope(system=SYSTEM_PROMPT, messages=messages, trimmed=trimmed)
