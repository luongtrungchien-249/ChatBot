"""Kiem tra schema va chia dev/test on dinh cho golden RAG."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Split = Literal["development", "test"]
MINIMUM_TOTAL = 60
REQUIRED_GROUPS = {
    "single_chunk": 15,
    "multi_chunk": 10,
    "distant_paraphrase": 10,
    "cross_language": 10,
    "unanswerable": 10,
    "scope_version_adversarial": 5,
}


@dataclass(frozen=True, slots=True)
class GoldenRecord:
    id: str
    question: str
    expected_answer: str
    expected_chunk_ids: tuple[str, ...]
    required_claims: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    category: str
    answerable: bool
    scope: str
    notes: str


def split_for_id(record_id: str) -> Split:
    bucket = int(hashlib.sha256(record_id.encode()).hexdigest()[:8], 16) % 10
    return "development" if bucket < 4 else "test"


def _record(data: Any, line: int) -> GoldenRecord:
    if not isinstance(data, dict):
        raise ValueError(f"dong {line}: record phai la object")

    def text(name: str, fallback: str = "") -> str:
        value = data.get(name, fallback)
        if not isinstance(value, str):
            raise ValueError(f"dong {line}: {name} phai la string")
        return value.strip()

    def strings(name: str, legacy: str | None = None) -> tuple[str, ...]:
        value = data.get(name, data.get(legacy, []) if legacy else [])
        if not isinstance(value, list) or any(
            not isinstance(x, str) or not x.strip() for x in value
        ):
            raise ValueError(f"dong {line}: {name} phai la list cac string khong rong")
        return tuple(x.strip() for x in value)

    record_id = text("id")
    question = text("question")
    category = text("category", text("loai", "khong_phan_loai"))
    answer = text("expected_answer", text("answer"))
    if not record_id or not question:
        raise ValueError(f"dong {line}: id va question bat buoc")
    answerable = data.get("answerable", category not in {"ngoai_kho", "unanswerable"})
    if not isinstance(answerable, bool):
        raise ValueError(f"dong {line}: answerable phai la boolean")
    if category in {"unanswerable", "ngoai_kho"} and answerable:
        raise ValueError(f"dong {line}: unanswerable category contradicts answerable")
    if "category" in data and category not in REQUIRED_GROUPS:
        raise ValueError(f"dong {line}: category khong thuoc nhom nghiem thu")
    expected_ids = strings("expected_chunk_ids")
    if len(set(expected_ids)) != len(expected_ids):
        raise ValueError(f"dong {line}: expected_chunk_ids trung")
    if not answerable and expected_ids:
        raise ValueError(f"dong {line}: unanswerable khong duoc co expected_chunk_ids")
    if not text("scope", "chung"):
        raise ValueError(f"dong {line}: scope khong duoc rong")
    required, forbidden = strings("required_claims", "neo"), strings("forbidden_claims")
    if len(set(required)) != len(required) or len(set(forbidden)) != len(forbidden):
        raise ValueError(f"dong {line}: duplicate claim annotations")
    if set(required) & set(forbidden):
        raise ValueError(f"dong {line}: required and forbidden claims overlap")
    return GoldenRecord(
        id=record_id,
        question=question,
        expected_answer=answer,
        expected_chunk_ids=expected_ids,
        required_claims=required,
        forbidden_claims=forbidden,
        category=category,
        answerable=answerable,
        scope=text("scope", "chung"),
        notes=text("notes"),
    )


def load_and_validate(path: Path) -> list[GoldenRecord]:
    records = [
        _record(json.loads(raw), line)
        for line, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if raw.strip()
    ]
    ids = Counter(record.id for record in records)
    duplicate = sorted(key for key, count in ids.items() if count > 1)
    if duplicate:
        raise ValueError(f"id trung: {duplicate}")
    if any("VI DU" in record.question for record in records):
        raise ValueError("dataset con placeholder VI DU")
    _validate_near_duplicates(records)
    return records


def _words(question: str) -> set[str]:
    return set(re.findall(r"\w+", question.casefold(), flags=re.UNICODE))


def _validate_near_duplicates(records: list[GoldenRecord]) -> None:
    for index, left in enumerate(records):
        left_words = _words(left.question)
        for right in records[index + 1 :]:
            right_words = _words(right.question)
            union = left_words | right_words
            similarity = len(left_words & right_words) / len(union) if union else 1.0
            if similarity >= 0.85 and split_for_id(left.id) != split_for_id(right.id):
                raise ValueError(
                    f"cau gan trung khac split: {left.id} va {right.id} ({similarity:.2f})"
                )


def coverage(records: list[GoldenRecord]) -> dict[str, int]:
    return dict(sorted(Counter(record.category for record in records).items()))


def coverage_deficits(records: list[GoldenRecord]) -> dict[str, int]:
    # Only two legacy types have an unambiguous correspondence. Do not assume
    # that an attribute/procedure question is a distant paraphrase or single chunk.
    aliases = {"xuyen_ngon_ngu": "cross_language", "ngoai_kho": "unanswerable"}
    counts = Counter(aliases.get(record.category, record.category) for record in records)
    return {
        category: minimum - counts[category]
        for category, minimum in REQUIRED_GROUPS.items()
        if counts[category] < minimum
    }


def annotation_deficits(records: list[GoldenRecord]) -> dict[str, int]:
    missing = {
        "answerable_without_expected_answer": sum(
            record.answerable and not record.expected_answer for record in records
        ),
        "answerable_without_chunk_annotation": sum(
            record.answerable and not record.expected_chunk_ids for record in records
        ),
    }
    return {name: count for name, count in missing.items() if count}


def review_template(path: Path, records: list[GoldenRecord], author_id: str) -> dict[str, Any]:
    """Create a pending declaration, never an automatic human sign-off."""
    if not author_id.strip():
        raise ValueError("opaque author ID required")
    return {
        "schema_version": 1,
        "dataset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "record_sha256": {
            record.id: hashlib.sha256(
                json.dumps(dataclasses.asdict(record), sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            for record in records
        },
        "author_id_sha256": hashlib.sha256(author_id.strip().encode()).hexdigest(),
        "reviewer_id_sha256": None,
        "reviewed_ids": [],
        "source_checked": False,
        "labels_before_model_results": False,
        "test_locked": False,
        "locked_eval_config_sha256": None,
    }


def check_review(
    path: Path,
    records: list[GoldenRecord],
    manifest: Path | None,
    locked_config_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate content-free declarations; identities/independence remain human obligations."""
    if manifest is None:
        return {"status": "missing", "attested": False, "reviewed": 0}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("invalid review manifest schema")
    current = review_template(path, records, "unused-template-author")
    if data.get("dataset_sha256") != current["dataset_sha256"] or (
        data.get("record_sha256") != current["record_sha256"]
    ):
        raise ValueError("review manifest does not match dataset snapshot")
    sha = re.compile(r"[0-9a-f]{64}")
    author, reviewer = data.get("author_id_sha256"), data.get("reviewer_id_sha256")
    if not isinstance(author, str) or not sha.fullmatch(author):
        raise ValueError("invalid author identity hash")
    if reviewer is not None and (
        not isinstance(reviewer, str) or not sha.fullmatch(reviewer) or reviewer == author
    ):
        raise ValueError("review requires distinct author and reviewer identity hashes")
    reviewed = data.get("reviewed_ids")
    if not isinstance(reviewed, list) or any(not isinstance(key, str) for key in reviewed):
        raise ValueError("reviewed_ids must be a list of IDs")
    expected = {record.id for record in records}
    if len(reviewed) != len(set(reviewed)) or not set(reviewed) <= expected:
        raise ValueError("unknown or duplicate reviewed IDs")
    flags = ("source_checked", "labels_before_model_results", "test_locked")
    if any(not isinstance(data.get(name), bool) for name in flags):
        raise ValueError("review declarations must be booleans")
    locked = data.get("locked_eval_config_sha256")
    if locked is not None and (not isinstance(locked, str) or not sha.fullmatch(locked)):
        raise ValueError("invalid locked evaluation config hash")
    if locked_config_sha256 is not None and locked != locked_config_sha256:
        raise ValueError("test evaluation configuration differs from reviewed lock")
    attested = bool(
        reviewer and locked and set(reviewed) == expected and all(data[name] for name in flags)
    )
    return {
        "status": "attested" if attested else "incomplete",
        "attested": attested,
        "reviewed": len(reviewed),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "locked_eval_config_sha256": locked,
        "independence_verified_by_tool": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline golden coverage and review declarations")
    parser.add_argument("dataset", type=Path, nargs="?", default=Path("evals/dataset/golden.jsonl"))
    parser.add_argument("--review-manifest", type=Path)
    parser.add_argument("--prepare-review", type=Path)
    parser.add_argument("--author-id", help="Opaque ID, not a name/email")
    parser.add_argument("--reviewer-id", help="Optional opaque reviewer ID; no attestation is made")
    args = parser.parse_args()
    path = args.dataset
    try:
        records = load_and_validate(path)
        if args.prepare_review:
            if not args.author_id:
                raise ValueError("--prepare-review requires --author-id")
            content = review_template(path, records, args.author_id)
            if args.reviewer_id:
                if args.reviewer_id.strip() == args.author_id.strip():
                    raise ValueError("reviewer ID must differ from author ID")
                content["reviewer_id_sha256"] = hashlib.sha256(
                    args.reviewer_id.strip().encode()
                ).hexdigest()
            with args.prepare_review.open("x", encoding="utf-8") as stream:
                json.dump(content, stream, indent=2, ensure_ascii=True)
                stream.write("\n")
        review = check_review(path, records, args.review_manifest)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Dataset khong hop le: {error}", file=sys.stderr)
        return 1
    splits = Counter(split_for_id(record.id) for record in records)
    deficits = coverage_deficits(records)
    missing_annotations = annotation_deficits(records)
    print(
        json.dumps(
            {
                "total": len(records),
                "splits": splits,
                "categories": coverage(records),
                "coverage_deficits": deficits,
                "annotation_deficits": missing_annotations,
                "minimum_total": MINIMUM_TOTAL,
                "review": review,
            }
        )
    )
    if len(records) < MINIMUM_TOTAL or deficits or missing_annotations or not review["attested"]:
        print(
            f"Dataset not ready: {len(records)}/{MINIMUM_TOTAL}; "
            f"coverage={deficits}; review={review['status']}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
