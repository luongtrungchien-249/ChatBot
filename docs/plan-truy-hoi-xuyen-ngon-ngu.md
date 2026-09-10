# Plan: truy hồi xuyên ngôn ngữ

*10/09/2026. Mọi con số đo trên kho thật đang chạy — 2 tài liệu, 179 chunk, 98 mục có tên.*

> **Đã thi công. Đọc §11 trước §1.**
>
> Phần §1–§10 là bản kế hoạch viết TRƯỚC khi làm. Khi thi công thì mốc **2/6** ở §4
> không tái lập được, và lý do đó quan trọng hơn cả bản kế hoạch: nút thắt thật nằm
> cao hơn một tầng. §11–§14 ghi lại những gì đo được, kể cả hai bản vá đã thử và đã
> phải gỡ bỏ.

---

## 1. Vấn đề, đo được

Tám câu hỏi tiếng Việt dạng "món nào có X và Y", đáp án chuẩn dựng từ chính văn bản
trong CSDL: **4/8 trượt**. Và hình dạng của lỗi mới là thứ đáng chú ý:

| Đáp án nằm ở | Kết quả |
|---|---|
| Sách Sa Pa (song ngữ Việt–Anh) | **4/4 đúng** |
| Sách Open Source Cookbook (thuần tiếng Anh) | **0/4 đúng** |

Hỏi **cùng câu đó bằng tiếng Anh** thì tìm ra ngay:

```
[VI] Món nào dùng phô mai và mì ống?
     → canh khoai sọ, mứt chuối, ốc om chuối đậu          SAI hoàn toàn
[EN] Which dish uses cheese and macaroni?
     → Callamon's Tuna Casserole, Andrew's Macaroni       ĐÚNG cả hai đáp án chuẩn
```

## 2. Chẩn đoán

Xem tầng vector **trước** rerank, với câu hỏi tiếng Việt:

```
 1. d=0.4698  Ố C O M / CH UỐ I ĐẬU
 2. d=0.5567  MỨT CHUỐI
 3. d=0.5600  BRAISED SNAILS WITH BANANA AND TOFU
 ...
10. d=0.6083  STIR-FRIED H'MONG GREEN MUSTARD
lexical_search: (rỗng)
```

**Không một món tiếng Anh nào lọt vào top 10.** Rerank chưa bao giờ được nhìn thấy đáp
án đúng — nên đây là lỗi ở tầng **truy hồi**, không phải tầng xếp hạng.

Nguyên nhân: **embedding bị chi phối bởi NGÔN NGỮ chứ không phải nội dung.** Một câu hỏi
tiếng Việt nằm gần *mọi* văn bản tiếng Việt hơn là gần văn bản tiếng Anh đúng nghĩa.
"Ốc om chuối đậu" đạt d=0,4698 cho một câu hỏi về phô mai và mì ống — đó là gom cụm theo
ngôn ngữ, thuần tuý.

Đường BM25 rỗng là tất yếu: `vn_tsv()` so khớp từ, mà "phô mai" không bao giờ trùng
"cheese".

## 3. Nguyên nhân trực tiếp — một dòng mô tả

`src/tools/knowledge_search.py`:

```python
"query": {
    "description": (
        "Câu hỏi đầy đủ ngữ cảnh, viết bằng tiếng Việt như người dùng đã hỏi. "
        "Giữ nguyên mã số, tên riêng, thuật ngữ."
    ),
},
```

Mô tả này **ra lệnh cho model viết truy vấn bằng tiếng Việt**. Model làm đúng như được
bảo, và kết quả là nửa kho tài liệu trở nên vô hình.

Đây là lần thứ ba trong dự án gặp đúng loại lỗi này:

| Công cụ | Mô tả sai điều gì | Hậu quả đo được |
|---|---|---|
| `youtube_search` | Lấy hạn mức API làm trọng tâm | Model né, đốt 3 vòng `web_search` tìm link |
| `search_knowledge_base` | Bó hẹp kho vào "quy định, quy trình" | Không gọi công cụ cho câu hỏi món ăn (2/6) |
| `search_knowledge_base` (tham số) | Bắt viết truy vấn tiếng Việt | 2/6 câu giao tập hợp |

**Mô tả công cụ là code, không phải chú thích.** Model đọc nó để quyết định.

## 4. Ba biến thể truy vấn, đo thật

| Truy vấn viết bằng | Đúng |
|---|---|
| Tiếng Việt (hiện tại) | **2/6** |
| **Tiếng Anh** | **5/6** |
| Trộn Việt + Anh trong một chuỗi | 4/6 |

Hai điều rút ra:

