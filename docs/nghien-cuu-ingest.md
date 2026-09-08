# Nghiên cứu: kiến trúc lưu trữ, trích xuất tài liệu, và chunking

*08/09/2026 — viết sau khi đo trên chính `lakehouse/datalake/The_Open_Source_Cookbook_v0.4.pdf`.*

Ba phần dưới đây độc lập nhau về chủ đề nhưng nối nhau về quyết định: chọn kiến trúc
lưu trữ nào → trích xuất bằng gì → cắt chunk ra sao. Mọi con số có ghi "đo được" là tôi
chạy thật trên tệp trong repo; phần nào lấy từ tài liệu bên ngoài đều ghi rõ nguồn.

---

## 1. Data lake vs Data warehouse vs Lakehouse

### 1.1 Ba mô hình

| | **Data warehouse** | **Data lake** | **Lakehouse** |
|---|---|---|---|
| Áp lược đồ | Khi **ghi** (schema-on-write) | Khi **đọc** (schema-on-read) | Khi ghi, nhưng **tiến hoá được** |
| Dữ liệu | Có cấu trúc, đã làm sạch | Thô, mọi định dạng | Cả hai |
| Chi phí lưu | Cao | Thấp (object storage) | Thấp (object storage) |
| Giao dịch ACID | Có | Không | Có, qua Delta Lake / Iceberg / Hudi |
| Phục vụ ai | Nhà phân tích BI, SQL | Khoa học dữ liệu, ML | Cả hai trên **cùng một bản** dữ liệu |

### 1.2 Ưu và nhược

**Data warehouse.** Thắng ở phân tích có mô hình chặt, truy vấn SQL đoán trước được:
báo cáo tài chính, dashboard điều hành, SLA nghiêm. Đổi lại **đắt**, và đuối với dữ
liệu phi cấu trúc hoặc dòng chảy liên tục. Lược đồ áp lúc ghi nghĩa là mọi thay đổi
nguồn đều thành việc sửa đường ống.

**Data lake.** Rẻ và linh hoạt — đổ tất cả vào, tính sau. Nhược điểm nằm đúng ở chỗ
đó: không có lược đồ cưỡng chế thì chất lượng dữ liệu trôi dần, và không có tầng quản
trị mạnh bên trên thì hồ biến thành đầm lầy. Không có ACID nghĩa là hai tiến trình ghi
đồng thời có thể để lại trạng thái sai mà không ai biết.

**Lakehouse.** Ghép hai vế: lưu rẻ và linh hoạt của hồ, cộng ACID, cưỡng chế lược đồ và
tốc độ truy vấn của kho. Lược đồ **tiến hoá được** — thêm cột, đổi ràng buộc null, lan
thay đổi xuống hạ nguồn mà không phải dựng lại toàn bộ. Nhược điểm thật: đây vẫn là
công nghệ **tương đối mới**, tầng metadata (Delta/Iceberg/Hudi) là một hệ thống nữa
phải vận hành, và hệ sinh thái quanh nó chưa chín bằng kho dữ liệu vốn đã hai mươi năm
tuổi.

Về xu hướng: đến 2026 lakehouse đã thành kiến trúc chủ đạo cho các đội dữ liệu hiện
đại, với hơn 50% tổ chức triển khai theo mẫu này.

### 1.3 Áp vào dự án này

**Khuyến nghị: không dựng lakehouse. Cũng không dựng data lake.**

Hiện `lakehouse/` có **đúng một tệp PDF 829 KB**, `datawarehouse/` rỗng, và **không một
dòng code, doc hay cấu hình nào trong repo nhắc tới nó** — thư mục mồ côi, không đường
ống nào đọc.

Ba chữ đó giải quyết những bài toán mà dự án này chưa có: nhiều nguồn dữ liệu, nhiều
định dạng, nhiều người ghi đồng thời, nhu cầu truy vấn lại lịch sử. Cái đang có là
**một kho tri thức cho RAG** — và nó đã tồn tại: `kb_document` + `kb_chunk` trong
Postgres, có pgvector, có BM25, có `ingested_by`, có migration đánh số.

Nếu vẫn muốn giữ cách bố trí thư mục kiểu lakehouse như một quy ước sắp xếp tệp thì
hợp lý, nhưng nên gọi đúng tên nó:

```
lakehouse/datalake/       # vùng THÔ: tệp gốc, không sửa, không commit (đã .gitignore)
lakehouse/datawarehouse/  # vùng ĐÃ XỬ LÝ: text đã trích + manifest, để tái lập được
```

Giá trị thật của vùng thứ hai không phải là "kho dữ liệu", mà là **tái lập được**: giữ
lại văn bản đã trích cùng hash của tệp gốc, để khi đổi thư viện trích xuất hoặc đổi
cách chunk thì so được kết quả mới với cũ thay vì nạp lại mù. Đó là thứ đáng làm; còn
Delta Lake / Iceberg thì không.

---

## 2. Trích xuất tài liệu (Document Extraction)

### 2.1 Hiện trạng đo được trên tệp thật

`src/knowledge/ingest/extract.py` dùng **pypdf**. Chạy trên cookbook:

| Chỉ số | Giá trị |
|---|---|
| Số trang | 88 |
| Ký tự trích ra | 200.871 |
| Trang gần rỗng | **0 / 88** |
| Trung bình | 2.280 ký tự/trang |
| Ký tự thay thế U+FFFD | **0** |

Tức là: **không phải bản scan, không cần OCR, dấu nháy cong và gạch ngang dài đều ra
đúng.** Với một PDF dựng từ Word năm 2003 thì đây là kết quả tốt.

### 2.2 Nhưng có một lỗi nghiêm trọng, và nó không phải lỗi thư viện

Đếm được **86 chỗ** phân số biến thành chữ cái đơn lẻ:

