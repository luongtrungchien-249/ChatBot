# Master Plan — AI Chatbot cho Zalo & Messenger

**Vai trò:** Senior AI Engineer
**Ngày lập:** 02/09/2026
**Phiên bản:** 3.0 — hợp nhất toàn bộ (Platform + RAG + Memory)

> **Đọc file này như một bản ghi lịch sử, không phải trạng thái hiện tại.**
> Cập nhật 07/09/2026. Ba chỗ trong đây đã bị thực tế bác bỏ, giữ nguyên văn để thấy
> vì sao chúng đổi:
>
> | Chỗ | Bản này viết | Thực tế |
> |---|---|---|
> | Messenger (§2.2, tuần 2, phần V) | Nộp App Review ngày 1 | **Bỏ khỏi phạm vi 07/09/2026** — chỉ tích hợp Zalo. Không còn code, biến cấu hình hay `Platform` nào cho nó |
> | Ngưỡng chống trùng fact (§4.2) | `cosine > 0.9` | **0,70.** Con số 0,9 viết trước khi có phép đo nào; đo bằng `ops/calibrate_dedupe.py` thì hai cách diễn đạt của **cùng một ý** chỉ đạt 0,736 |
> | Lịch 6 tuần (phần III) | RAG tuần 3, Memory tuần 4 | Thứ tự thật: Memory (GĐ 7) xong **trước** RAG (GĐ 6). Trạng thái thật ở `docs/plan-thi-cong.md` §2 |
>
> Trạng thái hiện tại: **`docs/plan-thi-cong.md`**. Kiến trúc: **`ARCHITECTURE.md`**.

---

## PHẦN I — TỔNG QUAN

### 1.1 Mục tiêu

Xây dựng một chatbot AI hoạt động trong nhóm chat Zalo và Messenger, phản hồi khi được mention (`@nam_chatbot`), có khả năng tra cứu tài liệu riêng (RAG) và ghi nhớ ngữ cảnh qua thời gian (Memory).

### 1.2 Bản chất dự án

Đây là **dự án tích hợp LLM vào hệ thống messaging**, không phải dự án nghiên cứu model. Phân bổ công sức thực tế:

| Mảng | Tỷ trọng | Nội dung |
|---|---|---|
| Integration / Platform | ~50% | Webhook, token, adapter, dedup, queue, deploy |
| LLM Application | ~30% | RAG, memory, prompt, context, chống injection |
| Backend / DevOps | ~20% | Rate limit, monitoring, cost, CI |

Phần gọi model chỉ là vài chục dòng code. Giá trị kỹ thuật nằm ở phần còn lại.

### 1.3 Kiến trúc tổng thể

```
Zalo Bot API  ─┐
Meta webhook  ─┼→ Adapter → Normalizer → Core Engine → OpenAI API
Zalo Personal ─┘                            │
                                            ├─ L1 Working Memory  (Redis)
                                            ├─ L2 Episodic        (Postgres)
                                            ├─ L3 Semantic        (pgvector)
                                            └─ L4 Knowledge/RAG   (pgvector)
```

**Nguyên tắc số một:** lõi xử lý là MỘT service. Zalo và Messenger chỉ là adapter mỏng ở rìa. Đừng viết hai bot.

**Contract chung:**

```python
@dataclass(frozen=True, slots=True)
class InboundMessage:
    platform: Platform            # zalo_bot | zalo_personal | messenger | cli | web
    thread_id: str
    sender_id: str
    sender_name: str
    text: str
    is_group: bool
    mentioned_bot: bool
    message_id: str
    timestamp: int
    trace_id: str                 # L8 — mot trace_id xuyen suot moi log
    reply_to: ReplyTo | None = None
    attachments: tuple[Attachment, ...] = ()
```

Adapter lo: verify chữ ký, ack nhanh, đẩy vào queue, gửi trả lời.
Core **không được biết** Zalo hay Messenger là gì.

### 1.4 Stack

