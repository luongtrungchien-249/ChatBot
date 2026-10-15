# Trạng thái đánh giá

> Cập nhật tiếp 15/10: [báo cáo](execution-2026-10-15.md). Rebuild fact vector có manifest
> đã được kiểm chứng bằng fake/SQL; **không thay benchmark semantic hoặc hiệu chuẩn E4**.
> Golden vẫn 52/60, test split chưa mở, E7/E8 và Gate B chưa được nghiệm thu.

> Cập nhật 13/10/2026: **E3/E4/E7 và Gate B chưa nghiệm thu**.
> [Báo cáo đầy đủ](execution-2026-10-13.md); phần05/10 bên dưới là lịch sử.

Runner hiện đo final refusal và required/forbidden claims bằng structured judge,
no-answer confusion matrix và metric states; tool-mode Recall lấy typed evidence
theo policy first-k unique evidence trong thứ tự call. Evidence được truy xuất không
chứng minh citation/final grounded; LLM judgments vẫn cần hiệu chuẩn human.
Test split đòi reviewed dataset đủ coverage và locked config hash khớp review manifest.

```text
uv run python -m evals.dataset_contract evals/dataset/golden.jsonl
uv run python -m evals.runner evals/dataset/golden.jsonl --ragas --qua-cong-cu --print-config
```

Hai lệnh trên offline, không gọi provider. Contract hiện không đạt: 52/60, thiếu coverage
chuẩn và review manifest. `--print-config` chỉ xuất hash, không tự phê duyệt/khóa model.
Sau khi author/reviewer thật được xác định, chuẩn bị declaration bằng
`dataset_contract --prepare-review <new-path> --author-id <opaque-id>` và đối chiếu từng
record; template mặc định chưa attested. Không đổi ID để lựa split theo kết quả test.

Khi đủ dữ liệu/review và config được khóa sau development, lệnh test cần
`--split test --confirm-test --review-manifest <reviewed-manifest>` cùng các flag
pipeline/judge đã khóa. Các lệnh paid trong phần lịch sử phải bổ sung manifest này;
chưa chạy test split hoặc benchmark trả phí trong lượt 13/10.

Pool thơ staging mới ở`evals/results/2026-10-13/e7-candidates-v2.jsonl`, SHA-256
`5ac7ea35fee77774a63847a1ef8c864d00428cef37dfd056c4bb230e7cf1b3a5`.
Round ở`evals/results/2026-10-13/e7-round-v2/`:blind.json/private.json/rubric.json.
72 string khác nhau, sáu category × 12, ba thể × 24; chỉ 14 parent poems và 60 synthetic
variants. Cần human curation/kiểm quyền sử dụng, không coi pool này là72 mẫu chất lượng
độc lập. Hai reviewer phải dùng blind+rubric frozen, không xem metadata/machine score
trước chấm; raw output gắn cả hai hash. CLI yêu cầu reviewer kind human, hai ID khác
nhau, nhưng việc xác minh hai người thực sự độc lập thuộc quy trình bên ngoài.
Chưa có review scores hay repeated judge đủ sáu chiều; hard gate luôn chưa authorized.
E8/RLVR giữ đóng. Không sử dụng điểm judge/synthetic variants làm chứng cứ nghiệm thu E7.

## Lịch sử05/10/2026

> Cập nhật ngày 05/10/2026. Đây là trạng thái có thể kiểm chứng, không phải tuyên bố Gate B đạt.

## Golden RAG

- Dataset hiện tại: `evals/dataset/golden.jsonl`.
- Số câu: 52; không còn placeholder `VI DU`.
- Split SHA-256 theo ID: 24 development, 28 test.
- Schema mới hỗ trợ `expected_answer`, `required_claims`, `forbidden_claims`, `category`,
  `answerable`, `scope` và `notes`; runner vẫn đọc được schema lịch sử.
- Bộ kiểm tra từ chối ID trùng, chunk annotation trùng, scope rỗng, no-answer có chunk
  annotation và câu gần trùng từ vựng bị chia sang hai split. Chưa kiểm tra trùng semantic.
- Mã thoát `2` nghĩa là dữ liệu hợp lệ nhưng thiếu tổng số hoặc coverage; mã `1` nghĩa là
  schema/dữ liệu không hợp lệ.

Phân bố hiện tại theo nhãn lịch sử:

| Nhóm | Số câu |
|---|---:|
| tra_cuu | 10 |
| thuoc_tinh | 10 |
| quy_trinh | 10 |
| giao_tap_hop | 8 |
| xuyen_ngon_ngu | 7 |
| ngoai_kho | 4 |
| xung_dot | 2 |
| mo_ho | 1 |

## Blocker Gate B

- Còn thiếu ít nhất 8 câu để đạt mức tối thiểu 60.
- Nhóm xuyên ngôn ngữ mới có 7/10 và ngoài kho mới có 4/10.
- Nhãn lịch sử khác chưa được tự suy diễn sang `single_chunk`, `multi_chunk`,
  `distant_paraphrase`, `scope_version_adversarial`. Cần review/gán nhãn chuẩn;
  không chỉ thêm tám câu rồi coi đủ coverage.
- Chưa có xác nhận độc lập của người biên soạn thứ hai.
- Corpus thật không nằm trong Git; CI cần mount từ secret storage. Preflight metadata
  trên database local đã qua, nhưng corpus/version và đáp án vẫn cần chủ dữ liệu review.
- Threshold chưa được chọn trên development rồi xác nhận đúng một lần trên test.

Không tự thêm đáp án hoặc chunk ID để đủ số lượng: các trường này phải được viết từ tài
liệu thật và được người thứ hai đối chiếu.

## Preflight corpus chỉ đọc

```text
uv run python -m evals.dataset_contract evals/dataset/golden.jsonl
uv run python -m evals.corpus_contract evals/dataset/golden.jsonl --output corpus-preflight.json
```

Lệnh thứ hai không gọi LLM/embedding/rerank và không đọc nội dung tài liệu. Dùng một
transaction repeatable-read/read-only để kiểm tra annotation tồn tại, thuộc bản mới nhất
và nằm trong scope cho phép (`chung` hoặc scope record). File output phải chưa tồn tại.
Mã `1` là lỗi metadata/schema/DB; mã `2` là thiếu annotation hoặc không có câu hỏi;
coverage được kiểm tra riêng bởi lệnh thứ nhất, không suy từ preflight exit 0.

Lượt 05/10: 52 câu, 63 tham chiếu annotation, 0 lỗi metadata; fingerprint:
`aea8dd9f7f800c142e8f21b12cd8a60d85488ea977b252a344f598e325db6881`.
Đây là hash metadata document mới nhất (checksum/version/scope/số chunk), không phải
hash từng chunk/vector. Kết quả không chứng minh chunk trả lời đúng hoặc review độc lập.
Dataset contract vẫn exit `2` do coverage chưa đủ; không sửa dữ liệu để làm gate xanh.

## Artifact eval và khóa test split

Các lệnh dưới gọi provider có phí và gửi dataset/context để trả lời/chấm điểm;
chỉ chạy sau khi được duyệt dữ liệu và ngân sách. Chưa chạy chúng trên corpus thật
trong lượt triển khai này.

```text
uv run python -m evals.runner evals/dataset/golden.jsonl --ragas --qua-cong-cu --output eval-development.json
uv run python -m evals.runner evals/dataset/golden.jsonl --ragas --qua-cong-cu --split test --confirm-test --output eval-test.json
```

Mặc định chỉ chạy development. Lệnh test cần cấu hình đã khóa và xác nhận riêng;
CLI không tự chứng nhận việc khóa/review và không ngăn người vận hành lặp test.
Preflight chặn lỗi annotation/corpus trước gọi provider; dataset đổi trong preflight
cũng bị chặn. Scope khác `chung` vẫn cần fixture biệt lập, chưa được phép chạy tự động.

Artifact v1 có SHA-256 dataset/corpus metadata/config/source, commit/dirty, provider
và cấu hình model trả lời/model judge, threshold, pipeline/split; endpoint chỉ ghi hash,
không ghi API key/URL/DSN. Có tổng và từng category, kể cả category lỗi toàn bộ:
attempted/completed/failed, mean metric/mẫu đo được/mẫu completed chưa đo, p50/p95.
Mean chỉ tính mẫu có điểm, không che lỗi bằng mẫu số hoàn tất; một câu lỗi làm run fail.
Chi phí chưa đo giữ null. Không lưu câu hỏi, answer, tool output hay raw exception.

