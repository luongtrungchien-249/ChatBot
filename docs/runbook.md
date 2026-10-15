# Runbook vận hành

> Cập nhật tiếp 15/10/2026: [báo cáo mới](execution-2026-10-15.md), migration tới `0027`.

## Rebuild vector fact legacy

Migrate `0027` trước, rồi inspect từng scope. CLI không in content/vector; repository
đọc content tại chỗ để băm snapshot. Giữ manifest trong nơi chỉ operator truy cập.

```text
uv run python -m main.cli memory-embeddings inspect web <thread_id>
uv run python -m main.cli memory-embeddings rebuild --manifest /private/facts.json
uv run python -m main.cli memory-embeddings rebuild --manifest /private/facts.json --apply --max-estimated-usd 0.01
```

Manifest JSON schema_version=1 cần `actor`, `reason`, `scope` gồm platform/thread_id,
`target_identity` copy chính xác từ inspect và `facts` chỉ gồm fact_id/subject_id/snapshot_sha256
đã đối chiếu. Không copy nguyên row inspect vào facts: schema từ chối field thừa.
Mặc định dry-run; tối đa 100 ID và tổng 8.000 UTF-8 bytes/batch; có thể chọn batch nhỏ hơn
hoặc cấu hình `--max-input-bytes` rõ ràng. Giá ước tính từ catalog local, không chứng nhận
billing/free credit. Provider trả phí yêu cầu ceiling và daily budget fail-closed;
chưa có reservation chi tiêu đồng thời. Apply gửi nội dung đã chọn tới provider hiện tại.

Sau network phase, transaction kiểm lại snapshot dưới Web/subject/row lock. Không sửa
content hay phục hồi fact revoked/deleted. Một lỗi hủy mọi update; không auto retry stale
manifest vì request provider có thể đã tính phí. Audit cuối gắn manifest hash làm snapshot
cũ hết hiệu lực. All-data deletion xóa audit cùng fact. Inspect lại sau apply; các fact
unknown/mismatch còn lại vẫn làm semantic recall của subject liên quan bị chặn.

## Restore archive cũ trước 0026

Chỉ dùng archive đã xác định nguồn và một target drill mới. Không restore dở rồi chạy
migrate để che lỗi. Nếu archive chứa function `public.vn_tsv(text)` cũ:

```text
uv run python ops/restore_drill.py /private/backup.dump --legacy-vn-tsv
uv run python ops/restore_drill.py /private/backup.dump --legacy-vn-tsv --execute-isolated --output /private/restore-evidence.json
```

Flag legacy yêu cầu TOC chính xác và chỉ vector/unaccent extensions. Tool restore
extensions, bootstrap function từ 0026 và restore phần còn lại; hash archive giữ nguyên,
artifact ghi override SQL hash, không tự mark migration. Sau restore hoàn chỉnh, chạy
migration thực tế trên bản sao trước khi xem xét cutover. Lỗi startup/cleanup không được
tính thành “lỗi archive dự kiến”. Output failure của restore_drill ghi
`restore_verified=false`; restore_smoke ghi `verified=false`; cả hai chỉ ghi error type.

Smoke PG16 mới chỉ dùng fixture synthetic, không nhận target/container/volume cũ:

```text
uv run python ops/restore_smoke.py
uv run python ops/restore_smoke.py --execute-isolated --output /private/restore-smoke.json
```

Docker image PG16 cần có sẵn; tool không pull image. CI đã có bước chạy và upload artifact;
chưa chạy Docker tại máy này. Kết quả PG18 local và synthetic smoke không thay restore
backup production, AOF, RTO/RPO và nghiệm thu của operator.

> Cập nhật 13/10/2026. Báo cáo kiểm chứng mới nhất: [execution-2026-10-13.md](execution-2026-10-13.md).
> Migration hiện hành tới `0027`; triển khai writer/API đồng bộ sau migration.

## Provenance và ownership legacy

Các lệnh inspect chỉ đọc metadata và không gọi provider:

```text
uv run python -m main.cli embeddings inspect
uv run python -m main.cli owners inspect
```

Thread không owner không được tự claim khi đã có message. Operator đối chiếu nguồn
ownership và lập file riêng, giữ nguyên snapshot hash từ inspect. Mẫu manifest:

```json
{"schema_version":1,"assigned_by":"operator-id","evidence":"ownership-proof-reference",
 "assignments":[{"thread_id":"legacy-thread","user_id":"verified-subject",
 "snapshot_sha256":"<64 lowercase hex từ inspect>"}]}
```

```text
uv run python -m main.cli owners backfill --manifest /private/owners.json
uv run python -m main.cli owners backfill --manifest /private/owners.json --apply
```

Lệnh đầu dry-run; lệnh sau ghi audit cùng manifest hash. Transaction khóa đúng thread,
từ chối owner đã có, thread thiếu, snapshot đổi hoặc writer đang bận; một lỗi hủy cả batch.
CLI không xác minh danh tính/độc lập của operator và không suy ra ownership từ display name.
Ownership mới cấp quyền đọc/xoá/SSE, nên chỉ dùng user ID đã đối chiếu với proxy thật.

