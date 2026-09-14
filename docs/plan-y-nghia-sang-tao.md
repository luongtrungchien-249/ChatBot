# Nâng `ý nghĩa` và `sáng tạo` của thơ — plan

> Ngày lập: 14/09/2026. Trạng thái: **bước 0 và B1 đã xong** (§8). B1 trượt và đã tắt.
> B2, B3 chưa làm — và §8.4 đổi điều kiện cho chúng.
>
> Yêu cầu: *"Làm thế nào để tôi có thể cải thiện được phần ý nghĩa và sáng tạo của thơ"*
> → *"lên plan thực hiện sửa cho tôi"*.

---

## 0. Đính chính một khuyến nghị tôi vừa đưa

Hôm qua tôi xếp **"bật lại người chấm để xếp hạng bản"** là đề xuất mạnh nhất, với lý do
*"lý do từng bác bỏ nó đã bị bác bỏ — người chấm nay chạy 240/240 không hỏng"*.

Đọc lại hồ sơ trong `sinh.py` thì **chỉ đúng một nửa**. Việc này đã được thử **ba lần**,
trong đó có một lần **đúng bằng người chấm `gpt-5-mini`** — tức đúng người chấm mà tôi
vừa nói là "nay đã dùng được":

```
                             ngôn ngữ  sáng tạo  vần    TỔNG    p50
không chọn (SO_BAN=8)          3,7      1,2     17,1   68,9    1.750 ms
chấm gpt-4o-mini "nghiêm"      4,0      1,7     14,8   69,4    3.156 ms
chấm gpt-5-mini                4,8      1,5     11,0   67,2   24.609 ms
```

Và kết luận đã ghi lại, quan trọng hơn mọi con số trên:

> **Chọn không tạo ra được chất lượng KHÔNG CÓ SẴN trong các bản.** Phương sai của `vần`
> lớn (sd 4,6/20) nên chọn ăn mạnh ở đó; phương sai của `ngôn ngữ` thì không — mọi bản
> đều tầm thường như nhau, và chọn bản "ít tệ nhất" trong bốn bản tầm thường vẫn ra một
> bài tầm thường.

Cái tôi nói đúng: **người chấm hôm nay nhanh hơn hẳn** — 240+ lượt trong A/B ở khoảng
~2 giây/lượt, không phải 24,6 giây. Con số 24,6 giây kia cần được giải thích trước khi
dùng làm căn cứ cho bất cứ điều gì (xem §3.2).

Cái tôi nói sai: coi "người chấm dùng được" là đủ để lật lại kết luận. **Không đủ** —
vì lập luận bác bỏ không nằm ở người chấm, mà ở **phân bố của các bản**.

---

## 1. Số đo hiện tại, và trần thực tế của thang đo

Hiệu chuẩn 14/09: cho chính người chấm chấm **thơ kinh điển**. Cùng nguyên tắc với
`ops/hieu_chuan_tho.py` — không biết trần thì không biết 1,15/5 là "rất tệ" hay "gần
mức tối đa thực tế".

| | BOT | ca dao (bài hoàn chỉnh) | khoảng cách |
|---|---|---|---|
| **ngôn ngữ** /10 | 5,47 | 9,00 | **35 pp** |
| **sáng tạo** /5 | 1,15 | 2,75 | **32 pp** |
| hình ảnh /10 | 5,67 | 7,25 | 16 pp |
| **ý nghĩa** /10 | **7,22** | 8,75 | **15 pp** |
| cảm xúc /5 | 2,80 | 3,50 | 14 pp |

Ba điều rút ra, và cả ba đều đổi hướng công việc:

**1. `ý nghĩa` không phải chỗ yếu.** Nó là mục thứ ba từ dưới lên về khoảng cách. Bot
hiểu đúng đề; chỗ hỏng là **viết ra bằng chữ gì**. Đổ công vào `ý nghĩa` là đổ vào chỗ
gần như đã kín.

**2. Thang này chấm rất nghiêm, kể cả với Nguyễn Du.** Kiều câu 3000 được `ngôn ngữ
2,0/10`, `sáng tạo 1,0/5`. Thơ kinh điển trung bình `sáng tạo 2,56/5`. Nên **mục tiêu
là ~2,75 chứ không phải 5,0** — bot còn thiếu ~1,6 điểm, không phải 3,85.

