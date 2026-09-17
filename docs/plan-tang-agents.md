# Tầng `agents/` — phân tích và plan thi công

> Ngày lập: 17/09/2026. Trạng thái: **đã thi công xong**; plan này là bản **đặc tả kỹ
> thuật ngược** — viết lại tầng này cần làm gì, theo thứ tự nào, bằng kỹ thuật gì.
>
> Phạm vi: **chỉ công nghệ**. Không có một dòng nội dung prompt, không có luật nghiệp
> vụ, không có câu chữ tiếng Việt nào của sản phẩm. Chỗ nào cần nội dung thì plan chỉ
> nói *"chuỗi hằng số, đặt ở đâu, ràng buộc gì"* — phần viết nội dung là việc khác.
>
> Dùng cho: dựng lại tầng này trên một dự án khác, onboarding người mới, hoặc rà lại
> xem bản đang chạy có còn đúng đặc tả không.

---

## 0. Tầng này là gì

`agents/` là **lõi nghiệp vụ**: nó quyết định *một tin nhắn vào thì chuyện gì xảy ra*.
Nó không biết Zalo là gì, không biết Postgres là gì, không biết OpenAI là gì.

| | |
|---|---|
| Quy mô | 39 tệp `.py`, **3.065 dòng** |
| I/O | **Không một dòng**. Không socket, không tệp, không `os.environ` |
| Phụ thuộc ra ngoài | Đúng **hai** gói: `shared/` (thuần) và `tho/` (thuần) |
| Thư viện ngoài | **Không có**. Chỉ `dataclasses`, `typing`, `re`, `unicodedata`, `asyncio`, `time` |
| Test | Chạy < 2s, không Docker, không khoá API |

Bốn luật kiến trúc định hình nó, và cả bốn đều **cưỡng chế bằng máy**:

| Luật | Nội dung | Cưỡng chế bởi |
|---|---|---|
| L1 | `agents/` không import `adapters` `infra` `llm` `memory` `knowledge` `tools` `config` | `.importlinter` hợp đồng 1 + 2 |
| L2 | Ra ngoài **chỉ qua** `agents/ports/` | Hệ quả của L1 + review |
| L3 | Mọi truy vấn memory nhận `ThreadScope` ở tham số **đầu tiên** | Chữ ký `MemoryPort` + `tests/security` |
| L8 | Mỗi tin có đúng **một** `trace_id` xuyên suốt | `InboundMessage.trace_id` + `logger.bind` |

**Chiều phụ thuộc bị đảo có chủ đích ở một chỗ:** `config/schema.py` import
`agents/policy/access.py` để lấy kiểu `GroupPolicy`/`DmPolicy`, chứ không phải ngược lại.
Vì đó là **từ vựng của miền nghiệp vụ**; đặt nó ở `config` thì `agents` phải import
`config` để biết kiểu của chính mình, và L1 mất hiệu lực.

---

## 1. Tám quyết định công nghệ áp cho TOÀN tầng

Đây là phần đọc trước. Mọi module bên dưới chỉ là áp dụng lại tám thứ này.

### 1.1 `@dataclass(frozen=True, slots=True)` cho mọi kiểu dữ liệu

Không dùng `dict`, không dùng `TypedDict`, không dùng class thường.

- `frozen=True` — giá trị bất biến. Một `InboundMessage` đi qua 15 stage mà không stage
  nào sửa được nó, nên không cần đọc cả đường ống để biết nó còn nguyên hay không.
- `slots=True` — chặn gán nhầm thuộc tính không tồn tại, và bớt bộ nhớ.
- Hệ quả: so sánh, hash, `repr` miễn phí; test viết bằng `==` trên cả object.

### 1.2 `typing.Protocol` thay vì lớp cơ sở trừu tượng

Port là `Protocol`, không phải `ABC`. **Khớp cấu trúc là đủ.**

Lợi ích cụ thể đã thu được: `structlog.BoundLogger` cắm thẳng vào `LoggerPort` mà không
cần một lớp adapter chỉ để thoả kế thừa. Implementation ở `infra/` **không import**
`agents/ports/` — chiều phụ thuộc sạch một chiều.

Không dùng `@runtime_checkable` trừ khi thật sự cần `isinstance` — và trong tầng này
không chỗ nào cần.

### 1.3 Tagged union + `TypeAlias`, so khớp bằng `isinstance`

Mỗi kết quả có nhiều nhánh thì khai **một dataclass cho mỗi nhánh** rồi hợp thành
`TypeAlias`:

```python
@dataclass(frozen=True, slots=True)
class Pass: ...
@dataclass(frozen=True, slots=True)
class Warn:
    tier: str
    retry_after_ms: int
@dataclass(frozen=True, slots=True)
class Silent:
    tier: str
    retry_after_ms: int

RateLimitOutcome: TypeAlias = Pass | Warn | Silent
```

Vì sao không dùng `Enum` + trường phụ: mỗi nhánh mang **dữ liệu khác nhau**, và union
cho phép `mypy --strict` thu hẹp kiểu sau `isinstance` — nhánh nào quên xử lý thì trình
kiểm kiểu bắt được, không phải người đọc.

Tầng này có **9 union** kiểu này: `MentionVerdict`, `MentionOutcome`, `Command`,
`CommandOutcome`, `RateLimitOutcome`, `LimitVerdict`, `LlmMessage`, `BotError`,
`ReactEvent`, `HandleResult`.

### 1.4 `Result[T, E]` ở biên, exception cho lỗi lập trình

`shared/result.py`: `Ok[T] | Err[E]`, kèm `TypeGuard` cho `is_ok` / `is_err`.

Ranh giới rõ: **lỗi upstream là kết quả bình thường của đường ống** (có câu fallback, có
quyết định retry) → trả về `Err`. **Lỗi lập trình** → `raise`.

Chỗ duy nhất dùng: `generate()` trả `Result[str, BotError]`.

### 1.5 Hằng số module, không đọc cấu hình

Tầng này **không được** import `config/`. Mọi con số cấu hình đi vào qua **tiêm phụ
thuộc** (`Deps`), mọi con số cố định là **hằng số module viết hoa** kèm chú thích nguồn gốc.

Quy tắc viết chú thích cho một hằng số: *con số này từ đâu ra, đo bằng gì, ngày nào, và
sai thì hỏng như thế nào*. Một hằng số không có ba thứ đó là một con số không ai dám sửa.

### 1.6 Hàm thuần + tiêm phụ thuộc qua tham số

Không có singleton, không có biến toàn cục mang trạng thái, không có framework DI.

- Mỗi stage là **một hàm** nhận đúng thứ nó cần.
- Orchestrator nhận **một** `Deps` frozen dataclass.
- `Deps` gom cả **6 port**, cấu hình đã phân giải, và **3 hook tuỳ chọn** (`Callable | None`).

Hook tuỳ chọn là cách tầng này nhận năng lực mà không sinh phụ thuộc: adapter nào có nút
dừng thì truyền `should_stop`, không có thì để `None` và nhánh đó tự tắt.

### 1.7 `Literal` thay cho `Enum`

