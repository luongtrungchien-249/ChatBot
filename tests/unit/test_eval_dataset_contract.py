import hashlib
import json
from pathlib import Path

import pytest

from evals.dataset_contract import (
    annotation_deficits,
    check_review,
    coverage_deficits,
    load_and_validate,
    review_template,
    split_for_id,
)


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_split_on_dinh_va_chi_co_hai_tap() -> None:
    assert split_for_id("leave-001") == split_for_id("leave-001")
    assert split_for_id("leave-001") in {"development", "test"}


def test_schema_moi_va_tuong_thich_schema_cu(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    _write(
        path,
        [
            {
                "id": "a",
                "question": "Câu hỏi có nguồn?",
                "expected_answer": "Đáp án",
                "required_claims": ["ý bắt buộc"],
                "category": "single_chunk",
                "answerable": True,
                "scope": "chung",
            },
            {"id": "b", "question": "Ngoài kho?", "answer": "", "loai": "ngoai_kho"},
        ],
    )

    records = load_and_validate(path)

    assert records[0].expected_answer == "Đáp án"
    assert records[0].required_claims == ("ý bắt buộc",)
    assert records[1].answerable is False


def test_id_trung_bi_tu_choi(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    _write(path, [{"id": "a", "question": "Một"}, {"id": "a", "question": "Hai"}])

    with pytest.raises(ValueError, match="id trung"):
        load_and_validate(path)


def test_dataset_hien_tai_khong_con_placeholder() -> None:
    path = Path(__file__).resolve().parents[2] / "evals" / "dataset" / "golden.jsonl"
    records = load_and_validate(path)

    assert records
    assert all("VI DU" not in record.question for record in records)


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", 123),
        ("question", None),
        ("answerable", "false"),
        ("required_claims", "a claim"),
        ("expected_chunk_ids", [123]),
        ("category", "misspelled_category"),
    ],
)
def test_schema_tu_choi_ep_kieu_im_lang(tmp_path: Path, field: str, value: object) -> None:
    path = tmp_path / "bad.jsonl"
    _write(path, [{"id": "a", "question": "Một câu hỏi", field: value}])
    with pytest.raises(ValueError, match=field):
        load_and_validate(path)


def test_60_cau_mot_loai_khong_duoc_coi_la_du_coverage(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    _write(
        path,
        [
            {
                "id": f"q{i}",
                "question": f"Question with distinct identifier word{i}",
                "category": "single_chunk",
            }
            for i in range(60)
        ],
    )
    deficits = coverage_deficits(load_and_validate(path))
    assert "single_chunk" not in deficits
    assert deficits["cross_language"] == deficits["unanswerable"] == 10
    assert deficits["scope_version_adversarial"] == 5


@pytest.mark.parametrize(
    "extra",
    [
        {"expected_chunk_ids": ["1", "1"]},
        {"answerable": False, "expected_chunk_ids": ["1"]},
        {"scope": ""},
    ],
)
def test_contradictory_or_duplicate_annotations_rejected(
    tmp_path: Path, extra: dict[str, object]
) -> None:
    path = tmp_path / "bad.jsonl"
    _write(path, [{"id": "one", "question": "Synthetic question", **extra}])
    with pytest.raises(ValueError):
        load_and_validate(path)


def test_review_template_never_attests_human_work(tmp_path: Path) -> None:
    path = tmp_path / "input.jsonl"
    _write(path, [{"id": "a", "question": "Synthetic private question", "answer": "secret"}])
    records = load_and_validate(path)
    content = review_template(path, records, "opaque-author")
    manifest = tmp_path / "review.json"
    manifest.write_text(json.dumps(content), encoding="utf-8")
    assert content["reviewed_ids"] == [] and content["reviewer_id_sha256"] is None
    assert "private" not in manifest.read_text(encoding="utf-8")
    assert "secret" not in manifest.read_text(encoding="utf-8")
    assert check_review(path, records, manifest)["status"] == "incomplete"
    assert check_review(path, records, None)["status"] == "missing"


def test_review_requires_distinct_ids_complete_snapshot_and_matching_lock(tmp_path: Path) -> None:
    path = tmp_path / "input.jsonl"
    _write(path, [{"id": "a", "question": "Synthetic query"}])
    records = load_and_validate(path)
    content = review_template(path, records, "opaque-author")
    content.update(
        reviewer_id_sha256=hashlib.sha256(b"opaque-reviewer").hexdigest(),
        reviewed_ids=["a"],
        source_checked=True,
        labels_before_model_results=True,
        test_locked=True,
        locked_eval_config_sha256="a" * 64,
    )
    manifest = tmp_path / "review.json"
    manifest.write_text(json.dumps(content), encoding="utf-8")
    checked = check_review(path, records, manifest, "a" * 64)
    assert checked["attested"] and not checked["independence_verified_by_tool"]
    with pytest.raises(ValueError, match="configuration"):
        check_review(path, records, manifest, "b" * 64)
    content["reviewer_id_sha256"] = content["author_id_sha256"]
    manifest.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(ValueError, match="distinct"):
        check_review(path, records, manifest)
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="snapshot"):
        check_review(path, records, manifest)


@pytest.mark.parametrize("ids", [["a", "a"], ["unrelated"]])
def test_review_rejects_duplicate_or_unknown_ids(tmp_path: Path, ids: list[str]) -> None:
    path = tmp_path / "input.jsonl"
    _write(path, [{"id": "a", "question": "Synthetic query"}])
    records = load_and_validate(path)
    content = review_template(path, records, "opaque-author")
    content["reviewed_ids"] = ids
    manifest = tmp_path / "review.json"
    manifest.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed IDs"):
        check_review(path, records, manifest)


def test_valid_schema_with_incomplete_annotations_is_not_ready(tmp_path: Path) -> None:
    path = tmp_path / "input.jsonl"
    _write(path, [{"id": "a", "question": "Synthetic query", "category": "single_chunk"}])
    assert annotation_deficits(load_and_validate(path)) == {
        "answerable_without_expected_answer": 1,
        "answerable_without_chunk_annotation": 1,
    }


@pytest.mark.parametrize(
    "fields",
    [
        {"category": "unanswerable", "answerable": True},
        {"required_claims": ["same", "same"]},
        {"required_claims": ["same"], "forbidden_claims": ["same"]},
    ],
)
def test_contradictory_claim_or_answerability_annotations_rejected(
    tmp_path: Path,
    fields: dict[str, object],
) -> None:
    path = tmp_path / "input.jsonl"
    _write(path, [{"id": "a", "question": "Synthetic query", **fields}])
    with pytest.raises(ValueError):
        load_and_validate(path)
