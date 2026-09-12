"""System prompt cho route lam tho, va thong diep sinh lai khi sai luat.

KHONG nhet vao SYSTEM_PROMPT chinh, vi hai ly do:

  1. Tang `system` dang o 12.948 / 12.960 ky tu — con 12 ky tu. Them luat tho vao do
     la vo tran.
  2. Luat tho chi dung cho MOT route. Moi tin nhan hoi thoai thuong deu phai tra tien
     cho no neu de chung.

Cach viet theo dung thu tu da CHUNG MINH duoc hieu qua trong du an nay (xem
docs/plan-truy-hoi-xuyen-ngon-ngu.md muc 11):

  - Menh lenh len CAU DAU, khong buoc dieu kien theo su tu tin cua model.
  - Kem VI DU. Vi du day manh hon luat — ket luan da do duoc.
  - Kem mot VI DU SAI co giai thich. Voi tho thi ca phan dien dac biet quan trong:
    loi hay gap nhat la thua mot tieng, va model rat kho tu thay.
"""

from .luat import Loi, chu_thich_thanh, danh_so_tieng
from .y_dinh import TheTho

#: Bai mau. CO Y chon ca dao quen thuoc chu khong tu sang tac: no chac chan dung luat
#: (da qua bo kiem tra o `luat.py` — xem `TestPrompt`), va model nhieu kha nang da doc.
#:
#: LA MOT TUPLE du chi co mot bai: `tho/sinh.py::so_cau_chep` doc day de chan viec
#: model CHEP bai mau roi tra ve nhu tho no vua lam.
#:
#: RANG BUOC DO DAI ("viet DUNG 4 cau") them ngay 12/09/2026. Do HAI luot doc lap,
#: n=40 moi luot moi ben, roi gop lai (n=80):
#:
#:                        8 cau (cu)      4 cau (moi)     p (Fisher)
#:     SACH ca van         1/80 =  1%     13/80 = 16%       0,0012   THAT
#:     dung KHUNG         79/80 = 99%     78/80 = 98%       1,0      khong mat gi
#:     do tre p50          ~2.050 ms       ~1.870 ms
#:
#: CO CHE: bai 8 cau co BAY moi van, bai 4 cau chi co BA. Moi moi van la mot co hoi
#: that bai doc lap, nen bai cang dai cang kho giu sach ca bai. Sach hay khong la thu
#: NGUOI DUNG THAY: bai sach gui thang, bai con loi kem mot cau xin loi.
#:
#: Luot do dau cho thay khung tut 40/40 -> 38/40 va toi da tuong do la cai gia phai
#: tra. Luot hai cho 39/40 -> 40/40, tuc HOI QUY DO KHONG LAP LAI — no la nhieu. Gop
#: hai luot thi p = 1,0. Day la ly do phai chay hai luot doc lap chu khong mot.
#:
#: DA THU BON BAI VA DA QUAY VE MOT — xem `TestPrompt` va
#: docs/plan-van-ngon-ngu-sang-tao.md muc 10.
_MAU_LUC_BAT: tuple[str, ...] = (
    (
        "Công cha như núi Thái Sơn\n"
        "Nghĩa mẹ như nước trong nguồn chảy ra\n"
        "Một lòng thờ mẹ kính cha\n"
        "Cho tròn chữ hiếu mới là đạo con"
    ),
)

