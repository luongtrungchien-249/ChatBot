# Plan: nâng chất lượng thơ từ 0/5 lên mức dùng được

*11/09/2026. Tiếp nối `plan-lam-tho-va-tu-host.md`. Bản kế hoạch, chưa thi công.*

> Tính năng đã chạy đầu-cuối nhưng **chưa dùng được**: 0/5 bài đúng luật, và vòng sinh
> lại không cứu được gì.
>
> **§1-§7 nhắm vào LUẬT. Thang 100 điểm ở §9 cho thấy đó là chỗ gần hết dư địa** —
> luật đã 38,7/45 (86%), còn phần "hay" mới 31,0/55 (56%). **Đọc PHẦN II (§11-§15)
> trước** nếu bạn muốn biết làm gì tiếp; §1-§10 là đường đã đi và các phép đo.

---

## 1. Số đo hiện tại — điểm xuất phát

Sinh 5 lần cùng chủ đề «hoa sen», qua đúng đường tính năng chạy:

```
model gpt-4o-mini · effort=None

  đúng số tiếng + vần (tầng đang ép) : 0/5
  đúng cả bằng-trắc                  : 0/5
  lượt gọi model mỗi bài             : 3-3   (luôn kịch trần)
  độ trễ p50 / p95                   : 4.078 / 5.109 ms
```

Và trên 8 chủ đề khác nhau, một lượt sinh mỗi bài, tách theo tầng luật:

```
                       số tiếng   + vần   + bằng-trắc
gpt-4o-mini (n=8)        6/8       0/8       0/8
gpt-5-mini  (n=1)        1/1       1/1       0/1
```

### 1.1 Ba kết luận rút thẳng từ đó

**Chỗ nghẽn KHÔNG phải đếm chữ.** Model đếm tiếng đúng ~75%. Cái nó hỏng là **vần** và
**bằng-trắc** — tức **ngữ âm tiếng Việt**, không phải khả năng đếm.

**Vòng sinh lại đang là chi phí thuần.** Cả 5 lần dùng hết 3 lượt rồi vẫn sai: 3 lần
chi phí, 3 lần độ trễ, kết quả bằng không. Cơ chế "nói rõ sai ở đâu" — thứ đã đưa chặn
7 từ 3/6 lên 6/6 — **không hiệu quả ở đây**, và §2 giải thích vì sao.

**`gpt-4o-mini` rẻ hơn nhưng cho ra thứ không dùng được.** Chi phí trên mỗi bài *dùng
được* là vô hạn. Mẫu duy nhất của `gpt-5-mini` (số tiếng OK, **vần OK**) gợi ý nó khá
hơn hẳn, nhưng n=1 nên chưa kết luận được — xem §5.

---

## 2. Vì sao lời nhắc sửa không ăn — và cách chữa

Lời nhắc hiện tại nói:

```
câu 1: tiếng 4 ('trời') là thanh bằng, luật cần thanh trắc
```

Model **không hành động được** trên câu đó, vì nó không biết chắc chữ nào mang thanh
nào. Nó phải tự làm ba việc liên tiếp: xác định "trời" mang thanh gì → biết thanh đó
thuộc nhóm bằng hay trắc → nghĩ ra một chữ khác vừa đúng nghĩa vừa đúng thanh. Hỏng ở
bước nào cũng ra kết quả sai, và ta không thấy nó hỏng ở đâu.

**Nhưng hai bước đầu là việc `tach_tieng()` làm được — tất định, miễn phí, chính xác
100%.** Bắt model tự đoán lại thứ ta đã biết chắc là lãng phí đúng thế mạnh của mình.

### 2.1 Bản sửa: chú thích thanh điệu ngay trên dòng thơ

Thay vì mô tả lỗi, **vẽ ra**:

```
Câu 1 sai luật bằng-trắc:

  Xa    xôi   phương  trời   lạ    nơi
  ngang ngang ngang   HUYỀN  nặng  ngang
                      ^^^^^
                      vị trí 4 phải là TRẮC (sắc / hỏi / ngã / nặng),
                      "trời" đang là HUYỀN nên thuộc nhóm BẰNG.
                      Đổi "trời" thành một chữ mang thanh trắc.
```

Model không còn phải suy ra gì. Nó chỉ còn một việc **thuần ngữ nghĩa**: tìm một chữ
khác cùng ý, mang thanh trắc. Đó là việc model làm được.

Chi phí: **0 lượt gọi model, 0 đồng.** Toàn bộ bảng thanh điệu đã có trong `tho/luat.py`.

### 2.2 Với lỗi vần thì đi xa hơn được: gợi ý sẵn chữ

Vần thì khác thanh điệu — ta **liệt kê được** các chữ hiệp vần, vì `lay_van()` và
`_tach_van()` đã tách được âm chính + âm cuối.

```
Câu 2 sai vần: "thơ" (vần ƠO) không hiệp vần "hương" (vần ƯƠNG).

  Tiếng 8 câu bát phải hiệp vần tiếng 6 câu lục sau.
  Chữ hiệp vần với "hương": thương, vương, đường, trường, mương, sương,
  nương, chương, gương, phương...
```

Cần một **từ điển âm tiết tiếng Việt** phân theo (vần, thanh). Đây là phần tốn công
thật của bản kế hoạch — xem §3.2.

### 2.3 Vì sao tin là cách này ăn

Đây đúng là cơ chế đã đo được hiệu quả hai lần trong dự án:

| lần | thay đổi | kết quả |
|---|---|---|
| 10/09 | mô tả công cụ: gọi tên cạm bẫy + ví dụ cụ thể | 1/4 → 4/4 |
| 11/09 | chặn 7: nói **rõ** chưa tra tài liệu, nêu hai nhánh | 3/6 → 6/6 |

Cả hai đều là: **chuyển từ mô tả trừu tượng sang chỉ đích danh**. Lời nhắc thơ hiện
tại vẫn ở mức trừu tượng, và đó là chỗ chưa đụng tới.

---

## 3. Việc phải làm, xếp theo đòn bẩy trên mỗi giờ công

### 3.1 Chú thích thanh điệu trong lời nhắc sửa — LÀM TRƯỚC

Sửa `tho/prompt.py::nhac_sua` để nhận `list[Loi]` thay vì `list[str]`, rồi dựng bảng
chú thích như §2.1 cho lỗi bằng-trắc.

Cần thêm vào `tho/luat.py`:
```python
def chu_thich_thanh(cau: str) -> str:
    """Dòng thơ kèm thanh điệu từng tiếng, để đưa vào lời nhắc sửa."""
```

Không cần từ điển, không cần dữ liệu mới. Ước lượng: **một buổi**.

