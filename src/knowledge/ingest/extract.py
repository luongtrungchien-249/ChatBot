"""Tep -> van ban tho, giu duoc ranh gioi doan va tieu de.

Giu xuong dong la CO Y, khong phai tien the: buoc chunk sau do cat theo tieu de va
doan van. Ep het ve mot dong thi chi con cach cat cung theo so ky tu — dung cai ma
plan noi la "bien so anh huong chat luong nhieu nhat".
"""

from pathlib import Path

#: Duoi tep doc duoc. Duoi khac -> bao thang cho nguoi nap, khong doc bua roi nap
#: mot mo rac vao CSDL vector.
SUPPORTED = (".txt", ".md", ".pdf", ".docx")


class UnsupportedDocumentError(Exception):
    pass


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        return _from_pdf(path)
    if suffix == ".docx":
        return _from_docx(path)
    raise UnsupportedDocumentError(
        f"khong doc duoc {path.suffix!r}. Chi ho tro: {', '.join(SUPPORTED)}"
    )


def _from_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    # Ngan trang bang dong trong: buoc chunk coi do la ranh gioi doan, nen mot chunk
    # khong bat qua hai trang tru khi that su can.
    return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages)


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