#: MUC 10 CUA DAC TA ("cau dat") VA "cam xuc" — CO TRONG PROMPT THEO QUYET DINH CUA
#: NGUOI DUNG, sau khi da do va da bao cao cai gia.
#:
#: Doi chieu dac ta 10 muc cua nguoi dung voi prompt nay: 9/10 da co san. Hai muc nay
#: la phan con lai, va chung ung voi hai chi so thap nhat so voi thang (`sang tao`
#: 1,6/5, `cam xuc` 3,1/5).
#:
#: PHEP DO NOI CHUNG KHONG UNG HO. A/B n=40 moi ben, 12/09/2026:
#:
#:                      khong co      co           chenh
#:     sang tao          1,62/5      1,82/5    +0,20 ± 0,34  nhieu   <- nham vao
#:     cam xuc           3,23/5      3,27/5    +0,05 ± 0,21  nhieu   <- nham vao
#:     ngon ngu          5,78/10     4,60/10   -1,18 ± 0,74  THAT    <- gia phai tra
#:     sach ca van        5/40        1/40
#:     do tre           1.792 ms    2.344 ms     +552 ms     THAT    <- gia phai tra
#:     CHEP cau mau       0/40        0/40                           (bo chan chay)
#:
#: Hai muc nham vao khong nhuc nhich; `ngon ngu` va do tre hong that. Nguoi dung biet
#: con so nay va van chon giu — day la dac ta cua ho, va no dung o day vi the.
#:
#: DUNG GO RA vi "do cho thay no khong an". Muon go thi phai hoi nguoi dung.
#:
#: BOI CANH RONG HON, de nguoi sau khong thu lai cac bien the: day la lan thu TU cung
#: mot co che — bao model NHAM CAO HON ve chat tho thi no voi lay chu la va `ngon ngu`
#: tut:
#:
#:     chon van truoc (rang buoc cung)              69,7 -> 57,1 /100
#:     giu dung muc cu the (rang buoc cung)          4/6 -> 2/6
#:     prompt v3 (them vi du + "dung chu thuong")   ngon ngu -1,45 (khi da chan chep)
#:     cau dat + cam xuc (them muc tieu)            ngon ngu -1,18
#:
#: Cai DA an thi deu la thu THU HEP viec phai lam:
#:     ep DO DAI 4 cau   -> sach ca van 1% -> 16% (p=0,0012)
#:     chan CHEP         -> bo mot nguon diem gia
#:     ve SO TIENG ra    -> khung 6-8 len 100%

#: Cau lam vi du cho CAU DAT. Nguyen Du, Truyen Kieu — chinh cau nguoi dung dan ra.
#:
#: NAM TRONG BO CHAN CHEP (`tho/sinh.py::_CAU_MAU`). Bat buoc: prompt v3 da day rang
#: them tho vao prompt ma khong chan thi model chep no, va muc tang do duoc hoa ra la
#: diem cua ca dao chu khong phai cua bot.
CAU_DAT_MAU = "Người buồn cảnh có vui đâu bao giờ"

