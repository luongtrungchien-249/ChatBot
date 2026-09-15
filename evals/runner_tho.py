"""Bo danh gia TONG THE cho duong lam tho. Anh em voi evals/runner.py (phia RAG).

    uv run python evals/runner_tho.py
    uv run python evals/runner_tho.py --so-luot 1 --nhanh    # xem nhanh, KHONG ket luan

VI SAO TEP NAY CAN TON TAI. Truoc no, moi con so ve tho trong du an deu den tu mot
script tam voi danh sach chu de tu che, moi lan mot khac. Hau qua do duoc:

    van  8,40  (nguoi con gai VN xua)
        11,12  (uong nuoc nho nguon)
        13,33  (mua thu Ha Noi)

Cung cau hinh, cung n — chenh 4,9 diem CHI VI DOI CHU DE. Lon hon moi cai thien do
duoc trong hai ngay. Tuc khong the tra loi "he thong co tot len khong" bang cach chay
mot chu de roi so voi lan truoc.

BON QUYET DINH THIET KE, moi cai sua mot cho da tung lam hong phep do:

1. BO CHU DE DONG BANG (evals/tho/bo_chuan.jsonl, 40 de, 14 chu the).
   So sanh duoc giua cac lan chay la nho DUNG CHUNG MOT BO, khong phai nho can bang do
   kho — do kho cua tung de thi khong doan truoc duoc, chi giu co dinh duoc.

   Bo nay lay tu tap TEST cua RLVR (ops/sinh_chu_de.py), nen no DA tach khoi tap huan
   luyen theo chu the. Train RLVR xong van danh gia duoc bang chinh bo nay.

2. NEO DUOC CHAM TRONG CUNG LUOT.
   Truoc day tran cua thang (ca dao: sang tao 2,75) do o mot lan chay KHAC. Neu nguoi
   cham troi giua hai lan thi so sanh do vo nghia ma khong ai biet. Gio ca dao (TRAN)
   va van xuoi xuong dong (SAN) di CUNG mot me cham, cung mot me goi.

3. HAI LUOT DOC LAP, TU DONG.
   `LAP_Y` tung cho +1,38 TONG va `y nghia` +0,35 +/- 0,35 o luot 1 — vua du "co y
   nghia thong ke" — roi luot 2 dao dau han. Mot luot khong ket luan duoc, va bat nguoi
   chay nho chay hai lan thi se co ngay quen.

4. THANG TAT DINH KHONG LAM PHAN QUYET CUOI.
   Do la ham he thong duoc toi uu de toi da hoa (`phan_thuong` dung chinh no). Goodhart:
   khi mot thuoc do tro thanh muc tieu, no thoi la thuoc do tot. Nen phan quyet phai
   dua vao NOI DUNG (nguoi cham) va vao khoang cach toi NEO, con thang 45 chi de theo
   doi hoi quy ve LUAT.
"""

import argparse
import asyncio
import json
import statistics
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
for _p in ("src", "."):
    sys.path.insert(0, str(GOC / _p))

from agents.domain.message import InboundMessage  # noqa: E402
from agents.domain.thread import ThreadScope  # noqa: E402
from agents.pipeline.handle_message import Failed, handle_message  # noqa: E402
from evals.metrics.tho_hay import MUC, cham_tho_hay  # noqa: E402
from infra.db import close_db  # noqa: E402
from infra.http import close_http  # noqa: E402
from infra.redis_client import close_redis  # noqa: E402
from tho.cham_diem import cham_tat_dinh  # noqa: E402
from tho.luat import kiem_luc_bat  # noqa: E402
from tho.phan_thuong import phan_thuong  # noqa: E402
from tho.sinh import so_cau_chep  # noqa: E402
from tho.tu_vung import cum_kha_nghi  # noqa: E402

#: Ma thoat — giong evals/runner.py de CI doi xu nhu nhau.
EXIT_DAT = 0
EXIT_TRUOT = 1
EXIT_CHUA_DU_DU_LIEU = 2

BO_CHUAN = GOC / "evals" / "tho" / "bo_chuan.jsonl"
SO_KET_QUA = GOC / "evals" / "tho" / "so_ket_qua.jsonl"
BAI_DA_SINH = GOC / "evals" / "tho" / "bai_da_sinh.jsonl"

