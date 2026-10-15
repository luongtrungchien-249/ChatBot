import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from evals.corpus_contract import CorpusCheck
from evals.dataset_contract import split_for_id


def _load() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "ops" / "benchmark_rerank.py"
    spec = importlib.util.spec_from_file_location("benchmark_rerank_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


benchmark = _load()


@pytest.fixture(autouse=True)
def valid_corpus_preflight(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        benchmark, "check_corpus", AsyncMock(return_value=CorpusCheck("synthetic-hash", 3, 2))
    )
    for name in ("close_db", "close_http", "close_redis"):
        monkeypatch.setattr(benchmark, name, AsyncMock())


def test_quet_nguong_moi_005_va_xuat_duoc_json(capsys: object) -> None:
    rows = benchmark._quet_nguong([0.8, 0.6], [0.2, 0.4])

    assert len(rows) == 19
    assert rows[0]["threshold"] == 0.05
    assert rows[-1]["threshold"] == 0.95
    assert all(0.0 <= row["correct_recall"] <= 1.0 for row in rows)
    assert all(0.0 <= row["incorrect_rejected"] <= 1.0 for row in rows)


async def test_retrieval_loi_khong_duoc_giau_duoi_fallback(monkeypatch: Any) -> None:
    monkeypatch.setattr(benchmark, "vector_search", AsyncMock(side_effect=ConnectionError()))
    monkeypatch.setattr(benchmark, "lexical_search", AsyncMock(return_value=[]))
    with pytest.raises(RuntimeError, match="branch failed"):
        await benchmark.ung_vien("query")


@pytest.mark.parametrize("mode", ["dense", "sparse", "hybrid"])
async def test_retrieval_matrix_branches_are_isolated(monkeypatch: Any, mode: str) -> None:
    hit = SimpleNamespace(chunk_id=1, content="synthetic")
    dense = AsyncMock(return_value=[hit])
    sparse = AsyncMock(return_value=[hit])
    monkeypatch.setattr(benchmark, "vector_search", dense)
    monkeypatch.setattr(benchmark, "lexical_search", sparse)
    assert await benchmark.ung_vien("query", mode) == [(1, "synthetic")]
    assert dense.await_count == int(mode in {"dense", "hybrid"})
    assert sparse.await_count == int(mode in {"sparse", "hybrid"})


async def test_invalid_corpus_cannot_spend_provider_calls(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    identifier = next(f"q{i}" for i in range(20) if split_for_id(f"q{i}") == "development")
    dataset = tmp_path / "input.jsonl"
    dataset.write_text(
        json.dumps({"id": identifier, "question": "Synthetic", "expected_chunk_ids": ["1"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["benchmark", str(dataset)])
    monkeypatch.setattr(benchmark, "corpus_hash", AsyncMock(return_value="different"))
    monkeypatch.setattr(
        benchmark,
        "get_settings",
        lambda: SimpleNamespace(
            RERANK_PROVIDER="fake",
            RERANK_MODEL="fake",
            EMBEDDING_PROVIDER="fake",
        ),
    )
    candidates = AsyncMock()
    monkeypatch.setattr(benchmark, "ung_vien", candidates)
    assert await benchmark.main() == 1
    candidates.assert_not_awaited()


async def test_no_rerank_baseline_and_locked_test_do_not_calibrate(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    ids = [f"x{i}" for i in range(30) if split_for_id(f"x{i}") == "test"][:2]
    dataset, output = tmp_path / "input.jsonl", tmp_path / "output.json"
    dataset.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {"id": ids[0], "question": "Source question", "expected_chunk_ids": ["1"]},
                {
                    "id": ids[1],
                    "question": "Unavailable question",
                    "expected_chunk_ids": [],
                    "answerable": False,
                },
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["benchmark", str(dataset), "--confirm-test", "--no-rerank", "--output", str(output)],
    )
    settings = SimpleNamespace(
        RERANK_PROVIDER="fake",
        RERANK_MODEL="fake",
        RERANK_MIN_SCORE=0.5,
        EMBEDDING_PROVIDER="fake",
        EMBEDDING_MODEL="fake",
        EMBEDDING_DIM=1024,
    )
    monkeypatch.setattr(benchmark, "get_settings", lambda: settings)
    monkeypatch.setattr(benchmark, "corpus_hash", AsyncMock(return_value="synthetic-hash"))
    monkeypatch.setattr(benchmark, "ung_vien", AsyncMock(return_value=[(1, "synthetic")]))
    reranker = SimpleNamespace(diem_dang_tin=True, rerank=AsyncMock())
    monkeypatch.setattr(benchmark, "get_reranker", lambda: reranker)
    assert await benchmark.main() == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["threshold_tradeoffs"] == []
    assert report["no_answer_false_positive_rate"] == 1.0
    assert report["config"]["filter_policy"] == "none"
    assert not report["score_is_calibrated"]
    reranker.rerank.assert_not_awaited()


@pytest.mark.parametrize("failure", [False, True])
async def test_artifact_dem_ca_empty_error_va_no_answer(
    tmp_path: Path, monkeypatch: Any, failure: bool
) -> None:
    ids = [f"q{i}" for i in range(30) if split_for_id(f"q{i}") == "development"][:3]
    dataset = tmp_path / "data.jsonl"
    artifact = tmp_path / "report.json"
    rows = [
        {"id": ids[0], "question": "First source query", "expected_chunk_ids": ["1"]},
        {
            "id": ids[1],
            "question": "Second entirely different request",
            "expected_chunk_ids": ["2"],
        },
        {"id": ids[2], "question": "Unknown topic", "expected_chunk_ids": [], "answerable": False},
    ]
    dataset.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["benchmark", str(dataset), "--output", str(artifact)])
    settings = SimpleNamespace(
        RERANK_PROVIDER="fake",
        RERANK_MODEL="fake",
        RERANK_MIN_SCORE=0.5,
        EMBEDDING_PROVIDER="fake",
        EMBEDDING_MODEL="fake",
        EMBEDDING_DIM=1024,
    )
    monkeypatch.setattr(benchmark, "get_settings", lambda: settings)
    monkeypatch.setattr(benchmark, "corpus_hash", AsyncMock(return_value="synthetic-hash"))
    monkeypatch.setattr(
        benchmark,
        "ung_vien",
        AsyncMock(side_effect=[ConnectionError() if failure else [(1, "synthetic")], [], []]),
    )
    reranker = SimpleNamespace(
        diem_dang_tin=False, rerank=AsyncMock(return_value=[SimpleNamespace(index=0, score=0.9)])
    )
    monkeypatch.setattr(benchmark, "get_reranker", lambda: reranker)

    assert await benchmark.main() == int(failure)
    report = json.loads(artifact.read_text(encoding="utf-8"))
    assert report["questions"] == 3
    assert report["answerable_questions"] == 2
    assert report["mrr"] == report["ndcg_at_5"] == (0 if failure else 0.5)
    assert report["top1_accuracy"] == (0 if failure else 0.5)
    assert report["errors"] == int(failure)
    assert report["candidate_recall"] == (0 if failure else 0.5)
    assert report["candidate_answerable_measured"] == (1 if failure else 2)
    assert report["candidate_answerable_with_hits"] == (0 if failure else 1)
    assert report["recall_at_1"] == (0 if failure else 0.5)
    assert report["ranked_context_precision_at_5"] == (0 if failure else 0.5)
    assert report["no_answer_measured"] == 1
    assert report["no_answer_false_positive_rate"] is None
    assert report["dataset_sha256"]
    assert report["corpus_stable"]


@pytest.fixture
def synthetic_input(tmp_path: Path, monkeypatch: Any) -> tuple[Path, Path]:
    identifiers = [f"dev{i}" for i in range(30) if split_for_id(f"dev{i}") == "development"][:3]
    dataset, output = tmp_path / "input.jsonl", tmp_path / "report.json"
    dataset.write_text(
        "\n".join(
            json.dumps(
                {
                    "id": identifier,
                    "question": f"Synthetic request token{index}",
                    "expected_chunk_ids": [str(index + 1)] if index < 2 else [],
                    "answerable": index < 2,
                }
            )
            for index, identifier in enumerate(identifiers)
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        benchmark,
        "get_settings",
        lambda: SimpleNamespace(
            RERANK_PROVIDER="fake",
            RERANK_MODEL="fake",
            RERANK_API_KEY="synthetic-key",
            RERANK_MIN_SCORE=0.45,
            EMBEDDING_PROVIDER="fake",
            EMBEDDING_MODEL="fake",
            EMBEDDING_DIM=1024,
        ),
    )
    monkeypatch.setattr(benchmark, "corpus_hash", AsyncMock(return_value="synthetic-hash"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark",
            str(dataset),
            "--output",
            str(output),
            "--provider",
            "voyage",
            "--allow-provider-data",
        ],
    )
    return dataset, output


async def test_preflight_does_not_construct_or_call_any_provider(
    monkeypatch: Any,
    synthetic_input: tuple[Path, Path],
) -> None:
    dataset, output = synthetic_input
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark",
            str(dataset),
            "--preflight-only",
            "--provider",
            "voyage",
            "--output",
            str(output),
        ],
    )
    factory, candidates = AsyncMock(), AsyncMock()
    monkeypatch.setattr(benchmark, "build_reranker", factory)
    monkeypatch.setattr(benchmark, "ung_vien", candidates)
    assert await benchmark.main() == 0
    factory.assert_not_called()
    candidates.assert_not_awaited()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["provider_calls"] == 0 and report["questions"] == 3
    assert not report["release_gate_b_accepted"]
    assert "Synthetic request" not in output.read_text(encoding="utf-8")


async def test_paid_transfer_requires_explicit_cli_consent(
    monkeypatch: Any,
    synthetic_input: tuple[Path, Path],
) -> None:
    dataset, _ = synthetic_input
    monkeypatch.setattr(sys, "argv", ["benchmark", str(dataset), "--provider", "voyage"])
    candidates = AsyncMock()
    monkeypatch.setattr(benchmark, "ung_vien", candidates)
    assert await benchmark.main() == 1
    candidates.assert_not_awaited()


@pytest.mark.parametrize("uncertain", [False, True])
async def test_voyage_cost_override_budget_stop_and_metrics(
    monkeypatch: Any,
    synthetic_input: tuple[Path, Path],
    uncertain: bool,
) -> None:
    import httpx

    from llm import reranker
    from llm.reranker import VoyageReranker

    _, output = synthetic_input
    ranker = VoyageReranker(
        model="rerank-3-lite", api_key="synthetic", max_cost_usd=0.012 if uncertain else 0.10
    )
    client = AsyncMock()
    client.post.return_value = httpx.Response(
        200,
        json={
            "data": [{"index": 0, "relevance_score": 0.9}, {"index": 1, "relevance_score": 0.1}],
            "usage": {"total_tokens": 1000},
        },
    )
    if uncertain:
        client.post.side_effect = httpx.ReadTimeout("private-query")
    monkeypatch.setattr(reranker, "get_http", lambda: client)
    monkeypatch.setattr(reranker, "record_rerank", AsyncMock())
    from unittest.mock import Mock

    factory = Mock(return_value=ranker)
    monkeypatch.setattr(benchmark, "build_reranker", factory)
    candidates = AsyncMock(return_value=[(1, "synthetic-one"), (2, "synthetic-two")])
    monkeypatch.setattr(benchmark, "ung_vien", candidates)
    assert await benchmark.main() == int(uncertain)
    assert factory.call_args.args[0] == "voyage"
    assert factory.call_args.kwargs["model"] == "rerank-3-lite"
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["config"]["provider"] == "voyage"
    assert report["recall_at_5"] == (0 if uncertain else 1)
    assert report["candidate_recall"] == 1
    assert report["candidate_answerable_measured"] == 2
    assert report["candidate_answerable_with_hits"] == 2
    if uncertain:
        assert client.post.await_count == 1 and candidates.await_count == 2
        assert report["budget_skipped_questions"] == 1
        assert report["rerank_cost"]["estimated_usd"] is None
        assert report["rerank_cost"]["reserved_upper_bound_usd"] == pytest.approx(0.012)
    else:
        assert report["rerank_cost"]["estimated_usd"] == pytest.approx(0.00006)
        assert report["rerank_cost"]["reported_tokens"] == 3000
    assert "private" not in output.read_text(encoding="utf-8")


async def test_dataset_changes_are_not_hashed_as_the_measured_input(
    monkeypatch: Any,
    synthetic_input: tuple[Path, Path],
) -> None:
    dataset, output = synthetic_input
    monkeypatch.setattr(
        sys, "argv", ["benchmark", str(dataset), "--no-rerank", "--output", str(output)]
    )

    async def candidates(_: str) -> list[tuple[int, str]]:
        with dataset.open("a", encoding="utf-8") as stream:
            stream.write("\n")
        return [(1, "synthetic")]

    monkeypatch.setattr(benchmark, "ung_vien", candidates)
    assert await benchmark.main() == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["dataset_stable"] is False


@pytest.mark.parametrize("rerank_fails", [False, True])
async def test_candidate_recall_is_separate_from_rank_and_partial_annotation_recall(
    monkeypatch: Any,
    synthetic_input: tuple[Path, Path],
    rerank_fails: bool,
) -> None:
    dataset, output = synthetic_input
    identifiers = [f"dev{i}" for i in range(30) if split_for_id(f"dev{i}") == "development"][:3]
    rows = [
        {
            "id": identifiers[0],
            "question": "Synthetic first multi source request",
            "expected_chunk_ids": ["1", "2"],
        },
        {
            "id": identifiers[1],
            "question": "Different second single reference query",
            "expected_chunk_ids": ["3"],
        },
        {
            "id": identifiers[2],
            "question": "Unavailable third topic entirely",
            "expected_chunk_ids": [],
            "answerable": False,
        },
    ]
    dataset.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["benchmark", str(dataset), "--output", str(output)])
    ranker = SimpleNamespace(
        diem_dang_tin=False,
        rerank=AsyncMock(
            side_effect=TimeoutError("sensitive-body") if rerank_fails else None,
            return_value=[benchmark.RerankHit(0, 0.9), benchmark.RerankHit(1, 0.8)],
        ),
    )
    monkeypatch.setattr(benchmark, "get_reranker", lambda: ranker)
    monkeypatch.setattr(
        benchmark,
        "ung_vien",
        AsyncMock(return_value=[(1, "synthetic-one"), (99, "synthetic-other")]),
    )
    assert await benchmark.main() == int(rerank_fails)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema_version"] == 5
    assert report["candidate_recall"] == 0.25
    assert report["candidate_answerable_measured"] == 2
    assert report["candidate_answerable_with_hits"] == 1
    assert report["top1_accuracy"] == (0 if rerank_fails else 0.5)
    assert report["recall_at_1"] == (0 if rerank_fails else 0.25)
    assert report["ranked_context_precision_at_5"] == (0 if rerank_fails else 0.25)
    assert report["ranking_metrics_scope"] == "before_relevance_filter_annotation_ids_only"
    assert "sensitive-body" not in output.read_text(encoding="utf-8")


async def test_candidate_and_ranking_metrics_without_answerable_are_unknown(
    monkeypatch: Any,
    synthetic_input: tuple[Path, Path],
) -> None:
    dataset, output = synthetic_input
    identifier = next(f"dev{i}" for i in range(30) if split_for_id(f"dev{i}") == "development")
    dataset.write_text(
        json.dumps(
            {"id": identifier, "question": "Synthetic absent request", "answerable": False}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys, "argv", ["benchmark", str(dataset), "--no-rerank", "--output", str(output)]
    )
    monkeypatch.setattr(benchmark, "ung_vien", AsyncMock(return_value=[]))
    assert await benchmark.main() == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    for metric in ("candidate_recall", "recall_at_1", "ranked_context_precision_at_5"):
        assert report[metric] is None
    assert report["candidate_answerable_measured"] == 0


async def test_cached_latency_preserves_sub_millisecond_resolution(
    monkeypatch: Any,
    synthetic_input: tuple[Path, Path],
) -> None:
    from unittest.mock import Mock

    dataset, output = synthetic_input
    monkeypatch.setattr(
        sys, "argv", ["benchmark", str(dataset), "--no-rerank", "--output", str(output)]
    )
    monkeypatch.setattr(benchmark, "ung_vien", AsyncMock(return_value=[(1, "synthetic")]))
    monkeypatch.setattr(
        benchmark,
        "time",
        SimpleNamespace(perf_counter=Mock(side_effect=[0.0, 0.0001, 1.0, 1.0002, 2.0, 2.0003])),
    )
    assert await benchmark.main() == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["latency_clock"] == "perf_counter"
    assert report["latency_p50_ms"] == pytest.approx(0.2)
    assert report["latency_p95_ms"] == pytest.approx(0.3)


@pytest.mark.parametrize("status", [401, 403, 429])
async def test_terminal_provider_error_stops_before_more_retrieval_or_paid_calls(
    monkeypatch: Any, synthetic_input: tuple[Path, Path], status: int
) -> None:
    dataset, output = synthetic_input
    monkeypatch.setattr(sys, "argv", ["benchmark", str(dataset), "--output", str(output)])
    candidates = AsyncMock(return_value=[(1, "synthetic")])
    ranker = SimpleNamespace(
        diem_dang_tin=True,
        rerank=AsyncMock(side_effect=benchmark.RerankHttpError("voyage", status)),
    )
    monkeypatch.setattr(benchmark, "get_reranker", lambda: ranker)
    monkeypatch.setattr(benchmark, "ung_vien", candidates)
    assert await benchmark.main() == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert candidates.await_count == ranker.rerank.await_count == 1
    assert report["provider_http_errors"] == {f"voyage/{status}": 1}
    assert report["provider_stop_reason"] == f"voyage/{status}"
    assert report["provider_skipped_questions"] == 2
    assert report["budget_skipped_questions"] == 0
    assert report["candidate_recall"] == 0.5
    assert report["recall_at_5"] == 0
    assert not report["threshold_sweep_valid"]


async def test_pacing_is_excluded_from_provider_and_query_latency(
    monkeypatch: Any, synthetic_input: tuple[Path, Path]
) -> None:
    from unittest.mock import Mock

    dataset, output = synthetic_input
    monkeypatch.setattr(
        sys,
        "argv",
        ["benchmark", str(dataset), "--rerank-interval-s", "30", "--output", str(output)],
    )
    sleeper = AsyncMock()
    monkeypatch.setattr(benchmark, "asyncio", SimpleNamespace(sleep=sleeper))
    monkeypatch.setattr(benchmark, "time", SimpleNamespace(perf_counter=Mock(return_value=0.0)))
    monkeypatch.setattr(benchmark, "ung_vien", AsyncMock(return_value=[(1, "synthetic")]))
    monkeypatch.setattr(
        benchmark,
        "get_reranker",
        lambda: SimpleNamespace(
            diem_dang_tin=False, rerank=AsyncMock(return_value=[benchmark.RerankHit(0, 0.9)])
        ),
    )
    assert await benchmark.main() == 0
    assert sleeper.await_count == 2
    assert sleeper.await_args is not None
    assert sleeper.await_args.args == (30,)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["config"]["rerank_interval_s"] == 30
