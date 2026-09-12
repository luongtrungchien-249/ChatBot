# Plan: làm thơ lục bát / thất ngôn tứ tuyệt, và tự host model

*11/09/2026. Đây là bản kế hoạch, chưa thi công dòng nào.*

> **§0.2 đã có câu trả lời, và nó chặn việc tự host trên máy này: RTX 3050 Ti, 4 GB
> VRAM — thiếu 3,5 lần ngay cả ở int4.** Xem §11. Đường ống đã dựng xong nên tự host
> chỉ còn là một dòng cấu hình khi có phần cứng.

---

## 0. Ba ẩn số, và chúng quyết định phần lớn bản kế hoạch

### 0.1 `gemma-4-26B-A4B-it` — tôi không có model này trong hiểu biết

Tôi biết Gemma 2 (2B/9B/27B) và Gemma 3 (1B/4B/12B/27B). Không biết "Gemma 4", và
hậu tố `A4B` là lối đặt tên của MoE (tổng 26B, ~4B tham số **hoạt động** mỗi token),
lối đó giống họ Qwen3-MoE hơn là họ Gemma.

Có thể nó ra sau mốc hiểu biết của tôi. **Không sao** — bản kế hoạch này viết theo
*hình dạng* của model chứ không theo tên: một MoE cỡ ~26B tổng / ~4B hoạt động, bản
`it` (instruction-tuned), phục vụ qua một endpoint tương thích OpenAI.

Cái bạn cần xác nhận trước khi làm gì: **giấy phép** (Gemma có điều khoản sử dụng
riêng, không phải Apache-2.0 thuần), **độ dài ngữ cảnh**, và **chất lượng tiếng Việt**.
Điểm cuối cùng là quan trọng nhất và không tra được — phải đo (§3).

### 0.2 Có GPU không? Đây là câu hỏi quyết định toàn bộ mục tiêu latency

VRAM cần cho 26B tham số (MoE vẫn phải nạp **toàn bộ** expert vào VRAM, chỉ phần tính
toán mới thưa):

| lượng tử hoá | VRAM cho trọng số | phần cứng tối thiểu thực tế |
|---|---|---|
| bf16 | ~52 GB | A100 80GB, hoặc 2× A100 40GB |
| int8 / fp8 | ~26 GB | A100 40GB, L40S 48GB |
| int4 (AWQ/GPTQ) | ~13-15 GB | 1× RTX 4090 24GB, đủ chỗ cho KV cache |

Cộng thêm KV cache: với ngữ cảnh ~8K và vài luồng đồng thời, tính thêm 2-6 GB.

**Trên CPU thì đừng.** MoE 4B hoạt động chạy CPU được về mặt kỹ thuật, nhưng tốc độ
sinh rơi xuống cỡ 2-8 token/giây. Một bài lục bát ~80-120 token sẽ mất **15-60 giây**
— tức **tệ hơn** con số `p95 = 14-19s` hiện tại, đúng thứ bạn muốn giảm.

Máy đang chạy dự án này là một laptop Windows chạy Docker Desktop. Nếu đó cũng là nơi
định host model thì câu trả lời là không.

### 0.3 Luật thơ: chỉ đếm chữ, hay đủ vần và luật bằng-trắc?

Yêu cầu bạn viết mới nói phần **đếm chữ**:

> *Lục bát một dòng 6 một dòng 8, kết thúc bằng một dòng 8. Thất ngôn tứ tuyệt: mỗi
> dòng 7 chữ.*

Đếm chữ là phần **dễ nhất** và cũng là phần **ít liên quan nhất tới "thơ hay"**. Một
bài đúng 6-8 tuyệt đối mà sai vần thì người Việt đọc lên là thấy ngay, và nó không
còn là lục bát nữa — nó là văn xuôi xuống dòng.

Luật đầy đủ, và tôi đề nghị **ép cả ba tầng**:

**Lục bát**
```
Số tiếng   6 - 8 - 6 - 8 ... và KẾT THÚC bằng câu 8

Vần        tiếng 6 câu lục   vần với   tiếng 6 câu bát
           tiếng 8 câu bát   vần với   tiếng 6 câu lục kế tiếp

Bằng/trắc  câu lục:  tiếng 2 bằng · 4 trắc · 6 bằng
           câu bát:  tiếng 2 bằng · 4 trắc · 6 bằng · 8 bằng
           (tiếng 6 và 8 của câu bát phải KHÁC thanh: một huyền một ngang)
```

**Thất ngôn tứ tuyệt**
```
Số tiếng   4 câu × 7 tiếng
Vần        cuối câu 1, 2, 4 cùng vần (hoặc chỉ 2 và 4)
Bằng/trắc  luật bằng hoặc luật trắc, xét tiếng 2-4-6 ("nhất tam ngũ bất luận,
           nhị tứ lục phân minh")
Niêm       tiếng 2 câu 1 niêm với tiếng 2 câu 4; tiếng 2 câu 2 niêm với câu 3
```

**Đây là câu bạn cần trả lời trước §2:** ép cả vần và bằng-trắc, hay chỉ ép số tiếng?
Ép cả ba làm bài thơ *đúng luật* nhưng khó hơn cho model nhiều lần, và tỉ lệ phải
sinh lại sẽ cao — điều đó **đánh thẳng vào mục tiêu latency**.