**Nghiệm thu:** sinh lại 5 lần «hoa sen», tầng *số tiếng + vần* đạt ≥ 2/5. Dưới mức
đó thì bản sửa này không phải thứ đang nghẽn, và phải đọc lại câu trả lời của model để
tìm chỗ khác.

### 3.2 Từ điển âm tiết theo (vần, thanh)

Để gợi ý chữ hiệp vần như §2.2.

**Nguồn**: không cần kho ngoài. Sinh thẳng từ tổ hợp phụ âm đầu × vần × thanh, rồi
**lọc bằng một danh sách từ tiếng Việt có thật** — nếu không sẽ gợi ý ra những chuỗi
không phải từ.

Danh sách từ: lấy từ một bộ từ điển mở (`vietnamese-wordlist`, Hunspell `vi_VN`), hoặc
rút từ chính Truyện Kiều + ca dao ở §3.4 — cách sau ít phụ thuộc hơn và cho ra chữ
**đúng chất thơ**, nhưng vốn từ hẹp hơn.

Ước lượng: **một đến hai ngày**, chủ yếu là làm sạch dữ liệu.

**Nghiệm thu:** mọi chữ gợi ý đều là từ có thật, và đều thật sự hiệp vần khi kiểm lại
bằng `van_nhau()`. Đây là chỗ dễ tự lừa — bộ gợi ý phải bị chính bộ kiểm tra kiểm lại.

### 3.3 Sinh N bài song song, chọn bài tốt nhất

Hiện tại: 3 lượt **tuần tự**, độ trễ cộng dồn, kết quả 0/5.

Đổi thành: sinh 3 bài **đồng thời** bằng `asyncio.gather`, chấm cả ba bằng bộ kiểm tra,
lấy bài ít lỗi nhất. Nếu bài tốt nhất vẫn sai thì mới sửa **một** vòng.

```
                  hiện tại          đề xuất
lượt gọi model      3                 3-4
độ trễ            3 x 1,3s         1 x 1,3s  (+1 vòng sửa nếu cần)
xác suất đạt      P(sửa được)      1 - (1-p)^3
```

Cùng chi phí, **độ trễ giảm ba lần**, và xác suất có một bài đạt cao hơn hẳn — miễn là
các lần sinh độc lập.

Ước lượng: **nửa buổi**. `sinh_tho` đã tách sẵn `goi_model` nên không đụng tới tầng nào
khác.

**Nghiệm thu:** p95 xuống dưới 2.000 ms, và tầng *số tiếng + vần* không thấp hơn bản
tuần tự.

### 3.4 Corpus Truyện Kiều + ca dao

Đã nợ từ `plan-lam-tho-va-tu-host.md` §9.5. Giờ nó phục vụ **ba** việc chứ không phải
một:

1. hiệu chuẩn bộ kiểm tra (`ops/hieu_chuan_tho.py` đã sẵn sàng, đang chờ tệp);
2. nguồn từ vựng cho §3.2;
3. dữ liệu huấn luyện cho §4.

Ước lượng: **nửa buổi** (tải, làm sạch, kiểm định dạng).

**Nghiệm thu:** `ops/hieu_chuan_tho.py` báo lỗi giả < 1% trên ≥ 3.000 câu.

### 3.5 Biến các script đo thành công cụ trong repo

Mọi số trong tài liệu này đến từ script nằm ở thư mục tạm. Chúng sẽ biến mất, và lần
sau sẽ phải viết lại — rồi đo ra một thứ hơi khác mà không ai biết vì sao.

Gom thành `ops/do_tho.py`: nhận danh sách chủ đề, số lần lặp, model; xuất bảng theo
tầng luật + độ trễ. Đây là thứ biến "tôi nghĩ nó khá hơn" thành một con số.

Ước lượng: **một tiếng**. Code đã có, chỉ là dọn lại.

---

## 4. Fine-tune — giờ đã có căn cứ, và đây là điều kiện

`plan-lam-tho-va-tu-host.md` §4.2 viết: *"chỉ làm khi bước prompt chạm trần"*.

**Nó đã chạm trần, và có số: 0/5 sau ba vòng sửa.** Nhưng §3.1 và §3.3 chưa thử, nên
trần đó **chưa phải trần thật**. Thứ tự bắt buộc:

```
3.1 + 3.3  ->  đo lại  ->  vẫn dưới ngưỡng?  ->  MỚI fine-tune
```

Làm ngược lại thì không bao giờ biết fine-tune có đáng không, vì không có đường cơ sở
sạch để so.

### 4.1 Nếu tới bước đó

**Model**: 3-4B ở int4, vì đó là thứ **vừa 4 GB VRAM của máy này** (đo ở
`plan-lam-tho-va-tu-host.md` §11). QLoRA một model 4B huấn luyện được trên 4 GB với
batch nhỏ. LoRA trên 26B thì không — cần 24 GB trở lên.

**Dữ liệu**: 1.000-3.000 cặp (yêu cầu → bài đúng luật), từ §3.4. Bắt buộc **lọc mọi
mẫu qua chính `tho/luat.py` và loại mẫu sai luật** — huấn luyện trên dữ liệu sai luật
là dạy model sai luật, và việc lọc này tất định, gần như miễn phí.

**Cảnh báo về giọng**: Truyện Kiều là văn thế kỷ 19. Huấn luyện nặng vào đó thì bot sẽ
làm thơ chúc mừng sinh nhật bằng giọng cổ. Cần trộn ca dao (gần lời nói thường hơn), và
đo cả **độ tự nhiên** chứ không chỉ độ đúng luật.

---

## 5. Đo lại `gpt-5-mini` khi API hồi

Hôm nay `gpt-5-mini` timeout **15 lần liên tiếp**, nên không so được. Mẫu duy nhất lấy
được: số tiếng OK, **vần OK**, chỉ sai bằng-trắc — khá hơn hẳn `gpt-4o-mini` (0/8 về
vần).

Nếu tái lập được thì kết luận về chi phí **đảo ngược**: `gpt-4o-mini` rẻ hơn theo token
nhưng cho ra thứ không dùng được, tức đắt vô hạn trên mỗi bài dùng được.

Đây là phép đo **rẻ nhất** trong cả bản kế hoạch (khoảng 2 xu) và nó có thể làm thay
đổi mọi lựa chọn sau đó. Chạy nó trước §4, ngay khi API phục vụ được.

---

## 6. Câu hỏi về sản phẩm, phải trả lời trước §4

Nếu sau §3 mà bằng-trắc vẫn 0%, thì có ba lựa chọn, và chúng khác nhau về bản chất chứ
không phải về mức độ:

**Chấp nhận thơ đúng số tiếng + vần, bỏ bằng-trắc.** Người đọc bình thường nhận ra sai
số tiếng và sai vần ngay; bằng-trắc sai nhẹ thì phần lớn không thấy. Đây là lựa chọn
thực dụng, và `EP_BANG_TRAC = False` hiện đã theo hướng này.

