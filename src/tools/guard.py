"""Lop bao ve cho KET QUA CONG CU — mot trong ba be mat dung chung bo do injection.

Bo do da chuyen sang agents/policy/injection.py (08/09/2026) de ca ba be mat dung
chung mot danh sach mau: tin nhan nguoi dung, tai lieu luc nap, va ket qua cong cu.
Ba danh sach roi nhau la ba danh sach se lech nhau sau vai lan sua.

Phan con lai o day la thu rieng cua ket qua cong cu: boc the, cat tran.

ARCHITECTURE.md section 7.2 chi tinh injection qua tai lieu do ADMIN nap. Web search
dua vao van ban do NGUOI LA soan, va trong vong ReAct thi observation do lai quyet
dinh hanh dong tiep theo — injection duoc khuech dai.

CO Y KHONG CHAN theo tu khoa. Chan bang danh sach tu vua de vuot (viet lai mot chut
la lot), vua tao cam giac an toan gia khien nguoi ta bo qua cac lop that su co tac
dung: boc the, noi ro trong RULES rang do la du lieu, va khong bao gio dua ket qua
cong cu vao role 'system'.

Ham detect_injection ton tai de AUDIT: biet co ai dang thu, va thu bang cach nao.
"""

from agents.policy.injection import detect_injection
from agents.ports.logger import LoggerPort
from agents.prompt.budget import exceeds_budget, trim_to_budget
from agents.prompt.builder import sanitize


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
