"""LLM-as-judge: cau tra loi co bam tai lieu khong. Muc tieu > 0,9.

Cham diem TON TIEN THAT o moi lan chay, nen bo eval chi chay nightly va khi PR dung
vao prompt/, knowledge/ingest/, llm/models.py — khong chay moi commit.

Vi sao van dung model de cham: khong co cach nao khac do duoc "cau nay co bia khong"
tren van xuoi tieng Viet. Doi lai phai chan hai kieu sai cua chinh nguoi cham:
  - Cham diem cho van phong thay vi cho tinh dung: instruction noi ro chi xet CO
    TRONG TAI LIEU hay khong.
  - Tra ve mot bai binh luan thay vi mot con so: bat xuat DUNG mot so, va coi moi
    thu khac la khong doc duoc.
"""

import re

from agents.domain.thread import ThreadScope
from agents.ports.llm import CallContext
from llm.models import MODELS
from llm.openai_client import llm

JUDGE_INSTRUCTION = """\nNhiệm vụ: chấm điểm một câu trả lời xem nó có bám vào tài liệu được cung cấp không.

Chỉ xét MỘT điều: mọi khẳng định trong câu trả lời có tìm được trong tài liệu không.
Không chấm văn phong, không chấm độ dài, không chấm thái độ.

Thang điểm:
1.0 — mọi khẳng định đều có trong tài liệu.
0.5 — phần lớn có, nhưng có một chi tiết không tìm thấy.
0.0 — có khẳng định mâu thuẫn với tài liệu, hoặc bịa ra thông tin không có.

Câu trả lời nói thẳng là "không tìm thấy trong tài liệu" trong khi tài liệu thật sự
không có thông tin đó thì được 1.0 — nói không biết là trung thực, không phải thất bại.

Phần trích dẫn nguồn trong ngoặc, ví dụ "(theo Sổ tay nhân viên 2026, mục Chính sách hoàn tiền)", KHÔNG phải là một khẳng định cần kiểm chứng. Nó chỉ nói câu trả lời lấy từ đâu, và tên nguồn nằm ở thuộc tính của thẻ <tai_lieu>. Đừng trừ điểm vì nó.

Chỉ xuất ra đúng một con số. Không giải thích.
"""

_SCORE = re.compile(r"[01](?:[.,]\d+)?")


async def judge_faithfulness(question: str, answer: str, context: str, trace_id: str) -> float:
    """0.0 - 1.0. Nguoi cham khong doc duoc thi tra ve 0.0, khong phai bo qua.

    Bo qua mot cau khong cham duoc se lam diem trung binh DEP LEN mot cach gia tao:
    dung nhung cau kho nhat lai la nhung cau nguoi cham hay tra ve rac.
    """
    raw = await llm.cheap(
        system=JUDGE_INSTRUCTION,
        input=f"TÀI LIỆU:\n{context}\n\nCÂU HỎI:\n{question}\n\nCÂU TRẢ LỜI:\n{answer}",
        max_tokens=MODELS["summarize"].max_tokens,
        route="summarize",
        ctx=CallContext(
            scope=ThreadScope(platform="cli", thread_id="eval"),
            sender_id="eval",
            trace_id=trace_id,
        ),
    )
    match = _SCORE.search(raw.strip())
    if match is None:
        return 0.0
    return min(1.0, max(0.0, float(match.group().replace(",", "."))))
