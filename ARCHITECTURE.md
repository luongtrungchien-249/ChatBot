# Cấu trúc dự án — AI Chatbot Zalo

**Vai trò:** Senior AI Engineer
**Trạng thái:** Bản chốt để thi công. Thay thế phần "kiến trúc" đang rải rác trong 3 file kế hoạch.
**Phạm vi (07/09/2026):** chỉ tích hợp **Zalo**. Messenger đã bị bỏ — không còn code, biến cấu hình hay giá trị `Platform` nào cho nó. Xem `docs/plan-thi-cong.md` §7.
**Quan hệ:** `master-plan-chatbot.md` = *cái gì / khi nào*. File này = *code nằm ở đâu, ai được gọi ai*.

---

## 0. Bốn quyết định tôi chốt thay bạn

Ba file kế hoạch để mở những thứ mà nếu không chốt thì không viết được dòng `import` đầu tiên. Tôi chốt như dưới. Nếu bạn không đồng ý, phản đối **trước khi** code, không phải ở tuần 3.

| # | Quyết định | Chốt | Lý do |
|---|---|---|---|
| D1 | Model chính | `gpt-5-mini` (OpenAI) | **Sửa 05/09/2026.** Trước là `claude-opus-5`. Rẻ hơn 20× input, 12,5× output; cửa sổ 400K. Chi phí ở §8.3. |
| D2 | Model phụ (tóm tắt, rewrite, trích fact) | `gpt-5-mini` — cùng model | **Sửa 05/09/2026.** Hiện chỉ có một agent hỏi đáp. Khi tách multi-agent thì hạ ba route async xuống `gpt-5-nano` ($0,05/$0,40); đổi chỗ này là đổi một file `llm/models.py`. |
| D3 | Embedding + Rerank | Port riêng, nhà cung cấp cắm vào — **chốt ở tuần 4** | OpenAI có embedding (`text-embedding-3-small/large`) nhưng **không có rerank**, nên rerank vẫn phải là nhà cung cấp thứ hai. |
| D4 | Số chiều vector | Cố định 1024, kiểm tra lúc khởi động | `VECTOR(1024)` trong plan là đã ngầm chọn model rồi. Chốt cho minh bạch. |

**Ba chỗ tôi sửa so với plan:**

1. **`max_tokens` 500–800 → 2000 → `max_completion_tokens` 16000.** Cắt cứng ở 800 token thì câu trả lời dài đứt giữa chừng. Chi phí output tính theo token **thực sinh ra**, không theo cap — nâng cap không tốn thêm tiền. **Sửa 05/09/2026:** `gpt-5-mini` là model reasoning, tham số đúng là `max_completion_tokens` và **token reasoning ăn vào cap đó**. Cap thấp thì API trả về `content` rỗng với `finish_reason: 'length'` — không lỗi, không ngoại lệ, câu trả lời chỉ đơn giản biến mất. Xem cảnh báo trong `llm/models.py`.
2. **Tin nhắn thô lưu Postgres, không lưu Redis.** Xem §6.1 — đây là lỗi mất dữ liệu trong plan, không phải khác biệt sở thích.
3. ~~**Meta App Review nộp cuối tuần 3.**~~ **Không còn** — Messenger đã bỏ khỏi phạm vi (07/09/2026). Xem §11.

---

## 1. Nguyên tắc kiến trúc — 8 luật, không có ngoại lệ

Đây là phần quan trọng nhất của tài liệu. Cây thư mục chỉ là hệ quả của nó.

| # | Luật | Vi phạm sẽ dẫn tới |
|---|---|---|
| L1 | `agents/` **không được import** bất cứ thứ gì trong `adapters/`, `infra/`, `llm/`, `memory/`, `knowledge/`, `tools/`, `config/` | Bạn đang viết hai bot |
| L2 | `agents/` giao tiếp với thế giới **chỉ qua interface trong `agents/ports/`** | Không test được agents nếu không dựng Redis + Postgres + API key |
| L3 | Mọi truy vấn memory đi qua repository, nhận `ThreadScope` bắt buộc ở tham số đầu | Rò rỉ memory cross-group — lỗi phải gỡ sản phẩm |
| L4 | Không có câu SQL nào chạm `memory_fact` ngoài `memory/repository/` | Cùng L3 |
| L5 | Adapter chỉ làm 4 việc: verify → chuẩn hoá → enqueue → gửi trả lời. **Không gọi LLM, không đọc DB** | Logic nhân đôi giữa các adapter (hiện có bốn: `zalo_bot`, `web`, `cli`, và `zalo_personal` để ngỏ) |
| L6 | Mọi lời gọi ra ngoài đi qua `infra/` hoặc `llm/` (có timeout, retry, log, đo cost) | Không biết tiền đi đâu, không debug được |
| L7 | Config đọc **một lần** lúc khởi động, qua schema pydantic-settings. Không có `os.environ` ngoài `config/` | Chạy được ở máy bạn, chết ở prod |
| L8 | Mỗi tin nhắn vào có đúng **một** `traceId` xuyên suốt mọi log | Không truy được một hội thoại hỏng |

**Cưỡng chế bằng máy, không bằng niềm tin — ba công cụ, vì một công cụ không đủ:**

```ini
# .importlinter — chay trong CI (uv run lint-imports), fail build khi vi pham
[importlinter]
root_packages = adapters agents config infra knowledge llm main memory shared tools

[importlinter:contract:1]
name = L1: agents khong biet ha tang
type = forbidden
source_modules = agents
forbidden_modules = adapters infra llm memory knowledge tools
```

`import-linter` chỉ so khớp **import module**. Hai lỗ nó không bịt được, mỗi lỗ một script AST:

| Lỗ | Vì sao import-linter mù | Lớp bù |
|---|---|---|
| L7 — `os.environ` ngoài `config/` | `os.environ` là **truy cập thuộc tính**, không phải import | `ops/guard_env.py` |
| L4 — SQL chạm `memory_fact` ngoài `memory/repository/` | Câu SQL là **chuỗi**, không phải import | `ops/guard_sql.py` |

Và cả ba đều được **chứng minh** bằng `ops/canary_import_rules.py`: script tạo vi phạm cố ý cho từng
luật, chạy lại công cụ, và bắt buộc luật phải **đỏ**. Một luật viết sai vẫn chạy xanh — nó chỉ đơn giản
là không bắt được gì, và bạn sẽ không biết cho tới lúc kiến trúc đã vỡ.

---

## 2. Hình thái triển khai: một codebase, bốn process

Không monorepo. Một `pyproject.toml`, bốn entrypoint. Một người làm thì workspace chỉ là nghi lễ.

| Process | File | Nhiệm vụ | Scale theo |
|---|---|---|---|
| `api` | `src/main/api.py` | FastAPI: giao diện web + SSE, `/api/metrics`, (sau) webhook Zalo. **Trả 200 trong <2s rồi thôi** | Số webhook/giây |
| `worker` | `src/main/worker.py` | ARQ: pipeline trả lời, tóm tắt, trích fact, ingest | Chi phí LLM |
| `zalo` | `src/main/zalo.py` | Long-poll Zalo Bot, chuẩn hoá, xếp hàng | — |
| `cli` | `src/main/cli.py` | Chat với agents qua terminal, migrate, quản trị allowlist | — |

