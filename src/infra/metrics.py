"""Doc `usage_log` — tien di dau, cham o dau, hong bao nhieu.

Bang nay DA co du lieu that tu ngay dau, nen mot cau SELECT o day dung duoc ngay
hom nay va khong can dung them gi. Grafana la buoc sau, khong phai buoc dau.

Moi ham o day chi DOC. Khong ham nao ghi, khong ham nao xoa.
"""

import math
import time
from dataclasses import dataclass

from config import get_settings

from .db import fetch
from .queue_metrics import queue_age
from .ratelimit import spent_today
from .redis_client import aw, get_redis


@dataclass(frozen=True, slots=True)
class RouteStats:
    route: str
    model: str
    calls: int
    errors: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: float
    avg_latency_ms: int
    p95_latency_ms: int


@dataclass(frozen=True, slots=True)
class TurnStats:
    """Do tre theo LUOT — thu nguoi dung thuc su cam nhan.

    `usage_log.latency_ms` la do tre cua MOT LAN GOI. Mot luot co tra cuu gom nhieu
    lan goi model cong nhieu lan chay cong cu, nen hai con so do lech nhau vai lan.
    Wall-clock duoc worker ghi trong `turn_telemetry`; khong cong do tre upstream
    vi cac tool co the chay song song. `usage_log` chi phan loai co/khong tool.
    """

    #: True = luot nay co tra cuu.
    used_tools: bool
    turns: int
    p50_ms: int
    p95_ms: int
    max_ms: int


@dataclass(frozen=True, slots=True)
class CacheStats:
    """Prompt caching co dang an khong.

    Cot nay tra loi mot cau hoi khong nhin thay duoc tu ben ngoai. Neu no tut ve 0
    suot thi ai do da lam vo tien to on dinh cua prompt — vi du noi suy mot bien vao
    dau SYSTEM_PROMPT — va ta dang tra gia day du cho ~1500 token o MOI cau hoi.
    """

    calls_with_cache: int
    total_calls: int
    avg_cached_tokens: int


async def route_stats(days: int = 7) -> list[RouteStats]:
    rows = await fetch(
        """SELECT route, model,
                  count(*)                                   AS calls,
                  count(*) FILTER (WHERE NOT ok)             AS errors,
                  coalesce(sum(input_tokens), 0)             AS input_tokens,
                  coalesce(sum(output_tokens), 0)            AS output_tokens,
                  coalesce(sum(cache_read_tokens), 0)        AS cache_read_tokens,
                  coalesce(sum(cost_usd), 0)                 AS cost_usd,
                  coalesce(avg(latency_ms), 0)               AS avg_latency,
                  coalesce(
                    percentile_disc(0.95) WITHIN GROUP (ORDER BY latency_ms), 0
                  )                                          AS p95_latency
             FROM usage_log
            WHERE created_at > now() - ($1 || ' days')::interval
            GROUP BY route, model
            ORDER BY sum(cost_usd) DESC""",
        str(days),
    )
    return [
        RouteStats(
            route=r["route"],
            model=r["model"],
            calls=int(r["calls"]),
            errors=int(r["errors"]),
            input_tokens=int(r["input_tokens"]),
            output_tokens=int(r["output_tokens"]),
            cache_read_tokens=int(r["cache_read_tokens"]),
            cost_usd=float(r["cost_usd"]),
            avg_latency_ms=int(r["avg_latency"]),
            p95_latency_ms=int(r["p95_latency"]),
        )
        for r in rows
    ]


