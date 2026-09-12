"""Tu vung tieng Viet — de bat cum bi BE CHO VAN.

VI SAO TEP NAY TON TAI. Kieu hong nang nhat con lai cua tinh nang lam tho khong phai
sai luat, ma la BE MOT TU CO THAT cho khop van:

    "ngọt ngào"  ->  "ngọt ngao"     (mat dau huyen, de van voi "cao")
    "rực rỡ"     ->  "rực rao"       (doi ca van lan dau)
    "trong veo"  ->  "trong cao"

Bai chua ba cho do duoc cham VAN 20/20 TUYET DOI — vi model da be chu cho khop van.
Tuc thang diem dang THUONG cho dung hanh vi pha nghia, va khau chon ban cung vay: no
xep hang theo so loi luat, nen ban be chu se THANG ban giu chu dung ma lech mot van.

VI SAO TU SOAN CHU KHONG TAI TU DIEN CO SAN. Hai bo tu vung tieng Viet du lon
(undertheseanlp/dictionary 79K tu, Viet74K) deu la GPL-3.0, ma du an nay khong co tep
LICENSE nao. Dua du lieu GPL vao lich su git la mot quyet dinh phap ly, khong phai mot
quyet dinh ky thuat.

VI SAO KHONG DUNG KHO TAI LIEU NOI BO LAM TU DIEN. Da thu: rut 38.978 cum hai tieng tu
Truyen Kieu cong toan bo kb_chunk, roi soi mot bai tho. No bao "hoa sen", "nụ cười",
"tâm tình", "gió thổi" la KHONG CO THAT. Kho 598K ky tu van ban cong so khong chua noi
tu vung tho — dung no lam tu dien la loai dung nhung chu hay.

PHAM VI CO Y HEP. Day KHONG phai tu dien. No la danh sach nhung TU HAY BI BE — chu yeu
tu lay doi, vi tieng thu hai cua tu lay la cho de bien dang nhat va cung la cho hay roi
vao vi tri van. Mot cum khong co trong day KHONG co nghia la no sai.
"""

