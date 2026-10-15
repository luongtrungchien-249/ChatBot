"""Content-free RAG evaluation aggregates with explicit measurement denominators."""

import hashlib
import json
import math
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from .metrics.latency import percentile

METRICS = (
    "recall",
    "faithfulness",
    "neo_recall",
    "context_recall",
    "context_precision",
    "claim_faithfulness",
    "answer_relevance",
    "required_claims_recall",
    "forbidden_claims_rate",
    "retrieval_scope_violation_rate",
    "retrieval_version_violation_rate",
)


def no_answer_summary(outcomes: list[dict[str, Any]], attempted: int) -> dict[str, Any]:
    """Positive = abstention expected/observed; unknowns never become negatives."""
    tp = fp = fn = tn = 0
    for row in outcomes:
        expected, refused = row.get("answerable"), row.get("refused")
        if expected is not None and not isinstance(expected, bool):
            raise ValueError("invalid answerable judgment")
        if refused is not None and not isinstance(refused, bool):
            raise ValueError("invalid refusal judgment")
        if expected is None or refused is None:
            continue
        if refused:
            tp += not expected
            fp += expected
        else:
            fn += not expected
            tn += expected
    measured = tp + fp + fn + tn
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "measured": measured,
        "unknown": attempted - measured,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "false_answer_rate": fn / (tp + fn) if tp + fn else None,
        "false_refusal_rate": fp / (fp + tn) if fp + tn else None,
    }


def source_identity(root: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    sources = sorted([*(root / "src").rglob("*.py"), *(root / "evals").rglob("*.py")])
    for source in sources:
        digest.update(source.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(source.read_bytes()).digest())
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=False
    )
    return {
        "source_sha256": digest.hexdigest(),
        "commit": commit or "unavailable",
        "worktree_dirty": bool(status.stdout) if status.returncode == 0 else None,
    }


def config_hash(config: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True, allow_nan=False).encode()).hexdigest()


def aggregate(
    outcomes: list[dict[str, Any]],
    attempted: int,
) -> dict[str, Any]:
    if attempted < len(outcomes):
        raise ValueError("attempted count cannot be smaller than completions")
    result: dict[str, Any] = {
        "attempted": attempted,
        "completed": len(outcomes),
        "failed": attempted - len(outcomes),
        "metrics": {},
    }
    for name in METRICS:
        observed: list[float] = []
        states: Counter[str] = Counter()
        for row in outcomes:
            value = row.get(name)
            if value is not None and (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                or not 0 <= value <= 1
            ):
                raise ValueError(f"invalid metric {name}")
            if value is not None:
                observed.append(float(value))
            state = row.get("metric_states", {}).get(
                name, "measured" if value is not None else "unknown"
            )
            if state not in {"measured", "unknown", "not_applicable", "disabled"} or (
                (state == "measured") != (value is not None)
            ):
                raise ValueError(f"inconsistent metric state {name}")
            states[state] += 1
        result["metrics"][name] = {
            "mean": sum(observed) / len(observed) if observed else None,
            "measured": len(observed),
            "unmeasured_completed": len(outcomes) - len(observed),
            "unknown_completed": states["unknown"],
            "not_applicable_completed": states["not_applicable"],
            "disabled_completed": states["disabled"],
        }
    result["no_answer"] = no_answer_summary(outcomes, attempted)
    if any(
        isinstance(row["latency_ms"], bool) or not isinstance(row["latency_ms"], (int, float))
        for row in outcomes
    ):
        raise ValueError("invalid latency")
    latencies = [float(row["latency_ms"]) for row in outcomes]
    if any(not math.isfinite(value) or value < 0 for value in latencies):
        raise ValueError("invalid latency")
    result["latency_p50_ms"] = percentile(latencies, 0.50) if latencies else None
    result["latency_p95_ms"] = percentile(latencies, 0.95) if latencies else None
    # Judge calls/embedding trace attribution are not measured by the runner.
    result["mean_cost_usd"] = result["p95_cost_usd"] = None
    return result


def build_artifact(
    *,
    selected: list[dict[str, str]],
    outcomes: list[dict[str, Any]],
    failures: list[dict[str, str]],
    dataset_sha256: str,
    corpus_before: str,
    corpus_after: str | None,
    config: dict[str, Any],
    measured_gate_passed: bool,
    dataset_stable: bool = True,
    source_stable: bool = True,
    dataset_readiness: dict[str, Any] | None = None,
    category_gate_passed: dict[str, bool] | None = None,
) -> dict[str, Any]:
    selected_ids = {row["id"] for row in selected}
    completed_ids = {row["id"] for row in outcomes}
    failed_ids = {row["id"] for row in failures}
    if (
        len(selected_ids) != len(selected)
        or len(completed_ids) != len(outcomes)
        or len(failed_ids) != len(failures)
        or completed_ids & failed_ids
        or selected_ids != completed_ids | failed_ids
    ):
        raise ValueError("every selected ID must have exactly one outcome or failure")
    categories_by_id = {row["id"]: row["category"] for row in selected}
    if any(row["category"] != categories_by_id[row["id"]] for row in outcomes):
        raise ValueError("outcome category differs from the selected dataset")
    stable = bool(
        corpus_after is not None
        and corpus_before == corpus_after
        and dataset_stable
        and source_stable
    )
    counts = Counter(row["category"] for row in selected)
    categories = {
        category: aggregate([row for row in outcomes if row["category"] == category], count)
        for category, count in sorted(counts.items())
    }
    for category, values in categories.items():
        values["measured_gate_passed"] = (
            category_gate_passed.get(category, False) if category_gate_passed is not None else None
        )
    return {
        "schema_version": 2,
        "dataset_sha256": dataset_sha256,
        "corpus_metadata_sha256": corpus_before,
        "corpus_after_metadata_sha256": corpus_after,
        "corpus_stable": corpus_before == corpus_after if corpus_after is not None else None,
        "dataset_stable": dataset_stable,
        "source_stable": source_stable,
        "config": config,
        "config_hash": config_hash(config),
        "dataset_readiness": dataset_readiness,
        "totals": aggregate(outcomes, len(selected)),
        "categories": categories,
        "failures": [{"id": row["id"], "error_type": row["error_type"]} for row in failures],
        "measured_gate_passed": measured_gate_passed,
        "run_passed": bool(selected) and measured_gate_passed and not failures and stable,
        "release_gate_b_accepted": False,
        "limitations": [
            "missing costs",
            "LLM final-answer judgments require human calibration",
            "scope/version final-answer citation provenance not attested",
            "human review declarations require external identity/independence verification",
            "metric means exclude failures; attempted/completed/failed are separate",
            "corpus fingerprint is metadata, not chunk/vector content",
        ],
    }


def write_artifact(path: Path, artifact: dict[str, Any]) -> None:
    # Refuse accidental overwrite of previous evidence. No questions/answers or
    # exception messages are accepted by the runner's allowlisted serialization.
    rendered = json.dumps(artifact, ensure_ascii=True, allow_nan=False, indent=2) + "\n"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(rendered)
