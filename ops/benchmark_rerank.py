"""So sanh nha cung cap rerank TREN TAI LIEU THAT cua ban, roi moi chot va chot nguong.

Vi sao khong the chot san: bang xep hang chung do tren tap tieng Anh; cai quyet dinh
la model co xep dung tren van ban cua CHINH ban khong. Va quan trong khong kem —
`RERANK_MIN_SCORE` phai do lai theo tung nha cung cap, vi hai cross-encoder khac nhau
tra ve hai THANG DIEM khac nhau. Bung nguong cua nha nay sang nha kia la doan mo.

Dau vao: mot tep JSONL, moi dong `{"question": "...", "expected_chunk_ids": ["12"]}`.
Dung duoc luon `evals/dataset/qa.jsonl`.

Cach chay:
    1. Nap tai lieu that:  uv run python -m main.cli ingest <tep>
    2. Viet cau hoi that:  moi dong mot cau + id chunk dung
    3. uv run python ops/benchmark_rerank.py evals/dataset/qa.jsonl

Script KHONG sua `.env`: `--provider`/`--model` chi ghi de trong process benchmark.
Chay moi cau hinh ra mot artifact moi, giu corpus/embedding/test split nguyen ven.

DO NAY TON TIEN THAT (rerank tinh theo so van ban).
"""

import argparse
import asyncio
import hashlib
import json
import math
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

from agents.domain.thread import ThreadScope  # noqa: E402
from config import get_settings  # noqa: E402
from evals.corpus_contract import check_corpus, corpus_fingerprint  # noqa: E402
from evals.dataset_contract import load_and_validate, split_for_id  # noqa: E402
from evals.metrics.latency import percentile  # noqa: E402
from evals.run_artifact import write_artifact  # noqa: E402
from infra.db import close_db  # noqa: E402
from infra.http import close_http  # noqa: E402
from infra.redis_client import close_redis  # noqa: E402
from knowledge.retrieve.fusion import reciprocal_rank_fusion  # noqa: E402
from knowledge.retrieve.search import (  # noqa: E402
    CANDIDATES_PER_SIDE,
    lexical_search,
    vector_search,
)
from knowledge.retrieve.service import FUSION_TOP  # noqa: E402
from llm.embedder import embedding_model_override  # noqa: E402
from llm.reranker import (  # noqa: E402
    RerankBudgetExceededError,
    RerankHit,
    RerankHttpError,
    VoyageReranker,
    build_reranker,
    get_reranker,
    is_placeholder_key,
)

TOP_K = 5

#: Do tren pham vi "chung" — dung pham vi ma moi nhom deu doc duoc.
_SCOPE = ThreadScope(platform="cli", thread_id="benchmark")


async def ung_vien(question: str, mode: str = "hybrid") -> list[tuple[int, str]]:
    """(chunk_id, content) sau buoc hop nhat, TRUOC rerank.

    Dung dung duong ma service.py chay, khong dung mot ban rut gon: do nguong tren
    mot tap ung vien khac voi tap that la do sai thu.
    """
    if mode not in {"dense", "sparse", "hybrid"}:
        raise ValueError("unknown retrieval mode")
    branches = []
    if mode in {"dense", "hybrid"}:
        branches.append(vector_search(_SCOPE, question, CANDIDATES_PER_SIDE))
    if mode in {"sparse", "hybrid"}:
        branches.append(lexical_search(_SCOPE, question, CANDIDATES_PER_SIDE))
    results = await asyncio.gather(*branches, return_exceptions=True)
    rows: dict[int, str] = {}
    rankings: list[list[int]] = []
    for hits in results:
        if isinstance(hits, BaseException) and not isinstance(hits, Exception):
            raise hits
        if isinstance(hits, BaseException):
            raise RuntimeError(
                "retrieval branch failed; benchmark must not hide degraded retrieval"
            ) from hits
        rankings.append([h.chunk_id for h in hits])
        rows.update({h.chunk_id: h.content for h in hits})
    fused = reciprocal_rank_fusion(rankings)[:FUSION_TOP]
    return [(r.chunk_id, rows[r.chunk_id]) for r in fused]