#: Danh sach cum KHONG CAN BAO — phan lon la tu lay, nhung co ca vai cum chi la
#: hai tu ke nhau vo toi (`bao là`, `trăng trong`). Day khong phai tu dien; no la
#: danh sach nhung cho bo do KHONG duoc bao.
#:
#: Tu hai tieng thong dung, phan lon la TU LAY — tieng thu hai cua tu lay la cho de
#: bien dang nhat, va cung la cho hay roi vao vi tri van.
#:
#: Viet duoi dang van ban ngan cach bang `|` de doc va sua duoc bang mat.
#:
#: KHI THEM TU MOI: them mot tu co tieng dau X thi phai them CA cac ban thuong gap
#: khac cua X. Che do `chat=False` bao nghi moi cum co tieng dau DA BIET ma khong
#: khop tu nao — thieu ban se thanh bao nham.
_NGUON = """
ngọt ngào|ngọt lịm|ngọt bùi
mặn mà|đậm đà|nhạt nhòa
thiết tha|thướt tha|yểu điệu|duyên dáng|đằm thắm|xinh xắn|xinh đẹp
dịu dàng|dịu êm|dịu ngọt|êm đềm|êm ái|êm ả
nhẹ nhàng|nhè nhẹ|khẽ khàng|khe khẽ|se sẽ
rực rỡ|rực sáng|rực hồng|lấp lánh|long lanh|lung linh|lóng lánh
chói chang|chói lọi|chập chờn|chập chùng|chênh vênh|chơi vơi|chấp chới
mờ ảo|mịt mù|mịt mờ|mơ hồ|mơ màng|mộng mơ
mênh mông|bát ngát|bao la|thăm thẳm|vời vợi|xa xăm|xa xôi
xanh xao|vàng vọt|đỏ au|trắng ngần|đen nhánh|bạc phơ
bâng khuâng|ngẩn ngơ|bơ vơ|chơ vơ|lẻ loi|cô đơn|quạnh quẽ|vắng vẻ
hắt hiu|hiu hắt|hiu quạnh
rì rào|xào xạc|thì thầm|thủ thỉ|róc rách|lao xao|xôn xao|rộn ràng
dạt dào|chứa chan|tràn trề|đầy ắp
mộc mạc|chân chất|thật thà|hiền hòa|hiền lành|hiền từ
đong đưa|đong đầy
nhạt nhoà|nhạt nhòa|nhạt phai
điệu đà|điệu hò|điệu buồn
mờ mịt|mịt mùng|mịt mù|mờ ảo
mặn mòi|mặn nồng|mặn chát
trăng trong|trăng rằm|trăng thanh|trăng non
bao la|bao là|bao dung
hoa huệ|hoa hồng|hoa cau
mơn man|mơn mởn
dập dình|dập dìu|dìu dặt
năm nào|năm xưa|năm tháng
phấp phơ|phấp phới|phất phơ
xốn xao|xốn xang|xôn xao
bập bồng|bập bùng|bồng bềnh
xanh xưa|xanh biếc|xanh ngắt
tảo tần|vất vả|nhọc nhằn|gian nan|lam lũ|cần cù|chịu khó
nâng niu|chăm chút|ân cần
lất phất|lâm thâm|tí tách|rả rích
ngào ngạt|thoang thoảng|ngan ngát|thơm tho|thơm ngát
mềm mại|mượt mà|óng ả|phất phơ|phấp phới
bồi hồi|xao xuyến|rưng rưng|nghẹn ngào|thổn thức|nức nở
man mác|nao nao|nôn nao
lặng lẽ|lặng thinh|im lìm|tĩnh mịch|thanh vắng
tưng bừng|náo nhiệt|nhộn nhịp
nồng nàn|nồng ấm|ấm áp|ấm cúng
mong manh|mỏng manh
chập chững|lững thững|thong thả|khoan thai
vun vút|vội vàng|hối hả|tất tả
trong veo|trong vắt|trong lành|trong trẻo
bập bùng|rừng rực
da diết|day dứt|khắc khoải
ngậm ngùi|tiếc nuối|luyến tiếc
phôi pha|nhạt phai|tàn phai
chống chếnh
sâu thẳm|sâu lắng
quê hương|quê nhà|làng quê|đồng quê|quê mùa
cha mẹ|mẹ cha|ông bà|anh em|chị em|con cái
nụ cười|ánh mắt|mái tóc|bàn tay|dáng hình|bóng dáng
hoa sen|hoa cau|hoa nhài|bông lúa|cành mai
dòng sông|con sông|bến sông|dòng nước|dòng đời|dòng kênh
cánh đồng|ruộng đồng|bờ đê|lũy tre|bờ ao|ao làng
trăng rằm|ánh trăng|vầng trăng|đêm trăng|trăng thanh
gió xuân|heo may|sương mai|sương sớm|nắng chiều|nắng vàng|gió mát
bếp lửa|khói bếp|mái nhà|mái đình|mái tranh|hiên nhà
áo dài|áo nâu|yếm đào|guốc mộc
tuổi thơ|ngày xưa|thuở xưa|năm xưa|thời gian
tình yêu|tình thương|yêu thương|nhớ thương|thương nhớ|nhớ nhung
cuộc đời|kiếp người|phận người|đời người
con đường|lối nhỏ|ngõ nhỏ|đường quê
mùa thu|mùa xuân|mùa hạ|mùa đông|mùa gặt
chiều tà|hoàng hôn|bình minh|đêm khuya|canh khuya
lời ru|câu hát|tiếng ru|tiếng hát|điệu hò
lao đao|long đong|lận đận|truân chuyên|cơ cực|khốn khó
bồng bềnh|bập bềnh|dập dềnh|lênh đênh|chòng chành
nghiêng nghiêng|chênh chếch|nhấp nhô|gập ghềnh|khúc khuỷu|quanh co|ngoằn ngoèo
thênh thang|lồng lộng|rộng rãi|chật chội|chon von|cheo leo
líu lo|ríu rít|thánh thót|văng vẳng|râm ran|rộn rã|ồn ào
mơn mởn|non nớt|tươi tắn|tươi tốt|tươi thắm
rạng rỡ|rạng ngời|sáng ngời|sáng trong|ngời ngời
thẹn thùng|e ấp|e lệ|ngượng ngùng|nũng nịu|nỉ non
vấn vương|vương vấn|lưu luyến|quyến luyến|bịn rịn
đong đầy|lâng lâng|phơi phới|hân hoan|rạo rực|xốn xang|ngất ngây
ngơ ngác|bỡ ngỡ|ngỡ ngàng|thẫn thờ|bần thần|hồi hộp
hoang vu|hoang sơ|hoang vắng|tiêu điều|xơ xác|tàn tạ|quạnh hiu
lã chã|đầm đìa|nghẹn ngào|bùi ngùi
ngút ngàn|ngút ngát|dập dờn|rập rờn|lấp ló|thấp thoáng|thấp thỏm
mịn màng|nõn nà|óng mượt|thơm lừng|thơm phức
chua chát|đắng cay|cay đắng|mặn chát
xa vắng|vắng lặng|vắng tanh|lắng đọng|êm ru|yên bình|thanh bình|an lành
mong nhớ|mong chờ|chờ mong|ngóng trông|trông ngóng|đợi chờ
hờn dỗi|giận hờn|hờn ghen|nồng thắm|thắm thiết|mặn nồng
son sắt|sắt son|thủy chung|bạc bẽo|phũ phàng|phụ bạc
sum vầy|quây quần|đoàn viên|ấm êm|êm ấm
say sưa|đắm đuối|mê mải|miệt mài|mải miết
xanh biếc|xanh rờn|xanh um|xanh ngắt|xanh thẳm|xanh tươi
vàng ươm|vàng rực|vàng óng|vàng hoe
đỏ thắm|đỏ rực|đỏ hồng|hồng tươi|hồng thắm
trắng muốt|trắng tinh|trắng xóa|trắng phau
tím biếc|tím ngắt|rợp bóng|rợp trời
lơ thơ|lưa thưa|thưa thớt|chơ vơ
lặng im|lặng ngắt|im ắng|tĩnh lặng
bến bờ|bờ bến|bến nước
mùa màng|mùa vụ
mải mê|mải miết|mê mải
thanh thoát|thanh tao|thanh cao
mơ mộng|mơ màng|mộng mị|mơ ước
lững lờ|lặng lờ|lờ lững
nhớ nhau|nhớ nhà|nhớ quê
mênh mang|mênh mông
dập dìu|dìu dặt
lấp lửng|lấp lánh|lấp ló
vội vã|vội vàng
sáng soi|soi sáng|sáng tỏ
đồng đội|đồng lòng|đồng quê
đêm đông|đêm khuya|đêm trăng
xao xác|xao xuyến|xao động
hiu hiu|hiu hắt|hiu quạnh
đậm đà|đậm nét
hiền hòa|hiền lành|hiền từ
"""


