"""Reproduce and recover a synthetic schema-25 archive using isolated PG16 containers.

No existing DB/DSN is accepted. Default prints a plan. CI uses --execute-isolated.
The local pgvector/pgvector:pg16 image must exist; no image pull is performed.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from restore_drill import (
    IMAGE,
    ArchiveRestoreError,
    _run,
    cleanup_container,
    container_name,
    execute_drill,
    start_command,
    wait_for_database,
)

ROOT = Path(__file__).resolve().parents[1]


def create_legacy_fixture(archive: Path) -> None:
    name, marker = container_name(uuid.uuid4().hex), secrets.token_hex(16)
    environment = dict(os.environ)
    environment["POSTGRES_PASSWORD"] = secrets.token_urlsafe(32)
    archive.write_bytes(b"PGDMPsynthetic-placeholder")
    attempted = False
    try:
        attempted = True
        _run(start_command(archive, name, marker), environment=environment)
        wait_for_database(name)

        def sql(text: str) -> None:
            _run([
                "docker", "exec", "-i", name, "psql", "-X", "-v", "ON_ERROR_STOP=1",
                "-U", "drill", "-d", "drill", "-f", "-",
            ], input_text=text)

        sql("CREATE TABLE schema_migration(filename TEXT PRIMARY KEY, "
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT now());")
        for path in sorted((ROOT / "db/migrations").glob("*.sql")):
            if int(path.name[:4]) > 25:
                continue
            sql("BEGIN;\n" + path.read_text(encoding="utf-8")
                + "\nINSERT INTO schema_migration(filename) VALUES ('"
                + path.name.replace("'", "''") + "');\nCOMMIT;")
        vector = "[" + ",".join(["0"] * 1024) + "]"
        sql(
            "INSERT INTO kb_document(title,source_path,version,checksum,ingested_by) "
            "VALUES('synthetic','synthetic',1,'" + "a" * 64 + "','test');"
            "INSERT INTO kb_chunk(doc_id,ord,content,embed_input,embedding,token_count) "
            "VALUES(1,1,'Nghỉ phép năm','Nghỉ phép năm','" + vector + "',4);"
        )
        # Binary dump goes to a private synthetic file; stdout/stderr never reach CI logs.
        with archive.open("wb") as stream:
            result = subprocess.run(
                ["docker", "exec", name, "pg_dump", "-U", "drill", "-d", "drill", "-Fc"],
                stdout=stream, stderr=subprocess.PIPE, timeout=300, check=False,
            )
        if result.returncode:
            raise RuntimeError("Synthetic archive creation failed")
    finally:
        if attempted and not cleanup_container(name, marker):
            raise RuntimeError("Synthetic source cleanup could not be verified")


def run_smoke() -> dict[str, Any]:
    directory = ROOT / "evals/results"
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="restore-smoke-", dir=directory) as temporary:
        resolved = Path(temporary).resolve()
        if not resolved.is_relative_to(directory.resolve()):
            raise ValueError("Synthetic temporary directory escaped its artifact root")
        archive = resolved / "legacy.dump"
        create_legacy_fixture(archive)
        failed_without_override = False
        try:
            execute_drill(archive)
        except ArchiveRestoreError:
            failed_without_override = True
        if not failed_without_override:
            raise RuntimeError("Legacy failure was not reproduced; inspect fixture assumptions")
        recovered = execute_drill(archive, legacy_vn_tsv=True)
        if recovered["table_counts"]["kb_chunk"] != 1:
            raise RuntimeError("Synthetic restored data did not match the fixture")
        return {
            "kind": "synthetic_legacy_restore_smoke", "image": IMAGE,
            "unpatched_restore_failed": True, "recovered": recovered,
            "production_gate_accepted": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-isolated", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.execute_isolated:
        print("Plan: schema-25 fixture; expected failed restore; explicit override; cleanup.")
        return 0
    if args.output is None:
        parser.error("--output is required")
    try:
        with args.output.open("x", encoding="utf-8") as stream:
            try:
                report = run_smoke()
            except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
                json.dump({
                    "kind": "synthetic_legacy_restore_smoke", "verified": False,
                    "error_type": type(error).__name__, "production_gate_accepted": False,
                }, stream, indent=2)
                raise
            json.dump(report, stream, indent=2)
            stream.write("\n")
        print("Synthetic legacy archive recovery verified; production gate remains unaccepted.")
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
        print("Synthetic restore smoke failed; private subprocess output suppressed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
