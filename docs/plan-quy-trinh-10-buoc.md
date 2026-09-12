# Sản xuất thơ theo đúng trình tự 10 bước — plan

> Ngày lập: 13/09/2026. Trạng thái: **xong**. Mục tiêu A đã thi công (§8). Mục tiêu B:
> B1 và B3 đã đo và đều KHÔNG dùng (§9.1, §9.3); B2 dừng theo đúng cổng của plan (§9.2).
>
> Yêu cầu: *"Bạn sửa lại chi tiết từng phần trong dự án này của tôi để có thể sản xuất
> thơ theo đúng yêu cầu trình tự từng bước phải như trên / lập plan trước khi sửa."*
>
> Kèm theo lưu ý của chính người yêu cầu: *"đây là cách mình mô tả quy trình ở mức khái
> quát; không phải mình đang nói rằng bên trong mô hình có một chuỗi bước tuần tự, tách
> biệt."* Lưu ý đó định hình cả plan này — xem §3.

---

## 1. Kiểm kê: 10 bước đó hiện đã có bao nhiêu trong dự án

Đây là việc phải làm trước tiên, vì phần lớn quy trình **đã tồn tại** — chỉ là nó không
mang tên 10 bước ấy và không ai nhìn thấy được nó chạy.

| Bước | Có chưa | Nằm ở đâu |
|---|---|---|
| **1** Xác định yêu cầu | **có, một phần** | `tho/y_dinh.py: nhan_dien()` → `YeuCauTho(the_tho, chu_de)` |
| **2** Lập ý / mạch cảm xúc | **không có chặng riêng** | chỉ là chữ trong prompt (mục CẢM XÚC, CÂU ĐẮT) |
| **3** Chọn hình ảnh & từ khóa | **có một nửa** | `bang_van_goi_y()` gợi 53 nhóm vần; phần *hình ảnh* thì không |
| **4** Xây câu lục | có | một lượt gọi model, `SO_BAN=4` bản song song |
| **5** Xây câu bát + gieo vần | có | cùng lượt gọi đó |
| **6** Phát triển mạch nội dung | có | cùng lượt gọi đó |
| **7** Kiểm luật ①②③④ | **có đủ, tất định** | `luat.py`: `kiem_luc_bat` (số tiếng), `lay_van`+`van_nhau` (vần), `la_bang` (thanh), `kiem_nhip` (nhịp) |
| **8** Kiểm nội dung & cảm xúc | **không có** | — |
| **9** Chỉnh sửa câu chữ | **có, ba tầng** | `sinh.py` chặng 1a lọc cứng · 2 sửa khung · 2b sửa chữ bị bẻ · 3 cắt về khung đúng |
| **10** Xuất bản | có | `sinh.py: tra_loi()` |

Tức là **7/10 bước đã chạy thật**, ba bước thiếu là **2, 3 (phần hình ảnh), 8**.

Điều đáng nói hơn: bước 4, 5, 6 hiện **gộp trong đúng một lượt gọi model**. Theo sơ đồ
của bạn chúng là ba ô nối tiếp; trong code chúng là một ô.

---

## 2. Ba bước còn thiếu trùng khít với ba thí nghiệm đã đo và đã thất bại

Đây là phần tôi phải nói thẳng trước khi đề xuất bất cứ điều gì, vì đây là **lần thứ ba**
một quy trình chia chặng được yêu cầu trong dự án này, và hai lần trước đã có số đo.

| Chặng từng tách ra | Tương ứng bước | Kết quả đo | Hiện trạng |
|---|---|---|---|
| `CHON_VAN_TRUOC` — chọn chữ vần trước khi viết | bước 3 | **69,7 → 57,1** /100 | đã tắt |
| Vòng sửa lại sau khi kiểm luật | bước 9 | 1 tốt hơn / 3 như cũ / **6 tệ hơn**, tốn ~2 s | `SUA_LOI_VAN=False` |
| Người chấm xếp hạng bản | bước 8 | 3 lần thử đều hỏng; **+23 s**; 21/30 lượt timeout | `CHON_BANG_NGUOI_CHAM=False` |
| "Sổ tay" ghi ý trước khi viết | bước 2 | ngôn ngữ 4,75 → **4,78** (không phân biệt được với nhiễu) | đã gỡ |