async def turn_stats(days: int = 7) -> list[TurnStats]:
    """Do tre tung luot, tach theo CO/KHONG tra cuu.

    Muc tieu khac nhau cho hai nhom, va do la ly do phai tach: mot luot co tra cuu bat
    buoc hai lan goi model cong thoi gian chay cong cu, nen ep no ve cung muc voi luot
    khong tra cuu la ep bo tra cuu. Gop chung lai thi khong biet dang truot cai nao.

    Chi tinh cac turn co telemetry worker; du lieu cu khong duoc suy doan wall-clock.
    """
    rows = await fetch(
        """WITH luot AS (
             SELECT EXISTS (SELECT 1 FROM usage_log u
                            WHERE u.trace_id = t.trace_id AND u.route = 'tool') AS co_tra_cuu,
                    t.latency_ms AS tong_ms
               FROM turn_telemetry t
              WHERE t.created_at > now() - ($1 || ' days')::interval
           )
           SELECT co_tra_cuu,
                  count(*)                                          AS luot,
                  percentile_disc(0.5)  WITHIN GROUP (ORDER BY tong_ms) AS p50,
                  percentile_disc(0.95) WITHIN GROUP (ORDER BY tong_ms) AS p95,
                  max(tong_ms)                                      AS mx
             FROM luot
            GROUP BY co_tra_cuu
            ORDER BY co_tra_cuu""",
        str(days),
    )
    return [
        TurnStats(
            used_tools=bool(r["co_tra_cuu"]),
            turns=int(r["luot"]),
            p50_ms=int(r["p50"]),
            p95_ms=int(r["p95"]),
            max_ms=int(r["mx"]),
        )
        for r in rows
    ]


async def cache_stats(days: int = 7) -> CacheStats:
    rows = await fetch(
        """SELECT count(*) FILTER (WHERE cache_read_tokens > 0) AS co_cache,
                  count(*)                                      AS tong,
                  coalesce(round(avg(cache_read_tokens)
                    FILTER (WHERE cache_read_tokens > 0)), 0)   AS tb
             FROM usage_log
            WHERE ok AND route = 'reply'
              AND created_at > now() - ($1 || ' days')::interval""",
        str(days),
    )
    row = rows[0] if rows else None
    if row is None:
        return CacheStats(calls_with_cache=0, total_calls=0, avg_cached_tokens=0)
    return CacheStats(
        calls_with_cache=int(row["co_cache"]),
        total_calls=int(row["tong"]),
        avg_cached_tokens=int(row["tb"]),
    )


async def message_stats(days: int = 7) -> list[tuple[str, int, int]]:
    """(ngay, so tin vao, so tin bot tra loi). Theo gio Viet Nam, khong theo UTC."""
    rows = await fetch(
        """SELECT to_char(created_at AT TIME ZONE 'Asia/Ho_Chi_Minh', 'YYYY-MM-DD') AS ngay,
                  count(*) FILTER (WHERE NOT from_bot) AS vao,
                  count(*) FILTER (WHERE from_bot)     AS ra
             FROM inbound_message
            WHERE created_at > now() - ($1 || ' days')::interval
            GROUP BY 1 ORDER BY 1 DESC""",
        str(days),
    )
    return [(r["ngay"], int(r["vao"]), int(r["ra"])) for r in rows]


async def budget_today(budget_usd: float) -> tuple[float, float]:
    """(da tieu, ngan sach). Doc dung khoa `cost:day` ma chot chan dang dung."""
    return await spent_today(), budget_usd


def _line(name: str, labels: str, value: float) -> str:
    return f"{name}{{{labels}}} {value}" if labels else f"{name} {value}"


def _route_labels(stats: RouteStats) -> str:
    def escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')

    return f'route="{escape(stats.route)}",model="{escape(stats.model)}"'


