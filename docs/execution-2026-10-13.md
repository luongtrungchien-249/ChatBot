# Thực thi Execute_02_10 — 13/10/2026

Đã tiếp tục phần code, migration, công cụ quản trị và kiểm chứng local của
[Execute_02_10.md](Execute_02_10.md). **Chưa nghiệm thu Gate A/B/C và chưa go-live.**
Các bước cần tài liệu thật, review độc lập hoặc hạ tầng production được giữ trạng thái
chưa hoàn tất. Không gọi provider trả phí, gửi tin Zalo, sửa `.env` hay áp migration/backfill
lên database dự án thật trong lượt này. Worktree vốn đã dirty; chưa tạo commit/PR/deploy.

## Kết quả kiểm chứng

| Kiểm tra | Kết quả | Giới hạn |
|---|---|---|
| Full pytest sau sửa restore | **1.518 passed, 29 skipped**, 12,66s | Fake embedding/rerank; không chứng minh semantic quality |
| Web UI recovery | **6 passed** bằng Node test runner | Handler với network/DOM fake; chưa kiểm browser/proxy production |
| Mypy strict | **291 source files**, không lỗi | Bao gồm source, ops, evals, tests, RLVR hiện hành |
| Ruff | Pass | Toàn workspace theo cấu hình repository |
| Import contracts | **6 kept, 0 broken** | 9 canary bắt được vi phạm cố ý |
| Guard env/SQL | Pass | Giữ boundary config và memory repository |
| Migration | **26** áp dụng trên database tạm; lần hai `ran=0` | Database dự án thật không kết nối được lúc baseline; chưa áp dụng |
| Restore synthetic | Archive mới restore hoàn chỉnh; migrate `ran=0`; **40 passed, 0 skipped** trên bản sao | PostgreSQL 18; không phải backup production/Redis AOF/RTO/RPO |
| Prometheus rules | `check rules`: **14 rules**; `test rules`: SUCCESS | promtool 2.53.5; CI dùng image 3.1.0; chưa gửi notification thật |
| Alertmanager | `amtool check-config`: SUCCESS | Version 0.28.1; bản cấu hình giữ nguyên schema, thay đường dẫn secret bằng fixture synthetic |
| Compose | Dev, app, app+Zalo+monitoring+alerts đều PASS resolve và preflight | Compose 2.40.3, env synthetic; không build/deploy container hay xác minh SSO |

PostgreSQL 18.6, pgvector 0.8.1 và Redis 8.0.5 được giải nén từ gói chính thức vào thư mục
tạm trong WSL, bind loopback ở cổng 65432/65433. Không cài service hệ thống; chỉ database
`review` và bản sao mới được dùng. Deployment Compose vẫn là PG 16/Redis 7; CI và môi trường
triển khai phải kiểm chứng đúng các version đó.

29 skip đều do yêu cầu embedding thật: fact repository 17, knowledge 5 và cross-thread
semantic security 7. Không có skip vì thiếu PostgreSQL/Redis trong lượt full suite.
Các invariant scope/provenance mới cũng có integration với vector fake để kiểm SQL và
transaction; chúng không thay thế bảy kiểm thử bảo mật dựa trên semantic distance.

Artifact local, đang được Git ignore:

- `evals/results/plan-2026-10-13/full-suite-v4.xml`: lượt full cuối cùng.
- `evals/results/plan-2026-10-13/restored-integration-v2.xml`: 40 test trên bản restore hoàn chỉnh.
- `evals/results/plan-2026-10-13/compose-validation-v2.json`: ba profile với synthetic env.
- `evals/results/zalo-synthetic-smoke-2026-10-13.json`: hai process/cycle mới, mỗi cycle 39 test,
  không fail/error/skip; khoảng hai giây, không phải soak vài giờ.

Các artifact initial/v1 được giữ để thấy lỗi và lần sửa, không dùng chúng làm nghiệm thu.
SHA-256 archive restore-v2: `b28ecbc14f27ad11e1711d0169c0140568bc2fc0edec2bb73db83a61ef112f6b`.
Archive chỉ chứa dữ liệu synthetic và ở thư mục WSL tạm, không phải backup cần giữ lâu dài.

## Thay đổi đã tích hợp

