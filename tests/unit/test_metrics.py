from typing import Any
from unittest.mock import AsyncMock

import pytest

from infra import metrics
from infra.queue_metrics import QueueAge


@pytest.mark.parametrize("timestamp", [None, "NaN", "Infinity", "-1", "broken"])
async def test_unknown_heartbeat_has_observed_zero_without_fake_age(
    timestamp: str | None, monkeypatch: Any,
) -> None:
    monkeypatch.setattr(metrics, "route_stats", AsyncMock(return_value=[]))
    monkeypatch.setattr(metrics, "cache_stats", AsyncMock(return_value=metrics.CacheStats(0, 0, 0)))
    monkeypatch.setattr(metrics, "turn_stats", AsyncMock(return_value=[]))
    monkeypatch.setattr(metrics, "budget_today", AsyncMock(return_value=(0.0, 1.0)))
    monkeypatch.setattr(metrics, "fetch", AsyncMock(return_value=[]))
    redis = AsyncMock()
    redis.get.return_value = timestamp
    redis.zcard.return_value = 0
    monkeypatch.setattr(metrics, "get_redis", lambda: redis)
    rendered = await metrics.prometheus_text(1, 1)
    assert 'cp_heartbeat_observed{component="zalo"} 0' in rendered
    assert 'cp_heartbeat_age_seconds{component="zalo"}' not in rendered


@pytest.fixture(autouse=True)
def mock_queue_age(monkeypatch: Any) -> None:
    monkeypatch.setattr(metrics, "queue_age", AsyncMock(return_value=QueueAge(0.0, True)))


async def test_prometheus_khong_trung_series_khi_route_doi_model(monkeypatch: Any) -> None:
    routes = [
        metrics.RouteStats("reply", model, 10, 1, 100, 50, 0, 0.001, 10, 20)
        for model in ("model-a", "model-b")
    ]
    monkeypatch.setattr(metrics, "route_stats", AsyncMock(return_value=routes))
    monkeypatch.setattr(
        metrics, "cache_stats", AsyncMock(return_value=metrics.CacheStats(0, 20, 0))
    )
    monkeypatch.setattr(metrics, "turn_stats", AsyncMock(return_value=[]))
    monkeypatch.setattr(metrics, "budget_today", AsyncMock(return_value=(0.02, 1.0)))
    monkeypatch.setattr(metrics, "fetch", AsyncMock(return_value=[]))
    redis = AsyncMock()
    redis.get.return_value = None
    redis.zcard.return_value = 0
    monkeypatch.setattr(metrics, "get_redis", lambda: redis)

    rendered = await metrics.prometheus_text(7, 1.0)
    samples = [line.rsplit(" ", 1)[0] for line in rendered.splitlines() if not line.startswith("#")]
    assert len(samples) == len(set(samples))
    assert 'cp_llm_errors_total{route="reply",model="model-a"} 1' in rendered
    assert 'cp_llm_errors_total{route="reply",model="model-b"} 1' in rendered


async def test_rag_metrics_labels_bornes_et_pas_de_fausse_latence(monkeypatch: Any) -> None:
    query = AsyncMock(
        return_value=[
            {
                "outcome": "found",
                "n": 2,
                "retrieval_degraded": 1,
                "rerank_degraded": 1,
                "degraded": 1,
                "low_confidence": 1,
                "latency": 120,
            },
            {
                "outcome": "uncertain",
                "n": 1,
                "retrieval_degraded": 0,
                "rerank_degraded": 0,
                "degraded": 0,
                "low_confidence": 1,
                "latency": 250,
            },
        ]
    )
    monkeypatch.setattr(metrics, "fetch", query)
    rendered = "\n".join(await metrics._rag_prometheus())
    assert 'cp_rag_requests{outcome="found"} 2' in rendered
    assert 'cp_rag_requests{outcome="empty"} 0' in rendered
    assert 'cp_rag_requests{outcome="unknown"} 0' in rendered
    assert 'cp_rag_degraded_requests{stage="any"} 1' in rendered
    assert "cp_rag_low_confidence_requests 2" in rendered
    assert 'cp_rag_latency_p95_ms{outcome="found"} 120' in rendered
    assert 'cp_rag_latency_p95_ms{outcome="empty"}' not in rendered
    assert query.await_args is not None
    assert "outcome NOT IN ('cancelled','unknown')" in query.await_args.args[0]
    assert "query=" not in rendered and "trace_id=" not in rendered