#: Van ban "KHONG PHAI THO" — chan ngan sach, loi he thong... Gap la BO ca luot chay.
#:
#: Da mot lan cham van ban bao het ngan sach nhu mot bai tho va cho ra 28,2/100. Mot bo
#: danh gia tra ve so RAC con te hon mot bo khong chay.
_KHONG_PHAI_THO = ("ngân sách", "chưa trả lời được", "Mình chưa hiểu", "quá nhiều tin nhắn")

#: NEO TREN — tho da duoc thua nhan. Diem cua bot phai doc SO VOI day, khong doc tuyet doi.
NEO_TREN: tuple[str, ...] = (
    "Công cha như núi Thái Sơn\nNghĩa mẹ như nước trong nguồn chảy ra\n"
    "Một lòng thờ mẹ kính cha\nCho tròn chữ hiếu mới là đạo con",
    "Anh đi anh nhớ quê nhà\nNhớ canh rau muống nhớ cà dầm tương\n"
    "Nhớ ai dãi nắng dầm sương\nNhớ ai tát nước bên đường hôm nao",
    "Trong đầm gì đẹp bằng sen\nLá xanh bông trắng lại chen nhị vàng\n"
    "Nhị vàng bông trắng lá xanh\nGần bùn mà chẳng hôi tanh mùi bùn",
    "Trâu ơi ta bảo trâu này\nTrâu ra ngoài ruộng trâu cày với ta\n"
    "Cấy cày vốn nghiệp nông gia\nTa đây trâu đấy ai mà quản công",
)

#: NEO DUOI — van xuoi xuong dong. Neu bot khong hon HAN cai nay thi moi con so o tren
#: deu vo nghia, va phai nghi nguoi cham hong truoc khi nghi he thong hong.
#:
#: NANG TU 2 LEN 6 BAI ngay 15/09/2026, sau khi do tren 4 luot chay:
#:
#:                 so bai   bien do     sd
#:     ca dao         4       2,50     1,05
#:     bot           40       1,63     0,78
#:     van xuoi       2       6,00     2,55   <- gap 3 lan neo tren
#:
#:     ca dao - bot     13,92 +/- 0,51   ON DINH
#:     bot - van xuoi    4,71 +/- 2,43   KHONG on dinh
#:
#: TOAN BO dao dong cua phep dinh vi den tu day. Hai bai thi mot bai bi cham lech 3
#: diem la keo ca neo di 1,5; con bot co 40 bai nen nhieu tu trung binh mat het.
#:
#: Sau bai van la it, nhung do la muc con soan tay duoc ma khong phai bia van ban vo
#: nghia. Phai do lai sau vai luot nua.
NEO_DUOI: tuple[str, ...] = (
    "Hôm nay trời nắng đẹp lắm\nTôi đi ra chợ mua rau\n"
    "Rau hôm nay hơi đắt một chút\nNhưng mà vẫn phải mua thôi",
    "Hà Nội có nhiều đường phố\nMùa thu thì lá rụng nhiều\n"
    "Người ta hay đi chơi hồ\nTrời se lạnh vào buổi tối",
    "Mẹ tôi năm nay đã già rồi\nMẹ hay ngồi ở ngoài hiên\n"
    "Buổi chiều mẹ thường quét sân\nRồi mẹ vào nhà nấu cơm",
    "Quê tôi ở một tỉnh miền Trung\nỞ đó có biển và có núi\n"
    "Mùa hè thì rất là nóng\nMùa đông thì lại hơi lạnh",
    "Tôi nhớ hồi còn đi học\nLớp tôi có ba mươi bạn\n"
    "Thầy giáo dạy môn toán rất hiền\nCuối năm cả lớp đi chơi",
    "Con sông chảy qua làng tôi\nNước sông thì không sâu lắm\n"
    "Trẻ con hay ra đó tắm\nNgười lớn thì đi làm đồng",
)

