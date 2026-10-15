import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from evals.human_review import CANDIDATE_CATEGORIES, SUPPORTED_FORMS, prepare_round


def tool() -> Any:
    spec = importlib.util.spec_from_file_location(
        "poetry_pool_cli_test", Path(__file__).resolve().parents[2] / "ops/prepare_poetry_pool.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_fixture(tmp_path: Path) -> Path:
    poems = (
        "Công cha như núi Thái Sơn\nNghĩa mẹ như nước trong nguồn chảy ra\n"
        "Một lòng thờ mẹ kính cha\nCho tròn chữ hiếu mới là đạo con",
        "Tiếng suối trong như tiếng hát xa\nTrăng lồng cổ thụ bóng lồng hoa\n"
        "Cảnh khuya như vẽ người chưa ngủ\nChưa ngủ vì lo nỗi nước nhà",
        "Bước tới Đèo Ngang bóng xế tà\nCỏ cây chen đá lá chen hoa\n"
        "Lom khom dưới núi tiều vài chú\nLác đác bên sông chợ mấy nhà\n"
        "Nhớ nước đau lòng con quốc quốc\nThương nhà mỏi miệng cái gia gia\n"
        "Dừng chân đứng lại trời non nước\nMột mảnh tình riêng ta với ta",
    )
    rows = []
    for poem in poems:
        for word in ("như", "tựa", "từng", "vẫn"):
            lines = poem.splitlines()
            words = lines[0].split()
            words[2] = word
            lines[0] = " ".join(words)
            rows.append({"tho": "\n".join(lines), "may": {"ngon_ngu": 3}})
    path = tmp_path / "synthetic-fixtures.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


def test_pool_is_balanced_distinct_unreviewed_and_sources_unchanged(tmp_path: Path) -> None:
    module, source = tool(), source_fixture(tmp_path)
    before = source.read_bytes()
    rows = module.build_pool(module.read_sources(source, tmp_path / "missing"))
    assert source.read_bytes() == before
    assert len(rows) == len({row["tho"] for row in rows}) == 72
    assert Counter(row["category"] for row in rows) == dict.fromkeys(CANDIDATE_CATEGORIES, 12)
    assert Counter(row["form"] for row in rows) == dict.fromkeys(SUPPORTED_FORMS, 24)
    assert all(row["review_status"] == "proposed_unreviewed" for row in rows)
    assert all(not row["provenance"]["rights_independently_verified"] for row in rows)
    invalid = [row for row in rows if row["category"] == "meaningful_invalid_candidate"]
    assert all(row["law_check"]["error_count"] > 0 for row in invalid)
    assert all(row["may"] is None for row in rows if row["category"] != "lawful_quality_candidate")
    assert all(
        row["provenance"]["kind"] == "synthetic_adversarial"
        for row in rows
        if row["category"] != "lawful_quality_candidate"
    )
    pool = tmp_path / "pool.jsonl"
    pool.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    target = tmp_path / "round"
    assert (
        prepare_round(
            pool,
            target,
            "fixture-round",
            category_minimums=dict.fromkeys(CANDIDATE_CATEGORIES, 10),
            form_minimums=dict.fromkeys(SUPPORTED_FORMS, 10),
        )
        == 72
    )
    blind = json.loads((target / "blind.json").read_text(encoding="utf-8"))
    assert all(set(row) == {"id", "tho"} for row in blind)
    assert all(row["id"] == hashlib.sha256(row["tho"].encode()).hexdigest() for row in blind)
    private = json.loads((target / "private.json").read_text(encoding="utf-8"))
    assert private["balance_checked"] and not private["category_labels_human_reviewed"]
    assert all("provenance" in row for row in private["records"].values())
    with pytest.raises(FileExistsError):
        prepare_round(pool, target, "fixture-round")


def test_missing_local_reference_forms_fail_without_fabrication(tmp_path: Path) -> None:
    module = tool()
    with pytest.raises(ValueError, match="all three forms"):
        module.build_pool([])
    with pytest.raises(ValueError, match="60 total"):
        module.build_pool([], 9)
