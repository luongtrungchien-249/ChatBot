# Đánh giá tổng thể hệ thống làm thơ — plan

> Ngày lập: 15/09/2026. Trạng thái: **§2 đã thi công**, §3-§6 chưa.
>
> Yêu cầu: *"làm thế nào để có thể đánh giá tổng thể được hệ thống có thật sự tốt hay
> không / cần tạo cái gì"*.

---

## 1. Vì sao câu hỏi này chưa trả lời được

Trước hôm nay, **mọi con số về thơ trong dự án đều đến từ một script tạm với danh sách
chủ đề tự chế, mỗi lần một khác**. Hậu quả đo được:

```
vần   8,40   (người con gái VN xưa)
     11,12   (uống nước nhớ nguồn)
     13,33   (mùa thu Hà Nội)
```

Cùng cấu hình, cùng n — **chênh 4,9 điểm chỉ vì đổi chủ đề**. Lớn hơn *mọi* cải thiện
đo được trong hai ngày làm việc. Nghĩa là câu hỏi *"hệ thống có tốt lên không"* không
thể trả lời bằng cách chạy một chủ đề rồi so với lần trước — và đó đúng là cách mọi
phép đo trước đây đã làm.

Phía RAG có `evals/runner.py` với ngưỡng, mã thoát, chạy trong CI. Phía thơ **không có
gì tương đương**.

---

## 2. Đã thi công — bộ chuẩn và bộ chạy

`evals/runner_tho.py` + `evals/tho/bo_chuan.jsonl` (40 đề · 14 chủ thể).

Bốn quyết định thiết kế, mỗi cái vá một chỗ đã từng làm hỏng phép đo:

| # | quyết định | vá chỗ nào |
|---|---|---|
| 1 | **bộ chủ đề đóng băng** | độ khó chủ đề lấn át mọi hiệu ứng khác |
| 2 | **neo chấm trong cùng lượt** | trần (ca dao) trước đây đo ở lần chạy khác |
| 3 | **hai lượt độc lập, tự động** | `LAP_Y` suýt được ship vì chỉ chạy một lượt |
| 4 | **thang tất định không phán quyết** | Goodhart — nó là hàm hệ thống được tối ưu |

Bộ chuẩn lấy từ **tập test của RLVR**, nên đã tách khỏi tập huấn luyện theo chủ thể.
Train RLVR xong vẫn đánh giá được bằng chính bộ này mà không nhiễm.

**Ngưỡng đặt theo NEO, không theo số tuyệt đối:**

```
bot / ca dao      >= 55%
bot - văn xuôi    >= 2,0 điểm
đúng khung        >= 90%
cụm bị bẻ         <= 10%
chép bài mẫu      =  0
p95               <= 6.000 ms
hai lượt lệch     <= 3,0   -> vượt thì KHÔNG kết luận gì, kể cả kết luận xấu
```

Lý do: *"ngôn ngữ ≥ 5,0"* không nói lên gì nếu hôm đó người chấm chặt tay hơn.
*"≥ 55% của ca dao"* thì có — vì cả hai đi cùng một mẻ chấm.

Lượt thử 10 đề đã cho thấy neo làm được việc, **và lộ ra một điều đáng lưu**:

```
ca dao 47,00   ·   bot 33,50   ·   văn xuôi 28,50
```

Văn xuôi xuống dòng được **28,5/40**. Người chấm rộng tay với văn xuôi hơn ta tưởng,
nghĩa là **thang bị nén**: đọc `ngôn ngữ 6,00` một mình là vô nghĩa.

---

## 3. Mảnh còn thiếu lớn nhất — hiệu chuẩn người chấm bằng NGƯỜI

Toàn bộ cột "nội dung" hiện là **model chấm model**. Ta neo nó bằng ca dao và văn xuôi,
nhưng đó vẫn là hai điểm do chính model định vị. Chưa ai biết `ngôn ngữ 6,00` có tương
ứng với cảm nhận của người đọc không.

Đây là mảnh **duy nhất tôi không tự dựng được**, và cũng là mảnh làm cho mọi con số còn
lại có nghĩa hay không.

### 3.1 Việc cần bạn làm — khoảng 30-40 phút

`ops/cham_tay.py` (chưa viết) sẽ:

1. Rút **30 bài** từ lần chạy gần nhất: 10 bài điểm cao, 10 bài giữa, 10 bài thấp
   (theo người chấm) — **trộn ngẫu nhiên, giấu điểm máy**.
