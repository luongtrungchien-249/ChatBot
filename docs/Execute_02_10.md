# Execute 02/10 — Kế hoạch đưa CP Assistant tới trạng thái vận hành thật

> Ngày lập: 02/10/2026
> Trạng thái: **Đang thi công, chưa nghiệm thu**
> Cập nhật 15/10/2026: **1.549 pass, 29 skip; schema 27; thêm fact vector recovery và legacy restore**.
> [Báo cáo mới nhất](execution-2026-10-15.md). Gate A/B/C chưa nghiệm thu, E8 giữ đóng.
> Cập nhật13/10/2026: **1.518 test pass,29 skip có lý do;26 migration; restore synthetic40 test pass**.
> Báo cáo mới:[execution-2026-10-13.md](execution-2026-10-13.md).
> Gate A/B/C vẫn chưa nghiệm thu; E3/E4/E7 cần corpus/review/hiệu chuẩn thật; E8 giữ đóng.
> Dòng05/10 và baseline/lịch trình bên dưới là lịch sử, không phải số đo hiện hành.
> Cập nhật thực thi 05/10/2026: **đã triển khai một phần, chưa nghiệm thu Gate A/B/C**.
> Xem [trạng thái đo hiện tại](status.md) và [báo cáo thực thi](execution-report.md);
> E4 đã đo hai ma trận small/large query development; large cải thiện mạnh.
> Voyage live chưa hoàn tất do lỗi/budget stop; threshold/test chưa nghiệm thu.
> Chi tiết ở [bảng đánh giá](evaluation.md).
> baseline và lịch trình bên dưới được giữ làm lịch sử của kế hoạch.
> Phạm vi: hoàn thiện an toàn dữ liệu, Web authentication, RAG evaluation,
> retrieval/rerank, observability, Zalo production path, đánh giá thơ và quyết định
> RLVR.
> Nguồn kiến trúc bắt buộc tuân theo: `ARCHITECTURE.md`.
> Nguồn trạng thái kỹ thuật: code và test tại thời điểm lập tài liệu; các plan cũ chỉ
> được dùng làm lịch sử quyết định.

---

## 0. Mục tiêu và nguyên tắc thi công

### 0.1 Mục tiêu cuối

Sau kế hoạch này, hệ thống phải đạt các điều kiện sau:

1. Web có danh tính người dùng và không thể đọc, sửa, xoá hoặc nghe SSE của thread
   thuộc người khác.
2. Người dùng biết chính xác thao tác "xoá hội thoại" xoá thứ gì; chế độ xoá toàn bộ
   không để summary, fact hoặc cache làm dữ liệu xuất hiện trở lại.
3. RAG được đo bằng bộ câu hỏi viết tay từ tài liệu thật, có tập development và test
   tách biệt.
4. Nhà cung cấp rerank và các ngưỡng lọc được chọn bằng số đo, không bằng giá trị mặc
   định viết trước khi có corpus.
5. Hệ thống phát cảnh báo được khi bot còn sống về mặt process nhưng đang chậm, lỗi,
   hết ngân sách, nghẽn queue hoặc trả fallback bất thường.
6. Đường vào Zalo có cơ chế không mất tin, không trả lời trùng và phục hồi được sau
   restart.
7. Chất lượng thơ được hiệu chuẩn bằng người trước khi dùng LLM judge hoặc RLVR làm
   căn cứ phát hành.
8. Tài liệu trạng thái không còn mâu thuẫn với code và migration hiện hành.

### 0.2 Baseline đã xác minh ngày 02/10/2026

- `pytest`: **1030 passed, 53 skipped** trên môi trường phát triển hiện tại.
- `ruff check .`: đạt.
- `mypy --strict`: đạt trên 218 source files.
- `lint-imports`: 6 contract giữ, 0 contract vỡ.
- `ops/guard_env.py`: đạt.
- `ops/guard_sql.py`: đạt.
- Migration hiện tại: `0001` đến `0013`.
- Worktree không có thay đổi tracked trước khi lập plan; `.claude/` là thư mục chưa
  được Git theo dõi và không thuộc phạm vi kế hoạch này.

53 test bị bỏ qua không được tự động diễn giải là "53 tính năng hỏng". Phải phân loại
theo nguyên nhân: thiếu PostgreSQL, Redis, API key thật hoặc điều kiện tích hợp. Trên CI,
PostgreSQL và Redis đã được dựng; các test cần embedding thật vẫn phụ thuộc secret.

### 0.3 Luật không được phá

1. `agents/` chỉ giao tiếp ra ngoài qua `agents/ports/`.
2. Mọi truy vấn memory phải nhận `ThreadScope`; không truyền `platform` và `thread_id`
   rời rạc qua tầng nghiệp vụ.
3. Không thêm SQL chạm `memory_fact` ngoài `memory/repository/`.
4. Adapter chỉ xác thực, chuẩn hoá, enqueue và gửi phản hồi; không gọi LLM trực tiếp.
5. Không đọc environment ngoài `config/`.
6. Mọi lời gọi mạng phải có timeout, log và đo chi phí/độ trễ phù hợp.
7. Không đưa nội dung tài liệu hoặc tool output vào role `system`.
8. Mỗi thay đổi hành vi phải có test ghim và tiêu chí rollback trước khi merge.

### 0.4 Cách chia commit

Mỗi giai đoạn dùng commit riêng; migration, code và test của cùng một invariant nằm
trong cùng pull request. Không gom authentication, xoá dữ liệu, RAG benchmark và thơ
vào một PR lớn.

Quy ước đề xuất:

```text
docs(status): ghi baseline 02/10
fix(privacy): định nghĩa và thi công xoá thread
feat(auth): cô lập web thread theo danh tính
feat(evals): thêm golden dataset RAG thật
perf(rag): hiệu chuẩn rerank và ngưỡng lọc
feat(ops): thêm telemetry và alert
feat(zalo): làm bền đường nhận tin production
eval(tho): hiệu chuẩn người chấm
docs(status): chốt trạng thái sau thi công
```