Để attest vector legacy, manifest riêng phải có `schema_version=1`, `attested_by`,
`evidence`, `identity` (provider/model/dimensions/revision) và `documents`
(doc_id/version/checksum đúng inspect). Không lấy identity bằng cách đo Recall hoặc
nhìn 1024 chiều. Chỉ attest khi có bằng chứng provenance bên ngoài; nếu không có,
re-ingest bằng model đã chọn vào version mới với `--ep`, giữ scope và version cũ.

```text
uv run python -m main.cli embeddings attest --manifest /private/embedding-identity.json
uv run python -m main.cli embeddings attest --manifest /private/embedding-identity.json --apply
```

Dry-run không gọi model/ghi DB; apply khóa và kiểm tra lại checksum/version/dimension,
không ghi đè identity đã biết. Fact legacy vẫn audit/revoke theo ID được nhưng semantic
recall/forget/dedupe từ chối provenance unknown/mismatch. Đừng gán toàn bộ fact sang
model hiện tại; xác minh và tái tạo từng fact theo đúng scope/subject khi được phép.

## Migration mới và khôi phục

`0022/0024` thêm provenance nullable, không backfill; `0023` thêm số lần gọi poetry;
`0025` thêm audit gán owner; `0026` qualify function/dictionary trong `public.vn_tsv`.
Chạy migration trước restart API/worker. Giữ cột khi rollback code; không rollback
về code so sánh vector không provenance trên corpus đang trộn identity.

Restore synthetic 13/10 đã phát hiện `pg_restore` thất bại với function `vn_tsv` cũ
vì search_path hạn chế. Sau `0026`, archive mới restore được và 40 kiểm thử quan trọng
pass trên bản sao. Áp `0026` trước khi lấy backup mới. Backup cũ chứa function lỗi vẫn
cần quy trình legacy trên bản sao đã nêu ở đầu runbook; migration sau restore dở dang không sửa
được archive chưa hoàn thành. Giữ traffic đóng, không bỏ qua lỗi `pg_restore` hay tự
mark schema_migration. Khi thay dictionary unaccent, cần tái tạo generated TSV và GIN,
chỉ REINDEX không cập nhật giá trị TSV đã lưu.

Kết quả này dùng PostgreSQL 18/Redis 8 tạm và dữ liệu synthetic; production Compose dùng
PG 16/Redis 7. Vẫn phải thử backup production, Redis AOF, restore drill Docker và RTO/RPO
trong môi trường được duyệt trước go-live.

## Hai cách khởi động và network boundary

Development chạy API/worker trực tiếp trên host, với `NODE_ENV=development`,
`WEB_AUTH_MODE=dev`, `WEB_BIND=127.0.0.1`. Dev identity còn kiểm tra địa chỉ client
loopback; không nới kiểm tra này cho Docker bridge hoặc `X-Forwarded-For`.
Docker chỉ chạy PostgreSQL/Redis qua override dành riêng cho development:

```text
docker compose --env-file .env -f ops/docker-compose.yml -f ops/docker-compose.dev.yml up -d postgres redis
uv run python ops/deployment_preflight.py --development
```

Đặt `POSTGRES_PASSWORD` trong file riêng, đồng thời cập nhật mật khẩu trong
`DATABASE_URL` native. Chỉ override development publish hai port dữ liệu và cả hai
đều bind `127.0.0.1`. Không dùng override đó ở production. Đổi biến password không
đổi password của role trên volume PostgreSQL đã tồn tại: rotate role theo quy trình
DBA rồi cập nhật mọi consumer; không xóa volume để xử lý lỗi đăng nhập.

Container app dùng profile `app`; `zalo` là profile riêng, chỉ bật khi token/contract
đã được xác minh. Mọi process app được ép `NODE_ENV=production`,
`WEB_AUTH_MODE=trusted_header`, bind trong container `0.0.0.0:3000`.
`CONTAINER_DATABASE_URL` phải trỏ `postgres:5432/chatbot`, mật khẩu percent-encode
khớp `POSTGRES_PASSWORD`; `CONTAINER_REDIS_URL` trỏ `redis:6379`. DSN native dùng
localhost không được chuyển nguyên vào container. PostgreSQL/Redis base không publish
port ra host. Network Docker thuộc cùng trust boundary riêng tư; không gắn container
không tin cậy vào đó. API chỉ publish `127.0.0.1:3000` cho proxy trên host.

```text
uv run python ops/deployment_preflight.py
docker compose --env-file .env -f ops/docker-compose.yml --profile app run --rm worker uv run python -m main.cli migrate
docker compose --env-file .env -f ops/docker-compose.yml --profile app up -d
```

