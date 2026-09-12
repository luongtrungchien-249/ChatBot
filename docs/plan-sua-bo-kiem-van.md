# Sửa bộ kiểm vần — plan

> Ngày lập: 11/09/2026. Trạng thái: **đã thi công xong**, kết quả ở §12.
>
> Tiếp theo `plan-nang-chat-luong-tho.md` §17.2 và §18.4, hai chỗ đều dừng lại ở cùng
> một câu hỏi: *điểm `vần` 10,8/20 có bao nhiêu là bot sai thật, bao nhiêu là thước đo
> sai?*

---

## 1. Vì sao sửa THƯỚC ĐO trước, không sửa model

Lý do **không phải** để con số đẹp hơn.

Bộ kiểm vần sai đang **chủ động phá thơ**. `tho/prompt.py::nhac_sua` lấy đúng danh sách
lỗi từ `kiem_luc_bat()` làm **mệnh lệnh** gửi cho model:

> *"Bài vừa rồi sai luật. Từng chỗ một: … Sửa đúng những chỗ đó rồi viết lại TOÀN BỘ
> bài thơ."*

Nên mỗi lỗi vần giả là một lệnh bảo model đi sửa một câu **vốn đã đúng**. Và §18.3 đo
được vòng sửa chạy ở **100% số bài** (5,0 lượt gọi/bài) — nghĩa là chuyện này xảy ra ở
mọi bài, không phải thỉnh thoảng.

Cải thiện model trong khi thước đo sai thì:

- mọi phép so sánh A/B đều nhiễu bởi 30% lỗi giả;
- vòng sửa vẫn tiếp tục phá các câu đúng;
- và ta không biết mình đang sửa cái gì.

---

## 2. Bằng chứng: đây là LỖI CODE, không phải luật vần lỏng

Bốn dòng này không cần tranh luận về luật vần lục bát:

```python
van_nhau('tiên', 'yên')  = False     # cùng MỘT vần, khác mỗi cách viết
van_nhau('khi',  'gì')   = False     # Kiều dùng
van_nhau('nhan', 'tàn,') = False     # chỉ khác một dấu phẩy
van_nhau('nhan', 'tàn')  = True      # bỏ dấu phẩy đi thì đúng
```

Đo trên 1.627 cặp vần Truyện Kiều: **bị loại 497 = 30,5%**.

Và 87% số cặp bị loại có **cùng âm cuối**, chỉ khác nguyên âm chính — tức chúng "gần
vần", không phải rác ngẫu nhiên. Đó là dấu hiệu của một bộ tách hỏng, không phải của
một corpus lệch.

---

## 3. Ba lỗi tất định (F1–F3)

Đã mô phỏng từng bước trên Truyện Kiều:

| bước | bị loại | tỉ lệ | |
|---|---|---|---|
| hiện tại | 497 | 30,5% | |
| + F1 bóc dấu câu | 481 | 29,6% | −16 |
| + F2 phụ âm `gi` bóc xong còn rỗng | 462 | 28,4% | −19 |
| + F3 hợp nhất `yê` với `iê` | 440 | 27,0% | −22 |

### F1 — dấu câu không bị bóc

```
lay_van('tàn,')  →  'an,'  →  tách thành (',', '')
```

Dấu `, . ! ? " ; :` dính vào tiếng vần làm hỏng hoàn toàn phép kiểm.

**Trên Kiều chỉ −16 vì corpus đã được làm sạch. Với thơ của bot thì nặng hơn nhiều** —
model sinh ra đầy dấu câu. Ví dụ thật từ lượt đo §18:

```
Khẽ đưa hương cốm, nồng nàn café.     ← tiếng 8, đúng mối vần bát[8]~lục[6]
```

Sửa ở `lay_van()`: `tieng.strip(",.;:!?\"'“”‘’()-–—…")` trước khi gọi `tach_tieng`.

### F2 — `gi` bóc xong còn rỗng

`_PHU_AM_DAU` có `"gi"`, đúng theo cách phân tích truyền thống. Nhưng với chính tiếng
`gì` thì bóc `gi` xong còn chuỗi rỗng, và code hiện tại **giữ nguyên cả tiếng**:

```python
return con_lai or chu     # 'gì' → 'gi' → tách thành ('g', 'i')
```

