# Kiểm chứng luật kiến trúc

Ba công cụ cưỡng chế 8 luật ở `ARCHITECTURE.md` §1. **Một luật viết sai vẫn chạy xanh** — nó chỉ đơn
giản là không bắt được gì, và bạn sẽ không biết cho tới lúc kiến trúc đã vỡ. Vì vậy mỗi luật phải được
**chứng minh** bằng một vi phạm cố ý.

```bash
uv run python ops/canary_import_rules.py
```

Script tạo file vi phạm, chạy công cụ tương ứng, kiểm tra nó **đỏ**, rồi tự xoá file.

**Chạy lại mỗi khi sửa `.importlinter` hoặc hai script guard.**

## Kết quả — 2026-09-06

Toàn bộ 8 luật bắt được vi phạm cố ý:

| Luật | Gốc | Canary | Công cụ | Kết quả |
|---|---|---|---|---|
| `L1: agents khong biet ha tang` | L1 | `src/agents/` import `infra.logger` | import-linter | bắt được |
| `L1: agents khong duoc goi tools` | L1 | `src/agents/` import `tools.registry` | import-linter | bắt được |
| `L1: agents khong doc config` | L1/L7 | `src/agents/` import `config` | import-linter | bắt được |
| `L5: moi adapter la mot hop kin` | L5 | `adapters/cli/` import `adapters.web` | import-linter | bắt được |
| `L5: adapter khong goi LLM` | L5 | `adapters/cli/` import `llm.models` | import-linter | bắt được |
| `L4: chi memory.repository duoc cham fact_repo` | L4 | `knowledge/` import `memory.repository.fact_repo` | import-linter | bắt được |
| `L4b: khong SQL nao cham memory_fact ngoai repository` | L4 | `knowledge/` chứa `"SELECT * FROM memory_fact"` | `ops/guard_sql.py` | bắt được |
| `L7: chi config duoc doc bien moi truong` | L7 | `infra/` gọi `os.environ.get(...)` | `ops/guard_env.py` | bắt được |

## Vì sao cần ba công cụ chứ không một

`import-linter` chỉ so khớp **import module**. Hai luật không diễn đạt được bằng import:

| Luật | Vì sao import-linter mù | Lớp bù |
|---|---|---|
| L7 | `os.environ` là **truy cập thuộc tính**, không phải import | `ops/guard_env.py` — duyệt AST |
| L4 | Câu SQL là **chuỗi ký tự**, không phải import | `ops/guard_sql.py` — duyệt AST |

`guard_sql.py` cố tình **bỏ qua docstring**: nhắc tên bảng trong tài liệu là hợp lệ, chạy SQL lên nó thì
không. Nếu quét text thô thì chính tài liệu giải thích luật lại làm luật đỏ.

## Hai lần canary cứu được kết luận sai

**Lần 1 — luật đúng, canary sai.** Lần chạy đầu báo hai luật L1 "chết". Chẩn đoán ra lỗi nằm ở chính
canary: file canary đặt tại `src/cp_assistant/agents/` dùng `...infra` (ba chấm, trỏ ra ngoài gói) thay
vì `..infra`. Luật vẫn tốt. Nếu chỉ tin `lint-imports` báo "kept, 0 broken" thì đã kết luận sai rằng L1
đang bảo vệ kiến trúc.

**Lần 2 — bỏ gói bao `cp_assistant`.** Khi mười tầng thành gói cấp cao nhất, canary phải chuyển sang
import **tuyệt đối**. Để nguyên `from ..infra...` thì file canary nổ ngay lúc import — công cụ vẫn trả
về mã lỗi khác 0, canary vẫn báo "SỐNG", nhưng nó đang đỏ **vì lý do sai**. Luật có thể đã chết mà ta
không biết.

Bài học chung: canary phải đỏ **vì đúng luật đó bắt được**, không phải vì bất kỳ lỗi nào.

## Một luật mới bắt được vi phạm thật

Hợp đồng `L1: agents khong doc config` được thêm ngày 06/09/2026 và **đỏ ngay lần chạy đầu**:
`agents/policy/access.py` import `GroupPolicy` / `DmPolicy` từ `config.schema`.

Cách sửa **không phải** khoét một ngoại lệ trong luật. Hai kiểu đó là từ vựng của miền nghiệp vụ chứ
không phải cơ chế cấu hình, nên chúng chuyển sang `agents/policy/access.py`, và `config/schema.py`
import ngược lên. Chiều phụ thuộc giờ là `config → agents`, đúng chiều, và không có chu trình vì
`agents` không import `config`.

Nếu chọn cách khoét lỗ, luật vẫn "xanh" mãi mãi và sẽ không bao giờ chặn được lần vi phạm thật tiếp theo.
