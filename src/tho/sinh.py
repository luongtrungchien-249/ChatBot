"""Vong sinh tho co KIEM TRA: sinh -> kiem luat -> sai thi noi ro sai gi -> sinh lai.

Nhan mot ham `goi_model` chu khong tu goi: giu module nay THUAN ve phu thuoc, test
duoc khong can mang, va khong rang buoc vao mot nha cung cap nao.

BA RANG BUOC, moi cai chan mot kieu hong:

  1. Gioi han so lan sinh lai. `SO_LAN_TOI_DA = 2` nghia la truong hop xau nhat ton 3
     luot goi model. Voi mot tinh nang co muc tieu GIAM LATENCY thi day la tran hop
     ly; N=5 se lam tinh nang nay thanh thu cham nhat trong bot.

  2. Noi RO sai o dau khi sinh lai. Xem `prompt.nhac_sua`.

  3. KHONG BAO GIO im lang. Het so lan ma van sai thi tra bai TOT NHAT kem mot cau noi
     thang con loi gi — dung luat "khong biet thi noi khong biet" cua SYSTEM_PROMPT.
     Tha mot bai sai luat ra ma noi la dung con te hon la khong lam tho.
"""

import asyncio
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from difflib import SequenceMatcher

from .bang_van import CHU_THEO_VAN
from .cham_diem import cham_tat_dinh
from .chon_van import (
    HUONG_DAN as HUONG_DAN_CHON_VAN,
)
from .chon_van import (
    SO_LAN_THU,
    doc_bo_van,
    yeu_cau_chon_van,
    yeu_cau_viet_bai,
)
from .luat import Loi, kiem_luc_bat, kiem_that_ngon_tu_tuyet
from .prompt import (
    _MAU_LUC_BAT,
    CAU_DAT_MAU,
    DIEM_CHON_TOI_DA,
    huong_dan_chon,
    nhac_sua,
    nhac_sua_be_chu,
    system_prompt,
    yeu_cau,
    yeu_cau_chon,
)
from .quy_trinh import SoVet, VetBuoc, VetCon, vet_kiem_luat
from .tu_vung import cum_kha_nghi, cum_nghi_be
from .y_dinh import TheTho, YeuCauTho

#: Chon CHU VAN truoc khi viet cau — DA THU VA DA TAT.
#:
#: Gia thuyet: model ep van vi no viet trai sang phai, toi vi tri van thi ca cau da
#: xong nen khong con tu do chon NGHIA. Chon chu truoc thi chu duoc chon VI NGHIA, va
#: cau xay quanh chung se khong phai nhet. Xem tho/chon_van.py.
#:
#: Do 11/09/2026 tren 5 bai «hoa sen», gpt-4o-mini, thang 100 diem:
#:
#:                   mot giai doan   hai giai doan
#:     tat dinh         38,7/45         27,9/45     <- SUP
#:     phai cham        31,0/55         29,2/55
#:     TONG            69,7/100        57,1/100     <- tut 12,6
#:     do tre p50        2.953ms         4.797ms
#:     ngon ngu          4,4/10          4,6/10     <- khong nhuc nhich
#:     sang tao          1,8/5           1,0/5      <- te hon
#:
#: Nguong nghiem thu dat o plan muc 13.1 la `ngon ngu >= 6,5` va `sang tao >= 2,5`.
#: Truot xa, VA keo sap ca phan tat dinh.
#:
#: VI SAO SAP: bai sinh ra dai 6 cau thay vi 4, va cac chu van bi dat sai vi tri. Ep
#: model dung DUNG nhung chu do o DUNG nhung cho do la them mot rang buoc CUNG vao mot
#: viec no von da lam khong xong — no khong thoa man duoc ca hai, va buong ca hai.
#:
#: Giu lai code vi gia thuyet van co ly va co the dung voi model manh hon (hoac sau
#: fine-tune). Bat bang `chon_van_truoc=True`. Nhung DUNG bat mac dinh lai ma khong do
#: lai — con so o tren la tren `gpt-4o-mini`.
CHON_VAN_TRUOC = False

#: So BAN sinh SONG SONG o luot dau.
#:
#: Ban truoc sinh 3 lan TUAN TU, do tre cong don, va do 11/09/2026 cho ket qua 0/5 —
#: ba luot goi de duoc con so khong. Sinh song song thi cung chi phi nhung:
#:
#:                   tuan tu        song song
#:     luot goi        3              3
#:     do tre        3 x 1,3s       1 x 1,3s
#:
#: DA THU 8 VA DA QUAY VE 4, ngay 11/09/2026.
#:
#: Ly do THU: do phan bo diem van cua 22 ban doc lap cho sd 4,6/20, va cong thuc
#: best-of-N tren phan bo do du bao N=8 se cho +1,7 diem.
#:
#: Ly do QUAY VE: do lai o n=20 kem khoang tin cay thi khong thay gi.
#:
#:     SO_BAN=4   van 11,67 +/- 1,57   tat dinh 34,86   p50 1.563 ms
#:     SO_BAN=8   van 11,81 +/- 1,48   tat dinh 34,93   p50 2.375 ms
#:     chenh van  +0,14 +/- 2,16   -> KHONG phan biet duoc voi nhieu
#:
#: Du bao +1,7 SAI vi cong thuc best-of-N gia dinh cac ban la DOC LAP va cung mot phan
#: bo. Ca hai deu khong dung: cac ban trong CUNG mot yeu cau dung chung prompt, chung
#: model, cung thoi diem nen tuong quan voi nhau; va phan bo 22 ban kia GOP NHIEU CHU
#: DE, tuc phuong sai do duoc phan lon la phuong sai GIUA cac chu de — thu ma viec
#: chon KHONG the thu hoach, vi moi lan chon chi chon trong mot chu de.
#:
#: Con so "+4,7 diem van" thay o lan do dau (n=6) la NHIEU thuan tuy: hai luot chay
#: CUNG cau hinh SO_BAN=8 cho van 17,1 roi 10,0.
#:
#: Va do tre thi TE HON THAT: 8 luot goi song song tranh nhau nhieu hon 4 luot.
#:
#: Nang 3 -> 4 ngay 11/09/2026 sau khi do ti le dung KHUNG cua mot ban la 65%:
#: n=3 cho 95,7% co it nhat mot ban dung khung, n=4 cho 98,5%. Cac ban chay SONG
#: SONG nen them mot ban KHONG cong do tre, chi cong ~0,0008 USD moi bai. Voi mot
#: luat BAT BUOC thi doi lay 2,8 diem phan tram do la dang.
#:     xac suat dat  P(sua duoc)    1 - (1-p)^3
#:
#: Bon lan sinh doc lap nen xac suat co mot ban dat cao hon han mot ban roi sua hai
#: lan — nhat la khi phep do cho thay viec SUA gan nhu khong an.
SO_BAN = 4

