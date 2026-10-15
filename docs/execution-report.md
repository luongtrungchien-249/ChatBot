# Báo cáo thực thi 03–05/10/2026

> Bổ sung mới nhất: [thực thi 15/10](execution-2026-10-15.md). Nội dung bên dưới là lịch sử.

> Báo cáo này là **lịch sử 03–05/10**. Kết quả và nghiệm thu hiện hành xem
> [thực thi 13/10/2026](execution-2026-10-13.md) và [status](status.md).
> Source hiện tới 0026; các số 21 migration/12 rule/17 panel bên dưới thuộc lượt cũ.

## Trạng thái nghiệm thu

| Giai đoạn | Kết quả thực tế | Công việc còn lại |
|---|---|---|
| E0 | JUnit/provider/DB/Redis; full suite embedding thật không skip | Artifact CI trên commit sạch, kiểm tra nightly trong môi trường CI |
| E1 | Scoped delete/rollback/cleanup; khóa Web writer; generation loại job cũ; HTTP 409 khi bận | Deploy đồng bộ mọi writer, retention queue/backup và restore drill |
| E2 | Signed request v2 ràng buộc method/path/query/body, nonce Redis một lần; owner claim atomic, IDOR/SSE; credential metrics riêng | OIDC proxy thật tương thích v2, backfill, scrape thật và security review triển khai |
| E3 | 52 câu, split ổn định; preflight chunk/current version/scope; eval artifact từng category/config/source; lỗi hoặc missing required judgment không cho pass | Gán category chuẩn, bổ sung coverage, fixture scope/corpus, metric/gate đầy đủ, gần trùng semantic, hai người review |
| E4 | Artifact v5; hai ma trận small/large query-only, candidate Recall; key Voyage xác thực, benchmark live partial; budget/HTTP stop/pacing; test chưa mở | Rate limits/billing chưa đo, provenance corpus, benchmark Voyage hoàn tất; tổng cost và policy distance/no-answer đầy đủ |
| E5 | Turn/RAG telemetry; lỗi retrieval không biến thành empty; tuổi enqueue gốc; bounded cause ReAct; 12 rule có test; 17 panel | Cause ngoài ReAct/final clarification chưa đo; scrape/contact point thật, SLA hiệu chuẩn |
| E6 | Durable inbox/replay; crash trước DB commit sau enqueue không tạo job thứ hai; ARQ Retry đúng | Remote delivery uncertainty, contract thật, soak/restart |
| E7 | Blinded rounds, nhập sáu chiều tương tác có resume; agreement/Spearman/repeatability offline, không tự cấp hard gate | 60 bài cân bằng; hiện chỉ 40 distinct; hai người chấm thật và nghiệm thu độ ổn định |
| E8 | Chưa bắt đầu vì E7 chưa đạt | Chỉ triển khai RLVR sau calibration và ngân sách/GPU được xác nhận |
| E9 | Runbook v2/deploy migration/metric; 17 plan có banner lịch sử; trạng thái nghiệm thu được ghi | Backup/restore drill, on-call/go-live review |

## Kiểm tra đã thực hiện

- Lượt offline trước đó: **1130 passed, 28 skipped**.
- Sau khi người dùng cho phép API: ba file fact/cross-thread/knowledge **36 passed**;
  full suite **1158 passed, 0 skipped**.
- Sau sửa cache phân biệt fake/OpenAI và thêm bảy regression test: full suite trước
  **1165 passed, 0 skipped, 0 failed**, dùng embedding thật.
- Lượt mới sau bổ sung E5 và 29 regression test: **1194 passed, 0 skipped, 0 failed**,
  vẫn dùng embedding thật; JUnit đã cập nhật.
- Lượt 04/10 sau RAG health và 38 test mới: **1232 passed, 0 skipped, 0 failed**,
  embedding thật; JUnit cập nhật.
- Lượt kiểm tra source 04/10 lúc 14:24 (UTC+7), thêm 45 regression test:
  **1277 passed, 0 skipped, 0 failed**, embedding thật; JUnit cập nhật, 19,65 giây.
- Lượt 05/10 sau preflight/artifact và 40 regression test mới: **1317 passed,
  0 skipped, 0 failed**, embedding thật; JUnit cập nhật, 31,32 giây.
- Lượt 05/10 lúc 11:56 sau Voyage/benchmark cost và 42 regression test:
  **1359 passed, 0 skipped, 0 failed**, embedding tổng hợp thật; 28,88 giây.
