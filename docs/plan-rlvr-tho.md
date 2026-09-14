# RLVR cho thơ luật — verifier làm hàm thưởng, huấn luyện bằng GRPO

> Ngày lập: 14/09/2026. Trạng thái: **bước 1-5 xong** (§9). Bước 6-7 đã có script,
> chờ GPU để chạy.
>
> Yêu cầu: xây verifier chấm điểm chính xác một bài thơ theo từng luật của **Lục bát**
> và **Thất ngôn bát cú**, rồi thiết kế reward verifiable từ kết quả đó để huấn luyện
> lại LLM bằng **GRPO**, kiểm chứng xem có nâng được tỉ lệ thơ đúng luật so với model
> gốc hay không.

---

## 1. Vì sao hướng này đúng — bằng số đo vừa lấy hôm nay

Không phải suy đoán. Đo n=12 chủ đề, **hai lượt độc lập**, cùng prompt, cùng đường ống:

| | gpt-4o-mini | gpt-5-mini | mốc ca dao |
|---|---|---|---|
| sáng tạo /5 | 1,33 · 1,42 | **3,00 · 3,08** | 2,75 |
| hình ảnh /10 | 5,83 · 6,75 | **8,00 · 8,00** | 7,25 |
| ý nghĩa /10 | 7,50 · 7,75 | 8,25 · 8,08 | 8,75 |
| **vần /20** | **14,11 · 11,67** | **2,22 · 3,33** | — |

Model mạnh hơn **vượt cả mốc ca dao** về sáng tạo và hình ảnh, nhưng **sụp hoàn toàn ở
vần**. Hai model hỏng ngược nhau.

Điều đó cho hướng đi này ba chỗ tựa:

**(a) Chiều hỏng của model mạnh đúng là chiều verify được.** Vần, số tiếng, bằng-trắc,
niêm đều là hàm tất định trên chuỗi. Không cần người chấm, không cần preference.

**(b) Can thiệp bằng prompt đã cạn.** 9 lần can thiệp trong dự án này, **8 thất bại**.
Chọn lọc có cận trên +0,575 và giá ≥4,8 giây. Nhiệt độ lấy mẫu: phẳng, phá mọi thứ
khác. Những cần gạt rẻ đã thử hết — cái còn lại là **đổi chính policy**.

**(c) Phần lớn verifier đã có và đã hiệu chuẩn.** Xem §2.

---

## 2. Kiểm kê verifier: đã có gì, thiếu gì

### 2.1 Đã có, đã hiệu chuẩn trên Truyện Kiều

| luật | hàm | báo nhầm trên thơ chuẩn |
|---|---|---|
| số tiếng, số câu | `kiem_luc_bat` | **0,0 %** |
| bằng-trắc (nhị tứ lục) | `_kiem_bang_trac` | **0,0 %** |
| tiếng 6 ≠ tiếng 8 câu bát | `kiem_luc_bat` | 0,0 % |
| **vần** | `lay_van` + `van_nhau` | **17,0 %** ⚠️ |
| nhịp | `kiem_nhip` | *chỉ kiểm được dấu phẩy* |
| thất ngôn **tứ tuyệt** | `kiem_that_ngon_tu_tuyet` | chưa hiệu chuẩn |
| chấm điểm liên tục | `cham_tat_dinh` → 45 điểm | — |

`cham_tat_dinh` **đã cho điểm theo tỉ lệ đạt/tổng**, không phải nhị phân. Đó đúng là
dạng tín hiệu GRPO cần — thưởng đặc, không thưa.

### 2.2 Thiếu — phải xây

| | ghi chú |
|---|---|
| **Thất ngôn bát cú** (8 câu) | chưa có gì; dự án mới chỉ có **tứ tuyệt** (4 câu) |
| **Niêm** | chưa có; là ràng buộc *giữa các cặp câu*, tất định hoàn toàn |
| **Đối** (câu 3-4, 5-6) | chưa có — và **không verify tất định được trọn vẹn**, xem §3 |
| Hàm thưởng chung | `cham_tat_dinh` mới chỉ cho lục bát, chưa chuẩn hoá về [0,1] |
| Bộ chủ đề huấn luyện | chưa có |