**Nói thẳng với người dùng đây là thơ "gần đúng luật".** Trung thực, đúng tinh thần
`SYSTEM_PROMPT` ("không biết thì nói không biết"), nhưng làm tính năng bớt hấp dẫn.

**Bỏ tính năng.** Nếu §10 của tài liệu kia đúng — rằng phải đếm `usage_log` xem người
dùng thật có hỏi loại này không — thì có thể câu trả lời là không ai hỏi. Và
`usage_log` **hiện không lưu nội dung câu hỏi**, nên vẫn chưa trả lời được. Đây là lý
do thứ ba để nối `trace_id` giữa bảng tin nhắn và `usage_log`.

---

## 7. Thứ tự làm, và tiêu chí dừng

| # | việc | ước lượng | xong khi |
|---|---|---|---|
| 1 | `ops/do_tho.py` — công cụ đo | 1 tiếng | chạy lại được số ở §1 |
| 2 | §3.1 chú thích thanh điệu | 1 buổi | *số tiếng + vần* ≥ 2/5 |
| 3 | §3.3 sinh N song song | nửa buổi | p95 < 2.000 ms, không tụt chất lượng |
| 4 | §5 đo lại `gpt-5-mini` | 2 xu | có bảng theo tầng, n ≥ 8 |
| 5 | §3.4 corpus | nửa buổi | hiệu chuẩn < 1% trên ≥ 3.000 câu |
| 6 | §3.2 từ điển vần | 1-2 ngày | mọi chữ gợi ý qua được `van_nhau()` |
| 7 | **Điểm quyết định** — §6 | — | chốt sản phẩm trước khi fine-tune |
| 8 | §4 fine-tune | vài ngày | chỉ khi 2-6 vẫn dưới ngưỡng |

Bước 1 đến 4 gói gọn trong **hai ngày** và nhiều khả năng quyết định được phần lớn vấn
đề. Bước 6 và 8 đắt hơn hẳn — đừng bắt đầu chúng trước khi có số của bước 4.

---

## 8. Đã thi công §3.1 và §3.3 — kết quả đo

*11/09/2026, ngay sau khi viết bản kế hoạch này.*

### 8.1 §3.1 chú thích thanh điệu — KHÔNG ĐẠT ngưỡng

Lời nhắc sửa giờ **vẽ ra** chỗ sai thay vì mô tả nó:

```
Câu 1 sai luật bằng-trắc — tiếng 4 ('trời') là thanh bằng, luật cần thanh trắc:

Xa     xôi    phương  trời   lạ    nơi
ngang  ngang  ngang   huyền  nặng  ngang
                      ^^^^^

Thanh BẰNG là ngang và huyền. Thanh TRẮC là sắc, hỏi, ngã, nặng.
Đổi đúng tiếng được đánh dấu sang một chữ khác cùng ý, đúng thanh.
```

Ngưỡng nghiệm thu đặt ở §3.1 là **≥ 2/5**. Kết quả:

```
                      đúng số tiếng + vần
trước (5 mẫu)               0/5
sau  (5 mẫu)                1/5
sau  (10 mẫu)               0/10
                            ------
gộp 15 mẫu                  1/15  ≈ 7%
```

**Không đạt.** Cái 1/5 là dao động, không phải cải thiện — 10 mẫu tiếp theo về 0.

### 8.2 §3.3 sinh song song — ĐẠT, và cơ chế chứng minh được

```
                     trước      sau
độ trễ p50          4.078ms    3.093ms
độ trễ khi trúng       —       1.656ms
lượt gọi mỗi bài      3,0        3,8
```

Lần trúng duy nhất trong 15 mẫu cho thấy cơ chế hoạt động đúng thiết kế: một trong ba
bản song song đã đúng luật ngay, nên **không tốn vòng sửa nào** — 3 lượt gọi, 1.656ms,
tức nhanh gấp 2,5 lần đường cũ.

Ngưỡng đặt ở §3.3 là p95 < 2.000ms; thực tế 4.593ms. **Chưa đạt**, nhưng lý do là vòng
sửa vẫn phải chạy ở 14/15 bài. Nếu tỉ lệ trúng lên được thì p95 tự xuống theo.

### 8.3 Kết luận: model là chỗ nghẽn, không phải prompt

Lớp câu này giờ đã bị đánh bằng **ba chiến lược prompt khác nhau**:

| | cách | kết quả |
|---|---|---|
| 1 | luật + ví dụ + ví dụ sai trong system prompt | 0/8 về vần |
| 2 | sinh lại 2 vòng, liệt kê mô tả lỗi | 0/5 |
| 3 | sinh song song 3 bản + vẽ ra chỗ sai | 1/15 |

Ba lần, ba cách, cùng một trần. Đây **không còn là bài toán chỉnh câu chữ**.

Giữ lại cả hai bản sửa, nhưng với lý do khác nhau:

- **§3.3 giữ vì nó thắng rõ ràng**: cùng chi phí, độ trễ thấp hơn, và khi model làm
  được thì nó lấy được ngay.
- **§3.1 giữ vì nó không mất gì** — thuần định dạng chuỗi, 0 lượt gọi thêm — và vì
  không tách được tác dụng của nó khỏi §3.3 trong cùng một phép đo. Nhưng **đừng ghi
  nó là một thắng lợi**: chưa có bằng chứng nào nói nó giúp.

### 8.4 Vẫn chưa đo được `gpt-5-mini`

Thử lại hai lần nữa: **timeout 100%** (4/4 và 5/5 lượt, mỗi lượt đã thử lại 3 lần).
`REPLY_TIMEOUT_S = 15s` có thể quá ngắn cho model này hôm nay, nhưng cũng có thể API
đang hỏng thật — không phân biệt được từ phía này.

Mẫu duy nhất lấy được hôm qua vẫn là dữ kiện đáng giá nhất còn lại: số tiếng OK,
**vần OK**, chỉ sai bằng-trắc. Nếu tái lập được trên 8-10 mẫu thì kết luận đảo hẳn, và
toàn bộ §4 (fine-tune) có thể không cần tới.

**Đây là việc phải làm trước mọi việc khác trong tài liệu này.**

### 8.5 Một bài đúng luật, để biết đích trông thế nào

Bài duy nhất qua được bộ kiểm tra trong 15 lần:

```
Hoa sen nở rực giữa trời
Tỏa hương thơm ngát ngàn nơi sông rồng
Tựa như nét đẹp trong dòng
Mang tâm hồn Việt thắm nồng với đời
Lá xanh vươn giữa mây trời
Sóng gợn bao la như lời yêu thương
Cứ nở trong cái bình thường
Thể hiện vẻ đẹp tròn vương cuộc đời.
```

