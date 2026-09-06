"""Parse lenh TRUOC khi vao LLM.

Stage 3 dung TRUOC stage 4 (ratelimit) co chu dich: nguoi dung phai xoa duoc memory
cua chinh minh ngay ca khi dang bi rate limit. Dung "toi uu" thu tu do.

CHUA DUOC NOI vao handle_message — stage 3 thuoc Giai doan 7, cung luc L3 memory
chay that. Giu o day vi day la mot HOP DONG da chot (ARCHITECTURE.md section 6.2
khai ro ai duoc xoa gi), va viet lai tu dau khi den luot thi de bo sot mot nhanh.
"""

import re
from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class ShowMemory:
    """Liet ke fact ve CHINH MINH, trong CHINH thread nay."""


@dataclass(frozen=True, slots=True)
class Remember:
    """Nguoi dung CHU DONG bao bot nho — che do explicit, an toan nhat.

    Chi ghi khi duoc noi thang ra. Trich fact tu dong (implicit) di duong khac va
    chi bat sau khi da co cong cu audit.
    """

    content: str


@dataclass(frozen=True, slots=True)
class Forget:
    pattern: str


@dataclass(frozen=True, slots=True)
class ForgetAll:
    pass


@dataclass(frozen=True, slots=True)
class ConfirmForget:
    """Xac nhan mot yeu cau xoa dang cho.

    KHONG dung ma xac nhan dang chuoi hex: khong ai go mot ma tam ky tu vao nhom
    chat. Trang thai duoc khoa theo (thread, nguoi go lenh) va het han sau vai phut,
    nen mot tu "dong y" la du va khong the dung nham cua nguoi khac.

    `choices` la so thu tu trong danh sach da liet ke, bat dau tu 1. Rong = tat ca.

    Vi sao can chon: nguong tim ung vien co y dat RONG de khong bo sot cach noi cua
    nguoi dung, nen danh sach thuong co ca thu ho khong dinh xoa. Da troi that:
    "quen cho lam" liet ke ca "nhom hop thu 3", va mot cai "dong y" xoa sach ca hai.
    """

    choices: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class Help:
    pass


@dataclass(frozen=True, slots=True)
class NoCommand:
    pass


Command: TypeAlias = (
    ShowMemory | Remember | Forget | ForgetAll | ConfirmForget | Help | NoCommand
)

#: Nhan ca ban CO DAU lan ban KHONG DAU. Nguoi Viet go khong dau la chuyen thuong,
#: va mot lenh khong duoc nhan dien se roi vao LLM — tuc la nguoi dung go "quen het"
#: roi nhan mot cau tra loi than mat thay vi memory bi xoa.
_EXACT: dict[str, Command] = {
    "memory": ShowMemory(),
    "bo nho": ShowMemory(),
    "bộ nhớ": ShowMemory(),
    "quen het": ForgetAll(),
    "quên hết": ForgetAll(),
    "help": Help(),
    "huong dan": Help(),
    "hướng dẫn": Help(),
}

#: Chi nhan dung hai cach go nay. "ok" hay "u" thi qua rong — nguoi ta noi trong
#: nhom suot ngay, va mot cai gat dau vo tinh khong duoc phep xoa memory.
#: Kem so thu tu tuy chon: "dong y 2", "đồng ý 1,3", "dong y 1 3".
_CONFIRM = re.compile(r"^(?:dong y|đồng ý)\s*([\d\s,]*)$", re.IGNORECASE)

_FORGET = re.compile(r"^(?:quen|quên)\s+(.+)$", re.IGNORECASE)

#: "nho giup: X", "nhớ giúp X", "ghi nhớ: X", "nhớ: X".
#:
#: Dau hai cham la TUY CHON: nguoi ta go tu nhien, khong ai nho dau cau cua mot
#: lenh chat. Nhung "nhớ" mot minh (khong co noi dung) thi KHONG phai lenh —
#: "nhớ hôm qua họp gì không" la mot cau hoi that.
_REMEMBER = re.compile(
    r"^(?:ghi\s+)?(?:nho|nhớ)(?:\s+(?:giup|giúp|gium|giùm))?\s*:?\s+(.+)$",
    re.IGNORECASE,
)


def parse_command(text: str) -> Command:
    """Van ban da BOC MENTION (dau ra cua stage 2), khong phai van ban tho."""
    stripped = text.strip()

    exact = _EXACT.get(stripped.lower())
    if exact is not None:
        return exact

    match = _CONFIRM.match(stripped)
    if match is not None:
        numbers = tuple(int(n) for n in re.findall(r"\d+", match.group(1)))
        return ConfirmForget(choices=numbers)

    match = _FORGET.match(stripped)
    if match is not None:
        return Forget(pattern=match.group(1).strip())

    match = _REMEMBER.match(stripped)
    if match is not None:
        return Remember(content=match.group(1).strip())

    return NoCommand()