Khuyến nghị của tôi: **ép số tiếng + vần THÔNG, còn bằng-trắc thì đo rồi mới quyết.**
Số tiếng và vần là thứ người đọc nhận ra ngay; bằng-trắc sai nhẹ thì phần lớn người
đọc không thấy, mà nó lại tốn nhiều lượt sinh lại nhất.

> **Chữ THÔNG ở trên không phải tuỳ chọn.** Nguyên mẫu ở §9 cho thấy bộ kiểm tra vần
> chặt chẽ **loại thẳng bốn câu mở đầu Truyện Kiều** (`nhau` / `dâu` khác vần thật,
> nhưng lục bát truyền thống vẫn tính là vần). Ép vần chính tuyệt đối là bắt model
> viết thứ mà chính Nguyễn Du cũng trượt.

---

## 1. Vấn đề kiến trúc: thơ và RAG là hai bài toán NGƯỢC nhau

Bot này vừa được siết bằng hai luật hệ thống (xem `plan-truy-hoi-xuyen-ngon-ngu.md`
§25-§26):

> *KHÔNG trả lời từ trí nhớ. Mọi câu hỏi có dữ kiện đều phải tra tài liệu TRƯỚC.*

Và hôm nay thêm **chặn 7** trong vòng ReAct: model định trả lời mà chưa gọi
`search_knowledge_base` thì bị nhắc một lần.

Làm thơ là **đúng cái ngược lại**. Nó thuần sinh, không có tài liệu nào để tra, và
tra cũng vô nghĩa.

### 1.1 Hệ quả cụ thể phải xử lý

*"Làm cho mình bài lục bát về mùa thu Hà Nội"* sẽ:

1. Đi qua chặn 7 → model bị nhắc "chưa tra tài liệu" → **tốn một lượt gọi model thừa**,
   cộng thẳng vào latency đúng lúc bạn đang muốn giảm nó.
2. Có nguy cơ model hiểu nhầm và đi tra thật, rồi trả về "không tìm thấy tài liệu về
   mùa thu Hà Nội".

Lời nhắc hiện đã có nhánh *"không phải câu có dữ kiện thì trả lời như cũ"*, và ca âm
đã kiểm bốn dạng (chào, cảm ơn, hỏi tên bot, nhờ viết lại câu) — **nhưng chưa kiểm
dạng sáng tác**. Đây là việc phải làm, không phải việc tuỳ chọn.

### 1.2 Hai cách định tuyến, chọn một

**Cách A — thêm nhánh vào lời nhắc của chặn 7.** Rẻ nhất: thêm "sáng tác (làm thơ,
viết lời chúc)" vào danh sách không-dữ-kiện, và thêm ca âm vào
`tests/unit/test_react_loop.py`. Không đổi kiến trúc. Nhưng vẫn tốn một lượt gọi
model thừa cho mỗi bài thơ.

**Cách B — phân loại ý định TRƯỚC vòng ReAct**, rồi route thẳng sang model thơ, bỏ
qua cả tool lẫn chặn 7. Nhanh hơn hẳn và là điều kiện cần nếu muốn dùng model riêng
cho thơ. Chỗ đặt: một stage mới trước `generate`, cùng tầng với
`pipeline/stages/command.py` (đã có sẵn cơ chế nhận lệnh `nhớ giúp:` / `quên`).

**Khuyến nghị: B**, vì nó cũng chính là chỗ cắm model tự host. Nhưng nếu chỉ muốn có
tính năng thơ mà chưa tự host thì A đủ và làm trong một buổi.

Phân loại bằng gì: bắt đầu bằng **từ khoá** (`làm thơ`, `lục bát`, `thất ngôn`,
`tứ tuyệt`, `sáng tác`) chứ đừng gọi model để phân loại — gọi model để quyết có gọi
model không là cộng thẳng latency vào mọi lượt. Từ khoá sai thì rơi về luồng cũ, tức
sai *an toàn*.

---

## 2. Chuẩn output: luật thơ phải là CODE, không phải câu chữ trong prompt

Đây là điểm quan trọng nhất của bản kế hoạch, và nó rút thẳng từ bài học ba ngày qua.

Ba ngày vừa rồi chứng minh một điều rất cụ thể: **một luật viết trong prompt được
tuân thủ khoảng 50-95%, không bao giờ 100%.** Lớp câu *"làm sao / bao lâu"* bị đánh ở
cả ba tầng câu chữ mà vẫn chỉ giữ được 3/6, cho tới khi thêm một **chặn cứng trong
code** thì mới lên 6/6.

Đếm tiếng trong thơ Việt là bài toán **tất định tuyệt đối** — tiếng Việt viết rời,
mỗi tiếng là một token cách nhau bởi khoảng trắng. Nghĩa là:

```
Không cần model để biết bài thơ có đúng 6-8 hay không. Chỉ cần len(dòng.split()).
```

Bỏ qua món quà đó rồi đi cầu mong prompt tuân thủ là lặp lại đúng sai lầm đã mất ba
ngày để sửa.

### 2.1 Bộ kiểm tra tất định

Một module thuần, không I/O, không gọi model — `src/tho/luat.py`:

```python
def kiem_luc_bat(bai: str) -> list[Loi]:
    """Tra ve danh sach loi. Rong = dung luat."""
    # 1. so tieng   6, 8, 6, 8, ... va dong cuoi phai la 8
    # 2. van        tieng 6 cau luc ~ tieng 6 cau bat
    #               tieng 8 cau bat ~ tieng 6 cau luc ke
    # 3. bang/trac  tieng 2-4-6 (va 8 o cau bat)

def kiem_that_ngon_tu_tuyet(bai: str) -> list[Loi]:
    # 1. dung 4 dong, moi dong 7 tieng
    # 2. van cuoi cau 1, 2, 4
    # 3. luat bang-trac o tieng 2-4-6, va niem
```

