# Tài liệu dùng cho eval

Thư mục này **cố ý trống** trong repo.

Bộ eval phải chạy trên tài liệu thật của tổ chức, mà tài liệu nội bộ thì không nên
nằm trong git — nó đi theo mọi bản clone, mọi fork, và mọi lần lộ repo.

## Cách dùng

Đặt (hoặc symlink) bản sao tài liệu dùng cho eval vào đây. Workflow `.github/workflows/evals.yml`
sẽ tự nạp mọi tệp trong thư mục này trước khi chạy, và **bỏ qua trong im lặng nếu
thư mục trống** — lúc đó eval chạy trên kho tài liệu rỗng và mọi câu hỏi cần RAG sẽ trượt.

Trên CI, cách đúng là mount chúng từ một nguồn ngoài repo (artifact, object storage,
hoặc một checkout riêng có quyền hạn chế), không phải commit vào đây.

`.gitignore` đã loại trừ mọi thứ trong thư mục này trừ chính hai tệp `.gitkeep` và
`README.md`.