---

# PHẦN I — Thứ tự, phụ thuộc và cổng phát hành

## 1. Thứ tự bắt buộc

```text
E0 Baseline
   |
   +--> E1 Xoá dữ liệu đúng nghĩa
   |       |
   |       +--> E2 Web authentication + authorization
   |
   +--> E3 Golden dataset RAG
           |
           +--> E4 Benchmark retrieval/rerank

E1 + E2 + E4
   |
   +--> E5 Observability + alerting
   |       |
   |       +--> E6 Zalo production path
   |
   +--> E9 Đồng bộ tài liệu và go-live review

E7 Hiệu chuẩn thơ
   |
   +--> E8 Quyết định RLVR/FlashREINFORCE
```

E3 có thể chạy song song với E1/E2 vì chủ yếu là công việc dữ liệu. E7 cũng có thể chạy
song song với phần chatbot chính, nhưng E8 tuyệt đối không bắt đầu trước khi E7 trả lời
được thước đo nào đáng tin.

## 2. Ba cổng phát hành

### Gate A — An toàn dữ liệu

Phải đạt trước khi mở Web ra ngoài localhost:

- Xoá toàn bộ không để dữ liệu đọc lại được qua public repository API.
- User A không truy cập được thread của user B qua REST hoặc SSE.
- Cấu hình production thiếu authentication phải fail lúc startup.
- Security tests không bị skip.

### Gate B — Chất lượng trả lời

Phải đạt trước khi quảng bá RAG là sẵn sàng dùng thật:

- Golden dataset không còn placeholder.
- Có kết quả riêng cho câu có đáp án, không có đáp án, xuyên ngôn ngữ và sai scope.
- Threshold được chọn trên development set và xác nhận trên test set.
- Không trộn phiên bản tài liệu cũ và không rò tài liệu private.

### Gate C — Vận hành

Phải đạt trước khi chạy không giám sát:

- Có alert cho error rate, latency, budget, queue và heartbeat.
- Restart Zalo/worker không làm mất hoặc lặp phản hồi.
- Có runbook backup, restore và xử lý sự cố.
- Dashboard và alert không chứa nội dung người dùng trong label.

---

# PHẦN II — E0: Chốt baseline có thể tái tạo

## 3. Kết quả cần tạo

Tạo `docs/status.md` làm nguồn trạng thái hiện hành. Tệp này chỉ ghi sự thật có thể
kiểm chứng, không chứa kế hoạch dài. Tối thiểu gồm:

- commit SHA;
- ngày đo;
- số test pass/skip/fail;
- migration mới nhất;
- số document/chunk/fact/message nếu database có dữ liệu;
- chi phí theo route;
- p50/p95 toàn lượt và từng upstream;
- tỷ lệ cache;
- trạng thái provider và các tính năng bị tắt;
- danh sách blocker go-live.

## 4. Công cụ thực thi

Không ghi số test bằng tay nếu có thể sinh tự động. Thêm một script đọc-only, dự kiến
`ops/baseline.py`, có nhiệm vụ:

1. Đọc commit SHA.
2. Đọc migration đã áp dụng.
3. Truy vấn thống kê không chứa nội dung tin nhắn.
4. In Markdown ổn định để lưu vào artifact CI hoặc dán vào `docs/status.md`.
5. Không gọi LLM và không làm thay đổi dữ liệu.

Lệnh baseline:

```bash
uv run pytest
uv run ruff check .
uv run mypy
uv run lint-imports
uv run python ops/guard_env.py
uv run python ops/guard_sql.py
uv run python ops/canary_import_rules.py
uv run python ops/baseline.py
```

## 5. Phân loại test skip

Thêm báo cáo theo bốn nhóm:

1. Thiếu PostgreSQL/pgvector.
2. Thiếu Redis.
3. Thiếu API key/embedding thật.
4. Chủ động bỏ qua theo platform hoặc điều kiện khác.

CI phải coi nhóm 1 và 2 là lỗi vì CI đã dựng hai service này. Nhóm 3 được phép skip ở
PR không có secret, nhưng nightly có secret phải chạy. Không để security test
cross-thread bị skip im lặng.

## 6. Nghiệm thu E0

- Chạy lại hai lần cho cùng commit cho kết quả cấu trúc giống nhau.
- Không có secret hoặc nội dung người dùng trong báo cáo.
- `docs/status.md` chỉ tới đúng commit và ngày đo.

Rollback: xoá script/report mới; E0 không thay đổi runtime.

---

# PHẦN III — E1: Xoá hội thoại và xoá dữ liệu đúng nghĩa

## 7. Vấn đề hiện tại

Route Web hiện xoá `inbound_message` và `thread_meta`, nhưng không thể hiện rõ việc xử
lý `thread_summary`, `memory_fact` và các khoá Redis liên quan. Vì vậy nhãn "xoá cuộc
trò chuyện" có thể tạo kỳ vọng mạnh hơn hành vi thật.

## 8. Hợp đồng sản phẩm

Tách hai hành động:

### 8.1 Xoá lịch sử hội thoại

Xoá:

- tin nhắn của thread;
- summary L2;
- tên/metadata Web thread;
- cache L1, trạng thái typing/cancel và dữ liệu tạm của thread.

Không tự động xoá fact explicit mà người dùng đã chủ động bảo bot nhớ. UI phải nói rõ
điều này và dẫn tới thao tác "xoá toàn bộ dữ liệu" nếu người dùng muốn.

### 8.2 Xoá toàn bộ dữ liệu của thread

Xoá hoặc revoke:

- toàn bộ dữ liệu của §8.1;
- mọi fact thuộc đúng `ThreadScope`;
- yêu cầu quên đang chờ;
- cache embedding/query không chứa ownership thì không cần xoá, vì nó chỉ chứa vector
  của chuỗi và không được dùng để tái dựng memory. Quyết định này phải được xác minh
  lại bằng code trước khi thi công.

Mặc định ưu tiên hard-delete cho dữ liệu Web do người dùng yêu cầu xoá toàn bộ. Nếu cần
audit bắt buộc, phải mô tả retention và dùng tombstone không chứa nội dung fact; không
được gọi revoke mềm là "đã xoá hoàn toàn".

## 9. Thiết kế code

Không để `adapters/web/routes.py` điều phối nhiều câu SQL. Bổ sung hợp đồng tại tầng
phù hợp:

- Một port quản trị thread hoặc mở rộng `MemoryPort` bằng thao tác có `ThreadScope`.
- Implementation nằm trong `memory/repository/` để được phép chạm `memory_fact`.
- Adapter gọi đúng một service/repository method.

Kiểu kết quả dự kiến:

```python
@dataclass(frozen=True, slots=True)
class DeleteReport:
    messages: int
    summaries: int
    facts: int
    metadata: int

DeleteMode = Literal["conversation", "all_data"]
```

Không bắt buộc giữ đúng tên trên nếu trong lúc thi công tìm được từ vựng rõ hơn; invariant
là scope và mode phải nằm trong chữ ký, không truyền bằng boolean khó đọc.

## 10. Transaction và thứ tự

PostgreSQL:

1. Khoá hoặc xác nhận ownership của thread.
2. Với `all_data`, xoá fact đúng `(platform, thread_id)` trong repository.
3. Xoá summary.
4. Xoá messages.
5. Xoá metadata/access record.
6. Commit.

Redis chỉ dọn sau khi transaction PostgreSQL thành công. Nếu dọn Redis thất bại, log
cảnh báo và đặt khoá invalidation/version để cache cũ không còn được tin; không rollback
dữ liệu đã xoá trong PostgreSQL chỉ vì Redis tạm hỏng.

## 11. API Web

Đề xuất giữ tương thích:

```text
DELETE /api/threads/{thread_id}
  -> xoá lịch sử hội thoại

DELETE /api/threads/{thread_id}/data
  -> xoá toàn bộ dữ liệu, cần xác nhận rõ trên UI
```

Phản hồi nên có `204` khi thành công. Thao tác phải idempotent: gọi lần hai vẫn trả thành
công, không lộ thread từng tồn tại hay không.

## 12. UI

- Menu thread có "Xoá hội thoại".
- Trong hộp xác nhận có lựa chọn riêng "Xoá cả thông tin đã nhớ".
- Không dùng checkbox được chọn sẵn cho thao tác mạnh hơn.
- Trong lúc request chạy, khoá nút để tránh gửi lặp.
- Sau thành công, đóng SSE, tạo thread mới và refresh danh sách.
- Nếu thất bại, không tự xoá thread khỏi giao diện.

## 13. Test E1

Unit:

- mode parse đúng;
- repository luôn dùng đủ `ThreadScope`;
- delete report đếm đúng;
- lỗi Redis không làm báo sai rằng PostgreSQL chưa xoá.

Integration:

- thread A bị xoá, thread B nguyên vẹn;
- summary biến mất;
- conversation mode giữ fact explicit;
- all-data mode không còn fact qua `facts`, `all_facts`, review hoặc prompt builder;
- gọi hai lần không lỗi;
- transaction rollback khi một câu SQL giữa chừng hỏng.

Security:

- không thể dùng thread ID của người khác để xoá;
- sau xoá, cache không làm dữ liệu cũ xuất hiện lại;
- không trả số lượng fact của thread không thuộc quyền người gọi.

## 14. Nghiệm thu và rollback E1

Đạt khi public API của memory không đọc lại được dữ liệu thuộc mode đã xoá và UI diễn
đạt đúng semantics.

Rollback code được, nhưng migration phá huỷ dữ liệu không được rollback bằng cách giả
vờ khôi phục. Trước khi phát hành phải có backup và thử restore trên bản sao.

---

# PHẦN IV — E2: Authentication và authorization cho Web

## 15. Phạm vi phiên bản đầu

Không tự xây password database. Dùng OIDC/SSO tại reverse proxy hoặc middleware chuẩn.
Ứng dụng nhận một danh tính đã xác minh và ánh xạ về:

```text
WebIdentity
- user_id: ID ổn định, không dùng display name
- display_name
- roles: user/operator/admin
- issuer
```

Local development được phép có dev identity, nhưng chỉ khi `NODE_ENV=development` và
`WEB_BIND` là loopback. Production tuyệt đối không tự tạo anonymous identity.

## 16. Quyết định trust boundary

Có hai lựa chọn triển khai; chọn một trước khi code:

1. Reverse proxy xác thực OIDC và ký/truyền identity header.
2. FastAPI trực tiếp làm OAuth/OIDC authorization-code flow.

Khuyến nghị giai đoạn đầu: reverse proxy nếu tổ chức đã có hạ tầng SSO. Khi dùng header,
ứng dụng chỉ tin header từ proxy tin cậy; request trực tiếp tới app phải bị chặn bằng
network policy hoặc chữ ký header. Không được tin `X-User-Id` do client tự gửi.

## 17. Mô hình quyền thread

Thêm migration `0014_web_thread_access.sql` hoặc tên kế tiếp thực tế:

```sql
CREATE TABLE web_thread_access (
  thread_id  TEXT NOT NULL,
  user_id    TEXT NOT NULL,
  role       TEXT NOT NULL CHECK (role IN ('owner', 'reader')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (thread_id, user_id)
);

CREATE INDEX web_thread_access_user_idx
  ON web_thread_access (user_id, created_at DESC);
```

