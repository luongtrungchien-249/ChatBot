import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from infra.db import execute, fetch
from llm import cost_meter


@pytest.mark.parametrize("ok", [True, False])
async def test_rerank_usage_records_valid_or_malformed_paid_result(
    postgres_san_sang: None,
    monkeypatch: Any,
    ok: bool,
) -> None:
    model = f"synthetic-rerank-{uuid.uuid4().hex}"
    budget = AsyncMock()
    monkeypatch.setattr(cost_meter, "add_cost", budget)
    try:
        await cost_meter.record_rerank(
            model=model, tokens=1500, cost_usd=0.00003, latency_ms=100, ok=ok
        )
        rows = await fetch(
            "SELECT route,input_tokens,cost_usd,ok FROM usage_log WHERE model=$1", model
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["route"] == "rerank" and row["input_tokens"] == 1500
        assert float(row["cost_usd"]) == pytest.approx(0.00003) and row["ok"] is ok
        budget.assert_awaited_once_with(0.00003)
    finally:
        # Exact synthetic model only; do not touch real usage or daily Redis cost.
        await execute("DELETE FROM usage_log WHERE model=$1 AND route='rerank'", model)
