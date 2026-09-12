"""Sinh tho, in ra cac cum bi NGHI BE de nguoi doc phan xu.

Chay:
    uv run python ops/soi_cum_nghi.py            # 20 chu de x 4 ban
    uv run python ops/soi_cum_nghi.py --so 40    # nhieu hon

VI SAO CAN CONG CU NAY. Bo do bat cum bi be (`tho/tu_vung.py`) co do chinh xac ~29% tren
tho that — phan lon cai no bao la TU THAT chua co trong danh sach. Moi lan doc va them
nhung tu do vao la mot lan bo do chinh xac hon.

Vong lap: chay -> doc -> them tu that vao `_NGUON` trong tho/tu_vung.py -> chay lai.

VI SAO PHAI DOC BANG MAT, khong tu dong hoa duoc: phan biet "mơ mang" (bi be, tu that la
"mơ màng") voi "mùa màng" (tu that) doi biet NGHIA. Do dung la thu can mot tu dien, va
tu dien du lon thi deu la GPL — xem docstring `tho/tu_vung.py`.

CANH BAO QUAN TRONG: chi them nhung tu ban thay o DAY, tuc tim duoc tren THO CUA BOT.
DUNG rut tu tu Truyen Kieu roi them vao de ha ti le bao nham tren chinh Truyen Kieu —
do la hoc vet corpus do, va no bien con so hieu chuan thanh vo nghia. Xem
docs/plan-sua-bo-do-be-chu.md muc 2.
"""

import argparse
import asyncio
import sys
import uuid
from collections import Counter
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "src"))

from agents.domain.thread import ThreadScope  # noqa: E402
from agents.ports.llm import CallContext, UserMessage  # noqa: E402
from infra.db import close_db  # noqa: E402
from infra.http import close_http  # noqa: E402
from infra.redis_client import close_redis  # noqa: E402
from llm.openai_client import llm  # noqa: E402
from tho.prompt import system_prompt, yeu_cau  # noqa: E402
from tho.sinh import SO_BAN, _sach  # noqa: E402
from tho.tu_vung import TU_GHEP, cum_nghi_be  # noqa: E402

CHU_DE = [
    "người con gái đẹp thời xưa", "cha mẹ", "hoa sen", "mùa thu Hà Nội", "mưa đêm",
    "dòng sông quê", "tuổi học trò", "biển chiều", "cánh đồng lúa", "phố cổ",
    "bến đò", "cây đa đầu làng", "tiếng ve mùa hạ", "chiều đông", "vườn nhà",
    "con đường đến trường", "khói bếp", "trăng rằm", "tết quê", "áo dài",
    "người lính", "mẹ tảo tần", "đêm trung thu", "giếng nước", "con diều",
    "mùa gặt", "bà ngoại", "chợ quê", "lũy tre", "dòng kênh",
    "mái đình", "sương sớm", "đồi chè", "thuyền chài", "cầu tre",
    "ao làng", "lời ru", "hàng cau", "bếp lửa", "sông Hương",
]


async def _mot_ban(chu_de: str) -> str:
    kq = await llm.reply(
        system=system_prompt("luc_bat"),
        messages=(UserMessage(content=yeu_cau(chu_de)),),
        max_tokens=4_000,
        effort="low",
        ctx=CallContext(
            scope=ThreadScope(platform="cli", thread_id="soi-cum"),
            sender_id="soi-cum",
            trace_id=str(uuid.uuid4()),
        ),
        route="poem",
    )
    return _sach(kq.text)


async def chay(so_chu_de: int) -> int:
    dem: Counter[str] = Counter()
    vi_du: dict[str, str] = {}
    n = 0
    for chu_de in CHU_DE[:so_chu_de]:
        ban = await asyncio.gather(
            *(_mot_ban(chu_de) for _ in range(SO_BAN)), return_exceptions=True
        )
        for b in ban:
            if isinstance(b, BaseException) or not b:
                continue
            n += 1
            for cum, dung in cum_nghi_be(b):
                dem[cum] += 1
                vi_du.setdefault(cum, dung)

    print(f"{n} bản nháp · {len(TU_GHEP)} từ trong danh sách\n")
    if not dem:
        print("Không cụm nào bị nghi. Chạy lại với --so lớn hơn.")
        return 0

    print(f"  {'cụm bị nghi':<22} {'lần':>4}   từ thật gần nhất")
    print("  " + "-" * 60)
    for cum, k in dem.most_common():
        print(f"  {cum:<22} {k:>4}   {vi_du[cum]}")

    print("""
  ĐỌC BẰNG MẮT rồi phân làm hai:

    a) TỪ THẬT bị báo nhầm  -> thêm vào `_NGUON` trong src/tho/tu_vung.py
       Thêm tiếng đầu X thì phải thêm CẢ các bạn thường gặp của X, kẻo báo nhầm chỗ khác.

    b) CHỮ BỊ BẺ thật       -> để nguyên, đó là việc bộ dò làm đúng

  Sau khi thêm, chạy lại:
      uv run python ops/hieu_chuan_tho.py evals/corpus/tho/truyen-kieu.txt
  để chắc tỉ lệ báo nhầm trên thơ chuẩn mực không xấu đi.

  ĐỪNG rút từ TỪ Truyện Kiều để thêm vào — đó là học vẹt chính corpus dùng để hiệu chuẩn.
""")
    return 0


def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")
    bo = argparse.ArgumentParser(description=__doc__)
    bo.add_argument("--so", type=int, default=20, help="số chủ đề (mặc định 20)")
    tham = bo.parse_args()

    async def _chay() -> int:
        try:
            return await chay(max(1, min(tham.so, len(CHU_DE))))
        finally:
            await close_db()
            await close_redis()
            await close_http()

    return asyncio.run(_chay())


if __name__ == "__main__":
    sys.exit(main())
