# FlashREINFORCE cho RLVR thơ — plan thi công

> Ngày lập: 16/09/2026. Trạng thái: **chưa thi công**.
>
> Yêu cầu: thay GRPO bằng **FlashREINFORCE** — ba cơ chế: One-Batch REINFORCE với
> Reward Centering, Sequence Trust Region, Sample-Mean Optimization.
>
> Tiếp nối `docs/plan-rlvr-tho.md` — thay bước 6 của plan đó.
>
> **Cách đọc:** §1 là ba việc phải xong trước, không liên quan tới FlashREINFORCE.
> §2–§4 là ba phần, mỗi phần có công thức chốt, code tham chiếu, test, và nghiệm thu.
> §5 là vòng huấn luyện ghép cả ba. §6–§9 là thứ tự, nghiệm thu chung, rủi ro.

---

## 0. Ghi chú về nguồn, và bốn chỗ tôi chốt khác mô tả

**Tôi không có "FlashREINFORCE" trong hiểu biết của mình.** Plan này thi công **cơ chế
được mô tả**, không thi công một bài báo tôi đã đọc, và không kiểm chứng được các con số
hiệu quả đi kèm. Ở mỗi chỗ mô tả để ngỏ, tôi chốt một phương án và ghi rõ **vì sao** —
nếu nguồn gốc chốt khác thì sửa theo nguồn, không theo tôi.

| # | Chỗ                        | Mô tả              | Plan này                                           | Lý do                                                          |
| - | --------------------------- | -------------------- | --------------------------------------------------- | --------------------------------------------------------------- |
| 1 | Baseline                    | `R̄ = (1/B)ΣRⱼ` | **Leave-one-out**                             | §2.2.1 — khử hệ số co`(1−1/B)`, miễn phí              |
| 2 | Baseline khi có mặt nạ   | không nói          | **Chỉ tính trên quỹ đạo được nhận** | §3.3.1                                                         |
| 3 | Chuẩn hoá ngoài          | `1/B`              | **`1/Σmᵢ`**                               | §3.3.2 —`1/B` làm LR tụt âm thầm theo tỉ lệ loại     |
| 4 | Khử phương sai độ khó | không có           | **Baseline EMA theo chủ đề** (tuỳ chọn)  | §2.4 — lấy lại thứ nhóm sibling giữ, không cần sibling |

Chỗ 4 là chỗ tôi cho là đáng nhất, và nó **không phá vỡ** nguyên tắc "không sibling
rollouts" của đề xuất.

---

# §1 — BA VIỆC PHẢI XONG TRƯỚC

Không cái nào liên quan tới FlashREINFORCE. Cả ba đang làm cho **mọi** phép đo huấn
luyện trở nên vô nghĩa, nên chúng đứng trước.

## 1.1 Prompt huấn luyện KHÔNG PHẢI prompt phục vụ

`rlvr/huan_luyen.py` mở đầu bằng ba chỗ dễ làm sai, và chỗ thứ nhất là:

> *PROMPT HUẤN LUYỆN PHẢI LÀ PROMPT PHỤC VỤ. Nếu train bằng một prompt khác lúc chạy
> thật thì model học đúng luật DƯỚI prompt đó, và con số nghiệm thu không nói gì về hệ
> thống thật. Nên tệp này gọi thẳng `tho.prompt.system_prompt` — cùng hàm mà `sinh_tho`
> dùng.*

**Gọi cùng một hàm không phải là truyền cùng tham số:**

```python
# src/tho/prompt.py:251
def system_prompt(the_tho, *, muoi_buoc: bool = False, cau_dat: bool = True)

# rlvr/huan_luyen.py:141        muoi_buoc=False, cau_dat=True    <- MẶC ĐỊNH
sys_prompt = system_prompt("luc_bat")

# src/tho/sinh.py               muoi_buoc=True,  cau_dat=False   <- CỜ THẬT
#   QUY_TRINH_10_BUOC = True         CAU_DAT = False
sys_prompt = system_prompt(the_tho, muoi_buoc=muoi_buoc, cau_dat=cau_dat)
```

**Cả hai cờ đều ngược nhau:**

| Cờ           | Train đang dùng  | Phục vụ dùng    | Số đo của cờ đó                                                                                                                                |
| ------------- | ------------------ | ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `muoi_buoc` | `False`          | **`True`** | **+3,20 ± 1,85** tất định, cùng dấu cả hai lượt — can thiệp prompt **duy nhất trong 9 lần** có kết quả lặp lại được |
| `cau_dat`   | **`True`** | `False`          | **−2,35 ± 2,18** tất định, `sáng tạo` âm cả hai lượt — đã đo và **đã tắt**                                          |

Tức đường train đang **tắt** thứ đã đo là tốt và **bật** thứ đã đo là tệ. Không lỗi,
không log, và docstring nói ngược với hành vi.

### Sửa

Một nguồn duy nhất, `rlvr/` đọc chính cờ phục vụ:

```python
# rlvr/cau_hinh_tho.py  (mới — một chỗ duy nhất nối hai đường)
"""Cờ prompt dùng CHUNG giữa đường phục vụ và đường huấn luyện.

Không gõ lại giá trị ở đây. Đọc từ `tho.sinh` để lần sau ai đổi cờ phục vụ thì đường
train đổi theo — không phải nhớ sửa hai chỗ.
"""
from tho.sinh import CAU_DAT, QUY_TRINH_10_BUOC
from tho.prompt import system_prompt as _system_prompt

def prompt_he_thong(the_tho: str) -> str:
    return _system_prompt(the_tho, muoi_buoc=QUY_TRINH_10_BUOC, cau_dat=CAU_DAT)
```

**Test ghim** (`tests/unit/test_rlvr_prompt.py`):

```python
def test_prompt_train_TRUNG_KHIT_prompt_phuc_vu():
    from rlvr.cau_hinh_tho import prompt_he_thong
    from tho.sinh import CAU_DAT, QUY_TRINH_10_BUOC
    from tho.prompt import system_prompt
    mong_doi = system_prompt("luc_bat", muoi_buoc=QUY_TRINH_10_BUOC, cau_dat=CAU_DAT)
    assert prompt_he_thong("luc_bat") == mong_doi
```

Test này đỏ nếu một ngày ai đổi mặc định của `system_prompt` — đúng cái đã xảy ra.

## 1.2 Hàm thưởng KHÔNG bóc phần nháp

Cặp đôi với §1.1, và đây là lý do hai việc phải làm **cùng lúc**.

```python
# rlvr/huan_luyen.py:99
return [thuong(c, t) for c, t in zip(completions, the_tho, strict=True)]
#              ^ completion THÔ, chưa bóc nháp
```

Ở chế độ 10 bước model in phần **nháp** (ý, hình ảnh, khai nghĩa từng chữ vần, câu đắt,
soát), rồi mốc `BÀI THƠ:`, rồi bài thơ. Đường phục vụ bóc:

```python
# src/tho/sinh.py
def _lay_tho(raw: str, muoi_buoc: bool) -> str:
    return _sach(bo_dong_nhap(tach_bai(raw))) if muoi_buoc else _sach(raw)
```

Đường huấn luyện thì không. Nên **ngay khi sửa §1.1**, mọi dòng nháp bị `kiem_luc_bat`
đếm thành một câu sai số tiếng → `nhom["khung"] > 0` → `phan_thuong` đặt vần/thanh/đối
= 0 → thưởng gần 0 cho **mọi** bản, ở **mọi** bước.

Và tín hiệu không chết hẳn — nó suy biến thành *"in ít dòng nháp đi"*. Model sẽ học đúng
điều đó: **bỏ phần nháp**, tức tự gỡ chính can thiệp đã đo được là có tác dụng.

### Sửa

Nâng `_lay_tho` thành hàm công khai, đặt ở `muoi_buoc.py` (nơi đã có `tach_bai` và
`bo_dong_nhap`), rồi cả hai đường gọi nó:

```python
# src/tho/muoi_buoc.py
def lay_tho(raw: str, muoi_buoc: bool) -> str:
    """Phần BÀI THƠ trong câu trả lời của model. Một nguồn duy nhất.

    `sinh.py` (đường phục vụ) và `rlvr/` (đường huấn luyện) PHẢI gọi cùng hàm này. Hai
    đường bóc nháp khác nhau nghĩa là hai đường chấm hai thứ khác nhau, và con số nghiệm
    thu không nói gì về hệ thống thật.
    """
    if not muoi_buoc:
        return _sach(raw)
    return _sach(bo_dong_nhap(tach_bai(raw)))
```

`sinh.py::_lay_tho` thành một dòng gọi lại; `_sach` chuyển sang `muoi_buoc.py`.

### Một hệ quả phải biết trước

`tach_bai` **trả nguyên văn khi không thấy mốc** `BÀI THƠ:` — có chủ đích, để một lỗi
định dạng không biến thành một bài thơ rỗng.

Với vai trò **thưởng** thì điều đó thành một áp lực học: model quên in mốc → cả phần nháp
bị chấm → thưởng thấp. Đó là áp lực **đúng hướng** (ta muốn nó in mốc), nhưng nó phải
được ghi ra, không phải phát hiện sau. Thêm vào telemetry: **tỉ lệ bản có mốc**
(§5.4). Tỉ lệ đó tụt là dấu hiệu model đang trôi khỏi định dạng.

### Test ghim