#: Loai loi thuoc KHUNG cua the tho — so tieng va so cau.
#:
#: Day la LUAT CUNG, khong phai diem tru: mot "cau bat" 7 tieng khong phai cau bat.
#: Van sai thi bai van con la luc bat, doc van xuoi. Sai khung thi khong.
#:
#: Nen moi phep chon ban o duoi deu xep hang theo (so loi KHUNG, so loi con lai), chu
#: khong dem gop. Do 11/09/2026 tren 20 ban `gpt-4o-mini`: 65% ban dung khung, nhung
#: 0% dung ca van — dem gop thi mot ban DUNG khung sai 6 van se thua mot ban SAI khung
#: sai 1 van, va ta tra ra dung cai ban khong phai luc bat.
LOI_KHUNG = frozenset({"so_tieng", "so_cau"})


def _xep_hang(loi: list[Loi], bai: str = "") -> tuple[int, int, int, int]:
    """Khoa sap xep: (CHEP, loi KHUNG, cum BI BE, loi con lai). Nho hon la tot hon.

    Thu tu tu dien, khong phai tong. Ba ly do cho thu tu nay:

      - CHEP dat truoc het: mot bai chep lai ca dao khong phai bai bot lam ra, va tra
        no ve nhu tho minh vua lam la noi doi. Mot bai sai luat thi con la bai cua no.
      - loi KHUNG nang hon moi thu con lai: sai van thi bai VAN la luc bat, sai so
        tieng thi khong.
      - CUM BI BE dat TREN loi van, va day la cho quan trong nhat.

    VI SAO CUM BI BE PHAI TREN LOI VAN. Do 12/09/2026 tren mot bai that:

        Như dòng nước chảy trong cao
        Tỏa hương thanh khiết ngọt ngao nụ cười

    "ngọt ngao" la "ngọt ngào" bi be mat dau huyen, de van voi "cao". Bai do duoc cham
    VAN 20/20 TUYET DOI — dung vi model da be chu cho khop van.

    Tuc truoc thay doi nay, khau chon dang THUONG cho hanh vi pha nghia: ban be chu se
    co diem van cao hon va THANG ban giu chu dung ma lech mot van. Dat cum bi be len
    tren loi van la dao nguoc dung cai dong luc do.

    `bai` de rong thi khong xet chep va khong xet be — dung khi chi co danh sach loi.
    """
    khung = sum(1 for x in loi if x.loai in LOI_KHUNG)
    if not bai:
        return 0, khung, 0, len(loi) - khung
    return so_cau_chep(bai), khung, len(cum_nghi_be(bai)), len(loi) - khung

#: Co dem loi VAN di sua khong.
#:
#: TAT, va day la ket luan da DO theo CAP — cung mot ban goc, mot ban de nguyen, mot
#: ban dem di sua mot vong. Do 11/09/2026, 10 bai, `gpt-4o-mini`:
#:
#:     tot hon      1/10
#:     khong doi    3/10
#:     TE HON       6/10   (mot ca con lam hong ca khung 6-8)
#:     van trung binh  8,8/20 -> 7,1/20   (-1,7)
#:     ton them        p50 1.969 ms
#:
#: Luat "giu ban tot nhat" ngay duoi da chan 6 ca te hon, nen san pham khong hong. Cai
#: no khong chan duoc la DO TRE: hai giay bi tieu tren MOI bai, ke ca 9/10 bai ma vong
#: sua khong dem lai gi. Loi ich ky vong that:
#:
#:     +2,9/20 x 1/10 = +0,3/20 diem  doi lay ~2 giay moi bai
#:
#: PHEP DO NAY KHAC phep do cu o plan-nang-chat-luong-tho muc 16. Cai cu cung ket luan
#: "sua khong an", nhung no chay khi bo kiem van dang bao sai 30% — tuc no do mot vong
#: sua dang nhan MENH LENH RAC. Sau khi sua bo kiem van (xem docs/plan-sua-bo-kiem-van.md)
#: phep do duoc lam lai tu dau, va lan nay ket luan dung tren du lieu sach.
#:
#: Loi KHUNG thi VAN sua — xem `SO_LAN_SUA_KHUNG`. Khung la luat bat buoc, va o do mot
#: vong goi model them la dang gia.
SUA_LOI_VAN = False

#: So vong SUA sau khi da chon ban tot nhat. Mot vong.
#:
#: Hai vong khong duoc gi them: do 11/09 cho thay sua khong an, va moi vong la mot
#: lan cong do tre vao dung tinh nang dat muc tieu GIAM do tre.
SO_LAN_SUA = 1

#: So vong sua THEM, chi cap khi KHUNG van con sai sau cac vong thuong.
#:
#: Khung la luat bat buoc, con van thi khong — nen dang de danh rieng cho no mot vong.
#: Vong nay gan nhu khong bao gio chay: sau khi xep hang theo khung tren 4 ban, xac
#: suat ca 4 ban cung sai khung la ~1,5% (do 11/09/2026: 65% moi ban). Tuc no khong
#: cong do tre vao 98,5% so luot, va chi bung ra o dung nhung luot dang hong.
SO_LAN_SUA_KHUNG = 1

