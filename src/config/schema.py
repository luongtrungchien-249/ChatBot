"""L7: config doc MOT LAN luc khoi dong, qua schema.

Thieu bien -> process khong khoi dong duoc (fail fast, khong fail luc 2 gio sang).
Day la NOI DUY NHAT trong codebase duoc cham bien moi truong; luat so 2 trong
.importlinter cuong che dieu do.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Tu vung chinh sach thuoc ve agents/policy, config chi kiem tra .env co khop khong.
#: Chieu phu thuoc la config -> agents, KHONG duoc nguoc lai (luat L1).
from agents.policy.access import DmPolicy, GroupPolicy

__all__ = ["DmPolicy", "GroupPolicy", "Settings"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Bien la o trong .env khong duoc lam chet process — nhung bien THIEU thi co.
        extra="ignore",
        frozen=True,
    )

    NODE_ENV: Literal["development", "test", "production"] = "development"
    LOG_LEVEL: Literal["debug", "info", "warn", "error"] = "info"

    # --- LLM ---
    OPENAI_API_KEY: str = Field(min_length=1)

    # --- Embedding & Rerank ---
    # Tuan 1-3 chua dung RAG: dien 'fake' de process khoi dong duoc.
    EMBEDDING_PROVIDER: str = Field(min_length=1)
    EMBEDDING_API_KEY: str = Field(min_length=1)
    EMBEDDING_MODEL: str = Field(min_length=1)
    EMBEDDING_DIM: int = Field(gt=0)
    RERANK_PROVIDER: str = Field(min_length=1)
    RERANK_API_KEY: str = Field(min_length=1)
    RERANK_MODEL: str = Field(min_length=1)
    # Tran khoang cach cosine de mot chunk duoc coi la co lien quan.
    #
    # Chi dung khi reranker KHONG phai cross-encoder that (xem
    # llm/reranker.py: `diem_dang_tin`). Ban du phong cham do trung TU VUNG,
    # nen diem cua no khong phai do lien quan — dung no de LOC la sai ve ban
    # chat khi cau hoi va tai lieu khac ngon ngu.
    #
    # NGUONG NAY PHU THUOC CORPUS. Do hai lan, va lan hai chung minh dieu do:
    #
    #   corpus TIENG ANH (cookbook, 14 cau hoi tieng Viet):
    #       cau CO trong tai lieu   0,4382 - 0,7587
    #       cau NGOAI tai lieu      0,7918 - 0,9294     -> nguong 0,78
    #
    #   corpus TRON Anh + Viet (them booklet Sa Pa, 17 cau):
    #       cau CO trong tai lieu   0,3183 - 0,5607
    #       cau NGOAI tai lieu      0,6987 - 0,7751     -> nguong 0,63
    #
    # Them tai lieu tieng Viet keo MOI cau hoi tieng Viet lai gan hon, nen giu 0,78
    # thi cau "luong thang 13 tinh the nao" (0,7698) lot qua va bot tra ve cong thuc
    # nau an. Doi lai khoang tach RONG HON han: 0,138 so voi 0,033.
    #
    # Mau nho (17 cau) — do lai moi khi corpus doi.
    RAG_MAX_DISTANCE: float = Field(default=0.63, gt=0.0, le=2.0)

    # Tren nguong nay thi lan tim bi coi la CHUNG CHUNG, va cong cu tra ve mot danh
    # sach ung vien de NGUOI DUNG chon thay vi tra loi luon. Xem tools/knowledge_search.
    #
    # Do 10/09/2026 tren kho that (179 chunk), khoang cach cua ung vien gan nhat:
    #
    #   hoi thang mot muc co ten     0,2468  0,2613  0,2810  0,3499
    #   hoi chung chung / mo ho      0,3504  0,4658  0,5061  0,5629  0,5625  0,5960
    #
    # Hai lop CHONG NHAU o quanh 0,35, nen 0,35 la cho dat nguong te nhat. Chon 0,50:
    # no nam trong khoang trong 0,466 - 0,506 cua mau nay, va no giu nguyen hai cau
    # dang tra loi DUNG (0,3504 va 0,4658) trong khi van bat duoc "dishes that use
    # cheese and pasta" (0,5625) — dung cau da truot vi truy van bi khai quat hoa.
    #
    # Dat CAO hon RAG_MAX_DISTANCE thi tinh nang tat: moi thu qua duoc cua loc kia
    # deu duoi nguong nay. Mau nho — do lai khi corpus doi, y het RAG_MAX_DISTANCE.
    RAG_HOI_LAI_TU: float = Field(default=0.50, gt=0.0, le=2.0)

    RERANK_MIN_SCORE: float = Field(ge=0, le=1)

    # --- Ha tang ---
    #: Tu host model cho route `poem`. Rong = dung model chung cua ca bot.
    #:
    #: Dat vao day mot endpoint TUONG THICH OpenAI (vLLM, TGI). Vi du:
    #:     POEM_BASE_URL=http://localhost:8000/v1
    #:     POEM_MODEL_ID=google/gemma-4-26b-a4b-it
    #:     POEM_API_KEY=khoa-gia
    #:
    #: CANH BAO VE PHAN CUNG: model 26B can ~13-15 GB VRAM o int4, ~26 GB o int8. MoE
    #: van phai nap TOAN BO expert vao VRAM — phan thua chi nam o phep tinh. Do tren
    #: may dang phat trien: RTX 3050 Ti Laptop, 4 GB VRAM — THIEU khoang 3,5 lan, va
    #: model se khong nap noi chu khong phai chay cham.
    POEM_BASE_URL: str = ""
    #: Model cho RIENG route tho. De trong = dung chung model voi ca bot.
    #:
    #: Dat mot id OpenAI (gpt-4o-mini, gpt-5-nano) de doi model cho rieng route nay
    #: ma khong dung toi phan con lai — moi luat trong SYSTEM_PROMPT deu duoc hieu
    #: chuan tren gpt-5-mini, nen doi model cho ca bot se lam so lieu do het gia tri.
    #:
    #: Dat cung POEM_BASE_URL thi day la ten model tren may tu host.
    POEM_MODEL_ID: str = ""
    POEM_API_KEY: str = "khong-can"

    DATABASE_URL: str = Field(min_length=1)
    REDIS_URL: str = Field(min_length=1)

    # --- Zalo Bot Platform (giai doan 4) ---
    ZALO_BOT_TOKEN: str = ""
    ZALO_MODE: Literal["webhook", "polling"] = "polling"
    ZALO_WEBHOOK_SECRET: str = ""

    # --- Chinh sach ---
    #: Mot hoac NHIEU ten goi, ngan cach bang dau phay: "CP_Assistant,CP".
    #: Nguoi trong nhom go ten ngan nhat go duoc, nen phai khai ca ten ngan.
    #: Gach duoi trong ten se khop ca khoang trang, va dau tieng Viet duoc bo qua.
    BOT_MENTION_NAME: str = Field(min_length=1)
    GROUP_POLICY: GroupPolicy = "allowlist"
    DM_POLICY: DmPolicy = "pairing"
    RL_USER_PER_MIN: int = Field(default=10, gt=0)
    RL_THREAD_PER_MIN: int = Field(default=30, gt=0)

    #: L3 implicit — bot TU trich fact tu hoi thoai. MAC DINH TAT.
    #:
    #: Day la tinh nang ghi thong tin ve nguoi co ten ma khong ai bam nut dong y.
    #: Chi bat sau khi da chay duoc cong cu audit:
    #:     uv run python -m main.cli memory <platform> <thread_id>
    MEMORY_IMPLICIT_ENABLED: bool = False

    # --- Cong cu ---
    # De TRONG thi cong cu tuong ung khong duoc khai trong ToolPort.specs(). Cho model
    # thay mot cong cu roi de no goi that bai la cach nhanh nhat de no bia ket qua.
    TAVILY_API_KEY: str = ""
    SEMANTIC_SCHOLAR_API_KEY: str = ""
    #: YouTube Data API v3. Khong co khoa thi cong cu youtube_stats khong duoc khai.
    #: Khong co duong nao khac: so luot thich chi lay duoc qua API chinh thuc — mot
    #: trang ket qua tim kiem khong mang con so do mot cach dang tin.
    YOUTUBE_API_KEY: str = ""

    # Chan cung cua vong ReAct. Thieu cai nao cung thanh vong dot tien khong day.
    # 5 -> 8 (08/09/2026), do do that. Cau "tim top video roi kiem tra so like" can
    # mot vong tim danh sach + MOT VONG CHO MOI VIDEO de doi ten sang so lieu. Voi
    # tran 5, model cham tran khi moi tra duoc mot video va tra ve mot LOI HUA
    # ("bat dau lay so lieu...") thay vi ket qua.
    #
    # Nang tran KHONG lam cau hoi thuong dat hon: vong dung ngay khi model thoi goi
    # cong cu, va phan lon luot chi dung 1-2 vong. Chot chan that su van la deadline
    # (45s Zalo / 60s web) — kiem truoc moi vong.
    #
    # Khong con tran tong so loi goi cong cu (bo 08/09/2026): xem chu thich dai o
    # dau agents/pipeline/stages/generate.py.
    REACT_MAX_ITERATIONS: int = Field(default=8, gt=0)
    REACT_DEADLINE_MS: int = Field(default=60_000, gt=0)

    # --- Giao dien web ---
    WEB_PORT: int = Field(default=3000, gt=0)
    #: Chi localhost. Mo ra 0.0.0.0 khi CHUA co auth nghia la ai trong mang cung dot
    #: duoc ngan sach cua ban.
    WEB_BIND: str = "127.0.0.1"

    #: BAT BUOC, khong co mac dinh. Xem ARCHITECTURE.md section 8.3 de tinh nguoc
    #: tu ngan sach thang.
    DAILY_BUDGET_USD: float = Field(gt=0)
