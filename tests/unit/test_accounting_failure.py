from typing import Any
from unittest.mock import AsyncMock

import pytest

from agents.domain.thread import ThreadScope
from agents.ports.llm import LlmUsage
from llm import cost_meter


@pytest.mark.parametrize("route", ["llm", "embed", "rerank"])
async def test_db_outage_cannot_skip_budget_accounting(route: str, monkeypatch: Any) -> None:
    monkeypatch.setattr(cost_meter, "execute", AsyncMock(side_effect=RuntimeError("private DSN")))
    budget = AsyncMock()
    monkeypatch.setattr(cost_meter, "add_cost", budget)
    if route == "embed":
        await cost_meter.record_embedding(model="model", tokens=10, cost_usd=0.01, latency_ms=1)
    elif route == "rerank":
        await cost_meter.record_rerank(model="model", tokens=10, cost_usd=0.01, latency_ms=1)
    else:
        await cost_meter.record(cost_meter.UsageRecord(
            "reply", LlmUsage(100, 10, 0, 0), ThreadScope("web", "test"), "u", "trace", 1, True,
        ))
    assert budget.await_count == 1 and budget.await_args is not None
    assert budget.await_args.args[0] > 0
