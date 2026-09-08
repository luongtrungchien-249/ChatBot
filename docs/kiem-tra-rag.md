# Kiểm tra hệ thống RAG: Indexing — Retrieval — Generation

*08/09/2026. Mọi con số trong tài liệu này đo trên `lakehouse/datalake/The_Open_Source_Cookbook_v0.4.pdf`
và trên chính mã nguồn trong repo, không lấy từ tài liệu ngoài.*

Ký hiệu: **✅ có** · **⚠️ có một nửa** · **❌ chưa có** · **➖ không áp dụng**

---

## Bảng tổng hợp

| # | Bước | Trạng thái | Ở đâu |
|---|---|---|---|
| 1 | Đọc dữ liệu | ✅ | `knowledge/ingest/extract.py` |
| 2 | Parse / làm sạch | **⚠️** | một phần, xem §2 |
| 3 | Chunking | ✅ | `knowledge/ingest/chunk.py` |
| 4 | Metadata | **⚠️** | thiếu 4/6 mục, xem §4 |
| 5 | Embedding | ✅ | `llm/embedder.py` |
| 6 | Lưu database | ✅ | Postgres + pgvector |
| 7 | Xây dựng index | ✅ | HNSW, migration 0004 |
| 8 | Kiểm tra chất lượng | **❌** | khung có, nội dung rỗng |
| — | Retrieval | ✅ | hybrid + RRF + rerank |
| — | Generation | ⚠️ | thiếu trích dẫn trang |

**Kết luận ngắn: phần khó đã xong, phần thiếu là phần buồn tẻ.** Hybrid search, RRF,
rerank, ngưỡng, chế độ suy giảm — những thứ dễ làm sai đều đã đúng. Cái thiếu là làm
sạch dữ liệu vào, metadata, và kiểm chứng — ba việc không thú vị nhưng quyết định chất
lượng nhiều hơn cả.

---

## INDEXING

### 1. Đọc dữ liệu — ✅

`extract_text(path)` nhận `.txt`, `.md`, `.pdf`, `.docx`. Đuôi khác thì **ném lỗi** chứ
không đọc bừa — đúng: nạp một mớ rác vào CSDL vector còn tệ hơn báo lỗi.

`.docx` đổi `Heading 1` thành `# ` để bước chunk nhận ra bằng **đúng một luật**, không
phải hai. Đo trên PDF: 88 trang, 200.871 ký tự, **0 trang rỗng** — không phải bản scan,
không cần OCR.

### 2. Parse / làm sạch — ⚠️ thiếu phần lớn

Đo từng mục bạn liệt kê, trên tệp thật:

| Vấn đề | Có trong tệp? | Đã xử lý? |
|---|---|---|
| Ký tự lỗi | **86** phân số thành chữ cái | ✅ `profiles.py` (08/09) |
| **Số trang lẫn vào text** | **88/88 trang** | ❌ **chưa** |
| Header / footer lặp lại | 0 (tệp này không có) | ❌ chưa có cơ chế |
| Nhiều khoảng trắng | 2 chỗ | ➖ không đáng làm |
| Thẻ HTML | 0 | ➖ không hỗ trợ `.html` |
| **PDF xuống dòng giữa câu** | **1.209 chỗ** | ❌ **chưa** |
| Văn bản dọc (mỗi dòng 1 chữ cái) | 1 trang (mục lục) | ❌ chưa |

Hai dòng in đậm là hai vấn đề thật, và cả hai đều **đo được**:

**a) Số trang lẫn vào nội dung.** `_from_pdf` nối các trang bằng `\n\n`, và mỗi trang
bắt đầu bằng chính số trang:

```
'22\n1 cp coarsely chopped celery\n5 or 6 carrots, sliced\n...'
```

Hệ quả kép. Thứ nhất, con số lạc vào chunk và vào cả `tsv` — câu hỏi chứa số có thể
khớp nhầm. Thứ hai, và đáng tiếc hơn: **số trang đang nằm sẵn ngay đó, mà cột `page`
thì luôn NULL.** Thông tin cần thiết có sẵn nhưng bị vứt đi.