```
"1 whole cayenne pepper OR H tsp. ground cayenne"     →  H  = ½
"G cp butter (more if you like it sweeter)"           →  G  = ¼
"5 tbsp + 1 tsp N cp"                                 →  N  = ⅓
"Dash/Pinch < J tsp"                                  →  J  = ⅛
"O cp (170 mL) cocoa"                                 →  O  = ⅔
"I cp lukewarm milk"                                  →  I  = ¾
```

Phân bố: `H` ×40, `G` ×24, `N` ×8, `I` ×7, `J` ×6, `O` ×1.

Với một quyển sách nấu ăn thì đây là hỏng ở chỗ chí mạng: bot sẽ bảo người ta cho
**"H thìa cà phê"** ớt cayenne. Một câu trả lời sai, trôi chảy, và không có dấu hiệu
nào cho thấy nó sai.

**Truy nguyên.** Tệp nhúng một font phân số riêng tên `MrsEavesFractions`. Font này
**có** bảng `ToUnicode` — nhưng bảng đó ghi:

```
4 beginbfrange
<47> <4a> <0047>     # G,H,I,J  →  U+0047, U+0048, U+0049, U+004A  ("G","H","I","J")
<4e> <4f> <004E>     # N,O      →  U+004E, U+004F                  ("N","O")
endbfrange
```

Bảng `ToUnicode` là **nguồn chân lý** mà mọi trình trích xuất phải theo. Ở đây nó khai
rằng glyph phân số ¼ chính là chữ "G". Distiller năm 2003 sinh ra một bảng đồng nhất
thay vì ánh xạ đúng.

**Kết luận: đây là khiếm khuyết của chính tệp PDF, không phải của pypdf.** PyMuPDF,
pdfplumber, Docling, LlamaParse — bất kỳ công cụ nào tôn trọng `ToUnicode` cũng trả về
"G". Công cụ nào bỏ qua `ToUnicode` mà đọc tên glyph thì gặp `/G` — cũng ra "G". Cả hai
đường đều cụt. Đổi thư viện **không** sửa được lỗi này.

Đây là lý do vì sao "chọn thư viện trích xuất tốt hơn" là câu trả lời sai cho câu hỏi
"làm sao trích cho đúng". Thư viện chỉ quyết định được phần mà tệp nói thật.

### 2.3 Bảng công cụ trích xuất

**Ghi rõ: phần này tôi KHÔNG đo được.** Môi trường chạy bị chặn mạng tới PyPI nên không
cài được PyMuPDF hay pdfplumber để so. Các nhận định dưới đây lấy từ benchmark công bố,
không phải số của tôi — cần kiểm lại trước khi dựa vào để quyết.

| Công cụ | Giấy phép | Mạnh | Yếu |
|---|---|---|---|
| **pypdf** *(đang dùng)* | BSD | Thuần Python, không phụ thuộc nhị phân, đủ tốt cho PDF text | Chậm hơn; bố cục phức tạp và bảng thì đuối |
| **PyMuPDF** (fitz) | **AGPL-3.0** | Nhanh hơn 10–50×, đứng đầu về độ chính xác text | **Giấy phép AGPL** — phải kiểm trước khi dùng cho sản phẩm đóng |
| **pdfplumber** | MIT | Tái dựng **bảng** từ toạ độ ký tự, chính xác nhất nhóm cổ điển | Chậm; thừa nếu tài liệu không có bảng |
| **pymupdf4llm** | AGPL-3.0 | Xuất thẳng **Markdown** — xem §2.4, rất hợp dự án này | Kế thừa AGPL của PyMuPDF |
| **Docling** | MIT | Phân tích bố cục bằng mô hình, mạnh với tài liệu phức tạp | Nặng, cần mô hình, chậm |
| **LlamaParse** | Dịch vụ trả phí | Tốt nhất cho tài liệu rối (báo cáo tài chính, hợp đồng) | Gửi tài liệu ra **ngoài** — không hợp tài liệu nội bộ |

Với PDF dạng text đơn giản, PyMuPDF vẫn là lựa chọn nhanh và tin cậy nhất; tài liệu
phức tạp (nhiều cột, biểu đồ, bảng lồng) thì thư viện cổ điển không còn đủ và mới cần
tới nhóm dùng mô hình.

### 2.4 Điểm đáng giá nhất: Markdown, không phải độ chính xác

Có một lý do **riêng của dự án này** khiến `pymupdf4llm` (hoặc bất cứ thứ gì xuất
Markdown) đáng cân nhắc hơn hẳn việc so từng phần trăm độ chính xác.

`_split_by_heading` trong `knowledge/ingest/chunk.py` tìm tiêu đề **Markdown** (`#`).
pypdf trả về văn bản thuần, không có ký tự nào như vậy. Đo được: **0/108 chunk có đường
dẫn tiêu đề** — cả 88 trang thành một section `path=None`, cột `section` NULL toàn bộ,
và trích dẫn chỉ nói được "trong quyển cookbook" chứ không nói được **món nào**.

Nghĩa là: trình trích xuất nào giữ được cấu trúc tiêu đề sẽ **tự động** làm sống lại
một tính năng đã viết sẵn trong chunker mà hiện đang chết. Đó là giá trị lớn hơn nhiều
so với vài phần trăm ký tự.

### 2.5 Thiết kế đề xuất cho bước trích xuất

Giữ nguyên `extract.py` là một hàm thuần `Path -> str`, thêm ba thứ:

1. **Ghi nhận hỏng, đừng nuốt.** Sau khi trích, quét các mẫu đã biết là dấu hiệu hỏng
   (chữ cái đơn lẻ đứng trước đơn vị đo, tỉ lệ U+FFFD, trang rỗng) và **log cảnh báo
   kèm số lượng**. Nạp một tài liệu hỏng âm thầm là cách chắc chắn nhất để về sau tưởng
   lỗi nằm ở embedding.