`zalo` tách riêng có chủ đích: long-poll là một vòng lặp treo liên tục, nhét nó vào `api` nghĩa là một
lỗi trong vòng poll kéo cả giao diện web xuống theo.

`cli` không phải đồ chơi. Nó là **adapter thứ ba** và là cách duy nhất để làm Phase 0 khi chưa có token Zalo. Nó cũng là chỗ duy nhất nạp được tài liệu vào RAG (`cli ingest`) và đọc được chi phí (`cli stats`). Nếu agents chỉ chạy được khi có webhook thật thì kiến trúc đã sai từ đầu.

### Stack

| Vai trò | Chọn |
|---|---|
| Ngôn ngữ | Python 3.11, `mypy --strict` |
| Quản lý gói | `uv` (lockfile `uv.lock`) |
| HTTP | FastAPI + uvicorn |
| Hàng đợi | ARQ (trên Redis) |
| DB | asyncpg → Postgres + pgvector |
| Config | pydantic-settings |
| Log | structlog |
| Test | pytest |
| Lint / luật kiến trúc | ruff · import-linter · hai script AST trong `ops/` |
| Giao diện web | Jinja2 + JavaScript thuần — **không có bước build, không có Node** |

Giao diện từng là React + TypeScript + Vite. Cả trang chỉ có hai danh sách và một ô nhập; kéo theo cả
một toolchain Node để vẽ bấy nhiêu đó là chi phí bảo trì không mua được gì. Trình duyệt không chạy được
Python, nên phần chạy trên máy người dùng vẫn là JavaScript — nhưng là JavaScript thuần, đọc thẳng,
sửa xong tải lại trang.

---

## 3. Cây thư mục

Mười gói cấp cao nhất dưới `src/`, mỗi gói là một **tầng**. Không có gói bao bọc ngoài: tên tầng chính
là thứ người đọc code cần thấy đầu tiên, và `from agents.ports.llm import LlmPort` nói rõ hơn một tiền
tố lặp lại ở mọi dòng import. Đổi lại, các tên này chiếm không gian tên cấp cao nhất, nên **thêm một
phụ thuộc mới thì phải kiểm xem nó có gói cấp cao nhất nào trùng tên không**.

`✗` = chưa viết, có chủ đích. Xem `docs/plan-thi-cong.md` để biết thuộc giai đoạn nào.

```
chatbot/
├─ src/
│  ├─ main/                        # Entrypoint — mỏng, chỉ wiring
│  │  ├─ api.py                    # FastAPI: giao diện web, SSE, (sau) webhook
│  │  ├─ worker.py                 # ARQ worker
│  │  ├─ zalo.py                   # Long-poll Zalo Bot
│  │  ├─ cli.py                    # REPL + migrate + allow/deny/allowed
│  │  └─ container.py              # Dependency injection thủ công (không framework DI)
│  │
│  ├─ config/
│  │  ├─ schema.py                 # pydantic-settings cho toàn bộ env
│  │  └─ __init__.py               # đọc 1 lần (lru_cache), export get_settings()
│  │
│  ├─ agents/                      # ⛔ KHÔNG import adapters/infra/llm/memory/knowledge/tools/config
│  │  ├─ domain/
│  │  │  ├─ message.py             # InboundMessage, OutboundMessage, StoredMessage
│  │  │  ├─ thread.py              # ThreadScope — khoá chống rò rỉ
│  │  │  ├─ knowledge.py           # RetrievedChunk — GIÁ TRỊ, không phải hợp đồng
│  │  │  └─ errors.py              # Taxonomy lỗi (§9)
│  │  ├─ ports/                    # Protocol — agents chỉ biết đến những cái này
│  │  │  ├─ llm.py  memory.py  channel.py
│  │  │  ├─ ratelimit.py  logger.py
│  │  │  └─ tool.py                # ToolPort — công cụ gọi mạng nên đứng sau port
│  │  ├─ policy/
│  │  │  ├─ mention.py             # Bóc @ten_bot: 2 lớp payload + regex có dấu tiếng Việt
│  │  │  ├─ access.py              # dm_policy / group_policy + tự vựng GroupPolicy/DmPolicy
│  │  │  └─ command.py             # memory / quên / help — parse TRƯỚC khi vào LLM
│  │  ├─ prompt/
│  │  │  ├─ system.py              # System prompt — HẰNG SỐ, không nội suy biến động
│  │  │  ├─ instructions.py        # Instruction prompt theo từng tác vụ — cũng là hằng số
│  │  │  ├─ context.py             # 5 vùng ngữ cảnh (§7.3)
│  │  │  ├─ builder.py             # Render từng khối + sanitize chống thoát thẻ
│  │  │  └─ budget.py              # Cầu dao token từng tầng
│  │  └─ pipeline/
│  │     ├─ handle_message.py      # Orchestrator — đọc file này là hiểu cả hệ thống
│  │     └─ stages/                # Mỗi stage một file, thuần, test riêng được
│  │        ├─ access.py  mention.py  budget_guard.py  persist.py
│  │        ├─ typing_.py  build_prompt.py  respond.py
│  │        └─ generate.py         # VÒNG ReAct + 6 chặn cứng
│  │
│  ├─ memory/                      # L1 L2 L3 — implement MemoryPort
│  │  ├─ repository/
│  │  │  ├─ message_repo.py        # L1 (Postgres là nguồn thật, Redis là cache)
│  │  │  ├─ summary_repo.py        # L2
│  │  │  └─ fact_repo.py           # L3 — CHỖ DUY NHẤT chạm memory_fact
│  │  ├─ jobs/                     # summarize.py, extract_facts.py (async)
│  │  └─ dedupe.py                 # Chống trùng / mâu thuẫn fact bằng cosine
│  │
│  ├─ knowledge/                   # L4 RAG — dùng qua công cụ search_knowledge_base
│  │  ├─ ingest/                   # extract.py, chunk.py, pipeline.py
│  │  └─ retrieve/                 # search.py (vector+lexical), fusion.py, service.py
│  │
│  ├─ llm/
│  │  ├─ openai_client.py          # Bọc SDK OpenAI, implement LlmPort
│  │  ├─ models.py                 # ID model + effort + cap + giá — MỘT chỗ duy nhất
│  │  ├─ cost_meter.py             # Ghi token in/out/cache mỗi call → usage_log
│  │  ├─ embedder.py              # implement EmbedderPort (nhà cung cấp cắm vào)
│  │  └─ reranker.py              # implement RerankerPort — nhà cung cấp THỨ HAI
│  │
│  ├─ tools/                       # Công cụ agent gọi được — implement ToolPort
│  │  ├─ registry.py               # Nơi DUY NHẤT biết tên nhà cung cấp công cụ
│  │  ├─ guard.py                  # Bọc thẻ + dò injection + cắt trần observation
│  │  ├─ web_search.py             # Tavily — CHƯA chạy lần nào, thiếu khoá
│  │  ├─ paper_search.py           # OpenAlex + arXiv + Semantic Scholar + Crossref
│  │  └─ knowledge_search.py       # search_knowledge_base — RAG (Giai đoạn 6)
│  │
│  ├─ adapters/                    # Mỗi adapter là một hộp kín
│  │  ├─ zalo_bot/
│  │  │  ├─ api.py                 # getMe / getUpdates / sendMessage
│  │  │  ├─ polling.py             # Long-poll + ingest() dùng chung cho cả webhook
│  │  │  ├─ normalize.py           # payload Zalo → InboundMessage
│  │  │  └─ send.py                # ChannelPort, chunk 2000 ký tự
│  │  ├─ web/
│  │  │  ├─ routes.py              # /api/chat, /api/stream/{id}, /api/threads...
│  │  │  ├─ normalize.py  send.py  # ChannelPort → PUBLISH Redis → SSE
│  │  │  ├─ templates/index.html   # Jinja2 — không có bước build
│  │  │  └─ static/app.js styles.css
│  │  ├─ zalo_personal/         ✗  # Tùy chọn — chỉ tạo khi Bot Platform không đủ
│  │  └─ cli/normalize.py          # Adapter thứ ba, dùng để dev Phase 0
│  │
│  ├─ infra/
│  │  ├─ db.py                     # asyncpg pool
│  │  ├─ redis_client.py           # KHÔNG đặt tên redis.py — sẽ che mất gói thật
│  │  ├─ queue.py                  # ARQ — queue + job_id + FIFO theo thread (§5.2)
│  │  ├─ logger.py                 # structlog, luôn kèm trace_id, luôn redact
│  │  ├─ http.py                   # MỘT pool kết nối HTTP cho cả process (§16.8)
│  │  ├─ dedupe.py                 # SET NX — atomic, KHÔNG check-then-set
│  │  ├─ cancel.py                 # Cờ dừng qua Redis (api và worker là hai process)
│  │  ├─ allowlist.py              # Bảng thread_allowlist
│  │  ├─ ratelimit.py              # Token bucket 3 tầng (Lua) + chốt chặn ngân sách ngày
│  │  ├─ http.py                   # MỘT pool kết nối HTTP cho cả process (§16.8)
│  │  └─ metrics.py                # Đọc usage_log → `cli stats` và /api/metrics
│  │
│  └─ shared/
│     ├─ result.py                 # Result[T,E] — lỗi là giá trị, không phải raise
│     ├─ chunk_text.py
│     └─ redact.py                 # Che token / số điện thoại trước khi log
│
├─ db/
│  ├─ migrations/                  # Đánh số tăng dần, chỉ tiến, không sửa file cũ
│  │  ├─ 0001_extensions.sql       0004_knowledge_1024.sql   ← số chiều nằm trong TÊN file
│  │  ├─ 0002_messages.sql         0005_ops.sql
│  │  ├─ 0003_memory.sql           0006_message_direction.sql
│  │  ├─                           0007_thread_meta.sql
│  │  ├─                           0008_kb_tsv_embed_input.sql
│  │  └─ 0009_usage_tools.sql      0010_drop_used_tools.sql   ← xem plan §19
│  └─ seed/
│
├─ evals/
│  ├─ dataset/qa.jsonl             # 50 câu VIẾT TAY — hiện mới có dòng mẫu
│  ├─ runner.py                   # Chạy được; ĐỎ khi qa.jsonl còn là dòng mẫu
│  └─ metrics/                     # recall@5, faithfulness, latency
│
├─ tests/
│  ├─ unit/                        # chỉ agents/ — không I/O
│  ├─ contract/                   # adapters ăn fixtures Zalo thật đã ghi lại
│  ├─ integration/                # Postgres+pgvector, Redis, embedding thật
│  └─ security/
│     └─ test_cross_thread_leak.py # ⚠ Test bắt buộc, xem §10
│
├─ ops/
│  ├─ docker-compose.yml           # api, worker, maintenance, zalo, postgres, redis
│  │                               #   + profile `monitoring`: prometheus, grafana
│  ├─ Dockerfile
│  ├─ guard_env.py                 # L7 — cưỡng chế bằng AST
│  ├─ guard_sql.py                 # L4b — cưỡng chế bằng AST
│  ├─ canary_import_rules.py       # Chứng minh cả 8 luật thật sự bắt được vi phạm
│  ├─ benchmark_embedding.py       # So sanh model embedding tren du lieu that
│  ├─ benchmark_rerank.py          # So sanh nha cung cap rerank + de xuat nguong
│  ├─ prometheus.yml               # Scrape /api/metrics moi 30s
│  └─ grafana/                     # Datasource + dashboard + 4 luật cảnh báo, cắm sẵn
│                                 #   (mã nguồn, không chỉnh trong giao diện rồi quên)
│
├─ docs/                           # master-plan, plan-thi-cong, dep-rules-verified, archive/
├─ .importlinter                   # cưỡng chế luật ở §1
├─ .env.example
├─ pyproject.toml                  # phụ thuộc + mypy + ruff + pytest, một chỗ
├─ uv.lock
├─ README.md
└─ ARCHITECTURE.md
```