#: CHI TIET HOA LUAT theo dac ta nguoi dung, 12/09/2026 — so do van, bang bang-trac
#: day du ("nhi tu luc phan minh"), tieu doi, nhip 2/4.
#:
#: CO TRONG PROMPT THEO QUYET DINH CUA NGUOI DUNG. Phep do KHONG ung ho, va cung khong
#: bac bo. A/B n=40 moi ben, chay HAI luot doc lap roi gop (n=80):
#:
#:                          khong co    co (v4)      p / ket luan
#:     bang-trac 0 loi        6/80       12/80       p=0,21  trong nhieu
#:     + ep tieng 2           4/80        6/80       p=0,75  trong nhieu
#:     sach ca van            4/80        5/80       p=1,00  trong nhieu
#:     dung khung            79/80       78/80       p=1,00  trong nhieu
#:     van (trung binh)      10,89        9,64       -1,25, lech AM o CA HAI luot
#:     do tre                1.855 ms    1.564 ms    -291 ms
#:
#: Khong chi so LUAT nao nhich len co y nghia — ke ca `bang-trac`, du da them han mot
#: bang day du. Con `van` thi lech am o ca hai luot (-1,31 va -1,20), tuc mot tin hieu
#: yeu nhung NHAT QUAN: prompt dai them 762 ky tu lam loang cac rang buoc khac, va so
#: cau tang tu 6,4 len 7,0-7,6 (bai dai hon = nhieu moi van hon = kho sach hon).
#:
#: DUNG GO RA vi "do cho thay khong an". Muon go thi phai hoi nguoi dung.
#:
#: Day la lan thu NAM them chi tiet vao prompt ma khong cai thien duoc chat luong. Cac
#: lan truoc: chon van truoc (69,7 -> 57,1), giu muc cu the (4/6 -> 2/6), prompt v3
#: (ngon ngu -1,45), cau dat + cam xuc (ngon ngu -1,18).
#:
#: CO SO CHO TIENG 2 trong bang, do tren 1.627 cau Truyen Kieu:
#:     cau luc  tieng 2 bang   1604/1627 = 98,6%
#:     cau bat  tieng 2 bang   1627/1627 = 100,0%
#:     cau bat  tieng 6 != 8   1627/1627 = 100,0%
#: 23 cau "vi pham" hau het la TIEU DOI ("Mai cốt cách, tuyết tinh thần") — ngoai le co
#: ten, khong phai nhieu. Bang CHAN `_LUC_BAT_LUC` van khong ep tieng 2 vi chinh bai
#: mau tren vi pham no ("Nghĩa mẹ như nước trong nguồn chảy ra"); cham diem thi DA tinh.
_LUAT_LUC_BAT = f"""\
LÀM THƠ LỤC BÁT. Chỉ xuất bài thơ, không lời dẫn, không giải thích, không tiêu đề.

1. SỐ TIẾNG VÀ ĐỘ DÀI. Câu lẻ 6 tiếng (câu lục), câu chẵn 8 tiếng (câu bát).
   Viết ĐÚNG 4 câu: lục - bát - lục - bát. Không dài hơn.

2. VẦN — mạch vần nối liên tục, không đứt đoạn:

       câu lục   x x x x x A
       câu bát   x x x x x A x B
       câu lục   x x x x x B
       câu bát   x x x x x B x C

   Tiếng 6 câu lục vần với tiếng 6 câu bát ngay sau nó.
   Tiếng 8 câu bát đó vần với tiếng 6 câu lục kế tiếp.
   Vần CÙNG NHÓM là được, không cần trùng khít:
       sông - hồng - trong        ngân - trần - xuân

3. BẰNG-TRẮC — "nhị tứ lục phân minh, nhất tam ngũ bất luận".
   Tiếng 2, 4, 6 phải đúng; tiếng 1, 3, 5, 7 tự do.

       câu lục    1   2   3   4   5   6
                  ·   B   ·   T   ·   B
       câu bát    1   2   3   4   5   6   7   8
                  ·   B   ·   T   ·   B   ·   B

   BẰNG = không dấu (ngang) và dấu huyền.  TRẮC = sắc, hỏi, ngã, nặng.

   Riêng câu bát: tiếng 6 và tiếng 8 đều thanh bằng nhưng phải KHÁC NHÓM — một chữ
   ngang thì chữ kia phải huyền. Cùng ngang hoặc cùng huyền thì câu đọc bị đơ.
       "...lòng tràn" (ngang) rồi "...nắng vàng" (huyền)  → đúng

Bài mẫu đúng luật:
{_MAU_LUC_BAT[0]}

Ở bài mẫu: "Sơn" (tiếng 6 câu 1) vần "nguồn" (tiếng 6 câu 2); "ra" (tiếng 8 câu 2)
vần "cha" (tiếng 6 câu 3).

Bài mẫu chỉ để cho thấy LUẬT và CÁCH DÙNG CHỮ. ĐỪNG chép lại câu nào của nó — kể cả
khi đề bài trùng chủ đề với nó.

VÍ DỤ SAI — "Công cha như núi Thái Sơn cao": câu này 7 tiếng, câu lục chỉ được 6.
Thừa một tiếng là lỗi hay gặp nhất và khó tự thấy nhất. Đếm lại từng tiếng trước khi
trả lời.

NHỊP. Câu lục ngắt 2/2/2 hoặc 2/4. Câu bát ngắt 2/2/2/2 hoặc 4/4. Nhịp chẵn tạo cảm
giác đều đặn, êm ái. Đọc thành tiếng trong đầu — phải tự chảy, không lấy hơi bất thường.

TIỂU ĐỐI (không bắt buộc, nhưng làm câu bát hay hẳn lên): hai vế bốn tiếng đối nhau
về ý hoặc thanh.
    "Mai cốt cách, tuyết tinh thần"

THỨ TỰ LÀM VIỆC — quan trọng ngang luật vần:

    Ý muốn nói  →  hình ảnh  →  chữ  →  rồi mới xử lý vần

ĐỪNG làm ngược: nghĩ ra vần trước rồi nhét một chữ bất kỳ vào cho khớp. Đó là lỗi nặng
nhất của thơ tập làm, và người đọc nhận ra ngay.

VÍ DỤ VỀ LỖI ÉP VẦN — "Thể hiện vẻ đẹp tròn vương cuộc đời": câu này đúng 8 tiếng và
đúng vần, nhưng "tròn vương" không có nghĩa gì. Nó được nhét vào chỉ vì vần với
"thường". Thà đổi cả câu trước còn hơn để lại một cụm vô nghĩa.

Thơ phải CÓ NGHĨA: nói về một điều cụ thể, có hình ảnh thật, tránh sáo ngữ chung chung
kiểu "vẻ đẹp thanh khiết" hay "tâm hồn Việt".

CÂU ĐẮT — đây là thứ tách một bài thơ khỏi một đoạn văn xuôi có vần.

Cả bài nên có MỘT câu khiến người đọc dừng lại. Không phải câu dùng chữ kêu, mà là câu
nói trúng một điều ai cũng từng thấy mà chưa nói thành lời:

    {CAU_DAT_MAU}

Câu đó dùng toàn chữ thường, không một chữ lạ. Cái đắt nằm ở Ý, không ở chữ.
Ba câu còn lại mộc mạc cũng được — nhưng phải có một câu như vậy.

CẢM XÚC: viết từ một chỗ đứng cụ thể — người con nhớ mẹ, người đi xa ngoái lại, người
ngồi một mình lúc chiều xuống. Đừng tả từ bên ngoài như người qua đường.\
"""

