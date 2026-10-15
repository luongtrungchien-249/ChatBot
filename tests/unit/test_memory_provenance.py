from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from agents.domain.errors import UpstreamError
from agents.domain.thread import ThreadScope
from llm.embedder import EmbeddingIdentity
from memory.dedupe import Insert, Skip, decide
from memory.repository import fact_repo

IDENTITY = EmbeddingIdentity("fake", "sha256", 2, "hash-vector-v1")
SCOPE = ThreadScope("web", "synthetic-memory")


def row(**changes: Any) -> dict[str, Any]:
    return {
        "id": 7, "subject_id": "user:nam", "content": "Nam thích cà phê",
        "source": "explicit", "confidence": 1.0, "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "embedding": "[0.99,0.01]", "embedding_provider": "fake", "embedding_model": "sha256",
        "embedding_dim": 2, "embedding_revision": "hash-vector-v1", **changes,
    }


@pytest.mark.parametrize("new,old", [
    ("Nam thích trà", "Nam thích cà phê"),
    ("Nam phụ trách phần backend", "Nam làm backend Node.js"),
    ("Nam làm ở công ty B", "Nam làm ở công ty A"),
])
def test_similar_different_facts_are_preserved_without_contradiction_inference(
    new: str, old: str,
) -> None:
    assert isinstance(decide(new, [1.0, 0.0], [("7", old, [0.99, 0.01])]), Insert)


def test_exact_text_skip_does_not_depend_on_similarity_or_only_the_nearest_candidate() -> None:
    decision = decide("  NAM thích cà phê  ", [1.0, 0.0], [
        ("8", "Nam thích trà", [1.0, 0.0]), ("7", "Nam thích cà phê", [0.0, 1.0]),
    ])
    assert isinstance(decision, Skip) and decision.existing_id == "7"


@pytest.fixture
def memory_setup(monkeypatch: pytest.MonkeyPatch) -> Any:
    fetch = AsyncMock(return_value=[row()])
    embed = AsyncMock(return_value=[[1.0, 0.0]])
    connection = SimpleNamespace(fetch=AsyncMock(return_value=[row()]), execute=AsyncMock())
    transactions: list[str] = []

    @asynccontextmanager
    async def transaction() -> AsyncIterator[Any]:
        transactions.append("begin")
        try:
            yield connection
        except BaseException:
            transactions.append("rollback")
            raise
        else:
            transactions.append("commit")

    monkeypatch.setattr(fact_repo, "fetch", fetch)
    monkeypatch.setattr(fact_repo, "transaction", transaction)
    monkeypatch.setattr(fact_repo, "embedding_identity", lambda: IDENTITY)
    monkeypatch.setattr(fact_repo, "_ready_identity", AsyncMock(return_value=IDENTITY))
    monkeypatch.setattr(fact_repo, "get_embedder", lambda: SimpleNamespace(embed=embed))
    monkeypatch.setattr(fact_repo, "embed_query", AsyncMock(return_value=[1.0, 0.0]))
    return SimpleNamespace(
        fetch=fetch, embed=embed, connection=connection, transactions=transactions
    )


async def test_new_fact_persists_identity_without_revoking_compatible_preference(
    memory_setup: Any,
) -> None:
    await fact_repo.remember(SCOPE, fact_repo.new_fact("user:nam", "Nam thích trà", "nam"))
    calls = memory_setup.connection.execute.await_args_list
    assert len(calls) == 2 and "pg_advisory_xact_lock" in calls[0].args[0]
    sql, *args = calls[1].args
    assert "INSERT INTO memory_fact" in sql
    assert args[:4] == ["web", "synthetic-memory", "user:nam", "Nam thích trà"]
    assert args[8:] == ["fake", "sha256", 2, "hash-vector-v1"]
    assert memory_setup.transactions == ["begin", "commit"]


async def test_exact_fact_duplicate_is_serialized_and_skipped(memory_setup: Any) -> None:
    await fact_repo.remember(SCOPE, fact_repo.new_fact("user:nam", "NAM thích cà phê", "nam"))
    assert memory_setup.connection.execute.await_count == 1
    assert "FOR UPDATE" in memory_setup.connection.fetch.await_args.args[0]


async def test_explicit_replacement_revokes_and_inserts_in_same_scoped_transaction(
    memory_setup: Any,
) -> None:
    await fact_repo.replace_fact(
        SCOPE, fact_repo.new_fact("user:nam", "Nam thích trà", "nam"), "7"
    )
    calls = memory_setup.connection.execute.await_args_list
    assert len(calls) == 3 and "pg_advisory_xact_lock" in calls[0].args[0]
    assert "UPDATE memory_fact" in calls[1].args[0]
    assert calls[1].args[1:] == ("web", "synthetic-memory", "user:nam", 7, "nam")
    assert "INSERT INTO memory_fact" in calls[2].args[0]
    assert memory_setup.transactions == ["begin", "commit"]