---

## 4. Ports — hợp đồng giữa agents và phần còn lại

Đây là toàn bộ bề mặt mà `agents/` được phép nhìn thấy. Ngắn là có chủ ý.

Port là `typing.Protocol`, không phải lớp cơ sở: cấu trúc khớp là đủ, nên `structlog.BoundLogger` cắm
thẳng vào `LoggerPort` mà không cần một lớp adapter chỉ để thoả kế thừa.

**Sáu port, sau khi dọn ngày 08/09/2026.** `KnowledgePort` và `ClockPort` đã bị xoá:
cả hai được khai báo, tiêm vào `Deps`, và **không chỗ nào gọi**. Đường tra cứu thật đi
qua công cụ `search_knowledge_base`, tức qua `ToolPort`. Dự án này có một câu riêng cho
chuyện đó — *"thêm port là quyết định kiến trúc, không phải tiện tay"* — và một port
chết còn tệ hơn không có port, vì người đọc sau sẽ tưởng đó là đường đi thật.

```python
# agents/domain/thread.py
# Không truyền platform + thread_id rời rạc. Truyền một object.
# Lý do: không ai quên tham số thứ hai của một object cả.
Platform = Literal["zalo_bot", "zalo_personal", "cli", "web"]

@dataclass(frozen=True, slots=True)
class ThreadScope:
    platform: Platform
    thread_id: str

# agents/ports/llm.py
class LlmPort(Protocol):
    async def reply(
        self, *, system: str, messages: tuple[LlmMessage, ...], max_tokens: int,
        effort: Effort, ctx: CallContext, tools: tuple[ToolSpec, ...] = (),
    ) -> LlmResult: ...          # system PHẢI là hằng số

    async def cheap(
        self, *, system: str, input: str, max_tokens: int,
        route: CheapRoute, ctx: CallContext,
    ) -> str: ...                # rewrite / summarize / extract_facts

# LlmMessage là UNION, không phải {role, content} phẳng: lượt assistant có thể KHÔNG
# có văn bản mà chỉ có lời gọi tool, và lượt tool phải mang theo tool_call_id. Kiểu
# phẳng không biểu diễn được vòng ReAct.
LlmMessage: TypeAlias = UserMessage | AssistantMessage | ToolMessage

# agents/ports/memory.py
class MemoryPort(Protocol):
    async def append(self, scope: ThreadScope, msg: NewMessage) -> None: ...
    async def recent(self, scope: ThreadScope, limit: int) -> list[StoredMessage]: ...   # L1
    async def summary(self, scope: ThreadScope) -> str | None: ...                       # L2
    async def facts(self, scope: ThreadScope, subject_id: str, query: str) -> list[Fact]: ...  # L3
    async def remember(self, scope: ThreadScope, fact: NewFact) -> None: ...
    async def forget(self, scope: ThreadScope, actor_id: str, pattern: str) -> list[Fact]: ...
    async def list_facts(self, scope: ThreadScope, subject_id: str) -> list[Fact]: ...
# Mọi phương thức nhận ThreadScope ở tham số ĐẦU TIÊN. Không có biến thể nào bỏ nó.

# agents/ports/channel.py
class ChannelPort(Protocol):
    max_message_chars: int       # Zalo 2000 — agents không hardcode con số của nền tảng
    async def typing(self, scope: ThreadScope) -> None: ...
    async def send(self, scope: ThreadScope, text: str, reply_to: str | None = None) -> None: ...

# agents/ports/tool.py — thêm ở Giai đoạn 3
class ToolPort(Protocol):
    def specs(self) -> tuple[ToolDefinition, ...]: ...
    async def call_many(
        self, calls: tuple[ToolCall, ...], ctx: CallContext
    ) -> tuple[ToolResult, ...]: ...
    # call_many chứ không phải call: model trả nhiều tool_call trong MỘT message và
    # chúng phải chạy đồng thời. Phải trả ĐỦ số kết quả, kể cả cái thất bại —
    # thiếu một tool_call_id là cả request sau trả 400.
```

