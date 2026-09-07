"""So sanh cac model embedding TREN CHINH du lieu cua du an, roi moi chot.

Cau hoi phai tra loi: co ha duoc xuong model re hon ma khong mat gi khong.

    text-embedding-3-large   $0,13 / 1M token
    text-embedding-3-small   $0,02 / 1M token   -> re hon 6,5 lan

Bang xep hang chung khong tra loi duoc cau do. Cai quyet dinh la model co TACH duoc
ba nhom cap cau cua chinh du an nay khong — cung bo cap ma ops/calibrate_dedupe.py
dung, vi chung la thu nguong DUPLICATE_THRESHOLD phai phan biet.

Ba so do, va chi so thu ba moi la thu dang nhin:

  bat_min    diem THAP nhat trong nhom phai bat (trung y + mau thuan)
  bo_qua_max diem CAO nhat trong nhom phai bo qua (hai fact khac nhau, cung nguoi)
  KHOANG AN TOAN = bat_min - bo_qua_max

Khoang an toan am nghia la KHONG CO nguong nao dung duoc: model do khong phan biet
duoc "cung mot y" voi "hai dieu khac nhau ve cung mot nguoi". Khoang cang rong thi
nguong cang khong nhay cam voi mot cau la.

Rang buoc cung: so chieu phai bang EMBEDDING_DIM de khop cot VECTOR(n). Ca hai model
text-embedding-3-* deu nhan tham so `dimensions` (huan luyen kieu Matryoshka), nen
so sanh o day luon o CUNG so chieu — neu khong thi dang so sanh hai thu khac nhau.

DO NAY TON TIEN THAT (vai phan nghin do la).
Chay: uv run python ops/benchmark_embedding.py
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from calibrate_dedupe import KHAC, MAU_THUAN, QUEN, TRUNG

from config import get_settings
from llm.models import EMBEDDING_PRICES
from memory.dedupe import cosine

#: Cac model dem ra so. Them mot dong la them mot ung vien.
CANDIDATES = ["text-embedding-3-large", "text-embedding-3-small"]

#: Bo tim kiem: doan tai lieu + cau hoi tro toi doan dung.
#:
#: Dedupe chi la MOT trong hai cho dung embedding. Cho kia la RAG, va no hoi mot cau
#: khac han: khong phai "hai cau nay co cung y khong" ma "cau hoi nay tro toi doan
#: nao". Mot model tach tot nhom cap cau van co the xep sai o day, nen phai do ca hai.
DOAN_TAI_LIEU: list[str] = [
    "Don hoan tien duoc xu ly trong 7 ngay lam viec ke tu khi nhan hang tra ve. "
    "Khach hang phai giu nguyen bao bi va hoa don goc. Truong hop hang loi do san "
    "xuat, thoi han rut xuong 3 ngay lam viec va cong ty chiu phi van chuyen.",
    "Nhan vien chinh thuc duoc 12 ngay phep nam. Nhan vien lam tren 5 nam duoc them "
    "2 ngay. Phep khong dung het duoc chuyen sang quy 1 nam sau, toi da 5 ngay.",
    "Quy trinh duyet chi gom ba buoc: truong nhom duyet, ke toan kiem tra chung tu, "
    "giam doc ky. Khoan chi tren 20 trieu dong can them phe duyet cua hoi dong.",
    "Cong ty ho tro chi phi dao tao chuyen mon toi da 10 trieu dong mot nam cho moi "
    "nhan vien, phai dang ky truoc voi truong bo phan va co hoa don hop le.",
    "Gio lam viec tu 8h30 den 17h30, nghi trua mot tieng. Lam them gio phai duoc "
    "truong bo phan duyet truoc va duoc tinh theo quy dinh cua luat lao dong.",
]

#: (cau hoi, chi so doan DUNG trong DOAN_TAI_LIEU)
#:
#: Co y viet bang loi nguoi dung chu khong lap tu cua tai lieu — do moi la ca that.
#: Cau hoi lap y nguyen tu cua tai lieu thi BM25 da du, khong can vector.
CAU_HOI: list[tuple[str, int]] = [
    ("Bao lau thi toi duoc tra lai tien?", 0),
    ("Hang bi loi thi co duoc uu tien khong?", 0),
    ("Mot nam toi duoc nghi bao nhieu ngay?", 1),
    ("Phep thua co bi mat khong?", 1),
    ("Ai phai ky khi chi mot khoan lon?", 2),
    ("Muon di hoc them thi cong ty co tra tien khong?", 3),
    ("May gio thi bat dau lam viec?", 4),
    ("Lam ngoai gio co duoc tinh khong?", 4),
]


async def embed_all(
    model: str, texts: list[str], dimensions: int
) -> tuple[list[list[float]], int, float]:
    """Tra ve (vector, so token, giay). Goi thang SDK chu khong qua get_embedder():
    o day can DOI model theo tung vong, con get_embedder() co y chi doc mot cau hinh.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY, timeout=60.0)
    started = time.monotonic()
    response = await client.embeddings.create(model=model, input=texts, dimensions=dimensions)
    seconds = time.monotonic() - started
    ordered = sorted(response.data, key=lambda d: d.index)
    tokens = response.usage.total_tokens if response.usage else 0
    return [d.embedding for d in ordered], tokens, seconds


