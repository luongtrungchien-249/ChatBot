"""Doc `usage_log` — tien di dau, cham o dau, hong bao nhieu.

Bang nay DA co du lieu that tu ngay dau, nen mot cau SELECT o day dung duoc ngay
hom nay va khong can dung them gi. Grafana la buoc sau, khong phai buoc dau.

Moi ham o day chi DOC. Khong ham nao ghi, khong ham nao xoa.
"""

from dataclasses import dataclass

from .db import fetch
from .ratelimit import spent_today


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
    Cong theo `trace_id` moi ra dung thu de so voi muc tieu — moi buoc trong mot luot
    deu mang cung mot trace_id (luat L8).
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

    Bo qua route `embed`: no chay ca ngoai duong phan hoi (job nen, trich fact) nen
    cong vao se lam do tre luot trong sai lech.
    """
    rows = await fetch(
        """WITH luot AS (
             SELECT trace_id,
                    -- Mot luot CO tra cuu la mot luot co it nhat mot buoc route='tool'.
                    -- Khong dung mot cot rieng: xem db/migrations/0010.
                    bool_or(route = 'tool') AS co_tra_cuu,
                    sum(latency_ms)         AS tong_ms
               FROM usage_log
              WHERE route IN ('reply', 'tool')
                AND created_at > now() - ($1 || ' days')::interval
              GROUP BY trace_id
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
        tag = f'route="{r.route}",model="{r.model}"'
        out.append(_line("cp_llm_calls_total", tag, r.calls))
    out += ["# HELP cp_llm_errors_total So lan goi that bai.", "# TYPE cp_llm_errors_total gauge"]
    for r in routes:
        out.append(_line("cp_llm_errors_total", f'route="{r.route}"', r.errors))
    out += ["# HELP cp_llm_cost_usd Chi phi theo route.", "# TYPE cp_llm_cost_usd gauge"]
    for r in routes:
        out.append(_line("cp_llm_cost_usd", f'route="{r.route}"', round(r.cost_usd, 6)))
    out += [
        "# HELP cp_llm_latency_p95_ms Do tre p95. Muc tieu duong tra loi: < 5000.",
        "# TYPE cp_llm_latency_p95_ms gauge",
    ]
    for r in routes:
        out.append(_line("cp_llm_latency_p95_ms", f'route="{r.route}"', r.p95_latency_ms))
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
    return chr(10).join(out) + chr(10)
