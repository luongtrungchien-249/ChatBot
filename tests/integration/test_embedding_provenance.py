"""Actual pgvector/constraint tests in temporary tables, never the user's corpus.

The checked-in migrations are applied to session-local shadow tables. The outer
transaction always rolls back, including nested ingest/attestation transactions.
No model API is called; vectors here exercise SQL compatibility, not semantics.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agents.domain.thread import ThreadScope
from infra.db import get_pool
from knowledge import provenance
from knowledge.ingest import pipeline
from knowledge.retrieve import search
from llm.embedder import EmbeddingIdentity, FakeEmbedder

IDENTITY = EmbeddingIdentity("fake", "sha256", 1024, "hash-vector-v1")
SCOPE = ThreadScope("web", "synthetic-scope")
ROOT = Path(__file__).resolve().parents[2]
TEXT = "# Synthetic\n\nLeave policy grants 12 days.\n"


@pytest.fixture
async def isolated_knowledge(
    postgres_san_sang: None, monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[Any]:
    pool = await get_pool()
    async with pool.acquire() as connection:
        outer = connection.transaction()
        await outer.start()
        try:
            for name in (
                "0004_knowledge_1024.sql", "0008_kb_tsv_embed_input.sql",
                "0012_kb_latest_version.sql", "0013_kb_pham_vi.sql",
                "0022_embedding_provenance.sql",
            ):
                sql = (ROOT / "db" / "migrations" / name).read_text(encoding="utf-8")
                if name.startswith("0004"):
                    sql = sql.replace("CREATE TABLE kb_", "CREATE TEMP TABLE kb_")
                await connection.execute(sql)

            @asynccontextmanager
            async def transaction() -> AsyncIterator[Any]:
                async with connection.transaction():
                    yield connection

            for module in (pipeline, provenance):
                monkeypatch.setattr(module, "transaction", transaction)
            for module in (pipeline, provenance, search):
                monkeypatch.setattr(module, "fetch", connection.fetch)
                monkeypatch.setattr(module, "embedding_identity", lambda: IDENTITY)
            fake = FakeEmbedder(1024)
            monkeypatch.setattr(pipeline, "get_embedder", lambda: fake)

            async def embed_query(text: str) -> list[float]:
                return (await fake.embed([text]))[0]

            monkeypatch.setattr(search, "embed_query", embed_query)
            yield SimpleNamespace(connection=connection, transaction=transaction)
        finally:
            await outer.rollback()


async def test_ingest_identity_and_scoped_sql_metadata(
    isolated_knowledge: Any, tmp_path: Path,
) -> None:
    path = tmp_path / "synthetic.md"
    path.write_text(TEXT, encoding="utf-8")
    result = await pipeline.ingest_file(path, "test")
    row = await isolated_knowledge.connection.fetchrow(
        "SELECT * FROM kb_document WHERE id=$1", result.doc_id
    )
    assert provenance.identity_from_row(row) == IDENTITY
    assert row["embedding_provenance"] == "ingested"
    status = await provenance.inspect_knowledge_provenance(SCOPE)
    assert status.ready and status.total_documents == 1
    for branch in (search.vector_search, search.lexical_search):
        rows = await branch(SCOPE, "leave")
        assert rows and rows[0].doc_id == str(result.doc_id)
        assert (rows[0].doc_version, rows[0].doc_scope, rows[0].is_latest) == (1, "chung", True)
    await isolated_knowledge.connection.execute(
        "UPDATE kb_document SET pham_vi='web:private-other' WHERE id=$1", result.doc_id
    )
    assert await search.vector_search(SCOPE, "leave") == []
    assert await search.lexical_search(SCOPE, "leave") == []


async def test_legacy_unknown_is_blocked_until_explicit_snapshot_attestation(
    isolated_knowledge: Any, tmp_path: Path,
) -> None:
    path = tmp_path / "legacy.md"
    path.write_text(TEXT, encoding="utf-8")
    result = await pipeline.ingest_file(path, "test")
    # Simulate an original pre-0022 record. The migration itself never supplies
    # these values from timestamps/config; only this explicit fixture clears them.
    await isolated_knowledge.connection.execute(
        """UPDATE kb_document SET embedding_provider=NULL, embedding_model=NULL,
                  embedding_dim=NULL, embedding_revision=NULL, embedding_provenance=NULL
            WHERE id=$1""", result.doc_id,
    )
    for branch in (search.vector_search, search.lexical_search):
        with pytest.raises(provenance.KnowledgeProvenanceError):
            await branch(SCOPE, "leave")
    row = await isolated_knowledge.connection.fetchrow(
        "SELECT version, checksum FROM kb_document WHERE id=$1", result.doc_id
    )
    snapshot = provenance.DocumentSnapshot(result.doc_id, row["version"], row["checksum"])
    await provenance.attest_document_embeddings(
        [snapshot], IDENTITY, attested_by="test-operator", evidence="synthetic-fixture"
    )
    assert (await provenance.inspect_knowledge_provenance(SCOPE)).ready
    assert await search.vector_search(SCOPE, "leave")
    with pytest.raises(ValueError, match="unknown"):
        await provenance.attest_document_embeddings(
            [snapshot], IDENTITY, attested_by="test-operator", evidence="synthetic-fixture"
        )


async def test_same_dimension_other_model_is_not_compatible(
    isolated_knowledge: Any, tmp_path: Path,
) -> None:
    path = tmp_path / "other-model.md"
    path.write_text(TEXT, encoding="utf-8")
    result = await pipeline.ingest_file(path, "test")
    await isolated_knowledge.connection.execute(
        "UPDATE kb_document SET embedding_model='other-model' WHERE id=$1", result.doc_id
    )
    status = await provenance.inspect_knowledge_provenance(SCOPE)
    assert status.mismatched_documents == 1 and not status.ready
    with pytest.raises(provenance.KnowledgeProvenanceError):
        await search.vector_search(SCOPE, "leave")


async def test_reingest_preserves_scope_and_failed_reingest_restores_old_latest(
    isolated_knowledge: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    path = tmp_path / "private.md"
    path.write_text(TEXT, encoding="utf-8")
    first = await pipeline.ingest_file(path, "test")
    connection = isolated_knowledge.connection
    await connection.execute(
        "UPDATE kb_document SET pham_vi='web:synthetic-scope' WHERE id=$1", first.doc_id
    )
    second = await pipeline.ingest_file(path, "test", ep=True)
    assert second.version == 2
    row = await connection.fetchrow("SELECT * FROM kb_document WHERE id=$1", second.doc_id)
    assert row["pham_vi"] == "web:synthetic-scope" and row["la_ban_moi_nhat"]

    class FailingConnection:
        async def execute(self, sql: str, *args: Any) -> Any:
            if "INSERT INTO kb_chunk" in sql:
                raise RuntimeError("synthetic chunk failure")
            return await connection.execute(sql, *args)

        async def fetch(self, sql: str, *args: Any) -> Any:
            return await connection.fetch(sql, *args)

        async def fetchrow(self, sql: str, *args: Any) -> Any:
            return await connection.fetchrow(sql, *args)

    @asynccontextmanager
    async def failing_transaction() -> AsyncIterator[Any]:
        async with connection.transaction():
            yield FailingConnection()

    monkeypatch.setattr(pipeline, "transaction", failing_transaction)
    with pytest.raises(RuntimeError, match="synthetic chunk failure"):
        await pipeline.ingest_file(path, "test", ep=True)
    rows = await connection.fetch(
        "SELECT id, la_ban_moi_nhat FROM kb_document ORDER BY version"
    )
    assert [(row["id"], row["la_ban_moi_nhat"]) for row in rows] == [
        (first.doc_id, False), (second.doc_id, True)
    ]
