# Sửa bộ dò bẻ chữ — plan

> Ngày lập: 12/09/2026. Trạng thái: **đã thi công**, kết quả ở §9.
>
> Tiếp theo `plan-chon-tu-co-nghia.md` §8.7. Bộ dò rộng đã vào khâu **chọn** và cho
> `bài không có cụm bẻ` 48% → 69% (p = 0,0101). Plan này nhắm hai thứ còn lại:
> **31% vẫn còn cụm bẻ**, và **vần mất 0,89 điểm** để đổi lấy mức giảm đó.

---

## 1. Đang ở đâu

| | bộ dò | báo nhầm trên Kiều | vai trò |
|---|---|---|---|
| **chặt** | bẻ dấu thanh | 0,03% | **CHẶN** — loại hẳn bản |
| **rộng** | + điệp âm | 9,22%/cặp | **CHỌN** — chỉ xếp hạng |

Ranh giới đó là có thật: chặn báo nhầm một lần là mất hẳn một bài tốt; chọn báo nhầm chỉ
đổi thứ tự ưu tiên giữa 4 bản.

---

## 2. Đường KHÔNG đi được, và phải nói trước

**Thêm từ vào `tu_vung.py` cho tới khi báo nhầm về 0.** Nghe rất hợp lý, và nó là bẫy.

159 lượt báo nhầm trên Kiều đến từ **113 cụm KHÁC NHAU** — trung bình 1,4 lượt mỗi cụm.
Phân bố thoải như vậy nghĩa là vốn từ **mở**: thêm đủ 113 cụm thì báo nhầm về 0% **trên
Kiều**, nhưng bài thơ tiếp theo sẽ gặp từ láy khác.

```
thêm  10 cụm → còn 3,56%     thêm  50 cụm → còn 1,94%
thêm  30 cụm → còn 2,55%     thêm 113 cụm → còn 0,00%   ← học vẹt corpus
```

Con số 0% cuối bảng **được tạo ra bằng định nghĩa**, không đo được gì. Và tôi chỉ có
Kiều, không có corpus giữ riêng để kiểm chứng — nên đi đường này là mất luôn khả năng
biết mình đang ở đâu.

> Đây đúng loại sai mà cả dự án này đã tốn nhiều ngày để học: **một con số đẹp có được
> bằng cách sửa thước thì không phải một cải thiện.**

---

## 3. Hai chỗ thu hẹp có NGUYÊN TẮC, đã đo

Khác với thêm từ, hai chỗ này thu hẹp bộ dò bằng **lý do**, không bằng dữ liệu Kiều —
nên chúng tổng quát hoá được.

### 3.1 Chỉ xét VỊ TRÍ VẦN

Việc bẻ chữ xảy ra **vì bí từ vần**, nên nó xảy ra ở vị trí vần. Cả hai ca thật đều thế:

```
"rực rao"    "rao" ở tiếng 8 câu bát   ← vị trí vần
"ngọt ngao"  "ngao" ở tiếng 6 câu bát  ← vị trí vần
```

Còn phần lớn báo nhầm là điệp âm ngẫu nhiên giữa hai từ kề nhau ở **giữa** câu: *thì
thôi, năm năm, vội về, lời là*.

### 3.2 Bỏ ĐIỆP TỪ (hai tiếng giống hệt nhau)

*xa xa, ngày ngày, xanh xanh, con con, chênh chênh* — điệp từ là thủ pháp có thật, và
**bẻ chữ không bao giờ tạo ra một cặp giống hệt nhau**. Loại chúng là zero-risk.

### Kết quả đo

```
bộ dò RỘNG          150/1627 = 9,22%
+ chỉ vị trí vần     50/1627 = 3,07%
+ bỏ điệp từ         35/1627 = 2,15%
```

**Cắt hơn bốn lần**, và cả hai ca thật vẫn bị bắt.

---

## 4. Vì sao 2,15% vẫn chưa đủ để làm BỘ CHẶN

Ngưỡng cho một bộ chặn là **< 1%** — đó là ngưỡng `ops/hieu_chuan_tho.py` đang dùng cho
số tiếng và số câu.

22 cụm còn lại — *tình ta, thì thôi, trăng trong, dập dìu, lưu ly, mơn man* — phần lớn
là tiếng Việt đúng. Muốn xuống dưới 1% thì lại quay về thêm từ, tức quay về §2.

