# Vần · Ngôn ngữ · Sáng tạo — plan

> Ngày lập: 11/09/2026. Trạng thái: **đã thi công, kết quả ở §8**.
>
> Tóm tắt: §6 giữ. Bước 1 và 2 **đều hoàn tác** sau khi đo. Bước 3–6 **bị chặn**.
> Phát hiện lớn nhất không nằm trong plan: **phép đo n=6 dùng cả ngày không đủ
> mạnh** để thấy những hiệu ứng đang tìm.
>
> Ba chỉ số còn lại sau khi khung 6-8 đã chốt 100% và bộ kiểm vần đã sửa xong:
>
> ```
> vần        12,4/20      đã nhích từ 7,0 nhờ sửa thước, nhưng phần lớn lỗi là THẬT
> ngôn ngữ    5,5/10      KHÔNG nhúc nhích qua mọi can thiệp hôm nay
> sáng tạo    1,5/5       KHÔNG nhúc nhích qua mọi can thiệp hôm nay
> ```

---

## 1. Vì sao hai chỉ số kia đứng yên

Mọi thứ sửa hôm nay đều ở tầng **LUẬT**: khung 6-8, bảng vần thông, bóc dấu câu, vòng
sửa. `ngôn ngữ` và `sáng tạo` đo **chất thơ**, và chúng không phản ứng với việc sửa luật.

Bài điểm cao nhất hôm nay (74,1/100, vần 20/20) vẫn chứa *"nhẹ diêu"* và *"lấp lơ"* —
chữ ghép cho đủ vần, không có nghĩa. Một bài **đúng luật tuyệt đối vẫn có thể là thơ
dở**, và đó chính là ranh giới mà `tho/cham_diem.py` đã tách ra từ đầu.

Nên plan này không thêm một phép kiểm luật nào nữa.

---

## 2. Ba cơ chế đã được CHỨNG MINH trong chính dự án này

Đây là phần quan trọng nhất của plan, vì nó loại bỏ phần lớn ý tưởng nghe hay.

| cơ chế | kết quả đo được | |
|---|---|---|
| **CHỌN** giữa nhiều bản | vần 7,9 → 12,5/20 (N=4) | **ăn** |
| **SỬA** một bản đã sinh | 1 tốt hơn / 3 không đổi / **6 tệ hơn** | **phản tác dụng** |
| **RÀNG BUỘC CỨNG** thêm vào prompt | 69,7 → 57,1 (chọn vần trước); 4/6 → 2/6 (giữ mức cụ thể) | **phản tác dụng** |

Quy tắc rút ra, và plan này bám chặt vào nó:

> **Đưa cho model NHIỀU ĐƯỜNG rồi chọn, đừng bắt nó đi đúng một đường.**

---

## 3. Năm phép đo đã làm, và bốn hướng chúng LOẠI BỎ

Làm trước khi lập plan, để plan không xếp thứ tự bằng cảm giác.

### 3.1 Vần phân tán mạnh, nhưng trần thấp

22 bản độc lập, đúng khung, `gpt-4o-mini`:

```
trung bình     7,9/20
độ lệch chuẩn  4,6
thấp / cao     0,0 / 17,1
đạt 20/20      0/22 = 0%
```

Bài 20/20 hôm trước là **may mắn của một mẫu khác**, không phải năng lực ổn định. Chọn
4 bản đã kéo 7,9 → 12,5 — tức khâu chọn đang gánh phần lớn điểm vần hiện có.

### 3.2 best-of-N có lợi suất giảm dần

```
  N    vần kỳ vọng   so với N=4
  4        12,5/20        +0,0
  8        14,2/20        +1,7
 12        15,0/20        +2,5
 16        15,5/20        +3,0
```

Gấp đôi số bản được **+1,7/20**. Thật, chắc chắn, **không tốn thêm độ trễ** (các bản
chạy song song) — nhưng có trần.

### 3.3 ✗ LOẠI — lỗi vần không dồn về mối nào

```
A  lục[6] ~ bát[6]      29%
B  bát[8] ~ lục[6] kế   39%
```

Không lệch hẳn về bên nào, nên **không có mối nào để prompt nhấn mạnh**.

### 3.4 ✗ LOẠI — rút ngắn bài không cứu được gì

```
cặp 1   25%        chỉ 4 câu   → vần ≈ 12,9/20
cặp 2   46%        chỉ 6 câu   → vần ≈ 13,6/20
cặp 3   25%        cả bài      → vần ≈ 13,3/20
cặp 4   42%
```

