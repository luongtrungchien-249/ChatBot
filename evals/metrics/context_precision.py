"""Context Precision (RAGAS): trong nhung gi lay ve, bao nhieu la dung viec — va no
co duoc xep len TREN khong.

    AP@k = tong( precision@i * lien_quan_i ) / tong so chunk lien quan

Day la Average Precision, tuc no phat viec xep sai thu tu chu khong chi dem. Lay ve 5
chunk trong do 2 chunk dung nam o vi tri 1-2 thi duoc 1,0; cung 2 chunk do nam o vi
tri 4-5 thi chi duoc khoang 0,4. Dung la thu ta can: prompt co ngan sach, chunk rac
xep tren day chunk dung ra khoi phan bot thuc su doc ky.

Chi so nay do DUONG XEP HANG, khong do duong tim kiem. Recall cao ma precision thap
nghia la rerank dang la khau yeu; ca hai cung thap thi van de nam o truy hoi. Do la
ly do phai co ca hai con so chu khong gop lam mot.

MOT lan goi cho ca k chunk, khong phai k lan goi nhu RAGAS goc. Voi k=5 va 50 cau thi
ban goc la 250 lan goi moi lan chay, tren mot bo eval ma file runner da ghi ro la
"CHAY TON TIEN THAT". Doi lai: nguoi cham nhin thay ca 5 doan cung luc nen co the so
sanh chung voi nhau — vua la diem yeu (mot doan te co the trong kha hon khi dung canh
doan te hon) vua la diem manh (do lien quan von la mot khai niem so sanh).
"""

from ._cham import doc_phan_quyet, goi_cham

HUONG_DAN = """\
Nhiệm vụ: với mỗi ĐOẠN tài liệu, xét xem nó có giúp trả lời CÂU HỎI không.

Một đoạn được tính là CO khi nó chứa thông tin dùng được cho câu hỏi này. Tính cả
đoạn chỉ trả lời được một phần.

Tính là KHONG khi đoạn chỉ trùng chủ đề mà không trả lời được gì — ví dụ câu hỏi về
cách nấu một món, còn đoạn chỉ giới thiệu chung về loại cây đó.

Không chấm độ dài, không chấm đoạn viết bằng tiếng gì.

Định dạng bắt buộc, mỗi đoạn một dòng, không thêm gì khác:

<số thứ tự đoạn>|CO hoặc KHONG
"""


def average_precision(lien_quan: list[bool]) -> float:
    """AP@k tu danh sach nhan da xep theo DUNG thu tu truy hoi.

    Khong co chunk nao lien quan -> 0,0. Do la mot lan truy hoi hong that, khong phai
    mot phep chia cho khong can lang tranh.
    """
    tong_lien_quan = sum(lien_quan)
    if tong_lien_quan == 0:
        return 0.0
    cong = 0.0
    dung = 0
    for i, co in enumerate(lien_quan, start=1):
        if co:
            dung += 1
            cong += dung / i
    return cong / tong_lien_quan


async def judge_context_precision(
    question: str, doan: list[str], trace_id: str
) -> float | None:
    """0.0 - 1.0, hoac None neu khong cham duoc. `doan` phai giu DUNG thu tu truy hoi."""
    if not doan:
        return None
    danh_sach = "\n\n".join(f"ĐOẠN {i}:\n{d}" for i, d in enumerate(doan, start=1))
    raw = await goi_cham(
        system=HUONG_DAN,
        input=f"CÂU HỎI:\n{question}\n\n{danh_sach}",
        trace_id=trace_id,
    )
    nhan = doc_phan_quyet(raw, len(doan))
    if nhan is None:
        return None
    return average_precision(nhan)
