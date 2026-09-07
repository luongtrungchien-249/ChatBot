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
    RERANK_MIN_SCORE: float = Field(ge=0, le=1)

    # --- Ha tang ---
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

    # Chan cung cua vong ReAct. Thieu cai nao cung thanh vong dot tien khong day.
    REACT_MAX_ITERATIONS: int = Field(default=5, gt=0)
    REACT_MAX_TOOL_CALLS: int = Field(default=8, gt=0)
    REACT_DEADLINE_MS: int = Field(default=60_000, gt=0)

    # --- Giao dien web ---
    WEB_PORT: int = Field(default=3000, gt=0)
    #: Chi localhost. Mo ra 0.0.0.0 khi CHUA co auth nghia la ai trong mang cung dot
    #: duoc ngan sach cua ban.
    WEB_BIND: str = "127.0.0.1"

    #: BAT BUOC, khong co mac dinh. Xem ARCHITECTURE.md section 8.3 de tinh nguoc
    #: tu ngan sach thang.
    DAILY_BUDGET_USD: float = Field(gt=0)