`Platform`, `Effort`, `CheapRoute`, `ReplyRoute`, `FactSource`, `Muc`, `Loai`,
`BudgetLayer` — tất cả là `Literal[...]`.

Lý do: giá trị đi thẳng vào JSON payload của hàng đợi và vào cột `TEXT` của Postgres mà
không cần `.value`; và `mypy` vẫn kiểm được đủ chặt. `Enum` chỉ thêm một lớp bọc phải
gỡ ra ở mọi biên.

### 1.8 Cưỡng chế bằng máy, không bằng review

| Công cụ | Bắt được gì | Bắt hụt gì |
|---|---|---|
| `import-linter` | Import module sai tầng | Truy cập thuộc tính, chuỗi SQL |
| `ops/guard_env.py` (AST) | `os.environ` ngoài `config/` | — |
| `ops/guard_sql.py` (AST) | SQL chạm bảng nhạy cảm ngoài repository | — |
| `ops/canary_import_rules.py` | **Luật đã chết mà vẫn xanh** | — |
| `mypy --strict` | Nhánh union quên xử lý, `None` lọt | — |

Cái thứ tư là cái hay bị bỏ qua nhất: **một luật viết sai vẫn chạy xanh, nó chỉ đơn giản
không bắt được gì.** Canary tạo vi phạm cố ý cho từng luật và bắt buộc luật phải **đỏ**.

---

## 2. `domain/` — từ vựng, không hành vi

**Trách nhiệm:** kiểu dữ liệu mà mọi tầng khác nói chuyện qua. Không hàm nào có tác dụng phụ.

| Tệp | Dòng | Nội dung kỹ thuật |
|---|---|---|
| `thread.py` | 32 | `Platform` (Literal), `ThreadScope` (frozen), 3 hàm dựng khoá |
| `message.py` | 65 | `InboundMessage`, `OutboundMessage`, `StoredMessage`, `Attachment`, `ReplyTo` |
| `errors.py` | 73 | 6 dataclass lỗi → `BotError` union + 3 vị từ phân loại |
| `knowledge.py` | 35 | `RetrievedChunk` — **giá trị**, không phải hợp đồng |

### 2.1 Kỹ thuật: gói khoá thành object, đừng truyền rời

```python
Platform = Literal["zalo_bot", "zalo_personal", "cli", "web"]

@dataclass(frozen=True, slots=True)
class ThreadScope:
    platform: Platform
    thread_id: str
```

**Không bao giờ** truyền `platform` và `thread_id` như hai tham số rời. Lý do kỹ thuật:
không ai quên tham số thứ hai của một object, nhưng ai cũng có lúc quên tham số thứ hai
của một hàm — và ở đây quên nó là rò rỉ dữ liệu giữa các nhóm.

Đây là **cả chiến lược chống rò rỉ** nằm trong một kiểu dữ liệu 4 dòng. Nửa còn lại là
chữ ký của `MemoryPort` (§3.2).

### 2.2 Kỹ thuật: lỗi là dữ liệu có cấu trúc, phân loại bằng vị từ

```python
BotError: TypeAlias = RateLimited | BudgetExceeded | NotAllowed | UpstreamTimeout | UpstreamError | BadPayload

def is_config_error(e: BotError) -> bool: ...   # 401/403 — thử lại vô ích
def is_retryable(e: BotError) -> bool: ...      # 429 + 5xx + lỗi không rõ status
def is_silent(e: BotError) -> bool: ...         # nhóm nào im lặng hoàn toàn
```

Ba vị từ, không phải ba trường `bool` trong mỗi lỗi. Vì sao: chính sách retry là **một
quyết định**, và nó phải nằm **một chỗ**. Nhét `retryable=True` vào chỗ tạo ra lỗi nghĩa
là chính sách đó rải khắp codebase và sẽ lệch nhau.

Quy tắc mặc định phải chốt tường minh: **`status is None` → cho retry.** Lỗi mạng
thường không có status, và hướng lợi của sự nghi ngờ ở đây là thử lại.

### 2.3 Kỹ thuật: tách GIÁ TRỊ khỏi HỢP ĐỒNG

`RetrievedChunk` từng nằm cạnh `KnowledgePort` trong `ports/`. Port đó đã bị xoá; kiểu
dữ liệu thì không, vì nó vẫn được dùng.

**Luật rút ra, áp cho mọi dự án:** `ports/` chỉ chứa **Protocol**. Một `@dataclass` nằm
trong `ports/` là dấu hiệu nó bị đặt nhầm chỗ — nó là giá trị, nó thuộc về `domain/`.

Ngoại lệ hợp lệ: dataclass là **tham số hoặc kiểu trả về** của chính Protocol đó và
không ai ngoài nó dùng (`Fact`, `NewFact`, `ToolCall`, `ToolResult`…). Lúc đó để cạnh
Protocol là đúng, vì vòng đời của chúng gắn nhau.

---

## 3. `ports/` — toàn bộ bề mặt tầng này nhìn thấy

**Trách nhiệm:** khai báo *tầng này cần thế giới làm gì cho nó*. Ngắn là có chủ ý.

**Sáu port**, sau khi dọn 2 port chết (08/09/2026):

| Port | Dòng | Bề mặt |
|---|---|---|
| `LlmPort` | 132 | `reply()` (có tool, có route) · `cheap()` |
| `MemoryPort` | 93 | 8 phương thức, **tất cả** nhận `ThreadScope` đầu tiên |
| `ToolPort` | 76 | `specs()` · `call_many()` |
| `RateLimitPort` | 47 | `check()` · `should_warn()` · `within_daily_budget()` |
| `ChannelPort` | 14 | thuộc tính `max_message_chars` · `typing()` · `send()` |
| `LoggerPort` | 24 | 4 mức + `bind()` |

### 3.1 Luật vàng: thêm port là quyết định kiến trúc

Dự án này đã xoá **hai** port (`KnowledgePort`, `ClockPort`) vì lý do: chúng được khai
báo, được hiện thực, được tiêm vào `Deps` — và **không chỗ nào gọi**.

> **Một port chết còn tệ hơn không có port**, vì người đọc sau sẽ tưởng đó là đường đi
> thật và thiết kế theo nó.

**Kỹ thuật phát hiện:** grep từng phương thức của từng port xem có ai gọi không. Làm
định kỳ, không làm một lần. Xem §10.1 — hôm nay vẫn còn một đường chết cùng loại.

### 3.2 `MemoryPort` — ràng buộc nằm trong CHỮ KÝ

```python
class MemoryPort(Protocol):
    async def append(self, scope: ThreadScope, msg: NewMessage) -> None: ...
    async def recent(self, scope: ThreadScope, limit: int) -> list[StoredMessage]: ...
    async def facts(self, scope: ThreadScope, subject_id: str, query: str) -> list[Fact]: ...
    #  ... 8 phương thức, KHÔNG phương thức nào thiếu tham số đầu
```

Không có biến thể "tiện tay" bỏ `scope`. Không có phương thức `all_facts()`.

**Kỹ thuật cho thao tác nguy hiểm — tách thành ba bước có trạng thái:**