2. **Bảng sửa theo từng tài liệu, khai báo tường minh.** Với tệp này là
   `{"G": "¼", "H": "½", "I": "¾", "J": "⅛", "N": "⅓", "O": "⅔"}`. Không đoán tự động —
   chữ "H" trong văn bản thường là chữ H thật. Chỉ áp khi đứng trước đơn vị đo, và ghi
   vào manifest của tài liệu để người sau biết vì sao có bảng đó.
3. **Lưu văn bản đã trích + hash tệp gốc** vào `lakehouse/datawarehouse/`. Đây chính là
   lý do tồn tại của vùng thứ hai ở §1.3.

Còn việc đổi sang PyMuPDF/pymupdf4llm: **cần đo trước, và cần kiểm giấy phép AGPL
trước.** Đừng đổi vì bảng so sánh trên mạng.

---

## 3. Chunking

### 3.1 Năm phương pháp

**a. Fixed-size split.** Cắt theo số ký tự/token cố định. Nhanh nhất, đoán trước được,
không phụ thuộc nội dung. Nhược điểm: cắt giữa câu, giữa ý — và chunk đó khi trả về
trong kết quả tìm kiếm sẽ không tự giải thích được nó đang nói về cái gì.

**b. Overlap.** Không phải một phương pháp riêng mà là **một sửa đổi ghép được vào mọi
phương pháp**: nối phần đuôi của chunk trước vào đầu chunk sau. Lý do tồn tại: câu trả
lời hay nằm vắt qua ranh giới — câu hỏi khớp chunk sau, nhưng điều kiện của nó lại nằm
ở cuối chunk trước. Giá phải trả là **lặp dữ liệu**: overlap 100/700 token làm phình
kho khoảng 14% và làm một đoạn văn xuất hiện ở hai chunk, nên kết quả tìm kiếm có thể
trả về hai bản gần trùng nhau.

Dự án này đã có, ở `chunk.py`: `OVERLAP_TOKENS = 100` trên `TARGET_TOKENS = 700`. Và có
một chi tiết đúng, đáng giữ — chỉ nối overlap **giữa các mảnh cùng một section**:

> *Kéo đuôi của mục trước sang mục sau sẽ trộn hai chủ đề, và chunk kết quả sẽ khớp với
> cả hai câu hỏi mà trả lời đúng không câu nào.*

**c. Recursive Character Splitting.** Thử lần lượt một danh sách dấu phân tách theo thứ
tự ưu tiên — đoạn văn (`\n\n`) → dòng (`\n`) → câu (`. `) → từ (` `) → ký tự — và chỉ
tụt xuống mức thô hơn khi mức hiện tại vẫn cho ra mảnh quá dài. Kết quả là chunk tôn
trọng ranh giới tự nhiên của văn bản mà vẫn nằm trong trần kích thước.

Đây là **mặc định tốt nhất cho phần lớn hệ RAG**: benchmark cho thấy nó đạt độ chính
xác đầu-cuối cao nhất (69%), nhanh, rẻ, và chịu được tài liệu hỗn tạp.

**d. Structure-Aware.** Cắt theo cấu trúc **thật** của tài liệu: tiêu đề Markdown, thẻ
HTML, chương/mục, hoặc một mẫu lặp đặc thù của tài liệu đó. Ưu điểm lớn nhất không phải
kích thước chunk mà là **đường dẫn tiêu đề** đi kèm — thứ vừa dùng để trích dẫn đúng
chỗ, vừa nhét vào `embed_input` để chunk tự nói được nó nằm ở đâu.

Đây là điều `chunk.py` đã làm cho Markdown, và đang chết với PDF (§2.4).

**e. Semantic Break Point.** Nhúng từng câu, đo độ tương đồng giữa các câu liền kề, cắt
ở chỗ độ tương đồng **rơi mạnh** — tức chỗ chủ đề đổi. Nghe có lý nhất, và tốn nhất:
mỗi câu là một lần gọi embedding, một tài liệu 10.000 từ tốn 200–300 lần nhúng chỉ để
quyết định chỗ cắt.

**Và bằng chứng thì không ủng hộ.** Trong benchmark Vecta 02/2026 trên 50 bài báo,
recursive 512 token đứng đầu với 69%, còn semantic chỉ 54% — mảnh trung bình 43 token,
khớp tốt khi đứng riêng nhưng **quá ít ngữ cảnh để mô hình trả lời**. Kết luận đã bình
duyệt của Vectara nói thẳng: trên dữ liệu thực tế, chi phí tính toán không được bù lại
bằng cải thiện ổn định.

Sai lầm phổ biến nhất là chọn semantic vì nó *nghe có vẻ nguyên tắc hơn*.

### 3.2 Đo trên chính corpus này

Corpus có một mốc cấu trúc rất đều — **60 lần** xuất hiện mẫu tiêu đề kiểu Slashdot:

```
Kristin's Poor Man's Goulash
from the el-cheapo dept.
```

kèm khung cố định `EQUIPMENT` → `INGREDIENTS` → `INSTRUCTIONS` (67 công thức có đủ cặp
nguyên liệu–cách làm). Độ dài từng món: trung vị **1.157** ký tự, p90 **3.048**.

Tôi cài bốn phương pháp và đo bằng **hai thước đối lập nhau**:

- **Nguyên vẹn** — `INGREDIENTS` và `INSTRUCTIONS` của cùng một món có nằm chung một
  chunk không. Tách đôi nghĩa là chunk khớp câu hỏi nhưng trả lời thiếu, mà không báo
  là thiếu.
- **Tinh khiết** — chunk có lấn sang món khác không. Lấn nghĩa là trả về nguyên liệu
  của món người ta **không** hỏi.

