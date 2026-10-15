"""Restore a custom-format backup into a fresh, disposable Docker database.

Default is a plan only. --execute-isolated never accepts a target DSN, existing
container or volume; it restores with no network and removes only its own container.
Backup contents are sensitive: container cleanup is not a certified secure erase.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

IMAGE = "pgvector/pgvector:pg16"
LABEL_PREFIX = "com.cp-assistant.restore-drill"
EXPECTED_TABLES = (
    "inbound_message",
    "memory_fact",
    "thread_summary",
    "kb_document",
    "kb_chunk",
    "web_thread_access",
    "web_thread_generation",
    "zalo_inbox",
    "turn_telemetry",
    "rag_telemetry",
)


class ArchiveRestoreError(RuntimeError):
    """Restore failed after the owned target became ready; no raw SQL in the message."""


def validate_backup(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or "," in str(resolved):
        raise ValueError("backup must be a regular file suitable for a Docker bind mount")
    with resolved.open("rb") as stream:
        if stream.read(5) != b"PGDMP":
            raise ValueError("backup must be pg_dump custom format (-Fc)")
    return resolved


def container_name(identifier: str) -> str:
    if len(identifier) != 32 or any(char not in "0123456789abcdef" for char in identifier):
        raise ValueError("drill identifier must be a newly generated UUID hex")
    return f"cp-restore-drill-{identifier}"


def start_command(backup: Path, name: str, task_marker: str) -> list[str]:
    if not name.startswith("cp-restore-drill-"):
        raise ValueError("refuse a non-drill container name")
    container_name(name.removeprefix("cp-restore-drill-"))
    container_name(task_marker)  # Same constrained hex shape, independent nonce.
    return [
        "docker",
        "run",
        "--detach",
        "--pull=never",
        "--name",
        name,
        "--label",
        f"{LABEL_PREFIX}.id={name.removeprefix('cp-restore-drill-')}",
        "--label",
        f"{LABEL_PREFIX}.marker={task_marker}",
        "--network",
        "none",
        "--tmpfs",
        "/var/lib/postgresql/data:rw,size=2048m",
        "--mount",
        f"type=bind,source={backup},target=/backup.dump,readonly",
        "--env",
        "POSTGRES_PASSWORD",
        "--env",
        "POSTGRES_USER=drill",
        "--env",
        "POSTGRES_DB=drill",
        IMAGE,
    ]


def _run(
    command: list[str], *, environment: dict[str, str] | None = None,
    input_text: str | None = None,
) -> str:
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", timeout=300,
        check=False, env=environment, input=input_text,
    )
    if result.returncode:
        # pg_restore/Docker stderr can include private paths, SQL and data.
        raise RuntimeError("isolated Docker operation failed; private output suppressed")
    return result.stdout.strip()


def legacy_restore_lists(toc: str) -> tuple[str, str, int]:
    """Allow only our exact public function and vector/unaccent extensions.

    Keep every other TOC entry/order unchanged; archive bytes are never edited.
    Unexpected/ambiguous entries fail before any bootstrap or table restore.
    """
    extensions: dict[str, str] = {}
    function_ids: list[int] = []
    identifiers: set[int] = set()
    main: list[str] = []
    for line in toc.splitlines():
        if not line.strip() or line.lstrip().startswith(";"):
            main.append(line)
            continue
        entry = re.fullmatch(r"(\d+);\s+\d+\s+\d+\s+(.+)", line)
        if entry is None or int(entry[1]) in identifiers:
            raise ValueError("Invalid or duplicate archive TOC entries")
        identifiers.add(int(entry[1]))
        description = entry[2]
        if description.startswith("EXTENSION "):
            extension = re.fullmatch(r"EXTENSION - (vector|unaccent)(?:\s+.*)?", description)
            if extension is None or extension[1] in extensions:
                raise ValueError("Legacy mode requires only known vector/unaccent extensions")
            extensions[extension[1]] = line
            main.append("; " + line)
        elif re.fullmatch(r"FUNCTION public vn_tsv\(text\)(?:\s+.*)?", description):
            function_ids.append(int(entry[1]))
            main.append("; " + line)
        else:
            main.append(line)
    if set(extensions) != {"vector", "unaccent"} or len(function_ids) != 1:
        raise ValueError("Legacy override needs one public.vn_tsv(text) and both extensions")
    return "\n".join(extensions.values()) + "\n", "\n".join(main) + "\n", function_ids[0]


def restore_archive(
    run: Callable[[list[str], str | None], str], *, legacy_vn_tsv: bool = False,
) -> dict[str, Any]:
    base = ["pg_restore", "--single-transaction", "--no-owner", "--no-acl",
            "-U", "drill", "-d", "drill"]
    override: dict[str, Any] = {"legacy_vn_tsv_override": False}
    if legacy_vn_tsv:
        toc = run(["pg_restore", "--list", "/backup.dump"], None)
        extensions, main, identifier = legacy_restore_lists(toc)
        sql_path = (
            Path(__file__).resolve().parents[1] / "db/migrations/0026_restore_safe_vn_tsv.sql"
        )
        sql = sql_path.read_text(encoding="utf-8")
        run(["tee", "/tmp/cp-restore-extensions.list"], extensions)
        run(["tee", "/tmp/cp-restore-main.list"], main)
        run([*base, "--use-list=/tmp/cp-restore-extensions.list", "/backup.dump"], None)
        run(["psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "drill", "-d", "drill", "-f", "-"], sql)
        base += ["--use-list=/tmp/cp-restore-main.list"]
        override = {
            "legacy_vn_tsv_override": True, "omitted_function_toc_id": identifier,
            "bootstrap_sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
            "schema_migration_not_marked": True,
        }
    run([*base, "/backup.dump"], None)
    return override


def cleanup_container(name: str, task_marker: str) -> bool:
    """Delete only the inspected immutable ID belonging to this exact drill task."""
    identifier = name.removeprefix("cp-restore-drill-")
    if container_name(identifier) != name:
        raise ValueError("refuse non-drill cleanup target")
    container_name(task_marker)
    result = subprocess.run(
        ["docker", "inspect", "--type", "container", name],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        return False  # Absent/unavailable; never substitute an arbitrary target.
    inspected = json.loads(result.stdout)
    if not isinstance(inspected, list) or len(inspected) != 1:
        raise ValueError("refuse ambiguous cleanup inspection")
    container = inspected[0]
    labels = container.get("Config", {}).get("Labels", {}) or {}
    container_id = container.get("Id", "")
    if (
        container.get("Name") != f"/{name}"
        or container.get("Config", {}).get("Image") != IMAGE
        or labels.get(f"{LABEL_PREFIX}.id") != identifier
        or labels.get(f"{LABEL_PREFIX}.marker") != task_marker
        or container.get("HostConfig", {}).get("NetworkMode") != "none"
        or len(container_id) != 64
        or any(char not in "0123456789abcdef" for char in container_id)
    ):
        raise ValueError("refuse cleanup of a container not verified as this isolated drill")
    # Immutable ID avoids deleting a replacement created under the inspected name.
    _run(["docker", "rm", "--force", "--volumes", container_id])
    return True


def wait_for_database(name: str) -> None:
    for _ in range(45):
        ready = subprocess.run(
            ["docker", "exec", name, "pg_isready", "-U", "drill", "-d", "drill"],
            capture_output=True, timeout=10, check=False,
        )
        if ready.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("isolated database did not become ready")


def execute_drill(backup: Path, *, legacy_vn_tsv: bool = False) -> dict[str, Any]:
    name = container_name(uuid.uuid4().hex)
    task_marker = secrets.token_hex(16)
    env = dict(os.environ)
    env["POSTGRES_PASSWORD"] = secrets.token_urlsafe(32)
    start_attempted = False
    created = False
    started = time.monotonic()
    with backup.open("rb") as stream:
        original_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    try:
        start_attempted = True
        _run(start_command(backup, name, task_marker), environment=env)
        created = True
        wait_for_database(name)
        def run_program(command: list[str], input_text: str | None) -> str:
            prefix = ["docker", "exec", *(["-i"] if input_text is not None else []), name]
            return _run([*prefix, *command], input_text=input_text)

        try:
            override = restore_archive(run_program, legacy_vn_tsv=legacy_vn_tsv)
        except RuntimeError:
            raise ArchiveRestoreError("Archive restore failed; output is private") from None
        # Table names are fixed code identifiers; no user content, IDs or facts.
        counts: dict[str, int] = {}
        for table in EXPECTED_TABLES:
            value = _run(
                [
                    "docker",
                    "exec",
                    name,
                    "psql",
                    "-X",
                    "-At",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-U",
                    "drill",
                    "-d",
                    "drill",
                    "-c",
                    f"SELECT count(*) FROM public.{table}",
                ]
            )
            counts[table] = int(value)
        with backup.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != original_hash:
            raise RuntimeError("Backup changed during restore; reject the drill evidence")
        return {
            "kind": "isolated_postgresql_restore_drill",
            "completed_at": datetime.now(UTC).isoformat(),
            "backup_sha256": digest,
            "image": IMAGE,
            "duration_s": round(time.monotonic() - started, 3),
            "table_counts": counts,
            "restore_verified": True,
            **override,
            "production_gate_accepted": False,
            "not_verified": [
                "Redis AOF restore",
                "migrations against restored schema",
                "application integration",
                "RTO/RPO",
                "traffic cutover",
            ],
        }
    finally:
        if start_attempted:
            # Docker run may time out after creating the container. Inspect this
            # generated task even when no successful start response was received.
            cleaned = cleanup_container(name, task_marker)
            if created and not cleaned:
                raise RuntimeError("isolated drill cleanup could not be verified")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("--execute-isolated", action="store_true")
    parser.add_argument("--legacy-vn-tsv", action="store_true",
                        help="Explicitly replace the known legacy function in the isolated target")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        backup = validate_backup(args.backup)
        if not args.execute_isolated:
            print(
                "Plan: fresh pgvector database; no network/host ports/app volumes; "
                "readonly archive; isolated restore then cleanup."
            )
            if args.legacy_vn_tsv:
                print(
                    "Legacy mode: exact vn_tsv TOC override; unchanged archive; no migration mark."
                )
            return 0
        if args.output is None:
            raise ValueError("--output is required for drill evidence")
        # Reserve an exclusive output before doing work; never overwrite evidence.
        with args.output.open("x", encoding="utf-8") as stream:
            try:
                report = execute_drill(backup, legacy_vn_tsv=args.legacy_vn_tsv)
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
                json.dump({
                    "kind": "isolated_postgresql_restore_drill", "restore_verified": False,
                    "production_gate_accepted": False, "error_type": type(error).__name__,
                    "legacy_vn_tsv_requested": args.legacy_vn_tsv,
                }, stream, indent=2)
                stream.write("\n")
                raise
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print("Isolated restore verified; remaining acceptance checks are listed in the report.")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        print(
            "Restore drill failed; no production database targeted. Check prerequisites privately."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
