"""VET cua quy trinh lam tho: 10 buoc, moi buoc mot dong doc duoc bang mat.

VI SAO CO TEP NAY. Quy trinh lam tho cua du an nay von da co 7/10 buoc trong so do ma
nguoi dung mo ta (docs/plan-quy-trinh-10-buoc.md §1) — nhung khong buoc nao co TEN, va
khong ai nhin thay duoc buoc nao da chay, buoc nao chua. Mot quy trinh khong quan sat
duoc thi khong sua duoc: bon thi nghiem truoc day (CHON_VAN_TRUOC, vong sua, nguoi cham,
so tay) deu phai dung mot script do rieng moi biet chuyen gi xay ra ben trong.

DIEU MODULE NAY KHONG LAM, va day la ranh gioi quan trong nhat:

    no KHONG doi mot byte nao duoc gui len model.

Vet chi GHI LAI nhung gi da chay. Do la ly do no khong co rui ro ve chat luong va gan
nhu khong co rui ro ve do tre — va cung la ly do no duoc lam TRUOC ba chang model moi o
§5 cua plan, vi ba chang do thi co rui ro that.

BA LUAT CUA MOT VET, ca ba deu sinh ra tu loi da tung mac trong du an nay:

  1. KHONG GIA VO CO. Buoc chua thi cong thi ghi `da_chay=False` kem ly do, khong im
     lang bo qua. Mot so do 10 o ma 3 o rong la mot so do that; mot so do 10 o deu xanh
     trong khi 3 o khong ton tai la mot so do noi doi.

  2. KHONG NHAM "KHONG BIET" VOI "DAT". `kiem_nhip` tra None nghia la khong phat hien
     duoc gi — khong phai dung nhip. Day chinh la lop loi `None` vs `0.0` da lam hong
     hai phep do trong du an nay (mot lan cham van ban bao het ngan sach nhu tho, mot
     lan trung binh cac bai CHUA duoc cham).

  3. SO LUOT GOI TRONG VET PHAI BANG SO LUOT GOI THAT. Vet ma lech voi thuc te thi no
     con hai hon khong co vet. Co test ghim dieu nay.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import Literal, TypeAlias

from .luat import Loi, kiem_nhip

#: Muoi buoc, DUNG thu tu nguoi dung mo ta. Xem docs/plan-quy-trinh-10-buoc.md.
Buoc: TypeAlias = Literal[
    "yeu_cau",  # 1. Xac dinh yeu cau
    "lap_y",  # 2. Xac dinh cac y tuong chinh
    "hinh_anh",  # 3. Chon hinh anh va tu khoa
    "sinh_cau",  # 4. Xay dung cau luc
    "gieo_van",  # 5. Xay dung cau bat va gieo van
    "noi_mach",  # 6. Tiep tuc phat trien mach noi dung
    "kiem_luat",  # 7. Kiem tra luat luc bat
    "kiem_noi_dung",  # 8. Kiem tra noi dung va cam xuc
    "chinh_sua",  # 9. Chinh sua cau chu
    "xuat_ban",  # 10. Xuat ban bai tho
]

#: Thu tu chuan. `vet_du_10_buoc` doi dung day nay, khong thieu khong lech.
THU_TU: tuple[Buoc, ...] = (
    "yeu_cau",
    "lap_y",
    "hinh_anh",
    "sinh_cau",
    "gieo_van",
    "noi_mach",
    "kiem_luat",
    "kiem_noi_dung",
    "chinh_sua",
    "xuat_ban",
)

#: Ten tieng Viet de in ra. Khoa trung voi `Buoc`.
TEN_BUOC: dict[Buoc, str] = {
    "yeu_cau": "Xác định yêu cầu",
    "lap_y": "Lập ý / mạch cảm xúc",
    "hinh_anh": "Chọn hình ảnh & từ khóa",
    "sinh_cau": "Xây câu lục",
    "gieo_van": "Xây câu bát & gieo vần",
    "noi_mach": "Phát triển mạch nội dung",
    "kiem_luat": "Kiểm tra luật lục bát",
    "kiem_noi_dung": "Kiểm tra nội dung & cảm xúc",
    "chinh_sua": "Chỉnh sửa câu chữ",
    "xuat_ban": "Xuất bản",
}

#: Ten DE RIENG cho that ngon tu tuyet — nhung buoc ma ten mac dinh se NOI SAI.
#:
#: `TEN_BUOC` viet theo luc bat vi do la the mac dinh va la the ma nguoi dung mo ta quy
#: trinh. Nhung in "Xay cau luc" hay "Kiem tra luat luc bat" khi dang lam mot bai that
#: ngon tu tuyet la mot cau SAI, va mot bang vet ma noi sai thi mat het gia tri — cung
#: ly do voi luat 2 o dau tep.
TEN_TNTT: dict[Buoc, str] = {
    "sinh_cau": "Xây câu thơ",
    "gieo_van": "Gieo vần cuối câu 1-2-4",
    "kiem_luat": "Kiểm tra luật tứ tuyệt",
}

#: Ai chiu trach nhiem mot buoc: code TAT DINH hay mot luot goi model.
#:
#: Phan biet nay khong phai de trang tri. Cai gi `luat` lam thi lap lai duoc, test duoc,
#: khong ton tien va khong timeout; cai gi `model` lam thi khong. Moi lan mot buoc doi
#: tu `luat` sang `model` la mot lan du an nhan them rui ro, va no phai nhin thay duoc.
AiLam: TypeAlias = Literal["luat", "model"]


@dataclass(frozen=True, slots=True)
class VetCon:
    """Mot muc kiem nho trong mot buoc — dung cho bon muc ①②③④ cua buoc 7.

    `dat` la ba trang thai chu khong phai hai: `None` nghia la KHONG KIEM DUOC, khac
    han voi `False` (kiem roi, sai). Xem luat 2 o dau tep.
    """

    ten: str
    dat: bool | None
    tom_tat: str


@dataclass(frozen=True, slots=True)
class VetBuoc:
    buoc: Buoc
    ai_lam: AiLam
    #: False = buoc co TEN nhung chua thi cong / dang tat. `tom_tat` phai noi ly do.
    da_chay: bool
    ms: float
    so_lan_goi: int
    tom_tat: str
    #: Ten hien thi. Mang theo trong vet chu khong tra cuu luc IN ra: the tho quyet dinh
    #: ten, ma `bang_vet` thi khong biet the tho — nen tra cuu luc in se lai in sai.
    ten: str
    chi_tiet: tuple[VetCon, ...] = ()


@dataclass(slots=True)
class _Ghi:
    """Cho de than ham dien ket qua vao trong luc no dang chay."""

    tom_tat: str = ""
    so_lan_goi: int = 0
    chi_tiet: tuple[VetCon, ...] = ()


@dataclass(slots=True)
class SoVet:
    """So ghi vet, truyen doc theo mot luot sinh tho."""

    _vet: list[VetBuoc] = field(default_factory=list)
    #: Ten de rieng, de len tren `TEN_BUOC`. Rong = dung ten mac dinh (luc bat).
    ten_rieng: dict[Buoc, str] = field(default_factory=dict)

    def _ten(self, buoc: Buoc) -> str:
        return self.ten_rieng.get(buoc) or TEN_BUOC[buoc]

    @contextmanager
    def do(self, buoc: Buoc, ai_lam: AiLam) -> Iterator[_Ghi]:
        """Chay than ham, do gio, roi ghi mot vet.

        Ghi vet ca khi than ham NEM RA. Mot buoc hong van la mot buoc da chay, va do
        dung la luc nguoi doc vet can nhin thay no nhat.
        """
        ghi = _Ghi()
        t0 = time.monotonic()
        try:
            yield ghi
        finally:
            self._vet.append(
                VetBuoc(
                    buoc=buoc,
                    ai_lam=ai_lam,
                    da_chay=True,
                    ms=(time.monotonic() - t0) * 1000,
                    so_lan_goi=ghi.so_lan_goi,
                    tom_tat=ghi.tom_tat,
                    ten=self._ten(buoc),
                    chi_tiet=ghi.chi_tiet,
                )
            )

    def ghi_kem(self, buoc: Buoc, ai_lam: AiLam, noi: str) -> None:
        """Buoc DA CHAY nhung chay chung trong mot buoc khac, khong tach rieng duoc.

        Buoc 4, 5, 6 nam trong dung MOT luot goi model. Ghi ca ba de so do khong thieu
        o nao, nhung hai o sau mang gio 0 va so luot goi 0 — neu khong thi tong o cuoi
        bang se dem mot luot goi thanh ba. `noi` phai chi ro no chay chung voi cai gi.
        """
        self._vet.append(
            VetBuoc(
                buoc=buoc,
                ai_lam=ai_lam,
                da_chay=True,
                ms=0.0,
                so_lan_goi=0,
                tom_tat=noi,
                ten=self._ten(buoc),
            )
        )

    def ghi(
        self,
        buoc: Buoc,
        ai_lam: AiLam,
        *,
        ms: float,
        so_lan_goi: int,
        tom_tat: str,
        chi_tiet: tuple[VetCon, ...] = (),
    ) -> None:
        """Ghi mot vet voi so gio TU DO lay.

        Dung khi chang trai dai qua nhieu khoi lenh long nhau ma boc bang `do()` se
        phai thut lai ca tram dong ma da on — cu the la buoc 9, gom ba tang sua noi
        tiep nhau. Thut lai ma dang chay dung de lay mot dong hien thi la doi gia dat
        hon gia tri nhan duoc.
        """
        self._vet.append(
            VetBuoc(
                buoc=buoc,
                ai_lam=ai_lam,
                da_chay=True,
                ms=ms,
                so_lan_goi=so_lan_goi,
                tom_tat=tom_tat,
                ten=self._ten(buoc),
                chi_tiet=chi_tiet,
            )
        )

    def them_goi(self, buoc: Buoc, n: int, ghi_chu: str) -> None:
        """Cong them luot goi vao mot vet DA ghi, va noi vi sao.

        Dung cho chang chay NGOAI khoi `do()` nhung thuoc ve buoc do — cu the la vong
        nguoi cham (1b), no thuoc buoc 8 nhung nam sau bo loc cung trong ma nguon.

        Neu khong co ham nay thi luat 3 o dau tep bi pha: nguoi cham dang tat nen hom
        nay khong ai thay, va den ngay ai do bat no len thi vet se am tham dem thieu.
        """
        if n <= 0:
            return
        for i, v in enumerate(self._vet):
            if v.buoc == buoc:
                self._vet[i] = replace(
                    v,
                    so_lan_goi=v.so_lan_goi + n,
                    tom_tat=f"{v.tom_tat} · {ghi_chu}",
                )
                return

    def bo_qua(self, buoc: Buoc, ai_lam: AiLam, ly_do: str) -> None:
        """Ghi mot buoc CHUA chay. Bat buoc co ly do — xem luat 1 o dau tep."""
        self._vet.append(
            VetBuoc(
                buoc=buoc,
                ai_lam=ai_lam,
                da_chay=False,
                ms=0.0,
                so_lan_goi=0,
                tom_tat=ly_do,
                ten=self._ten(buoc),
            )
        )

    def xong(self) -> tuple[VetBuoc, ...]:
        return tuple(self._vet)


def vet_kiem_luat(
    bai: str,
    loi: list[Loi],
    loi_bang_trac: tuple[Loi, ...],
    the_tho: str = "luc_bat",
) -> tuple[VetCon, ...]:
    """Bon muc ①②③④ cua buoc 7, SUY RA tu ket qua kiem da co.

    KHONG goi lai bo kiem. Suy tu `loi` nghia la vet khong the lech voi thuc te; goi
    lai nghia la vet do mot thu khac voi cai da dung de chon bai.

    VI SAO SUY O DAY CHU KHONG TACH TRONG `luat.py`: plan §7 buoc 3 noi tach trong
    `luat.py`. Lam vay phai doi chu ky `kiem_luc_bat` — mot ham thuan, da hieu chuan
    tren Truyen Kieu, co hang chuc test ghim. Doi no de lay mot dong hien thi la doi
    gia qua dat. Suy ra o day cho dung ket qua ma khong cham vao ma da on.
    """
    so_tieng = [x for x in loi if x.loai in ("so_tieng", "so_cau")]
    van = [x for x in loi if x.loai == "van"]
    # `_kiem` chay voi `EP_BANG_TRAC=False` nen loi bang-trac khong nam trong `loi` —
    # no di duong rieng qua `_loi_bang_trac`, duoc GHI LAI chu khong chan. Vet phai noi
    # dung dieu do, neu khong nguoi doc se tuong bai da dat luat bang-trac.
    bang_trac = [x for x in loi if x.loai == "bang_trac"] or list(loi_bang_trac)

    # Noi dung KHUNG cho dung the. "dung khung 6-8" tren mot bai that ngon tu tuyet la
    # mot cau SAI, va sai ngay trong cai bang duoc dung de kiem tra su that.
    khung = "6-8" if the_tho == "luc_bat" else "7 chữ"
    cau = [d.strip() for d in bai.strip().split("\n") if d.strip()]
    gay = [(i, kiem_nhip(c)) for i, c in enumerate(cau, 1)]
    gay_that = [(i, v) for i, v in gay if v is not None]
    co_dau_phay = any("," in c or ";" in c for c in cau)

    return (
        VetCon(
            ten="① số tiếng",
            dat=not so_tieng,
            tom_tat=(
                f"{len(cau)} câu, đúng khung {khung}"
                if not so_tieng
                else f"{len(so_tieng)} lỗi: "
                + "; ".join(f"câu {x.cau} {x.mo_ta}" for x in so_tieng)
            ),
        ),
        VetCon(
            ten="② vần",
            dat=not van,
            tom_tat=(
                ("mạch vần liền, không đứt" if the_tho == "luc_bat" else "hiệp vần đủ")
                if not van
                else f"{len(van)} chỗ đứt: " + "; ".join(f"câu {x.cau} {x.mo_ta}" for x in van)
            ),
        ),
        VetCon(
            ten="③ thanh điệu",
            dat=not bang_trac,
            # Noi thang la KHONG CHAN. Xem `EP_BANG_TRAC` trong sinh.py: khong model nao
            # lam duoc bang-trac (0/9 tren ca hai model), nen ep chi ton luot goi.
            tom_tat=(
                "không lệch bằng-trắc (ghi lại, không chặn)"
                if not bang_trac
                else f"{len(bang_trac)} chỗ lệch (ghi lại, KHÔNG chặn): "
                + "; ".join(f"câu {x.cau} {x.mo_ta}" for x in bang_trac[:2])
            ),
        ),
        VetCon(
            ten="④ nhịp",
            # None khi ca bai khong co dau phay nao: luc do khong co gi de kiem, va noi
            # "dat" la noi doi. Xem docstring `kiem_nhip`.
            dat=(None if not co_dau_phay else not gay_that),
            tom_tat=(
                "không có dấu phẩy nào — KHÔNG kiểm được nhịp"
                if not co_dau_phay
                else "dấu phẩy đều rơi vào chỗ ngắt chẵn"
                if not gay_that
                else "gãy nhịp: " + "; ".join(f"câu {i} phẩy sau tiếng {v}" for i, v in gay_that)
            ),
        ),
    )


def mot_dong(vet: tuple[VetBuoc, ...]) -> str:
    """Ca 10 buoc go gon vao MOT chuoi, du de vao mot dong log co cau truc.

    `!` = buoc chua chay. `xN` = so luot goi model. Chi buoc nao ton gio moi hien gio.

    Vi sao can dang gon: `bang_vet` dai 14 dong — hop de doc bang mat trong ops/, khong
    hop de ghi vao moi luot lam tho o production. Dang gon nay cho phep tim trong log
    "luot nao co buoc 9 goi model" ma khong phai bat them mot he thong tracing nao.
    """
    phan: list[str] = []
    for i, v in enumerate(vet, 1):
        x = f"{i}{v.buoc}"
        if not v.da_chay:
            x += "!"
        if v.so_lan_goi:
            x += f"x{v.so_lan_goi}"
        if v.ms >= 1.0:
            x += f"({v.ms:.0f}ms)"
        phan.append(x)
    return " ".join(phan)


def _danh_dau(v: VetBuoc) -> str:
    if not v.da_chay:
        return "-"
    if not v.chi_tiet:
        return "·"
    if any(c.dat is False for c in v.chi_tiet):
        return "x"
    if any(c.dat is None for c in v.chi_tiet):
        return "?"
    return "v"


def bang_vet(vet: tuple[VetBuoc, ...]) -> str:
    """In 10 buoc ra man hinh. Chi dung trong ops/ va test — khong gui cho nguoi dung."""
    dong: list[str] = []
    for i, v in enumerate(vet, 1):
        ai = "luật " if v.ai_lam == "luat" else "MODEL"
        gio = f"{v.ms:7.1f}ms" if v.da_chay else "      -- "
        goi = f" x{v.so_lan_goi}" if v.so_lan_goi else "   "
        dong.append(
            f"{_danh_dau(v)} {i:2}. {v.ten:<28} {ai} {gio}{goi}  {v.tom_tat}"
        )
        for c in v.chi_tiet:
            dau = "v" if c.dat is True else "x" if c.dat is False else "?"
            dong.append(f"      {dau} {c.ten:<26} {c.tom_tat}")
    tong_ms = sum(v.ms for v in vet)
    tong_goi = sum(v.so_lan_goi for v in vet)
    dong.append(f"       tổng {tong_ms:.0f} ms · {tong_goi} lượt gọi model")
    return "\n".join(dong)