#: NGUONG — deu la nguong MUON. Xem chu thich tung cai.
#:
#: Dat nguong theo NEO chu khong theo con so tuyet doi: "ngon ngu >= 5,0" khong noi len
#: gi neu nguoi cham hom do cham chat hon moi khi. "ngon ngu >= 55% cua ca dao" thi co.
TI_LE_NEO_TREN_MIN = 0.55  # noi dung cua bot / noi dung cua ca dao
#: Bot phai hon van xuoi it nhat bay nhieu diem noi dung.
#:
#: 2,0 la mot nguong DAT SAI, va do duoc: tren 4 luot, `bot - van xuoi` ra
#: [5,00 · 1,68 · 4,55 · 7,60]. Luot thu hai SE TRUOT — vi nhieu cua neo hai bai, khong
#: vi he thong hong.
#:
#: TAM HA VE 1,0 va danh dau CHUA CHOT. Dung nang lai cho toi khi co ~5 luot voi neo
#: sau bai de biet no dao dong bao nhieu. Chinh evals/runner.py da ghi bai hoc nay cho
#: `Answer Relevance`: "mot job do mai la mot job khong ai doc nua".
CACH_NEO_DUOI_MIN = 1.0
DUNG_KHUNG_MIN = 0.90
CUM_BI_BE_MAX = 0.10
CHEP_MAX = 0.0
P95_MAX_MS = 6_000

#: Chenh toi da cho phep GIUA HAI LUOT tren thang noi dung. Vuot = phep do khong on
#: dinh, va luc do KHONG duoc ket luan gi ca — ke ca ket luan xau.
LECH_HAI_LUOT_MAX = 3.0


@dataclass(slots=True)
class KetQuaLuot:
    """Mot luot chay tren toan bo bo chuan."""

    tat_dinh: float = 0.0
    thuong: float = 0.0
    dung_khung: float = 0.0
    sach_van: float = 0.0
    cum_bi_be: float = 0.0
    chep: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    noi_dung: dict[str, float] = field(default_factory=dict)
    noi_dung_neo_tren: dict[str, float] = field(default_factory=dict)
    noi_dung_neo_duoi: dict[str, float] = field(default_factory=dict)
    so_bai: int = 0


class Kenh:
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
        thread_id=f"dgt-{i}-{uuid.uuid4().hex[:6]}",
        sender_id=f"dgt-{i}",
        sender_name="Bạn",
        text=f"Làm cho mình một bài thơ lục bát về chủ đề {chu_de}",
        is_group=False,
        mentioned_bot=True,
        message_id=str(uuid.uuid4()),
        timestamp=int(time.time() * 1000),
        trace_id=str(uuid.uuid4()),
    )


def _chi_bai_tho(van_ban: str) -> str:
    """Bo cau bao loi ma `tra_loi()` gan them khi con sai luat."""
    return van_ban.split("\n\n(")[0].strip()


async def _cham_nhieu(bai: list[str]) -> dict[str, float] | None:
    """Trung binh cac muc noi dung. None = cham hong qua nhieu.

    None CHU KHONG 0: coi bai CHUA CHAM DUOC nhu bai 0 diem thi con so phu thuoc vao
    chat luong MANG chu khong vao chat luong THO.
    """
    diem: list[dict[str, float]] = []
    hong = 0
    for b in bai:
        try:
            d = await cham_tho_hay(b, str(uuid.uuid4()))
        except Exception:
            d = None
        if d is None:
            hong += 1
        else:
            diem.append(d)
    if not diem or hong > len(bai) * 0.2:
        print(
            f"    người chấm hỏng {hong}/{len(bai)} — BỎ phần nội dung",
            file=sys.stderr,
        )
        return None
    return {m: statistics.mean(d[m] for d in diem) for m, _ in MUC}


async def _cham_tung_bai(bai: list[str]) -> list[dict[str, float] | None]:
    """Diem TUNG BAI, giu nguyen thu tu. `None` cho bai cham hong.

    Tach khoi `_cham_nhieu` vi hai muc dich khac nhau: cai kia cho ra mot con so de
    phan quyet, cai nay giu lai tung bai de `ops/cham_tay.py` rut mau hieu chuan.
    """
    ra: list[dict[str, float] | None] = []
    for b in bai:
        try:
            ra.append(await cham_tho_hay(b, str(uuid.uuid4())))
        except Exception:
            ra.append(None)
    return ra