Lấy phụ âm làm nguyên âm. Sửa: khi phụ âm là `gi` mà bóc xong rỗng thì vần là `i`
(nguyên âm bị nuốt vào chính chữ `i` của `gi`). Tương tự xét `qu`.

### F3 — `yê` và `iê` là hai cách VIẾT của cùng một nguyên âm

Không phải vần thông, là chính tả: `tiên`/`yên`, `thêu`/`yêu`, `duyên`/`hiền`. Hiện
`_AM_CHINH_DOI` liệt kê cả hai và `van_nhau` coi chúng khác nhau.

Sửa: chuẩn hoá `yê → iê`, `ya → ia` ngay trong `_tach_van`. Đây là bước một mình gỡ
được 24 cặp, và không nới lỏng gì cả — chỉ hết coi một chữ là hai.

---

## 4. Mô hình vần hiện tại SAI: nhóm phải khoá theo ÂM CUỐI

`_THONG_VAN` là một danh sách nhóm **toàn cục** trên âm chính. Mô hình đó không diễn
đạt được thứ cần diễn đạt, và mở rộng nó sẽ hỏng theo kiểu im lặng.

Bằng chứng — mở nhóm `{a, i}` để cho `anh ~ inh` (48 dẫn chứng trong Kiều):

```
mành ~ tình   True      ← muốn
ta   ~ ti     True      ← KHÔNG muốn
nhà  ~ nhì    True      ← KHÔNG muốn
ba   ~ bi     True      ← KHÔNG muốn
```

`anh`/`inh` hiệp vần **vì có âm cuối `-nh`**; `ta`/`ti` thì không. Cùng một cặp nguyên
âm, hai kết quả khác nhau — nên khoá phải là **âm cuối**:

```python
_THONG_VAN: dict[str, tuple[frozenset[str], ...]]
#            ^ âm cuối     ^ các nhóm âm chính hiệp vần KHI có âm cuối đó
```

Nhóm nào đúng với mọi âm cuối thì để dưới khoá `"*"`.

**Đây cũng là lời giải cho nhóm `{a, ươ}` phi lý đã chặn §17.2.** Thống kê thô gộp mọi
âm cuối lại rồi đọc ra một cặp nguyên âm vô nghĩa. Tách theo âm cuối thì thấy ngay nó
là ba thứ khác nhau: `-ng` 69 lần, `-i` 32 lần, và chúng cần được xét riêng.

---

## 5. Bảng nhóm đề xuất, kèm dẫn chứng

Rút từ chính các cặp còn bị loại sau F1+F2, khoá theo âm cuối:

| âm cuối | nhóm | số lần | ví dụ | mở? |
|---|---|---|---|---|
| `-nh` | {a, i} | 48 | mành/tình, đành/mình | **CÓ** |
| `-i` | {ơ, ươ} | 47 | nơi/người, trời/người | **CÓ** |
| `-ng` | {u, ô} | 14 | chung/hồng, đồng/tùng | **CÓ** |
| `-n` | {iê, ê} | 11 | thiên/trên, lên/tiền | **CÓ** |
| `-ng` | {o, u} | 11 | phùng/lòng, lùng/lòng | **CÓ** |
| `(trống)` | {i, ê} | 9 | thề/nghì, nề/gì | **CÓ** |
| `-n` | {e, iê} | 7 | tiền/đen, đen/miền | **CÓ** |
| `(trống)` | {i, ia} | 5 | kia/gì, đi/chia | **CÓ** |
| `-ng` | {ă, ư} | 5 | trăng/chừng, rừng/trăng | **CÓ** |
| `-ng` | **{a, ươ}** | **69** | trang/nhường, đường/vàng | **KHÔNG** |
| `-i` | {a, ơ} | 35 | vời/ngài, trời/vài | **KHÔNG** |
| `-i` | {a, ươ} | 32 | bài/mười, cài/người | **KHÔNG** |
| `(trống)` | {ơ, ưa} | 27 | thưa/cờ, chờ/đưa | **KHÔNG** |

`yê`-family (24 lần) đã được F3 xử lý, không cần nhóm.

### Vì sao bốn nhóm cuối KHÔNG mở dù nhiều dẫn chứng nhất

`_THONG_VAN` đã có sẵn luật *"đừng thêm vì nghe có vẻ hiệp vần"*. Plan này thêm vế
ngược lại: **đừng thêm chỉ vì có dẫn chứng.**