Hai bảng tra cần dựng (đây là phần tốn công thật, không phải phần gọi model):

**Bảng thanh điệu** — từ dấu sang bằng/trắc. Dễ và tất định:
```
bằng: không dấu (ngang), huyền
trắc: sắc, hỏi, ngã, nặng
```
Lấy dấu bằng cách chuẩn hoá Unicode NFD rồi đọc ký tự tổ hợp — cùng kỹ thuật đã dùng
trong `ops/gan_chunk_id.py`.

**Bảng vần** — khó hơn. Vần tiếng Việt xét phần **âm chính + âm cuối**, bỏ phụ âm
đầu: `an ~ àn ~ bàn ~ hoàn`. Cần một hàm tách tiếng thành (âm đầu, vần, thanh). Có thư
viện làm việc này, nhưng một bảng tự viết cho các vần thông dụng đã đi được rất xa, và
nó **không phụ thuộc mạng, không tốn token, chạy trong micro-giây**.

### 2.2 Vòng sinh lại có kiểm tra

```
sinh bài  ->  kiểm tra  ->  đúng luật?  ->  trả cho người dùng
                              |
                           sai luật
                              |
                     nói RÕ sai chỗ nào, sinh lại (tối đa N lần)
                              |
                     vẫn sai sau N lần -> trả bài tốt nhất + nói rõ còn lỗi gì
```

Ba điều bắt buộc, và cả ba đều rút từ bài học của `plan-truy-hoi-xuyen-ngon-ngu.md`:

**Nói RÕ sai ở đâu, đừng chỉ nói "sai".** *"Câu 3 có 7 tiếng, lục bát cần 6"* mạnh hơn
hẳn *"sai luật, làm lại"*. Đây đúng là cơ chế đã làm chặn 7 hiệu quả.

**Giới hạn số lần — và con số đó là ngân sách latency của bạn.** N=2 nghĩa là trường
hợp xấu nhất tốn 3 lượt gọi model. Với mục tiêu giảm latency thì N=2 là trần hợp lý;
N=5 thì tính năng này thành thứ chậm nhất trong bot.

**Không bao giờ im lặng.** Hết N lần mà vẫn sai thì trả bài tốt nhất kèm một câu nói
thẳng còn lỗi gì — đúng luật "không biết thì nói không biết" của `SYSTEM_PROMPT`.

### 2.3 System prompt cho thơ

Một prompt riêng, **không** nhét vào `SYSTEM_PROMPT` chính. Lý do rất cụ thể: tầng
`system` đang ở **12.948 / 12.960 ký tự** — còn đúng 12 ký tự. Thêm luật thơ vào đó
là vỡ trần, và luật thơ cũng chỉ dùng cho một route.

Chỗ đặt: `src/agents/prompt/tho.py`, đi theo route `poem` (§5).

Nội dung cần có, theo đúng thứ tự đã chứng minh là hiệu quả (mệnh lệnh lên **câu
đầu**, kèm **ví dụ**, kèm **lý do**):

1. Luật số tiếng, nói bằng con số cụ thể.
2. Luật vần, kèm **một ví dụ đúng** — ví dụ dạy mạnh hơn luật, đây là kết luận đã đo
   được của chính dự án này.
3. Một **ví dụ sai kèm giải thích vì sao sai**. Với thơ thì ví dụ phản diện đặc biệt
   quan trọng, vì lỗi hay gặp nhất (thừa một tiếng) rất khó tự thấy.
4. Yêu cầu về **nghĩa**: bài thơ phải nói về một điều cụ thể, có hình ảnh, không ghép
   sáo ngữ. Đây là phần prompt **không** ép được bằng code, và cũng là phần
   fine-tuning giúp được nhiều nhất (§4).
5. Chỉ xuất bài thơ. Không lời dẫn, không giải thích, không "đây là bài thơ của bạn".

---

## 3. Đo TRƯỚC, fine-tune SAU — và đây là phần dự án này đã có sẵn công cụ

Ba ngày vừa qua đã dựng một bộ eval đầy đủ (`evals/`, khung RAGAS, golden 52 câu).
**Áp dụng thẳng được cho thơ**, và với thơ nó còn tốt hơn — vì phần lớn tiêu chí là
tất định, không cần người chấm bằng model.

### 3.1 Bộ chỉ số

| chỉ số | cách đo | tất định? |
|---|---|---|
| Đúng số tiếng | `kiem_luc_bat` | **có** |
| Đúng vần | `kiem_luc_bat` | **có** |
| Đúng bằng-trắc | `kiem_luc_bat` | **có** |
| Số lượt sinh lại | đếm trong vòng lặp | **có** |
| Latency p50/p95 | đồng hồ | **có** |
| **Hay / có nghĩa** | người chấm bằng model | không |
| Đúng chủ đề người dùng yêu cầu | người chấm bằng model | không |

Năm chỉ số đầu **miễn phí và chạy trong micro-giây**. Đó là thứ hiếm: bạn có thể chạy
1.000 lần sinh thử mà không tốn gì ngoài tiền sinh.

