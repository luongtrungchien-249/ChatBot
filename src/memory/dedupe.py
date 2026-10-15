"""Conservative deduplication: similarity is not proof of contradiction.

Only normalized identical text is suppressed. Different paraphrases, preferences,
and employment statements are preserved; an explicit scoped replacement is the
only write path that revokes an older fact. No LLM or threshold can silently turn
an additive fact into a destructive update.
"""

import math
from dataclasses import dataclass
from typing import TypeAlias

#: Historical candidate threshold retained for the calibration scripts. It is
#: never authorization to replace a fact; decide() does not use this threshold.
DUPLICATE_THRESHOLD = 0.70

#: Nguong cho lenh `quen <noi dung>`. THAP hon han, va co chu dich.
#:
#: Nguoi dung go bang loi cua ho, khong phai nguyen van fact. Do duoc:
#:     "cho lam cua toi" | "Nam lam o cong ty A"     0,589
#:     "lich hop"        | "Nhom hop thu 3 hang tuan" 0,569
#:     "cach xung ho"    | "Goi toi la anh Nam"       0,488
#:     "nghe nghiep"     | "Nam lam backend Node.js"  0,354
#:
#: Voi 0,85 nhu tai lieu ghi thi KHONG cai nao khop — lenh `quen` im lang khong lam
#: gi, va nguoi dung tuong da xoa xong. Do la loai hong te nhat trong mot tinh nang
#: ve quyen rieng tu.
#:
#: Rong o day an toan vi ket qua chi de HOI XAC NHAN, khong xoa gi ngay. Lop chan
#: that su la buoc xac nhan, khong phai con so nay.
FORGET_THRESHOLD = 0.30

#: Nhieu nhat bay nhieu ung vien dua ra hoi. Dai hon thi nguoi dung khong doc, va
#: mot danh sach khong ai doc thi buoc xac nhan mat tac dung.
FORGET_MAX_CANDIDATES = 5


@dataclass(frozen=True, slots=True)
class Insert:
    """Fact moi, khong dung toi cai nao dang co."""


@dataclass(frozen=True, slots=True)
class Skip:
    """Trung y voi mot fact dang co — bo qua fact moi."""

    existing_id: str
    similarity: float


@dataclass(frozen=True, slots=True)
class Replace:
    """Explicit replacement intent, never inferred by decide() from cosine."""

    existing_id: str
    similarity: float


Decision: TypeAlias = Insert | Skip | Replace


def cosine(a: list[float], b: list[float]) -> float:
    """Hai vector deu da chuan hoa (norm = 1) nen tich vo huong CHINH LA cosine.

    Van chia cho norm de ham nay dung duoc ca voi vector chua chuan hoa — mot ngay
    nao do doi nha cung cap embedding, khong phai ai cung tra ve vector don vi.
    """
    if len(a) != len(b):
        raise ValueError(f"so chieu lech: {len(a)} vs {len(b)}")
    dot = math.fsum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(math.fsum(x * x for x in a))
    norm_b = math.sqrt(math.fsum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def decide(
    new_content: str,
    new_vector: list[float],
    existing: list[tuple[str, str, list[float]]],
) -> Decision:
    """`existing`: (id, content, vector) cua cac fact CUNG subject, chua bi revoke.

    Chi so sanh trong cung subject: "Nam lam backend" va "Lan lam backend" gan nhau
    ve ngu nghia nhung noi ve hai nguoi khac nhau. Loc theo subject truoc khi goi
    ham nay la mot phan cua hop dong.
    """
    normalized = _normalize(new_content)
    for fact_id, content, vector in existing:
        if normalized == _normalize(content):
            return Skip(existing_id=fact_id, similarity=cosine(new_vector, vector))
    return Insert()


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())