Lỗi **không dồn về cuối bài**. Bài ngắn không tốt hơn — nút vặn "cho làm 4 câu thôi"
trông rất hợp lý và hoàn toàn vô dụng.

### 3.5 ✗ LOẠI — model mạnh hơn (và một niềm tin sai đã mang cả phiên)

`gpt-5-mini` **gọi được**. Suốt phiên tôi tưởng nó chết, vì mọi lần thử đều lỗi ở
~15.600 ms. Nguyên nhân:

```python
REPLY_TIMEOUT_S = 15.0      # route `poem` dùng chung — llm.reply
CHEAP_TIMEOUT_S = 45.0      # người chấm dùng — llm.cheap, CŨNG là gpt-5-mini, chạy tốt
```

`gpt-5-mini` là model **reasoning**: nó sinh token suy luận trước khi trả lời, nên một
việc sinh dài như làm thơ vượt 15s trong khi một việc chấm ngắn thì không.

Nâng timeout lên 120s thì chạy, và kết quả trả lời luôn câu hỏi về trần model:

| | thời gian | tất định |
|---|---|---|
| gpt-4o-mini | ~1.800 ms | 35,7/45 |
| gpt-5-mini «hoa sen» | **60.829 ms** | 34,6/45 |
| gpt-5-mini «mùa thu» | **36.718 ms** | 32,6/45 |

**Chậm hơn 20–40 lần và không tốt hơn.** Thơ nó ra còn tệ hơn về nghĩa — *"Gửi hương
mây rơi lên sen trời quê"*, và vần "quê" lặp ba lần.

> **Một cái bẫy phải ghi lại:** đặt `POEM_MODEL_ID` thành một model reasoning sẽ làm
> route thơ hỏng **im lặng** ở 15s, và log chỉ hiện `APITimeoutError` — không có gì
> chỉ ra rằng nguyên nhân là timeout của route chứ không phải API chết. Xem §6.

---

## 4. Bốn hướng còn lại, xếp theo CƠ CHẾ

### 4.1 ⭐ Chọn bản bằng chính thang 100, thay vì chỉ đếm lỗi luật

**Đây là hướng duy nhất chạm được cả ba chỉ số cùng lúc.**

Hiện `sinh_tho` chọn bản theo `_xep_hang = (lỗi khung, lỗi còn lại)` — tức **hoàn toàn
mù** với `ngôn ngữ` và `sáng tạo`. Một bản đầy *"nhẹ diêu"*, *"lấp lơ"* mà đúng vần hơn
sẽ thắng một bản hay hơn hẳn.

Mà ta **đã có** người chấm hai mục đó: `evals/metrics/tho_hay.py`.

Cách làm: giữ khung làm bộ lọc cứng, rồi xếp hạng các bản còn lại bằng **một lần gọi
người chấm duy nhất** xếp hạng cả N bản cùng lúc.

Vì sao hướng này khớp với §2: nó là **CHỌN**, không phải **SỬA**, và không thêm ràng
buộc nào vào prompt.

**Cái giá phải nói thẳng:** +1 lượt gọi tuần tự, ~2 giây — đúng bằng vòng sửa vừa gỡ.
Khác biệt là vòng sửa làm thơ **tệ đi** ở 6/10 ca, còn chọn thì trường hợp xấu nhất
bằng hiện tại. Nhưng nó tiêu mất phần lớn mức giảm độ trễ 44% vừa đạt được, nên §5 đặt
điều kiện nghiệm thu rõ ràng cho nó.

### 4.2 ⭐ Từ điển tiếng Việt — một hiện vật mở khoá BA chỗ đang tắc

Ba việc khác nhau đang cùng chờ đúng một thứ:

| đang tắc ở | cần gì | mở ra được gì |
|---|---|---|
| `kiem_nhip` chỉ kiểm được dấu phẩy | ranh giới **từ ghép** | nhịp 2/2/2, 3/3 thật sự |
| `ngôn ngữ` 5,5/10 | danh sách **từ có thật** | bắt được *"nhẹ diêu"*, *"lấp lơ"* |
| gợi ý chữ vần | tra **theo vần** | đưa model chữ CÓ NGHĨA cùng vần |

Tất định, $0 lúc chạy, không thêm độ trễ. Đây là hiện vật có đòn bẩy cao nhất trong cả
bộ tính năng.