Chỉ số "hay" thì dùng lại đúng khuôn `evals/metrics/faithfulness.py` — và nhớ bài học
ở đó: **bắt xuất đúng một con số**, và **cảnh giác với chính người chấm**. Tài liệu
kia ghi bốn lần người chấm sai.

### 3.2 Bộ golden cho thơ

`evals/dataset/tho.jsonl`, 30-50 dòng, mỗi dòng là một **yêu cầu**, không phải một
bài thơ mẫu:

```json
{"id": "t001", "the_tho": "luc_bat", "yeu_cau": "mùa thu Hà Nội", "so_cau": 4}
{"id": "t002", "the_tho": "that_ngon_tu_tuyet", "yeu_cau": "tiễn bạn đi xa"}
{"id": "t003", "the_tho": "luc_bat", "yeu_cau": "cảm ơn đồng nghiệp đã giúp đỡ"}
```

Cần phủ: chủ đề trừu tượng (nhớ nhà) và cụ thể (một tách cà phê), yêu cầu ngắn và dài,
yêu cầu có ràng buộc thêm (phải có chữ "trăng"), và **yêu cầu vô lý** (làm lục bát 5
câu — đúng ra phải nói lại là lục bát kết thúc bằng câu 8).

### 3.3 Đường cơ sở phải đo trước khi đụng vào fine-tuning

Chạy bộ golden qua **model hiện tại** (`gpt-5-mini`) và qua **model mới zero-shot**.
Không có hai con số này thì mọi tuyên bố "fine-tune giúp được X%" đều là nói suông —
và đó chính xác là sai lầm mà `plan-truy-hoi-xuyen-ngon-ngu.md` §10 ghi lại ba lần.

---

## 4. Fine-tuning: làm gì, và quan trọng hơn — KHÔNG làm gì

### 4.1 Đừng fine-tune để sửa việc đếm chữ

Cám dỗ lớn nhất là fine-tune cho model đếm đúng 6-8. **Đừng.** Đếm chữ là việc của
`len(dòng.split())`, và bộ kiểm tra tất định làm việc đó với độ chính xác 100%, chi
phí bằng không, không cần dữ liệu huấn luyện nào.

Fine-tune dạy được thứ code không làm được: **giọng thơ, hình ảnh, cách chọn chữ, và
tỉ lệ đúng luật ngay từ lần sinh đầu.** Thứ cuối cùng mới là thứ tác động tới latency —
càng ít phải sinh lại thì càng nhanh.

### 4.2 Thứ tự việc, dừng ngay khi đã đủ tốt

**Bước 0 — đo zero-shot.** Có thể model `it` đã làm lục bát đúng luật 70% rồi. Nếu
prompt + vòng sinh lại N=2 cho ra 95% đúng luật thì **dừng ở đây**, không fine-tune.

**Bước 1 — prompt + few-shot.** 3-5 bài mẫu đúng luật ngay trong prompt. Rẻ, sửa trong
vài phút, và với thơ thì few-shot thường ăn rất mạnh vì nó dạy *hình dạng* trực tiếp.
Cái giá: ~500-1.500 token mỗi lượt — đánh vào latency, nên phải đo cả hai chiều.

**Bước 2 — LoRA / QLoRA.** Chỉ làm khi bước 1 chạm trần. LoRA rank 16-32 là đủ cho
việc học hình dạng và giọng; không cần full fine-tune, và full fine-tune một model
26B cần hạ tầng khác hẳn.

Dữ liệu cần: **1.000-3.000 cặp** (yêu cầu → bài thơ đúng luật). Nguồn:
- **Ca dao, tục ngữ** — lục bát thuần, đã hết hạn bảo hộ, sẵn nhiều.
- **Truyện Kiều** — 3.254 câu lục bát chuẩn mực, hết hạn bảo hộ. Nhưng giọng cổ; huấn
  luyện nhiều quá thì bot làm thơ nghe như thế kỷ 19.
- **Thơ hiện đại** — còn bản quyền. Kiểm tra trước khi đưa vào tập huấn luyện.

Điểm mấu chốt về dữ liệu: **chạy mọi mẫu huấn luyện qua chính bộ kiểm tra ở §2.1 và
loại bỏ mẫu sai luật.** Huấn luyện trên dữ liệu sai luật là dạy model sai luật. Việc
này tất định và gần như miễn phí — không có lý do gì để bỏ qua.

**Bước 3 — đo lại bằng đúng bộ golden ở §3.** Nếu không nhúc nhích, hoàn lại và ghi
lại là đã thử — đúng lối `plan-truy-hoi-xuyen-ngon-ngu.md` ghi ba bản vá đã gỡ bỏ.

---

## 5. Áp vào codebase này thế nào — từng chỗ cụ thể

### 5.1 `llm/models.py` — thêm route

```python
Route = Literal["reply", "rewrite", "summarize", "extract_facts", "compress", "poem"]
```

Docstring của chính file này đã viết sẵn: *"Hiện tại MỌI route dùng chung một model...
Đổi chỗ này là đổi một file."* Thiết kế đã lường trước việc này.

**Nhưng có một chỗ rò trừu tượng phải xử lý:** `ModelConfig.effort` là tham số
**reasoning của OpenAI**. Gemma không có nó. Cần đổi `effort` thành tuỳ chọn
(`Effort | None`), và `openai_client` chỉ gửi tham số đó khi khác `None`.

