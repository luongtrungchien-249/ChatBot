"""REPL chat + lenh quan tri.

CLI la adapter thu ba, khong phai do choi — day la cach duy nhat lam Phase 0 khi
chua co token Zalo/Meta.

CO Y bo qua hang doi: REPL von tuan tu mot nguoi dung, nen FIFO theo thread da duoc
bao dam san. Bat buoc chay them worker chi de go mot cau hoi la lam kho viec phat
trien ma khong mua duoc gi.
"""

import asyncio
import sys
from pathlib import Path

from adapters.cli.normalize import CLI_MAX_MESSAGE_CHARS, normalize_cli_input
from agents.domain.thread import Platform, ThreadScope
from agents.pipeline.handle_message import Failed, handle_message
from infra.allowlist import allow_thread, deny_thread, list_threads
from infra.db import close_db, execute, fetch, transaction
from infra.logger import configure_logging, get_logger
from infra.redis_client import close_redis
from memory.repository.fact_repo import dump_thread

from .container import build_deps

MIGRATIONS_DIR = Path.cwd() / "db" / "migrations"


class ConsoleChannel:
    """ChannelPort in ra terminal."""

    max_message_chars = CLI_MAX_MESSAGE_CHARS

    async def typing(self, scope: ThreadScope) -> None:
        print("...", end="\r", flush=True)

    async def send(self, scope: ThreadScope, text: str, reply_to: str | None = None) -> None:
        print(f"\nbot> {text}\n")


async def migrate() -> None:
    # Bang theo doi phai ton tai TRUOC khi chay 0001 — chinh 0001 cung can duoc ghi
    # lai la da chay. File 0005 tao lai bang nay bang CREATE TABLE IF NOT EXISTS.
    await execute(
        """CREATE TABLE IF NOT EXISTS schema_migration (
             filename   TEXT PRIMARY KEY,
             applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
           )"""
    )

    applied = {r["filename"] for r in await fetch("SELECT filename FROM schema_migration")}
    # Danh so tang dan, chi tien, khong sua file cu.
    files = sorted(f for f in MIGRATIONS_DIR.glob("*.sql"))

    log = get_logger()
    ran = 0
    for path in files:
        if path.name in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        # Mot migration mot transaction: hong giua chung thi khong de lai nua vet.
        # Ten file di vao cau lenh duoi dang THAM SO, khong noi suy vao chuoi SQL.
        async with transaction() as connection:
            await connection.execute(sql)
            await connection.execute(
                "INSERT INTO schema_migration (filename) VALUES ($1)", path.name
            )
        log.info("da chay migration", filename=path.name)
        ran += 1

    log.info(
        "khong co migration moi" if ran == 0 else "migrate xong", ran=ran, total=len(files)
    )


async def chat() -> None:
    deps = await build_deps(ConsoleChannel())
    log = get_logger()

    print("Go cau hoi roi Enter. Ctrl+C hoac Ctrl+D de thoat.\n")
    loop = asyncio.get_running_loop()

    while True:
        try:
            # input() chan luong; day sang thread khac de event loop van chay
            # (typing va cac task nen van song).
            line = (await loop.run_in_executor(None, lambda: input("ban> "))).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if not line:
            continue

        msg = normalize_cli_input(line)
        result = await handle_message(msg, deps)
        if isinstance(result, Failed):
            log.error("luot chat that bai", trace_id=msg.trace_id, error=str(result.error))


_PLATFORMS: tuple[Platform, ...] = ("zalo_bot", "zalo_personal", "messenger", "cli", "web")


async def allowlist_command(command: str, args: list[str]) -> int:
    """`allow` / `deny` / `allowed` — quan tri nhom nao duoc dung bot.

    GROUP_POLICY=allowlist nghia la bot cai vao nhom moi thi IM LANG cho toi khi
    duoc them o day. Do la thiet ke, khong phai loi — nhung khong co lenh nay thi
    khong ai mo duoc nhom nao ma khong sua code.
    """
    if command == "allowed":
        rows = await list_threads()
        if not rows:
            print("Chua co nhom nao trong allowlist.")
        for key, mode, added_by in rows:
            print(f"{key:<40} {mode:<10} boi {added_by}")
        return 0

    if len(args) != 2 or args[0] not in _PLATFORMS:
        print(
            f"Dung: {command} <platform> <thread_id>\n"
            f"platform: {' | '.join(_PLATFORMS)}\n"
            "thread_id cua nhom Zalo nam trong log cua process zalo "
            '("da xep hang tin Zalo", truong thread_id).',
            file=sys.stderr,
        )
        return 1

    # mypy tu thu hep str -> Platform nho phep kiem `args[0] not in _PLATFORMS` o tren.
    platform: Platform = args[0]
    thread_id = args[1]
    if command == "allow":
        await allow_thread(platform, thread_id)
        print(f"Da cho phep {platform}:{thread_id}")
    else:
        await deny_thread(platform, thread_id)
        print(f"Da cam {platform}:{thread_id}")
    return 0


async def memory_dump(args: list[str]) -> int:
    """`memory <platform> <thread_id>` — moi fact con hieu luc cua mot thread.

    Cong cu AUDIT. ARCHITECTURE.md section 6.2 va plan section 9 deu dat mot dieu
    kien: L3 implicit (bot TU trich fact) chi duoc bat SAU khi lenh nay chay duoc.
    Khong nhin duoc bot da tu ghi gi thi khong the cho phep no tu ghi.
    """
    if len(args) != 2 or args[0] not in _PLATFORMS:
        print(
            f"Dung: memory <platform> <thread_id>\nplatform: {' | '.join(_PLATFORMS)}",
            file=sys.stderr,
        )
        return 1

    platform: Platform = args[0]
    scope = ThreadScope(platform=platform, thread_id=args[1])
    facts = await dump_thread(scope)
    if not facts:
        print(f"Khong co fact nao trong {platform}:{args[1]}")
        return 0

    print(f"{len(facts)} fact trong {platform}:{args[1]}\n")
    for f in facts:
        khi = f.created_at.strftime("%Y-%m-%d %H:%M")
        print(f"  [{f.subject_id:<16}] {f.content}")
        print(f"  {'':<18} {f.source}, tin cay {f.confidence:.2f}, tao luc {khi}\n")
    return 0


async def main() -> int:
    configure_logging()
    command = sys.argv[1] if len(sys.argv) > 1 else "chat"

    try:
        if command == "migrate":
            await migrate()
        elif command == "chat":
            await chat()
        elif command in ("allow", "deny", "allowed"):
            return await allowlist_command(command, sys.argv[2:])
        elif command == "memory":
            return await memory_dump(sys.argv[2:])
        else:
            print(
                f"Lenh khong biet: {command}. "
                "Co: migrate | chat | allow | deny | allowed | memory",
                file=sys.stderr,
            )
            return 1
        return 0
    finally:
        # Ca migrate lan chat deu ket thuc duoc, nen luon dong ket noi — con treo mot
        # pool Postgres la process khong bao gio thoat.
        await asyncio.gather(close_db(), close_redis(), return_exceptions=True)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