Khi cần polling, đặt `ZALO_POLLING_EXPECTED=true` cùng token hợp lệ; chạy preflight
với `--zalo` và thêm `--profile zalo` vào lệnh deploy. API nhận cùng expectation để
alert phát hiện poller không chạy. Flag này mô tả kỳ vọng của người vận hành, không
phải token presence và không tự khởi động process. Deployment chỉ Web giữ flag false;
một token đã cấu hình nhưng profile chưa bật không bị coi là outage.

Preflight chỉ đọc cấu hình Docker đã resolve, giữ output chứa secret trong memory,
không in DSN/key hoặc lỗi validation chứa giá trị. Exit 0 là cấu hình local hợp lệ,
không phải Gate A/B/C. Nó cố ý chỉ hỗ trợ topology dữ liệu bundled ở trên; triển khai
DB/Redis ngoài cần network/secret contract riêng, không sửa URL để vượt check.
Dừng nhận tin ở proxy, drain queue, rồi `docker compose ... stop` với cùng profile.
App có `stop_grace_period=150s`, lớn hơn timeout job hiện tại. Giữ persistent volumes.

## Process và migration

Chạy từ thư mục repo với dependencies đã cài:

```text
uv run python -m main.cli migrate
uv run python -m main.api
uv run arq main.worker.WorkerSettings
uv run arq main.worker.MaintenanceWorkerSettings
uv run python -m main.zalo
```

Dừng bằng SIGTERM/Ctrl+C và chờ job hiện tại kết thúc. Migration chạy theo filename;
chạy lần hai phải báo `ran=0`. Không sửa migration đã áp dụng. Khi rollback ứng dụng,
giữ schema tương thích; dữ liệu đã xóa không được phục hồi bằng rollback code.

Migration `0017` yêu cầu deploy đồng bộ API, reply worker và maintenance worker:
dừng nhận tin Web, drain queue trước khi nâng cấp, dừng mọi worker cũ, migrate rồi
khởi động toàn bộ bản mới. Không để worker cũ ghi bên cạnh API mới khi cho phép xóa.
Job Web legacy không có generation và chưa có tombstone sẽ bị loại fail-closed;
vì thế không bỏ qua bước drain. Nếu rollback về bản chưa có guard, phải đóng tính
năng xóa/traffic Web trước; giữ bảng generation và ownership.

Khi DELETE trả `409`, bot/maintenance đang giữ khóa thread: dừng hoặc chờ lượt hiện
tại xong rồi thử xóa lại. `204` chỉ trả sau transaction xóa commit. Reply/maintenance
của generation cũ sẽ bị bỏ qua. Không xóa tombstone để "dọn DB"; làm vậy có thể cho
job cũ chạy lại. Payload job cũ vẫn có retention trong Redis/ARQ cho tới khi được
xử lý/dọn theo cơ chế queue; đây chưa phải chứng nhận erasure cho mọi backup/queue.

Migration `0018` và `0019` chỉ thêm cột telemetry; chạy trước khi restart API/worker
bản mới. Rollback code giữ các cột này, không xóa bảng hoặc sửa migration đã chạy.
Chưa migrate thì metrics mới có thể lỗi query; không bỏ qua log `turn telemetry failed`.
Migration `0020` thêm bảng RAG telemetry; chạy trước khi nâng API/worker. Rollback
code giữ bảng; nếu quay về retrieval cũ có thể lại nhầm sự cố thành “không có đáp án”,
nên phải báo rõ trạng thái suy giảm hoặc tạm dừng RAG khi gặp lỗi tương ứng.
Migration `0021` bổ sung cặp failure_service/failure_kind nullable. Migrate trước
restart API/worker; rollback ứng dụng giữ cột. Không backfill nguyên nhân từ text.

## Trusted-header request v2

`WEB_AUTH_MODE=trusted_header` chỉ nhận chữ ký **v2**. V1 không còn được chấp nhận.
Proxy phải xác thực OIDC, xóa mọi header `x-cp-*` do client gửi (kể cả header trùng),
và ký từng request mới sau khi rewrite URL/body. Chặn đường truy cập trực tiếp,
bảo vệ TLS và áp giới hạn body tại proxy. Contract triển khai có ở
[`ops/proxy-contract.json`](../ops/proxy-contract.json); chưa có proxy OIDC production
hay mapping role của tổ chức trong repo. Issuer/audience/token validation và session
thuộc proxy; HMAC của app không thay thế OIDC login.

Header: `x-cp-user-id`, `x-cp-display-name`, `x-cp-roles`, `x-cp-issuer`,
`x-cp-timestamp`, `x-cp-nonce`, `x-cp-signature`. Nonce ngẫu nhiên mật mã tối thiểu
16 byte, encode hex lowercase 32–128 ký tự; tạo nonce mới cho mỗi lần gửi/retry/SSE
reconnect, không chuyển tiếp lại bộ header cũ. Timestamp là giây Unix, lệch tối đa 60s.

Canonical bytes là JSON array theo đúng thứ tự dưới đây, `ensure_ascii=True`,
`separators=(",", ":")`, encode ASCII; không trim/truncate field trước ký:

```text
["cp-web-v2", user_id, display_name, roles_raw, issuer, timestamp_raw,
 nonce, method, raw_path.hex(), query_string.hex(), sha256(body_bytes).hexdigest()]
```

`method` là method ASGI thực nhận; path/query là byte nguyên gốc mà API nhận, không
decode percent-encoding hoặc sắp lại query. Body là byte nguyên gốc, kể cả khoảng
trắng JSON. Chữ ký là hex lowercase của HMAC-SHA256 với `WEB_AUTH_HEADER_SECRET`.
Implementation tham chiếu: `src/adapters/web/auth.py::_canonical`; test tích hợp
`test_signed_request.py` xác nhận đọc body trong dependency không làm mất JSON ở route.

Sau kiểm chữ ký, Redis `SET NX EX 121` tiêu thụ nonce dùng chung mọi replica; hash key
không chứa identity/query/body. Replay trả 401; Redis lỗi/timeout 2s trả 503, không
fail-open. TTL bao phủ cả timestamp tương lai trong cửa sổ skew. Redis phải private,
không cho người dùng ghi/xóa nonce. Mất Redis state/restart/restore có thể làm mất
marker replay: giữ Web traffic đóng ít nhất 121s hoặc rotate secret đồng bộ trước
mở lại. Không rollback về v1 khi đang mở traffic. Scrape Bearer riêng không đổi.

## Backup và restore

Dùng `pg_dump -Fc` trên database production vào nơi lưu trữ hạn chế quyền truy cập.
Restore bằng `pg_restore` vào database mới, chạy migration và integration tests trên
bản sao trước khi chuyển traffic. Không restore đè production để thử nghiệm.
Redis queue cần AOF và persistent volume; xác minh cấu hình `appendonly yes` trước khi
chạy unattended. Sao lưu AOF theo quy trình Redis đang triển khai: với Redis 7 cần
giữ toàn bộ multipart AOF directory, manifest và các base/incremental file của cùng
snapshot nhất quán; không chỉ copy một file `appendonly.aof` khi Redis đang rewrite.
Quiesce producer/worker rồi stop Redis để snapshot volume, hoặc dùng snapshot storage
đã được kiểm chứng; restore vào volume/instance mới tách mạng, không restore đè queue
đang chạy. Redis backup còn payload nhạy cảm và replay nonce; áp retention/access policy
như PostgreSQL và giữ traffic Web đóng/rotate secret theo cửa sổ 121s ở trên.

Helper PostgreSQL mặc định chỉ mô tả kế hoạch; chấp nhận archive `pg_dump -Fc`, không
nhận target DSN/container/volume đang tồn tại:

```text
uv run python ops/restore_drill.py <backup.dump>
uv run python ops/restore_drill.py <backup.dump> --execute-isolated --output <report-moi.json>
```

`--execute-isolated` tạo tên container UUID riêng, dùng `--network none`, không publish
port, database tạm trên tmpfs 2 GiB và mount archive read-only. Nó restore vào database
trống, kiểm các bảng và row count, rồi xóa đúng container do nó tạo. Output tạo độc quyền
và không chứa nội dung/identity. Cần Docker, image pgvector PostgreSQL 16 đã có local và
archive tương thích. Archive lớn hơn tmpfs phải dùng quy trình drill riêng đã duyệt;
không nới helper để trỏ production. Drill này chưa chạy với backup thật trong lượt
13/10/2026 do không có Docker/backup được duyệt. Nó cũng chưa kiểm migration, application
integration, Redis restore hoặc RTO/RPO; phải nghiệm thu các phần đó trên bản sao.

## Sự cố

- Budget exceeded: xem `uv run python -m main.cli stats 1`; xác minh route gây tăng phí,
  dừng traffic bất thường trước khi tăng budget. Rotate API key tại provider, cập nhật
  secret storage và restart process để config mới có hiệu lực.
- Queue nghẽn: xem ARQ worker logs, queue depth và upstream timeout; giữ concurrency
  reply bằng 1 cho đến khi có kiểm thử FIFO theo thread.
- Zalo mất kết nối: kiểm tra 401/403 và token; 429/5xx cần backoff. Không bật webhook
  khi chưa có signature contract được xác minh.
- Provider lỗi: kiểm tra status, latency và budget; đổi provider/threshold về cấu hình
  đã có benchmark. Lexical rerank score không được dùng như score cross-encoder.

## Inbox Zalo

Sau migration `0016`, poller commit receipt PostgreSQL trước enqueue. Khi Redis lỗi,
receipt giữ payload để replay khi process chạy lại; mỗi batch tối đa 100 tin và enqueue
có timeout 30 giây. Chỉ chạy một poller để giữ thứ tự. Kiểm tra backlog bằng:

```sql
SELECT count(*) AS pending, min(received_at) AS oldest
FROM zalo_inbox WHERE queued_at IS NULL;
```