Tương tự: `price_in` / `price_out` với model tự host thì bằng 0 USD — nhưng chi phí
thật là **giờ GPU**. Quyết định: để 0 và chấp nhận `usage_log` không phản ánh chi phí
thật, hay thêm một trường giá quy đổi. Tôi nghiêng về **để 0 và ghi chú rõ**, vì giá
GPU theo giờ không quy được về token một cách trung thực.

### 5.2 `llm/openai_client.py` — thêm `base_url`

Hiện tại:
```python
_client = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY, max_retries=0)
```

Một client duy nhất, hard-code endpoint OpenAI. Cần:
- `ModelConfig.base_url: str | None`
- `_get_client(base_url)` cache theo `base_url` thay vì một biến toàn cục.

vLLM và TGI đều phục vụ API **tương thích OpenAI**, nên đây là thay đổi nhỏ — không
cần adapter mới, không cần port mới. Đó là lợi thế lớn của kiến trúc hiện tại.

Thêm vào `config/schema.py`: `POEM_BASE_URL`, `POEM_MODEL_ID`, `POEM_API_KEY`
(vLLM chấp nhận một khoá giả).

### 5.3 Định tuyến và chặn 7

Theo cách B ở §1.2: một stage trước `generate`, nhận diện yêu cầu làm thơ bằng từ
khoá, rồi đi thẳng sang `tho/` — không tool, không chặn 7.

Nếu chọn cách A thì tối thiểu phải: thêm "sáng tác" vào nhánh không-dữ-kiện của
`NHAC_TRA_TAI_LIEU`, và thêm ca âm vào `tests/unit/test_react_loop.py`.

### 5.4 Những chỗ khác sẽ gãy nếu quên

| chỗ | vì sao |
|---|---|
| `llm/cost_meter.py` | ghi `cost_usd` theo giá token — model tự host giá 0 |
| `DAILY_BUDGET_USD` | chặn ngân sách sẽ không bao giờ bắn cho route thơ; GPU vẫn tốn tiền thật |
| `ops/docker-compose.yml` | thêm service vLLM, và nó cần `deploy.resources.reservations.devices` cho GPU |
| `.github/workflows/evals.yml` | CI không có GPU — eval thơ phải bỏ qua hoặc chạy trên endpoint từ xa |
| `agents/prompt/budget.py` | nếu dùng few-shot thì prompt thơ cần tầng ngân sách riêng |

### 5.5 Test cần có

- `tests/unit/test_tho_luat.py` — bộ kiểm tra luật, **thuần, không mạng**. Đây là nơi
  đặt nhiều ca nhất: bài đúng, thiếu tiếng, thừa tiếng, kết thúc bằng câu 6 (sai), sai
  vần, sai bằng-trắc, bài rỗng, bài một câu.
- Ca âm cho định tuyến: *"làm thơ"* không được kéo đi tra tài liệu; và ngược lại,
  *"quy định nghỉ phép"* không được rơi vào nhánh thơ.

---

## 6. Latency: con số phải đo trước khi mua GPU

Mục tiêu của bạn là **giảm latency**. Đây là chỗ tôi phải nói thẳng.

### 6.1 Con số hiện tại đo cái gì

`p95 = 14-19s` đo **cả lượt ReAct có tra cứu**: gọi model → gọi công cụ → gọi model.
Một yêu cầu làm thơ **không có** bước tra cứu, nên nó vốn đã nhanh hơn nhiều.

**Việc đầu tiên, làm được ngay hôm nay, không tốn phần cứng:** đo latency của một yêu
cầu làm thơ qua `gpt-5-mini` hiện tại. Nếu nó đã là 2-4 giây, thì việc tự host để
xuống 1-2 giây là đổi lấy toàn bộ gánh nặng vận hành cho một khoản lời rất nhỏ.

### 6.2 Ước tính khi tự host

Với MoE ~4B tham số hoạt động, phục vụ bằng vLLM trên GPU:

```
TTFT (prompt ngắn)      100-300 ms
Tốc độ sinh             50-150 token/s
Bài lục bát 4 câu       ~80-120 token      ->  ~1-2 giây
```

Nhưng phải cộng cả vòng sinh lại: **N=2 nghĩa là trường hợp xấu nhất ~3-6 giây.** Tỉ lệ
đúng-ngay-lần-đầu vì thế là biến số latency quan trọng nhất — và đó chính là thứ
fine-tuning cải thiện được (§4.1).

### 6.3 Cái bạn đánh đổi

Hiện tại OpenAI chết thì bot trả câu xin lỗi rồi thôi. **Tự host thì bạn sở hữu uptime.**
GPU chết, OOM, container không lên — bot chết theo. Cần: health check, hàng đợi, và một
đường lui về model đám mây cho route thơ.

Và: hai model nghĩa là hai hành vi phải giữ đồng bộ. Mọi luật trong `SYSTEM_PROMPT`
được hiệu chuẩn trên `gpt-5-mini`; một model khác sẽ tuân thủ khác đi. Nếu sau này
định chuyển **cả bot** sang model tự host thì phải chạy lại toàn bộ bộ eval 52 câu —
đó là một dự án riêng, không phải phần phụ của việc làm thơ.

---

## 7. Khuyến nghị

**Tách làm hai việc, đừng gộp.**