**Lưu ý quan trọng về cách dùng:** gợi ý chữ vần phải là **GỢI Ý**, không phải ràng
buộc. Bản "chọn vần trước" đã ép model dùng ĐÚNG những chữ đó ở ĐÚNG vị trí và làm sập
điểm từ 69,7 → 57,1. Đưa thêm lựa chọn thì được; bắt đi một đường thì không.

### 4.3 Few-shot chọn theo chủ đề (nhắm `sáng tạo`)

`sáng tạo` 1,5/5 là chỗ thấp nhất so với thang. Tiêu chí của nó là **câu đắt** — một câu
làm người đọc dừng lại.

Hiện prompt chỉ **mô tả** điều đó. Dự án này đã hai lần đo được rằng chuyển từ *mô tả
trừu tượng* sang *chỉ đích danh bằng ví dụ* mới ăn (mô tả công cụ 1/4 → 4/4; chặn 7
3/6 → 6/6).

Dùng chính RAG đã có để lấy 2–3 cặp lục bát **cùng chủ đề** làm ví dụ trong prompt.
Đây là §13.2 của `plan-nang-chat-luong-tho.md`, chưa từng thi công.

**Rủi ro phải canh:** few-shot dễ làm model **chép giọng** thay vì sáng tạo — đúng cái
mà `sáng tạo` trừ điểm. Phải đo cả `sáng tạo` lẫn độ trùng lặp chữ với ví dụ.

### 4.4 Nâng `SO_BAN` 4 → 8

Đã đo: **+1,7/20 vần**, không tốn độ trễ, gấp đôi token (~+0,0024 USD/bài).

Nhỏ nhưng chắc chắn và gần như miễn phí về trải nghiệm. Đáng làm **cùng lúc** với 4.1,
vì chọn giữa 8 bản tốt hơn chọn giữa 4 — hai hướng cộng hưởng.

---

## 5. Thứ tự thi công, và tiêu chí dừng

| # | việc | chi phí | tiêu chí dừng |
|---|---|---|---|
| 1 | `SO_BAN` 4 → 8 | ~$0,02 đo | vần ≥ 13,5/20; độ trễ p50 **không tăng** |
| 2 | Chọn bản bằng thang 100 (4.1) | ~$0,05 đo | `ngôn ngữ` ≥ 6,5 **và** `sáng tạo` ≥ 2,5; p50 ≤ 3.500 ms |
| 3 | Từ điển: dựng + nối vào `ngôn ngữ` | $0 lúc chạy | bắt được ≥ 80% cụm vô nghĩa trong bộ mẫu tay |
| 4 | Từ điển: nối vào `kiem_nhip` | $0 | `hieu_chuan_tho` không hồi quy |
| 5 | Từ điển: gợi ý chữ vần (GỢI Ý) | ~$0,02 đo | vần tăng **và** `ngôn ngữ` không giảm |
| 6 | Few-shot theo chủ đề (4.3) | ~$0,05 đo | `sáng tạo` ≥ 2,5, trùng lặp chữ với ví dụ < 15% |

Bước 1 trước bước 2 có chủ đích: nâng N là thay đổi **một dòng**, và nó làm nền cho
bước 2 (chọn giữa 8 tốt hơn chọn giữa 4). Gộp hai bước thì không biết cái nào ăn.

Bước 3 → 4 → 5 tách ra vì chúng dùng **chung một từ điển** nhưng là **ba phép đo khác
nhau**; một bước hỏng không được kéo hai bước kia theo.

**Mỗi bước phải đo lại `độ trễ p50`,** không chỉ điểm. Mục tiêu gốc của cả tính năng là
giảm độ trễ, và hôm nay vừa đạt 1.813 ms từ 2.890 ms. Một cải thiện điểm mà đẩy độ trễ
về 4 giây là một sự đánh đổi, không phải một chiến thắng — và phải được gọi đúng tên.

---

## 6. Việc nhỏ nên làm ngay, độc lập với tất cả

`REPLY_TIMEOUT_S = 15.0` áp cho route `poem`. Ai đặt `POEM_MODEL_ID` thành một model
reasoning (`gpt-5-mini`, `gpt-5-nano` — **cả hai đều nằm trong `_GIA_OPENAI`**, tức
đang được mời dùng) sẽ thấy route thơ hỏng im lặng ở 15s.

Đề xuất: cho route `poem` một timeout riêng, và ghi ngay tại `_GIA_OPENAI` rằng model
reasoning cần timeout lớn hơn nhiều. Không có dòng đó thì người sau sẽ mất đúng một
ngày như tôi vừa mất.

