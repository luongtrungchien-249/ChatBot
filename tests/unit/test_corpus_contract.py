import json
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from evals import corpus_contract as corpus
from evals.dataset_contract import GoldenRecord


def record(ids: tuple[str, ...] = ("1",), scope: str = "chung") -> GoldenRecord:
    return GoldenRecord(
        "synthetic",
        "Private question",
        "Private answer",
        ids,
        (),
        (),
        "single_chunk",
        True,
        scope,
        "",
    )


@pytest.mark.parametrize(
    "scope,ref_scope,latest,code",
    [
        ("chung", "chung", True, None),
        ("web:a", "chung", True, None),
        ("web:a", "web:a", True, None),
        ("web:a", "web:b", True, "scope_mismatch"),
        ("chung", "chung", False, "stale_version"),
        ("chung", None, True, "missing_chunk"),
    ],
)
def test_references_must_be_current_and_visible(
    scope: str,
    ref_scope: str | None,
    latest: bool,
    code: str | None,
) -> None:
    refs = {} if ref_scope is None else {"1": corpus.ChunkReference(ref_scope, latest)}
    result = corpus.check_references([record(scope=scope)], refs, "hash")
    assert result.exit_code == (1 if code else 0)
    assert [issue.code for issue in result.issues] == ([code] if code else [])
    assert "Private question" not in json.dumps(corpus.as_artifact(result))


def test_missing_annotation_differs_from_unanswerable_and_empty_dataset() -> None:
    assert corpus.check_references([record(())], {}, "hash").exit_code == 2
    assert (
        corpus.check_references([replace(record(()), answerable=False)], {}, "hash").exit_code == 0
    )
    assert corpus.check_references([], {}, "hash").exit_code == 2


async def test_snapshot_is_repeatable_read_readonly_metadata(monkeypatch: Any) -> None:
    conn = MagicMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [{"id": 1, "version": 2, "checksum": "test", "pham_vi": "chung", "chunks": 1}],
            [{"id": "1", "pham_vi": "chung", "la_ban_moi_nhat": True}],
        ]
    )
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    monkeypatch.setattr(corpus, "get_pool", AsyncMock(return_value=pool))
    result = await corpus.check_corpus([record(), record()])
    assert result.exit_code == 0 and len(result.fingerprint) == 64
    conn.transaction.assert_called_once_with(isolation="repeatable_read", readonly=True)
    assert conn.fetch.await_args_list[1].args[1] == ["1"]
    for call in conn.fetch.await_args_list:
        sql = call.args[0]
        assert sql.lstrip().startswith("SELECT")
        assert "content" not in sql and "embedding" not in sql and "title" not in sql


async def test_cli_errors_do_not_print_connection_secret(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    dataset = tmp_path / "data.jsonl"
    dataset.write_text(
        json.dumps({"id": "one", "question": "Synthetic", "expected_chunk_ids": ["1"]}),
        encoding="utf-8",
    )
    import sys

    monkeypatch.setattr(sys, "argv", ["preflight", str(dataset)])
    monkeypatch.setattr(
        corpus, "check_corpus", AsyncMock(side_effect=ConnectionError("private-password-dsn"))
    )
    monkeypatch.setattr(corpus, "close_db", AsyncMock())
    assert await corpus.main() == 1
    assert "private-password-dsn" not in capsys.readouterr().err