async def chay_mot_luot(
    chu_de: list[str], deps: object, kenh: Kenh, nhan: str, luu_bai: bool = False
) -> KetQuaLuot | None:
    print(f"\n--- {nhan}: sinh {len(chu_de)} bài ---", flush=True)
    bai: list[str] = []
    ms: list[float] = []
    for i, cd in enumerate(chu_de):
        truoc = len(kenh.thu)
        t0 = time.monotonic()
        try:
            kq = await handle_message(_tin(cd, i), deps)  # type: ignore[arg-type]
        except Exception as loi:
            print(f"  [{i}] {cd}: NÉM RA {type(loi).__name__}", file=sys.stderr)
            continue
        if isinstance(kq, Failed) or len(kenh.thu) == truoc:
            print(f"  [{i}] {cd}: không có trả lời", file=sys.stderr)
            continue
        van_ban = kenh.thu[-1]
        if any(x.lower() in van_ban.lower() for x in _KHONG_PHAI_THO):
            print(f"  [{i}] {cd}: KHÔNG PHẢI THƠ — {van_ban[:50]}", file=sys.stderr)
            continue
        ms.append((time.monotonic() - t0) * 1000)
        bai.append(_chi_bai_tho(van_ban))

    if len(bai) < len(chu_de):
        print(
            f"  DỪNG {nhan}: chỉ {len(bai)}/{len(chu_de)} lượt ra thơ. Không kết luận.",
            file=sys.stderr,
        )
        return None

    td = [cham_tat_dinh(b) for b in bai]
    t = sorted(ms)

    def pv(q: float) -> float:
        i = q * (len(t) - 1)
        lo, hi = int(i), min(int(i) + 1, len(t) - 1)
        return t[lo] + (t[hi] - t[lo]) * (i - lo)

    print(
        f"  chấm nội dung: {len(bai)} bài + {len(NEO_TREN)} neo trên"
        f" + {len(NEO_DUOI)} neo dưới"
    )
    if luu_bai:
        # Luu TUNG bai kem diem may, de ops/cham_tay.py rut mau hieu chuan.
        #
        # Ghi DE chu khong noi them: bo cham tay phai ung voi MOT lan chay, neu
        # khong thi 30 bai rut ra se tron lan nhieu phien ban he thong khac nhau va
        # tuong quan do duoc khong thuoc ve phien ban nao ca.
        diem_tung_bai = await _cham_tung_bai(bai)
        BAI_DA_SINH.parent.mkdir(parents=True, exist_ok=True)
        dong = [
            json.dumps({"tho": b, "may": d}, ensure_ascii=False)
            for b, d in zip(bai, diem_tung_bai, strict=True)
            if d is not None
        ]
        BAI_DA_SINH.write_text("\n".join(dong) + "\n", encoding="utf-8", newline="\n")
        print(f"  đã lưu {len(bai)} bài -> {BAI_DA_SINH.relative_to(GOC)}")
    return KetQuaLuot(
        tat_dinh=statistics.mean(x.tong for x in td),
        thuong=statistics.mean(phan_thuong(b).tong for b in bai),
        dung_khung=sum(1 for x in td if x.the >= 9.99) / len(bai),
        sach_van=sum(1 for b in bai if not kiem_luc_bat(b, kiem_bang_trac=False)) / len(bai),
        cum_bi_be=sum(1 for b in bai if cum_kha_nghi(b)) / len(bai),
        chep=sum(1 for b in bai if so_cau_chep(b)) / len(bai),
        p50_ms=pv(0.50),
        p95_ms=pv(0.95),
        noi_dung=await _cham_nhieu(bai) or {},
        noi_dung_neo_tren=await _cham_nhieu(list(NEO_TREN)) or {},
        noi_dung_neo_duoi=await _cham_nhieu(list(NEO_DUOI)) or {},
        so_bai=len(bai),
    )


def _sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return "?"