`đường ~ vàng` không phải vần tiếng Việt. Không người Việt nào đọc `trang`/`nhường`
thành một cặp vần. Có 69 dẫn chứng mà vẫn không mở, vì dẫn chứng chưa được giải thích
thì chưa phải bằng chứng — xem §7.

---

## 6. Bộ test ÂM TÍNH — bắt buộc, làm TRƯỚC khi mở bảng

Nới bảng là đánh đổi: **loại nhầm ít đi** thì **chấp nhận nhầm nhiều lên**. Hiện chỉ có
phép đo cho một chiều (`ops/hieu_chuan_tho.py` đo loại nhầm trên thơ chuẩn mực). Chiều
kia không ai canh, và nó hỏng im lặng — bộ kiểm tra nới lỏng thì vô dụng.

Nên trước khi mở nhóm nào, phải có một tập cặp **chắc chắn KHÔNG vần** và chúng phải
giữ nguyên `False`:

```
ta ~ ti      nhà ~ nhì     ba ~ bi        ← nhóm -nh không được rò ra âm cuối trống
ma ~ mơ      tà ~ tơ                      ← {a, ơ} không mở
an ~ ang     tan ~ tang                   ← âm cuối phải trùng khít
thu ~ tho    cu ~ co                      ← nhóm -ng không được rò
đường ~ vàng  trang ~ nhường              ← §7
```

Mỗi nhóm mở thêm trong §5 phải kèm **cả** một ca dương tính (từ Kiều) **và** một ca âm
tính đóng đúng cái cửa nó vừa mở.

---

## 7. Chỗ DỪNG, và vì sao dừng ở đó

Sau F1–F3 và bảng §5, ước tính còn **~17–18%** bị loại trên Kiều, phần lớn là bốn nhóm
không mở.

Tôi đã đọc nguyên cặp câu cho nhóm `{a, ươ}`. Chúng là những cặp lục bát **liên mạch,
ghép đúng**, không phải corpus lệch:

```
Khuôn trăng đầy đặn, nét ngài nở nang
Hoa cười ngọc thốt đoan trang          ← nang ~ trang  ✓ (mối vần B)
Mây thua nước tóc, tuyết nhường màu da  ← trang ~ nhường ✗ (mối vần A)
Kiều càng sắc sảo, mặn mà              ← da ~ mà  ✓
```

Mối vần B chạy đúng, mối vần A không. Còn **hai khả năng chưa phân biệt được**, và
chúng đòi hai hành động ngược nhau:

1. **Dị bản văn bản.** Bản wikisource này có `"Khúc nhà tay lựa nên chương"`, trong khi
   nhiều bản in là `"nên xoang"` — và `xoang ~ càng` thì hiệp vần. Một dị bản đủ để tạo
   ra hàng chục cặp giả.
2. **Mối vần A có ngoại lệ** mà mô tả chuẩn không nói tới.

Phân biệt được hai cái này cần **một bản in đã kiểm chứng**, không phải thêm một phép
thống kê. Nên:

> **Không đuổi xuống dưới ~17%.** Ghi con số đó lại như một giới hạn đã biết, không như
> một thất bại. Nới bảng theo dữ liệu chưa hiểu sẽ làm bộ kiểm tra im lặng chấp nhận
> thơ sai vần — hỏng theo đúng kiểu không ai phát hiện được.

---

## 8. Các bước thi công, và tiêu chí dừng của từng bước

| # | việc | chi phí | tiêu chí dừng |
|---|---|---|---|
| 1 | Bộ test âm tính (§6) | $0 | đỏ đúng chỗ cần đỏ |
| 2 | F1 bóc dấu câu | $0 | `van_nhau('nhan','tàn,')` True; Kiều ≤ 29,6% |
| 3 | F2 `gi` | $0 | `van_nhau('khi','gì')` True; Kiều ≤ 28,4% |
| 4 | F3 `yê`≡`iê` | $0 | `van_nhau('tiên','yên')` True; Kiều ≤ 27,0% |
| 5 | Đổi `_THONG_VAN` sang khoá theo âm cuối | $0 | mọi test cũ + âm tính xanh, tỉ lệ **không đổi** |
| 6 | Mở 9 nhóm §5, **từng nhóm một** | $0 | mỗi nhóm: Kiều giảm, âm tính vẫn xanh |
| 7 | Đo lại thang 100 | ~$0,02 | biết `vần` thật là bao nhiêu |

