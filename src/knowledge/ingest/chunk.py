"""Cat tai lieu thanh chunk theo RANH GIOI NGU NGHIA.

Day la bien so anh huong chat luong tra loi nhieu hon ca viec chon embedding model
(master-plan section 3.1). Cat cung theo so ky tu se xe doi mot cau, va chunk do
tra ve trong ket qua tim kiem se khong tu giai thich duoc no dang noi ve cai gi.

Thu tu uu tien: tieu de (markdown '#') -> doan van -> cau. Chi cat cung khi mot
doan don le da dai hon ca tran.

Chong lan (overlap) ton tai vi mot cau tra loi hay nam vat qua ranh gioi hai chunk:
cau hoi khop chunk sau, nhung dieu kien cua no lai o cuoi chunk truoc.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from agents.prompt.budget import CHARS_PER_TOKEN
from infra.logger import get_logger
from shared.chunk_text import chunk_text

from .clean import trang_cua
from .profiles import HoSo, nhan_dien

_log = get_logger()

#: 500-800 token/chunk, overlap 100 (master-plan section 3.1). Quy ra ky tu bang
#: cung mot ti le ma prompt budget dung — do bang ops/calibrate_tokens.py.
TARGET_TOKENS = 700
OVERLAP_TOKENS = 100

TARGET_CHARS = int(TARGET_TOKENS * CHARS_PER_TOKEN)
OVERLAP_CHARS = int(OVERLAP_TOKENS * CHARS_PER_TOKEN)

_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Chunk:
    ord: int
    #: Duong dan tieu de day du: "Chuong 2 > Chinh sach hoan tien". Di vao cot
    #: `section` de trich dan chi dung cho, va di vao `embed_input` de chunk tu noi
    #: duoc no nam o dau.
    section: str | None
    content: str
    #: So trang cua cho chunk BAT DAU. None khi tai lieu khong co trang (.md/.docx)
    #: hoac khi khong doc duoc so trang in tren tai lieu.
    page: int | None = None

    #: Vi tri va do dai cua PHAN GOC (truoc khi ap chong lan) trong van ban nguon.
    #: Khong ghi vao CSDL — chi dung de tinh do phu va suy ra so trang.
    #:
    #: Ton tai vi mot ly do cu the: sau khi ap chong lan, `content` KHONG con la mot
    #: lat cat lien tuc cua van ban (duoi manh truoc bi lstrip roi noi bang '\n'),
    #: nen `text.find(content)` truot. Do phu tinh bang cach do tung do sai 54,7%
    #: tren mot tai lieu khong mat mot ky tu nao.
    bat_dau: int = 0
    dai_goc: int = 0


@dataclass(frozen=True, slots=True)
class _Section:
    path: str | None
    body: str
    #: Vi tri bat dau cua `body` trong van ban goc. Can de suy ra so trang; khong co
    #: no thi phai di tim lai chuoi trong van ban, ma chunk co chong lan nen tim lai
    #: se ra sai cho.
    bat_dau: int = 0


def _split_by_heading(text: str) -> list[_Section]:
    """Cat theo tieu de markdown, giu DUONG DAN tieu de (cha > con)."""
    matches = list(_HEADING.finditer(text))
    if not matches:
        return [_Section(path=None, body=text, bat_dau=0)]

    sections: list[_Section] = []
    # Phan van ban truoc tieu de dau tien (loi noi dau, muc luc...) van phai giu.
    if matches[0].start() > 0:
        tho = text[: matches[0].start()]
        head = tho.strip()
        if head:
            sections.append(_Section(path=None, body=head, bat_dau=tho.index(head)))

    stack: list[str] = []
    for i, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        del stack[level - 1 :]
        stack.append(title)

        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        tho = text[match.end() : end]
        body = tho.strip()
        if body:
            sections.append(
                _Section(
                    path=" > ".join(stack),
                    body=body,
                    bat_dau=match.end() + tho.index(body),
                )
            )
    return sections


def _split_by_profile(text: str, ho_so: HoSo) -> list[_Section]:
    """Cat theo MOC lap cua ho so, dung khi tai lieu khong co tieu de markdown.

    Cung hinh dang ket qua nhu `_split_by_heading` de phan con lai cua chunker khong
    phai biet muc nay den tu dau. Khac mot cho: cau truc o day PHANG (khong co cha >
    con), vi mot mau lap khong noi len quan he long nhau.
    """
    khop = list(ho_so.moc.finditer(text))
    if not khop:
        return [_Section(path=None, body=text, bat_dau=0)]

    sections: list[_Section] = []
    # Phan truoc moc dau tien (loi noi dau, muc luc, cac chuong khong phai cong thuc)
    # van phai giu — bo di la mat mot phan tai lieu ma khong ai bao.
    tho = text[: khop[0].start()]
    dau = tho.strip()
    if dau:
        sections.append(_Section(path=None, body=dau, bat_dau=tho.index(dau)))

    # Tieu de LIEN NHAU (khong co than o giua) duoc GOP lam mot.
    #
    # Tai lieu song ngu dat ten mon hai lan lien tiep — ban tieng Viet roi ban tieng
    # Anh. Cat thanh hai muc se cho ra mot muc RONG mang ten tieng Viet, va toan bo
    # noi dung roi vao muc tieng Anh. Gop lai thi `section` mang CA HAI ten, tuc cau
    # hoi bang ca hai thu tieng deu khop duoc o duong BM25.
    cho: list[str] = []
    for i, m in enumerate(khop):
        cho.append(m.group(1).strip())
        het = khop[i + 1].start() if i + 1 < len(khop) else len(text)
        tho = text[m.start() : het]
        than = tho.strip()
        if not than or than == m.group(1).strip():
            continue  # tieu de khong co than — de danh, gop vao tieu de ke tiep
        sections.append(
            _Section(
                path=" / ".join(cho),
                body=than,
                bat_dau=m.start() + tho.index(than),
            )
        )
        cho = []
    return _chan_muc_qua_dai(sections)


#: Mot muc duoc phep trai dai toi da may chunk truoc khi ta thoi tin cai ten cua no.
#:
#: Moc lap cua ho so danh dau cho BAT DAU cua mot muc, khong danh dau cho KET THUC.
#: Nen muc cuoi cung an het phan duoi tai lieu, va phan duoi tai lieu thuong khong
#: phai cong thuc nua: cookbook tieng Anh het cong thuc o trang 67 roi chuyen sang
#: bai tham khao (`All About Chocolate`, `Spice Guide`, `Toys, Stuff, and Other
#: Thingies`) — nhung bai do khong mang byline `... from the ... dept.` nen khong
#: sinh moc moi.
#:
#: Hau qua do duoc 10/09/2026: `Cameron s Spice Stew` mang 35 chunk, tuc 20% ca kho,
#: trong khi moi muc khac <= 5. Bot trich kien thuc bao quan so co la kem "mục
#: Cameron s Spice Stew" — mot cai nhan SAI, va nhan do di thang vao trich dan lan
#: vao danh sach ung vien ma cong cu dua cho nguoi dung chon.
#:
#: Do dai than muc, do tren ca hai tai lieu that:
#:
#:     cookbook tieng Anh   trung vi 1.172   p90 3.352   lon nhat THAT 8.995
#:     booklet Sa Pa        trung vi 1.057   p90 2.646   lon nhat THAT 5.230
#:     Cameron s Spice Stew                              62.482   <- gap 53 lan trung vi
#:
#: 5 chunk = 12.600 ky tu: bo lot muc hop le dai nhat (8.995) mot cach thoai mai, va
#: cat dung mot ca benh. Vuot tran thi phan du KHONG bi vut di — no thanh mot muc
#: KHONG TEN. "Khong biet muc nao" la mot cau tra loi trung thuc; "Cameron s Spice
#: Stew" thi khong.
_TRAN_MUC_CHUNKS = 5


def _chan_muc_qua_dai(sections: list[_Section]) -> list[_Section]:
    """Muc dai bat thuong thi CHI phan dau duoc giu ten."""
    tran = _TRAN_MUC_CHUNKS * TARGET_CHARS
    ra: list[_Section] = []
    for muc in sections:
        if muc.path is None or len(muc.body) <= tran:
            ra.append(muc)
            continue

        cat = muc.body.rfind("\n\n", 0, tran)
        if cat <= 0:
            cat = muc.body.rfind("\n", 0, tran)
        if cat <= 0:
            cat = tran

        con_lai = muc.body[cat:].strip()
        ra.append(_Section(path=muc.path, body=muc.body[:cat].strip(), bat_dau=muc.bat_dau))
        if con_lai:
            ra.append(
                _Section(
                    path=None,
                    body=con_lai,
                    bat_dau=muc.bat_dau + muc.body.index(con_lai, cat),
                )
            )
    return ra


def _with_overlap(pieces: list[str]) -> list[str]:
    """Noi duoi chunk truoc vao dau chunk sau.

    Chi lam giua cac manh CUNG mot muc: keo duoi cua muc truoc sang muc sau se tron
    hai chu de, va chunk ket qua se khop voi ca hai cau hoi ma tra loi dung khong
    cau nao.
    """
    if len(pieces) < 2 or OVERLAP_CHARS <= 0:
        return pieces
    out = [pieces[0]]
    for previous, current in pairwise(pieces):
        tail = previous[-OVERLAP_CHARS:].lstrip()
        out.append(f"{tail}\n{current}" if tail else current)
    return out


def _cat_muc(text: str) -> list[_Section]:
    """Tieu de markdown truoc, moc cua ho so tai lieu sau.

    Thu tu nay co chu dich: markdown la cau truc TUONG MINH do nguoi viet dat ra, con
    moc cua ho so la cau truc SUY RA. Cai tuong minh luon thang. Chi khi markdown
    khong tim thay gi — dung truong hop cua moi tep PDF — moi hoi den ho so.
    """
    theo_tieu_de = _split_by_heading(text)
    if len(theo_tieu_de) > 1 or theo_tieu_de[0].path is not None:
        return theo_tieu_de

    ho_so = nhan_dien(text)
    if ho_so is None:
        return theo_tieu_de

    theo_ho_so = _split_by_profile(text, ho_so)
    _log.info("cat muc theo ho so tai lieu", ho_so=ho_so.ten, so_muc=len(theo_ho_so))
    return theo_ho_so


def chunk_document(
    text: str, ban_do_trang: Sequence[tuple[int, int | None]] | None = None
) -> list[Chunk]:
    """Cat tai lieu thanh chunk. Co `ban_do_trang` thi moi chunk mang them so trang.

    Offset duoc tinh TRUOC khi ap chong lan, va do la diem mau chot: `chunk_text` giu
    bat bien `"".join(pieces) == text`, nen cong don do dai cac manh cho ra vi tri
    that. Sau khi ap chong lan thi manh khong con la lat cat lien tuc cua van ban nua
    — di tim lai chuoi luc do se ra nham cho, vi phan chong lan xuat hien hai lan.
    """
    chunks: list[Chunk] = []
    for section in _cat_muc(text):
        # Giu ban goc de tinh vi tri, ban da chong lan de lam noi dung.
        goc = chunk_text(section.body, TARGET_CHARS)
        pieces = _with_overlap(goc)

        vi_tri = section.bat_dau
        for goc_i, piece in zip(goc, pieces, strict=True):
            body = piece.strip()
            if body:
                chunks.append(
                    Chunk(
                        ord=len(chunks),
                        section=section.path,
                        content=body,
                        page=trang_cua(ban_do_trang, vi_tri) if ban_do_trang else None,
                        bat_dau=vi_tri,
                        dai_goc=len(goc_i),
                    )
                )
            vi_tri += len(goc_i)
    return chunks