Thiếu judgment bắt buộc làm fail; Recall không áp dụng ở tool mode giữ null, không
được hiểu là đạt retrieval Recall. Answer Relevance vẫn chỉ tham khảo chưa hiệu chuẩn.
Corpus/dataset/source đổi hoặc không kiểm chứng được cuối lượt làm fail. Sau khi lượt
chạy bắt đầu, lỗi toàn lượt hoặc lỗi kiểm tra cuối vẫn giữ artifact; schema/preflight
fail trước lượt chạy không tạo eval artifact. File đã tồn tại không bị ghi đè.
`run_passed` chỉ phản ánh các ngưỡng đo hiện hành; `release_gate_b_accepted=false`
vì còn thiếu cost/no-answer judgments/scope-version answer violations/human review.

CI đã nối upload artifact kể cả eval fail; nightly vẫn chạy development qua tool,
không tự mở test split. Chưa push/chạy workflow trên GitHub hoặc mount corpus CI.

## Benchmark retrieval/rerank

`ops/benchmark_rerank.py` mặc định chỉ đọc development split. Chỉ dùng
`--confirm-test` sau khi đã khóa provider và threshold. Tùy chọn `--output <file.json>`
ghi artifact gồm config hash, phân bố score đúng/sai, top-1, kích thước candidate,
p50/p95, error rate và bảng quét threshold bước 0,05.

Artifact v5 giữ SHA-256 dataset và corpus metadata (document checksum/version/scope,
số chunk); kiểm tra corpus không đổi trong lượt chạy. Đây không phải hash nội dung từng
chunk/vector. MRR/NDCG/top-1 tính trên toàn bộ câu answerable, kể cả empty/error bằng 0;
no-answer có số câu đo được riêng. Lỗi nhánh retrieval không bị che thành fallback.
Artifact vẫn được ghi khi lỗi/không có chunk đúng, nhưng command báo thất bại.
Provider fake/lexical không được đề xuất threshold. Có lựa chọn `--retrieval-mode`
`dense|sparse|hybrid` và `--no-rerank`; bốn baseline development đã chạy, xem bảng dưới. Token/cost rerank
Voyage đã có usage đo được ở lượt live partial; tổng cost các request lỗi vẫn unknown,
không phải giá đầy đủ/1.000 query. Run lỗi/bị dừng budget/input đổi không quét hoặc đề xuất threshold.
Chạy mỗi cấu hình với artifact riêng, đối chiếu cùng dataset/corpus/embedding/top-k;
không sửa `.env` để đổi hai biến cùng lúc. Sparse dùng đúng nhánh production nên vẫn
gọi embedding để tính distance, không phải benchmark lexical không có chi phí embed.
Baseline `--no-rerank` không lọc relevance (`filter_policy=none`); false-positive đo
candidate hiện diện, không phải lỗi câu trả lời cuối. Fake có policy distance chưa
đo nên no-answer false-positive giữ null, không dùng score overlap để lọc.
Test split không quét hoặc gợi ý threshold. Dataset thiếu chunk annotation cho câu
answerable hoặc scope khác `chung` bị chặn trước gọi provider; scoped eval cần fixture
corpus/memory biệt lập, không chạy trên thread production.
Benchmark dùng cùng preflight metadata; chunk thiếu/cũ/sai scope hoặc corpus đổi giữa
các kiểm tra đầu bị chặn trước provider, không tạo performance artifact.
`--output` không ghi đè bằng chứng cũ.

Runner sử dụng cùng contract nghiêm, xử lý `answerable` thay vì nhãn lịch sử; Recall
không áp dụng giữ null, không mặc định 1 cho no-answer. Chỉ một câu upstream chạy
lỗi cũng làm exit 1, dù các câu còn lại vượt ngưỡng. Artifact config/category đã có,
nhưng no-answer judgments/scope-version answer gate/chi phí chưa đầy đủ; E3/E4 chưa đạt.

Đã có artifact Voyage thật nhưng incomplete; người dùng đã cấu hình runtime Voyage
và key xác thực. Query runtime vẫn small, threshold chưa hiệu chuẩn (xem lượt 22:24).
Baseline đã qua approval sau xác nhận thực thi; không tiếp tục ghi là thiếu consent
cho các lượt đó. Không thay `RERANK_MIN_SCORE` cho tới khi benchmark provider thật
hoàn tất; score lexical fallback được đánh dấu `score_is_calibrated=false`.

### Baseline development đã đo 05/10 lúc 13:11

