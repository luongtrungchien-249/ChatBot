# Trạng thái hệ thống

> Cập nhật **15/10/2026**: [báo cáo mới nhất](execution-2026-10-15.md).
> **Gate A/B/C chưa nghiệm thu; E8 giữ đóng.**

- Full suite: **1.549 passed, 29 skipped**, 15,22 giây; fake provider, PG 18/Redis 8 tạm.
- Mypy strict 299 file, Ruff, 6 import contracts, 9 canary và guard env/SQL đạt;
  6 Node tests tiếp tục đạt.
- Schema hiện hành tới `0027_fact_embedding_rebuild_audit.sql`; database tạm đã áp 27,
  lần hai no-op. Chưa áp dụng lên database cấu hình thật.
- Có CLI rebuild vector fact theo scope/snapshot manifest, dry-run mặc định, audit và
  rollback batch; giữ nguyên content/lifecycle, không dựng lại fact đã xoá/revoke.
- Restore archive synthetic schema 25 đã tái hiện lỗi và phục hồi, archive hash giữ
  nguyên; nâng lên schema 27 rồi 18 integration tests pass. Thêm smoke PG16 vào CI,
  chưa chạy Docker/CI thật ở đây.
- Baseline chỉ đọc lúc 09:27 ngày 15/10: PostgreSQL ConnectionRefusedError, Redis TimeoutError;
  chưa có số migration/data/cost/latency của môi trường đó. `.env` không được sửa.
- Golden vẫn 52/60; review độc lập, E4 benchmark/threshold, E7 calibration, SSO/proxy,
  on-call, Zalo soak và restore production/AOF vẫn thiếu bằng chứng nghiệm thu.

## Lịch sử cập nhật 13/10/2026

> Cập nhật thực thi **13/10/2026**. [Báo cáo hiện hành](execution-2026-10-13.md).
> **Gate A/B/C chưa nghiệm thu; chưa production-ready.**

- Full suite mới nhất: **1.518 passed, 29 skipped**, 12,66s; provider fake, PG 18/Redis 8 tạm.
- 29 skip cần embedding thật: fact 17, knowledge 5, semantic cross-thread security 7.
  Không có skip vì thiếu PostgreSQL/Redis trong lượt kiểm thử tạm.
- Mypy strict 291 file, Ruff, 6 import contracts, 9 canary và guard env/SQL đạt.
- Source tới migration `0026_restore_safe_vn_tsv.sql`; database tạm đã áp 26, lần hai no-op.
- Restore synthetic sau 0026 thành công; 40 integration/security test pass trên bản sao.
- Node UI recovery 6 test đạt; Prometheus 14 rule test đạt, Alertmanager schema đạt,
  ba profile Compose resolve/preflight đạt với env synthetic. Dashboard 19 panel.
- Database/Redis dự án thật không kết nối được lúc baseline 13/10; số document/fact,
  migration thực tế, chi phí/latency hiện tại trên môi trường đó **chưa đo được**.
  Không sử dụng các số 05/10 dưới đây như số đo mới.
- Golden 52/60, thiếu taxonomy coverage và review; test split chưa mở.
- Pool E7 có 72 candidate strings nhưng 14 parent poems và 60 synthetic variants;
  chưa có hai human reviewer/calibration. E8/RLVR giữ đóng.
- SSO/proxy/ownership proof, corpus provenance/re-ingest, quota/budget benchmark,
  notification/on-call, Zalo contract/soak và restore production/AOF vẫn chờ bằng chứng.
- Chưa sửa `.env`, áp migration/backfill trên database thật, gọi API trả phí hoặc deploy.

## Lịch sử đo05/10/2026

Các số và hạn chế dưới đây mô tả bản code tại ngày 05/10, không mô tả lượt kiểm chứng 13/10.

> Đo lại ngày 05/10/2026 lúc 22:24 (UTC+7), từ database local và JUnit của lượt test này.
> Chưa đo môi trường production. Đây không phải tuyên bố
> hệ thống đã sẵn sàng production.

- Commit nền: `8a13491386e1abcabe69b2157942ddb0180ba200 (dirty)`
- PostgreSQL: `available`
- Redis: `available`
- Migration mới nhất trong source/đã áp dụng: `0021_turn_upstream_failure.sql`;
  0021 chạy lần đầu `ran=1`, lần hai `ran=0`, tổng 21 migration.
- Full suite với embedding thật: `1370 passed, 0 skipped, 0 failed` (JUnit), 24,44 giây.
  Process test override rerank=fake để không gọi Voyage thật; không sửa `.env`.
- Ruff, mypy strict (266 file), 6 import contracts, guard env/SQL và 9 canary đạt.

## Phân loại skip lượt đo05/10

