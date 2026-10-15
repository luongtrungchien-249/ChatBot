"""Inspect legacy Web metadata and assign owners from an operator's frozen manifest."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, StrictInt, StringConstraints

from agents.domain.thread import ThreadScope
from infra.db import fetch, transaction
from infra.thread_lifecycle import ThreadBusyError, lock_web_thread

from .embedding_admin import Nonblank, _Strict

_SNAPSHOT_SQL = """SELECT m.thread_id, m.message_id, m.created_at,
                          a.user_id, coalesce(g.generation, 0) AS generation
                     FROM inbound_message m
                     LEFT JOIN web_thread_access a ON a.thread_id=m.thread_id
                     LEFT JOIN web_thread_generation g ON g.thread_id=m.thread_id
                    WHERE m.platform='web' AND ($1::text[] IS NULL OR m.thread_id=ANY($1))
                    ORDER BY m.thread_id, m.message_id"""


def _snapshots(rows: list[Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Any]] = {}
    for row in rows:
        grouped.setdefault(row["thread_id"], []).append(row)
    result: list[dict[str, Any]] = []
    for thread_id, messages in grouped.items():
        payload = [
            [row["message_id"], row["created_at"].isoformat(), row["generation"]]
            for row in messages
        ]
        result.append({
            "thread_id": thread_id, "message_count": len(messages),
            "owner_present": messages[0]["user_id"] is not None,
            "snapshot_sha256": hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
            ).hexdigest(),
        })
    return result


class OwnerAssignment(_Strict):
    thread_id: Annotated[str, StringConstraints(
        strict=True, min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$",
    )]
    user_id: Nonblank
    snapshot_sha256: Annotated[str, StringConstraints(
        strict=True, pattern=r"^[0-9a-f]{64}$",
    )]


class OwnerManifest(_Strict):
    schema_version: Annotated[StrictInt, Field(ge=1, le=1)]
    assigned_by: Nonblank
    evidence: Nonblank
    assignments: Annotated[list[OwnerAssignment], Field(min_length=1)]


def _validate_snapshot(manifest: OwnerManifest, current: list[dict[str, Any]]) -> None:
    expected = {row.thread_id: row for row in manifest.assignments}
    if len(expected) != len(manifest.assignments) or len(current) != len(expected):
        raise ValueError("duplicate/missing thread")
    if any(
        row["owner_present"]
        or row["snapshot_sha256"] != expected[row["thread_id"]].snapshot_sha256
        for row in current
    ):
        raise ValueError("already owned or stale snapshot")


async def assign_legacy_owners(manifest: OwnerManifest, digest: str) -> None:
    ids = sorted(row.thread_id for row in manifest.assignments)
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate thread")
    async with transaction() as connection:
        for thread_id in ids:
            # Same owner lock as normal claim, plus the lifecycle lock used by writers/deletion.
            await connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", f"web:{thread_id}"
            )
            await lock_web_thread(connection, ThreadScope("web", thread_id))
        rows = await connection.fetch(_SNAPSHOT_SQL, ids)
        _validate_snapshot(manifest, _snapshots(rows))
        audit = json.dumps({
            "assigned_by": manifest.assigned_by, "evidence": manifest.evidence,
            "manifest_sha256": digest,
        }, ensure_ascii=False)
        for assignment in manifest.assignments:
            await connection.execute(
                """INSERT INTO web_thread_access(thread_id,user_id,owner_assignment)
                   VALUES($1,$2,$3::jsonb)""",
                assignment.thread_id, assignment.user_id, audit,
            )


async def owners_command(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="cli owners")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect")
    backfill = commands.add_parser("backfill")
    backfill.add_argument("--manifest", required=True, type=Path)
    backfill.add_argument("--apply", action="store_true")
    options = parser.parse_args(args)
    try:
        if options.command == "inspect":
            print(json.dumps(_snapshots(await fetch(_SNAPSHOT_SQL, None)), indent=2))
            return 0
        raw = options.manifest.read_bytes()
        manifest = OwnerManifest.model_validate_json(raw)
        ids = [row.thread_id for row in manifest.assignments]
        _validate_snapshot(manifest, _snapshots(await fetch(_SNAPSHOT_SQL, ids)))
        digest = hashlib.sha256(raw).hexdigest()
        if options.apply:
            await assign_legacy_owners(manifest, digest)
        print(json.dumps({
            "action": "applied" if options.apply else "dry_run",
            "manifest_sha256": digest, "assignments": len(ids),
            "external_evidence_verified": False,
        }))
        return 0
    except (OSError, ValueError, ThreadBusyError):
        print("Invalid/stale owner manifest or busy thread; no ownership inferred/overwritten.")
        return 1
