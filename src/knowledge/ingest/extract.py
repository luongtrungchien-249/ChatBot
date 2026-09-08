"""Tep -> van ban tho, giu duoc ranh gioi doan va tieu de.

Giu xuong dong la CO Y, khong phai tien the: buoc chunk sau do cat theo tieu de va
doan van. Ep het ve mot dong thi chi con cach cat cung theo so ky tu — dung cai ma
plan noi la "bien so anh huong chat luong nhieu nhat".
"""

import re
from dataclasses import dataclass
from pathlib import Path

from infra.logger import get_logger

from .clean import Trang, ghep, lam_sach
from .profiles import ap_sua_ky_tu, nhan_dien

_log = get_logger()

#: Duoi tep doc duoc. Duoi khac -> bao thang cho nguoi nap, khong doc bua roi nap
#: mot mo rac vao CSDL vector.
SUPPORTED = (".txt", ".md", ".pdf", ".docx")


class UnsupportedDocumentError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Document:
    text: str
    #: (offset bat dau, so trang) da sap tang dan. Rong voi dinh dang khong co trang.
    ban_do_trang: list[tuple[int, int | None]]


def extract_text(path: Path) -> str:
    """Van ban da lam sach. Cho cac cho chi can chu, khong can so trang."""
    return extract_document(path).text


def extract_document(path: Path) -> Document:
    """Trich xuat DAY DU: van ban da lam sach + ban do vi tri -> so trang.

    Buoc nap dung ham nay chu khong dung `extract_text`, vi no can so trang de dien
    `kb_chunk.page` — cot da ton tai tu migration 0004 nhung chua bao gio duoc dien.
    """
    trang = _doc_theo_trang(path)
    text, ban_do = ghep(trang)
    _bao_cao_suc_khoe(text, path)

    # Ho so tai lieu: neu nhan ra dang tep nay thi ap bang sua ky tu cua no.
    # Khong nhan ra -> tra ve y nguyen, hanh vi khong doi.
    ho_so = nhan_dien(text)
    if ho_so is None:
        return Document(text=text, ban_do_trang=ban_do)

    # Bang sua thay MOT ky tu bang MOT ky tu (chu cai -> phan so) nen do dai van
    # ban khong doi va `ban_do` van dung. Luat nay duoc khoa bang test.
    text, da_sua = ap_sua_ky_tu(text, ho_so)
    _log.info(
        "nhan ra ho so tai lieu",
        path=str(path),
        ho_so=ho_so.ten,
        ky_tu_da_sua=da_sua,
    )
    return Document(text=text, ban_do_trang=ban_do)


def _doc_theo_trang(path: Path) -> list[Trang]:
    """Doc thanh TUNG TRANG roi lam sach. Chi PDF moi co trang that."""
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        # Markdown da la van ban sach, va lam sach them se PHA cau truc: buoc noi
        # dong gay se nuot xuong dong co y nghia trong khoi code va danh sach.
        return [Trang(so=None, noi_dung=path.read_text(encoding="utf-8"))]
    if suffix == ".pdf":
        return lam_sach(_trang_pdf(path))
    if suffix == ".docx":
        return [Trang(so=None, noi_dung=_from_docx(path))]
    raise UnsupportedDocumentError(
        f"khong doc duoc {path.suffix!r}. Chi ho tro: {', '.join(SUPPORTED)}"
    )


#: Chu cai don le dung ngay truoc mot don vi do — dau hieu font phan so bi trich sai.
#: Rong hon mau trong profiles.py MOT CACH CO Y: cai kia de SUA (phai hep, sua nham
#: la lam hong van ban dung), cai nay de DEM (phai rong, bo sot la khong ai biet).
_NGHI_HONG = re.compile(r"(?<![A-Za-z])([A-Z])(?=\s+(?:tsp|tbsp|cp|cup|cups|lb|oz|qt|pt|gal)\b)")


def _bao_cao_suc_khoe(text: str, path: Path) -> None:
    """Dem cac dau hieu trich xuat hong va GHI LOG.

    Co y khong nem: quyen quyet dinh co nap hay khong thuoc ve nguoi nap. Nhung nap
    mot tai lieu hong AM THAM la cach chac chan nhat de vai tuan sau tuong loi nam o
    embedding hay o nguong rerank — trong khi no nam ngay o buoc dau tien.
    """
    if not text:
        return

    thay_the = text.count("\ufffd")
    nghi_hong = len(_NGHI_HONG.findall(text))
    if not thay_the and not nghi_hong:
        return

    _log.warning(
        "trich xuat co dau hieu hong — VAN NAP, hay xem lai truoc khi tin so lieu",
        path=str(path),
        ky_tu_thay_the=thay_the,
        chu_cai_dung_truoc_don_vi_do=nghi_hong,
    )


def _trang_pdf(path: Path) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return [(page.extract_text() or "").strip() for page in reader.pages]


def _from_docx(path: Path) -> str:
    import docx

    document = docx.Document(str(path))
    lines: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        # Tieu de cua Word ('Heading 1'...) duoc doi thanh markdown de buoc chunk
        # nhan ra chung bang DUNG mot luat, khong phai hai.
        style = (paragraph.style.name or "") if paragraph.style else ""
        if style.startswith("Heading"):
            level = "".join(c for c in style if c.isdigit()) or "1"
            lines.append(f"{'#' * min(int(level), 6)} {text}")
        else:
            lines.append(text)
    return "\n\n".join(lines)