```python
def test_hai_duong_boc_nhap_GIONG_HET_nhau():
    raw = "Ý: mùa thu\nCHỮ VẦN: trời/nơi\nBÀI THƠ:\nHoa sen nở rực giữa trời\n..."
    from tho.muoi_buoc import lay_tho
    from tho.sinh import _lay_tho
    assert _lay_tho(raw, True) == lay_tho(raw, True)
    assert lay_tho(raw, True).startswith("Hoa sen")

def test_thuong_tren_completion_THO_va_DA_BOC_lech_nhau():
    """Ghim chính cái bug: nếu hai số này bằng nhau thì nháp không được bóc."""
    raw = "Ý: mùa thu\nBÀI THƠ:\n" + BAI_DUNG_LUAT
    assert thuong(raw) < thuong(lay_tho(raw, True))
```

## 1.3 `GRPOTrainer` không biểu diễn được cả ba cơ chế

| Cơ chế | Thứ nó thay trong`GRPOTrainer`                            |
| -------- | ------------------------------------------------------------- |
| 1        | Cách tính lợi thế (`R − mean(nhóm)`, chia `std`)    |
| 2        | Cách xử lý lệch policy (cắt tỉ số**cấp token**) |
| 3        | Cách chuẩn hoá loss                                        |

Đặt `num_generations = 1` thì lợi thế bằng 0 cho **mọi** bản — nhóm một phần tử có trung
bình bằng chính nó. Không gradient, **không lỗi nào được báo**.

|         | Kế thừa`GRPOTrainer`                                                                             | Vòng riêng                         |
| ------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------ |
| Sửa    | Ghi đè`_generate_and_score_completions` + `compute_loss`                                       | `rlvr/flash.py`, ~350 dòng        |
| Được | Checkpoint, logging, accelerate sẵn                                                                 | Không phụ thuộc nội bộ TRL      |
| Mất    | **Bám nội bộ TRL**; `pyproject` ghim `trl>=0.12`, nội bộ đổi nhiều giữa các bản | Tự lo grad accumulation, checkpoint |

**Chốt: vòng riêng.** Khi ba cơ chế thay gần hết phần TRL sở hữu thì kế thừa chỉ là giữ
cái vỏ, và cái vỏ đó sẽ vỡ ở lần `uv sync` sau. `peft` + `transformers` + `accelerate`
vẫn dùng — API công khai, ổn định.

**`rlvr/huan_luyen.py` GIỮ NGUYÊN, không xoá.** Nó là **đường cơ sở GRPO** để so ở §7.
Không có nó thì không biết FlashREINFORCE hơn hay kém — chỉ biết nó *chạy*.

---

# §2 — PHẦN 1: One-Batch REINFORCE với Reward Centering

## 2.1 Công thức chốt

Batch `B` quỹ đạo, mỗi quỹ đạo từ **một chủ đề khác nhau**, mỗi chủ đề đúng **một** bản.

```
S      =  Σⱼ Rⱼ                          tổng thưởng của batch
R̄₋ᵢ    =  (S − Rᵢ) / (B − 1)             baseline leave-one-out
Aᵢ     =  Rᵢ − R̄₋ᵢ  =  (B·Rᵢ − S)/(B−1)  =  B/(B−1) · (Rᵢ − R̄)
```

Một batch tươi, cập nhật **một lần**, bỏ. Không replay, không nhiều epoch trên cùng dữ
liệu.

## 2.2 Bốn chỗ để ngỏ — quyết định và dẫn giải

### 2.2.1 Leave-one-out  **[CHỐT KHÁC]**

Mô tả dùng `R̄ = (1/B)ΣRⱼ`, tức trung bình **chứa chính `Rᵢ`**.

Với các prompt **độc lập**, hệ quả của việc đó **không phải một thiên lệch hướng** — đây
là chỗ tôi phải nói chính xác hơn lần bàn trước:

```
E[ Σᵢ (Rᵢ − R̄)·∇log πᵢ ]
  = Σᵢ E[Rᵢ∇log πᵢ]  −  Σᵢ (1/B)·E[Rᵢ∇log πᵢ]  −  Σᵢ (1/B)Σ_{j≠i} E[Rⱼ]·E[∇log πᵢ]
                                                                    └── = 0
  = (1 − 1/B) · Σᵢ E[Rᵢ∇log πᵢ]
```

Tức nó là một **hệ số co đều `(1 − 1/B)`** — tương đương giảm learning rate 1,6% ở
`B = 64`. Không lệch hướng. LOO khử nó **chính xác**, chi phí bằng không:

```python
S = R.sum()
A = (B * R - S) / (B - 1)        # = B/(B-1) · (R - R.mean())
```

Cái giá: phương sai nhích `B/(B−1) = 1,016`. Đổi 1,6% phương sai lấy 1,6% biên độ — hoà,
và LOO đúng về mặt công thức nên không có lý do chọn bản kia.

**Ghi lại lý do thật:** dùng LOO vì nó *sạch*, không phải vì nó *cứu* điều gì.

### 2.2.2 KHÔNG chia độ lệch chuẩn

GRPO chia `A` cho `std` của nhóm. Ở đây **không chia**:

1. `phan_thuong()` đã nằm trong `[0, 1]` và đã chuẩn hoá theo số ràng buộc (`_dem_rang_buoc`)
   — thang đo không cần chuẩn hoá lại.
2. Chia cho `std` của một batch **nhiều chủ đề** khuếch đại bước ở đúng những batch toàn
   đề dễ (phương sai nhỏ) — bước lớn nhất rơi vào lúc tín hiệu ít thông tin nhất.
3. Dr.GRPO chỉ ra chuẩn hoá theo `std` đưa vào một thiên lệch theo độ khó.

Cờ `CHIA_STD = False`, giữ đường code, kèm ba dòng lý do.

### 2.2.3 Batch: chủ đề PHÂN BIỆT, cùng MỘT thể thơ

**Trùng chủ đề** trong một batch → baseline lẫn hai mẫu cùng đề → quay về nhóm sibling
bằng một đường vòng không ai khai báo.

**Trộn thể thơ** → `luc_bat` và `that_ngon_bat_cu` đi qua hai bộ kiểm khác nhau, hai thang
độ khó khác nhau; lấy trung bình chéo là trộn đúng thứ mà việc căn chỉnh sinh ra để khử.

Hiện chưa cắn: `chu_de_train.jsonl` **352/352 là `luc_bat`**, test 112/112 cũng vậy. Nhưng
`ham_thuong` đã nhận `the_tho` theo từng dòng và `bat_cu.py` đã có verifier — nên **ghim
bằng assert ngay bây giờ**, lúc nó còn đúng một cách tình cờ.

### 2.2.4 Kích thước batch `B`

`Var(R̄)` giảm theo `1/B`, nhưng phần **không** giảm được là `σ²_b` (phương sai giữa các
chủ đề). Tăng `B` làm baseline **chính xác hơn**, không làm lợi thế **ít nhiễu hơn**.

`B = 64` là điểm khởi đầu, chưa hiệu chuẩn cho tới §2.5. Ràng buộc bộ nhớ:
`B × (len(prompt) + max_completion_length)` token phải vừa một lần forward — nếu không thì
**chia micro-batch, nhưng baseline vẫn tính trên cả `B`** (§5.3, đây là một cái bẫy thật).

## 2.3 Vì sao baseline theo batch là chỗ đáng lo — bằng số của chính dự án

`Aᵢ` mang theo *"đề này dễ hay khó"* lẫn vào *"bản này tốt hay tệ"*. Dự án đã đo phương
sai giữa chủ đề, ở một chỗ khác, cho một mục đích khác, và **nó lớn**:

```
vần   8,40   (người con gái VN xưa)
     11,12   (uống nước nhớ nguồn)
     13,33   (mùa thu Hà Nội)
```

Chênh **4,9 điểm chỉ vì đổi chủ đề** — lớn hơn *mọi* cải thiện đo được trong hai ngày
(`plan-danh-gia-tong-the.md` §1).

Và dự án đã **trả giá một lần** cho đúng nhầm lẫn này: docstring `SO_BAN` trong
`sinh.py` — dự báo best-of-N cho +1,7 điểm vần, đo thật ra **+0,14 ± 2,16**, vì phân bố
dùng để dự báo gộp nhiều chủ đề.

**Nhưng cũng phải nói nốt vế còn lại:** dưới một ngân sách sinh **cố định**, chế độ batch
phủ được `G` lần nhiều chủ đề hơn mỗi bước. Đó là một lợi thế thật, và nó bù một phần.
Cân bằng ròng không hiển nhiên về mặt giải tích — và đó chính là lý do §2.4 đáng làm:
**nó lấy cả hai.**

## 2.4 Baseline EMA theo chủ đề  **[NÊN LÀM]**

Nhóm sibling khử `σ²_b` bằng cách lấy nhiều mẫu **cùng một đề**. Có một cách khác, rẻ hơn
hẳn: **nhớ điểm trung bình của chính đề đó qua các lần gặp trước.**

```
Aᵢ  =  Rᵢ − b(pᵢ)        nếu đã gặp pᵢ
Aᵢ  =  Rᵢ − R̄₋ᵢ          lần đầu gặp pᵢ  (rơi về LOO)

b(pᵢ) ← (1−α)·b(pᵢ) + α·Rᵢ       CẬP NHẬT SAU KHI đã dùng
```

