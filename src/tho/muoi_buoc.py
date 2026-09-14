"""Bat model di QUA 10 BUOC va KHAI NGHIA tung chu van truoc khi nop bai.

Bon yeu cau cua nguoi dung, ngay 14/09/2026:

  1. diem that su rat thap                       (ngon ngu 4,38/10 · sang tao 1,27/5)
  2. them vao prompt: "khong duoc be cong" chu cho van
  3. chay mo hinh lam tho QUA 10 BUOC
  4. bat model khi chon tu phai THE HIEN DUOC tu do co nghia hay khong

VI SAO KHONG LAM BANG CODE — da thu va da do, hai lan:

    bo do "cum bi be" tu CHINH TA (cum_kha_nghi, 460 tu)
        -> khong bat duoc "sơn hong", "giữ dào", "không bao"
           vi chung doi ca van lan phu am, khong chi doi dau thanh
    bo do "cum van khong co trong tu dien 18k"
        -> 79,3% bao nham tren Truyen Kieu ("trước đèn", "ghét nhau" cung khong co)
    bo do "mach noi dung" bang truong nghia (mach_y.py)
        -> 19,50% bao nham, nguong la 1,60%

Phan biet "sơn hong" voi "trước đèn" can NGHIA, khong phai chinh ta. Ta khong co vector
nghia. Nhung MODEL thi co — nen cach con lai la bat CHINH NO khai ra, roi doc cai khai
do. Do dung la yeu cau so 4.

VI SAO KHAI RA LAI KHAC VOI DAN DO. Prompt hien tai DA CO "ĐỪNG làm ngược", "VÍ DỤ VỀ
LỖI ÉP VẦN", "Thơ phải CÓ NGHĨA" — va van cho ra "sơn hong". Bay lan can thiep vao
prompt trong du an nay da that bai. Khac biet o day khong phai them mot cau dan do
nua, ma la doi HINH DANG DAU RA: model phai viet ra nghia cua tung chu van TRUOC khi
viet cau chua no. Mot chu vo nghia luc do phai di kem mot dong dinh nghia bia ra — kho
hon nhieu so voi viec lang le nhet no vao cuoi cau.

DO LA MOT GIA THUYET, KHONG PHAI MOT SU THAT. No phai tra bang A/B n>=40 moi nhanh,
HAI luot doc lap. Xem `QUY_TRINH_10_BUOC` trong sinh.py.
"""

import re

#: Moc ngan phan nhap va bai tho. Model phai ket thuc bang dong nay roi moi den tho.
MOC = "BÀI THƠ:"

#: Ba cum BI BE da bat duoc tren dau ra that, dung lam vi du CAM.
#:
#: Dung ca ba chu khong bia vi du: day la loi model NAY thuc su mac, tren chu de that,
#: do ngay 13-14/09/2026. Vi du bia ra thi model co the coi la truong hop khong lien
#: quan; vi du that thi no dung dang cai model vua lam.
_VI_DU_BE = (
    ('"sơn hà" (núi sông)', '"sơn hong"', "cho vần với «mong»"),
    ('"dạt dào"', '"giữ dào"', "cho vần với «xao»"),
    ('"ngọt ngào"', '"ngọt ngao"', "cho vần với «cao»"),
    ('"không bao giờ"', '"không bao"', "cắt cụt cho đủ 6 tiếng"),
)

_DONG_BE = "\n".join(f"    {that:<26} -> {be:<14} ({vi})" for that, be, vi in _VI_DU_BE)

CAM_BE_CHU = f"""\
CẤM BẺ CHỮ — luật nặng nhất, nặng hơn cả luật vần.

Không được đổi, thêm, bớt hay cắt cụt chữ của một từ có thật để nó vần. Bốn cái dưới
đây là lỗi THẬT đã mắc, không phải ví dụ bịa:

{_DONG_BE}

Cả bốn đều đúng vần và đúng số tiếng — và cả bốn đều hỏng, vì chữ không còn nghĩa.

KHI KHÔNG TÌM ĐƯỢC CHỮ CÓ NGHĨA ĐỂ VẦN: viết lại CẢ CÂU TRƯỚC cho nó kết thúc bằng
một vần khác. Đừng bao giờ bẻ chữ ở câu sau. Một bài đúng vần mà có một cụm vô nghĩa
thì tệ hơn một bài lệch một vần mà chữ nào cũng thật."""