- Lượt 05/10 lúc 13:12 sau metric candidate/ranking và timer benchmark:
  **1363 passed, 0 skipped, 0 failed**, 19,14 giây; bốn regression test mới.
- Lượt 05/10 lúc 22:24 sau query model override, HTTP stop và pacing:
  **1370 passed, 0 skipped, 0 failed**, 24,44 giây; bảy regression test mới.
  Rerank=fake chỉ trong process test; Voyage adapter test HTTP mock, không sửa `.env`.
- Ruff đạt; mypy strict đạt trên 266 file; 6 import contracts, guard env/SQL và 9 canary đạt.
- `promtool check rules`: SUCCESS, 12 rules.
- `promtool test rules`: SUCCESS; test firing và trường hợp không firing/boundary.
- `docker compose config --quiet`: thành công.
- Migration 0016 và 0017: lần đầu ran=1, lần hai ran=0; tổng 17 migration.
- Migration mới nhất 0021: lần đầu ran=1, lần hai ran=0; tổng hiện tại 21 migration.
- Test IDOR HTTP: 8 đường truy cập bị từ chối trước query nội dung/subscription.
- Test Redis heartbeat, telemetry upsert, ARQ Retry và enqueue failure/replay: đạt.
- Test crash giả lập sau Redis acceptance/trước DB commit dùng queue riêng, không đụng job thật.
- Test PostgreSQL: xóa bị từ chối khi writer giữ lock; reply/maintenance epoch cũ không vào pipeline.
- Baseline đo lại: 5 document, 405 chunk, 1 fact, 1.878 message; không đọc nội dung để báo cáo.
- Cache v2 băm provider/model/dimension/query, bỏ cache v1 không rõ provenance;
  kiểm tra vector cache đúng kiểu/kích thước và hữu hạn. Cache cũ tự hết TTL, không xóa hàng loạt.

## Những bằng chứng bên ngoài còn thiếu

- Corpus version được chủ dữ liệu xác nhận, câu hỏi bổ sung theo coverage và review thứ hai.
- Rate limits Voyage, billing các request lỗi, retention tài khoản và provenance corpus;
  giới hạn rerank development đã thống nhất 0.10 USD/lượt, không gồm embedding.
- OIDC proxy, token metrics được cấu hình trong runtime và danh sách owner legacy được duyệt.
- Payload/ack/cursor Zalo thật để thiết kế recovery đúng contract.
- Bộ 60 bài đã cân bằng và hai người chấm độc lập.
- Backup/restore môi trường bản sao, alert contact point và người vận hành.

Gate A, B, C chưa đạt. Các test xanh hiện tại chưa thay thế những nghiệm thu trên.
Không tự gán owner legacy, thêm câu hỏi/đáp án giả hoặc điểm người để lấp coverage;
không bật E8 trước E7 và quyết định ngân sách/GPU.

## Quyền chạy API thật

Lượt xin phép ban đầu bị auto-review từ chối. Sau khi người dùng trả lời "thực hiện đi",
đã xác minh endpoint `api.openai.com`, model `text-embedding-3-small`, 1.024 chiều và
dữ liệu gửi là câu/fact/tài liệu tổng hợp khai báo trong test. Lượt chạy có quyền mạng
đã được duyệt; không thay `.env` hoặc đưa key vào log/báo cáo.

Cost meter trước/sau: `0.000086` → `0.000215 USD` cho route embed trong cửa sổ bảy ngày;
chênh lệch khoảng `0.000129 USD` là chi phí ghi nhận ước tính, không phải hóa đơn API.

## Tiếp tục E5: telemetry theo kết quả pipeline

- Report ReAct tách khỏi progress SSE, chỉ chứa reason/counter, không chứa câu hỏi,
  answer hoặc tool output. Sink lỗi không đổi hành vi trả lời.
- Pipeline trả metadata cho mọi nhánh xử lý: command/help, budget/rate limit,
  access/mention ignore, thơ và generation. Lý do dừng khác với outcome xử lý.
- Retry im lặng không được tính là fallback; attempt thành công ghi đè chi tiết lỗi
  cũ trên đúng trace. Duplicate/job generation cũ không làm mất kết quả đã ghi.
- Migration 0018/0019 áp dụng local; chạy lặp `ran=0`, tổng 19 migration. Các cột
  chưa đo giữ NULL, không backfill thành công/0 cho dữ liệu lịch sử.
