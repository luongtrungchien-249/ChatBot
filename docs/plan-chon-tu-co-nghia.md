# Buộc model chọn từ CÓ NGHĨA, không bẻ chữ — plan

> Ngày lập: 12/09/2026. Trạng thái: **đã thi công**, kết quả ở §8.
>
> Yêu cầu: *"chỉ được chọn lựa các từ có ý nghĩa … không được bẻ cong ép các từ làm
> hỏng chữ, suy nghĩ chi tiết trước khi chọn lọc"*.

---

## 1. Đang bảo đảm được gì, và chưa bảo đảm được gì

Đã thi công hôm nay (`tho/tu_vung.py` + ba tầng trong `tho/sinh.py`):

| | |
|---|---|
| **giữ được** | không còn chữ bị **bẻ dấu thanh** trong 406 từ đã biết — `ngọt ngào → ngọt ngao` bị loại, và nếu mọi bản đều bẻ thì có một vòng sửa gọi đích danh |
| **chưa giữ được** | mọi chữ trong bài đều có nghĩa |

Hai ca vẫn lọt, và cả hai đều từ lượt đo thật:

```
"rực rao"    từ thật "rực rỡ"    — đổi CẢ vần lẫn dấu
"trong cao"  từ thật "trong veo" — đổi hẳn tiếng thứ hai
```

Bộ dò suy từ **chính tả** nên chỉ bắt được sai lệch chính tả. Hai ca trên phải suy từ
**nghĩa**.

---

## 2. Vì sao model bẻ chữ — nguyên nhân gốc

Không phải nó không biết `ngọt ngào` viết thế nào. Nó viết đến tiếng thứ 6 của câu bát,
cần một chữ vần với `cao`, và trong lúc đó nó **không có sẵn một chữ thật nào** vừa hợp
vần vừa hợp nghĩa. Thế là nó bẻ chữ gần nhất.

Đây là **bí từ vần**, không phải lỗi chính tả.

> Mọi thứ đã làm cho tới giờ đều là **phát hiện sau khi đã bẻ**. Plan này nhắm vào chỗ
> khác: **đừng để nó rơi vào thế bí**.

---

## 3. Ba cơ chế đã CHỨNG MINH — thu hẹp không gian thiết kế

Đây là phần quan trọng nhất, vì nó loại bỏ phần lớn ý tưởng nghe hợp lý.

| cơ chế | kết quả đo được | |
|---|---|---|
| **CHỌN** giữa nhiều bản | vần 7,9 → 12,5/20 | **ăn** |
| **CHỈ ĐÍCH DANH** (vẽ ra thay vì mô tả) | khung 6-8 → 100%; mô tả công cụ 1/4 → 4/4 | **ăn** |
| **CHẶN tất định** | chép 0/80; chữ bị bẻ 2 → 0 | **ăn** |
| **SỬA** một bản đã sinh | 1 tốt / 3 hoà / **6 tệ hơn** | **phản tác dụng** |
| **RÀNG BUỘC CỨNG** trong prompt | 5 lần liên tiếp không cải thiện; 2 lần làm sập điểm | **phản tác dụng** |

**Đặc biệt phải nhớ:** *"chọn vần trước"* — bắt model chọn chữ vần rồi mới viết câu — đã
làm **69,7 → 57,1/100**. Nó đúng là "suy nghĩ trước khi chọn", và nó thất bại nặng.

Plan này phải giải thích được vì sao hướng 4.1 **khác** nó. Xem §4.1.

---

## 4. Ba hướng, xếp theo cơ chế

### 4.1 ⭐ BẢNG VẦN gồm chữ CÓ THẬT — chữa đúng nguyên nhân gốc

Thay vì để model tự nghĩ ra chữ vần (rồi bí và bẻ), **đưa cho nó một bảng chữ thật**
cùng vần để chọn.

Đã kiểm khả thi, và con số rất tốt. Rút từ **vị trí vần** của 3.254 câu Truyện Kiều —
tức những chữ thật sự được dùng để gieo vần trong thơ:

```
82 nhóm vần (thanh bằng) · 838 chữ khác nhau
trung vị 7 chữ/nhóm · 53/82 nhóm có ≥5 chữ · 32/82 nhóm có ≥10 chữ
```

Đúng những vần đã bị bẻ trong lượt đo đều có sẵn chữ thật:

```
vần "ao"   30 chữ:  vào sao nào cao đào bao xao dào nao bào đao
vần "ơi"   19 chữ:  lời trời nơi đời chơi rời bời khơi dời vời
vần "ang"  34 chữ:  vàng nàng chàng sang ràng hàng trang càng ngang màng
```

