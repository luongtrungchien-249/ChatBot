# CP Assistant

Chatbot AI tra loi khi duoc mention trong nhom Zalo, co RAG va memory.
Viet hoan toan bang **Python 3.11**.

**Pham vi:** chi tich hop Zalo. Messenger da bi bo khoi ke hoach ngay 07/09/2026 —
khong con code, bien cau hinh hay gia tri `Platform` nao cho no.

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
| `uv run python -m main.cli ingest <tep>` | Nap tai lieu vao RAG (chi admin) |
| `uv run python -m main.cli stats [ngay]` | Tien di dau, cham o dau, cache co an khong |
| `uv run python -m main.cli review <nen-tang> <thread>` | Duyet SAU fact bot tu ghi (L3 implicit) |
| `uv run pytest` | unit test (khong can I/O) |
| `uv run lint-imports` | **Cuong che luat kien truc. Bat buoc trong CI.** |
| `uv run python ops/guard_env.py` | **Chan doc env ngoai `config/`. Bat buoc trong CI.** |
| `uv run python ops/guard_sql.py` | **Chan SQL cham `memory_fact` ngoai `memory/repository/`. Bat buoc trong CI.** |
| `uv run python ops/canary_import_rules.py` | Chung minh 8 luat tren that su bat duoc vi pham |
| `uv run python -m evals.runner [dataset]` | Bo eval: Recall@5, faithfulness, p95. **Ton tien that** |
| `uv run python ops/benchmark_embedding.py` | So sanh model embedding tren du lieu cua chinh du an |
| `uv run python ops/benchmark_rerank.py <ds>` | So sanh nha cung cap rerank, va de xuat RERANK_MIN_SCORE |

### Audit memory

Xem MOI fact con hieu luc cua mot thread. Cong cu nay phai chay duoc TRUOC khi bat
trich fact tu dong (L3 implicit) — khong nhin duoc bot da tu ghi gi thi khong the
cho phep no tu ghi.

```bash
uv run python -m main.cli memory zalo_bot <thread_id>
```

### Nap tai lieu (RAG)

Bot chi tra loi duoc theo tai lieu sau khi co tai lieu. Nap bang CLI — **chi admin**,
khong co route HTTP nao lam viec nay:

```bash
uv run python -m main.cli ingest tai-lieu/so-tay.md "So tay nhan vien 2026"
```

Nhan `.txt` `.md` `.pdf` `.docx`. Nap lai cung mot tep khong doi thi khong lam gi;
noi dung doi thi len **phien ban moi** chu khong sua ban cu — mot cau tra loi da
trich dan chunk cu thi chunk do phai con nguyen van.

Nap tai lieu **dau tien** xong phai khoi dong lai worker: cong cu
`search_knowledge_base` chi duoc khai bao khi kho tai lieu co gi.

### Quan tri nhom (Zalo)

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
5. Co `replied:` chi duoc dat khi that su da gui van ban. Dat no o moi that bai se
   lam lan retry tu thoat ngay va `max_tries` thanh vo nghia — xem `main/worker.py`.

## Theo doi

```bash
uv run python -m main.cli stats 7      # doc thang tu usage_log, khong can dung gi
curl http://127.0.0.1:3000/api/metrics # dinh dang Prometheus, cho Grafana

# Grafana + Prometheus, cam san datasource va dashboard:
docker compose -f ops/docker-compose.yml --profile monitoring up -d
#   Grafana    http://127.0.0.1:3001
#   Prometheus http://127.0.0.1:9090
```

`cli stats` tra loi ba cau: tien di dau, route nao cham, va prompt caching co dang
an khong. Ti le cache tut ve 0 nghia la tien to on dinh cua prompt da vo.

## Ghi cong du lieu ben thu ba

**Tu ghep tieng Viet** (`src/tho/tu_ghep_wiktionary.py` — 18.157 tu)

Trich tu **Wiktionary** tieng Anh bang cong cu `wiktextract`, phan phoi qua
[kaikki.org](https://kaikki.org/dictionary/Vietnamese/). Noi dung Wiktionary o duoi
**CC BY-SA 4.0** (va GFDL).

Tep trong repo la mot **ban trich** cua du lieu do — tuc mot tac pham phai sinh — nen
no mang theo cung giay phep. Dung de bat cum chu bi be cho van khi lam tho
(«ngọt ngào» -> «ngọt ngao»).

Sinh lai:

```bash
curl -L -o /tmp/vi.jsonl \
  https://kaikki.org/dictionary/Vietnamese/kaikki.org-dictionary-Vietnamese.jsonl
uv run python ops/dung_tu_ghep.py /tmp/vi.jsonl
```

Tep 79 MB goc **khong** duoc commit: ta chi can danh sach tu, va ban trich nho hon vai
tram lan nen con doc va review duoc bang mat.

**Tho luc bat lam vi du** (`src/tho/bang_van.py`, `evals/corpus/tho/`)

Truyen Kieu — Nguyen Du, va mot so cau ca dao. Het han bao ho.