---

## 3. Hai chỗ phải nói thẳng trước khi xây

### 3.1 Vần báo nhầm 17 % — với vai trò THƯỞNG thì đây là vấn đề nghiêm trọng

Dự án này đã có sẵn một ranh giới được ghi trong `sinh.py`: bộ **chặn** cần gần như
không bao giờ sai, bộ **chọn** thì chịu được nhiễu. RLVR thêm **vai trò thứ ba** —
**thưởng** — và nó khắt khe hơn cả hai:

> Một bộ lọc báo nhầm 17 % thì loại oan 17 % bài tốt — khó chịu nhưng không tích luỹ.
> Một hàm **thưởng** báo nhầm 17 % thì **dạy model tránh những vần đúng**, và sai lệch
> đó tích luỹ qua từng bước cập nhật. Model sẽ học đúng cái sai của verifier.

Nên **việc đầu tiên không phải là GRPO, mà là hạ 17 % xuống**. Đây cũng là việc rẻ nhất
và chắc chắn có ích kể cả khi phần RLVR không đi tiếp.

### 3.2 "Đối" không phải ràng buộc tất định trọn vẹn

Tiền đề của báo cáo là *"các luật này đều có thể biểu diễn thành hàm kiểm tra xác
định"*. Đúng với **số tiếng, vần, thanh điệu, niêm**. **Không hoàn toàn đúng với đối.**

Đối chuẩn đòi hai câu tương ứng nhau về **từ loại** và **ý** — danh đối danh, động đối
động, và nghĩa phải tương hoặc phản. Từ loại cần bộ gán nhãn tiếng Việt; ý thì không có
cách tất định.

Verify được, và nên làm:
- số tiếng bằng nhau (hiển nhiên, đã có)
- **thanh đối**: tiếng 2-4-6 của hai câu ngược thanh — tất định 100 %
- **cấu trúc ngắt nhịp** giống nhau — một phần

Không verify được: danh-đối-danh, và nghĩa tương/phản.

**Đề xuất:** tách `doi_thanh` (tất định, vào thưởng) khỏi `doi_tu_loai` (xấp xỉ, **không**
vào thưởng, chỉ báo cáo). Đưa một xấp xỉ ồn vào hàm thưởng là lặp lại đúng lỗi 17 % ở
§3.1, chỉ tệ hơn.

---

## 4. Lớp 1 — verifier

### 4.1 Thất ngôn bát cú: `kiem_that_ngon_bat_cu`

```
8 câu × 7 tiếng
vần:   cuối câu 1, 2, 4, 6, 8 — cùng một vần (câu 1 có thể thất vận)
luật:  bằng hoặc trắc, xét tiếng 2-4-6 ("nhất tam ngũ bất luận")
niêm:  câu 1–8, 2–3, 4–5, 6–7 cùng thanh ở tiếng 2
đối:   câu 3–4 (thực) và câu 5–6 (luận)
bố cục: đề (1-2) · thực (3-4) · luận (5-6) · kết (7-8)
```

Thi công theo đúng nếp `kiem_luc_bat` đã có:
- sai số tiếng thì **không** kiểm vần/thanh trên câu đó (tránh lỗi giả dây chuyền)
- thử **cả luật bằng lẫn luật trắc**, lấy bản ít lỗi hơn — tác giả không khai báo trước
- mỗi lỗi là một `Loi(cau, loai, mo_ta)` để dùng lại được toàn bộ hạ tầng

### 4.2 Hiệu chuẩn — bắt buộc, trước khi dùng làm thưởng