async def test_replace_insert_failure_rolls_back_transaction(memory_setup: Any) -> None:
    async def execute(sql: str, *_: Any) -> None:
        if "INSERT INTO memory_fact" in sql:
            raise RuntimeError("synthetic insert failure")

    memory_setup.connection.execute.side_effect = execute
    with pytest.raises(RuntimeError, match="synthetic insert failure"):
        await fact_repo.replace_fact(
            SCOPE, fact_repo.new_fact("user:nam", "Nam thích trà", "nam"), "7"
        )
    assert memory_setup.transactions == ["begin", "rollback"]


async def test_explicit_update_cannot_replace_other_subject_or_inactive_id(
    memory_setup: Any,
) -> None:
    memory_setup.connection.fetch.return_value = []
    with pytest.raises(ValueError, match="scope and subject"):
        await fact_repo.replace_fact(
            SCOPE, fact_repo.new_fact("user:other", "Other preference", "other"), "7"
        )
    assert memory_setup.connection.execute.await_count == 1
    assert memory_setup.transactions == ["begin", "rollback"]


@pytest.mark.parametrize("unknown", [True, False])
async def test_unknown_or_different_model_never_enters_dedupe_or_forget(
    memory_setup: Any, unknown: bool,
) -> None:
    invalid = row(embedding_model=None if unknown else "other-model")
    memory_setup.connection.fetch.return_value = [invalid]
    memory_setup.fetch.return_value = [invalid]
    with pytest.raises(fact_repo.MemoryEmbeddingProvenanceError) as failure:
        await fact_repo.remember(SCOPE, fact_repo.new_fact("user:nam", "Nam thích trà", "nam"))
    assert failure.value.bot_error == UpstreamError(service="embed", status=409)
    assert memory_setup.connection.execute.await_count == 1
    with pytest.raises(fact_repo.MemoryEmbeddingProvenanceError):
        await fact_repo.match_for_forget(SCOPE, "user:nam", "cà phê")


async def test_legacy_raw_list_and_audit_remain_available_without_embedding(
    memory_setup: Any,
) -> None:
    memory_setup.fetch.return_value = [row(embedding_provider=None)]
    assert len(await fact_repo.list_facts(SCOPE, "user:nam")) == 1
    assert len(await fact_repo.dump_thread(SCOPE)) == 1
    assert len(await fact_repo.search_facts(SCOPE, "user:nam", "  ")) == 1
    memory_setup.embed.assert_not_awaited()


async def test_similarity_snapshot_guard_catches_concurrent_incompatible_fact(
    memory_setup: Any,
) -> None:
    memory_setup.fetch.return_value = [{
        "id": None, "total_facts": 1, "unknown_facts": 1, "mismatched_facts": 0,
    }]
    with pytest.raises(fact_repo.MemoryEmbeddingProvenanceError):
        await fact_repo.search_facts(SCOPE, "user:nam", "coffee")


async def test_preflight_inspection_is_scoped_metadata_only(monkeypatch: Any) -> None:
    fetch = AsyncMock(return_value=[{
        "total_facts": 3, "unknown_facts": 1, "mismatched_facts": 1,
    }])
    monkeypatch.setattr(fact_repo, "fetch", fetch)
    status = await fact_repo.inspect_fact_embedding_provenance(
        SCOPE, ["user:nam"], identity=IDENTITY
    )
    assert not status.ready and status.total_facts == 3
    assert fetch.await_args is not None
    sql, *args = fetch.await_args.args
    assert args[:3] == ["web", "synthetic-memory", ["user:nam"]]
    assert "content" not in sql and "UPDATE" not in sql


async def test_unknown_preflight_blocks_before_embedding_or_write(monkeypatch: Any) -> None:
    status = fact_repo.MemoryEmbeddingProvenanceStatus(1, 1, 0, IDENTITY)
    inspect = AsyncMock(return_value=status)
    embed = AsyncMock()
    query = AsyncMock()
    monkeypatch.setattr(fact_repo, "embedding_identity", lambda: IDENTITY)
    monkeypatch.setattr(fact_repo, "inspect_fact_embedding_provenance", inspect)
    monkeypatch.setattr(fact_repo, "get_embedder", lambda: SimpleNamespace(embed=embed))
    monkeypatch.setattr(fact_repo, "embed_query", query)
    with pytest.raises(fact_repo.MemoryEmbeddingProvenanceError):
        await fact_repo.remember(SCOPE, fact_repo.new_fact("user:nam", "preference", "nam"))
    with pytest.raises(fact_repo.MemoryEmbeddingProvenanceError):
        await fact_repo.search_facts(SCOPE, "user:nam", "preference")
    embed.assert_not_awaited()
    query.assert_not_awaited()