---

## 5. Luồng dữ liệu

### 5.1 Đường vào (process `api`, phải xong <2s)

```
HTTP POST  (hoặc một vòng getUpdates của process `zalo`)
  → verify chữ ký           Zalo: đường dẫn bí mật + shared token
                            (webhook chưa làm — Zalo chưa công bố sơ đồ ký)
  → parse tối thiểu, lấy message_id
  → dedupe.claim(id)        Redis SET NX EX 600 — atomic, không phải GET rồi SET
  → normalize()             → InboundMessage
  → enqueue_reply(msg)      job_id = message_id
  → return 202              ⟵ KẾT THÚC. Không chờ LLM ở đây.
```

Verify chữ ký phải chạy **trên raw body, trước khi parse JSON**. Trong FastAPI phải đọc
`await request.body()` và tự parse; nhận `body: Model` như route thường là đã parse mất rồi, và HMAC sẽ
luôn sai trên payload đã chuẩn hoá lại — bạn sẽ ngồi debug nhầm chỗ cả ngày.

### 5.2 Hàng đợi

```python
# infra/queue.py
await queue.enqueue_job(
    "handle_reply", to_payload(msg),
    _job_id=job_id_for(msg.platform, msg.message_id),   # lớp chống trùng thứ 2
    _queue_name=QUEUE_REPLY,
)
```

**Đây là chỗ plan bỏ sót hoàn toàn.** Hai tin nhắn liên tiếp trong một nhóm chạy song song thì bot
**trả lời sai thứ tự**.

ARQ không có khái niệm "group" — không có cách khai báo "các job cùng `thread_id` phải chạy tuần tự".
Giải pháp hiện tại: `WorkerSettings.max_jobs = 1` — tuần tự toàn cục, thứ tự đúng tuyệt đối. Trần thông
lượng ~240 câu/giờ ở trường hợp xấu nhất (timeout 15s/câu), trong khi mục tiêu là 200–1000 câu một
**ngày**. Chạm trần thì tự khoá phân tán per-thread bằng Redis. Không giải quyết sớm một vấn đề chưa có.

**Hai bẫy đã trả giá, ghi ra để không dẫm lại:**

- `WorkerSettings` **phải** khai `queue_name = QUEUE_REPLY` khớp với `_queue_name` lúc enqueue. Thiếu
  dòng đó thì worker lắng nghe queue mặc định còn job nằm ở queue `reply` — **không ai nhận, không ai
  báo lỗi**.
- `job_id` dùng `-` chứ không dùng `:`. Một số hàng đợi coi `:` là dấu phân cách khoá Redis và từ chối
  thẳng. Các khoá Redis khác trong dự án vẫn dùng `:` bình thường; ràng buộc này của riêng `job_id`.

Ba queue tách biệt: `reply` (đường phản hồi, ưu tiên), `maintenance` (tóm tắt, trích fact), `ingest` (nạp tài liệu). Không trộn — một job ingest 10 phút không được phép chặn một câu trả lời.

### 5.3 Pipeline (process `worker`)

`agents/pipeline/handle_message.py` — danh sách stage tường minh, mỗi stage một file thuần:

```
 1. access          Thread có trong allowlist? Không → dừng, im lặng.
 2. mention         is_group && !mentioned_bot → dừng. Bóc @nam_chatbot.
 3. command         memory / quên / help → xử lý và TRẢ LỜI LUÔN, không gọi LLM.
 4. ratelimit       user 10/phút, thread 30/phút, global theo budget.
 5. budget-guard    Chi tiêu hôm nay > ngưỡng → chế độ từ chối lịch sự.
                    ⟵ CHỐT CHẶN CỨNG, không phải alert.
 6. persist         Ghi tin vào Postgres (nguồn thật) + đẩy Redis cache.
 7. typing          channel.typing() — không await.
 8. rewrite         Câu hỏi thiếu ngữ cảnh → viết lại bằng model rẻ.
 9. retrieve        knowledge.search() khi model gọi tool hoặc heuristic bật.
10. recall          L2 summary + L3 facts (luôn kèm ThreadScope).
11. build-prompt    Ghép theo §7.3, áp hard cap từng tầng.
12. generate        llm.reply() — timeout 15s, có fallback.
13. respond         channel.send() — tự chunk.
14. account         cost-meter → usage_log.
15. schedule        Đẩy job tóm tắt / trích fact vào queue `maintenance`.
                    KHÔNG chạy tại đây.
```

Stage 3 đứng trước stage 4 là có chủ ý: người dùng phải xoá được memory của mình ngay cả khi đang bị rate limit.

---

## 6. Mô hình dữ liệu

### 6.1 Sửa lỗi mất dữ liệu L1/L2

Plan viết: L1 = 15 tin trong Redis TTL 2h; nén khi đủ 30 tin; xoá 15 tin đã nén khỏi Redis. Ba mâu thuẫn cùng lúc:

- Nếu chỉ giữ 15 tin thì **không bao giờ đạt 30** → L2 không bao giờ chạy.
- Nhóm im 2 tiếng (mỗi đêm) → toàn bộ tin chưa nén bốc hơi, **không bao giờ vào L2**.
- Redis đang đóng vai nguồn sự thật cho dữ liệu cần bền.

Sửa: **Postgres là nguồn thật, Redis chỉ là cache đọc.**

```sql
-- 0002_messages.sql
CREATE TABLE inbound_message (
  platform     TEXT NOT NULL,
  message_id   TEXT NOT NULL,
  thread_id    TEXT NOT NULL,
  sender_id    TEXT NOT NULL,
  sender_name  TEXT NOT NULL,
  text         TEXT NOT NULL,
  is_group     BOOLEAN NOT NULL,
  reply_to_id  TEXT,
  summarized   BOOLEAN NOT NULL DEFAULT FALSE,   -- đã bị L2 nuốt chưa
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (platform, message_id)             -- dedup lớp 3, sống lâu hơn TTL Redis
);
CREATE INDEX ON inbound_message (platform, thread_id, created_at DESC);
CREATE INDEX ON inbound_message (platform, thread_id) WHERE NOT summarized;

CREATE TABLE thread_summary (
  platform    TEXT NOT NULL,
  thread_id   TEXT NOT NULL,
  summary     TEXT NOT NULL,
  msg_count   INT  NOT NULL DEFAULT 0,
  gen_count   INT  NOT NULL DEFAULT 0,   -- số lần nén đệ quy; > 6 thì cảnh báo trôi thông tin
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (platform, thread_id)
);
```