Không in/select payload vào log vận hành. Sau queue acceptance, payload bị xóa và chỉ
giữ message ID/timestamps chống trùng; hiện chưa tự GC marker. Không xóa pending receipt
để "thông queue". Nếu queue đã nhận mà transaction chưa commit, replay dùng cùng ARQ
job ID; kiểm thử crash giả lập cho tình huống này đã qua. Redis AOF/persistent volume
vẫn bắt buộc: inbox không giữ payload sau acceptance để thay thế backup Redis.

Chưa bảo đảm exactly-once khi remote send thành công nhưng process chết trước đánh dấu
replied, hoặc khi process chết sau nhận update nhưng trước commit receipt. Cần contract
ack/cursor, payload thật và soak/restart test trước Gate C.

### Synthetic fault/restart soak

```text
uv run python ops/zalo_soak.py --duration-s 10 --max-cycles 2 --output evals/results/zalo-smoke-moi.json
uv run python ops/zalo_soak.py --duration-s 10800 --output evals/results/zalo-lab-3h-moi.json
```

Runner tạo process Python mới mỗi cycle, override provider/token/DSN bằng cấu hình
synthetic, chạy adapter với HTTP transport trong memory và không gửi tin ra Zalo.
Nó kiểm empty poll, payload riêng/nhóm, enqueue failure, replay trước request sau
restart, send 429/5xx/401, chunk order. JUnit chỉ lưu số đếm; failure payload không
vào report. Lượt smoke 13/10 có hai cycle, mỗi cycle 39 test, không fail/error/skip.
Đây là smoke synthetic khoảng hai giây, không phải soak production vài giờ.

Một test cố ý ghi nhận remote effect trùng khi response mất sau remote commit:
send API hiện retry request không có upstream idempotency contract. Report luôn giữ
`gate_c_accepted=false`. Durable database/ARQ crash tests ở
`tests/integration/test_zalo_inbox.py` vẫn phải chạy với PostgreSQL/Redis biệt lập;
fresh mocked processes không chứng minh persistence của chúng. Không thêm cursor/
offset không được API hỗ trợ. Owner Zalo cần cung cấp contract và kết quả thử thật
cho cả receive-before-receipt và send-before-marker trước khi duyệt E6.

## Prometheus/Grafana

Tạo `METRICS_SCRAPE_TOKEN` ngẫu nhiên tối thiểu 32 ký tự trong secret storage/cấu hình
local, không dán vào Git hoặc lệnh có logging. API đọc token từ `.env`; Compose cần
nhận cùng giá trị để mount `/run/secrets/metrics_scrape_token`. Từ repo root:

```text
docker compose --env-file .env -f ops/docker-compose.yml --profile app --profile monitoring --profile alerts config --quiet
uv run python ops/deployment_preflight.py --require-alerts
docker compose --env-file .env -f ops/docker-compose.yml --profile app --profile monitoring --profile alerts up -d
```

Không dùng `docker compose config` không có `--quiet` trong báo cáo: nó có thể in secret.
Bearer scrape token chỉ đọc metrics, không cấp identity cho REST/SSE. Production vẫn
phải có proxy auth; compose giữ host bind localhost, không cấu hình proxy thay bạn.
Rotate token riêng, cập nhật API và Compose secret đồng bộ rồi kiểm tra scrape `up=1`.

Mười bốn rule gồm heartbeat worker/Zalo, backlog/queue age/age unavailable,
budget70/90, error ratio,
wall-clock latency, scrape down,
tỷ lệ fallback đã gửi và ba rule RAG no-result/error/degradation.
Runtime outcome/latency/queue wait là gauge cửa sổ 5 phút, không dùng `rate()` như counter.
Error ratio cần ít nhất 20 turn; ngưỡng 10%, 30s và backlog 100 là tạm thời. Dashboard
JSON có 19 panel; promtool firing/negative test cũ đã có kết quả lịch sử, nhưng chưa kiểm
thử notification thật. Rule hiện hành nằm trong `ops/alert-rules.yml` và gửi qua
Prometheus → Alertmanager → operator webhook. Provisioning xóa bốn Grafana rule cũ
và thay contact point trỏ chính `/api/health` bằng forwarding tới Alertmanager;
endpoint health đó không phải kênh nhận cảnh báo. Policy vẫn dùng cùng tên contact
point nên không để reference cũ trỏ tới receiver đã xóa.