**3. `sáng tạo` trong thang này thực chất là bộ dò CÂU ĐẮT.** Tiêu chí viết thẳng:
*"CHO ĐIỂM TỐI ĐA khi bài có một CÂU ĐẮT"*. Bài ca dao duy nhất được 5/5 là bài có
`Gần bùn mà chẳng hôi tanh mùi bùn`. Vậy "nâng sáng tạo" = **làm ra được một câu đắt**,
không phải "viết sáng tạo hơn" nói chung.

> Cảnh báo về chính phép đo này: **n=9 bài kinh điển là ít**, và người chấm cho Kiều câu
> 3000 chỉ 2,0/10 ngôn ngữ — tức nó cũng sai. Dùng "2,75" làm **mốc định hướng**, đừng
> dùng làm ngưỡng nghiệm thu.

---

## 2. Những gì đã thử cho đúng hai mục này, và đã trượt

| cách | kết quả | nguồn |
|---|---|---|
| Chọn bằng người chấm (3 lần, có cả gpt-5-mini) | `ngôn ngữ` 3,7 → 4,8, đổi 6,1 điểm vần + 23 s | `CHON_BANG_NGUOI_CHAM` |
| `SO_BAN` 4 → 8 | `vần` +0,14 ± 2,16, độ trễ tệ hơn | `SO_BAN` |
| Chọn chữ vần trước | 69,7 → 57,1 | `CHON_VAN_TRUOC` |
| Lập ý thành lượt riêng | hai lượt đảo dấu, +1 000 ms | `LAP_Y` |
| "Sổ tay" ghi ý cùng lượt | 4,75 → 4,78 | đã gỡ |
| Prompt v3 — few-shot bốn bài ca dao | **+1,60 là do CHÉP**; bật chốt chặn chép thì −1,45 | đã lùi |
| Mục CÂU ĐẮT trong prompt (đang bật) | `sáng tạo` vẫn 1,15 | `prompt.py` |

**Cách duy nhất đã ăn và lặp lại được:** phiếu 10 bước (14/09) — `tất định +3,20 ± 1,85`,
`hình ảnh +0,38 ± 0,31`, cả hai lượt cùng dấu. Nó **không** thêm lời dặn; nó **đổi hình
dạng đầu ra**.

Đó là giả thuyết trung tâm của plan này:

> Thêm lời dặn thì trượt (7/8 lần). **Đổi hình dạng đầu ra thì ăn.** Và chọn lọc chỉ thu
> hoạch được cái đã có sẵn trong phân bố.

---

## 3. Bước 0 — phép đo quyết định, làm TRƯỚC khi xây gì

Cả plan rẽ đôi tuỳ một con số chưa ai đo: **phương sai của `sáng tạo` GIỮA CÁC BẢN trong
cùng một yêu cầu.**

### 3.1 Đo phương sai giữa các bản

Sinh 4 bản cho mỗi chủ đề (đúng như `SO_BAN=4` đang chạy), chấm **cả 4 bản** bằng người
chấm, trên 20 chủ đề = 80 bản.

| kết quả | nghĩa là | đi nhánh |
|---|---|---|
| `sd(sáng tạo)` trong một chủ đề **≥ 0,8** và max−min ≥ 2 | có bản hay lẫn trong đám, chỉ là không ai nhặt ra | **A** (§4) |
| `sd` **< 0,5**, cả 4 bản đều 1–1,5 | không có gì để nhặt | **B** (§5) |

Đây chính là con số mà kết luận *"chọn không tạo ra được cái không có sẵn"* dựa vào —
nhưng nó **suy ra từ `ngôn ngữ`**, chưa từng đo trực tiếp cho `sáng tạo`. Hai mục này
khác nhau: `ngôn ngữ` là thuộc tính đều khắp cả bài, còn `sáng tạo` phụ thuộc vào việc
**có hay không một câu đắt** — một sự kiện rời rạc, hiếm, nên phương sai của nó có thể
lớn hơn hẳn. Đó là lý do đáng đo lại chứ không suy ra.

*Chi phí:* 80 lượt chấm ≈ 3 phút. Không sửa một dòng code sản phẩm nào.

### 3.2 Làm rõ con số 24,6 giây

Hồ sơ ghi người chấm `gpt-5-mini` tốn **24,6 giây**; hôm nay 240+ lượt chấm chạy ở
~2 giây. Chênh **hơn 10 lần**, và một trong hai con số đang sai.