L1 = `ORDER BY created_at DESC LIMIT 15`, kết quả cache Redis TTL 2h. Cache trượt thì đọc lại DB — không mất gì. Job nén chạy trên `WHERE NOT summarized`, hoàn toàn không phụ thuộc TTL.

`gen_count` có mặt vì plan đã tự chỉ ra cạm bẫy "sau 5–6 lần nén summary bắt đầu sai lệch" nhưng không đề xuất cách phát hiện. Đây là cách phát hiện.

### 6.2 Memory L3 — bản đầy đủ

Master plan khi hợp nhất đã làm rơi `last_used_at` và **toàn bộ index**, trong khi vẫn tuyên bố `thread_id` là "hàng rào chống rò rỉ". Hàng rào đó cần index.

```sql
-- 0003_memory.sql
CREATE TABLE memory_fact (
  id           BIGSERIAL PRIMARY KEY,
  platform     TEXT NOT NULL,
  thread_id    TEXT NOT NULL,
  subject_id   TEXT NOT NULL,              -- 'user:123' | 'thread:abc'
  content      TEXT NOT NULL,
  embedding    VECTOR(1024) NOT NULL,
  source       TEXT NOT NULL CHECK (source IN ('explicit','implicit')),
  confidence   REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  created_by   TEXT NOT NULL,              -- ai gây ra fact này (audit)
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at TIMESTAMPTZ,
  revoked_at   TIMESTAMPTZ,
  revoked_by   TEXT
);

CREATE INDEX ON memory_fact (platform, thread_id, subject_id) WHERE revoked_at IS NULL;
CREATE INDEX ON memory_fact USING hnsw (embedding vector_cosine_ops) WHERE revoked_at IS NULL;
```

**Quyền xoá — plan chưa định nghĩa, tôi chốt:**

| Lệnh | Ai được dùng | Phạm vi |
|---|---|---|
| `nhớ giúp: <nội dung>` | bất kỳ ai | ghi fact về chính mình, `source=explicit`, `confidence=1.0` |
| `memory` | bất kỳ ai | fact có `subject_id = 'user:' \|\| sender_id`, **trong thread hiện tại** |
| `quên <nội dung>` | bất kỳ ai | chỉ fact về **chính mình**; liệt kê ứng viên rồi **hỏi xác nhận** trước khi revoke |
| `quên hết` | bất kỳ ai | chỉ fact về chính mình |
| `đồng ý` / `đồng ý 1,3` | người vừa gõ `quên` | xác nhận tất cả, hoặc chọn theo số |
| fact `thread:*` | chỉ admin thread (bảng `thread_allowlist`) | fact chung của nhóm |

Không có bước xác nhận thì một lần gõ nhầm là mất sạch, mà soft delete lại không có lệnh khôi phục. Trong nhóm 50 người, "ai được xoá của ai" không thể để ngỏ.

`subject_id` **suy ra từ `sender_id` của tin nhắn**, không bao giờ nhận từ văn bản người dùng gõ — đó là
chỗ chặn "người X xoá fact của người Y".

**Ngưỡng cosine — sửa 06/09/2026.** Bản trước ghi `> 0,9` cho chống trùng và `> 0,85` cho lệnh `quên`.
Cả hai viết trước khi có phép đo nào và **cả hai đều sai** với `text-embedding-3-large` @ 1024 chiều:

| | Cũ | Đo được (`ops/calibrate_dedupe.py`) | Chốt |
|---|---|---|---|
| Trùng ý / mâu thuẫn | 0,90 | cần bắt 0,736–0,958 · cần bỏ qua 0,276–0,524 | **0,70** |
| Lệnh `quên` | 0,85 | cách người dùng nói khớp chỉ 0,354–0,589 | **0,30** + top-5 |

Với 0,85 thì lệnh `quên` không bao giờ tìm thấy gì, và người dùng tưởng đã xoá xong.

### 6.3 Knowledge L4 — schema mà cả 3 file kế hoạch **không hề có**

```sql
-- 0001_extensions.sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Bọc unaccent thành IMMUTABLE để dùng được trong generated column.
-- Dạng 2 tham số (chỉ định rõ dictionary) mới immutable; dạng 1 tham số thì không.
CREATE FUNCTION vn_tsv(t text) RETURNS tsvector
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $fn$
  SELECT to_tsvector('simple', unaccent('unaccent', t))
$fn$;
```

```sql
-- 0004_knowledge_1024.sql
CREATE TABLE kb_document (
  id          BIGSERIAL PRIMARY KEY,
  title       TEXT NOT NULL,
  source_path TEXT NOT NULL,
  version     INT  NOT NULL DEFAULT 1,
  checksum    TEXT NOT NULL,
  ingested_by TEXT NOT NULL,          -- chỉ admin; ghi lại là ai
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_path, version)
);

CREATE TABLE kb_chunk (
  id           BIGSERIAL PRIMARY KEY,
  doc_id       BIGINT NOT NULL REFERENCES kb_document(id) ON DELETE CASCADE,
  ord          INT  NOT NULL,
  section      TEXT,
  page         INT,
  content      TEXT NOT NULL,          -- nguyên văn: hiển thị + trích dẫn
  embed_input  TEXT NOT NULL,          -- content + câu ngữ cảnh (contextual retrieval)
  embedding    VECTOR(1024) NOT NULL,
  tsv          tsvector GENERATED ALWAYS AS (vn_tsv(content)) STORED,
  token_count  INT NOT NULL,
  UNIQUE (doc_id, ord)
);

CREATE INDEX ON kb_chunk USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON kb_chunk USING gin (tsv);
```

Hai chỗ plan lập luận đúng nhưng không có phương án kỹ thuật:

- **Không có index vector** → sequential scan, hỏng mục tiêu p95 < 5s ngay khi có vài chục nghìn chunk. Đã thêm HNSW.
- **BM25 tiếng Việt.** Postgres không có dictionary tiếng Việt. `to_tsvector('simple', …)` không bỏ dấu, nên "tra cuu" không khớp "tra cứu" — trong khi chính plan nói BM25 tồn tại để bắt mã sản phẩm và tên riêng. Phải đi qua `unaccent`. Đây là ~2 ngày công **không có** trong lịch 6 tuần.

### 6.4 Vận hành

```sql
-- 0005_ops.sql
CREATE TABLE usage_log (
  id BIGSERIAL PRIMARY KEY,
  trace_id TEXT NOT NULL,
  platform TEXT NOT NULL, thread_id TEXT NOT NULL, sender_id TEXT NOT NULL,
  route TEXT NOT NULL,          -- reply | rewrite | summarize | extract | embed | rerank
  model TEXT NOT NULL,
  input_tokens INT, output_tokens INT,
  cache_read_tokens INT, cache_write_tokens INT,
  cost_usd NUMERIC(10,6), latency_ms INT, ok BOOLEAN NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON usage_log (created_at);
CREATE INDEX ON usage_log (platform, thread_id, created_at);

CREATE TABLE thread_allowlist (
  platform TEXT NOT NULL, thread_id TEXT NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('open','allowlist','disabled')),
  added_by TEXT NOT NULL, added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (platform, thread_id)
);
```