Quy luật rút ra và đã ghi trong code: **chọn thì ăn, sửa và ràng buộc cứng thì phản tác
dụng.** Bảy can thiệp vào prompt đã thất bại, cái mạnh nhất ở n=160/nhánh.

Nên plan này **không hứa** rằng dựng đủ 10 chặng sẽ làm thơ hay hơn. Số đo đang nói
ngược lại.

---

## 3. Vậy thì sửa cái gì — tách bạch hai mục tiêu

Lưu ý của bạn ("không phải mình nói bên trong mô hình có chuỗi bước tuần tự") mở ra một
cách đọc thứ hai, và tôi cho rằng đó mới là cách đọc đúng:

> mục tiêu không phải là **ép model đi từng bước**, mà là **quy trình phải nhìn thấy
> được từng bước** — mỗi bước có tên, có đầu vào, có đầu ra, có người chịu trách nhiệm
> (code tất định hay model), và kiểm được là nó đã chạy.

Hai mục tiêu này khác nhau hoàn toàn về rủi ro:

| | Mục tiêu A — **quy trình lộ ra được** | Mục tiêu B — **thêm chặng model mới** |
|---|---|---|
| làm gì | đặt tên 10 chặng, mỗi chặng phát một vết (trace); in ra được | thêm lượt gọi cho bước 2, 3, 8 |
| rủi ro chất lượng | **không** — không đổi một byte nào gửi lên model | cao; bốn tiền lệ ở §2 |
| rủi ro độ trễ | **không** | +2 s đến +23 s mỗi bước |
| đo được ngay | có | cần A/B n≥40 × 2 lượt |

**Đề xuất: làm trọn A trước, rồi mới thử B từng bước một, mỗi bước sau một cờ tắt mặc
định.** A cho bạn đúng thứ bạn mô tả — một pipeline 10 ô nhìn thấy được — mà không đánh
đổi gì. B mới là phần có thể làm hỏng, và phải trả bằng số đo.

---

## 4. Mục tiêu A — thi công chi tiết

### 4.1 Kiểu dữ liệu vết (`src/tho/quy_trinh.py`, tệp mới)

```python
BUOC = Literal[
    "yeu_cau", "lap_y", "hinh_anh", "sinh_cau", "gieo_van",
    "noi_mach", "kiem_luat", "kiem_noi_dung", "chinh_sua", "xuat_ban",
]

@dataclass(frozen=True, slots=True)
class VetBuoc:
    buoc: BUOC
    ai_lam: Literal["luat", "model"]   # tất định hay một lượt gọi
    da_chay: bool                      # False = chặng có tên nhưng đang tắt
    ms: float
    so_lan_goi: int
    tom_tat: str                       # một dòng, đọc được bằng mắt
```

`KetQua` có thêm `vet: tuple[VetBuoc, ...]`. Trường mới, mặc định rỗng → không tệp gọi
nào phải sửa.

### 4.2 Ánh xạ chặng hiện có vào tên bước

Không dời code, chỉ **đặt tên và bọc đo giờ**:

| bước | gắn vào | ai làm |
|---|---|---|
| 1 `yeu_cau` | `y_dinh.nhan_dien` | luật |
| 2 `lap_y` | *(chưa có — vết ghi `da_chay=False`)* | — |
| 3 `hinh_anh` | `bang_van_goi_y()` trong `system_prompt` | luật |
| 4-6 `sinh_cau` / `gieo_van` / `noi_mach` | chặng 1 sinh song song | model |
| 7 `kiem_luat` | `_kiem()` — tách vết con cho ①②③④ | luật |
| 8 `kiem_noi_dung` | `cum_kha_nghi` (1a) — *một phần* của bước 8 | luật |
| 9 `chinh_sua` | chặng 2, 2b, 3 | model + luật |
| 10 `xuat_ban` | `tra_loi()` | luật |

Bước 7 xứng đáng có vết con, vì bạn nêu đủ bốn mục ①②③④ và cả bốn **đều đã có hàm
riêng** — chỉ là kết quả đang bị gộp thành một danh sách `Loi` phẳng.

### 4.3 Bước 1 làm đúng như bạn tả

Hiện `YeuCauTho` chỉ có `the_tho` + `chu_de`. Bạn tách yêu cầu thành **bốn** phần, trong
đó có *"nội dung cần truyền tải"*. Thêm một trường, suy bằng luật (bảng chủ đề → thông
điệp) chứ không gọi model, và **không nhét vào prompt** ở giai đoạn A — chỉ để lộ ra
trong vết. Nhét vào prompt là việc của B.