async def prometheus_text(days: int, budget_usd: float) -> str:
    """Dinh dang phoi bay cua Prometheus. Grafana doc thang duoc.

    Day la ANH CHUP hien tai tinh tu Postgres, khong phai bo dem trong bo nho: ba
    process (`api`, `worker`, `zalo`) la ba tien trinh, nen bo dem cuc bo cua tien
    trinh nao chi ke duoc phan viec cua rieng no. Postgres thi ca ba cung ghi vao.

    Doi lai, moi lan scrape la vai cau GROUP BY. Giu chu ki scrape >= 30s.
    """
    routes = await route_stats(days)
    cache = await cache_stats(days)
    turns = await turn_stats(days)
    spent, budget = await budget_today(budget_usd)

    out: list[str] = [
        "# HELP cp_budget_spent_usd Chi tieu hom nay, theo gio Viet Nam.",
        "# TYPE cp_budget_spent_usd gauge",
        _line("cp_budget_spent_usd", "", round(spent, 6)),
        "# HELP cp_budget_limit_usd Chot chan ngan sach ngay.",
        "# TYPE cp_budget_limit_usd gauge",
        _line("cp_budget_limit_usd", "", budget),
        "# HELP cp_llm_calls_total So lan goi model.",
        "# TYPE cp_llm_calls_total gauge",
    ]
    for r in routes:
        tag = _route_labels(r)
        out.append(_line("cp_llm_calls_total", tag, r.calls))
    out += ["# HELP cp_llm_errors_total So lan goi that bai.", "# TYPE cp_llm_errors_total gauge"]
    for r in routes:
        out.append(_line("cp_llm_errors_total", _route_labels(r), r.errors))
    out += ["# HELP cp_llm_cost_usd Chi phi theo route.", "# TYPE cp_llm_cost_usd gauge"]
    for r in routes:
        out.append(_line("cp_llm_cost_usd", _route_labels(r), round(r.cost_usd, 6)))
    out += [
        "# HELP cp_llm_latency_p95_ms Do tre p95. Muc tieu duong tra loi: < 5000.",
        "# TYPE cp_llm_latency_p95_ms gauge",
    ]
    for r in routes:
        out.append(_line("cp_llm_latency_p95_ms", _route_labels(r), r.p95_latency_ms))
    out += [
        "# HELP cp_turn_latency_p95_ms Do tre CA LUOT — thu nguoi dung cam nhan.",
        "# Muc tieu: khong tra cuu < 5000, co tra cuu < 15000.",
        "# TYPE cp_turn_latency_p95_ms gauge",
    ]
    for t in turns:
        tag = f'used_tools="{str(t.used_tools).lower()}"'
        out.append(_line("cp_turn_latency_p95_ms", tag, t.p95_ms))
    out += ["# HELP cp_turns_total So luot tra loi.", "# TYPE cp_turns_total gauge"]
    for t in turns:
        out.append(_line("cp_turns_total", f'used_tools="{str(t.used_tools).lower()}"', t.turns))
    out += [
        "# HELP cp_prompt_cache_hit_ratio Ti le luot tra loi doc duoc cache. Tut ve 0 la",
        "# tien to on dinh cua prompt da vo — xem agents/prompt/system.py.",
        "# TYPE cp_prompt_cache_hit_ratio gauge",
        _line(
            "cp_prompt_cache_hit_ratio",
            "",
            round(cache.calls_with_cache / cache.total_calls, 4) if cache.total_calls else 0.0,
        ),
    ]
    runtime = await fetch(
        """SELECT outcome,count(*) n,
             percentile_disc(0.95) WITHIN GROUP (ORDER BY latency_ms) latency,
             percentile_disc(0.95) WITHIN GROUP (ORDER BY queue_wait_ms) queue_wait
           FROM turn_telemetry WHERE created_at > now() - interval '5 minutes'
           GROUP BY outcome"""
    )
    out += [
        "# HELP cp_runtime_turns Turn outcomes in the last 5 minutes (rolling gauge).",
        "# TYPE cp_runtime_turns gauge",
        "# HELP cp_runtime_turn_latency_p95_ms Worker wall-clock p95 in the last 5 minutes.",
        "# TYPE cp_runtime_turn_latency_p95_ms gauge",
        "# HELP cp_queue_wait_p95_ms Queue wait p95 in the last 5 minutes.",
        "# TYPE cp_queue_wait_p95_ms gauge",
        "# HELP cp_heartbeat_age_seconds Seconds since last process heartbeat.",
        "# TYPE cp_heartbeat_age_seconds gauge",
        "# HELP cp_queue_depth Jobs currently queued, including in-progress jobs.",
        "# TYPE cp_queue_depth gauge",
        "# HELP cp_queue_oldest_age_seconds Original enqueue age, including deferred/running jobs.",
        "# TYPE cp_queue_oldest_age_seconds gauge",
        "# HELP cp_queue_age_complete All queued timestamps read (1); unknown age (0).",
        "# TYPE cp_queue_age_complete gauge",
    ]
    by_outcome = {row["outcome"]: row for row in runtime}
    for outcome in ("completed", "error"):
        row = by_outcome.get(outcome)
        tag = f'outcome="{outcome}"'
        out.append(_line("cp_runtime_turns", tag, int(row["n"]) if row else 0))
        # No percentile exists without observations; do not invent a zero latency.
        if row:
            out.append(_line("cp_runtime_turn_latency_p95_ms", tag, int(row["latency"])))
            out.append(_line("cp_queue_wait_p95_ms", tag, int(row["queue_wait"])))

    details = await fetch(
        """SELECT reason,count(*) n,
             count(*) FILTER (WHERE replied AND fallback IS NOT NULL) measured_replies,
             count(*) FILTER (WHERE replied AND fallback) fallbacks,
             count(react_iterations) react_turns,
             coalesce(sum(react_iterations),0) iterations,
             coalesce(sum(tool_calls),0) tool_calls,
             coalesce(sum(tool_errors),0) tool_errors,
             coalesce(sum(poetry_calls),0) poetry_calls,
             count(poetry_calls) poetry_turns,
             coalesce(sum(recorded_cost_usd),0) recorded_cost_usd
           FROM turn_telemetry WHERE created_at > now() - interval '5 minutes'
           GROUP BY reason"""
    )
    out += [
        "# HELP cp_runtime_turn_reason Last-attempt turn reasons in the last 5 minutes.",
        "# TYPE cp_runtime_turn_reason gauge",
    ]
    for row in details:
        out.append(_line("cp_runtime_turn_reason", f'reason="{row["reason"]}"', int(row["n"])))
    for name, column, description in (
        (
            "cp_runtime_measured_replies",
            "measured_replies",
            "Replies with measured fallback status",
        ),
        ("cp_runtime_fallbacks", "fallbacks", "Fallback replies actually sent"),
        ("cp_runtime_react_turns", "react_turns", "Turns with measured ReAct counts"),
        ("cp_runtime_react_iterations", "iterations", "ReAct model calls including failures"),
        ("cp_runtime_tool_calls", "tool_calls", "Tool calls requested during ReAct"),
        ("cp_runtime_tool_errors", "tool_errors", "Failed tool observations during ReAct"),
        ("cp_runtime_poetry_calls", "poetry_calls", "Poetry model and judge attempts"),
        ("cp_runtime_poetry_turns", "poetry_turns", "Turns with measured poetry attempts"),
    ):
        out += [
            f"# HELP {name} {description}, last attempts in a rolling 5-minute window.",
            f"# TYPE {name} gauge",
            _line(name, "", sum(int(row.get(column, 0)) for row in details)),
        ]
    out += [
        "# HELP cp_runtime_recorded_cost_usd Trace-linked usage cost estimates, rolling 5 minutes.",
        "# TYPE cp_runtime_recorded_cost_usd gauge",
        _line(
            "cp_runtime_recorded_cost_usd",
            "",
            round(sum(float(row["recorded_cost_usd"]) for row in details), 6),
        ),
    ]
    out.extend(await _rag_prometheus())
    failures = await fetch(
        """SELECT failure_service,failure_kind,count(*) n FROM turn_telemetry
           WHERE created_at > now() - interval '5 minutes'
             AND failure_kind IS NOT NULL GROUP BY failure_service,failure_kind"""
    )
    out += [
        "# HELP cp_runtime_upstream_failures Measured last-attempt upstream causes, rolling 5m.",
        "# TYPE cp_runtime_upstream_failures gauge",
    ]
    for row in failures:
        out.append(
            _line(
                "cp_runtime_upstream_failures",
                f'service="{row["failure_service"]}",kind="{row["failure_kind"]}"',
                int(row["n"]),
            )
        )
    redis = get_redis()
    out += [
        "# HELP cp_process_expected Explicit operator expectation of an optional process.",
        "# TYPE cp_process_expected gauge",
        _line(
            "cp_process_expected", 'component="zalo"',
            int(get_settings().ZALO_POLLING_EXPECTED),
        ),
        "# HELP cp_heartbeat_observed A valid process heartbeat was observed (1) or not (0).",
        "# TYPE cp_heartbeat_observed gauge",
    ]
    for component in ("worker", "maintenance", "zalo"):
        timestamp = await aw(redis.get(f"heartbeat:{component}"))
        try:
            measured = float(timestamp) if timestamp is not None else None
            if measured is not None and (not math.isfinite(measured) or measured < 0):
                measured = None
        except (ValueError, TypeError):
            measured = None
        tag = f'component="{component}"'
        out.append(_line("cp_heartbeat_observed", tag, int(measured is not None)))
        if measured is not None:
            out.append(_line("cp_heartbeat_age_seconds", tag, max(0.0, time.time() - measured)))
    for queue in ("reply", "maintenance"):
        depth = await aw(redis.zcard(queue))
        out.append(_line("cp_queue_depth", f'queue="{queue}"', depth))
        observed_age = await queue_age(queue)
        out.append(_line("cp_queue_age_complete", f'queue="{queue}"', int(observed_age.complete)))
        if observed_age.oldest_seconds is not None:
            out.append(
                _line(
                    "cp_queue_oldest_age_seconds", f'queue="{queue}"', observed_age.oldest_seconds
                )
            )
    return chr(10).join(out) + chr(10)


