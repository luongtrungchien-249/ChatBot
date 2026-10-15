import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from infra import redis_client
from llm import embedder


def test_query_cache_separe_provider_model_dimension() -> None:
    config = embedder.EmbeddingConfig("model", 2, 0.0)
    key = embedder._query_cache_key("openai", config, "query")
    assert key.startswith("emb:v2:")
    assert key != embedder._query_cache_key("fake", config, "query")
    assert key != embedder._query_cache_key(
        "openai", embedder.EmbeddingConfig("other", 2, 0), "query"
    )
    assert key != embedder._query_cache_key(
        "openai", embedder.EmbeddingConfig("model", 3, 0), "query"
    )


@pytest.mark.parametrize("cached", [None, "[1]", "[true, false]", "[NaN, 0]", '["a", "b"]'])
async def test_cache_invalide_est_recalcule(monkeypatch: Any, cached: str | None) -> None:
    config = embedder.EmbeddingConfig("model", 2, 0.0)
    redis = AsyncMock()
    redis.get.return_value = cached
    real = SimpleNamespace(embed=AsyncMock(return_value=[[0.25, 0.75]]))
    monkeypatch.setattr(embedder, "embedding_config", lambda: config)
    monkeypatch.setattr(
        embedder, "get_settings", lambda: SimpleNamespace(EMBEDDING_PROVIDER="openai")
    )
    monkeypatch.setattr(embedder, "get_embedder", lambda: real)
    monkeypatch.setattr(redis_client, "get_redis", lambda: redis)
    assert await embedder.embed_query("query") == [0.25, 0.75]
    real.embed.assert_awaited_once_with(["query"])
    redis.get.assert_awaited_once_with(embedder._query_cache_key("openai", config, "query"))


async def test_cache_valide_epargne_api(monkeypatch: Any) -> None:
    config = embedder.EmbeddingConfig("model", 2, 0.0)
    redis = AsyncMock()
    redis.get.return_value = json.dumps([0.25, 0.75])
    real = SimpleNamespace(embed=AsyncMock())
    monkeypatch.setattr(embedder, "embedding_config", lambda: config)
    monkeypatch.setattr(
        embedder, "get_settings", lambda: SimpleNamespace(EMBEDDING_PROVIDER="openai")
    )
    monkeypatch.setattr(embedder, "get_embedder", lambda: real)
    monkeypatch.setattr(redis_client, "get_redis", lambda: redis)
    assert await embedder.embed_query("query") == [0.25, 0.75]
    real.embed.assert_not_awaited()


def test_benchmark_model_override_restores_config_even_after_failure(monkeypatch: Any) -> None:
    settings = SimpleNamespace(
        EMBEDDING_PROVIDER="openai", EMBEDDING_MODEL="text-embedding-3-small", EMBEDDING_DIM=1024
    )
    monkeypatch.setattr(embedder, "get_settings", lambda: settings)
    original = embedder.embedding_config()
    with pytest.raises(RuntimeError), embedder.embedding_model_override("text-embedding-3-large"):
        overridden = embedder.embedding_config()
        assert overridden.model == "text-embedding-3-large"
        assert overridden.dimensions == original.dimensions
        assert embedder._query_cache_key("openai", overridden, "q") != embedder._query_cache_key(
            "openai", original, "q"
        )
        assert original.model == settings.EMBEDDING_MODEL
        raise RuntimeError("synthetic")
    assert embedder.embedding_config() == original


async def test_benchmark_embedding_override_is_task_local(monkeypatch: Any) -> None:
    import asyncio

    monkeypatch.setattr(
        embedder,
        "get_settings",
        lambda: SimpleNamespace(
            EMBEDDING_PROVIDER="openai",
            EMBEDDING_MODEL="text-embedding-3-small",
            EMBEDDING_DIM=1024,
        ),
    )
    async def current(model: str | None) -> str:
        with embedder.embedding_model_override(model):
            await asyncio.sleep(0)
            return embedder.embedding_config().model

    assert list(await asyncio.gather(current("text-embedding-3-large"), current(None))) == [
        "text-embedding-3-large", "text-embedding-3-small"
    ]


def test_unknown_embedding_override_is_rejected(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        embedder, "get_settings", lambda: SimpleNamespace(EMBEDDING_PROVIDER="openai")
    )
    with pytest.raises(ValueError), embedder.embedding_model_override("unknown"):
        pytest.fail("unknown model cannot enter override")


async def test_parallel_cache_misses_share_one_embedding_and_one_cache_read(
    monkeypatch: Any,
) -> None:
    import asyncio

    config = embedder.EmbeddingConfig("model", 2, 0.0)
    redis = AsyncMock()
    redis.get.return_value = None

    async def slow_embed(texts: list[str]) -> list[list[float]]:
        await asyncio.sleep(0)
        return [[0.25, 0.75] for _ in texts]

    real = SimpleNamespace(embed=AsyncMock(side_effect=slow_embed))
    monkeypatch.setattr(embedder, "embedding_config", lambda: config)
    monkeypatch.setattr(
        embedder, "get_settings", lambda: SimpleNamespace(EMBEDDING_PROVIDER="openai")
    )
    monkeypatch.setattr(embedder, "get_embedder", lambda: real)
    monkeypatch.setattr(redis_client, "get_redis", lambda: redis)
    with embedder.shared_query_embeddings():
        results = await asyncio.gather(embedder.embed_query("q"), embedder.embed_query("q"))
    assert list(results) == [[0.25, 0.75], [0.25, 0.75]]
    real.embed.assert_awaited_once_with(["q"])
    redis.get.assert_awaited_once()


async def test_shared_failure_expires_with_operation_and_does_not_poison_next_turn(
    monkeypatch: Any,
) -> None:
    import asyncio

    config = embedder.EmbeddingConfig("model", 2, 0.0)
    redis = AsyncMock()
    redis.get.return_value = None
    real = SimpleNamespace(embed=AsyncMock(side_effect=TimeoutError()))
    monkeypatch.setattr(embedder, "embedding_config", lambda: config)
    monkeypatch.setattr(
        embedder, "get_settings", lambda: SimpleNamespace(EMBEDDING_PROVIDER="openai")
    )
    monkeypatch.setattr(embedder, "get_embedder", lambda: real)
    monkeypatch.setattr(redis_client, "get_redis", lambda: redis)
    with embedder.shared_query_embeddings():
        results = await asyncio.gather(
            embedder.embed_query("q"), embedder.embed_query("q"), return_exceptions=True
        )
    assert all(isinstance(result, TimeoutError) for result in results)
    real.embed.assert_awaited_once()
    real.embed.side_effect = None
    real.embed.return_value = [[0.25, 0.75]]
    with embedder.shared_query_embeddings():
        assert await embedder.embed_query("q") == [0.25, 0.75]
    assert real.embed.await_count == 2
