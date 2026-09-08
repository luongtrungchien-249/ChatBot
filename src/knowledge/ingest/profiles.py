"""Ho so tai lieu: mo ta CAU TRUC va CHO HONG cua mot dang tep cu the.

Vi sao can khai niem nay. Buoc cat chunk uu tien tieu de markdown ('#'), va cach do
dung cho .md va .docx (extract.py doi 'Heading 1' thanh '#'). Nhung PDF tra ve van
ban THUAN — khong co ky tu nao nhu vay. Do duoc tren cookbook trong lakehouse/: 0/108
chunk co duong dan tieu de, tuc cot `section` NULL toan bo, va trich dan chi noi duoc
"trong quyen sach" chu khong noi duoc MUC NAO.

Nhieu tai lieu van co cau truc, chi la khong viet bang markdown: mot mau lap di lap
lai ma mat nguoi doc ra ngay. Ho so la cho de KHAI mau do mot lan, thay vi nhet kien
thuc ve tung tai lieu vao loi chunker.

Hai luat giu cho no khong thanh cho chua rac:

  1. NGUONG NHAN DIEN. Duoi `toi_thieu` lan khop thi coi nhu KHONG khop. Mot mau tinh
     co xuat hien vai lan trong tai lieu khac khong duoc phep doi cach cat cua ca tep.
  2. KHOP HAY KHONG DEU GHI LOG. Khong khop -> hanh vi y het truoc day. Neu mot ngay
     nao do chunk ra ket qua la, dong log noi ngay ho so nao da dong vao.

`sua_ky_tu` la thu rieng cua tung tep, khong phai luat chung: xem `_PHAN_SO` ben duoi.
"""

import re
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class HoSo:
    ten: str

    #: Mau TIEU DE lap lai. Group(1) phai la ten muc — no di thang vao cot `section`.
    moc: re.Pattern[str]

    #: Bang sua ky tu bi trich xuat sai. Rong = khong sua gi.
    #: Khong phai luat chung: chi ap khi CHINH ho so nay duoc nhan dien.
    sua_ky_tu: dict[str, str] = field(default_factory=dict)

    #: Duoi nguong nay coi nhu khong khop. Xem luat 1 o docstring.
    toi_thieu: int = 5

    def so_lan_khop(self, text: str) -> int:
        return len(self.moc.findall(text))


# --------------------------------------------------------------------------------
# Ho so 1: sach nau an kieu Slashdot
# --------------------------------------------------------------------------------
# Moi cong thuc mo dau bang ten mon roi mot dong tagline kieu Slashdot:
#
#     Kristin's Poor Man's Goulash
#     from the el-cheapo dept.
#
# Do duoc tren The_Open_Source_Cookbook_v0.4.pdf: 60 lan, rat deu. Cat theo moc nay
# cho ra 1,00 mon/chunk — khong chunk nao lan sang mon khac.

_MOC_COOKBOOK = re.compile(r"\n([^\n]{3,80})\nfrom the [^\n]{2,60} dept\.")

# Bang phan so.
#
# Tep nhung font `MrsEavesFractions`, va bang ToUnicode cua font do khai glyph phan so
# CHINH LA chu cai: <47> <4a> -> <0047>, tuc G,H,I,J -> "G","H","I","J". ToUnicode la
# nguon chan ly cua moi trinh trich xuat, nen KHONG cong cu nao doc dung duoc — doi
# pypdf sang PyMuPDF hay Docling deu ra ket qua y het. Day la khiem khuyet cua chinh
# tep, va cach duy nhat la mot bang khai bang tay.
#
# Doi chieu tu bang quy doi in trong sach:
#   4 tbsp = G cp -> 1/4     8 tbsp = H cp -> 1/2     5 tbsp+1 tsp = N cp -> 1/3
#   Dash/Pinch < J tsp -> 1/8     O cp = 170 mL -> 2/3     con lai I -> 3/4
#
# Do duoc 86 cho trong tep. Voi mot quyen sach nau an thi day la hong o cho chi mang:
# bot se bao nguoi ta cho "H thia ca phe" ot cayenne — sai, troi chay, khong dau hieu.
_PHAN_SO = {"G": "¼", "H": "½", "I": "¾", "J": "⅛", "N": "⅓", "O": "⅔"}

COOKBOOK_SLASHDOT = HoSo(
    ten="cookbook_slashdot",
    moc=_MOC_COOKBOOK,
    sua_ky_tu=_PHAN_SO,
)

#: Danh sach ho so. Them mot dang tai lieu = them mot dong o day.
HO_SO: tuple[HoSo, ...] = (COOKBOOK_SLASHDOT,)


def nhan_dien(text: str) -> HoSo | None:
    """Ho so khop NHIEU nhat, va phai dat nguong. Khong khop -> None."""
    tot_nhat: tuple[int, HoSo] | None = None
    for ho_so in HO_SO:
        n = ho_so.so_lan_khop(text)
        if n >= ho_so.toi_thieu and (tot_nhat is None or n > tot_nhat[0]):
            tot_nhat = (n, ho_so)
    return tot_nhat[1] if tot_nhat else None


# --------------------------------------------------------------------------------
# Ap bang sua
# --------------------------------------------------------------------------------
# Don vi do luong. CO Y bo 'c' tran: mot chu 'c' don le dung truoc rat nhieu thu khac
# ngoai don vi do, va nham o day nghia la SUA HONG mot van ban von dung.
_DON_VI = r"tsp|tbsp|cp|cup|cups|lb|lbs|oz|qt|pt|gal|stick|sticks"

#: `(?<![A-Za-z])` chu khong phai `\b`: can bat ca "1H cp" (= 1 1/2 cup), noi chu H
#: dung ngay sau chu so nen khong co ranh gioi tu. Nhung "Vitamin H" thi khong duoc
#: dung — va no khong dung, vi con phai co don vi do di ngay sau.
_MAU_PHAN_SO = re.compile(rf"(?<![A-Za-z])([GHIJNO])(?=\s+(?:{_DON_VI})\b)")


def ap_sua_ky_tu(text: str, ho_so: HoSo) -> tuple[str, int]:
    """Tra ve (van ban da sua, so cho da thay).

    Luat HEP la bat buoc: chi thay khi chu cai thuoc bang VA co don vi do dung ngay
    sau. Chu 'H' trong van ban thuong la chu H that; thay bua o day la doi mot loi
    hien thanh mot loi im lang, dung huong ma ca du an nay dang chong.
    """
    if not ho_so.sua_ky_tu:
        return text, 0

    dem = 0

    def thay(khop: re.Match[str]) -> str:
        nonlocal dem
        moi = ho_so.sua_ky_tu.get(khop.group(1))
        if moi is None:
            return khop.group(0)
        dem += 1
        return moi

    return _MAU_PHAN_SO.sub(thay, text), dem