#: So vong sua danh rieng cho CHU BI BE ("ngọt ngào" -> "ngọt ngao").
#:
#: Tach rieng khoi `SO_LAN_SUA` vi day la loi NGHIA, khong phai loi luat, va no co mot
#: cach sua RAT CU THE: ta biet chac tu that la gi, nen goi dich danh no ra. Cung co
#: che da dua khung 6-8 len 100% (`danh_so_tieng`).
#:
#: Vong nay hiem khi chay: do 12/09/2026 tren 40 chu de x 4 ban, chi 2 ban duoc chon co
#: cum bi be, va khau LOC o duoi da xu ly ca hai. No chi bung ra khi CA BON ban deu be.
SO_LAN_SUA_BE = 1

#: Cau noi them khi het luot ma van sai. KHONG im lang — nguoi dung phai biet.
CON_LOI = "\n\n(Mình chưa chỉnh được hết luật: {loi}.)"

#: Cau noi khi sai KHUNG — nang hon han, va phai noi nang hon han.
#:
#: Sai van thi bai van la luc bat, chi la doc khong xuoi. Sai so tieng thi no KHONG
#: PHAI luc bat: mot "cau bat" 7 tieng khong phai cau bat. Dung chung mot cau
#: "chua chinh duoc het luat" cho ca hai la noi giam mot loi hong the loai thanh mot
#: loi nho — nguoi dung se tuong minh dang cam mot bai luc bat.
CON_LOI_KHUNG = (
    "\n\n(Bài này CHƯA đúng thể lục bát: {loi}. "
    "Lục bát bắt buộc câu 6 tiếng xen câu 8 tiếng, mình chưa làm đúng được khung đó.)"
)

GoiModel = Callable[[str, list[str]], Awaitable[str]]
"""(system_prompt, cac luot nguoi dung) -> van ban model tra ve."""


@dataclass(frozen=True, slots=True)
class KetQua:
    bai_tho: str
    #: Loi CON LAI sau lan sinh cuoi. Rong = dung luat (theo tang dang ep).
    con_loi: tuple[Loi, ...]
    #: So lan goi model. Dung de theo doi chi phi va latency that.
    so_lan_goi: int
    #: Loi bang-trac — ghi lai de theo doi, KHONG chan. Xem `EP_BANG_TRAC`.
    loi_bang_trac: tuple[Loi, ...] = ()
    #: VET cua 10 buoc lam tho. Xem tho/quy_trinh.py.
    #:
    #: Mac dinh RONG va la truong cuoi cung: them no khong bat cho goi nao phai sua, va
    #: `tra_loi()` khong dung toi no — vet la thu de NGUOI PHAT TRIEN doc, khong phai
    #: thu gui cho nguoi dung.
    vet: tuple[VetBuoc, ...] = ()


#: Co EP luat bang-trac khong.
#:
#: TAT, va day la ket luan da DO duoc chu khong phai de cho de tinh.
#:
#: Bo kiem tra bang-trac DUNG: no cho 0% bao loi gia tren Truyen Kieu va ca dao (xem
#: ops/hieu_chuan_tho.py). Van de nam o phia model. Do 11/09/2026, mot luot sinh moi
#: bai, khong sinh lai:
#:
#:                        so tieng   + van    + bang-trac
#:     gpt-4o-mini (n=8)    6/8       0/8       0/8
#:     gpt-5-mini  (n=1)    1/1       1/1       0/1
#:
#: KHONG model nao lam duoc bang-trac — 0/9 tren ca hai. Dem tieng thi duoc, hiep van
#: thi kho, con thanh dieu theo vi tri 4-6-8 thi khong.
#:
#: Hau qua neu VAN EP: moi bai deu ton du 3 luot goi model roi VAN sai, tuc 3 lan chi
#: phi va 3 lan do tre de doi lay mot cau "minh chua chinh duoc het luat" — dung luc
#: tinh nang nay dat muc tieu GIAM do tre. Do la mot san pham te hon han.
#:
#: Bang-trac VAN duoc kiem va VAN duoc ghi log (xem `KetQua.loi_bang_trac`), chi la
#: no khong chan. Bat lai khi nao co model lam duoc — hoac khi da fine-tune.
EP_BANG_TRAC = False


