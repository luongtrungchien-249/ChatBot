"""Cat van ban dai theo gioi han ky tu, uu tien ranh gioi ngu nghia.

BAT BIEN: "".join(chunk_text(t, n)) == t. Khong mat, khong them mot ky tu nao.
Cac cho goi (stage 13-respond, send.py cua tung adapter) tu strip neu can.

Thu tu uu tien cho cat: doan van -> dong -> cau -> tu -> cat cung.
Cat cung chi xay ra khi mot "tu" dai hon ca max_chars (URL, chuoi base64).
"""

import re

_SENTENCE_END = re.compile(r"[.!?…]\s")


def _find_cut(text: str, limit: int) -> int:
    """Vi tri cat tot nhat trong text[0:limit]. Ket qua LUON <= limit.

    Cua so chi dai dung `limit` ky tu nen moi ung vien deu vua.
    """
    if len(text) <= limit:
        return len(text)

    window = text[:limit]

    para = window.rfind("\n\n")
    if para >= 0:
        return para + 2

    line = window.rfind("\n")
    if line >= 0:
        return line + 1

    last_sentence = -1
    for match in _SENTENCE_END.finditer(window):
        last_sentence = match.end()
    if last_sentence > 0:
        return last_sentence

    space = window.rfind(" ")
    if space >= 0:
        return space + 1

    # Mot "tu" dai hon ca cua so (URL, base64) — buoc phai cat cung.
    return limit


def chunk_text(text: str, max_chars: int) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars phai duong")
    if text == "":
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    rest = text
    while len(rest) > max_chars:
        cut = _find_cut(rest, max_chars)
        chunks.append(rest[:cut])
        rest = rest[cut:]
    if rest:
        chunks.append(rest)
    return chunks


def truncate_at_boundary(text: str, max_chars: int) -> str:
    """Giu lai toi da max_chars ky tu dau, cat tai ranh gioi ngu nghia.

    Dung boi agents/prompt/budget.py — cat mot tang prompt cho vua tran.
    """
    if len(text) <= max_chars:
        return text
    return text[: _find_cut(text, max_chars)]