Cộng thêm **từ ghép hai tiếng** tra theo vần của tiếng cuối, từ `tho/tu_vung.py` — 61
nhóm:

```
vần "ao"   dạt dào · ngọt ngào · nghẹn ngào · lao xao · lao đao · nôn nao · bờ ao
vần "ang"  dịu dàng · nhẹ nhàng · mơ màng · mịn màng · ngỡ ngàng · chói chang
```

Nghĩa là ở đúng chỗ model từng bẻ ra `ngọt ngao`, nó sẽ có sẵn `ngọt ngào`, `nghẹn
ngào`, `dạt dào` để chọn.

#### Vì sao hướng này KHÁC "chọn vần trước" đã thất bại

Khác biệt nằm ở **ràng buộc**, không ở thông tin:

| | chọn vần trước (thất bại) | bảng vần (đề xuất) |
|---|---|---|
| model phải dùng | **ĐÚNG** những chữ đã chọn | chữ nào cũng được |
| ở vị trí | **ĐÚNG** vị trí đã định | tự do |
| số lượt gọi | **2** (thêm độ trễ) | **1** |
| bản chất | ràng buộc cứng | tài liệu tham khảo |

Cái làm sập điểm lần trước là ép **đúng chữ ở đúng chỗ** — thêm một ràng buộc cứng vào
một việc model vốn đã làm không xong, nên nó buông cả hai. Bảng vần thì chỉ **mở rộng
lựa chọn**, không thu hẹp.

#### Chi phí

Tất định, **$0 lúc chạy**, dựng một lần lúc import. Chỉ tốn **token đầu vào**: chọn
~6 nhóm vần thông dụng × ~12 chữ ≈ 400 ký tự.

> **Cần bạn duyệt:** nguồn từ vựng là Truyện Kiều (đã có trong repo, hết hạn bảo hộ).
> Bạn từng nói *"không phải làm Truyện Kiều"* — ý đó là không làm **dự án corpus Kiều**.
> Ở đây nó chỉ là **nguồn từ vựng**, không phải mục tiêu. Nếu bạn vẫn không muốn, tôi
> dựng bảng từ riêng `tu_vung.py` (nhỏ hơn nhiều: 61 nhóm thay vì 82).

---

### 4.2 SỔ TAY trước khi viết — "suy nghĩ chi tiết" trong MỘT lượt gọi

Bắt model viết ra phần chuẩn bị trước, rồi mới viết bài:

```
HÌNH ẢNH: 5 hình ảnh cụ thể, nhìn thấy được, về chủ đề
CHỮ VẦN : với mỗi vần định dùng, 3 chữ CÓ THẬT
THƠ     : bài thơ
```

Phần trên `THƠ:` bị **cắt bỏ** trước khi gửi người dùng.

Vì sao đây không phải "chọn vần trước": **cùng một lượt gọi**, và sổ tay là ghi chú của
chính nó chứ không phải một hợp đồng nó phải tuân thủ. Không có lượt thứ hai, không có
vị trí bị ép.

**Rủi ro phải canh:** thêm token đầu ra ⇒ tăng độ trễ. Hiện p50 ≈ 1.600 ms; sổ tay có
thể đẩy lên 2.500–3.000 ms. Mục tiêu gốc của cả tính năng là **giảm** độ trễ, nên bước
này phải có ngưỡng độ trễ rõ ràng, không chỉ ngưỡng chất lượng.

---

### 4.3 Mở rộng bộ dò để bắt được hai ca còn lọt

`rực rao` và `trong cao` cần biết **tiếng thứ hai có phải chữ thật không**, không chỉ
so chính tả.

Với 838 chữ ở vị trí vần từ Kiều cộng vốn từ có sẵn, dựng được một **danh sách tiếng
có thật**. Quy tắc mới: cụm có tiếng đầu đã biết **và** tiếng sau **không** nằm trong
danh sách tiếng thật ⇒ nghi bẻ.

**Phải hiệu chuẩn hai chiều như lần trước.** Chế độ `chat=False` đã báo nhầm 54,8% trên
Kiều — con số đó là lời nhắc rằng một quy tắc nghe hợp lý có thể loại luôn Nguyễn Du.

---

## 5. Thứ tự thi công, và tiêu chí dừng

