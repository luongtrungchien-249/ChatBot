from typing import Any

import pytest

from .test_deployment_operations import restore

TOC = """; Archive TOC
2; 3079 100 EXTENSION - vector
3; 3079 101 EXTENSION - unaccent
8; 1255 103 FUNCTION public vn_tsv(text) bot
9; 1255 104 FUNCTION public vn_tsv(integer) bot
10; 1259 105 TABLE public kb_chunk bot
11; 0 105 TABLE DATA public kb_chunk bot
"""


def test_legacy_selection_preserves_other_function_and_every_table_data_entry() -> None:
    extensions, main, identifier = restore.legacy_restore_lists(TOC)
    assert identifier == 8 and "FUNCTION" not in extensions
    assert "; 8;" in main and "9; 1255 104 FUNCTION public vn_tsv(integer)" in main
    assert "TABLE DATA public kb_chunk" in main and "TABLE public kb_chunk" in main


@pytest.mark.parametrize("toc", [
    TOC.replace("public vn_tsv(text)", "other vn_tsv(text)"),
    TOC + "12; 1255 200 FUNCTION public vn_tsv(text) other\n",
    TOC + "12; 3079 201 EXTENSION - unexpected_extension\n",
    TOC + "8; 1259 202 TABLE public duplicate_id bot\n",
    TOC.replace("3; 3079 101 EXTENSION - unaccent\n", ""),
    TOC + "not a TOC entry\n",
])
def test_ambiguous_or_unknown_legacy_archive_fails_before_bootstrap(toc: str) -> None:
    calls: list[list[str]] = []

    def run(command: list[str], _: str | None) -> str:
        calls.append(command)
        return toc

    with pytest.raises(ValueError):
        restore.restore_archive(run, legacy_vn_tsv=True)
    assert calls == [["pg_restore", "--list", "/backup.dump"]]


def test_legacy_bootstrap_order_never_restores_old_function_definition() -> None:
    calls: list[tuple[list[str], str | None]] = []

    def run(command: list[str], payload: str | None) -> str:
        calls.append((command, payload))
        return TOC if "--list" in command else ""

    evidence = restore.restore_archive(run, legacy_vn_tsv=True)
    assert evidence["schema_migration_not_marked"]
    programs = [command[0] for command, _ in calls]
    assert programs == ["pg_restore", "tee", "tee", "pg_restore", "psql", "pg_restore"]
    assert "--single-transaction" in calls[-1][0]
    assert "public.unaccent" in (calls[-2][1] or "")
    assert "schema_migration" not in (calls[-2][1] or "")


def test_normal_restore_never_silently_enables_legacy_override() -> None:
    calls: list[Any] = []

    def run(command: list[str], _: str | None) -> str:
        calls.append(command)
        return ""

    evidence = restore.restore_archive(run)
    assert evidence == {"legacy_vn_tsv_override": False}
    assert len(calls) == 1 and "--list" not in calls[0] and "--single-transaction" in calls[0]
