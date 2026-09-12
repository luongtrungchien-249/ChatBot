"""BUOC 8 muc ba: bat cau LAC khoi mach noi dung — bang LUAT, khong bang model.

Nguoi dung neu dich danh ca can bat:

    Cau 1 noi ve cha
    Cau 2 noi ve cay
    Cau 3 dot nhien noi ve bien
    Cau 4 noi ve mua thu
    "Mỗi hình ảnh nên phục vụ một mạch cảm xúc chung."

VI SAO BANG LUAT TRUOC, KHONG BANG NGUOI CHAM. Nguoi cham da duoc thu ba lan cho viec
xep hang ban va hong ca ba: +23 giay moi bai, va co lan 21/30 luot timeout. Mot bo do
tat dinh chay trong micro-giay, lap lai duoc, va test duoc.

CACH LAM: moi cau cham vao nhung TRUONG NGHIA nao. Mot cau bi goi la LAC khi no cham
vao it nhat mot truong, ma KHONG CHIA truong nao voi bat ky cau nao khac trong bai.

================================================================================
DA DO VA DANG KHONG DUOC DUNG. Doc phan nay truoc khi noi module nay vao dau.
================================================================================

Hieu chuan 13/09/2026 tren Truyen Kieu, 1.626 cua so 4 cau (tho DUNG CHUAN, moi bao
deu la bao NHAM). Bon cach dinh nghia "lac" da thu:

    v1  khong chia truong voi BAT KY cau nao        77,31%
    v2  them dieu kien >= 3 cau nhan ra truong      31,30%
    v3  chi xet khi bai co TRUONG TROI (>=2 cau)    19,50%
    v4  truong troi phai phu >= nua so cau          19,50%

Cach tot nhat cho 19,50%. Nguong de mot bo do duoc phep tham gia XEP HANG trong du an
nay la muc cua `cum_nghi_be`: 1,60%. Tuc cach nay te hon 12 lan.

Va con so 19,50% la CAN DUOI chu khong phai uoc luong: no do tren tho co dien, noi cac
cau von da chat mach hon tho bot sinh ra. Tren dau ra cua bot no chi co the cao hon.

NEN: module nay KHONG duoc noi vao `_xep_hang`, va vet buoc 8 van ghi `dat=None` cho
muc "mach noi dung" — tuc KHONG KIEM DUOC, dung nhu su that.

VI SAO GIU CODE LAI. Cung ly do voi `chon_van.py`: de lan sau ai do dinh lam lai thi
doc duoc con so thay vi thu lai tu dau. Va vi gia thuyet khong sai — chi la BANG TU
VUNG SOAN TAY qua tho. Muon lam duoc that thi can vector nghia, khong phai them tu vao
bang: them tu lam MOI cau nhan ra nhieu truong hon, tuc lam bo do bao it di vi ly do
sai, chu khong phai vi no chinh xac hon.

BA CHO CO TINH THAN TRONG, va ca ba deu la bai hoc da tra gia trong du an nay:

  1. CAU KHONG NHAN RA TRUONG NAO thi KHONG BAO GIO bi bao lac. Bang tu vung o duoi la
     tu soan tay, no khong phu het tieng Viet — "khong biet" phai ra "khong biet", chu
     khong duoc ra "sai". Cung luat voi `kiem_nhip` tra None.

  2. BAI DUOI BA CAU thi khong xet. Hai cau thi "chia truong voi cau khac" tro thanh
     "giong het cau kia", va moi cap luc bat binh thuong deu bi bao.

  3. NO LA TIN HIEU XEP HANG, KHONG PHAI BO CHAN. Ranh gioi nay da duoc ghi trong
     sinh.py: bo CHAN bao nham mot lan la loai han mot bai tot; bo CHON bao nham chi
     doi thu tu uu tien. Bo do nay tho hon `cum_kha_nghi` nhieu nen no khong duoc phep
     chan gi.
"""

import re

from .luat import _DAU_CAU

