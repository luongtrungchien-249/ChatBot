"""Read-only validation of golden chunk IDs against the current corpus metadata."""

import argparse
import asyncio
import contextlib
import hashlib
import io
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infra.db import close_db, get_pool

from .dataset_contract import GoldenRecord, load_and_validate


@dataclass(frozen=True, slots=True)
class ChunkReference:
    scope: str
    latest: bool


@dataclass(frozen=True, slots=True)
class CorpusIssue:
    record_id: str
    code: Literal["missing_chunk", "stale_version", "scope_mismatch", "missing_annotation"]
    count: int


@dataclass(frozen=True, slots=True)
class CorpusCheck:
    fingerprint: str
    questions: int
    references: int
    issues: tuple[CorpusIssue, ...] = ()

    @property
    def exit_code(self) -> int:
        if self.questions == 0:
            return 2
        if any(issue.code != "missing_annotation" for issue in self.issues):
            return 1
        return 2 if self.issues else 0


def check_references(
    records: list[GoldenRecord],
    references: dict[str, ChunkReference],
    fingerprint: str,
) -> CorpusCheck:
    issues: list[CorpusIssue] = []
    for record in records:
        if record.answerable and not record.expected_chunk_ids:
            issues.append(CorpusIssue(record.id, "missing_annotation", 1))
        counts = {"missing_chunk": 0, "stale_version": 0, "scope_mismatch": 0}
        for identifier in record.expected_chunk_ids:
            ref = references.get(identifier)
            if ref is None:
                counts["missing_chunk"] += 1
            elif not ref.latest:
                counts["stale_version"] += 1
            elif ref.scope not in {"chung", record.scope}:
                counts["scope_mismatch"] += 1
        for code, count in counts.items():
            if count:
                if code == "missing_chunk":
                    issues.append(CorpusIssue(record.id, "missing_chunk", count))
                elif code == "stale_version":
                    issues.append(CorpusIssue(record.id, "stale_version", count))
                else:
                    issues.append(CorpusIssue(record.id, "scope_mismatch", count))
    return CorpusCheck(
        fingerprint,
        len(records),
        sum(len(r.expected_chunk_ids) for r in records),
        tuple(issues),
    )


async def _snapshot(ids: list[str]) -> tuple[str, dict[str, ChunkReference]]:
    # Repeatable-read keeps the fingerprint and reference checks on ONE snapshot.
    # Only metadata is selected; no chunk text, titles, source paths or vectors.
    pool = await get_pool()
    async with pool.acquire() as conn, conn.transaction(isolation="repeatable_read", readonly=True):
        documents = await conn.fetch(
            """SELECT d.id,d.version,d.checksum,d.pham_vi,
                     (SELECT count(*) FROM kb_chunk c WHERE c.doc_id=d.id) AS chunks
                   FROM kb_document d WHERE d.la_ban_moi_nhat ORDER BY d.id"""
        )
        found = (
            await conn.fetch(
                """SELECT c.id::text AS id,d.pham_vi,d.la_ban_moi_nhat
                   FROM kb_chunk c JOIN kb_document d ON d.id=c.doc_id
                   WHERE c.id::text=ANY($1::text[])""",
                ids,
            )
            if ids
            else []
        )
    fingerprint = hashlib.sha256(
        json.dumps([dict(row) for row in documents], sort_keys=True).encode()
    ).hexdigest()
    return fingerprint, {
        row["id"]: ChunkReference(row["pham_vi"], row["la_ban_moi_nhat"]) for row in found
    }


async def check_corpus(records: list[GoldenRecord]) -> CorpusCheck:
    identifiers = sorted(
        {identifier for record in records for identifier in record.expected_chunk_ids}
    )
    fingerprint, references = await _snapshot(identifiers)
    return check_references(records, references, fingerprint)


async def corpus_fingerprint() -> str:
    fingerprint, _ = await _snapshot([])
    return fingerprint


def as_artifact(result: CorpusCheck) -> dict[str, Any]:
    return {
        "schema_version": 1,
        **asdict(result),
        "exit_code": result.exit_code,
        "fingerprint_kind": "latest_document_metadata_and_chunk_counts_not_content",
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        records = load_and_validate(args.dataset)
        with contextlib.redirect_stdout(io.StringIO()):
            result = await check_corpus(records)
        rendered = json.dumps(as_artifact(result), ensure_ascii=True, indent=2)
        print(rendered)
        if args.output:
            with args.output.open("x", encoding="utf-8") as output:
                output.write(rendered + "\n")
        return result.exit_code
    except (OSError, ValueError) as error:
        print(f"Corpus preflight failed ({type(error).__name__}).", file=sys.stderr)
        return 1
    except Exception as error:
        # DSNs/auth/provider errors may include secrets: print only the type.
        print(f"Corpus metadata unavailable ({type(error).__name__}).", file=sys.stderr)
        return 1
    finally:
        await close_db()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
