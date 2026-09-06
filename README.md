# CP Assistant

Chatbot AI tra loi khi duoc mention trong nhom Zalo va Messenger, co RAG va memory.
Viet hoan toan bang **Python 3.11**.

## Tai lieu

| File | Noi dung |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | **Doc truoc.** Code nam o dau, ai duoc goi ai, schema DB, chi phi. |
| [docs/plan-thi-cong.md](docs/plan-thi-cong.md) | **Plan end-to-end.** Luong du lieu, 8 giai doan, cach kiem chung, rui ro. |
| [docs/master-plan-chatbot.md](docs/master-plan-chatbot.md) | Lo trinh: lam gi, tuan nao. |
| [docs/dep-rules-verified.md](docs/dep-rules-verified.md) | Bang chung 8 luat kien truc thuc su bat duoc vi pham. |
| [docs/archive/](docs/archive/) | Ban ke hoach cu, giu de tra cuu. Da bi ARCHITECTURE.md thay the. |

## Chay lan dau

```bash
uv sync                                    # phu thuoc da ghim trong uv.lock
cp .env.example .env                       # dien OPENAI_API_KEY va DAILY_BUDGET_USD
docker compose -f ops/docker-compose.yml up -d postgres redis
uv run python -m main.cli migrate
uv run python -m main.cli                  # REPL: chat qua terminal, chua can token nao
```

Muon dung giao dien web thi chay ba process (moi cai mot terminal):

```bash
uv run python -m main.api                  # http://127.0.0.1:3000
uv run arq main.worker.WorkerSettings      # worker chay pipeline
uv run python -m main.zalo                 # tuy chon: long-poll Zalo Bot
```

Giao dien do chinh process `api` render (Jinja2 + JavaScript thuan). **Khong co buoc
build, khong can Node** — sua giao dien xong thi tai lai trang.

## Lenh

| Lenh | Lam gi |
|---|---|
| `uv run python -m main.cli` | REPL — adapter thu ba, khong can token Zalo/Meta |
| `uv run python -m main.cli migrate` | Chay migration (chay lai khong lam gi them) |
| `uv run python -m main.api` | FastAPI: giao dien web + SSE + (sau nay) webhook |
| `uv run arq main.worker.WorkerSettings` | Worker chay pipeline (queue `reply`) |
| `uv run arq main.worker.MaintenanceWorkerSettings` | Worker nen L2 (queue `maintenance`) |
| `uv run python -m main.zalo` | Long-poll Zalo Bot, xep tin vao hang doi |
| `uv run mypy` | Kiem tra kieu, che do strict |
| `uv run ruff check .` | Lint |
| `uv run pytest` | unit test (khong can I/O) |
| `uv run lint-imports` | **Cuong che luat kien truc. Bat buoc trong CI.** |
| `uv run python ops/guard_env.py` | **Chan doc env ngoai `config/`. Bat buoc trong CI.** |
| `uv run python ops/guard_sql.py` | **Chan SQL cham `memory_fact` ngoai `memory/repository/`. Bat buoc trong CI.** |
| `uv run python ops/canary_import_rules.py` | Chung minh 8 luat tren that su bat duoc vi pham |

### Audit memory

Xem MOI fact con hieu luc cua mot thread. Cong cu nay phai chay duoc TRUOC khi bat
trich fact tu dong (L3 implicit) — khong nhin duoc bot da tu ghi gi thi khong the
cho phep no tu ghi.

```bash
uv run python -m main.cli memory zalo_bot <thread_id>
```

### Quan tri nhom (Zalo, Messenger)

`GROUP_POLICY=allowlist` nghia la bot cai vao nhom moi thi **im lang** cho toi khi
duoc them. Lay `thread_id` tu log cua process `zalo` (dong `da xep hang tin Zalo`):

```bash
uv run python -m main.cli allowed                  # xem danh sach
uv run python -m main.cli allow zalo_bot <thread_id>
uv run python -m main.cli deny  zalo_bot <thread_id>
```

Co hieu luc ngay, khong can khoi dong lai worker.

## Bon dieu de nham nhat

1. `src/agents/` khong duoc import `adapters/` `infra/` `llm/` `memory/` `knowledge/`
   `tools/` `config/`. `uv run lint-imports` se bao do.
2. Moi truy van memory phai kem `ThreadScope`. Day la hang rao chong ro ri cross-group,
   khong phai toi uu hoa.
3. `SYSTEM_PROMPT` la hang so. Noi suy bien vao do lam hanh vi bot khong tai lap duoc
   va bo eval mat y nghia. Xem ARCHITECTURE.md section 7.1.
4. `gpt-5-mini` la model reasoning: dung `max_completion_tokens`, va token reasoning
   AN VAO cap do. Cap thap thi API tra ve content rong, khong nem loi nao.