Profile `monitoring` phục vụ dashboard; profile `alerts` bật Alertmanager. Đặt
`GRAFANA_ADMIN_PASSWORD` tối thiểu 16 ký tự; anonymous/login bypass đã tắt. Đặt
`ALERT_WEBHOOK_URL_FILE` thành đường dẫn tuyệt đối tới file ngoài Git chứa HTTPS URL
của receiver do người vận hành quản lý; URL được mount thành secret, không commit
URL/token. Receiver phải hiểu **generic Alertmanager webhook**, không cắm trực tiếp
Slack incoming webhook có payload khác. Cấu hình `url_file` và schema tham khảo
[tài liệu Alertmanager](https://prometheus.io/docs/alerting/latest/configuration/#webhook_config).
Nếu cần Bearer header riêng, mở rộng cấu hình với secret file theo contract của receiver;
không đưa token vào repo. Monitoring không bật `alerts` thì chỉ có rule/dashboard,
chưa có on-call nhận notification. Không coi scrape `up=1` là alert delivery thành công.

Trên môi trường được duyệt, chạy `amtool check-config /etc/alertmanager/alertmanager.yml`
trong container, thử mất heartbeat hoặc scrape, ghi alert name/thời điểm firing và
acknowledgement của người nhận; sau phục hồi xác nhận resolved cũng đến đúng nơi.
Kiểm runbook link có URL truy cập được ở nơi nhận; `/docs/runbook.md` hiện là đường dẫn
repo, chưa phải trang public. Không gửi alert thử tới người khác từ helper local.
Trong lượt 13/10 chỉ parse YAML và chạy test local; chưa có Docker/amtool, receiver
hoặc acknowledgement để nghiệm thu E5/Gate C.

Budget70 là warning khi tỷ lệ **chi đã ghi nhận / budget dương** đạt 70% và dưới 90%,
giữ 2 phút; Budget90 critical từ 90%, giữ 1 phút và thay rule exhausted cũ. Warning
được tắt tại critical để tránh báo hai mức cùng lúc. Không có dữ liệu hoặc budget
không dương không được suy thành tỷ lệ 0/100%. Đây là ngưỡng/hold time tạm, cần baseline
và thử notification trước vận hành. Panel đầu hiển thị tỷ lệ percentunit; panel USD
riêng giữ số tiền thô, không áp 0.7/0.9 USD lên một budget khác 1 USD.

`cp_process_expected{component="zalo"}` xuất kỳ vọng bật/tắt rõ ràng.
`cp_heartbeat_observed` phân biệt timestamp hợp lệ với chưa có/lỗi timestamp;
`cp_heartbeat_age_seconds` chỉ xuất khi có tuổi đo được. Khi Zalo expected=1,
observed=0 hoặc observed=1 và age>120s liên tục 2 phút mới báo missing/stale.
Expected=0 không báo outage, expectation/observation chưa có series không bị đoán
thành zero. Rule ghép `instance/job/component`, không lấy kỳ vọng API khác để chứng
nhận cùng poller. Panel heartbeat ẩn Zalo disabled; panel expectation hiển thị Disabled,
Expected hoặc Unknown. Rule tests mới gồm pending/firing, 70/90/120 boundary, day reset,
budget zero/missing và polling disabled/unknown/cross-instance. Ngày13/10 đã chạy
`promtool check rules` (14 rule) và `promtool test rules` thành công với promtool 2.53.5.
CI dùng image Prometheus3.1.0; cần kết quả CI đúng image triển khai và notification thật.
Reply worker và maintenance luôn được kỳ vọng trong profile app: observed=0 cũng
báo missing sau 2 phút, dù chưa từng có heartbeat hoặc timestamp malformed; tuổi
đúng 120s không báo stale. Vì vậy bỏ sentinel không làm mất cảnh báo lúc worker
chưa khởi động thành công.

`cp_runtime_turn_reason` phân biệt trả lời, lỗi, ngân sách, deadline, user stop,
max iterations, access/mention ignore, help/command, rate limit và thơ; không lấy
nội dung câu trả lời để suy đoán lý do. `completed` là pipeline xử lý xong, không
đồng nghĩa trả lời đầy đủ: kiểm tra thêm reason/replied. Fallback ở đây là câu báo
lỗi của pipeline, chưa bao gồm can thiệp output guard hay RAG không có đáp án.

`CPFallbackRateHigh` đòi ít nhất 20 phản hồi có đo fallback, tỷ lệ >10% trong cửa sổ
5 phút và giữ 2 phút. Retry im lặng không vào mẫu số; không nhầm với tỷ lệ lỗi worker.
Khi alert firing, xem reason và upstream error/latency/budget trước khi đổi provider.

`cp_queue_oldest_age_seconds` dùng enqueue timestamp gốc trong payload ARQ, không
dùng sorted-set score (score đổi khi deferred/retry). Bao gồm in-progress/deferred
giống queue depth. Mỗi scrape đọc tối đa 10.000 job/queue, batch 500, timeout 2s;
payload thiếu/lỗi hoặc vượt giới hạn thì bỏ age và xuất `cp_queue_age_complete=0`,
không giả tuổi bằng 0. Queue rỗng thật mới xuất age=0. Queue là snapshot không atomic;
job hoàn tất giữa scrape có thể gây gap tạm thời. `CPReplyQueueOld` dùng ngưỡng tạm
120s giữ 2m; `CPQueueAgeUnavailable` giữ 5m. Không coi 120s là SLA đã nghiệm thu.
Đọc serializer ARQ đòi Redis có cùng trust boundary riêng tư như worker (pickle).

`cp_runtime_upstream_failures{service,kind}` chỉ chứa nhãn hữu hạn. Phân loại từ
domain error ReAct: timeout, 401/403 auth, 429 throttled, 4xx client, 5xx server;
không biết status thì unknown, không đoán lỗi mạng. Retry thành công xóa nguyên nhân
attempt cũ. Lỗi API poetry và provenance memory có typed cause; persist/infrastructure vẫn chưa đo nguyên nhân;
không diễn giải thiếu series là không có lỗi.

Mỗi trace chỉ giữ kết quả/counter của attempt mới nhất; duplicate và job generation
cũ không ghi đè kết quả. ReAct iteration đếm lời gọi model đã bắt đầu, kể cả lỗi và
vòng nhắc tra tài liệu; không bao gồm route thơ. `NULL` là chưa đo, không phải 0.
Chi phí `recorded_cost_usd` cộng usage cùng trace qua mọi attempt, không đếm trùng
khi upsert. Đây là ước tính đã ghi nhận: embedding hiện dùng trace `system`, phí
tool bên thứ ba chưa liên kết đầy đủ; không dùng số này như hóa đơn tổng chi phí.

Query kiểm tra không cần đọc nội dung hoặc ID thread:

```sql
SELECT reason, count(*) AS turns,
       count(*) FILTER (WHERE replied AND fallback) AS sent_fallbacks,
       sum(react_iterations) AS react_calls, sum(tool_calls) AS tool_calls,
       sum(tool_errors) AS tool_errors, sum(recorded_cost_usd) AS recorded_cost_usd
FROM turn_telemetry WHERE created_at > now() - interval '5 minutes'
GROUP BY reason;
```

### RAG health

`cp_rag_requests` đo số lần gọi knowledge tool thực tế, không phải số người dùng/turn
hay final reply. Retry được đo như attempt khác; hai search pass trong cùng lần gọi
tool chỉ ghi một row. Caller text-only bên ngoài registry (ví dụ eval retrieval trực
tiếp) không tự tạo row vận hành. Không dùng `rate()` cho gauge cửa sổ 5 phút.

Outcome: `empty` là không có candidates khi retrieval khỏe; `filtered` là candidates
bị relevance filter loại hết; `uncertain` là công cụ đưa danh sách ứng viên; `found`
là đã trả chunks. `error` không được gộp với no-result, `cancelled` và `unknown`
không dùng để kết luận chất lượng. `uncertain` không chứng minh final hỏi lại thật.

Khi RAG lỗi/suy giảm tăng, kiểm tra PostgreSQL, embedding và rerank timeout trước.
Hai nhánh retrieval lỗi (hoặc nhánh sống không cho kết quả đủ dùng) phải báo chưa
tra cứu được, không khẳng định kho thiếu đáp án. Rerank lỗi/malformed giữ thứ tự RRF
và bỏ score filter; không xem score 0 của fallback như điểm relevance được hiệu chuẩn.
Stage `retrieval`/`rerank` có thể trùng; dùng `stage="any"` khi tính tỷ lệ suy giảm,
không cộng cả ba series. Low confidence là tín hiệu threshold hiện tại, không phải
phán quyết đúng/sai đã được review.

Alert RAG no-result >50%, ít nhất 20 attempt found/empty/filtered/uncertain, giữ 5 phút; error và
degradation >10%, ít nhất 20 attempt đo được không bị hủy, giữ 2 phút. Đây là ngưỡng
tạm thời, cần baseline production và E3/E4 trước nghiệm thu. Scrape một target API
cho dữ liệu DB dùng chung; không cộng bản sao API như các nguồn lưu lượng độc lập.

```sql
SELECT outcome, count(*) AS attempts,
       count(*) FILTER (WHERE retrieval_degraded) AS retrieval_degraded,
       count(*) FILTER (WHERE rerank_degraded) AS rerank_degraded,
       count(*) FILTER (WHERE low_confidence) AS low_confidence,
       percentile_disc(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms
FROM rag_telemetry WHERE created_at > now() - interval '5 minutes'
GROUP BY outcome;
```

Bảng không chứa query/nội dung/sender/thread; trace chỉ dùng drill-down nội bộ,
không thành metric label. Chưa backfill số liệu lịch sử hoặc tự dọn telemetry:
phải duyệt retention/GC trước production. Sink lỗi/timeout chỉ cảnh báo
`RAG telemetry failed`, không biến câu trả lời thành lỗi; không bỏ qua cảnh báo này.

## Cache embedding

Query cache dùng namespace `emb:v2:`, băm provider/model/dimension/query để không trộn
vector fake với OpenAI. Cache v1 không được đọc lại vì thiếu provenance; tự hết TTL
24 giờ, không cần `FLUSHDB` hoặc xóa toàn bộ Redis. Sau nâng cấp sẽ có cache miss và
phát sinh lượt embedding mới. Vector cache sai kiểu/kích thước hoặc không hữu hạn
được tính lại. Namespace này không thay thế việc re-embed dữ liệu PostgreSQL khi
đổi model/provider của corpus hoặc memory fact.

## Preflight và eval RAG

Kiểm tra schema/coverage và metadata corpus không gọi provider:

```text
uv run python -m evals.dataset_contract evals/dataset/golden.jsonl
uv run python -m evals.corpus_contract evals/dataset/golden.jsonl --output corpus-preflight.json
```

Chọn output mới, không ghi đè artifact. Khi báo chunk thiếu/cũ/sai scope, đối chiếu
annotation với corpus/version do chủ dữ liệu duyệt; không thay ID ngẫu nhiên để pass.
Preflight exit 0 chỉ xác nhận metadata, không nghiệm thu đáp án hoặc coverage.
Không chạy eval trả lời/chấm điểm trên dữ liệu chưa được duyệt gửi tới provider.
Eval mặc định development; test cần `--split test --confirm-test` sau khóa cấu hình.
Benchmark có `--preflight-only` chỉ đọc metadata, không gọi provider. Với dữ liệu
thật cần approval cụ thể rồi `--allow-provider-data`. Đã tích hợp provider `voyage`,
model `rerank-3-lite`; key phải là Voyage riêng. Người dùng đã cấu hình Voyage nhưng
đó chưa phải quyết định nghiệm thu: lượt live
chưa hoàn tất và threshold cũ chưa hiệu chuẩn. Query large cải thiện mạnh so small;
chỉ override benchmark, chưa đổi runtime/memory embedding.
V5 có candidate Recall trước rerank; nếu annotation không có trong candidate,
đổi reranker không cứu được phần recall thiếu. Kiểm tra provenance model corpus
so với query trước thử model khác; không suy từ dimension hoặc timestamp gần nhau
rằng tương thích. Không tự re-embed corpus/đổi `.env` để làm gate xanh.
Latency v5 dùng `perf_counter`; phân biệt cache-warm query với cold API/toàn turn.
Khi benchmark Voyage timeout hoặc thiếu usage, budget
reservation được giữ và có thể dừng sớm; không tự nâng `--max-rerank-usd` để đi tiếp.
Limit 0.10 USD mặc định chỉ cho tiền rerank/list price, không gồm embedding hoặc
account credits. Không giả missing billing thành 0; xem `rerank_cost` trong artifact.
`--embedding-model` là query-only/task-local, không re-embed corpus; không dùng cache
của model khác. `--rerank-interval-s` pace theo RPM/TPM account; phần chờ không tính
query/adapter latency. HTTP 401/403/429 dừng cả benchmark ngay trước call/retrieval
tiếp theo; xem provider stop/status và số câu bị skip. Không retry ngầm hoặc mở lượt
mới để né budget/billing unknown; xác minh Rate Limits của account trước chạy lại.
Trước gửi corpus, owner phải duyệt sharing/retention; xem chính sách Voyage trong
evaluation.md. Không dán key vào command line hoặc báo cáo.
Xem [evaluation.md](evaluation.md) cho artifact/cách đọc mẫu số, giới hạn metric và
quy trình giữ test set. CI local edit chưa thay thế artifact từ workflow thật.
Rollback công cụ eval về bản trước không thay dữ liệu/runtime; không dùng báo cáo cũ
thiếu preflight hoặc có metric unknown-as-pass để chứng nhận Gate B.

## Web và dữ liệu

Production dùng reverse proxy OIDC và signed identity headers. Không mở traffic trước
khi kiểm thử chữ ký, timeout và ownership. Thread cũ chưa có owner phải được gán theo
bằng chứng được duyệt. Ownership được giữ sau xóa để bảo vệ fact còn lưu và hỗ trợ
request DELETE lặp; không tự gán thread ID đó cho người dùng khác.

Request v2 đã bind method/path/query/body và chặn replay bằng nonce Redis; xem contract
ở đầu runbook. Proxy phải strip identity header của client, ký đúng v2 và được nghiệm
thu end-to-end trước mở Web production. Thread ID Web chỉ nhận
ASCII chữ/số, `_`, `-`, dài tối đa 200 ký tự để tránh alias/glob trong Redis key.

Xóa conversation giữ fact; `/data` xóa cả fact. Backup có thể còn dữ liệu đã xóa và
phải có retention riêng. Trước go-live, kiểm thử restore, alert contact point và
cross-user REST/SSE bằng identity thực của proxy.

## Kiểm tra sau deploy

Kiểm tra health, migration, gửi một câu hỏi, đọc SSE với đúng owner, thử identity khác,
metrics operator/Bearer scrape và queue drain. Rollback nếu có rò dữ liệu, lỗi trả lời tăng hoặc
latency vượt ngưỡng đã hiệu chuẩn. Gate A/B/C hiện chưa được nghiệm thu đầy đủ.
