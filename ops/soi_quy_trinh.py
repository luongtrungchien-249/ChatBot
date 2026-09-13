"""Soi VET cua 10 buoc lam tho, tren mot chu de that, qua model that.

    uv run python ops/soi_quy_trinh.py "uống nước nhớ nguồn"
    uv run python ops/soi_quy_trinh.py "cha mẹ" --so-lan 5

CAI NAY TRA LOI DUOC GI ma mot bai tho tra ve khong tra loi duoc:

  - buoc nao ton do tre  (truoc day chi biet TONG, khong biet ton o dau)
  - buoc nao goi model   (moi luot goi la tien va la mot cho co the timeout)
  - buoc nao CHUA thi cong — in ra dung nhu the, khong to xanh cho du mat

NO KHONG PHAI PHEP DO. n=1 hay n=5 deu khong ket luan duoc gi ve chat luong: hai luot
chay cung mot cau hinh trong du an nay da tung lech nhau 7 diem tren n=6. Muon so sanh
hai cau hinh thi can n>=40 moi nhanh va HAI luot doc lap — xem
docs/plan-quy-trinh-10-buoc.md §4.6.
"""

import argparse
import asyncio
import sys
import time
import uuid
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "src"))

from agents.domain.message import InboundMessage  # noqa: E402
from agents.domain.thread import ThreadScope  # noqa: E402
from agents.pipeline.handle_message import handle_message  # noqa: E402
from infra.db import close_db  # noqa: E402
from infra.http import close_http  # noqa: E402
from infra.redis_client import close_redis  # noqa: E402
from main.container import build_deps  # noqa: E402
from tho.quy_trinh import bang_vet  # noqa: E402
from tho.sinh import KetQua  # noqa: E402


class Kenh:
    """Kenh gia: giu lai van ban thay vi gui di dau."""

    max_message_chars = 4_000

    def __init__(self) -> None:
        self.thu: list[str] = []

    async def typing(self, scope: ThreadScope) -> None:
        return None

    async def send(self, scope: ThreadScope, text: str, reply_to: str | None = None) -> None:
        self.thu.append(text)


def _tin(chu_de: str, i: int) -> InboundMessage:
    return InboundMessage(
        platform="cli",
        thread_id=f"soi-{i}-{uuid.uuid4().hex[:6]}",
        sender_id=f"soi-{i}",
        sender_name="Bạn",
        text=f"Làm cho mình một bài thơ lục bát về chủ đề {chu_de}",
        is_group=False,
        mentioned_bot=True,
        message_id=str(uuid.uuid4()),
        timestamp=int(time.time() * 1000),
        trace_id=str(uuid.uuid4()),
    )


async def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")

    bo = argparse.ArgumentParser(description="In vet 10 buoc lam tho")
    bo.add_argument("chu_de", help="chủ đề bài thơ")
    bo.add_argument("--so-lan", type=int, default=1, help="số lượt chạy (mặc định 1)")
    tham = bo.parse_args()

    # Bat lay KetQua tren duong di. `handle_message` chi tra ve van ban cuoi, con vet
    # nam trong `KetQua` — nen ta doc no ra bang cach boc `sinh_tho`. Lam o ops/ chu
    # khong bat `sinh_tho` tra them gi cho production: vet la thu de doc, khong phai
    # thu de gui.
    import tho.sinh as _sinh
    from agents.pipeline.stages import tho as _stage

    thu: list[tuple[KetQua, float]] = []
    goc = _sinh.sinh_tho

    async def boc(*a: object, **k: object) -> KetQua:
        t0 = time.monotonic()
        kq = await goc(*a, **k)  # type: ignore[arg-type]
        thu.append((kq, (time.monotonic() - t0) * 1000))
        return kq

    # Vá vào CHÍNH module stage, không vá `tho.sinh`: stage đã `from tho.sinh import
    # sinh_tho` lúc nạp, nên tên nó giữ là một tham chiếu riêng — vá `tho.sinh` sẽ
    # không có tác dụng gì và ta sẽ ngồi nhìn một bảng vết rỗng mà không hiểu vì sao.
    _stage.sinh_tho = boc  # type: ignore[attr-defined]

    kenh = Kenh()
    deps = await build_deps(kenh)
    print(f'chủ đề: "{tham.chu_de}" · {tham.so_lan} lượt\n')

    for i in range(tham.so_lan):
        truoc = len(kenh.thu)
        t0 = time.monotonic()
        await handle_message(_tin(tham.chu_de, i), deps)
        ms = (time.monotonic() - t0) * 1000
        if not thu or len(kenh.thu) == truoc:
            print(f"[{i + 1}] không ra thơ — xem log")
            continue
        kq, ms_sinh = thu[-1]

        print("=" * 78)
        print(f"[{i + 1}]  {ms:.0f} ms đầu-cuối · {ms_sinh:.0f} ms trong sinh_tho")
        print("=" * 78)
        print(kenh.thu[-1])
        print()
        print(bang_vet(kq.vet))
        print()

    await close_db()
    await close_redis()
    await close_http()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
