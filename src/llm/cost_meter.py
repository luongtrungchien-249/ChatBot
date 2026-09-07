"""Ghi token in/out/cache moi lan goi -> usage_log + cost:day.

cache_read_tokens la cot dat ra de TRA LOI mot cau hoi khong nhin thay duoc tu ben
ngoai: prompt caching co dang an khong.

Do 06/09/2026: CO — 20/32 lan goi, moi lan 1408-1792 token doc tu cache, dung bang
system prompt (1535 token sau lan do lai 07/09). Input duoc cache tinh $0,025/1M thay vi $0,25/1M.

Neu cot nay tut ve 0 suot thi ai do da lam vo tien to on dinh cua prompt — vi du
noi suy mot bien vao dau SYSTEM_PROMPT — va ban dang tra gia day du cho 1539 token
o MOI cau hoi ma khong he biet.
"""

from dataclasses import dataclass

from agents.domain.thread import ThreadScope
from agents.ports.llm import LlmUsage
from infra.db import execute
from infra.logger import get_logger
from infra.ratelimit import add_cost

from .models import MODELS, Route

_log = get_logger()


def cost_of(route: Route, usage: LlmUsage) -> float:
    """USD cho mot lan goi.

    Gia cache lay tu price_cached_in cua tung model, khong dung he so uoc chung:
    ti le cached/input khac nhau theo model va theo thoi diem.

    usage.input_tokens theo hop dong LlmPort la phan tinh gia DAY DU (da tru phan
    doc tu cache) — llm/openai_client.py chiu trach nhiem chuan hoa.

    OpenAI khong tinh phi ghi cache nen cache_write_tokens luon 0; cot van giu trong
    usage_log de khong phai doi schema neu doi nha cung cap.
    """
    model = MODELS[route]
    per_million = (
        usage.input_tokens * model.price_in
        + usage.cache_read_tokens * model.price_cached_in
        + usage.output_tokens * model.price_out
    )
    return per_million / 1_000_000


@dataclass(frozen=True, slots=True)
class UsageRecord:
    route: Route
    usage: LlmUsage
    scope: ThreadScope
    sender_id: str
    trace_id: str
    latency_ms: int
    ok: bool


async def record_embedding(
    *, model: str, tokens: int, cost_usd: float, latency_ms: int
) -> None:
    """Ghi mot lan goi EMBEDDING.

    Duong rieng chu khong dung `record()`: embedding khong co output token, khong co
    reasoning, khong co cache, va gia cua no khong nam trong MODELS (bang do khai
    model sinh van ban). Nhoi no vao cung mot ham se bat MODELS mang mot loai model
    khac han chi de dung chung mot cau INSERT.

    KHONG co scope/sender: embedding duoc goi tu nhieu cho, ke ca job nen chay khong
    do ai kich hoat. Ba cot do NOT NULL nen dien gia tri he thong.
    """
    try:
        await execute(
            """INSERT INTO usage_log
                 (trace_id, platform, thread_id, sender_id, route, model,
                  input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                  cost_usd, latency_ms, ok)
               VALUES ('system','system','system','system','embed',$1,$2,0,0,0,$3,$4,TRUE)""",
            model,
            tokens,
            cost_usd,
            latency_ms,
        )
        await add_cost(cost_usd)
    except Exception as error:
        _log.error("khong ghi duoc usage_log cho embedding", err=str(error))


async def record(entry: UsageRecord) -> float:
    """Ghi mot lan goi.

    KHONG duoc nem loi ra ngoai: hong ke toan thi van phai tra loi nguoi dung, nhung
    phai hien trong log de con biet ma sua.
    """
    cost = cost_of(entry.route, entry.usage)

    try:
        await execute(
            """INSERT INTO usage_log
                 (trace_id, platform, thread_id, sender_id, route, model,
                  input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                  cost_usd, latency_ms, ok)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
            entry.trace_id,
            entry.scope.platform,
            entry.scope.thread_id,
            entry.sender_id,
            entry.route,
            MODELS[entry.route].id,
            entry.usage.input_tokens,
            entry.usage.output_tokens,
            entry.usage.cache_read_tokens,
            entry.usage.cache_write_tokens,
            cost,
            entry.latency_ms,
            entry.ok,
        )
        await add_cost(cost)
    except Exception as error:
        _log.error(
            "khong ghi duoc usage_log — ngan sach ngay dang bi dem thieu",
            trace_id=entry.trace_id,
            err=str(error),
        )

    return cost