Nếu sản phẩm không cần chia sẻ thread, chỉ cần owner; không thêm `reader` vì một khả
năng chưa có yêu cầu. Quyết định cuối phải ưu tiên schema nhỏ nhất đáp ứng sản phẩm.

Thread mới được claim atomically ở tin nhắn đầu tiên. Không có trạng thái một thread đã
có message nhưng chưa có owner.

## 18. Áp quyền cho từng route

Mọi route dưới đây đều phải lấy `WebIdentity` từ một dependency duy nhất:

- `GET /threads`: chỉ list thread người dùng được đọc.
- `GET /threads/{id}/messages`: kiểm tra quyền trước query messages.
- `POST /chat`: claim thread mới hoặc kiểm tra owner của thread cũ.
- `POST /threads/{id}/stop`: chỉ owner/operator.
- `PATCH /threads/{id}`: chỉ owner.
- `DELETE /threads/{id}`: chỉ owner.
- `GET /stream/{id}`: kiểm tra quyền **trước khi** mở stream.
- `GET /metrics`: chỉ operator/admin; localhost không còn là điều kiện đủ khi đã mở
  qua proxy.

Trả `404` thay vì `403` cho thread không thuộc quyền nếu cần tránh tiết lộ sự tồn tại.

## 19. Gắn identity vào pipeline

- `sender_id` của Web phải là `user_id` đã xác minh, không phải hằng dùng chung.
- `sender_name` lấy từ display name đã kiểm soát độ dài.
- Không cho client gửi hai giá trị này trong body.
- `thread_id` vẫn do client tạo được, nhưng ownership mới là hàng rào; tính ngẫu nhiên
  của UUID không phải authorization.

## 20. Cấu hình

Các biến mới phải nằm trong `config/schema.py` và `.env.example`, ví dụ:

- `WEB_AUTH_MODE`
- `WEB_AUTH_ISSUER`
- `WEB_AUTH_AUDIENCE`
- `WEB_TRUSTED_PROXY`

Tên cuối cùng phụ thuộc lựa chọn §16. Validation:

- production + auth off -> `ValidationError` lúc startup;
- trusted-header mode nhưng không có trusted proxy/signature -> fail startup;
- development loopback có thể dùng dev mode.

## 21. Test E2

- A không list/read/rename/delete/stop/stream thread của B.
- A không gửi tiếp tin vào thread của B.
- Header giả từ client không tạo identity.
- SSE bị từ chối trước khi subscribe Redis.
- Operator xem metrics nhưng không mặc nhiên đọc nội dung hội thoại.
- Production thiếu auth fail startup.
- Dev identity không thể bật trong production.
- Migration chạy hai lần qua runner mà lần hai không thực hiện lại.

## 22. Triển khai và rollback E2

Triển khai hai bước:

1. Deploy schema + code đọc ownership ở chế độ shadow/audit, vẫn localhost-only.
2. Backfill owner cho thread Web hiện có theo chính sách được duyệt, bật enforce, rồi
   mới mở reverse proxy.

Không tự đoán owner của dữ liệu cũ nếu không có bằng chứng. Có thể giữ dữ liệu cũ chỉ
cho admin hoặc yêu cầu người vận hành gán thủ công.

Rollback phải đưa app về localhost-only; không rollback về trạng thái public anonymous.

---

# PHẦN V — E3: Golden dataset RAG thật

## 23. Cấu trúc dữ liệu

Thay các dòng mẫu bằng dữ liệu có nguồn. Mỗi record nên có tối thiểu:

```json
{
  "id": "leave-001",
  "question": "Nhân viên được nghỉ phép năm bao nhiêu ngày?",
  "expected_answer": "...",
  "expected_chunk_ids": ["..."],
  "required_claims": ["..."],
  "forbidden_claims": ["..."],
  "category": "single_chunk",
  "answerable": true,
  "scope": "chung",
  "notes": "..."
}
```

Không lưu dữ liệu nhạy cảm hoặc tài liệu nội bộ thật vào Git nếu giấy phép/chính sách
không cho phép. Khi đó commit schema + manifest + dữ liệu tổng hợp, còn corpus thật được
nạp từ secret storage trong môi trường eval.

## 24. Phân bố tối thiểu

Tối thiểu 60 câu để mỗi nhóm có tín hiệu riêng:

| Nhóm | Số câu tối thiểu |
|---|---:|
| Một chunk trả lời đủ | 15 |
| Cần ghép nhiều chunk | 10 |
| Paraphrase xa từ vựng tài liệu | 10 |
| Truy vấn xuyên ngôn ngữ | 10 |
| Không có đáp án | 10 |
| Version/scope/adversarial | 5 |

Mục tiêu tốt hơn là 100 câu. Không tăng số lượng bằng cách đổi vài từ trên cùng một câu;
những câu gần trùng phải nằm cùng split để tránh rò giữa development và test.

## 25. Chia tập

- Development: 40%, dùng chọn threshold và sửa pipeline.
- Test: 60%, chỉ chạy để nghiệm thu.
- Nếu sau này huấn luyện model, tạo train split riêng; không biến development thành
  train rồi vẫn báo nó là dữ liệu chưa thấy.

Split phải ổn định bằng ID hoặc seed cố định và có test chống giao nhau.

## 26. Quy trình biên soạn

1. Chọn tài liệu đại diện production.
2. Người A viết câu hỏi và đáp án từ nội dung.
3. Người B đối chiếu nguồn, chunk và tính answerable.
4. Chạy tool kiểm tra chunk ID tồn tại trong bản corpus tương ứng.
5. Gắn category trước khi xem kết quả model để tránh đổi nhãn theo kết quả.
6. Khoá test set; mọi quyết định threshold chỉ dựa development set.

## 27. Metric và báo cáo

Giữ các metric hiện có, nhưng báo riêng từng category:

- Recall@5 hoặc retrieval hit rate;
- context precision;
- context recall;
- claim faithfulness;
- answer relevance;
- no-answer precision/recall;
- scope/version violations;
- p50/p95 toàn lượt;
- chi phí trung bình và p95 chi phí.

Không chỉ in trung bình chung. Một điểm đẹp không được che việc nhóm xuyên ngôn ngữ
hoặc no-answer đang hỏng.

## 28. Ngưỡng khởi đầu

Ngưỡng dưới đây là mục tiêu để hiệu chuẩn, chưa phải chân lý:

- Context Recall >= 0,90.
- Context Precision >= 0,75.
- Claim Faithfulness >= 0,90.
- Answer Relevance >= 0,80.
- Scope/version violation = 0.
- Tỷ lệ trả lời sai câu không có đáp án <= 5%.

Sau ít nhất ba lượt độc lập, đặt quality gate thấp hơn mức thấp nhất hợp lệ một khoảng an
toàn. Không đặt ngưỡng đúng bằng kết quả tốt nhất của một lượt.

## 29. Nghiệm thu E3

- Dataset không còn placeholder.
- Hai người đã review test set.
- Development/test không giao nhau.
- CI phân biệt mã thoát "trượt" với "thiếu dữ liệu".
- Nightly chạy đường thật qua công cụ, không chỉ gọi thẳng retrieval service.

---

# PHẦN VI — E4: Benchmark retrieval, rerank và threshold

## 30. Ma trận thí nghiệm

Chạy cùng development set trên:

1. Dense only.
2. Sparse only.
3. Hybrid RRF, không rerank.
4. Hybrid + lexical fallback.
5. Hybrid + Cohere multilingual.
6. Hybrid + provider thứ hai nếu có ngân sách và lý do thực tế.

Mọi nhánh phải dùng cùng corpus version, cùng embedding và cùng top-k đầu vào. Nếu đổi
hai biến cùng lúc thì kết quả không giải thích được.

## 31. Số cần đo

- Recall@1, Recall@5, MRR/NDCG.
- Context Precision sau rerank.
- No-answer false positive.
- p50/p95 rerank và toàn lượt.
- Tỷ lệ timeout/error.
- Chi phí trên 1.000 truy vấn.
- Kích thước candidate set và số chunk qua threshold.

## 32. Quét threshold

Trên development set:

1. Lưu score của chunk đúng và sai.
2. Quét `RERANK_MIN_SCORE` theo bước phù hợp, không mặc định chỉ thử 0,35/0,45.
3. Quét `RAG_MAX_DISTANCE` riêng; không đổi cùng lúc với rerank threshold trong lượt
   đầu.
4. Chọn điểm rẻ nhất đạt mục tiêu precision/recall.
5. Khoá cấu hình và xác nhận trên test set.

Provider không có score hiệu chuẩn, như lexical overlap fallback, không được dùng
`RERANK_MIN_SCORE` như thể score có cùng ý nghĩa với cross-encoder. Tiếp tục dùng
distance hoặc một chính sách riêng đã được test.

## 33. Thay đổi code dự kiến

- `ops/benchmark_rerank.py`: xuất JSON/CSV máy đọc được ngoài bảng console.
- `evals/runner.py`: báo theo category/provider/config hash.
- `config/schema.py`: comment nguồn của threshold và ngày hiệu chuẩn.
- `docs/evaluation.md`: lưu bảng kết quả, corpus version và quyết định.

Không hard-code threshold mới trước khi benchmark hoàn tất.

## 34. Nghiệm thu và rollback E4

Đạt khi provider/threshold thắng baseline trên test set hoặc mua được lợi ích rõ ràng về
latency/chi phí mà không phá quality gate.

Rollback bằng biến cấu hình về provider và threshold trước đó. Giữ artifact benchmark
để biết vì sao rollback.

---

# PHẦN VII — E5: Observability và alerting

## 35. Telemetry còn thiếu

Hiện có usage theo lời gọi và metrics cơ bản. Cần bổ sung thứ người dùng thực sự cảm
nhận:

- thời gian từ enqueue đến worker bắt đầu;
- thời gian toàn lượt từ nhận tin tới gửi final;
- số vòng ReAct;
- có/không gọi tool;
- fallback theo nguyên nhân;
- queue depth và tuổi job cũ nhất;
- heartbeat của worker, maintenance và Zalo;
- số lượt bị huỷ;
- tỷ lệ RAG rỗng/hỏi lại/không đủ chắc chắn.

Không dùng `sender_id`, `thread_id`, query hoặc nội dung làm Prometheus label vì cardinality
và quyền riêng tư. Trace ID ở structured log, không phải metric label.

## 36. Instrumentation

Thêm một bản ghi hoặc metric `turn` ở biên pipeline. Phải ghi đúng một lần khi lượt kết
thúc, gồm:

- trace ID trong log/database nếu cần drill-down;
- platform;
- outcome chuẩn hoá;
- latency toàn lượt;
- queue wait;
- tool count;
- iteration count;
- replied;
- cost tổng hợp.

Nếu chọn ghi vào `usage_log`, phải chứng minh schema vẫn đúng nghĩa. Phương án sạch hơn
là bảng `turn_log` riêng vì một turn khác một upstream usage record.

## 37. Alert đề xuất

| Alert | Điều kiện khởi đầu | Mức |
|---|---|---|
| Budget70 | chi ngày >= 70% | warning |
| Budget90 | chi ngày >= 90% | critical |
| ReplyErrors | error/fallback tăng liên tục 10 phút | warning |
| QueueOld | job cũ nhất vượt SLA | critical |
| WorkerMissing | mất heartbeat 2 chu kỳ | critical |
| ZaloMissing | không heartbeat/poll thành công | critical |
| ReplyP95 | p95 không tool vượt baseline + biên | warning |
| ToolP95 | p95 có tool vượt SLA | warning |
| EmbedNearTimeout | p95 embedding > 80% timeout | warning |
| CacheCollapse | cache ratio giảm mạnh so baseline | warning |
| RagEmptySpike | tỷ lệ kết quả rỗng tăng bất thường | warning |

