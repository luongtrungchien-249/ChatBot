"""Tran an toan cho tung tang prompt.

KHONG con la "ngan sach" theo nghia section 7.3 nua. Bang goc (system 400,
knowledge 1500, recent 1200, tong ~4000) duoc tinh cho gia Opus 5 la $5/1M input.
gpt-5-mini co cua so 400.000 token va gia $0,25/1M — re hon 20 lan — nen cat bot
ngu canh la danh doi chat luong cau tra loi lay vai xu. Khong dang.

Cac con so duoi day dat cao den muc trong van hanh binh thuong KHONG BAO GIO cat:
15 tin nhan gan nhat hiem khi qua 2000 token, rerank tra ve 3-5 chunk (~4000).
Chung ton tai nhu mot CAU DAO, khong phai mot chinh sach.

Vi sao van giu cau dao: o 400.000 token thi MOT request ton $0,10. Mot tai lieu dai
lot vao prompt, hoac mot vong lap hong, la du dot ngan sach ngay trong vai chuc lan
goi. Chot chan cuoi cung van la DAILY_BUDGET_USD.

Luu y ve chat luong, khong phai chi phi: nhoi them ngu canh khong lam cau tra loi
tot hon vo han. Duong ong rerank (top 3-5 + nguong) ton tai de gui IT va DUNG.
"""

from dataclasses import dataclass
from typing import Literal, TypeAlias

from shared.chunk_text import truncate_at_boundary

BudgetLayer: TypeAlias = Literal[
    "system", "knowledge", "facts", "summary", "recent", "question", "tool"
]

TOKEN_BUDGET: dict[BudgetLayer, int] = {
    # Hang so ta tu viet nen day la cap THAT SU, khong phai cau dao.
    # Do that 06/09/2026 bang ops/calibrate_tokens.py: 1539 token.
    #
    # Prompt caching DANG AN tren tang nay: usage_log ghi nhan cache_read_tokens
    # 1408-1792 o 20/32 lan goi. OpenAI chia cache theo block 128 token, va 1408 =
    # 11 x 128 — tuc la phan duoc cache chinh la SYSTEM PROMPT. Do la ly do thuc te
    # thu hai, ben canh tinh tai lap, de giu chuoi nay dong bang.
    "system": 2_600,
    "knowledge": 20_000,
    "facts": 4_000,
    "summary": 4_000,
    "recent": 20_000,
    "question": 8_000,
    # Ket qua mot lan goi cong cu. Mot trang web dai khong duoc nuot ca cua so.
    "tool": 12_000,
}

#: So ky tu tren mot token.
#:
#: 3,6 la SO DO DUOC, khong phai so doan: chay ops/calibrate_tokens.py tren ba mau
#: tieng Viet that (hoi thoai nhom, van ban hanh chinh, cau hoi ky thuat) voi
#: gpt-5-mini, ngay 06/09/2026 — ket qua 3,61 / 3,41 / 3,82, trung binh 3,61.
#: Ba mau do nam TRONG script, nen do lai la chay mot lenh.
#:
#: Truoc do dat 3 theo phong doan (uoc luong du 13%), roi 3,4 theo mot lan do cu.
#: Do lai khi doi model — moi model mot tokenizer.
#:
#: Uoc THAP hon thuc te thi an toan: tran tinh ra chat hon, tuc la cat som hon can
#: chu khong bao gio de lot nhieu token hon ngan sach.
#:
#: Khong dem token that o day: agents/ khong duoc import llm/ (L1), va them mot lan
#: goi mang cho moi tang moi cau tra loi thi hong muc tieu p95 < 5s.
CHARS_PER_TOKEN = 3.6


@dataclass(frozen=True, slots=True)
class TrimResult:
    text: str
    trimmed_tokens: int


def trim_to_budget(text: str, layer: BudgetLayer) -> TrimResult:
    """Vuot tran thi cat DUNG tang do, khong dung tang khac.

    Luon tra ve so token da cat de ghi log — mot lan cat la mot tin hieu bat thuong
    can xem, khong phai chuyen binh thuong.
    """
    limit_chars = int(TOKEN_BUDGET[layer] * CHARS_PER_TOKEN)
    if len(text) <= limit_chars:
        return TrimResult(text=text, trimmed_tokens=0)

    kept = truncate_at_boundary(text, limit_chars)
    trimmed = -(-(len(text) - len(kept)) // 1)  # so ky tu bi cat
    return TrimResult(text=kept, trimmed_tokens=int(trimmed / CHARS_PER_TOKEN) + 1)


def exceeds_budget(text: str, layer: BudgetLayer) -> bool:
    """Co vuot tran khong — cho goi dung cai nay de biet co CAN NEN khong."""
    return len(text) > int(TOKEN_BUDGET[layer] * CHARS_PER_TOKEN)