- Chi phí trace cộng usage đã ghi qua retry. Chưa liên kết embedding `system`
  hoặc đủ phí tool bên thứ ba; không gọi đây là tổng hóa đơn.
- Test PostgreSQL/Redis thật: upsert/reset metadata, chi phí không lẫn trace khác,
  và xuất metric fallback/tool không lộ ID. Dữ liệu synthetic tự dọn sau test.
- Alert fallback >10%, mẫu ít nhất 20 phản hồi, giữ 2 phút: firing, pending,
  boundary 10%, mẫu ít hơn 20 và mẫu rỗng đều đã kiểm tra bằng promtool.
- Dashboard thêm ba panel fallback/reason/ReAct. Chỉ xác nhận JSON/rule và metrics
  local; chưa xác nhận notification hoặc dashboard live production.
- Baseline 22:28 (UTC+7): dữ liệu corpus/memory giữ nguyên; embed 373 calls, 0 lỗi,
  `0.000301 USD`, tăng `0.000086 USD` so với 17:24, p95 `843 ms`.

## Tiếp tục E5 ngày 04/10: RAG health

- `search_detailed` bổ sung kết quả có metadata; `search` vẫn trả list cho caller cũ.
  API text-only của knowledge tool giữ nguyên, ToolPort không đổi hợp đồng.
- Hai nhánh lỗi, hoặc nhánh còn sống không có kết quả đủ dùng: raise lỗi tra cứu,
  không báo “tài liệu không có đáp án”. Một nhánh lỗi nhưng còn kết quả vẫn phục vụ
  suy giảm và có flag. Cancellation không bị nuốt thành kết quả rỗng.
- Rerank rỗng/malformed (index âm/trùng/ngoài phạm vi/bool, điểm không hữu hạn) hoặc
  timeout: fallback RRF, không lọc bằng score giả. Không thay threshold/provider.
- Phân biệt empty trước rerank, filtered do relevance filter, uncertain do danh sách
  ứng viên, found và error. Chọn sâu không ép hỏi lại nhưng vẫn ghi low confidence.
  Widening lỗi giữ ứng viên pass đầu nếu còn; flags suy giảm được hợp nhất.
- Metadata không được đưa vào prompt. Registry ghi một row mỗi actual tool attempt,
  dù search hai pass. Cùng trace có thể có nhiều attempt; không gọi chúng là số turn.
- Migration 0020 áp dụng local, chạy lặp `ran=0`; chỉ lưu trace/platform/status,
  boolean flags, latency và timestamp, không lưu query/nội dung/sender/thread.
  Sink best-effort timeout 2 giây; chưa có GC/retention policy được nghiệm thu.
- Metric gauge cửa sổ 5 phút có zero outcome series nhưng không bịa p95 khi thiếu mẫu.
  Cancellation/unknown không vào mẫu số chất lượng, cũng không vào degradation ratio.
- Thêm ba alert RAG no-result/error/degradation; firing, pending, boundary, mẫu ít
  và zero sample đều qua promtool. Ngưỡng 50%/10% chỉ tạm thời, chưa hiệu chuẩn E3/E4.
- Sáu integration test dùng PostgreSQL thật; bốn scenario chạy native retrieval →
  tool → DB với branch/rerank tổng hợp, không gọi thêm endpoint ngoài. Không giữ row test.
- Baseline 04/10 lúc 03:14 (UTC+7): corpus/memory không đổi; embed 420 calls, 0 lỗi,
  `0.000344 USD`, tăng khoảng `0.000043 USD` so với snapshot trước; p95 `843 ms`.

Chưa tuyên bố E5 hay Gate C hoàn thành. `uncertain` là nội dung công cụ đề xuất lựa chọn,
không chứng minh LLM đã hỏi lại trong final; dashboard live, receiver và SLA còn thiếu.

## Kiểm tra source và triển khai bổ sung 04/10 lúc 14:24

Đối chiếu trực tiếp auth/routes/startup config, thread repository/lifecycle/cleanup,
queue/worker, inbox/poller Zalo, retrieval/tool registry, telemetry, dataset contract,
runner, benchmark và human-review với E0–E9; không chỉ đọc báo cáo hoặc số test.