**Thứ tự cập nhật là bắt buộc.** Cập nhật trước rồi mới lấy `b(p)` nghĩa là baseline chứa
chính `Rᵢ` — đúng cái §2.2.1 vừa khử, và lần này với trọng số `α = 0,1` chứ không phải
`1/B = 0,016`, tức nặng hơn sáu lần.

**Vì sao đúng về lý thuyết.** Với `b` chỉ phụ thuộc **trạng thái** (prompt), không phụ
thuộc **hành động**:

```
E_{a∼π}[ ∇log π(a|s) · b(s) ]  =  b(s) · ∇ Σ_a π(a|s)  =  b(s) · ∇1  =  0
```

Gradient **không thiên lệch**, bất kể `b` ước lượng tốt hay tệ. `b(p)` lạc hậu so với
policy đang đổi chỉ làm giảm chất lượng khử phương sai — **không bao giờ làm sai hướng**.
Đó là khác biệt căn bản so với batch-mean thuần (chứa `Rᵢ`, tức phụ thuộc hành động).

|                       |                                                                                                                          |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Chi phí              | Một`float` cho mỗi chủ đề train. **352 số.** Không thêm một lần sinh nào                              |
| Ngân sách quan sát | 500 bước × B=64 = 32.000 quỹ đạo / 352 đề ≈**91 lần gặp mỗi đề**                                     |
| `α = 0,1`          | Trí nhớ hiệu dụng ≈`1/α = 10` lần gặp. Đủ ngắn để bám policy đang khá lên, đủ dài để khử nhiễu |

**Phải checkpoint cùng model.** Không lưu thì mỗi lần `resume` là mất sạch bảng và vài
chục bước đầu chạy với baseline sai — train vẫn chạy, chỉ kém đi, không ai thấy.

Cờ `BASELINE: "loo" | "batch" | "ema" = "loo"`. Bật `"ema"` sau khi có số ở §2.5.

## 2.5 Phép đo hiệu chuẩn — phân rã phương sai thưởng

Không phải cổng chặn. Nó trả lời ba câu Phần 1 cần số để chốt: **có bật EMA không**,
`B` bao nhiêu là đủ, và mỗi bước đang mang bao nhiêu nhiễu độ-khó.

### 2.5.1 Ước lượng đúng — KHÔNG dùng `Var(R̄_p)` thô

Thiết kế cân bằng: `P` chủ đề × `G` bản. Mô hình một chiều, hiệu ứng ngẫu nhiên:

```
MSB  =  G/(P−1) · Σ_p (R̄_p − R̄)²                  trung bình bình phương GIỮA nhóm
MSW  =  1/(P(G−1)) · Σ_p Σ_i (R_{p,i} − R̄_p)²      trung bình bình phương TRONG nhóm

σ̂²_w  =  MSW
σ̂²_b  =  max( 0 , (MSB − MSW) / G )
ICC   =  σ̂²_b / (σ̂²_b + σ̂²_w)
```

**`Var_p(R̄_p)` thô là ước lượng CHỆCH LÊN** của `σ²_b`, đúng bằng `σ²_w/G` — vì mỗi
`R̄_p` tự nó đã mang nhiễu lấy mẫu. Dùng nó là thổi phồng ICC, tức thiên vị về phía
"phải bật EMA". Trừ `MSW/G` là chỗ sửa.

Clamp về 0: `MSB < MSW` xảy ra thật khi `σ²_b` gần 0, và một phương sai âm là dấu hiệu
`P` quá nhỏ, không phải một phát hiện.

### 2.5.2 Cái giá của việc bỏ nhóm

Cả hai chế độ dùng LOO cho công bằng:

```
nhóm G bản, LOO trong nhóm     Var(A) = σ²_w · G/(G−1)
batch B đề,  LOO trong batch    Var(A) = (σ²_b + σ²_w) · B/(B−1)

k  =  [B/(B−1)] / [G/(G−1)]  ·  1/(1 − ICC)
```

Với `B = 64`, `G = 8`: hệ số đầu = `1,0159 / 1,1429 = 0,889`.

| ICC   | 0,10 | 0,20 | 0,30           | 0,40 | 0,50 | 0,60 |
| ----- | ---- | ---- | -------------- | ---- | ---- | ---- |
| `k` | 0,99 | 1,11 | **1,27** | 1,48 | 1,78 | 2,22 |

Đọc cho đúng: **ở `ICC ≈ 0,11` hai chế độ hoà nhau**, vì LOO trong một nhóm nhỏ (`G = 8`)
tự nó đã cộng 14% phương sai. Bảng này khiêm tốn hơn con số tôi đưa lúc bàn miệng, và nó
là bảng đúng.

### 2.5.3 Luật quyết định

| ICC          | Nghĩa                                      | Làm gì                                              |
| ------------ | ------------------------------------------- | ----------------------------------------------------- |
| ≥ 0,30      | Độ khó đề chiếm phần lớn tín hiệu | **Bật `BASELINE="ema"`**                     |
| 0,15 – 0,30 | Đáng kể, không áp đảo                | Bật EMA, đo lại sau 100 bước train thật (§2.7) |
| < 0,15       | Baseline batch là đủ                     | Giữ`"loo"`, ghi số vào docstring                 |

**Dự đoán của tôi: ICC ≥ 0,30.** Ghi ra để kiểm chứng được, kèm tiền lệ:
`plan-sua-bo-do-be-chu.md` §9.2 là một dự đoán tương tự của tôi về phương sai, và nó
**sai** — *"Lập luận nghe hợp lý và sai."*

### 2.5.4 Ba ràng buộc phương pháp

1. **Đo trên bản THÔ**, không trên đầu ra `sinh_tho`. Đường phục vụ có bốn tầng lọc và
   xếp hạng nằm **sau** việc lấy mẫu; phương sai sau khi chọn nhỏ hơn hẳn và có hình dạng
   khác. `thuong ≈ 0,77–0,80` trong `so_ket_qua.jsonl` chính là loại số đó và **không
   dùng được**. Ghim: script **không được** import `sinh_tho`.
2. **Đo hai lần**: trên `chi_tiet.tong` (đã nhân `he_so_phat` — thứ optimizer thật sự
   thấy) và trên phần thơ thuần trước khi nhân phạt. Khối điểm dồn ở 0 do `PHAT_CHEP` /
   `PHAT_TIENG_SAI` làm phồng `σ²_w`, kéo ICC **xuống**, tức thiên vị về phía "không cần
   EMA". Lệch > 0,15 giữa hai con số → kết luận phải nêu điều kiện, không nêu một con số.
3. **Hai lượt độc lập**, lệch ICC > 0,10 thì không kết luận gì. `LAP_Y` từng cho
   `+0,35 ± 0,35` ở lượt 1 rồi đảo dấu hẳn ở lượt 2.

### 2.5.5 Đặc tả `ops/do_phuong_sai_thuong.py`

```
uv run python ops/do_phuong_sai_thuong.py [--so-de 40] [--so-ban 8] [--so-luot 2]
```

Đầu vào: `evals/tho/bo_chuan.jsonl` (bộ **đóng băng**, đã tách khỏi tập train RLVR).
Sinh `so_ban` bản cho mỗi đề bằng `goi_model(prompt_he_thong(the_tho), [yeu_cau(chu_de)])`,
bóc bằng `lay_tho`, chấm bằng `phan_thuong`.

Khoảng tin cậy: **bootstrap theo CỤM** — lấy mẫu lại `P` **chủ đề** (không phải từng bản),
1.000 lần, lấy phân vị 2,5 / 97,5. Bootstrap theo từng bản sẽ phá đúng cấu trúc nhóm mà ta
đang đo.

Đầu ra — bảng cho người đọc, và một dòng JSONL nối vào `evals/tho/phuong_sai.jsonl` (cùng
nếp với `so_ket_qua.jsonl`, có `sha` để truy được lần chạy):

```
  P=40 đề · G=8 bản · lượt 1/2 · sha 4b58e2a

                        có phạt     thô
    σ²_b                 0.0142    0.0121
    σ²_w                 0.0231    0.0402
    ICC                   0.381     0.231      <- lệch 0.150, ĐÚNG NGƯỠNG cảnh báo
    KTC 95% (ICC)   [0.24, 0.52]  [0.13,0.35]
    k  (B=64,G=8)          1.44      1.16

  lượt 2 lệch 0.04  ->  KẾT LUẬN ĐƯỢC
  ICC >= 0.30 ở cột "có phạt"  ->  BẬT BASELINE="ema"
```

**Chi phí:** 40 × 8 × 2 = 640 lần gọi ≈ **$0,5**, trong `DAILY_BUDGET_USD = 3`.

**Giới hạn đã biết:** đo trên `gpt-4o-mini`, train `Qwen2.5-7B`. ICC là thuộc tính của
*độ khó đề* và *verifier* nhiều hơn của model, nên tôi cho rằng nó chuyển được về hướng —
nhưng đó là **giả định**. §2.7 đóng lỗ này miễn phí.

## 2.6 Code tham chiếu — `rlvr/loi_the.py`