Cùng 24 development: 22 answerable, 2 no-answer; 28 test chưa sử dụng. Embedding query
`openai/text-embedding-3-small`, 1024 chiều; input 20/nhánh, fusion tối đa 10, output 5.
Dataset hash `691939f1988a2ce725e55d544209400f0187d1abb301cb33b4203a6b30f04419` và
corpus metadata hash ở preflight phía trên không đổi. Bốn lượt cuối cache-warm,
`latency_clock=perf_counter`, không phải benchmark cold API hoặc latency toàn turn.

| Cấu hình | Top-1 đúng | Recall@5 | Candidate Recall | MRR | NDCG@5 | p50/p95 query (ms) | No-answer candidate FP |
|---|---:|---:|---:|---:|---:|---:|---:|
| Dense, không rerank | 0/22 | 4,55% | 4,55% | 0,0152 | 0,0227 | 4,43 / 4,93 | 2/2 |
| Sparse, không rerank | 0/22 | 0% | 0% | 0 | 0 | 2,27 / 3,00 | 0/2 |
| Hybrid RRF, không rerank | 0/22 | 4,55% | 4,55% | 0,0091 | 0,0176 | 3,50 / 5,18 | 2/2 |
| Hybrid + lexical fallback | 0/22 | 4,55% | 4,55% | 0,0114 | 0,0196 | 5,02 / 6,82 | Chưa đo policy distance |

0 lỗi upstream, dataset/corpus stable ở cả bốn cấu hình. Sparse exit 1 vì không có
annotation đúng; các exit 0 khác chỉ nói run hoàn tất, không phải chất lượng đạt.
Recall@1 đều 0. Ranked context precision@5: 0,91% ở dense/hybrid/lexical, sparse 0%.
Lexical adapter p50/p95 1,40/1,88ms. False positive là candidate hiện diện, không
phải judgment câu trả lời; không coi sparse toàn empty là thắng no-answer gate.

Artifact local cuối được giữ riêng, không ghi đè:

- `evals/results/2026-10-05/dense-no-rerank-v5-precise.json`
- `evals/results/2026-10-05/sparse-no-rerank-v5-precise.json`
- `evals/results/2026-10-05/hybrid-no-rerank-v5-precise.json`
- `evals/results/2026-10-05/hybrid-lexical-v5-precise.json`

Candidate Recall v5 là trung bình tỷ lệ annotation có trong tối đa 10 candidate trên
toàn bộ answerable; có số câu đo được/có ít nhất một annotation để không che lỗi.
Chỉ 1/22 câu có hit trước rerank ở dense/hybrid, nên reranker trên cùng candidate
không thể phục hồi các annotation còn thiếu. Recall@1 tính tỷ lệ annotation ở hạng 1,
khác top-1 accuracy với câu nhiều annotation. Ranked context precision là tỷ lệ
annotation trong danh sách trả về trước relevance filter, chưa phải Context Precision
sau threshold/LLM judge. Không có answerable giữ null; không đổi Gate B thành pass.

Chẩn đoán metadata/usage local cho thấy log embed cuối trong 10 phút trước ingest
của hai document current scope chung là `text-embedding-3-large`, khác query `small`.
179 vector đều 1024 chiều, không giống cấu trúc lặp của FakeEmbedder. Đây chỉ là
**nghi vấn lệch model**, vì schema chưa có provenance embedding liên kết trực tiếp
document/chunk; không suy từ dimension rằng hai model tương thích, cũng không dùng
usage gần timestamp làm backfill chắc chắn. Cần xác minh provenance trước đổi model
hoặc re-embed; chưa gửi corpus cho OpenAI hoặc sửa dữ liệu để làm Recall xanh.
Giữ runtime/threshold cũ; không nghiệm thu E4/Gate B từ các baseline thấp này.

### Lượt 22:24: đối chiếu query large và Voyage live partial