- **Tiếng Anh là mẫu số chung của kho này.** Sách Sa Pa song ngữ nên mỗi trang có cả hai
  thứ tiếng; hỏi tiếng Anh vẫn tìm được `khoai sọ` và `bí đỏ và gà`. Không mất gì.
- **Đừng trộn hai thứ tiếng trong một chuỗi.** 4/6, kém hơn tiếng Anh thuần: vector của
  chuỗi lai nằm lưng chừng giữa hai cụm, không thuộc về cụm nào.

## 5. Phương án đã cân nhắc và loại

**Thêm một LLM chuyên dịch câu hỏi — LOẠI.**

Dự án **đã bỏ** stage `rewrite` ngày 07/09, lý do ghi thẳng trong
`agents/pipeline/handle_message.py`:

> *Retrieval giờ là một CÔNG CỤ trong vòng ReAct, và model nhìn thấy lịch sử dưới dạng
> lượt thật, nên chính nó đã tự viết truy vấn có ngữ cảnh — đo được trong log: từ "AI" nó
> sinh ra "artificial intelligence latest 2026 2025 2024". Thêm một lần gọi model rẻ để
> làm lại việc đó là cộng thêm độ trễ và tiền cho thứ vòng lặp đang làm rồi.*

Model **đã tự viết truy vấn**. Thêm một lần gọi để dịch là trả tiền và độ trễ cho việc
đang được làm sẵn — đúng lý do người ta đã bỏ `rewrite`. Sửa một dòng mô tả tốn **0 lần
gọi model, 0 độ trễ**.

**Phát hiện ngôn ngữ người dùng — LOẠI.** Cứ luôn viết truy vấn tiếng Anh. Người dùng hỏi
tiếng Anh thì model chép lại, không tốn gì. Thêm một bước phát hiện là thêm một chỗ để
đoán sai mà không mua được gì.

**Bung hai truy vấn song song rồi hợp nhất — CHƯA LÀM, để dành.** RRF trong `fusion.py`
đã nhận `list[list[int]]` nên thêm bảng xếp hạng thứ ba và thứ tư là chuyện nhỏ về cấu
trúc. Nhưng tính từ bảng §4, hợp của VI ∪ EN = **5/6**, **đúng bằng** tiếng Anh thuần —
tức nó **không mua thêm gì** cho kho hiện tại, chỉ tốn thêm một lần embed và hai truy vấn
CSDL. Đây là bảo hiểm cho tương lai, không phải cải thiện hôm nay. Xem §8.

**Bảng nguyên liệu có cấu trúc — CHƯA LÀM.** Xem §9.

**GraphRAG — KHÔNG.** Lỗi nằm *phía trên* mọi thứ đồ thị làm: ứng viên đúng không bao giờ
được lấy ra. Dựng đồ thị trên một tầng truy hồi không với tới nửa kho là xây nhà trên nền
lún. Chưa kể chi phí: GraphRAG trích quan hệ cho **từng chunk** rồi phát hiện cụm và tóm
tắt cụm, trong khi hệ này phải nạp lại toàn bộ mỗi lần đổi chunker.

## 6. Việc phải làm

### 6.1 Sửa mô tả tham số `query`

`src/tools/knowledge_search.py`. Nội dung mới phải nói ba điều:

1. **Viết truy vấn bằng tiếng Anh**, kể cả khi người dùng hỏi bằng tiếng Việt.
2. **Vì sao** — tài liệu trong kho phần lớn là tiếng Anh; truy vấn tiếng Việt không với
   tới chúng. Nêu lý do chứ không chỉ ra lệnh: model tuân lệnh có lý do tốt hơn lệnh trần.
3. **Không dịch cái không được dịch** — mã số (`QD-145/2026`), tên riêng, tên món đặc
   thù không có từ tương đương. Giữ nguyên, hoặc để cả hai dạng.

Không đụng vào phần mô tả công cụ (`description`) — phần đó vừa sửa 08/09 và đang đạt
6/6 cho luồng RAG-trước-web-sau.

### 6.2 Không đụng vào ngôn ngữ TRẢ LỜI

`SYSTEM_PROMPT` đã có: *"Tiếng Việt tự nhiên... Người dùng viết tiếng Anh thì trả lời
tiếng Anh."* Đo thật 09/09 xác nhận nó chạy: hỏi tiếng Việt, tài liệu tiếng Anh, bot trả
lời tiếng Việt kèm nguồn. **Không cần làm gì.**

Ngôn ngữ **truy vấn** và ngôn ngữ **trả lời** là hai thứ tách rời — đây là điểm dễ nhầm
nhất của cả thay đổi này.

### 6.3 Test khoá hợp đồng

Trong `tests/unit/test_knowledge_tool.py`:

- Mô tả tham số phải yêu cầu tiếng Anh (chống việc ai đó "sửa lại cho nhất quán" về
  tiếng Việt).