#: Co goi NGUOI CHAM de xep hang cac ban khong.
#:
#: VI SAO CAN: cho chon ban truoc day xep hang bang `_xep_hang` — tuc CHI dem loi luat,
#: va MU hoan toan voi `ngon ngu` va `sang tao`. Mot ban day "nhe dieu", "lap lo" ma
#: dung van hon se thang mot ban hay hon han.
#:
#: Do 11/09/2026 khi nang SO_BAN 4 -> 8 da lam lo dieu do ra rat ro:
#:
#:                  SO_BAN=4    SO_BAN=8
#:     van            12,4/20     17,1/20   <- ep chon manh hon tren LUAT
#:     ngon ngu        5,5/10      3,7/10   <- va no CHON dung nhung bai hy sinh nghia
#:     TONG           69,1/100    68,9/100  <- dung yen
#:
#: Sinh nhieu hon ma van xep hang bang thuoc cu thi chi doi vần lay ngôn ngữ. Ap luc
#: chon phai dat dung len thu ta muon.
#:
#: Day la CHON, khong phai SUA — dung co che da do duoc la an (sinh song song: van
#: 7,9 -> 12,5), khong phai co che da do duoc la phan tac dung (vong sua: 6/10 te hon).
#: NGUOI CHAM PHAI LA MODEL KHAC model lam tho. Truyen qua `cham_model`; khong truyen
#: thi buoc nay bi bo qua hoan toan.
#:
#: Do 11/09/2026 voi `gpt-4o-mini` lam nguoi cham — HAI thiet ke prompt, ca hai hong:
#:
#:     "chấm nghiêm"              -> 26-38/40, trung binh 81%, khong phan biet
#:     neo thang, tru theo cum    -> diem GIONG HET nhau trong cung chu de
#:
#: Trong khi nguoi cham cua evals/metrics/tho_hay.py PHAN BIET duoc (`ngon ngu`
#: 3,7-5,5/10 qua cac luot) — va no chay route `summarize` = gpt-5-mini.
#:
#: Bai hoc: mot vong CHON chi tot bang NGUOI CHON. Chon bang mot nguoi cham khong phan
#: biet duoc thi khong phai "chon khong an" — la chua chon gi ca.
#:
#: DA THU BA LAN VA DA TAT. Nguong nghiem thu (plan-van-ngon-ngu-sang-tao muc 5):
#: `ngon ngu >= 6,5`, `sang tao >= 2,5`, `p50 <= 3.500 ms`.
#:
#:                              ngon ngu  sang tao  van   TONG   p50
#:     khong chon (SO_BAN=8)       3,7      1,2    17,1   68,9   1.750 ms
#:     cham gpt-4o-mini "nghiem"   4,0      1,7    14,8   69,4   3.156 ms
#:     cham gpt-4o-mini, neo thang  —        —      —      —     (diem giong het nhau)
#:     cham gpt-5-mini             4,8      1,5    11,0   67,2  24.609 ms  <- +23 GIAY
#:
#: Truot ca ba nguong o ban tot nhat. Va con so quan trong hon moi nguong: NGAY CA khi
#: nguoi cham phan biet duoc (gpt-5-mini), `ngon ngu` cung chi len 4,8 — trong khi no
#: DOI 6,1 diem van va 23 giay.
#:
#: KET LUAN: chon khong tao ra duoc chat luong KHONG CO SAN trong cac ban. Phuong sai
#: cua `van` lon (sd 4,6/20) nen chon an manh o do; phuong sai cua `ngon ngu` thi
#: khong — moi ban deu tam thuong nhu nhau ve ngon ngu, va chon ban "it te nhat" trong
#: tam ban tam thuong van ra mot bai tam thuong.
#:
#: Muon nang `ngon ngu` thi phai nang chinh PHAN BO — tu dien de bat chu vo nghia, hoac
#: few-shot. Xem plan muc 4.2 va 4.3.
#:
#: Bat lai bang `chon_bang_nguoi_cham=True` VA truyen `cham_model`. Nhung DUNG bat mac
#: dinh lai ma khong do lai.
CHON_BANG_NGUOI_CHAM = False

#: `n|<so cum vo nghia>|<diem>`. Chap nhan khoang trang thua va so thap phan.
#:
#: Cot GIUA bat buoc phai co, va no khong duoc dung de tinh diem. No ton tai de BUOC
#: nguoi cham dem cum vo nghia TRUOC khi cho diem — "chi dich danh roi moi ket luan",
#: co che da an hai lan trong du an. Bo cot do di thi nguoi cham quay ve cho 81%.
_DONG_DIEM = re.compile(
    r"^\s*(\d+)\s*\|\s*\d+\s*\|\s*(\d+(?:[.,]\d+)?)\s*$", re.MULTILINE
)


def doc_diem_chon(raw: str, so_ban: int) -> list[float] | None:
    """Doc `n|<diem>` thanh list dai dung `so_ban`. Doc khong duoc -> None.

    Doi DU so dong. Thieu mot dong nghia la nguoi cham bo qua mot ban, va doan lay
    phan con lai se cho ra mot bang xep hang trong nhu that — dung loi da mac bon lan
    trong ba ngay (xem plan-truy-hoi-xuyen-ngon-ngu.md).
    """
    if so_ban <= 0:
        return None
    thay: dict[int, float] = {}
    for khop in _DONG_DIEM.finditer(raw):
        i = int(khop.group(1))
        if 1 <= i <= so_ban:
            # Kep vao thang: nguoi cham hay tu bia thang rieng.
            thay[i] = max(0.0, min(float(DIEM_CHON_TOI_DA), float(khop.group(2).replace(",", "."))))
    if len(thay) != so_ban:
        return None
    return [thay[i] for i in range(1, so_ban + 1)]


async def _xep_hang_bang_cham(
    ung_vien: list[tuple[str, list[Loi]]], cham_model: GoiModel
) -> tuple[list[float] | None, int]:
    """Diem nguoi cham cho tung ban. (diem, so lan goi model).

    MOT lan goi cho TAT CA cac ban, khong phai moi ban mot lan: xep hang can so sanh
    chung voi nhau, va mot lan goi thi re hon N lan va cong it do tre hon han.
    """
    raw = await cham_model(huong_dan_chon(), [yeu_cau_chon([b for b, _ in ung_vien])])
    return doc_diem_chon(raw, len(ung_vien)), 1


#: Nguong coi mot cau la CHEP tu bai mau.
#:
#: 0,80 dat vao giua mot KHOANG TRONG do duoc, khong phai mot con so chon bua. Do
#: 11/09/2026 tren 10 chu de:
#:
#:     tho THAT, khong chep     do giong cao nhat 58%
#:     ban chep                 89% - 100%
#:
#: 89% la truong hop model doi dung MOT chu ("chảy ra" -> "tuôn ra") — van la chep.
#: Khoang 58%-89% trong tron, nen nguong o 0,80 vua bat het ca chep vua khong cham
#: vao tho that. Nguong 0,95 bo lot dung truong hop doi mot chu.
NGUONG_CHEP = 0.80

#: MOI cau tho co mat trong prompt — bai mau CONG cau vi du CAU DAT.
#:
#: `CAU_DAT_MAU` phai co mat o day. Prompt v3 da day: them tho vao prompt ma khong chan
#: thi model chep no, va muc tang do duoc hoa ra la diem cua ca dao.
_CAU_MAU: tuple[str, ...] = (
    *(c.strip().lower() for m in _MAU_LUC_BAT for c in m.split(chr(10)) if c.strip()),
    CAU_DAT_MAU.strip().lower(),
)


