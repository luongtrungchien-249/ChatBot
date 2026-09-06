"""Chay bo cau hoi trong dataset/qa.jsonl, xuat bang chi so.

TODO(giai-doan-8). Chua viet vi thieu dau vao that: 50 cau hoi phai VIET TAY dua
tren tai lieu that cua to chuc, va tai lieu do chua duoc nap (Giai doan 6). Sinh
cau hoi tu dong roi cham diem bang chinh model la do luong vong tron.

Nguong o docs/plan-thi-cong.md section 10:
    Recall@5 > 0,85 · Faithfulness > 0,9 · Answer relevance > 0,85
    Latency p95 < 5s · Cost/query theo ngan sach

Chay: uv run python -m evals.runner
"""

import json
import sys
from pathlib import Path
from typing import Any

DATASET = Path(__file__).resolve().parent / "dataset" / "qa.jsonl"


def load_dataset() -> list[dict[str, Any]]:
    """Doc qa.jsonl. Moi dong: {question, answer, expected_chunk_ids}."""
    if not DATASET.exists():
        return []
    return [
        json.loads(line)
        for line in DATASET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    rows = load_dataset()
    print(f"Bo eval: {len(rows)} cau trong {DATASET}")
    print("Runner chua duoc viet — xem TODO(giai-doan-8) o dau file.")
    # Tra ve 0: CI khong duoc do vi mot viec CO Y chua lam. Khi runner chay that,
    # cho nay se tra ve 1 neu bat ky nguong nao khong dat.
    return 0


if __name__ == "__main__":
    sys.exit(main())
