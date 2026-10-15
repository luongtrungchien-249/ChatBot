# Tiếp tục Execute_02_10 — 15/10/2026

Đã hoàn thiện hai đường phục hồi còn thiếu ở E4/E9: rebuild vector fact legacy bằng
manifest và restore archive cũ chứa `vn_tsv` không an toàn với search_path hạn chế.
**Gate A/B/C chưa nghiệm thu; E8 vẫn đóng.** Không sửa `.env`, dữ liệu thật, gọi provider
trả phí hoặc gửi tin Zalo trong lượt này. Thay đổi trước đó trong worktree được giữ lại.

## Kiểm chứng

| Hạng mục | Kết quả |
|---|---|
| Full pytest | **1.549 passed, 29 skipped**, 15,22 giây |
| Static checks | Ruff đạt; mypy strict **299 file**; 6 import contracts, 9 canary, guard env/SQL đạt |
| Web recovery | 6 Node tests đạt |
| Migration database tạm | 27 migration; lần hai `ran=0` |
| Archive legacy | Tạo schema 25 có một chunk tiếng Việt; tái hiện restore lỗi, phục hồi bằng chính helper mới; archive hash không đổi |
| Upgrade bản phục hồi | Chạy thật migration 26/27, lần hai no-op; **18 integration tests passed, 0 skipped** |
| CLI recovery | Inspect → dry-run → apply với fake → từ chối replay manifest cũ; JSON stdout hợp lệ ở LOG_LEVEL=debug; fixture/audit được xoá sau kiểm tra |
| CI | Thêm smoke restore dùng image PG16 và upload artifact; YAML parse đạt; **chưa có run CI/Docker thật trong lượt này** |

PostgreSQL 18.6, pgvector 0.8.1 và Redis 8.0.5 được giải nén vào thư mục WSL tạm, dùng
loopback 65432/65433. Không cài service hệ thống. Provider fake chỉ chứng minh SQL,
transaction, phạm vi dữ liệu và control flow; chưa chứng minh semantic quality.
29 skip vẫn là các test cần embedding thật: fact repository 17, knowledge 5 và semantic
cross-thread security 7; không có skip do thiếu PostgreSQL/Redis trong lượt full này.

Baseline chỉ đọc từ cấu hình dự án lúc **09:27 ngày 15/10 (UTC+7)**: PostgreSQL
ConnectionRefusedError, Redis TimeoutError. Không đo được migration/data/cost/latency
của môi trường đó. Config vẫn là embedding small, Voyage lite, Web dev loopback và chưa
có metrics scrape credential. Không lấy số của database synthetic làm số môi trường thật.

Artifact local, được Git ignore:

- `evals/results/plan-2026-10-15/full-suite.xml`.
- `evals/results/plan-2026-10-15/legacy-restore.json`.
- `evals/results/plan-2026-10-15/legacy-recovered-integration.xml`.
- `evals/results/plan-2026-10-15/cli-rebuild-smoke.json`.

## E4: phục hồi vector fact có kiểm soát

`memory-embeddings inspect <platform> <thread_id>` chỉ xuất ID, subject, identity,
input size và snapshot hash. Để tính hash, repository đọc nội dung tại chỗ; nội dung và
vector không được xuất ra CLI hoặc ghi vào manifest.

Manifest bắt buộc có scope, target identity đúng cấu hình hiện tại, actor/reason và danh
sách chính xác `{fact_id, subject_id, snapshot_sha256}`. Mỗi batch tối đa 100 fact,
mặc định tổng input tối đa 8.000 UTF-8 bytes. Dry-run kiểm snapshot/schema/dimension,
target và chi phí ước tính, không gọi provider hay ghi DB.

Apply thực sự embed lại nội dung đã chọn, không attest vector cũ bằng suy đoán model.
Provider có phí đòi `--max-estimated-usd` và daily budget đọc được/chưa hết. Giá từ catalog
local chỉ là ước tính; guard này không phải billing guarantee hay reservation đồng thời.
Unknown price, input quá giới hạn, vector không hợp lệ, zero vector, thiếu migration hoặc
config đổi đều bị từ chối. Có timeout 30 giây cho phase provider.