| Phương pháp | Chunk | TB ký tự | Nguyên vẹn | Lấn ≥2 món |
|---|---:|---:|---:|---:|
| 1. Fixed-size, không overlap | 80 | 2.510 | 58/67 (86%) | 20/80 (**25%**) |
| 2. Fixed-size + overlap | 93 | 2.516 | 65/67 (97%) | 22/93 (**23%**) |
| 3. Recursive character splitting | 116 | 1.729 | 62/67 (92%) | 17/116 (14%) |
| **`chunk_document` — HIỆN TẠI** | **108** | **2.211** | **63/67 (94%)** | **19/108 (17%)** |
| 4. Structure-aware + recursive | 137 | 1.465 | 64/67 (95%) | **0/137 (0%)** |

**Đọc bảng này cho đúng — và tôi đã đọc sai một lần.**

Bản đầu của tài liệu này xếp cấu hình hiện tại vào hàng 2 (fixed-size + overlap). Sai.
`chunk_text` trong `shared/chunk_text.py` **đã là** recursive character splitting: hàm
`_find_cut` thử lần lượt đoạn văn → dòng → câu → từ → cắt cứng, đúng thứ tự fallback
của phương pháp (c). Chạy đúng `chunk_document` cho ra hàng in đậm ở trên.

Nghĩa là **recursive splitting không phải việc cần làm — nó đã có sẵn.**

Còn về hai thước: thước "nguyên vẹn" **thiên vị chunk to** — một chunk 2.500 ký tự thì
đương nhiên dễ chứa trọn một cặp, nên hàng 2 đạt 97% mà vẫn lấn 23%. So đúng phải là
hiện tại (94% / 17%) với structure-aware (95% / **0%**): đổi **không mất gì** về tính
nguyên vẹn, lấy toàn bộ phần lấn, chunk nhỏ hơn 34%. Con số 1,00 món/chunk không phải
may mắn — nó là hệ quả của việc cắt đúng ranh giới có thật trong tài liệu.

3 món structure-aware vẫn cắt đôi là 3 món dài hơn trần 2.520 ký tự (8 món vượt trần,
5 món vẫn giữ được cặp nhờ overlap). Sửa được bằng luật: **không cắt giữa `INGREDIENTS`
và `INSTRUCTIONS`**, cho phép chunk vượt trần trong trường hợp đó.

### 3.3 Vì sao không dùng Semantic Break Point ở đây

Không phải vì nó dở, mà vì với corpus này nó **thừa**: ranh giới chủ đề đã được viết
sẵn, tường minh, đều đặn 60 lần trong văn bản. Trả tiền embedding cho mỗi câu để *đoán*
lại một ranh giới đã ghi rõ là đổi tiền lấy một câu trả lời tệ hơn.

Semantic đáng cân nhắc khi tài liệu **không** có cấu trúc để bám — biên bản họp, ghi
chú thô, transcript. Cách dùng đúng là **định tuyến theo loại tài liệu**, chỉ cho loại
nào chứng minh được là có cải thiện đi qua đường ống đắt tiền đó.

*(Tôi không đo semantic trên corpus này — nó tốn tiền API thật của bạn, và với một
corpus có mốc cấu trúc rõ như vậy thì kết quả không đổi được kết luận.)*

### 3.4 Thiết kế đề xuất

Thứ tự ưu tiên trong `chunk_document`, giữ nguyên kiến trúc hiện có:

```
1. Tiêu đề Markdown (#)          — đã có, hoạt động với .md
2. Mẫu cấu trúc theo tài liệu    — THÊM: nhận diện mốc lặp, sinh `section`
3. Recursive character splitting — THÊM: thay cắt cứng ở bước cuối
4. Cắt cứng theo ký tự           — chỉ khi một đoạn đơn lẻ đã dài hơn trần
```

Bước 3 **đã có sẵn** trong `shared/chunk_text.py` — không phải làm. Còn lại hai việc:

1. **Cho chunker nhận mốc cấu trúc của tài liệu không-Markdown**, và sinh `section` từ
   đó. Đây là thứ làm sống lại cột `section` đang NULL toàn bộ, và là thay đổi kéo lấn
   từ 17% về 0%. Đây là **thay đổi duy nhất có giá trị đo được** trong cả phần chunking.
2. **Luật không cắt giữa nguyên liệu và cách làm** — hẹp, chỉ cho corpus dạng công thức.
   Làm sau cùng, nếu đo thấy 3 món kia thật sự gây lỗi trả lời.

**Chưa đụng vào `TARGET_TOKENS = 700`.** Khuyến nghị phổ biến hiện nay là 512 token, và
trung vị món ở đây là 1.157 ký tự ≈ 320 token — tức phần lớn công thức lọt gọn trong
một chunk ở cả hai mức. Đổi trần là thay đổi ảnh hưởng mọi tài liệu đã nạp và bắt nạp
lại toàn bộ; chỉ nên đổi khi có bộ eval đo được, không đổi theo bài blog.

---

## 4. Đã thực hiện (08/09/2026)

| | Việc | Trạng thái |
|---|---|---|
| 1 | **Không dựng lakehouse** — giữ `lakehouse/` như quy ước thư mục | Quyết định, không có code |
| 2 | Cảnh báo hỏng lúc trích xuất (§2.5.1) | **Xong** — `extract.py::_bao_cao_suc_khoe` |
| 3 | Mốc cấu trúc + `section` cho PDF (§3.4.1) | **Xong** — `profiles.py` + `chunk.py::_cat_muc` |
| 4 | Bảng sửa phân số (§2.5.2) | **Xong** — `profiles.py::ap_sua_ky_tu` |
| 5 | Đo PyMuPDF/pymupdf4llm | **Chưa** — chặn mạng, và còn phải kiểm giấy phép AGPL |

Kết quả đo trên `The_Open_Source_Cookbook_v0.4.pdf`:

| Chỉ số | Trước | Sau |
|---|---:|---:|
| Chunk lấn ≥2 món | 19/108 (17%) | **0/129 (0%)** |
| Chunk có `section` | 0/108 (0%) | **105/129 (81%)** |
| Công thức nguyên vẹn | 63/67 (94%) | **64/67 (95%)** |
| Phân số hỏng | 86 | **0** |

