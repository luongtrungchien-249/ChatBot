"""REPL chat + lenh quan tri.

CLI la adapter thu ba, khong phai do choi — day la cach duy nhat lam Phase 0 khi
chua co token Zalo/Meta.

CO Y bo qua hang doi: REPL von tuan tu mot nguoi dung, nen FIFO theo thread da duoc
bao dam san. Bat buoc chay them worker chi de go mot cau hoi la lam kho viec phat
trien ma khong mua duoc gi.
"""

import asyncio
import getpass
import sys
from pathlib import Path

from adapters.cli.normalize import CLI_MAX_MESSAGE_CHARS, normalize_cli_input
from agents.domain.thread import Platform, ThreadScope
from agents.pipeline.handle_message import Failed, handle_message
from config import get_settings
from infra.allowlist import allow_thread, deny_thread, list_threads
from infra.db import close_db, execute, fetch, transaction
from infra.http import close_http
from infra.logger import configure_logging, get_logger
from infra.metrics import budget_today, cache_stats, message_stats, route_stats, turn_stats
from infra.redis_client import close_redis
from knowledge.ingest.extract import SUPPORTED, UnsupportedDocumentError
from knowledge.ingest.pipeline import ingest_file
from memory.repository.fact_repo import cho_duyet, danh_dau_da_duyet, dump_thread, revoke

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


_PLATFORMS: tuple[Platform, ...] = ("zalo_bot", "zalo_personal", "cli", "web")


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


async def ingest_command(args: list[str]) -> int:
    """`ingest <duong-dan> [ten hien thi]` — nap tai lieu vao knowledge base.

    CHI ADMIN. Cuong che bang chinh cho dat lenh nay: khong co route HTTP nao goi
    toi ingest_file(), nen ai chay duoc lenh tren may chu thi moi nap duoc.
    Moi lan nap ghi lai nguoi nap vao kb_document.ingested_by (master-plan 3.4).
    """
    if not args:
        print("Dung: ingest <duong-dan> [ten hien thi]", file=sys.stderr)
        print(f"Duoi ho tro: {', '.join(SUPPORTED)}", file=sys.stderr)
        return 1

    path = Path(args[0]).expanduser()
    if not path.is_file():
        print(f"Khong thay tep: {path}", file=sys.stderr)
        return 1

    title = " ".join(args[1:]) or None
    # Ten nguoi nap: ghi lai ai da dua tai lieu nao vao. Khong co he thong tai khoan
    # nen lay ten dang nhap he dieu hanh — du de truy khi can, va trung thuc ve viec
    # no khong phai mot danh tinh da xac thuc.
    try:
        result = await ingest_file(path, ingested_by=f"cli:{getpass.getuser()}", title=title)
    except (UnsupportedDocumentError, ValueError) as error:
        print(f"Khong nap duoc: {error}", file=sys.stderr)
        return 1

    if result.skipped:
        print(f"Tai lieu khong doi (ban {result.version}), khong nap lai.")
        return 0

    print(f'Da nap "{result.title}" ban {result.version}: {result.chunks} chunk.')
    print(
        "Neu day la tai lieu DAU TIEN, khoi dong lai worker de cong cu "
        "search_knowledge_base duoc khai bao."
    )
    return 0


async def stats_command(args: list[str]) -> int:
    """`stats [so-ngay]` — tien di dau, cham o dau, cache co an khong.

    Doc thang tu `usage_log`, khong can dung Grafana hay Prometheus. Bang do da co
    du lieu that tu ngay dau; mot lenh doc no dung duoc ngay hom nay, con dashboard
    thi la buoc sau.
    """
    try:
        days = int(args[0]) if args else 7
    except ValueError:
        print("So ngay phai la mot so nguyen.", file=sys.stderr)
        return 1

    settings = get_settings()
    spent, budget = await budget_today(settings.DAILY_BUDGET_USD)
    print(f"Hom nay: ${spent:.4f} / ${budget:.2f} ngan sach ({spent / budget * 100:.0f}%)")

    routes = await route_stats(days)
    if not routes:
        print(f"\nChua co lan goi nao trong {days} ngay qua.")
        return 0

    print(f"\n{days} ngay qua, theo route:")
    header = f"  {'route':<14}{'goi':>6}{'loi':>5}{'in':>10}{'out':>9}{'cache':>9}"
    print(f"{header}{'USD':>10}{'tb ms':>8}{'p95 ms':>8}")
    for r in routes:
        print(
            f"  {r.route:<14}{r.calls:>6}{r.errors:>5}{r.input_tokens:>10}"
            f"{r.output_tokens:>9}{r.cache_read_tokens:>9}"
            f"{r.cost_usd:>10.4f}{r.avg_latency_ms:>8}{r.p95_latency_ms:>8}"
        )
    print(f"  {'TONG':<14}{sum(r.calls for r in routes):>6}"
          f"{sum(r.errors for r in routes):>5}{'':>28}"
          f"{sum(r.cost_usd for r in routes):>10.4f}")

    turns = await turn_stats(days)
    if turns:
        print("\nDo tre CA LUOT (thu nguoi dung cam nhan), muc tieu trong ngoac:")
        for t in turns:
            nhan = "co tra cuu" if t.used_tools else "khong tra cuu"
            muc_tieu = 15_000 if t.used_tools else 5_000
            dat = "DAT " if t.p95_ms < muc_tieu else "TRUOT"
            print(
                f"  {dat} {nhan:<14}{t.turns:>4} luot   "
                f"p50 {t.p50_ms:>6}ms   p95 {t.p95_ms:>6}ms   (muc tieu p95 < {muc_tieu}ms)"
            )

    cache = await cache_stats(days)
    if cache.total_calls:
        ti_le = cache.calls_with_cache / cache.total_calls * 100
        print(
            f"\nPrompt caching: {cache.calls_with_cache}/{cache.total_calls} luot "
            f"({ti_le:.0f}%), trung binh {cache.avg_cached_tokens} token doc tu cache."
        )
        if cache.calls_with_cache == 0:
            # Khong phai canh bao cho vui: mat cache la tra gia day du cho ~1500
            # token o MOI cau hoi, va khong co dong nao khac bao dieu do.
            print(
                "  CANH BAO: khong luot nao an cache. Kiem xem SYSTEM_PROMPT co bi "
                "noi suy bien vao khong (agents/prompt/system.py)."
            )

    messages = await message_stats(days)
    if messages:
        print("\nTin nhan theo ngay (vao / bot tra loi):")
        for ngay, vao, ra in messages:
            print(f"  {ngay}  {vao:>5} / {ra:<5}")
    return 0