**E1/E2 và bảo vệ đầu ra.** Mọi generated final, kể cả thơ và fallback, được gửi và lưu
cùng văn bản đã qua output guard, rồi xếp maintenance best effort. Thought progress cũng
được guard; history legacy guard bot rows theo input có reply ID tương ứng. HTTP chat giới
hạn28.800 ký tự; L1 không giữ nguyên một message quá lớn vượt context cap.

Web final được Redis MULTI cache/publish với TTL 300s, API subscribe trước khi đọc cache.
UI dedupe bằng reply ID, chỉ hoàn tất request đang chờ tương ứng, xử lý final đến trước
POST acknowledgement và bỏ response từ thread cũ. Reconnect đọc PostgreSQL history cho
request đang chờ đã quá TTL. Xoá thread dọn thêm final cache; cả cache và live final được
đối chiếu generation PostgreSQL, nên Redis DEL lỗi không phát lại final thuộc generation đã xoá.
Đây chưa phải replay stream
đầy đủ có cursor hoặc exactly-once; PostgreSQL vẫn là nguồn history, còn browser reload
có thể cần mở lại hội thoại để xem các final cũ.

CLI `owners inspect/backfill` dùng snapshot metadata và manifest operator cung cấp,
dry-run mặc định. Apply khóa thread, không ghi đè owner, kiểm snapshot lại, ghi audit
manifest hash và hủy cả batch khi lỗi. Chưa có manifest ownership thật để áp dụng.

**E3/E4.** Eval judge final-answer có JSON contract cho refusal và required/forbidden
claims; không suy refusal từ keyword. No-answer có confusion matrix và metric states
measured/unknown/not_applicable/disabled. Tool results có typed evidence để đo retrieval
Recall/scope/version; không coi evidence đã truy xuất là citation của final.
Review manifest gắn dataset hash và từng record; test split cần coverage, review và config
lock khớp. CLI `--print-config` hoạt động offline. CI thiếu key/corpus ghi NOT RUN artifact
và Gate B false, không ingest README như tài liệu QA.

Embedding identity được lưu trên document/fact mới và trong cache key. Legacy giữ NULL;
runtime semantic retrieval/memory từ chối unknown hoặc identity khác, thay vì so sánh
vector cùng chiều nhưng khác không gian. API/admin không bị chặn startup. Ingest đổi
identity cần `--ep` rõ ràng, tạo immutable version, giữ scope, khóa concurrent ingest và
lấy version tiếp theo từ mọi version. Hai nhánh hybrid chia sẻ query embedding trong
request; lexical có thể chạy text-only khi embedding lỗi và có trạng thái degraded.
Extractor DOCX đọc cả table/nested table theo document order.

CLI `embeddings inspect/attest` chỉ metadata, manifest exact ID/version/checksum,
dry-run mặc định; apply kiểm dimension và không overwrite identity đã biết. CLI không
xác minh bằng chứng ngoài hệ thống, cũng không tự gán model hiện tại cho dữ liệu cũ.
Fact dedupe chỉ skip normalized exact duplicate; similarity không còn tự thu hồi fact.
Thay thế explicit cần cùng scope/subject, identity hợp lệ và transaction revoke+insert.
Lỗi provenance qua MemoryPort được pipeline chuyển thành final rõ ràng và typed telemetry.

**E5/E6.** Đo riêng poetry call attempts trong migration 0023 và runtime metrics; deadline,
user stop, budget checkpoint áp dụng trước model/judge call, kể cả khi candidate recovery
bắt callback exception. Lỗi API poetry có typed failure và hành vi retry/fallback.
PostgreSQL usage và Redis budget được ghi độc lập: lỗi DB không bỏ qua budget counter.
Chưa có reservation cho request đồng thời/in-flight hoặc kế toán đầy đủ mọi phí tool.

Prometheus 14 rule và dashboard19 panel có budget70/90, expected Zalo heartbeat, age thực
hoặc observed=0; bỏ sentinel age giả. Polling disabled không bị báo outage. Compose phân
tách native dev/bundled production, private data ports, runtime env file, Grafana password
guard, graceful stop và optional polling expectation. Alertmanager dùng secret URL ngoài
Git, thay receiver health giả. Restore helper mặc định dry-run, chỉ xóa container được
xác minh đúng tên/image/task marker/immutable ID, kể cả docker run timeout sau tạo.
Zalo synthetic chaos/soak runner có lỗi mạng,429/5xx/401, replay và restart fake process.

