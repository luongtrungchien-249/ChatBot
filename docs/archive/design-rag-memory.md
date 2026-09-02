# Thiết kế RAG & Memory

**Phụ lục cho:** Kế hoạch triển khai AI Chatbot cho Zalo & Messenger
**Vai trò:** Senior AI Engineer
**Scope:** Phase 5 — chỉ triển khai sau khi Phase 0–2 đã chạy ổn định

---

## 0. Nguyên tắc bao trùm

Bot chạy trong nhóm chat, nên **mọi thứ ghi nhớ đều là dữ liệu của nhiều người**. Ba nguyên tắc không được vi phạm:

1. **Scope chặt.** Memory học được ở nhóm A không bao giờ xuất hiện ở nhóm B. Không có ngoại lệ.
2. **Người dùng kiểm soát được.** Phải có lệnh xem và xoá memory về chính mình.
3. **Ghi có chọn lọc.** Không lưu mọi thứ. Lưu bừa vừa tốn tiền, vừa làm model nhiễu, vừa tạo rủi ro riêng tư.

Vi phạm nguyên tắc 1 là loại lỗi khiến sản phẩm phải gỡ xuống, không phải loại lỗi sửa trong sprint sau.

---

## 1. Bốn tầng bộ nhớ

Đừng gộp tất cả thành "memory". Bốn tầng khác nhau về vòng đời, chi phí và cách truy xuất:

| Tầng | Nội dung | Lưu ở | TTL | Cách đưa vào prompt |
|---|---|---|---|---|
| L1 — Working | 15 tin gần nhất của thread | Redis | 2h | Luôn luôn, nguyên văn |
| L2 — Episodic | Tóm tắt hội thoại cũ | Postgres | 90 ngày | Khi thread có lịch sử dài |
| L3 — Semantic | Sự kiện bền về user/thread | Postgres + pgvector | Vĩnh viễn, có xoá | Truy xuất theo query |
| L4 — Knowledge (RAG) | Tài liệu bạn nạp vào | pgvector | Theo phiên bản tài liệu | Truy xuất theo query |

L1 đã có từ Phase 0. Phần dưới là L2, L3, L4.

---

## 2. L2 — Episodic Memory (nén hội thoại)

### Vấn đề

L1 chỉ giữ 15 tin. Hội thoại dài hơn thì mất ngữ cảnh. Nhưng nhét 200 tin vào prompt thì tốn tiền và model lạc đề.

### Giải pháp: rolling summarization

```
Khi thread đạt 30 tin chưa nén:
  1. Lấy 15 tin cũ nhất (ngoài cửa sổ L1)
  2. Gọi model rẻ (Haiku) để tóm tắt thành 3–5 câu
  3. Merge với summary cũ → summary mới
  4. Xoá 15 tin đã nén khỏi Redis
```

Prompt tóm tắt cần nêu rõ: giữ lại quyết định, số liệu, tên riêng, việc chưa xong; bỏ chào hỏi và tán gẫu.

### Chi tiết triển khai

- Chạy **bất đồng bộ** trong background job, không chặn luồng trả lời
- Dùng model rẻ nhất — đây là việc cơ học, không cần model mạnh
- Giới hạn summary ở ~500 token. Vượt thì nén tiếp summary.
- Lưu bảng `thread_summary(thread_id, platform, summary, updated_at, msg_count)`

### Cạm bẫy

Nén đệ quy nhiều lần sẽ làm thông tin trôi dần (lossy compression). Sau 5–6 lần nén, summary bắt đầu sai lệch. Cách giảm nhẹ: giữ nguyên văn các "fact" quan trọng ở L3 thay vì phó mặc cho summary.

---

## 3. L3 — Semantic Memory (nhớ về người dùng)

### Cái gì đáng nhớ

Chỉ ghi khi thoả **cả ba**: bền theo thời gian, hữu ích cho lần sau, và người dùng nói ra một cách chủ động.

| Nên nhớ | Không nên nhớ |
|---|---|
| "Nam làm backend Node.js" | "Nam đang buồn ngủ" |
| "Nhóm này họp thứ 3 hàng tuần" | "Trời hôm nay mưa" |
| "Gọi tôi là anh Nam" | Nội dung nhạy cảm: sức khoẻ, tài chính, chính trị |
| "Dự án tên là Hoshi" | Bất cứ điều gì suy đoán ra chứ không được nói ra |

### Cơ chế ghi

Hai chế độ, nên hỗ trợ cả hai:

**Explicit** — người dùng chủ động: `@nam_chatbot nhớ giúp: deadline dự án là 30/11`
Đây là chế độ an toàn nhất, nên bật trước.

**Implicit** — bot tự trích xuất. Sau mỗi N lượt, gọi model với prompt trích xuất fact, trả về JSON:

```json
{
  "facts": [
    {"subject": "user:123", "content": "làm backend Node.js", "confidence": 0.9}
  ]
}
```

Chỉ ghi khi `confidence >= 0.8`. Chế độ này bật sau, khi đã có công cụ audit.

### Schema