def in_bang(luot: list[KetQuaLuot]) -> None:
    print("\n" + "=" * 78)
    print(f"ĐÁNH GIÁ TỔNG THỂ — {len(luot)} lượt độc lập, {luot[0].so_bai} bài mỗi lượt")
    print("=" * 78)

    def cot(lay: "Callable[[KetQuaLuot], float]", dinh: str = ".2f") -> str:
        v = [lay(x) for x in luot]
        s = "".join(f"{x:>12{dinh}}" for x in v)
        if len(v) > 1:
            s += f"{max(v) - min(v):>12{dinh}}"
        return s

    dau = f"  {'':<22}" + "".join(f"{'lượt ' + str(i + 1):>12}" for i in range(len(luot)))
    if len(luot) > 1:
        dau += f"{'lệch':>12}"
    print(dau)
    print(f"  {'LUẬT (theo dõi)':<22}")
    print(f"    {'tất định /45':<20}" + cot(lambda x: x.tat_dinh))
    print(f"    {'thưởng RLVR':<20}" + cot(lambda x: x.thuong, ".3f"))
    print(f"    {'đúng khung':<20}" + cot(lambda x: x.dung_khung, ".0%"))
    print(f"    {'sạch cả vần':<20}" + cot(lambda x: x.sach_van, ".0%"))
    print(f"  {'LÁCH (phải bằng 0)':<22}")
    print(f"    {'cụm bị bẻ':<20}" + cot(lambda x: x.cum_bi_be, ".0%"))
    print(f"    {'chép bài mẫu':<20}" + cot(lambda x: x.chep, ".0%"))
    print(f"  {'ĐỘ TRỄ':<22}")
    print(f"    {'p50 ms':<20}" + cot(lambda x: x.p50_ms, ".0f"))
    print(f"    {'p95 ms':<20}" + cot(lambda x: x.p95_ms, ".0f"))

    if all(x.noi_dung for x in luot):
        print(f"  {'NỘI DUNG (phán quyết)':<22}")
        for m, toi_da in MUC:
            if m == "nhip":
                continue
            def lay(x: KetQuaLuot, m: str = m) -> float:
                return x.noi_dung[m]

            print(f"    {m + ' /' + str(toi_da):<20}" + cot(lay))


def _tb(luot: list[KetQuaLuot], lay: "Callable[[KetQuaLuot], float]") -> float:
    return statistics.mean(lay(x) for x in luot)


def phan_quyet(luot: list[KetQuaLuot]) -> list[str]:
    """Nhung nguong bi vi pham. Rong = DAT."""
    hong: list[str] = []

    if len(luot) > 1 and all(x.noi_dung for x in luot):
        tong = [sum(x.noi_dung.values()) for x in luot]
        lech = max(tong) - min(tong)
        if lech > LECH_HAI_LUOT_MAX:
            hong.append(
                f"HAI LƯỢT LỆCH {lech:.2f} > {LECH_HAI_LUOT_MAX} — phép đo không ổn định, "
                "KHÔNG kết luận gì (kể cả kết luận xấu)"
            )
            return hong

    if _tb(luot, lambda x: x.dung_khung) < DUNG_KHUNG_MIN:
        hong.append(f"đúng khung {_tb(luot, lambda x: x.dung_khung):.0%} < {DUNG_KHUNG_MIN:.0%}")
    if _tb(luot, lambda x: x.cum_bi_be) > CUM_BI_BE_MAX:
        hong.append(f"cụm bị bẻ {_tb(luot, lambda x: x.cum_bi_be):.0%} > {CUM_BI_BE_MAX:.0%}")
    if _tb(luot, lambda x: x.chep) > CHEP_MAX:
        hong.append(f"chép bài mẫu {_tb(luot, lambda x: x.chep):.0%} > {CHEP_MAX:.0%}")
    if _tb(luot, lambda x: x.p95_ms) > P95_MAX_MS:
        hong.append(f"p95 {_tb(luot, lambda x: x.p95_ms):.0f} ms > {P95_MAX_MS} ms")

    if not all(x.noi_dung and x.noi_dung_neo_tren and x.noi_dung_neo_duoi for x in luot):
        hong.append("KHÔNG chấm được nội dung hoặc neo — chưa đủ để kết luận")
        return hong

    bot = _tb(luot, lambda x: sum(x.noi_dung.values()))
    tren = _tb(luot, lambda x: sum(x.noi_dung_neo_tren.values()))
    duoi = _tb(luot, lambda x: sum(x.noi_dung_neo_duoi.values()))
    print(f"\n  NEO:  ca dao {tren:.2f}   ·   bot {bot:.2f}   ·   văn xuôi {duoi:.2f}")
    if tren <= duoi:
        hong.append(
            f"NEO SAI THỨ TỰ: ca dao {tren:.2f} <= văn xuôi {duoi:.2f} — "
            "người chấm hỏng, mọi số khác vô nghĩa"
        )
        return hong
    if bot - duoi < CACH_NEO_DUOI_MIN:
        hong.append(f"bot chỉ hơn văn xuôi {bot - duoi:.2f} < {CACH_NEO_DUOI_MIN}")
    if tren and bot / tren < TI_LE_NEO_TREN_MIN:
        hong.append(f"bot / ca dao = {bot / tren:.0%} < {TI_LE_NEO_TREN_MIN:.0%}")
    return hong