```python
forget(scope, actor_id, pattern) -> list[Fact]        # LIỆT KÊ ứng viên, không xoá
stage_forget(scope, actor_id, fact_ids) -> None       # ghi yêu cầu chờ, có TTL
confirm_forget(scope, actor_id, choices) -> int       # thực hiện, lấy-và-xoá nguyên tử
```

Ba điểm kỹ thuật:
1. `actor_id` là **người gõ lệnh**, và implementation tự suy ra chủ thể từ đó — **không
   bao giờ** nhận chủ thể từ văn bản người dùng. Đó là chỗ chặn "người X xoá của người Y".
2. Trạng thái chờ phải có **TTL** và phải **lấy-và-xoá nguyên tử** — một lần xác nhận chỉ
   dùng được một lần.
3. `choices` là số thứ tự trong danh sách đã liệt kê, rỗng = tất cả. Số ngoài danh sách
   **bỏ qua** thay vì ném lỗi — gõ nhầm một con số không được phép làm hỏng cả thao tác.

### 3.3 `LlmPort` — union cho lượt hội thoại

```python
LlmMessage: TypeAlias = UserMessage | AssistantMessage | ToolMessage
```

Kiểu phẳng `{role, content}` **không biểu diễn được** vòng ReAct: lượt assistant có thể
không có văn bản mà chỉ có lời gọi tool, và lượt tool phải mang `tool_call_id`.

Hai chi tiết kỹ thuật bắt buộc:
- `ToolCall.id` là **bắt buộc**, không `Optional`. API đối chiếu `tool_call_id`; thiếu
  một cái là cả request hỏng.
- `LlmUsage.input_tokens` khai rõ trong docstring là **phần tính giá đầy đủ, đã trừ
  cache**. Mỗi nhà cung cấp báo cáo một kiểu; việc chuẩn hoá thuộc về implementation,
  không thuộc về cho gọi. Không viết rõ thì hai bên hiểu hai nghĩa và hoá đơn lệch.

### 3.4 `ToolPort` — `call_many`, không `call`

```python
async def call_many(self, calls: tuple[ToolCall, ...], ctx: CallContext) -> tuple[ToolResult, ...]: ...
```

Model trả **nhiều** `tool_call` trong **một** message và chúng phải chạy đồng thời. Hợp
đồng: trả **đủ** số kết quả, **kể cả cái thất bại**.

`ToolDefinition` mô tả **nhiều hơn** thứ API cần — có `requirements` (tên biến env, hạn
mức, chi phí, timeout) và `failure_modes`. Phần thừa **không gửi lên model**; nó ở đó để
người đọc biết công cụ cần gì và hỏng kiểu nào mà không phải mở implementation.

Hàm `to_spec(definition) -> ToolSpec` cắt phần thừa. Kỹ thuật: **một kiểu giàu cho người,
một kiểu gầy cho máy, và một hàm chiếu giữa hai cái.**

### 3.5 `CallContext` — đi theo từng lần gọi, không nằm trong constructor

```python
@dataclass(frozen=True, slots=True)
class CallContext:
    scope: ThreadScope
    sender_id: str
    trace_id: str
```

Một `LlmPort` phục vụ mọi thread; không dựng một instance cho mỗi hội thoại. Ba trường
này là thứ bảng chi phí cần `NOT NULL`, nên bắt buộc ở **mọi** lần gọi.

---

## 4. `policy/` — luật thuần, không trạng thái

**Trách nhiệm:** quyết định *có trả lời không*, *đây có phải lệnh không*, *có được gửi
ra không*. Toàn bộ là hàm thuần, không I/O, không `async`.

| Tệp | Dòng | Kỹ thuật chính |
|---|---|---|
| `mention.py` | 99 | Regex sinh động từ cấu hình + mở rộng nguyên âm |
| `access.py` | 38 | Từ vựng chính sách + một vị từ |
| `command.py` | 127 | Bảng khớp chính xác + 3 regex, trả union |
| `injection.py` | 139 | Bỏ dấu rồi so khớp bảng mẫu, **ghi nhận không chặn** |
| `output_guard.py` | 139 | 4 luật có thứ tự bắt buộc |
| `autonomy.py` | 111 | Bảng dữ liệu **cưỡng chế được bằng test** |

### 4.1 Kỹ thuật: regex SINH RA từ cấu hình, không viết tay

Tên bot đến từ biến môi trường, nhiều tên ngăn bằng dấu phẩy. Bộ khớp phải:

1. **Sắp tên dài trước tên ngắn** — nếu không, tên ngắn khớp trước và nuốt mất phần đuôi.
2. **Mở rộng từng nguyên âm thành lớp ký tự có dấu.** Người Việt gõ có dấu trong khi
   cấu hình viết không dấu. Đây là kỹ thuật bắt buộc, không phải tiện ích.
3. **Cho gạch dưới khớp cả khoảng trắng** (`_` → `[_\s]?`).
4. **Chặn hậu tố** bằng `(?![^\W\d_]|\d|_)` — để một tên khác bắt đầu bằng tên bot không
   bị nhận nhầm. Dùng lớp chữ Unicode để chặn cả chữ có dấu.

**Vì sao mở rộng nguyên âm chứ không bỏ dấu cả hai vế rồi so sánh:** bỏ dấu làm **đổi độ
dài chuỗi**, nên mọi chỉ số vị trí lệch — mà ta còn cần bóc đúng đoạn mention ra khỏi câu
hỏi. Đây là một quyết định kỹ thuật có hệ quả thật.

**Phát hiện mention hai lớp:** đọc trường mention trong payload **và** regex dự phòng.
Payload các nền tảng không đồng nhất và hay đổi. Trên nền tảng hiện tại lớp một luôn trả
`False` nên lớp hai đang gánh toàn bộ — và test hợp đồng sẽ đỏ khi nền tảng thêm trường,
đó là lúc bật lớp một lên.

### 4.2 Kỹ thuật: từ vựng miền đặt ở `policy/`, `config` import ngược lên

```python
GroupPolicy = Literal["allowlist", "open", "disabled"]
DmPolicy = Literal["pairing", "allowlist", "open", "disabled"]
```

Đặt ở `config/` thì `agents/` phải import `config/` để biết kiểu của chính nó → L1 thủng
→ canary không bao giờ đỏ nữa. Đảo chiều là cách giữ luật.

Hàm kiểm tra vẫn **thuần**: nó nhận `frozenset[str]` đã nạp sẵn, nó không biết Postgres
tồn tại. Việc nạp là của tầng dưới, và nạp lại mỗi lượt để lệnh quản trị có hiệu lực ngay.

### 4.3 Kỹ thuật: parse lệnh — khớp chính xác trước, regex sau

```python
_EXACT: dict[str, Command] = {...}     # tra bảng, đã .lower()
_CONFIRM / _FORGET / _REMEMBER         # regex, thử theo thứ tự
```

Bốn ràng buộc kỹ thuật:
- Nhận **cả bản có dấu lẫn không dấu**. Người dùng gõ không dấu là chuyện thường, và một
  lệnh không nhận ra sẽ rơi vào model — tức người dùng tưởng đã xoá mà chưa xoá.
