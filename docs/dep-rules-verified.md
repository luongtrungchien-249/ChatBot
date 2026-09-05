# Kiểm chứng luật kiến trúc

Bảy luật trong `.dependency-cruiser.cjs` cưỡng chế 8 luật ở `ARCHITECTURE.md` §1. Một luật viết sai
cú pháp vẫn chạy xanh — nó chỉ đơn giản là không bắt được gì, và bạn sẽ không biết cho tới lúc kiến
trúc đã vỡ. Vì vậy mỗi luật phải được **chứng minh** bằng một vi phạm cố ý.

Chạy lại: `bash ops/canary-dep-rules.sh` — script tạo file vi phạm, chạy depcruise, rồi tự xoá.

**Chạy lại mỗi khi sửa `.dependency-cruiser.cjs`.**

## Kết quả — 2026-09-04

Toàn bộ 7 luật bắt được vi phạm cố ý (6 error + 1 warn):

| Luật | Luật gốc | Canary | Kết quả |
|---|---|---|---|
| `agents-khong-biet-ha-tang` | L1 | `src/agents/` import `infra/logger.js` | bắt được |
| `agents-khong-doc-env` | L7 | `src/agents/` import `config/_canary_secret.js` | bắt được |
| `adapter-khong-goi-adapter` | L5 | `adapters/cli/` import `adapters/zalo-bot/send.js` | bắt được |
| `adapter-khong-goi-llm` | L5 | `adapters/cli/` import `llm/models.js` | bắt được |
| `memory-fact-chi-o-repository` | L4 | `knowledge/` import `memory/repository/fact.repo.js` | bắt được |
| `khong-phu-thuoc-vong` | — | hai file trong `shared/` import lẫn nhau | bắt được |
| `khong-orphan` | — | (đang tự nổ sẵn: 53 warning từ stub chưa nối) | bắt được |

### Ghi chú về `adapter-khong-goi-adapter`

Luật này dùng back-reference `$1` bên trong negative lookahead:

```js
from: { path: '^src/adapters/([^/]+)/' },
to:   { path: '^src/adapters/(?!$1)([^/]+)/' },
```

Cú pháp này **hoạt động đúng** — dependency-cruiser thay `$1` bằng nhóm đã bắt trước khi biên dịch
regex. Đã kiểm chứng bằng canary, không phải bằng suy luận từ tài liệu.

### Ghi chú về `agents-khong-doc-env`

Luật chặn `src/(agents|adapters|memory|knowledge|llm|infra)` import `src/config/` **trừ**
`index`, `schema`, `policy`. Hiện `src/config/` chỉ có đúng ba file đó, nên luật **chưa thể nổ trong
thực tế** — canary phải tạo thêm `config/_canary_secret.ts` mới kích hoạt được. Luật đúng, nhưng
tác dụng của nó chỉ xuất hiện khi có người thêm file thứ tư vào `config/`.

## Lỗ hổng đã bịt bằng công cụ khác

L4 nói *"không câu SQL nào chạm `memory_fact` ngoài `memory/repository/`"*. dependency-cruiser so khớp
**đường dẫn module**, không đọc được chuỗi SQL — luật `memory-fact-chi-o-repository` chỉ chặn việc
*import* `fact.repo`, không chặn ai đó viết `SELECT ... FROM memory_fact` thẳng trong `knowledge/`.

Lớp còn thiếu: `npm run guard:sql` (`ops/guard-sql.mjs`), quét text toàn bộ `src/`, bỏ qua comment.
Đã kiểm chứng cả hai chiều: xanh khi sạch, đỏ khi có câu SQL thật ngoài `repository/`.
