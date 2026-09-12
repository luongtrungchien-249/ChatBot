"""Context Recall (RAGAS): ngu canh truy hoi co DU de dung nen dap an chuan khong.

    diem = so y trong DAP AN CHUAN co the truy ra tu ngu canh / tong so y

Khac Recall@5 o hai cho, va ca hai deu quan trong o du an nay:

1. KHONG DUNG `chunk_id`. Recall@5 doi `expected_chunk_ids`, ma id thi CHET moi lan
   nap lai kho — trong hai ngay 10-11/09/2026 da phai anh xa lai hai lan, mot lan vi
   nap lai sinh id moi, mot lan nua vi chinh cau hoi con mang ten muc bi vo. Chi so
   nay cham tren NOI DUNG nen no song qua moi lan nap lai.

2. Do DU chu khong do TRUNG. Recall@5 hoi "co lay dung manh giay do khong"; chi so
   nay hoi "nhung gi lay ve co du de tra loi khong". Mot cau tra loi dung co the nam
   rai o ba chunk khac han chunk ta danh dau, va Recall@5 se cham 0 cho no.

Cham tren DAP AN CHUAN, khong phai tren cau bot vua tra loi — do la cho phan biet no
voi faithfulness. Faithfulness hoi "bot co bia khong"; cai nay hoi "ta co dua du do
nghe cho bot khong". Mot he thong co the dat faithfulness tuyet doi bang cach luon tra
loi "khong tim thay", va chinh chi so nay bat duoc kieu do.

Cau `ngoai_kho` (dap an chuan la mot loi tu choi) KHONG co y nao de truy — runner bo
chung ra khoi trung binh chu khong cham 1,0 lay le.
"""

from ._cham import doc_phan_quyet, goi_cham

HUONG_DAN = """\
Nhiệm vụ: kiểm tra xem TÀI LIỆU có đủ căn cứ cho từng ý trong ĐÁP ÁN CHUẨN không.

Các bước:
1. Tách ĐÁP ÁN CHUẨN thành từng ý riêng lẻ, đánh số từ 1. Mỗi ý là một khẳng định
   kiểm chứng được — một nguyên liệu, một con số, một bước làm, một cái tên.
2. Với mỗi ý, xét xem TÀI LIỆU có nói ra điều đó không.

Chỉ xét MỘT điều: ý đó có truy được về tài liệu không. Không chấm văn phong, không
chấm việc đáp án chuẩn viết bằng tiếng gì. Tài liệu song ngữ thì một ý nêu bằng
tiếng Việt vẫn tính là có, nếu tài liệu nói điều đó bằng tiếng Anh, và ngược lại.

Định dạng bắt buộc, mỗi ý một dòng, không thêm gì khác:

<số thứ tự>|<nội dung ý, viết gọn>
---
<số thứ tự>|CO nếu tài liệu có căn cứ, KHONG nếu không

Ví dụ:

1|Bí đỏ 500g
2|Nấu trong 45 phút
---
1|CO
2|KHONG
"""


async def judge_context_recall(answer_chuan: str, context: str, trace_id: str) -> float | None:
    """0.0 - 1.0, hoac None neu khong cham duoc.

    None chu khong phai 0.0: khong doc duoc phan quyet la su co ha tang, con 0.0 la
    "ngu canh khong do duoc y nao". Runner dem hai cai nay o hai cho khac nhau.
    """
    raw = await goi_cham(
        system=HUONG_DAN,
        input=f"TÀI LIỆU:\n{context}\n\nĐÁP ÁN CHUẨN:\n{answer_chuan}",
        trace_id=trace_id,
    )
    if "---" not in raw:
        return None
    phan_y, _, phan_quyet = raw.partition("---")
    so_y = len([d for d in phan_y.splitlines() if "|" in d])
    nhan = doc_phan_quyet(phan_quyet, so_y)
    if nhan is None:
        return None
    return sum(nhan) / len(nhan)