- Từ xác nhận phải **hẹp**. Một từ quá phổ biến sẽ bị gật đầu vô tình trong nhóm chat.
- Dấu câu là **tuỳ chọn**, nhưng một từ khoá đứng một mình **không** phải lệnh — phải có
  phần nội dung đi kèm, nếu không một câu hỏi bình thường sẽ bị nuốt thành lệnh.
- Đầu vào là văn bản **đã bóc mention** (đầu ra stage 2), không phải văn bản thô. Ghi
  điều này vào docstring — nó là một giả định ngầm dễ vi phạm.

### 4.4 Kỹ thuật: bộ dò tấn công — MỘT bảng mẫu, BA bề mặt, GHI NHẬN không chặn

```python
Loai = Literal["injection", "jailbreak"]
_MAU: list[tuple[str, Loai, re.Pattern[str]]]

def fold_diacritics(text) -> str: ...        # NFD + bỏ ký tự tổ hợp + thay 'đ' thủ công
def detect_injection(text) -> InjectionScan  # (suspicious, patterns, loai)
```

Bốn quyết định kỹ thuật:

1. **Một danh sách mẫu, ba bề mặt dùng chung** (tin nhắn người dùng, tài liệu lúc nạp,
   kết quả công cụ). Ba danh sách rời nhau là ba danh sách sẽ lệch nhau sau vài lần sửa.
2. **Bỏ dấu trước khi so khớp**, và mẫu viết **không dấu**. Người gõ thường không dấu;
   người đang dò thử lại càng hay không dấu. `'đ'` không tách được bằng NFD nên phải thay tay.
3. **Phân loại hai nhóm.** Chúng nói hai điều khác nhau về nguồn tấn công, và cần hai
   phản ứng vận hành khác nhau.
4. **Không chặn.** Chặn theo từ khoá vừa dễ vượt vừa tạo an toàn giả. Tầng này để **ĐO**.

**Tại sao module này phải nằm ở `policy/` chứ không ở `tools/`:** L1 cấm `agents/` import
`tools/`. Muốn ba bề mặt dùng chung thì nó phải nằm ở tầng mà cả ba đều với tới được.
Đây là một ví dụ mẫu về việc **luật kiến trúc quyết định chỗ đặt code**.

### 4.5 Kỹ thuật: output rails — bốn luật, và THỨ TỰ là bắt buộc

```
1. ĐỊNH DẠNG   bỏ ký hiệu markdown        <- CHẠY TRƯỚC
2. BÍ MẬT      che cứng, vô điều kiện
3. CÁ NHÂN     che CÓ ĐIỀU KIỆN
4. TRÍCH DẪN   ghi nhận, KHÔNG chặn
```

**Thứ tự 1 trước 2–3 là một lỗi đã trả giá.** Dấu che dùng ký tự sao; bộ lọc markdown coi
sao là chữ đậm và **bóc mất chính các dấu che**. Chạy sau thì câu trả lời ra ngoài trông
như bị cắt xén và không ai hiểu vì sao.

**Luật 3 là chỗ thiết kế đáng nhất:** che *có điều kiện* — chỉ che thứ bot **không nhận
từ người dùng ở lượt này**. Kỹ thuật: trích tập thông tin cá nhân từ văn bản người dùng,
truyền vào làm **danh sách cho phép**. Che tất cả sẽ cho ra câu trả lời vô dụng.

**Luật 4 cố ý không chặn:** chặn ở đó là đổi một lỗi **hiện** thành một lỗi **im lặng**.
Nó ở đó để đo tỉ lệ.

Kiểu trả về mang theo **dấu vết can thiệp**, không chỉ văn bản:

```python
@dataclass(frozen=True, slots=True)
class OutputVerdict:
    text: str                          # LUÔN dùng được, không bao giờ rỗng
    da_can_thiep: tuple[str, ...]
    loai_bi_mat: tuple[str, ...]       # ghi LOẠI, không ghi chính chuỗi
    loai_ca_nhan: tuple[str, ...]
    thieu_trich_dan: bool
```

Ghi **loại** chứ không ghi chuỗi bị che — **log cũng là một chỗ rò rỉ**.

### 4.6 Kỹ thuật: tài liệu CƯỠNG CHẾ ĐƯỢC

`autonomy.py` là một **bảng dữ liệu**, không phải chú thích:

```python
Muc = Literal["on-the-loop", "in-the-loop", "tiebreaker"]

@dataclass(frozen=True, slots=True)
class HanhDong:
    ten: str
    muc: Muc
    ly_do: str          # vì sao mức ĐÓ, không phải mức cao/thấp hơn
    dao_nguoc: str      # rỗng = không đảo ngược được

HANH_DONG: tuple[HanhDong, ...] = (...)
MUC_CUA: dict[str, Muc] = {h.ten: h.muc for h in HANH_DONG}
```

Ràng buộc trung tâm, kiểm bằng test: **việc không đảo ngược được thì không được phép ở
mức `on-the-loop`.** Thêm một hành động mới mà quên xếp mức → test đỏ.

**Kỹ thuật tổng quát:** khi một tài liệu mô tả hành vi, hãy biến nó thành **dữ liệu** và
viết một test đối chiếu dữ liệu đó với hành vi thật. Tài liệu không cưỡng chế được sẽ
lệch khỏi mã nguồn, và không ai biết lúc nào.

---

## 5. `prompt/` — ba tầng, hằng số, và cầu dao token

**Trách nhiệm:** dựng chuỗi gửi lên model. **Không** quyết định gửi hay không.

| Tệp | Dòng | Vai trò |
|---|---|---|
| `system.py` | 205 | Tầng 1 — hằng số, dùng cho mọi lượt |
| `instructions.py` | 87 | Tầng 2 — hằng số theo từng tác vụ |
| `context.py` | 161 | Tầng 3 — ghép mỗi lượt |
| `builder.py` | 43 | Render từng khối + `sanitize` |
| `budget.py` | 102 | Trần token từng tầng + ước lượng ký tự/token |

### 5.1 Kỹ thuật: tách ba tầng theo VÒNG ĐỜI

- Tầng 1 đi theo **mọi** lần gọi trên đường trả lời.
- Tầng 2 đi theo **đúng tác vụ** của nó.
- Tầng 3 **đổi mỗi lượt**.

Tách ra để sửa một tác vụ không đụng các tác vụ kia, và để bộ eval đo được từng cái riêng.

### 5.2 Kỹ thuật: tầng 1 và 2 phải là HẰNG SỐ, không nội suy

Không `f-string`, không `.format()`, không tên nhóm, không ngày giờ, không tên người dùng.

Hai lý do, và cả hai đều là lý do kỹ thuật:

1. **Tính tái lập.** Nội suy biến vào đó thì hai người hỏi cùng một câu nhận hai prompt
   khác nhau, và bộ eval mất ý nghĩa.
2. **Prompt caching.** Nhà cung cấp khớp theo **tiền tố**; đổi một byte ở đầu là mất cache
   của toàn bộ phần sau. Đo được: phần được cache chính là tầng 1, và input được cache rẻ
   hơn một bậc.