`cache_read_tokens` có mặt vì nếu nó bằng 0 suốt thì prompt caching **đang không ăn**, và bạn đang trả giá đầy đủ cho 1500 token tài liệu ở mỗi câu hỏi mà không hề biết.

### 6.5 Không gian khoá Redis

| Khoá | Kiểu | TTL | Dùng làm gì |
|---|---|---|---|
| `dedup:{platform}:{message_id}` | string | 10 phút | `SET NX` — chống trùng |
| `replied:{platform}:{message_id}` | string | 1h | cờ "đã trả lời", chặn retry gửi lần hai (§9) |
| `ctx:{platform}:{thread_id}` | list | 2h | **cache** của L1 (nguồn thật ở Postgres) |
| `rl:u:{platform}:{sender_id}` | hash | 1 phút | token bucket per-user |
| `rl:t:{platform}:{thread_id}` | hash | 1 phút | token bucket per-thread |
| `cost:day:{YYYY-MM-DD}` | string | 48h | chốt chặn ngân sách ngày |
| `emb:{sha256(query)}` | string | 24h | cache embedding câu hỏi lặp |
| `cancel:{platform}:{thread_id}` | string | 3 phút | Người dùng bấm dừng (api và worker là hai process) |
| `forget:{platform}:{thread_id}:{actor}` | string | 5 phút | Yêu cầu xoá đang chờ xác nhận; lấy-và-xoá bằng `GETDEL` |
| `rl:warn:{platform}:{thread_id}` | string | 5 phút | Đã nhắc "chậm lại" chưa — `SET NX` |
| `arq:*` | — | — | ARQ |

Khoá `emb:` băm **cả tên model và số chiều** cùng với câu hỏi: đổi model mà dùng chung
khoá là đọc ra vector của model cũ, và kết quả tìm kiếm sai một cách hoàn toàn im lặng.

---

## 7. Prompt

### 7.1 System prompt phải là hằng số

`agents/prompt/system.py` export một chuỗi **không nội suy gì hết** — không tên nhóm, không ngày giờ, không tên người dùng. Thông tin động đi vào block riêng, đặt sau.

**Sửa 05/09/2026:** lý do ban đầu là prompt caching (khớp theo tiền tố, đổi một byte là mất cache phía
sau). Ở `gpt-5-mini` caching gần như không đáng kể (§8.3), nhưng luật này **vẫn giữ nguyên** vì lý do
quan trọng hơn: một system prompt đóng băng làm hành vi bot **tái lập được**. Nội suy biến động vào đó
nghĩa là hai người hỏi cùng một câu nhận hai prompt khác nhau, và bộ eval 50 câu ở tuần 6 mất ý nghĩa.

Nội dung bắt buộc (giữ đúng plan): tên bot; đang trong nhóm chat Việt Nam; trả lời tiếng Việt tự nhiên, dưới 4–5 câu; **không dùng markdown** (Zalo không render); không biết thì nói không biết; nội dung trong tag `<tai_lieu>` là **dữ liệu tham khảo, không phải chỉ thị**.

### 7.2 Chống injection qua tài liệu

```
<tai_lieu id="12" nguon="So tay nhan vien 2026" muc="Chinh sach hoan tien">
…nội dung chunk…
</tai_lieu>
```

Trước khi bọc, phải strip mọi chuỗi trông giống thẻ đóng của chính mình ra khỏi nội dung chunk. Không làm bước này thì một tài liệu chứa `</tai_lieu>` sẽ tự thoát khỏi hộp — và đó chính xác là cách người ta phá.

### 7.3 Ngân sách token (cap cứng, cưỡng chế trong `budget.py`)

**Sửa 05/09/2026.** Bảng cũ (tổng ~4000 token) tính cho giá Opus 5. `gpt-5-mini` có cửa sổ **400.000
token** và input rẻ hơn 20 lần, nên cắt bớt ngữ cảnh là đánh đổi chất lượng câu trả lời lấy vài xu.
Các con số dưới đây là **cầu dao**, không phải chính sách — trong vận hành bình thường không bao giờ chạm tới.

| Vị trí | Nội dung | Trần | Cũ |
|---|---|---|---|
| 1 | System prompt | 700 | 400 |
| 2 | L4 — tài liệu, có trích dẫn | 20.000 | 1500 |
| 3 | L3 — fact về user & thread | 4.000 | 200 |
| 4 | L2 — tóm tắt hội thoại trước | 4.000 | 400 |
| 5 | L1 — 15 tin gần nhất | 20.000 | 1200 |
| 6 | Câu hỏi hiện tại | 8.000 | 200 |

Cột "Cache" bị bỏ: xem §8.3, caching không còn là lý do để định hình prompt.

Vượt trần thì **cắt đúng tầng đó**, không đụng tầng khác. `budget.py` trả về cả phần đã bị cắt để ghi
log — một lần cắt giờ là **tín hiệu bất thường cần xem**, không phải chuyện thường ngày.

Cầu dao vẫn tồn tại vì ở 400.000 token thì một request tốn ~$0,10: một tài liệu dài lọt vào prompt là
đủ đốt ngân sách ngày trong vài chục lần gọi. Chốt chặn cuối cùng vẫn là `DAILY_BUDGET_USD`.

---

## 8. Model và chi phí

### 8.1 Bảng route

| Route | Model | `reasoning_effort` | `max_completion_tokens` | Lý do |
|---|---|---|---|---|
| `reply` | `gpt-5-mini` | `low` | 16000 | Chat, nhạy latency (p95 < 5s). Hạ effort là đòn bẩy latency đúng chỗ — không phải hạ model. |
| `rewrite` | `gpt-5-mini` | `low` | 2000 | Viết lại câu hỏi |
| `summarize` | `gpt-5-mini` | `low` | 4000 | Async |
| `extract-facts` | `gpt-5-mini` | `low` | 4000 | Async, structured output |

Bốn dòng này nằm **duy nhất** ở `llm/models.py`. Không rải model ID khắp code.

Các cap trên rộng hơn độ dài văn bản mong đợi rất nhiều **là có chủ đích**: token reasoning tính vào
`max_completion_tokens`. Cap 200 cho `rewrite` gần như chắc chắn trả về chuỗi rỗng.

### 8.2 Embedding và rerank — lỗ hổng lớn nhất của kế hoạch

Kế hoạch ngầm giả định nhà cung cấp LLM có luôn embedding và rerank.

**Sửa 05/09/2026 cùng D1.** Sau khi chuyển sang OpenAI, một nửa lỗ hổng được lấp: OpenAI **có** embedding
(`text-embedding-3-small` $0,02/1M, `text-embedding-3-large` $0,13/1M), dùng chung API key với LLM.
Nhưng OpenAI **không có API rerank**, nên rerank vẫn phải là nhà cung cấp thứ hai (Cohere / Jina / Voyage).

**Chốt 07/09/2026:** mặc định là **Cohere** (`rerank-multilingual-v3`), kèm một bản
`LexicalOverlapReranker` **không cần khoá** để đường ống chạy được khi chưa mua. Bản
không khoá xếp theo tỉ lệ từ của câu hỏi xuất hiện trong đoạn văn — nó không phải
cross-encoder và không giả vờ là một cái.