| Nhóm | Số lượng | Trạng thái |
|---|---:|---|
| Thiếu PostgreSQL/pgvector | 0 | Service hoạt động; không skip vì thiếu database |
| Thiếu Redis | 0 | Service hoạt động; không skip vì thiếu Redis |
| Thiếu API key/embedding thật | 0 | 28 test trước đây skip đã chạy với API OpenAI thật và pass |
| Platform/điều kiện khác | 0 | Không có skip thuộc nhóm này trong lượt đo |

## Dữ liệu và telemetry

- Document: 5
- Chunk: 405
- Fact: 1
- Message: 1.878
- 7 ngày: embedding small 907 calls/0 lỗi/`0.000733 USD`/p95 `750 ms`;
  embedding large 48 calls/0 lỗi/`0.000106 USD`/p95 `905 ms`.
- Voyage usage đo được: 3 calls, `0.000212 USD`, p95 `969 ms`. Chỉ ba request có
  usage hợp lệ được ghi, không bao gồm tám lỗi chưa đo billing; không suy thành
  provider error rate 0 hoặc tổng chi phí đầy đủ. Đây không phải hóa đơn provider.
- Chưa có lượt reply trong cửa sổ đo nên chưa có p50/p95 toàn turn hoặc cache hit.

## Provider và tính năng

- Sinh văn bản: `openai/gpt-4o-mini`
- Embedding: `openai/text-embedding-3-small`
- Rerank cấu hình hiện tại do người dùng thay: `voyage/rerank-3-lite`
- Đã chọn/tích hợp ứng viên chi phí thấp `voyage/rerank-3-lite` theo yêu cầu người dùng,
  key đã xác thực HTTP 200 bằng hai đoạn mẫu. Lượt benchmark Voyage thật đã được
  duyệt/chạy nhưng chưa hoàn tất: 11 calls, 3 có usage, 8 RuntimeError, dừng budget,
  12 câu chưa thử. Không đổi `.env`/`models.py`, corpus hoặc threshold trong lượt này.
  Cost toàn lượt unknown; reserved upper bound `0.09621256 USD`, không phải tiền đã trả.
  Cần xác minh rate limits; không tăng budget hoặc retry bằng lượt mới để né trần.
- Benchmark v5: dense/hybrid/hybrid+lexical top-1 đúng `0/22`, Recall@5 và candidate
  Recall `4,55%`; sparse `0%`. Chỉ `1/22` câu có annotation đúng trong candidate đầu
  vào rerank. Dataset/corpus metadata không đổi, 0 lỗi upstream; kết quả không đạt
  chất lượng. Log embedding gần hai lần ingest hiện hành ghi `text-embedding-3-large`,
  query đang dùng `text-embedding-3-small`: nghi vấn lệch model, chưa có provenance
  gắn trực tiếp với chunk để xác nhận. Phép thử query-only large mới: hybrid top-1
  `13/22`, dense `15/22`, Recall@5 cả hai `81,44%`, candidate Recall `82,58%` (19/22
  câu có hit), 0 lỗi; sparse vẫn 0%. Đây là bằng chứng mạnh về lệch model nhưng chưa
  backfill provenance hoặc thay runtime/query model. Xem bảng ở evaluation.md.
- Override embedding task-local bằng ContextVar, có reset khi lỗi và namespace cache
  theo model; không sửa frozen settings hoặc vectors. Benchmark có pacing tùy chọn,
  mã HTTP đã loại dữ liệu nhạy cảm; dừng ngay khi 401/403/429, không retry ngầm.
- Zalo: `polling`
- Web bind: `127.0.0.1`
- Cấu hình local thực tế: `WEB_AUTH_MODE=dev`; metrics scrape token chưa cấu hình.
- Web authentication/ownership: signed trusted-header v2 gắn method/path/query/body,
  nonce dùng một lần qua Redis chung và owner-only đã triển khai. V1 bị từ chối;
  Redis auth lỗi trả 503 fail-closed. Chưa cấu hình reverse proxy/backfill production.
- Xóa dữ liệu: transaction/cleanup/rollback có test; ownership và generation tombstone
  được giữ. Lock chung cho Web reply/maintenance/delete; xóa khi đang ghi trả 409;
  job cũ sau xóa không vào pipeline. Có test PostgreSQL thật.
- REST/SSE IDOR: 8 test HTTP không phụ thuộc embedding đã qua.
- Memory cross-thread, fact dedup/forget và RAG semantic tests đã qua với embedding thật.
- Golden corpus preflight chỉ đọc metadata: 52 câu/63 tham chiếu chunk đều tồn tại,
  thuộc phiên bản hiện hành và đúng scope; không đọc nội dung hoặc gọi provider.
  Đây không phải review đáp án hoặc nghiệm thu coverage/chất lượng.