Đúng 6-8 toàn bài, vần chuẩn (trời/nơi, rồng/dòng, đời/trời, thương/thường). Nhưng
đọc kỹ thì *"ngàn nơi sông rồng"* và *"tròn vương cuộc đời"* là chữ ghép cho đủ vần,
không có nghĩa rõ.

Nghĩa là kể cả khi **đúng luật**, chất lượng ý vẫn là vấn đề riêng — và đó là thứ bộ
kiểm tra không đo được, chỉ người chấm hoặc người đọc mới thấy. §6 của tài liệu này
(câu hỏi về sản phẩm) vì thế vẫn đứng nguyên.

---

## 9. Thang 100 điểm — và nó đổi hẳn chẩn đoán

*11/09/2026, theo bản đặc tả lục bát của người dùng.*

Chia đôi đúng ranh giới giữa "đo được" và "phải có người đọc":

```
TẤT ĐỊNH   45đ   thể 6-8 (10) · vần (20) · bằng-trắc (15)     src/tho/cham_diem.py
PHẢI CHẤM  55đ   nhịp (15) · ngôn ngữ (10) · hình ảnh (10) ·  evals/metrics/tho_hay.py
                 ý nghĩa (10) · cảm xúc (5) · sáng tạo (5)
```

Truyện Kiều được **45/45** tất định — bộ chấm không tự bịa ra lỗi trên thơ chuẩn mực.

### 9.1 Kết quả: 69,7/100 trung bình, và chỗ mất điểm KHÔNG phải luật

5 bài «hoa sen», `gpt-4o-mini`, prompt v2:

```
tất định trung bình    38,7/45    (86%)
phải chấm trung bình   31,0/55    (56%)
TỔNG                   69,7/100

    nhịp          7,8/15   52%
    ngôn ngữ      4,4/10   44%   <- thấp nhất
    hình ảnh      6,4/10   64%
    ý nghĩa       7,6/10   76%   <- cao nhất
    cảm xúc       3,0/5    60%
    sáng tạo      1,8/5    36%   <- thấp nhất
```

Bài cao nhất được **74,1/100**, trong đó tất định **43,1/45** — gần như hoàn hảo về
luật — mà phải chấm chỉ **31/55**.

### 9.2 Đòn bẩy đảo chiều

Đây là con số làm thay đổi thứ tự việc của cả tài liệu:

```
còn có thể kiếm thêm ở TẤT ĐỊNH   45 - 38,7 =  6,3 điểm
còn có thể kiếm thêm ở PHẢI CHẤM  55 - 31,0 = 24,0 điểm
```

**Gấp gần bốn lần.** Suốt hai ngày qua mọi bản sửa đều nhắm vào phần tất định — vần,
bằng-trắc, đếm tiếng. Phần đó giờ đã ở 86% và trần chỉ còn 6,3 điểm.

Nghĩa là §3.2 (từ điển vần, ước lượng 1-2 ngày) mua được **nhiều nhất vài điểm** trong
số 6,3 đó. Nó tụt xuống cuối danh sách.

### 9.3 Hai mục tệ nhất nói đúng một điều

`ngôn ngữ 44%` và `sáng tạo 36%` — cả hai đều là **ép vần**. Người chấm được dặn trừ
mạnh những cụm nhét vào chỉ để khớp vần, và nó trừ thật.

Prompt v2 đã nói thẳng *"Ý → hình ảnh → chữ → rồi mới xử lý vần"*, kèm một ví dụ phản
diện lấy từ chính bài bot vừa làm (*"tròn vương cuộc đời"*). **Vẫn 44%.** Đây là lần
thứ tư một bản sửa bằng câu chữ không dời được kim.

Bài cao điểm nhất vẫn chứa *"Đời người như thể, một đà vươn cao"* — "một đà" là chữ
nhét vào cho đủ tiếng và đủ vần.

### 9.4 Việc phải làm, xếp lại theo đòn bẩy

| # | việc | mua được tối đa | ghi chú |
|---|---|---|---|
| 1 | đo lại `gpt-5-mini` trên thang 100 | không rõ | vẫn chưa chạy được, xem §8.4 |
| 2 | fine-tune nhắm vào **giọng và hình ảnh** | ~24đ | đây mới là chỗ có dư địa |
| 3 | corpus Kiều + ca dao | điều kiện của (2) | và của hiệu chuẩn |
| 4 | §3.2 từ điển vần | vài điểm trong 6,3 | **hạ xuống cuối** |

Và một việc mới, rẻ: **`nhịp 52%` chưa ai đụng tới.** Nhịp 2/2/2 phụ thuộc chỗ ngắt
TỪ, nên muốn kiểm tất định thì cần một từ điển từ ghép tiếng Việt — cùng loại dữ liệu
với §3.2, nên hai việc đó nên làm chung một lần.

### 9.5 Cảnh giác với chính thang điểm này

55 điểm kia do một model chấm, và tài liệu `plan-truy-hoi-xuyen-ngon-ngu.md` ghi **bốn
lần** người chấm sai trong ba ngày. Chưa có gì kiểm chứng rằng `nhịp 7,8/15` là con số
thật chứ không phải thói quen chấm của model.

Cách kiểm rẻ nhất: **chấm Truyện Kiều bằng chính thang 55 điểm đó.** Nếu Nguyễn Du
không được điểm cao thì người chấm sai, không phải thơ sai — đúng nguyên tắc đã dùng
cho phần tất định. Chưa làm.


---

## 10. Hiệu chuẩn người chấm — chạy rồi, và nó bắt được hai lỗi

*11/09/2026. Nguyên tắc y hệt phần tất định: nếu Nguyễn Du không được điểm cao thì
NGƯỜI CHẤM sai, không phải thơ sai.*

```
bài                          tất định   phải chấm
Kiều — mở đầu                 45,0/45     53,0/55
Ca dao — bầu bí               45,0/45     52,0/55
Kiều — cảnh và tình           38,3/45     42,0/55   <- tất định thấp bất thường
Ca dao — công cha             44,1/45     39,0/55   <- phải chấm bằng đúng bài của bot
BOT làm — hoa sen             43,1/45     39,0/55
VĂN XUÔI xuống dòng           12,6/45     21,0/55   (ca âm)
```

### 10.1 Người chấm ĐẠT, với một ngoại lệ

Thơ chuẩn mực 52-53, bot 39, văn xuôi xuống dòng 21. Thang điểm **phân biệt được** ba
mức — đó là điều kiện tối thiểu để nó dùng được, và nó đạt.

Ngoại lệ: *"Công cha như núi Thái Sơn"* chỉ được 39/55, bằng đúng bài của bot, với
`sáng tạo = 1`. Người chấm trừ nó vì **quá quen thuộc**. Về mặt nào đó không sai —
nhưng nó cho thấy người chấm **không phân biệt được "sáo vì quá nổi tiếng" với "sáo vì
lười"**. Với việc chấm thơ MỚI do bot làm thì điểm yếu này ít hại, nên chưa sửa.