_QUY_TRINH = f"""\
LÀM THEO ĐÚNG 10 BƯỚC DƯỚI ĐÂY, và VIẾT RA các bước 2, 3, 5, 8 trước khi nộp bài.

BƯỚC 1 — Yêu cầu: thể lục bát, chủ đề đã cho.

BƯỚC 2 — LẬP Ý. Vạch mạch cảm xúc, 5 ý nối bằng dấu →, mỗi ý 2-4 chữ.
    Ví dụ chủ đề "uống nước nhớ nguồn":
    Cội nguồn → Cha ông → Hy sinh → Hòa bình hôm nay → Không quên

BƯỚC 3 — HÌNH ẢNH. Liệt kê 6-8 hình ảnh CỤ THỂ nhìn thấy được, không phải khái niệm.
    Tốt:  mái đình, bến sông, luống cày, tiếng ve
    Kém:  vẻ đẹp, tâm hồn, niềm tự hào

BƯỚC 4, 5, 6 — Viết câu lục, câu bát, nối mạch.

BƯỚC 5b — KHAI NGHĨA CHỮ VẦN. Đây là bước quan trọng nhất.
    Với MỖI chữ đứng ở vị trí vần (tiếng 6 câu lục, tiếng 6 và 8 câu bát), viết ra:

        <chữ> = <nghĩa bằng tiếng Việt thường, 2-6 chữ>

    Nếu bạn KHÔNG giải nghĩa được nó thành tiếng Việt bình thường, thì nó KHÔNG phải
    một từ — bỏ đi, chọn chữ khác, hoặc viết lại câu.
    Không được viết nghĩa bịa cho một chữ bạn vừa bẻ ra.

{{buoc_6b}}BƯỚC 7 — Tự kiểm: câu lục 6 tiếng, câu bát 8 tiếng, mạch vần liền, tiếng 2 thanh bằng.

BƯỚC 8 — SOÁT NGHĨA. Đọc lại cả bài, tìm cụm nào vô nghĩa. Ghi "sạch" nếu không có.

BƯỚC 9, 10 — Sửa nốt rồi nộp.

ĐỊNH DẠNG BẮT BUỘC — đúng thứ tự này, không thêm gì khác:

Ý: <5 ý nối bằng →>
HÌNH ẢNH: <6-8 hình ảnh, cách nhau bằng dấu phẩy>
CHỮ VẦN:
<chữ> = <nghĩa>
<chữ> = <nghĩa>
{{dinh_dang_6b}}SOÁT: <sạch, hoặc nêu cụm đáng ngờ và đã sửa thế nào>
{MOC}
<bài thơ, mỗi câu một dòng, không đánh số>"""


#: Khoi BUOC 6b — bat model viet CAU DAT truoc roi xay bai quanh no.
#:
#: Tach rieng de A/B duoc mot minh no. `sang tao` trong thang cham thuc chat la BO DO
#: CAU DAT — tieu chi ghi thang "CHO DIEM TOI DA khi bai co mot CAU DAT" — nen day la
#: can thiep nham THANG vao muc thap nhat cua ca he thong: 1,15/5, tuc 23%.
_BUOC_6B = """BƯỚC 6b — CÂU ĐẮT. Viết câu này TRƯỚC khi viết cả bài, rồi xây bài quanh nó.

    Một câu bát nói trúng một điều ai cũng từng thấy mà chưa nói thành lời.
    Toàn chữ thường, không một chữ lạ. Cái đắt nằm ở Ý, không ở chữ.

    Rồi viết một dòng: nó đắt ở chỗ nào. Nếu bạn không nói được nó đắt ở chỗ nào
    thì nó chưa đắt — viết câu khác.

"""

_DINH_DANG_6B = """CÂU ĐẮT: <một câu 8 tiếng>
ĐẮT Ở CHỖ: <một dòng>
"""