#: Ban dich Nam Quoc Son Ha — bon cau bay tieng, van "ơi".
_MAU_TNTT = (
    "Sông núi nước Nam vua Nam ở\n"
    "Rành rành định phận tại sách trời\n"
    "Cớ sao lũ giặc sang xâm phạm\n"
    "Chúng bay sẽ bị đánh tơi bời"
)

_LUAT_TNTT = f"""\
LÀM THƠ THẤT NGÔN TỨ TUYỆT. Chỉ xuất bài thơ, không lời dẫn, không giải thích.

Luật bắt buộc:
1. Đúng 4 câu, mỗi câu đúng 7 tiếng. Không hơn, không kém.
2. Tiếng cuối câu 2 và câu 4 hiệp vần. Câu 1 nên hiệp vần cùng chúng.
3. Luật bằng-trắc xét tiếng 2, 4, 6 của mỗi câu; tiếng 1, 3, 5 tự do.

Bài mẫu đúng luật:
{_MAU_TNTT}

Ở bài mẫu: "trời" (cuối câu 2) hiệp vần "bời" (cuối câu 4).

VÍ DỤ SAI — "Sông núi nước Nam là của vua Nam ở": câu này 9 tiếng, thất ngôn chỉ được
7. Đếm lại từng tiếng trước khi trả lời.

THỨ TỰ LÀM VIỆC — quan trọng ngang luật vần:

    Ý muốn nói  →  hình ảnh  →  chữ  →  rồi mới xử lý vần

ĐỪNG làm ngược: nghĩ ra vần trước rồi nhét một chữ bất kỳ vào cho khớp. Một câu đúng
vần mà cụm từ vô nghĩa thì tệ hơn một câu thất vận.

Thơ phải CÓ NGHĨA: nói về một điều cụ thể, có hình ảnh thật, tránh sáo ngữ chung chung.\
"""