| Thành phần | Lựa chọn | Lý do |
|---|---|---|
| Runtime | **Python 3.11 + FastAPI** | Người bảo trì đọc và sửa được — ràng buộc quan trọng nhất của một dự án một người |
| Queue | Redis + ARQ | Nhẹ, cùng chỗ với L1 memory |
| DB | Postgres + pgvector | L2, L3, L4 và log dùng chung một DB |
| Deploy | Docker Compose → VPS Việt Nam | Zalo nhạy cảm với IP lạ |

---

## PHẦN II — QUYẾT ĐỊNH NỀN TẢNG

### 2.1 Ba đường vào Zalo

| | Zalo Bot Platform | Zalo OA | Zalo Personal |
|---|---|---|---|
| Nơi tạo | bot.zaloplatforms.com | oa.zalo.me + developers.zalo.me | Tài khoản Zalo thường |
| Xác thực | Token tĩnh `id:secret` | OAuth + refresh token | Đăng nhập QR |
| Chính thức | Có | Có | **Không** (zca-js) |
| Xác minh doanh nghiệp | Không cần | Cần, vài ngày | Không |
| Chat nhóm | Có, còn đang hoàn thiện | **Không** | Có, đầy đủ |
| Rủi ro khóa tài khoản | Không | Không | **Có** |
| Chi phí | Miễn phí | Quota / Premium | Miễn phí |

**Quyết định: dùng Zalo Bot Platform.**
OA chỉ cần nếu làm chăm sóc khách hàng doanh nghiệp. Personal chỉ khi Bot Platform không đủ và bạn chấp nhận rủi ro mất số.

**Cảnh báo:** tính năng group của Bot API còn ở trạng thái thử nghiệm, trọng tâm hiện tại vẫn là hội thoại 1:1. Thiết kế sao cho nếu group ngừng hoạt động thì bot vẫn dùng được ở DM.

### 2.2 Messenger — **đã bỏ khỏi phạm vi (07/09/2026)**

> Phần dưới giữ nguyên để tra cứu nếu một ngày quay lại. Hiện tại: không làm.


Bot chạy dưới danh nghĩa **Facebook Page**, không dùng được profile cá nhân. Cần Meta Business account, App loại Business, App Review cho `pages_messaging`.

**Đường găng:** App Review mất 1–2 tuần và hay bị từ chối lần đầu. **Nộp ngay ngày đầu tiên.**

---

## PHẦN III — LỘ TRÌNH THỰC THI

### Tổng quan 6 tuần

| Tuần | Trọng tâm | Kết quả bàn giao |
|---|---|---|
| 1 | Core Engine + Zalo Bot | Bot trả lời được trong nhóm Zalo |
| 2 | Messenger + Hardening cơ bản | Bot chạy trên 2 nền tảng, có rate limit |
| 3 | RAG ingestion + retrieval | Bot trả lời dựa trên tài liệu |
| 4 | Memory L2 + L3 | Bot nhớ ngữ cảnh và fact về người dùng |
| 5 | Eval + tuning | Bộ test 50 câu chạy trong CI |
| 6 | Production hardening + monitoring | Sẵn sàng mở cho người dùng thật |

**Ngày 1 bắt buộc làm:** nộp Meta App Review, tạo bot trên Zalo Bot Platform. Hai việc này chờ lâu nhất.

---

### TUẦN 1 — Core Engine + Zalo Bot Platform

#### Phase 0: Core Engine (2–3 ngày)

Viết trước, chạy được qua CLI, chưa động gì tới Zalo/Meta.

**Xử lý mention:**
```
1. is_group == false  → luôn trả lời
2. is_group == true   → chỉ trả lời khi mentioned_bot
3. Strip "@nam_chatbot" khỏi text
4. Còn lại rỗng → trả lời hướng dẫn cách dùng
5. Là reply của tin khác → kéo tin gốc vào ngữ cảnh
```

Phát hiện mention hai lớp: đọc trường mention trong payload nếu có, đồng thời fallback regex `/@nam[_\s]?chatbot/i`. Payload các nền tảng không đồng nhất và hay đổi.