### 10.2 Một lỗi THẬT trong bộ kiểm tra tất định — chưa sửa, và có lý do

Đoạn Kiều thứ hai bị chấm 38,3/45 vì bộ kiểm tra báo `giờ` (vần **ơ**) không hiệp vần
`kề` (vần **ê**):

```
Cảnh nào cảnh chẳng đeo sầu
Người buồn cảnh có vui đâu bao giờ      <- giờ
Đòi phen gió tựa hoa kề                 <- kề
Nửa rèm tuyết ngậm bốn bề trăng thâu
```

Theo nguyên tắc đã dùng suốt tài liệu này — *"báo sai trên thơ chuẩn mực thì BỘ KIỂM
TRA SAI"* — đáng lẽ phải thêm {ơ, ê} vào bảng thông vần ngay.

**Chưa thêm.** Đoạn thơ trên được chép **từ trí nhớ**, chưa đối chiếu bản in. Nếu nhớ
sai mà lại nới bảng vần theo nó thì ta phá bộ kiểm tra bằng đúng loại tự lừa mà nó sinh
ra để chống — và lần này sẽ không ai phát hiện, vì bộ kiểm tra nới lỏng thì chỉ im
lặng cho qua.

Đã ghi thành `_NGHI_THONG_VAN` trong `tho/luat.py`, kèm test ghim hành vi hiện tại và
một test bảo đảm danh sách nghi ngờ **không** bị nối vào `van_nhau()` mà không ai biết.

**Điều kiện để bật:** đối chiếu corpus Truyện Kiều thật. Nếu cặp vần đó xuất hiện nhiều
lần trong 3.254 câu thì bật, kèm kiểm thử.

Việc này đẩy §3.4 (corpus) từ *"nên có"* thành **chặn**: giờ có ba thứ chờ nó — hiệu
chuẩn bộ kiểm tra, xác minh {ơ, ê}, và dữ liệu fine-tune.

### 10.3 Sự cố hạ tầng trong lúc đo

OpenAI trả **Cloudflare 520** (`retryable: true, retry_after: 60`) giữa lượt chạy. Đây
cũng là lời giải cho chuỗi timeout của `gpt-5-mini` suốt hôm nay — người chấm đi qua
route `summarize`, tức cùng model đó.

Script đo đã có thử lại với giãn cách. **Đường production thì chưa**: `AsyncOpenAI` đặt
`max_retries=0` có chủ ý, và đổi nó là đổi hành vi thật của bot — cần đo trước, chưa
làm.

---

# PHẦN II — làm sao cho thơ HAY, không phải cho thơ ĐÚNG LUẬT

*11/09/2026. Phần I (§1-§7) nhắm vào luật. Thang 100 điểm ở §9 cho thấy đó là chỗ
gần hết dư địa. Phần này viết lại kế hoạch theo chẩn đoán mới.*

## 11. Dư địa nằm ở đâu — bằng số

```
                     đang có     trần    còn kiếm được
tất định (luật)      38,7/45      45          6,3
phải chấm (hay)      31,0/55      55         24,0
                                             -----
                                             gấp 3,8 lần
```

Và trong 24 điểm đó, chỗ thủng lớn nhất rất rõ:

```
  ngôn ngữ      4,4/10   44%     thiếu 5,6   <- ép vần
  sáng tạo      1,8/5    36%     thiếu 3,2   <- ép vần
  nhịp          7,8/15   52%     thiếu 7,2   <- chưa ai đụng
  hình ảnh      6,4/10   64%     thiếu 3,6
  cảm xúc       3,0/5    60%     thiếu 2,0
  ý nghĩa       7,6/10   76%     thiếu 2,4   <- tốt nhất
```

**Nhịp (7,2) và ngôn ngữ + sáng tạo (8,8) chiếm 2/3 số điểm đang mất.**

## 12. Vì sao bảo model "đừng ép vần" không có tác dụng

Đã thử **bốn** lần, bốn cách, cùng một trần:

| | cách | kết quả |
|---|---|---|
| 1 | luật + ví dụ + ví dụ sai trong system prompt | 0/8 về vần |
| 2 | sinh lại 2 vòng, liệt kê mô tả lỗi | 0/5 |
| 3 | sinh song song + vẽ ra chỗ sai | 1/15 |
| 4 | prompt v2: "Ý → hình ảnh → chữ → rồi mới vần", kèm ví dụ phản diện | ngôn ngữ vẫn 44% |

Lần 4 nói **đúng** điều cần nói, kèm ví dụ lấy từ chính bài bot vừa làm hỏng. Vẫn 44%.

Lý do là **cơ chế sinh**, không phải chỉ dẫn. Model viết trái sang phải. Khi nó đi tới
tiếng thứ 6 của câu lục, cả câu đã viết xong rồi — nó **không còn tự do chọn nghĩa**,
chỉ còn chọn một chữ vừa vần. Nên nó nhét *"một đà"*, *"tròn vương"*.

Bảo nó "nghĩ ý trước" không đổi được điều đó, vì tới lúc chạm vị trí vần thì ý đã cạn
chỗ xoay. **Phải đổi thứ tự sinh, không phải đổi lời dặn.**

## 13. Bốn hướng, xếp theo cơ chế chứ không theo công sức

### 13.1 Chọn CẶP VẦN trước, viết câu sau — đánh thẳng vào cơ chế

Sinh hai giai đoạn:

```
Giai đoạn 1 — chỉ chọn chữ, chưa viết câu:
  "Chủ đề «hoa sen». Cho 3 cặp từ hiệp vần, mỗi từ phải CÓ NGHĨA và gợi được
   hình ảnh thuộc chủ đề. Không cần thành câu."
      -> sen/chen · hồng/dòng · sương/vương

Giai đoạn 2 — viết câu quanh những chữ đã chọn:
  "Viết lục bát, dùng ĐÚNG các chữ này ở vị trí vần: ..."
```

Vì sao tin là ăn: ở giai đoạn 1, model **chỉ có một việc** — chọn chữ có nghĩa. Không
bị sức ép phải vừa đủ tiếng, vừa hợp câu trước, vừa vần. Tới giai đoạn 2 thì các chữ
vần đã **được chọn vì nghĩa**, nên câu xây quanh chúng không phải nhét.

Và ta **kiểm được giai đoạn 1 bằng code**: `van_nhau()` xác minh các cặp có thật hiệp
vần không, trước khi tốn lượt thứ hai.

Giá: 2 lượt gọi thay vì 1, nhưng lượt 1 rất ngắn (chỉ vài chữ) nên độ trễ tăng ít.

