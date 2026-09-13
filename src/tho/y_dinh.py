"""Nhan ra yeu cau LAM THO, truoc khi vao vong ReAct.

VI SAO BANG TU KHOA, KHONG BANG MODEL: goi model de quyet co goi model khong la cong
THANG mot luot goi vao MOI tin nhan — ke ca loi chao. Mot yeu cau lam tho co hinh dang
rat de nhan; khong can toi mot model 26B de biet "lam cho minh bai luc bat" la yeu cau
lam tho.

SAI THI PHAI SAI AN TOAN. Khong nhan ra -> roi ve luong cu, bot van tra loi duoc, chi
la khong qua duong chuyen. Nhan nham -> bot lam tho khi nguoi ta hoi quy dinh, va do
la kieu hong te hon nhieu. Nen moi mau o day deu doi MOT DONG TU SANG TAC di kem, chu
khong bat moi cau co chu "tho".

Lien quan toi chan 7 trong agents/pipeline/stages/generate.py: yeu cau lam tho khong
duoc di qua chan do. No la cau KHONG CO DU KIEN — khong co tai lieu nao de tra, va tra
cung vo nghia. Xem docs/plan-lam-tho-va-tu-host.md muc 1.
"""

import re
from dataclasses import dataclass
from typing import Literal, TypeAlias

TheTho = Literal["luc_bat", "that_ngon_tu_tuyet"]


@dataclass(frozen=True, slots=True)
class YeuCauTho:
    the_tho: TheTho
    #: Phan con lai cua cau — chu de nguoi dung muon. Rong thi model tu chon.
    chu_de: str

    @property
    def thong_diep(self) -> str:
        """NOI DUNG CAN TRUYEN TAI, suy tu chu de. Rong = khong suy duoc.

        Buoc 1 cua quy trinh (docs/plan-quy-trinh-10-buoc.md) tach yeu cau thanh BON
        phan, trong do co "noi dung can truyen tai" — o day la phan thu tu do.

        LA MOT THUOC TINH SUY RA, khong phai mot truong: no la ham cua `chu_de`, nen
        luu rieng se tao ra hai nguon su that co the lech nhau. Va vi no suy ra, khong
        cho goi nao phai sua.

        SUY BANG BANG TU KHOA, khong bang model — cung ly do voi `nhan_dien`: them mot
        luot goi model vao MOI yeu cau lam tho de doi lay mot dong mo ta la cai gia
        khong dang. Khong khop thi tra RONG chu khong doan bua: mot thong diep sai con
        te hon khong co thong diep, vi no se dan bai tho di nham huong.

        Giai doan A CHI dung truong nay de HIEN THI trong vet. Dua no vao prompt la
        viec cua giai doan B (§5 plan), va phai tra bang mot phep do A/B.
        """
        cd = self.chu_de.lower()
        for tu_khoa, thong_diep in _THONG_DIEP:
            if any(t in cd for t in tu_khoa):
                return thong_diep
        return ""


#: Chu de -> noi dung can truyen tai. Doi khop THEO THU TU, cai dau tien khop thi lay.
#:
#: Thu tu co y nghia: "người con gái Việt Nam xưa" khop ca "việt nam" lan "con gái", va
#: cai dung hon la "con gái" — nen no phai dung TRUOC. Moi lan them dong moi phai nghi
#: xem no chen len cai gi.
#:
#: Bang nay CO CHU DICH nho: no khong co tham vong phu het moi chu de tieng Viet. Chu de
#: khong khop thi tra rong, va vet se ghi "không suy được" — dung nhu su that.
_THONG_DIEP: tuple[tuple[tuple[str, ...], str], ...] = (
    (("cha", "mẹ", "phụ mẫu", "sinh thành"), "công ơn sinh thành, lòng hiếu thảo"),
    (("thầy", "cô giáo", "trường", "dạy dỗ"), "ơn dạy dỗ, nhớ trường xưa"),
    (("nguồn", "cội", "biết ơn", "uống nước", "tổ tiên", "ông bà"),
     "lòng biết ơn, nhớ người đi trước"),
    (("con gái", "thiếu nữ", "người đẹp", "giai nhân"), "vẻ đẹp và nết người"),
    (("quê", "làng", "xa nhà", "cố hương"), "tình quê, nỗi nhớ nhà"),
    (("bạn", "tri kỷ"), "tình bạn, nghĩa gắn bó"),
    (("tình yêu", "người thương", "nhớ nhung"), "tình yêu và nỗi nhớ"),
    (("đất nước", "non sông", "tổ quốc", "việt nam", "quê hương"), "tình yêu đất nước"),
    (("xuân", "hạ", "thu", "đông", "mùa", "trăng", "hoa", "mưa", "nắng", "sen"),
     "cảnh vật, và tâm trạng gửi trong cảnh"),
    (("lao động", "công việc", "nghề"), "giá trị của lao động"),
)


@dataclass(frozen=True, slots=True)
class KhongPhaiTho:
    pass