Giả thuyết: `huong_dan_chon()` đưa **cả 4 bài cùng lúc** và đòi model xuất một bảng
điểm, còn `cham_tho_hay()` chấm **một bài**. Đầu ra dài hơn nhiều, và `gpt-5-mini` tính
token suy luận vào đầu ra.

Phải biết cái nào đúng trước khi dùng độ trễ làm căn cứ loại bỏ nhánh A. *Chi phí:* 10
lượt gọi, ~2 phút.

---

## 4. Nhánh A — nếu phương sai lớn: chọn bản bằng người chấm

Chỉ thi công khi §3.1 cho `sd ≥ 0,8`.

Khác ba lần trước ở ba chỗ, và cả ba đều là điều kiện, không phải hy vọng:

1. **Chấm từng bài một** (`cham_tho_hay`) thay vì một bảng cho cả 4 bản — đây là dạng
   đã chạy 240/240 không hỏng và phân biệt được 1,0→5,0 trên thơ kinh điển.
2. **Chỉ xếp hạng theo `sáng tạo` + `ngôn ngữ`**, không theo tổng. Ba lần trước chấm
   theo tổng 40 điểm, và tổng bị `ý nghĩa` (7,2–7,9, gần như không đổi giữa các bản)
   làm loãng đúng cái tín hiệu cần.
3. **Giữ nguyên bộ lọc cứng hiện có trước đó** — khung, chép, cụm bị bẻ vẫn chặn trước;
   người chấm chỉ xếp hạng trong số bản đã sạch.

*Rủi ro đã biết:* lần trước nhánh này làm `vần` tụt 17,1 → 11,0. Nghiệm thu phải ràng
buộc `vần` không tụt quá 1,5 điểm.

---

## 5. Nhánh B — nếu phương sai nhỏ: nâng chính phân bố

Đây là nhánh tôi cho là **nhiều khả năng xảy ra hơn**, vì hồ sơ đã kết luận đúng điều đó
cho `ngôn ngữ`.

### B1. CÂU ĐẮT thành một bước trong phiếu 10 bước — *ưu tiên cao nhất*

Phiếu 10 bước vừa chứng minh đổi hình dạng đầu ra thì ăn. Thêm một bước:

```
BƯỚC 6b — CÂU ĐẮT. Trước khi viết cả bài, viết ra MỘT câu bát nói trúng
một điều ai cũng từng thấy mà chưa nói thành lời. Rồi xây bài quanh nó.
    CÂU ĐẮT: <một câu 8 tiếng>
    Nó đắt ở chỗ nào: <một dòng>
```

Vì sao có lý: hiện câu đắt (nếu có) chỉ **tình cờ** xuất hiện ở cuối bài. Bắt viết nó
**trước** biến nó từ sản phẩm phụ thành ràng buộc thiết kế. Và bắt giải thích *"đắt ở
chỗ nào"* là đúng cơ chế đã làm việc ở khai nghĩa chữ vần — bịa một lời giải thích khó
hơn là lặng lẽ viết một câu nhạt.

*Rủi ro thật:* phiếu dài thêm → `ý nghĩa` có thể tụt tiếp (đã tụt −0,29 khi thêm phiếu).
Nghiệm thu phải ràng buộc `ý nghĩa` không tụt thêm quá 0,3.

### B2. Few-shot bằng câu đắt RỜI, không bằng bài nguyên

Prompt v3 nhét bốn bài ca dao nguyên vẹn và model **chép** chúng — mức tăng +1,60 hoá ra
là điểm của ca dao, và khi bật chốt chặn chép thì thành −1,45.

Cách tránh đúng cơ chế đó: đưa **5–6 câu đắt rời** từ các bài **khác nhau**, kèm một
dòng nói *vì sao* nó đắt. Không bài nào nguyên vẹn để chép, và `so_cau_chep` vẫn chặn.

*Bắt buộc:* mọi câu đưa vào phải được thêm vào `_CAU_MAU` — nếu không, chốt chặn chép
không nhìn thấy chúng, và ta lặp lại đúng lỗi của v3.

### B3. Cụ thể hoá CHỖ ĐỨNG của đề bài

Đề bài hiện là `"Làm một bài về: lòng yêu nước"` — trừu tượng. Bài ca dao điểm cao đều
có **một người cụ thể trong một tình huống cụ thể** (`Anh đi anh nhớ quê nhà`). Thêm một
dòng vào đề bài: *"Viết từ chỗ đứng của một người cụ thể trong một lúc cụ thể."*

