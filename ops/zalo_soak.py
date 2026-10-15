"""Repeated synthetic Zalo fault checks in fresh processes; no external API calls.

This is a laboratory soak. It cannot certify upstream cursor semantics, remote
exactly-once delivery or real persistent-store recovery. Use --duration-s 10800
only for the requested three-hour lab run; a short smoke run is not Gate C.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
SUITE = (
    "tests/unit/test_zalo_polling_delivery.py",
    "tests/unit/test_zalo_api.py",
    "tests/unit/test_zalo_normalize.py",
    "tests/unit/test_zalo_synthetic_chaos.py",
    "tests/contract/test_zalo_contract.py",
)


def synthetic_environment() -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        NODE_ENV="test",
        WEB_AUTH_MODE="dev",
        WEB_BIND="127.0.0.1",
        OPENAI_API_KEY="sk-synthetic-no-network",
        EMBEDDING_PROVIDER="fake",
        EMBEDDING_API_KEY="fake",
        EMBEDDING_MODEL="fake",
        EMBEDDING_DIM="1024",
        RERANK_PROVIDER="fake",
        RERANK_API_KEY="fake",
        RERANK_MODEL="fake",
        RERANK_MIN_SCORE="0.45",
        DAILY_BUDGET_USD="1",
        BOT_MENTION_NAME="CP_Assistant",
        DATABASE_URL="postgresql://synthetic:synthetic@127.0.0.1:65432/synthetic",
        REDIS_URL="redis://127.0.0.1:65433/15",
        ZALO_MODE="polling",
        ZALO_BOT_TOKEN="synthetic-no-network",
        PYTHONUTF8="1",
        PYTEST_ADDOPTS="",
        METRICS_SCRAPE_TOKEN="",
    )
    env.pop("CI", None)
    return env


def read_cycle(path: Path) -> dict[str, int]:
    summary = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for case in ElementTree.parse(path).getroot().iter("testcase"):
        summary["tests"] += 1
        for tag, key in (("failure", "failures"), ("error", "errors"), ("skipped", "skipped")):
            summary[key] += int(case.find(tag) is not None)
    return summary


def run_soak(duration_s: float, max_cycles: int) -> dict[str, Any]:
    if duration_s <= 0 or max_cycles < 0:
        raise ValueError("duration must be positive and max_cycles non-negative")
    started = time.monotonic()
    cycles: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="cp-zalo-synthetic-") as directory:
        while time.monotonic() - started < duration_s and (
            not max_cycles or len(cycles) < max_cycles
        ):
            junit = Path(directory) / "cycle.xml"
            result = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    "-m",
                    "pytest",
                    *SUITE,
                    "-o",
                    "addopts=",
                    "-q",
                    f"--junitxml={junit}",
                ],
                cwd=ROOT,
                env=synthetic_environment(),
                capture_output=True,
                timeout=60,
                check=False,
            )
            summary = read_cycle(junit) if junit.exists() else {"tests": 0, "errors": 1}
            cycles.append({"cycle": len(cycles) + 1, "exit_code": result.returncode, **summary})
            if result.returncode or summary.get("skipped") or not summary["tests"]:
                break
    elapsed = round(time.monotonic() - started, 3)
    return {
        "kind": "synthetic_zalo_process_restart_soak",
        "completed_at": datetime.now(UTC).isoformat(),
        "requested_duration_s": duration_s,
        "elapsed_s": elapsed,
        "completed_requested_duration": elapsed >= duration_s,
        "cycles": cycles,
        "passed": bool(cycles)
        and all(c["exit_code"] == 0 and not c.get("skipped") for c in cycles),
        "external_messages_sent": 0,
        "gate_c_accepted": False,
        "not_verified": [
            "live upstream receive/ack semantics",
            "PostgreSQL/Redis persistence",
            "remote send-before-marker crash",
            "production hours-long soak",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-s", type=float, default=10800)
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        with args.output.open("x", encoding="utf-8") as stream:
            report = run_soak(args.duration_s, args.max_cycles)
            json.dump(report, stream, indent=2)
            stream.write("\n")
        print(
            f"Synthetic cycles: {len(report['cycles'])}; passed: {report['passed']}; "
            "Gate C: not accepted."
        )
        return 0 if report["passed"] else 1
    except (OSError, ValueError, subprocess.TimeoutExpired, ElementTree.ParseError):
        print("Synthetic soak failed; private child output suppressed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
