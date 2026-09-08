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
import unicodedata
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

    #: Do CHUYEN BIET. Cao hon thang, bat ke so lan khop.
    #:
    #: Khong dung "khop nhieu nhat thang": mot mau TONG QUAT luon dong hon mot mau
    #: HEP tren cung mot tai lieu. Do that — tren cookbook Slashdot, mau tieu de viet
    #: hoa khop 222 lan con mau tagline chuyen biet chi 59, nen luat "nhieu nhat
    #: thang" cuop tai lieu khoi dung ho so cua no va keo ket qua tut lai.
    do_uu_tien: int = 0

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

# `[ \n]` chu khong phai `\n`: buoc lam sach (clean.py) noi dong bi PDF ngat giua cau,
# va "from" la chu THUONG nen dong tagline bi noi vao dong ten mon:
#
#     truoc lam sach:  "Kristin's Poor Man's Goulash\nfrom the el-cheapo dept."
#     sau lam sach:    "Kristin's Poor Man's Goulash from the el-cheapo dept."
#
# Mau chi nhan dang co xuong dong se khop 0/60 sau khi lam sach — da xay ra that, va
# trieu chung la `section` tut ve NULL toan bo chu khong phai mot loi nao. Nhan ca hai
# dang de mau khong phu thuoc vao viec buoc truoc no lam gi.
#
# `{3,80}?` khong tham: can dung lai o " from the" gan nhat, khong nuot qua no.
_MOC_COOKBOOK = re.compile(r"\n([^\n]{3,80}?)[ \n]from the [^\n]{2,60} dept\.")

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
    #: Chuyen biet: mau tagline "from the ... dept." gan nhu khong the trung hop.
    do_uu_tien=10,
)

# --------------------------------------------------------------------------------
# Ho so 2: tai lieu dung dong VIET HOA lam tieu de
# --------------------------------------------------------------------------------
# Dang rat pho bien trong sach/booklet duoc thiet ke: ten muc va ten mon in hoa toan
# bo, than bai viet thuong. Do tren booklet Sa Pa (song ngu Viet-Anh, 46 trang):
# 108 moc, trong do 61 co dau tieng Viet.
#
# VI SAO KHONG DUNG DAI `A-Z` HAY `À-Ỹ`:
#
# Dai Unicode `à-ỹ` (U+00E0..U+1EF9) BAO TRUM ca chu HOA tieng Viet — `Ạ` la U+1EA0,
# nam gon trong do. Viet `[^a-zà-ỹ]` de nghia "khong co chu thuong" se loai luon
# `GÀ HẦM BÍ ĐỎ`. Da gap that: ban dau chi bat duoc 59 moc va toan tieng Anh, tuc mat
# sach ten mon tieng Viet — dung thu quan trong nhat, vi `section` di vao `embed_input`
# roi vao `tsv`, tuc no la duong duy nhat de BM25 khop duoc cau hoi tieng Viet.
#
# Nen dung sinh tap chu thuong bang unicodedata thay vi go tay mot dai.
_CHU_THUONG = "".join(
    chr(c)
    for c in range(0x61, 0x1F00)
    if chr(c).islower() and "LATIN" in unicodedata.name(chr(c), "")
)
_KHONG_THUONG = "[^" + chr(10) + "a-z" + _CHU_THUONG + "]"

#: Mot dong: khong co chu thuong nao, co it nhat mot chu cai, dai 4-60.
#: `(?=\n)` chu khong `\n`: khong nuot ky tu xuong dong, de hai tieu de lien nhau
#: (ban tieng Viet va ban tieng Anh cua cung mot mon) deu duoc nhan ra.
_MOC_VIET_HOA = re.compile(
    r"\n[ \t]*((?=[^\n]*[^\W\d_])" + _KHONG_THUONG + r"{4,60}?)[ \t]*(?=\n)"
)

TIEU_DE_VIET_HOA = HoSo(
    ten="tieu_de_viet_hoa",
    moc=_MOC_VIET_HOA,
    #: Nguong cao hon mac dinh: mot dong viet hoa le (vi du "OK" hay "LUU Y") xuat
    #: hien vai lan trong tai lieu binh thuong la chuyen thuong. Doi hoi 10 lan de
    #: chac day la mot QUY UOC trinh bay chu khong phai trung hop.
    toi_thieu=10,
    #: TONG QUAT — de o muc 0. Bat cu ho so hep nao cung phai thang no.
    do_uu_tien=0,
)

#: Danh sach ho so. Them mot dang tai lieu = them mot dong o day.
#:
#: Thu tu trong tuple KHONG quan trong — `do_uu_tien` moi quyet dinh.
HO_SO: tuple[HoSo, ...] = (COOKBOOK_SLASHDOT, TIEU_DE_VIET_HOA)


def nhan_dien(text: str) -> HoSo | None:
    """Ho so CHUYEN BIET nhat trong so cac ho so dat nguong. Khong co -> None.

    Uu tien truoc, so lan khop chi de pha hoa. Ly do o `HoSo.do_uu_tien`: mau tong
    quat luon dong hon mau hep, nen xep hang theo so lan khop se lam moi ho so hep
    tro nen vo dung ngay khi them mot ho so tong quat vao danh sach.
    """
    tot_nhat: tuple[int, int, HoSo] | None = None
    for ho_so in HO_SO:
        n = ho_so.so_lan_khop(text)
        if n < ho_so.toi_thieu:
            continue
        khoa = (ho_so.do_uu_tien, n)
        if tot_nhat is None or khoa > (tot_nhat[0], tot_nhat[1]):
            tot_nhat = (ho_so.do_uu_tien, n, ho_so)
    return tot_nhat[2] if tot_nhat else None


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
