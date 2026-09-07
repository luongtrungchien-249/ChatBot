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

Route = Literal["reply", "rewrite", "summarize", "extract_facts", "compress"]


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
#: DA THU `effort="medium"` CHO ROUTE `reply` — VA NO TE HON. Do 07/09/2026, chay
#: cung mot doan hoi thoai bon luot, hai lan moi muc:
#:
#:              cau hoi lam ro    timeout (het deadline ReAct)
#:     low            1                    0
#:     medium         0                    5
#:
#: `medium` doi mot cau hoi lam ro hiem gap lay viec HONG HAN qua nua so luot: suy
#: luan sau hon lam moi lan goi lau hon, va mot luot co tra cuu (goi model -> cong cu
#: -> goi model) vuot deadline 45s cua Zalo. Nguoi dung nhan "minh dang bi cham" thay
#: vi cau tra loi.
#:
#: Ket luan: voi mot bot chat co cong cu, `low` la diem van hanh dung. Muon giam so
#: cau hoi lam ro thi sua PROMPT (xem agents/prompt/system.py, khoi CONSTRAINTS),
#: khong phai tang effort.
MODELS: dict[Route, ModelConfig] = {
    "reply": ModelConfig(effort="low", max_tokens=16_000, **_GPT_5_MINI),  # type: ignore[arg-type]
    "rewrite": ModelConfig(effort="low", max_tokens=2_000, **_GPT_5_MINI),  # type: ignore[arg-type]
    "summarize": ModelConfig(effort="low", max_tokens=4_000, **_GPT_5_MINI),  # type: ignore[arg-type]
    "extract_facts": ModelConfig(effort="low", max_tokens=4_000, **_GPT_5_MINI),  # type: ignore[arg-type]
    # Nen ket qua cong cu. Route RIENG chu khong dung chung 'summarize': gop lai thi
    # usage_log tron chi phi nen mot trang web vao chi phi nen hoi thoai L2, va cau
    # hoi "viec nen L2 ton bao nhieu" khong con tra loi duoc.
    "compress": ModelConfig(effort="low", max_tokens=8_000, **_GPT_5_MINI),  # type: ignore[arg-type]
}

#: Gia embedding, USD / 1M token.
#:
#: CHOT `text-embedding-3-large` sau khi DO ca hai, 07/09/2026
#: (`uv run python ops/benchmark_embedding.py`, cung 1024 chieu):
#:
#:                          khoang an toan   top-1 tim kiem   bien xep hang   USD/1M
#:     3-large                    +0,212         7/8             +0,074        0,13
#:     3-small                    +0,171         6/8             +0,034        0,02
#:
#: `3-small` re hon 6,5 lan nhung KEM DO DUOC o ca hai phep:
#:   - Xep sai 2/8 cau tim kiem, va bien phan biet tut hon MOT NUA (0,074 -> 0,034).
#:     Bien hep nghia la thu tu ket qua nhay cam voi mot cau chu la.
#:   - `bat_min` = 0,695, tuc la NAM DUOI DUPLICATE_THRESHOLD = 0,70 dang dung. Doi
#:     sang no ma khong ha nguong la lam hong chong trung mot cach im lang.
#:
#: Va khoan tiet kiem gan nhu bang khong: do bang `cli stats`, `embed` chiem ~7% chi
#: phi (0,0028 tren 0,0388 USD mot tuan). Doi model de tiet kiem 6% cua 7% trong khi
#: chat luong tim kiem giam do duoc — day la mot mon hoi khong dang.
#:
#: Cach cat chi phi embedding DUNG cho nam o cho khac va da lam: cache vector cau hoi
#: dung chung giua L3 va RAG (`llm/embedder.embed_query`). Do that: hai cau hoi giong
#: nhau giờ ton 2 lan goi thay vi 4.
#:
#: Nam o day chu khong o embedder.py vi cung mot ly do voi MODELS: mot cho duy nhat
#: khai model va gia. Doi EMBEDDING_MODEL trong .env sang mot model KHONG co trong
#: bang nay thi process khong khoi dong duoc — thay vi chay tiep va ghi cost_usd sai
#: vao usage_log, tuc la ngan sach ngay dem theo mot bang gia khong con dung.
EMBEDDING_PRICES: dict[str, float] = {
    "text-embedding-3-large": 0.13,
    "text-embedding-3-small": 0.02,
}

#: Timeout duong phan hoi. Qua nguong nay -> cau fallback ngan, khong im lang.
REPLY_TIMEOUT_S = 15.0

#: Timeout cho cac route chay nen (nen ket qua cong cu, tom tat, trich fact).
#: Rong hon duong tra loi vi khong ai dang cho, nhung van phai co: mac dinh cua SDK
#: du de treo ca mot job trong hang doi.
CHEAP_TIMEOUT_S = 45.0