24 chunk không có `section` là phần đầu sách (lời nói đầu, chương dụng cụ, kiểm kê tủ
đồ) — nằm trước công thức đầu tiên, nên không thuộc món nào. Đúng như thiết kế.

*(Recursive splitting từng nằm trong danh sách này. Đã bỏ: đo lại cho thấy nó đã được
cài sẵn trong `shared/chunk_text.py` từ trước.)*

Mọi thay đổi ở mục 3–4 đều đổi kết quả chunk của tài liệu đã nạp, nên phải kèm **nạp
lại** — và trước khi nạp lại thì phải sửa lỗi ở §7.2, nếu không kết quả tìm kiếm sẽ trộn
hai phiên bản.

---

## 5. Vector Store: quy tắc ANN (Recall / Latency / Memory)

### 5.1 Ba núm vặn, và cái tam giác không thoát được

ANN (Approximate Nearest Neighbor) đánh đổi **độ đúng lấy tốc độ**. Chữ "Approximate"
là phần quan trọng nhất của tên gọi: index có quyền trả về kết quả **thiếu**, và nó
không báo. Với HNSW trong pgvector có đúng ba núm:

| Núm | Đặt lúc | Tăng lên thì | Trả giá bằng |
|---|---|---|---|
| `m` | **Build** | Recall ↑ (đồ thị dày hơn) | **Memory** ↑, build chậm ↑ |
| `ef_construction` | **Build** | Recall ↑ (đồ thị tốt hơn) | Build chậm ↑↑ |
| `ef_search` | **Query** | Recall ↑ | **Latency** ↑ |

Khoảng hợp lý của `m` là 5–48, mặc định pgvector là 16. `m` nhỏ tốt hơn cho recall thấp
hoặc số chiều thấp; `m` lớn tốt hơn cho recall cao hoặc số chiều cao. `ef_construction`
tăng quá một ngưỡng thì gần như không thêm được gì mà thời gian dựng index tăng vọt.

**Điểm mấu chốt về vận hành:** `m` và `ef_construction` **đóng cứng lúc build** — đổi là
phải dựng lại index. `ef_search` **vặn được từng truy vấn**, tức điều chỉnh được cán cân
recall–latency mà không phải rebuild. Nên chiến lược đúng là: chọn `m` / `ef_construction`
một lần cho đủ dùng, rồi mọi tinh chỉnh về sau làm bằng `ef_search`.

### 5.2 Cấu hình hiện tại của dự án

```sql
CREATE INDEX ON kb_chunk USING hnsw (embedding vector_cosine_ops);
```

Không truyền tham số → `m = 16`, `ef_construction = 64`, và `hnsw.ef_search = 40` mặc
định lúc truy vấn. `CANDIDATES_PER_SIDE = 20` nên `LIMIT 20 < ef_search 40` — tỉ lệ này
đúng, không có gì phải sửa.

### 5.3 Và đây là điều cần nói thẳng: ở quy mô hiện tại, ANN chưa mua được gì

`kb_chunk` đang có **0 dòng**. Một tài liệu cookbook nạp vào cho **129 chunk**.

Với 129 vector 1024 chiều, quét tuần tự toàn bảng mất **dưới một mili-giây**. HNSW ở quy
mô này **không nhanh hơn**, nhưng vẫn **gần đúng** — tức là bạn trả bằng recall mà không
nhận lại latency. Index chỉ bắt đầu có lãi từ khoảng **10.000 dòng** trở lên.

Nên: **đừng vặn gì cả cho tới khi vượt ~10k chunk.** Giữ index vì nó vô hại và để sẵn cho
sau này, nhưng mọi buổi tinh chỉnh `m` / `ef_search` trước mốc đó là tối ưu một thứ không
phải nút thắt.

### 5.4 Memory — tính bằng số, không bằng cảm giác

Vector 1024 chiều, `float4` = 4 byte/chiều. HNSW cộng thêm khoảng `m × 2` liên kết 4 byte
mỗi nút:

| Quy mô | Chunk | Vector thô | **HNSW** | halfvec | binary |
|---|---:|---:|---:|---:|---:|
| 1 tài liệu | 129 | 0,5 MB | 0,5 MB | 0,3 MB | 0,02 MB |
| 100 tài liệu | 12.900 | 52,8 MB | 54,5 MB | 26,4 MB | 1,7 MB |
| 1.000 tài liệu | 129.000 | 528 MB | **545 MB** | 264 MB | 16,5 MB |
| 10.000 tài liệu | 1.290.000 | 5,3 GB | **5,4 GB** | 2,6 GB | 165 MB |

Đọc bảng này: một trợ lý nội bộ khó vượt 1.000 tài liệu, và ở mốc đó index vẫn **nằm gọn
trong RAM** của một máy chủ tầm thường. Nói cách khác — **bài toán memory của bạn không
tồn tại**, và sẽ không tồn tại trong tương lai gần.

Chỉ khi index không còn vừa RAM mới cần đến lượng tử hoá: `halfvec` (16-bit, giảm một
nửa, mất rất ít recall) rồi mới tới binary quantization (giảm 32 lần, mất nhiều recall,
phải rerank lại bằng vector gốc). Ghi ở đây để biết đường lui, **không phải để làm bây
giờ**.

### 5.5 Cách đo khi đến lúc phải đo

Ba số phải đo **cùng nhau**, vì cải thiện một cái luôn làm hỏng cái khác:

1. **Recall@k** — so kết quả ANN với kết quả **quét tuần tự chính xác** (tạm tắt index
   bằng `SET enable_indexscan = off`). Không có mẫu số này thì không biết đang mất gì.
2. **Latency p95**, không phải trung bình. Trung bình giấu đúng cái đuôi làm người dùng
   thấy chậm — bài học đã trả giá ở lần đo embed p95 19.969 ms.
3. **Kích thước index** (`pg_relation_size`) so với RAM còn trống.