**L1 Working Memory:** 15 tin gần nhất mỗi thread, Redis, TTL 2h, key `ctx:{platform}:{thread_id}`. Trong nhóm prefix tên người gửi: `[Nam]: nội dung`.

**System prompt:** tên bot, đang trong nhóm chat Việt Nam, tiếng Việt tự nhiên, dưới 4–5 câu trừ khi được hỏi chi tiết, **không dùng markdown nặng** (Zalo và Messenger đều không render), không biết thì nói không biết. Về cap token xem `ARCHITECTURE.md` §8.1 — con số 500–800 ở đây đã lỗi thời và sẽ làm câu trả lời biến mất trên model reasoning.

**Fallback:** API lỗi hoặc timeout > 15s → trả câu ngắn thay vì im lặng. Im lặng trong nhóm trông như bot chết và người dùng sẽ spam mention.

#### Phase 1: Zalo Bot Platform adapter (2–3 ngày)

1. Tạo bot tại `bot.zaloplatforms.com` — **tên bắt buộc bắt đầu bằng "Bot"**
2. Token dạng `numeric_id:secret` gửi qua tin nhắn Zalo
3. Dev bằng **polling** (`getUpdates`), production bằng **webhook**. Adapter hỗ trợ cả hai qua config.
4. Dedup `message_id` trong Redis, TTL 10 phút
5. Access control ngay từ đầu: `groupPolicy: allowlist`, `dmPolicy: pairing`
6. `sendMessage` với `chat_id`, tự chunk tin dài

**Milestone tuần 1:** bot trả lời được khi mention trong một nhóm Zalo cụ thể.

---

### TUẦN 2 — Messenger + Hardening cơ bản

#### Phase 2: Messenger adapter (3–5 ngày)

**Webhook verify (GET):** so khớp `hub.verify_token` → echo `hub.challenge`.

**Webhook nhận tin (POST):**
- **Bắt buộc** verify `X-Hub-Signature-256` bằng HMAC-SHA256 với App Secret. Bỏ qua là mở cửa cho spoofing.
- Trả `200` trong **dưới 2 giây**, xử lý async. Timeout → Meta retry → trả lời trùng.
- Dedup `message_id`, TTL 10 phút. Retry của Meta là chuyện thường xuyên.

**Gửi trả lời:**
- `sender_action: typing_on` trước cho mượt
- Giới hạn **2000 ký tự** mỗi tin, phải tự chunk
- Cửa sổ **24 giờ**: trả lời trong luồng thì không sao, chủ động nhắn ngoài cửa sổ thì không được

#### Hardening cơ bản (2 ngày)

**Rate limit (token bucket trên Redis):**

| Tầng | Ngưỡng |
|---|---|
| Per-user | 10 tin/phút |
| Per-thread | 30 tin/phút |
| Global | Theo ngân sách |

**Cost tracking:** log token in/out mỗi request kèm `thread_id` và `sender_id`. Đặt alert chi tiêu ngày.

> Một nhóm 50 người nghịch bot có thể đốt sạch ngân sách tháng trong một buổi chiều. Đây không phải giả thuyết.

**Milestone tuần 2:** bot chạy trên cả hai nền tảng, có rate limit và cost tracking.

---

### TUẦN 3 — RAG

#### 3.1 Ingestion pipeline (2–3 ngày)

```
File (pdf/docx/md/txt) → Extract → Chunk → Embed → Upsert pgvector
```

**Chunking** — biến số ảnh hưởng chất lượng nhiều nhất, quan trọng hơn cả việc chọn embedding model:
- 500–800 token, overlap 100 token
- Cắt theo **ranh giới ngữ nghĩa** (heading, đoạn văn), không cắt cứng theo ký tự
- Metadata mỗi chunk: `doc_id`, `doc_title`, `section`, `page`, `version`

**Contextual retrieval:** trước khi embed, thêm 1–2 câu mô tả chunk nằm ở đâu trong tài liệu. Cải thiện độ chính xác đáng kể với chi phí thấp.

**Embedding:** chọn model hỗ trợ tiếng Việt tốt, nhưng **benchmark trên chính tài liệu của bạn**, đừng tin bảng xếp hạng chung.