YDinh: TypeAlias = YeuCauTho | KhongPhaiTho

#: Dong tu bao hieu YEU CAU SANG TAC. Bat buoc phai co mot trong so nay.
#:
#: Khong co nhom nay thi "bai tho nay hay qua" hay "quy dinh ve tho ca cong ty" cung
#: roi vao nhanh lam tho.
_SANG_TAC = r"(?:làm|viết|sáng\s*tác|soạn|cho\s+(?:mình|tôi|tớ|em)|giúp)"

#: Ten the tho. `lục bát` va `thất ngôn tứ tuyệt` la tin hieu manh nhat.
_LUC_BAT = r"lục\s*bát"
_TNTT = r"(?:thất\s*ngôn\s*tứ\s*tuyệt|tứ\s*tuyệt|thất\s*ngôn)"

_MAU_LUC_BAT = re.compile(rf"{_SANG_TAC}[^.\n]{{0,40}}?{_LUC_BAT}", re.IGNORECASE)
_MAU_TNTT = re.compile(rf"{_SANG_TAC}[^.\n]{{0,40}}?{_TNTT}", re.IGNORECASE)

#: "lam mot bai tho" khong noi the gi -> mac dinh luc bat.
#:
#: Luc bat la the pho thong nhat va de doc nhat voi nguoi Viet. Chon mac dinh thay vi
#: hoi lai: luat "lam truoc, hoi sau" trong SYSTEM_PROMPT cam hoi lai gan nhu tuyet
#: doi, va o day ta co mot mac dinh hop ly chu khong phai dang bi ket.
_MAU_THO_CHUNG = re.compile(rf"{_SANG_TAC}[^.\n]{{0,30}}?\bbài\s+thơ\b", re.IGNORECASE)

#: Cat phan chu de ra khoi cau — CHI tim o phan SAU ten the tho.
#:
#: KHONG co "cho" trong danh sach nay, va do la mot ca da sai that: "làm CHO mình bài
#: lục bát về mùa thu" bi cat tu chu "cho" dau tien, cho ra chu de
#: "mình bài lục bát về mùa thu". "cho" xuat hien trong chinh cum dong tu sang tac
#: ("làm cho mình", "viết cho tớ") nen no khong dung lam moc duoc.
_DAN_CHU_DE = re.compile(
    r"\b(?:về|chủ\s*đề|nói\s*về|tả|nhân\s*dịp|mừng|tặng)\b\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)


#: Cat NOT nhung dan con sot lai o DAU chu de.
#:
#: `_DAN_CHU_DE` chi cat MOT dan. Voi "về chủ đề uống nước nhớ nguồn" no cat "về" roi
#: dung, cho ra chu de "chủ đề uống nước nhớ nguồn" — va de bai gui len model thanh
#: "Chủ đề: chủ đề uống nước nhớ nguồn".
#:
#: Loi nay chay am tham nhieu ngay. No lo ra khi vet buoc 1 bat dau in chu de ra man
#: hinh (xem tho/quy_trinh.py) — dung cai ma mot quy trinh quan sat duoc dung de lam.
_DAU_THUA = re.compile(
    r"^(?:về|chủ\s*đề|nói\s*về|tả|đề\s*tài|là)\b[\s:,-]*",
    re.IGNORECASE,
)


def _chu_de(text: str, tu_vi_tri: int) -> str:
    """Chu de nam SAU ten the tho. Tim tu truoc do se vo phai cum dong tu sang tac."""
    khop = _DAN_CHU_DE.search(text, tu_vi_tri)
    if khop is None:
        return ""
    cd = khop.group(1).strip().rstrip(".!?")
    # Lap, khong phai mot lan: "về chủ đề về mùa thu" co ba dan chong nhau. Co tran de
    # mot mau benh hoan khong bien thanh vong lap vo tan.
    for _ in range(3):
        moi = _DAU_THUA.sub("", cd).strip()
        if moi == cd:
            break
        cd = moi
    return cd


def nhan_dien(text: str) -> YDinh:
    """Van ban da BOC MENTION, y het `parse_command`."""
    cau = text.strip()
    if not cau:
        return KhongPhaiTho()

    # The tho cu the duoc uu tien hon mau chung: "lam bai tho luc bat" phai ra
    # luc_bat chu khong phai mac dinh.
    uu_tien: tuple[tuple[re.Pattern[str], TheTho], ...] = (
        (_MAU_TNTT, "that_ngon_tu_tuyet"),
        (_MAU_LUC_BAT, "luc_bat"),
    )
    for mau, the in uu_tien:
        khop = mau.search(cau)
        if khop is not None:
            return YeuCauTho(the_tho=the, chu_de=_chu_de(cau, khop.end()))

    khop = _MAU_THO_CHUNG.search(cau)
    if khop is not None:
        return YeuCauTho(the_tho="luc_bat", chu_de=_chu_de(cau, khop.end()))
    return KhongPhaiTho()