async def review_command(args: list[str]) -> int:
    """`review <platform> <thread_id> [ok|bo] [so...]` — duyet SAU fact bot tu ghi.

    Day la lop duyet cua human-ON-the-loop: bot da ghi roi, nguoi xem lai va bo cai
    sai. Xem agents/policy/autonomy.py de biet vi sao la "on" chu khong phai "in".

    L3 implicit tat tu Giai doan 7 voi mot ly do ghi thang trong code: no ghi thong
    tin ve NGUOI CO TEN ma khong ai bam nut dong y. Dieu kien de bat khong phai them
    mot lop chan (ba lop da co) ma la NHIN THAY duoc bot da ghi gi. Lenh nay la cai do.
    """
    if len(args) < 2 or args[0] not in _PLATFORMS:
        print("Dung: review <platform> <thread_id> [ok|bo] [so...]", file=sys.stderr)
        print(f"platform: {' | '.join(_PLATFORMS)}", file=sys.stderr)
        return 1

    platform: Platform = args[0]
    scope = ThreadScope(platform=platform, thread_id=args[1])
    lenh = args[2] if len(args) > 2 else "xem"

    facts = await cho_duyet(scope)
    if not facts:
        print("Khong co fact tu dong nao dang cho duyet.")
        return 0

    if lenh == "xem":
        print(f"{len(facts)} fact bot TU GHI, chua ai xem lai:\n")
        for i, f in enumerate(facts, start=1):
            khi = f.created_at.strftime("%Y-%m-%d %H:%M")
            print(f"  {i}. [{f.subject_id}] {f.content}")
            print(f"     tin cay {f.confidence:.2f}, ghi luc {khi}")
        print("\n  review ... ok        danh dau da xem TAT CA")
        print("  review ... ok 1 3    chi danh dau so 1 va 3")
        print("  review ... bo 2      XOA so 2 (soft delete, khong khoi phuc duoc)")
        return 0

    if lenh not in ("ok", "bo"):
        print(f"Lenh khong biet: {lenh}. Co: ok | bo", file=sys.stderr)
        return 1

    # So thu tu bat dau tu 1; khong co so nao = tat ca.
    so = [int(x) for x in args[3:] if x.isdigit()]
    chon = [facts[n - 1] for n in so if 1 <= n <= len(facts)] if so else facts
    if not chon:
        print("Khong so nao nam trong danh sach.", file=sys.stderr)
        return 1

    boi = f"cli:{getpass.getuser()}"
    ids = [f.id for f in chon]
    if lenh == "ok":
        n = await danh_dau_da_duyet(scope, ids, boi)
        print(f"Da danh dau {n} fact la da xem.")
    else:
        n = await revoke(scope, ids, revoked_by=boi)
        print(f"Da xoa {n} fact. Chung khong con vao prompt nua.")
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
        elif command == "ingest":
            return await ingest_command(sys.argv[2:])
        elif command == "stats":
            return await stats_command(sys.argv[2:])
        elif command == "review":
            return await review_command(sys.argv[2:])
        else:
            print(
                f"Lenh khong biet: {command}. "
                "Co: migrate | chat | allow | deny | allowed | memory | review | ingest | stats",
                file=sys.stderr,
            )
            return 1
        return 0
    finally:
        # Ca migrate lan chat deu ket thuc duoc, nen luon dong ket noi — con treo mot
        # pool Postgres la process khong bao gio thoat.
        await asyncio.gather(close_db(), close_redis(), close_http(), return_exceptions=True)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
