"""Durable wall-clock turn measurements and shared process heartbeats."""

import asyncio
import time
from typing import Literal

from agents.domain.telemetry import RagObservation, TurnDetails

from .db import execute
from .logger import get_logger
from .redis_client import aw, get_redis


async def record_turn(
    trace_id: str,
    platform: str,
    outcome: Literal["completed", "error"],
    latency_ms: int,
    queue_wait_ms: int,
    *,
    details: TurnDetails | None = None,
    replied: bool | None = None,
) -> None:
    details = details or TurnDetails()
    generation = details.generation
    try:
        await execute(
            """INSERT INTO turn_telemetry
               (trace_id,platform,outcome,latency_ms,queue_wait_ms,reason,replied,
                fallback,react_iterations,tool_calls,tool_errors,recorded_cost_usd,
                failure_service,failure_kind,poetry_calls)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,
                 (SELECT sum(cost_usd) FROM usage_log WHERE trace_id=$1),$12,$13,$14)
               ON CONFLICT(trace_id) DO UPDATE SET
               outcome=EXCLUDED.outcome,latency_ms=EXCLUDED.latency_ms,
               queue_wait_ms=EXCLUDED.queue_wait_ms,reason=EXCLUDED.reason,
               replied=EXCLUDED.replied,fallback=EXCLUDED.fallback,
               react_iterations=EXCLUDED.react_iterations,tool_calls=EXCLUDED.tool_calls,
               tool_errors=EXCLUDED.tool_errors,
               recorded_cost_usd=EXCLUDED.recorded_cost_usd,
               failure_service=EXCLUDED.failure_service,failure_kind=EXCLUDED.failure_kind,
               poetry_calls=EXCLUDED.poetry_calls,
               created_at=now()""",
            trace_id,
            platform,
            outcome,
            latency_ms,
            queue_wait_ms,
            details.reason,
            replied,
            details.fallback,
            generation.iterations if generation else None,
            generation.tool_calls if generation else None,
            generation.tool_errors if generation else None,
            details.failure.service if details.failure else None,
            details.failure.kind if details.failure else None,
            details.poetry_calls,
        )
    except Exception as error:
        get_logger().warning("turn telemetry failed", error=type(error).__name__)


async def heartbeat(component: Literal["worker", "maintenance", "zalo"]) -> None:
    await aw(get_redis().set(f"heartbeat:{component}", str(time.time())))


async def record_rag(
    trace_id: str, platform: str, observation: RagObservation, latency_ms: int
) -> None:
    """Bounded, best-effort sink. Failures must not change tool/response behavior."""
    try:
        async with asyncio.timeout(2):
            await execute(
                """INSERT INTO rag_telemetry
                   (trace_id,platform,outcome,retrieval_degraded,rerank_degraded,
                    low_confidence,latency_ms) VALUES($1,$2,$3,$4,$5,$6,$7)""",
                trace_id,
                platform,
                observation.outcome,
                observation.retrieval_degraded,
                observation.rerank_degraded,
                observation.low_confidence,
                latency_ms,
            )
    except Exception as error:
        get_logger().warning("RAG telemetry failed", error=type(error).__name__)