def chuan_hoa(cum: str) -> str:
    """Dang chuan cua mot cum, khong phu thuoc CACH DAT DAU.

    Tieng Viet co hai quy uoc dat dau thanh cho van co am dem, va chung la CUNG MOT CHU:

        kieu cu   "hòa"  "hóa"  "thủy"  "lòa"
        kieu moi  "hoà"  "hoá"  "thuỷ"  "loà"

    So chuoi tho thi chung khac nhau, va hau qua do duoc 12/09/2026: `hiền hoà` bi bao
    la cum la trong khi `hiền hòa` DA CO trong danh sach. Do la loi TRA CUU, khong phai
    thieu tu — va them "hiền hoà" vao danh sach la va trieu chung chu khong sua benh.

    `tach_tieng()` da phan giai dung ca hai ve ("hoa", "huyen"), nen chi can tra cuu
    bang dang da phan giai.
    """
    from .luat import tach_tieng

    ra = []
    for t in cum.split():
        chu, thanh = tach_tieng(t.strip(",.;:!?\"'()").lower())
        ra.append(f"{chu}~{thanh}")
    return " ".join(ra)


def _doc() -> frozenset[str]:
    ra: set[str] = set()
    for dong in _NGUON.strip().split(chr(10)):
        for tu in dong.split("|"):
            t = tu.strip().lower()
            if len(t.split()) == 2:
                ra.add(t)
    return frozenset(ra)


TU_GHEP: frozenset[str] = _doc()

#: Cung danh sach tren, o DANG CHUAN — tra cuu dung bang nay chu khong dung `TU_GHEP`,
#: de "hiền hoà" va "hiền hòa" cung khop. Xem `chuan_hoa`.
_TU_CHUAN: frozenset[str] = frozenset(chuan_hoa(t) for t in TU_GHEP)

#: Tieng DAU cua cac tu tren. Mot cum co tieng dau nam trong day nhung khong khop tu
#: nao la cum DANG NGO — xem `cum_kha_nghi(chat=False)`.
TIENG_DAU: frozenset[str] = frozenset(t.split()[0] for t in TU_GHEP)