def quy_trinh(*, cau_dat: bool) -> str:
    """Phieu 10 buoc. `cau_dat=False` bo han buoc 6b — de A/B rieng buoc do."""
    return _QUY_TRINH.format(
        buoc_6b=_BUOC_6B if cau_dat else "",
        dinh_dang_6b=_DINH_DANG_6B if cau_dat else "",
    )


#: Bat moc `BÀI THƠ:` du model viet hoa thuong the nao, co hay khong co dau hai cham.
_MOC = re.compile(r"^\s*B[ÀA]I\s*TH[ƠO]\s*:?\s*$", re.IGNORECASE | re.MULTILINE)


def tach_bai(raw: str) -> str:
    """Lay phan BAI THO, bo phan nhap. Khong thay moc thi tra nguyen van.

    TRA NGUYEN VAN khi khong thay moc chu khong tra rong: model quen in moc nhung van
    lam tho dung la chuyen se xay ra, va bien no thanh mot bai tho rong la doi mot loi
    dinh dang thanh mot su co.
    """
    khop = list(_MOC.finditer(raw))
    if not khop:
        return raw
    return raw[khop[-1].end() :].strip()


#: Nhan cua cac dong NHAP. Dung de don not neu model in moc roi VAN lap lai phan nhap.
_NHAN_NHAP = re.compile(
    r"^\s*(Ý|Y|HÌNH ẢNH|HINH ANH|CHỮ VẦN|CHU VAN|SOÁT|SOAT|BƯỚC|BUOC"
    r"|CÂU ĐẮT|CAU DAT|ĐẮT Ở CHỖ|DAT O CHO)\b.*:",
    re.IGNORECASE,
)


def bo_dong_nhap(bai: str) -> str:
    """Bo nhung dong nhap con sot lai trong phan tho.

    Model doi khi in lai "CHỮ VẦN:" giua bai. Mot dong nhu vay se bi `kiem_luc_bat`
    dem thanh mot cau sai so tieng, va ca bai bi loai oan.
    """
    return "\n".join(d for d in bai.split("\n") if not _NHAN_NHAP.match(d))


def doc_khai_nghia(raw: str) -> dict[str, str]:
    """Doc phan CHU VAN: {chu: nghia}. Rong = model khong khai.

    Dung de DO xem model co lam that buoc nay khong — khong dung de chan. Mot ban khai
    day du ma bai van be chu thi con te hon khong khai, va ta can biet dieu do co xay
    ra khong.
    """
    ra: dict[str, str] = {}
    trong_khoi = False
    for dong in raw.split("\n"):
        d = dong.strip()
        if re.match(r"^(CHỮ VẦN|CHU VAN)\s*:", d, re.IGNORECASE):
            trong_khoi = True
            continue
        if re.match(
            r"^(SOÁT|SOAT|BÀI THƠ|BAI THO|CÂU ĐẮT|CAU DAT)\s*:?", d, re.IGNORECASE
        ):
            trong_khoi = False
            continue
        if trong_khoi and "=" in d:
            chu, _, nghia = d.partition("=")
            chu, nghia = chu.strip().strip("\"'“”"), nghia.strip()
            if chu and nghia:
                ra[chu.lower()] = nghia
    return ra


#: Doc CAU DAT model tu khai. Rong = model khong lam buoc 6b.
_CAU_DAT = re.compile(r"^\s*(?:CÂU ĐẮT|CAU DAT)\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_DAT_O_CHO = re.compile(
    r"^\s*(?:ĐẮT Ở CHỖ|DAT O CHO)\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE
)


def doc_cau_dat(raw: str) -> tuple[str, str]:
    """`(cau dat, dat o cho)`. Rong = model khong khai buoc 6b.

    Chi de DO xem model co lam that buoc nay khong — KHONG dung de chan. Mot ban khai
    day du ma bai van nhat thi con te hon khong khai, va ta can nhin thay dieu do neu
    no xay ra.
    """
    a = _CAU_DAT.search(raw)
    b = _DAT_O_CHO.search(raw)
    return (a.group(1).strip() if a else "", b.group(1).strip() if b else "")