- Auth cũ chỉ ký identity/timestamp. Đã thay v2 với JSON framing, hash body, raw
  method/path/query và nonce. Test thay từng thành phần, replay/outage; test HTTP
  dùng Redis thật trên hai app xác nhận body vẫn đọc được và nonce đã dùng bị từ chối.
  Không tuyên bố proxy/SSO production đã được cấu hình. V1 bị từ chối, cần deploy
  proxy đồng bộ theo runbook; mất Redis state cần đóng traffic/rotate để tránh replay.
- Queue age lấy timestamp enqueue gốc từ ARQ, không lấy score deferred/retry. Test
  job thật ở queue tổng hợp riêng: schedule tương lai vẫn có age >600s. Cleanup chỉ
  xóa key tổng hợp của test, không chạm job thực tế. Thiếu dữ liệu không giả age=0.
- Domain cause chỉ phân loại lỗi ReAct có evidence (timeout/status), bounded labels;
  0021 và test PostgreSQL xác nhận retry mới xóa cause cũ. Lỗi ngoài đường này chưa
  được suy diễn thành một service cụ thể.
- Eval trước có thể trả exit 0 dù một số câu upstream lỗi; đã sửa fail gate.
  No-answer trước được mặc định Recall=1; đã sửa null khi không có ground-truth.
  Dataset sai kiểu hoặc scope chưa có fixture bị chặn trước gọi provider.
- Benchmark có dense/sparse/hybrid/no-rerank; test branch isolation và locked test
  không quét/gợi ý threshold. Chưa gọi provider thật trên corpus để tuyên bố thắng.
- Chấm thơ tương tác không đọc private scores, append bài đủ sáu chiều và resume;
  test nhập NaN/out-of-range, dừng giữa bài, file reviewer khác và resume. Report
  Spearman xử lý ties/constant/thiếu điểm/lặp; không thay người chấm hoặc cấp hard gate.
- Thêm banner nguồn trạng thái lịch sử cho 17 plan, không xóa nội dung hoặc biến
  những thí nghiệm bị chặn/thất bại thành “đã hoàn thành”.

Kết quả: 1.277 test xanh (45 test mới so với 1.232), không skip; mypy 258 file,
Ruff/6 import contracts/guard env/SQL/9 canary đạt. Rule Prometheus parse/firing/
pending/boundary đạt trên image local `prom/prometheus:v3.14.0` với network none;
12 rule, dashboard JSON 17 ID panel duy nhất, Compose config quiet đạt. Đây chưa
chứng minh dashboard load live hoặc gửi được notification.

Baseline: commit nền giữ nguyên (dirty), 21 migration, 5 document/405 chunk/1 fact/
1.878 message. Route embed 7 ngày 514 calls, 0 errors, cost ước tính 0.000430 USD,
p95 827ms; tăng 0.000086 USD so với snapshot 03:14. Endpoint xác minh lại chỉ in host
`api.openai.com`. Không sửa `.env` hoặc `src/llm/models.py` trong lượt này, không
đưa key vào báo cáo, không gửi dữ liệu người dùng/corpus để chạy benchmark.
Hai lần collect baseline liên tiếp giữ cùng kết quả khi loại timestamp đo;
`git diff --check` không có lỗi whitespace. Không tạo commit từ worktree đang dirty.

## Tiếp tục E3–E4 ngày 05/10: corpus preflight và artifact eval

Đối chiếu source `dataset_contract`, runner, benchmark, judge metric, DB schema và
CI eval với §23–34 của plan. Không chạy paid golden eval/benchmark hoặc tự thêm dữ
liệu người chấm; `.env` và thay đổi hiện hữu trong `src/llm/models.py` được giữ nguyên.

- Bổ sung `evals/corpus_contract.py`: transaction repeatable-read/read-only kiểm tra
  chunk annotation tồn tại/bản hiện hành/scope, fingerprint metadata ổn định; không
  SELECT text/title/source path/vector. CLI chỉ báo ID câu/mã lỗi/count/hash, không
  in raw exception/DSN. Coverage và review nội dung vẫn là kiểm tra độc lập.
- Runner và benchmark thực hiện preflight trước gọi provider. Dataset chặn annotation
  trùng, scope rỗng và no-answer gán relevant chunk; scoped eval ngoài `chung` vẫn
  bị chặn cho đến khi có fixture biệt lập. Dataset đổi trong preflight không gọi API.
- Runner mặc định development; test phải có `--split test --confirm-test`. Nightly
  không tự dùng test; CLI không chứng nhận người vận hành đã khóa/review test set.