#: Truong nghia. TU SOAN TAY, co chu dich khong phu het tieng Viet.
#:
#: Mot tu nam o NHIEU truong la binh thuong va co loi: "giếng" vua la que huong vua la
#: nuoc, nen mot bai noi ve giếng va mot cau noi ve sông van chia nhau truong `nuoc`.
#: Chinh cho chong lan nay lam bo do bot bao nham.
TRUONG_NGHIA: dict[str, frozenset[str]] = {
    "gia đình": frozenset(
        {
            "cha", "mẹ", "con", "bà", "ông", "anh", "chị", "em", "cháu", "bố", "má",
            "nhà", "hiếu", "sinh thành", "nôi", "ru", "lời ru", "công cha", "nghĩa mẹ",
            "mẹ cha", "cha mẹ", "ông bà", "tổ tiên", "cội nguồn", "nguồn cội",
        }
    ),
    "quê hương": frozenset(
        {
            "quê", "làng", "xóm", "đình", "đa", "cây đa", "bến", "đò", "con đò",
            "ruộng", "đồng", "lúa", "tre", "chợ", "giếng", "mái tranh", "hiên",
            "quê nhà", "quê hương", "cổng làng", "lũy tre", "sân đình",
        }
    ),
    "sông nước": frozenset(
        {
            "sông", "nước", "biển", "suối", "dòng", "thuyền", "sóng", "bờ", "hồ", "ao",
            "giếng", "đò", "bến", "kênh", "rạch", "khơi", "buồm", "mưa", "nguồn",
        }
    ),
    "thời gian": frozenset(
        {
            "xuân", "hạ", "thu", "đông", "mùa", "chiều", "sớm", "đêm", "ngày", "năm",
            "tháng", "khuya", "hoàng hôn", "bình minh", "trưa", "tối", "xưa", "nay",
        }
    ),
    "thiên nhiên": frozenset(
        {
            "trăng", "sao", "mây", "gió", "nắng", "hoa", "lá", "cây", "chim", "ve",
            "sương", "trời", "cành", "rừng", "núi", "non", "sen", "cỏ", "bướm",
        }
    ),
    "chiến tranh": frozenset(
        {
            "lính", "súng", "giặc", "trận", "hy sinh", "máu", "chiến", "biên cương",
            "đồn", "quân", "chiến trường", "khói lửa", "bom", "đạn", "anh hùng",
        }
    ),
    "lao động": frozenset(
        {
            "cày", "cấy", "gánh", "gặt", "nghề", "mồ hôi", "nhọc", "vun", "trồng",
            "cuốc", "liềm", "thợ", "nông", "chăn", "dệt", "vất vả", "lam lũ",
        }
    ),
    "học hành": frozenset(
        {
            "thầy", "cô", "trường", "lớp", "sách", "bút", "chữ", "học", "trò", "bảng",
            "phấn", "giảng", "bài", "đèn sách",
        }
    ),
    "tình cảm": frozenset(
        {
            "thương", "nhớ", "yêu", "buồn", "sầu", "đợi", "chờ", "lòng", "tim",
            "tủi", "hờn", "vui", "mừng", "xót", "ơn", "biết ơn", "nghĩa", "tình",
        }
    ),
    "tín ngưỡng": frozenset(
        {
            "chùa", "đình", "khấn", "hương", "giỗ", "bàn thờ", "miếu", "phật", "cầu",
            "lễ", "nhang", "tổ tiên", "thờ",
        }
    ),
}

#: So cau TOI THIEU de xet. Xem cho than trong so 2 o dau tep.
SO_CAU_TOI_THIEU = 3

#: Dung CHUNG bang dau cau cua `luat.py` chu khong giu mot ban sao thu hai: hai ban
#: sao se lech nhau vao ngay ai do them mot dau vao mot ben.
_DAU = re.compile(f"[{re.escape(_DAU_CAU)}]")


def _tieng(cau: str) -> list[str]:
    return [t for t in _DAU.sub(" ", cau.lower()).split() if t]


def truong_cua_cau(cau: str) -> set[str]:
    """Nhung truong nghia ma mot cau cham vao. Rong = KHONG NHAN RA, khac voi "lac"."""
    tieng = _tieng(cau)
    cum = set(tieng) | {
        f"{tieng[i]} {tieng[i + 1]}" for i in range(len(tieng) - 1)
    }
    return {ten for ten, tu in TRUONG_NGHIA.items() if cum & tu}


def cau_lac_mach(bai: str) -> list[tuple[int, str]]:
    """Cac cau LAC khoi mach. Danh sach (so cau tu 1, ten truong khong ai chia).

    Rong = khong phat hien duoc gi. KHONG co nghia la "mach chac" — bang tu vung nay
    khong phu het tieng Viet, va mot bo do mot phan noi "dat" la mot bo do noi doi.
    """
    cau = [d.strip() for d in bai.strip().split("\n") if d.strip()]
    if len(cau) < SO_CAU_TOI_THIEU:
        return []

    truong = [truong_cua_cau(c) for c in cau]
    ra: list[tuple[int, str]] = []
    for i, t in enumerate(truong):
        if not t:
            # Khong nhan ra truong nao -> khong ket luan gi. Xem cho than trong so 1.
            continue
        khac: set[str] = set()
        for j, x in enumerate(truong):
            if j != i:
                khac |= x
        if not (t & khac):
            ra.append((i + 1, ", ".join(sorted(t))))
    return ra
