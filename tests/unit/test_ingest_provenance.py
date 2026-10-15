import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from knowledge.ingest import pipeline
from knowledge.ingest.chunk import chunk_document
from llm.embedder import EmbeddingIdentity

IDENTITY = EmbeddingIdentity("fake", "sha256", 2, "hash-vector-v1")
TEXT = "# Policy\n\nA synthetic allowance is 12 days.\n\n## Travel\n\nSynthetic limit is 42.\n"


def existing(**changes: Any) -> dict[str, Any]:
    return {
        "id": 5, "version": 2, "max_version": changes.get("version", 2),
        "checksum": hashlib.sha256(TEXT.encode()).hexdigest(),
        "title": "Synthetic", "pham_vi": "web:private-test",
        "embedding_provider": IDENTITY.provider, "embedding_model": IDENTITY.model,
        "embedding_dim": IDENTITY.dimensions, "embedding_revision": IDENTITY.revision,
        **changes,
    }


@pytest.fixture
def ingest_setup(monkeypatch: Any, tmp_path: Path) -> Any:
    path = tmp_path / "synthetic.md"
    path.write_text(TEXT, encoding="utf-8")
    vectors = [[1.0, 0.0] for _ in chunk_document(TEXT)]
    embed = AsyncMock(return_value=vectors)
    fetch = AsyncMock(return_value=[])
    connection = SimpleNamespace(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value={"id": 9}),
        execute=AsyncMock(),
    )
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

    monkeypatch.setattr(pipeline, "embedding_identity", lambda: IDENTITY)
    monkeypatch.setattr(pipeline, "get_embedder", lambda: SimpleNamespace(embed=embed))
    monkeypatch.setattr(pipeline, "fetch", fetch)
    monkeypatch.setattr(pipeline, "transaction", transaction)
    return SimpleNamespace(
        path=path, embed=embed, fetch=fetch, connection=connection, transactions=transactions
    )


async def test_new_ingestion_persists_actual_identity_with_immutable_content(
    ingest_setup: Any,
) -> None:
    result = await pipeline.ingest_file(ingest_setup.path, "operator", title="Synthetic")
    assert result.version == 1 and not result.skipped
    sql, *args = ingest_setup.connection.fetchrow.await_args.args
    assert "embedding_provenance" in sql and "'ingested'" in sql
    assert args[2] == 1 and args[5:] == ["chung", "fake", "sha256", 2, "hash-vector-v1"]
    assert "pg_advisory_xact_lock" in ingest_setup.connection.execute.await_args_list[0].args[0]
    assert ingest_setup.transactions == ["begin", "commit"]


async def test_known_unchanged_document_skips_without_embedding(ingest_setup: Any) -> None:
    ingest_setup.fetch.return_value = [existing()]
    result = await pipeline.ingest_file(ingest_setup.path, "operator")
    assert result.skipped and result.doc_id == 5 and result.version == 2
    ingest_setup.embed.assert_not_awaited()
    assert not ingest_setup.transactions


@pytest.mark.parametrize("unknown", [True, False])
async def test_unchanged_unknown_or_other_model_requires_explicit_reingest(
    ingest_setup: Any, unknown: bool,
) -> None:
    changes = (
        {column: None for column in (
            "embedding_provider", "embedding_model", "embedding_dim", "embedding_revision"
        )} if unknown else {"embedding_model": "different-model-same-dimension"}
    )
    ingest_setup.fetch.return_value = [existing(**changes)]
    with pytest.raises(ValueError, match="--nap-lai"):
        await pipeline.ingest_file(ingest_setup.path, "operator")
    ingest_setup.embed.assert_not_awaited()
    assert not ingest_setup.transactions


async def test_explicit_reingest_preserves_private_scope_and_creates_new_version(
    ingest_setup: Any,
) -> None:
    old = existing(embedding_model="old-model")
    ingest_setup.fetch.return_value = ingest_setup.connection.fetch.return_value = [old]
    result = await pipeline.ingest_file(ingest_setup.path, "operator", ep=True)
    assert result.version == 3 and not result.skipped
    args = ingest_setup.connection.fetchrow.await_args.args
    assert args[6] == "web:private-test"
    assert args[7:] == ("fake", "sha256", 2, "hash-vector-v1")
    old_update = ingest_setup.connection.execute.await_args_list[1].args[0]
    assert "la_ban_moi_nhat = false" in old_update
    assert "embedding" not in old_update and "checksum" not in old_update


async def test_version_is_rechecked_after_serializing_concurrent_ingesters(
    ingest_setup: Any,
) -> None:
    ingest_setup.fetch.return_value = [existing(version=2, checksum="b" * 64)]
    ingest_setup.connection.fetch.return_value = [existing(version=4, checksum="c" * 64)]
    result = await pipeline.ingest_file(ingest_setup.path, "operator")
    assert result.version == 5


async def test_concurrent_identical_ingestion_skips_after_lock(ingest_setup: Any) -> None:
    ingest_setup.connection.fetch.return_value = [existing(version=3)]
    result = await pipeline.ingest_file(ingest_setup.path, "operator")
    assert result.skipped and result.version == 3
    ingest_setup.connection.fetchrow.assert_not_awaited()
    assert ingest_setup.connection.execute.await_count == 1


async def test_reingest_after_version_rollback_uses_next_unused_version_and_active_scope(
    ingest_setup: Any,
) -> None:
    ingest_setup.connection.fetch.return_value = [existing(version=1, max_version=4)]
    result = await pipeline.ingest_file(ingest_setup.path, "operator", ep=True)
    assert result.version == 5
    assert ingest_setup.connection.fetchrow.await_args.args[6] == "web:private-test"


@pytest.mark.parametrize("vectors", [[], [[1.0]], [[float("nan"), 0.0]], [[True, 0.0]]])
async def test_malformed_embedding_is_rejected_before_latest_flag_changes(
    ingest_setup: Any, vectors: Any,
) -> None:
    ingest_setup.embed.return_value = vectors * len(chunk_document(TEXT)) if vectors else []
    with pytest.raises(ValueError, match="response"):
        await pipeline.ingest_file(ingest_setup.path, "operator")
    assert not ingest_setup.transactions
    ingest_setup.connection.execute.assert_not_awaited()


async def test_chunk_insert_failure_exits_document_transaction_with_rollback(
    ingest_setup: Any,
) -> None:
    async def execute(sql: str, *_: Any) -> None:
        if "INSERT INTO kb_chunk" in sql:
            raise RuntimeError("synthetic insert failure")

    ingest_setup.connection.execute.side_effect = execute
    with pytest.raises(RuntimeError, match="synthetic insert failure"):
        await pipeline.ingest_file(ingest_setup.path, "operator")
    assert ingest_setup.transactions == ["begin", "rollback"]