#: Tieng SAU, theo tieng dau. Dung cho che do CHAT: chi bao khi tieng sau chi khac
#: mot tu da biet o DAU THANH.
_THEO_DAU: dict[str, frozenset[str]] = {}
for _t in TU_GHEP:
    _a, _b = _t.split()
    # KHOA o dang CHUAN (de "hoà"/"hòa" khop nhau), nhung GIA TRI giu NGUYEN VAN.
    #
    # Gia tri di thang vao loi nhac sua ("từ thật là ..."), nen no phai la chu that co
    # dau. Luu dang chuan roi lay nguoc ra se mat dau: loi nhac tro thanh "từ thật là
    # ngọt ngao" — chinh cai chu vua bao la sai.
    _k = chuan_hoa(_a)
    _THEO_DAU[_k] = _THEO_DAU.get(_k, frozenset()) | {_b}


def _bo_dau(tieng: str) -> str:
    """Tieng KHONG con dau thanh. Dung `tach_tieng` de giu nguyen mu/rau/trang."""
    from .luat import tach_tieng

    return tach_tieng(tieng)[0]


def _phu_am_dau(tieng: str) -> str:
    """Phu am dau cua mot tieng, rong neu khong co."""
    from .luat import _PHU_AM_DAU

    chu = _bo_dau(tieng)
    for p in _PHU_AM_DAU:
        if chu.startswith(p):
            return p
    return ""


def cum_nghi_be(bai: str, *, hep: bool = True) -> list[tuple[str, str]]:
    """Bo do RONG: `chat=True` CONG kieu DIEP AM. CHI DE XEP HANG, dung de chan.

    Bat them kieu ma `chat=True` bo sot: doi ca van lan dau cua mot tu lay.

        "rực rỡ" -> "rực rao"   : r- va r- diep am, "rao" khong phai ban cua "rực"

    HIEU CHUAN 12/09/2026:
        bao nham tren 3.254 cau Truyen Kieu: 153/3254 = 4,70%
        cac ca bao nham deu la TU LAY THAT chua liet ke — "đầy đặn", "dập dìu",
        "hiu hiu", "mê mẩn". Tuc nguon bao nham CUNG LOAI voi nguon bat dung.

    4,70% QUA CAO DE CHAN, VUA DU DE CHON — va khac biet do la co that, khong phai
    cach noi:

        chan : bao nham mot lan la loai han mot bai tot, khong lay lai duoc
        chon : bao nham chi doi thu tu uu tien giua 4 ban; xau nhat la lay mot ban
               tuong duong

    Do theo CAP tren cung bo ban, HAI luot doc lap, n=40 moi luot:

                              xep hang cu   + bo do rong
        cum bi be / bai            0,713         0,375     -47%
        bai KHONG co cum be        38/80         55/80     p=0,0101  THAT
                                     48%           69%
        van /20                     9,94          9,04     -0,89

    Doi it chu be lay diem van thap hon. Dung thu tu uu tien nguoi dung dat ra:
    "chi duoc chon lua cac tu co y nghia".
    """
    ra = list(cum_kha_nghi(bai, chat=True))
    for dong in bai.split(chr(10)):
        t = [w.strip(",.;:!?\"'()").lower() for w in dong.split()]
        for i in range(len(t) - 1):
            a, b = t[i], t[i + 1]
            if not a or not b or chuan_hoa(f"{a} {b}") in _TU_CHUAN:
                continue
            ban = _THEO_DAU.get(chuan_hoa(a))
            if not ban or any(chuan_hoa(x) == chuan_hoa(b) for x in ban):
                continue
            pa = _phu_am_dau(a)
            if pa and pa == _phu_am_dau(b):
                ra.append((f"{a} {b}", f"{a} {sorted(ban)[0]}"))
    return _thu_hep(bai, ra) if hep else ra


#: Vi tri VAN trong mot dong luc bat: tieng 6 cau luc; tieng 6 va 8 cau bat.
_VI_TRI_VAN: dict[int, frozenset[int]] = {6: frozenset({6}), 8: frozenset({6, 8})}