**Cách kiểm chứng caching thật sự đang ăn:** ghi số token đọc từ cache vào bảng chi phí,
rồi so con số đó với độ dài tầng 1. Bằng 0 kéo dài = tiền tố đã vỡ.

Thông tin động đi vào **khối riêng, đặt sau**.

### 5.3 Kỹ thuật: bọc thẻ + `sanitize` chống tự thoát

```python
_TAG_LOOKALIKE = re.compile(r"</?(the1|the2|the3)[^>]*>", re.IGNORECASE)

def sanitize(content: str) -> str:
    return _TAG_LOOKALIKE.sub("", content)
```

Mọi nội dung **không tin cậy** (tài liệu, kết quả công cụ, ghi nhớ) đều bọc trong thẻ có
thuộc tính nguồn, và **phải strip mọi chuỗi trông giống thẻ đóng của chính mình** trước
khi bọc. Không làm bước này thì một tài liệu chứa thẻ đóng sẽ tự thoát khỏi hộp — và đó
chính xác là cách người ta phá.

Áp cho **cả** kết quả công cụ, nơi rủi ro cao hơn vì văn bản do người lạ soạn.

### 5.4 Kỹ thuật: lịch sử hội thoại là LƯỢT THẬT, không phải khối văn bản

Đây là lỗi thiết kế đắt nhất mà tầng này từng mắc, nên nó phải nằm trong đặc tả:

```
SAI    nén cả lịch sử vào MỘT user message bọc trong thẻ dữ liệu,
       rồi chèn một lượt assistant GIẢ trước câu hỏi hiện tại

ĐÚNG   mỗi lượt là một message thật:  người dùng -> user,  bot -> assistant
```

Vì sao cách sai hỏng: lượt assistant **ngay trước** câu hỏi không bao giờ là câu bot vừa
nói. Và tệ hơn — tầng 1 dạy model rằng nội dung trong thẻ là *dữ liệu tham khảo*, nên câu
hỏi thật của bot vừa bị đẩy ra xa vừa bị gán nhãn "chỉ là tài liệu". Kết quả đo được:
model hỏi lại vòng tròn, không bao giờ hành động.

**Ranh giới phải vẽ rõ:** tài liệu / ghi nhớ / tóm tắt **là** nền → khối riêng. Lịch sử
hội thoại **không** phải nền → lượt thật.

Hai chi tiết kỹ thuật đi kèm:
- **Bỏ tin cuối của người dùng khỏi lịch sử** nếu stage ghi chạy trước stage đọc — nếu
  không, câu đang được trả lời xuất hiện hai lần.
- **Cắt theo lượt cũ nhất**, không cắt giữa một tin nhắn. Một lượt bị cụt nửa chừng còn
  khó hiểu hơn là không có nó.

### 5.5 Kỹ thuật: trần token là CẦU DAO, không phải chính sách

```python
BudgetLayer: TypeAlias = Literal["system", "knowledge", "facts", "summary", "recent", "question", "tool"]
TOKEN_BUDGET: dict[BudgetLayer, int] = {...}
CHARS_PER_TOKEN = 3.6      # ĐO ĐƯỢC, không đoán
```

Bốn quyết định:

1. **Đặt cao đến mức vận hành bình thường không bao giờ chạm.** Cửa sổ ngữ cảnh hiện đại
   rộng và input rẻ; cắt bớt ngữ cảnh là đánh đổi chất lượng lấy vài xu.
2. **Vượt trần thì cắt ĐÚNG tầng đó**, không đụng tầng khác.
3. **Luôn trả về số token đã cắt** để ghi log. Một lần cắt là **tín hiệu bất thường cần
   xem**, không phải chuyện thường ngày.
4. **Ước bằng tỉ lệ ký tự/token, không đếm token thật.** Đếm thật đòi `agents/` gọi ra
   ngoài (vi phạm L1) và thêm một vòng mạng cho mỗi tầng của mỗi câu trả lời.

**Tỉ lệ ký tự/token phải ĐO, và script đo phải nằm trong repo** kèm mẫu ngay trong script
— để đo lại là chạy một lệnh. Ước **thấp hơn** thực tế thì an toàn: trần tính ra chặt hơn,
tức cắt sớm hơn cần chứ không bao giờ để lọt nhiều hơn ngân sách.

Chốt chặn cuối cùng vẫn là ngân sách ngày, không phải trần này.

---

## 6. `pipeline/stages/` — mỗi stage một tệp, thuần, test riêng được

**Trách nhiệm:** một bước, một tệp. 11 tệp, từ **13** đến **314** dòng.

### 6.1 Kỹ thuật: stage trả UNION, orchestrator so khớp

Stage không tự quyết định gửi gì. Nó trả một union mô tả *chuyện gì đã xảy ra*, và
orchestrator quyết định hành động.

```python
MentionOutcome: TypeAlias = Ignore | ShowHelp | Ask
RateLimitOutcome: TypeAlias = Pass | Warn | Silent
```

Nhờ đó mỗi stage test được bằng một lời gọi hàm và một `assert isinstance`.

### 6.2 Kỹ thuật: stage mỏng là stage ĐÚNG

Ba stage chỉ **13–19 dòng** — chúng là điểm nối, và logic nằm ở `policy/` hoặc `prompt/`.

Vì sao không gọi thẳng `policy/` từ orchestrator: giữ **danh sách stage tường minh** để
đọc orchestrator là thấy đủ hình dạng đường ống. Một stage 13 dòng có giá trị **tài liệu**
cao hơn giá trị mã nguồn của nó.

Và nó cho phép **vùng ngữ cảnh dùng lại được ở chỗ khác** — vòng ReAct dùng lại chính
`ContextEnvelope` để ghép kết quả công cụ vào giữa các vòng.

### 6.3 Kỹ thuật: hoãn thao tác GHI qua ranh giới chốt chặn

Stage lệnh chạy **trước** rate limit để người dùng xoá được dữ liệu của mình kể cả khi bị
chặn. Nhưng lệnh **ghi** thì tốn tiền thật (nó gọi embedding).

Giải pháp kiểu: stage trả về một nhánh `DeferredWrite`; orchestrator **giữ lại**, chạy
qua rate limit và ngân sách, rồi mới thực hiện.

```python
CommandOutcome: TypeAlias = Answer | AskConfirm | DeferredWrite | NoCommand
```

**Kỹ thuật tổng quát:** khi một bước phải chạy sớm vì lý do A nhưng có một nhánh phải
chạy muộn vì lý do B, đừng tách bước — hãy để nó trả về một **ý định** và cho orchestrator
chọn thời điểm.

### 6.4 Kỹ thuật: vòng ReAct với chặn cứng đánh số

Stage nặng nhất (314 dòng). Cấu trúc:

```python
for iteration in range(1, max_iterations + 1):
    # chặn 4: kiểm ngân sách LẠI, mỗi vòng
    # chặn 3: deadline treo đồng hồ
    # chặn 6: cờ dừng của người dùng
    # vòng cuối KHÔNG trao tool nữa
    result = await llm.reply(...)
    if not result.tool_calls:
        # chặn 7: nhắc MỘT LẦN nếu chưa tra tài liệu
        return Ok(result.text)
    observations = await tools.call_many(result.tool_calls, ctx)
    # kết quả -> role 'tool', TUYỆT ĐỐI không vào 'system'
```