**Việc 1 — tính năng làm thơ, dùng model hiện tại.** Bộ kiểm tra tất định + prompt
riêng + vòng sinh lại + định tuyến + bộ golden. Không cần GPU, không cần fine-tune, và
nó cho bạn **đường cơ sở** để biết tự host có đáng không. Đây là phần lớn giá trị.

**Việc 2 — tự host, chỉ làm khi có GPU và đã có số đo từ việc 1.** Nếu §6.1 cho thấy
thơ qua model hiện tại đã mất 2-3 giây, thì việc 2 đổi lấy ~1 giây bằng cả gánh nặng
vận hành — và câu trả lời gần như chắc chắn là không đáng, **trừ khi** mục tiêu thật
sự là chuyển cả bot sang tự host vì chi phí hoặc vì dữ liệu không được rời máy. Hai lý
do đó chính đáng, nhưng chúng **không phải latency**.

## 8. Thứ tự làm, và tiêu chí dừng của từng bước

| # | việc | xong khi |
|---|---|---|
| 1 | Chốt §0.3 — ép vần và bằng-trắc hay chỉ số tiếng | có câu trả lời |
| 2 | `src/tho/luat.py` + test | bộ test luật xanh, không gọi mạng |
| 3 | `evals/dataset/tho.jsonl` 30-50 yêu cầu | phủ đủ các dạng ở §3.2 |
| 4 | Đo đường cơ sở `gpt-5-mini` zero-shot | có tỉ lệ đúng luật **và** latency |
| 5 | Prompt thơ + vòng sinh lại N=2 | đúng luật > 90%, latency < đường cơ sở × 2 |
| 6 | Định tuyến + ca âm | "làm thơ" không kéo đi tra; "quy định" không rơi nhánh thơ |
| 7 | **Điểm quyết định**: số đo có biện minh cho tự host không | có/không, ghi rõ lý do |
| 8 | (nếu có) vLLM + `base_url` + route `poem` | chạy được, đo lại bước 4 trên model mới |
| 9 | (nếu cần) LoRA | đúng-ngay-lần-đầu tăng đủ để bù công sức |

Bước 7 là điểm dừng thật. Đừng làm bước 8 trước khi có số của bước 4 và 5.

---

## 9. Nguyên mẫu bộ kiểm tra — đã dựng và chạy thật

*11/09/2026. Khoảng 120 dòng Python thuần, không mạng, không model. Mục đích: chứng
minh §2 làm được, và tìm ra chỗ nó gãy — trước khi viết vào `src/`.*

### 9.1 Đếm tiếng và bằng-trắc: dễ đúng như dự đoán

Tách tiếng bằng khoảng trắng, tách thanh bằng Unicode NFD. Chạy trên bốn câu mở đầu
Truyện Kiều:

```
6 tiếng | Trăm(ngang) năm(ngang) trong(ngang) cõi(ngã) người(huyền) ta(ngang)
8 tiếng | Chữ(ngã) tài(huyền) chữ(ngã) mệnh(nặng) khéo(sắc) là(huyền) ghét(sắc) nhau(ngang)
6 tiếng | Trải(hỏi) qua(ngang) một(nặng) cuộc(nặng) bể(hỏi) dâu(ngang)
8 tiếng | Những(ngã) điều(huyền) trông(ngang) thấy(sắc) mà(huyền) đau(ngang) đớn(sắc) lòng(huyền)
```

Luật bằng-trắc tiếng 2-4-6-8 và luật "tiếng 6 khác thanh tiếng 8" đều qua. Phần này
**tất định, không có vùng xám**.

### 9.2 Bộ kiểm tra vần CHẶT CHẼ loại thẳng Truyện Kiều

```
--- VẦN CHÍNH (chặt chẽ) ---
   LỖI: câu 2-3: 'nhau' không vần 'dâu'
   LỖI: câu 3-4: 'dâu' không vần 'đau'

--- VẦN THÔNG (nới lỏng) ---
   đúng luật
```

`nhau` có vần **au**, `dâu` có vần **âu**. Khác nhau thật — và thơ lục bát truyền
thống vẫn tính đó là vần (**vần thông**).

Đây là kết quả quan trọng nhất của nguyên mẫu: **bắt vần chính tuyệt đối là bắt model
viết thứ mà chính Nguyễn Du cũng trượt.** Vần thông là bắt buộc, không phải tuỳ chọn.

Bảng nhóm nguyên âm thông vần đã thử:
```
{a, â, ă}   {o, ô, ơ}   {u, ư}   {e, ê}   {i, y}
```

### 9.3 Một lỗi IM LẶNG trong chính nguyên mẫu — và nó suýt lọt

Bản đầu tiên của `tach_thanh()` xoá **mọi** dấu tổ hợp Unicode:

```python
elif unicodedata.category(k) != "Mn":   # SAI
    chu.append(k)
```

Kết quả:
```
dâu    -> dau       nguoi  <- người      nghieng <- nghiêng
```

Dấu **mũ** và **râu** (â, ê, ô, ơ, ư, ă) thuộc về **nguyên âm**, không phải thanh
điệu. Xoá chúng đi là gộp `dâu` với `đau`, `người` với `ngươi`.

Hậu quả: Truyện Kiều **qua được cả chế độ chặt chẽ** — vì bộ kiểm tra đã âm thầm gộp
`au` với `âu`. Nó đúng **vì một lý do sai**, và nếu không in bảng tách vần ra xem thì
lỗi này đã đi thẳng vào `src/` rồi nằm đó.