- Phải nêu luật giữ nguyên mã số / tên riêng.
- Ghi lại trong docstring **con số 2/6 → 5/6** và lý do, để lần sau người đọc biết dòng
  đó không phải tuỳ hứng.

## 7. Tiêu chí nghiệm thu

*Kết quả thật của các tiêu chí này nằm ở §13 — bảng dưới đây là ngưỡng đặt ra trước
khi làm.*

Chạy **đầu-cuối qua bot thật** (không phải gọi thẳng `knowledge.search`), có theo dõi
công cụ được gọi:

| Chỉ số | Ngưỡng |
|---|---|
| 6 câu giao tập hợp ở §4 | **≥ 5/6** (hiện 2/6) |
| Truy vấn model sinh ra | Bằng tiếng Anh |
| Mã số / tên riêng trong truy vấn | Giữ nguyên, không bị dịch |
| Ngôn ngữ câu trả lời | Vẫn là ngôn ngữ người dùng hỏi |
| Bốn nhóm RAG-trước-web-sau | Vẫn **6/6**, không hồi quy |
| Recall@5 trên `qa.jsonl` | Không tụt dưới 0,85 |

Hai hàng cuối là hàng chống hồi quy, và phải chạy — thay đổi này đụng vào chính công cụ
vừa được chỉnh 08/09.

## 8. Điều kiện hết hạn

**Khuyến nghị "viết truy vấn tiếng Anh" phụ thuộc CORPUS, không phải là chân lý.**

Kho hiện tại: một sách thuần Anh + một sách song ngữ → tiếng Anh là mẫu số chung.

Nhưng corpus thật của một trợ lý nội bộ Việt Nam nhiều khả năng là **sổ tay, quy định,
quy trình bằng tiếng Việt**. Lúc đó luật này **đảo ngược**: truy vấn tiếng Anh sẽ không
với tới tài liệu tiếng Việt, và cả BM25 lẫn vector đều tệ đi.

Nên khi nạp tài liệu tiếng Việt vào:

1. **Đo lại** ba biến thể ở §4 trên corpus mới.
2. Nếu tài liệu thành đa ngôn ngữ thật (có cả Việt thuần lẫn Anh thuần) thì mới làm
   **bung hai truy vấn song song** ở §5 — lúc đó nó mới mua được thứ mà một ngôn ngữ
   không mua nổi.

Ghi điều kiện này vào chính chú thích trong `knowledge_search.py`, không chỉ ở tài liệu
này — người sửa code sẽ đọc code trước.

## 9. Hạn chế đã biết, không sửa ở đợt này

**Câu hỏi với nguyên liệu quá phổ biến vẫn trượt.** `trứng và hành` trượt **cả ba** biến
thể truy vấn. Đáp án chuẩn có 4 món, nhưng hàng chục món khác cũng có trứng và hành, nên
top-5 nào cũng trúng món khác.

Dịch không cứu được loại này — đây là câu hỏi **giao tập hợp** thật sự, và tương đồng
vector về bản chất không làm được phép giao. Chỗ này mới là chỗ một bảng quan hệ kiếm
được tiền:

```sql
CREATE TABLE kb_mon (id, chunk_id, ten_vi, ten_en);
CREATE TABLE kb_mon_nguyen_lieu (mon_id, nguyen_lieu_chuan);
```

`GROUP BY mon_id HAVING count(*) = 2` — chính xác tuyệt đối, không phụ thuộc ngôn ngữ.
Chi phí: một lần gọi LLM cho mỗi mục có tên (98 lần, một lần cho mỗi lần nạp).

**Nhưng chưa làm**, vì nó chỉ chiếm 1/6 số câu đo được. Trước khi xây: đếm trong
`usage_log` xem câu hỏi dạng giao tập hợp chiếm bao nhiêu phần trăm câu hỏi **thật**.
Dưới ~5% thì đó là nghi lễ.

## 10. Ghi chú về phương pháp — hai lần đo sai của chính tài liệu này

Ghi lại để người sau không lặp:

**Lần một: đáp án chuẩn khớp chuỗi con.** Dựng đáp án bằng cách tìm chuỗi con trên chữ đã
bỏ dấu, nên `"ga"` trúng cả `garlic`, `sugar`, `vegetable` — "gà và mì" ra 58/98 mục và
cho con số 5/8 vô nghĩa. Siết bằng ranh giới từ mới ra 4/8 dùng được.