**b) Xuống dòng giữa câu.** 1.209 chỗ kiểu:

```
'cumentation License" at the end\nof this document. If for w'
```

Đây là ngắt dòng trình bày của PDF, không phải ngắt câu. Nó làm hai việc hại: chunker
coi `\n` là ranh giới ưu tiên cao hơn câu nên **cắt sai chỗ**, và văn bản trích dẫn ra
màn hình bị gãy giữa câu.

### 3. Chunking — ✅

`TARGET_TOKENS = 700`, `OVERLAP_TOKENS = 100`. Thứ tự ưu tiên: tiêu đề markdown → mốc
cấu trúc của hồ sơ tài liệu → recursive character splitting (`shared/chunk_text.py`, đã
có sẵn: đoạn văn → dòng → câu → từ → cắt cứng).

Overlap chỉ nối **giữa các mảnh cùng một mục** — kéo đuôi mục trước sang mục sau sẽ trộn
hai chủ đề và cho ra chunk khớp cả hai câu hỏi mà trả lời đúng không câu nào.

Kết quả sau thay đổi 08/09: 0% chunk lấn sang mục khác, 81% chunk có `section`.

### 4. Metadata — ⚠️ thiếu 4/6

| Mục tiêu bạn nêu | Trạng thái | Ghi chú |
|---|---|---|
| Biết câu lấy từ file nào | ✅ | `doc_id` → `kb_document.title` |
| **Trích dẫn đúng trang** | ❌ | cột `page` **luôn NULL** |
| **Lọc theo tài liệu** | ❌ | `search.py` không có `WHERE` nào |
| **Lọc theo người dùng** | ❌ | không có cột phạm vi |
| Cập nhật / xoá dữ liệu | ⚠️ | có `version`, nhưng **search không lọc version** |
| **Kiểm soát quyền truy cập** | ❌ | xem cảnh báo dưới |

**⚠️ Điểm nghiêm trọng nhất của cả bản kiểm tra: tài liệu không có phạm vi.**

`kb_document` và `kb_chunk` không có cột nào giới hạn phạm vi, `search.py` không nhận
`ThreadScope`, và `run_knowledge_search(payload, _trace_id)` thậm chí **không có tham số
phạm vi**. Nghĩa là **mọi nhóm trong allowlist đọc được toàn bộ mọi tài liệu**.

Điều này lệch hẳn với chuẩn mà chính dự án đặt ra ở chỗ khác: `ThreadScope` là tham số
**bắt buộc, đứng đầu** trên mọi truy vấn `memory_fact`, dựng riêng làm hàng rào chống rò
giữa các nhóm. Ký ức thì có hàng rào, tài liệu thì không.

Hiện chưa gây hại vì `kb_chunk` đang rỗng và mới có một nhóm. Nó thành lỗ hổng thật vào
đúng ngày có nhóm thứ hai và một tài liệu không dành cho họ.

**⚠️ Lỗi thứ hai: không lọc phiên bản.** `pipeline.py` cố ý bất biến theo phiên bản —
nạp lại tạo `version + 1` và **giữ bản cũ** — nhưng không chỗ nào trong mã nguồn xoá hay
đánh dấu bản cũ, và truy vấn không lọc. Ngay lần nạp lại đầu tiên, kết quả sẽ **trộn
chunk v1 với v2**.

### 5. Embedding — ✅

`text-embedding-3-large`, 1024 chiều, nạp theo lô 64 (`_EMBED_BATCH`). Số chiều nằm
trong **tên file migration** (`0004_knowledge_1024.sql`) với ghi chú: đổi chiều = làm
migration mới, không sửa file cũ. Đúng — đổi chiều tại chỗ là làm hỏng toàn bộ vector cũ
một cách im lặng.

Vector câu hỏi được cache `emb:{sha256}` TTL 24h, dùng chung giữa đường tìm tài liệu và
L3 ký ức.

`embed_input` ≠ `content`: `content` giữ **nguyên văn** để trích dẫn, `embed_input` là
`[Tên tài liệu > Mục]\n<thân>` — contextual retrieval làm bằng metadata có sẵn, không
tốn thêm một lần gọi model cho từng chunk và **không thể bịa**.