Vẫn phải benchmark trên chính tài liệu tiếng Việt của bạn trước khi chốt thật — đây là
quyết định mua sắm, không phải một dòng ghi chú. Và `RERANK_MIN_SCORE = 0,35` hiện được
chọn cho thang điểm của bản không khoá; cross-encoder có thang khác, nên **đo lại ngưỡng
khi đổi nhà cung cấp**. Ràng buộc cứng: số chiều phải khớp `VECTOR(1024)`; `text-embedding-3-large`
nhận tham số `dimensions` để cắt về đúng 1024.

Hệ quả với cấu trúc: `EmbedderPort` và `RerankerPort` là **port thật**, có ít nhất hai implementation từ ngày đầu (thật + fake cho test). Đổi nhà cung cấp = viết một file trong `llm/`, không phải sửa `knowledge/`.

Ràng buộc cứng: số chiều model phải khớp `VECTOR(1024)`. `main/container.py` kiểm tra lúc khởi động:

```python
# main/container.py — assert_embedding_dim()
# Doc atttypmod cua cot embedding tu pg_attribute, so voi settings.EMBEDDING_DIM.
# Lech -> RuntimeError, khong cho process khoi dong.
# Khong co buoc nay, loi se hien ra duoi dang "ket qua tim kiem kem" — ba tuan sau.
#
# BAY da tra gia: atttypmod cua pgvector CHINH LA so chieu. Ban dau viet
# `atttypmod - 4`, chep tu quy uoc cua varchar. Loi song sot rat lau vi nhanh
# EMBEDDING_PROVIDER=fake thoat truoc khi cham toi day — chot chan chi duoc thu
# lan dau tien luc bat provider that.
```

### 8.3 Chi phí — con số mà không file nào đưa ra

**Sửa 05/09/2026 cùng D1.** `gpt-5-mini`: **$0,25 / 1M input, $0,025 / 1M cached input, $2,00 / 1M output**.
(Để so sánh, bản cũ dùng Opus 5 ở $5 / $25 — đắt hơn 20× input và 12,5× output.)

Một câu trả lời (~3900 token input, ~400 token output hiển thị, ~500 token reasoning):

```
input      3900 × $0,25/1M  = $0,000975
output      400 × $2,00/1M  = $0,000800
reasoning   500 × $2,00/1M  = $0,001000   <- tinh gia OUTPUT
                            ≈ $0,0028 / cau
```

| Lưu lượng | Mỗi ngày | Mỗi tháng |
|---|---|---|
| 200 câu/ngày | ~$0,6 | ~$17 |
| 1.000 câu/ngày | ~$3 | ~$85 |

**Token reasoning tính giá output** và không hiện trong câu trả lời — đây là khoản mà bảng cũ không hề
có. Phải đo bằng `usage_log` (`completion_tokens_details.reasoning_tokens`) rồi mới chốt
`DAILY_BUDGET_USD`, đừng tin con số ước lượng ở trên.

**Prompt caching ĐANG ăn** — đo từ `usage_log`, không suy đoán:

```
20 / 32 lan goi co cache hit    cache_read_tokens: 1408 - 1792
SYSTEM_PROMPT: 1539 token       OpenAI chia cache theo block 128 token
1408 = 11 x 128                 -> phan duoc cache CHINH LA system prompt
```

Bản trước của mục này viết *"caching gần như không đáng kể, system prompt chỉ ~620 token nên không đạt
ngưỡng 2048"*. **Sai cả ba số.** System prompt là 1539 token, cache hit thấp nhất quan sát được là 1408,
nên ngưỡng thực tế nằm dưới mức đó. Kết luận rút ra từ tiền đề sai đó cũng phải rút lại.

Hệ quả: §7.1 (*"system prompt là hằng số"*) giờ có **hai** lý do chứ không phải một — tính tái lập, **và
tiền**. Input được cache tính $0,025/1M thay vì $0,25/1M, tức rẻ hơn 10 lần trên phần lớn nhất của prompt.
Đổi một byte ở đầu chuỗi là mất cache của toàn bộ phần sau.

12/32 lượt không có cache là lượt **đầu tiên của một tiền tố** (lần đó là cache *write*) hoặc lượt sau
một quãng nghỉ dài. Đó là hành vi bình thường, không phải hỏng.

Suy ra: ngưỡng rate limit global và `cost:day` vẫn phải tính ngược từ ngân sách bạn chấp nhận — chỉ là
ngân sách đó giờ mua được nhiều hơn 10 lần.

---

## 9. Lỗi và fallback

```python
# agents/domain/errors.py — lỗi là GIÁ TRỊ, không phải exception.
# Một lỗi upstream là kết quả bình thường của đường ống (có câu fallback, có quyết
# định retry), không phải sự cố bất thường. Exception vẫn dùng cho lỗi lập trình.
BotError: TypeAlias = (
    RateLimited | BudgetExceeded | NotAllowed | UpstreamTimeout | UpstreamError | BadPayload
)
```

| Lỗi | Hành vi trong nhóm | Retry job? |
|---|---|---|
| `not_allowed` | **im lặng** | không |
| `rate_limited` | một câu ngắn, tối đa 1 lần / 5 phút / thread | không |
| `budget_exceeded` | báo tạm dừng đến ngày mai | không |
| `upstream_timeout` (LLM > 15s) | câu fallback ngắn | không — người dùng đã nhận trả lời rồi |
| `upstream_error` 5xx / 429 | **im lặng** ở các lần thử đầu, fallback ở lần cuối | có, tối đa 3 |
| `upstream_error` 401/403 | câu báo lỗi cấu hình, **không** nói "thử lại sau" | không — thử lại một cấu hình sai ba lần vẫn sai ba lần |
| `bad_payload` | im lặng, log mức error | không |

**Luật:** retry không bao giờ được gửi tin nhắn thứ hai cho cùng một `message_id`.

Luật đó đúng, nhưng cách cưỡng chế ban đầu **đã vô hiệu hoá chính cơ chế retry** — sửa
07/09/2026. Một khoá Redis không gánh được hai ý nghĩa:

| Khoá / cờ | Ý nghĩa | Đặt khi nào |
|---|---|---|
| `replied:{platform}:{message_id}` | **Đã gửi văn bản cho người dùng** | Chỉ khi pipeline thật sự đã gửi gì đó (`Failed.replied` / `Handled.replied`) |
| `Deps.is_final_attempt` | Đây là lần thử cuối | Worker tính từ `ctx["job_try"]` của ARQ |

Bản cũ đặt `replied:` ở **mọi** thất bại rồi mới `raise` để hàng đợi thử lại — nên lần
retry vào lại `handle_reply`, gặp cờ đó và thoát ngay. `max_tries = 3` chưa bao giờ thử
lại lần nào.

Hệ quả của cách sửa: lỗi **có thể** retry được thì pipeline **không gửi gì** ở các lần
thử đầu. Gửi câu fallback ngay mà lần sau thành công nghĩa là người dùng nhận hai tin
cho một câu hỏi. Đổi lại họ chờ lâu hơn — đó là cái giá đúng, vì bản cũ trả lời nhanh
nhưng **không bao giờ** đưa được câu trả lời thật.

---

## 10. Test — bốn tầng, một cái bắt buộc

