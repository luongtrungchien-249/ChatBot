"""Chay bo cau hoi trong dataset/qa.jsonl, xuat bang chi so, DO khi khong dat nguong.

Vi sao ton tai: khong co eval thi moi thay doi prompt deu la doan mo. Doi mot chu
trong SYSTEM_PROMPT co the lam chat luong tut ma khong ai nhan ra trong hai tuan.

Nguong (docs/plan-thi-cong.md section 10):
    Recall@5 > 0,85 · Faithfulness > 0,9 · Latency p95 < 5s

CHAY TON TIEN THAT: moi cau la mot lan tim + mot lan tra loi + mot lan cham. Chay
nightly va khi PR dung vao prompt/, knowledge/ingest/, llm/models.py — khong phai
moi commit.

Chay: uv run python -m evals.runner
"""

import asyncio
import json
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agents.domain.thread import ThreadScope
from agents.ports.llm import CallContext
from agents.prompt.builder import render_knowledge
from agents.prompt.context import ContextInput, build_context
from infra.db import close_db
from infra.logger import get_logger
from infra.redis_client import close_redis
from knowledge.retrieve.service import knowledge
from llm.models import MODELS
from llm.openai_client import llm

from .metrics.faithfulness import judge_faithfulness
from .metrics.latency import percentile
from .metrics.recall import recall_at_k

#: Bo cau hoi mac dinh. Truyen duong dan khac lam tham so de chay thu tren mot bo
#: nho — vi du de kiem chinh runner nay con chay dung khong ma khong dung toi bo
#: chinh thuc: uv run python -m evals.runner duong/dan/khac.jsonl
DEFAULT_DATASET = Path(__file__).resolve().parent / "dataset" / "qa.jsonl"

#: Ma thoat. CI phan biet ba truong hop nay, va do la ly do chung khac nhau:
#:   0  dat het nguong
#:   1  TRUOT — co van de that, phai xem
#:   2  chua co du lieu de chay (dataset con la dong mau) — KHONG phai loi
#:
#: Gop 2 vao 1 thi job nightly do moi dem vi mot viec co y chua lam, va mot job do
#: thuong truc la mot job khong ai doc nua.
EXIT_DAT = 0
EXIT_TRUOT = 1
EXIT_CHUA_CO_DU_LIEU = 2

RECALL_MIN = 0.85
FAITHFULNESS_MIN = 0.9
LATENCY_P95_MAX_MS = 5_000

#: So chunk lay ra — Recall@5 nen la 5.
K = 5

#: Dataset mau di kem repo. Chay eval tren no roi bao "dat" la tu lua: no do dung
#: mot cau hoi khong co that tren mot tai lieu khong ton tai.
_PLACEHOLDER = "VI DU"

_log = get_logger()


@dataclass(frozen=True, slots=True)
class Row:
    id: str
    question: str
    answer: str
    expected_chunk_ids: list[str]


@dataclass(frozen=True, slots=True)
class Outcome:
    row: Row
    recall: float
    faithfulness: float
    latency_ms: int
    answer: str


def load_dataset(dataset: Path) -> list[Row]:
    """Doc qa.jsonl. Moi dong: {question, answer, expected_chunk_ids}."""
    if not dataset.exists():
        return []
    rows: list[Row] = []
    for line in dataset.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data: dict[str, Any] = json.loads(line)
        rows.append(
            Row(
                id=str(data.get("id") or len(rows)),
                question=data["question"],
                answer=data.get("answer", ""),
                expected_chunk_ids=[str(c) for c in data.get("expected_chunk_ids") or []],
            )
        )
    return rows


def is_placeholder(rows: list[Row]) -> bool:
    return all(_PLACEHOLDER in r.question for r in rows) if rows else True