def _thu_hep(bai: str, cum: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Bo hai loai bao nham, ca hai deu co LY DO chu khong phai vua voi corpus.

    1. KHONG O VI TRI VAN. Be chu xay ra VI BI TU VAN, nen no xay ra o vi tri van. Ca
       hai ca that deu the: "rao" o tieng 8 cau bat, "ngao" o tieng 6 cau bat. Con phan
       lon bao nham la diep am ngau nhien giua cau — "thì thôi", "năm năm", "vội về".

    2. DIEP TU (hai tieng giong het nhau) — "xa xa", "ngày ngày", "xanh xanh". Diep tu
       la thu phap co that, va BE CHU KHONG BAO GIO tao ra mot cap giong het nhau. Bo
       chung la khong rui ro.

    Do 12/09/2026 tren 1.627 cap luc bat Truyen Kieu:

        bo do RONG          150/1627 = 9,22%
        + chi vi tri van     50/1627 = 3,07%
        + bo diep tu         35/1627 = 2,15%     <- cat hon BON lan

    Ca hai ca that van bi bat.

    VAN CHUA DU DE LAM BO CHAN: nguong cho mot bo chan la < 1% (nguong
    `ops/hieu_chuan_tho.py` dung cho so tieng). 22 cum con lai — "tình ta", "dập dìu",
    "lưu ly", "mơn man" — phan lon la tieng Viet dung. Bo do nay o lai khau CHON.

    Truyen `hep=False` de lay ban rong nguyen goc — dung de kiem xem thu hep co lam lot
    ca that khong. Xem docs/plan-sua-bo-do-be-chu.md muc 7.
    """
    from .luat import _cac_cau

    chu_van: set[str] = set()
    for t in _cac_cau(bai):
        for k in _VI_TRI_VAN.get(len(t), frozenset()):
            if k <= len(t):
                chu_van.add(t[k - 1].strip(",.;:!?\"'()").lower())
    ra = []
    for c, dung in cum:
        a, b = c.split()
        if a != b and b in chu_van:
            ra.append((c, dung))
    return ra


def cum_kha_nghi(bai: str, *, chat: bool = True) -> list[tuple[str, str]]:
    """Cac cum hai tieng co dau hieu BI BE. Tra (cum trong bai, tu that gan nhat).

    HAI CHE DO, va khac biet giua chung la khac biet giua "gan nhu chac chan" va
    "dang ngo":

      chat=True  — cum chi khac mot tu da biet o DAU THANH cua tieng thu hai.
                   "ngọt ngao" vs "ngọt ngào": bo dau thi ca hai deu la "ngot ngao".
                   Day la BE DAU, gan nhu khong the la trung hop.

      chat=False - tieng dau nam trong `TIENG_DAU` nhung cum khong khop tu nao.
                   DA DO VA KHONG DUNG DUOC — xem bang o duoi.

    HIEU CHUAN 12/09/2026, do CA HAI CHIEU:

                        bat 'ngọt ngao'   bao nham tren 3.254 cau Truyen Kieu
        chat=True             CO             1/3254 = 0,03%
        chat=False            CO          1559/3254 = 47,9%   <- VO DUNG

    `chat=False` bao ca 'Trăm năm trong cõi người ta' ('trong cõi' khong khop
    'trong lành') — tuc no loai dung cau tho noi tieng nhat tieng Viet. Danh sach
    249 tu khong the du de phan xu MOI ban cua mot tieng dau. Giu che do nay lai
    chi de ghi rang DA THU; dung bat no.

    `chat=True` chi bat duoc kieu BE DAU THANH. No KHONG bat duoc 'rực rao' (tu
    that la 'rực rỡ', doi ca van lan dau) hay 'trong cao' (tu that la 'trong
    veo'). Bat nhung ca do can mot TU DIEN THAT — dang cho quyet dinh ve giay
    phep GPL, xem docstring dau tep.

    KHONG PHAI BO CHAN. Danh sach tu o tren co y hep, nen mot cum khong khop hoan toan
    co the la tieng Viet dung. Dung no lam TIN HIEU XEP HANG giua cac ban — chon thi
    an, chan thi phan tac dung (xem ghi chu trong tho/sinh.py).
    """
    ra: list[tuple[str, str]] = []
    for dong in bai.split(chr(10)):
        t = [w.strip(",.;:!?\"'()").lower() for w in dong.split()]
        for i in range(len(t) - 1):
            a, b = t[i], t[i + 1]
            if not a or not b:
                continue
            cum = f"{a} {b}"
            if chuan_hoa(cum) in _TU_CHUAN:
                continue
            ban = _THEO_DAU.get(chuan_hoa(a))
            if not ban:
                continue
            if chat:
                # Chi bao khi bo dau thanh di thi TRUNG mot tu that.
                khong_dau = _bo_dau(b)
                khop = [
                    x for x in ban
                    if _bo_dau(x) == khong_dau and chuan_hoa(x) != chuan_hoa(b)
                ]
                if khop:
                    ra.append((cum, f"{a} {khop[0]}"))
            else:
                ra.append((cum, f"{a} {sorted(ban)[0]}"))
    return ra


__all__ = ["TIENG_DAU", "TU_GHEP", "cum_kha_nghi", "cum_nghi_be"]
