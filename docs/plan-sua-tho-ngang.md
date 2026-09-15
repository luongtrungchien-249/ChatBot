# Sửa thơ "ngang" — plan

> Ngày lập: 15/09/2026. Trạng thái: **§3 (lớp A) đã xong**; §5 đang chờ bạn chấm tay.
>
> Xuất phát: người dùng chấm tay 5 bài đầu và chỉ ra thơ *"bị ngang"*.

---

## 1. Dữ liệu người dùng vừa cho — và nó nói được nhiều hơn 5 bài

| # | loại | NGƯỜI (nn/ha/st) | MÁY (nn/ha/st) |
|---|---|---|---|
| 1 | bot | 10/10/6 | 7/6/1 |
| 2 | bot | **0/0/0** | 2/5/1 |
| 3 | **ca dao** | **10/10/10** | — |
| 4 | bot | 5/10/10 | 3/6/1 |
| 5 | bot | 6/10/6 | 6/8/2 |

**Hai điều đọc được ngay:**

**(a) Người TÁCH được ca dao khỏi bot.** Bài 3 là neo trên **trộn lẫn, giấu nhãn** — người dùng cho 10/10/10, cao nhất bộ. Nghĩa là thang chấm tay có nghĩa, và phép hiệu chuẩn ở
`docs/plan-danh-gia-tong-the.md` §3 đáng làm tiếp.

**(b) Máy chấm `sáng tạo` quá chặt.** Người cho 6 · 0 · 10 · 6; máy cho 1 · 1 · 1 · 2.
Máy dồn gần hết về 1, tức **không phân biệt được** — mà `sáng tạo` đúng là mục hệ thống
đang kém nhất. Đây là nghi vấn nghiêm trọng về chính thước đo, không phải về thơ.

*4 bài thì chưa tính tương quan được.* Cần đủ 30 bài rồi mới kết luận.

---

## 2. "Ngang" gồm ba lớp lỗi khác hẳn nhau

Đọc kỹ các bài người dùng cho điểm thấp:

| lớp | ví dụ thật | bắt được bằng code? |
|---|---|---|
| **A. tiếng không phải tiếng Việt** | `mìmh` (bài 2) | **ĐƯỢC** — xem §3 |
| **B. cụm hai tiếng vô nghĩa** | `đêm rờ`, `ấm nỡ`, `bầu gian` | **KHÔNG** — đã đo, xem §4 |
| **C. hình ảnh rời rạc** | `Bát cơm nóng hổi giữa rừng` + `chiếc khăn bạc màu` | **KHÔNG** — đã đo, xem §4 |

Gộp cả ba vào một chữ "ngang" là lý do trước đây không sửa được: mỗi lớp cần một công cụ
khác nhau, và hai trong ba đã có kết luận âm rồi.

---

## 3. Lớp A — thi công ngay, đã có số đo

Bài 2 được người dùng cho **0/0/0**. Máy cho **32,71/45 tất định** và **0,778/1,000
thưởng**, `cum_kha_nghi` báo **không bắt được gì**.

Nguyên nhân:

```
mìmh  ->  vần 'imh'  ->  âm chính 'h'   <- KHÔNG PHẢI NGUYÊN ÂM
mình  ->  vần 'inh'  ->  âm chính 'i'   âm cuối 'nh'
```

`mìmh` **không phải một âm tiết tiếng Việt**. Cấu trúc âm tiết tiếng Việt là hữu hạn và
đều đặn, nên kiểm được **tất định**: âm chính phải toàn nguyên âm.

**Đã đo trước khi đề xuất:**

```
Truyện Kiều   22.778 tiếng · báo nhầm 2 = 0,009%
              (cả hai là `Gìn`/`gìn` — ca biên của phụ âm kép `gi`)
40 bài bot    1 bài có tiếng không hợp lệ  (`mìmh`)
```

**0,009 %** thấp hơn cả ngưỡng của bộ chặn hiện có. Đây là bộ dò duy nhất trong ba lớp
đủ sạch để **chặn**, không chỉ xếp hạng.

### Việc đã làm — 15/09/2026

1. `tho/tu_vung.py`: `tieng_la()` + `tieng_khong_hop_le()` ✓
2. Ca biên `gi` ✓ — **và nó không phải ca biên, nó là một lỗi thật**. Xem dưới.
3. Nối vào ba chỗ ✓
   - `sinh.py` chặng 1a — bộ lọc cứng, đặt **trước** `cum_kha_nghi` vì sạch hơn
   - `phan_thuong.py` — `PHAT_TIENG_SAI = 0.0`, cùng hạng với `chép`
   - vết bước 8 — `VetCon("tiếng không phải tiếng Việt")`
4. `tests/unit/test_tho_tieng_hop_le.py` — 5 test ✓

### Số đo sau khi thi công

