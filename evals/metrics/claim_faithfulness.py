"""Faithfulness kieu RAGAS: tach cau tra loi thanh tung Y roi dem y nao co can cu.

    diem = so y co can cu trong ngu canh / tong so y cua CAU TRA LOI

KHAC `faithfulness.py` san co, va co y giu ca hai:

    faithfulness.py        mot nguoi cham cho DIEM TONG 1,0 / 0,5 / 0,0
    claim_faithfulness.py  dem tung y, diem la mot phan so

Ban tong nhanh va re hon, nhung thang diem ba muc cua no rat tho: mot cau tra loi 10 y
sai 1 y va mot cau 2 y sai 1 y deu roi vao "0,5". Ban dem y phan biet duoc hai cai do
(0,9 so voi 0,5), tuc no noi duoc MUC DO bia chu khong chi noi co bia hay khong.

Khong thay the ban cu vi mot ly do rat thuc dung: doi cach do se lam moi con so
faithfulness truoc day het so sanh duoc. Giu ca hai mot thoi gian con cho ta mot thu
khac nua — xem hai nguoi cham co dong y voi nhau khong. Ho khong dong y o cho nao thi
cho do dang co van de ve dinh nghia, khong phai ve he thong.

Cau tra loi kieu "khong tim thay trong tai lieu" khi kho thuc su khong co: khong co y
nao de kiem, va do la hanh vi DUNG. Tra ve None, de runner bo ra khoi trung binh.
"""

from ._cham import doc_phan_quyet, goi_cham, la_thoai_thac

HUONG_DAN = """\
Nhiệm vụ: kiểm tra từng khẳng định trong CÂU TRẢ LỜI có căn cứ trong TÀI LIỆU không.

Các bước:
1. Tách CÂU TRẢ LỜI thành từng khẳng định riêng lẻ, đánh số từ 1. Mỗi khẳng định là
   một điều kiểm chứng được — một nguyên liệu, một con số, một bước làm, một cái tên.
2. Với mỗi khẳng định, xét xem TÀI LIỆU có nói ra điều đó không.

KHÔNG tách thành khẳng định, và KHÔNG đánh số, những thứ sau:
- Phần trích dẫn nguồn trong ngoặc, ví dụ "(theo Sổ tay 2026, mục Chính sách hoàn
  tiền)". Nó chỉ nói câu trả lời lấy từ đâu, không phải một điều cần kiểm chứng.
- Câu chào, câu hỏi lại, lời mời hỏi thêm.

Giá trị QUY ĐỔI hoặc suy ra trực tiếp từ tài liệu vẫn tính là CO: đổi đơn vị
(145°F ≈ 63°C, 1 lb ≈ 0,45 kg), đổi cách diễn đạt cùng một ý, hoặc cộng hai con
số có sẵn. Chỉ tính là KHONG khi con số hay sự việc đó không hề suy ra được từ
tài liệu.

Tài liệu song ngữ thì một khẳng định nêu bằng tiếng Việt vẫn tính là CO nếu tài liệu
nói điều đó bằng tiếng Anh, và ngược lại.

Định dạng bắt buộc, không thêm gì khác:

<số thứ tự>|<nội dung khẳng định, viết gọn>
---
<số thứ tự>|CO nếu tài liệu có căn cứ, KHONG nếu không
"""


async def judge_claim_faithfulness(answer: str, context: str, trace_id: str) -> float | None:
    """0.0 - 1.0. None khi cau tra loi la mot loi tu choi, hoac khi khong cham duoc."""
    if la_thoai_thac(answer):
        return None
    raw = await goi_cham(
        system=HUONG_DAN,
        input=f"TÀI LIỆU:\n{context}\n\nCÂU TRẢ LỜI:\n{answer}",
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