def scores(vectors: dict[str, list[float]], pairs: list[tuple[str, str]]) -> list[float]:
    return [cosine(vectors[a], vectors[b]) for a, b in pairs]


async def main() -> int:
    dimensions = get_settings().EMBEDDING_DIM

    # Mot lan embed cho MOI model, dung chung cho moi phep so — de khong tra tien
    # nhieu lan cho cung mot chuoi.
    texts = sorted({t for pairs in (TRUNG, MAU_THUAN, KHAC, QUEN) for pair in pairs for t in pair})
    print(f"{len(texts)} chuoi, {dimensions} chieu, {len(CANDIDATES)} model.\n")

    rows: list[tuple[str, float, float, float, int, float]] = []
    for model in CANDIDATES:
        vectors_list, tokens, seconds = await embed_all(model, texts, dimensions)
        vectors = dict(zip(texts, vectors_list, strict=True))

        phai_bat = scores(vectors, TRUNG) + scores(vectors, MAU_THUAN)
        phai_bo_qua = scores(vectors, KHAC)
        quen = scores(vectors, QUEN)

        bat_min = min(phai_bat)
        bo_qua_max = max(phai_bo_qua)
        rows.append((model, bat_min, bo_qua_max, min(quen), tokens, seconds))

        gia = EMBEDDING_PRICES.get(model, 0.0)
        print(f"--- {model}  (${gia}/1M token) ---")
        print(f"  phai BAT      : {min(phai_bat):.3f} - {max(phai_bat):.3f}")
        print(f"  phai BO QUA   : {min(phai_bo_qua):.3f} - {max(phai_bo_qua):.3f}")
        print(f"  KHOANG AN TOAN: {bat_min - bo_qua_max:+.3f}")
        print(f"  lenh `quen`   : {min(quen):.3f} - {max(quen):.3f}")
        print(f"  {tokens} token, {seconds:.2f}s\n")

    # --- Phan hai: xep hang tim kiem ---
    print("Tim kiem tren doan tai lieu that:")
    print()
    xep_hang: dict[str, tuple[int, float]] = {}
    for model in CANDIDATES:
        doan_vec, _t, _s = await embed_all(model, DOAN_TAI_LIEU, dimensions)
        hoi_vec, _t2, _s2 = await embed_all(model, [q for q, _ in CAU_HOI], dimensions)

        dung = 0
        bien: list[float] = []
        for (cau, mong_doi), vec in zip(CAU_HOI, hoi_vec, strict=True):
            diem = [cosine(vec, d) for d in doan_vec]
            thu_hang = sorted(range(len(diem)), key=lambda i: diem[i], reverse=True)
            top1 = thu_hang[0]
            # Cach biet giua doan DUNG va doan sai tot nhat. Am = xep sai.
            sai_tot_nhat = max(x for i, x in enumerate(diem) if i != mong_doi)
            bien.append(diem[mong_doi] - sai_tot_nhat)
            if top1 == mong_doi:
                dung += 1
            else:
                print(f"  [{model}] SAI: {cau!r} -> doan {top1}, dung la {mong_doi}")

        trung_binh_bien = sum(bien) / len(bien)
        xep_hang[model] = (dung, trung_binh_bien)
        print(
            f"  {model:<26} top-1 dung {dung}/{len(CAU_HOI)}, "
            f"bien trung binh {trung_binh_bien:+.3f}"
        )
    print()

    print("So sanh:")
    print(
        f"  {'model':<26}{'bat_min':>9}{'an toan':>10}"
        f"{'quen_min':>10}{'top-1':>8}{'bien':>9}{'USD/1M':>9}"
    )
    for model, bat_min, bo_qua_max, quen_min, _tokens, _s in rows:
        dung, bien_tb = xep_hang[model]
        print(
            f"  {model:<26}{bat_min:>9.3f}{bat_min - bo_qua_max:>+10.3f}{quen_min:>10.3f}"
            f"{dung:>5}/{len(CAU_HOI):<2}{bien_tb:>+9.3f}{EMBEDDING_PRICES.get(model, 0):>9.2f}"
        )

    hong = [m for m, bat, bo, _q, _t, _s in rows if bat <= bo]
    if hong:
        hong_ten = ', '.join(hong)
        print(f"\nKHONG DUNG DUOC: {hong_ten} — khoang an toan am,")
        print("khong co nguong nao tach duoc hai nhom.")
    print(
        "\nNguong nen dat LECH LEN sat can tren cua khoang an toan: cao qua thi bang co ban\n"
        "trung (phien, khong mat gi); thap qua thi fact moi revoke fact cu (mat thong tin,\n"
        "va im lang)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
