"""Chong trung va mau thuan cho fact L3.

Khong co buoc nay thi sau vai tuan bang day cac bien the cua cung mot cau: "Nam lam
backend", "Nam lam ve backend", "Nam phu trach backend" — ba dong, mot y, va ca ba
deu di vao prompt moi luot.

Nguong lay tu ARCHITECTURE.md section 6.2. Chung la NGUONG, khong phai chan ly: do
tren du lieu that roi chinh, dung suy doan.
"""

import math
from dataclasses import dataclass
from typing import TypeAlias

#: Tren nguong nay thi hai fact duoc coi la NOI VE CUNG MOT DIEU (trung y hoac mau
#: thuan). Do bang ops/calibrate_dedupe.py ngay 06/09/2026 voi
#: text-embedding-3-large @ 1024 chieu:
#:
#:     can BAT (trung y + mau thuan)         0,736 - 0,958
#:     can BO QUA (khac fact, cung mot nguoi) 0,276 - 0,524
#:     khoang an toan                         (0,524 ; 0,736)
#:
#: KHONG lay diem giua khoang do, vi hai huong sai khong ngang nhau:
#:   - Nguong cao qua -> bang co ban trung. Phien, ton cho trong prompt, khong mat gi.
#:   - Nguong thap qua -> fact moi REVOKE fact cu. Mat thong tin, va im lang.
#: Nen lech len sat can tren, chi chua mot bien an nho.
#:
#: ARCHITECTURE.md va master-plan deu ghi "cosine > 0,9". Con so do viet TRUOC khi
#: co phep do nao va KHONG dung voi model nay — 0,9 thi ngay ca hai cach dien dat
#: cua cung mot y (0,736) cung khong bi coi la trung.
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
    """Mau thuan voi mot fact dang co — revoke cai cu roi chen cai moi.

    Vi du: "Nam lam o cong ty A" roi sau do "Nam lam o cong ty B". Giu ca hai thi
    prompt chua hai su that loai tru nhau va model se chon bua mot cai.
    """

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
    if not existing:
        return Insert()

    best_id, best_content, best_score = "", "", -1.0
    for fact_id, content, vector in existing:
        score = cosine(new_vector, vector)
        if score > best_score:
            best_id, best_content, best_score = fact_id, content, score

    if best_score < DUPLICATE_THRESHOLD:
        return Insert()

    # Rat giong nhau. Cung mot cau chu (bo khoang trang, khong phan biet hoa thuong)
    # thi chac chan la trung; khac chu thi coi la BAN CAP NHAT va thay the.
    #
    # Khong hoi model o day: them mot lan goi model vao duong ghi fact de phan biet
    # "trung y" voi "mau thuan" la doi do tre va tien lay mot phan biet ma hau qua
    # hai ben gan nhu nhau — ca hai deu ket thuc bang MOT fact dung trong bang.
    if _normalize(new_content) == _normalize(best_content):
        return Skip(existing_id=best_id, similarity=best_score)
    return Replace(existing_id=best_id, similarity=best_score)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())