Đây là lần thứ năm trong ba ngày cùng một bài học: **dụng cụ đo phải được đo.** Bốn
lần trước ở `plan-truy-hoi-xuyen-ngon-ngu.md`; lần này lỗi nằm trong công cụ còn chưa
kịp viết.

### 9.4 Ba chỗ còn phải xử lý

**`qu-` và `gi-` nuốt nguyên âm.** `quả → vần a`, `giả → vần a`. Cách phân tích truyền
thống cũng coi `qu` và `gi` là phụ âm đầu, nên kết quả này chấp nhận được — nhưng cần
ca kiểm tra riêng để nó không lặng lẽ đổi.

**Sai số tiếng làm LỆCH mọi phép kiểm vần phía sau.** Câu 7 tiếng thì "tiếng 6" trỏ vào
chữ khác, và mọi lỗi vần báo sau đó đều là rác. Bộ kiểm tra phải **báo lỗi số tiếng
rồi BỎ QUA phần vần** của những câu đó — nếu không, lời nhắc sinh lại sẽ đầy lỗi giả và
model đi sửa nhầm chỗ.

**Bảng vần thông ở §9.2 mới là một GIẢ THUYẾT.** Nó vừa đủ để Truyện Kiều qua, nhưng
bốn câu không chứng minh được gì. Phải hiệu chuẩn.

### 9.5 Cách hiệu chuẩn bộ kiểm tra — và nó không tốn một đồng nào

Chạy bộ kiểm tra trên **toàn bộ 3.254 câu Truyện Kiều** (hết hạn bảo hộ, tải được),
cộng vài trăm bài ca dao. Mục tiêu: **tỉ lệ báo lỗi giả ≈ 0%**.

Mỗi lần nó báo một câu Kiều là sai luật, đó gần như chắc chắn là **bộ kiểm tra sai**,
không phải Nguyễn Du sai. Đó là một tập kiểm thử vàng gần như hoàn hảo: đã có sẵn, đã
được thừa nhận, và miễn phí.

Việc này phải làm **TRƯỚC** khi dùng bộ kiểm tra để chấm model. Một bộ kiểm tra chưa
hiệu chuẩn sẽ:
- báo lỗi giả → ép model sinh lại vô ích → **tăng latency**, đúng thứ đang muốn giảm;
- hoặc bỏ lọt lỗi thật → thả thơ sai luật ra cho người dùng.

Cả hai đều tệ, và cả hai đều **im lặng**.

### 9.6 Việc này đổi thứ tự làm ở §8

Bước 2 cũ là *"`src/tho/luat.py` + test"*. Giờ tách làm ba, và bước hiệu chuẩn là bắt
buộc:

| # | việc | xong khi |
|---|---|---|
| 2a | `src/tho/luat.py` — đếm tiếng, tách thanh, tách vần | test thuần xanh |
| 2b | Tải Truyện Kiều + ca dao vào `evals/corpus/tho/` | có tệp, ghi rõ nguồn và giấy phép |
| 2c | **Hiệu chuẩn**: chạy bộ kiểm tra trên corpus đó | báo lỗi giả < 1% trên thơ đã được thừa nhận |

Chi phí của cả ba: **0 đồng, 0 lần gọi model.** Đây là phần rẻ nhất và có đòn bẩy cao
nhất của toàn bộ bản kế hoạch — nó quyết định mọi con số về sau có nghĩa hay không.

### 9.7 Ước tính latency cần sửa lại một chỗ

§6.2 ước tính một bài lục bát ~80-120 token. Con số đó giả định ~1 token mỗi tiếng.
Tiếng Việt có dấu thường tốn **1,5-3 token mỗi tiếng** trong các bộ tách token BPE,
nên:

```
lục bát 4 câu   = 28 tiếng  ≈  45-85 token
lục bát 8 câu   = 56 tiếng  ≈  90-170 token
```

Vẫn trong khoảng cũ, nhưng **chưa đo**. `tiktoken` không có trong môi trường này, và
bộ tách token của model đích thì phải có model mới đo được. Ghi lại là một ẩn số, đừng
coi con số ở §6.2 là đã chốt.

---

## 10. Hai phép đo còn nợ, và vì sao chưa làm được hôm nay

**Tỉ lệ lưu lượng của tính năng thơ.** Đây là câu hỏi có thể huỷ cả dự án: nếu thơ
chiếm 1% số tin nhắn thì giảm 2 giây cho 1% lưu lượng **không đổi gì** về latency mà
người dùng cảm nhận. Cần một truy vấn trên `usage_log` — nhưng Postgres đang tắt, và
`usage_log` cũng **không lưu nội dung câu hỏi** (đã ghi ở phần khuyến nghị công cụ
trước đó), nên hiện chưa trả lời được. Đây là một lý do nữa để nối `trace_id` giữa
bảng tin nhắn và `usage_log`.

**Đường cơ sở latency của thơ qua `gpt-5-mini`.** Cần gọi model thật. `DAILY_BUDGET_USD`
đã cạn hôm nay (2,0062 / 2 USD), nên phải chờ sang ngày hoặc nâng hạn mức.

Hai phép đo này đứng **trước** mọi quyết định phần cứng ở §6. Đừng mua GPU trước khi
có chúng.

---

## 11. §0.2 đã có câu trả lời — và nó chặn việc tự host trên máy này

*11/09/2026. Đo bằng `nvidia-smi`, không hỏi nữa.*

