import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from .test_deployment_operations import _load

with patch.object(sys, "path", [str(Path(__file__).resolve().parents[2] / "ops"), *sys.path]):
    smoke = _load("restore_smoke")


def test_smoke_accepts_only_archive_failure_and_reports_production_false(
    tmp_path: Path, monkeypatch: Any,
) -> None:
    monkeypatch.setattr(smoke, "ROOT", tmp_path)
    monkeypatch.setattr(smoke, "create_legacy_fixture", lambda path: path.write_bytes(b"PGDMPtest"))
    modes: list[bool] = []

    def execute(archive: Path, *, legacy_vn_tsv: bool = False) -> dict[str, Any]:
        modes.append(legacy_vn_tsv)
        if not legacy_vn_tsv:
            raise smoke.ArchiveRestoreError("expected archive failure")
        return {"table_counts": {"kb_chunk": 1}, "restore_verified": True}

    monkeypatch.setattr(smoke, "execute_drill", execute)
    result = smoke.run_smoke()
    assert result["production_gate_accepted"] is False and modes == [False, True]


def test_cleanup_or_startup_failure_cannot_be_misreported_as_expected_archive_failure(
    tmp_path: Path, monkeypatch: Any,
) -> None:
    monkeypatch.setattr(smoke, "ROOT", tmp_path)
    monkeypatch.setattr(smoke, "create_legacy_fixture", lambda path: path.write_bytes(b"PGDMPtest"))
    calls: list[bool] = []

    def execute(archive: Path, *, legacy_vn_tsv: bool = False) -> None:
        calls.append(legacy_vn_tsv)
        raise RuntimeError("cleanup could not be verified")

    monkeypatch.setattr(smoke, "execute_drill", execute)
    with pytest.raises(RuntimeError, match="cleanup"):
        smoke.run_smoke()
    assert calls == [False]
