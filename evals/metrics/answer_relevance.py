"""Answer Relevance (RAGAS): cau tra loi co tra loi DUNG CAU DA HOI khong.

Cach do cua RAGAS, va no kheo: bat model doc cau tra loi roi DOAN NGUOC lai xem cau
hoi ban dau la gi. Sinh N cau hoi nhu vay, nhung vao vector, roi lay cosine trung binh
voi cau hoi that.

    diem = trung binh cosine( cau hoi that , cau hoi doan nguoc tu cau tra loi )

Y nghia: cau tra loi lac de thi khong ai doan nguoc ra duoc cau hoi ban dau. Cau tra
loi dung trong tam thi doan nguoc rat trung.

Chi so nay KHONG doc tai lieu, va do la co y — no khong do dung/sai, no do LAC DE.
Mot cau tra loi bia dat nhung dung trong tam van duoc diem cao o day, va bi
faithfulness danh truot. Hai chi so bat hai kieu hong khac nhau.

MOT CHO PHAI SUA SO VOI RAGAS GOC
---------------------------------
RAGAS cham 0 cho cau tra loi "thoai thac" (noncommittal) — kieu "toi khong biet". Ap
nguyen luat do vao day thi SAI HUONG, vi bot nay duoc thiet ke de noi "khong tim thay
trong tai lieu" khi kho khong co thong tin, va `faithfulness.py` cham cho hanh vi do
1,0 vi no trung thuc.

De nguyen luat cua RAGAS thi bo eval se THUONG cho viec bia ra mot cau tra loi lac de
va PHAT cau tra loi trung thuc — dung nguoc voi thu du an nay muon. Nen o day cau
thoai thac tra ve None, va runner bo chung ra khoi trung binh; dung/sai cua nhung cau
do da co nhom `ngoai_kho` trong golden.jsonl lo, cham bang faithfulness.
"""

import math

from llm.embedder import get_embedder

from ._cham import goi_cham, la_thoai_thac

#: So cau hoi doan nguoc. RAGAS mac dinh 3. Tang len thi diem on dinh hon nhung moi
#: cau la them mot vector phai nhung.
SO_CAU_DOAN = 3

HUONG_DAN = f"""\
Nhiệm vụ: đọc CÂU TRẢ LỜI và đoán ngược xem câu hỏi ban đầu là gì.

Viết đúng {SO_CAU_DOAN} câu hỏi, mỗi câu một dòng, không đánh số, không giải thích.

Chỉ dựa vào CÂU TRẢ LỜI. Viết câu hỏi bằng đúng thứ tiếng của câu trả lời.
"""


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine hai vector. Vector khong -> 0,0."""
    tich = sum(x * y for x, y in zip(a, b, strict=True))
    do_dai = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return tich / do_dai if do_dai else 0.0


async def judge_answer_relevance(question: str, answer: str, trace_id: str) -> float | None:
    """0.0 - 1.0. None khi cau tra loi la loi tu choi, hoac khi khong doan duoc cau nao."""
    if la_thoai_thac(answer):
        return None

    raw = await goi_cham(system=HUONG_DAN, input=f"CÂU TRẢ LỜI:\n{answer}", trace_id=trace_id)
    doan = [d.strip() for d in raw.splitlines() if d.strip()][:SO_CAU_DOAN]
    if not doan:
        return None

    # Mot lan nhung cho ca cau that lan cac cau doan: cung mot lan goi, va chac chan
    # cung mot model — nhung hai lan bang hai lan goi khac nhau la mo duong cho mot
    # kieu lech rat kho thay.
    vector = await get_embedder().embed([question, *doan])
    goc, cac_doan = vector[0], vector[1:]
    return sum(cosine(goc, v) for v in cac_doan) / len(cac_doan)
