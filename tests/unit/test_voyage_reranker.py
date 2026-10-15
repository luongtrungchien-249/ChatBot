import json
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from llm import reranker
from llm.reranker import (
    CohereReranker,
    RerankBudgetExceededError,
    VoyageReranker,
    build_reranker,
)


@pytest.fixture
def provider(monkeypatch: Any) -> tuple[VoyageReranker, AsyncMock, AsyncMock]:
    response = httpx.Response(
        200,
        json={
            "data": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.2}],
            "usage": {"total_tokens": 1500},
        },
    )
    client = AsyncMock()
    client.post.return_value = response
    meter = AsyncMock()
    monkeypatch.setattr(reranker, "get_http", lambda: client)
    monkeypatch.setattr(reranker, "record_rerank", meter)
    ranker = VoyageReranker(
        model="rerank-3-lite", api_key="synthetic-voyage-key", max_cost_usd=0.10
    )
    return ranker, client, meter


async def test_voyage_request_schema_usage_and_timeout(provider: Any) -> None:
    ranker, client, meter = provider
    hits = await ranker.rerank("Synthetic query", ["Document one", "Document two"], 5)
    assert [hit.index for hit in hits] == [1, 0]
    args = client.post.await_args
    assert args.args == ("https://api.voyageai.com/v1/rerank",)
    assert args.kwargs["timeout"] == 15 and args.kwargs["follow_redirects"] is False
    assert args.kwargs["json"] == {
        "model": "rerank-3-lite",
        "query": "Synthetic query",
        "documents": ["Document one", "Document two"],
        "top_k": 2,
        "return_documents": False,
        "truncation": False,
    }
    assert ranker.calls == ranker.measured_calls == 1 and ranker.total_tokens == 1500
    assert ranker.estimated_cost_usd == pytest.approx(0.00003)
    assert ranker.reserved_cost_usd == pytest.approx(0.00003)
    assert meter.await_args.kwargs["cost_usd"] == pytest.approx(0.00003)
    assert meter.await_args.kwargs["model"] == "voyage/rerank-3-lite"


async def test_empty_inputs_do_not_call_provider(provider: Any) -> None:
    ranker, client, meter = provider
    assert await ranker.rerank("x", [], 5) == []
    client.post.assert_not_awaited()
    meter.assert_not_awaited()


@pytest.mark.parametrize("top_n", [0, -1, True])
async def test_invalid_top_n_is_rejected_before_network(provider: Any, top_n: int) -> None:
    ranker, client, _ = provider
    with pytest.raises(ValueError):
        await ranker.rerank("q", ["d"], top_n)
    client.post.assert_not_awaited()


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [],
        [{"index": True, "relevance_score": 0.9}],
        [{"index": -1, "relevance_score": 0.9}],
        [{"index": 2, "relevance_score": 0.9}],
        [{"index": 0, "relevance_score": float("nan")}],
        [{"index": 0, "relevance_score": "0.9"}],
        [{"index": 0, "relevance_score": True}],
        [{"index": 0, "relevance_score": 1.1}],
        [{"index": 0, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.8}],
        [{"index": 0, "relevance_score": 0.1}, {"index": 1, "relevance_score": 0.9}],
    ],
)
async def test_malformed_rankings_never_become_empty_or_success(provider: Any, raw: Any) -> None:
    ranker, client, meter = provider
    # A malformed paid response may still report valid billable usage.
    response = AsyncMock()
    response.status_code = 200
    from unittest.mock import Mock

    response.json = Mock(return_value={"data": raw, "usage": {"total_tokens": 100}})
    client.post.return_value = response
    with pytest.raises(ValueError):
        await ranker.rerank("q", ["d1", "d2"], 2)
    assert ranker.measured_calls == 1 and ranker.total_tokens == 100
    assert meter.await_args.kwargs["ok"] is False


@pytest.mark.parametrize(
    "usage", [None, {}, {"total_tokens": True}, {"total_tokens": -1}, {"total_tokens": 600001}]
)
async def test_missing_usage_keeps_conservative_budget_reservation(
    provider: Any, usage: Any
) -> None:
    ranker, client, _ = provider
    client.post.return_value = httpx.Response(
        200,
        json={
            "data": [{"index": 0, "relevance_score": 0.9}],
            "usage": usage,
        },
    )
    with pytest.raises(ValueError):
        await ranker.rerank("q", ["d"], 1)
    assert ranker.measured_calls == 0 and ranker.reserved_cost_usd == pytest.approx(0.012)


@pytest.mark.parametrize("status", [301, 401, 429, 503])
async def test_http_error_is_sanitized_and_never_retried(provider: Any, status: int) -> None:
    ranker, client, meter = provider
    client.post.return_value = httpx.Response(status, text="private-key-and-document")
    with pytest.raises(RuntimeError) as error:
        await ranker.rerank("q", ["d"], 1)
    assert "private" not in str(error.value)
    assert str(status) in str(error.value)
    assert isinstance(error.value, reranker.RerankHttpError)
    assert error.value.status_code == status
    assert error.value.provider == "voyage"
    assert client.post.await_count == 1
    meter.assert_not_awaited()


async def test_timeout_reservation_blocks_next_call_before_network(provider: Any) -> None:
    ranker, client, _ = provider
    ranker.max_cost_usd = 0.012
    client.post.side_effect = httpx.ReadTimeout("private-request")
    with pytest.raises(httpx.ReadTimeout):
        await ranker.rerank("q", ["d"], 1)
    with pytest.raises(RerankBudgetExceededError):
        await ranker.rerank("q", ["d"], 1)
    assert client.post.await_count == 1 and ranker.calls == 1


async def test_accounting_failure_does_not_change_rankings(provider: Any) -> None:
    ranker, _, meter = provider
    meter.side_effect = TimeoutError("private-dsn")
    assert len(await ranker.rerank("q", ["d1", "d2"], 2)) == 2


@pytest.mark.parametrize(
    "key,model,budget",
    [
        ("dev", "rerank-3-lite", 0.1),
        ("fake", "rerank-3-lite", 0.1),
        ("synthetic", "unknown", 0.1),
        ("synthetic", "rerank-3-lite", float("nan")),
    ],
)
def test_unsafe_config_is_rejected(key: str, model: str, budget: float) -> None:
    with pytest.raises(ValueError):
        VoyageReranker(api_key=key, model=model, max_cost_usd=budget)


def test_factory_and_lazy_runtime_select_voyage(monkeypatch: Any) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(reranker, "_reranker", None)
    monkeypatch.setattr(
        reranker,
        "get_settings",
        lambda: SimpleNamespace(
            RERANK_PROVIDER="voyage",
            RERANK_MODEL="rerank-3-lite",
            RERANK_API_KEY="synthetic",
        ),
    )
    assert isinstance(reranker.get_reranker(), VoyageReranker)
    assert reranker.get_reranker() is reranker.get_reranker()
    with pytest.raises(ValueError):
        build_reranker("typo", model="model", api_key="synthetic")


async def test_cohere_error_does_not_leak_provider_body(provider: Any) -> None:
    _, client, _ = provider
    client.post.return_value = httpx.Response(401, text=json.dumps({"key": "private-key"}))
    with pytest.raises(RuntimeError) as error:
        await CohereReranker(model="synthetic", api_key="synthetic").rerank("q", ["d"], 1)
    assert "private" not in str(error.value)
    assert client.post.await_args.kwargs["follow_redirects"] is False
