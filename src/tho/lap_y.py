"""BUOC 2 cua quy trinh: LAP Y — dung mach cam xuc TRUOC khi viet cau.

Nguoi dung mo ta buoc nay nhu sau:

    Cội nguồn → Cha ông → Hy sinh → Hòa bình hôm nay → Không quên nguồn cội
    "Đây là bước lập ý, trước khi chọn câu chữ."

DA CO MOT BAN THU GAN GIONG VA NO THAT BAI. Ban do la "so tay": bat model tu ghi y ra
truoc khi viet, TRONG CUNG MOT LUOT. Do duoc ngon ngu 4,75 -> 4,78 — chim trong nhieu,
va da bi go.

KHAC BIET CUA BAN NAY, va la ly do no dang thu lai mot lan: mach y duoc sinh o mot
LUOT GOI RIENG, xong han roi moi viet cau. Trong mot luot, model viet "y" roi viet tho
ngay sau do — khong co gi bat no thuc su dung cai y vua viet. Hai luot thi cai y da la
van ban CO SAN trong de bai, khong phai thu no vua bia ra cung mach.

VI SAO VAN CO THE HONG — phai noi truoc: `chon_van.py` cung tach mot buoc ra thanh luot
rieng va lam diem TUT 12,6 (69,7 -> 57,1). Co che lam no hong la RANG BUOC: bo van ep
model dat chu dinh san vao dung vi tri. O day ta CHI GOI Y mach nghia, khong ep chu nao
— nen co che do khong ap dung. Nhung "khong ap dung" la mot lap luan, khong phai mot
phep do, va lap luan trong du an nay da sai nhieu lan.

================================================================================
DA DO 13/09/2026 — VA DA TAT. Doc truoc khi dinh bat len.
================================================================================

A/B n=40 cap GHEP THEO CHU DE, HAI luot doc lap, cham ca hai thang. Con so day du nam
o hang so `LAP_Y` trong sinh.py. Tom tat:

    HAI LUOT NOI NGUOC NHAU tren ca ba muc quan trong nhat.
    `ngon ngu` +0,33 o luot 1 va -0,90 o luot 2. `sang tao` +0,03 roi -0,47.

Khong co hieu ung do duoc. Gia thi co that: +1.000 ms va +1,1 luot goi moi bai.

DIEU DANG GHI NHAT tu phep do nay khong phai ket qua, ma la CACH no suyt sai. Luot 1
cho `y nghia` +0,35 +/- 0,35 — vua du "co y nghia thong ke" — va TONG +1,38. Dung o do
thi ket luan la "bat len". Luot 2 lat nguoc han. Neu chi chay mot luot, du an nay da
ship mot cai tot khong co that, lan thu hai.

Nguoi cham chay 160/160 khong hong. Dieu do bac bo niem tin cu trong du an rang thang
100 "khong do duoc vi nguoi cham hay timeout" — no do duoc, va con so 21/30 timeout hom
truoc la mot su co nhat thoi chu khong phai mot gioi han.
"""

#: So y trong mach. Nam la so nguoi dung dua ra trong vi du cua ho.
#:
#: Khong lay nhieu hon: bai mac dinh 4 cau, tuc 2 cap luc bat. Bay tam y cho bon cau se
#: ep model nhet — va NHET chinh la cai lam hong tho, xem `cum_kha_nghi` trong tu_vung.
SO_Y = 5

HUONG_DAN = """\
Bạn đang LẬP Ý cho một bài thơ — chưa viết thơ.

Cho một chủ đề, hãy vạch ra mạch cảm xúc: các ý nối tiếp nhau, ý sau nảy ra từ ý trước,
dẫn người đọc đi từ đâu đến đâu.

Ví dụ với chủ đề "uống nước nhớ nguồn":
Cội nguồn → Cha ông → Hy sinh → Hòa bình hôm nay → Không quên nguồn cội

Ví dụ với chủ đề "mẹ":
Dáng mẹ trong bếp → Đôi tay chai → Những đêm thức → Con đi xa → Quay về

Quy tắc:
- Đúng {so_y} ý, nối bằng dấu →
- Mỗi ý 2-4 chữ, là một HÌNH ẢNH hoặc một việc cụ thể, không phải lời bình
- Các ý phải nối được vào nhau thành một mạch, không rời rạc
- Chỉ dùng từ tiếng Việt có nghĩa thật

Xuất đúng MỘT dòng, không giải thích, không tiêu đề."""


def huong_dan() -> str:
    return HUONG_DAN.format(so_y=SO_Y)


def yeu_cau_lap_y(chu_de: str) -> str:
    return f"Chủ đề: {chu_de}"


def doc_mach_y(raw: str) -> str | None:
    """Lay dong mach y tu cau tra loi. None = khong doc duoc.

    NGHIEM NGAT CO CHU DICH. Tra None thi goi y la BO QUA buoc nay va viet mot mach nhu
    cu — dung nhu `_chon_van_truoc` lam. Mot mach y hong con te hon khong co mach y:
    no chiem cho trong de bai va dan model di sai.
    """
    for dong in raw.strip().split("\n"):
        d = dong.strip().strip("-*• ").strip()
        if "→" not in d and "->" not in d:
            continue
        d = d.replace("->", "→")
        y = [x.strip() for x in d.split("→")]
        y = [x for x in y if x]
        # Doi DUNG so y: it hon thi mach cut, nhieu hon thi model se nhet. Va so tieng
        # moi y phai nho — mot "y" dai mot cau la model dang viet tho chu khong lap y.
        if len(y) != SO_Y or any(len(x.split()) > 4 for x in y):
            continue
        return " → ".join(y)
    return None


def yeu_cau_viet_bai(mach: str, chu_de: str) -> str:
    """De bai co mach y kem theo.

    Noi ro "KHONG bat buoc dung het" va "dung lap lai nguyen chu": mach y la de DAN
    huong, khong phai danh sach tu phai nhet vao bai. Ep dung het chinh la co che da
    lam `CHON_VAN_TRUOC` hong.
    """
    dau = f"Làm một bài về: {chu_de}" if chu_de else "Làm một bài thơ."
    return (
        f"{dau}\n\n"
        f"Mạch cảm xúc gợi ý: {mach}\n"
        "Đi theo mạch này để bài có đường dẫn, nhưng ĐỪNG chép lại nguyên các chữ đó "
        "vào thơ, và không bắt buộc dùng hết."
    )