---

## 7. Những thứ plan này CỐ Ý không làm

- **Không đổi sang model mạnh hơn.** Đã đo: `gpt-5-mini` chậm hơn 20–40 lần, điểm luật
  thấp hơn, nghĩa tệ hơn (§3.5).
- **Không rút ngắn bài thơ.** Đã đo: lỗi không dồn về cuối bài (§3.4).
- **Không thêm vòng sửa nào.** Đã đo hai lần: sửa làm thơ tệ đi (§2).
- **Không thêm ràng buộc cứng vào prompt.** Đã đo hai lần: phản tác dụng (§2).
- **Không fine-tune.** Nó có thể là câu trả lời đúng, nhưng cả sáu bước trên đều rẻ hơn
  và nhanh hơn, và chưa cái nào được thử. Fine-tune trước khi cạn các bước đó là trả
  tiền để khỏi phải suy nghĩ.


---

## 8. Kết quả thi công (11/09/2026)

### 8.1 Phát hiện quan trọng nhất, và nó không nằm trong plan

Chạy **hai lượt cùng một cấu hình** (SO_BAN=8, n=6 bài):

```
lượt A   vần 17,1/20   TỔNG 68,9/100
lượt B   vần 10,0/20   TỔNG 63,8/100
```

Chênh **7 điểm vần** giữa hai lượt **giống hệt nhau**. Nghĩa là bộ đo n=6 không đủ mạnh
để tách hiệu ứng khỏi nhiễu, và mọi kết luận rút ra từ nó hôm nay đều phải xem lại.

Số học: sd của vần mỗi bài ≈ 3,5/20, nên sai số chuẩn của trung bình n=6 là ≈ 1,4 —
tức hai lượt cách nhau 4 điểm là **chuyện bình thường**. Muốn phân biệt một khác biệt
2 điểm thì cần n ≈ 40.

**Kết luận nào của hôm nay còn đứng vững** — những cái dùng thiết kế mạnh hơn n=6:

| kết luận | thiết kế | còn vững? |
|---|---|---|
| khung 6-8 từ 0/6 → 12/12 | tỉ lệ, hiệu ứng rất lớn | **có** |
| thước vần cũ trừ oan 2,1/20 | **so theo cặp**, cùng 12 bài | **có** |
| vòng sửa làm thơ tệ đi | **so theo cặp**, 10 bài | **có** |
| bảng vần: 30,5% → 17,0% | 1.627 cặp Truyện Kiều | **có** |
| «tổng 61,0 → 69,1 trong ngày» | n=6 so n=6 | **KHÔNG** |

Con số tiến bộ trong ngày mà tôi đã báo là **không đáng tin**. Phần tiến bộ chắc chắn
là khung 6-8 và bộ kiểm vần, không phải điểm tổng.

### 8.2 §6 — timeout riêng cho route thơ: GIỮ

`POEM_TIMEOUT_S = 90.0`. Không cần đo: nó sửa một lỗi hỏng-im-lặng có thật.

### 8.3 Bước 1 — `SO_BAN` 4 → 8: HOÀN TÁC

Lần đo đầu (n=6) cho vần 12,4 → 17,1 và tôi đã tưởng đó là thắng lợi lớn. Đo lại ở
**n=20 kèm khoảng tin cậy**:

```
SO_BAN=4   vần 11,67 ± 1,57   tất định 34,86   p50 1.563 ms
SO_BAN=8   vần 11,81 ± 1,48   tất định 34,93   p50 2.375 ms
chênh vần  +0,14 ± 2,16   →  KHÔNG phân biệt được với nhiễu
```

Và độ trễ **tệ hơn thật**: 8 lượt gọi song song tranh nhau nhiều hơn 4.

**Dự báo +1,7 của tôi sai, và sai vì một lỗi thống kê cụ thể.** Công thức best-of-N giả
định các bản **độc lập** và **cùng một phân bố**. Cả hai đều không đúng: các bản trong
cùng một yêu cầu dùng chung prompt, chung model, cùng thời điểm nên tương quan với
nhau; và phân bố 22 bản tôi đo gộp **nhiều chủ đề**, nên phần lớn phương sai đo được là
phương sai **giữa các chủ đề** — thứ mà việc chọn không thể thu hoạch, vì mỗi lần chọn
chỉ chọn trong một chủ đề.