Cùng nguyên tắc `ops/hieu_chuan_tho.py`: **mỗi lần verifier bảo Nguyễn Khuyến sai luật,
gần như chắc chắn là verifier sai.**

Cần một tập thơ bát cú chuẩn (Qua Đèo Ngang, Thu điếu, Bạn đến chơi nhà, Thương vợ…).
Ngưỡng: số tiếng/số câu **0 %**, niêm **< 2 %**, bằng-trắc **< 5 %**, vần **< 5 %**.

Nếu không đạt, **verifier chưa được dùng làm thưởng** — dù phần RLVR đã sẵn sàng.

### 4.3 Hạ tỉ lệ báo nhầm vần (§3.1)

Việc rẻ nhất và có ích nhất. Hướng: soi 17 % ca báo nhầm trên Kiều, phân loại, và mở
rộng `_THONG_VAN` theo **âm cuối** — đúng cách đã hạ 30,5 % → 17,0 % lần trước.

*Mục tiêu:* **< 8 %**. *Chi phí:* không gọi model, chạy trong vài giây, lặp được.

---

## 5. Lớp 2 — hàm thưởng verifiable

```python
def phan_thuong(bai: str, the_tho: TheTho) -> float:   # [0, 1]
```

**Thưởng đặc, không thưa.** Nhị phân (đúng luật / không) thì với model gốc gần như luôn
bằng 0 → GRPO không có gradient để đi. Cho điểm theo **tỉ lệ ràng buộc thoả** — đúng
cách `cham_tat_dinh` đang làm.

Trọng số đề xuất, và lý do:

| thành phần | trọng số | vì sao |
|---|---|---|
| số tiếng / số câu | 0,30 | ràng buộc cứng nhất; sai thì mọi thứ khác vô nghĩa |
| vần | 0,35 | **chỗ model mạnh hỏng nặng nhất** (2,2/20) — đây là mục tiêu chính |
| bằng-trắc / niêm | 0,25 | đo được sạch (0 % báo nhầm) |
| đối thanh (bát cú) | 0,10 | tất định; chỉ phần thanh |

**Chống lách (reward hacking) — phải có ngay từ đầu, không thêm sau:**

- **chép** — `so_cau_chep` đã có: chép ca dao là cách dễ nhất để ăn điểm luật tuyệt đối.
  Chép thì thưởng **= 0**.
- **bẻ chữ** — `cum_kha_nghi` đã có: bẻ `ngọt ngào → ngọt ngao` cho khớp vần **làm tăng**
  điểm vần. Đây là lỗ hổng nguy hiểm nhất, vì nó *trực tiếp* được thưởng.
- **lặp chữ / bài suy biến** — phạt lặp tiếng bất thường.
- **độ dài** — bài dài hơn thì dễ ăn điểm tỉ lệ hơn; chuẩn hoá theo số ràng buộc.

> Ba trong bốn chốt chặn này **đã tồn tại và đã hiệu chuẩn** trong dự án. Đó là lợi thế
> lớn nhất của việc làm RLVR trên nền repo này thay vì từ đầu.

---

## 6. Lớp 3 — GRPO

### 6.1 Điều kiện bắt buộc

**Không train được `gpt-4o-mini`/`gpt-5-mini` qua API.** Phải có model mở. Dự án đã lường
trước: `POEM_BASE_URL` / `POEM_MODEL_ID` đã có sẵn để trỏ sang máy tự host
(xem `docs/plan-lam-tho-va-tu-host.md`).

| | |
|---|---|
| model nền | Qwen2.5-7B-Instruct hoặc Gemma — có tiếng Việt, vừa 1 GPU khi LoRA |
| thư viện | TRL `GRPOTrainer` + vLLM cho sinh |
| phần cứng | 1×A100 40GB (hoặc 24GB với LoRA + 4-bit) |
| dữ liệu | **chỉ cần danh sách chủ đề** — RLVR không cần thơ mẫu |