| # | việc | chi phí | tiêu chí dừng |
|---|---|---|---|
| 1 | Dựng `bang_van.py` từ Kiều + `tu_vung.py` | $0 | ≥30 nhóm có ≥8 chữ; 0 chữ rác |
| 2 | Nhúng bảng vần vào prompt (4.1) | ~$0,08 đo | `vần` **không giảm**; cụm bị bẻ ≤ mốc; p50 **không tăng** |
| 3 | Mở rộng bộ dò (4.3) | $0 | bắt được `rực rao`+`trong cao`; báo nhầm trên Kiều **< 1%** |
| 4 | Sổ tay trước khi viết (4.2) | ~$0,08 đo | `ngôn ngữ` ≥ 7,0/10 **và** p50 ≤ 2.500 ms |

**Bước 3 làm trước bước 4** dù nó ít hấp dẫn hơn: nó là thứ duy nhất **đo được** mức độ
"bẻ chữ", và không có nó thì bước 4 không có thước để chấm.

### Quy tắc đo, rút từ những lần sai trong tuần này

- **n ≥ 40 mỗi bên, và CHẠY HAI LƯỢT ĐỘC LẬP.** Ở n=6 hai lượt cùng cấu hình từng chênh
  7 điểm. Ở n=40 một lượt vẫn đảo chiều được: `bằng-trắc 0 lỗi` cho 4/40 → 2/40 ở lượt
  một rồi 2/40 → 10/40 ở lượt hai. **Một lượt không đủ để kết luận bất cứ điều gì.**
- **Phân vị, không chỉ trung bình.** Thứ người dùng thấy là *bài có sạch không*, và đó
  là một tỉ lệ.
- **Mỗi bước đo lại độ trễ.** Một cải thiện điểm mà đẩy p50 lên 4 giây là đánh đổi, và
  phải gọi đúng tên.

---

## 6. Rủi ro lớn nhất, và cách phát hiện sớm

**Bảng vần biến thành ràng buộc trá hình.** Nếu model coi bảng là danh sách bắt buộc, ta
quay lại đúng thất bại "chọn vần trước" — điểm sập 12,6.

Dấu hiệu sớm, kiểm được ngay ở bước 2: **tỉ lệ chữ vần nằm trong bảng**. Nếu nó vọt lên
gần 100% thì model đang coi bảng là bắt buộc — lúc đó phải đổi cách diễn đạt sang *"vài
chữ gợi ý, dùng chữ khác cũng được"*, hoặc bỏ hướng này.

Mốc lành mạnh: chữ vần trong bảng tăng **vừa phải** và `ngôn ngữ` tăng theo.

---

## 7. Những thứ plan này CỐ Ý không làm

- **Không thêm luật vào prompt.** Đã năm lần không cải thiện; hai lần làm sập điểm.
- **Không thêm vòng sửa nào ngoài vòng "bẻ chữ" đã có.** Sửa làm thơ tệ đi ở 6/10 ca.
- **Không dùng model suy luận.** `gpt-5-mini` đã đo: chậm hơn 20–40 lần, điểm luật thấp
  hơn, nghĩa tệ hơn.
- **Không tải từ điển GPL.** Vẫn chờ quyết định của bạn; cả plan này chạy được mà không
  cần nó.
- **Không hứa "mọi chữ đều có nghĩa".** Hứa được là: không còn chữ bị bẻ **thuộc các
  kiểu đã đo được và hiệu chuẩn được**. Khoảng cách giữa hai điều đó phải nói thẳng,
  không giấu sau một con số đẹp.


---

## 8. Kết quả thi công (12/09/2026)

### 8.1 Bước 1 — bảng vần: ĐẠT

`ops/dung_bang_van.py` sinh ra `src/tho/bang_van.py`.

```
3.254 câu · 838 tiếng ở vị trí vần
82 nhóm vần · giữ 53 nhóm có ≥5 chữ · 39/53 nhóm có ≥8 chữ
61 nhóm từ ghép hai tiếng
```

Tiêu chí là ≥30 nhóm có ≥8 chữ — đạt với 39.

Sinh ra **tệp hằng số** chứ không đọc corpus lúc chạy: `src/tho/` không được phụ thuộc
`evals/`, và `src/` phải chạy được khi không có corpus.

### 8.2 Bước 2 — nhúng bảng vần vào prompt: KHÔNG HẠI, CŨNG KHÔNG LỢI

A/B n=40 mỗi bên:

| | hiện tại | + bảng vần | chênh |
|---|---|---|---|
| vần /20 | 10,36 | 10,25 | −0,11 ± 2,04 nhiễu |
| bằng-trắc /15 | 12,88 | 12,68 | −0,20 ± 0,59 nhiễu |
| độ trễ | 2.193 ms | 2.014 ms | −180 ms nhiễu |
| cụm bị bẻ | **0** | **0** | |
| chữ vần TRONG BẢNG | 60% | 62% | ← cảnh báo sớm **không** kích hoạt |

Ba tiêu chí của §5 đều đạt (vần không giảm, cụm bị bẻ không tăng, p50 không tăng). Và
dấu hiệu cảnh báo sớm sạch: chữ vần trong bảng chỉ nhích 60% → 62%, không vọt lên gần
100% — model coi bảng là **gợi ý**, không phải danh sách bắt buộc. Nghĩa là hướng này
**không lặp lại** thất bại "chọn vần trước".

**Nhưng cũng không đo được lợi ích nào**, và lý do rất cụ thể: `cụm bị bẻ` đã là **0/0 ở
cả hai bên** — bộ lọc ba tầng làm hôm trước đã dọn sạch mọi ca *đo được*. Bảng vần chỉ
có thể giúp cho những ca **không đo được**, và không đo được thì không chứng minh được.

### 8.3 Bước 3 — mở rộng bộ dò: TIỀN ĐỀ SAI, KHÔNG THI CÔNG

§4.3 dựa trên giả định *"`rao`, `cao` không phải tiếng thật"*. Kiểm trên Kiều:

```
'cao'  xuất hiện  40 lần
'ngao' xuất hiện   2 lần
'rao'  xuất hiện   1 lần
'veo'  xuất hiện   1 lần
```

Chúng **là** tiếng thật. Vấn đề của `rực rao` và `trong cao` thuần tuý là **kết hợp
từ**, không phải âm tiết — nên quy tắc "âm tiết không có thật" không bắt được gì.

Thử một quy tắc hẹp hơn: *không phải bạn đã biết của tiếng đầu* **và** *điệp âm với
tiếng đầu* (nghi là từ láy bị bẻ).

```
bắt được  "rực rao"     ✓
bỏ sót    "trong cao"   ✗ (tr- và c- không điệp âm)
báo nhầm trên Kiều  153/3254 = 4,70%   ← tiêu chí là < 1%
```

Và các ca báo nhầm đều là **từ láy thật chưa được liệt kê**: *đầy đặn, dập dìu, hiu
hiu, mê mẩn, thanh thanh, đầm đầm*. Tức nguồn báo nhầm **cùng loại** với nguồn bắt
đúng — thêm từ vào danh sách sẽ đuổi hình bắt bóng, vì tiếng Việt có hàng nghìn từ láy.

> **Kết luận: bước 3 cần một từ điển thật.** Cùng chỗ tắc đã biết, và nó chặn luôn khả
> năng ĐO được hiệu quả của bước 2.

### 8.4 Bước 4 - sổ tay "suy nghĩ chi tiết": TRƯỢT XA

Bắt model ghi HÌNH ẢNH + CHỮ VẦN CÓ THẬT + KIỂM trước khi viết, trong cùng một lượt gọi,
phần nháp bị cắt trước khi gửi. A/B n=40 mỗi bên:

| | hiện tại | + sổ tay | chênh |
|---|---|---|---|
| **ngôn ngữ** | 4,75 | 4,78 | **+0,03 ± 0,81** nhiễu |
| hình ảnh | 6,65 | 6,67 | +0,02 nhiễu |
| sáng tạo | 1,75 | 1,90 | +0,15 nhiễu |
| vần /20 | 10,00 | 9,73 | −0,28 nhiễu |
| độ trễ | 1.896 ms | 2.103 ms | +207 ms |

Ngưỡng là `ngôn ngữ >= 7,0`. Đo được **4,78** - tức nó **không làm gì cả**, xê dịch 0,03
trên thang 10.

Đây là lần thứ **sáu** một can thiệp ở tầng prompt không cải thiện được chất lượng. Và
lần này đáng kể hơn các lần trước, vì nó là hình thức "suy nghĩ trước khi làm" - thứ
thường được coi là có tác dụng. Với `gpt-4o-mini` ở tác vụ này thì không.

Không đưa vào.

### 8.5 Quyết định cuối

| bước | kết quả | có vào sản phẩm |
|---|---|---|
| 1 bảng vần | ĐẠT (39/53 nhóm ≥8 chữ) | **có** |
| 2 nhúng vào prompt | đạt cả 3 tiêu chí, lợi ích không đo được | **có** |
| 3 mở rộng bộ dò | tiền đề sai, 4,70% báo nhầm | không |
| 4 sổ tay | ngôn ngữ 4,78 vs ngưỡng 7,0 | không |