- `evals/run_artifact.py` ghi artifact v1 theo tổng/category, cả nhóm lỗi toàn bộ:
  attempted/completed/failed, metric mean/mẫu số đo được, p50/p95, config/hash,
  dataset/corpus metadata/source SHA-256 và commit/dirty. Allowlist không chứa nội
  dung câu hỏi/answer/tool/raw exception; hash endpoint thay vì URL/API key/DSN.
  Cấu hình có cả model trả lời và judge. Output mới dùng exclusive-create.
- Sửa gate metric unknown-as-pass: thiếu required judgment không cho xanh. Recall
  tool mode/no-answer không áp dụng giữ null; Answer Relevance chưa hard gate.
  Lỗi bất kỳ câu hoặc corpus/dataset/source đổi/không kiểm chứng được làm fail;
  artifact vẫn giữ kết quả đã đo, kể cả dataset biến mất cuối lượt. Preflight/schema
  fail trước lượt chạy không có eval artifact; standalone preflight có output riêng.
- `release_gate_b_accepted=false` luôn được ghi: chi phí/no-answer precision-recall/
  scope-version answer violations/human review chưa đầy đủ. Mean trên mẫu đo được
  không được coi là mean toàn dataset; lỗi có mẫu số riêng và chặn run pass.
- CI eval nối `--output`/upload khi fail, retention 14 ngày; chưa push hoặc chạy
  workflow GitHub, chưa có mount corpus được duyệt trong CI.

Kiểm tra metadata local: 52 câu, 63 tham chiếu chunk, 0 lỗi; fingerprint
`aea8dd9f7f800c142e8f21b12cd8a60d85488ea977b252a344f598e325db6881`.
Hash là latest document metadata/chunk count, không phải từng chunk/vector. Không
chứng minh annotation đúng nghĩa. Dataset contract vẫn exit `2`: 24 development,
28 test; thiếu coverage chuẩn 15 single_chunk, 10 multi_chunk, 10 distant_paraphrase,
3 cross_language, 6 unanswerable, 5 scope_version_adversarial theo contract/nhãn hiện có;
nhãn lịch sử chưa được review/gán đủ category chuẩn, không tự đổi để lấp số lượng.

Regression kiểm tra cả CLI và PostgreSQL thật: stale/scope/missing IDs, snapshot
read-only, chặn provider, artifact cả nhóm lỗi, unknown required metric, input đổi/
mất cuối lượt, output không ghi đè, source hash bỏ `.env`, config judge và split
isolation. Integration tạo/xóa đúng document tổng hợp riêng; metadata corpus trở về
fingerprint gốc, không sửa tài liệu người dùng. Full suite mới **1317 passed**, 0
skip/fail (40 test mới so với 1277); Ruff/mypy 263 file/6 contracts/guard/9 canary đạt.
Không có migration mới; schema vẫn 0021/tổng 21 migration.

Baseline local 05/10 lúc 10:24 (UTC+7): 5 document/405 chunk/1 fact/1.878 message.
Embed 7 ngày 624 calls, 0 errors, cost ghi nhận 0.000516 USD, p95 750ms; tăng khoảng
0.000086 USD so với snapshot 04/10 14:24, là ước tính chứ không phải hóa đơn provider.
Chỉ gọi embedding thật bằng dữ liệu tổng hợp trong regression suite theo phạm vi
đã được duyệt; không gửi corpus/tin nhắn người dùng để chạy quality benchmark.
Web vẫn dev/loopback, metrics scrape token chưa cấu hình, rerank vẫn fake.
Gate A/B/C chưa nghiệm thu; E8 chưa bắt đầu. Cần dữ liệu/review/ngân sách/provider/
SSO/Zalo contract/soak/alert receiver/restore drill thật để đóng các giai đoạn.

## Tiếp tục E4 ngày 05/10: chọn provider rerank chi phí thấp