Thêm `--embedding-model text-embedding-3-large` chỉ override query trong task/process
benchmark: ContextVar reset khi kết thúc/lỗi, không sửa `.env`/frozen settings, không
re-embed corpus, không gửi corpus tới OpenAI. Cache phân biệt model. Dim vẫn 1024;
[API chính thức](https://developers.openai.com/api/docs/guides/embeddings) hỗ trợ
dimensions cho hai model. Không giả hai model tương thích chỉ vì cùng dimension.

24 development/corpus hash/top-k giống bảng small. Kết quả large:

| Cấu hình | Top-1 đúng | Recall@5 | Candidate Recall | MRR | NDCG@5 |
|---|---:|---:|---:|---:|---:|
| Dense, không rerank | 15/22 | 81,44% | 82,58% | 0,7538 | 0,7565 |
| Sparse, không rerank | 0/22 | 0% | 0% | 0 | 0 |
| Hybrid RRF, không rerank | 13/22 | 81,44% | 82,58% | 0,6856 | 0,7048 |
| Hybrid + lexical fallback | 11/22 | 78,03% | 82,58% | 0,6053 | 0,6407 |

Dense/hybrid có hit trước rerank ở 19/22 câu, 0 lỗi, dataset/corpus stable; sparse exit
1 vì không annotation đúng, ba lượt khác exit 0 nhưng Gate B false. Hybrid large
query cold p50/p95 281/959ms; dense và lexical dùng cache nên không so p95 như cùng
điều kiện cold. Dense/hybrid no-answer candidate FP 2/2 (không lọc relevance); sparse
0/2 do empty, lexical policy distance chưa đo. Không kết luận độ đúng câu trả lời.

Artifacts: `evals/results/2026-10-05/dense-large-development-v5.json`,
`sparse-large-development-v5.json`, `hybrid-large-development-v5.json`,
`hybrid-lexical-large-development-v5.json`. Log ingest large và Recall cải thiện mạnh
là bằng chứng lệch query model; chưa chứng minh provenance trực tiếp của mọi chunk.
Không đổi embedding runtime bởi model dùng cả memory/dedupe; cần xác minh trước
migration/re-embed. Không sử dụng 28 test để chọn model.

Voyage live với query small: artifact `voyage-development-v5.json`, 11 calls/3 có
usage hợp lệ/8 RuntimeError, budget stop và 12 câu chưa thử. Usage hợp lệ 10.628
tokens = 0.00021256 USD theo list price; tổng cost unknown, reserved upper bound
0.09621256 USD. Không tăng trần 0.10 USD hoặc tạo lượt mới để bỏ qua billing unknown.
Recall/top-1 thấp của lượt incomplete không dùng để quyết định provider/threshold
hoặc so với large như một phép thử chỉ đổi reranker. Không quét threshold/test.

Đã thêm HTTP status an toàn vào exception/log/artifact, stop toàn lượt ngay khi
401/403/429, ghi `provider_stop_reason`/`provider_skipped_questions`; câu chưa thử
giữ 0 trên mẫu số answerable. Lượt cũ chỉ có RuntimeError nên chưa chứng minh lỗi
429. `--rerank-interval-s` pace start-to-start, thời gian chờ không tính vào query
hay adapter latency; chưa thực thi lượt Voyage paced vì cần quota account và quyết
định cho billing unknown. [Xem Rate Limits](https://docs.voyageai.com/docs/rate-limits).
Không retry ngầm, nâng budget, mua credit hoặc thêm payment method.

### Lựa chọn provider chi phí thấp 05/10

Chọn **Voyage AI / `rerank-3-lite`** làm ứng viên theo yêu cầu chi phí thấp của người
dùng. Giá niêm yết `0.02 USD/1M token`, quota miễn phí ban đầu theo tài khoản; không
giả định credit còn lại. [Giá chính thức](https://docs.voyageai.com/docs/pricing).
Voyage công bố model mới có multilingual evaluation; đó không thay benchmark tiếng
Việt/corpus local. [Thông tin model](https://blog.voyageai.com/2026/09/30/rerank-3/).
Không tuyên bố rẻ nhất mọi provider hoặc đã thắng baseline.

Adapter dùng HTTP pool hiện có, timeout 15s, không tự retry/redirect, không truncate
âm thầm hoặc nhận document trong response. Index/score/order/usage được kiểm tra;
error body không vào log. Token đo được ghi usage route `rerank` với attribution
`system`, cộng daily budget theo list price; chưa liên kết chi phí với từng turn.
Sink best-effort timeout 2s; không dùng dữ liệu chưa đo như zero/bill chính thức.

Benchmark có `--provider`/`--model` ghi đè trong process, không sửa `.env`. Voyage
giới hạn `--max-rerank-usd` mặc định 0.10 USD/lượt, chỉ tiền rerank, không gồm
embedding/tax. Trước mỗi call giữ khoản dự phòng cho trần 600K token của API rồi
thay bằng usage hợp lệ. Timeout/missing usage giữ khoản dự phòng; chặn call tiếp theo
nếu vượt budget và dừng cả lượt, không tiếp tục trả phí retrieval những câu còn lại.
Không tăng limit hoặc dùng credit để vượt limit. Cost artifact tách token đo được,
list price estimate và khoản reserved; unknown billing giữ null.

Chỉ đọc metadata (không cần key, không gọi provider):

```text
uv run python ops/benchmark_rerank.py evals/dataset/golden.jsonl --provider voyage --model rerank-3-lite --preflight-only --output evals/results/2026-10-05/voyage-preflight-new.json
```

Preflight lịch sử trước khi có key: 24 development, 30 tham chiếu, 0 lỗi, key placeholder, 0 provider
calls; artifact local `evals/results/2026-10-05/voyage-preflight.json`. Không phải
kết quả chất lượng/cost API. Không chạy test split hoặc đổi threshold/runtime.

Sau khi owner xác nhận quyền xuất dữ liệu, cấu hình key Voyage riêng tại
`RERANK_API_KEY` (không gửi key vào chat/log) và xác minh retention của tài khoản:

```text
uv run python ops/benchmark_rerank.py evals/dataset/golden.jsonl --no-rerank --allow-provider-data --output evals/results/hybrid-baseline-new.json
uv run python ops/benchmark_rerank.py evals/dataset/golden.jsonl --provider voyage --model rerank-3-lite --allow-provider-data --max-rerank-usd 0.10 --output evals/results/voyage-development-new.json
```

`--allow-provider-data` là xác nhận quyền gửi question tới embedding và context tới
rerank; không tự thay approval của hệ thống hoặc chính sách chủ dữ liệu. Với rerank
thật, chưa có key thì dừng trước mọi call. Baseline ban đầu bị auto-review chặn;
sau user xác nhận thực thi đã xin lại approval và chạy được, không né lần từ chối.
Approval baseline không tự cho phép thêm corpus tới OpenAI, LLM judge hoặc test split.
Voyage cho phép opt-out lưu/training để có zero-day retention, cần account admin và
payment method; không tự cấu hình hoặc thêm payment method.
[Chính sách từ Voyage](https://docs.voyageai.com/docs/faq#what-are-your-policies-in-regard-to-protecting-customer-data).
Key đã xác thực và có lượt live partial phía trên. Retention tài khoản vẫn do owner
xác minh; không tự tạo account, thêm billing hoặc bật config production. Runtime
provider/model hiện do người dùng cấu hình; threshold chưa được chốt lại.

## Hiệu chuẩn thơ

`ops/cham_tay.py --prepare-round <thư-mục-mới> --round-id <id>` tạo round ẩn nguồn,
không ghi đè round trước. `blind.json` chỉ có ID/hash và bài thơ; `private.json` chứa
nguồn và điểm máy, chỉ dành cho người điều phối. Cần phân quyền storage trước chia sẻ.

`--review-round <round> --reviewer-one <jsonl> --reviewer-two <jsonl>` kiểm tra đủ bài,
không trùng ID và sáu chiều điểm hữu hạn 1–5, rồi xuất disagreement và Spearman với
từng reviewer/điểm trung bình. Các giá trị constant hoặc dưới ba mẫu giữ null.
Mỗi record có `id` và `scores` gồm `ngon_ngu`, `y_nghia`, `hinh_anh`, `cam_xuc`,
`sang_tao`, `san_sang`. Máy thiếu chiều hoặc score invalid được đếm, không bổ sung
điểm giả. `--machine-repeat <jsonl>` nhận run thứ hai (`id`, `scores`), đo tương quan
người và rank stability; phải dùng cùng judge/config/scale, do người điều phối xác nhận.
Report không tự cấp hard gate. Ngưỡng ổn định và agreement vẫn cần nghiệm thu bằng người.

Chấm tương tác (chỉ đọc blind.json, không đọc điểm máy):

```text
uv run python ops/cham_tay.py --score-round <round> --reviewer-id <opaque-id> --judgments-output <reviewer.jsonl>
```

Mỗi người dùng ID mã hóa và file riêng; tool lưu SHA-256 của opaque ID, chỉ append bài
đã chấm đủ sáu chiều, có thể tiếp tục hoặc `q` để dừng. Từ chối file của reviewer khác,
ID ngoài round và bài sửa sai hash. Không dùng tên/email thật làm CLI ID. Hai file
khác nhau chưa chứng minh hai người chấm độc lập; người điều phối vẫn phải xác nhận.

Lượt chuẩn bị 03/10 bị chặn đúng điều kiện: chỉ có 40 bài distinct, cần ít nhất 60.
E7 chưa đạt, E8 chưa được bắt đầu.