Bước 5 tách khỏi bước 6 có chủ đích: đổi cấu trúc dữ liệu mà **không** đổi hành vi thì
nếu tỉ lệ nhúc nhích, ta biết ngay là đổi cấu trúc đã làm hỏng gì đó. Gộp hai bước thì
không còn cách nào biết.

Bước 6 mở **từng nhóm một** vì cùng lý do: mở cả chín rồi thấy âm tính đỏ thì không
biết nhóm nào gây ra.

**Bước 1 làm TRƯỚC tất cả.** Viết test âm tính sau khi đã nới bảng là viết test để hợp
thức hoá cái vừa làm.

---

## 9. Ngưỡng nghiệm thu hiện tại KHÔNG đạt được — phải đổi

`ops/hieu_chuan_tho.py` chốt `< 1%` báo lỗi giả thì mới in "ĐẠT". Với vần thì ~17% là
trần thực tế (§7), nên cổng đó sẽ luôn nói "CHƯA ĐẠT" và dần thành một dòng chữ không
ai đọc — tệ hơn là không có cổng.

Đề xuất: tách ngưỡng theo **chiều đo**.

- số tiếng, số câu: giữ `< 1%` (đây là luật cứng, và §18 đã đạt 100%)
- bằng-trắc: giữ ngưỡng hiện có
- **vần: ngưỡng là "không tệ hơn lần đo trước"**, kèm con số mốc ghi thẳng trong file

Ngưỡng so-với-lần-trước không đẹp bằng một con số tuyệt đối, nhưng nó **đúng**: nó phát
hiện được hồi quy, và không nói dối về một mục tiêu không với tới.

---

## 10. Sau khi thước đo đúng thì mới trả lời được hai câu

**a. Điểm `vần` thật là bao nhiêu?** Hiện 10,8/20. Không biết bao nhiêu trong đó là lỗi
giả. Bước 7 trả lời.

**b. Có nên bỏ vòng sửa khi chỉ còn lỗi vần không?** (§18.4) Nó cộng ~1,3s vào **mọi**
bài, đúng lúc tính năng này đặt mục tiêu giảm độ trễ. §16 đo được rằng sửa gần như
không ăn với lỗi vần — nhưng phép đo đó chạy khi bộ kiểm tra đang báo sai 30%, tức nó
đo một vòng sửa đang nhận mệnh lệnh rác. **Phải đo lại sau bước 7, không dùng lại kết
luận cũ.**

---

## 11. Những thứ plan này CỐ Ý không làm

- **Không mở bốn nhóm nhiều dẫn chứng nhất** (§7). Chưa giải thích được thì chưa mở.
- **Không đi tìm bản Kiều khác.** Việc đó đáng làm, nhưng nó là một việc riêng và không
  chặn bước 1–7.
- **Không đổi gì trong `tho/sinh.py`.** Khung 6-8 vừa chốt ở §18 và đang 12/12; đụng
  vào lúc đang sửa vần thì hai thay đổi che lẫn nhau.
- **Không đổi model.** Cùng lý do.


---

## 12. Kết quả thi công (11/09/2026)

Cả bảy bước cộng §9 đã làm. 677 test xanh, ruff + mypy sạch, 5 hợp đồng import còn
nguyên.

### 12.1 Tỉ lệ báo lỗi giả trên Truyện Kiều

| bước | bị loại | |
|---|---|---|
| trước khi sửa | 30,5% | |
| F1 bóc dấu câu | 29,6% | −16 cặp |
| F2 phụ âm `gi` bóc xong còn rỗng | 28,4% | −19 |
| F3 hợp nhất `yê` với `iê` | 27,0% | −22 |
| đổi bảng sang khoá theo âm cuối | 27,0% | **0 — đúng như yêu cầu** |
| mở 9 nhóm, từng nhóm một | **17,0%** | −164 |

Bước đổi cấu trúc giữ nguyên 27,0% là kết quả **muốn có**: nó chứng minh việc đổi cấu
trúc dữ liệu không lén đổi hành vi. Gộp nó vào bước mở nhóm thì không còn cách nào biết.