Người dùng yêu cầu chọn provider rẻ và thực hiện. Đã kiểm tra giá/API/model trực tiếp
từ tài liệu chính thức; chọn **Voyage AI / `rerank-3-lite`** làm ứng viên chi phí thấp,
giá niêm yết 0.02 USD/1M token, chưa giả định credit miễn phí còn lại hoặc đã thắng
benchmark corpus local. [Giá](https://docs.voyageai.com/docs/pricing),
[model](https://blog.voyageai.com/2026/09/30/rerank-3/),
[REST API](https://docs.voyageai.com/reference/reranker-api).

- Thêm adapter Voyage vào factory/runtime, không thêm SDK/phụ thuộc hoặc sửa
  `src/llm/models.py`. HTTP pooled, timeout 15s, không tự retry/redirect/truncate;
  `return_documents=false`. Validate index/type/range/order/usage và không in error
  body. Giữ lexical fallback và Cohere; lỗi HTTP Cohere cũng không lộ body nữa.
- List-price token/cost từ usage Voyage ghi `usage_log` route rerank và daily budget,
  attribution system như embedding. Ranking malformed nhưng có usage vẫn ghi phí,
  `ok=false`, không che sự cố thành thành công. Sink 2s best-effort; đây chưa là chi
  phí đầy đủ theo từng turn hoặc hóa đơn có credit/tax. PostgreSQL thật đã kiểm tra
  cả ok/invalid; row tổng hợp được dọn đúng model UUID, không sửa Redis budget thật.
- Benchmark override provider/model trong process, không sửa `.env`. Mặc định limit
  0.10 USD **chỉ tiền Voyage rerank**; reserve tối đa 600K token trước mỗi request,
  cập nhật bằng usage hợp lệ. Timeout/missing usage giữ reservation. Khi limit chặn,
  dừng lượt và không gọi retrieval các câu còn lại; ghi skipped/error/unknown cost.
  Không tăng limit để vượt chốt hoặc giả định free credits để lách budget.
- Artifact v4 bổ sung Recall@5, latency adapter rerank, token/list-price cost và
  reserved upper bound; tổng cost gồm embedding vẫn null. Dataset hash được chốt
  trước đọc; đổi dữ liệu/corpus làm fail. Run lỗi/budget stop không quét/đề xuất
  threshold; fake/test vẫn không quét. `release_gate_b_accepted=false`.
- Thêm `--preflight-only` không dựng provider hoặc gọi API; `--allow-provider-data`
  là yêu cầu xác nhận cho paid benchmark, không thay quyền hệ thống/owner. Output
  exclusive-create, generated evidence trong `evals/results/` được gitignore.

Đã chạy metadata preflight local: development 24 câu/30 tham chiếu, 0 lỗi corpus,
0 provider calls; dataset SHA `691939f1988a2ce725e55d544209400f0187d1abb301cb33b4203a6b30f04419`,
corpus metadata SHA giữ nguyên như lượt trước. Artifact local:
`evals/results/2026-10-05/voyage-preflight.json`.
Đây không phải artifact chất lượng/provider thật. Key hiện là development placeholder,
không gửi key đó sang Voyage, không sao chép key OpenAI làm key rerank.

Thử mở lượt baseline hybrid/no-rerank bị **auto-review từ chối**: thiếu quyền cụ thể
gửi question golden/corpus-derived data tới OpenAI. Lệnh không chạy; không đổi shell,
quyền hoặc đường gọi để né. Đã yêu cầu user xác nhận xuất 24 question development tới
OpenAI, candidates scope chung tới Voyage và đặt key Voyage trực tiếp trong `.env`;
chưa có xác nhận/key mới trong lượt này. Không có golden/corpus data được gửi ra
provider, không có paid Voyage call. Retention tài khoản cần owner duyệt; Voyage
opt-out lưu/training/zero-day retention cần admin và payment method, không tự đăng ký
hoặc thêm thanh toán. [Chính sách chính thức](https://docs.voyageai.com/docs/faq#what-are-your-policies-in-regard-to-protecting-customer-data).

Kết quả cuối: **1359 passed**, 0 skip/fail (42 test mới so với 1317); Ruff, mypy strict
266 file, 6 import contracts, guard env/SQL và 9 canary đạt. Test Voyage là HTTP mock
dữ liệu tổng hợp, không phải chứng nhận tài khoản/API live. Embedding thật chỉ được
gọi cho regression tổng hợp theo quyền đã duyệt trước đây, không dùng benchmark bị
chặn. Schema vẫn 0021/tổng 21 migration; corpus/memory giữ 5/405/1/1.878.
Baseline 11:56 UTC+7: embed 718 calls, 0 lỗi, 0.000602 USD, p95 827ms; tăng 0.000086
USD so với snapshot 10:24, là ước tính chứ không phải hóa đơn. Runtime rerank vẫn
fake; `.env`, provider/threshold đang chạy và thay đổi hiện hữu trong models.py được
giữ nguyên. E4 và Gate B chưa nghiệm thu; E8 vẫn chưa bắt đầu.

## Tiếp tục E4 ngày 05/10 sau xác nhận thực thi

Sau câu trả lời `OK thực thi đi` cho yêu cầu duyệt dữ liệu ở lượt trước, đã xin lại
approval cho baseline; hệ thống cho chạy. Không né lần từ chối trước đó. Câu hỏi
development được embedding qua OpenAI đã cấu hình; chỉ đọc corpus trong máy,
không gửi corpus tới OpenAI/Voyage, không gọi LLM trả lời/judge hoặc mở test split.
Key Voyage vẫn placeholder, không có paid Voyage call; runtime vẫn `fake/fake`.

- Chạy đúng bốn baseline §30: dense, sparse, hybrid RRF không rerank và hybrid+lexical.
  Cùng 24 development (22 answerable, 2 no-answer), dataset/corpus metadata hash
  giống nhau và ổn định. Không đổi annotation, corpus, provider runtime hoặc threshold.
- Kết quả: top-1 đúng `0/22` cho mọi cấu hình. Dense/hybrid/hybrid+lexical Recall@5
  `4,55%`; sparse `0%`. Sparse exit 1 vì không trả annotation đúng, không phải lỗi
  API. Các baseline còn lại exit 0 chỉ xác nhận run hoàn tất, không có quality gate.
- Bổ sung artifact v5: candidate Recall và số câu có hit trước rerank, Recall@1,
  ranked context precision. Chỉ `1/22` câu có annotation trong candidate (Recall
  `4,55%`); reranker không cứu được các annotation không có trong đầu vào.
  Metrics ranking là trước relevance filter, đối chiếu chunk ID annotation,
  không phải độ đúng ngữ nghĩa câu trả lời hoặc Context Precision sau threshold.
- Candidate Recall giữ số đo khi rerank lỗi; retrieval lỗi/câu bị budget skip tính 0
  trên mẫu số toàn bộ answerable. Không có answerable giữ null, không tự cho pass.
- Timer dùng `perf_counter` để cache-warm trên Windows không bị lượng tử thành 0ms;
  có test sub-millisecond. Lượt cuối dùng cache embedding, p95 toàn query khoảng
  3,00–6,82ms, không phải p95 cold provider hay toàn turn. Lượt hybrid đầu chưa warm
  có p95 khoảng 688ms; hai loại latency không dùng để kết luận speedup giữa cấu hình.
- Artifact cuối: `evals/results/2026-10-05/*-v5-precise.json`; artifact v4/v5 cũ được
  giữ, không ghi đè. Bảng đầy đủ và quyết định ở evaluation.md.

Chẩn đoán chỉ đọc thêm: 179 vector của hai document mới nhất scope chung có đúng
1024 chiều, không có mẫu lặp 32 phần tử của FakeEmbedder. Usage embedding gần thời
điểm ingest (cửa sổ 10 phút, record cuối trước ingest) của cả hai document ghi
`text-embedding-3-large`; query hiện là `text-embedding-3-small`. Đây là **giả thuyết
lệch model**, không phải provenance trực tiếp: schema ingest chưa lưu provider/model
gắn chunk/document, record usage gần thời gian có thể thuộc request khác. Không tự
re-embed, đổi model hay backfill provenance từ suy đoán. Cần chủ corpus xác minh trước
thử query model tương thích/chọn provider; rerank thật vẫn cần key riêng.

Kiểm tra cuối: **1363 passed**, 0 fail/skip, 19,14s; Ruff, mypy strict 266 file,
6 import contracts, guard env/SQL, 9 canary và diff whitespace đạt. Baseline 13:12:
5 document/405 chunk/1 fact/1.878 message giữ nguyên; embed 7 ngày 860 calls, 0 lỗi,
0.000690 USD, p95 750ms. Tăng 0.000088 USD so snapshot 11:56 gồm benchmark và hai
lượt regression, không phải phí riêng từng query hoặc hóa đơn provider. E4 chưa đạt,
Gate A/B/C vẫn chưa nghiệm thu; E8 chưa bắt đầu.

## Tiếp tục E4 ngày 05/10 lúc 22:24: Voyage live và đối chiếu query embedding

Người dùng đã điền key, sửa provider/model thành `voyage/rerank-3-lite` và yêu cầu
thực thi tiếp. Config hợp lệ; giữ thay đổi của người dùng, không tự ghi `.env` hoặc
chuyển threshold. Kiểm tra key trước đó dùng hai đoạn mẫu cho HTTP 200, 23 tokens;
không chứng minh chất lượng trên corpus. Đã xin/qua approval cho lượt live gửi
candidate scope chung tới Voyage và development query tới OpenAI khi cache thiếu.

**Voyage development chưa hoàn tất**: 11 calls, chỉ 3 có usage hợp lệ (10.628 tokens,
chi phí đo được theo list price 0.00021256 USD); 8 RuntimeError, một lần chặn budget,
12 câu chưa thử. Reserved upper bound 0.09621256 USD dưới trần 0.10 USD nhưng
không đủ dự phòng cho call kế tiếp. Cost tổng unknown, không phải đã chi 0.096 USD
hay chỉ chi 0.000213 USD. Dataset/corpus ổn định; không quét threshold, không test
split, không tăng cap hay mở một lượt Voyage mới để bỏ qua khoản chưa đo. Artifact
`evals/results/2026-10-05/voyage-development-v5.json` được giữ với exit 1/Gate B false.

Lượt đầu adapter chỉ trả RuntimeError an toàn, artifact chưa lưu mã HTTP, nên không
thể kết luận tám lỗi đều 429. Đã bổ sung RerankHttpError (chỉ provider/status), log
status không chứa body/key, thống kê status trong benchmark, stop ngay 401/403/429
trước retrieval/call tiếp theo. Budget unknown vẫn giữ dự phòng. Có tùy chọn
`--rerank-interval-s` để pace theo RPM/TPM của account; không retry ngầm, không tự
thêm payment method/nâng quota. Chờ người dùng cung cấp Rate Limits của account;
[hướng dẫn Voyage](https://docs.voyageai.com/docs/rate-limits) không xác định quota
riêng của account này. Daily cost meter chỉ có ba request có usage; 0 errors trong
nhóm đó không phải error rate thật của provider trong lượt benchmark.

Dùng skill OpenAI Docs để đối chiếu API embedding/dimensions và giá model; nguồn
[embedding](https://developers.openai.com/api/docs/guides/embeddings),
[large](https://developers.openai.com/api/docs/models/text-embedding-3-large).
Thêm override query model task-local bằng ContextVar, reset kể cả exception,
kiểm tra provider/model có giá trước call. Settings frozen, `.env`, vectors và
annotation không đổi; cache khóa theo model nên không trộn vector small/large.
Không gửi corpus tới OpenAI hoặc chạy judge; chỉ embedding 24 development query đã duyệt.

Phép thử cùng corpus/top-k/dimension với large cho hybrid top-1 **13/22**, Recall@5
**81,44%** thay vì **0/22 / 4,55%** với small; candidate Recall **82,58%**, 19/22 câu
có annotation trước rerank, 0 lỗi. Dense large đạt 15/22, cùng Recall@5; lexical
fallback large 11/22, Recall@5 78,03%; sparse vẫn không tìm annotation. Hai model
được so riêng, không dùng kết quả incomplete Voyage-small so trực tiếp large để
kết luận thắng rerank. Log ingest large cộng phép thử là bằng chứng mạnh về lệch
query model, nhưng chưa provenance trực tiếp hoặc chứng nhận tất cả vectors thuộc large.
Chưa đổi query runtime vì cấu hình embedding còn dùng cả memory fact/dedupe; không
tự re-embed dữ liệu, gán provenance hay sử dụng test để chọn model.

Các artifact large `*-large-development-v5.json` được giữ, bảng ở evaluation.md.
Large hybrid cold-query p95 khoảng 959ms; các lượt sau dùng cache nên không suy
speedup từ p95 của hai cấu hình. Corpus vẫn 5 document/405 chunk/1 fact/1.878 message,
metadata hash và dataset hash không đổi. Runtime do user cấu hình Voyage nhưng
embedding vẫn small/threshold 0.45 chưa hiệu chuẩn; không coi là quyết định phát hành.

Full suite **1370 passed**, 0 fail/skip, 24,44s (rerank=fake trong process test,
embedding thật tổng hợp); unit targeted 65 pass sau bổ sung log status. Ruff, mypy
strict 266 file, 6 import contracts, guard env/SQL, 9 canary đạt. E4/Gate B chưa đạt;
các nghiệm thu ngoài hệ thống ở E1/E2/E5/E6/E7/E9 vẫn còn, E8 chưa bắt đầu.
