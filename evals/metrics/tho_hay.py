"""55 diem PHAI CHAM cua thang 100 cho tho luc bat.

45 diem tat dinh nam o `tho/cham_diem.py` — the 6-8, van, bang-trac. Chung do duoc
trong micro-giay, khong goi model.

55 diem o day thi khong: nhip, ngon ngu, hinh anh, y nghia, cam xuc, sang tao. Khong
co cach nao do chung bang code.

    nhip        15   doc len co tu nhien khong, hay bi gay
    ngon ngu    10   co tu nao chi de EP VAN khong
    hinh anh    10   co hinh anh that, co suc goi
    y nghia     10   co chu de thong nhat
    cam xuc      5
    sang tao     5

VI SAO PHAN NAY MOI LA PHAN QUAN TRONG: bai "hoa sen" bot lam duoc 44,1/45 diem tat
dinh — gan nhu hoan hao ve luat. Nhung no chua "ngàn nơi sông rồng" va "tròn vương
cuộc đời", tuc chu ghep cho du van, khong co nghia. Bo kiem tra tat dinh KHONG THAY
duoc dieu do. Neu chi do 45 diem kia thi ta se ket luan bai tho da tot.

CANH GIAC VOI CHINH NGUOI CHAM. Tai lieu plan-truy-hoi-xuyen-ngon-ngu.md ghi BON lan
nguoi cham sai trong ba ngay. Nen o day:
  - bat xuat DUNG dinh dang so, moi muc mot dong, va coi moi thu khac la khong doc duoc
  - noi ro thang diem tung muc, khong de model tu bia thang
  - tra None khi khong doc duoc, KHONG tra 0 — hai cai do khac nhau han
"""

import re

from tho.cham_diem import (
    DIEM_CAM_XUC,
    DIEM_HINH_ANH,
    DIEM_NGON_NGU,
    DIEM_NHIP,
    DIEM_SANG_TAO,
    DIEM_Y_NGHIA,
)

from ._cham import goi_cham

MUC: tuple[tuple[str, int], ...] = (
    ("nhip", DIEM_NHIP),
    ("ngon_ngu", DIEM_NGON_NGU),
    ("hinh_anh", DIEM_HINH_ANH),
    ("y_nghia", DIEM_Y_NGHIA),
    ("cam_xuc", DIEM_CAM_XUC),
    ("sang_tao", DIEM_SANG_TAO),
)

HUONG_DAN = f"""\
Nhiệm vụ: chấm một bài thơ lục bát theo sáu tiêu chí. Bài thơ ĐÃ được kiểm luật số
tiếng, vần và bằng-trắc bằng máy — ĐỪNG chấm lại những thứ đó.

Chấm đúng sáu mục sau, mỗi mục một dòng:

nhip|<0-{DIEM_NHIP}>
  Đọc lên có tự nhiên không. Câu lục thường ngắt 2/2/2 ("Trăm năm / trong cõi /
  người ta") hoặc 3/3 ("Người về / có nhớ người chăng"); câu bát thường 2/2/2/2 hoặc
  4/4. Câu phải tự chảy, không bị khựng hay phải lấy hơi bất thường.
  Điểm thấp khi chỗ ngắt rơi vào giữa một từ, hoặc khi phải thêm chữ đệm cho đủ tiếng.

ngon_ngu|<0-{DIEM_NGON_NGU}>
  Có từ nào bị nhét vào CHỈ ĐỂ ÉP VẦN không. Đây là lỗi nặng nhất của thơ tập làm:
  câu đúng vần nhưng cụm từ vô nghĩa, ví dụ "tròn vương cuộc đời" hay "ngàn nơi sông
  rồng". Mỗi cụm như vậy trừ mạnh.

hinh_anh|<0-{DIEM_HINH_ANH}>
  Có hình ảnh thật, cụ thể, có sức gợi không. Điểm thấp khi toàn sáo ngữ chung chung
  ("vẻ đẹp thanh khiết", "tâm hồn Việt").

y_nghia|<0-{DIEM_Y_NGHIA}>
  Bài có một chủ đề thống nhất không, hay là các câu rời rạc ghép lại.

cam_xuc|<0-{DIEM_CAM_XUC}>
  Có cảm xúc thật không, hay chỉ là mô tả.

sang_tao|<0-{DIEM_SANG_TAO}>
  Có gì mới, hay chỉ lặp lại những câu ai cũng viết được.
  CHO ĐIỂM TỐI ĐA khi bài có một CÂU ĐẮT — một câu khiến người đọc dừng lại, kiểu
  "Người buồn cảnh có vui đâu bao giờ". Một bài trôi chảy mà không có câu nào đọng
  lại thì chỉ nên được khoảng một nửa.

Chấm NGHIÊM. Một bài đúng luật nhưng đọc như văn xuôi xuống dòng chỉ nên được khoảng
một nửa số điểm.

Chỉ xuất đúng sáu dòng theo định dạng trên. Không giải thích, không thêm gì khác.\
"""

_DONG = re.compile(r"^\s*([a-z_]+)\s*\|\s*(\d+(?:[.,]\d+)?)\s*$", re.MULTILINE)


async def cham_tho_hay(bai: str, trace_id: str) -> dict[str, float] | None:
    """Diem tung muc. None = khong cham duoc (su co), KHONG phai 0 diem.

    Gop hai cai lam mot se bien mot su co ha tang thanh mot van de chat luong gia —
    dung loi da mac bon lan trong ba ngay, xem plan-truy-hoi-xuyen-ngon-ngu.md.
    """
    raw = await goi_cham(system=HUONG_DAN, input=f"BÀI THƠ:\n{bai}", trace_id=trace_id)

    thay: dict[str, float] = {}
    toi_da = dict(MUC)
    for khop in _DONG.finditer(raw):
        ten = khop.group(1)
        if ten not in toi_da:
            continue
        diem = float(khop.group(2).replace(",", "."))
        # Kep vao thang: nguoi cham hay tu bia thang rieng roi cho 8/10 o muc toi da 5.
        thay[ten] = max(0.0, min(float(toi_da[ten]), diem))

    # Doi DU sau muc. Thieu mot muc nghia la nguoi cham bo qua no, va doan lay phan
    # con lai se cho ra mot tong trong nhu that.
    if len(thay) != len(MUC):
        return None
    return thay
