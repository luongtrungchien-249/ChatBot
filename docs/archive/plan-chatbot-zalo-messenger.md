# Kế hoạch triển khai AI Chatbot cho Zalo & Messenger

**Vai trò:** Senior AI Engineer
**Mục tiêu:** Một bot trả lời khi được mention (`@nam_chatbot`) trong nhóm chat Zalo và Messenger.
**Phiên bản:** 2 — đã bổ sung Zalo Bot Platform

---

## 1. Nguyên tắc kiến trúc

Sai lầm phổ biến nhất là viết hai bot riêng cho hai nền tảng. Lõi xử lý là **một** service duy nhất; Zalo và Messenger chỉ là hai adapter mỏng ở rìa.

```
Zalo Bot API  ─┐
Meta webhook  ─┼─→ Adapter → Normalizer → Core Engine → Claude API
(Zalo Personal)┘                             ↓
                                  Redis (memory, dedup, rate limit)
                                  Postgres (log, audit, cost)
```

**Contract chung giữa adapter và core:**

```ts
interface InboundMessage {
  platform: 'zalo_bot' | 'zalo_personal' | 'messenger';
  thread_id: string;
  sender_id: string;
  sender_name: string;
  text: string;
  is_group: boolean;
  mentioned_bot: boolean;
  reply_to?: { id: string; text: string };
  attachments: Attachment[];
  message_id: string;
  timestamp: number;
}

interface OutboundMessage {
  thread_id: string;
  text: string;
  reply_to?: string;
}
```

Adapter lo: verify chữ ký, ack nhanh, đẩy vào queue, gửi trả lời theo API riêng.
Core **không được biết** Zalo hay Messenger là gì.

**Stack đề xuất:**

| Thành phần | Lựa chọn | Lý do |
|---|---|---|
| Runtime | Node.js + TypeScript (Fastify) | SDK Zalo Bot API có bản TS; nếu cần `zca-js` sau này thì cùng runtime |
| Queue | Redis (BullMQ) | Nhẹ, đủ dùng, cùng chỗ với memory |
| Memory ngắn hạn | Redis, TTL 2h | Không cần bền |
| Log / audit | Postgres | Truy vấn cost, debug hội thoại |
| Deploy | Docker Compose → VPS | Đơn giản, dễ chuyển |

**Lưu ý hạ tầng:** đặt server ở datacenter Việt Nam. Zalo nhạy cảm với IP lạ, đặc biệt nếu về sau dùng đường Personal.

---

## 2. Ba đường vào Zalo — chọn đúng ngay từ đầu

| | Zalo Bot Platform | Zalo OA | Zalo Personal |
|---|---|---|---|
| Nơi tạo | bot.zaloplatforms.com | oa.zalo.me + developers.zalo.me | Tài khoản Zalo thường |
| Xác thực | Token tĩnh `id:secret` | OAuth + refresh token | Đăng nhập QR |
| Chính thức | Có | Có | **Không** (zca-js) |
| Xác minh doanh nghiệp | Không cần | Cần, vài ngày | Không |
| Chat 1-1 | Có | Có | Có |
| Chat nhóm | Có, còn đang hoàn thiện | Không | Có, đầy đủ |
| Rủi ro khóa tài khoản | Không | Không | **Có** |
| Chi phí | Miễn phí | Quota / gói Premium | Miễn phí |

**Kết luận:** dùng **Zalo Bot Platform** làm đường chính. OA chỉ cần khi bạn làm chatbot chăm sóc khách hàng cho doanh nghiệp. Personal chỉ khi Bot Platform không đáp ứng được yêu cầu nhóm và bạn chấp nhận rủi ro.

**Cảnh báo về group:** Bot API hỗ trợ nhóm nhưng phần này ở trạng thái thử nghiệm, các framework tích hợp đều ghi chú rằng trọng tâm hiện tại vẫn là hội thoại 1:1. Thiết kế sao cho nếu group ngừng hoạt động, bot vẫn dùng được ở DM.

---

## 3. Lộ trình theo phase

| Phase | Nội dung | Thời gian |
|---|---|---|
| 0 | Core engine + adapter giả (CLI) + test | 2–3 ngày |
| 1 | Zalo Bot Platform adapter | 2–3 ngày |
| 2 | Messenger adapter | 3–5 ngày |
| — | *Chờ Meta App Review (chạy song song)* | 1–2 tuần |
| 3 | Zalo Personal (tùy chọn, có rủi ro) | 3–4 ngày |
| 4 | Hardening: rate limit, monitoring, cost | 3–4 ngày |

**Tổng: 2–3 tuần** cho một người làm nghiêm túc. Nộp App Review của Meta **ngay ngày đầu tiên** vì đó là đường găng.

