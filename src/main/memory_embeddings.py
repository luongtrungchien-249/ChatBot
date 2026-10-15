"""Local operator CLI: metadata snapshots, dry-run, then explicit vector-only rebuild."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from pydantic import Field, StrictInt, StringConstraints

from agents.domain.thread import Platform, ThreadScope
from llm.embedder import embedding_identity
from memory.repository.embedding_rebuild import (
    DEFAULT_MAX_INPUT_BYTES,
    FactEmbeddingSelection,
    inspect_fact_embeddings,
    plan_fact_embedding_rebuild,
    rebuild_fact_embeddings,
)

from .embedding_admin import IdentityManifest, Nonblank, PositiveInt, _Strict

_PLATFORMS = ("web", "cli", "zalo_bot", "zalo_personal")


class ScopeManifest(_Strict):
    platform: Platform
    thread_id: Nonblank


class FactSelectionManifest(_Strict):
    fact_id: PositiveInt
    subject_id: Nonblank
    snapshot_sha256: Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]


class FactRebuildManifest(_Strict):
    schema_version: Annotated[StrictInt, Field(ge=1, le=1)]
    actor: Nonblank
    reason: Nonblank
    scope: ScopeManifest
    target_identity: IdentityManifest
    facts: Annotated[list[FactSelectionManifest], Field(min_length=1, max_length=100)]


async def memory_embeddings_command(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="cli memory-embeddings")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("platform", choices=_PLATFORMS)
    inspect.add_argument("thread_id")
    rebuild = commands.add_parser("rebuild")
    rebuild.add_argument("--manifest", type=Path, required=True)
    rebuild.add_argument("--max-input-bytes", type=int, default=DEFAULT_MAX_INPUT_BYTES)
    rebuild.add_argument("--max-estimated-usd", type=float)
    rebuild.add_argument("--apply", action="store_true")
    options = parser.parse_args(args)
    try:
        if options.command == "inspect":
            declared_scope = ScopeManifest(platform=options.platform, thread_id=options.thread_id)
            rows = await inspect_fact_embeddings(
                ThreadScope(declared_scope.platform, declared_scope.thread_id)
            )
            print(json.dumps({
                "scope": declared_scope.model_dump(),
                "target_identity": asdict(embedding_identity()),
                "facts": [asdict(row) for row in rows], "content_included": False,
                "api_called": False,
            }, ensure_ascii=False, indent=2))
            return 0
        raw = options.manifest.read_bytes()
        manifest = FactRebuildManifest.model_validate_json(raw)
        scope = ThreadScope(manifest.scope.platform, manifest.scope.thread_id)
        selections = [FactEmbeddingSelection(**row.model_dump()) for row in manifest.facts]
        target = manifest.target_identity.identity()
        digest = hashlib.sha256(raw).hexdigest()
        if options.apply:
            plan = await rebuild_fact_embeddings(
                scope, selections, target, actor=manifest.actor, reason=manifest.reason,
                manifest_sha256=digest, max_input_bytes=options.max_input_bytes,
                max_estimated_usd=options.max_estimated_usd,
            )
        else:
            plan = await plan_fact_embedding_rebuild(
                scope, selections, target, max_input_bytes=options.max_input_bytes,
                max_estimated_usd=options.max_estimated_usd,
            )
        print(json.dumps({
            "action": "applied" if options.apply else "dry_run", "manifest_sha256": digest,
            "facts": len(plan.facts), "input_bytes": plan.input_bytes,
            "estimated_cost_upper_usd": plan.estimated_cost_upper_usd,
            "price_source": "local_estimate_not_billing_guarantee",
            "target_identity": asdict(target), "content_included": False,
            "whole_scope_ready_not_inferred": True,
        }, ensure_ascii=False))
        return 0
    except Exception as error:
        # Provider/DB exceptions can contain content or credentials. No raw values.
        print(json.dumps({
            "status": "failed", "error_type": type(error).__name__,
            "detail": "Check scope/snapshot/target/migration/budget privately; no retry inferred.",
        }))
        return 1
