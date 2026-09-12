"""Giai doan 1: chon CHU VAN truoc, viet cau sau.

VI SAO: do 11/09/2026 cho thay bao model "dung ep van" khong co tac dung — bon lan,
bon cach, cung mot tran (`ngon ngu` 44%, `sang tao` 36%). Lan thu tu noi DUNG dieu can
noi ("Y -> hinh anh -> chu -> roi moi van") kem vi du phan dien lay tu chinh bai bot
vua lam hong. Van 44%.

Ly do la CO CHE SINH, khong phai chi dan. Model viet trai sang phai. Khi no di toi
tieng thu 6 cua cau luc, ca cau da viet xong — no khong con tu do chon NGHIA, chi con
chon mot chu vua VAN. Nen no nhet "mot da", "tron vuong".

Bao no "nghi y truoc" khong doi duoc dieu do, vi toi luc cham vi tri van thi y da can
cho xoay. Phai DOI THU TU SINH:

    giai doan 1   chi chon chu, chua viet cau   -> chu duoc chon VI NGHIA
    giai doan 2   viet cau quanh nhung chu do   -> khong con phai nhet

O giai doan 1 model chi co MOT viec. Khong bi suc ep phai vua du tieng, vua hop cau
truoc, vua van. Va ta KIEM DUOC ket qua cua no bang code truoc khi ton luot thu hai.

CAU TRUC VAN cua mot bai luc bat 4 cau, doi chieu tu chinh Truyen Kieu:

    Tram nam trong coi nguoi TA          c1[6]  \\
    Chu tai chu menh kheo LA ghet NHAU   c2[6]  /  nhom 1
                                         c2[8]  \\
    Trai qua mot cuoc be DAU             c3[6]   |  nhom 2
    Nhung dieu trong thay ma DAU don long c4[6]  /

Nhom 1 hai chu, nhom 2 BA chu — vi c3[6] vua hiep van voi c2[8] vua voi c4[6].
"""

import re
from dataclasses import dataclass

from .luat import van_nhau

#: So lan thu lai giai doan 1. Mot lan: neu model khong chon noi chu hiep van thi lan
#: hai cung kho hon, va moi lan la mot lan cong do tre.
SO_LAN_THU = 1

HUONG_DAN = """\
Nhiệm vụ: chọn CHỮ HIỆP VẦN cho một bài lục bát. CHƯA viết câu thơ.

Cần hai nhóm:
  nhóm 1 — 2 chữ hiệp vần với nhau
  nhóm 2 — 3 chữ hiệp vần với nhau

Yêu cầu với TỪNG chữ:
- phải là một từ CÓ NGHĨA, dùng được trong câu, không phải chữ ghép cho đủ vần;
- phải gợi được hình ảnh hoặc cảm xúc thuộc chủ đề được giao;
- hai nhóm nên khác vần nhau.

Hiệp vần nghĩa là phần sau phụ âm đầu giống nhau: "ta / là / hoa" hiệp vần;
"sen / hồng" thì không.

Định dạng bắt buộc, đúng hai dòng, không thêm gì khác:

1|<chữ>, <chữ>
2|<chữ>, <chữ>, <chữ>
"""


@dataclass(frozen=True, slots=True)
class BoVan:
    """Chu van cho bai luc bat 4 cau."""

    #: c1[6], c2[6]
    nhom1: tuple[str, str]
    #: c2[8], c3[6], c4[6]
    nhom2: tuple[str, str, str]


_DONG = re.compile(r"^\s*([12])\s*\|\s*(.+)$", re.MULTILINE)


def doc_bo_van(raw: str) -> BoVan | None:
    """Doc phan hoi giai doan 1 va KIEM bang `van_nhau()`.

    Tra None khi khong doc duoc HOAC khi cac chu khong thuc su hiep van. Kiem o day
    la mien phi, va no chan mot bo van hong TRUOC khi ton luot goi thu hai.
    """
    thay: dict[str, list[str]] = {}
    for khop in _DONG.finditer(raw):
        # Strip HAI CHIEU va lap: model hay tra ve " ta ." — bo dau cau xong van
        # con khoang trang, roi chu do bi loai vi tuong la cum nhieu tu.
        chu = [c.strip(" .,;\"'") for c in khop.group(2).split(",")]
        thay[khop.group(1)] = [c for c in chu if c and " " not in c]

    n1, n2 = thay.get("1", []), thay.get("2", [])
    if len(n1) < 2 or len(n2) < 3:
        return None
    n1, n2 = n1[:2], n2[:3]

    # Moi chu trong cung mot nhom phai hiep van voi chu dau nhom.
    if not van_nhau(n1[0], n1[1]):
        return None
    if not all(van_nhau(n2[0], c) for c in n2[1:]):
        return None
    return BoVan(nhom1=(n1[0], n1[1]), nhom2=(n2[0], n2[1], n2[2]))


def yeu_cau_chon_van(chu_de: str) -> str:
    return (
        f"Chủ đề: {chu_de}" if chu_de else "Chủ đề: tự chọn một điều gần gũi, cụ thể."
    )


def yeu_cau_viet_bai(bo: BoVan, chu_de: str) -> str:
    """Giai doan 2. Chi RO chu nao dat o vi tri nao — khong de model tu suy."""
    a, b = bo.nhom1
    c, d, e = bo.nhom2
    de = f"về {chu_de}" if chu_de else ""
    return (
        f"Viết một bài lục bát 4 câu {de}, dùng ĐÚNG các chữ sau ở ĐÚNG vị trí vần:\n\n"
        f"  câu 1, tiếng thứ 6  →  {a}\n"
        f"  câu 2, tiếng thứ 6  →  {b}\n"
        f"  câu 2, tiếng thứ 8  →  {c}\n"
        f"  câu 3, tiếng thứ 6  →  {d}\n"
        f"  câu 4, tiếng thứ 6  →  {e}\n\n"
        "Những chữ này đã được chọn vì nghĩa và vì hợp chủ đề — hãy dựng câu quanh "
        "chúng, đừng đổi chúng. Phần còn lại của mỗi câu do bạn viết, miễn đủ số "
        "tiếng (câu lẻ 6, câu chẵn 8).\n\n"
        "Chỉ xuất bài thơ."
    )
