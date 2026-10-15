# Tài liệu dùng cho eval

Thư mục này **cố ý trống** trong repo.

Bộ eval phải chạy trên tài liệu thật của tổ chức, mà tài liệu nội bộ thì không nên
nằm trong git — nó đi theo mọi bản clone, mọi fork, và mọi lần lộ repo.

## Cách dùng

Đặt (hoặc symlink) bản sao tài liệu dùng cho eval vào đây. Workflow `.github/workflows/evals.yml`
sẽ nạp các tệp `.txt`, `.md`, `.pdf`, `.docx` kể cả thư mục con, trước khi chạy.
`evals/corpus/README.md` và `.gitkeep` không phải tài liệu benchmark và không được ingest.
Nếu không có tài liệu phù hợp, RAG eval **không chạy**; workflow ghi cảnh báo,
Summary và artifact `eval-status.json` với `reason=missing_corpus`. Trạng thái này
khác với một lượt đã đo nhưng trượt chất lượng và không nghiệm thu Gate B.

Trên CI, cách đúng là mount chúng từ một nguồn ngoài repo (artifact, object storage,
hoặc một checkout riêng có quyền hạn chế), không phải commit vào đây.

`.gitignore` đã loại trừ mọi thứ trong thư mục này trừ chính hai tệp `.gitkeep` và
`README.md`.

## Khoá dữ liệu và review

Kiểm tra coverage/schema không gọi API:

```text
uv run python -m evals.dataset_contract evals/dataset/golden.jsonl
uv run python -m evals.dataset_contract evals/dataset/golden.jsonl --prepare-review review-pending.json --author-id author-opaque-001 --reviewer-id reviewer-opaque-002
```

File thứ hai chỉ là mẫu **chưa review**: chứa hash dataset và từng record, không chứa
câu hỏi/đáp án. Người review phải đối chiếu nguồn/chunk/answerable, điền hash ID riêng
khác tác giả, `reviewed_ids`, các xác nhận và hash cấu hình đã khoá. Không dùng tên/email
thật làm ID. Hai ID khác nhau không chứng minh hai người độc lập; coordinator phải xác nhận.

```text
uv run python -m evals.runner --ragas --qua-cong-cu --print-config
uv run python -m evals.dataset_contract evals/dataset/golden.jsonl --review-manifest review-completed.json
```

Copy `locked_eval_config_sha256` từ lệnh offline vào manifest sau khi chốt development.
Hash lock bao gồm model, pipeline, thresholds và source code; không bao gồm tên split.
Dataset contract exit `1` khi manifest/schema sai; exit `2` khi thiếu coverage hoặc review;
exit `0` chỉ xác nhận declarations và coverage, không xác nhận chất lượng model.
Thay đổi dataset làm manifest cũ mất hiệu lực. Test runner yêu cầu manifest hợp lệ,
đủ coverage, cấu hình khớp lock và `--confirm-test`; các điều kiện này không tự cấp
quyền xuất dữ liệu hoặc ngân sách gọi provider. Không tạo đáp án/human attestation giả.

Artifact eval v2 tách measured/unknown/not-applicable/disabled cho từng metric; final
claim judge chỉ dùng `required_claims`/`forbidden_claims` đã ghi rõ. `neo` lịch sử vẫn
chỉ là anchor trong context. No-answer precision/recall dùng structured judgment về
hành vi từ chối, không suy từ regex. Tất cả judge cần human calibration; typed retrieval
metadata chỉ kiểm scope/version của evidence, chưa chứng minh citation cuối đúng.