Sau provider call, transaction giữ lifecycle lock của Web, subject lock theo thứ tự ổn
định và row lock; kiểm lại snapshot trước khi update. Fact bị xoá/revoke/đổi trong lúc
gọi provider không được dựng lại. Một row update lỗi hủy cả batch. Chi phí một request
đã gửi có thể vẫn phát sinh khi snapshot sau đó không còn hợp lệ.

Chỉ vector/identity và audit rebuild cuối cùng thay đổi. Fact ID, content, source,
confidence, created/reviewed/revoked state được giữ nguyên. Migration `0027` thêm
`embedding_rebuild_audit`: actor/reason, manifest hash, previous snapshot/identity và
target identity. Audit nằm trong row fact và được xoá theo all-data deletion. Đây là
audit lần rebuild cuối, không phải lịch sử mọi lần thay đổi.

Snapshot mới bao gồm audit này, nên manifest đã apply không thể replay ngay cả khi
provider trả cùng vector. Rebuild một subset không tự chứng nhận cả subject/thread đã
sẵn sàng: provenance guard tiếp tục chặn các fact còn unknown/mismatch.

## E9: archive legacy và CI

`restore_drill.py --legacy-vn-tsv` là lựa chọn rõ ràng của operator. Mặc định không tự
thay đổi định nghĩa trong archive. Chế độ legacy xác minh TOC có đúng một
`public.vn_tsv(text)` và hai extension vector/unaccent, từ chối cấu trúc mơ hồ hoặc
extension khác. Restore extension trước, tạo function từ migration 0026, rồi restore
các entry còn lại với single transaction; không sửa archive và không mark migration.
Cơ chế chọn entry theo TOC dùng `pg_restore --list/--use-list`, theo
[tài liệu PostgreSQL 16](https://www.postgresql.org/docs/16/app-pgrestore.html).

Table/data/sequence/index entry khác giữ nguyên thứ tự; không bỏ hàng lỗi rồi báo pass.
Archive được hash trước/sau, source SQL override có hash trong artifact. Restore mặc
định cũng dùng single transaction. Lỗi archive có type riêng, không bị nhầm với lỗi
startup/cleanup. Artifact thất bại ghi `restore_verified=false` và error type, không
ghi SQL/content/raw stderr. Cleanup vẫn chỉ xóa container đúng image/task marker/ID.

`ops/restore_smoke.py` tạo source synthetic schema 25 trong container mới không network,
dump, xác minh restore thường thất bại rồi thử override và kiểm data. Không nhận DSN,
container hoặc volume có sẵn. Default chỉ in plan; CI dùng `--execute-isolated` với
`pgvector/pgvector:pg16`, lưu artifact và luôn giữ production gate false.

Đã kiểm chứng helper thực tế trên PG18 tạm bằng archive schema 25 và nâng schema sau
phục hồi. Docker không có trong PATH tại đây, nên smoke dùng PG16 mới chỉ có code/unit
test và bước CI chuẩn bị sẵn; chưa được ghi nhận như một lần chạy Docker/CI thành công.

## Điều kiện chưa thay đổi

- Golden vẫn 52/60, chưa đủ taxonomy coverage và review độc lập; không mở test split.
- Corpus/fact production chưa được xác minh provenance hoặc rebuild thật.
- E7 vẫn chưa có hai human reviewer và repeated judge/calibration; pool candidate
  trước đó không phải bộ mẫu độc lập đã nghiệm thu. E8/RLVR giữ đóng.
- SSO/proxy, ownership proof, quota/budget benchmark, on-call notification, Zalo
  contract/soak, production backup/AOF/RTO/RPO và release CI vẫn chờ bằng chứng.

Thứ tự áp dụng khi môi trường thật sẵn sàng: backup theo runbook, migrate 27, inspect
và đối chiếu manifest, dry-run rồi apply đúng scope. Sau đó đo lại readiness và chạy
kiểm thử/provider benchmark phù hợp; không dùng kết quả fake để mở release gates.
