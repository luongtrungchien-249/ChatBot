from typing import Any
from unittest.mock import AsyncMock

from llm import cost_meter


async def test_rerank_cost_tracks_reported_tokens_without_content(monkeypatch: Any) -> None:
    execute, add_cost = AsyncMock(), AsyncMock()
    monkeypatch.setattr(cost_meter, "execute", execute)
    monkeypatch.setattr(cost_meter, "add_cost", add_cost)
    await cost_meter.record_rerank(
        model="voyage/rerank-3-lite", tokens=1500, cost_usd=0.00003, latency_ms=100
    )
    assert execute.await_args is not None
    call = execute.await_args.args
    assert "'rerank'" in call[0] and "'system'" in call[0]
    assert call[1:] == ("voyage/rerank-3-lite", 1500, 0.00003, 100, True)
    add_cost.assert_awaited_once_with(0.00003)


async def test_rerank_cost_failure_is_sanitized_and_best_effort(
    monkeypatch: Any, capsys: Any
) -> None:
    monkeypatch.setattr(
        cost_meter, "execute", AsyncMock(side_effect=ConnectionError("private-dsn"))
    )
    await cost_meter.record_rerank(model="synthetic", tokens=100, cost_usd=0.000002, latency_ms=10)
    assert "private-dsn" not in capsys.readouterr().out