### 6. Lưu database — ✅

Postgres 16.15 + pgvector 0.8.6. Cả tài liệu nạp trong **một transaction**, với lý do
ghi thẳng trong code: *hỏng giữa chừng mà vẫn để lại nửa số chunk nghĩa là bot trả lời
dựa trên nửa tài liệu mà không ai biết*.

Bỏ qua nếu checksum không đổi — so checksum của **văn bản đã trích**, không phải của
tệp, nên một PDF sửa metadata không bị nạp lại vô ích.

### 7. Xây dựng index — ✅ (và các loại còn lại chưa cần)

```sql
CREATE INDEX ON kb_chunk USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON kb_chunk USING gin (tsv);
```

| Loại index bạn nêu | Trong hệ thống | Có nên dùng? |
|---|---|---|
| **Flat** (so hết) | không khai, nhưng Postgres tự quét tuần tự khi có lợi | Ở quy mô hiện tại **đây mới là thứ đúng** |
| **HNSW** | ✅ đang dùng | Giữ, cho tương lai |
| **IVF** (IVFFlat) | ❌ | pgvector có, nhưng recall kém hơn HNSW ở cùng tốc độ |
| **IVF-PQ** | ❌ | pgvector không hỗ trợ PQ |
| **DiskANN** | ❌ | cần `pgvectorscale`; chỉ đáng khi index không vừa RAM |

Nhắc lại kết luận đã đo ở `nghien-cuu-ingest.md` §5.3: với 129 chunk, HNSW **không nhanh
hơn** quét tuần tự nhưng vẫn **gần đúng** — trả bằng recall mà không nhận lại latency.
Index chỉ có lãi từ ~10.000 dòng. Giữ nó vì vô hại và để sẵn, nhưng **đừng vặn tham số**
trước mốc đó.

### 8. Kiểm tra chất lượng index — ❌ khung có, nội dung rỗng

Có `evals/runner.py` + ba chỉ số (`recall`, `faithfulness`, `latency`) với ngưỡng ghi
sẵn: Recall@5 > 0,85 · Faithfulness > 0,9 · Latency p95 < 5s.

**Nhưng bộ câu hỏi rỗng:** `evals/dataset/qa.jsonl` có **đúng 1 dòng**, và nó là dòng ví
dụ mẫu — `"VI DU - thay bang cau hoi that"`, `expected_chunk_ids: []`. `recall.py` còn
ghi `TODO(giai-doan-8)`: cần `expected_chunk_ids` thật, mà cái đó cần tài liệu đã nạp.

Sáu câu hỏi kiểm tra bạn liệt kê — **không có câu nào được trả lời tự động**:

| Câu hỏi | Có công cụ trả lời? |
|---|---|
| Có đọc đủ tài liệu không? | ⚠️ một phần — `_bao_cao_suc_khoe` đếm dấu hiệu hỏng |
| Chunk có bị mất nội dung không? | ❌ |
| Metadata có đúng không? | ❌ |
| Embedding có tạo thành công không? | ⚠️ gián tiếp — transaction all-or-nothing |
| Có chunk bị trùng không? | ❌ |
| Tìm kiếm có trả về đoạn liên quan không? | ❌ eval rỗng |

---

## RETRIEVAL — ✅ phần lõi đã đúng

```
vector (top 20)  ─┐
                  ├─ RRF k=60 ─ top 10 ─ rerank ─ top 3–5 + ngưỡng 0,55
lexical (top 20) ─┘
```

Những chỗ dễ làm sai mà ở đây đã làm đúng:

- **Hai đường chạy song song** (`asyncio.gather`), không cộng dồn độ trễ.
- **`return_exceptions=True`** — một đường chết không làm hỏng cả lần tìm.
- **RRF chỉ dùng thứ hạng**, nên không phải chuẩn hoá điểm cosine với `ts_rank` — hai
  thang đo khác đơn vị, cộng chúng lại là cộng hai thứ không cùng loại.
- **Rerank hỏng → giữ thứ tự RRF, bỏ qua ngưỡng, ghi log to.** Trả về rỗng ở đây sẽ là
  **nói dối**: rỗng nghĩa là "không có trong tài liệu", còn đây là sự cố hạ tầng.