Quy trình: cố định `m` / `ef_construction`, rồi quét `ef_search` qua 20/40/80/160 và vẽ
recall theo latency. Chọn điểm **rẻ nhất đạt ngưỡng recall bạn cần** — không chọn điểm
recall cao nhất.

---

## 6. Chọn kho vector: FAISS, ChromaDB, Qdrant hay pgvector

### 6.1 Bảng so

| | **pgvector** | **FAISS** | **ChromaDB** | **Qdrant** |
|---|---|---|---|---|
| Bản chất | Extension của Postgres | **Thư viện** ANN | CSDL vector nhúng | CSDL vector (Rust) |
| Lưu bền | Postgres lo | **Không có** — tự lo | Có | Có |
| Lọc metadata | **SQL thuần** | Không có | **Lọc SAU** ANN | **Lọc TRƯỚC** ANN |
| Giao dịch / ACID | **Có** | Không | Không | Không |
| Hạ tầng thêm | **Không** | Không (nhưng phải tự dựng) | Có | Có |
| Hợp quy mô | < vài triệu vector | Tuỳ bạn cài | Dev, < ~5M | 5M+, lọc phức tạp |

**FAISS** không phải cơ sở dữ liệu — nó là **thư viện** tìm kiếm. Không lưu bền, không
lọc metadata, không giao dịch. Chọn FAISS nghĩa là tự viết lấy tầng lưu trữ, tầng đồng bộ
và tầng khôi phục. Nó mạnh khi cần tốc độ thô và GPU.

**ChromaDB** tối ưu cho tốc độ *phát triển*, không phải quy mô *vận hành*. Điểm yếu cần
biết: nó **áp bộ lọc metadata SAU khi ANN chạy xong**, rồi lấy dư ra để bù — cách này làm
hỏng recall khi bộ lọc hẹp.

**Qdrant** áp bộ lọc **trước** ANN, đó là hành vi đúng về mặt kỹ thuật, và là lý do nó
được khuyên cho dữ liệu đa người thuê hoặc điều kiện lọc hẹp.

**pgvector**: nếu ứng dụng đã chạy trên Postgres thì đây là lựa chọn thực dụng nhất —
không hạ tầng mới, không dịch vụ mới phải giám sát, vector nằm cùng chỗ với dữ liệu ứng
dụng. Với corpus nhỏ đến vừa (dưới 2–3 triệu vector), hiệu năng thừa đủ.

### 6.2 Chọn cho bài toán này: **giữ nguyên pgvector**

Không phải vì nó "đủ dùng", mà vì bốn lý do cụ thể của dự án này:

1. **Bạn đã chạy Postgres 16.15 + pgvector 0.8.6.** Thêm một kho vector nữa là thêm một
   tiến trình phải giám sát, thêm một chỗ để dữ liệu lệch nhau, thêm một thứ hỏng lúc 3
   giờ sáng — đổi lấy một vấn đề hiệu năng **chưa tồn tại**.
2. **Hybrid search cần cả hai đường trong cùng một truy vấn.** BM25 của bạn là `tsvector`
   + GIN **trong chính Postgres**. Tách vector sang FAISS/Chroma nghĩa là hai kho, hai lần
   gọi mạng, và phải tự ghép ID — trong khi hiện tại hai đường chạy song song trên cùng
   một kết nối.
3. **Ghi theo giao dịch.** `pipeline.py` nạp cả tài liệu trong **một transaction**, với lý
   do viết thẳng trong code: *hỏng giữa chừng mà vẫn để lại nửa số chunk nghĩa là bot trả
   lời dựa trên nửa tài liệu mà không ai biết*. FAISS và Chroma **không có** thứ đó.
4. **Quy mô.** Xem §5.4: 1.000 tài liệu = 545 MB, vẫn nằm gọn trong RAM. Ngưỡng phải cân
   nhắc Qdrant là vài triệu vector — cách xa hàng chục lần.

**Khi nào thì đổi:** vượt ~2–3 triệu chunk, **hoặc** cần lọc metadata hẹp trên nhiều người
thuê mà §7.3 không giải quyết nổi. Cả hai đều còn xa.

Về lời khuyên phổ biến *"cứ bắt đầu bằng Qdrant để khỏi phải di trú sau này"* — nó hợp lý
cho một dự án **chưa có** CSDL. Dự án này đã có Postgres mang sẵn `memory_fact`,
`kb_document`, allowlist và migration đánh số. Ở đây "đường sản xuất đã sẵn" chính là
Postgres.

---

## 7. Metadata cho từng chunk, tích hợp Hybrid Search

### 7.1 Thiết kế hiện có, và vì sao nó đúng hơn vẻ ngoài

Cột của `kb_chunk`: `doc_id`, `ord`, `section`, `page`, `content`, `embed_input`,
`embedding`, `tsv`, `token_count`.

Điều đáng chú ý nằm ở chỗ **metadata không phải một bộ lọc riêng — nó được nhét vào cả
hai chỉ mục**:

```
contextualize()  →  embed_input = "[Tên tài liệu > Mục]\n<thân chunk>"
                          │                         │
                          ▼                         ▼
                   embedding (DENSE)          tsv (SPARSE, migration 0008)
```

`content` giữ **nguyên văn** để trích dẫn; `embed_input` là bản có ngữ cảnh đem đi embed.
Migration 0008 sửa `tsv` sinh từ `embed_input` thay vì `content`, với lý do ghi rõ trong
file: tài liệu có mục "Nghỉ phép năm" nhưng thân mục không lặp lại cụm đó thì câu hỏi
*"nghỉ phép năm bao nhiêu ngày"* **không khớp một từ nào** bên đường lexical.

Đây là **contextual retrieval làm bằng metadata có sẵn**, không phải bằng một lần gọi
model cho từng chunk: hai cách gần bằng nhau trên tài liệu có tiêu đề rõ, mà cách này
không tốn tiền và không thể bịa.