Đây là **thêm lời dặn**, tức là lớp đã trượt 7/8 lần. Xếp cuối, và chỉ làm nếu B1 và B2
đều không đủ.

---

## 6. Việc KHÔNG làm

- **Không** đổ công vào `ý nghĩa`. Khoảng cách 15 pp, thứ ba từ dưới, và phiếu 10 bước
  vừa cho thấy mỗi lần thêm việc vào phiếu thì nó lại tụt. Cách tốt nhất cho `ý nghĩa`
  lúc này là **đừng làm nó tệ thêm** — nên nó vào ngưỡng nghiệm thu chứ không vào mục tiêu.
- **Không** nâng `SO_BAN` khi chưa biết phương sai (§3.1). Sinh thêm bản mà người chọn
  không nhìn thấy cái hay thì vô ích — đã đo: +0,14 ± 2,16.
- **Không** thêm lời dặn "hãy sáng tạo hơn" vào prompt. Mục CÂU ĐẮT đã có sẵn cả một
  đoạn kèm ví dụ, và `sáng tạo` vẫn 1,15.
- **Không** dùng con số "2,75" làm ngưỡng đạt/trượt — nó đo trên n=9.

---

## 7. Thứ tự thi công và ngưỡng nghiệm thu

| # | việc | chi phí | cổng |
|---|---|---|---|
| 1 | §3.1 đo phương sai `sáng tạo` giữa các bản | ~3 phút | quyết định nhánh |
| 2 | §3.2 làm rõ 24,6 s vs 2 s | ~2 phút | — |
| 3 | nhánh A **hoặc** B1 | nửa ngày | A/B bên dưới |
| 4 | B2 nếu B1 chưa đủ | nửa ngày | A/B |
| 5 | B3 nếu vẫn chưa đủ | ngắn | A/B |

**Ngưỡng nghiệm thu cho mỗi bước** — n≥40 cặp ghép theo chủ đề, **hai lượt độc lập**,
gộp hai lượt mới kết luận:

```
ĐẠT khi:   sáng tạo   +0,4 trở lên, CÙNG DẤU ở cả hai lượt
GIỮ khi:   ý nghĩa    không tụt quá 0,3
           vần        không tụt quá 1,5
           p50        không quá 3.000 ms
```

Một lượt đo duy nhất **không** được dùng để kết luận. Đây không phải hình thức: `LAP_Y`
cho `+1,38 TỔNG` và `ý nghĩa +0,35 ± 0,35` ở lượt 1 — vừa đủ "có ý nghĩa thống kê" — rồi
lượt 2 lật ngược hẳn. Chạy một lượt thì đã ship một cái tốt không có thật.

Và như bốn lần trước: **kết luận "không dùng" cũng là kết quả hợp lệ**, sẽ được ghi lại
ngay cạnh cờ trong code kèm con số.

---

## 8. Kết quả thi công (14/09/2026)

### 8.1 Bước 0 — phép đo quyết định: **đi nhánh B**

Phương sai `sáng tạo` giữa 4 bản trong cùng một chủ đề, n=20 chủ đề × 4 bản:

```
sd trung bình 0,50 · biên độ (max−min) trung bình 1,00
17/20 chủ đề: cả 4 bản đều 1–2 điểm
```

Cận trên của chọn lọc, giả sử người chọn **không bao giờ sai**:

| | |
|---|---|
| lấy ngẫu nhiên một bản | 1,425/5 |
| lấy bản tốt nhất | 2,000/5 |
| **cận trên** | **+0,575** |
| ca dao (mốc) | 2,750/5 |

Chọn lọc **hoàn hảo vẫn thiếu 0,75 điểm** so với ca dao, mà giá phải trả là ≥4 844 ms
(chấm 4 bản song song) hoặc 10 287 ms (một bảng) — trong khi p50 hiện tại ~2 050 ms và
ngưỡng là 3 000 ms.

**→ Nhánh A bị loại bằng số đo.** Kết luận cũ *"chọn không tạo ra được cái không có
sẵn"* — vốn chỉ suy từ `ngôn ngữ` — nay đã được xác nhận trực tiếp cho `sáng tạo`.

### 8.2 §3.2 — giải được mâu thuẫn 24,6 s