- **Rỗng là hợp đồng, không phải lỗi** — cho phép bot nói thẳng "tài liệu không đề cập"
  thay vì lấy kiến thức chung thay thế.
- **Câu hỏi cũng đi qua `vn_tsv`** để bỏ dấu y hệt lúc lập chỉ mục — một bên bỏ dấu một
  bên không thì không bao giờ khớp.

Thiếu: lọc metadata (§4), và `hnsw.iterative_scan` — nhưng cái sau **chỉ cần khi** thêm
bộ lọc, không sớm hơn.

---

## GENERATION — ⚠️ gần đủ

Chunk vào prompt dưới dạng:

```xml
<tai_lieu id="42" nguon="Tên tài liệu" muc="Tên mục">
...nội dung đã sanitize...
</tai_lieu>
```

- **`sanitize()`** chạy trên nội dung tài liệu — input rails cho văn bản người lạ soạn.
- **`trim_to_budget`** cắt theo ngân sách token của tầng knowledge.
- **Output guard đòi trích dẫn** khi prompt có khối `<tai_lieu>` (`co_tai_lieu`) — ghi
  nhận, không chặn, vì câu trả lời đúng mà quên trích dẫn vẫn hơn câu bị nuốt.
- Công cụ `search_knowledge_base` **đã viết sẵn** phần in trang:
  `(f" — trang {c.page}" if c.page else "")` — nhưng `page` luôn NULL nên **nhánh này
  chưa bao giờ chạy**.

Thiếu duy nhất: `page`. Sửa được ở bước làm sạch, vì số trang đang nằm ngay trong text.

---

# PLAN cho phần còn thiếu

Xếp theo **rủi ro trước, tiện ích sau**. Hai việc đầu phải xong **trước khi nạp bất cứ
thứ gì**, vì chúng quyết định dữ liệu vào CSDL đúng hay sai.

## Đợt 1 — chặn dữ liệu sai (bắt buộc trước khi nạp)

**1.1 Lọc phiên bản** — sửa lỗi trộn v1/v2.
- Migration `0012`: `kb_document.la_ban_moi_nhat BOOLEAN NOT NULL DEFAULT true` + index.
- `pipeline.py`: đặt `false` cho bản cũ **trong chính transaction** nạp bản mới.
- `search.py`: thêm `WHERE d.la_ban_moi_nhat` vào cả hai đường.
- Test: nạp 2 lần với nội dung khác nhau → tìm kiếm chỉ trả về chunk của bản mới.

**1.2 Làm sạch văn bản trích xuất** — `knowledge/ingest/clean.py` (mới).
- **Bóc số trang, và giữ lại nó** — trả về `list[Trang]` thay vì một chuỗi phẳng, mỗi
  trang mang `so_trang` + `noi_dung`. Đây là bước làm hai việc một lúc: bỏ nhiễu **và**
  lấy được `page`.
- **Nối dòng bị wrap** — nối `a\nb` thành `a b` khi dòng trước **không** kết thúc bằng
  dấu câu và dòng sau bắt đầu bằng chữ thường. Luật hẹp, không đụng vào danh sách
  nguyên liệu (mỗi dòng một món, không phải câu bị gãy).
- **Gộp dòng chữ cái đơn** — `C\nO\nN\nT\nE\nN\nT\nS` → `CONTENTS`.
- **Bóc header/footer lặp** — dòng đầu/cuối giống nhau trên > 60% số trang thì bỏ. Tệp
  này không có, nhưng cơ chế phải sẵn cho tài liệu sau.
- Nén khoảng trắng ≥3 về 1.
- Test cho **từng luật**, kèm ca âm: dòng kết thúc bằng dấu chấm **không** được nối.

**1.3 Điền `page`** — chunk mang số trang của chỗ nó bắt đầu.
- `chunk.py` nhận `list[Trang]`, tính offset → trang.
- `pipeline.py` ghi `chunk.page` thay cho `NULL` cứng.
- Trích dẫn "trang 32" chạy được ngay, không cần đổi gì bên generation.