Bảy chặn, **đánh số và gọi tên trong chú thích**, mỗi cái chặn một kiểu hỏng:

| # | Chặn | Kỹ thuật |
|---|---|---|
| 1 | Số vòng | `range()` |
| 2 | ~~Tổng số lời gọi tool~~ | **Đã bỏ** — xem dưới |
| 3 | Deadline | `time.monotonic()`, kiểm **đầu vòng** |
| 4 | Ngân sách ngày | Gọi lại port **mỗi vòng** |
| 5 | Trần kích thước observation | Áp ở tầng công cụ |
| 6 | Cờ dừng | Hook `Callable | None`, kiểm đầu vòng |
| 7 | Chưa tra tài liệu mà đã định trả lời | Nhắc **đúng một lần**, có điều kiện |

**Chặn 2 bị bỏ, và lý do là một bài học kỹ thuật:** khi chạm trần giữa một vòng, đoạn cắt
`[:còn_lại]` **vứt bớt** một phần các lời gọi model vừa xin, rồi ghi vào lịch sử như thể
model chỉ xin bấy nhiêu. Model không biết mình bị cắt, nên nó trả lời như đã có đủ dữ liệu.

> **Luật rút ra:** không bao giờ **âm thầm cắt bớt ý định của model** rồi ghi lại như thể
> đó là ý định ban đầu. Hoặc chạy đủ, hoặc dừng hẳn và nói ra.

Ba chi tiết kỹ thuật nữa:
- **Vòng cuối không trao tool.** Trao tool ở vòng cuối là chắc chắn phí một lượt gọi — kết
  quả trả về sẽ không còn vòng nào để đọc.
- **Kết quả công cụ luôn vào `role: "tool"`.** Văn bản do người lạ soạn không được mang
  thẩm quyền hệ thống.
- **Kết thúc sớm mà đã có văn bản** → trả về kèm ghi chú *chưa đầy đủ*; **chưa có gì** →
  trả lỗi. Không bao giờ im lặng.

### 6.5 Kỹ thuật: hiệu ứng phụ không chặn đường phản hồi

```python
def start_typing(channel, scope, logger) -> asyncio.Task[None]:
    async def run() -> None:
        try:
            await channel.typing(scope)
        except Exception as error:
            logger.warning(...)
    return asyncio.create_task(run())
```

Không `await`. Nhưng **phải bắt lỗi bên trong**: một task bị từ chối mà không ai xử lý sẽ
in `Task exception was never retrieved` và che mất lỗi thật. Và **phải trả về task** để
nơi gọi huỷ được lúc tắt process.

### 6.6 Kỹ thuật: khoá ghi suy ra từ khoá gốc

```python
message_id = f"{in_reply_to_id}:bot"
```

Một câu hỏi sinh ra đúng một câu trả lời, nên khoá này vừa duy nhất vừa **tự chống trùng
khi job retry**. Không sinh UUID mới — UUID mới nghĩa là mỗi lần retry ghi thêm một dòng.

Và trường mô tả **cuộc hội thoại** phải lấy từ tin gốc, không đặt cứng. Đặt cứng thì một
nửa số dòng của một thread khai sai, và mọi truy vấn lọc theo cột đó đọc ra một nửa sự thật.

---

## 7. `pipeline/handle_message.py` — orchestrator

**351 dòng, và mục tiêu thiết kế là: đọc tệp này là hiểu cả hệ thống.**

### 7.1 Kỹ thuật: danh sách stage TƯỜNG MINH, đánh số, có cả stage đã bỏ

Các stage chưa làm hoặc đã bỏ **được giữ lại dưới dạng chú thích đánh số**, kèm lý do.
Đọc tệp vẫn thấy đủ hình dạng cuối cùng của đường ống, và không ai phải tra lịch sử git
để biết vì sao số 8 nhảy sang số 9.

### 7.2 Kỹ thuật: thứ tự stage là ĐẶC TẢ, không phải ngẫu nhiên

Bốn ràng buộc thứ tự, mỗi cái có lý do và phải ghi ngay tại chỗ:

| Ràng buộc | Lý do |
|---|---|
| lệnh **trước** rate limit | Người dùng phải xoá được dữ liệu của mình kể cả khi bị chặn |
| rate limit **trước** ghi | Tin bị chặn không được vào lịch sử, nếu không một đợt spam làm nhiễu cả hội thoại |
| ghi **trước** gọi model | Model lỗi thì câu hỏi vẫn còn |
| đường chuyên biệt **sau** ngân sách, **trước** đọc bộ nhớ | Vẫn tốn tiền nên phải chịu chốt chặn; nhưng không cần ngữ cảnh nên không đọc |

Ghi thẳng *"đừng tối ưu thứ tự này"* vào chú thích. Nó trông như một chỗ tối ưu được.

### 7.3 Kỹ thuật: đọc SONG SONG những thứ độc lập

```python
recent, summary, facts = await gather(
    memory.recent(scope, limit),
    memory.summary(scope),
    memory.facts(scope, subject, query),
)
```

Ba lần đọc độc lập; tuần tự là cộng thẳng độ trễ của cả ba vào đường phản hồi mà không
được gì. Mọi truy vấn đều kèm `scope`.

### 7.4 Kỹ thuật: kiểu trả về mang theo THÔNG TIN CHO TẦNG DƯỚI

```python
@dataclass(frozen=True, slots=True)
class Handled:
    replied: bool
@dataclass(frozen=True, slots=True)
class Failed:
    error: BotError
    replied: bool        # <- trường quan trọng nhất của tầng này
```

`replied` tồn tại vì một bài học đắt: dùng **một** cờ hạ tầng cho **hai** ý nghĩa
("đã gửi văn bản" và "job coi như xong") làm cơ chế retry chết hoàn toàn — lần thử lại vào
lại đường ống, gặp cờ, thoát ngay, và số lần thử tối đa chưa bao giờ được dùng.

Kết hợp với `Deps.is_final_attempt` (tầng dưới tính từ số lần thử của hàng đợi):

```
lỗi CÓ THỂ retry  +  còn lượt   ->  KHÔNG gửi gì, trả Failed(replied=False)
lỗi KHÔNG retry được            ->  trả lời NGAY, kể cả khi còn lượt
```

**Luật kỹ thuật tổng quát:** một cờ mang hai ý nghĩa sẽ hỏng ở đúng lúc hai ý nghĩa đó
tách nhau ra. Tách thành hai.

### 7.5 Kỹ thuật: đọc điều kiện trên KẾT QUẢ ĐÃ DỰNG, không trên đầu vào

```python
def _co_tai_lieu(prompt: ContextEnvelope) -> bool:
    return any("<the_tai_lieu" in m.content for m in prompt.messages)
```

Tầng trần token có thể đã cắt hết khối đó. Hỏi *"đầu vào có tài liệu không"* cho câu trả
lời sai; hỏi *"chuỗi cuối cùng có tài liệu không"* mới đúng.