**Lần hai: chẩn đoán sai nguyên nhân.** Ban đầu kết luận lớp câu hỏi này hỏng vì
"embedding không làm được phép giao". Đo ra thì phép giao **chạy được** khi cùng ngôn ngữ
(EN tìm đúng cả hai món phô mai + mì ống, hạng 1 và 2). Cái hỏng là truy hồi xuyên ngôn
ngữ. Nếu tin chẩn đoán cũ mà đi xây bảng nguyên liệu ngay, sẽ sửa được một lớp câu hỏi
hẹp rồi vẫn thấy phần lớn câu tiếng Việt trượt trên sách tiếng Anh.

Bài học chung: **đo cái đúng trước khi sửa, và kiểm cả thước đo.** Một thước đo sai còn
nguy hiểm hơn không có thước đo, vì nó cho phép tuyên bố thành công sớm.

---

# PHẦN II — thi công, và những gì phép đo trả lời khác kế hoạch

*10/09/2026, sau khi làm. Đo trên cùng kho, chạy đầu-cuối qua `handle_message()` thật
chứ không gọi thẳng `knowledge.search`.*

## 11. Nút thắt thật nằm cao hơn một tầng

Sửa xong dòng mô tả ở §6.1, đo lại 6 câu §4 — **0/6**. Đổi lại đúng mô tả cũ để đối
chứng — cũng **0/6**.

Cả hai bằng nhau vì một lý do chung mà cả bản kế hoạch không nhắc tới: với câu hỏi
dạng "món nào có X và Y", model **phần lớn không gọi `search_knowledge_base` lần nào**.
Nó trả lời thẳng từ trí nhớ, không nguồn — và từng cái tên nó kể đều là món có thật
trên đời, chỉ không phải món trong kho của người dùng.

    câu TRA CỨU      ("Gà hầm bí đỏ cần nguyên liệu gì")   4/4 có gọi công cụ
    câu GIAO TẬP HỢP ("Món nào có phô mai và mì ống")      1/4 có gọi công cụ

Đã loại trừ: công cụ vẫn được khai trong `specs()` (`_has_documents=True`), và **không**
phải do hai ví dụ 7–8 mới thêm vào `SYSTEM_PROMPT` — bỏ hai ví dụ đó đi vẫn ra đúng 1/4.

Nên **mốc 2/6 của §4 giả định công cụ luôn được gọi**, và giả định đó sai. Đo lại ngôn
ngữ truy vấn khi công cụ chưa chắc được gọi thì đang đo hai thứ trộn vào nhau.

### 11.1 Vì sao model không gọi

Mệnh lệnh "gọi công cụ TRƯỚC khi trả lời" nằm ở **giữa đoạn** mô tả, và điều kiện của
nó buộc theo **sự tự tin** của model: *"kể cả câu bạn nghĩ mình đã biết đáp án"*. Với
lớp câu hỏi này model **luôn** tự tin — nên điều kiện đó tự vô hiệu đúng lúc cần nhất.

Ba thay đổi, đo riêng từng cái:

| Mô tả công cụ | giao tập hợp |
|---|---|
| Bản cũ | 1/4 |
| Thêm luật "câu hỏi ngược", mệnh lệnh vẫn ở giữa | 2/4 |
| **Mệnh lệnh lên câu đầu** + gọi tên cạm bẫy + một ví dụ cụ thể | **4/4** |

Thứ tự câu là một nửa tác dụng, không phải gia vị.

Ví dụ trong mô tả **cố ý** dùng một cặp nguyên liệu không nằm trong bộ đo (đậu phụ + cà
chua). Lấy đúng câu đang đo làm ví dụ là dạy vẹt, và con số sau đó hết đo được gì. Có
một test khoá điều này.

## 12. Người trong vòng lặp — khi truy hồi không chắc

§9 của bản kế hoạch dừng ở "câu giao tập hợp thật sự thì tương đồng vector không làm
được phép giao". Đúng, nhưng có một đường ra rẻ hơn nhiều so với bảng nguyên liệu: khi
không chắc thì **đừng đoán — hỏi**.

Bot đưa ra danh sách ứng viên **có thật trong kho**, kèm một dòng "Khác", rồi tra sâu
theo lựa chọn:

```
bạn> Món nào dùng phô mai và mì ống?
bot> 1. Kristin's Poor Man's Goulash
     2. Andrew's Macaroni with Bacon & Green Onion
     3. Callamon's Tuna Casserole
     4. 1000monkeys' "Allon Kohns"
     5. TTurner's Cheese Dreams
     6. Khác — không phải mục nào ở trên
     Bạn chọn mục nào?
```

Mục 2 và 3 chính là hai đáp án chuẩn của câu này — thứ mà truy hồi thuần đã bỏ sót.
Chọn "Khác" thì công cụ tra rộng hơn và tìm ra đủ cả ba món dùng phô mai + mì ống.