Một điều đáng ghi cho người sau: **ba lần thêm chữ vào prompt gần đây đều làm `vần` lệch
âm** - v4 −1,25, bảng vần −0,11, sổ tay −0,28. Từng cái đều nằm trong nhiễu, nhưng cả ba
cùng dấu. Nghi vấn: prompt càng dài thì các ràng buộc càng loãng. Chưa đủ bằng chứng để
kết luận, nhưng đủ để **không thêm gì nữa mà không đo**.

### 8.6 "rực rao" vẫn lọt - chỉ dẫn trong prompt KHÔNG cứu được

Soạn một chỉ dẫn gọi đích danh THAO TÁC bẻ chữ, kèm ba ca thật (`rực rỡ -> rực rao`,
`ngọt ngào -> ngọt ngao`, `trong veo -> trong cao`) và nêu hành động thay thế ("đổi cả
câu, đừng đổi chữ").

Đo ở **mức bản nháp** - nơi prompt thật sự tác động, vì bộ lọc đã đưa kết quả cuối về
0/0. n=**160 bản mỗi bên**:

| | hiện tại | + cấm bẻ | chênh |
|---|---|---|---|
| cụm bị bẻ / bản | 0,675 | 0,781 | **+0,106 ± 0,184** nhiễu, hướng XẤU |
| bản CÓ chữ bị bẻ | 79/160 | 88/160 | p = 0,37 |
| vần /20 | 6,43 | 5,60 | −0,82 nhiễu |

Khoảng tin cậy ±0,184 đủ hẹp để nói: nếu có tác dụng thì tác dụng đó **nhỏ hơn 0,08
cụm/bản**. Đây là lần thứ **bảy** một can thiệp ở tầng prompt không cải thiện chất lượng,
và là lần được đo kỹ nhất. **Không đưa vào.**

Nhưng phép đo lộ ra con số quan trọng hơn:

```
bản nháp có cụm nghi bị bẻ:  79/160 = 49%
cùng bộ dò trên Truyện Kiều:          4,7%
```

Gấp mười lần. Vấn đề lớn hơn nhiều so với phần bộ dò chặt nhìn thấy.

### 8.7 Bộ dò RỘNG dùng để CHỌN - ĐẠT, và đây là thứ cứu được "rực rao"

Bộ dò rộng (chặt + điệp âm) báo nhầm 4,70% trên Kiều. Quá cao để **chặn**, vừa đủ để
**chọn** - và khác biệt đó là có thật:

```
CHẶN  báo nhầm một lần là loại hẳn một bài tốt, không lấy lại được
CHỌN  báo nhầm chỉ đổi thứ tự ưu tiên giữa 4 bản; xấu nhất là lấy một bản tương đương
```

So theo CẶP trên cùng bộ bản, **hai lượt độc lập**, n=40 mỗi lượt:

| | xếp hạng cũ | + bộ dò rộng | |
|---|---|---|---|
| cụm bị bẻ / bài | 0,713 | 0,375 | **−47%** |
| bài KHÔNG có cụm bẻ | 38/80 (48%) | 55/80 (69%) | **p = 0,0101 THẬT** |
| vần /20 | 9,94 | 9,04 | −0,89 (lệch âm cả hai lượt) |

Lượt 1 −0,275 [nhiễu], lượt 2 −0,400 [THẬT] - cùng dấu, lượt hai đạt ý nghĩa, gộp lại
p = 0,0101.

**Đánh đổi phải nói rõ: ít chữ bẻ hơn, đổi lấy điểm vần thấp hơn.** Đúng thứ tự ưu tiên
người dùng đặt ra - *"chỉ được chọn lựa các từ có ý nghĩa"*.

Ranh giới được ghim bằng test: bộ CHẶN dùng `cum_kha_nghi` (0,03%), khâu CHỌN dùng
`cum_nghi_be` (4,70%).

### 8.4 Ranh giới của lời hứa

| | |
|---|---|
| **giữ được** | không còn chữ bị **bẻ dấu thanh** thuộc 406 từ đã biết |
| **không giữ được** | mọi chữ đều có nghĩa (`rực rao`, `trong cao` vẫn lọt) |
| **không đo được** | bảng vần có giảm được loại lọt đó hay không |

Ba dòng này nên đọc cùng nhau. Vòng lặp *"sửa → đo → giữ"* mà cả dự án dựa vào **đứt ở
đây**, vì không còn thước nào cho phần còn lại.