### 4.4 In ra cho người xem

`ops/soi_quy_trinh.py` chạy một chủ đề thật và in đầy đủ bảng vết.

> **Đã lệch khỏi plan khi thi công, có chủ đích.** Plan định dùng một cờ env
> `THO_IN_VET=1`. Không làm, vì `ops/guard_env.py` (luật L7) chỉ cho `config/` chạm
> biến môi trường, mà `config/` thì `agents/` lại không được đọc (contract 2). Bẻ hai
> luật kiến trúc để lấy một công tắc gỡ lỗi là cái giá sai. Thay vào đó vết đi vào
> **log có cấu trúc** mỗi lượt (`vet=...`, `so_buoc_chua_lam=...` trong
> `stages/tho.py`) — hợp production hơn một cờ, và `ops/soi_quy_trinh.py` lo phần đọc
> bằng mắt.

### 4.5 Test

- mỗi lượt `sinh_tho` phát ra **đủ 10 vết**, đúng thứ tự, không thiếu bước nào;
- `da_chay=False` đúng ở các bước chưa thi công (ghim sự thật, không giả vờ có);
- tổng `so_lan_goi` trong vết **bằng** `KetQua.so_lan_goi` — vết không được nói dối;
- bước 7 có đủ bốn vết con.

### 4.6 Nghiệm thu A

Độ trễ p50/p95 **không đổi quá 5 %** (đo n≥40, hai lượt độc lập), điểm tất định 45 không
đổi. A mà làm chậm đi là A đã sai — nó không được gọi model.

Hiện trạng làm mốc: p50 ≈ 1 313 ms · p95 ≈ 3 653 ms · 42,7/45 bài cao nhất · đúng khung
29/30 (chủ đề "Người con gái Việt Nam xưa", n=30).

---

## 5. Mục tiêu B — ba chặng model mới, mỗi chặng một thí nghiệm riêng

Thi công theo thứ tự tăng dần rủi ro, **dừng ngay khi một chặng không thắng**:

### B1. Bước 2 — lập ý (`LAP_Y=False`)

Một lượt gọi: chủ đề → mạch 5 ý (`Cội nguồn → Cha ông → Hy sinh → Hòa bình → Không
quên`), rồi ghép vào `yeu_cau()`.

*Khác lần trước thế nào:* lần trước là "sổ tay" tự viết trong cùng một lượt (+0,03, chìm
trong nhiễu). Lần này là **lượt riêng**, mạch ý sinh xong mới viết câu — tức đúng ý bước
2 của bạn. Đây là khác biệt thật, nên đáng đo lại một lần.

*Đo:* ngôn ngữ + ý nghĩa + cảm xúc (thang người chấm), n≥40/nhánh, 2 lượt, ghép cặp theo
chủ đề. Chi phí dự kiến +0,6-1,2 s.

### B2. Bước 3 — chọn hình ảnh (`CHON_HINH_ANH=False`)

Sinh 8-10 hình ảnh cụ thể cho chủ đề, đưa vào prompt **dưới dạng gợi ý**, không bắt buộc.

*Cảnh báo có thật:* `CHON_VAN_TRUOC` đúng hình dạng này và mất 12,6 điểm. Khác biệt: nó
ràng buộc **âm** (chữ vần), cái này gợi **nghĩa** (hình ảnh) và không bắt buộc. Ràng buộc
âm là thứ đã làm hỏng; gợi ý nghĩa thì chưa đo.

*Chỉ làm nếu B1 thắng.*

### B3. Bước 8 — kiểm mạch nội dung (`KIEM_MACH=False`)

Bắt đúng ca bạn nêu: *câu 1 nói cha, câu 3 đột nhiên nói biển*.

**Thử bằng luật trước, không bằng model**: đo độ trùng trường nghĩa giữa các cặp câu dựa
trên từ điển sẵn có. Chỉ dùng làm **tín hiệu xếp hạng** (thêm vào `_xep_hang`), tuyệt đối
không làm bộ chặn — đúng ranh giới đã ghi trong `sinh.py`: bộ chặn cần gần như không bao
giờ sai (`cum_kha_nghi`, nhầm 0,00 %), bộ chọn thì chịu được nhiễu (`cum_nghi_be`, 1,60 %).

