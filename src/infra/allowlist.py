"""Bang `thread_allowlist` — nhom nao duoc phep dung bot.

Truoc giai doan 4, `AccessRules.allowed_threads` la mot frozenset RONG duoc hardcode
trong container. Ket hop voi GROUP_POLICY=allowlist, no co nghia la: bot cai vao nhom
Zalo nao cung im lang, va khong co cach nao mo ma khong sua code roi khoi dong lai.

Doc lai o MOI tin nhan chu khong cache: mot cau SELECT tren bang vai chuc dong la
khong dang ke so voi mot lan goi model, doi lai `allow` co hieu luc ngay, khong phai
khoi dong lai worker luc 11 gio dem.
"""

from agents.domain.thread import Platform

from .db import execute, fetch

#: Cot `mode` cua bang cho phep chan RIENG mot nhom ke ca khi chinh sach chung mo.
#: Mot dong 'disabled' la lenh cam, khong phai mot dong bi bo quen.
_BLOCKED = "disabled"


def row_key(platform: str, thread_id: str) -> str:
    """PHAI cho ra chuoi giong het `domain.thread.scope_key`.

    Khong goi thang scope_key duoc: `platform` doc tu Postgres la `str`, con
    ThreadScope doi Literal — ep kieu o day chi la noi doi voi trinh kiem kieu.
    Rang buoc duoc giu bang test `test_allowlist.py::test_khop_scope_key` thay vi
    bang niem tin; lech dinh dang thi ca allowlist im lang khong khop gi.
    """
    return f"{platform}:{thread_id}"


async def load_allowed_threads() -> frozenset[str]:
    """Tra ve tap `scope_key` duoc phep."""
    rows = await fetch(
        "SELECT platform, thread_id FROM thread_allowlist WHERE mode <> $1", _BLOCKED
    )
    return frozenset(row_key(row["platform"], row["thread_id"]) for row in rows)


async def allow_thread(platform: Platform, thread_id: str, added_by: str = "cli") -> None:
    """Them hoac mo lai mot nhom. Chay lai nhieu lan khong sao."""
    await execute(
        """INSERT INTO thread_allowlist (platform, thread_id, mode, added_by)
           VALUES ($1, $2, 'allowlist', $3)
           ON CONFLICT (platform, thread_id)
           DO UPDATE SET mode = 'allowlist', added_by = $3, added_at = now()""",
        platform,
        thread_id,
        added_by,
    )


async def deny_thread(platform: Platform, thread_id: str, added_by: str = "cli") -> None:
    """Cam mot nhom. Ghi dong 'disabled' chu KHONG xoa dong.

    Xoa thi khong con dau vet ai cam, luc nao, va lan sau co nguoi 'allow' lai vi
    tuong day chi la nhom chua duoc them.
    """
    await execute(
        """INSERT INTO thread_allowlist (platform, thread_id, mode, added_by)
           VALUES ($1, $2, 'disabled', $3)
           ON CONFLICT (platform, thread_id)
           DO UPDATE SET mode = 'disabled', added_by = $3, added_at = now()""",
        platform,
        thread_id,
        added_by,
    )


async def list_threads() -> list[tuple[str, str, str]]:
    """(scope_key, mode, added_by) — cho lenh `allowed` cua CLI."""
    rows = await fetch(
        "SELECT platform, thread_id, mode, added_by FROM thread_allowlist ORDER BY added_at DESC"
    )
    return [
        (row_key(row["platform"], row["thread_id"]), row["mode"], row["added_by"]) for row in rows
    ]