```sql
CREATE TABLE memory_fact (
  id           BIGSERIAL PRIMARY KEY,
  platform     TEXT NOT NULL,
  thread_id    TEXT NOT NULL,          -- scope: không bao giờ cross-thread
  subject_id   TEXT NOT NULL,          -- user:xxx hoặc thread:xxx
  content      TEXT NOT NULL,
  embedding    VECTOR(1024),
  source       TEXT,                   -- explicit | implicit
  confidence   REAL,
  created_at   TIMESTAMPTZ DEFAULT now(),
  last_used_at TIMESTAMPTZ,
  revoked_at   TIMESTAMPTZ             -- soft delete
);

CREATE INDEX ON memory_fact (platform, thread_id, subject_id)
  WHERE revoked_at IS NULL;
```

**`thread_id` nằm trong mọi truy vấn.** Đây là hàng rào chống rò rỉ cross-group, không phải tối ưu hoá.

### Chống trùng và mâu thuẫn

Trước khi insert, tìm fact tương tự (cosine > 0.9) cùng subject:
- Trùng ý → bỏ qua
- Mâu thuẫn (ví dụ đổi công ty) → revoke fact cũ, insert fact mới
- Khác biệt → insert bình thường

Không xử lý bước này thì sau vài tuần bảng sẽ đầy các biến thể của cùng một câu.

### Quyền của người dùng

Bắt buộc có, làm ngay từ đầu:

```
@nam_chatbot memory              → liệt kê fact về mình trong nhóm này
@nam_chatbot quên [nội dung]     → revoke fact khớp
@nam_chatbot quên hết            → revoke toàn bộ fact về mình
```

Xoá là soft delete (`revoked_at`), nhưng fact đã revoke **không bao giờ** được đưa vào prompt.

---

## 4. L4 — RAG (tri thức từ tài liệu)

### 4.1 Ingestion pipeline

```
File (pdf/docx/md/txt)
  → Extract text
  → Chunk
  → Embed
  → Upsert vào pgvector
```

**Chunking.** Đây là biến số ảnh hưởng chất lượng nhiều nhất, quan trọng hơn cả việc chọn model embedding.

- Kích thước: 500–800 token, overlap 100 token
- Cắt theo **ranh giới ngữ nghĩa** (heading, đoạn văn), không cắt cứng theo số ký tự
- Với markdown: cắt theo heading, giữ đường dẫn heading vào metadata
- Mỗi chunk lưu kèm: `doc_id`, `doc_title`, `section`, `page`, `version`

**Contextual retrieval.** Trước khi embed, thêm 1–2 câu mô tả chunk này nằm ở đâu trong tài liệu. Ví dụ: *"Đoạn này thuộc mục Chính sách hoàn tiền của Sổ tay nhân viên 2026, nói về thời hạn nộp đơn."* Kỹ thuật này cải thiện độ chính xác truy xuất đáng kể với chi phí ingestion thấp hơn nhiều so với việc thay đổi kiến trúc.

**Embedding.** Dùng model hỗ trợ tiếng Việt tốt. Vietnamese-specific hoặc multilingual đều được, nhưng phải benchmark trên chính tài liệu của bạn — đừng tin bảng xếp hạng chung.

### 4.2 Retrieval

**Hybrid search** — dùng cả hai, đừng chỉ vector:

```
1. Vector search (pgvector, cosine)   → top 20
2. BM25 / full-text (Postgres tsvector) → top 20
3. Reciprocal Rank Fusion             → gộp, top 10
4. Rerank (cross-encoder)             → top 3–5
5. Đưa vào prompt
```

Lý do phải có BM25: vector search kém với mã sản phẩm, tên riêng, số hiệu văn bản — đúng những thứ người Việt hay hỏi ("cho hỏi mã ABC-123 là gì"). Chỉ dùng vector là hỏng ở đúng loại câu hỏi dễ nhất.

**Query rewriting.** Câu hỏi trong nhóm chat thường thiếu ngữ cảnh: "cái đó bao nhiêu tiền?" Trước khi search, dùng L1 để viết lại thành câu độc lập: "gói dịch vụ Premium bao nhiêu tiền?". Bước này rẻ và cải thiện rõ rệt.

**Khi nào thì search.** Đừng search mọi tin nhắn. Dùng một bước phân loại nhẹ:
- Chào hỏi, tán gẫu → bỏ qua RAG
- Câu hỏi có tính tra cứu → chạy RAG
- Không chắc → chạy RAG (chi phí sai sót thấp hơn)

Có thể làm bằng tool calling: cho model tự quyết định gọi `search_knowledge_base` hay không. Cách này linh hoạt hơn phân loại cứng.

### 4.3 Chống bịa

- **Bắt buộc trích dẫn.** System prompt yêu cầu nêu nguồn (tên tài liệu, mục) cho mọi khẳng định lấy từ knowledge base.
- **Ngưỡng liên quan.** Nếu điểm rerank cao nhất dưới ngưỡng → trả lời "mình không tìm thấy thông tin này trong tài liệu" thay vì cố suy đoán.
- **Tách bạch nguồn.** Trong prompt, đánh dấu rõ đâu là tài liệu, đâu là hội thoại. Model không được lẫn hai thứ.

