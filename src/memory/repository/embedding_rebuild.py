"""Explicit scoped recovery of unknown/mismatched fact vectors, never attestation.

Inspect outputs metadata only; content is read locally to calculate its snapshot.
Apply sends exactly the selected content to the configured embedding provider.
Network work happens before locks, then exact snapshots are rechecked atomically.
"""

import asyncio
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from agents.domain.thread import ThreadScope
from infra.db import fetch, transaction
from infra.ratelimit import rate_limit
from infra.thread_lifecycle import lock_web_thread
from llm.embedder import EmbeddingIdentity, embedding_identity, get_embedder
from llm.models import EMBEDDING_PRICES

from .fact_repo import _identity_args, _lock_subject, _to_vector, _validate_vector

MAX_FACTS = 100
DEFAULT_MAX_INPUT_BYTES = 8_000
_HASH = re.compile(r"[0-9a-f]{64}")
_SELECT = """SELECT id,subject_id,content,embedding,source,confidence,created_by,created_at,
                   embedding_provider,embedding_model,embedding_dim,embedding_revision,
                   embedding_rebuild_audit
              FROM memory_fact
             WHERE platform=$1 AND thread_id=$2 AND revoked_at IS NULL
               AND ($3::bigint[] IS NULL OR id=ANY($3::bigint[])) ORDER BY id"""


@dataclass(frozen=True, slots=True)
class FactEmbeddingSnapshot:
    fact_id: int
    subject_id: str
    source: str
    input_bytes: int
    identity: dict[str, str | int] | None
    snapshot_sha256: str


@dataclass(frozen=True, slots=True)
class FactEmbeddingSelection:
    fact_id: int
    subject_id: str
    snapshot_sha256: str


@dataclass(frozen=True, slots=True)
class FactRebuildPlan:
    target_identity: EmbeddingIdentity
    facts: tuple[FactEmbeddingSnapshot, ...]
    input_bytes: int
    estimated_cost_upper_usd: float


def _snapshot(row: Any) -> FactEmbeddingSnapshot:
    names = ("embedding_provider", "embedding_model", "embedding_dim", "embedding_revision")
    identity: dict[str, str | int] | None = None
    if any(row[name] is not None for name in names):
        if any(row[name] is None for name in names):
            raise ValueError("Incomplete stored embedding identity")
        identity = {
            "provider": str(row[names[0]]), "model": str(row[names[1]]),
            "dimensions": int(row[names[2]]), "revision": str(row[names[3]]),
        }
    content = str(row["content"]).encode("utf-8")
    audit = row.get("embedding_rebuild_audit")
    if isinstance(audit, str):
        audit = json.loads(audit)
    frozen = {
        "id": int(row["id"]), "subject_id": row["subject_id"],
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "vector_sha256": hashlib.sha256(str(row["embedding"]).encode()).hexdigest(),
        "identity": identity, "source": row["source"], "confidence": float(row["confidence"]),
        "created_by": row["created_by"], "created_at": row["created_at"].isoformat(),
        "last_rebuild_audit": audit,
    }
    digest = hashlib.sha256(json.dumps(
        frozen, sort_keys=True, ensure_ascii=True, allow_nan=False,
    ).encode()).hexdigest()
    return FactEmbeddingSnapshot(
        int(row["id"]), row["subject_id"], row["source"], len(content), identity, digest,
    )


async def inspect_fact_embeddings(scope: ThreadScope) -> list[FactEmbeddingSnapshot]:
    return [_snapshot(row) for row in await fetch(_SELECT, scope.platform, scope.thread_id, None)]


def _check_selection(selections: list[FactEmbeddingSelection]) -> list[int]:
    if not 1 <= len(selections) <= MAX_FACTS:
        raise ValueError("Choose between 1 and 100 exact fact snapshots")
    if any(
        type(item.fact_id) is not int or item.fact_id < 1 or not item.subject_id.strip()
        or _HASH.fullmatch(item.snapshot_sha256) is None for item in selections
    ):
        raise ValueError("Invalid fact snapshot")
    ids = [item.fact_id for item in selections]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate fact IDs")
    return ids


def _check_rows(rows: list[Any], selections: list[FactEmbeddingSelection]) -> None:
    expected = {item.fact_id: item for item in selections}
    if len(rows) != len(expected):
        raise ValueError("Fact missing, revoked or outside this scope")
    for row in rows:
        current = _snapshot(row)
        approved = expected.get(current.fact_id)
        if approved is None or (current.subject_id, current.snapshot_sha256) != (
            approved.subject_id, approved.snapshot_sha256,
        ):
            raise ValueError("Fact snapshot is stale or belongs to another subject")