def so_cau_chep(bai: str) -> int:
    """So cau CHEP gan nguyen tu bai mau trong prompt.

    VI SAO CAN, va vi sao bang CODE chu khong bang loi dan trong prompt:
    do 11/09/2026 tren 10 chu de, prompt v3.1 (bon bai ca dao lam mau):

        chu de "cha mẹ"          -> chep 4/4 cau cua bai mau, giong 100%
        chu de "công ơn cha mẹ"  -> chep 4/4 cau, giong 100%
        tam chu de con lai       -> khong chep (giong nhat 58%, la trung tu binh thuong)

    Tuc chep CHI xay ra khi de bai trung chu de voi mot bai mau — nhung luc do no chep
    NGUYEN BAI. Bai «cha mẹ» cham duoc 76,4/100, va phan lon so diem do la cua Nguyen
    Du... khong, cua ca dao. Tra ve nhu tho minh vua lam la noi doi.

    Loi dan "đừng chép" co trong prompt, nhung prompt khong CUONG CHE duoc gi — cung ly
    do vi sao luat tho nam o `luat.py` chu khong nam trong cau chu. Xem docstring
    module do.
    """
    dem = 0
    for cau in bai.split(chr(10)):
        c = cau.strip().lower()
        if not c:
            continue
        if any(SequenceMatcher(None, c, m).ratio() >= NGUONG_CHEP for m in _CAU_MAU):
            dem += 1
    return dem


def _kiem(the_tho: TheTho, bai: str) -> list[Loi]:
    """Loi CHAN: nhung loi bat phai sinh lai."""
    if the_tho == "luc_bat":
        return kiem_luc_bat(bai, kiem_bang_trac=EP_BANG_TRAC)
    return kiem_that_ngon_tu_tuyet(bai, kiem_bang_trac=EP_BANG_TRAC)


def _loi_bang_trac(the_tho: TheTho, bai: str) -> tuple[Loi, ...]:
    """Loi bang-trac — GHI LAI de theo doi, khong chan."""
    if EP_BANG_TRAC:
        return ()
    day_du = (
        kiem_luc_bat(bai) if the_tho == "luc_bat" else kiem_that_ngon_tu_tuyet(bai)
    )
    return tuple(x for x in day_du if x.loai == "bang_trac")


#: So CAP 6-8 toi thieu de con goi la mot bai tho.
#:
#: Mot cap (6 + 8) van la luc bat dung luat — ca dao day nhung bai hai cau. Nhung cat
#: mot bai tam cau xuong con hai cau thi thu tra ve khong con la thu nguoi dung xin.
#: Duoi nguong nay thi tha noi that la chua lam duoc.
CAP_TOI_THIEU = 2


def _cat_ve_khung_dung(bai: str) -> str | None:
    """Bo nhung cap 6-8 SAI, giu nguyen thu tu nhung cap dung. None = khong cuu duoc.

    Thu ca hai cach ghep cap: bat dau tu cau 1, va bat dau tu cau 2. Mot dong thua lot
    vao dau bai (model hay them mot dong tua de) lam LECH toan bo cac cap phia sau —
    luc do ghep tu cau 2 cuu duoc ca bai, con ghep tu cau 1 thi hong het.
    """
    cau = [d.strip() for d in bai.strip().split(chr(10)) if d.strip()]

    tot: list[str] = []
    for bat_dau in (0, 1):
        giu: list[str] = []
        i = bat_dau
        while i + 1 < len(cau):
            luc, bat = cau[i], cau[i + 1]
            if len(luc.split()) == 6 and len(bat.split()) == 8:
                giu += [luc, bat]
            i += 2
        if len(giu) > len(tot):
            tot = giu

    if len(tot) < CAP_TOI_THIEU * 2:
        return None
    return chr(10).join(tot)


def _sach(bai: str) -> str:
    """Bo dong trong thua va khoang trang hai dau. Model hay them dong trong."""
    return "\n".join(d.strip() for d in bai.strip().split("\n") if d.strip())


async def _chon_van_truoc(chu_de: str, goi_model: GoiModel) -> tuple[str | None, int]:
    """Giai doan 1. Tra (yeu cau cho giai doan 2, so lan goi model).

    Tra None o phan tu dau khi khong chon duoc bo van dung — luc do goi y la BO QUA
    giai doan nay va viet mot mach nhu cu. Mot bo van hong con te hon khong co bo van
    nao: no ep model dat nhung chu KHONG hiep van vao dung vi tri van.
    """
    so_lan = 0
    for _ in range(SO_LAN_THU + 1):
        try:
            raw = await goi_model(HUONG_DAN_CHON_VAN, [yeu_cau_chon_van(chu_de)])
        except Exception:
            return None, so_lan
        so_lan += 1
        bo = doc_bo_van(raw)
        if bo is not None:
            return yeu_cau_viet_bai(bo, chu_de), so_lan
    return None, so_lan