Con số cuối phải dựa baseline E0/E3, không sao chép ngưỡng ví dụ vào production.

## 38. Dashboard

Bổ sung panel:

- end-to-end p50/p95 theo có tool/không tool;
- queue wait và depth;
- outcome/fallback theo nguyên nhân;
- heartbeat;
- ngân sách theo ngày và dự báo hết ngày;
- RAG no-result/low-confidence;
- tool latency/error theo tên tool;
- Zalo poll lag.

## 39. Kênh nhận alert

Contact point không commit secret. Cấu hình URL/token bằng environment hoặc secret
manager. Alert phải có runbook URL và câu truy vấn kiểm tra, không chỉ ghi "High latency".

## 40. Test E5

- Metrics không chứa PII/nội dung.
- Một turn retry không bị đếm thành nhiều phản hồi thành công.
- Tool call song song cộng đúng latency toàn lượt, không cộng tuần tự giả.
- Alert rule parse được bằng công cụ Prometheus.
- Dashboard JSON load được.
- Mất heartbeat giả lập làm alert firing.

---

# PHẦN VIII — E6: Đường Zalo production

## 41. Quyết định webhook hay polling

Trước khi code, xác minh tài liệu/API Zalo hiện hành bằng payload và chữ ký thật. Nếu
webhook chính thức có hợp đồng ổn định thì ưu tiên webhook. Nếu không, polling vẫn là
đường production hợp lệ nhưng phải được làm bền.

Không giữ `ZALO_MODE=webhook` như một giá trị cấu hình có vẻ chạy được khi chưa có route
verify/signature thật. Hoặc thi công đầy đủ, hoặc validation từ chối mode đó.

## 42. Nếu dùng webhook

Luồng bắt buộc:

```text
request
→ giới hạn body
→ verify signature trên raw body
→ kiểm timestamp/replay
→ parse + contract validation
→ atomic dedupe message_id
→ enqueue
→ trả 2xx dưới 2 giây
```

- Không gọi LLM hoặc Postgres nặng trong request.
- Secret dùng constant-time comparison.
- Payload sai trả mã phù hợp nhưng log đã redact.
- Retry từ Zalo gặp cùng message ID không tạo job mới.

## 43. Nếu giữ polling

- Lưu cursor/update offset bền vững sau khi enqueue thành công.
- Không advance cursor trước khi message được chấp nhận.
- Backoff exponential có jitter.
- Phân biệt empty updates với lỗi.
- Heartbeat ghi lần poll thành công gần nhất.
- Shutdown chờ request hiện tại và không mất offset.
- Restart test phải chứng minh không mất/lặp message.

## 44. Thứ tự và retry

Queue trả lời cần giữ FIFO theo thread nhưng không để một thread chậm chặn toàn bộ hệ
thống vô hạn. Thiết kế hiện tại `max_jobs=1` đơn giản và an toàn cho thứ tự, nhưng khi
tải tăng phải đo queue wait trước khi tăng concurrency.

Invariant retry:

- Chỉ đặt cờ `replied` sau khi thực sự gửi văn bản.
- Lỗi retry được ở lượt chưa cuối không gửi fallback sớm.
- Lần gửi thành công phải atomic với idempotency marker ở mức thực tế cho phép.

## 45. Contract và chaos tests

- Payload tin riêng thật.
- Payload tin nhóm và mention thật.
- Empty updates.
- Duplicate update.
- Mạng hỏng sau enqueue nhưng trước khi Zalo nhận response.
- Restart giữa hai lần poll.
- Send API trả 429/5xx/401.
- Tin dài phải chunk đúng giới hạn và không đảo thứ tự.

## 46. Nghiệm thu E6

Qua một bài soak test tối thiểu vài giờ với restart chủ động, lỗi mạng giả lập và duplicate
payload mà không mất tin hoặc gửi hai phản hồi final cho cùng message ID.

---

# PHẦN IX — E7: Hiệu chuẩn chất lượng thơ bằng người

## 47. Lý do phải làm trước RLVR

Luật tất định đo được số câu, số tiếng, vần và bằng-trắc. Nó không trả lời chắc chắn bài
thơ có nghĩa, tự nhiên, cảm xúc hay sáng tạo. Nếu LLM judge không tương quan với người,
tối ưu reward theo judge chỉ làm model giỏi đánh lừa thước đo.

## 48. Bộ chuẩn

Chọn tối thiểu 60 bài, cân bằng:

- bài đúng luật và hay;
- đúng luật nhưng vô nghĩa/ngang;
- có ý nhưng sai luật;
- bẻ chữ;
- chép hoặc gần chép;
- lặp ý/lặp chữ;
- nhiều thể thơ được hệ thống tuyên bố hỗ trợ.

Ẩn nguồn bài và cấu hình sinh khi chấm để giảm thiên lệch.

## 49. Phiếu chấm

Mỗi bài được ít nhất hai người chấm độc lập trên:

- ngôn ngữ tự nhiên;
- ý nghĩa/mạch;
- hình ảnh;
- cảm xúc;
- sáng tạo;
- mức sẵn sàng đưa cho người dùng.

Định nghĩa từng mức điểm bằng ví dụ neo. Không chỉ ghi "1 rất tệ, 5 rất tốt" vì hai
người sẽ hiểu khác nhau.

## 50. Phân tích

- Agreement giữa người với người.
- Spearman giữa LLM judge và điểm người.
- Độ ổn định khi chấm lặp.
- Tỷ lệ judge không parse được.
- Phân tích riêng bài đúng luật nhưng dở để xem judge có bị điểm luật đánh lừa.

Quy tắc:

- tương quan < 0,3: bỏ metric khỏi quyết định;
- 0,3–0,5: chỉ dùng tham khảo;
- > 0,5 và ổn định qua hai lượt: có thể dùng làm guard mềm;
- quality gate cứng cần độ tin cậy cao hơn và được ghi rõ trong `docs/evaluation.md`.

## 51. Thay đổi công cụ

Hoàn thiện hoặc chuẩn hoá `ops/cham_tay.py` để:

- sinh file chấm đã ẩn nguồn;
- kiểm tra không thiếu/trùng bài;
- nhập điểm mà không sửa tay JSONL dễ lỗi;
- tính agreement/correlation;
- xuất báo cáo và giữ raw judgments.

Không ghi đè bộ chuẩn gốc; mỗi vòng chấm có ID/ngày/người chấm đã mã hoá.

## 52. Nghiệm thu E7

- Hai người hoàn tất chấm.
- Có báo cáo agreement và correlation.
- Biết cột nào được giữ, cột nào bỏ.
- Ngưỡng `runner_tho.py` được hiệu chuẩn từ nhiều lượt, không từ một lượt đẹp.

---

# PHẦN X — E8: Cổng quyết định RLVR và FlashREINFORCE

## 53. Điều kiện được bắt đầu

Không bắt đầu E8 nếu thiếu bất kỳ điều kiện nào:

- E7 có thước đo nội dung đáng tin;
- train/test topic không giao nhau;
- completion được bóc đúng phần bài thơ trước khi reward;
- cấu hình sinh ở training và production không mâu thuẫn;
- baseline được lưu cùng model/version/seed;
- có GPU hoặc ngân sách thuê GPU phù hợp;
- có kế hoạch checkpoint, resume và rollback model.

## 54. Thứ tự thí nghiệm

1. Sửa hai tiền đề được ghi trong `plan-flash-reinforce.md`: đồng nhất cấu hình và bóc
   completion.
2. Chạy GRPO hiện tại làm baseline.
3. Thi công one-batch REINFORCE + reward centering nhỏ nhất.
4. So sánh với GRPO trên cùng ngân sách sinh.
5. Chỉ thêm sequence trust region nếu bước 3 có tín hiệu.
6. Chỉ thêm sample-mean optimization sau khi chứng minh implementation cơ sở đúng.
7. Nghiệm thu trên test topic chưa thấy khi train.

## 55. Hai cột nghiệm thu

### ĐẠT

- tỷ lệ bài sạch luật tăng có ý nghĩa;
- bẻ chữ, chép và sai khung không tăng;
- reward không bị thống trị bởi một thành phần dễ hack.

### GIỮ

- ngôn ngữ, ý nghĩa, cảm xúc và sáng tạo không giảm theo thước đo đã hiệu chuẩn;
- latency và chi phí nằm trong ngân sách;
- không chỉ tạo một khuôn bài lặp lại để lấy điểm luật.

ĐẠT tăng nhưng GIỮ giảm là thất bại. Không phát hành model chỉ vì reward tổng tăng.

## 56. Artifact bắt buộc

- config đầy đủ;
- commit SHA;
- dataset hashes;
- seed;
- checkpoint;
- optimizer/scheduler state;
- baseline và báo cáo nghiệm thu;
- model card nêu giới hạn.

---

# PHẦN XI — E9: Tài liệu, runbook và go-live

## 57. Hệ thống tài liệu sau cùng

### Tài liệu hiện hành

- `ARCHITECTURE.md`: ranh giới và dependency rules.
- `docs/status.md`: trạng thái được kiểm chứng gần nhất.
- `docs/runbook.md`: vận hành, backup, restore, incident.
- `docs/evaluation.md`: dataset, metric, threshold và kết quả.
- `docs/Execute_02_10.md`: kế hoạch thi công này.

### Tài liệu lịch sử

Mỗi plan cũ phải có banner chỉ rõ một trong bốn trạng thái:

- đã hoàn thành;
- hoàn thành một phần;
- chưa thi công;
- đã bị thay thế.

Không cần xoá lịch sử thất bại; đó là tài sản kỹ thuật. Nhưng người mới phải biết file
nào mô tả code hiện tại.

## 58. Runbook bắt buộc

`docs/runbook.md` phải trả lời được:

1. Khởi động/dừng từng process.
2. Chạy migration và rollback ứng dụng khi migration không rollback được.
3. Backup/restore PostgreSQL và Redis AOF.
4. Rotate API key.
5. Xử lý budget exceeded.
6. Xử lý queue nghẽn.
7. Xử lý Zalo mất kết nối.
8. Xử lý provider LLM/rerank/embed lỗi.
9. Audit/xoá dữ liệu người dùng.
10. Kiểm tra sau deploy và tiêu chí rollback.

## 59. Go-live review

Checklist cuối:

- [ ] Gate A đạt.
- [ ] Gate B đạt.
- [ ] Gate C đạt.
- [ ] Backup và restore đã chạy thử.
- [ ] Secrets không nằm trong Git hoặc image.
- [ ] Production bind/auth đúng.
- [ ] Daily budget và alert đã cấu hình.
- [ ] Corpus production đúng version/scope.
- [ ] Dashboard có dữ liệu.
- [ ] On-call biết dùng runbook.
- [ ] Có rollback version ứng dụng trước.

---

# PHẦN XII — Danh sách file dự kiến thay đổi

Danh sách này là bản đồ, không phải lệnh phải sửa tất cả. Trong lúc thi công chỉ tạo
file thực sự cần cho invariant của giai đoạn.

## 60. E0

```text
docs/status.md                  mới
ops/baseline.py                mới
tests/unit/test_baseline.py    mới
.github/workflows/ci.yml       cập nhật artifact/skip policy nếu cần
```

## 61. E1