| Tầng | Ở đâu | Chạy khi nào | Yêu cầu |
|---|---|---|---|
| Unit | `tests/unit` — chỉ `agents/` | mọi commit | Không I/O, < 2s. Đây là lý do tồn tại của ports. |
| Contract | `tests/contract` — adapter ăn fixtures thật | mọi commit | Ghi payload thật một lần, dùng mãi. Zalo đổi payload → test đỏ, không phải prod đỏ. |
| Integration | `tests/integration` — Postgres+pgvector, Redis, embedding thật | mọi PR | Máy bạn: bỏ qua có nêu lý do. **CI: ĐỎ** |
| Security | `tests/security` — rò rỉ cross-thread | mọi PR | **Không được phép xoá**, và trên CI không được bỏ qua |
| Eval | `evals/` — 50 câu | khi đổi prompt / chunking / model | Recall@5 > 0.85, faithfulness > 0.9, p95 < 5s |

**363 test** (07/09/2026). Cả bốn tầng đều có file, và không tầng nào tự bỏ qua trong im lặng.

**Test không được phép xoá:**

```python
# tests/security/test_cross_thread_leak.py
# Ghi fact o thread A -> truy van tu thread B qua MOI phuong thuc public cua
#   MemoryPort -> phai rong, khong tru phuong thuc nao.
# Fact da revoke -> khong xuat hien trong prompt cuoi cung (kiem tra tren CHUOI DA
#   BUILD, khong phai tren ket qua repository): ro ri co the xay ra o builder trong
#   khi repository van sach.
```

Master plan xếp rò rỉ cross-group là "xác suất thấp, hậu quả nghiêm trọng". Xác suất thấp **là nhờ** có test này. Bỏ test thì xác suất không còn thấp nữa.

---

## 11. Thứ tự thi công — đã sửa đường găng

Bản đầu của mục này xoay quanh đường găng của Meta: App Review, Business Verification,
screencast. **Toàn bộ phần đó không còn** — Messenger đã bị bỏ khỏi phạm vi ngày
07/09/2026, và cùng với nó là thứ mất thời gian nhất trong cả kế hoạch.

Trạng thái thật, không phải lịch dự kiến:

| Giai đoạn | Nội dung | Trạng thái |
|---|---|---|
| 0–2 | `config` `agents` `infra` `llm` `shared` `adapters/cli` `adapters/web` + prompt ba tầng | Xong |
| 3 | Tool layer + vòng ReAct, 6 chặn cứng, 6 lớp chống injection | Xong, trừ `web_search` (thiếu `TAVILY_API_KEY`) |
| 4 | `adapters/zalo_bot` — polling, dedup, rate limit 3 tầng, allowlist | Xong |
| ~~5~~ | ~~Messenger~~ | **Bỏ khỏi phạm vi** |
| 6 | `knowledge/` — ingest, chunk, hybrid, RRF, rerank | Xong (07/09/2026) |
| 7 | `memory/` — L2, L3 explicit, L3 implicit (mặc định TẮT) | Xong |
| 8 | `evals/` runner + workflow nightly + `cli stats` + `/api/metrics` + Grafana | Xong; **thiếu 50 câu hỏi viết tay** |
| 9 | Thiết kế lại giao diện web | Xong (07/09/2026) |

**Còn lại, và cả hai đều cần thứ không tự tạo ra được:**

1. **Tài liệu thật** — để benchmark rerank (`ops/benchmark_rerank.py` đã sẵn) và viết 50 câu eval.
2. **Sơ đồ ký chữ ký webhook của Zalo** — viết phần xác minh bằng cách đoán là loại lỗi hỏng im lặng.

`TAVILY_API_KEY` đã có từ 07/09/2026; `web_search` đã chạy thật qua một vòng ReAct.

**Definition of Done mỗi giai đoạn:** `lint-imports` + hai guard + canary xanh + test tầng tương ứng xanh + ít nhất một mục trong checklist go-live được tick. Không có khái niệm "gần xong".

---

## 12. Cấu hình

`.env.example` — mọi biến đều khai trong `config/schema.py`; thiếu một biến là process **không khởi động được** (fail fast, không fail lúc 2 giờ sáng).

```ini
NODE_ENV=production
LOG_LEVEL=info

OPENAI_API_KEY=
EMBEDDING_PROVIDER=            # nhà cung cấp bạn chọn ('fake' cho tới GĐ 6)
EMBEDDING_API_KEY=
EMBEDDING_MODEL=
EMBEDDING_DIM=1024             # PHẢI khớp cột VECTOR(n); kiểm tra lúc khởi động
RERANK_PROVIDER=
RERANK_API_KEY=
RERANK_MODEL=
RERANK_MIN_SCORE=0.35          # dưới ngưỡng → "không tìm thấy trong tài liệu"

DATABASE_URL=postgres://...
REDIS_URL=redis://...

ZALO_BOT_TOKEN=                # dạng numeric_id:secret
ZALO_MODE=webhook              # webhook | polling
ZALO_WEBHOOK_SECRET=           # đường dẫn bí mật + shared token

BOT_MENTION_NAME=nam_chatbot
GROUP_POLICY=allowlist         # allowlist | open | disabled
DM_POLICY=pairing
RL_USER_PER_MIN=10
RL_THREAD_PER_MIN=30
DAILY_BUDGET_USD=              # BẮT BUỘC — không có mặc định, bạn phải điền
```

`DAILY_BUDGET_USD` cố tình không có giá trị mặc định. Plan đã viết: "một nhóm 50 người nghịch bot có thể đốt sạch ngân sách tháng trong một buổi chiều". Giờ câu đó là một biến bắt buộc, không phải một câu cảnh báo.

---

## 13. Những gì cấu trúc này cố tình **không** làm

Ghi ra để sau này không ai tưởng là quên:

- **Không có microservice.** Một service, ba process. Tách service khi có đội, không phải khi có sơ đồ.
- **Không có framework DI.** `container.py` là một hàm trả về object. Nhìn là biết cái gì nối vào cái gì.
- **Không có ORM.** SQL viết tay + migration đánh số. RAG và memory là truy vấn vector/tsvector — ORM chỉ cản đường.
- **Không xử lý `attachments`.** Trường này có trong contract của plan nhưng không nơi nào trong 3 file định nghĩa hành vi. Giữ trường lại, hành vi Phase 1 là: bỏ qua và trả lời "mình chưa xem được ảnh". Không để trường chết.
- **Chưa có `zalo-personal/`.** Chỉ tạo thư mục khi Bot Platform thật sự không đáp ứng được nhóm. Tạo sớm là mời gọi dùng sớm.
- **Không có Messenger.** Bỏ khỏi phạm vi 07/09/2026 theo quyết định của chủ dự án. Đã dọn sạch chứ không để lại gói rỗng: một placeholder không ai xoá sẽ được người đọc sau hiểu là "sắp làm".
- **Không có Grafana dashboard.** `/api/metrics` đã phơi bày đủ số liệu ở định dạng Prometheus; dựng dashboard là việc cấu hình, không phải việc code, và làm được bất cứ lúc nào.
- **Không đếm token thật khi cắt ngữ cảnh.** `budget.py` ước bằng tỉ lệ ký tự/token đo được (3,6). Đếm thật đòi `agents/` gọi ra ngoài — vi phạm L1 — và thêm một vòng mạng cho mỗi tầng của mỗi câu trả lời.
