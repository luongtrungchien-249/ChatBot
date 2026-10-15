import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from knowledge.provenance import DocumentEmbeddingInspection
from main import embedding_admin, web_owners


def _attestation() -> dict[str, Any]:
    return {
        "schema_version": 1, "attested_by": "operator", "evidence": "external provenance log",
        "identity": {"provider": "openai", "model": "model", "dimensions": 1024, "revision": "v1"},
        "documents": [{"doc_id": 1, "version": 1, "checksum": "a" * 64}],
    }


@pytest.mark.parametrize("field,value", [("attested_by", " "), ("evidence", ""), ("unknown", 1)])
def test_manifest_rejects_empty_evidence_and_extra_fields(field: str, value: Any) -> None:
    data = _attestation()
    data[field] = value
    with pytest.raises(ValidationError):
        embedding_admin.AttestationManifest.model_validate(data)


@pytest.mark.parametrize("apply", [False, True])
async def test_attestation_requires_explicit_apply(
    apply: bool, tmp_path: Path, monkeypatch: Any,
) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_attestation()), encoding="utf-8")
    monkeypatch.setattr(embedding_admin, "inspect_document_embeddings", AsyncMock(return_value=[
        DocumentEmbeddingInspection(1, 1, "a" * 64, None, None, "chung", True),
    ]))
    write = AsyncMock()
    monkeypatch.setattr(embedding_admin, "attest_document_embeddings", write)
    assert await embedding_admin.embeddings_command([
        "attest", "--manifest", str(path), *(["--apply"] if apply else []),
    ]) == 0
    assert write.await_count == int(apply)


async def test_stale_attestation_never_calls_write(tmp_path: Path, monkeypatch: Any) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_attestation()), encoding="utf-8")
    monkeypatch.setattr(embedding_admin, "inspect_document_embeddings", AsyncMock(return_value=[
        DocumentEmbeddingInspection(1, 2, "b" * 64, None, None, "chung", True),
    ]))
    write = AsyncMock()
    monkeypatch.setattr(embedding_admin, "attest_document_embeddings", write)
    assert await embedding_admin.embeddings_command([
        "attest", "--manifest", str(path), "--apply",
    ]) == 1
    write.assert_not_awaited()


@pytest.mark.parametrize("owned,sha", [(True, "a" * 64), (False, "b" * 64)])
def test_owner_manifest_rejects_owned_or_changed_thread(owned: bool, sha: str) -> None:
    manifest = web_owners.OwnerManifest.model_validate({
        "schema_version": 1, "assigned_by": "operator", "evidence": "ownership record",
        "assignments": [{"thread_id": "legacy", "user_id": "alice", "snapshot_sha256": "a" * 64}],
    })
    with pytest.raises(ValueError):
        web_owners._validate_snapshot(manifest, [{
            "thread_id": "legacy", "owner_present": owned, "snapshot_sha256": sha,
        }])
