"""MOT cho duy nhat khai model. Khong rai model ID khap code.

Gia (USD / 1M token) de cost_meter tinh cost_usd. Xem ARCHITECTURE.md section 8.

Nha cung cap: OpenAI. gpt-5-mini la ban ke nhiem chinh thuc cua o4-mini va re hon
han (0,25 so voi 1,10 input; 2,00 so voi 4,40 output).

Hien tai MOI route dung chung mot model — dung mot agent hoi dap. Khi nao tach
multi-agent, ba route async (rewrite/summarize/extract_facts) nen ha xuong
gpt-5-nano ($0,05 / $0,40): viec co hoc, khoi luong lon, khong nhay latency.
Doi cho nay la doi mot file.
"""

from dataclasses import dataclass
from typing import Literal

Route = Literal["reply", "rewrite", "summarize", "extract_facts"]


@dataclass(frozen=True, slots=True)
class ModelConfig:
    id: str
    effort: Literal["low", "medium", "high"]
    max_tokens: int
    price_in: float
    price_cached_in: float
    price_out: float


#: gpt-5-mini: context 400K, max output 128K.
_GPT_5_MINI = {
    "id": "gpt-5-mini",
    "price_in": 0.25,
    "price_cached_in": 0.025,
    "price_out": 2.0,
}

#: CANH BAO ve max_completion_tokens tren model reasoning.
#:
#: Token reasoning tinh VAO max_completion_tokens va tinh tien theo gia output.
#: Dat cap qua thap thi API tra ve content RONG voi finish_reason 'length' —
#: khong loi, khong ngoai le, chi la cau tra loi bien mat. Day chinh la ly do cac
#: cap duoi day rong rai hon nhieu so voi do dai van ban mong doi.
#:
#: Nang cap khong ton them tien: output tinh theo token THUC SINH RA, khong theo cap.
#: Do dai cau tra loi kiem soat bang system prompt ("duoi 4-5 cau"), khong bang cap.
MODELS: dict[Route, ModelConfig] = {
    "reply": ModelConfig(effort="low", max_tokens=16_000, **_GPT_5_MINI),  # type: ignore[arg-type]
    "rewrite": ModelConfig(effort="low", max_tokens=2_000, **_GPT_5_MINI),  # type: ignore[arg-type]
    "summarize": ModelConfig(effort="low", max_tokens=4_000, **_GPT_5_MINI),  # type: ignore[arg-type]
    "extract_facts": ModelConfig(effort="low", max_tokens=4_000, **_GPT_5_MINI),  # type: ignore[arg-type]
}

#: Timeout duong phan hoi. Qua nguong nay -> cau fallback ngan, khong im lang.
REPLY_TIMEOUT_S = 15.0

#: Timeout cho cac route chay nen (nen ket qua cong cu, tom tat, trich fact).
#: Rong hon duong tra loi vi khong ai dang cho, nhung van phai co: mac dinh cua SDK
#: du de treo ca mot job trong hang doi.
CHEAP_TIMEOUT_S = 45.0