### 8.4 Bước 2 — chọn bản bằng thang 100: HOÀN TÁC sau BA lần thử

Ngưỡng: `ngôn ngữ ≥ 6,5`, `sáng tạo ≥ 2,5`, `p50 ≤ 3.500 ms`.

| người chấm | ngôn ngữ | sáng tạo | vần | p50 |
|---|---|---|---|---|
| không chọn | 3,7 | 1,2 | 17,1 | 1.750 ms |
| gpt-4o-mini, "chấm nghiêm" | 4,0 | 1,7 | 14,8 | 3.156 ms |
| gpt-4o-mini, neo thang trừ theo cụm | — | — | — | *cho điểm giống hệt nhau* |
| gpt-5-mini | 4,8 | 1,5 | 11,0 | **24.609 ms** |

Trượt cả ba ngưỡng. Latency của bản tốt nhất vượt ngưỡng **14 lần** — và đó là con số
duy nhất trong bảng lớn hơn nhiễu, nên việc bác bỏ bước 2 đứng vững bất kể phần còn lại.

Đường đi của ba lần thử đáng ghi lại:

1. `gpt-4o-mini` cho 26–38/40, trung bình **81%**, trong khi người chấm nghiêm cho
   `ngôn ngữ` 40% trên cùng loại bài. **Không phân biệt được.**
2. Neo thang bằng "đếm cụm vô nghĩa rồi trừ 8 điểm mỗi cụm" → nó cho **điểm giống hệt
   nhau** trong cùng chủ đề (40,40,40,40), tức áp một khuôn trừ điểm thay vì đọc bài.
3. Đổi sang `gpt-5-mini` (model mà người chấm của `evals/` dùng, và nó phân biệt được)
   → phân biệt được thật, nhưng **+23 giây**.

> **Bài học:** một vòng CHỌN chỉ tốt bằng NGƯỜI CHỌN. Chọn bằng một người chấm không
> phân biệt được thì không phải "chọn không ăn" — là **chưa chọn gì cả**.

Và kể cả khi người chấm phân biệt được, `ngôn ngữ` cũng chỉ lên 4,8. **Chọn không tạo
ra được chất lượng không có sẵn trong các bản.**

Code giữ lại sau `CHON_BANG_NGUOI_CHAM = False` kèm `cham_model`, theo đúng tiền lệ
`CHON_VAN_TRUOC`.

### 8.5 Bước 3–5 (từ điển) — BỊ CHẶN, cần bạn quyết

Hai bộ từ vựng tiếng Việt đủ lớn đều là **GPL**:

| nguồn | số từ | giấy phép |
|---|---|---|
| `undertheseanlp/dictionary` | 79.226 | **GPL-3.0** |
| `duyet/vietnamese-wordlist` (Viet74K) | ~74.000 | **GPL** |

Dự án này **không có file LICENSE nào**. Đưa dữ liệu GPL vào repo là một quyết định
pháp lý, và nó khó đảo ngược vì dữ liệu đi vào lịch sử git.

**Không dùng kho tài liệu nội bộ thay thế được.** Nó chỉ có 405 chunk / 598K ký tự và
là văn bản công sở — thiếu hẳn từ vựng thơ (*heo may*, *sương khói*, *bảng lảng*). Dựng
từ điển trên đó sẽ báo nhầm đúng những chữ hay, tức tạo ra chính loại hỏng-im-lặng mà
cả `plan-sua-bo-kiem-van.md` dành ra để diệt.

### 8.6 Bước 6 (few-shot) — TIỀN ĐỀ SAI

§4.3 dựa trên §13.2 của plan cũ: *"lấy ví dụ cùng chủ đề qua RAG có sẵn"*. Nhưng kho
tài liệu chứa văn bản công sở, **không có thơ**. Thứ duy nhất trong repo là
`truyen-kieu.txt` — mà bạn đã nói rõ là không làm Truyện Kiều nữa.

Muốn làm bước này thì cần một **kho lục bát hiện đại**, và đó là một việc riêng.

---

## 9. Trạng thái code sau khi thi công

Chỉ **một** thay đổi được giữ: `POEM_TIMEOUT_S`. Mọi thứ khác trở về như trước, cộng
thêm code đã tắt và các test ghim việc tắt đó.

Điều đó **không phải** là không được gì. Cái thu được là bốn hướng nghe hợp lý nay đã
có số liệu bác bỏ — và một bộ đo mà ta biết là yếu, thay vì một bộ đo ta tưởng là mạnh.