> Nên **bộ dò này ở lại khâu CHỌN.** Thu hẹp không đổi vai trò của nó; nó chỉ làm việc
> chọn chính xác hơn và **rẻ hơn về điểm vần** — xem §5.

---

## 5. Vì sao thu hẹp sẽ trả lại một phần điểm vần

Hiện xếp hạng trả giá **−0,89 điểm vần** để giảm cụm bẻ. Một phần cái giá đó là **trả
oan**: bộ dò đang đếm cả *thì thôi*, *xa xa* như lỗi, nên đôi khi nó loại một bản chỉ vì
bản đó có một điệp từ hợp lệ.

Bỏ 4/5 số báo nhầm thì tín hiệu xếp hạng sạch hơn, và phần vần mất oan sẽ quay lại.

**Đây là dự đoán, chưa phải kết quả.** Nó phải được đo, và có thể sai.

---

## 6. Thứ tự thi công, và tiêu chí dừng

| # | việc | chi phí | tiêu chí dừng |
|---|---|---|---|
| 1 | Thu hẹp bộ dò rộng: vị trí vần + bỏ điệp từ | $0 | báo nhầm Kiều ≤ 2,5%; hai ca thật vẫn bắt được |
| 2 | Đo lại xếp hạng theo cặp | ~$0,05 × 2 lượt | `cụm bị bẻ` **không tăng**; `vần` **không giảm thêm** |
| 3 | Nếu vần hồi phục ≥ 0,5: giữ. Nếu không: vẫn giữ (bước 1 là thuần cải thiện độ chính xác) | | |

**Bước 2 phải chạy HAI lượt độc lập.** Tuần này đã bốn lần một lượt duy nhất đánh lừa
tôi — gần nhất là `bằng-trắc 0 lỗi` cho 4/40 → 2/40 rồi 2/40 → 10/40.

**So theo CẶP trên cùng bộ bản** — chênh lệch khi đó chỉ có thể do khâu xếp hạng.

---

## 7. Rủi ro

**Thu hẹp làm lọt ca thật.** Ví dụ một chữ bị bẻ ở giữa câu, không ở vị trí vần. Đã kiểm:
cả hai ca thật đều ở vị trí vần, và điều đó có lý do cơ chế (bẻ vì bí vần). Nhưng mẫu chỉ
có hai ca — nếu về sau gặp ca bẻ ở giữa câu thì phải xem lại §3.1.

**Cách phát hiện:** giữ bộ dò rộng nguyên bản dưới dạng một hàm riêng, và trong phép đo
bước 2 in ra số ca mà bản rộng bắt được còn bản hẹp bỏ sót. Nếu con số đó lớn thì §3.1
sai.

---

## 8. Những thứ plan này CỐ Ý không làm

- **Không thêm từ vào `tu_vung.py` để hạ báo nhầm.** §2 — đó là học vẹt corpus.
- **Không đưa bộ dò rộng lên làm bộ chặn.** 2,15% vẫn gấp đôi ngưỡng 1%.
- **Không đụng vào prompt.** Bảy lần can thiệp tầng prompt, bảy lần không cải thiện; lần
  gần nhất đo ở n=160 mỗi bên và cận trên của hiệu ứng là 0,08 cụm/bản.
- **Không hứa "mọi chữ đều có nghĩa".** Hứa được: cụm bẻ giảm, và bộ dò chính xác hơn.
  Khoảng cách giữa hai điều đó vẫn cần một từ điển thật.


---

## 9. Kết quả thi công (12/09/2026)

### 9.1 Bước 1 — thu hẹp: ĐẠT

```
bộ dò RỘNG          150/1627 = 9,22%
+ chỉ vị trí vần     50/1627 = 3,07%
+ bỏ điệp từ         35/1627 = 2,15%    ← tiêu chí ≤ 2,5%
```

Cả hai ca thật (`rực rao`, `ngọt ngao`) vẫn bị bắt. Bản rộng giữ lại sau `hep=False` để
kiểm rủi ro §7.

### 9.2 Bước 2 — đo lại: hai bộ xếp hạng gần như không khác nhau

Hai lượt độc lập, so theo cặp, n=40 mỗi lượt:

| | lượt 1 | lượt 2 |
|---|---|---|
| đổi lựa chọn | 4/40 | 5/40 |
| chênh vần | −0,119 nhiễu | **+0,881** nhiễu |
| bài không có cụm bẻ | 27→24 | 27→24 |
| rủi ro §7 (bản bỏ sót) | 46 | 45 |

Hai bộ **đồng ý ~88%**. Vần lệch hai chiều ngược nhau giữa hai lượt — nhiễu thuần tuý.

> **Dự đoán §5 của tôi SAI.** Tôi viết rằng thu hẹp sẽ trả lại một phần điểm vần đã mất,
> vì bộ dò cũ trừ oan những bài có điệp từ hợp lệ. Thực tế hai bộ chỉ bất đồng 4–5/40
> lần, quá ít để dịch chuyển trung bình. Lập luận nghe hợp lý và sai.

### 9.3 Không có trọng tài trung lập — và điều đó phải nói ra

Tôi chấm kết quả bằng **bộ dò rộng**. Nhưng bộ xếp hạng hẹp tối ưu một **tập con** của
cái đang được chấm, nên chấm bằng tập cha thì nó thua từ định nghĩa; chấm bằng tập con
thì nó thắng cũng từ định nghĩa. **Không có ground truth** cho "chữ này có bị bẻ không".

Nên căn cứ quyết định phải nằm **ngoài** phép A/B, và nó nằm ở §9.4.

### 9.4 Đọc tận mắt — bằng chứng thay cho suy luận

Sinh 80 bản nháp mới, in ra những cụm bản rộng bắt còn bản hẹp bỏ:

```
HẸP BỎ  (25 cụm)  lững lờ · hiu hiu · vội vã · mộng mị · đồng đội · lấp lửng
                  · sáng soi · đêm đông · nhớ những · bếp bay · đường đến
                  -> gần như toàn TỪ THẬT hoặc hai từ kề nhau vô tội

HẸP GIỮ (14 cụm)  mơ mang · xao xát · đậm đàng · hiền hung
                  -> chứa đúng các ca BẺ THẬT
```

**Việc thu hẹp được xác nhận**: thứ nó bỏ đi là vô tội, thứ nó giữ lại chứa ca thật.

### 9.5 Một con số mới, và nó khiêm tốn hơn nhiều

Trong 14 cụm bộ hẹp giữ lại, chỉ **~4 là bẻ thật** — độ chính xác **~29%**, không phải
~98% như tỉ lệ báo nhầm 2,15% trên Kiều gợi ý.

Lý do: **Kiều đo báo nhầm trên thơ HAY**. Thơ của bot có nhiều cụm lưng chừng hơn hẳn,
nên tỉ lệ đo trên Kiều là **cận dưới**, không phải ước lượng.

> Đây là chỗ tôi suýt tự lừa: một bộ dò "98% chính xác" trên corpus hiệu chuẩn hoá ra
> chỉ ~29% trên dữ liệu thật. Tỉ lệ đo trên thơ chuẩn mực nói lên rất ít về hành vi trên
> thơ của bot.

### 9.6 Sửa được ngay: thêm các TỪ THẬT bị báo nhầm

Phần lớn báo nhầm ở §9.4 là **từ thật tôi thiếu** — `bến bờ`, `mùa màng`, `mải mê`,
`lững lờ`, `vội vã`, `mộng mị`, `đồng đội`, `xao xác`…

Thêm chúng **không phải** cái bẫy §2: chúng được tìm thấy trên **thơ của bot**, không
phải trên corpus hiệu chuẩn. Thêm từ tìm thấy ở nguồn khác thì cải thiện tổng quát hoá;
thêm từ rút từ chính corpus đo thì chỉ làm đẹp con số.

```
406 -> 439 từ

báo nhầm CHẶT (chặn)   1/1627 = 0,06%
báo nhầm HẸP  (chọn)  31/1627 = 1,91%   (từ 2,15%)
```

Hai ca thật vẫn bị bắt.

### 9.7 Còn nợ

`1,91%` vẫn gấp đôi ngưỡng 1% để làm bộ chặn, và độ chính xác thật trên thơ bot là ~29%.
Muốn hơn nữa thì phải **lặp lại §9.4** — sinh thơ, đọc tận mắt cụm bị báo, thêm từ thật
vào danh sách. Mỗi vòng như vậy rẻ (~$0,01) và cải thiện thật, nhưng nó là **thủ công**
và không có điểm dừng tự nhiên.

