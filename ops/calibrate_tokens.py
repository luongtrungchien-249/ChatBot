"""Do ti le KY TU / TOKEN cua tieng Viet, va do dai that cua SYSTEM_PROMPT.

Vi sao can do chu khong doan: `agents/prompt/budget.py` cat tung tang ngu canh theo
CHARS_PER_TOKEN. Doan sai thi tran that lech theo — ban dau dat 3,0 theo phong doan
va no uoc luong DU 13% so voi thuc te.

Vi sao khong dem cuc bo: agents/ khong duoc import llm/ (luat L1), va moi model mot
tokenizer. Cach dung la hoi chinh API roi doc `usage.prompt_tokens`.

DO NAY TON TIEN THAT — vai phan nghin do la. Chay lai khi DOI MODEL, khong phai moi
lan build.

Chay: uv run python ops/calibrate_tokens.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agents.prompt.budget import CHARS_PER_TOKEN, TOKEN_BUDGET
from agents.prompt.system import SYSTEM_PROMPT
from config import get_settings
from llm.models import MODELS

#: Ba the van tieng Viet THAT, khac nhau ve mat do dau va tu Han Viet — ba loai van
#: ban bot se gap. Do tren mot loai roi suy ra ca ba se lech.
SAMPLES: dict[str, str] = {
    "hoi thoai nhom": (
        "Sáng nay họp lúc mấy giờ vậy mọi người? Mình bận chút việc gia đình nên có thể "
        "tới muộn khoảng mười lăm phút, ai tới trước thì mở phòng họp giúp mình nhé. "
        "Tài liệu mình đã gửi lên nhóm từ tối qua rồi, mọi người xem trước cho đỡ mất thời gian. "
        "Nếu anh Hùng không tham gia được thì mình dời sang chiều mai cũng được."
    ),
    "van ban hanh chinh": (
        "Căn cứ Quyết định số 145/QĐ-TCT ngày 12 tháng 3 năm 2026 của Tổng cục Thuế về việc "
        "ban hành qui trình hoàn thuế giá trị gia tăng, đơn vị có trách nhiệm nộp hồ sơ đề nghị "
        "hoàn thuế trong thời hạn không quá bảy ngày làm việc kể từ ngày phát sinh nghĩa vụ. "
        "Trường hợp hồ sơ chưa đầy đủ, cơ quan thuế thông báo bằng văn bản để đơn vị bổ sung."
    ),
    "cau hoi ky thuat": (
        "Mình đang dựng một pipeline RAG cho tài liệu nội bộ tiếng Việt, dùng pgvector với "
        "embedding 1024 chiều và rerank bằng cross-encoder. Vấn đề là truy vấn chứa mã sản phẩm "
        "kiểu ABC-123 thì vector search trả về kết quả rất kém, phải kết hợp BM25 mới ổn. "
        "Có cách nào chuẩn hoá dấu tiếng Việt trong tsvector của Postgres không?"
    ),
}


async def prompt_tokens(text: str) -> int:
    """So token that cua `text` khi lam input, theo chinh API."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY, max_retries=1)
    response = await client.chat.completions.create(
        model=MODELS["reply"].id,
        messages=[{"role": "user", "content": text}],
        # Chi can phan USAGE, khong can cau tra loi. Nhung model reasoning van sinh
        # token suy luan nen khong the dat 1 — dat vua du de no ket thuc sach se.
        max_completion_tokens=64,
        reasoning_effort="minimal",
    )
    usage = response.usage
    assert usage is not None, "API khong tra ve usage"
    return usage.prompt_tokens


#: API luon them mot it token bao boc quanh message (role, dau phan cach). Tru ra thi
#: ti le moi phan anh dung VAN BAN, khong phai van ban cong khung.
_OVERHEAD_TOKENS = 7


async def main() -> int:
    print(f"Model: {MODELS['reply'].id}\n")

    ratios: list[float] = []
    for name, text in SAMPLES.items():
        tokens = await prompt_tokens(text) - _OVERHEAD_TOKENS
        ratio = len(text) / tokens
        ratios.append(ratio)
        print(f"  {name:<20} {len(text):>5} ky tu / {tokens:>5} token = {ratio:.2f}")

    average = sum(ratios) / len(ratios)
    print(f"\n  Trung binh: {average:.2f} ky tu/token")
    print(f"  Dang dung trong budget.py: {CHARS_PER_TOKEN}")
    if abs(average - CHARS_PER_TOKEN) / average > 0.05:
        print(f"  >> LECH QUA 5% — cap nhat CHARS_PER_TOKEN thanh {average:.2f}")

    system_tokens = await prompt_tokens(SYSTEM_PROMPT) - _OVERHEAD_TOKENS
    cap = TOKEN_BUDGET["system"]
    print(f"\n  SYSTEM_PROMPT: {len(SYSTEM_PROMPT)} ky tu = {system_tokens} token (cap {cap})")
    if system_tokens > cap:
        print("  >> VUOT CAP — noi long TOKEN_BUDGET['system'] hoac cat bot prompt")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