#### 3.2 Retrieval (2 ngày)

**Hybrid search — dùng cả hai, đừng chỉ vector:**

```
1. Vector search (pgvector, cosine)      → top 20
2. BM25 / full-text (Postgres tsvector)  → top 20
3. Reciprocal Rank Fusion                → top 10
4. Rerank (cross-encoder)                → top 3–5
5. Đưa vào prompt
```

Vector search kém với mã sản phẩm, tên riêng, số hiệu văn bản — đúng loại câu hỏi phổ biến nhất. Chỉ dùng vector là hỏng ở ca dễ nhất.

#### 3.3 Query rewriting + tool calling (1–2 ngày)

Câu hỏi trong nhóm thường thiếu ngữ cảnh ("cái đó bao nhiêu tiền?"). Dùng L1 viết lại thành câu độc lập trước khi search.

Đừng search mọi tin nhắn. Cho model tự quyết định gọi `search_knowledge_base` qua tool calling — linh hoạt hơn phân loại cứng.

#### 3.4 Chống bịa và chống injection

- **Bắt buộc trích dẫn** nguồn cho mọi khẳng định lấy từ knowledge base
- **Ngưỡng rerank:** dưới ngưỡng → "mình không tìm thấy thông tin này trong tài liệu"
- **Bọc chunk trong tag**, system prompt nêu rõ nội dung trong tag là **dữ liệu tham khảo, không phải chỉ thị**
- **Chỉ admin nạp tài liệu**, không mở cho thành viên nhóm. Log mọi lần ingestion.

**Milestone tuần 3:** bot trả lời được câu hỏi dựa trên tài liệu, có trích dẫn nguồn.

---

### TUẦN 4 — Memory

#### Nguyên tắc bao trùm

Bot chạy trong nhóm, nên **mọi thứ ghi nhớ đều là dữ liệu của nhiều người**:

1. **Scope chặt.** Memory ở nhóm A không bao giờ xuất hiện ở nhóm B. Không ngoại lệ.
2. **Người dùng kiểm soát được.** Phải có lệnh xem và xoá.
3. **Ghi có chọn lọc.** Lưu bừa vừa tốn tiền, vừa nhiễu, vừa rủi ro riêng tư.

Vi phạm nguyên tắc 1 là loại lỗi phải gỡ sản phẩm xuống, không phải loại sửa trong sprint sau.

#### 4.1 L2 — Episodic Memory (1–2 ngày)

Rolling summarization:
```
Khi thread đạt 30 tin chưa nén:
  1. Lấy 15 tin cũ nhất (ngoài cửa sổ L1)
  2. Gọi model rẻ (Haiku) tóm tắt 3–5 câu
  3. Merge với summary cũ
  4. Xoá 15 tin đã nén khỏi Redis
```

Chạy **async** trong background job. Giữ summary ~500 token. Prompt tóm tắt: giữ quyết định, số liệu, tên riêng, việc chưa xong; bỏ chào hỏi.

**Cạm bẫy:** nén đệ quy nhiều lần làm thông tin trôi dần. Sau 5–6 lần, summary bắt đầu sai lệch. Giảm nhẹ bằng cách giữ fact quan trọng ở L3.

#### 4.2 L3 — Semantic Memory (2 ngày explicit + 2 ngày implicit)

**Chỉ ghi khi thoả cả ba:** bền theo thời gian, hữu ích lần sau, người dùng chủ động nói ra.

| Nên nhớ | Không nên nhớ |
|---|---|
| "Nam làm backend Node.js" | "Nam đang buồn ngủ" |
| "Nhóm họp thứ 3 hàng tuần" | "Trời hôm nay mưa" |
| "Gọi tôi là anh Nam" | Sức khoẻ, tài chính, chính trị |
| "Dự án tên Hoshi" | Bất cứ điều gì suy đoán ra |

