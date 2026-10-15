"""Immutable blinded poetry rounds and independently identified judgments."""

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

DIMENSIONS = ("ngon_ngu", "y_nghia", "hinh_anh", "cam_xuc", "sang_tao", "san_sang")
CANDIDATE_CATEGORIES = (
    "lawful_quality_candidate",
    "lawful_incoherent_candidate",
    "meaningful_invalid_candidate",
    "broken_word_candidate",
    "copy_candidate",
    "repetition_candidate",
)
SUPPORTED_FORMS = ("luc_bat", "that_ngon_tu_tuyet", "that_ngon_bat_cu")
RUBRIC_VERSION = 1
RUBRIC = {
    "ngon_ngu": (
        "Nhiều từ không hiểu được hoặc ghép sai; ví dụ từ bị cắt chỉ để đủ tiếng.",
        "Hiểu được vài câu nhưng nhiều chỗ gượng; phải đoán cách nối từ.",
        "Phần lớn tự nhiên, còn một vài đảo từ/đệm từ; đọc lại mới trôi.",
        "Từ chính xác, câu trôi; chỉ cần sửa nhẹ một chỗ để đọc thành tiếng.",
        "Toàn bài tự nhiên và có giọng riêng; không thấy chữ nào chỉ để ép vần.",
    ),
    "y_nghia": (
        "Không tìm ra mạch; các câu như danh sách sự vật không liên hệ.",
        "Có chủ đề nhưng quan hệ sự việc mâu thuẫn/đứt; phải tự thêm nhiều ý.",
        "Mạch cơ bản rõ, có đoạn lặp hoặc chuyển ý đột ngột.",
        "Mỗi câu góp vào mạch; mở và kết nối được, chỉ một chỗ hơi mơ hồ.",
        "Mạch liền và có chuyển biến; ví dụ hình ảnh cuối làm sáng ý mở đầu.",
    ),
    "hinh_anh": (
        "Chỉ phát biểu trừu tượng, không dựng được cảnh cụ thể.",
        "Có cảnh nhưng toàn khuôn quen như 'trăng buồn'; ít chi tiết giác quan.",
        "Một hình ảnh rõ, những câu khác còn kể tên đồ vật.",
        "Nhiều chi tiết nhìn/nghe/cảm được và cùng phục vụ chủ đề.",
        "Hình ảnh cụ thể, mới và tương tác; ví dụ một âm thanh làm cảnh đổi nghĩa.",
    ),
    "cam_xuc": (
        "Chỉ gọi tên cảm xúc ('rất buồn') mà không tạo trải nghiệm.",
        "Có giọng cảm xúc nhưng áp đặt; các câu chưa làm nó đáng tin.",
        "Một khoảnh khắc có sức gợi, phần còn lại còn kể lể.",
        "Cảm xúc nhất quán, được gợi bằng hành động/chi tiết hơn là tuyên bố.",
        "Cảm xúc có chiều sâu và thay đổi có căn cứ; kết còn dư âm khi đọc lại.",
    ),
    "sang_tao": (
        "Nhận ra chép/gần chép hoặc chỉ nối sáo ngữ; đổi vài từ chưa tạo ý mới.",
        "Khuôn rất quen, có một chi tiết riêng nhưng chưa phát triển.",
        "Có cách nhìn riêng ở một chỗ, chưa xuyên suốt toàn bài.",
        "Nhiều kết hợp mới có nghĩa; chi tiết mới vẫn phù hợp với mạch.",
        "Cách nhìn/giọng/cấu trúc riêng xuyên suốt, bất ngờ mà thuyết phục.",
    ),
    "san_sang": (
        "Phải viết lại: sai khung nghiêm trọng, khó hiểu, chép hoặc có nội dung không phù hợp.",
        "Cần sửa nhiều câu; ví dụ mạch có nhưng nhiều câu gượng và lỗi thể thơ.",
        "Có thể dùng sau một lượt biên tập; còn lỗi ảnh hưởng trải nghiệm.",
        "Chỉ cần chỉnh nhẹ một câu/từ; phần lớn có thể gửi người dùng.",
        "Có thể gửi toàn bài ngay cho yêu cầu/thể đã nêu, không cần sửa nội dung hay luật.",
    ),
}


def canonical_poem(poem: str) -> str:
    return "\n".join(
        " ".join(line.split())
        for line in unicodedata.normalize("NFC", poem).splitlines()
        if line.strip()
    )