## Đợt 2 — phạm vi và quyền truy cập

**2.1 Phạm vi tài liệu** — đóng lỗ hổng ở §4.
- Migration `0013`: `kb_document.pham_vi TEXT NOT NULL DEFAULT 'chung'`.
  `'chung'` = mọi nhóm đọc được; giá trị khác = khoá theo `thread_key`.
- `search.py` **nhận `ThreadScope` làm tham số đầu**, y hệt hợp đồng của `memory_fact`.
  Đây là điểm quan trọng: đặt cùng hình dạng thì người sau không phải nhớ hai luật.
- `run_knowledge_search` nhận scope từ `CallContext`.
- **Bật `hnsw.iterative_scan = relaxed_order` ở đúng lúc này** — đây chính là lần đầu
  thêm `WHERE` vào đường vector, tức là lúc bẫy sập recall bắt đầu có thật.
- Test: tài liệu của nhóm A **không** xuất hiện trong kết quả của nhóm B.

## Đợt 3 — kiểm tra chất lượng (bước 8 của bạn)

**3.1 `cli ingest --kiem-tra`** — chạy khô, không ghi CSDL, in báo cáo:

| Kiểm tra | Cách đo |
|---|---|
| Đọc đủ tài liệu? | số trang, số trang rỗng, ký tự/trang |
| Chunk mất nội dung? | `sum(len(chunk))` so với độ dài văn bản, trừ phần overlap |
| Metadata đúng? | tỉ lệ chunk có `section`, có `page` |
| Chunk trùng? | băm nội dung đã chuẩn hoá, đếm trùng |
| Phân bố độ dài | min / trung vị / p90 / max, cảnh báo chunk quá ngắn |
| Dấu hiệu hỏng | đã có `_bao_cao_suc_khoe`, gom vào cùng báo cáo |

Đây là việc **rẻ nhất trong cả plan** và trả lời trực tiếp 5/6 câu hỏi bạn liệt kê ở
bước 8. Không cần gọi API, không cần tài liệu đã nạp.

**3.2 Bộ câu hỏi eval thật** — thay dòng mẫu trong `qa.jsonl`.
- 20–30 câu hỏi dựa trên tài liệu thật, kèm `expected_chunk_ids` lấy sau khi nạp.
- Mở khoá `recall.py` (đang `TODO`) và cho `runner.py` chạy được thật.
- Đây là câu hỏi thứ 6 — *"tìm kiếm có trả về đoạn liên quan không?"* — và là việc **duy
  nhất trong plan cần công sức thủ công**, vì không ai tự sinh được câu hỏi tốt thay bạn.

## Không làm

- **IVF / IVF-PQ / DiskANN** — chưa tới quy mô; đổi index bây giờ là tối ưu một thứ
  không phải nút thắt (`nghien-cuu-ingest.md` §5.3).
- **Bóc thẻ HTML** — đo được 0 thẻ, và `.html` không nằm trong `SUPPORTED`.
- **Nén khoảng trắng thành một bước riêng** — chỉ 2 chỗ trong 200k ký tự; gộp vào 1.2.
- **Đổi thư viện trích xuất** — chặn mạng nên chưa đo được, và PyMuPDF là AGPL-3.0.

## Thứ tự và ràng buộc

```
1.1 (lọc version) ──┐
1.2 (làm sạch) ─────┼──► 1.3 (page) ──► NẠP LẦN ĐẦU ──► 3.2 (eval thật)
                    │                        ▲
3.1 (--kiem-tra) ───┘                        │
                                    2.1 (phạm vi) ─┘
```

- **1.1 phải xong trước mọi lần nạp**, nếu không lần nạp lại đầu tiên đã sai dữ liệu.
- **1.2 và 1.3 phải xong trước lần nạp đầu**, vì đổi cách làm sạch = phải nạp lại.
- **3.1 nên làm sớm** — nó là cách kiểm chứng 1.2 và 1.3 mà không tốn tiền API.
- **3.2 phải làm sau khi nạp**, vì `expected_chunk_ids` chỉ tồn tại sau đó.
- **2.1 độc lập**, nhưng nên xong trước khi có nhóm thứ hai.