Đảo thứ tự so với bản trước: Zalo Bot Platform lên trước Messenger vì nó không cần duyệt app, làm xong trong một buổi tối, và validate được core engine sớm nhất.

---

## 4. Phase 0 — Core Engine

Viết trước, chạy được qua CLI, chưa động gì tới Zalo/Meta. Đây là phần quan trọng nhất và cũng dễ bị bỏ qua nhất.

### 4.1 Xử lý mention

```
1. is_group == false  → luôn trả lời
2. is_group == true   → chỉ trả lời khi mentioned_bot
3. Strip "@nam_chatbot" khỏi text
4. Nếu phần còn lại rỗng → trả lời hướng dẫn cách dùng
5. Nếu là reply của tin khác → kéo tin gốc vào ngữ cảnh
```

Phát hiện mention nên có hai lớp: đọc trường mention trong payload nếu có, đồng thời fallback regex `/@nam[_\s]?chatbot/i` trên text. Payload của các nền tảng không đồng nhất và hay đổi.

### 4.2 Memory

- Lưu **15 tin gần nhất** mỗi thread trong Redis, TTL 2 giờ
- Trong nhóm, prefix tên người gửi vào mỗi tin: `[Nam]: nội dung`
- **Không** nhét toàn bộ lịch sử nhóm — vừa tốn tiền vừa làm model lạc đề
- Key: `ctx:{platform}:{thread_id}`

### 4.3 Gọi Claude

System prompt cần nêu rõ:
- Tên bot và vai trò
- Đang ở trong nhóm chat Việt Nam, trả lời bằng tiếng Việt tự nhiên
- Ngắn gọn, dưới 4–5 câu trừ khi được hỏi chi tiết
- **Không dùng markdown nặng** — cả Zalo lẫn Messenger đều không render markdown
- Không bịa thông tin; không biết thì nói không biết

`max_tokens`: 500–800. Kiểm soát cả chi phí lẫn độ dài trả lời.

### 4.4 Fallback

Nếu API lỗi hoặc timeout > 15s → trả một câu ngắn thay vì im lặng.
Im lặng trong nhóm chat trông như bot chết, và người dùng sẽ spam mention.

---

## 5. Phase 1 — Zalo Bot Platform

### 5.1 Chuẩn bị

1. Truy cập `bot.zaloplatforms.com`, đăng nhập bằng tài khoản Zalo
2. Tạo bot mới — **tên bắt buộc bắt đầu bằng tiền tố "Bot"** (ví dụ: `Bot Nam`)
3. Điền danh mục, mô tả, ảnh đại diện
4. Token dạng `numeric_id:secret` sẽ được gửi qua **tin nhắn Zalo** cho bạn
5. Lưu token vào secret manager, không hardcode

### 5.2 Nhận tin

Hai chế độ, chọn một:

**Polling** (`getUpdates`) — dễ dev, không cần domain public, chạy được ở localhost. Dùng cho giai đoạn phát triển.

**Webhook** — production. Cần HTTPS công khai, `Content-Type: application/json`. Ổn định và tiết kiệm hơn.

Khuyến nghị: dev bằng polling, deploy bằng webhook, viết adapter hỗ trợ cả hai qua config.

### 5.3 Chống trùng lặp

Lưu `message_id` vào Redis, TTL 10 phút. Thấy trùng thì bỏ. Bắt buộc với cả hai chế độ.

### 5.4 Access control

Ngay từ đầu phải có, đừng để sau:

```
dmPolicy:    pairing | allowlist | open | disabled
groupPolicy: allowlist | open | disabled   (mặc định: allowlist)
```

Giai đoạn đầu **luôn để allowlist** — chỉ hoạt động trong nhóm bạn cho phép. Mở `open` khi đã có rate limit và cost control.

### 5.5 Gửi trả lời

`sendMessage` với `chat_id`. Tự chunk câu trả lời dài. Có API gửi ảnh và sticker nếu cần.

---

## 6. Phase 2 — Messenger

### 6.1 Chuẩn bị

- Facebook Page (bot chạy dưới danh nghĩa Page, **không dùng được profile cá nhân**)
- Meta Business account + Meta App loại Business
- Bật sản phẩm Messenger, subscribe webhook `messages` và `messaging_postbacks`
- Page Access Token (long-lived) + App Secret
- App Review cho scope `pages_messaging` khi ra production

### 6.2 Webhook verify (GET)

Meta gửi `hub.mode`, `hub.verify_token`, `hub.challenge`.
So khớp verify_token → echo lại challenge.

### 6.3 Webhook nhận tin (POST)