**Nghiệm thu:** `ngôn ngữ` ≥ 6,5/10 và `sáng tạo` ≥ 2,5/5 trên 5 bài. Đây là hai mục
mà giả thuyết này nhắm tới — nếu chúng không nhúc nhích thì giả thuyết sai, ghi lại và
gỡ bỏ.

### 13.2 Bài mẫu ĐÚNG CHỦ ĐỀ, lấy bằng chính hệ RAG đã có

Prompt hiện dùng **một** bài mẫu cố định (ca dao "công cha"), bất kể người dùng hỏi
chủ đề gì. Với chủ đề "hoa sen" thì bài mẫu đó chẳng dạy được gì về hình ảnh sen.

Dự án đã có sẵn cả đường ống: `kb_chunk`, embedding, `knowledge.search`. Nạp ca dao +
Truyện Kiều vào một `pham_vi` riêng, rồi **truy hồi theo chủ đề** để lấy 2-3 bài mẫu
gần nhất làm few-shot.

Đây là chỗ hai phần của dự án gặp nhau, và nó gần như không tốn gì mới: đường truy hồi
đã được đo suốt ba ngày và đang ở Context Recall 0,835.

Rủi ro phải canh: bài mẫu cổ kéo giọng bot về thế kỷ 19. Đo bằng chính mục `ngôn ngữ`
và `sáng tạo`.

**Nghiệm thu:** `hình ảnh` ≥ 7,5/10, và `ngôn ngữ` không tụt.

### 13.3 Nhịp — chưa ai đụng, và đang mất 7,2 điểm

Nhịp 2/2/2 và 3/3 phụ thuộc **chỗ ngắt TỪ**, nên kiểm tất định được nếu có từ điển từ
ghép tiếng Việt:

```
Trăm năm / trong cõi / người ta      2/2/2   ✓
Hoa sen / nở rực / giữa trời         2/2/2   ✓
Đời người / như thể / một đà / vươn cao    <- "một đà" khong phai mot tu
```

Cùng loại dữ liệu với §3.2 (từ điển vần), nên **làm chung một lần**. Có từ điển rồi thì
nhịp chuyển từ "phải chấm" sang "tất định" — tức 15 điểm nữa đo được bằng code, và
người chấm bớt được một việc nó làm không đáng tin.

**Nghiệm thu:** chấm nhịp bằng code trên Truyện Kiều cho ≥ 90% câu đúng nhịp chuẩn.

### 13.4 Fine-tune — nhắm vào giọng, không nhắm vào luật

Giờ mới đúng lúc, và mục tiêu đã rõ hơn nhiều so với §4: **không phải dạy đếm tiếng**
(code làm rồi, 86%), mà dạy **cách chọn chữ và dựng hình ảnh** — tức đúng 24 điểm đang
mất.

Điều kiện không đổi: làm sau 13.1 và 13.2, để có đường cơ sở sạch mà so.

## 14. Câu hỏi phải trả lời trước khi làm 13.4

**69,7/100 có phải là tệ không?**

Thơ chuẩn mực được 97-98/100 (Kiều 45+53, ca dao bầu bí 45+52). Bot được 69,7. Khoảng
cách rõ.

Nhưng bot đang làm thơ **chúc mừng sinh nhật đồng nghiệp trong nhóm Zalo**, không dự
thi. Một bài 70/100 đúng luật, đọc trôi, có một hình ảnh dùng được — với mục đích đó có
thể là đủ.

Ba mức để chọn, và chúng khác nhau về công sức cả chục lần:

| mức | điểm | công sức | đủ cho việc gì |
|---|---|---|---|
| đang có | ~70 | đã xong | thơ vui trong nhóm chat |
| sau 13.1 + 13.2 | ~80? | vài ngày | thơ tặng, đọc được ra miệng |
| sau fine-tune | ~85? | vài tuần | thơ có câu đắt |

Hai con số sau là **phỏng đoán**, không phải đo. Tôi để dấu hỏi có chủ ý.

**Đây là câu hỏi của bạn, không phải của tôi.** Nhưng nếu câu trả lời là "70 là đủ" thì
toàn bộ §13 không cần làm, và việc đúng tiếp theo là ngược lại: đo xem người dùng thật
có hỏi làm thơ không (mà `usage_log` hiện vẫn chưa lưu nội dung câu hỏi).

## 15. Thứ tự, và tiêu chí dừng của từng bước

| # | việc | công sức | nghiệm thu |
|---|---|---|---|
| 1 | **corpus Kiều + ca dao** | nửa buổi | đang chặn BA thứ, xem §10.2 |
| 2 | §13.1 chọn cặp vần trước | một buổi | ngôn ngữ ≥ 6,5 · sáng tạo ≥ 2,5 |
| 3 | đo lại thang 100 | vài xu | tổng ≥ 76/100 |
| 4 | §13.2 bài mẫu theo chủ đề | một buổi | hình ảnh ≥ 7,5, ngôn ngữ không tụt |
| 5 | **điểm quyết định** §14 | — | chốt "đủ tốt" là bao nhiêu |
| 6 | §13.3 nhịp bằng code | 1-2 ngày | ≥ 90% câu Kiều đúng nhịp |
| 7 | §13.4 fine-tune | vài tuần | chỉ khi 2-6 chưa đủ |

Bước 1 và 2 gói trong **một ngày** và đủ để biết §13.1 có đúng hướng không. Đừng bắt
đầu bước 6 hay 7 trước khi có số của bước 3.

### 15.1 Một điều cần giữ suốt

Mỗi bước ở trên đều phải đo bằng **cùng một thang 100 điểm**, trên **cùng bộ chủ đề**.
Ba ngày qua đã cho thấy cái giá của việc đổi thước đo giữa chừng: bốn lần một con số
tụt hoá ra là lỗi thước đo chứ không phải lỗi hệ thống.

Và người chấm 55 điểm cũng phải được **chấm lại bằng thơ chuẩn mực** mỗi lần sửa
prompt của nó — đúng như §10 vừa làm.


---

## 16. §13.1 đã thi công, đã đo, và ĐÃ GỠ BỎ

*11/09/2026, ngay sau khi viết §13.*

Giả thuyết: model ép vần vì nó viết trái sang phải, tới vị trí vần thì cả câu đã xong
nên không còn tự do chọn nghĩa. Chọn chữ vần **trước** thì chữ được chọn **vì nghĩa**,
và câu xây quanh chúng sẽ không phải nhét.

Đã dựng đủ: `tho/chon_van.py` — giai đoạn 1 chỉ chọn chữ, kiểm bằng `van_nhau()` trước
khi tốn lượt thứ hai, giai đoạn 2 chỉ rõ chữ nào đặt ở vị trí nào.

### 16.1 Kết quả: tệ hơn hẳn

