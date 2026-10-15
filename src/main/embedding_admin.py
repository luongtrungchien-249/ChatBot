"""Metadata-only inspection and explicit manifest-based legacy attestation."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints

from knowledge.provenance import (
    DocumentSnapshot,
    attest_document_embeddings,
    inspect_document_embeddings,
    inspect_knowledge_provenance,
)
from llm.embedder import EmbeddingIdentity

Nonblank = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]
PositiveInt = Annotated[StrictInt, Field(gt=0)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IdentityManifest(_Strict):
    provider: Nonblank
    model: Nonblank
    dimensions: PositiveInt
    revision: Nonblank

    def identity(self) -> EmbeddingIdentity:
        return EmbeddingIdentity(**self.model_dump())


class SnapshotManifest(_Strict):
    doc_id: PositiveInt
    version: PositiveInt
    checksum: Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]


class AttestationManifest(_Strict):
    schema_version: Annotated[StrictInt, Field(ge=1, le=1)]
    attested_by: Nonblank
    evidence: Nonblank
    identity: IdentityManifest
    documents: Annotated[list[SnapshotManifest], Field(min_length=1)]


async def embeddings_command(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="cli embeddings")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--doc-id", type=int, action="append")
    attest = commands.add_parser("attest")
    attest.add_argument("--manifest", type=Path, required=True)
    attest.add_argument("--apply", action="store_true")
    options = parser.parse_args(args)
    try:
        if options.command == "inspect":
            status = await inspect_knowledge_provenance()
            documents = await inspect_document_embeddings(options.doc_id)
            print(json.dumps({
                "summary": {**asdict(status), "ready": status.ready},
                "documents": [asdict(document) for document in documents],
            }, ensure_ascii=False, indent=2))
            return 0
        raw = options.manifest.read_bytes()
        manifest = AttestationManifest.model_validate_json(raw)
        identity = manifest.identity.identity()
        snapshots = [DocumentSnapshot(**row.model_dump()) for row in manifest.documents]
        ids = [row.doc_id for row in snapshots]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate document IDs")
        current = await inspect_document_embeddings(ids)
        expected = {row.doc_id: row for row in snapshots}
        if len(current) != len(ids) or any(
            row.identity is not None or row.version != expected[row.doc_id].version
            or row.checksum != expected[row.doc_id].checksum for row in current
        ):
            raise ValueError("manifest is stale, missing or already attested")
        if options.apply:
            await attest_document_embeddings(
                snapshots, identity, attested_by=manifest.attested_by, evidence=manifest.evidence,
            )
        print(json.dumps({
            "action": "applied" if options.apply else "dry_run",
            "manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "documents": len(ids), "identity": asdict(identity),
            "external_evidence_verified": False,
        }, ensure_ascii=False))
        return 0
    except (OSError, ValueError):
        # Validation messages may contain manifest values: keep them private.
        print("Invalid/stale attestation manifest; no implicit identity assignment.")
        return 1