_THEO_THE: dict[TheTho, str] = {
    "luc_bat": _LUAT_LUC_BAT,
    "that_ngon_tu_tuyet": _LUAT_TNTT,
}


def system_prompt(the_tho: TheTho) -> str:
    """System prompt cho mot the tho.

    Bang van duoc GHEP O DAY chu khong nam trong hang so `_LUAT_LUC_BAT`: no duoc sinh
    ra tu `bang_van.py`, va ghep luc goi thi tranh duoc rang buoc thu tu dinh nghia
    trong module.

    CHI GHEP CHO LUC BAT. That ngon tu tuyet co cau truc van khac (cuoi cau 1-2-4) nen
    bang nay khong dung cho no, va chua do duoc gi tren the do.
    """
    if the_tho == "luc_bat":
        return _THEO_THE[the_tho] + chr(10) + chr(10) + bang_van_goi_y()
    return _THEO_THE[the_tho]


def yeu_cau(chu_de: str) -> str:
    """Tin nhan nguoi dung gui cho model."""
    return f"Làm một bài về: {chu_de}" if chu_de else "Làm một bài thơ."


#: Diem toi da nguoi cham cho moi ban khi XEP HANG. Bang tong cac muc ma bo kiem tra
#: tat dinh KHONG nhin thay duoc: ngon ngu 10 + hinh anh 10 + y nghia 10 + cam xuc 5
#: + sang tao 5 = 40. Trung voi thang 100 o evals/metrics/tho_hay.py, tru `nhip` (15)
#: — nhip can mot tu dien tu ghep ma ta chua co, nen dung hoi nguoi cham ve no o day.
DIEM_CHON_TOI_DA = 40

#: Diem tru cho MOI cum chu ghep vo nghia. Tam cum la het diem.
#:
#: Con so nay lam cong viec ma chu "chấm nghiêm" khong lam duoc: no BUOC thang diem
#: phai gian ra. Ban dau chi noi "chấm nghiêm" va nguoi cham cho 26-38/40 — trung binh
#: 81%, trong khi nguoi cham nghiem cua evals/metrics/tho_hay.py cho `ngon ngu` 40%
#: tren cung loai bai. Khong phan biet duoc thi CHON khong nhat duoc gi.
TRU_MOI_CUM = 8

_HUONG_DAN_CHON = f"""\
Bạn đang chọn bài thơ lục bát hay nhất trong nhiều bản. Tất cả đã được máy kiểm luật
số tiếng, vần và bằng-trắc rồi — ĐỪNG chấm lại những thứ đó.

Với MỖI bản, làm đúng hai việc theo thứ tự:

BƯỚC 1 — ĐẾM CỤM CHỮ GHÉP CHO ĐỦ VẦN.
Đó là cụm đúng vần nhưng KHÔNG có nghĩa trong tiếng Việt, kiểu:

    "tròn vương cuộc đời"     "ngàn nơi sông rồng"
    "nhẹ diêu"                "lấp lơ"
    "tình trang đầy vơi"      "thanh sang giữa đời"

Thử đọc riêng cụm đó ra khỏi câu: nếu không giải nghĩa được thành tiếng Việt bình
thường thì nó là một cụm vô nghĩa. Đếm số cụm.

BƯỚC 2 — CHO ĐIỂM, bắt đầu từ {DIEM_CHON_TOI_DA} rồi trừ:

    mỗi cụm vô nghĩa đếm được ở bước 1   trừ {TRU_MOI_CUM}
    toàn sáo ngữ chung chung
      ("vẻ đẹp thanh khiết", "tâm hồn Việt")   trừ 6
    các câu rời rạc, không một chủ đề          trừ 6
    chỉ mô tả, không có cảm xúc thật           trừ 4
    không có CÂU ĐẮT nào khiến người đọc dừng lại   trừ 4

Xuất đúng một dòng cho mỗi bản, theo thứ tự, KHÔNG giải thích:

    <số bản>|<số cụm vô nghĩa>|<điểm>

Ví dụ với hai bản:

    1|2|14
    2|0|32\
"""