async def _prepare(
    scope: ThreadScope, selections: list[FactEmbeddingSelection], target: EmbeddingIdentity,
    max_input_bytes: int, max_estimated_usd: float | None,
) -> tuple[FactRebuildPlan, list[Any]]:
    ids = _check_selection(selections)
    if embedding_identity() != target:
        raise ValueError("Manifest target differs from the configured embedding implementation")
    if type(max_input_bytes) is not int or max_input_bytes < 1:
        raise ValueError("Input byte bound must be positive")
    if max_estimated_usd is not None and (
        not math.isfinite(max_estimated_usd) or max_estimated_usd < 0
    ):
        raise ValueError("Estimated cost bound must be finite and nonnegative")
    rows = list(await fetch(_SELECT, scope.platform, scope.thread_id, ids))
    _check_rows(rows, selections)
    dimension = await fetch(
        """SELECT atttypmod AS dimension,
                  EXISTS(SELECT 1 FROM pg_attribute WHERE attrelid='memory_fact'::regclass
                           AND attname='embedding_rebuild_audit'
                           AND NOT attisdropped) AS audit_ready
             FROM pg_attribute WHERE attrelid='memory_fact'::regclass
               AND attname='embedding' AND NOT attisdropped"""
    )
    if not dimension or int(dimension[0]["dimension"]) != target.dimensions:
        raise ValueError("Configured dimensions do not match the fact vector column")
    if not dimension[0]["audit_ready"]:
        raise ValueError("Apply migration 0027 before planning a fact rebuild")
    snapshots = tuple(_snapshot(row) for row in rows)
    size = sum(row.input_bytes for row in snapshots)
    if size > max_input_bytes:
        raise ValueError("Selected content exceeds the input byte bound")
    # Conservative token bound from UTF-8 bytes; the repository's price catalog
    # is an estimate, not a billing/quota guarantee or concurrency reservation.
    price = 0.0 if target.provider == "fake" else EMBEDDING_PRICES.get(target.model)
    if price is None:
        raise ValueError("No local price estimate for the configured embedding model")
    estimate = size * price / 1_000_000
    if max_estimated_usd is not None and estimate > max_estimated_usd:
        raise ValueError("Selected content exceeds the estimated cost bound")
    return FactRebuildPlan(target, snapshots, size, estimate), rows


async def plan_fact_embedding_rebuild(
    scope: ThreadScope, selections: list[FactEmbeddingSelection], target: EmbeddingIdentity, *,
    max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES, max_estimated_usd: float | None = None,
) -> FactRebuildPlan:
    plan, _ = await _prepare(scope, selections, target, max_input_bytes, max_estimated_usd)
    return plan


async def rebuild_fact_embeddings(
    scope: ThreadScope, selections: list[FactEmbeddingSelection], target: EmbeddingIdentity, *,
    actor: str, reason: str, manifest_sha256: str,
    max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES, max_estimated_usd: float | None = None,
) -> FactRebuildPlan:
    if not actor.strip() or not reason.strip() or _HASH.fullmatch(manifest_sha256) is None:
        raise ValueError("Explicit operator, reason and manifest hash are required")
    if target.provider != "fake" and max_estimated_usd is None:
        raise ValueError("Paid rebuilding requires an explicit estimated cost ceiling")
    plan, rows = await _prepare(scope, selections, target, max_input_bytes, max_estimated_usd)
    if target.provider != "fake" and not await rate_limit.within_daily_budget():
        raise ValueError("Daily budget unavailable or exhausted; no provider call made")
    async with asyncio.timeout(30):
        vectors = await get_embedder().embed([str(row["content"]) for row in rows])
    if len(vectors) != len(rows) or embedding_identity() != target:
        raise ValueError("Embedding count or configuration changed")
    for vector in vectors:
        _validate_vector(vector, target)
        if not any(vector):
            raise ValueError("Embedding provider returned a zero vector")
    ids = [item.fact_id for item in selections]
    async with transaction() as connection:
        await lock_web_thread(connection, scope)
        for subject in sorted({item.subject_id for item in selections}):
            await _lock_subject(connection, scope, subject)
        current = list(await connection.fetch(
            _SELECT + " FOR UPDATE", scope.platform, scope.thread_id, ids,
        ))
        _check_rows(current, selections)
        for row, snapshot, vector in zip(rows, plan.facts, vectors, strict=True):
            audit = json.dumps({
                "kind": "reembedded", "at": datetime.now(UTC).isoformat(),
                "actor": actor, "reason": reason, "manifest_sha256": manifest_sha256,
                "previous_snapshot_sha256": snapshot.snapshot_sha256,
                "previous_identity": snapshot.identity, "target_identity": asdict(target),
            }, ensure_ascii=True)
            status = await connection.execute(
                """UPDATE memory_fact SET embedding=$5::vector,
                          embedding_provider=$6,embedding_model=$7,embedding_dim=$8,
                          embedding_revision=$9,embedding_rebuild_audit=$10::jsonb
                    WHERE platform=$1 AND thread_id=$2 AND subject_id=$3 AND id=$4
                      AND revoked_at IS NULL""",
                scope.platform, scope.thread_id, snapshot.subject_id, int(row["id"]),
                _to_vector(vector), *_identity_args(target), audit,
            )
            if status != "UPDATE 1":
                raise RuntimeError("Fact rebuild did not update exactly one selected row")
    return plan
