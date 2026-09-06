Chuyển toàn bộ backend từ TypeScript sang Python, và hoàn thành Giai đoạn 4 (Zalo Bot) cùng Giai đoạn 7 (Memory L2 + L3).

**260 file · +14.143 / −9.236** — 125 file `.py` mới, 94 file `.ts` bị xoá, cùng toàn bộ `package.json`, `tsconfig.json`, `node_modules/` và `.dependency-cruiser.cjs`.

---

## 1. Đổi ngôn ngữ

Lý do là **tự bảo trì được** — code không đọc được là code không sửa được.

| Cũ | Mới |
|---|---|
| Fastify | FastAPI |
| BullMQ | ARQ |
| Zod | pydantic-settings |
| vitest | pytest |
| pino | structlog |
| `pg` / `ioredis` | asyncpg / redis-py |
| tsc | mypy `--strict` |
| ESLint | ruff |
| dependency-cruiser | import-linter + 2 script AST |
| React + Vite + npm | **Jinja2 + JavaScript thuần** |

**Bố cục:** mười tầng nằm thẳng dưới `src/` (`agents/`, `adapters/`, `infra/`, `llm/`, `memory/`, `tools/`, …), đúng chỗ TypeScript từng nằm — không có gói bao bọc ngoài. Đổi lại, tên tầng chiếm không gian tên cấp cao nhất, nên **thêm phụ thuộc mới thì phải kiểm trùng tên**; ghi chú này nằm trong `pyproject.toml`.

**Giao diện web:** trình duyệt không chạy được Python, nên phần chạy trên máy người dùng vẫn là JavaScript — nhưng là JavaScript thuần, không TypeScript, không bundler, không Node. Cả trang chỉ có hai danh sách và một ô nhập; kéo theo một toolchain Node để vẽ bấy nhiêu đó không mua được gì. Đủ tính năng cũ: sidebar, đổi tên, xoá, SSE, hiện các bước ReAct, nút dừng.

---

## 2. Giai đoạn 4 — Zalo Bot adapter

Ba điều **kiểm chứng bằng lệnh gọi thật**, khác cả tài liệu Zalo lẫn plan cũ:

1. **`getUpdates` rỗng trả `{"ok":false,"error_code":408}`** sau khi treo đúng `timeout` giây. Đó là trạng thái bình thường nhất của một con bot. Coi là lỗi thì vòng poll backoff nhầm và bot trễ hàng phút, đồng thời log đầy cảnh báo giả.
2. **Không có tham số `offset`** (khác Telegram). Plan cũ ghi "offset lưu Redis" — không dùng được. Chống trùng dựa vào `message_id`.
3. **Zalo trả HTTP 200 kèm `ok:false` cho cả lỗi thật.** Chỉ đọc status code thì mọi lỗi đều trông như thành công.

**Mention trong nhóm.** Payload nhóm **không có trường mention nào** — Zalo chèn thẳng tên hiển thị của bot vào `text`: `@Bot CP Assistant xin chào`. Tên đó khác cả hai tên bot tự quảng bá, nên bot im lặng trong nhóm cho tới khi thêm `Bot_CP_Assistant` vào `BOT_MENTION_NAME`.

Kèm theo: `infra/allowlist.py` + `cli allow/deny/allowed`. Trước đó `allowed_threads` là `frozenset()` hardcode — cộng `GROUP_POLICY=allowlist` nghĩa là **bot cài vào nhóm nào cũng im lặng và không có cách nào mở mà không sửa code**.

---

## 3. Rate limit ba tầng

`RedisRateLimit.check()` trước đây trả `Allowed()` vô điều kiện. Token bucket user + thread trong **một script Lua**.

- **Lua chứ không `INCR`+`EXPIRE`** — hai lệnh là hai vòng mạng; mất kết nối giữa chúng để lại khoá **không có TTL**, tức người đó bị chặn vĩnh viễn.
- **Cả hai tầng trong một script** — phải peek cả hai rồi mới trừ cả hai. Gọi riêng thì khi tầng thread hết lượt, lượt của người dùng *đã bị trừ* cho một câu bot không trả lời.
- **Token bucket chứ không cửa sổ cố định** — cửa sổ cố định cho qua gấp đôi ở ranh giới.
- **Câu nhắc tối đa 1 lần / 5 phút / thread** — thiếu trần này thì spam 100 tin nhận 100 câu "chậm lại", bot tự thành kẻ spam nhóm.

