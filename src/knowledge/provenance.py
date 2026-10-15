"""Read-only readiness and explicit, audited attestation of legacy RAG vectors.

Normal startup must remain available for inspection/recovery. Retrieval itself
fails closed for visible latest documents whose embedding identity is unknown or
different. Attestation changes metadata only and requires external evidence;
new ingestion/re-embedding is the alternative when that evidence does not exist.
"""

import re
from dataclasses import dataclass
from typing import Any

from agents.domain.thread import ThreadScope, scope_key
from infra.db import fetch, transaction
from llm.embedder import EmbeddingIdentity, embedding_identity

IDENTITY_COLUMNS = (
    "embedding_provider", "embedding_model", "embedding_dim", "embedding_revision"
)


@dataclass(frozen=True, slots=True)
class KnowledgeProvenanceStatus:
    total_documents: int
    unknown_documents: int
    mismatched_documents: int
    identity: EmbeddingIdentity

    @property
    def ready(self) -> bool:
        return self.unknown_documents == self.mismatched_documents == 0


class KnowledgeProvenanceError(RuntimeError):
    def __init__(self, status: KnowledgeProvenanceStatus) -> None:
        super().__init__(
            "Kho tai lieu chua san sang: embedding provenance chua xac minh hoac khong khop. "
            "Kiem tra manifest; chi attest khi co bang chung, hoac nap lai ro rang."
        )
        self.status = status


def identity_from_row(row: Any) -> EmbeddingIdentity | None:
    values = [row[column] for column in IDENTITY_COLUMNS]
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise ValueError("Incomplete stored embedding identity")
    return EmbeddingIdentity(str(values[0]), str(values[1]), int(values[2]), str(values[3]))


async def inspect_knowledge_provenance(
    scope: ThreadScope | None = None, *, identity: EmbeddingIdentity | None = None
) -> KnowledgeProvenanceStatus:
    """Aggregate metadata only; no document content, API calls, writes, or assumptions."""
    identity = identity or embedding_identity()
    rows = await fetch(
        """SELECT count(*) AS total_documents,
                  count(*) FILTER (WHERE d.embedding_provider IS NULL) AS unknown_documents,
                  count(*) FILTER (WHERE d.embedding_provider IS NOT NULL AND
                    (d.embedding_provider, d.embedding_model, d.embedding_dim,
                     d.embedding_revision) IS DISTINCT FROM ($2::text,$3::text,$4::int,$5::text))
                    AS mismatched_documents
             FROM kb_document d
            WHERE d.la_ban_moi_nhat AND ($1::text IS NULL OR d.pham_vi IN ('chung', $1))
              AND EXISTS (SELECT 1 FROM kb_chunk c WHERE c.doc_id = d.id)""",
        scope_key(scope) if scope is not None else None,
        identity.provider, identity.model, identity.dimensions, identity.revision,
    )
    return status_from_row(rows[0], identity)


def status_from_row(row: Any, identity: EmbeddingIdentity) -> KnowledgeProvenanceStatus:
    return KnowledgeProvenanceStatus(
        int(row["total_documents"]), int(row["unknown_documents"]),
        int(row["mismatched_documents"]), identity,
    )


@dataclass(frozen=True, slots=True)
class DocumentSnapshot:
    doc_id: int
    version: int
    checksum: str


@dataclass(frozen=True, slots=True)
class DocumentEmbeddingInspection:
    doc_id: int
    version: int
    checksum: str
    identity: EmbeddingIdentity | None
    provenance: str | None
    scope: str
    is_latest: bool


async def inspect_document_embeddings(
    doc_ids: list[int] | None = None,
) -> list[DocumentEmbeddingInspection]:
    """Admin metadata for explicit manifests; all versions unless IDs are specified.

    No text, title, path, automatic identity assignment, API calls, or writes. A
    provided empty ID list selects nothing rather than unexpectedly selecting all.
    """
    if doc_ids is not None:
        if any(type(doc_id) is not int or doc_id < 1 for doc_id in doc_ids):
            raise ValueError("Document IDs must be positive integers")
        if not doc_ids:
            return []
    rows = await fetch(
        """SELECT id, version, checksum, embedding_provider, embedding_model,
                  embedding_dim, embedding_revision, embedding_provenance,
                  pham_vi, la_ban_moi_nhat
             FROM kb_document WHERE ($1::bigint[] IS NULL OR id = ANY($1::bigint[]))
            ORDER BY id""", sorted(set(doc_ids)) if doc_ids is not None else None,
    )
    return [DocumentEmbeddingInspection(
        doc_id=int(row["id"]), version=int(row["version"]), checksum=row["checksum"],
        identity=identity_from_row(row), provenance=row["embedding_provenance"],
        scope=row["pham_vi"], is_latest=bool(row["la_ban_moi_nhat"]),
    ) for row in rows]


async def attest_document_embeddings(
    snapshots: list[DocumentSnapshot], identity: EmbeddingIdentity, *,
    attested_by: str, evidence: str,
) -> list[int]:
    """Apply an operator claim to exactly the unknown snapshots in one transaction.

    Never overwrites a known identity, even a matching one. A stale/missing/duplicate
    document or dimension mismatch aborts the entire operation before any update.
    Old document content, checksums, versions, scopes, and latest flags are untouched.
    """
    if not snapshots or not attested_by.strip() or not evidence.strip():
        raise ValueError("Explicit document snapshots, operator and evidence are required")
    ids = [snapshot.doc_id for snapshot in snapshots]
    if len(set(ids)) != len(ids) or any(
        type(snapshot.doc_id) is not int or snapshot.doc_id < 1
        or type(snapshot.version) is not int or snapshot.version < 1
        or re.fullmatch(r"[0-9a-f]{64}", snapshot.checksum) is None
        for snapshot in snapshots
    ):
        raise ValueError("Invalid or duplicate document snapshots")
    expected = {snapshot.doc_id: snapshot for snapshot in snapshots}
    async with transaction() as connection:
        dimension = await connection.fetchrow(
            """SELECT atttypmod AS dim FROM pg_attribute
                WHERE attrelid = 'kb_chunk'::regclass AND attname = 'embedding'"""
        )
        if dimension is None or dimension["dim"] != identity.dimensions:
            raise ValueError("Declared embedding dimension does not match kb_chunk schema")
        rows = await connection.fetch(
            """SELECT id, version, checksum, embedding_provider, embedding_model,
                      embedding_dim, embedding_revision
                 FROM kb_document WHERE id = ANY($1::bigint[]) ORDER BY id FOR UPDATE""",
            sorted(ids),
        )
        if len(rows) != len(ids):
            raise ValueError("Document snapshot missing")
        for row in rows:
            snapshot = expected[int(row["id"])]
            if row["version"] != snapshot.version or row["checksum"] != snapshot.checksum:
                raise ValueError("Document snapshot changed; inspect again")
            if identity_from_row(row) is not None:
                raise ValueError("Attestation only accepts unknown embedding provenance")
        await connection.execute(
            """UPDATE kb_document SET embedding_provider=$2, embedding_model=$3,
                      embedding_dim=$4, embedding_revision=$5, embedding_provenance='attested',
                      embedding_attested_by=$6, embedding_attestation_evidence=$7,
                      embedding_attested_at=now()
                WHERE id = ANY($1::bigint[])""",
            sorted(ids), identity.provider, identity.model, identity.dimensions,
            identity.revision, attested_by.strip(), evidence.strip(),
        )
    return sorted(ids)