**Áp dụng rộng:** test bảo mật của dự án cũng kiểm trên **chuỗi prompt đã build**, không
trên kết quả repository — rò rỉ có thể xảy ra ở tầng dựng trong khi repository vẫn sạch.

---

## 8. Chiến lược test

### 8.1 Bốn tầng, và tầng này chỉ thuộc tầng thứ nhất

| Tầng | Chạy khi nào | Yêu cầu |
|---|---|---|
| **Unit** — chỉ `agents/` | mọi commit | **Không I/O, < 2s.** Đây là lý do tồn tại của `ports/` |
| Contract | mọi commit | Adapter ăn payload thật đã ghi lại |
| Integration | mọi PR | CSDL + cache + embedding thật |
| Security | mọi PR | **Không được phép xoá**, CI không được bỏ qua |

### 8.2 Kỹ thuật: fake thủ công, không mock framework

Một tệp `fakes.py` chứa implementation giả cho **mỗi** port. Không `unittest.mock`, không
`monkeypatch` vào nội bộ.

Lý do kỹ thuật: `Protocol` khớp cấu trúc, nên một fake chỉ là một class có đủ phương thức.
Mock framework cho phép vá **bất cứ chỗ nào**, kể cả chỗ không phải biên — và test vá vào
nội bộ sẽ xanh trong khi đường thật đã đổi.

**Dấu hiệu nhận biết test đang vá sai chỗ:** đổi một chi tiết hạ tầng làm test đỏ *mà hành
vi không đổi*. Khi gom các lời gọi mạng về một pool dùng chung, ba test vá thẳng vào thư
viện HTTP hoá đỏ — **đó là kết quả đúng**: vá ở chỗ cũ mà vẫn xanh nghĩa là test đang kiểm
một đường mà mã thật không đi.

### 8.3 Kỹ thuật: bỏ qua có ngữ cảnh

```
                     Máy dev        CI
thiếu hạ tầng        bỏ qua         ĐỎ
thiếu khoá API       bỏ qua         bỏ qua + cảnh báo nổi bật
```

Hạ tầng do chính workflow dựng lên → thiếu là lỗi cấu hình CI. Khoá API phải do chủ repo
thêm → không có nó là **lựa chọn hợp lệ**, nhưng phải kêu to chứ không được lặng lẽ xanh.

Đây là cách một bộ test bảo mật chết mà không ai hay: không ai xoá nó, nó chỉ lặng lẽ
thôi chạy.

### 8.4 Kỹ thuật: test ghim (ghim hành vi, ghim quyết định)

Ngoài test đúng/sai thông thường, tầng này dùng ba loại ghim:

| Loại | Ghim cái gì | Ví dụ áp dụng |
|---|---|---|
| Ghim **thứ tự** | Hai bước không được đảo | Bỏ định dạng trước khi che |
| Ghim **quyết định âm** | Một hướng đã đo và đã tắt, không ai bật lại mà không đo | Các cờ thí nghiệm |
| Ghim **tính nhất quán** | Hai đường phải cho cùng kết quả | Hai nơi dựng cùng một khoá |

Ghim quyết định âm là loại đặc biệt đáng giá trong một dự án có nhiều thí nghiệm: nó biến
*"đã thử và không ăn"* từ một câu trong tài liệu thành một ràng buộc chạy được.

### 8.5 Kỹ thuật: đặt tên test cho người đọc báo cáo lỗi

Trong tiếng Việt không dấu, một từ phủ định lọt giữa tên hàm dài rất dễ đọc lướt qua — mà
đọc nhầm phủ định là hiểu ngược hoàn toàn. Giải pháp: **viết hoa từ mang tính phủ định**,
và tắt luật lint về cách đặt tên cho riêng thư mục test.

Tên test là **văn xuôi cho người đọc báo cáo lỗi**, không phải API ai gọi.

---

## 9. Thứ tự thi công

Dựng từ trong ra ngoài. Mỗi bước biên dịch và test được **trước khi** có bước sau.

| # | Bước | Phụ thuộc vào | Xong khi |
|---|---|---|---|
| 1 | `shared/result.py` | — | `Ok`/`Err` + `TypeGuard`, mypy sạch |
| 2 | `domain/thread.py` | 1 | `Platform`, `ThreadScope`, hàm dựng khoá |
| 3 | `domain/message.py` `errors.py` `knowledge.py` | 2 | 3 vị từ lỗi có test cho từng nhánh |
| 4 | `ports/` — cả 6 | 3 | Chỉ `Protocol`; **không** implementation nào tồn tại |
| 5 | `tests/unit/fakes.py` | 4 | Một fake cho mỗi port, không dùng mock |
| 6 | `policy/access.py` `mention.py` `command.py` | 3 | Thuần, test bảng ca |
| 7 | `prompt/budget.py` `builder.py` | 3 | Trần + `sanitize`, có test tự-thoát-thẻ |
| 8 | `prompt/system.py` `instructions.py` | — | **Nội dung — ngoài phạm vi plan này**. Chỉ chốt: hằng số, không nội suy, có trần |
| 9 | `prompt/context.py` | 7, 8 | Lịch sử render thành **lượt thật**, có test cấu trúc |
| 10 | `pipeline/stages/` — các stage mỏng | 6, 9 | Mỗi stage một hàm, trả union |
| 11 | `pipeline/stages/generate.py` | 4, 9 | 6 chặn có số; mỗi chặn một test |
| 12 | `pipeline/handle_message.py` | 10, 11 | Đường ống chạy đủ với **fake toàn bộ** |
| 13 | `policy/injection.py` | 6 | Ba bề mặt dùng chung một bảng |
| 14 | `policy/output_guard.py` + `stages/respond.py` | 12 | 4 luật + **test ghim thứ tự** |
| 15 | `policy/autonomy.py` | 12 | Bảng + test đối chiếu với hành vi thật |

**Bước 4 trước bước 5, bước 5 trước mọi thứ dùng port.** Viết implementation thật trước
khi có fake là cách tầng này mọc một phụ thuộc hạ tầng mà không ai để ý.

**Bước 12 là mốc thật:** cả đường ống chạy đầu-cuối mà **không có một dòng hạ tầng nào**.
Nếu tới bước này mà test đòi một CSDL, thì L1 hoặc L2 đã thủng ở đâu đó.

**Bước 14 sau bước 12** có chủ đích: output rails là chốt chặn cuối, và nó phải bọc **mọi**
đường ra — kể cả câu báo lỗi và câu trả lời lệnh. Viết nó trước khi biết có bao nhiêu
đường ra sẽ bỏ sót vài đường.

### 9.1 Cưỡng chế phải dựng SONG SONG, không dựng sau

| Làm ở bước | Việc |
|---|---|
| Ngay bước 4 | Thêm hợp đồng cấm `agents → hạ tầng` vào `import-linter`, chạy trong CI |
| Ngay bước 4 | Viết canary: tạo vi phạm cố ý, bắt buộc luật phải **đỏ** |
| Ngay bước 6 | Guard AST chặn đọc biến môi trường ngoài tầng cấu hình |
| Ngay bước 12 | Guard AST chặn SQL chạm bảng nhạy cảm ngoài repository |

