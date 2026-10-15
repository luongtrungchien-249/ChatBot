import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "ops" / "baseline.py"
    spec = importlib.util.spec_from_file_location("ops_baseline", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


baseline = _load()


def test_render_on_dinh_va_khong_co_noi_dung_nhay_cam() -> None:
    snapshot = baseline.Baseline(
        commit="abc123",
        measured_at="2026-10-02T12:00:00+07:00",
        database_status="available",
        latest_migration="0013_kb_pham_vi.sql",
        counts={"documents": 2, "chunks": 10, "facts": 3, "messages": 8},
        routes=(
            {
                "route": "reply",
                "model": "gpt-4o-mini",
                "calls": 4,
                "errors": 0,
                "cost_usd": 0.001,
                "avg_latency_ms": 100,
                "p95_latency_ms": 150,
            },
        ),
        turns=(
            {
                "used_tools": False,
                "turns": 2,
                "p50_ms": 100,
                "p95_ms": 150,
                "max_ms": 160,
            },
        ),
        cache={"calls_with_cache": 1, "total_calls": 2, "avg_cached_tokens": 500},
        providers={"generation": "openai/gpt-4o-mini"},
        blockers=("Chua co auth.",),
    )

    report = baseline.render(snapshot)

    assert "abc123" in report
    assert "50.0%" in report
    assert "gpt-4o-mini" in report
    assert "API_KEY" not in report
    assert "DATABASE_URL" not in report


def test_database_error_chi_bao_loai_exception() -> None:
    snapshot = baseline.Baseline(
        commit="abc",
        measured_at="2026-10-02T12:00:00+07:00",
        database_status="unavailable (ConnectionError)",
        latest_migration="unavailable",
        counts={},
        routes=(),
        turns=(),
        cache={},
        providers={"rerank": "fake/fake"},
        blockers=("PostgreSQL khong san sang khi do baseline.",),
    )

    report = baseline.render(snapshot)

    assert "ConnectionError" in report
    assert "postgres://" not in report


def test_blocker_phan_anh_idor_phu_thuoc_e2() -> None:
    blockers = baseline._blockers("available", {"rerank": "fake/fake"})

    assert any("reverse proxy production" in item for item in blockers)
    assert all("chua duoc thi cong (E1)" not in item for item in blockers)


def test_junit_dem_pass_fail_skip_khong_in_ly_do(tmp_path: Path) -> None:
    path = tmp_path / "results.xml"
    path.write_text(
        '<testsuites><testsuite><testcase name="ok"/><testcase name="fail">'
        '<failure message="private failure"/></testcase><testcase name="setup">'
        '<error/></testcase><testcase name="embedding">'
        '<skipped message="EMBEDDING_PROVIDER fake; API_KEY private"/></testcase>'
        '<testcase name="db"><skipped message="Postgres down"/></testcase>'
        '<testcase name="queue"><skipped message="Redis down"/></testcase>'
        '<testcase name="platform"><skipped message="unsupported"/></testcase>'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    summary = baseline.read_junit(path)
    assert (summary.passed, summary.failed, summary.errors, summary.skipped) == (1, 1, 1, 4)
    assert summary.skip_groups == {"postgres": 1, "redis": 1, "embedding_or_key": 1, "other": 1}
    assert "private" not in repr(summary)


def test_junit_thieu_file_khong_duoc_gia_bao_cao_xanh(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        baseline.read_junit(tmp_path / "missing.xml")