```python
"""Lợi thế cho FlashREINFORCE. Thuần, không I/O, không GPU bắt buộc.

BA CHẾ ĐỘ, và mỗi cái khử một thứ khác nhau:

    "batch"  A = R − mean(batch)        co đều (1−1/B), xem plan §2.2.1
    "loo"    A = R − mean(batch ∖ i)    khử hệ số co đó. MẶC ĐỊNH
    "ema"    A = R − b(chủ đề)          khử luôn PHƯƠNG SAI GIỮA CHỦ ĐỀ. Xem plan §2.4

`m` là mặt nạ của Sequence Trust Region (§3). Baseline CHỈ tính trên quỹ đạo được nhận:
tính trên cả B trong khi gradient chỉ lấy từ phần được nhận là ước lượng baseline trên
một phân phối khác với phân phối của gradient.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import torch

CHIA_STD = False
ALPHA_EMA = 0.1


@dataclass
class BangEMA:
    """b(p) cho từng chủ đề. Một float mỗi đề — 352 số cho cả tập train."""

    alpha: float = ALPHA_EMA
    bang: dict[str, float] = field(default_factory=dict)

    def lay(self, chu_de: str) -> float | None:
        return self.bang.get(chu_de)

    def cap_nhat(self, chu_de: list[str], R: torch.Tensor, m: torch.Tensor) -> None:
        """Gọi SAU KHI đã tính lợi thế. Xem plan §2.4 về thứ tự.

        Chỉ cập nhật bằng quỹ đạo được NHẬN: quỹ đạo bị mặt nạ loại không đại diện cho
        policy hiện tại, nên nó không được phép dịch chuyển baseline.
        """
        for p, r, giu in zip(chu_de, R.tolist(), m.tolist(), strict=True):
            if not giu:
                continue
            cu = self.bang.get(p)
            self.bang[p] = r if cu is None else (1 - self.alpha) * cu + self.alpha * r

    def luu(self, duong_dan: Path) -> None:
        duong_dan.write_text(
            json.dumps({"alpha": self.alpha, "bang": self.bang}, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def nap(cls, duong_dan: Path) -> "BangEMA":
        if not duong_dan.exists():
            return cls()
        d = json.loads(duong_dan.read_text(encoding="utf-8"))
        return cls(alpha=d["alpha"], bang=d["bang"])


def kiem_batch_hop_le(chu_de: list[str], the_tho: list[str]) -> None:
    """Chủ đề PHÂN BIỆT và cùng MỘT thể thơ. Xem plan §2.2.3."""
    if len(set(chu_de)) != len(chu_de):
        trung = [c for c in set(chu_de) if chu_de.count(c) > 1]
        raise ValueError(f"batch có chủ đề trùng: {trung} — baseline sẽ lẫn hai mẫu cùng đề")
    if len(set(the_tho)) > 1:
        raise ValueError(
            f"batch trộn thể thơ: {sorted(set(the_tho))} — hai bộ kiểm, hai thang độ khó"
        )


def tinh_loi_the(
    R: torch.Tensor,             # (B,) float
    chu_de: list[str],           # (B,)
    m: torch.Tensor | None = None,   # (B,) bool. None = nhận hết
    *,
    che_do: str = "loo",
    bang: BangEMA | None = None,
    chia_std: bool = CHIA_STD,
) -> torch.Tensor:              # (B,) float, bản bị loại = 0
    R = R.float()
    w = torch.ones_like(R) if m is None else m.float()
    n = w.sum()

    if n < 1:
        return torch.zeros_like(R)

    S = (R * w).sum()

    if che_do == "batch":
        A = R - S / n
    elif che_do in ("loo", "ema"):
        # LOO trên tập ĐƯỢC NHẬN. n == 1 thì không có gì để so -> lợi thế 0.
        loo = torch.where(n > 1, (n * R - S) / (n - 1), torch.zeros_like(R))
        if che_do == "loo":
            A = loo
        else:
            if bang is None:
                raise ValueError("che_do='ema' nhưng không truyền BangEMA")
            b = torch.tensor(
                [bang.lay(p) if bang.lay(p) is not None else float("nan") for p in chu_de],
                dtype=R.dtype, device=R.device,
            )
            # Lần đầu gặp đề -> chưa có b(p) -> rơi về LOO.
            A = torch.where(torch.isnan(b), loo, R - b)
    else:
        raise ValueError(f"che_do không hợp lệ: {che_do!r}")

    A = A * w                     # bản bị loại đóng góp 0
    if chia_std:
        sd = A[w.bool()].std(unbiased=False)
        A = A / (sd + 1e-8)
    return A
```

## 2.7 Đo lại trên policy đích — miễn phí

Trong vòng train, ghi `(bước, chu_de, R, nhan)` ra `rlvr/ket_qua/thuong.jsonl`. Sau 100
bước, chạy lại **đúng** phép phân rã §2.5.1 trên dữ liệu đó — nhưng lưu ý: đó là thiết kế
**không cân bằng** (mỗi đề xuất hiện số lần khác nhau), nên dùng ước lượng hiệu ứng ngẫu
nhiên cho thiết kế lệch, hoặc đơn giản là cắt xuống số lần gặp nhỏ nhất chung.

Không tốn một lần sinh nào — những con số đó đã được tính rồi. Đây cũng là cách duy nhất
biết ICC có **trôi** khi policy khá lên hay không.

## 2.8 Test (thuần, không GPU) — `tests/unit/test_rlvr_loi_the.py`

| Test                                          | Khẳng định                                                                                 |
| --------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `test_loo_bang_cong_thuc_dong`              | `A == B/(B−1)·(R − R.mean())` với sai số `1e−6`                                     |
| `test_loo_tong_bang_khong`                  | `A.sum() ≈ 0`                                                                              |
| `test_batch_co_deu_1_tru_1_tren_B`          | `A_batch == (1−1/B)·A_loo`                                                                |
| `test_de_trung_thi_do`                      | `kiem_batch_hop_le(["a","a"], ...)` nổ `ValueError`                                      |
| `test_tron_the_tho_thi_do`                  | `["luc_bat","that_ngon_bat_cu"]` nổ `ValueError`                                         |
| `test_ema_lan_dau_roi_ve_loo`               | Bảng rỗng →`A == A_loo` chính xác                                                      |
| `test_ema_lan_hai_dung_b_cua_de`            | Sau`cap_nhat`, `A == R − b(p)`                                                           |
| `test_ema_cap_nhat_SAU_khi_dung`            | Gọi`tinh_loi_the` hai lần liên tiếp không đổi kết quả nếu chưa `cap_nhat`      |
| `test_ema_khong_cap_nhat_ban_bi_loai`       | `m=False` → `b(p)` không đổi                                                          |
| `test_ema_song_sot_qua_luu_nap`             | `nap(luu(x)).bang == x.bang`                                                                |
| `test_mat_na_lam_ban_bi_loai_dong_gop_0`    | `A[~m] == 0`                                                                                |
| `test_baseline_chi_tinh_tren_ban_duoc_nhan` | Đổi`R` của một bản **bị loại** không đổi `A` của các bản được nhận |
| `test_n_bang_1_thi_loi_the_0`               | Một bản được nhận →`A == 0`, không `NaN`                                          |
| `test_chia_std_mac_dinh_TAT`                | `CHIA_STD is False`                                                                         |

## 2.9 Nghiệm thu Phần 1