Chỉ khi bộ dò tất định thất bại mới tính tới người chấm — và người chấm đã hỏng ba lần.

---

## 6. Việc KHÔNG làm, và vì sao

- **Không** biến bước 4/5/6 thành ba lượt gọi riêng (viết câu lục → viết câu bát → nối
  mạch). Sinh từng câu một thì model mất ngữ cảnh cả bài, và đó chính là cơ chế đã làm
  `CHON_VAN_TRUOC` hỏng. Độ trễ cũng thành ~4×.
- **Không** bật bất kỳ cờ nào của §5 theo mặc định khi chưa có hai lượt đo độc lập.
- **Không** gỡ `SO_BAN=4` sinh song song. Đây là cơ chế duy nhất **đã đo được là có tác
  dụng**; 10 chặng đẹp đến mấy cũng không đổi được điều đó.

---

## 7. Thứ tự thi công

1. ✅ `tho/quy_trinh.py` + `VetBuoc` + test rỗng
2. ✅ Bọc vết vào `sinh_tho` (không đổi logic) — chạy lại toàn bộ test
3. ✅ Tách vết con bước 7 — **làm ở `quy_trinh.py`, không ở `luat.py`** (xem ghi chú dưới)
4. ✅ `YeuCauTho` thêm trường thông điệp
5. ✅ `ops/soi_quy_trinh.py` — **không làm cờ `THO_IN_VET`** (xem §4.4)
6. ✅ **Đo nghiệm thu A** (n≥40 × 2) → §8.2
7. ✅ B1 sau cờ tắt + A/B → §9.1, **không thắng**
8. ✅ B3 → §9.3, **trượt**. ⛔ B2 → §9.2, dừng theo cổng ở bước 7

> **Lệch ở bước 3, có chủ đích.** Plan định tách bốn mục ①②③④ ngay trong `luat.py`. Làm
> vậy phải đổi chữ ký `kiem_luc_bat` — một hàm thuần, đã hiệu chuẩn trên Truyện Kiều, có
> hàng chục test ghim. Đổi nó để lấy một dòng hiển thị là trả giá quá đắt. Thay vào đó
> `vet_kiem_luat` **suy ra** bốn mục từ danh sách `Loi` đã có: cho đúng kết quả, không
> chạm vào mã đang ổn, và vết không thể lệch với cái đã dùng để chọn bài (vì cùng một
> nguồn). Lý do này cũng nằm trong docstring của `vet_kiem_luat`.

Bước 1-6 rủi ro gần như bằng không và làm được trong một lượt. Bước 7-8 mỗi cái là một
thí nghiệm riêng có thể kết luận "không dùng" — và kết luận đó cũng là kết quả hợp lệ,
sẽ được ghi lại trong code như bốn lần trước.

---

## 8. Kết quả — mục tiêu A (đã thi công 13/09/2026)

### 8.1 Đã làm

| | |
|---|---|
| `src/tho/quy_trinh.py` | `VetBuoc` / `VetCon` / `SoVet`, 10 bước có tên, `bang_vet`, `mot_dong` |
| `src/tho/sinh.py` | phát vết ở cả 10 bước; không đổi một dòng logic sinh nào |
| `src/tho/y_dinh.py` | `YeuCauTho.thong_diep` (bảng từ khóa, không gọi model) |
| `src/agents/pipeline/stages/tho.py` | log `vet=...` và `so_buoc_chua_lam=...` mỗi lượt |
| `ops/soi_quy_trinh.py` | chạy chủ đề thật, in bảng 14 dòng |
| `tests/unit/test_tho_quy_trinh.py` | 35 test |

Ba bước chưa thi công **được in ra đúng là chưa**, không tô xanh cho đủ mặt: bước 2
`da_chay=False`, mục *hình ảnh* của bước 3 và mục *mạch nội dung* của bước 8 ghi
`dat=None`.

### 8.2 Nghiệm thu độ trễ

Chi phí của **chính phần vết**, đo tất định (2 000 lượt, không mạng):

```
34 µs mỗi lượt  =  0,0025 % của p50
```

Đo đầu-cuối qua `handle_message`, chủ đề "người con gái Việt Nam xưa", n=40 × 2 lượt
độc lập:

| | trước (n=30) | lượt 1 (n=40) | lượt 2 (n=40) |
|---|---|---|---|
| p50 | 1 313 ms | 1 391 ms | 1 407 ms |
| p95 | 3 653 ms | 3 479 ms | 3 791 ms |
| tổng tất định | — | 31,96/45 | 31,75/45 |
| đúng khung 6-8 | 29/30 | **40/40** | **40/40** |
| vần | 8,40/20 | 9,41/20 | 9,26/20 |

**Đọc con số cho đúng:** p50 cao hơn mốc cũ 6-7 %, tức vượt ngưỡng 5 % ở §4.6. Nhưng
mốc cũ là n=30 từ một phiên khác, còn hai lượt mới lệch nhau đúng 1,2 % — nên 6-7 % kia
nằm trong sai khác giữa các phiên, không phải chi phí của vết. Bằng chứng độc lập là
con số 34 µs: phần vết không gọi model, không chạm mạng, và không đổi một byte nào gửi
lên model.

### 8.3 Vết phơi ra một lỗi thật ngay ngày đầu

Bước 1 vừa in chủ đề ra màn hình thì thấy:

```
1. Xác định yêu cầu   chủ đề: chủ đề uống nước nhớ nguồn
                              ^^^^^^^
```

`_DAN_CHU_DE` chỉ cắt **một** dẫn: với "… lục bát **về chủ đề** uống nước nhớ nguồn" nó
cắt "về" rồi dừng. Đề bài gửi lên model suốt nhiều ngày là *"Chủ đề: chủ đề uống nước
nhớ nguồn"*.

Đã sửa (`_DAU_THUA`, cắt lặp, có `\b` để "tảng đá" không thành "ng đá"), có 8 test ghim.

Đây đúng là thứ §3 nói: giá trị của mục tiêu A không nằm ở điểm thơ, mà ở chỗ **nhìn
thấy được**. Lỗi này không một phép chấm nào bắt được — bài thơ vẫn đúng luật.

### 8.4 Chưa làm

§5 (B1 lập ý, B2 hình ảnh, B3 mạch nội dung) — chưa động tới, đúng như plan: mỗi cái là
một thí nghiệm riêng, sau một cờ tắt mặc định, và phải trả bằng A/B n≥40 × 2 lượt.

---

## 9. Kết quả — mục tiêu B

### 9.0 Sửa lỗi trước khi làm tiếp (13/09/2026)

Ba lỗi, đều do chính bảng vết phơi ra hoặc do rà lại phần vừa viết:

| lỗi | hậu quả |
|---|---|
| `_DAN_CHU_DE` chỉ cắt một dẫn | đề bài gửi lên model là *"Chủ đề: **chủ đề** uống nước nhớ nguồn"* (§8.3) |
| vết in "Kiểm tra luật **lục bát**", "Xây câu **lục**", "đúng khung **6-8**" cho bài thất ngôn tứ tuyệt | bảng vết **nói sai sự thật** trên đường TNTT — đúng thứ làm mất toàn bộ giá trị của nó |
| một khối chú thích bị lặp trong `luat.py` | không đổi hành vi |

Lỗi thứ hai đã sửa bằng cách cho mỗi vết **mang theo tên hiển thị của nó** (`VetBuoc.ten`)
thay vì tra bảng lúc in — `bang_vet` không biết thể thơ, nên tra lúc in thì lại in sai.

### 9.1 B1 — lập ý thành một lượt gọi riêng: **ĐÃ ĐO, KHÔNG BẬT**

Thi công sau cờ `LAP_Y=False` (`src/tho/lap_y.py`). A/B **n=40 cặp ghép theo chủ đề**,
**hai lượt độc lập**, chấm bằng **cả hai thang** — 45 tất định (hình thức) và 40 người
chấm (nội dung), vì lập ý nhắm vào nội dung nên đo bằng thang 45 thôi là dùng sai dụng cụ.

| | lượt 1 | lượt 2 |
|---|---|---|
| ngôn ngữ | **+0,33 ± 0,72** | **−0,90 ± 0,90** |
| sáng tạo | +0,03 ± 0,33 | **−0,47 ± 0,33** |
| ý nghĩa | +0,35 ± 0,35 | −0,28 ± 0,32 |
| TỔNG /40 | +1,38 ± 1,81 | −2,10 ± 2,13 |
| tất định /45 | −0,56 ± 2,86 | −0,22 ± 2,31 |
| độ trễ | **+1 029 ms** | **+949 ms** |
| lượt gọi model | 4,15 → 5,25 | 4,12 → 5,15 |