```
GPU   NVIDIA GeForce RTX 3050 Ti Laptop
VRAM  4096 MiB  =  4 GB
```

Đối chiếu với bảng ở §0.2:

| lượng tử hoá | cần | có | thiếu |
|---|---|---|---|
| bf16 | ~52 GB | 4 GB | 13× |
| int8 | ~26 GB | 4 GB | 6,5× |
| int4 (AWQ) | ~13-15 GB | 4 GB | **3,5×** |

Ngay cả int4 cũng thiếu **3,5 lần**, và MoE không cứu được: phần thưa nằm ở **phép
tính**, không nằm ở bộ nhớ — toàn bộ expert vẫn phải nạp vào VRAM.

**Đây không phải vấn đề tốc độ. Model sẽ không nạp nổi.** vLLM sẽ dừng ở bước cấp
phát bộ nhớ, trước khi phục vụ request nào.

Và chạy CPU thì đi ngược mục tiêu: 2-8 token/giây nghĩa là một bài lục bát mất 15-60
giây, tệ hơn con số `p95` hiện tại.

### 11.1 Ba đường đi được, xếp theo mức thực tế

**Thuê GPU theo giờ.** 1× A10G 24GB hoặc L4 24GB đủ cho int4. Đây là đường duy nhất
giữ nguyên được model bạn chọn, và nó cũng cho bạn **đo trước khi mua** — đúng thứ §6
đòi hỏi. Đổi lại: dữ liệu rời khỏi máy bạn, nên nếu lý do tự host là *dữ liệu không
được rời máy* thì đường này không giải quyết gì.

**Đổi sang model vừa 4 GB.** Một model 3-4B ở int4 chiếm ~2-3 GB và sinh rất nhanh
trên 3050 Ti. Và đây là chỗ **kiến trúc của bạn có lợi thế thật**: luật thơ đã được
cưỡng chế bằng `tho/luat.py`, nên model nhỏ sai luật thì bộ kiểm tra bắt được và bắt
sinh lại. Model nhỏ + bộ kiểm tra tất định có thể thắng model lớn không có bộ kiểm tra.
Cái model nhỏ thua là **chất lượng ý thơ**, và đó chính là thứ fine-tuning giúp được.

**Giữ model đám mây cho route thơ.** Đường ống đã dựng xong nên đổi lúc nào cũng được
— chỉ là một dòng trong `.env`.

### 11.2 Đường ống đã dựng, chạy được ngay khi có phần cứng

Tự host giờ là **một dòng cấu hình**, không phải một đợt sửa code:

```
POEM_BASE_URL=http://localhost:8000/v1
POEM_MODEL_ID=google/gemma-4-26b-a4b-it
POEM_API_KEY=khoa-gia
```

Để trống thì route thơ dùng model chung — mặc định chạy được ngay, không cần GPU.

Đã sửa bốn chỗ:

| chỗ | vì sao |
|---|---|
| `ModelConfig.base_url` + `api_key` | mỗi route có thể trỏ tới một endpoint khác |
| `ModelConfig.effort` thành tuỳ chọn | Gemma **không có** `reasoning_effort`; gửi lên là bị từ chối cả request |
| `_get_client()` cache theo endpoint | một client duy nhất sẽ gửi khoá của bên này sang bên kia |
| `LlmPort.reply(route=...)` | trước đó `_do_reply` **cứng** `MODELS["reply"]` |

`docker compose --profile tu-host up vllm` dựng máy phục vụ, kèm khai báo GPU và
cache trọng số.

### 11.3 Hai lỗi bắt được trong lúc nối, cả hai đều im lặng

**`_do_reply` cứng `MODELS["reply"]`.** Stage thơ gọi `llm.reply()` và sẽ chạy trên
`gpt-5-mini` **bất kể** `POEM_BASE_URL` đặt gì. Cấu hình trông như có tác dụng, log
trông bình thường, và không có gì báo sai. Đã thêm tham số `route` vào `LlmPort`.

**`MODELS` đọc config lúc import.** Bản đầu đặt `"poem": _model_tho()` thẳng vào dict
cấp module, nghĩa là `import llm.models` đọc biến môi trường — biến chính lệnh `import`
thành một chỗ có thể chết vì thiếu cấu hình, kể cả trong test không dùng tới route đó.

`llm/reranker.py` đã ghi rõ cạm bẫy này từ trước:

> *"Tao luoi luc goi dau tien chu khong luc import: doc config ngay khi import bien
> moi lenh `import` thanh mot cho co the chet vi thieu bien moi truong."*

Tôi đọc dòng đó rồi vẫn mắc đúng lỗi đó. Đã đổi sang `model_cho(route)` có cache, và
có test khoá lại.

### 11.4 Một hệ quả phải biết trước khi bật

Model tự host có giá **0 USD/token** trong `llm/models.py`, vì chi phí thật là **giờ
GPU** và giờ GPU không quy về token một cách trung thực được.

Hệ quả: route `poem` sẽ **không bao giờ** làm `DAILY_BUDGET_USD` nhích lên. Chặn ngân
sách — thứ đã cứu lượt chạy eval hôm nay — **không còn bảo vệ gì** cho route đó. GPU
vẫn tốn tiền thật, chỉ là bot không đếm được.

Nếu sau này chuyển cả bot sang tự host thì chặn ngân sách mất tác dụng hoàn toàn, và
phải thay bằng một chặn khác (số lượt/giờ chẳng hạn). Chưa làm.