Redis hỏng thì **cho qua**, không chặn: rate limit là lớp chống lạm dụng chứ không phải lớp bảo mật. Chốt chặn tiền vẫn nguyên vì `within_daily_budget()` tự fail-closed.

---

## 4. Giai đoạn 7 — Memory L2 + L3

**L2 — tóm tắt cuộn.** Job chạy trên `WHERE NOT summarized`, không phụ thuộc TTL Redis. Ghi bản tóm tắt và đánh dấu `summarized` nằm trong **một transaction** — tách ra là mất dữ liệu theo một trong hai hướng, hướng tệ hơn làm 15 tin biến mất vĩnh viễn. Worker `maintenance` tách riêng vì queue `reply` chạy `max_jobs=1`.

**L3 — explicit.** `nhớ giúp:` / `memory` / `quên` / `quên hết` / `đồng ý`. `subject_id` **suy ra từ `sender_id` của tin nhắn**, không bao giờ từ văn bản — đó là chỗ chặn "người X xoá fact của người Y". Yêu cầu xoá đang chờ sống trong Redis TTL 5 phút, lấy-và-xoá bằng `GETDEL`.

**L3 — implicit.** Đã viết, **mặc định TẮT**. Điều kiện tiên quyết đã xong trước: `cli memory <platform> <thread_id>` in ra mọi fact của một thread — không nhìn được bot đã tự ghi gì thì không cho phép nó tự ghi.

**Embedding — quyết định chốt:** OpenAI `text-embedding-3-large` với `dimensions=1024`. D3/D5 để mở, nhưng hai quyết định đó nói về **RAG** (cần benchmark tài liệu thật + một nhà cung cấp rerank). L3 thì khác: fact là câu ngắn, không rerank, và `dimensions=1024` khớp thẳng `VECTOR(1024)`.

---

## 5. Sáu lỗi thật, tìm ra bằng cách chạy chứ không bằng đọc

1. **`assert_embedding_dim()` sai công thức.** Dùng `atttypmod - 4` (quy ước của `varchar`); pgvector thì `atttypmod` *chính là* số chiều. Chốt chặn này chưa bao giờ chạy vì `EMBEDDING_PROVIDER=fake` luôn thoát sớm — lần đầu bật provider thật là nó chặn khởi động và báo một lỗi migration không hề tồn tại.

2. **Prompt caching: tài liệu nói sai ở 4 chỗ.** Ghi `cache_read_tokens = 0`; `usage_log` cho thấy **20/32 lượt có cache, 1408–1792 token**. `1408 = 11 × 128` — đúng bước chia block của OpenAI, tức phần được cache **chính là system prompt**. Luật "system prompt là hằng số" giờ có hai lý do chứ không một: tính tái lập, *và* tiền.

3. **Cả hai ngưỡng cosine trong tài liệu đều sai.** Đo bằng `ops/calibrate_dedupe.py`: chống trùng `0,9 → 0,70` (hai cách nói cùng một ý chỉ đạt 0,736); lệnh `quên` `0,85 → 0,30` (cách người dùng nói chỉ khớp 0,354–0,589, nên với 0,85 lệnh `quên` **không bao giờ tìm thấy gì** — gõ xong tưởng đã xoá).

4. **Bot nói dối.** `nhớ giúp: ...` không phải lệnh nên rơi xuống model, model đáp "Đã ghi nhớ", `memory` ngay sau đó rỗng. Thiếu hẳn đường ghi fact tường minh.

5. **`quên <nội dung>` xoá nhiều hơn ý người dùng.** Ngưỡng rộng cố ý, nhưng xác nhận lại là tất-cả-hoặc-không. Thêm chọn theo số (`đồng ý 1`).

6. **`llm/embedder.py` vi phạm chính luật L6** mà dự án cưỡng chế: không timeout, không retry, không log, không đo cost. L3 gọi embedding ở **mỗi tin nhắn**, nên tiền đó **không nằm trong** chốt chặn `DAILY_BUDGET_USD`. Đã sửa cả bốn; `usage_log` giờ có route `embed`.

Ngoài ra: `CHARS_PER_TOKEN` 3,4 → **3,6** và `SYSTEM_PROMPT` 1.470 → **1.539 token**, đo lại bằng `ops/calibrate_tokens.py` — script này từng được nhắc trong 4 chỗ nhưng **chưa bao giờ tồn tại** ở bản Python.

---

## 6. Cưỡng chế kiến trúc