Điểm đắt giá của RLVR ở đây: **không cần tập thơ có nhãn.** Thưởng sinh ra từ verifier,
nên dữ liệu huấn luyện chỉ là vài nghìn chủ đề — thứ có thể sinh bằng code.

### 6.2 Thiết kế GRPO

GRPO so sánh **một nhóm** đầu ra cho cùng một prompt, lấy lợi thế tương đối trong nhóm —
không cần value model. Trùng khớp tự nhiên với `SO_BAN=4` đang chạy.

```
nhóm G = 8 bài / chủ đề
lợi thế = (r_i − mean(r)) / std(r)
KL đối chiếu model gốc, β ≈ 0,04   — giữ không trôi khỏi tiếng Việt tự nhiên
```

### 6.3 Nghiệm thu

So với **chính model nền chưa huấn luyện**, trên tập chủ đề **chưa từng thấy khi train**:

```
ĐẠT khi:  tỉ lệ bài SẠCH LUẬT tăng có ý nghĩa (Fisher, n >= 200)
GIỮ khi:  ngôn ngữ / hình ảnh / ý nghĩa (người chấm) KHÔNG tụt quá 0,5
          chép bài mẫu = 0
          cụm bị bẻ không tăng
```

Cột "GIỮ" là phần dễ bị bỏ quên nhất: **tối ưu thẳng vào luật sẽ hy sinh chất thơ** nếu
không canh. Model có thể học ra những bài đúng luật tuyệt đối mà vô hồn — và verifier sẽ
chấm chúng điểm tuyệt đối.

---

## 7. Thứ tự thi công

| # | việc | cần GPU | giá trị nếu dừng ở đây |
|---|---|---|---|
| 1 | `kiem_that_ngon_bat_cu` + niêm + đối thanh | không | verifier đủ hai thể |
| 2 | Tập thơ bát cú chuẩn + hiệu chuẩn | không | biết verifier có tin được không |
| 3 | Hạ báo nhầm vần 17 % → < 8 % | không | **cải thiện ngay cả hệ thống hiện tại** |
| 4 | `phan_thuong()` + chốt chống lách + test | không | reward dùng được |
| 5 | Sinh bộ chủ đề huấn luyện | không | — |
| 6 | GRPO trên model mở | **có** | trả lời câu hỏi của báo cáo |
| 7 | Đo nghiệm thu §6.3 | có | — |

**Bước 1-5 không cần GPU và có ích độc lập.** Bước 3 nâng thẳng hệ thống đang chạy. Đó
là lý do nên làm theo thứ tự này: mỗi bước có giá trị riêng kể cả khi bước 6 không bao
giờ chạy được.

---

## 8. Điều báo cáo nên thừa nhận

1. **Đối không tất định trọn vẹn** (§3.2). Nói nó tất định là nói quá.
2. **Verifier có sai số, và sai số đó trở thành mục tiêu tối ưu.** 17 % báo nhầm vần
   không phải chi tiết kỹ thuật — nó là giới hạn trên của cả phương pháp.
3. **RLVR nâng được tỉ lệ đúng luật, không nâng được chất thơ.** Số đo hôm nay cho thấy
   hai chiều này tách rời: gpt-5-mini hơn hẳn về sáng tạo (3,0 vs 1,4) mà thua hẳn về
   vần (2,2 vs 14,1). RLVR nhắm vào chiều thứ hai. Đó là một kết quả đáng giá — miễn là
   không tuyên bố nhầm thành chiều thứ nhất.

---

## 9. Kết quả thi công (14/09/2026)