- **Bắt buộc** verify header `X-Hub-Signature-256` bằng HMAC-SHA256 với App Secret. Bỏ qua bước này là mở cửa cho spoofing.
- Trả `200` trong **dưới 2 giây**, xử lý bất đồng bộ. Timeout → Meta retry → trả lời trùng.
- Dedup bằng `message_id`, TTL 10 phút. Retry của Meta là chuyện thường xuyên, không phải trường hợp hiếm.

### 6.4 Gửi trả lời

- Send API, gửi `sender_action: typing_on` trước cho mượt
- Giới hạn **2000 ký tự** mỗi tin — phải tự chunk
- Cửa sổ **24 giờ**: trả lời trong luồng hội thoại thì không sao; chủ động nhắn ngoài cửa sổ thì không được
- Send API không tính phí theo tin nhắn

### 6.5 Rủi ro

App Review có thể mất 1–2 tuần và **hay bị từ chối lần đầu**. Chuẩn bị screencast demo luồng đầy đủ và mô tả rõ use case. Đừng để việc này đến phút chót.

---

## 7. Phase 3 — Zalo Personal (chỉ khi bắt buộc)

Chỉ làm nếu Bot Platform không đáp ứng được yêu cầu nhóm.

Hướng khả thi: `zca-js` — reverse-engineering web protocol của Zalo, đăng nhập QR, hỗ trợ nhắn tin và quản lý nhóm, có mention gốc. Đây là tích hợp **không chính thức** và tài khoản **có thể bị tạm ngưng hoặc cấm vĩnh viễn**.

Nếu vẫn làm, giảm thiểu rủi ro:

- Dùng **số điện thoại phụ**, tuyệt đối không dùng số chính
- IP Việt Nam cố định, không đổi liên tục
- Delay ngẫu nhiên **2–5 giây** trước khi trả lời, đừng phản hồi trong 200ms như máy
- Giới hạn cứng số tin gửi mỗi giờ
- Chỉ trả lời khi được mention, không tự chen vào
- Persist session cookie, tránh đăng nhập lại liên tục
- Coi tài khoản là **disposable** — viết sẵn quy trình khôi phục

Về kỹ thuật, adapter này chạy như long-lived process giữ kết nối, không phải webhook stateless. Core engine dùng chung.

---

## 8. Phase 4 — Hardening

### 8.1 Rate limiting (token bucket trên Redis)

| Tầng | Ngưỡng đề xuất |
|---|---|
| Per-user | 10 tin/phút |
| Per-thread | 30 tin/phút |
| Global | Đặt theo ngân sách |

### 8.2 Cost control

Log token in/out mỗi request kèm `thread_id` và `sender_id`. Đặt ngưỡng cảnh báo chi tiêu theo ngày.

> Một nhóm 50 người nghịch bot có thể đốt sạch ngân sách tháng trong một buổi chiều. Đây không phải giả thuyết.

### 8.3 Bảo mật

- Secret trong secret manager, không commit
- Verify chữ ký webhook trên mọi nền tảng có hỗ trợ
- Allowlist thread trong giai đoạn đầu
- Lọc prompt injection — bot public trong nhóm **sẽ** bị người ta thử moi system prompt. Ghi log những lần bị thử.

### 8.4 Monitoring

- Health check endpoint
- Alert khi webhook lỗi liên tiếp
- Alert khi Zalo Personal mất session
- Dashboard: tin/ngày, latency p95, chi phí/ngày, tỉ lệ lỗi

---

## 9. Checklist trước khi go-live

- [ ] Core engine có unit test, chạy được qua CLI
- [ ] Dedup message_id hoạt động trên mọi adapter
- [ ] Verify chữ ký webhook Messenger
- [ ] Allowlist thread đang bật
- [ ] Rate limit ba tầng đã cấu hình
- [ ] Cost alert đã đặt ngưỡng
- [ ] Fallback message khi API lỗi
- [ ] Chunk tin nhắn dài (2000 ký tự cho Messenger)
- [ ] System prompt yêu cầu không dùng markdown
- [ ] Secret không nằm trong repo
- [ ] Quy trình khôi phục khi mất token/session

---

## 10. Việc cần quyết trước khi bắt đầu

1. **Bot phục vụ nhóm bạn bè/nội bộ hay khách hàng doanh nghiệp?**
   Nội bộ → Zalo Bot Platform, bỏ hẳn OA.
   Doanh nghiệp → cân nhắc thêm OA cho luồng chăm sóc khách hàng.

2. **Group trên Zalo Bot Platform có phải yêu cầu bắt buộc không?**
   Nếu bắt buộc và tính năng chưa đủ ổn định → phải cân nhắc Phase 3 với đầy đủ rủi ro.

3. **Ngân sách API mỗi tháng?**
   Quyết định `max_tokens`, độ dài memory, và ngưỡng rate limit global.