**Hai lượt nói ngược nhau** trên cả ba mục quan trọng nhất — cùng cấu hình, cùng 40 chủ
đề, chỉ khác lần chạy.

Điều đáng ghi nhất không phải kết quả, mà là **cách nó suýt sai**. Lượt 1 cho ý nghĩa
+0,35 ± 0,35 — vừa đủ "có ý nghĩa thống kê" — và TỔNG +1,38. Dừng ở đó thì kết luận là
*"bật lên"*. Lượt 2 lật ngược hẳn. Chạy một lượt thì dự án này đã ship một cái tốt không
có thật, **lần thứ hai**.

**Kết luận: giữ `LAP_Y=False`.** Không có hiệu ứng đo được, mà giá thì có thật: p50
1 282 → 2 172 ms (**+70 %**) trên một tính năng có mục tiêu *giảm* độ trễ.

Một phát hiện phụ, đáng kể: **người chấm chạy 160/160 không hỏng.** Điều đó bác bỏ niềm
tin cũ trong dự án rằng thang 100 "không đo được vì người chấm hay timeout" — nó đo
được, và con số 21/30 timeout hôm trước là một sự cố nhất thời chứ không phải một giới
hạn. Mọi kết luận trước đây bị chặn vì lý do đó nên được đo lại.

### 9.2 B2 — chọn hình ảnh: **KHÔNG LÀM**

Plan đặt cổng ở §5: *"Chỉ làm nếu B1 thắng."* B1 không thắng, nên B2 dừng ở đây — đúng
kỷ luật của chính plan này, không phải vì hết thời gian.

Nhắc lại lý do cái cổng đó tồn tại: `CHON_VAN_TRUOC` cũng đúng hình dạng "sinh gợi ý
trước rồi mới viết câu" và làm mất 12,6 điểm. Hai phép đo B1 vừa cho thấy thêm rằng
ngay cả phiên bản *không ràng buộc gì* cũng không mua được gì bằng một lượt gọi thêm.

### 9.3 B3 — mạch nội dung bằng luật: **ĐÃ THỬ, TRƯỢT, KHÔNG DÙNG**

Đây là mục người dùng nêu đích danh (*"câu 1 nói cha, câu 3 đột nhiên nói biển"*).
Làm bằng luật trước, đúng như plan: bảng **trường nghĩa** 10 nhóm tự soạn, một câu bị
gọi là lạc khi nó chạm vào ít nhất một trường mà không chia trường nào với câu khác.

Hiệu chuẩn trên Truyện Kiều, 1 626 cửa sổ 4 câu — **thơ đúng chuẩn, nên mọi báo đều là
báo nhầm**:

| cách định nghĩa "lạc" | báo nhầm |
|---|---|
| v1 không chia trường với bất kỳ câu nào | 77,31 % |
| v2 thêm điều kiện ≥ 3 câu nhận ra trường | 31,30 % |
| v3 chỉ xét khi bài có **trường trội** (≥ 2 câu) | **19,50 %** |
| v4 trường trội phải phủ ≥ nửa số câu | 19,50 % |

Ngưỡng để một bộ dò được phép tham gia **xếp hạng** trong dự án này là mức của
`cum_nghi_be`: **1,60 %**. Cách tốt nhất tệ hơn **12 lần**. Và 19,50 % là **cận dưới**,
không phải ước lượng — đo trên thơ cổ điển, nơi các câu vốn chặt mạch hơn thơ bot sinh ra.

**Kết luận: không nối vào `_xep_hang`.** Vết bước 8 giữ `dat=None` cho mục *mạch nội
dung*, nhưng lời giải thích đổi từ "chưa thi công" sang nêu thẳng số đo. Code giữ lại
(`src/tho/mach_y.py`) theo đúng nếp của `chon_van.py`: để lần sau ai đó định làm lại thì
đọc được con số thay vì thử lại từ đầu.

Điều đáng ghi thêm: **thêm từ vào bảng không cứu được**. Thêm từ làm mọi câu nhận ra
nhiều trường hơn, tức bộ dò báo ít đi vì lý do sai chứ không phải vì nó chính xác hơn.
Muốn làm được thật thì cần vector nghĩa.

Có 11 test, trong đó hai test ghim đúng ràng buộc quan trọng nhất: `_xep_hang` **không
được** gọi tới module này.