async def sinh_tho(
    the_tho: TheTho,
    chu_de: str,
    goi_model: GoiModel,
    *,
    so_ban: int = SO_BAN,
    so_lan_sua: int = SO_LAN_SUA,
    so_lan_sua_khung: int = SO_LAN_SUA_KHUNG,
    so_lan_sua_be: int = SO_LAN_SUA_BE,
    chon_bang_nguoi_cham: bool = CHON_BANG_NGUOI_CHAM,
    cham_model: GoiModel | None = None,
    chon_van_truoc: bool = CHON_VAN_TRUOC,
) -> KetQua:
    """Sinh mot bai tho dung luat, hoac bai tot nhat lam duoc kem loi con lai.

    Cac giai doan:
      0. (chi luc bat, `chon_van_truoc=True`) chon CHU VAN truoc khi viet cau;
      1. sinh `so_ban` ban SONG SONG, cham luat het, lay ban it loi nhat;
      1b. (`chon_bang_nguoi_cham`) trong cac ban DUNG KHUNG, goi nguoi cham xep hang
          theo thu bo kiem tra tat dinh khong nhin thay — chu ghep vo nghia, hinh anh,
          cau dat — roi chon theo THANG 100 that;
      2. ban do con sai KHUNG thi sua, co VE RA cho sai;
      3. van sai khung thi CAT ve nhung cap 6-8 dung.
    """
    so = SoVet()

    # ================= BUOC 1: xac dinh yeu cau =================
    with so.do("yeu_cau", "luat") as g:
        yc = YeuCauTho(the_tho=the_tho, chu_de=chu_de)
        ten_the = "lục bát" if the_tho == "luc_bat" else "thất ngôn tứ tuyệt"
        g.tom_tat = (
            f"thể {ten_the} · chủ đề {chu_de or '(model tự chọn)'} · "
            f"thông điệp {yc.thong_diep or '(không suy được)'}"
        )

    sys_prompt = system_prompt(the_tho)
    dau_bai = yeu_cau(chu_de)
    so_lan_goi = 0

    # ================= BUOC 2: lap y / mach cam xuc =================
    #
    # CHUA THI CONG, va vet phai noi that dieu do. Da co mot ban thu gan giong ("so
    # tay" — bat model tu ghi y truoc khi viet, trong CUNG mot luot): ngon ngu 4,75 ->
    # 4,78, tuc chim trong nhieu. Ban lam thanh mot LUOT RIENG chua duoc do lan nao va
    # nam o §5 (B1) cua docs/plan-quy-trinh-10-buoc.md.
    so.bo_qua(
        "lap_y",
        "model",
        "chưa thi công — mạch ý hiện nằm trong prompt (mục CẢM XÚC), không phải lượt gọi riêng",
    )

    # ================= BUOC 3: chon hinh anh & tu khoa =================
    #
    # HAI GIAI DOAN, chi cho luc bat. Xem docstring cua tho/chon_van.py: bao model
    # "dung ep van" khong an vi van de nam o THU TU SINH, khong o chi dan.
    #
    # That ngon tu tuyet chua lam vi cau truc van cua no khac (cuoi cau 1-2-4) va chua
    # do duoc gi tren the do — them mot duong chua kiem chung la them mot cho hong.
    hai_giai_doan = the_tho == "luc_bat" and chon_van_truoc
    with so.do("hinh_anh", "model" if hai_giai_doan else "luat") as g:
        if hai_giai_doan:
            yeu_cau_moi, them = await _chon_van_truoc(chu_de, goi_model)
            so_lan_goi += them
            g.so_lan_goi = them
            if yeu_cau_moi is not None:
                dau_bai = yeu_cau_moi
            g.tom_tat = "chọn CHỮ VẦN trước khi viết câu" + (
                "" if yeu_cau_moi is not None else " — không đọc được bộ vần, dùng đề bài gốc"
            )
        elif the_tho == "luc_bat":
            # Nua CO: bang van goi y trong system_prompt. Nua CHUA CO: hinh anh.
            g.tom_tat = (
                f"gợi ý VẦN từ bảng {len(CHU_THEO_VAN)} nhóm (trong system prompt); "
                "phần HÌNH ẢNH chưa thi công"
            )
        else:
            g.tom_tat = "thất ngôn tứ tuyệt chưa có bảng vần"

    # ================= BUOC 4-6: sinh cau · gieo van · noi mach =================
    #
    # Ba buoc nay chay TRONG CUNG MOT luot goi model. Vet ghi ra ca ba de so do khong
    # thieu o nao, nhung chi buoc 4 mang so gio va so luot goi — neu khong thi tong o
    # cuoi bang se dem mot luot goi ba lan.
    #
    # Tach chung thanh ba luot rieng la viec KHONG lam, co chu dinh: sinh tung cau mot
    # thi model mat ngu canh ca bai, va do dung la co che da lam `CHON_VAN_TRUOC` hong
    # (69,7 -> 57,1). Xem §6 cua docs/plan-quy-trinh-10-buoc.md.
    with so.do("sinh_cau", "model") as g:
        ban = await asyncio.gather(
            *(goi_model(sys_prompt, [dau_bai]) for _ in range(max(1, so_ban))),
            return_exceptions=True,
        )
        ung_vien: list[tuple[str, list[Loi]]] = []
        for b in ban:
            so_lan_goi += 1
            g.so_lan_goi += 1
            if isinstance(b, BaseException):
                continue
            bai = _sach(b)
            if bai:
                ung_vien.append((bai, _kiem(the_tho, bai)))
        g.tom_tat = f"{len(ung_vien)}/{max(1, so_ban)} bản sinh song song dùng được"

        if not ung_vien:
            # Moi ban deu hong. Nem ra de cho goi biet — tra ve mot KetQua rong se lam
            # su co ha tang trong y het mot bai tho te.
            loi_dau = next((b for b in ban if isinstance(b, BaseException)), None)
            raise loi_dau or RuntimeError("khong sinh duoc ban nao")

    so.ghi_kem("gieo_van", "model", "gieo vần cùng lúc với việc viết câu, trong lượt gọi ở bước 4")
    so.ghi_kem("noi_mach", "model", "nối mạch cùng lúc với việc viết câu, trong lượt gọi ở bước 4")

    # Xep hang theo KHUNG truoc. Truoc 11/09/2026 cho nay dem gop moi loai loi lam
    # mot, va hau qua do duoc tren 6 bai chay that: 0/6 bai dung khung, trong khi 65%
    # so ban sinh ra von da dung khung. Ta co san ban dat va da tu chon ban hong.
    tot_nhat, loi_tot_nhat = min(ung_vien, key=lambda x: _xep_hang(x[1], x[0]))

    # ================= BUOC 7: kiem tra luat =================
    #
    # Kiem da chay roi — no chay tren TUNG ban ngay trong buoc 4, va chinh no quyet
    # dinh ban nao duoc chon. O day chi SUY RA bon muc ①②③④ tu ket qua do, khong goi
    # lai bo kiem: goi lai la do mot thu khac voi cai da dung de chon.
    #
    # Vet nay mo ta BAN NHAP — dung nhu so do cua nguoi dung ("sau khi tao ban nhap,
    # can kiem tra"). Trang thai CUOI CUNG nam o vet buoc 10.
    with so.do("kiem_luat", "luat") as g:
        g.chi_tiet = vet_kiem_luat(tot_nhat, loi_tot_nhat, _loi_bang_trac(the_tho, tot_nhat))
        g.tom_tat = (
            f"bản nháp tốt nhất trong {len(ung_vien)} bản · còn {len(loi_tot_nhat)} lỗi chặn"
        )

    # KHUNG la bo loc CUNG, dat truoc moi phep xep hang khac: mot ban khong phai luc
    # bat thi hay den may cung khong dung duoc.
    sach_khung = [x for x in ung_vien if _xep_hang(x[1])[1] == 0]

    # ================= BUOC 8: kiem noi dung & cam xuc =================
    #
    # THI CONG DUOC MOT PHAN, va vet phai noi ro phan nao:
    #   co   — chu bi BE cho du van ("ngọt ngào" -> "ngọt ngao"): bo do tat dinh, chan
    #   co   — chep bai mau trong prompt: tat dinh
    #   CHUA — mach noi dung (cau 1 noi cha, cau 3 dot nhien noi bien)
    #
    # Muc thu ba la thu nguoi dung neu dich danh. No nam o §5 (B3) cua plan, va se thu
    # bang LUAT truoc chu khong bang nguoi cham: nguoi cham da hong ba lan (+23 giay,
    # 21/30 luot timeout).
    #
    # --- 1a. LOC CUNG: bo cac ban co CHU BI BE ---
    #
    # "chi duoc chon lua cac tu co y nghia" — nen ban co "ngọt ngao" bi loai han khoi
    # vong chon, khong phai chi bi xep hang thap hon.
    #
    # Chi loc khi CON ban nao sach: het sach thi giu nguyen danh sach, roi de vong sua
    # o tang 2 lo. Loc den rong la tu bo mat moi lua chon.
    #
    # DUNG `cum_kha_nghi` (chat, bao nham 0,03%) CHU KHONG `cum_nghi_be` (rong, 4,70%).
    # Day la mot ranh gioi co that, khong phai cach noi:
    #
    #     CHAN  bao nham mot lan la loai han mot bai tot, khong lay lai duoc
    #           -> doi bo do phai gan nhu khong bao gio sai
    #     CHON  bao nham chi doi thu tu uu tien giua cac ban; xau nhat la lay mot ban
    #           tuong duong  -> chiu duoc bo do nhieu
    #
    # Nen bo do rong nam o `_xep_hang` (chon), bo do chat nam o day (chan).
    with so.do("kiem_noi_dung", "luat") as g:
        be_truoc = [x for x in ung_vien if cum_kha_nghi(x[0])]
        sach_be = [x for x in ung_vien if not cum_kha_nghi(x[0])]
        if sach_be:
            ung_vien = sach_be
            sach_khung = [x for x in sach_khung if not cum_kha_nghi(x[0])] or sach_khung
            tot_nhat, loi_tot_nhat = min(ung_vien, key=lambda x: _xep_hang(x[1], x[0]))
        chep = so_cau_chep(tot_nhat)
        con_be = cum_kha_nghi(tot_nhat)
        g.chi_tiet = (
            VetCon(
                ten="chữ bị bẻ cho đủ vần",
                dat=not con_be,
                tom_tat=(
                    f"loại {len(be_truoc)}/{len(be_truoc) + len(sach_be)} bản có chữ bị bẻ"
                    if not con_be
                    else "MỌI bản đều bẻ chữ: "
                    + "; ".join(f"'{a}' (chắc là '{b}')" for a, b in con_be)
                ),
            ),
            VetCon(
                ten="chép bài mẫu",
                dat=chep == 0,
                tom_tat="không chép câu nào" if chep == 0 else f"chép {chep} câu của bài mẫu",
            ),
            VetCon(
                ten="mạch nội dung",
                # None, KHONG phai True. Chua co bo do nao cho muc nay — bao "dat" o
                # day la dung cai loi da lam hong hai phep do truoc day.
                dat=None,
                tom_tat="chưa thi công — không kiểm được mạch ý giữa các câu",
            ),
        )
        g.tom_tat = f"{len(ung_vien)} bản qua được bộ lọc cứng"

    # --- 1b. Xep hang bang NGUOI CHAM ---
    #
    # Chi chay khi con NHIEU HON MOT ban sach khung — mot ban thi khong co gi de chon,
    # va mot luot goi model de xac nhan dieu do la lang phi thuan.
    if chon_bang_nguoi_cham and len(sach_khung) > 1 and cham_model is not None:
        try:
            diem, them = await _xep_hang_bang_cham(sach_khung, cham_model)
        except Exception:
            diem, them = None, 0
        so_lan_goi += them
        if diem is not None:
            # Thang 100 that: tat dinh (45) + nguoi cham (40). `nhip` (15) nam ngoai
            # vi no can tu dien tu ghep — xem DIEM_CHON_TOI_DA.
            tot_nhat, loi_tot_nhat = max(
                zip(sach_khung, diem, strict=True),
                key=lambda x: cham_tat_dinh(x[0][0]).tong + x[1],
            )[0]
        # `diem is None` -> nguoi cham hong. GIU nguyen ban da chon theo luat: mot su
        # co ha tang khong duoc bien thanh mot bai tho te.
        #
        # Vong nay THUOC buoc 8 (chon theo noi dung) nhung nam sau bo loc cung, ngoai
        # khoi `so.do`. Cong luot goi vao dung vet do de tong trong vet khong dem thieu.
        so.them_goi("kiem_noi_dung", them, f"người chấm xếp hạng {len(sach_khung)} bản")

    # ================= BUOC 9: chinh sua cau chu =================
    #
    # Ba tang, deu da co tu truoc: sua KHUNG (2), sua CHU BI BE (2b), va luoi cuoi CAT
    # ve nhung cap dung (3). Tang 3 la tat dinh, hai tang dau goi model.
    #
    # Vet ghi lai bai TRUOC khi sua de so sanh duoc — day la buoc ma so do cua nguoi
    # dung goi la "rat quan trong", va cung la buoc co lich su do te nhat trong du an:
    # `SUA_LOI_VAN` tat vi 6/10 lan sua lam bai TE HON.
    truoc_sua = tot_nhat
    loi_truoc_sua = list(loi_tot_nhat)
    goi_truoc_sua = so_lan_goi
    t_sua = time.monotonic()

    # --- 2. Sua ban tot nhat ---
    for lan in range(so_lan_sua + so_lan_sua_khung):
        if not loi_tot_nhat:
            break
        # Het loi KHUNG roi thi dung, tru khi `SUA_LOI_VAN` duoc bat. Sua loi van
        # ton ~2 giay moi bai de doi lay +0,3/20 diem ky vong — xem `SUA_LOI_VAN`.
        if _xep_hang(loi_tot_nhat)[1] == 0 and not (SUA_LOI_VAN and lan < so_lan_sua):
            break
        luot = [dau_bai, tot_nhat, nhac_sua(tot_nhat, loi_tot_nhat)]
        try:
            bai = _sach(await goi_model(sys_prompt, luot))
        except Exception:
            break
        so_lan_goi += 1
        if not bai:
            break
        loi = _kiem(the_tho, bai)
        # Giu ban TOT NHAT, khong phai ban cuoi: sua khong bao dam tot hon, va tra ve
        # mot ban te hon ban truoc la lam nguoi dung thiet. "Tot nhat" xep theo KHUNG
        # truoc — mot ban sua xong dung khung thi lay, du no sai them mot van.
        if _xep_hang(loi, bai) < _xep_hang(loi_tot_nhat, tot_nhat):
            tot_nhat, loi_tot_nhat = bai, loi

    # --- 2b. Sua CHU BI BE ---
    #
    # Den day van con cum bi be nghia la MOI ban deu be. Goi dich danh tung chu va bat
    # viet lai ca cau — doi lai chinh ta thi hong van, nen va mot chu la vo ich.
    for _ in range(so_lan_sua_be):
        be = cum_kha_nghi(tot_nhat)
        if not be:
            break
        luot = [dau_bai, tot_nhat, nhac_sua_be_chu(tot_nhat, be)]
        try:
            bai = _sach(await goi_model(sys_prompt, luot))
        except Exception:
            break
        so_lan_goi += 1
        if not bai:
            break
        loi = _kiem(the_tho, bai)
        # Chi nhan ban sua khi no vua HET be vua KHONG lam hong khung.
        if not cum_kha_nghi(bai) and _xep_hang(loi)[1] == 0:
            tot_nhat, loi_tot_nhat = bai, loi

    # --- 3. Luoi cuoi: khung van sai thi CAT ve nhung cap dung ---
    #
    # Chi cho luc bat. That ngon tu tuyet co DUNG 4 cau nen cat di la khong con la tu
    # tuyet — o the do khong co gi de cat.
    if the_tho == "luc_bat" and _xep_hang(loi_tot_nhat)[1] > 0:
        cat = _cat_ve_khung_dung(tot_nhat)
        if cat is not None:
            loi_cat = _kiem(the_tho, cat)
            # Chi lay ban cat khi no THAT SU chua duoc khung. Cat xong van sai khung
            # thi giu ban goc: ban goc it ra con nguyen y cua no.
            if _xep_hang(loi_cat)[1] == 0:
                tot_nhat, loi_tot_nhat = cat, loi_cat

    # Dong vet buoc 9. Ghi CA khi khong sua gi — "khong can sua" la mot ket qua, va
    # giau no di se lam nguoi doc tuong buoc 9 chua duoc thi cong.
    doi = tot_nhat != truoc_sua
    so.ghi(
        "chinh_sua",
        "model",
        ms=(time.monotonic() - t_sua) * 1000,
        so_lan_goi=so_lan_goi - goi_truoc_sua,
        tom_tat=(
            f"đổi bản: còn {len(loi_tot_nhat)} lỗi chặn (trước khi sửa {len(loi_truoc_sua)})"
            if doi
            else "không sửa gì — bản nháp đã tốt nhất, hoặc mọi bản sửa đều tệ hơn"
        ),
    )

    # ================= BUOC 10: xuat ban =================
    #
    # Vet nay mo ta bai CUOI CUNG, doi lai voi vet buoc 7 (mo ta ban nhap).
    loi_bt = _loi_bang_trac(the_tho, tot_nhat)
    with so.do("xuat_ban", "luat") as g:
        g.chi_tiet = vet_kiem_luat(tot_nhat, loi_tot_nhat, loi_bt)
        so_cau = len([d for d in tot_nhat.split(chr(10)) if d.strip()])
        # Noi ro co kem cau bao loi khong: `tra_loi()` gan them mot cau khi con loi, va
        # do la thu nguoi dung nhin thay. Xem luat "khong bao gio im lang" o dau tep.
        g.tom_tat = (
            f"{so_cau} câu · "
            + ("sạch luật, trả thẳng bài thơ" if not loi_tot_nhat else
               f"còn {len(loi_tot_nhat)} lỗi — `tra_loi()` sẽ nói thẳng lỗi còn lại")
        )

    return KetQua(
        bai_tho=tot_nhat,
        con_loi=tuple(loi_tot_nhat),
        so_lan_goi=so_lan_goi,
        loi_bang_trac=loi_bt,
        vet=so.xong(),
    )


def tra_loi(ket_qua: KetQua) -> str:
    """Van ban cuoi cung gui cho nguoi dung."""
    if not ket_qua.con_loi:
        return ket_qua.bai_tho
    # Chi neu MOT loi dai dien: liet ke ba bon dong loi luat vao khung chat la thu
    # khong ai doc, va no bien mot bai tho thanh mot bao cao loi.
    #
    # Loi KHUNG duoc uu tien neu ra, va dung mot cau nang hon: no la loi duy nhat lam
    # bai thoi khong con la luc bat.
    khung = next((x for x in ket_qua.con_loi if x.loai in LOI_KHUNG), None)
    x = khung or ket_qua.con_loi[0]
    mau = CON_LOI_KHUNG if khung is not None else CON_LOI
    return ket_qua.bai_tho + mau.format(loi=f"câu {x.cau} {x.mo_ta}")