8 luật, ba công cụ, vì một công cụ không đủ. `import-linter` chỉ so khớp *import module*: nó không thấy `os.environ` (truy cập thuộc tính) và không đọc được chuỗi SQL — hai lỗ đó do `ops/guard_env.py` và `ops/guard_sql.py` bịt bằng AST.

Cả 8 luật đều được **chứng minh** bằng `ops/canary_import_rules.py`: script tạo vi phạm cố ý cho từng luật và bắt buộc luật phải đỏ. Một luật viết sai vẫn chạy xanh — nó chỉ đơn giản không bắt được gì.

**Luật mới bắt được một vi phạm thật:** hợp đồng *"agents không đọc config"* đỏ ngay lần chạy đầu — `agents/policy/access.py` import `GroupPolicy`/`DmPolicy` từ `config.schema`. Cách sửa **không phải** khoét ngoại lệ: hai kiểu đó là từ vựng của miền nghiệp vụ nên chuyển sang `agents/policy/access.py`, và `config` import ngược lên.

---

## 7. Kiểm chứng

| | |
|---|---|
| Test | **290** (TypeScript có 104) |
| mypy `--strict` | sạch, 130 file |
| ruff | sạch |
| `lint-imports` | 5 hợp đồng KEPT |
| `guard_env` + `guard_sql` | xanh |
| **canary** | **8/8 luật bắt được vi phạm cố ý** |

Bốn tầng test đều có file. `tests/security/test_cross_thread_leak.py` từ **7 test `skip`** (bỏ trống từ đầu dự án) thành **7 test chạy thật** trên Postgres + embedding thật — đi qua bề mặt công khai của `MemoryPort`, và test cuối kiểm trên **chuỗi prompt đã build** chứ không trên kết quả repository, vì rò rỉ có thể xảy ra ở builder trong khi repository vẫn sạch.

`tests/contract` chạy trên **payload Zalo thật đã ghi lại**, không phải payload tự nghĩ ra: test trên payload tự nghĩ chỉ chứng minh code khớp với *hiểu biết của người viết* — và hiểu biết đó đã sai một lần, về trường mention.

Chạy thật, không chỉ test: `migrate` (lần hai không làm gì) · REPL · giao diện web hỏi–đáp qua SSE · bot trả lời trong nhóm Zalo thật · L2 nén 32 tin → 15 · L3 nhớ/quên/xác nhận đầy đủ.

---

## 8. Cố ý chưa làm

| Việc | Chặn ở |
|---|---|
| `web_search` | `TAVILY_API_KEY` trống → công cụ không được khai trong `specs()`. Cho model thấy một công cụ rồi để nó gọi thất bại là cách nhanh nhất để nó bịa kết quả |
| Webhook Zalo | `ZALO_WEBHOOK_SECRET` là placeholder và Zalo không công bố sơ đồ ký chữ ký. Viết phần xác minh bằng cách đoán là loại lỗi hỏng im lặng. `ingest()` đã tách sẵn |
| Giai đoạn 5 — Messenger | Credential Meta còn placeholder + Business Verification |
| Giai đoạn 6 — RAG | Cần chốt nhà cung cấp **rerank** (OpenAI không có) + tài liệu thật |
| Giai đoạn 8 — Eval | `qa.jsonl` có 1 dòng ví dụ; cần 50 câu **viết tay** từ tài liệu thật |
| L3 implicit | Đã viết nhưng `MEMORY_IMPLICIT_ENABLED=false` |

**Một số đo chưa đạt mục tiêu:** độ trễ p95 = **8,5s**, mục tiêu < 5s. Mẫu còn nhỏ (32 lượt, phần lớn là traffic test) nên chưa đủ để kết luận — đo thêm rẻ hơn tối ưu mù.

---

## Ghi chú cho người review

- Hai nhánh rẽ từ `d1a04e9`; `main` có thêm `04ba46f "CI test"` mà nhánh này không có. Nội dung đó là TypeScript nên gộp xong sẽ bị xoá theo — **nên xem diff trước khi gộp**.
- `.env.example` có ba biến mới: `MEMORY_IMPLICIT_ENABLED`, và `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL` đổi giá trị.
- Migration không đổi; schema cũ dùng nguyên.
- Chạy `uv sync` rồi `uv run pytest`. Ba tầng test dưới cần Docker (`ops/docker-compose.yml`); chúng tự bỏ qua khi thiếu, nhưng **không bỏ qua im lặng** — dòng skip luôn nêu lý do.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