Cả 9 nhóm đều qua hai cửa (hạ tỉ lệ trên Kiều **và** không làm cặp âm tính nào thành
hiệp vần). Không nhóm nào phải bỏ.

### 12.2 Thước cũ đã trừ oan bao nhiêu — đo theo CẶP

Chấm **cùng một bộ 12 bài** bằng cả hai thước, nên chênh lệch chỉ có thể do thước:

```
thước CŨ   11,2/20
thước MỚI  13,3/20     +2,1
```

7/12 bài không đổi, 5/12 bài được cộng. Nghĩa là **phần lớn lỗi vần của bot là thật**,
không phải thước sai — thước cũ trừ oan khoảng 2,1 điểm trên thang 20 (~19% tương đối).

Đây là câu trả lời cho §10a, và nó khiêm tốn hơn tôi dự đoán. Đáng ghi lại đúng như vậy.

### 12.3 Vòng sửa lỗi vần: đã GỠ BỎ

§10b yêu cầu đo lại sau khi thước đúng, vì kết luận cũ (§16 của plan kia) chạy trên một
bộ kiểm đang báo sai 30% — tức nó đo một vòng sửa đang nhận **mệnh lệnh rác**.

Đo theo cặp, 10 bài, cùng một bản gốc:

```
tốt hơn      1/10
không đổi    3/10
TỆ HƠN       6/10      (một ca còn làm hỏng cả khung 6-8)
vần          8,8/20 → 7,1/20   (−1,7)
tốn thêm     p50 1.969 ms
```

Luật *"giữ bản tốt nhất"* trong `sinh_tho` đã chặn 6 ca tệ hơn, nên sản phẩm không
hỏng. Cái nó không chặn được là **độ trễ**. Lợi ích kỳ vọng thật:

```
+2,9/20 × 1/10 = +0,3/20 điểm   đổi lấy ~2 giây trên MỌI bài
```

Một tính năng đặt mục tiêu giảm độ trễ không nên trả hai giây cho ba phần mười điểm.
`SUA_LOI_VAN = False`. Lỗi **khung** thì vẫn sửa — đó là luật bắt buộc.

### 12.4 Sau tất cả

12 bài, 6 chủ đề, `gpt-4o-mini`:

| | trước hôm nay | sau |
|---|---|---|
| đúng khung 6-8 | 12/12 | **12/12** |
| lượt gọi/bài | 5,0 | **4,1** |
| độ trễ p50 (`sinh_tho`) | 2.938 ms | **1.641 ms** |
| vần (thang 20) | 10,8 | **12,4** |
| TỔNG (thang 100) | 66,2 | **67,3** |

Độ trễ giảm 44%. Điểm không giảm theo — đây là chỗ hiếm khi cả hai cùng đi đúng hướng.

### 12.5 Ngưỡng nghiệm thu, sau §9

```
so_tieng       0.0%  ngưỡng  1.0%  ĐẠT
so_cau         0.0%  ngưỡng  1.0%  ĐẠT
bang_trac      0.0%  ngưỡng  5.0%  ĐẠT
van           17.0%  mốc    17.0%  ĐẠT
```

`MOC_VAN = 0.17` nằm trong `ops/hieu_chuan_tho.py` kèm cả đường đi tới con số đó. Hạ
được thì hạ mốc theo — script tự nhắc khi thấy tốt hơn mốc quá 0,5 điểm phần trăm.

### 12.7 Bước tiếp theo

`vần` 12,4/20 vẫn còn xa, và phần lớn lỗi còn lại là **thật**. Cùng với `ngôn ngữ`
5,5/10 và `sáng tạo` 1,5/5 — hai chỉ số không nhúc nhích qua mọi can thiệp hôm nay —
chúng có plan riêng: **`docs/plan-van-ngon-ngu-sang-tao.md`**.

Plan đó đo trước rồi mới lập, và loại bỏ bốn hướng nghe rất hợp lý: model mạnh hơn, rút
ngắn bài, nhấn mạnh một mối vần, và thêm vòng sửa.

### 12.6 Chỗ dừng vẫn là chỗ dừng

245–276 cặp còn lại vẫn do bốn nhóm không mở được (§7), dẫn đầu là `{a, ươ}` với 69 dẫn
chứng. Không đụng tới. Muốn đi tiếp thì cần **một bản in Truyện Kiều đã kiểm chứng**,
không phải thêm một phép thống kê.