**Schema:**
```sql
CREATE TABLE memory_fact (
  id           BIGSERIAL PRIMARY KEY,
  platform     TEXT NOT NULL,
  thread_id    TEXT NOT NULL,      -- scope, không bao giờ cross-thread
  subject_id   TEXT NOT NULL,
  content      TEXT NOT NULL,
  embedding    VECTOR(1024),
  source       TEXT,               -- explicit | implicit
  confidence   REAL,
  created_at   TIMESTAMPTZ DEFAULT now(),
  revoked_at   TIMESTAMPTZ         -- soft delete
);
```

`thread_id` có mặt trong **mọi** truy vấn. Đây là hàng rào chống rò rỉ, không phải tối ưu hoá.

**Explicit trước, implicit sau.** Explicit: `@nam_chatbot nhớ giúp: deadline 30/11`. Implicit: model trích xuất fact, chỉ ghi khi `confidence >= 0.8`, bật sau khi đã có công cụ audit.

**Chống trùng:** trước khi insert, tìm fact tương tự cùng subject. Trùng ý → bỏ. Mâu thuẫn → revoke cũ, insert mới.

> ~~cosine > 0.9~~ → **0,70**. Đo bằng `ops/calibrate_dedupe.py` ngày 06/09/2026: cần bắt
> 0,736–0,958, cần bỏ qua 0,276–0,524. Với 0,9 thì ngay cả hai cách nói của cùng một ý
> cũng không bị coi là trùng. Ngưỡng cho lệnh `quên` là **0,30** + top-5, không phải 0,85.
> Xem `docs/plan-thi-cong.md` §9.

**Quyền người dùng — bắt buộc:**
```
@nam_chatbot memory            → liệt kê fact về mình trong nhóm này
@nam_chatbot quên [nội dung]   → revoke fact khớp
@nam_chatbot quên hết          → revoke toàn bộ
```

**Milestone tuần 4:** bot nhớ ngữ cảnh dài, nhớ fact về người dùng, và người dùng xoá được.

---

### TUẦN 5 — Đánh giá và tinh chỉnh

Không có eval thì mọi thay đổi prompt đều là đoán mò.

**Bộ test tối thiểu:** 50 câu hỏi kèm đáp án đúng và chunk nguồn mong đợi. Tự viết tay dựa trên tài liệu thật.

| Chỉ số | Đo cái gì | Mục tiêu |
|---|---|---|
| Recall@5 | Chunk đúng có trong top 5 | > 0.85 |
| Faithfulness | Bám tài liệu (LLM-as-judge) | > 0.9 |
| Answer relevance | Đúng câu hỏi | > 0.85 |
| Latency p95 | Toàn pipeline | < 5s |
| Cost/query | Gồm embedding + rerank | Theo ngân sách |

Chạy lại toàn bộ **mỗi khi đổi prompt, chunking, hoặc model**. Tự động hoá trong CI ngay từ đầu.

---

### TUẦN 6 — Production

**Ghép context vào prompt** (tổng ~4000 token đầu vào):

```
[System prompt]                          ~300
[L4 - Tài liệu liên quan, có trích dẫn]  ~1500
[L3 - Fact về user & thread]             ~200
[L2 - Tóm tắt hội thoại trước]           ~400
[L1 - 15 tin gần nhất]                   ~1200
[Câu hỏi hiện tại]                       ~100
```

Thông tin ổn định trước, tươi sau — hợp cơ chế chú ý của model và tận dụng prompt caching.

**Mỗi tầng phải có hard cap token.** Không có cap thì một tài liệu dài sẽ đẩy hội thoại ra khỏi cửa sổ và bot trả lời lạc đề mà bạn không hiểu tại sao.

**Tối ưu latency:**
- Prompt caching cho system prompt và tài liệu ít đổi
- Cache embedding câu hỏi lặp
- `typing_on` ngay khi nhận tin
- Tóm tắt và trích xuất fact chạy async, không nằm trên đường phản hồi

**Monitoring:**
- Health check endpoint
- Alert: webhook lỗi liên tiếp, token sắp hết hạn, chi phí vượt ngưỡng
- Dashboard: tin/ngày, latency p95, cost/ngày, tỉ lệ lỗi

---

## PHẦN IV — TÙY CHỌN: ZALO PERSONAL