def huong_dan_chon() -> str:
    return _HUONG_DAN_CHON


def yeu_cau_chon(cac_ban: list[str]) -> str:
    """Danh so cac ban de nguoi cham tra ve dung so dong va dung thu tu."""
    khoi = [f"BẢN {i}:\n{b}" for i, b in enumerate(cac_ban, start=1)]
    return "\n\n".join(khoi)


def nhac_sua(bai: str, loi: list[Loi]) -> str:
    """Thong diep sinh lai. VE RA cho sai, khong chi mo ta no.

    Ban truoc chi liet ke mo ta kieu "tieng 4 ('trời') la thanh bang, can trac". Do
    duoc 11/09/2026: 0/5 bai dat sau DU ba vong sua — vong sinh lai la chi phi thuan.

    Ly do: dong do bat model tu lam BA viec lien tiep — xac dinh `trời` mang thanh gi,
    biet thanh do thuoc nhom nao, roi nghi chu thay the. Hai viec dau la viec
    `tach_tieng()` lam duoc: tat dinh, mien phi, chinh xac 100%. Bat model doan lai
    thu ta da biet chac la lang phi dung the manh cua minh.

    Ve ra thi model chi con MOT viec thuan ngu nghia. Day dung la co che da do duoc
    hieu qua hai lan trong du an: mo ta cong cu 10/09 (1/4 -> 4/4) va chan 7 ngay
    11/09 (3/6 -> 6/6) — ca hai deu la chuyen tu MO TA TRUU TUONG sang CHI DICH DANH.
    """
    cau = [d.strip() for d in bai.strip().split("\n") if d.strip()]
    khoi: list[str] = []

    for x in loi:
        if x.loai == "so_cau":
            khoi.append(f"Câu {x.cau}: {x.mo_ta}.")
            continue

        if x.loai == "so_tieng":
            # VE SO RA. Bao model "cau nay co 7 tieng" la bat no dem lai — ma dem
            # tieng chinh la viec no vua lam sai. Xem `danh_so_tieng`.
            dong_sai = cau[x.cau - 1] if 0 < x.cau <= len(cau) else ""
            ve_so = danh_so_tieng(dong_sai) if dong_sai else ""
            if not ve_so:
                khoi.append(f"Câu {x.cau}: {x.mo_ta}.")
                continue
            can = 6 if x.cau % 2 == 1 else 8
            co = len(dong_sai.split())
            viec = (
                f"Bớt {co - can} tiếng" if co > can else f"Thêm {can - co} tiếng"
            )
            khoi.append(
                f"Câu {x.cau} sai SỐ TIẾNG — {x.mo_ta}:\n\n{ve_so}\n\n"
                f"{viec} cho đủ {can}, giữ nguyên ý câu."
            )
            continue

        dong = cau[x.cau - 1] if 0 < x.cau <= len(cau) else ""
        ve = chu_thich_thanh(dong, nhan_manh=x.vi_tri) if dong else ""
        if not ve:
            khoi.append(f"Câu {x.cau}: {x.mo_ta}.")
            continue

        if x.loai == "bang_trac":
            khoi.append(
                f"Câu {x.cau} sai luật bằng-trắc — {x.mo_ta}:\n\n{ve}\n\n"
                "Thanh BẰNG là ngang và huyền. Thanh TRẮC là sắc, hỏi, ngã, nặng.\n"
                "Đổi đúng tiếng được đánh dấu sang một chữ khác cùng ý, đúng thanh."
            )
        else:
            khoi.append(f"Câu {x.cau} sai vần — {x.mo_ta}:\n\n{ve}")

    danh_sach = "\n\n".join(khoi)
    return (
        f"Bài vừa rồi sai luật. Từng chỗ một:\n\n{danh_sach}\n\n"
        "SỐ TIẾNG là luật bắt buộc: câu lục đúng 6 tiếng, câu bát đúng 8 tiếng, "
        "không co giãn. Sửa số tiếng TRƯỚC, rồi mới tới vần.\n"
        "Sửa đúng những chỗ đó rồi viết lại TOÀN BỘ bài thơ. Chỉ xuất bài thơ, "
        "không giải thích."
    )