async def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")

    bo = argparse.ArgumentParser(description="Danh gia tong the duong lam tho")
    bo.add_argument("--so-luot", type=int, default=2)
    bo.add_argument("--nhanh", action="store_true", help="chi 10 chu de, KHONG ket luan")
    bo.add_argument(
        "--luu-bai",
        action="store_true",
        help="luu tung bai + diem may — bat buoc truoc khi cham tay",
    )
    tham = bo.parse_args()

    if not BO_CHUAN.exists():
        print(f"CHUA CO {BO_CHUAN}", file=sys.stderr)
        return EXIT_CHUA_DU_DU_LIEU

    chu_de = [
        json.loads(d)["chu_de"]
        for d in BO_CHUAN.read_text(encoding="utf-8").splitlines()
        if d.strip()
    ]
    if tham.nhanh:
        chu_de = chu_de[:10]

    print(f"bộ chuẩn {len(chu_de)} đề · {tham.so_luot} lượt · sha {_sha()}")
    if tham.so_luot < 2:
        print("CẢNH BÁO: 1 lượt KHÔNG kết luận được. Xem chỗ thiết kế số 3 ở đầu tệp.")

    from main.container import build_deps

    kenh = Kenh()
    deps = await build_deps(kenh)

    luot: list[KetQuaLuot] = []
    for i in range(tham.so_luot):
        kq = await chay_mot_luot(
            chu_de, deps, kenh, f"lượt {i + 1}", luu_bai=tham.luu_bai and i == 0
        )
        if kq is None:
            await close_db()
            await close_redis()
            await close_http()
            return EXIT_CHUA_DU_DU_LIEU
        luot.append(kq)

    in_bang(luot)
    hong = phan_quyet(luot)

    print()
    if hong:
        print("  TRƯỢT:")
        for h in hong:
            print(f"    - {h}")
    else:
        print("  ĐẠT — mọi ngưỡng đều qua.")

    SO_KET_QUA.parent.mkdir(parents=True, exist_ok=True)
    with SO_KET_QUA.open("a", encoding="utf-8", newline="\n") as f:
        f.write(
            json.dumps(
                {
                    "luc": datetime.now(UTC).isoformat(timespec="seconds"),
                    "sha": _sha(),
                    "so_chu_de": len(chu_de),
                    "so_luot": len(luot),
                    "dat": not hong,
                    "vi_pham": hong,
                    "luot": [
                        {
                            "tat_dinh": x.tat_dinh, "thuong": x.thuong,
                            "dung_khung": x.dung_khung, "sach_van": x.sach_van,
                            "cum_bi_be": x.cum_bi_be, "p50_ms": x.p50_ms, "p95_ms": x.p95_ms,
                            "noi_dung": x.noi_dung, "neo_tren": x.noi_dung_neo_tren,
                            "neo_duoi": x.noi_dung_neo_duoi,
                        }
                        for x in luot
                    ],
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    print(f"\n  đã ghi vào {SO_KET_QUA.relative_to(GOC)}")

    await close_db()
    await close_redis()
    await close_http()
    return EXIT_TRUOT if hong else EXIT_DAT


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