def test_prometheus_escape_model_label() -> None:
    stats = metrics.RouteStats("reply", 'a"b\\c\nd', 0, 0, 0, 0, 0, 0.0, 0, 0)
    assert metrics._route_labels(stats) == 'route="reply",model="a\\"b\\\\c\\nd"'


async def test_turn_stats_utilise_wall_clock_et_non_somme_tool(monkeypatch: Any) -> None:
    query = AsyncMock(return_value=[])
    monkeypatch.setattr(metrics, "fetch", query)
    assert await metrics.turn_stats() == []
    assert query.await_args is not None
    sql = query.await_args.args[0]
    assert "FROM turn_telemetry" in sql
    assert "sum(latency_ms)" not in sql


async def test_runtime_details_ne_confond_pas_retries_et_fallback(monkeypatch: Any) -> None:
    monkeypatch.setattr(metrics, "route_stats", AsyncMock(return_value=[]))
    monkeypatch.setattr(metrics, "cache_stats", AsyncMock(return_value=metrics.CacheStats(0, 0, 0)))
    monkeypatch.setattr(metrics, "turn_stats", AsyncMock(return_value=[]))
    monkeypatch.setattr(metrics, "budget_today", AsyncMock(return_value=(0.0, 1.0)))
    query = AsyncMock(
        side_effect=[
            [],
            [
                {
                    "reason": "error",
                    "n": 5,
                    "measured_replies": 2,
                    "fallbacks": 2,
                    "react_turns": 5,
                    "iterations": 7,
                    "tool_calls": 3,
                    "tool_errors": 1,
                    "recorded_cost_usd": 0.01,
                    "poetry_calls": 7,
                    "poetry_turns": 2,
                },
                {
                    "reason": "answer",
                    "n": 10,
                    "measured_replies": 10,
                    "fallbacks": 0,
                    "react_turns": 10,
                    "iterations": 20,
                    "tool_calls": 10,
                    "tool_errors": 0,
                    "recorded_cost_usd": 0.02,
                },
            ],
            [],
            [],
        ]
    )
    monkeypatch.setattr(metrics, "fetch", query)
    redis = AsyncMock()
    redis.get.return_value = None
    redis.zcard.return_value = 0
    monkeypatch.setattr(metrics, "get_redis", lambda: redis)
    rendered = await metrics.prometheus_text(7, 1.0)
    assert 'cp_runtime_turns{outcome="error"} 0' in rendered
    assert 'cp_runtime_turns{outcome="completed"} 0' in rendered
    assert 'cp_runtime_turn_reason{reason="error"} 5' in rendered
    assert "cp_runtime_fallbacks 2" in rendered
    assert "cp_runtime_measured_replies 12" in rendered
    assert "cp_runtime_react_iterations 27" in rendered
    assert "cp_runtime_tool_calls 13" in rendered
    assert "cp_runtime_tool_errors 1" in rendered
    assert "cp_runtime_poetry_calls 7" in rendered
    assert "cp_runtime_poetry_turns 2" in rendered
    assert "cp_runtime_recorded_cost_usd 0.03" in rendered
    sql = query.await_args_list[1].args[0]
    assert "WHERE replied AND fallback IS NOT NULL" in sql
    assert "WHERE replied AND fallback" in sql
    assert "sender_id" not in sql and "thread_id" not in sql
    samples = [line.rsplit(" ", 1)[0] for line in rendered.splitlines() if not line.startswith("#")]
    assert len(samples) == len(set(samples))
