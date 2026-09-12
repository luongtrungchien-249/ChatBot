"""Luat tho tieng Viet, cuong che bang CODE chu khong bang cau chu trong prompt.

Vi sao la mot goi rieng chu khong nam trong `agents/prompt/`: day la mot bo LUAT
THUAN — khong I/O, khong goi model, khong doc config. No khong thuoc ve tang nao ca,
va moi tang deu goi duoc no.

Bai hoc dan toi thiet ke nay, lay tu docs/plan-truy-hoi-xuyen-ngon-ngu.md: mot luat
viet trong prompt duoc tuan thu khoang 50-95%, khong bao gio 100%. Lop cau
"lam sao / bao lau" bi danh o ca BA tang cau chu ma van chi giu duoc 3/6, cho toi khi
them mot CHAN CUNG trong code thi moi len 6/6.

Dem tieng trong tho Viet la bai toan TAT DINH TUYET DOI — tieng Viet viet roi, moi
tieng cach nhau boi khoang trang. Bo qua mon qua do roi di cau mong prompt tuan thu
la lap lai dung sai lam da mat ba ngay de sua.
"""

from .cham_diem import DiemTatDinh, bang_diem, cham_tat_dinh
from .luat import (
    Loi,
    ThanhDieu,
    chu_thich_thanh,
    danh_so_tieng,
    kiem_luc_bat,
    kiem_nhip,
    kiem_that_ngon_tu_tuyet,
    la_bang,
    lay_van,
    tach_tieng,
    van_nhau,
)

__all__ = [
    "DiemTatDinh",
    "Loi",
    "ThanhDieu",
    "bang_diem",
    "cham_tat_dinh",
    "chu_thich_thanh",
    "danh_so_tieng",
    "kiem_luc_bat",
    "kiem_nhip",
    "kiem_that_ngon_tu_tuyet",
    "la_bang",
    "lay_van",
    "tach_tieng",
    "van_nhau",
]