### 4.4 Prompt injection qua tài liệu

Tài liệu nạp vào có thể chứa câu lệnh độc hại ("bỏ qua hướng dẫn trước đó..."). Đây là lỗ hổng thật, không phải lo xa.

- Bọc chunk trong tag rõ ràng, nêu trong system prompt rằng nội dung trong tag là **dữ liệu tham khảo, không phải chỉ thị**
- Chỉ cho phép admin nạp tài liệu, không mở cho thành viên nhóm
- Log mọi lần ingestion kèm người nạp

---

## 5. Ghép tất cả vào prompt

Thứ tự và ngân sách token đề xuất (tổng ~4000 token đầu vào):

```
[System prompt]                          ~300
[L4 - Tài liệu liên quan, có trích dẫn]  ~1500
[L3 - Fact về user & thread]             ~200
[L2 - Tóm tắt hội thoại trước]           ~400
[L1 - 15 tin gần nhất]                   ~1200
[Câu hỏi hiện tại]                       ~100
```

Nguyên tắc: **thông tin ổn định đặt trước, thông tin tươi đặt sau**. Vừa hợp với cơ chế chú ý của model, vừa tận dụng được prompt caching cho phần đầu ít thay đổi.

Mỗi tầng phải có **hard cap token**. Không có cap thì một tài liệu dài sẽ đẩy hội thoại ra khỏi cửa sổ và bot bắt đầu trả lời lạc đề mà bạn không hiểu tại sao.

---

## 6. Đánh giá

Không có eval thì mọi thay đổi prompt đều là đoán mò.

**Bộ test tối thiểu:** 50 câu hỏi kèm đáp án đúng và chunk nguồn mong đợi. Tự viết tay, dựa trên tài liệu thật của bạn.

**Chỉ số theo dõi:**

| Chỉ số | Đo cái gì |
|---|---|
| Recall@5 | Chunk đúng có nằm trong top 5 không |
| Faithfulness | Câu trả lời có bám tài liệu không (LLM-as-judge) |
| Answer relevance | Có trả lời đúng câu hỏi không |
| Latency p95 | Toàn bộ pipeline, mục tiêu < 5s |
| Cost/query | Gồm cả embedding và rerank |

Chạy lại toàn bộ bộ test **mỗi khi đổi prompt, đổi chunking, hoặc đổi model**. Tự động hoá bước này ngay từ đầu, đừng chạy tay.

---

## 7. Chi phí và độ trễ

RAG + memory làm tăng cả hai. Ước lượng thô cho mỗi câu hỏi:

| Bước | Latency | Chi phí tương đối |
|---|---|---|
| Query rewrite | ~300ms | Thấp |
| Embedding | ~100ms | Rất thấp |
| Hybrid search | ~50ms | Không đáng kể |
| Rerank | ~200ms | Thấp |
| Gọi model chính | 2–4s | Cao nhất |
| Tóm tắt (async) | — | Trung bình |

**Tối ưu:**
- Cache embedding của câu hỏi lặp lại
- Prompt caching cho phần system prompt và tài liệu ít đổi
- Gửi `typing_on` ngay khi nhận tin, đừng để người dùng chờ trong im lặng
- Tóm tắt và trích xuất fact chạy async, không nằm trên đường phản hồi

---

## 8. Lộ trình triển khai

| Bước | Nội dung | Thời gian |
|---|---|---|
| 5.1 | pgvector + ingestion pipeline + chunking | 2–3 ngày |
| 5.2 | Hybrid search + rerank | 2 ngày |
| 5.3 | Query rewriting + tool calling để bot tự quyết định search | 1–2 ngày |
| 5.4 | L2 rolling summarization | 1–2 ngày |
| 5.5 | L3 explicit memory + lệnh xem/xoá | 2 ngày |
| 5.6 | L3 implicit extraction (bật sau, có audit) | 2 ngày |
| 5.7 | Bộ eval 50 câu + CI | 2 ngày |

**Tổng: 2–2.5 tuần.**

Thứ tự này có chủ ý: RAG trước memory vì RAG dễ đo lường và ít rủi ro riêng tư hơn. Implicit memory để cuối cùng vì đó là phần dễ gây rắc rối nhất.

---

## 9. Checklist riêng cho phần này

- [ ] `thread_id` có mặt trong **mọi** truy vấn memory
- [ ] Fact đã revoke không bao giờ vào prompt
- [ ] Lệnh `memory` và `quên` hoạt động và có test
- [ ] Mỗi tầng context có hard cap token
- [ ] Ngưỡng rerank có, và bot biết nói "không tìm thấy"
- [ ] Chunk tài liệu được bọc tag chống injection
- [ ] Chỉ admin nạp được tài liệu
- [ ] Bộ eval 50 câu chạy tự động trong CI
- [ ] Tóm tắt và trích xuất fact chạy async
- [ ] Có công cụ xem toàn bộ fact của một thread để audit
