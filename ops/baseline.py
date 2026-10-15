"""In baseline van hanh dang Markdown ma khong thay doi du lieu.

Chay: ``uv run python ops/baseline.py``.

Bao cao chi gom metadata, so dem va thong ke tong hop. Khong truy van noi dung tin
nhan, tai lieu hay fact; khong in DSN, API key hoac token.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import get_settings
from infra.db import close_db, fetch
from infra.metrics import cache_stats, route_stats, turn_stats
from infra.redis_client import aw, close_redis, get_redis
from llm.models import model_cho
from memory.repository.fact_repo import count_for_operations

_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


@dataclass(frozen=True, slots=True)
class TestSummary:
    passed: int
    failed: int
    errors: int
    skipped: int
    skip_groups: dict[str, int]


def read_junit(path: Path) -> TestSummary:
    groups = {"postgres": 0, "redis": 0, "embedding_or_key": 0, "other": 0}
    passed = failed = errors = skipped = 0
    for case in ElementTree.parse(path).getroot().iter("testcase"):
        skip = case.find("skipped")
        if skip is not None:
            skipped += 1
            reason = (skip.get("message", "") + " " + (skip.text or "")).casefold()
            if "embedding" in reason or "api key" in reason or "api_key" in reason:
                group = "embedding_or_key"
            elif "postgres" in reason or "pgvector" in reason:
                group = "postgres"
            elif "redis" in reason:
                group = "redis"
            else:
                group = "other"
            groups[group] += 1
        elif case.find("failure") is not None:
            failed += 1
        elif case.find("error") is not None:
            errors += 1
        else:
            passed += 1
    return TestSummary(passed, failed, errors, skipped, groups)


@dataclass(frozen=True, slots=True)
class Baseline:
    commit: str
    measured_at: str
    database_status: str
    latest_migration: str
    counts: dict[str, int]
    routes: tuple[dict[str, object], ...]
    turns: tuple[dict[str, object], ...]
    cache: dict[str, int]
    providers: dict[str, str]
    blockers: tuple[str, ...]
    redis_status: str = "not measured"
    tests: TestSummary | None = None


def commit_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        return "unavailable"
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    suffix = " (dirty)" if status.returncode == 0 and status.stdout.strip() else ""
    return value + suffix


async def _database_snapshot() -> tuple[
    str,
    str,
    dict[str, int],
    tuple[dict[str, object], ...],
    tuple[dict[str, object], ...],
    dict[str, int],
]:
    try:
        migration_rows = await fetch(
            "SELECT filename FROM schema_migration ORDER BY applied_at DESC, filename DESC LIMIT 1"
        )
        count_rows = await fetch(
            """SELECT
                 (SELECT count(*) FROM kb_document)    AS documents,
                 (SELECT count(*) FROM kb_chunk)       AS chunks,
                 (SELECT count(*) FROM inbound_message) AS messages"""
        )
        facts = await count_for_operations()
        routes = await route_stats()
        turns = await turn_stats()
        cache = await cache_stats()
    except Exception as error:
        # Chi ten exception: str(error) co the chua hostname/DSN tu driver.
        return (
            f"unavailable ({type(error).__name__})",
            "unavailable",
            {},
            (),
            (),
            {},
        )

    row = count_rows[0] if count_rows else {}
    counts = {
        "documents": int(row.get("documents", 0)),
        "chunks": int(row.get("chunks", 0)),
        "facts": facts,
        "messages": int(row.get("messages", 0)),
    }
    route_rows = tuple(
        {
            "route": item.route,
            "model": item.model,
            "calls": item.calls,
            "errors": item.errors,
            "cost_usd": item.cost_usd,
            "avg_latency_ms": item.avg_latency_ms,
            "p95_latency_ms": item.p95_latency_ms,
        }
        for item in routes
    )
    turn_rows: tuple[dict[str, object], ...] = tuple(
        {
            "used_tools": item.used_tools,
            "turns": item.turns,
            "p50_ms": item.p50_ms,
            "p95_ms": item.p95_ms,
            "max_ms": item.max_ms,
        }
        for item in turns
    )
    cache_row = {
        "calls_with_cache": cache.calls_with_cache,
        "total_calls": cache.total_calls,
        "avg_cached_tokens": cache.avg_cached_tokens,
    }
    latest = str(migration_rows[0]["filename"]) if migration_rows else "none"
    return "available", latest, counts, route_rows, turn_rows, cache_row


def _providers() -> dict[str, str]:
    settings = get_settings()
    return {
        "generation": f"openai/{model_cho('reply').id}",
        "embedding": f"{settings.EMBEDDING_PROVIDER}/{settings.EMBEDDING_MODEL}",
        "rerank": f"{settings.RERANK_PROVIDER}/{settings.RERANK_MODEL}",
        "zalo": settings.ZALO_MODE,
        "web_bind": settings.WEB_BIND,
        "web_auth": settings.WEB_AUTH_MODE,
        "metrics_scrape": "configured" if settings.METRICS_SCRAPE_TOKEN else "not configured",
    }


def _blockers(database_status: str, providers: dict[str, str]) -> tuple[str, ...]:
    blockers = [
        "E2 chua backfill owner va kiem thu reverse proxy production; Gate A chua dat.",
        "Golden RAG chua nghiem thu coverage/review nguoi thu hai va hieu chuan E4.",
        "Zalo delivery chua qua soak/restart test (E6).",
        "Danh gia tho chua co hai nguoi cham doc lap (E7).",
    ]
    if database_status != "available":
        blockers.insert(0, "PostgreSQL khong san sang khi do baseline.")
    if providers["rerank"].startswith("fake/"):
        blockers.append("Reranker dang dung provider fake.")
    return tuple(blockers)


async def collect(tests: TestSummary | None = None) -> Baseline:
    database_status, migration, counts, routes, turns, cache = await _database_snapshot()
    providers = _providers()
    try:
        async with asyncio.timeout(3):
            await aw(get_redis().ping())
        redis_status = "available"
    except Exception as error:
        redis_status = f"unavailable ({type(error).__name__})"
    return Baseline(
        commit=commit_sha(),
        measured_at=datetime.now(_TIMEZONE).isoformat(timespec="seconds"),
        database_status=database_status,
        latest_migration=migration,
        counts=counts,
        routes=routes,
        turns=turns,
        cache=cache,
        providers=providers,
        blockers=_blockers(database_status, providers),
        redis_status=redis_status,
        tests=tests,
    )


def render(snapshot: Baseline) -> str:
    lines = [
        "# Trang thai he thong",
        "",
        f"- Commit: `{snapshot.commit}`",
        f"- Ngay do (Asia/Ho_Chi_Minh): `{snapshot.measured_at}`",
        f"- PostgreSQL: `{snapshot.database_status}`",
        f"- Redis: `{snapshot.redis_status}`",
        f"- Migration moi nhat: `{snapshot.latest_migration}`",
        "",
        "## Du lieu",
        "",
    ]
    if snapshot.tests is not None:
        summary = snapshot.tests
        lines[7:7] = [
            f"- Tests (JUnit supplied): {summary.passed} passed, {summary.failed} failed, "
            f"{summary.errors} errors, {summary.skipped} skipped",
            *[f"- Skip {group}: {count}" for group, count in summary.skip_groups.items()],
        ]
    if snapshot.counts:
        lines.extend(f"- {name}: {value}" for name, value in snapshot.counts.items())
    else:
        lines.append("- Khong do duoc vi PostgreSQL khong san sang.")

    lines.extend(["", "## Provider va tinh nang", ""])
    lines.extend(f"- {name}: `{value}`" for name, value in snapshot.providers.items())

    lines.extend(["", "## Chi phi va do tre theo route (7 ngay)", ""])
    if snapshot.routes:
        lines.extend(
            [
                "| Route | Model | Calls | Errors | Cost USD | Avg ms | P95 ms |",
                "|---|---|---:|---:|---:|---:|---:|",
            ]
        )
        for row in snapshot.routes:
            cost_value = row["cost_usd"]
            assert isinstance(cost_value, int | float)
            cost = float(cost_value)
            lines.append(
                f"| {row['route']} | {row['model']} | {row['calls']} | {row['errors']} | "
                f"{cost:.6f} | {row['avg_latency_ms']} | {row['p95_latency_ms']} |"
            )
    else:
        lines.append("Khong co so lieu.")

    lines.extend(["", "## Do tre toan luot (7 ngay)", ""])
    if snapshot.turns:
        lines.extend(
            [
                "| Co tool | Turns | P50 ms | P95 ms | Max ms |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in snapshot.turns:
            lines.append(
                "| {used_tools} | {turns} | {p50_ms} | {p95_ms} | {max_ms} |".format(**row)
            )
    else:
        lines.append("Khong co so lieu.")

    lines.extend(["", "## Prompt cache (7 ngay)", ""])
    if snapshot.cache:
        total = snapshot.cache["total_calls"]
        hit = snapshot.cache["calls_with_cache"]
        rate = hit / total if total else 0.0
        lines.extend(
            [
                f"- Calls co cache: {hit}/{total} ({rate:.1%})",
                f"- Cached tokens trung binh khi hit: {snapshot.cache['avg_cached_tokens']}",
            ]
        )
    else:
        lines.append("- Khong co so lieu.")

    lines.extend(["", "## Blocker go-live", ""])
    lines.extend(f"- {item}" for item in snapshot.blockers)
    return "\n".join(lines) + "\n"


async def _main(junit: Path | None = None) -> int:
    try:
        # Cac helper ha tang co the ghi log SQL ra stdout khi may local de DEBUG.
        # Artifact cua lenh nay phai chi chua Markdown, bat ke LOG_LEVEL hien tai.
        with contextlib.redirect_stdout(io.StringIO()):
            snapshot = await collect(read_junit(junit) if junit else None)
        print(render(snapshot), end="")
        return 0
    finally:
        await close_db()
        await close_redis()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, help="pytest JUnit XML from this measured run")
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(_main(arguments.junit)))