```
                  một giai đoạn   hai giai đoạn
tất định             38,7/45         27,9/45     <- SỤP
phải chấm            31,0/55         29,2/55
TỔNG                69,7/100        57,1/100     <- tụt 12,6
độ trễ p50            2.953ms         4.797ms
ngôn ngữ              4,4/10          4,6/10     <- không nhúc nhích
sáng tạo              1,8/5           1,0/5      <- tệ hơn
```

Ngưỡng nghiệm thu ở §13.1 là `ngôn ngữ ≥ 6,5` và `sáng tạo ≥ 2,5`. **Trượt xa** — và
còn kéo sập cả phần tất định vốn đang ổn.

### 16.2 Vì sao sập — và bài học

Bài sinh ra dài **6 câu thay vì 4**, và các chữ vần bị đặt **sai vị trí**.

Ép model dùng ĐÚNG những chữ đó ở ĐÚNG những chỗ đó là thêm một ràng buộc **cứng** vào
một việc nó vốn đã làm không xong. Nó không thoả mãn được cả hai, và **buông cả hai**.

Bài học, và nó ngược với trực giác đã dẫn tới §13.1: **giảm bậc tự do của model không
làm nó chính xác hơn — nó làm model hỏng ở chỗ khác.** Cùng một hiện tượng đã thấy ở
`plan-truy-hoi-xuyen-ngon-ngu.md` §28: luật "giữ đúng mức cụ thể" kéo 4/6 xuống 2/6 vì
model chuyển sang chèn tiếng Việt vào truy vấn.

Hai lần, hai chỗ, cùng một hình dạng: **thêm một ràng buộc thì model lách sang chỗ
khác.**

### 16.3 Đã tắt, giữ code

`CHON_VAN_TRUOC = False`. Code giữ lại vì giả thuyết vẫn có lý với model mạnh hơn hoặc
sau fine-tune — bật bằng `chon_van_truoc=True`. Có test ghim để không ai bật lại mặc
định mà không đo lại.

### 16.4 Điều này đổi gì trong kế hoạch

§13.1 là hướng tôi xếp **đầu tiên** vì nó đánh thẳng vào cơ chế. Nó hỏng.

Ba hướng còn lại của §13 chưa bị ảnh hưởng, nhưng thứ tự nên đổi:

1. **§13.2 bài mẫu đúng chủ đề** — giờ là hướng đầu. Nó **thêm** thông tin chứ không
   **thêm ràng buộc**, nên nó không dính bài học §16.2.
2. **§13.3 nhịp bằng code** — đo được, không đụng vào cách model sinh.
3. **§13.4 fine-tune** — dạy giọng, cũng không phải ràng buộc lúc sinh.

Cả ba đều tránh được đúng cái bẫy vừa sập. Đó không phải trùng hợp: **§13.1 là hướng
duy nhất siết model lúc sinh, và nó là hướng duy nhất hỏng.**


---

## 17. Đối chiếu đặc tả lục bát của người dùng với thực tế đã cài

*11/09/2026. Người dùng gửi một bản đặc tả lục bát đầy đủ 10 mục kèm thang 100 điểm.
Mục này đối chiếu từng mục với code.*

| # | mục trong đặc tả | cài ở đâu |
|---|---|---|
| 1 | số tiếng 6-8, kết thúc câu bát | `luat.kiem_luc_bat` |
| 2 | vần 6→6, 8→6 | `luat.van_nhau` — **xem §17.2** |
| 3 | vần êm, ý → từ → vần | `prompt.py` v2 + người chấm `ngon_ngu` |
| 4 | bằng-trắc `x B x T x B` | `cham_diem._LUC/_BAT` |
| 5 | nhịp 2/2/2, 3/3 | `luat.kiem_nhip` — **một phần**, xem §17.1 |
| 6 | nhạc, không chỉ đếm chữ | người chấm `nhip` + `ngon_ngu` |
| 7 | ý thơ tự nhiên | `prompt.py` v2 + người chấm `y_nghia` |
| 8 | checklist 7 tiêu chí | thang 100 điểm |
| 9 | vần đẹp / nhạc đẹp | người chấm |
| 10 | **câu đắt** | đã thêm vào tiêu chí `sang_tao` |

### 17.1 Nhịp — kiểm được một phần, và phần đó phải nói rõ

Nhịp 2/2/2 phụ thuộc **chỗ ngắt TỪ** (*"Trăm năm / trong cõi / người ta"*), mà biết chỗ
ngắt từ thì cần một từ điển từ ghép tiếng Việt — chưa có.

Cái kiểm được, tất định và không cần từ điển: **dấu phẩy do chính người viết đặt**. Đơn
vị nhịp của lục bát là chẵn (2/2/2, 2/2/2/2, 4/4), trừ nhịp 3/3 của câu lục. Dấu phẩy
rơi vào vị trí ngoài tập đó thì câu gần như chắc chắn gãy nhịp.

```
Lá xanh ôm ấp, dáng hồng kiêu sa      phẩy sau tiếng 4  -> hợp lệ
Cảnh nào cảnh, chẳng đeo sầu           phẩy sau tiếng 3  -> hợp lệ (nhịp 3/3)
Đời người như, thể một đà vươn cao     phẩy sau tiếng 3 ở câu bát -> GÃY
```

**Không có dấu phẩy thì trả `None`, KHÔNG phải "đúng nhịp".** Gộp hai cái đó làm một sẽ
biến một phép kiểm *một phần* thành một lời bảo đảm sai — có test riêng chặn việc này.

Muốn kiểm nhịp đầy đủ thì cần từ điển từ ghép, cùng loại dữ liệu với §3.2. Hai việc đó
nên làm chung một lần.

### 17.2 Một bất thường CHƯA GIẢI THÍCH ĐƯỢC ở luật vần

Luật vần ở mục 2 của đặc tả đã cài đúng. Nhưng *"thế nào là hiệp vần"* thì có vấn đề.

Đo trên một corpus lục bát 3.254 câu:

```
A: lục[6] ~ bát[6]        1130/1627 = 69,5%
B: bát[8] ~ lục kế[6]     1153/1626 = 70,9%
```

Hai mối vần thất bại **ngang nhau**, nên đây không phải lỗi ghép cặp — bảng vần thông
đang **từ chối nhầm khoảng 30%** số cặp vần hợp lệ.

Rút bảng từ chính dữ liệu thì nhóm nhiều dẫn chứng nhất là `{a, ươ}` (101 lần), tức
*"trang"* hiệp vần *"nhường"* — điều không người Việt nào chấp nhận.

**Nên KHÔNG nới bảng.** Có hai khả năng chưa phân biệt được: hoặc luật vần lục bát lỏng
hơn mô tả chuẩn, hoặc corpus/cách tách của tôi có lỗi hệ thống chưa thấy. Nới bảng theo
dữ liệu chưa hiểu sẽ làm bộ kiểm tra **im lặng chấp nhận thơ sai vần** — hỏng theo đúng
kiểu không ai phát hiện được.

