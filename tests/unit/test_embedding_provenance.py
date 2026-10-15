from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from agents.domain.thread import ThreadScope
from knowledge import provenance
from knowledge.retrieve import search, service
from knowledge.retrieve.search import ChunkRow
from llm import embedder
from llm.embedder import EmbeddingIdentity

IDENTITY = EmbeddingIdentity("openai", "text-embedding-3-large", 1024, "openai-embedding-v1")
SCOPE = ThreadScope("web", "synthetic-provenance")
CHECKSUM = "a" * 64


def document(doc_id: int = 1, **changes: Any) -> dict[str, Any]:
    return {
        "id": doc_id, "version": 2, "checksum": CHECKSUM,
        "embedding_provider": None, "embedding_model": None,
        "embedding_dim": None, "embedding_revision": None, **changes,
    }


def test_configuration_identity_separates_model_dimension_and_fake_algorithm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        EMBEDDING_PROVIDER="openai", EMBEDDING_MODEL="text-embedding-3-large", EMBEDDING_DIM=1024
    )
    monkeypatch.setattr(embedder, "get_settings", lambda: settings)
    assert embedder.embedding_identity() == IDENTITY
    settings.EMBEDDING_MODEL = "text-embedding-3-small"
    assert embedder.embedding_identity() != IDENTITY
    settings.EMBEDDING_PROVIDER = "fake"
    fake = embedder.embedding_identity()
    assert fake == EmbeddingIdentity("fake", "sha256", 1024, "hash-vector-v1")
    settings.EMBEDDING_MODEL = "unused-fake-model-name"
    assert embedder.embedding_identity() == fake
    settings.EMBEDDING_PROVIDER = "typo"
    with pytest.raises(ValueError, match="Unsupported"):
        embedder.embedding_identity()


@pytest.mark.parametrize(
    "identity", [("openai", "", 1, "v1"), ("openai", "model", True, "v1"),
                 ("other", "model", 1, "v1"), ("fake", "model", 1, "")],
)
def test_invalid_identity_is_rejected(identity: Any) -> None:
    with pytest.raises(ValueError):
        EmbeddingIdentity(*identity)


async def test_read_only_inspection_reports_unknown_and_same_dimension_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch = AsyncMock(return_value=[{
        "total_documents": 4, "unknown_documents": 1, "mismatched_documents": 2,
    }])
    monkeypatch.setattr(provenance, "fetch", fetch)
    status = await provenance.inspect_knowledge_provenance(SCOPE, identity=IDENTITY)
    assert not status.ready and status.total_documents == 4
    assert fetch.await_args is not None
    sql, *args = fetch.await_args.args
    assert args == ["web:synthetic-provenance", *search._identity_args(IDENTITY)]
    assert "d.la_ban_moi_nhat" in sql and "d.pham_vi IN ('chung', $1)" in sql
    assert "version" not in sql.lower() and "ingested_at" not in sql


def test_partial_identity_never_becomes_known() -> None:
    assert provenance.identity_from_row(document()) is None
    with pytest.raises(ValueError, match="Incomplete"):
        provenance.identity_from_row(document(embedding_provider="openai"))


async def test_document_inspection_is_metadata_only_and_does_not_invent_identity(
    monkeypatch: Any,
) -> None:
    fetch = AsyncMock(return_value=[document(
        embedding_provenance=None, pham_vi="web:private", la_ban_moi_nhat=False,
    )])
    monkeypatch.setattr(provenance, "fetch", fetch)
    assert await provenance.inspect_document_embeddings([]) == []
    fetch.assert_not_awaited()
    rows = await provenance.inspect_document_embeddings([1, 1])
    assert rows[0].identity is None and rows[0].checksum == CHECKSUM
    assert rows[0].scope == "web:private" and not rows[0].is_latest
    assert fetch.await_args is not None
    assert fetch.await_args.args[1] == [1]
    sql = fetch.await_args.args[0]
    assert "content" not in sql and "title" not in sql and "source_path" not in sql


