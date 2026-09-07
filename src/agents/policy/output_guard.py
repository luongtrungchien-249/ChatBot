"""OUTPUT RAILS — lop chan cuoi cung, chay tren cau tra loi TRUOC khi gui di.

Truoc 08/09/2026 tang nay KHONG TON TAI: `stages/respond.py` la mot ham di thang tu
model ra kenh chat. Moi lop phong thu cua du an deu nam o dau vao hoac trong prompt,
tuc la deu dua vao viec model chiu nghe loi. Model khong phai lop bao mat.

Da chung minh bang mot lan chay that: go "so dien thoai cua toi la 0912345678, ban
nhac lai giup toi" -> bot doc lai nguyen van. `shared/redact.py` CO san mau bat so
Viet Nam, nhung no chi chay tren log.

Bon luat, xep theo do nghiem trong cua hau qua:

  1. BI MAT      -> che cung, khong dieu kien. Mot khoa API doc ra giua nhom chat la
                    mot khoa phai thu hoi.
  2. CA NHAN     -> che CO DIEU KIEN: chi che thu bot khong nhan tu nguoi dung o luot
                    nay. Che tat ca se cho ra "so dien thoai cua ban la ***".
  3. DINH DANG   -> bo markdown. Chay TRUOC hai luat tren: neu khong, no an mat
                    chinh cac dau che.
  4. TRICH DAN   -> co <tai_lieu> trong prompt ma cau tra loi khong neu nguon nao thi
                    ghi nhan. KHONG chan — xem ghi chu o duoi.

Vi sao luat 4 khong chan: mot cau tra loi dung nhung quen trich dan van huu ich hon
mot cau bi nuot. Chan o day la doi mot loi hien thanh mot loi im lang, tuc la doi
dung huong ma ca du an nay dang chong lai. No o day de DO — biet ti le bao nhieu, roi
moi quyet dinh siet bang prompt hay bang cai gi khac.

Tang nay la THUAN: khong I/O, khong goi model. Do la ly do no test duoc va la ly do
no khong the tu hong.
"""

import re
from dataclasses import dataclass, field

from shared.secrets import (
    che_bi_mat,
    che_ca_nhan,
    tim_bi_mat,
    tim_ca_nhan,
    trich_ca_nhan,
)

#: Markdown ma Zalo khong render. Bot bi cam dung, nhung "bi cam" khong phai "khong
#: xay ra" — do duoc tren bot that: no van thinh thoang tra ve `**dam**` va `- gach`.
#:
#: Chi bo KY HIEU, giu NOI DUNG. Xoa ca dong la mat cau tra loi.
_DAM = re.compile(r"\*\*(.+?)\*\*", re.S)
_NGHIENG = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", re.S)
_MA = re.compile(r"`([^`]+)`")
_KHOI_MA = re.compile(r"```[a-zA-Z]*\n?")
#: Gach dau dong bang '-' hoac '*' o DAU DONG. Khong dung ky hieu thi doi thanh so.
_GACH_DAU_DONG = re.compile(r"^[ \t]*[-*•]\s+", re.M)
#: Tieu de markdown '# ', '## '...
_TIEU_DE = re.compile(r"^[ \t]*#{1,6}\s+", re.M)

#: Cau tra loi co trich dan hay khong. System prompt bat dang "(theo <nguon>, muc ...)".
#: Nhan rong hon mot chut de khong dem thieu: bat ky ngoac don nao chua "theo".
_CO_TRICH_DAN = re.compile(r"\(\s*theo\s+[^)]+\)", re.I)


@dataclass(frozen=True, slots=True)
class OutputVerdict:
    """Cau tra loi da qua kiem, kem danh sach thu da can thiep.

    `text` LUON dung duoc — tang nay khong bao gio tra ve rong. Mot cau tra loi bi
    che vai cho van tot hon khong co cau nao.
    """

    text: str
    #: Ten cac luat da can thiep: 'bi-mat', 'ca-nhan', 'markdown'.
    da_can_thiep: tuple[str, ...] = ()
    #: Loai bi mat tim thay — de log biet la khoa gi ma khong log chinh no.
    loai_bi_mat: tuple[str, ...] = ()
    loai_ca_nhan: tuple[str, ...] = ()
    #: Co <tai_lieu> trong prompt ma cau tra loi khong neu nguon nao.
    thieu_trich_dan: bool = False
    _unused: tuple[()] = field(default=(), repr=False)


def bo_markdown(text: str) -> str:
    """Bo ky hieu markdown, giu noi dung.

    Zalo va Messenger deu khong render markdown: nguoi dung se thay `**dam**` nguyen
    van va tuong bot loi.
    """
    text = _KHOI_MA.sub("", text)
    text = _DAM.sub(r"\1", text)
    text = _NGHIENG.sub(r"\1", text)
    text = _MA.sub(r"\1", text)
    text = _TIEU_DE.sub("", text)
    # Gach dau dong -> dau cham giua. Bo han thi hai muc dinh lien thanh mot cau.
    text = _GACH_DAU_DONG.sub("· ", text)
    return text


def co_markdown(text: str) -> bool:
    return bo_markdown(text) != text


def kiem_dau_ra(
    text: str, *, van_ban_nguoi_dung: str = "", co_tai_lieu: bool = False
) -> OutputVerdict:
    """Chay bon luat tren cau tra loi.

    `van_ban_nguoi_dung`: nguyen van cau nguoi dung vua go. Dung de biet thong tin ca
    nhan trong cau tra loi la thu ho vua noi ra (cho phep nhac lai) hay thu bot lay
    tu cho khac (phai che).

    `co_tai_lieu`: prompt lan nay co khoi <tai_lieu> khong. Chi khi do moi doi trich dan.
    """
    da_can_thiep: list[str] = []

    # BO MARKDOWN TRUOC khi che. Nguoc lai thi bo loc markdown an mat chinh cac dau
    # che, va tra lai mot chuoi trong nhu da bi cat xen. Da troi that o lan chay dau.
    if co_markdown(text):
        text = bo_markdown(text)
        da_can_thiep.append("markdown")

    loai_bi_mat = tim_bi_mat(text)
    if loai_bi_mat:
        text = che_bi_mat(text)
        da_can_thiep.append("bi-mat")

    loai_ca_nhan = tim_ca_nhan(text)
    if loai_ca_nhan:
        cho_phep = trich_ca_nhan(van_ban_nguoi_dung)
        da_che = che_ca_nhan(text, cho_phep)
        if da_che != text:
            text = da_che
            da_can_thiep.append("ca-nhan")

    thieu_trich_dan = co_tai_lieu and not _CO_TRICH_DAN.search(text)

    return OutputVerdict(
        text=text,
        da_can_thiep=tuple(da_can_thiep),
        loai_bi_mat=loai_bi_mat,
        loai_ca_nhan=loai_ca_nhan,
        thieu_trich_dan=thieu_trich_dan,
    )