2. Trộn thêm **5 neo**: 3 ca dao + 2 văn xuôi, không nói cho bạn biết bài nào là gì.
3. Hiện từng bài, xin bạn cho điểm **3 mục** trên thang 0-10:
   - `ngôn ngữ` — có chữ nào nhét vào chỉ để ép vần không
   - `hình ảnh` — có hình ảnh thật, cụ thể không
   - `sáng tạo` — có gì mới, hay chỉ lặp cái ai cũng viết được
4. Ghi vào `evals/tho/cham_tay.jsonl`.

**Ba mục, không phải sáu.** `nhịp` thì máy chỉ kiểm được một phần; `ý nghĩa` và `cảm
xúc` khó nhất quán khi chấm tay. Ba mục này là ba mục có khoảng cách lớn nhất tới ca
dao, tức ba mục đáng tin cậy hoá nhất.

**Neo trộn lẫn và giấu nhãn** là bắt buộc: nếu biết bài nào là ca dao thì điểm sẽ bị
kéo theo kỳ vọng, và ta mất luôn cái mốc cần.

### 3.2 Đo gì từ đó

```
tương quan Spearman giữa điểm NGƯỜI và điểm MÁY, từng mục
```

| kết quả | nghĩa là | làm gì |
|---|---|---|
| ρ ≥ 0,6 | người chấm **dùng được** | giữ nguyên, ghi ρ vào tài liệu |
| 0,3 ≤ ρ < 0,6 | yếu — xếp hạng thô thì được, con số tuyệt đối thì không | chỉ dùng để so hai nhánh, đừng báo cáo trị tuyệt đối |
| ρ < 0,3 | **không đo cái ta nghĩ nó đo** | mọi kết luận dựa vào cột nội dung phải rút lại |

Và kiểm riêng **neo**: bạn có xếp ca dao trên bot, bot trên văn xuôi không. Nếu người
không tách được ba nhóm thì chính bài toán đang mơ hồ, chứ không phải người chấm sai.

*Chi phí:* 35 bài × ~1 phút. Không gọi model. Làm một lần, dùng lại mãi.

---

## 4. Nối vào CI

`evals.yml` hiện chỉ chạy đánh giá RAG. Thêm một job cho thơ, nhưng **không chạy mỗi
push**: một lượt đầy đủ tốn ~90 lượt gọi model.

Đề xuất: chạy **theo lịch** (tuần một lần) và **khi chạm vào `src/tho/`**. Dùng đúng mã
thoát của `runner_tho.py` (0/1/2) như `runner.py` — CI đã biết cách đối xử với ba mã đó.

Kèm một luật: **không đặt ngưỡng nào thành cổng chặn CI cho tới khi có 5 lần chạy** để
biết nó dao động bao nhiêu. Chính `evals/runner.py` đã ghi bài học này cho
`Answer Relevance`: *"một job đỏ mãi là một job không ai đọc nữa"*.

---

## 5. Những gì bộ đánh giá này **không** trả lời được

Phải ghi rõ, vì một bộ đánh giá được tin quá mức còn nguy hơn không có:

1. **Không so được với hệ thống khác.** Nó đo hệ thống này theo thời gian, không đo
   "thơ của bot so với thơ của ChatGPT".
2. **Không đo được thứ người chấm không thấy.** Nếu mô hình tìm ra một kiểu lách mà cả
   verifier lẫn người chấm đều không bắt — như `diễn nhạc tình` đã lọt qua cả hai —
   bộ này sẽ báo ĐẠT.
3. **40 đề vẫn là ít.** Khoảng tin cậy trên 40 bài cho `sáng tạo` rộng khoảng ±0,3.
   Hiệu ứng nhỏ hơn thế thì bộ này không thấy.
4. **Neo chỉ có 4 + 2 bài.** Trần và sàn đều là ước lượng thô.

---

## 6. Thứ tự thi công

| # | việc | cần ai | giá trị nếu dừng ở đây |
|---|---|---|---|
| 1 | ✅ bộ chuẩn + `runner_tho.py` | — | đã có thước đo lặp lại được |
| 2 | chạy đầy đủ 40 đề × 2 lượt, ghi mốc đầu | tôi | có con số nền để so về sau |
| 3 | `ops/cham_tay.py` | tôi viết | — |
| 4 | **bạn chấm 35 bài** | **bạn** | biết cột nội dung có đáng tin không |
| 5 | đo Spearman, ghi vào tài liệu | tôi | mọi số nội dung có hoặc mất ý nghĩa |
| 6 | nối vào CI theo lịch | tôi | bắt hồi quy tự động |

Bước 4 là bước duy nhất cần bạn, và nó chặn bước 5 — mà bước 5 mới là thứ quyết định
toàn bộ cột "nội dung" có dùng được hay không.
