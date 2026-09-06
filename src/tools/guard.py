"""Lop bao ve cho ket qua cong cu.

ARCHITECTURE.md section 7.2 chi tinh injection qua tai lieu do ADMIN nap. Web search
dua vao van ban do NGUOI LA soan, va trong vong ReAct thi observation do lai quyet
dinh hanh dong tiep theo — injection duoc khuech dai.

CO Y KHONG CHAN theo tu khoa. Chan bang danh sach tu vua de vuot (viet lai mot chut
la lot), vua tao cam giac an toan gia khien nguoi ta bo qua cac lop that su co tac
dung: boc the, noi ro trong RULES rang do la du lieu, va khong bao gio dua ket qua
cong cu vao role 'system'.

Ham detect_injection ton tai de AUDIT: biet co ai dang thu, va thu bang cach nao.
"""

import re
import unicodedata
from dataclasses import dataclass

from agents.ports.logger import LoggerPort
from agents.prompt.budget import exceeds_budget, trim_to_budget
from agents.prompt.builder import sanitize


def fold_diacritics(text: str) -> str:
    """Bo dau truoc khi so khop.

    BAT BUOC, khong phai tien ich: nguoi Viet thuong go KHONG DAU, va ke dang do thu
    lai cang hay go khong dau. Mau "bo qua huong dan" co dau se de lot thang ban
    khong dau — dung loai lo hong da tung gap o regex mention.

    NFD tach dau thanh ky tu to hop rieng roi xoa; rieng 'd' gach ngang khong tach
    duoc nen phai thay tay.
    """
    replaced = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", replaced)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


#: Mau viet KHONG DAU vi input da duoc bo dau truoc khi so khop.
_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "bo-qua-huong-dan",
        re.compile(
            r"\b(bo qua|phot lo|quen)\s+(moi\s+|tat ca\s+)?(huong dan|chi dan|quy tac|luat)", re.I
        ),
    ),
    (
        "ignore-instructions",
        re.compile(
            r"\bignore\s+(all\s+|previous\s+|prior\s+|above\s+)+(instructions?|rules?)", re.I
        ),
    ),
    ("doi-vai", re.compile(r"\b(bay gio|tu gio|ke tu gio)\s+(ban|may)\s+(la|thanh)\b", re.I)),
    ("you-are-now", re.compile(r"\byou\s+are\s+now\b|\bact\s+as\s+(a\s+)?(dan|jailbreak)", re.I)),
    (
        "lo-system-prompt",
        re.compile(
            r"\b(in ra|hien thi|tiet lo|cho xem)\s+.{0,20}(system prompt|prompt he thong)", re.I
        ),
    ),
    (
        "reveal-prompt",
        re.compile(
            r"\b(reveal|print|show|repeat)\s+.{0,20}(system prompt|your instructions)", re.I
        ),
    ),
    (
        "che-do-dac-biet",
        re.compile(r"\b(che do|mode)\s+(nha phat trien|developer|god|unrestricted)", re.I),
    ),
    (
        "gia-danh-quan-tri",
        re.compile(r"\b(toi la|minh la)\s+(quan tri vien|admin|nguoi tao ra ban)", re.I),
    ),
]


@dataclass(frozen=True, slots=True)
class InjectionScan:
    suspicious: bool
    patterns: tuple[str, ...]


def detect_injection(text: str) -> InjectionScan:
    folded = fold_diacritics(text)
    hits = tuple(name for name, pattern in _INJECTION_PATTERNS if pattern.search(folded))
    return InjectionScan(suspicious=bool(hits), patterns=hits)


def exceeds_tool_budget(text: str) -> bool:
    """Ket qua co vuot tran tang 'tool' khong.

    Cho goi dung cai nay de biet co CAN NEN khong. Nen bang model re giu duoc trich
    dan; cat cung thi mat phan cuoi — ma phan cuoi thuong la noi chua DOI va link
    nguon, dung thu bat buoc phai trich dan.
    """
    return exceeds_budget(text, "tool")


def wrap_observation(
    *,
    tool_name: str,
    source: str,
    content: str,
    trace_id: str,
    logger: LoggerPort | None = None,
) -> str:
    """Boc ket qua cong cu thanh mot khoi du lieu an toan de dua vao prompt.

    Ba viec, theo dung thu tu:
      1. sanitize()  — bo the dong gia, chan noi dung tu thoat khoi hop.
      2. cat theo tran tang 'tool' — mot trang web dai khong duoc nuot ca cua so.
      3. boc trong <ket_qua_cong_cu> — RULES trong system prompt noi ro day la
         DU LIEU, khong phai chi thi.

    logger tiem vao chu khong import infra/logger: import se keo theo config/, va luc
    do unit test cua chinh ham nay lai doi du bien moi truong — dung cai ma L2 sinh
    ra de tranh.
    """
    scan = detect_injection(content)
    if scan.suspicious and logger is not None:
        logger.warning(
            "ket qua cong cu chua mau giong prompt injection — ghi nhan de audit, KHONG chan",
            trace_id=trace_id,
            tool=tool_name,
            source=source,
            patterns=list(scan.patterns),
        )

    # Cat cung o day la LUOI CUOI CUNG — cho goi da thu nen bang model re truoc do.
    clean = trim_to_budget(sanitize(content), "tool")
    if clean.trimmed_tokens > 0 and logger is not None:
        logger.warning(
            "ket qua cong cu VAN vuot tran sau khi nen — cat cung, co the mat trich dan o cuoi",
            trace_id=trace_id,
            tool=tool_name,
            trimmed_tokens=clean.trimmed_tokens,
        )

    flag = ' canh_bao="chua_cau_ra_lenh"' if scan.suspicious else ""
    return (
        f'<ket_qua_cong_cu cong_cu="{tool_name}" nguon="{source}"{flag}>\n'
        f"{clean.text}\n</ket_qua_cong_cu>"
    )
