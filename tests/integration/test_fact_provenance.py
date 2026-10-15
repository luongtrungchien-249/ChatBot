"""Memory provenance/transaction checks on rollback-only session TEMP tables."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from agents.domain.thread import ThreadScope
from infra.db import get_pool
from llm.embedder import EmbeddingIdentity, FakeEmbedder
from memory.repository import fact_repo

IDENTITY = EmbeddingIdentity("fake", "sha256", 1024, "hash-vector-v1")
SCOPE = ThreadScope("web", "synthetic-memory-provenance")
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
async def isolated_facts(
    postgres_san_sang: None, monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[Any]:
    pool = await get_pool()
    async with pool.acquire() as connection:
        outer = connection.transaction()
        await outer.start()
        try:
            for name in (
                "0003_memory.sql", "0011_fact_review.sql", "0024_memory_embedding_provenance.sql",
                "0027_fact_embedding_rebuild_audit.sql",
            ):
                sql = (ROOT / "db" / "migrations" / name).read_text(encoding="utf-8")
                if name.startswith("0003"):
                    sql = sql.replace("CREATE TABLE memory_fact", "CREATE TEMP TABLE memory_fact")
                await connection.execute(sql)

            @asynccontextmanager
            async def transaction() -> AsyncIterator[Any]:
                async with connection.transaction():
                    yield connection

            monkeypatch.setattr(fact_repo, "transaction", transaction)
            monkeypatch.setattr(fact_repo, "fetch", connection.fetch)
            monkeypatch.setattr(fact_repo, "execute", connection.execute)
            monkeypatch.setattr(fact_repo, "embedding_identity", lambda: IDENTITY)
            fake = FakeEmbedder(1024)
            monkeypatch.setattr(fact_repo, "get_embedder", lambda: fake)

            async def embed_query(text: str) -> list[float]:
                return (await fake.embed([text]))[0]

            monkeypatch.setattr(fact_repo, "embed_query", embed_query)
            yield connection
        finally:
            await outer.rollback()


async def test_actual_memory_identity_and_sql_search_are_scoped(isolated_facts: Any) -> None:
    fact = fact_repo.new_fact("user:nam", "Synthetic preference", "test")
    await fact_repo.remember(SCOPE, fact)
    row = await isolated_facts.fetchrow("SELECT * FROM memory_fact")
    assert tuple(row[column] for column in (
        "embedding_provider", "embedding_model", "embedding_dim", "embedding_revision"
    )) == ("fake", "sha256", 1024, "hash-vector-v1")
    assert (await fact_repo.inspect_fact_embedding_provenance(SCOPE)).ready
    assert len(await fact_repo.search_facts(SCOPE, "user:nam", "Synthetic preference")) == 1
    assert await fact_repo.search_facts(ThreadScope("web", "other"), "user:nam", "preference") == []


async def test_unknown_legacy_stays_auditable_and_deletable_without_similarity(
    isolated_facts: Any,
) -> None:
    await fact_repo.remember(SCOPE, fact_repo.new_fact("user:nam", "Legacy preference", "test"))
    await isolated_facts.execute(
        """UPDATE memory_fact SET embedding_provider=NULL,embedding_model=NULL,
                  embedding_dim=NULL,embedding_revision=NULL"""
    )
    assert len(await fact_repo.list_facts(SCOPE, "user:nam")) == 1
    assert len(await fact_repo.dump_thread(SCOPE)) == 1
    for operation in (
        fact_repo.search_facts(SCOPE, "user:nam", "preference"),
        fact_repo.match_for_forget(SCOPE, "user:nam", "preference"),
        fact_repo.remember(SCOPE, fact_repo.new_fact("user:nam", "Other preference", "test")),
    ):
        with pytest.raises(fact_repo.MemoryEmbeddingProvenanceError):
            await operation
    facts = await fact_repo.list_facts(SCOPE, "user:nam")
    assert await fact_repo.revoke(SCOPE, [facts[0].id], "test") == 1


async def test_equal_dimension_other_model_rejects_semantic_search(isolated_facts: Any) -> None:
    await fact_repo.remember(SCOPE, fact_repo.new_fact("user:nam", "Preference", "test"))
    await isolated_facts.execute("UPDATE memory_fact SET embedding_model='other-model'")
    status = await fact_repo.inspect_fact_embedding_provenance(SCOPE)
    assert status.mismatched_facts == 1 and not status.ready
    with pytest.raises(fact_repo.MemoryEmbeddingProvenanceError):
        await fact_repo.search_facts(SCOPE, "user:nam", "Preference")


async def test_real_transaction_restores_revoked_fact_if_replacement_insert_fails(
    isolated_facts: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    await fact_repo.remember(SCOPE, fact_repo.new_fact("user:nam", "Old preference", "test"))
    old = (await fact_repo.list_facts(SCOPE, "user:nam"))[0]

    async def fail_insert(*_: Any) -> None:
        raise RuntimeError("synthetic insert failure")

    monkeypatch.setattr(fact_repo, "_insert_fact", fail_insert)
    with pytest.raises(RuntimeError, match="synthetic insert failure"):
        await fact_repo.replace_fact(
            SCOPE, fact_repo.new_fact("user:nam", "New preference", "test"), old.id
        )
    active = await fact_repo.list_facts(SCOPE, "user:nam")
    assert [fact.id for fact in active] == [old.id]
    revoked_at = await isolated_facts.fetchval(
        "SELECT revoked_at FROM memory_fact WHERE id=$1", int(old.id)
    )
    assert revoked_at is None