Chỉ làm nếu Bot Platform không đáp ứng được yêu cầu nhóm.

`zca-js` — reverse-engineering web protocol, đăng nhập QR, hỗ trợ nhóm đầy đủ và mention gốc. **Không chính thức**, tài khoản **có thể bị cấm vĩnh viễn**.

Nếu vẫn làm:
- **Số điện thoại phụ**, tuyệt đối không dùng số chính
- IP Việt Nam cố định
- Delay ngẫu nhiên **2–5 giây** trước khi trả lời
- Giới hạn cứng tin/giờ
- Chỉ trả lời khi được mention
- Persist session cookie
- Coi tài khoản là **disposable**, viết sẵn quy trình khôi phục

Adapter chạy như long-lived process, không phải webhook. Core engine dùng chung.

---

## PHẦN V — CHECKLIST GO-LIVE

**Platform**
- [ ] Dedup `message_id` hoạt động trên mọi adapter
- [ ] Verify `X-Hub-Signature-256` cho Messenger
- [ ] Webhook trả 200 dưới 2 giây, xử lý async
- [ ] Chunk tin dài (2000 ký tự Messenger)
- [ ] Allowlist thread đang bật
- [ ] Quy trình khôi phục khi mất token/session

**LLM & RAG**
- [ ] System prompt yêu cầu không dùng markdown
- [ ] Fallback message khi API lỗi
- [ ] Ngưỡng rerank có, bot biết nói "không tìm thấy"
- [ ] Bắt buộc trích dẫn nguồn
- [ ] Chunk tài liệu bọc tag chống injection
- [ ] Chỉ admin nạp được tài liệu

**Memory**
- [ ] `thread_id` trong **mọi** truy vấn memory
- [ ] Fact đã revoke không bao giờ vào prompt
- [ ] Lệnh `memory` và `quên` hoạt động, có test
- [ ] Mỗi tầng context có hard cap token
- [ ] Công cụ audit xem toàn bộ fact của một thread

**Vận hành**
- [ ] Rate limit ba tầng
- [ ] Cost alert theo ngày
- [ ] Bộ eval 50 câu chạy trong CI
- [ ] Secret trong secret manager, không trong repo
- [ ] Monitoring và alert đã cấu hình

---

## PHẦN VI — CÁC QUYẾT ĐỊNH CÒN MỞ

1. **Bot phục vụ nhóm nội bộ hay khách hàng doanh nghiệp?**
   Nội bộ → Zalo Bot Platform, bỏ hẳn OA.
   Doanh nghiệp → cân nhắc thêm OA cho luồng chăm sóc khách hàng.

2. **Group trên Zalo Bot Platform có bắt buộc không?**
   Nếu bắt buộc mà tính năng chưa đủ ổn định → phải cân nhắc Zalo Personal với đầy đủ rủi ro.

3. **Ngân sách API mỗi tháng?**
   Quyết định `max_tokens`, độ dài memory, ngưỡng rate limit global.

4. **Tài liệu nạp vào RAG là gì, dung lượng bao nhiêu?**
   Ảnh hưởng chiến lược chunking và chi phí embedding ban đầu.

---

## PHẦN VII — RỦI RO CHÍNH

| Rủi ro | Xác suất | Tác động | Giảm thiểu |
|---|---|---|---|
| Meta App Review bị từ chối | Cao | Chậm 1–2 tuần | Nộp ngày 1, chuẩn bị screencast kỹ |
| Group Zalo Bot API đổi hành vi | Trung bình | Mất tính năng chính | Đảm bảo DM vẫn dùng được |
| Rò rỉ memory cross-group | Thấp | **Nghiêm trọng** | `thread_id` trong mọi query, có test |
| Chi phí vượt ngân sách | Cao | Trung bình | Rate limit + cost alert từ tuần 2 |
| Prompt injection qua tài liệu | Trung bình | Cao | Bọc tag, chỉ admin nạp, log |
| Khoá số (nếu dùng Personal) | Trung bình | Cao | Số phụ, delay, coi là disposable |