Từ điển thật vẫn là thứ cắt đứt được vòng lặp đó.


---

## 10. Vòng lặp §9.7 — đã chạy ba vòng, và đã tới điểm dừng (12/09/2026)

### 10.1 Công cụ, để vòng lặp không phụ thuộc vào tôi

`ops/soi_cum_nghi.py` — sinh thơ, in ra các cụm bị nghi kèm từ thật gần nhất, để người
đọc phân xử. Kèm cảnh báo ngay trong docstring: **đừng rút từ từ Truyện Kiều** để thêm
vào, vì đó là học vẹt chính corpus dùng để hiệu chuẩn (§2).

```
uv run python ops/soi_cum_nghi.py --so 40
```

### 10.2 Ba vòng

| | từ | báo nhầm Kiều (chọn) | báo nhầm Kiều (chặn) | cụm bị nghi/160 bản |
|---|---|---|---|---|
| đầu | 406 | 2,15% | 0,06% | 28 |
| vòng 2 | 439 | 1,91% | 0,06% | 28 |
| vòng 3 | 452 | 1,78% | **0,00%** | 17 |
| vòng 4 | 460 | **1,72%** | **0,00%** | 20 |

**Bộ chặn giờ không báo nhầm câu nào trong 1.627 cặp Truyện Kiều.**

### 10.3 Một lỗi TRA CỨU, không phải thiếu từ

Vòng 3 phát hiện `hiền hoà` bị báo trong khi `hiền hòa` **đã có** trong danh sách. Đó là
hai quy ước đặt dấu của cùng một chữ:

```
kiểu cũ   "hòa"  "hóa"  "thủy"  "lòa"      dấu trên nguyên âm đầu
kiểu mới  "hoà"  "hoá"  "thuỷ"  "loà"      dấu trên nguyên âm chính
```

Thêm `hiền hoà` vào danh sách là **vá triệu chứng**. Sửa đúng là tra cứu bằng dạng đã
phân giải (`chuan_hoa`), và nó sửa luôn mọi cặp tương tự chưa gặp.

**Và việc sửa đó đẻ ra một lỗi khác, bắt được nhờ test:** bảng tra lưu dạng chuẩn rồi lấy
ngược ra, nên lời nhắc sửa thành *"từ thật là ngọt ngao"* — chính cái chữ vừa báo là sai.
Một lời nhắc như vậy còn tệ hơn không nhắc. Sửa: khoá ở dạng chuẩn, **giá trị giữ nguyên
văn**.

### 10.4 Điểm dừng, và nó là điểm dừng thật

Vòng 4 còn 20 cụm, nhưng phần lớn **không còn là thiếu từ**:

```
tình ta · đường đi · cành cây · câu ca · nhẹ như · xa xưa · lắng lòng
```

Đây là **hai từ kề nhau vô tội** ngẫu nhiên cùng phụ âm đầu — không phải từ ghép. Thêm
`tình ta` vào danh sách từ là dán nhãn sai để làm đẹp con số.

> Đây là giới hạn **cấu trúc** của luật điệp âm, không phải lỗ hổng vốn từ. Vòng lặp
> thêm từ đã hết tác dụng, và tiếp tục nó là bắt đầu tự lừa mình.

Độ chính xác thật trên thơ bot: **~40%** (từ ~29%). Còn lại chủ yếu là báo nhầm cấu trúc.

### 10.5 Trạng thái cuối

| | |
|---|---|
| bộ CHẶN (`cum_kha_nghi`) | **0,00%** báo nhầm trên Kiều — chặn được an toàn |
| bộ CHỌN (`cum_nghi_be`) | 1,72% trên Kiều · ~40% chính xác trên thơ bot |
| bắt được | `ngọt ngao`, `rực rao` — cả hai ca thật |
| công cụ | `ops/soi_cum_nghi.py` chạy lại được bất cứ lúc nào |

Muốn qua ~40% thì phải phân biệt `tình ta` (vô tội) với `rực rền` (bẻ) — tức phải biết
**nghĩa**, không suy từ chính tả được nữa. Vẫn là từ điển thật.