**Hệ quả trực tiếp của việc vừa làm ở §2–3:** trước đây `section` NULL toàn bộ với PDF,
nên `embed_input` chỉ có tên tài liệu — cả hai chỉ mục đều mất một tầng ngữ cảnh. Giờ
`section` mang tên món (105/129 chunk), nên **cả dense lẫn sparse đều được lợi** mà không
phải đổi một dòng nào trong `search.py`.

### 7.2 ⚠ Một lỗi phải sửa TRƯỚC khi nạp lại

`search.py` truy vấn:

```sql
FROM kb_chunk c JOIN kb_document d ON d.id = c.doc_id
```

**Không có điều kiện lọc phiên bản.** Trong khi `pipeline.py` cố ý bất biến theo phiên
bản: nạp lại tài liệu có nội dung khác sẽ tạo `version + 1` và **giữ nguyên bản cũ**, và
không có chỗ nào trong toàn bộ mã nguồn xoá hay đánh dấu bản cũ.

Nghĩa là **ngay lần nạp lại đầu tiên, kết quả tìm kiếm sẽ trộn chunk của v1 và v2** — nội
dung cũ và mới cùng xuất hiện, trùng lặp, và bot trích dẫn cả thứ đã bị thay thế.

Hiện chưa lộ vì `kb_chunk` đang rỗng. Nhưng thay đổi chunker ở §3 **bắt buộc phải nạp
lại**, nên đây là cái bẫy nằm ngay trên đường đi.

Cách sửa rẻ và đánh index được: thêm `kb_document.la_ban_moi_nhat BOOLEAN`, đặt `false`
cho bản cũ ngay trong chính transaction nạp bản mới, rồi lọc `WHERE d.la_ban_moi_nhat` ở
cả hai đường tìm kiếm.

### 7.3 Bẫy thứ hai: thêm bộ lọc metadata sẽ làm sập recall

Đây là điều quan trọng nhất của cả mục 7, và nó phản trực giác.

Với index gần đúng, **bộ lọc được áp SAU khi index đã quét xong**. Với HNSW và
`hnsw.ef_search = 40` mặc định, nếu điều kiện lọc khớp 10% số dòng thì trung bình chỉ còn
**4 dòng** sống sót — dù trong CSDL có hàng nghìn dòng hợp lệ.

Nói cách khác: cái giây phút bạn viết `WHERE d.title = '...'` vào `vector_search`, bạn mất
phần lớn recall **mà không có lỗi nào báo ra**. Đúng loại hỏng im lặng mà dự án này chống.

**pgvector 0.8 có sẵn lời giải, và bạn đang chạy 0.8.6:**

```sql
SET hnsw.iterative_scan = strict_order;   -- hoac relaxed_order
```

Thay vì lấy một mẻ cố định, iterative scan **đi tiếp vào đồ thị** cho tới khi đủ số dòng
qua được `WHERE`, có trần bởi `hnsw.max_scan_tuples` (mặc định 20.000) và
`hnsw.scan_mem_multiplier`. Nó cải thiện recall, nhưng làm tăng CPU, bộ nhớ và **độ trễ
đuôi** — nên phải bật kèm đo, không bật rồi quên.

`strict_order` giữ đúng thứ tự khoảng cách; `relaxed_order` nhanh hơn nhưng thứ tự có thể
xê dịch — với pipeline này thì `relaxed_order` chấp nhận được, vì sau đó còn một bước
**rerank** xếp lại toàn bộ.

Lưu ý cuối: bẫy này **chỉ có ở đường dense**. Đường sparse (`tsv @@ q` + GIN) là chỉ mục
**chính xác**, thêm `WHERE` vào đó không mất gì. Đó là một lý do nữa để giữ cả hai đường:
khi một bên suy giảm vì bộ lọc, bên kia vẫn đủ.

### 7.4 Metadata nên thêm — và nên KHÔNG thêm

Nguyên tắc: **cột metadata mà không truy vấn nào lọc theo là cột chết.** Nó vẫn tốn chỗ,
vẫn phải điền, vẫn phải migrate, và vẫn sẽ lệch với thực tế. Bài học này dự án đã trả giá
với cột `used_tools` — thêm vào, điền sai, rồi phải bỏ ở migration 0010.

**Nên thêm:**

| Cột | Vì sao | Chi phí |
|---|---|---|
| `kb_document.la_ban_moi_nhat` | Sửa lỗi §7.2 — bắt buộc | 1 migration, 1 dòng SQL |
| `kb_chunk.page` | **Đã có cột, đang luôn NULL.** Trích dẫn "trang 32" kiểm chứng được | Cần `extract.py` trả kèm mốc trang |

**Chưa nên thêm:**

- `lang` — corpus tiếng Anh, câu hỏi tiếng Việt, nhưng hiện chỉ có **một** tài liệu. Thêm
  cột để lọc theo ngôn ngữ khi chỉ có một ngôn ngữ là nghi lễ.
- `loai_noi_dung` (công thức / hướng dẫn / phụ lục) — chưa có truy vấn nào cần.
- Metadata dạng JSONB tuỳ ý — nghe linh hoạt, thực tế là chỗ đổ rác không ai cưỡng chế
  được lược đồ, và không đánh index hiệu quả được.

### 7.5 Hybrid search: hợp nhất và cân bằng

Đường hợp nhất hiện tại là **RRF** (`fusion.py`), mỗi bên lấy 20 ứng viên, hợp nhất còn
10, rerank còn 3–5. RRF đúng cho bài này vì nó chỉ dùng **thứ hạng**, không dùng điểm —
nên không phải chuẩn hoá điểm cosine với điểm `ts_rank`, hai thang đo không cùng đơn vị và
không cùng phân bố.