@pytest.fixture
def attestation_connection(monkeypatch: pytest.MonkeyPatch) -> Any:
    connection = SimpleNamespace(
        fetchrow=AsyncMock(return_value={"dim": 1024}),
        fetch=AsyncMock(return_value=[document(1), document(2)]), execute=AsyncMock(),
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

    connection.transactions = transactions
    monkeypatch.setattr(provenance, "transaction", transaction)
    return connection


def snapshots() -> list[provenance.DocumentSnapshot]:
    return [
        provenance.DocumentSnapshot(2, 2, CHECKSUM), provenance.DocumentSnapshot(1, 2, CHECKSUM)
    ]


async def test_explicit_attestation_locks_exact_snapshots_and_records_audited_claim(
    attestation_connection: Any,
) -> None:
    result = await provenance.attest_document_embeddings(
        snapshots(), IDENTITY, attested_by="operator", evidence="manifest-sha256:synthetic"
    )
    assert result == [1, 2]
    assert "FOR UPDATE" in attestation_connection.fetch.await_args.args[0]
    assert attestation_connection.fetch.await_args.args[1] == [1, 2]
    sql, *args = attestation_connection.execute.await_args.args
    assert args == [[1, 2], *search._identity_args(IDENTITY), "operator",
                    "manifest-sha256:synthetic"]
    assert "embedding_provenance='attested'" in sql and "embedding_attested_at=now()" in sql
    assert "pham_vi=" not in sql and "checksum=" not in sql and "embedding=" not in sql
    assert attestation_connection.transactions == ["begin", "commit"]


@pytest.mark.parametrize("invalid", ["stale", "missing", "known", "dimension", "partial"])
async def test_attestation_any_invalid_snapshot_aborts_before_update(
    attestation_connection: Any, invalid: str,
) -> None:
    if invalid == "stale":
        attestation_connection.fetch.return_value = [document(1), document(2, version=3)]
    elif invalid == "missing":
        attestation_connection.fetch.return_value = [document(1)]
    elif invalid == "dimension":
        attestation_connection.fetchrow.return_value = {"dim": 512}
    elif invalid == "partial":
        attestation_connection.fetch.return_value = [
            document(1), document(2, embedding_provider="openai")
        ]
    else:
        attestation_connection.fetch.return_value = [document(1), document(
            2, embedding_provider=IDENTITY.provider, embedding_model=IDENTITY.model,
            embedding_dim=IDENTITY.dimensions, embedding_revision=IDENTITY.revision,
        )]
    with pytest.raises(ValueError):
        await provenance.attest_document_embeddings(
            snapshots(), IDENTITY, attested_by="operator", evidence="synthetic"
        )
    attestation_connection.execute.assert_not_awaited()
    assert attestation_connection.transactions == ["begin", "rollback"]


@pytest.mark.parametrize("invalid", ["empty", "duplicate", "operator", "evidence", "checksum"])
async def test_attestation_requires_explicit_valid_manifest(
    attestation_connection: Any, invalid: str,
) -> None:
    manifest = snapshots()
    if invalid == "empty":
        manifest = []
    elif invalid == "duplicate":
        manifest = [manifest[0], manifest[0]]
    elif invalid == "checksum":
        manifest = [provenance.DocumentSnapshot(1, 2, "unknown")]
    with pytest.raises(ValueError):
        await provenance.attest_document_embeddings(
            manifest, IDENTITY, attested_by="" if invalid == "operator" else "operator",
            evidence="" if invalid == "evidence" else "synthetic",
        )
    assert not attestation_connection.transactions


async def test_not_ready_blocks_before_embedding_or_search_sql(monkeypatch: Any) -> None:
    inspect = AsyncMock(return_value=provenance.KnowledgeProvenanceStatus(2, 1, 0, IDENTITY))
    embed, fetch = AsyncMock(), AsyncMock()
    monkeypatch.setattr(search, "embedding_identity", lambda: IDENTITY)
    monkeypatch.setattr(search, "inspect_knowledge_provenance", inspect)
    monkeypatch.setattr(search, "embed_query", embed)
    monkeypatch.setattr(search, "fetch", fetch)
    for branch in (search.vector_search, search.lexical_search):
        with pytest.raises(provenance.KnowledgeProvenanceError):
            await branch(SCOPE, "synthetic")
    embed.assert_not_awaited()
    fetch.assert_not_awaited()


def test_candidate_snapshot_detects_new_unknown_or_mismatched_document_even_without_hits() -> None:
    for unknown, mismatch in [(1, 0), (0, 1)]:
        with pytest.raises(provenance.KnowledgeProvenanceError):
            search._checked_rows([{
                "id": None, "total_documents": 1,
                "unknown_documents": unknown, "mismatched_documents": mismatch,
            }], IDENTITY)


async def test_provenance_error_cannot_be_hidden_by_surviving_branch(monkeypatch: Any) -> None:
    status = provenance.KnowledgeProvenanceStatus(1, 0, 1, IDENTITY)
    monkeypatch.setattr(service, "vector_search", AsyncMock(return_value=[
        ChunkRow(1, "synthetic", None, None, "synthetic", 0.2)
    ]))
    monkeypatch.setattr(service, "lexical_search", AsyncMock(
        side_effect=provenance.KnowledgeProvenanceError(status)
    ))
    with pytest.raises(service.RetrievalUnavailableError) as result:
        await service.HybridKnowledge().search(SCOPE, "synthetic", 5)
    assert isinstance(result.value.__cause__, provenance.KnowledgeProvenanceError)


async def test_lexical_survives_embedding_outage_and_preserves_structured_metadata(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(search, "embedding_identity", lambda: IDENTITY)
    monkeypatch.setattr(search, "_ready_identity", AsyncMock(return_value=IDENTITY))
    monkeypatch.setattr(search, "embed_query", AsyncMock(side_effect=TimeoutError()))
    fetch = AsyncMock(return_value=[{
        "id": 7, "section": "Policy", "page": 2, "content": "AB-001",
        "title": "Synthetic", "distance": None, "doc_id": 9,
        "doc_version": 3, "doc_scope": "web:synthetic-provenance", "is_latest": True,
        "total_documents": 1, "unknown_documents": 0, "mismatched_documents": 0,
    }])
    monkeypatch.setattr(search, "fetch", fetch)
    rows = await search.lexical_search(SCOPE, "AB-001")
    assert rows[0].distance is None and rows[0].doc_id == "9"
    chunk = service._to_chunk(rows[0], 0.5)
    assert (chunk.doc_id, chunk.doc_version, chunk.doc_scope, chunk.is_latest) == (
        "9", 3, "web:synthetic-provenance", True
    )
    assert fetch.await_args is not None and fetch.await_args.args[4] is None