| # | việc | trạng thái |
|---|---|---|
| 1 | `kiem_that_ngon_bat_cu` + niêm + đối thanh | ✅ `src/tho/bat_cu.py` |
| 2 | Tập thơ bát cú chuẩn + hiệu chuẩn | ✅ **0,31 %** báo nhầm |
| 3 | Hạ báo nhầm vần 17 % → < 8 % | ✅ **5,9 %** |
| 4 | `phan_thuong()` + chốt chống lách | ✅ `src/tho/phan_thuong.py` |
| 5 | Sinh bộ chủ đề huấn luyện | ✅ 352 train / 112 test, rời nhau |
| 6 | GRPO | ⏸ script xong, **cần GPU** |
| 7 | Đo nghiệm thu | ⏸ script xong, thiếu phần nối model |

### 9.1 Hai lỗi mà chính phép hiệu chuẩn bắt được

**(a) Verifier bát cú neo vần sai chỗ.** Ban đầu neo vào cuối câu 2. Trên *Thu vịnh*
(`cao · hiu · vào · nào · Đào`) bốn tiếng hiệp ở vần "ao", riêng câu 2 lệch — verifier
báo **ba câu đúng** là sai. Sửa: neo vào **vần đa số**, để chính bài quyết định vần của
nó. 3 lỗi → 1 lỗi.

**(b) Hàm thưởng cho điểm miễn phí khi khung hỏng.** Bài hai câu 7/3 tiếng ăn
**0,800/1,0**. Vì mọi bộ kiểm đều *bỏ qua* vần/thanh trên câu sai số tiếng — đúng với
bộ **lọc**, nhưng với hàm **thưởng** thì thành: không lỗi nào được báo → tỉ lệ thoả
1,00 → điểm tuyệt đối cho thứ chưa hề được kiểm. Model sẽ học phá khung để né kiểm vần.
Sửa: sai khung thì vần/thanh/đối = 0. Thứ tự giờ đúng:

```
sạch 1,000  >  sai một vần 0,650  >  khung nhẹ 0,200  >  khung nặng 0,100
```

### 9.2 Một quyết định cũ bị lật, có dẫn chứng

Bốn nhóm vần thông lớn nhất (`ương~ang` 126 cặp, `ai~ơi` 74, `ưa~ơ` 63, `ai~ươi` 49) đã
bị một phiên trước **cố ý không mở**, với lý do *"`đường ~ vàng` không phải vần tiếng
Việt; dẫn chứng chưa giải thích được thì chưa phải bằng chứng"*.

Mở văn bản gốc ra thì lý do đó sai:

```
Hoa cười ngọc thốt đoan TRANG  /  Mây thua nước tóc, tuyết NHƯỜNG màu da
Gọi là gặp gỡ giữa ĐƯỜNG       /  Họa là người dưới suối VÀNG biết cho
```

Nó bác bỏ 126 dẫn chứng từ chính văn bản gốc mà không mở văn bản ra xem — vi phạm đúng
nguyên tắc ghi ở đầu `ops/hieu_chuan_tho.py`.

**Và một chú thích của chính đợt này cũng sai:** tôi viết *"giữ bốn cặp rời để không mở
rộng hơn mức cần"*. Kiểm lại thì `ơ~ô` đã mở sẵn ở nhóm toàn cục `{o, ô, ơ}`, nên cả
sáu cặp trong `{a, ơ, ô, ươ}` đều hiệp ở `-i` — hệt như gộp. Chú thích nói chặt hơn code
là kiểu sai nguy hiểm: người đọc sau tin nó thay vì đo lại. Đã sửa và ghim bằng test.

### 9.3 Còn thiếu gì trước khi chạy GRPO

- `rlvr/nghiem_thu.py::sinh_hang_loat` còn là `NotImplementedError` — cần nối vLLM hoặc
  transformers. Để trống **có chủ đích**: viết mù một đường sinh không chạy thử được thì
  chỉ là đoán.
- Cột **GIỮ** của §6.3 mới đo được phần tất định (chép, cụm bị bẻ). Phần người chấm
  (`evals/metrics/tho_hay.py`) chưa nối vào — mà đó mới là phần bắt được "đúng luật
  nhưng vô hồn".