**E7.** Có staging pool 72 string khác nhau, sáu category × 12, ba thể thơ × 24 và provenance
tới source/parent hash. Pool có 14 parent poems. Theo provenance của 72 record, có 2 legacy
generated,10 reference và 60 synthetic variants. Đây là stress pool đề xuất, không phải 72 mẫu độc lập hay
bằng chứng chất lượng model. Nhãn và quyền sử dụng chưa được review độc lập. Chỉ hai
record có machine score legacy; thiếu chiều rubric mới và cần chấm lặp với config frozen.

Round-v2 tách blind `{id,tho}` khỏi metadata private và rubric sáu chiều với anchors.
Raw review gắn blind/rubric hash; resume hoặc phân tích từ chối snapshot bị đổi.
CLI yêu cầu reviewer kind human, hai reviewer ID khác nhau, và không tự xác minh rằng
hai người thực sự độc lập. Có agreement, Spearman theo reviewer/mean, invalid rate và
rank stability lặp; report không tự cấp hard gate. Chưa có điểm của hai người và chưa
bật thêm luật thơ/reward theo dữ liệu này.

**E9 và lỗi tìm thấy khi restore.** `pg_restore --exit-on-error` ban đầu thất bại tại
generated TSV vì `vn_tsv` gọi unaccent không kèm schema. Các test chạy trên bản restore
dở dang bị loại. Migration 0026 qualify function/dictionary, giữ migration cũ nguyên vẹn;
archive mới restore thành công và 40 test trên bản sao pass. Backup cũ có function lỗi
vẫn cần quy trình riêng trên bản sao; lấy backup mới sau 0026 và thử restore trước release.
README/ARCHITECTURE/status/evaluation/runbook được cập nhật, lịch sử 05/10 giữ riêng.

## Trạng thái nghiệm thu theo plan

| Bước | Trạng thái hiện tại | Điều kiện còn thiếu |
|---|---|---|
| E0 | Baseline/local verification cập nhật | CI trên commit sạch và số đo môi trường đích |
| E1 | Invariant code/test đạt local; có restore synthetic | Deploy đồng bộ writer, backup/AOF retention và restore production |
| E2 | ACL/auth v2/manifest backfill có code/test | OIDC/proxy thật, mapping role, ownership proof và deployment security review |
| E3 | Metric/tooling được sửa; **dataset chưa đạt** | ≥60 câu từ corpus thật, category chuẩn, annotations/split review bởi hai người |
| E4 | Provenance và fail-closed có code/test | Xác minh/re-ingest corpus đúng identity, benchmark cùng corpus, quota/budget Voyage, threshold development, rồi khóa test |
| E5 | Rule/config test đạt local | Scrape thật, người nhận firing/resolved, ngưỡng SLA được hiệu chuẩn |
| E6 | Durable inbox tests local và smoke synthetic | Contract receive/ack/cursor/send thật, restart/crash và soak vài giờ; chưa exactly-once |
| E7 | Rubric/round/pool candidate chuẩn bị | Curation đủ mẫu phù hợp, hai reviewer human độc lập, repeated judge/calibration |
| E8 | **Chưa được mở** | E7 được nghiệm thu, baseline/reward định nghĩa, quyết định GPU/model/license/ngân sách |
| E9 | Docs/tools và restore synthetic cập nhật | Restore production/AOF/RTO/RPO, CI/deploy smoke và các gate phía trên |

Golden hiện vẫn 52 câu, split development24/test28. Thiếu coverage theo taxonomy chuẩn:
single_chunk15, multi_chunk10, distant_paraphrase10, cross_language3, unanswerable6,
scope_version_adversarial5; các số này là deficits, không phải số câu đang có.
Legacy labels chưa được tự đổi thành nhãn chuẩn. Review manifest chưa có; không bổ sung
câu hỏi hoặc điểm human bằng nội dung AI rồi coi đó là review độc lập.

Trình tự tiếp theo là operator xác minh corpus/provenance và ownership/proxy, hai người
hoàn thiện/review golden cùng pool thơ, rồi chạy development với ngân sách/quota đã rõ.
Chỉ sau hiệu chuẩn và khóa config mới mở test split. E8 giữ đóng tới E7. Go-live vẫn cần
alert receiver thật, soak Zalo và restore production; không dùng những test xanh ở đây
để thay các bằng chứng đó.