Một điểm về corpus tiếng Anh + câu hỏi tiếng Việt đã nói ở §3: `vn_tsv()` dùng
`to_tsvector('simple', unaccent(...))`, không stemming không stopword, nên đường sparse chỉ
khớp những token **sống sót qua hai ngôn ngữ** — tên món, nguyên liệu vay mượn (`goulash`,
`casserole`, `oregano`). Với corpus này, RRF thực tế chạy gần như **một chân**. Đó không
phải lỗi cấu hình mà là hệ quả của việc chọn corpus khác ngôn ngữ, và là một lý do nữa để
corpus thật nên cùng ngôn ngữ với người dùng.

---

## 8. Việc còn lại, theo thứ tự

1. **Sửa lọc phiên bản (§7.2)** — trước khi nạp bất cứ thứ gì. Đây là bẫy nằm trên đường
   đi, không phải một cải tiến.
2. Nạp cookbook và kiểm bằng câu hỏi thật.
3. Điền `page` (§7.4) nếu muốn trích dẫn kiểm chứng được.
4. Bật `hnsw.iterative_scan` (§7.3) **cùng lúc** với lần đầu thêm bộ lọc metadata vào
   `vector_search` — không sớm hơn, không muộn hơn.
5. Không vặn `m` / `ef_search` cho tới khi vượt ~10k chunk (§5.3).

## Nguồn bổ sung

**ANN / pgvector**
- [pgvector — GitHub](https://github.com/pgvector/pgvector)
- [HNSW Indexes with Postgres and pgvector — Crunchy Data](https://www.crunchydata.com/blog/hnsw-indexes-with-postgres-and-pgvector)
- [Faster similarity search performance with pgvector indexes — Google Cloud](https://cloud.google.com/blog/products/databases/faster-similarity-search-performance-with-pgvector-indexes/)
- [Choosing a Vector Index: HNSW, IVF, and the Trade-Offs — Barking Iguana](https://barkingiguana.com/writing/choosing-a-vector-index-hnsw-ivf-and-the-trade-offs/)
- [Announcing: pgvector 0.8.0 — Nile](https://www.thenile.dev/blog/pgvector-080)
- [The Complete Guide to pgvector Tuning: HNSW/IVFFlat, halfvec, Binary Quantization](https://tomodahinata.com/en/blog/pgvector-index-tuning-hnsw-ivfflat-quantization-iterative-scan-guide)
- [How to scale vector search in Postgres (pgvector) — ClickHouse](https://clickhouse.com/resources/engineering/scale-vector-search-postgres)
- [Hybrid Search Patterns with Postgres and pgvector — Crunchy Data](https://www.crunchydata.com/blog/hybrid-vector-search)

**So sánh kho vector**
- [Best Vector Databases in 2026 — Firecrawl](https://www.firecrawl.dev/blog/best-vector-databases)
- [ChromaDB vs Qdrant vs Weaviate vs pgvector: shootout 2026 — DEV](https://dev.to/ayinedjimi-consultants/chromadb-vs-qdrant-vs-weaviate-vs-pgvector-vector-database-shootout-2026-14n7)
- [Vector Database Comparison 2026 — 4xxi](https://4xxi.com/articles/vector-database-comparison/)
- [Best Vector Databases 2026 — DataCamp](https://www.datacamp.com/blog/the-top-5-vector-databases)

---

## Nguồn

**Kiến trúc lưu trữ**
- [Data Warehouse vs Data Lake vs Lakehouse: 2026 Guide — Lucent Innovation](https://www.lucentinnovation.com/resources/it-insights/data-warehouse-vs-data-lake-vs-lakehouse)
- [Data Warehouse vs. Data Lake vs. Data Lakehouse — Striim](https://www.striim.com/blog/data-warehouse-vs-data-lake-vs-data-lakehouse-an-overview/)
- [Data Warehouse vs Data Lake vs Data Lakehouse: Key Differences — Monte Carlo](https://montecarlo.ai/blog-data-warehouse-vs-data-lake-vs-data-lakehouse-definitions-similarities-and-differences)
- [Data Lakehouse vs Data Warehouse: Which to Choose in 2026? — Wonderment Apps](https://www.wondermentapps.com/blog/data-lakehouse-vs-data-warehouse/)
- [Data Warehouse vs Data Lake vs Data Lakehouse (2026) — VanceIQ](https://vanceiq.com/blog/data-warehouse-vs-data-lake-vs-data-lakehouse-2026)

**Trích xuất PDF**
- [Best Python PDF to Text Parser Libraries: A 2026 Evaluation — Unstract](https://unstract.com/blog/evaluating-python-pdf-to-text-libraries/)
- [A Comparative Study of PDF Parsing Tools Across Diverse Document Categories — arXiv](https://arxiv.org/html/2410.09871v1)
- [Empirical Evaluation of PDF Parsing and Chunking for Financial QA with RAG — arXiv](https://arxiv.org/pdf/2604.12047)
- [pdfmux vs PyMuPDF vs marker vs docling vs pdfplumber: 200-PDF benchmark](https://pdfmux.com/blog/pdfmux-vs-pymupdf-vs-marker-vs-docling/)
- [PyMuPDF — Features Comparison](https://pymupdf.readthedocs.io/en/latest/about.html)

**Chunking**
- [RAG Chunking Strategies 2026: 8 Methods Compared — Denser](https://denser.ai/blog/rag-chunking-strategies/)
- [Chunking Strategies for RAG: Best Practices — Unstructured](https://unstructured.io/blog/chunking-for-rag-best-practices)
- [Best Chunking Strategies for RAG (and LLMs) in 2026 — Firecrawl](https://www.firecrawl.dev/blog/best-chunking-strategies-rag)
- [RAG Chunking Strategies: The 2026 Benchmark Guide — Prem AI](https://www.premai.io/blog/rag-chunking-strategies-the-2026-benchmark-guide/)
- [Chunking Methods on RAG — Effectiveness vs Computational Cost — arXiv](https://arxiv.org/html/2606.00881v1)
- [The Chunking Paradigm: Recursive Semantic for RAG Optimization — ACL Anthology](https://aclanthology.org/2025.icnlsp-1.15.pdf)