| | |
|---|---|
| `cham_tho_hay` (1 bài) | **4 844 ms** |
| `huong_dan_chon` (bảng 4 bản) | **10 287 ms** |

Không cái nào là 24,6 s — con số trong hồ sơ đã lỗi thời. Và bảng-4-bản **nay phân biệt
được** (`[22, 30, 14, 22]`, ổn định qua 3 lần), khác hẳn ghi chép cũ *"cho điểm giống
hệt nhau"*. Hai ghi chép cũ đều nên coi là hết hạn.

### 8.3 B1 — CÂU ĐẮT thành bước 6b: **ĐÃ ĐO, TRƯỢT, ĐÃ TẮT**

A/B n=40 cặp ghép theo chủ đề, hai lượt độc lập:

| | lượt 1 | lượt 2 | gộp | |
|---|---|---|---|---|
| **sáng tạo** /5 | −0,20 | −0,05 | **−0,12 ± 0,18** | ❌ mục nhắm vào, **đi xuống** |
| **tất định** /45 | +0,10 | −4,81 | **−2,35 ± 2,18** | ❌ **hỏng thật** |
| ngôn ngữ /10 | −0,05 | +0,68 | +0,32 ± 0,66 | đảo dấu |
| ý nghĩa /10 | +0,20 | +0,15 | +0,17 ± 0,35 | không đủ |
| đúng khung | 39/40 | 39/40 | → 39/40, **34/40** | |
| độ trễ | +464 ms | +600 ms | | |

**Trượt cả hai cổng ở §7.** Cổng ĐẠT đòi `sáng tạo ≥ +0,4` cùng dấu — thực tế **âm ở cả
hai lượt**. Cổng GIỮ đòi hình thức không tụt — thực tế tụt −2,35 ± 2,18.

**Vì sao hỏng, giả thuyết có lý nhất:** phiếu đã dài sẵn (khai nghĩa từng chữ vần), thêm
một bước nữa thì model tiêu hết ngân sách vào phần **nháp** và bài thơ lãnh phần còn
lại. Cùng cơ chế đã làm `ý nghĩa` tụt −0,29 khi thêm chính cái phiếu đó. Tức **phiếu có
một trần sức chứa, và bước 6b vượt qua nó**.

**Điều đáng ghi nhất:** bắt model *viết ra* một câu đắt không làm nó *viết được* một câu
đắt. Nó viết ra một câu, khai là đắt, rồi bài thơ vẫn như cũ — còn điểm `sáng tạo` thì
xuống. Đây là lần thứ 9 can thiệp vào prompt, và là lần thất bại thứ 8.

### 8.4 Điều rút ra cho B2 và B3

Giả thuyết "trần sức chứa của phiếu" ở §8.3 **đổi điều kiện cho hai bước còn lại**:

- **B2** (few-shot câu đắt rời) và **B3** (cụ thể hoá chỗ đứng) đều là **thêm chữ vào
  prompt**. Nếu chẩn đoán trên đúng, cả hai sẽ vấp đúng bức tường đó.
- Nên trước khi làm B2, phải kiểm chẩn đoán: **bỏ bớt một bước khỏi phiếu** (ví dụ bước
  3 HÌNH ẢNH) rồi thêm B2 vào, giữ tổng độ dài phiếu không đổi. Nếu trần sức chứa là
  thật thì đây là cách duy nhất còn chỗ để thêm.

Chưa thi công. Đây là việc tiếp theo.

### 8.5 Phát hiện phụ: `max_retries=0` không có chú thích

Client thật đặt `max_retries=0` mà không ghi vì sao (so với `embedder.py` đặt số lần thử
lại **kèm hai đoạn giải thích**). API trả `429` kèm *"try again in 10-600 ms"* — một lần
chờ ngắn là đủ.

Chưa gây hại cho người dùng vì `sinh_tho` sinh 4 bản song song với `return_exceptions=
True`: một bản dính 429 chỉ mất một bản. Chỉ khi **cả bốn** cùng đụng trần mới ném ra.
Nhưng dưới tải cao thì điều đó xảy ra được, và hiện không có gì ghi lại lựa chọn này.

**Không tự sửa** — thêm retry vào đường sinh sẽ cộng vào đuôi trễ, đúng chỉ số đang theo
dõi. Đây là đánh đổi người dùng nên quyết.
