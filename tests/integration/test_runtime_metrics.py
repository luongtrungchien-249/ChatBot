import time
import uuid

import pytest

from agents.domain.telemetry import GenerationStats, TurnDetails, UpstreamFailure
from infra.db import execute, fetch
from infra.metrics import prometheus_text
from infra.redis_client import aw, get_redis
from infra.runtime_metrics import heartbeat, record_turn


async def test_poetry_calls_are_measured_separately_from_react(postgres_san_sang: None) -> None:
    trace = uuid.uuid4().hex
    try:
        await record_turn(
            trace, "web", "completed", 150, 0,
            details=TurnDetails("poetry", False, poetry_calls=4), replied=True,
        )
        row = (await fetch("SELECT * FROM turn_telemetry WHERE trace_id=$1", trace))[0]
        assert row["poetry_calls"] == 4 and row["react_iterations"] is None
        await record_turn(trace, "web", "completed", 100, 0)
        row = (await fetch("SELECT * FROM turn_telemetry WHERE trace_id=$1", trace))[0]
        assert row["poetry_calls"] is None
    finally:
        await execute("DELETE FROM turn_telemetry WHERE trace_id=$1", trace)


async def test_retry_ghi_de_mot_turn_va_do_wall_clock(postgres_san_sang: None) -> None:
    trace = uuid.uuid4().hex
    try:
        await record_turn(trace, "web", "error", 150, 300)
        await record_turn(trace, "web", "completed", 100, 500)
        rows = await fetch("SELECT * FROM turn_telemetry WHERE trace_id=$1", trace)
        assert len(rows) == 1
        assert rows[0]["outcome"] == "completed"
        assert rows[0]["latency_ms"] == 100
        assert rows[0]["queue_wait_ms"] == 500
    finally:
        await execute("DELETE FROM turn_telemetry WHERE trace_id=$1", trace)


async def test_upstream_failure_retry_clears_old_cause(postgres_san_sang: None) -> None:
    trace = uuid.uuid4().hex
    try:
        await record_turn(
            trace,
            "web",
            "error",
            100,
            0,
            details=TurnDetails("error", False, failure=UpstreamFailure("llm", "auth")),
        )
        row = (
            await fetch(
                "SELECT failure_service,failure_kind FROM turn_telemetry WHERE trace_id=$1", trace
            )
        )[0]
        assert (row["failure_service"], row["failure_kind"]) == ("llm", "auth")
        await record_turn(trace, "web", "completed", 100, 0, details=TurnDetails("answer", False))
        row = (
            await fetch(
                "SELECT failure_service,failure_kind FROM turn_telemetry WHERE trace_id=$1", trace
            )
        )[0]
        assert row["failure_service"] is None and row["failure_kind"] is None
    finally:
        await execute("DELETE FROM turn_telemetry WHERE trace_id=$1", trace)


async def test_details_retry_remplace_fallback_et_ne_fabrique_pas_historique(
    postgres_san_sang: None,
) -> None:
    trace = uuid.uuid4().hex
    try:
        await record_turn(
            trace,
            "web",
            "error",
            150,
            300,
            details=TurnDetails("error", True, GenerationStats("error", 2, 3, 1)),
            replied=True,
        )
        row = (await fetch("SELECT * FROM turn_telemetry WHERE trace_id=$1", trace))[0]
        assert row["reason"] == "error" and row["fallback"] and row["replied"]
        assert (row["react_iterations"], row["tool_calls"], row["tool_errors"]) == (2, 3, 1)
        await record_turn(
            trace,
            "web",
            "completed",
            100,
            500,
            details=TurnDetails("answer", False, GenerationStats("answer", 1)),
            replied=True,
        )
        row = (await fetch("SELECT * FROM turn_telemetry WHERE trace_id=$1", trace))[0]
        assert row["reason"] == "answer" and row["fallback"] is False
        assert (row["react_iterations"], row["tool_calls"], row["tool_errors"]) == (1, 0, 0)
        await record_turn(trace, "web", "error", 200, 700)
        row = (await fetch("SELECT * FROM turn_telemetry WHERE trace_id=$1", trace))[0]
        assert row["reason"] == "unknown"
        assert all(
            row[name] is None
            for name in ("fallback", "replied", "react_iterations", "tool_calls", "tool_errors")
        )
    finally:
        await execute("DELETE FROM turn_telemetry WHERE trace_id=$1", trace)


async def test_heartbeat_duoc_chia_se_qua_redis(redis_san_sang: None) -> None:
    redis = get_redis()
    previous = await aw(redis.get("heartbeat:worker"))
    try:
        await heartbeat("worker")
        stored = await aw(redis.get("heartbeat:worker"))
        assert stored is not None
        assert abs(time.time() - float(stored)) < 5
    finally:
        if previous is None:
            await aw(redis.delete("heartbeat:worker"))
        else:
            await aw(redis.set("heartbeat:worker", previous))


async def test_cout_trace_cumulatif_retry_sans_compter_autre_turn(
    postgres_san_sang: None,
) -> None:
    trace = uuid.uuid4().hex
    other = uuid.uuid4().hex

    async def usage(identifier: str, cost: str) -> None:
        await execute(
            """INSERT INTO usage_log(trace_id,platform,thread_id,sender_id,route,model,cost_usd,ok)
               VALUES($1,'web','synthetic','synthetic','reply','synthetic',$2::text::numeric,TRUE)""",
            identifier,
            cost,
        )

    try:
        await record_turn(trace, "web", "error", 1, 1)
        row = (
            await fetch("SELECT recorded_cost_usd FROM turn_telemetry WHERE trace_id=$1", trace)
        )[0]
        assert row["recorded_cost_usd"] is None
        await usage(trace, "0.01")
        await usage(other, "0.99")
        await record_turn(trace, "web", "error", 1, 1)
        row = (
            await fetch("SELECT recorded_cost_usd FROM turn_telemetry WHERE trace_id=$1", trace)
        )[0]
        assert float(row["recorded_cost_usd"]) == pytest.approx(0.01)
        await usage(trace, "0.02")
        await record_turn(trace, "web", "completed", 1, 1)
        rows = await fetch("SELECT recorded_cost_usd FROM turn_telemetry WHERE trace_id=$1", trace)
        assert len(rows) == 1 and float(rows[0]["recorded_cost_usd"]) == pytest.approx(0.03)
    finally:
        await execute("DELETE FROM turn_telemetry WHERE trace_id=$1", trace)
        await execute("DELETE FROM usage_log WHERE trace_id=ANY($1::text[])", [trace, other])


async def test_metrics_reelles_mesurent_fallback_sans_exposer_trace(
    postgres_san_sang: None,
    redis_san_sang: None,
) -> None:
    trace = uuid.uuid4().hex
    try:
        await record_turn(
            trace,
            "web",
            "error",
            100,
            200,
            details=TurnDetails("error", True, GenerationStats("error", 2, 1, 1)),
            replied=True,
        )
        rendered = await prometheus_text(7, 1.0)
        samples = {
            name: float(value)
            for name, value in (
                line.rsplit(" ", 1) for line in rendered.splitlines() if not line.startswith("#")
            )
        }
        assert samples["cp_runtime_fallbacks"] >= 1
        assert samples["cp_runtime_measured_replies"] >= samples["cp_runtime_fallbacks"]
        assert samples["cp_runtime_tool_calls"] >= 1
        assert samples["cp_runtime_tool_errors"] >= 1
        assert trace not in rendered
        assert "sender_id=" not in rendered and "thread_id=" not in rendered
    finally:
        await execute("DELETE FROM turn_telemetry WHERE trace_id=$1", trace)