```text
src/agents/ports/memory.py                  hợp đồng xoá theo scope/mode
src/memory/repository/message_repo.py       transaction/service xoá
src/memory/repository/fact_repo.py          xoá fact, vẫn là chỗ duy nhất chạm bảng
src/infra/redis_client.py hoặc module hẹp    invalidation/dọn cache
src/adapters/web/routes.py                  route mỏng
src/adapters/web/static/app.js              UI xác nhận
src/adapters/web/templates/index.html       dialog nếu cần
src/adapters/web/static/styles.css          style dialog
tests/integration/test_delete_thread.py     mới
tests/security/test_delete_scope.py         mới
```

## 62. E2

```text
db/migrations/0014_*.sql          ownership/access
src/config/schema.py              auth config
.env.example                      auth config mẫu
src/adapters/web/auth.py          mới, biên xác thực
src/adapters/web/routes.py        dependency + ownership check
src/adapters/web/normalize.py     identity -> sender
src/main/api.py                   wiring/middleware
tests/unit/test_web_auth.py       mới
tests/integration/test_web_acl.py mới
tests/security/test_web_idor.py   mới
ops/docker-compose.yml            reverse proxy/profile nếu được chọn
```

## 63. E3–E4

```text
evals/dataset/*.jsonl             golden/dev/test
evals/runner.py                   category/config report
ops/benchmark_rerank.py           machine-readable artifact
tests/unit/test_evals*.py         split/schema/threshold tests
docs/evaluation.md                mới
```

## 64. E5

```text
db/migrations/0015_*.sql hoặc metrics backend được chọn
src/infra/metrics.py
src/main/worker.py
src/adapters/zalo_bot/polling.py
ops/prometheus.yml
ops/grafana/provisioning/alerting/*.yaml
ops/grafana/dashboards/cp-assistant.json
tests/unit/test_metrics.py
```

## 65. E6

```text
src/adapters/zalo_bot/api.py
src/adapters/zalo_bot/polling.py
src/adapters/zalo_bot/normalize.py
src/main/api.py hoặc route webhook riêng
src/main/zalo.py
src/infra/dedupe.py
tests/contract/fixtures/zalo_bot/*
tests/contract/test_zalo_contract.py
tests/integration/test_zalo_delivery.py
```

## 66. E7–E8

```text
ops/cham_tay.py
evals/runner_tho.py
evals/tho/*
rlvr/huan_luyen.py
rlvr/nghiem_thu.py
rlvr/flash.py                       chỉ khi qua cổng E8
tests/unit/test_rlvr_*.py
docs/evaluation.md
```

---

# PHẦN XIII — Kế hoạch thời gian và nguồn lực

## 67. Ước lượng cho một người

| Giai đoạn | Thời gian |
|---|---:|
| E0 baseline | 0,5–1 ngày |
| E1 xoá dữ liệu | 1–2 ngày |
| E2 Web auth | 3–5 ngày |
| E3 golden dataset | 4–7 ngày, phụ thuộc người biên soạn |
| E4 rerank benchmark | 2–3 ngày |
| E5 observability | 2–3 ngày |
| E6 Zalo production | 3–5 ngày, phụ thuộc API Zalo |
| E7 hiệu chuẩn thơ | 4–7 ngày, phụ thuộc hai người chấm |
| E8 RLVR nâng cao | 1–3 tuần, phụ thuộc GPU và kết quả E7 |
| E9 tài liệu/go-live | 1–2 ngày |

Phần chatbot production, không tính RLVR, khoảng 3–4 tuần làm việc. Toàn bộ kế hoạch
khoảng 5–8 tuần cho một người nếu dữ liệu, người chấm, API key và quyền Zalo có sẵn.

## 68. Những việc cần người khác

- Chủ dữ liệu xác nhận retention và semantics xoá.
- Quản trị danh tính cung cấp OIDC/proxy configuration.
- Người hiểu tài liệu nghiệp vụ viết/review golden dataset.
- Ít nhất hai người chấm thơ độc lập.
- Người vận hành cấp contact point alert và secrets.
- Chủ Zalo app cung cấp tài liệu, token và payload/chữ ký thật.

Không giả vờ tự động hoá được các quyết định này bằng code.

---

# PHẦN XIV — Definition of Done toàn kế hoạch

Kế hoạch hoàn thành khi tất cả điều sau đúng:

1. Toàn bộ static checks và test xanh; test bảo mật trọng yếu không skip.
2. Web có authentication, ownership và security test chống IDOR/SSE leak.
3. Hai chế độ xoá có semantics rõ và không làm dữ liệu tái xuất hiện qua cache.
4. RAG có golden dataset thật, report theo category và quality gate đã hiệu chuẩn.
5. Reranker/threshold có báo cáo benchmark tái tạo được.
6. Có end-to-end turn metrics, heartbeat và alert chạy thử thành công.
7. Zalo chịu được duplicate, retry, lỗi mạng và restart mà không mất/lặp final reply.
8. Chất lượng thơ có báo cáo human calibration trước mọi quyết định RLVR.
9. `docs/status.md`, `docs/runbook.md` và `docs/evaluation.md` phản ánh đúng bản phát hành.
10. Có backup, restore, rollback và người vận hành đã chạy qua checklist go-live.

---

# PHẦN XV — Cách bắt đầu thi công

PR đầu tiên chỉ thực hiện E0, không trộn runtime change:

1. Tạo `ops/baseline.py`.
2. Phân loại 53 test skip trên môi trường hiện tại.
3. Chạy PostgreSQL/Redis local và xác định số skip còn lại.
4. Tạo `docs/status.md` từ kết quả thật.
5. Chạy toàn bộ quality gate.
6. Commit baseline.

PR thứ hai thực hiện E1. Chỉ sau khi E1 có security/integration test mới bắt đầu schema
ownership của E2. Đây là thứ tự giảm rủi ro nhất: trước hết làm cho dữ liệu có vòng đời
đúng, sau đó mới mở rộng số người có thể truy cập hệ thống.