async def _rag_prometheus() -> list[str]:
    rows = await fetch(
        """SELECT outcome,count(*) n,
             count(*) FILTER (WHERE retrieval_degraded
               AND outcome NOT IN ('cancelled','unknown')) retrieval_degraded,
             count(*) FILTER (WHERE rerank_degraded
               AND outcome NOT IN ('cancelled','unknown')) rerank_degraded,
             count(*) FILTER (WHERE (retrieval_degraded OR rerank_degraded)
               AND outcome NOT IN ('cancelled','unknown')) degraded,
             count(*) FILTER (WHERE low_confidence) low_confidence,
             percentile_disc(0.95) WITHIN GROUP (ORDER BY latency_ms) latency
           FROM rag_telemetry WHERE created_at > now() - interval '5 minutes'
           GROUP BY outcome"""
    )
    by_outcome = {row["outcome"]: row for row in rows}
    out = [
        "# HELP cp_rag_requests Knowledge-tool attempts, rolling 5 minutes; not unique turns.",
        "# TYPE cp_rag_requests gauge",
        "# HELP cp_rag_latency_p95_ms Knowledge-tool attempt wall-clock p95, rolling 5 minutes.",
        "# TYPE cp_rag_latency_p95_ms gauge",
        "# HELP cp_rag_degraded_requests Noncancelled degraded attempts, rolling 5 minutes.",
        "# TYPE cp_rag_degraded_requests gauge",
        "# HELP cp_rag_low_confidence_requests Low-confidence attempts, rolling 5 minutes.",
        "# TYPE cp_rag_low_confidence_requests gauge",
    ]
    for outcome in ("found", "empty", "filtered", "uncertain", "error", "cancelled", "unknown"):
        row = by_outcome.get(outcome)
        tag = f'outcome="{outcome}"'
        out.append(_line("cp_rag_requests", tag, int(row["n"]) if row else 0))
        if row:
            out.append(_line("cp_rag_latency_p95_ms", tag, int(row["latency"])))
    for stage, column in (
        ("retrieval", "retrieval_degraded"),
        ("rerank", "rerank_degraded"),
        ("any", "degraded"),
    ):
        out.append(
            _line(
                "cp_rag_degraded_requests",
                f'stage="{stage}"',
                sum(int(row[column]) for row in rows),
            )
        )
    out.append(
        _line("cp_rag_low_confidence_requests", "", sum(int(row["low_confidence"]) for row in rows))
    )
    return out
