import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from agents.domain.thread import ThreadScope
from llm.embedder import FakeEmbedder
from memory.repository import embedding_rebuild as rebuild
from memory.repository import fact_repo

from .test_fact_provenance import IDENTITY, SCOPE
from .test_fact_provenance import isolated_facts as isolated_facts


@pytest.fixture
async def rebuilding(isolated_facts: Any, monkeypatch: Any) -> AsyncIterator[Any]:
    @asynccontextmanager
    async def transaction() -> AsyncIterator[Any]:
        async with isolated_facts.transaction():
            yield isolated_facts

    monkeypatch.setattr(rebuild, "fetch", isolated_facts.fetch)
    monkeypatch.setattr(rebuild, "transaction", transaction)
    monkeypatch.setattr(rebuild, "embedding_identity", lambda: IDENTITY)
    yield isolated_facts


async def _seed(connection: Any, subject: str = "user:nam") -> int:
    await fact_repo.remember(SCOPE, fact_repo.new_fact(subject, "Synthetic " + subject, "test"))
    identifier = int(await connection.fetchval(
        "SELECT id FROM memory_fact WHERE subject_id=$1", subject,
    ))
    await connection.execute(
        """UPDATE memory_fact SET embedding_provider=NULL,embedding_model=NULL,
                  embedding_dim=NULL,embedding_revision=NULL WHERE id=$1""", identifier,
    )
    return identifier


async def _selected() -> list[rebuild.FactEmbeddingSelection]:
    return [rebuild.FactEmbeddingSelection(row.fact_id, row.subject_id, row.snapshot_sha256)
            for row in await rebuild.inspect_fact_embeddings(SCOPE)]


async def _apply(selected: list[rebuild.FactEmbeddingSelection]) -> None:
    await rebuild.rebuild_fact_embeddings(
        SCOPE, selected, IDENTITY, actor="test-operator", reason="repair unknown vector",
        manifest_sha256="a" * 64,
    )


async def test_rebuild_preserves_fact_and_enables_semantic_port_without_attestation(
    rebuilding: Any,
) -> None:
    identifier = await _seed(rebuilding)
    before = dict(await rebuilding.fetchrow("SELECT * FROM memory_fact WHERE id=$1", identifier))
    chosen = await _selected()
    with pytest.raises(fact_repo.MemoryEmbeddingProvenanceError):
        await fact_repo.search_facts(SCOPE, "user:nam", "Synthetic user:nam")
    await _apply(chosen)
    after = dict(await rebuilding.fetchrow("SELECT * FROM memory_fact WHERE id=$1", identifier))
    changed = {"embedding", "embedding_provider", "embedding_model", "embedding_dim",
               "embedding_revision", "embedding_rebuild_audit"}
    assert all(after[key] == before[key] for key in before if key not in changed)
    audit = json.loads(after["embedding_rebuild_audit"])
    assert audit["previous_identity"] is None and audit["manifest_sha256"] == "a" * 64
    assert audit["kind"] == "reembedded"
    assert len(await fact_repo.search_facts(SCOPE, "user:nam", "Synthetic user:nam")) == 1
    with pytest.raises(ValueError):
        await _apply(chosen)  # Even identical fake vectors invalidate the approved snapshot.


@pytest.mark.parametrize("operation", ["delete", "revoke"])
async def test_concurrent_delete_or_revoke_during_provider_never_resurrects_fact(
    rebuilding: Any, monkeypatch: Any, operation: str,
) -> None:
    identifier = await _seed(rebuilding)
    selected = await _selected()

    async def embed(texts: list[str]) -> list[list[float]]:
        if operation == "delete":
            await rebuilding.execute("DELETE FROM memory_fact WHERE id=$1", identifier)
        else:
            await fact_repo.revoke(SCOPE, [str(identifier)], "test")
        return await FakeEmbedder(1024).embed(texts)

    monkeypatch.setattr(rebuild, "get_embedder", lambda: SimpleNamespace(embed=embed))
    with pytest.raises(ValueError):
        await _apply(selected)
    assert await rebuilding.fetchval(
        "SELECT count(*) FROM memory_fact WHERE revoked_at IS NULL"
    ) == 0


async def test_wrong_scope_is_rejected_before_provider(rebuilding: Any, monkeypatch: Any) -> None:
    await _seed(rebuilding)
    selected = await _selected()
    provider = AsyncMock()
    monkeypatch.setattr(rebuild, "get_embedder", provider)
    with pytest.raises(ValueError):
        await rebuild.rebuild_fact_embeddings(
            ThreadScope("web", "another-thread"), selected, IDENTITY,
            actor="test", reason="test", manifest_sha256="a" * 64,
        )
    provider.assert_not_called()


async def test_second_row_update_failure_rolls_back_entire_rebuild(rebuilding: Any) -> None:
    await _seed(rebuilding, "user:first")
    second = await _seed(rebuilding, "user:second")
    selected = await _selected()
    await rebuilding.execute(
        f"""CREATE FUNCTION pg_temp.reject_second_rebuild() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
              IF NEW.id={second} AND NEW.embedding_provider IS NOT NULL THEN
                RAISE EXCEPTION 'synthetic rebuild failure';
              END IF;
              RETURN NEW;
            END $$;
            CREATE TRIGGER reject_second BEFORE UPDATE ON memory_fact
            FOR EACH ROW EXECUTE FUNCTION pg_temp.reject_second_rebuild()"""
    )
    with pytest.raises(Exception, match="synthetic rebuild failure"):
        await _apply(selected)
    assert await rebuilding.fetchval(
        """SELECT count(*) FROM memory_fact
            WHERE embedding_provider IS NULL AND embedding_rebuild_audit IS NULL"""
    ) == 2


async def test_all_data_delete_removes_rebuild_audit_with_fact(rebuilding: Any) -> None:
    await _seed(rebuilding)
    await _apply(await _selected())
    assert await fact_repo.hard_delete_scope(rebuilding, SCOPE) == 1
    assert await rebuilding.fetchval("SELECT count(*) FROM memory_fact") == 0