- Eval/benchmark chặn chunk thiếu/cũ/sai scope trước provider. Eval mặc định development;
  test cần xác nhận riêng. Artifact tách từng category/mẫu số đo được/lỗi, giữ hash
  dataset/corpus/config/source; missing judgment bắt buộc không cho pass. Artifact
  không chứa query/answer/raw exception và không tự nghiệm thu Gate B.
- Cache query embedding v2 phân biệt provider/model/dimension; không đọc cache cũ
  không rõ nguồn, và từ chối vector cache sai kiểu/kích thước hoặc NaN.
- Heartbeat: worker/maintenance mỗi 30 giây, Zalo sau poll thành công.
- Queue depth, queue wait, tuổi enqueue gốc ARQ và wall-clock turn latency đã được instrument.
  Đo tuổi bị thiếu/lỗi/vượt 10.000 job trả incomplete, không giả thành queue rỗng.
- Stop reason/replied/fallback, số vòng ReAct/tool/lỗi tool và chi phí ghi nhận
  theo trace đã nối pipeline → worker → PostgreSQL → metrics.
  Retry im lặng không tính fallback; dữ liệu chưa đo giữ NULL/unknown.
  Counter giữ attempt cuối, chi phí cộng usage cùng trace qua retry.
  Domain error ReAct có service/kind hữu hạn cho timeout/auth/429/4xx/5xx/unknown;
  retry thành công xóa cause cũ, không suy từ nội dung lỗi.
- RAG tool có metadata found/empty/filtered/uncertain/error/cancelled/unknown,
  retrieval/rerank degradation và low confidence; lưu mỗi attempt, không suy từ text.
  Lỗi retrieval không biến thành “không có đáp án”; rerank lỗi/malformed dùng RRF.
  Test đường tool → PostgreSQL → metrics với dữ liệu tổng hợp đã qua.
- Prometheus: 12 rule parse/firing/boundary test đạt. Dashboard JSON có 17 panel;
  chưa nghiệm thu scrape và gửi thông báo trong stack production.
- Zalo inbox: lưu trước enqueue; replay khi queue lỗi; test rollback và crash giả lập
  sau Redis acceptance với PostgreSQL/ARQ thật đạt. Payload bị xóa sau queue acceptance.

## Blocker go-live

- E2 chưa qua backfill owner và reverse proxy production
  nên Gate A chưa đạt, dù các security test local đã chạy và không skip.
- Golden RAG có 52 câu và split ổn định, còn thiếu tối thiểu 8 câu/review người thứ hai;
  còn phải gán/review category chuẩn; đủ 60 câu chưa đủ chứng minh coverage.
  Threshold chưa được hiệu chuẩn (E3–E4).
- Người dùng đã cấu hình Voyage thật nhưng query runtime vẫn small và threshold
  `0.45` chưa hiệu chuẩn Voyage. Benchmark Voyage chưa hoàn tất; cần xác minh rate
  limits/billing chưa đo và provenance/model embedding trước chọn threshold/test.
  Không có quyết định phát hành hoặc tự chuyển embedding runtime sang large.
- Zalo delivery chưa qua soak/restart test (E6).
- Đánh giá thơ chưa có hai người chấm độc lập (E7).
- E5 chưa hiệu chuẩn SLA hoặc thử contact point thật. Exception ngoài ReAct
  (persist/poetry/worker) chưa đo cause chi tiết. Counter ReAct chưa bao gồm thơ;
  chi phí trace chưa bao gồm embedding `system` và đủ phí tool bên thứ ba.
  Tín hiệu RAG `uncertain` chưa chứng minh câu final thật sự hỏi lại người dùng.
- Inbox cứu được receipt đã commit, nhưng chưa chứng minh khôi phục tin khi process chết
  trước commit receipt hoặc remote send thành công nhưng chưa đánh dấu replied.
- Compose cần proxy auth và `METRICS_SCRAPE_TOKEN` hợp lệ trước khi vận hành.
- Restore drill trên bản sao production và nghiệm thu on-call chưa thực hiện.
- E8 vẫn bị chặn bởi E7 và quyết định GPU/ngân sách; chưa chạy huấn luyện.

## Tái tạo baseline

```text
uv run pytest -rs --junitxml=test-results.xml
uv run ruff check .
uv run mypy
uv run lint-imports
uv run python ops/guard_env.py
uv run python ops/guard_sql.py
uv run python ops/canary_import_rules.py
uv run python ops/baseline.py --junit test-results.xml
```

Khi Docker/PostgreSQL/Redis hoạt động, chạy migration hai lần rồi tạo lại ảnh chụp này.
