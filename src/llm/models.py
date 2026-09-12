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

Route = Literal["reply", "rewrite", "summarize", "extract_facts", "compress", "poem"]


@dataclass(frozen=True, slots=True)
class ModelConfig:
    id: str
    max_tokens: int
    price_in: float
    price_cached_in: float
    price_out: float
    #: `reasoning_effort` la tham so RIENG CUA MODEL REASONING cua OpenAI. Model tu
    #: host (Gemma, Qwen, Llama...) khong co no, va gui len se bi tu choi.
    #:
    #: None = khong gui tham so nay. Day la cho trừu tượng bi RO khi them model tu
    #: host, va giai phap trung thuc la thua nhan no o kieu du lieu chu khong phai
    #: giả vờ mọi model đều có effort.
    effort: Literal["low", "medium", "high"] | None = "low"
    #: Endpoint tuong thich OpenAI. None = dung endpoint mac dinh cua OpenAI.
    #:
    #: vLLM va TGI deu phuc vu API tuong thich OpenAI, nen tu host chi la doi mot
    #: duong dan — khong can adapter moi, khong can port moi.
    base_url: str | None = None
    #: Khoa cho endpoint tren. vLLM chap nhan mot khoa gia. None = dung OPENAI_API_KEY.
    api_key: str | None = None


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

#: Timeout RIENG cho route `poem`. Rong hon duong tra loi thuong.
#:
#: VI SAO PHAI RIENG — mot ngay da mat vi cho nay. Route tho dung chung
#: `REPLY_TIMEOUT_S = 15s`, va moi lan thu `gpt-5-mini` deu chet o ~15.600 ms. Ket luan
#: sai rut ra luc do: "API khong goi duoc". Su that: no goi duoc, chi la CHAM.
#:
#:     gpt-5-mini «hoa sen»      60.829 ms
#:     gpt-5-mini «mùa thu HN»   36.718 ms
#:     gpt-4o-mini                ~1.800 ms
#:
#: Model REASONING sinh them token suy luan truoc khi tra loi, nen mot viec sinh dai
#: nhu lam tho vuot 15s trong khi mot viec cham ngan (`llm.cheap`, CHEAP_TIMEOUT_S=45s,
#: CUNG la gpt-5-mini) thi khong. Bang chung ro nhat: nguoi cham chay tot ca buoi trong
#: khi route tho "chet".
#:
#: Con so 90s de dung cho model reasoning cham nhat da do duoc. Tho KHONG nam tren
#: duong phan hoi gap: nguoi dung xin mot bai tho thi cho duoc, va `sinh_tho` sinh cac
#: ban SONG SONG nen timeout nay khong nhan len theo so ban.
#:
#: VAN NEN dung model KHONG reasoning cho route nay — xem `_GIA_OPENAI`.
POEM_TIMEOUT_S = 90.0


_tho: ModelConfig | None = None


def model_cho(route: Route) -> ModelConfig:
    """Model cua mot route. Duong DUY NHAT de lay ModelConfig luc chay.

    Route `poem` doc config nen no KHONG the nam trong `MODELS` — dict do dung o cap
    module, va doc config luc import bien moi lenh `import llm.models` thanh mot cho
    co the chet vi thieu bien moi truong, ke ca trong test khong dung toi route nay.
    Cung ly do voi `get_reranker()` trong llm/reranker.py.
    """
    if route != "poem":
        return MODELS[route]
    global _tho
    if _tho is None:
        _tho = _model_tho()
    return _tho