Hệ quả cần biết: điểm `vần` trong thang 100 hiện **chấm chặt hơn thực tế**. Bài của bot
bị trừ oan một phần, và khoảng cách thật giữa bot với thơ chuẩn mực **hẹp hơn** con số
đang thấy.


## 18. Khung 6-8 thành LUẬT CỨNG (11/09/2026)

Yêu cầu người dùng: *"phải tuân theo luật theo yêu cầu của thể thơ lục bát thì là các
cặp 6 chữ và 8 chữ phải đầy đủ thông tin (bắt buộc)"*.

**Bắt buộc** khác **điểm trừ**, và trước hôm nay code đối xử với nó như điểm trừ.

### 18.1 Cái đã hỏng, và nó hỏng im lặng

Số tiếng vẫn luôn được kiểm. Nhưng chỗ **chọn bản** đếm gộp mọi loại lỗi:

```python
tot_nhat, loi_tot_nhat = min(ung_vien, key=lambda x: len(x[1]))
```

Một bản **đúng khung** sai 6 vần (7 lỗi) thua một bản **sai khung** sai 1 vần (2 lỗi).
Ta có sẵn bản đạt và tự tay chọn bản hỏng.

Đo được, và hai con số phải đặt cạnh nhau mới thấy:

| | |
|---|---|
| một bản sinh ra đúng khung | **65%** (13/20 bản, `gpt-4o-mini`) |
| bài CUỐI CÙNG trả cho người dùng đúng khung | **0/6** |

Nguyên liệu tốt sẵn có, khâu chọn làm hỏng.

### 18.2 Bốn thay đổi

| | cái gì | vì sao |
|---|---|---|
| 1 | `luat.danh_so_tieng` | vẽ số thứ tự từng tiếng ra thay vì bảo model tự đếm |
| 2 | `prompt.nhac_sua` | dùng bản vẽ đó cho lỗi `so_tieng`, nói rõ "sửa số tiếng TRƯỚC" |
| 3 | `sinh._xep_hang` | chọn bản theo `(lỗi KHUNG, lỗi còn lại)` — thứ tự từ điển, không đếm gộp |
| 4 | `sinh._cat_ve_khung_dung` | lưới cuối: bỏ cặp hỏng, giữ cặp đúng |

Cộng thêm: `SO_BAN` 3 → 4, và `SO_LAN_SUA_KHUNG = 1` — một vòng sửa dành **riêng** cho
khung, chỉ bung ra khi khung còn sai.

**Vì sao vẽ số ra.** 35% số bản sinh sai số tiếng, tức phép đếm của model không đáng
tin. Bảo nó *"câu này có 7 tiếng"* là bắt nó đếm lại bằng đúng cái khả năng vừa hỏng.
`cau.split()` đếm đúng 100%, tất định, miễn phí. Cùng cơ chế đã ăn hai lần trước đó —
mô tả công cụ 10/09 (1/4 → 4/4) và chặn 7 ngày 11/09 (3/6 → 6/6): chuyển từ **mô tả
trừu tượng** sang **chỉ đích danh**.

**Vì sao cần lưới cắt.** Sinh nhiều bản chỉ cho ra **xác suất**: 65% mỗi bản → 4 bản
cho ~98,5%. Với một luật BẮT BUỘC thì 98,5% không đủ — nó vẫn nghĩa là thỉnh thoảng
người dùng nhận về một thứ không phải lục bát. Lục bát **không có độ dài cố định**, nên
bỏ cặp hỏng và giữ cặp đúng vẫn cho ra một bài đúng thể. Giá phải trả: bài ngắn hơn,
mạch ý có thể đứt. Rẻ hơn hẳn việc trả ra thứ không phải lục bát.

Hàm cắt thử **cả hai cách ghép cặp** (từ câu 1 và từ câu 2): một dòng tựa đề thừa lọt
vào đầu bài làm lệch toàn bộ các cặp phía sau, và ghép từ câu 2 cứu được cả bài.

Dưới 2 cặp thì **không cứu** — trả về bài gốc kèm `CON_LOI_KHUNG`, câu nói nặng hơn hẳn
`CON_LOI`: sai vần thì bài **vẫn là** lục bát, chỉ đọc không xuôi; sai số tiếng thì nó
**không phải** lục bát. Dùng chung một câu cho cả hai là nói giảm một lỗi hỏng thể loại
thành một lỗi nhỏ.

### 18.3 Kết quả đo

Sáu bài qua `handle_message`, hai chủ đề, `gpt-4o-mini`:

| | trước | sau |
|---|---|---|
| thể 6-8 | 8,1/10 | **10,0/10** |
| vần | 7,0/20 | 10,8/20 |
| bằng-trắc | 12,6/15 | 13,3/15 |
| TỔNG | 61,0/100 | **66,2/100** |
| độ trễ p50 | 2.890 ms | 2.953 ms |

Nghiệm thu riêng luật bắt buộc, 12 bài trên **6 chủ đề khác nhau** (một chủ đề thì đo
phải khả năng thuộc bài):

```
ĐÚNG KHUNG 6-8 : 12/12 = 100%
độ trễ p50     : 2.938 ms
lượt gọi/bài   : 5,0
```

Bốn bản chạy **song song** nên bản thứ tư không cộng độ trễ — chỉ cộng ~0,0008 USD mỗi
bài. Điểm `vần` lên theo vì lý do máy móc: câu sai số tiếng làm *"tiếng 6"* trỏ vào chữ
khác, nên mọi phép kiểm vần trên câu đó đều cho lỗi giả.

### 18.4 Còn lại

**Vòng sửa chạy ở MỌI bài** (5,0 lượt gọi/bài, không bài nào 4). Vì 0/20 bản sinh ra
đúng hết vần, nên luôn còn lỗi để sửa. Nó cộng một lượt gọi tuần tự vào độ trễ của mọi
bài, trong khi §16 đã đo được rằng sửa **gần như không ăn** với lỗi vần. Bỏ vòng sửa
khi chỉ còn lỗi vần sẽ cắt ~1,3s/bài. **Chưa làm** — cần đo lại vì phép đo cũ có trước
khi `nhac_sua` biết vẽ số.

**Vần vẫn là chỗ yếu** (10,8/20), và một phần là bảng vần thông từ chối nhầm — xem §17.2.

> Cả hai chỗ treo ở §17.2 và §18.4 nay có kế hoạch riêng:
> **`docs/plan-sua-bo-kiem-van.md`**. Nhóm `{a, ươ}` phi lý ở §17.2 đã giải thích
> được: thống kê cũ gộp mọi âm cuối làm một, tách theo âm cuối thì nó là ba thứ
> khác nhau.