**Tín hiệu là KHOẢNG CÁCH cosine, không phải điểm rerank.** Ở chế độ dự phòng, điểm là
tỉ lệ từ trùng nên không so được với một ngưỡng cố định; khoảng cách thì có hiệu chuẩn
ngữ nghĩa trong cả hai chế độ.

    hỏi thẳng một mục có tên     d = 0,2468  0,2613  0,2810  0,3499
    hỏi chung chung / mơ hồ      d = 0,3504  0,4658  0,5061  0,5629  0,5625  0,5960

`RAG_HOI_LAI_TU = 0,50` nằm trong khoảng trống 0,466–0,506: giữ nguyên các câu đang trả
lời đúng, chỉ bắt câu mơ hồ.

Hai chốt chặn để không hồi sinh vòng hỏi lại vô tận đã chữa ngày 07/09: đã có tham số
`chon` thì **không bao giờ** hỏi lần nữa, và kết quả công cụ nói thẳng đây là ngoại lệ
đã được cho phép của luật "làm trước, hỏi sau".

### 12.1 Hai bản vá đã thử và đã GỠ BỎ

Ghi lại để không ai làm lại:

**Luật "giữ đúng mức cụ thể" — GỠ.** Câu trượt là do model dịch "mì ống" thành `pasta`,
rộng hơn `macaroni` một bậc. Thêm một câu bảo "đừng khái quát lên một bậc" thì kết quả
tụt **4/6 → 2/6**: model không chính xác hơn, nó bắt đầu chèn nguyên văn tiếng Việt vào
truy vấn để khỏi mất độ cụ thể —

    dishes that use cheese and pasta "phô mai" "mì ống"

— đúng chuỗi lai mà §4 đo là kém hơn tiếng Anh thuần. Hai luật về cùng một chuỗi thì
luật sau dễ đè luật trước, dù nó không nói gì về ngôn ngữ.