Dựng luật sau khi đã viết code nghĩa là luật đầu tiên bạn viết sẽ đỏ vì những vi phạm đã
tồn tại, và phản ứng tự nhiên là nới luật cho xanh.

---

## 10. Bốn chỗ hở thấy được khi rà lại — ĐÃ SỬA (17/09/2026)

Cả bốn đều **chạy xanh** và không lỗi nào được báo, nên không cái nào lộ ra bằng test.

**Trạng thái sau khi sửa:** `mypy` sạch 216 tệp · `ruff` sạch · `lint-imports` **6 hợp
đồng KEPT** (thêm một) · hai guard AST xanh · canary **9/9 luật sống** (thêm một) ·
**1023 test passed, 53 skipped**.

### 10.1 Một đường chết cùng loại với hai port đã bị xoá

Stage viết-lại-câu-hỏi đã bị **bỏ có chủ đích** (07/09/2026) vì vòng ReAct tự làm việc đó.
Nhưng toàn bộ bộ khung của nó vẫn còn, ở **bốn** chỗ:

```
agents/ports/llm.py        CheapRoute khai "rewrite"
agents/prompt/instructions.py   REWRITE_INSTRUCTION — hằng số đầy đủ
agents/prompt/instructions.py   INSTRUCTIONS["rewrite"]
llm/models.py              MODELS["rewrite"] — cấu hình model + trần token
```

**Không chỗ nào gọi.** Đây đúng tình huống đã khiến dự án xoá hai port chết, với đúng lý
do đã ghi: *"một port chết còn tệ hơn không có port, vì người đọc sau sẽ tưởng đó là
đường đi thật."*

**ĐÃ SỬA:** xoá cả bốn mảnh. `CheapRoute` và `Route` còn 3 và 5 giá trị; `MODELS` bỏ
một dòng; hằng số instruction bị xoá. Lý do xoá ghi ngay tại `CheapRoute` để lần sau
không ai dựng lại một route mà không nối nó vào đâu cả.

### 10.2 Một `dict` chết, và chú thích của nó nói sai

`INSTRUCTIONS` là một `dict[str, str]` gom các instruction theo khoá, kèm chú thích khẳng
định *"khoá trùng với danh sách route"*.

Hai vấn đề:
- **Không ai gọi `INSTRUCTIONS`.** Mọi nơi dùng import thẳng hằng số.
- **Chú thích nói sai.** Danh sách route có **bốn** giá trị; `dict` có **ba**. Thiếu route
  nén kết quả công cụ.

Chú thích nói chặt hơn mã nguồn là kiểu sai nguy hiểm — người đọc sau tin nó thay vì kiểm
lại. Dự án này đã bắt đúng lỗi đó một lần ở bảng vần và ghi lại nguyên văn.

**ĐÃ SỬA — chọn phương án hai, và nó đổi bản chất của `dict` này.** Điền `compress` cho
đủ, gắn kiểu `dict[CheapRoute, str]`, và thay test cũ bằng:

```python
assert set(INSTRUCTIONS) == set(get_args(CheapRoute))
```

Test **cũ** ghim chính cái lệch — nó khẳng định `sorted(INSTRUCTIONS) == ["extract_facts",
"rewrite", "summarize"]` bằng một danh sách gõ tay, tức nó **bảo vệ** trạng thái sai.
Bản mới đối chiếu thẳng với kiểu, nên thêm một route chạy nền mà quên viết instruction
sẽ làm test đỏ. `dict` từ chỗ chết thành chỗ **giữ một bất biến**.

### 10.3 Một gói phụ thuộc nằm NGOÀI vùng phủ của luật kiến trúc

`agents/` import `tho/` ở hai chỗ (nhận diện ý định, và stage chuyên biệt).

Kiểm lại thì `tho/` **hôm nay đúng là thuần** — không chạm cấu hình, hạ tầng, tầng LLM,
hay biến môi trường. Nên phụ thuộc này **hợp lệ về bản chất**.

Nhưng: `tho` **không có** trong danh sách gói gốc của `import-linter`. Hệ quả:

- Không luật nào gác chiều `agents → tho`.
- Quan trọng hơn: **không có gì giữ `tho` thuần.** Ngày nó import tầng hạ tầng, `agents`
  sẽ gián tiếp phụ thuộc hạ tầng, `lint-imports` vẫn xanh, và unit test của `agents` bắt
  đầu đòi biến môi trường — đúng triệu chứng mà L2 sinh ra để tránh, và nó đã từng xảy
  ra một lần với một module khác.

**Đề nghị — ba dòng, làm ngay:**

```ini
root_packages = ... tho ...

[importlinter:contract:N]
name = tho la goi THUAN — khong duoc cham ha tang
type = forbidden
source_modules = tho
forbidden_modules = adapters, infra, llm, memory, knowledge, tools, config
```

**ĐÃ SỬA.** Thêm `tho` vào `root_packages`, thêm hợp đồng `L1b`, thêm một ca canary.
Đã kiểm: `tho` import **đúng 0** gói cấp cao nhất nào — chỉ thư viện chuẩn — nên hợp
đồng qua ngay mà không phải sửa một dòng mã nào của `tho/`.

`shared` **không** nằm trong danh sách cấm: nó cũng là gói thuần, và `tho` được dùng nó.

Chi phí: ba dòng cấu hình + một ca canary. Nó biến một tính chất **đang đúng một cách
tình cờ** thành một tính chất **được giữ** — và canary chứng minh luật mới thật sự bắt
được vi phạm, chứ không chỉ báo `KEPT`.

### 10.4 Một trường không giải thích được

Hai dataclass có trường `_unused: tuple[()] = field(default=(), repr=False)`, không chú
thích, không ai đọc. Một trường không giải thích được trong một codebase mà mọi hằng số
đều có ba dòng lý do là một chỗ lệch chuẩn.

**ĐÃ SỬA:** xoá khỏi cả hai, và bỏ luôn `field` khỏi import vì không còn chỗ nào dùng.
An toàn vì nó là trường cuối, có giá trị mặc định, và không nơi nào tham chiếu tới.

---

## 11. Những thứ đặc tả này CỐ Ý không nói

- **Nội dung prompt.** Ba tầng prompt được mô tả ở mức *kỹ thuật* (hằng số, vòng đời,
  trần, bọc thẻ, render lượt thật). Viết nội dung là một việc khác, đo bằng bộ eval, và
  nó không thuộc phạm vi một đặc tả công nghệ.
- **Luật nghiệp vụ.** Ai được xoá gì, chính sách nhóm, mức tự chủ của từng hành động —
  plan chỉ mô tả **cấu trúc để biểu diễn** chúng (bảng dữ liệu cưỡng chế được bằng test),
  không mô tả các giá trị.
- **Chọn nhà cung cấp.** Tầng này không biết nhà cung cấp nào tồn tại, và đó là điểm chính.
- **Con số cụ thể** (trần token, số vòng, thời hạn). Chúng là kết quả đo trên một hệ thống
  cụ thể. Đặc tả chỉ nói: *phải có trần, phải đo, phải ghi nguồn gốc con số, và phải log
  khi chạm trần*.