def prepare_round(
    source: Path,
    target: Path,
    round_id: str,
    *,
    category_minimums: dict[str, int] | None = None,
    form_minimums: dict[str, int] | None = None,
) -> int:
    rows = [
        json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("tho"), str):
            raise ValueError("poem must be a string")
        poem = canonical_poem(row["tho"])
        if not poem:
            raise ValueError("missing poem")
        key = hashlib.sha256(poem.encode()).hexdigest()
        normalized = {**row, "tho": poem}
        if key in unique and any(
            unique[key].get(name) != normalized.get(name) for name in ("category", "form")
        ):
            raise ValueError("duplicate poem has conflicting category/form metadata")
        unique.setdefault(key, normalized)
    if len(unique) < 60:
        raise ValueError(f"need 60 distinct poems, found {len(unique)}")
    categories = Counter(row.get("category") for row in unique.values())
    forms = Counter(row.get("form") for row in unique.values())
    for counts, policy, valid, name in (
        (categories, category_minimums, CANDIDATE_CATEGORIES, "category"),
        (forms, form_minimums, SUPPORTED_FORMS, "form"),
    ):
        if policy is None:
            continue
        if any(
            key not in valid or not isinstance(value, int) or isinstance(value, bool) or value < 1
            for key, value in policy.items()
        ):
            raise ValueError(f"invalid {name} balance policy")
        if any(key not in valid for key in counts):
            raise ValueError(f"missing/invalid {name} metadata")
        if any(counts[key] < minimum for key, minimum in policy.items()):
            raise ValueError(f"insufficient {name} balance")
    # Creating a new directory refuses to overwrite any previous round.
    target.mkdir(parents=True, exist_ok=False)
    ordered = sorted(
        unique, key=lambda key: hashlib.sha256(f"{round_id}:{key}".encode()).hexdigest()
    )
    blind = [{"id": key, "tho": unique[key]["tho"]} for key in ordered]
    private = {
        "round_id": round_id,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "records": unique,
        "rubric_version": RUBRIC_VERSION,
        "category_counts": {str(key): value for key, value in categories.items()},
        "form_counts": {str(key): value for key, value in forms.items()},
        "balance_checked": category_minimums is not None or form_minimums is not None,
        "category_labels_human_reviewed": False,
    }
    (target / "blind.json").write_text(
        json.dumps(blind, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (target / "private.json").write_text(
        json.dumps(private, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (target / "rubric.json").write_text(
        json.dumps(
            {"version": RUBRIC_VERSION, "scale": [1, 5], "anchors": RUBRIC},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return len(blind)


def validate_judgments(
    records: list[dict[str, Any]], expected_ids: set[str]
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for record in records:
        key = str(record["id"])
        if key not in expected_ids or key in result:
            raise ValueError("unknown or duplicate poem ID")
        scores = record["scores"]
        if not isinstance(scores, dict):
            raise ValueError("scores must be an object")
        if set(scores) != set(DIMENSIONS):
            raise ValueError("all six dimensions are required")
        if any(isinstance(value, bool) for value in scores.values()):
            raise ValueError("scores cannot be booleans")
        if any(not isinstance(value, (int, float)) for value in scores.values()):
            raise ValueError("scores must be numeric")
        normalized = {name: float(scores[name]) for name in DIMENSIONS}
        if any(not math.isfinite(value) or not 1 <= value <= 5 for value in normalized.values()):
            raise ValueError("scores must be finite values between 1 and 5")
        result[key] = normalized
    if set(result) != expected_ids:
        raise ValueError("incomplete review")
    return result


def reviewer_identity(records: list[dict[str, Any]]) -> str:
    """Require explicit human declarations; this does not verify a person's identity."""
    if not records or any(record.get("reviewer_kind") != "human" for record in records):
        raise ValueError("human reviewer declaration required; agent/missing kinds are not humans")
    identifiers = {record.get("reviewer_id") for record in records}
    if len(identifiers) != 1:
        raise ValueError("mixed reviewer identities")
    identifier = next(iter(identifiers))
    if not isinstance(identifier, str) or re.fullmatch(r"[0-9a-f]{64}", identifier) is None:
        raise ValueError("reviewer identity must be an opaque SHA-256")
    return identifier


def agreement(
    first: dict[str, dict[str, float]], second: dict[str, dict[str, float]]
) -> dict[str, float]:
    if not first or set(first) != set(second):
        raise ValueError("reviewers must score the same nonempty set")
    return {
        name: sum(abs(first[key][name] - second[key][name]) for key in first) / len(first)
        for name in DIMENSIONS
    }


def spearman(first: list[float], second: list[float]) -> float | None:
    """Average ranks for ties; constant/insufficient samples are unmeasurable."""
    if len(first) != len(second):
        raise ValueError("paired samples must have equal length")
    if any(not math.isfinite(x) for x in first + second):
        raise ValueError("samples must be finite")
    if len(first) < 3:
        return None

    def ranks(values: list[float]) -> list[float]:
        ordered = sorted(range(len(values)), key=values.__getitem__)
        result = [0.0] * len(values)
        index = 0
        while index < len(ordered):
            end = index + 1
            while end < len(ordered) and values[ordered[end]] == values[ordered[index]]:
                end += 1
            for pos in range(index, end):
                result[ordered[pos]] = (index + end - 1) / 2 + 1
            index = end
        return result

    a, b = ranks(first), ranks(second)
    mean_a, mean_b = sum(a) / len(a), sum(b) / len(b)
    numerator = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    denominator = math.sqrt(sum((x - mean_a) ** 2 for x in a) * sum((y - mean_b) ** 2 for y in b))
    return numerator / denominator if denominator else None


def calibration_report(
    first: dict[str, dict[str, float]],
    second: dict[str, dict[str, float]],
    machine: dict[str, Any],
    repeated: dict[str, Any] | None = None,
    *,
    same_judge_config_attested: bool = False,
    categories: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Analyze supplied judgments offline; never invent missing machine scores.

    Machine dimensions can use different scales than human 1..5: Spearman is
    rank-based. Repeated runs must use the SAME judge/config/scale externally.
    This report is evidence, not automatic authorization of a quality gate.
    """
    disagreements = agreement(first, second)
    expected = set(first)
    if set(machine) != expected or (repeated is not None and set(repeated) != expected):
        raise ValueError("machine runs must cover exactly the reviewed IDs")

    def score(data: Any, dimension: str) -> float | None:
        value = data.get(dimension) if isinstance(data, dict) else None
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            return None
        return float(value) if math.isfinite(value) else None

    dimensions: dict[str, Any] = {}
    for dimension in DIMENSIONS:
        keys = sorted(key for key in expected if score(machine[key], dimension) is not None)
        judges = [float(machine[key][dimension]) for key in keys]
        human = [(first[key][dimension] + second[key][dimension]) / 2 for key in keys]
        correlation = spearman(judges, human)
        repeat_keys = [
            key
            for key in keys
            if repeated is not None and score(repeated[key], dimension) is not None
        ]
        repeat_correlation = None
        stability = None
        if repeated is not None:
            repeat_correlation = spearman(
                [float(repeated[key][dimension]) for key in repeat_keys],
                [(first[key][dimension] + second[key][dimension]) / 2 for key in repeat_keys],
            )
            stability = spearman(
                [float(machine[key][dimension]) for key in repeat_keys],
                [float(repeated[key][dimension]) for key in repeat_keys],
            )
        if correlation is None:
            decision = "unmeasurable"
        elif correlation < 0.3 or (repeat_correlation is not None and repeat_correlation < 0.3):
            decision = "exclude"
        elif (
            correlation > 0.5
            and repeat_correlation is not None
            and repeat_correlation > 0.5
            and stability is not None
            and stability > 0.5
            and len(keys) == len(repeat_keys) == len(expected)
            and len(expected) >= 60
            and same_judge_config_attested
        ):
            # Agreement/stability still require a reviewer-approved threshold.
            decision = "soft_guard_candidate_requires_stability_review"
        else:
            decision = "reference_only"
        dimensions[dimension] = {
            "n": len(keys),
            "missing_or_invalid": len(expected) - len(keys),
            "spearman_machine_human_mean": correlation,
            "spearman_machine_reviewer_one": spearman(judges, [first[k][dimension] for k in keys]),
            "spearman_machine_reviewer_two": spearman(judges, [second[k][dimension] for k in keys]),
            "repeat_n": len(repeat_keys),
            "repeat_spearman_human_mean": repeat_correlation,
            "repeat_rank_stability": stability,
            "repeat_missing_or_invalid": len(expected) - len(repeat_keys),
            "decision": decision,
        }
    invalid = sum(
        not isinstance(machine[key], dict)
        or any(score(machine[key], d) is None for d in DIMENSIONS)
        for key in expected
    )
    report: dict[str, Any] = {
        "reviewed_poems": len(expected),
        "mean_absolute_disagreement": disagreements,
        "human_spearman": {
            dimension: spearman(
                [first[key][dimension] for key in sorted(expected)],
                [second[key][dimension] for key in sorted(expected)],
            )
            for dimension in DIMENSIONS
        },
        "machine_incomplete_or_invalid_records": invalid,
        "machine_incomplete_or_invalid_rate": invalid / len(expected),
        "dimensions": dimensions,
        "hard_gate_authorized": False,
        "same_judge_config_attested": same_judge_config_attested,
        "minimum_samples_for_soft_guard_candidate": 60,
    }
    if categories is not None:
        if set(categories) != expected:
            raise ValueError("category metadata must cover exactly reviewed IDs")
        report["proposed_category_analysis"] = {}
        for category in sorted(set(categories.values())):
            category_ids = {key for key in expected if categories[key] == category}
            report["proposed_category_analysis"][category] = calibration_report(
                {key: first[key] for key in category_ids},
                {key: second[key] for key in category_ids},
                {key: machine[key] for key in category_ids},
                {key: repeated[key] for key in category_ids} if repeated is not None else None,
                same_judge_config_attested=same_judge_config_attested,
            )
        report["category_labels_human_reviewed"] = False
    return report