**Luật "dưới hai ứng viên thì không hỏi" — GỠ.** Nghe hợp lý ("một danh sách một dòng
không phải một lựa chọn") nhưng sai theo kiểu tự che giấu: truy vấn càng mơ hồ thì càng
**ít** đoạn qua được `RAG_MAX_DISTANCE`, nên đúng lúc cần hỏi nhất lại là lúc chỉ còn
một ứng viên — và luật đó tự tắt tính năng. Đo thật: truy vấn dài dòng model sinh ra cho
d=0,6223 và **đúng một** đoạn sống sót.

### 12.2 Một phát hiện phụ: truy vấn dài làm hỏng truy hồi

Model hay nhét mệnh lệnh vào truy vấn, và chữ thừa bị embed y như chữ thật:

    "Which dishes contain cheese and pasta?"                      d = 0,5619
    "... ? Provide common dish names ..., list up to 10."         d = 0,6223
    "... ? List common dishes that combine cheese and pasta."     d = 0,6336

Con số cuối vượt cả `RAG_MAX_DISTANCE = 0,63`, tức lần tìm trả về **rỗng**, bot quay
sang web và trả lời bằng kiến thức chung — trong khi đáp án vẫn nằm trong CSDL. Đã thêm
luật truy vấn ngắn; đo lại thấy model viết `dishes with cheese and pasta`.

## 13. Nghiệm thu §7 — kết quả thật

| Chỉ số §7 | Ngưỡng | Kết quả |
|---|---|---|
| Truy vấn model sinh ra | tiếng Anh | **đạt**, mọi lượt |
| Mã số / tên riêng trong truy vấn | giữ nguyên | **đạt** |
| Ngôn ngữ câu trả lời | như người dùng hỏi | **đạt** |
| 6 câu giao tập hợp | ≥ 5/6 | **5/6** |
| Nhóm câu tra cứu (chống hồi quy) | không tụt | **4/4** |
| Câu nội bộ ngoài kho | không tìm thấy, không tra web | **đạt** (d=0,8497) |

Truy vấn model thật sự sinh ra, chép từ log:

```
Andrew's Macaroni with Bacon & Green Onion ingredients
recipe for 'ốc om chuối đậu' braised snails with banana and tofu
Which dishes use bacon and scallions (green onions)?
```

Sau khi bật vòng người-trong-vòng-lặp, bộ 6 câu phân bố lại thành **4 đúng ngay · 1 hỏi
lại · 1 trượt**. Câu "hỏi lại" chính là câu phô mai + mì ống, và danh sách ứng viên của
nó **có cả hai** đáp án chuẩn — tức người dùng với tới được đáp án, thay vì nhận một câu
trả lời sai một cách tự tin như trước.

Lưu ý về phương pháp: **n = 1 cho mỗi câu**, trên một model ngẫu nhiên. Coi 5/6 là "đã
qua ngưỡng", đừng coi là hằng số. Trong lúc đo có ba lần `Request timed out` từ API —
hạ tầng, không phải logic.

## 13.1 Bộ eval `qa.jsonl` — lần đầu chạy trên dữ liệu thật

Hàng chống hồi quy cuối cùng của §7. Chạy `uv run python -m evals.runner`, 25 câu:

| Chỉ số | Ngưỡng | Kết quả |
|---|---|---|
| Recall@5 | > 0,85 | **0,960** đạt |
| Faithfulness | > 0,9 | **0,980** đạt |
| Latency p95 | < 5.000ms | **11.577ms** TRƯỢT |

*(Số ngày 10/09, trước khi sửa ba câu hỏng và lỗi nhãn ở §16: 0,886 · 0,960 · 11.000.)*

**Độ trễ trượt, và nó KHÔNG nằm ở truy hồi.** Đo riêng tầng truy hồi trên đúng 25 câu
đó: **p50 = 0ms · p95 = 47ms · max = 141ms** (vector câu hỏi có cache, và 179 chunk thì
Postgres quét tuần tự cũng xong ngay). Toàn bộ phần còn lại là một lần gọi
`llm.reply` — tức ngưỡng 5s đang đo **model sinh câu trả lời**, không đo đường tìm kiếm.

Ngưỡng đó đặt từ `plan-thi-cong.md` §10 khi `qa.jsonl` còn là dòng mẫu, nên đây là lần
đầu nó gặp dữ liệu thật. Trước khi đi tối ưu, phải quyết nó đo cái gì: nếu là độ trễ
người dùng cảm nhận thì 5s là sai với `gpt-5-mini` ở `effort=low` cho câu trả lời dài,
và nên tách thành hai ngưỡng — truy hồi và sinh — vì hai thứ này có hai cách sửa hoàn
toàn khác nhau.

Ba câu kéo điểm xuống — và **cả ba đều là lỗi của chính THƯỚC ĐO**, không phải của
truy hồi. Đây là lần thứ ba tài liệu này gặp đúng loại đó (xem §10):

| Câu | Vấn đề thật |
|---|---|
| `q014` *"ingredients needed for BÍ ĐỎ / PUMPKIN"* | Mục đó **không phải công thức** — nó là trang bách khoa về nguyên liệu ("Bí ngô... họ Cucurbitaceae"). Hỏi "nguyên liệu cần cho BÍ ĐỎ" là câu vô nghĩa. |
| `q018` *"...CHUỐI / BANANA"* | Y hệt — trang giới thiệu về cây chuối. |
| `q020` *"...Cameron's Spice Stew"* | `expected_chunk_ids` có **35 phần tử**. Với k=5 thì recall trần của nó là 5/35 = **0,143** — nó không bao giờ đạt được, dù truy hồi có hoàn hảo. |

Bộ eval được sinh máy móc bằng cách coi **mọi tên mục là một món ăn**. Ba câu này không
đo được gì cả, và chúng kéo trung bình xuống ở mọi lần chạy.

**Đã viết tay lại cả ba (11/09/2026)**, bám vào nội dung thật của chunk:

    q014  "Which plant family do pumpkins belong to, and which antioxidants...?"
    q018  "Which plant family does the banana belong to, and which nutrients...?"
    q020  "What equipment and ingredients are needed for Cameron's Spice Stew?"  -> 1 chunk

Recall@5 lên **0,960**. `q014` vẫn trượt, nhưng giờ nó là một cái trượt THẬT: trang bách
khoa về bí đỏ nằm ở d≈0,51 với câu hỏi tự nhiên, trong khi truy vấn kiểu từ khoá tìm ra
nó ở d=0,414. Đáng chú ý là trong bot thật câu đó rơi vào nhánh §12 (0,514 > 0,50), tức
người dùng nhận danh sách để chọn chứ không nhận một câu trả lời sai. Không sửa câu hỏi
cho vừa phép đo — đó là dạy vẹt.

`q020` còn tố cáo một lỗi nạp thật, xem §16.

### 13.2 Runner mất cả lượt chạy vì một lần timeout

Hai lần chạy liên tiếp chết giữa chừng ở `APITimeoutError`, và cả hai lần đều mất sạch
kết quả của những câu đã chạy xong — tức đã trả tiền cho chúng rồi mà không đọc được gì.
Với một job nightly thì đó là kiểu hỏng tệ nhất: chỉ cần một lần mạng chập là không bao
giờ có số liệu.

Đã sửa: câu hỏng được **ghi ra và đếm riêng**, không lặng lẽ chấm 0 — chấm 0 sẽ kéo
trung bình xuống vì một sự cố hạ tầng và biến nó thành một vấn đề chất lượng giả.

## 14. Còn lại, xếp theo đòn bẩy

*Chữ vỡ trong tiêu đề (§15), lỗi nhãn 20% kho (§16) và ba câu eval hỏng (§13.1) đã
xong. Danh sách này là phần chưa làm.*

1. **`RERANK_PROVIDER=fake`.** Cả ba ngưỡng — `RERANK_MIN_SCORE`, `RAG_MAX_DISTANCE`,
   `RAG_HOI_LAI_TU` — đều hiệu chuẩn trên bản xếp theo từ trùng. Cắm cross-encoder thật
   vào là phải đo lại cả ba, và nhiều khả năng vòng hỏi lại sẽ ít khi phải bật.
2. **Mở rộng nhận diện tiêu đề trong `profiles.py`** — phần dư của §16: 4 chunk nội dung
   sô cô la vẫn mang nhãn `Cameron's Spice Stew`. Trần độ dài cắt được 29/33 chunk sai,
   phần còn lại cần bắt được `All About Chocolate`, `Spice Guide`, `Toys, Stuff...`.
3. **`P R E F A C E MỞ ĐẦU`** vẫn là tiêu đề vỡ duy nhất còn lại (§15), và nó đang lọt
   vào top kết quả cho câu hỏi về bí đỏ. Một trang, sửa tay được.
4. **Ngưỡng latency của bộ eval đang đo nhầm thứ** — xem §13.1. Quyết xem nó đo độ trễ
   người dùng hay đo đường tìm kiếm, rồi tách làm hai.
5. **Tần suất hỏi lại** chỉ người dùng thật mới đánh giá được. Hỏi nhiều quá thì hạ
   `RAG_HOI_LAI_TU`; đoán bừa nhiều quá thì nâng lên. Sửa trong `.env`, không đụng code.
6. **§9 (bảng nguyên liệu có cấu trúc)** vẫn chưa làm, và điều kiện để làm cũng không
   đổi: đếm trong `usage_log` xem câu giao tập hợp chiếm bao nhiêu phần trăm câu hỏi
   thật. Vòng người-trong-vòng-lặp vừa hạ giá trị của nó xuống — lớp câu hỏi đó giờ có
   một đường ra không cần bảng nào.


## 15. Chữ vỡ trong tiêu đề — đã sửa 10/09/2026

Không phải nguyên nhân của ba câu eval ở §13.1 (chẩn đoán đầu tiên của bản ghi này sai
ở chỗ đó, đã sửa lại). Nhưng nó có thật, và nó hại ở chỗ khác:

    'Ố C O M / CH UỐ I ĐẬU'                        <- 'ỐC OM / CHUỐI ĐẬU'
    'BRAI SED SNAI LS / W I TH BANANA / AND TO FU' <- 'BRAISED SNAILS / WITH BANANA / AND TOFU'
    'CÁ K H O TH ÂN / CH UỐI NO N'                 <- 'CÁ KHO THÂN / CHUỐI NON'

`section` đi thẳng vào trích dẫn ("theo ..., mục Ố C O M"), vào `tsv`, và — từ §12 — vào
**danh sách ứng viên mà bot đưa cho người dùng chọn**. Thân bài thì chưa bao giờ hỏng;
chỉ riêng dòng tiêu đề đặt co giãn chữ.

**Không đoán lại chỗ ngắt từ.** Không có từ điển thì `Ố C O M` có thể là `ỐCOM`,
`Ố COM` hay `ỐC OM` — đoán là bịa. Thay vào đó đọc lại đúng trang đó bằng
`extraction_mode="layout"`, chế độ giữ bố cục và không làm vỡ tiêu đề, rồi **mượn** dòng
lành. Hai bản là hai lần đọc cùng một trang nên dãy ký tự phải trùng tuyệt đối — chính
đòi hỏi đó làm luật này an toàn.

Vì sao không dùng `layout` cho tất cả: nó dán hai cột song ngữ vào chung một dòng
(`MỨT  CHUỐI          BANANA  CHIPS`), tức thân bài tiếng Việt và tiếng Anh dính vào
nhau — tệ hơn hẳn bản mặc định.

**Một lần làm sai, đáng ghi lại.** Bộ dò đầu tiên đếm "token một chữ cái". Nó vá được
`Ố C O M` (bốn token một chữ) nhưng bỏ sót `BRAI SED SNAI LS`, `TO FU`, `BO I LED` —
vỡ y hệt mà không có chữ cái đơn nào. Phải nạp lại một lần mới lộ ra. Tiêu chí đúng là
**số chỗ ngắt**: cùng dãy ký tự, bản nào ít chỗ ngắt hơn thì ít vỡ hơn — định nghĩa trực
tiếp của "ít vỡ hơn", và nó không cần biết đâu là một từ thật.

Kết quả: 39/39 mục của booklet sạch, trừ `P R E F A C E MỞ ĐẦU` — không tìm được đoạn
tương ứng nên **để nguyên**. Luật chỉ vá cái nó chứng minh được.

Hệ quả đo được trên truy hồi: `dishes with snails and bananas` từ d=0,350 xuống
**d=0,327**, hai kết quả đầu đều đúng món; `dishes with cheese and pasta` kéo được
`Andrew's Macaroni` và `Callamon's Tuna Casserole` lên top-4, trước đó phải nới k=12.

### 15.1 Nạp lại làm chết `qa.jsonl`, hai lần

Nạp lại sinh `chunk_id` MỚI, nên `expected_chunk_ids` thành id chết — bộ eval đo một thứ
không còn tồn tại. Đã ánh xạ lại 15 id bằng nội dung đã bỏ khoảng trắng.

Rồi lần chạy sau lộ ra tàn dư thứ hai: **chính câu hỏi** cũng được sinh từ tên mục hỏng
(`"What ingredients are needed for BO I LED / TARO?"`). Đã sửa 4 câu.

Bài học trùng với §10: sửa dữ liệu thì phải sửa cả thước đo trỏ vào dữ liệu đó, và phải
tìm **hết** các chỗ nó trỏ — id và văn bản là hai chỗ khác nhau.

## 16. Một mục nuốt 20% kho — đã sửa 11/09/2026

`Cameron's Spice Stew` đang gán cho **35 chunk**, trong khi mọi mục khác ≤ 5.

Hồ sơ tài liệu nhận tiêu đề của cookbook tiếng Anh qua mẫu `... from the ... dept.`
(kiểu byline của Slashdot). Phần đuôi sách, trang 69–88, là bài tham khảo —
`All About Chocolate`, `Spice Guide`, `Toys, Stuff, and Other Thingies` — **không có**
mẫu đó, nên mọi chunk thừa kế tiêu đề cuối cùng nhìn thấy.

Hậu quả: bot trích kiến thức bảo quản sô cô la kèm "mục Cameron's Spice Stew", và
20% kho mang nhãn sai. Nó cũng là thứ đặt trần 0,143 cho `q020`.

### Cách sửa: chặn độ dài, không đoán tiêu đề

Mốc của hồ sơ đánh dấu chỗ **bắt đầu** của một mục, không đánh dấu chỗ **kết thúc** —
nên mục cuối cùng ăn hết phần đuôi tài liệu. Đặt trần cho độ dài thân mục, và phần dư
**không bị vứt đi** mà thành một mục **không tên**. "Không biết mục nào" là câu trả lời
trung thực; "Cameron's Spice Stew" thì không.

Trần đặt bằng số liệu chứ không bằng cảm tính:

    cookbook tiếng Anh   trung vị 1.172   p90 3.352   lớn nhất THẬT 8.995
    booklet Sa Pa        trung vị 1.057   p90 2.646   lớn nhất THẬT 5.230
    Cameron's Spice Stew                              62.482   <- gấp 53 lần trung vị

5 chunk = 12.600 ký tự: bỏ lọt mục hợp lệ dài nhất (8.995) thoải mái, và cắt đúng một
ca bệnh. Kết quả: **35 → 6 chunk**, và 29 chunk bị gán sai giờ về đúng trạng thái không
tên (nhóm không tên: 25 → 54).

### Còn dư, và nói rõ

4 trong 6 chunk còn lại **vẫn** là nội dung sô cô la mang nhãn `Cameron's Spice Stew` —
trần 5 chunk cắt được phần lớn nhưng không cắt sạch. Xoá hết cần đường thứ hai: **mở
rộng nhận diện tiêu đề** trong `profiles.py` để bắt `All About Chocolate`, `Spice Guide`,
`Toys, Stuff, and Other Thingies`. Chưa làm, vì nó phải đo lại tỉ lệ chunk có `section`
trên cả hai tài liệu.

Hạ trần xuống 3 chunk thì cắt sạch hơn — nhưng nó sẽ chặt đôi
`How to Prepare Pasta in a Microwave` (8.995 ký tự), một mục hợp lệ. Không đánh đổi.

### 16.1 Checksum không nhìn thấy thay đổi ở CÁCH CẮT

`ingest_file` bỏ qua khi checksum của **văn bản đã trích** không đổi. Sửa `chunk.py` mà
tệp không đổi thì bản vá nằm yên trong mã nguồn và không bao giờ tới được kho đang chạy —
đúng cái bẫy này đã sập khi nạp lại lần đầu.

Đã thêm cờ `ingest --nap-lai` để ép nạp lại. Ghi trong docstring của lệnh, vì người sửa
`chunk.py` hay `clean.py` là người cần biết.