#: Bang gia cac model OpenAI dung duoc cho route `poem`. USD / 1M token.
#:
#: TOKEN SUY LUAN TINH THEO GIA OUTPUT. Day la cho de nham khi so gia: `gpt-5-mini`
#: va `gpt-5-nano` la model reasoning, chung sinh them token suy luan va bi tinh tien
#: nhu output. `gpt-4o-mini` khong sinh token nao nhu vay, nen chi phi THUC TE cua no
#: co the thap hon con so $0,60 goi y khi so voi $2,00 cua gpt-5-mini.
#:
#: Voi viec lam tho thi suy luan nhieu buoc gan nhu khong giup gi — luat tho da duoc
#: cuong che bang code trong `tho/luat.py`, khong phai bang suy luan cua model.
#:
#: CANH BAO VE MODEL REASONING (cot cuoi = True): chung CHAM HON NHIEU LAN cho viec
#: lam tho, va do 11/09/2026 cho thay KHONG tot hon:
#:
#:                    thoi gian      tat dinh
#:     gpt-4o-mini     ~1.800 ms      35,7/45
#:     gpt-5-mini    36 toi 61 GIAY  32,6 toi 34,6/45
#:
#: Chon chung thi phai co `POEM_TIMEOUT_S` du rong — voi timeout 15s cu thi route tho
#: hong IM LANG va log chi hien `APITimeoutError`.
#:
#: GIA CO THE DA DOI. Kiem lai truoc khi dua vao bao cao chi phi.
_GIA_OPENAI: dict[str, tuple[float, float, float, bool]] = {
    # id: (price_in, price_cached_in, price_out, la_model_reasoning)
    "gpt-5-mini": (0.25, 0.025, 2.00, True),
    "gpt-5-nano": (0.05, 0.005, 0.40, True),
    "gpt-4o-mini": (0.15, 0.075, 0.60, False),
}


def _model_tho() -> ModelConfig:
    """Route `poem`. Ba duong, theo thu tu uu tien.

    1. POEM_BASE_URL co gia tri -> MODEL TU HOST.
       vLLM va TGI phuc vu API tuong thich OpenAI nen khong can adapter moi.
       Gia = 0: chi phi that la GIO GPU, va gio GPU khong quy ve token mot cach
       trung thuc duoc. HAU QUA PHAI BIET: route nay se khong bao gio lam
       `DAILY_BUDGET_USD` nhich len, tuc chan ngan sach khong con bao ve gi cho no.
       `effort=None`: model tu host khong co `reasoning_effort`, gui len la bi tu choi.

    2. POEM_MODEL_ID nam trong `_GIA_OPENAI` -> MODEL OPENAI KHAC.
       De doi model cho RIENG route tho ma khong dung toi phan con lai cua bot.

    3. Khong cau hinh gi -> DUNG CHUNG model voi ca bot. Mac dinh, chay duoc ngay.

    VI SAO CHI ROUTE NAY duoc doi tu do: moi luat trong SYSTEM_PROMPT deu duoc hieu
    chuan tren `gpt-5-mini` qua ba ngay do dac (xem docs/plan-truy-hoi-xuyen-ngon-ngu.md).
    Doi model cho ca bot se lam toan bo so lieu do het gia tri. Route `poem` thi khong
    dinh gi toi chung: no khong dung SYSTEM_PROMPT, khong goi cong cu, khong qua ReAct.
    """
    from config import get_settings

    cai_dat = get_settings()

    if cai_dat.POEM_BASE_URL:
        return ModelConfig(
            id=cai_dat.POEM_MODEL_ID,
            max_tokens=4_000,
            price_in=0.0,
            price_cached_in=0.0,
            price_out=0.0,
            effort=None,
            base_url=cai_dat.POEM_BASE_URL,
            api_key=cai_dat.POEM_API_KEY,
        )

    gia = _GIA_OPENAI.get(cai_dat.POEM_MODEL_ID)
    if gia is not None:
        vao, cache, ra, reasoning = gia
        return ModelConfig(
            id=cai_dat.POEM_MODEL_ID,
            max_tokens=4_000,
            price_in=vao,
            price_cached_in=cache,
            price_out=ra,
            # Model KHONG phai reasoning thi khong duoc gui `reasoning_effort` —
            # gpt-4o-mini se tu choi ca request.
            effort="low" if reasoning else None,
        )

    return ModelConfig(effort="low", max_tokens=4_000, **_GPT_5_MINI)  # type: ignore[arg-type]