```
Truyện Kiều          22.778 tiếng   báo nhầm 0   0,000%
thất ngôn bát cú        392 tiếng   báo nhầm 0   0,000%
thất ngôn tứ tuyệt      224 tiếng   báo nhầm 0   0,000%

bài người dùng cho 0/0/0:   thưởng 0,778  ->  0,000
```

### Cái tìm được ngoài dự kiến

Lần đo đầu báo nhầm 2 tiếng, cả hai là `Gìn`/`gìn`. Tôi đã ghi trong plan rằng đó là
"ca biên của phụ âm kép `gi`". **Sai.** Đó là một lỗi thật của `lay_van`:

```
gìn  ->  bỏ dấu 'gin'  ->  bóc phụ âm kép 'gi'  ->  còn 'n'   <- MẤT NGUYÊN ÂM
```

Tức `gìn` **không thể hiệp vần với bất cứ tiếng nào** — `gìn ~ tin` trả về `False`. Lỗi
này nằm im trong kho từ lâu và không bộ test nào bắt được, vì tất cả đều kiểm *giá trị
vần đúng*, không kiểm *vần có nguyên âm không*. `lay_van` nay bỏ qua phụ âm đầu nào mà
bóc xong không còn nguyên âm. Báo lỗi giả trên Kiều: 5,8% → **94/1627 = 5,78%**.

Đáng ghi lại vì đây là lần thứ hai trong dự án một bộ dò mới tìm ra lỗi của bộ dò cũ,
chứ không tìm ra lỗi của model.

### Một quyết định đã nới ra

Tiếng không chứa **chữ cái** nào (`1975`, `—`) thì bộ dò không có ý kiến. Nó kiểm cấu
trúc âm tiết; một con số không phải âm tiết sai, nó là một thứ khác. Chặn nó ở đây biến
bộ lọc cứng thành cái từ chối bài thơ có năm tháng.

*Chi phí:* không gọi model, chạy micro-giây.

---

## 4. Lớp B và C — đã thử, đã trượt, và phải nói thẳng

Không đề xuất làm lại, vì đã có số:

| cách | báo nhầm trên thơ chuẩn | ngưỡng cần |
|---|---|---|
| cụm bị bẻ từ **chính tả** (460 từ) | 0,00 % nhưng **không bắt được** `bầu gian` | — |
| cụm vần không có trong **từ điển 18k** | **79,3 %** | 1,60 % |
| mạch nội dung bằng **trường nghĩa** | **19,50 %** | 1,60 % |
| LLM chấm **đối ý** | lặp lại ổn (ρ tín hiệu/nhiễu 4,40) nhưng **cùng một câu hai lần = 10/10** | — |

Phân biệt `bầu gian` với `trước đèn` cần **nghĩa**, không phải chính tả. Bốn đường đã
bịt. Đường duy nhất đo được là **đổi model**: `gpt-5-mini` cho `ngôn ngữ 6,25-6,42` so
với `4,75-5,50` của `gpt-4o-mini` — nhưng sụp ở vần (2,2/20 so với 14,1/20).

**Nên với lớp B/C, plan này không hứa gì.** Việc trung thực nhất là §5.

---

## 5. Nghi vấn về chính thước đo `sáng tạo`

Người: `6 · 0 · 10 · 6`. Máy: `1 · 1 · 1 · 2`.

Máy dồn gần hết về 1 — **không phân biệt được**. Mà suốt hai ngày qua tôi đã dùng đúng
con số đó để kết luận *"bốn hướng đều không dịch được sáng tạo"*:

```
prompt · chọn lọc · nhiệt độ · câu đắt   ->  sáng tạo không nhúc nhích
```

Nếu thước đo bị nén ở đáy thì **những kết luận âm đó có thể là của thước đo, không phải
của hệ thống**. Đây là khả năng phải kiểm, không phải chi tiết nhỏ.

### Việc cần làm

1. Người dùng chấm nốt 30 bài còn lại (`ops/cham_tay.py`)
2. Đo Spearman **riêng cho `sáng tạo`**
3. Nếu ρ < 0,3 → **rút lại bốn kết luận âm kia** và đo lại bằng thang người
4. Nếu ρ ≥ 0,6 → bốn kết luận đó đứng vững, và `sáng tạo` đúng là chỗ hệ thống kém

*Đây là bước có đòn bẩy cao nhất trong cả plan*, vì nó quyết định bốn kết luận trước có
còn giá trị không.

---

## 6. Thứ tự thi công

| # | việc | cần ai | đòn bẩy |
|---|---|---|---|
| 1 | ~~bộ dò **tiếng không hợp lệ** + nối 3 chỗ + test~~ **XONG** | tôi | bịt lớp A |
| 2 | chấm nốt 30 bài | **bạn** | mở khoá bước 3 |
| 3 | Spearman, đặc biệt `sáng tạo` | tôi | **quyết định 4 kết luận trước còn giá trị không** |
| 4 | tuỳ kết quả 3 | — | — |

Bước 1 làm được ngay và độc lập. Bước 3 là bước quan trọng nhất trong cả tài liệu này.
