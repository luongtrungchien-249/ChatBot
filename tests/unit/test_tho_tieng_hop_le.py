"""Bo do TIENG KHONG PHAI TIENG VIET — lop A cua docs/plan-sua-tho-ngang.md.

Nguoi dung cham tay mot bai va cho 0/0/0. May cho 32,71/45 tat dinh va 0,778/1,000
thuong. Khac biet nam o mot tieng: `mìmh`.

Hai test duoi day ghim hai dau cua bo do, va dau thu hai moi la dau kho: mot bo do bat
duoc `mìmh` nhung cung bao nham tren tho that thi te hon la khong co bo do nao, vi no
duoc dung lam BO LOC CUNG va lam he so phat NHAN 0.
"""

from pathlib import Path

import pytest

from tho.phan_thuong import phan_thuong
from tho.tu_vung import tieng_khong_hop_le

GOC = Path(__file__).resolve().parents[2]

#: Bai nguoi dung cham 0/0/0. Giu nguyen van, ke ca loi.
BAI_HONG = """Lời cảm ơn gửi tận mìmh
Ơn thờ cha mẹ nghĩa tình bao la
Con đi khắp nẻo đường xa
Vẫn mang trong dạ mái nhà quê hương"""


def test_bat_duoc_tieng_bia_ra() -> None:
    assert tieng_khong_hop_le(BAI_HONG) == ["mìmh"]


#: Tho that, GHIM THANG VAO TEP — vi `evals/corpus/*` bi .gitignore, nen test doc
#: corpus se xanh o may toi va do tren CI, hoac te hon la bi bo qua im lang. Nhung
#: tieng duoi day chon co chu: `gìn` `quen` `khuỷu` `nguyện` `giường` la cac ca de lam
#: hong bo tach am tiet nhat (phu am kep `gi`/`qu`, am dem, van ba nguyen am).
THO_THAT = """Trăm năm trong cõi người ta
Chữ tài chữ mệnh khéo là ghét nhau
Trải qua một cuộc bể dâu
Những điều trông thấy mà đau đớn lòng
Lạ gì bỉ sắc tư phong
Trời xanh quen thói má hồng đánh ghen
Gìn vàng giữ ngọc cho hay
Cho đành lòng kẻ chân mây cuối trời
Giường kia treo cũng hững hờ
Đàn kia gảy cũng ngẩn ngơ tiếng đàn
Khuỷu tay chống xuống nguyện cầu
Quê hương khuất bóng hoàng hôn"""


def test_khong_bao_tren_tho_that() -> None:
    """Bao nham phai la 0 TUYET DOI, khong phai 'thap'.

    Bo do nay nhan thuong voi 0 va loai han ban khoi vong chon. Mot lan bao nham la
    mot bai tot bi vut di khong lay lai duoc, nen nguong o day chat hon moi bo do khac
    trong du an (`cum_nghi_be` duoc phep 4,70% vi no chi XEP HANG).
    """
    assert tieng_khong_hop_le(THO_THAT) == []


def test_khong_bao_tren_toan_corpus() -> None:
    """Phep do that: 23.394 tieng. Bo qua khi khong co corpus — xem `THO_THAT`.

    Do 15/09/2026: Truyen Kieu 22.778 tieng, bat cu 392, tu tuyet 224, bao nham 0 het.
    """
    thu = GOC / "evals" / "corpus" / "tho"
    if not thu.is_dir():
        pytest.skip("khong co evals/corpus/tho — xem evals/corpus/README.md")
    for ten in ("truyen-kieu.txt", "bat-cu.txt", "tu-tuyet.txt"):
        if not (thu / ten).exists():
            continue
        goc = (thu / ten).read_text(encoding="utf-8")
        tho = "\n".join(
            d for d in goc.splitlines() if d.strip() and not d.lstrip().startswith("#")
        )
        assert tieng_khong_hop_le(tho) == [], ten


def test_con_so_khong_bi_coi_la_tieng_sai() -> None:
    """`1975` khong phai am tiet sai — no la mot thu khac, va chan no la qua tay."""
    assert tieng_khong_hop_le("Năm 1975 nước nhà thống nhất") == []


def test_thuong_ve_khong() -> None:
    """Truoc khi sua, dung bai nay duoc 0,778/1,000."""
    assert phan_thuong(BAI_HONG).tong == 0.0


def test_gin_van_duoc_voi_tin() -> None:
    """Loi im lang ma bo do tren tim ra: `gìn` bi boc `gi` con `n`, mat nguyen am."""
    from tho.luat import lay_van, van_nhau

    assert lay_van("gìn") == "in"
    assert van_nhau("gìn", "tin")
