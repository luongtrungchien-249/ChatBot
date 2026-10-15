"""Prepare an unreviewed, balanced poetry candidate pool offline; never invent human scores."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from evals.human_review import (  # noqa: E402
    CANDIDATE_CATEGORIES,
    SUPPORTED_FORMS,
    canonical_poem,
)
from tho import kiem_luc_bat, kiem_that_ngon_tu_tuyet  # noqa: E402
from tho.bat_cu import kiem_that_ngon_bat_cu  # noqa: E402


def _sha(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def law_errors(poem: str, form: str) -> list[str]:
    if form == "luc_bat":
        errors = kiem_luc_bat(poem, kiem_bang_trac=True)
    elif form == "that_ngon_tu_tuyet":
        errors = kiem_that_ngon_tu_tuyet(poem, kiem_bang_trac=True)
    elif form == "that_ngon_bat_cu":
        errors = kiem_that_ngon_bat_cu(poem)
    else:
        raise ValueError("unsupported poem form")
    return [error.loai for error in errors]


def _form(poem: str) -> str | None:
    lengths = [len(line.split()) for line in poem.splitlines()]
    if (
        len(lengths) >= 2
        and len(lengths) % 2 == 0
        and all(length == (6 if index % 2 == 0 else 8) for index, length in enumerate(lengths))
    ):
        return "luc_bat"
    if lengths == [7] * 4:
        return "that_ngon_tu_tuyet"
    if lengths == [7] * 8:
        return "that_ngon_bat_cu"
    return None


def _source_record(
    poem: str, form: str, path: Path, kind: str, index: int, machine: Any = None
) -> dict[str, Any]:
    return {
        "tho": poem,
        "form": form,
        "may": machine,
        "provenance": {
            "kind": kind,
            "path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name,
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_record_index": index,
            "source_poem_sha256": _sha(poem),
            "rights_independently_verified": False,
        },
    }


def read_sources(generated: Path, references: Path) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    if generated.exists():
        for index, line in enumerate(generated.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            row = json.loads(line)
            poem = canonical_poem(row["tho"])
            form = _form(poem)
            if form:
                sources.append(
                    _source_record(
                        poem, form, generated, "existing_generated", index, row.get("may")
                    )
                )
    names = {
        "truyen-kieu.txt": "luc_bat",
        "tu-tuyet.txt": "that_ngon_tu_tuyet",
        "bat-cu.txt": "that_ngon_bat_cu",
    }
    for name, form in names.items():
        path = references / name
        if not path.exists():
            continue
        blocks: list[str] = []
        lines: list[str] = []
        for raw in [*path.read_text(encoding="utf-8").splitlines(), ""]:
            line = raw.strip()
            if line.startswith("#"):
                continue
            if line:
                lines.append(line)
            elif lines:
                blocks.append(canonical_poem("\n".join(lines)))
                lines = []
        if form == "luc_bat" and blocks and all(len(block.splitlines()) == 2 for block in blocks):
            # Adjacent couplets preserve context and the inter-couplet rhyme.
            blocks = [
                "\n".join(blocks[index : index + 2]) for index in range(0, len(blocks) - 1, 2)
            ]
        for index, poem in enumerate(blocks):
            sources.append(_source_record(poem, form, path, "reference_fixture", index))
    return sources


def transform(poem: str, category: str) -> tuple[str, str]:
    lines = [line.split() for line in poem.splitlines()]
    if category == "lawful_quality_candidate":
        return poem, "unchanged_source_quality_unreviewed"
    if category == "lawful_incoherent_candidate":
        # Keep rhyme words and all even tonal positions; disrupt phrase order.
        for words in lines:
            positions = [index for index in range(0, len(words) - 1, 2)]
            values = [words[index] for index in positions]
            for index, value in zip(positions, values[1:] + values[:1], strict=True):
                words[index] = value
        name = "rotate_odd_positions_preserving_rhyme_and_tone_constraints"
    elif category == "meaningful_invalid_candidate":
        lines[0].append("thêm")
        name = "append_one_syllable_to_first_line"
    elif category == "broken_word_candidate":
        lines[0][0] = "mưxx"
        name = "replace_first_word_with_explicit_invalid_syllable"
    elif category == "copy_candidate":
        lines[0][0] = "Nghe" if lines[0][0] != "Nghe" else "Nhìn"
        name = "near_copy_replace_only_first_word"
    elif category == "repetition_candidate":
        lines = lines[: len(lines) // 2] * 2
        name = "repeat_first_half_verbatim"
    else:
        raise ValueError("unsupported candidate category")
    return "\n".join(" ".join(words) for words in lines), name


def build_pool(sources: list[dict[str, Any]], per_category: int = 12) -> list[dict[str, Any]]:
    if per_category < 10:
        raise ValueError("at least 10 per category (60 total) required")
    pools = {
        form: [row for row in sources if row["form"] == form and not law_errors(row["tho"], form)]
        for form in SUPPORTED_FORMS
    }
    if any(not rows for rows in pools.values()):
        raise ValueError("need local verified-law source fixtures for all three forms")
    used: set[str] = set()
    result: list[dict[str, Any]] = []
    for category in CANDIDATE_CATEGORIES:
        for form_index, form in enumerate(SUPPORTED_FORMS):
            quota = per_category // len(SUPPORTED_FORMS) + (form_index < per_category % 3)
            found = 0
            ordered = sorted(
                pools[form],
                key=lambda row: (
                    row["provenance"]["kind"]
                    != (
                        "existing_generated"
                        if category == "lawful_quality_candidate"
                        else "reference_fixture"
                    ),
                    row["provenance"]["source_record_index"],
                    _sha(row["tho"]),
                ),
            )
            for source in ordered:
                poem, transformation = transform(source["tho"], category)
                key = _sha(poem)
                if key in used:
                    continue
                errors = law_errors(poem, form)
                if category == "lawful_incoherent_candidate" and errors:
                    continue
                used.add(key)
                result.append(
                    {
                        **source,
                        "tho": poem,
                        "category": category,
                        "review_status": "proposed_unreviewed",
                        "may": source.get("may")
                        if category == "lawful_quality_candidate"
                        else None,
                        "provenance": {
                            **source["provenance"],
                            "kind": source["provenance"]["kind"]
                            if category == "lawful_quality_candidate"
                            else "synthetic_adversarial",
                            "parent_kind": source["provenance"]["kind"],
                            "transformation": transformation,
                        },
                        "law_check": {
                            "bang_trac": True,
                            "error_count": len(errors),
                            "error_types": dict(Counter(errors)),
                            "not_a_semantic_quality_judgment": True,
                        },
                    }
                )
                found += 1
                if found == quota:
                    break
            if found != quota:
                raise ValueError(
                    f"insufficient distinct candidates: {category}/{form} ({found}/{quota})"
                )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generated", type=Path, default=ROOT / "evals/tho/bai_da_sinh.jsonl")
    parser.add_argument("--references-dir", type=Path, default=ROOT / "evals/corpus/tho")
    parser.add_argument("--per-category", type=int, default=12)
    args = parser.parse_args()
    manifest = args.output.with_suffix(".manifest.json")
    try:
        if args.output.exists() or manifest.exists():
            raise ValueError("output/manifest already exists; choose new paths")
        rows = build_pool(read_sources(args.generated, args.references_dir), args.per_category)
        rendered = "".join(
            json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in rows
        )
        metadata = {
            "schema_version": 1,
            "status": "candidate_pool_unreviewed",
            "total": len(rows),
            "distinct": len({_sha(row["tho"]) for row in rows}),
            "categories": dict(Counter(row["category"] for row in rows)),
            "forms": dict(Counter(row["form"] for row in rows)),
            "pool_sha256": _sha(rendered),
            "human_review_completed": False,
            "category_labels_human_reviewed": False,
            "hard_gate_authorized": False,
            "limitations": [
                "proposed categories need human verification",
                "rights not independently verified",
                "synthetic variants are related to their source and not independent samples",
                "existing legacy machine scores miss san_sang; judge reruns still required",
            ],
        }
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(rendered)
        with manifest.open("x", encoding="utf-8") as output:
            json.dump(metadata, output, ensure_ascii=True, allow_nan=False, indent=2)
            output.write("\n")
        print(json.dumps(metadata, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Candidate preparation failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