|            |                                                                                                                                                                            |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Không GPU | 14 test trên xanh;`ops/do_phuong_sai_thuong.py` chạy **hai lượt**, in `σ²_b / σ²_w / ICC / k` kèm KTC bootstrap theo cụm; hai lượt lệch ICC ≤ 0,10 |
| Có GPU    | 100 bước đầu:`mean(A) ≈ 0` (                                                                                                                                        |

---

# §3 — PHẦN 2: Sequence Trust Region

## 3.1 Công thức chốt

Với quỹ đạo `i`, token `t`, hành động **đã lấy mẫu** `a_{i,t}`:

```
p = exp( log π_θ(a_{i,t}) )        learner,  tính LẠI lúc cập nhật
q = exp( log μ  (a_{i,t}) )        behavior, ghi LÚC SINH

d_{i,t} = p·log(p/q) + (1−p)·log((1−p)/(1−q))          KL Bernoulli

D̄_i  =  (1/T_i) · Σ_t  mask_{i,t} · d_{i,t}
m_i  =  1[ D̄_i ≤ δ ]               nhận CẢ quỹ đạo, hoặc bỏ CẢ quỹ đạo
```

Chỉ cần log-xác suất của **token đã lấy mẫu** từ hai phía — không cần phân phối đầy đủ
trên toàn từ vựng. Đó là lý do cơ chế này rẻ, và là lý do vLLM cung cấp đủ dữ liệu.

**Nó đo cái gì.** Coi mỗi bước là một phép thử Bernoulli "có chọn đúng token này không".
`d_{i,t}` là KL giữa hai đồng xu đó. Nó **không** phải KL đầy đủ giữa hai phân phối trên
từ vựng — nó là một **đại diện** rẻ, và nó đủ vì thứ ta cần là một **thước đo trôi** đơn
điệu, không phải một đại lượng có ý nghĩa thông tin tuyệt đối.

**Lọc cấp chuỗi hợp với triết lý sẵn có của gói `tho`:** `_xep_hang` xếp theo
`(chép, khung, bẻ chữ, còn lại)` chứ không cộng gộp, vì **đơn vị quyết định là cả bài**.
(Tuyên bố rằng lọc cấp chuỗi ổn định hơn lọc cấp token là của đề xuất; chúng ta chưa kiểm
chứng nó, và plan này không tuyên bố thay.)

## 3.2 Hợp đồng dữ liệu — cái gì phải ghi lúc sinh

```python
@dataclass(frozen=True, slots=True)
class QuyDao:
    """Một lần sinh. TẤT CẢ các trường phải được ghi LÚC SINH, không dựng lại sau."""

    prompt_ids: list[int]
    ids: list[int]              # token của phần completion
    logp_mu: list[float]        # log-xác suất token ĐÃ LẤY MẪU, từ behavior policy
    raw: str                    # văn bản thô, TRƯỚC khi bóc nháp
    chu_de: str
    the_tho: str
    phien_ban_trong_so: int     # bộ trọng số nào đã sinh ra nó — để gỡ lỗi trôi
```

`len(ids) == len(logp_mu)` là bất biến, assert ngay lúc dựng.

`R` **không** nằm trong `QuyDao`: nó được tính sau, bằng
`thuong(lay_tho(raw, MUOI_BUOC), the_tho)`. Tách ra để một lỗi ở hàm thưởng không đòi
phải sinh lại.

## 3.3 Ba chỗ để ngỏ — quyết định

### 3.3.1 Baseline tính trên quỹ đạo ĐƯỢC NHẬN  **[CHỐT KHÁC]**

Nếu `R̄` tính trên cả `B` nhưng gradient chỉ lấy từ phần được nhận, baseline đang ước
lượng trên một phân phối khác với phân phối của gradient. Lệch bao nhiêu phụ thuộc việc
quỹ đạo bị loại có tương quan với thưởng hay không — và **không có lý do tin là không**:
quỹ đạo lệch xa policy thường là quỹ đạo lạ, và quỹ đạo lạ thường điểm thấp.

**Chốt:** LOO chỉ tính trên `{i : mᵢ = 1}`, `B_eff = Σmᵢ`. Đã cài trong `tinh_loi_the`
(§2.6) qua tham số `m`.

### 3.3.2 Chuẩn hoá theo `Σmᵢ`, không phải `1/B`  **[CHỐT KHÁC]**

Giữ `1/B` khi có mặt nạ nghĩa là: tỉ lệ loại càng cao thì bước cập nhật càng nhỏ — tức
**learning rate tự tụt theo độ trôi phân phối, im lặng**. Không ai đặt ra điều đó, không
log nào nói ra, và triệu chứng ("train chậm dần") không hề chỉ về nguyên nhân.

**Chốt:** chia `Σmᵢ`. Và **ghi `ti_le_nhan = Σmᵢ/B` mỗi bước** — con số duy nhất nói được
cơ chế này đang làm gì.

| `ti_le_nhan`                     | Nghĩa                             | Làm gì                                                                                          |
| ---------------------------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------- |
| `1,00`                           | Đồng bộ, hoặc`δ` quá rộng | Đúng ở chế độ đồng bộ (§3.5). Ở chế độ bất đồng bộ thì`δ` chưa làm gì    |
| `0,85 – 0,99`                   | Vùng vận hành                   | Không làm gì                                                                                   |
| `0,70 – 0,85`                   | Trôi nhiều                       | Theo dõi; xem lại độ trễ sinh                                                                |
| `< 0,70` (20 bước liên tiếp) | **Dừng**                    | Vứt >30% compute sinh. Giảm độ trễ hoặc nới`δ` — **không phải** cứ để chạy |

### 3.3.3 Nguồn của `log μ` — và cái bẫy phải chặn bằng test

Bộ sinh áp `temperature` / `top_p` trước khi lấy mẫu, và **tuỳ cấu hình mà log-xác suất
nó trả về là của phân phối đã xử lý hay của phân phối gốc.** Learner thì luôn tính từ
logits gốc.

Lệch một chỗ đó thì `D̄ᵢ` khác 0 **ngay cả khi hoàn toàn đồng bộ**, mặt nạ bắt đầu loại
quỹ đạo vô cớ, và không có gì báo sai. §3.5 là test chặn đúng cái đó.

**Chốt:** bộ sinh phải trả log-xác suất của **cùng phân phối mà learner tính** (logits
gốc, không temperature). Nếu backend không làm được thì `temperature` phải được ghi vào
`QuyDao` và learner phải chia logits cho nó — một trong hai, không được để ngỏ.

### 3.3.4 Số học

`p → 1` làm `log(1−p)` nổ. Tính ở **float32** kể cả khi train bf16, và dùng `log1p`:

```python
lp = logp_theta.clamp(min=LOG_EPS, max=LOG_MOT_TRU_EPS)
lq = logp_mu.clamp(min=LOG_EPS, max=LOG_MOT_TRU_EPS)
p, q = lp.exp(), lq.exp()
d = p * (lp - lq) + (1 - p) * (torch.log1p(-p) - torch.log1p(-q))
```

Một `NaN` trong `D̄` làm `mᵢ` thành `False` cho **mọi** quỹ đạo — tức tắt toàn bộ việc học
mà vẫn chạy xanh. Nên: `assert torch.isfinite(D).all()` trong vòng train, không chỉ trong
test.

## 3.4 Hiệu chuẩn `δ` — bằng đo, không bằng đoán

`δ` phụ thuộc model, độ dài, và độ trễ sinh. Không đoán được.

```
1. Chạy ở chế độ GHI NHẬN, không lọc (δ = +∞) trong ~50 bước.
2. Thu phân phối D̄ᵢ  (50 × B = 3.200 mẫu).
3. δ := phân vị 90 của phân phối đó      ->  ti_le_nhan ban đầu ≈ 0,90.
4. Từ đó CANH `ti_le_nhan`, không canh δ.
```

Giai đoạn 1–2 chạy được **ngay trong lượt GRPO nền** (§6 bước 8) — không tốn thêm một lần
sinh nào, vì `D̄ᵢ` chỉ cần hai log-xác suất đã có sẵn.

`δ` đi vào checkpoint: đổi `δ` giữa chừng mà không ghi lại là làm hai nửa của một lần chạy
không so được với nhau.

## 3.5 Bất biến phải ghim: ĐỒNG BỘ thì cơ chế này là no-op

Với sinh đồng bộ và cập nhật một-lượt, `μ = π_θ` tại thời điểm sinh, nên `d_{i,t} = 0` và
`mᵢ = 1` cho mọi `i`.

```
chế độ đồng bộ   ->   max_i D̄_i < 1e−6   VÀ   ti_le_nhan == 1,0 CHÍNH XÁC
```

**Đây là test giá trị nhất của cả Phần 2.** Nó bắt cả một lớp lỗi cùng lúc:

| Triệu chứng                           | Nguyên nhân thật                                                |
| --------------------------------------- | ------------------------------------------------------------------ |
| `D̄` khác 0 đều đặn, nhỏ       | Log-xác suất lấy từ phân phối đã áp temperature (§3.3.3) |
| `D̄` khác 0 ở vài token đầu     | Lệch vị trí do prompt bị cắt / offset sai                     |
| `D̄` khác 0 ở cuối chuỗi         | Mặt nạ padding sai, hoặc EOS bị tính/không tính lệch nhau  |
| `D̄` khác 0 rất lớn, ngẫu nhiên | Lệch tokenizer giữa bộ sinh và learner                         |

Không có test này thì Phần 2 "chạy được" mà không ai biết nó đang lọc theo cái gì.

**Nói thẳng về giá trị hiện tại:** cho tới khi `sinh_hang_loat` được nối vào vLLM và việc
sinh chạy bất đồng bộ, Phần 2 **không làm gì cả**. Nó được viết bây giờ để khi đó nó đã
đúng — không phải vì nó đang có tác dụng.

## 3.6 Thiên lệch còn lại — nói rõ, không giấu

Mặt nạ **chặn** độ lệch off-policy, nó **không sửa** độ lệch đó. Quỹ đạo được nhận vẫn
lệch tới `δ`, và gradient vẫn thiên lệch trong phạm vi ấy.

Muốn sửa thì nhân thêm tỉ số quan trọng **cấp chuỗi** `exp(ℓ̄_θ − ℓ̄_μ)`. Cờ
`DUNG_TI_SO_CHUOI = False`, **không bật mặc định**: nó thêm phương sai, và ở
`ti_le_nhan ≈ 0,9` thì độ lệch còn lại vốn đã nhỏ. Đo khi có lượt bất đồng bộ thật.

## 3.7 Code tham chiếu — `rlvr/tin_cay.py`

```python
"""Sequence Trust Region: lọc CẢ quỹ đạo theo độ trôi phân phối. Thuần, không I/O.

Đại diện KL Bernoulli tại hành động ĐÃ LẤY MẪU — chỉ cần hai log-xác suất, không cần
phân phối đầy đủ trên từ vựng.

BẤT BIẾN QUAN TRỌNG NHẤT (plan §3.5): ở chế độ ĐỒNG BỘ thì μ = π_θ, nên D̄ = 0 và mặt nạ
nhận hết. Test bất biến đó bắt được cả một lớp lỗi: log-xác suất lấy sai phân phối, lệch
tokenizer, lệch mặt nạ padding, lệch vị trí.
"""

import math

import torch

EPS = 1e-6
LOG_EPS = math.log(EPS)
LOG_MOT_TRU_EPS = math.log1p(-EPS)


def kl_bernoulli(logp_theta: torch.Tensor, logp_mu: torch.Tensor) -> torch.Tensor:
    """d_{i,t}, cùng shape với đầu vào. Tính ở float32 kể cả khi train bf16."""
    lp = logp_theta.float().clamp(min=LOG_EPS, max=LOG_MOT_TRU_EPS)
    lq = logp_mu.float().clamp(min=LOG_EPS, max=LOG_MOT_TRU_EPS)
    p = lp.exp()
    # log1p(-p) thay cho log(1-p): p sát 1 thì (1-p) mất hết chữ số có nghĩa.
    return p * (lp - lq) + (1 - p) * (torch.log1p(-p) - torch.log1p(-lq.exp()))


def mat_na_chuoi(
    logp_theta: torch.Tensor,   # (B, T)
    logp_mu: torch.Tensor,      # (B, T)
    mask_tok: torch.Tensor,     # (B, T) bool — True = token thật
    delta: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    """-> (m (B,) bool, D̄ (B,) float)."""
    d = kl_bernoulli(logp_theta, logp_mu) * mask_tok
    T = mask_tok.sum(-1).clamp(min=1)
    D = d.sum(-1) / T
    if not torch.isfinite(D).all():
        # KHÔNG nuốt: một NaN làm m toàn False, tức tắt việc học mà vẫn chạy xanh.
        raise FloatingPointError("D̄ có NaN/inf — xem plan §3.3.4")
    return D <= delta, D
```

## 3.8 Test — `tests/unit/test_rlvr_tin_cay.py`

| Test                                         | Khẳng định                                                                                              |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `test_dong_bo_thi_D_bang_0`                | `logp_theta is logp_mu` → `D̄.max() < 1e−6`, `m.all()` ← **bất biến §3.5**              |
| `test_dong_bo_ti_le_nhan_bang_1_CHINH_XAC` | `m.float().mean() == 1.0`, so sánh chính xác chứ không `approx`                                   |
| `test_mot_token_lech_manh_chuoi_dai`       | `T=200`, một token lệch → `D̄` nhỏ, `m` vẫn `True` (đúng: đây là cấp **chuỗi**) |
| `test_moi_token_lech_nhe`                  | `T=200`, mọi token lệch nhẹ → `D̄` lớn hơn ca trên                                             |
| `test_p_sat_0_va_sat_1`                    | `logp = log(1e−9)` và `log(1−1e−9)` → hữu hạn, không `NaN`                                   |
| `test_nan_thi_nem_loi`                     | `logp` chứa `nan` → `FloatingPointError`, **không** trả `m` toàn `False`              |
| `test_ti_le_nhan_giam_don_dieu_theo_delta` | `δ` giảm → `m.sum()` không tăng                                                                   |
| `test_padding_khong_tinh_vao_D`            | Đổi giá trị ở vị trí`mask=False` → `D̄` không đổi                                          |
| `test_T_bang_0_khong_chia_0`               | Một hàng`mask` toàn `False` → `D̄ = 0`, không `NaN`                                          |

## 3.9 Nghiệm thu Phần 2

|                          |                                                                                                                                     |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| Không GPU               | 9 test xanh, đặc biệt hai test bất biến đầu                                                                                  |
| Có GPU, đồng bộ      | `ti_le_nhan == 1,0` trong 50 bước liên tiếp; loss **trùng khít** với chạy không có mặt nạ (sai số `< 1e−5`) |
| Có GPU, bất đồng bộ | Sau khi chốt`δ`: `ti_le_nhan ∈ [0,85; 1,0]`; `thuong` trung bình không kém đường đồng bộ quá 0,02                |

---

# §4 — PHẦN 3: Sample-Mean Optimization

## 4.1 Công thức chốt

```
                1                 1   Tᵢ
L_pg  =  − ─────────  Σ  mᵢ·Aᵢ·───  Σ   log π_θ(a_{i,t})
              Σ mᵢ    i         Tᵢ  t=1

                1                 1   Tᵢ
L_kl  =  + β·─────────  Σ  mᵢ·  ───  Σ   k3( π_θ ‖ π_ref )_{i,t}
              Σ mᵢ     i        Tᵢ  t=1

L  =  L_pg + L_kl
k3 =  exp(Δ) − Δ − 1        với  Δ = log π_ref − log π_θ
```

Trung bình **trong** quỹ đạo trước (`1/Tᵢ`), rồi mới trung bình **giữa** các quỹ đạo
(`1/Σmᵢ`). Hệ số nhân độ dài `Tᵢ` biến mất.

**Định nghĩa `Tᵢ`:** số token **completion** thật (không prompt, không padding), **có**
tính EOS. Ghi ra vì ba cách đếm khác nhau cho ba kết quả khác nhau và không cách nào báo lỗi.

**`Aᵢ` phải `detach()`** — nó là trọng số vô hướng, không phải một đại lượng có gradient.

**KL phải dùng CÙNG cách chuẩn hoá.** `L_pg` sample-mean còn `L_kl` token-mean thì cán cân
giữa thưởng và KL **đổi theo độ dài** — quỹ đạo dài bị ghì về reference mạnh hơn quỹ đạo
ngắn, một hiệu ứng không ai đặt ra. `β = 0,04` giữ nguyên từ `huan_luyen.py`.

**Vì sao `k3`:** ước lượng KL không chệch và **luôn ≥ 0**. `k1 = −Δ` không chệch nhưng
phương sai lớn và **có thể âm** — một số hạng phạt âm nghĩa là model được thưởng vì rời
xa reference, đúng ngược ý định, và nó chỉ lộ ra khi KL đã trôi.

**Không có số hạng tỉ số/cắt:** một-lượt, on-policy ⇒ tỉ số bằng 1. Ở chế độ bất đồng bộ
thì mặt nạ §3 thay chỗ của việc cắt.

## 4.2 Lập luận ngược chiều DAPO — ghi lại, không giấu

DAPO lập luận **ngược**: chuẩn hoá theo từng chuỗi (`1/|oᵢ|`) làm *loãng* câu trả lời dài,
nên bài dài sai không bị phạt đủ → độ dài bùng nổ; và họ đề xuất token-mean toàn cục. Đề
xuất FlashREINFORCE nói ngược lại.

Cả hai đều bảo vệ được. Đây là **chuyện thực nghiệm phụ thuộc tác vụ**, không phải một
định lý — và plan này chọn sample-mean vì đang thi công FlashREINFORCE, **không phải** vì
đã chứng minh DAPO sai.

Cờ `CHUAN_HOA: "sample" | "token" = "sample"`, kèm đoạn này trong docstring. Ai đổi phải
đo, không được đổi vì đọc được một bài báo khác.

## 4.3 Vì sao ở đây nó cắn ÍT — và chỗ duy nhất nó cắn

"Long-response collapse" gần như không phải chế độ hỏng của bài toán này:

- `max_completion_length = 256`; lục bát 4 câu ≈ 45–85 token
- `_dem_rang_buoc` **đã** chuẩn hoá thưởng theo số ràng buộc, kèm `_SO_CAU_CHUAN` dùng số
  câu **chuẩn** chứ không phải số câu quan sát — chú thích tại chỗ nói rõ vì sao
- chế độ hỏng thật là **lặp/suy biến**, đã có `PHAT_LAP`, `NGUONG_LAP = 0,45`, hiệu chuẩn
  trên *Qua Đèo Ngang*

**Chỗ nó cắn thật:** sau khi sửa §1.1, completion gồm **phần nháp + bài thơ**, và độ dài
phần nháp biến động mạnh hơn bài thơ nhiều. Lúc đó `Tᵢ` mới thật sự khác nhau giữa các
quỹ đạo, và lựa chọn chuẩn hoá mới có hệ quả đo được.

Tức **Phần 3 chỉ có ý nghĩa nếu §1.1 và §1.2 được sửa** — thêm một lý do để chúng đứng trước.

## 4.4 Dây bẫy độ dài

Ghi mỗi 10 bước, **tách riêng hai phần** (bóc bằng `lay_tho`):

```
do_dai_tong_tb   do_dai_tong_p95   do_dai_nhap_tb   do_dai_tho_tb   ti_le_co_moc
```

**Dừng và xem lại khi:**

- `do_dai_tong_p95` đổi quá **25%** so với bước 0 theo bất kỳ chiều nào; hoặc
- `do_dai_tho_tb` và `do_dai_nhap_tb` **đi ngược chiều nhau** — model đang dịch chuyển
  ngân sách giữa hai phần, đúng hành vi §1.2 cảnh báo; hoặc
- `ti_le_co_moc` tụt dưới 0,95 — model đang trôi khỏi định dạng, và `tach_bai` sẽ bắt đầu
  trả nguyên văn (§1.2).

## 4.5 Code tham chiếu — `rlvr/loss.py`

```python
"""Loss của FlashREINFORCE. Thuần, không I/O.

SAMPLE-MEAN: trung bình TRONG quỹ đạo trước (1/Tᵢ), rồi mới trung bình GIỮA các quỹ đạo
(1/Σmᵢ). Hệ số nhân độ dài Tᵢ biến mất.

Chuẩn hoá ngoài là 1/Σmᵢ chứ KHÔNG phải 1/B (plan §3.3.2): giữ 1/B khi có mặt nạ nghĩa là
learning rate tự tụt theo tỉ lệ loại, im lặng.
"""

import torch

CHUAN_HOA = "sample"
BETA_KL = 0.04
MAX_DELTA = 20.0     # chặn tràn exp() trong k3


def _k3(logp_theta: torch.Tensor, logp_ref: torch.Tensor) -> torch.Tensor:
    """Ước lượng KL không chệch và LUÔN >= 0.

    k1 = -Δ không chệch nhưng CÓ THỂ ÂM — một số hạng phạt âm nghĩa là model được thưởng
    vì rời xa reference, đúng ngược ý định, và nó chỉ lộ ra khi KL đã trôi.
    """
    delta = (logp_ref - logp_theta).clamp(max=MAX_DELTA)
    return delta.exp() - delta - 1.0


def loss_flash(
    logp_theta: torch.Tensor,   # (B, T)  CÓ grad
    logp_ref: torch.Tensor,     # (B, T)  không grad
    A: torch.Tensor,            # (B,)    đã detach
    m: torch.Tensor,            # (B,)    bool
    mask_tok: torch.Tensor,     # (B, T)  bool
    *,
    beta: float = BETA_KL,
    chuan_hoa: str = CHUAN_HOA,
) -> tuple[torch.Tensor, dict[str, float]]:
    w = m.float()
    mask = mask_tok.float()
    A = A.detach()

    if chuan_hoa == "sample":
        T = mask.sum(-1).clamp(min=1.0)                     # (B,)
        lp_seq = (logp_theta * mask).sum(-1) / T            # (B,)
        kl_seq = (_k3(logp_theta, logp_ref) * mask).sum(-1) / T
        n_eff = w.sum().clamp(min=1.0)
        pg = -(w * A * lp_seq).sum() / n_eff
        kl = (w * kl_seq).sum() / n_eff
    elif chuan_hoa == "token":
        wm = w.unsqueeze(-1) * mask                         # (B, T)
        n_tok = wm.sum().clamp(min=1.0)
        pg = -(wm * A.unsqueeze(-1) * logp_theta).sum() / n_tok
        kl = (wm * _k3(logp_theta, logp_ref)).sum() / n_tok
    else:
        raise ValueError(f"chuan_hoa không hợp lệ: {chuan_hoa!r}")

    so = {
        "loss_pg": float(pg.detach()),
        "loss_kl": float(kl.detach()),
        "ti_le_nhan": float(w.mean()),
        "do_dai_tb": float((mask.sum(-1) * w).sum() / w.sum().clamp(min=1.0)),
    }
    return pg + beta * kl, so
```

## 4.6 Test — `tests/unit/test_rlvr_loss.py`

| Test                                         | Khẳng định                                                                                                       |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `test_sample_mean_KHONG_phu_thuoc_do_dai`  | Hai quỹ đạo cùng`A`, `T` và `3T`, cùng `logp` mỗi token → đóng góp gradient **bằng nhau** |
| `test_token_mean_phu_thuoc_do_dai_3_lan`   | Cùng dữ liệu,`chuan_hoa="token"` → lệch đúng **3 lần**                                              |
| `test_m_toan_0_thi_loss_bang_0`            | Không`NaN`, không chia 0                                                                                        |
| `test_beta_0_thi_chi_con_pg`               | `loss == loss_pg`                                                                                                 |
| `test_kl_dung_cung_chuan_hoa_voi_pg`       | Đổi`chuan_hoa` đổi **cả hai** số hạng                                                                |
| `test_k3_luon_khong_am`                    | 1.000 cặp`logp` ngẫu nhiên → `_k3 >= 0`                                                                     |
| `test_k3_bang_0_khi_trung_khit`            | `logp_theta == logp_ref` → `k3 == 0`                                                                           |
| `test_A_bang_0_thi_gradient_bang_0`        | `A = 0` → `grad` của `logp_theta` bằng 0                                                                   |
| `test_A_da_detach`                         | Truyền`A` có `requires_grad` → không có gradient chảy ngược vào `A`                                  |
| `test_padding_khong_dong_gop`              | Đổi`logp_theta` ở vị trí `mask=False` → loss không đổi                                                 |
| `test_ban_bi_loai_khong_dong_gop`          | Đổi`logp_theta` của hàng `m=False` → loss không đổi                                                     |
| `test_chuan_hoa_theo_sigma_m_khong_phai_B` | Loại nửa batch → `                                                                                               |

Test cuối là ghim của **[CHỐT KHÁC] #3** — nó đỏ nếu ai đổi về `1/B`.

## 4.7 Nghiệm thu Phần 3

|            |                                                                                                               |
| ---------- | ------------------------------------------------------------------------------------------------------------- |
| Không GPU | 12 test xanh; đặc biệt cặp`T` vs `3T` và test `Σmᵢ`                                              |
| Có GPU    | 200 bước:`do_dai_tong_p95` trong ±25% bước 0; `do_dai_tho_tb` không giảm; `ti_le_co_moc ≥ 0,95` |

---

# §5 — Ghép cả ba: `rlvr/flash.py`

## 5.1 Thứ tự thao tác trong một bước

Thứ tự **không** đổi được, mỗi mũi tên là một ràng buộc đã nêu:

```
1. lo = sampler.next()                        B đề phân biệt, cùng thể thơ   §2.2.3
2. kiem_batch_hop_le(chu_de, the_tho)         assert, không phải cảnh báo
3. quy_dao = sinh(lo, policy)                 trả logp_mu + phien_ban_trong_so  §3.2
4. R = thuong(lay_tho(raw, MUOI_BUOC), the)   BÓC NHÁP trước khi chấm       §1.2
5. logp_theta = forward(model, quy_dao)       CÓ grad
6. logp_ref   = forward(ref,   quy_dao)       no_grad
7. m, D = mat_na_chuoi(logp_theta.detach(), logp_mu, mask, delta)          §3
8. A = tinh_loi_the(R, chu_de, m, che_do=BASELINE, bang=bang_ema)          §2
9. L, so = loss_flash(logp_theta, logp_ref, A, m, mask, beta, chuan_hoa)   §4
10. L.backward(); optimizer.step()
11. bang_ema.cap_nhat(chu_de, R, m)           SAU khi đã dùng               §2.4
12. ghi_log(so | {"D_tb": D.mean(), "buoc": buoc, "de": chu_de})
```

Ba chỗ đảo thứ tự là hỏng im lặng:

- **7 trước 8** — baseline phải biết bản nào bị loại (§3.3.1)
- **8 trước 11** — EMA cập nhật trước thì baseline chứa chính `Rᵢ` (§2.4)
- **4 sau 3, trước 8** — chấm trên bản đã bóc nháp (§1.2)

## 5.2 `logp_theta` phải tính LẠI, không dùng `logp_mu`

`logp_mu` là log-xác suất của **behavior policy** lúc sinh. `logp_theta` là của **learner
hiện tại**. Ở chế độ đồng bộ chúng bằng nhau về **giá trị**, nhưng `logp_mu` **không có
đồ thị gradient** — dùng nó thay `logp_theta` cho ra loss đúng và gradient bằng 0.

Đây là loại lỗi cho ra một lần chạy "thành công" hoàn chỉnh mà model không học gì. Ghim:
`assert logp_theta.requires_grad` ngay đầu `loss_flash` khi ở chế độ train.

## 5.3 Grad accumulation — cái bẫy về baseline

`B = 64` có thể không vừa một lần forward. Chia micro-batch thì **baseline vẫn phải tính
trên cả `B`**:

```
ĐÚNG    sinh cả B  ->  R cho cả B  ->  m, A cho cả B  ->  rồi mới lặp micro-batch backward
SAI     lặp micro-batch, mỗi cái tự tính baseline của mình
```

Cách sai biến `B = 64` thành `B = 8` về mặt thống kê, và vì `A` vẫn tổng bằng 0 trong từng
micro-batch nên **không có gì trông bất thường**.

Hệ quả bộ nhớ: phải giữ `logp_theta` của cả `B`, hoặc forward hai lần (một lần no_grad để
lấy `m`, một lần có grad theo micro-batch). Chọn cách hai nếu chật — ghi rõ trong code là
đang đổi thời gian lấy bộ nhớ.

## 5.4 Telemetry — một dòng JSONL mỗi bước

Ghi ra `rlvr/ket_qua/buoc.jsonl`:

```json
{"buoc": 137, "R_tb": 0.781, "R_p10": 0.42, "A_tb": 0.0004, "A_std": 0.119,
 "ti_le_nhan": 0.94, "D_tb": 0.0031, "D_p95": 0.0089, "delta": 0.011,
 "loss_pg": -0.0421, "loss_kl": 0.0067, "do_dai_tong_p95": 214,
 "do_dai_nhap_tb": 131, "do_dai_tho_tb": 68, "ti_le_co_moc": 0.98,
 "chep": 0, "tieng_sai": 0, "cum_be": 2, "de": ["bến sông", "..."]}
```

Sáu con số đầu tiên là thứ nói được cơ chế nào đang làm gì; bốn con số cuối là cột GIỮ
(§7) đo được **trong lúc train**, không phải chờ tới nghiệm thu.

## 5.5 Checkpoint — cái gì phải lưu

| Thứ                                    | Vì sao                                                                              |
| --------------------------------------- | ------------------------------------------------------------------------------------ |
| Adapter LoRA + optimizer                | Hiển nhiên                                                                         |
| `bang_ema`                            | §2.4 — không lưu là mất baseline, train vẫn chạy nhưng kém đi, im lặng   |
| `delta`                               | §3.4 — đổi giữa chừng mà không ghi là hai nửa lần chạy không so được |
| `buoc`, trạng thái RNG của sampler | Resume phải tiếp đúng chỗ, không xáo lại từ đầu                           |
| `sha` của repo                       | Cùng nếp`so_ket_qua.jsonl` — truy được lần chạy                            |

## 5.6 Siêu tham số — một bảng, một chỗ

| Tên                      | Giá trị                        | Nguồn                                                              |
| ------------------------- | -------------------------------- | ------------------------------------------------------------------- |
| `B`                     | 64                               | §2.2.4, chưa hiệu chuẩn                                         |
| `BASELINE`              | `"loo"` → `"ema"` sau §2.5 | §2.4                                                               |
| `ALPHA_EMA`             | 0,1                              | §2.4                                                               |
| `CHIA_STD`              | `False`                        | §2.2.2                                                             |
| `delta`                 | đo, không đoán               | §3.4                                                               |
| `CHUAN_HOA`             | `"sample"`                     | §4.1                                                               |
| `BETA_KL`               | 0,04                             | giữ từ`huan_luyen.py`                                           |
| `learning_rate`         | 1e−6                            | giữ từ`huan_luyen.py`                                           |
| `max_completion_length` | 256                              | giữ;**kiểm lại sau §1.1** — nháp + thơ có thể vượt |
| LoRA                      | r=16, α=32, dropout=0,05        | giữ                                                                |

**`max_completion_length` là chỗ phải kiểm lại ngay sau §1.1.** Ở chế độ 10 bước,
completion = nháp + thơ, và 256 có thể cắt giữa bài — lúc đó `tach_bai` trả về một bài
cụt và thưởng thấp vì một lý do **không liên quan gì tới chất lượng thơ**. Đo độ dài thật
ở bước 1, đừng để nó thành một phát hiện ở bước 200.

---

# §6 — Thứ tự thi công

| #  | Việc                                                                                   | GPU                        | Ước lượng  | Chặn cái gì           |
| -- | --------------------------------------------------------------------------------------- | -------------------------- | -------------- | ------------------------ |
| 1  | §1.1 + §1.2 — prompt và bóc nháp, 4 test ghim                                     | không                     | nửa buổi     | **Chặn tất cả** |
| 1b | Đo độ dài completion thật ở chế độ 10 bước → chốt`max_completion_length` | không                     | 1 tiếng       | §4, §5.6               |
| 2  | `ops/do_phuong_sai_thuong.py`, chạy 2 lượt                                         | không                     | 1 buổi + $0,5 | Chốt`BASELINE`        |
| 3  | `rlvr/loi_the.py` + 14 test                                                           | không                     | 1 buổi        | —                       |
| 4  | `rlvr/loss.py` + 12 test                                                              | không                     | nửa buổi     | —                       |
| 5  | `rlvr/tin_cay.py` + 9 test                                                            | không                     | nửa buổi     | —                       |
| 6  | `rlvr/flash.py` — vòng huấn luyện, ghép 3–5                                     | không để**viết** | 2 ngày        | —                       |
| 7  | ⛔ Nối vLLM cho`sinh_hang_loat`                                                      | **có**              | —             | 8, 10                    |
| 8  | ⛔ Lượt**GRPO nền** + ghi `D̄` ở chế độ ghi nhận (§3.4)               | **có**              | —             | 9, 10                    |
| 9  | ⛔ Lượt FlashREINFORCE**đồng bộ**, so với 8                                 | **có**              | —             | —                       |
| 10 | ⛔ Bất đồng bộ, chốt`δ`, bật Phần 2 thật                                     | **có**              | —             | —                       |

**Bước 1–6 không cần GPU.** Gần như toàn bộ FlashREINFORCE viết và kiểm được trên CPU với
tensor nhỏ; chỉ lượt chạy thật mới cần phần cứng. 35 test, không cái nào cần mạng.

**Bước 9 phải sau bước 8.** Không có lượt GRPO nền thì không biết FlashREINFORCE hơn hay
kém — chỉ biết nó *chạy*. Đúng lỗi đã ghi ở `plan-nang-chat-luong-tho.md` §8.1.

---

# §7 — Nghiệm thu chung

Giữ §6.3 của `plan-rlvr-tho.md`, so trên `chu_de_test.jsonl` (112 đề, **chưa từng thấy khi
train**):

```
ĐẠT   tỉ lệ bài SẠCH LUẬT tăng có ý nghĩa so với model nền (Fisher, n >= 200)
      VÀ tăng có ý nghĩa so với lượt GRPO ở bước 8

GIỮ   ngôn ngữ / hình ảnh / ý nghĩa (người chấm) KHÔNG tụt quá 0,5
      chép bài mẫu = 0
      cụm bị bẻ không tăng
      tiếng không hợp lệ = 0
      ti_le_co_moc >= 0,95              <- mới, xem §1.2
```

**Một lượt chỉ cải thiện cột ĐẠT mà kéo tụt cột GIỮ là THẤT BẠI**, dù con số đầu bảng đẹp
đến đâu. Verifier chấm một bài đúng luật tuyệt đối mà vô hồn bằng điểm tuyệt đối — nó chỉ
biết đếm tiếng và dò vần.

Hai điều kiện riêng của plan này:

- **Cột GIỮ đang chờ một phép đo chưa có.** Nó đo bằng `evals/metrics/tho_hay.py`, và độ
  tin cậy của người chấm đó đang chờ hệ số Spearman từ 30 bài chấm tay còn thiếu
  (`evals/tho/cham_tay.jsonl`: **11/35**). Nếu ρ của `sáng tạo` < 0,3 thì cột GIỮ **không
  kết luận được gì**, và cả lượt train chỉ trả lời được nửa câu hỏi. Đây là việc có đòn
  bẩy cao nhất trong toàn bộ đường RLVR, và nó cần bạn.
- **Trần thật của cả phương pháp vẫn là verifier:** vần báo nhầm **5,9%** trên Truyện Kiều,
  và với vai trò **thưởng** thì đó là 5,9% vần ĐÚNG bị phạt, **tích luỹ** qua từng bước
  cập nhật. Không cơ chế nào trong ba cái dời con số đó.

---

# §8 — Rủi ro, và cách phát hiện sớm

| Rủi ro                                                          | Phát hiện bằng                                                                                                                                                            |
| ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sửa §1.1 mà quên §1.2 → thưởng ≈ 0 cho mọi bản        | `R_tb` ở bước 0 phải ≈ 0,77–0,80 như `so_ket_qua.jsonl`. Dưới 0,3 là **hỏng**, không phải "model còn kém"                                           |
| Model học cách**bỏ phần nháp** để né bộ kiểm     | §4.4 —`do_dai_nhap_tb` và `do_dai_tho_tb` **tách riêng**, cộng `ti_le_co_moc`                                                                              |
| `max_completion_length` cắt giữa bài sau khi bật 10 bước | Bước 1b — đo độ dài thật trước, không phát hiện ở bước 200                                                                                                   |
| ICC đo trên`gpt-4o-mini` không chuyển sang Qwen            | §2.7 — phân rã lại trên chính policy đích, miễn phí                                                                                                               |
| `logp_mu` lấy sai phân phối (temperature)                   | §3.5 — bất biến no-op ở chế độ đồng bộ                                                                                                                            |
| `ti_le_nhan` tụt âm thầm làm LR tụt theo                  | §3.3.2 — chia`Σmᵢ`, ghi `ti_le_nhan` mỗi bước, có ngưỡng dừng                                                                                                 |
| Dùng`logp_mu` thay `logp_theta` → gradient bằng 0         | §5.2 —`assert logp_theta.requires_grad`                                                                                                                                  |
| Micro-batch tự tính baseline riêng                            | §5.3 —`A` tính một lần cho cả `B`, trước vòng micro-batch                                                                                                       |
| Bảng EMA mất khi`resume`                                     | §5.5 — checkpoint, kèm test lưu/nạp                                                                                                                                     |
| Viết vòng riêng rồi sai một chi tiết TRL vốn lo hộ       | Bước 8 và 9 dùng**cùng** dữ liệu, **cùng** thưởng, **cùng** prompt — lệch bất thường thì nghi vòng riêng trước, nghi thuật toán sau |

---

# §9 — Những thứ plan này CỐ Ý không làm

- **Không xoá `rlvr/huan_luyen.py`.** Nó là đường cơ sở GRPO, và không có nó thì
  FlashREINFORCE không có gì để so.
- **Không đụng `phan_thuong()`.** Đổi thưởng và đổi optimizer cùng lúc thì hai thay đổi
  che lẫn nhau — cùng lý do `plan-sua-bo-kiem-van.md` §11 không đụng `sinh.py` khi đang
  sửa vần.
- **Không hạ 5,9% báo nhầm vần trong đợt này.** Đó là trần thật (§7), một việc riêng, và
  nó không chặn bước 1–6.
- **Không bật `DUNG_TI_SO_CHUOI`** (§3.6) trước khi có một lượt bất đồng bộ thật để đo.
- **Không bật `CHIA_STD`** (§2.2.2) và **không đổi `CHUAN_HOA`** (§4.2) mà không đo.
- **Không kế thừa `GRPOTrainer`** (§1.3).
- **Không mua GPU dựa trên plan này.** Plan trả lời một câu hỏi về thuật toán. Câu hỏi
  *thơ có đáng huấn luyện không* nằm ở §7, và nó cần 30 bài chấm tay trước.
