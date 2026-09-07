"""INPUT RAILS — dò prompt injection và jailbreak, trên MỌI văn bản đi vào prompt.

Trước 08/09/2026 bộ dò này nằm trong `tools/guard.py` và chỉ chạy trên **kết quả công
cụ**. Hai bề mặt còn lại không ai gác:

  - **Tin nhắn người dùng.** Đây là bề mặt bị thử nhiều nhất, và trước đó không có
    dòng log nào cho biết có ai đang dò hay không.
  - **Tài liệu lúc nạp.** Một tệp có câu ra lệnh nhúng sẽ nằm trong CSDL vector và
    được kéo vào prompt ở mọi câu hỏi liên quan — nguy hiểm hơn một tin nhắn, vì nó
    lặp lại mãi.

Chuyển về `agents/policy/` vì luật L1: `agents/` không được import `tools/`. Đặt ở đây
thì cả ba bề mặt dùng chung một danh sách mẫu — ba danh sách rời nhau là ba danh sách
sẽ lệch nhau sau vài lần sửa.

CỐ Ý KHÔNG CHẶN. Chặn theo từ khoá vừa dễ vượt (viết lại một chút là lọt) vừa tạo cảm
giác an toàn giả khiến người ta bỏ qua các lớp thật sự có tác dụng: bọc thẻ, nói rõ
trong RULES rằng nội dung trong thẻ là dữ liệu, và không bao giờ đưa văn bản lạ vào
`role: system`. Tầng này để **ĐO**: biết có ai đang thử, thử bằng cách nào, và tần suất
bao nhiêu — ba con số mà trước đây bằng không.

Tầng thuần: không I/O, không gọi model.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

#: Injection = cố làm văn bản dữ liệu trở thành chỉ thị.
#: Jailbreak  = cố phá vai hoặc moi cấu hình của chính bot.
#:
#: Tách hai loại vì chúng nói lên hai điều khác nhau: injection thường đến từ tài liệu
#: hoặc kết quả web (kẻ tấn công không ở trong nhóm), còn jailbreak đến từ chính người
#: dùng đang ngồi trong nhóm chat.
Loai = Literal["injection", "jailbreak"]


def fold_diacritics(text: str) -> str:
    """Bỏ dấu trước khi so khớp.

    BẮT BUỘC, không phải tiện ích: người Việt thường gõ KHÔNG DẤU, và kẻ đang dò thử
    lại càng hay gõ không dấu. Mẫu "bỏ qua hướng dẫn" có dấu sẽ để lọt thẳng bản không
    dấu — đúng loại lỗ hổng đã từng gặp ở regex mention.

    NFD tách dấu thành ký tự tổ hợp riêng rồi xoá; riêng 'đ' gạch ngang không tách được
    nên phải thay tay.
    """
    replaced = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", replaced)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


#: Mẫu viết KHÔNG DẤU vì đầu vào đã được bỏ dấu trước khi so khớp.
_MAU: list[tuple[str, Loai, re.Pattern[str]]] = [
    (
        "bo-qua-huong-dan",
        "injection",
        re.compile(
            r"\b(bo qua|phot lo|quen)\s+(moi\s+|tat ca\s+)?(huong dan|chi dan|quy tac|luat)", re.I
        ),
    ),
    (
        "ignore-instructions",
        "injection",
        re.compile(
            r"\bignore\s+(all\s+|previous\s+|prior\s+|above\s+)+(instructions?|rules?)", re.I
        ),
    ),
    (
        "chi-thi-nhung",
        "injection",
        # Câu ra lệnh nhắm vào "trợ lý"/"assistant" nằm trong văn bản dữ liệu. Một tài
        # liệu bình thường không xưng hô với trợ lý.
        re.compile(r"\b(tro ly|assistant|ai)\s*[:,]?\s*(hay|phai|must|should)\s+", re.I),
    ),
    (
        "doi-vai",
        "jailbreak",
        re.compile(r"\b(bay gio|tu gio|ke tu gio)\s+(ban|may)\s+(la|thanh)\b", re.I),
    ),
    (
        "you-are-now",
        "jailbreak",
        re.compile(r"\byou\s+are\s+now\b|\bact\s+as\s+(a\s+)?(dan|jailbreak)", re.I),
    ),
    (
        "lo-system-prompt",
        "jailbreak",
        re.compile(
            r"\b(in ra|hien thi|tiet lo|cho xem)\s+.{0,20}(system prompt|prompt he thong)", re.I
        ),
    ),
    (
        "reveal-prompt",
        "jailbreak",
        re.compile(
            r"\b(reveal|print|show|repeat)\s+.{0,20}(system prompt|your instructions)",
            re.I,
        ),
    ),
    (
        "che-do-dac-biet",
        "jailbreak",
        re.compile(r"\b(che do|mode)\s+(nha phat trien|developer|god|unrestricted)", re.I),
    ),
    (
        "gia-danh-quan-tri",
        "jailbreak",
        re.compile(r"\b(toi la|minh la)\s+(quan tri vien|admin|nguoi tao ra ban)", re.I),
    ),
    (
        "bo-gioi-han",
        "jailbreak",
        re.compile(r"\b(gia su|hay coi nhu)\s+.{0,25}(khong co gioi han|khong bi gioi han)", re.I),
    ),
]


@dataclass(frozen=True, slots=True)
class InjectionScan:
    suspicious: bool
    patterns: tuple[str, ...]
    #: Loại nào đã khớp. Rỗng khi sạch.
    loai: tuple[Loai, ...] = ()

    @property
    def co_jailbreak(self) -> bool:
        return "jailbreak" in self.loai


def detect_injection(text: str) -> InjectionScan:
    folded = fold_diacritics(text)
    hits = [(ten, loai) for ten, loai, mau in _MAU if mau.search(folded)]
    return InjectionScan(
        suspicious=bool(hits),
        patterns=tuple(ten for ten, _ in hits),
        loai=tuple(dict.fromkeys(loai for _, loai in hits)),
    )