async def corpus_hash() -> str:
    return await corpus_fingerprint()


async def _run() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark fixed corpus/config; calls paid providers"
    )
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--confirm-test", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--retrieval-mode", choices=("dense", "sparse", "hybrid"), default="hybrid")
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument("--provider", choices=("fake", "cohere", "voyage"))
    parser.add_argument("--model")
    parser.add_argument("--embedding-model", help="Query-only override; do not re-embed corpus")
    parser.add_argument("--rerank-interval-s", type=float, default=0.0)
    parser.add_argument(
        "--preflight-only", action="store_true", help="Metadata only; no provider calls"
    )
    parser.add_argument(
        "--allow-provider-data",
        action="store_true",
        help="Explicitly authorize dataset questions/context to configured providers",
    )
    parser.add_argument(
        "--max-rerank-usd",
        type=float,
        default=0.10,
        help="Voyage-only per-run list-price reservation limit; excludes embedding",
    )
    args = parser.parse_args()
    if not math.isfinite(args.rerank_interval_s) or args.rerank_interval_s < 0:
        print("Rerank interval must be finite and nonnegative.", file=sys.stderr)
        return 1
    with embedding_model_override(args.embedding_model):
        return await _benchmark(args)


async def _benchmark(args: argparse.Namespace) -> int:
    dataset = args.dataset
    confirm_test = args.confirm_test
    output = args.output
    if not math.isfinite(args.max_rerank_usd) or args.max_rerank_usd <= 0:
        print("Rerank budget must be finite and positive.", file=sys.stderr)
        return 1
    if output and output.exists():
        print("Artifact already exists; use a new output path.", file=sys.stderr)
        return 1
    if not dataset.exists():
        print(f"Khong thay {dataset}", file=sys.stderr)
        return 1

    dataset_fingerprint = hashlib.sha256(dataset.read_bytes()).hexdigest()
    rows = [
        json.loads(dong)
        for dong in dataset.read_text(encoding="utf-8").splitlines()
        if dong.strip()
    ]
    validated = load_and_validate(dataset)
    if not rows:
        print("Dataset rong.", file=sys.stderr)
        return 1
    split = "test" if confirm_test else "development"
    rows = [row for row in rows if split_for_id(str(row.get("id", ""))) == split]
    if not rows:
        print(f"Khong co cau nao trong split {split}.", file=sys.stderr)
        return 2
    selected = [record for record in validated if split_for_id(record.id) == split]
    if any(
        record.scope != "chung" or (record.answerable and not record.expected_chunk_ids)
        for record in selected
    ):
        print(
            "Benchmark needs chunk annotations and an isolated fixture for non-public scope.",
            file=sys.stderr,
        )
        return 2
    answerability = {record.id: record.answerable for record in selected}
    settings = get_settings()
    provider = (args.provider or settings.RERANK_PROVIDER).lower()
    model = args.model or ("rerank-3-lite" if provider == "voyage" else settings.RERANK_MODEL)
    ranker = None
    if (
        not args.preflight_only
        and not args.allow_provider_data
        and (settings.EMBEDDING_PROVIDER != "fake" or (not args.no_rerank and provider != "fake"))
    ):
        print(
            "Provider data transfer requires --allow-provider-data after owner approval.",
            file=sys.stderr,
        )
        return 1
    if not args.no_rerank and not args.preflight_only:
        if args.provider or args.model or provider == "voyage":
            ranker = build_reranker(
                provider,
                model=model,
                api_key=settings.RERANK_API_KEY,
                max_cost_usd=args.max_rerank_usd,
            )
        else:
            ranker = get_reranker()
    fingerprint = await corpus_hash()
    checked = await check_corpus(selected)
    if checked.exit_code or checked.fingerprint != fingerprint:
        print(
            "Corpus references invalid/incomplete or corpus changed during preflight.",
            file=sys.stderr,
        )
        return checked.exit_code or 1
    if hashlib.sha256(dataset.read_bytes()).hexdigest() != dataset_fingerprint:
        print("Dataset changed during preflight; provider calls blocked.", file=sys.stderr)
        return 1
    if args.preflight_only:
        artifact = {
            "schema_version": 1,
            "kind": "benchmark_preflight_only",
            "dataset_sha256": dataset_fingerprint,
            "corpus_metadata_sha256": fingerprint,
            "split": split,
            "questions": len(rows),
            "chunk_references": checked.references,
            "corpus_issues": len(checked.issues),
            "provider": provider,
            "model": model,
            "api_key_placeholder": is_placeholder_key(settings.RERANK_API_KEY),
            "max_rerank_usd": args.max_rerank_usd,
            "provider_calls": 0,
            "release_gate_b_accepted": False,
        }
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            write_artifact(output, artifact)
        print(json.dumps(artifact, ensure_ascii=True))
        return 0
    score_calibrated = ranker is not None and ranker.diem_dang_tin
    print(f"Nha cung cap: {provider} / {model}")
    print(f"Nguong dang dat: RERANK_MIN_SCORE = {settings.RERANK_MIN_SCORE}")
    print(f"{len(rows)} cau hoi\n")
    print(f"Split: {split}\n")

    diem_dung: list[float] = []
    diem_sai: list[float] = []
    top1 = 0
    khong_co_ung_vien = 0
    latencies_ms: list[float] = []
    rerank_latencies_ms: list[float] = []
    candidate_sizes: list[int] = []
    errors = 0
    reciprocal_ranks: list[float] = []
    ndcg_scores: list[float] = []
    recall_scores: list[float] = []
    candidate_recall_sum = 0.0
    candidate_answerable_measured = 0
    candidate_answerable_with_hits = 0
    recall_at_1_sum = 0.0
    ranked_precision_sum = 0.0
    error_types: dict[str, int] = {}
    provider_http_errors: dict[str, int] = {}
    provider_stop_reason: str | None = None
    previous_rerank_started: float | None = None
    budget_stopped = False
    no_answer_false_positives = 0
    no_answer_total = 0
    no_answer_questions = sum(not answerability[str(row["id"])] for row in rows)
    answerable_total = len(rows) - no_answer_questions

    for row in rows:
        question = row["question"]
        mong_doi = {str(c) for c in row.get("expected_chunk_ids") or []}
        if ranker is not None and previous_rerank_started is not None and args.rerank_interval_s:
            remaining = args.rerank_interval_s - (time.perf_counter() - previous_rerank_started)
            if remaining > 0:
                print(f"Provider pacing: waiting {remaining:.1f}s.", flush=True)
                await asyncio.sleep(remaining)
        # perf_counter preserves sub-millisecond cached-query timings on Windows.
        started = time.perf_counter()
        try:
            candidates = (
                await ung_vien(question)
                if args.retrieval_mode == "hybrid"
                else await ung_vien(question, args.retrieval_mode)
            )
            candidate_sizes.append(len(candidates))
            if mong_doi:
                # Rerank cannot recover an annotation missing from its input.
                # Preserve this measurement even if the later rerank call fails.
                relevant_candidates = {str(chunk_id) for chunk_id, _ in candidates} & mong_doi
                candidate_recall_sum += len(relevant_candidates) / len(mong_doi)
                candidate_answerable_measured += 1
                candidate_answerable_with_hits += bool(relevant_candidates)
            hits = (
                [RerankHit(index=index, score=0.0) for index in range(min(TOP_K, len(candidates)))]
                if args.no_rerank
                else []
            )
            if ranker is not None and candidates:
                rerank_started = time.perf_counter()
                previous_rerank_started = rerank_started
                try:
                    hits = await ranker.rerank(question, [c for _, c in candidates], TOP_K)
                finally:
                    rerank_latencies_ms.append((time.perf_counter() - rerank_started) * 1000)
            if (
                len(hits) > min(TOP_K, len(candidates))
                or len({hit.index for hit in hits}) != len(hits)
                or any(
                    type(hit.index) is not int
                    or not 0 <= hit.index < len(candidates)
                    or not math.isfinite(hit.score)
                    for hit in hits
                )
            ):
                raise ValueError("invalid reranker hit")
        except Exception as error:
            errors += 1
            kind = type(error).__name__
            error_types[kind] = error_types.get(kind, 0) + 1
            if isinstance(error, RerankHttpError):
                status = f"{error.provider}/{error.status_code}"
                provider_http_errors[status] = provider_http_errors.get(status, 0) + 1
                if error.status_code in {401, 403, 429}:
                    provider_stop_reason = status
            if mong_doi:
                reciprocal_ranks.append(0.0)
                ndcg_scores.append(0.0)
                recall_scores.append(0.0)
            if isinstance(error, RerankBudgetExceededError):
                budget_stopped = True
                break
            if provider_stop_reason:
                print(f"Provider stopped benchmark: {provider_stop_reason}.", flush=True)
                break
            continue
        finally:
            latencies_ms.append((time.perf_counter() - started) * 1000)
        if not mong_doi:
            no_answer_total += 1
            if hits and (
                args.no_rerank
                or (
                    score_calibrated and any(hit.score >= settings.RERANK_MIN_SCORE for hit in hits)
                )
            ):
                no_answer_false_positives += 1
            continue
        if not hits:
            khong_co_ung_vien += 1
            reciprocal_ranks.append(0.0)
            ndcg_scores.append(0.0)
            recall_scores.append(0.0)
            continue

        ranked_ids = [str(candidates[hit.index][0]) for hit in hits]
        recall_scores.append(len(set(ranked_ids) & mong_doi) / len(mong_doi))
        recall_at_1_sum += int(ranked_ids[0] in mong_doi) / len(mong_doi)
        ranked_precision_sum += len(set(ranked_ids) & mong_doi) / len(ranked_ids)

        ranks = [index + 1 for index, chunk_id in enumerate(ranked_ids) if chunk_id in mong_doi]
        reciprocal_ranks.append(1 / min(ranks) if ranks else 0.0)
        dcg = sum(1 / math.log2(rank + 1) for rank in ranks)
        ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(len(mong_doi), TOP_K) + 1))
        ndcg_scores.append(dcg / ideal if ideal else 0.0)

        if str(candidates[hits[0].index][0]) in mong_doi:
            top1 += 1

        for h in hits:
            chunk_id = str(candidates[h.index][0])
            (diem_dung if chunk_id in mong_doi else diem_sai).append(h.score)

    skipped = len(rows) - len(latencies_ms) if budget_stopped or provider_stop_reason else 0
    budget_skipped = skipped if budget_stopped else 0
    provider_skipped = skipped if provider_stop_reason else 0
    if skipped:
        for row in rows[len(latencies_ms) :]:
            if answerability[str(row["id"])]:
                reciprocal_ranks.append(0.0)
                ndcg_scores.append(0.0)
                recall_scores.append(0.0)
        print(f"Stopped benchmark; {skipped} questions not attempted.")
    if not diem_dung:
        print("Khong cau nao tra ve chunk dung. Da nap tai lieu chua?", file=sys.stderr)

    dung_min = min(diem_dung) if diem_dung else 0.0
    dung_tb = sum(diem_dung) / len(diem_dung) if diem_dung else 0.0
    sai_max = max(diem_sai) if diem_sai else 0.0

    print(f"  top-1 dung        {top1}/{answerable_total} answerable")
    print(
        f"  diem chunk DUNG   {dung_min:.3f} - {max(diem_dung, default=0):.3f}  (tb {dung_tb:.3f})"
    )
    print(f"  diem chunk SAI    {min(diem_sai) if diem_sai else 0:.3f} - {sai_max:.3f}")
    print(f"  khoang an toan    {dung_min - sai_max:+.3f}")
    if khong_co_ung_vien:
        print(f"  {khong_co_ung_vien} cau khong co ung vien nao")

    try:
        corpus_stable = fingerprint == await corpus_hash()
    except Exception:
        corpus_stable = False
    try:
        dataset_stable = hashlib.sha256(dataset.read_bytes()).hexdigest() == dataset_fingerprint
    except OSError:
        dataset_stable = False
    sweep_valid = (
        score_calibrated
        and not confirm_test
        and not errors
        and not budget_stopped
        and corpus_stable
        and dataset_stable
        and bool(diem_dung)
    )
    tradeoffs = _quet_nguong(diem_dung, diem_sai) if sweep_valid else []

    print()
    if confirm_test:
        print("  Locked test split: no threshold sweep or recommendation.")
    elif not score_calibrated:
        print("  Score du phong khong duoc hieu chuan; KHONG de xuat threshold.")
    elif not sweep_valid:
        print("  Incomplete/unstable run: no threshold sweep or recommendation.")
    elif diem_dung and dung_min > sai_max:
        de_xuat = (dung_min + sai_max) / 2
        print(f"  RERANK_MIN_SCORE de xuat: {de_xuat:.2f}")
        print("  (diem giua khoang an toan — moi huong sai deu co gia nhu nhau o day:")
        print("   cao qua thi bo sot tai lieu co that, thap qua thi dua rac vao prompt)")
    else:
        print("  KHONG co nguong nao tach duoc chunk dung khoi chunk sai.")
        print("  Doi nha cung cap rerank, hoac xem lai cach cat chunk truoc.")
    if output:
        settings_payload = {
            "provider": provider,
            "model": model,
            "top_k": TOP_K,
            "candidates_per_side": CANDIDATES_PER_SIDE,
            "fusion_top": FUSION_TOP,
            "embedding_provider": settings.EMBEDDING_PROVIDER,
            "embedding_model": args.embedding_model or settings.EMBEDDING_MODEL,
            "embedding_override_scope": "query_only_corpus_unchanged",
            "embedding_dim": settings.EMBEDDING_DIM,
            "threshold": settings.RERANK_MIN_SCORE,
            "distance_threshold": getattr(settings, "RAG_MAX_DISTANCE", None),
            "retrieval_mode": args.retrieval_mode,
            "rerank_enabled": not args.no_rerank,
            "max_rerank_usd": args.max_rerank_usd,
            "rerank_interval_s": args.rerank_interval_s,
            "threshold_source": "existing_config_not_validated_for_selected_provider",
            "filter_policy": "none"
            if args.no_rerank
            else ("score" if score_calibrated else "distance_not_measured"),
        }
        artifact = {
            "schema_version": 5,
            "dataset": str(dataset),
            "split": split,
            "dataset_sha256": dataset_fingerprint,
            "dataset_stable": dataset_stable,
            "corpus_metadata_sha256": fingerprint,
            "corpus_stable": corpus_stable,
            "config": settings_payload,
            "config_hash": hashlib.sha256(
                json.dumps(settings_payload, sort_keys=True).encode()
            ).hexdigest(),
            "questions": len(rows),
            "answerable_questions": answerable_total,
            "no_answer_questions": no_answer_questions,
            "no_answer_measured": no_answer_total,
            "top1_correct": top1,
            "top1_accuracy": top1 / answerable_total if answerable_total else None,
            "recall_at_1": recall_at_1_sum / answerable_total if answerable_total else None,
            "recall_at_5": sum(recall_scores) / len(recall_scores) if recall_scores else None,
            "candidate_recall": candidate_recall_sum / answerable_total
            if answerable_total
            else None,
            "candidate_answerable_measured": candidate_answerable_measured,
            "candidate_answerable_with_hits": candidate_answerable_with_hits,
            "ranked_context_precision_at_5": ranked_precision_sum / answerable_total
            if answerable_total
            else None,
            "ranking_metrics_scope": "before_relevance_filter_annotation_ids_only",
            "latency_clock": "perf_counter",
            "mrr": (sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else None),
            "ndcg_at_5": sum(ndcg_scores) / len(ndcg_scores) if ndcg_scores else None,
            "correct_scores": diem_dung,
            "incorrect_scores": diem_sai,
            "candidate_size_avg": (
                sum(candidate_sizes) / len(candidate_sizes) if candidate_sizes else 0.0
            ),
            "latency_p50_ms": percentile(latencies_ms, 0.50),
            "latency_p95_ms": percentile(latencies_ms, 0.95),
            "rerank_latency_p50_ms": percentile(rerank_latencies_ms, 0.50)
            if rerank_latencies_ms
            else None,
            "rerank_latency_p95_ms": percentile(rerank_latencies_ms, 0.95)
            if rerank_latencies_ms
            else None,
            "errors": errors,
            "error_types": error_types,
            "provider_http_errors": provider_http_errors,
            "provider_stop_reason": provider_stop_reason,
            "provider_skipped_questions": provider_skipped,
            "budget_skipped_questions": budget_skipped,
            "timeouts_or_errors_rate": errors / len(rows),
            "no_answer_false_positive_rate": (
                no_answer_false_positives / no_answer_total
                if no_answer_total and (score_calibrated or args.no_rerank)
                else None
            ),
            "estimated_cost_per_1000_queries_usd": None,
            "rerank_cost": voyage_cost_artifact(ranker, len(latencies_ms)),
            "threshold_tradeoffs": tradeoffs,
            "threshold_sweep_valid": sweep_valid,
            "release_gate_b_accepted": False,
            "score_is_calibrated": score_calibrated,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        write_artifact(output, artifact)
        print(f"Artifact: {output}")
    return 0 if diem_dung and not errors and corpus_stable and dataset_stable else 1


def voyage_cost_artifact(ranker: object, questions: int) -> dict[str, object] | None:
    if not isinstance(ranker, VoyageReranker):
        return None
    measured = ranker.calls == ranker.measured_calls
    return {
        "calls": ranker.calls,
        "measured_calls": ranker.measured_calls,
        "reported_tokens": ranker.total_tokens,
        "list_price_per_million_tokens_usd": ranker.price_per_million,
        "estimated_usd": ranker.estimated_cost_usd if measured else None,
        "reserved_upper_bound_usd": ranker.reserved_cost_usd,
        "estimated_per_1000_attempted_queries_usd": ranker.estimated_cost_usd / questions * 1000
        if measured and questions
        else None,
        "scope": "rerank_only_excludes_embedding_and_account_credits",
    }


async def main() -> int:
    try:
        return await _run()
    except Exception as error:
        # No raw provider response, query, document or credential in console.
        print(f"Benchmark failed ({type(error).__name__}).", file=sys.stderr)
        return 1
    finally:
        await close_http()
        await close_db()
        await close_redis()


def _quet_nguong(diem_dung: list[float], diem_sai: list[float]) -> list[dict[str, float]]:
    """Bang danh doi, cho truong hop hai phan bo CHONG NHAU.

    Khi chung tach roi thi chon nguong la viec de — lay diem giua. Khi chung chong
    nhau thi khong co dap an dung, chi co danh doi, va nguoi chon phai NHIN THAY no:

      giu duoc  = ti le chunk DUNG vuot nguong  -> mat cai nay la bo sot tai lieu that
      chan duoc = ti le chunk SAI bi loai       -> mat cai nay la dua rac vao prompt

    Khong tu chon ho: hai huong sai co gia khac nhau tuy viec, va do la quyet dinh
    cua chu du an chu khong phai cua mot cong thuc.
    """
    print()
    print("  Quet nguong (khi hai phan bo chong nhau, khong co dap an dung — chi co danh doi):")
    print()
    print(f"    {'nguong':>8}  {'giu duoc chunk DUNG':>21}  {'chan duoc chunk SAI':>21}")
    tradeoffs: list[dict[str, float]] = []
    for step in range(5, 96, 5):
        nguong = step / 100
        giu = sum(1 for d in diem_dung if d >= nguong) / len(diem_dung) if diem_dung else 0.0
        chan = sum(1 for d in diem_sai if d < nguong) / len(diem_sai) if diem_sai else 1.0
        print(f"    {nguong:>8.2f}  {giu:>20.1%}  {chan:>20.1%}")
        tradeoffs.append({"threshold": nguong, "correct_recall": giu, "incorrect_rejected": chan})
    return tradeoffs


def _option(name: str) -> Path | None:
    try:
        index = sys.argv.index(name)
    except ValueError:
        return None
    if index + 1 >= len(sys.argv):
        raise ValueError(f"{name} can mot duong dan")
    return Path(sys.argv[index + 1])


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