def nhac_sua_be_chu(bai: str, cum: list[tuple[str, str]]) -> str:
    """Thong diep sinh lai khi bat duoc chu BI BE cho van.

    CHI DICH DANH, khong mo ta chung chung. Cung co che da lam khung 6-8 len 100%:
    ta BIET CHAC tu that la gi (`tu_vung.py`), nen dua thang no ra thay vi bao model
    "co cum vo nghia, sua di".

    VA NOI RO CACH SUA: doi lai chinh ta thi HONG VAN — do la ly do model be chu ngay
    tu dau. Nen phai viet lai CA CAU voi mot van khac, khong phai va mot chu.
    """
    khoi = [
        f'    "{sai}"  -> từ thật là "{dung}"'
        for sai, dung in cum
    ]
    ds = chr(10).join(khoi)
    return (
        f"Bài vừa rồi có chữ bị BẺ cho khớp vần — những chữ này không có trong tiếng "
        f"Việt:\n\n{ds}\n\n"
        "Đổi lại cho đúng chính tả thì HỎNG VẦN — đó chính là lý do chúng bị bẻ.\n"
        "Nên hãy VIẾT LẠI CẢ CÂU với một vần khác, giữ nguyên ý, dùng chữ có thật.\n"
        "Thà đổi cả câu còn hơn để lại một chữ không ai hiểu.\n"
        "Viết lại TOÀN BỘ bài thơ. Chỉ xuất bài thơ, không giải thích."
    )


#: So nhom van va so chu dua vao prompt.
#:
#: Giu NGAN co chu dich. Do 12/09/2026: prompt v4 dai them 762 ky tu lam `van` tut 1,25
#: — prompt cang dai thi cac rang buoc cang loang. Bang nay phai tra du cho cho cho do.
SO_NHOM_GOI_Y = 6
SO_CHU_GOI_Y = 8
SO_TU_GOI_Y = 3


def bang_van_goi_y() -> str:
    """Vai nhom van kem chu CO THAT, de model khong phai tu bia chu khi bi tu van.

    LA GOI Y, VA CACH VIET PHAI NOI RO DIEU DO. «Chon van truoc» — ep dung nhung chu
    da chon o dung nhung vi tri da dinh — lam diem sap tu 69,7 xuong 57,1/100. Khac
    biet duy nhat giua thanh va bai o day la mot chu: bang nay MO RONG lua chon chu
    khong thu hep no.

    Neu do thay ti le chu van nam trong bang vot len gan 100% thi model dang coi day la
    danh sach bat buoc — luc do phai doi cach viet hoac bo han. Xem
    docs/plan-chon-tu-co-nghia.md muc 6.
    """
    from .bang_van import CHU_THEO_VAN, TU_THEO_VAN

    van = sorted(CHU_THEO_VAN, key=lambda v: (-len(CHU_THEO_VAN[v]), v))[:SO_NHOM_GOI_Y]
    dong = []
    for v in van:
        chu = " ".join(CHU_THEO_VAN[v][:SO_CHU_GOI_Y])
        tu = " · ".join(TU_THEO_VAN.get(v, ())[:SO_TU_GOI_Y])
        dong.append(f"    -{v}: {chu}" + (f"   |  {tu}" if tu else ""))
    ds = chr(10).join(dong)
    return (
        "CHỮ VẦN CÓ THẬT. Khi bí, ĐỪNG bẻ chữ cho khớp vần — hãy lấy một chữ thật:"
        f"\n\n{ds}\n\n"
        "Đây chỉ là vài ví dụ, còn rất nhiều vần khác. Dùng vần nào cũng được, chữ nào "
        "cũng được — miễn là chữ CÓ THẬT trong tiếng Việt."
    )
