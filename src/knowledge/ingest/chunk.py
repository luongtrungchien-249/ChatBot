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
from dataclasses import dataclass
from itertools import pairwise

from agents.prompt.budget import CHARS_PER_TOKEN
from shared.chunk_text import chunk_text

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


@dataclass(frozen=True, slots=True)
class _Section:
    path: str | None
    body: str


def _split_by_heading(text: str) -> list[_Section]:
    """Cat theo tieu de markdown, giu DUONG DAN tieu de (cha > con)."""
    matches = list(_HEADING.finditer(text))
    if not matches:
        return [_Section(path=None, body=text)]

    sections: list[_Section] = []
    # Phan van ban truoc tieu de dau tien (loi noi dau, muc luc...) van phai giu.
    if matches[0].start() > 0:
        head = text[: matches[0].start()].strip()
        if head:
            sections.append(_Section(path=None, body=head))

    stack: list[str] = []
    for i, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        del stack[level - 1 :]
        stack.append(title)

        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        if body:
            sections.append(_Section(path=" > ".join(stack), body=body))
    return sections


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


def chunk_document(text: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in _split_by_heading(text):
        pieces = _with_overlap(chunk_text(section.body, TARGET_CHARS))
        for piece in pieces:
            body = piece.strip()
            if body:
                chunks.append(Chunk(ord=len(chunks), section=section.path, content=body))
    return chunks
