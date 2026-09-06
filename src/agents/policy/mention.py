"""Phat hien mention HAI LOP: truong mention trong payload + fallback regex.

Payload cac nen tang khong dong nhat va hay doi — mot lop la khong du.
"""

import re
from dataclasses import dataclass
from typing import TypeAlias

from ..domain.message import InboundMessage

#: Moi nguyen am tieng Viet co the xuat hien co dau hoac khong.
#:
#: BOT_MENTION_NAME viet khong dau ('CP_Assistant') vi nen tang thuong khong cho dat
#: ten co dau, nhung nguoi Viet GO CO DAU. Khong co bang nay thi bot im lang truoc
#: dung cach goi tu nhien nhat — va im lang trong nhom trong nhu bot chet.
#:
#: Mo rong ngay trong regex (thay vi bo dau ca hai ben roi so sanh) de con boc dung
#: doan mention ra khoi cau hoi: bo dau lam doi do dai chuoi, chi so lech het.
_VIETNAMESE_VARIANTS: dict[str, str] = {
    "a": "aàáảãạăằắẳẵặâầấẩẫậ",
    "d": "dđ",
    "e": "eèéẻẽẹêềếểễệ",
    "i": "iìíỉĩị",
    "o": "oòóỏõọôồốổỗộơờớởỡợ",
    "u": "uùúủũụưừứửữự",
    "y": "yỳýỷỹỵ",
}


def _expand(char: str) -> str:
    variants = _VIETNAMESE_VARIANTS.get(char.lower())
    return f"[{variants}]" if variants else re.escape(char)


def _to_alternative(name: str) -> str:
    # Mo rong nguyen am truoc, roi moi cho gach duoi khop ca khoang trang.
    expanded = "".join(_expand(c) for c in name)
    return expanded.replace("_", r"[_\s]?")


def primary_name(bot_names: str) -> str:
    """Ten chinh: muc DAU TIEN trong danh sach.

    Dung khi can hien mot ten duy nhat — cau huong dan, ten nguoi gui khi luu cau
    tra loi cua bot.
    """
    first = bot_names.split(",")[0].strip()
    return first or bot_names


def mention_regex(bot_names: str) -> re.Pattern[str]:
    """BOT_MENTION_NAME nhan NHIEU ten, ngan cach bang dau phay: "CP_Assistant,CP".

    Vi sao can nhieu: bot tu gioi thieu la "CP Assistant", nhung trong nhom nguoi ta
    go ten NGAN nhat go duoc — "@CP". Chi khai ten day du thi bot im lang truoc dung
    cach goi pho bien nhat.

    Ten dai dat truoc de khop truoc, tranh truong hop ten ngan an mat phan duoi.
    """
    names = sorted(
        (n.strip() for n in bot_names.split(",") if n.strip()),
        key=len,
        reverse=True,
    )
    if not names:
        raise ValueError("BOT_MENTION_NAME rong")

    alternatives = "|".join(_to_alternative(n) for n in names)
    # (?![^\W\d_]|\d|_) chan '@CP_Assistant2' va '@CPU' — do la nguoi/thu khac,
    # khong phai bot. Dung lop chu Unicode de chan ca chu co dau.
    return re.compile(rf"@(?:{alternatives})(?![^\W\d_]|\d|_)", re.IGNORECASE | re.UNICODE)


@dataclass(frozen=True, slots=True)
class Ignore:
    reply: bool = False


@dataclass(frozen=True, slots=True)
class Reply:
    text: str
    empty: bool
    reply: bool = True


MentionVerdict: TypeAlias = Ignore | Reply


def resolve_mention(msg: InboundMessage, bot_names: str) -> MentionVerdict:
    """bot_names: mot hoac nhieu ten, ngan cach bang dau phay."""
    pattern = mention_regex(bot_names)
    mentioned = msg.mentioned_bot or bool(pattern.search(msg.text))

    if msg.is_group and not mentioned:
        return Ignore()

    stripped = re.sub(r"\s+", " ", pattern.sub(" ", msg.text)).strip()
    return Reply(text=stripped, empty=stripped == "")