async def run_one(row: Row) -> Outcome:
    trace_id = str(uuid.uuid4())
    scope = ThreadScope(platform="cli", thread_id=f"eval-{row.id}")
    ctx = CallContext(scope=scope, sender_id="eval", trace_id=trace_id)

    started = time.monotonic()
    chunks = await knowledge.search(scope, row.question, K)
    envelope = build_context(
        ContextInput(question=row.question, is_group=False, chunks=tuple(chunks)), _log
    )
    result = await llm.reply(
        system=envelope.system,
        messages=envelope.messages,
        max_tokens=MODELS["reply"].max_tokens,
        effort=MODELS["reply"].effort,
        ctx=ctx,
    )
    latency_ms = int((time.monotonic() - started) * 1000)

    # Cham TREN DUNG cac chunk da dua vao prompt, khong tren toan bo tai lieu: cau
    # hoi la "co bam vao thu no duoc doc khong", chu khong phai "co dung khong".
    # Cham TREN DUNG khoi tai lieu ma bot da nhin thay — cung mot ham render,
    # khong phai mot ban ghep lai.
    #
    # Da troi that: ban dau chi noi cac `content` lai voi nhau, tuc la bo mat ten
    # tai lieu va ten muc. Cau tra loi co trich dan '(theo So tay 2026, muc Chinh
    # sach hoan tien)' bi nguoi cham coi la chi tiet khong kiem chung duoc va cham
    # 0,5 — sai o phia NGUOI CHAM chu khong phai o bot. Va vi no cham deu moi cau
    # nen ket qua trong rat giong mot phep do that.
    context = render_knowledge(tuple(chunks))
    faithfulness = await judge_faithfulness(row.question, result.text, context, trace_id)

    return Outcome(
        row=row,
        recall=recall_at_k([c.chunk_id for c in chunks], row.expected_chunk_ids, K),
        faithfulness=faithfulness,
        latency_ms=latency_ms,
        answer=result.text,
    )


def _cho_phep_in_tieng_viet() -> None:
    """Console Windows mac dinh la cp1252 va nem UnicodeEncodeError khi in tieng Viet.

    Bao cao eval in ra chinh cau hoi cua nguoi dung, nen day khong phai truong hop
    hiem. infra/logger.py da lam dieu nay cho duong log; runner khong di qua do.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def report(outcomes: list[Outcome]) -> bool:
    """In bang chi so. True = dat het nguong."""
    recall = sum(o.recall for o in outcomes) / len(outcomes)
    faithfulness = sum(o.faithfulness for o in outcomes) / len(outcomes)
    p95 = percentile([float(o.latency_ms) for o in outcomes], 0.95)

    checks = [
        ("Recall@5", recall, RECALL_MIN, recall > RECALL_MIN, "{:.3f}"),
        ("Faithfulness", faithfulness, FAITHFULNESS_MIN, faithfulness > FAITHFULNESS_MIN, "{:.3f}"),
        ("Latency p95 (ms)", p95, LATENCY_P95_MAX_MS, p95 < LATENCY_P95_MAX_MS, "{:.0f}"),
    ]

    print(f"{len(outcomes)} cau" + chr(10))
    for name, value, threshold, ok, fmt in checks:
        mark = "DAT " if ok else "TRUOT"
        print(f"  {mark} {name:<18} {fmt.format(value):>8}   (nguong {threshold})")

    truot = [o for o in outcomes if o.faithfulness < FAITHFULNESS_MIN or o.recall < RECALL_MIN]
    if truot:
        print(chr(10) + "Cau keo diem xuong:")
        for o in truot[:10]:
            print(
                f"  [{o.row.id}] recall={o.recall:.2f} faith={o.faithfulness:.2f} "
                f"{o.row.question[:60]}"
            )

    return all(ok for _, _, _, ok, _ in checks)


async def main() -> int:
    _cho_phep_in_tieng_viet()
    dataset = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATASET
    rows = load_dataset(dataset)
    if not rows:
        print(f"Khong co cau nao trong {dataset}.", file=sys.stderr)
        return EXIT_CHUA_CO_DU_LIEU

    if is_placeholder(rows):
        # KHONG tra ve 0. Mot bo eval chay tren du lieu mau roi bao "dat" con te hon
        # khong co eval: no cho ta niem tin ma no khong he kiem chung dieu gi.
        print(
            "qa.jsonl mới chỉ có dòng mẫu. Cần 50 câu VIẾT TAY từ tài liệu thật "
            "(xem docs/plan-thi-cong.md section 10).",
            file=sys.stderr,
        )
        return EXIT_CHUA_CO_DU_LIEU

    try:
        # Tuan tu, khong gather: chay song song lam so do do tre vo nghia, ma do tre
        # la mot trong ba nguong.
        outcomes = [await run_one(row) for row in rows]
        return EXIT_DAT if report(outcomes) else EXIT_TRUOT
    finally:
        await close_db()
        await close_redis()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
