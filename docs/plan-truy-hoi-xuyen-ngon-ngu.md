# Plan: truy hồi xuyên ngôn ngữ

*10/09/2026. Mọi con số đo trên kho thật đang chạy — 2 tài liệu, 179 chunk, 98 mục có tên.*

> **Đã thi công. Đọc §11 trước §1.**
>
> Phần §1–§10 là bản kế hoạch viết TRƯỚC khi làm. Khi thi công thì mốc **2/6** ở §4
> không tái lập được, và lý do đó quan trọng hơn cả bản kế hoạch: nút thắt thật nằm
> cao hơn một tầng. §11–§16 ghi lại những gì đo được, kể cả ba bản vá đã thử và đã
> phải gỡ bỏ.
>
> §17–§24 (11/09) dựng khung đo RAGAS và bộ golden, rồi cho runner chạy qua đúng
> đường ống thật. §23 lộ ra **12/50 câu model không tra tài liệu lần nào** — lỗi mà
> chế độ đo cũ không bao giờ nhìn thấy được.
>
> §25–§27 là hai LUẬT HỆ THỐNG do người dùng đặt: không trả lời từ trí nhớ, và lệch
> nhau thì lấy công cụ. §26.1 giải thích vì sao một cổng chặn "phải khớp mới trả lời"
> sẽ chặn nhầm đúng những câu trả lời đúng.

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

---

# PHẦN III — khung đo RAGAS và bộ golden dataset

*11/09/2026.*

## 17. Vì sao phải làm bộ dữ liệu trước, rồi mới làm chỉ số

`qa.jsonl` có trường `answer`, nhưng nội dung của nó là `"Cac nguyen lieu liet ke trong
muc 'X'"` — một câu mô tả sinh máy móc từ tên mục, không phải đáp án.

**Context Recall chấm trên đáp án chuẩn**: nó tách đáp án thành từng ý rồi hỏi ngữ cảnh
có đủ căn cứ cho từng ý không. Với một "đáp án" không chứa ý nào, chỉ số đó không đo
được gì. Nên việc 2 là điều kiện tiên quyết của việc 1, không phải việc song song.

Và 22/25 câu cùng một khuôn `"What ingredients are needed for X?"` — bộ eval đang đo
đúng một loại câu hỏi, mà không phải loại đã hỏng suốt phần I.

## 18. `golden.jsonl` — 50 câu viết tay

36 câu tiếng Việt, 14 tiếng Anh, bảy loại. Đáp án đọc ra từ chunk thật.

| loại | n | đo cái gì |
|---|---|---|
| `tra_cuu` | 10 | hỏi thẳng một mục có tên |
| `quy_trinh` | 10 | các bước làm |
| `thuoc_tinh` | 10 | một con số cụ thể: thời gian, nhiệt độ, tỉ lệ |
| `giao_tap_hop` | 8 | "món nào có X và Y" |
| `xuyen_ngon_ngu` | 7 | hỏi tiếng Việt, đáp án chỉ có trong sách thuần Anh |
| `ngoai_kho` | 4 | đáp án đúng là *nói không tìm thấy* |
| `mo_ho` | 1 | đáng ra phải hỏi lại chứ không đoán |

Báo cáo **tách theo loại**. Một trung bình chung giấu mất việc một loại đang hỏng —
đúng kiểu hỏng ngày 10/09: Recall@5 báo 0,886 trong khi lớp câu giao tập hợp đang 0/4,
vì lớp đó chỉ chiếm 3/25 câu nên nó chìm trong trung bình.

### 18.1 `neo` thay cho `expected_chunk_ids`

Mỗi câu mang vài **cụm từ đặc trưng** phải xuất hiện trong ngữ cảnh. Lý do rất cụ thể:
`expected_chunk_ids` **chết mỗi lần nạp lại kho**, và trong hai ngày đã phải ánh xạ lại
hai lần — một lần vì nạp lại sinh id mới, một lần nữa vì chính câu hỏi còn mang tên mục
bị vỡ. Cụm từ thì sống.

Bốn chỉ số RAGAS cũng không đụng `chunk_id` — chúng chấm trên nội dung. Đó là một lý do
kỹ thuật để chuyển sang chúng, không chỉ là chuyện theo chuẩn.

`ops/gan_chunk_id.py` gán lại id từ neo sau mỗi lần nạp, nên Recall@5 vẫn sống mà không
phải ngồi dò tay.

### 18.2 Suýt lặp lại đúng lỗi vừa phê phán

Neo đầu tiên viết cho câu *"món nào dùng cải mèo và khoai sọ"* là `CẢI MÈO` — cụm đó
khớp **13 chunk**. Với k=5 thì recall trần của câu đó là 0,38: nó **không bao giờ** đạt
được, y hệt `q020` mà §13.1 vừa chê. Đã siết neo; giờ tối đa 4 chunk.

Bài học lặp lại lần thứ tư: mỗi lần đụng vào thước đo thì phải đo lại chính thước đo.
85/85 cụm neo đã được đối chiếu với nội dung thật trước khi tin.

### 18.3 Năm chunk mục lục đang đầu độc truy hồi

Khi gán id, ba câu cùng khớp vào chunk 1551-1553. `section` của chúng dài **442 ký tự** —
luật "tiêu đề liền nhau thì GỘP" trong `chunk.py` gặp trang mục lục thì gộp luôn cả danh
sách món thành một `section`.

```
mục thật         <= 64 ký tự
trang mục lục      144, 250, 442   (5 chunk)
```

Hậu quả không chỉ ở bộ eval: **trong hệ thống thật**, năm chunk này mang tên của *mọi*
món nên chúng khớp với bất kỳ câu hỏi nào có tên món trên đường BM25. `gan_chunk_id.py`
loại chúng khi gán, nhưng truy hồi thì chưa. Chưa sửa — xem §22.

## 19. Bốn chỉ số, và ba chỗ cố ý lệch khỏi RAGAS gốc

| chỉ số | bắt kiểu hỏng nào |
|---|---|
| Context Recall | ngữ cảnh có **đủ** dựng nên đáp án chuẩn không |
| Context Precision | lấy về có đúng việc không, **và có xếp lên trên không** |
| Faithfulness (ý) | bot có bịa không — đếm từng ý |
| Answer Relevance | câu trả lời có đúng trọng tâm không |

**Lệch 1 — câu thoái thác không bị chấm 0.** RAGAS gốc chấm 0 cho câu "tôi không biết".
Bot này được thiết kế để nói *"không tìm thấy trong tài liệu"* khi kho không có, và
`faithfulness.py` chấm hành vi đó 1,0 vì nó trung thực. Áp nguyên luật RAGAS thì bộ eval
sẽ **thưởng cho việc bịa** và **phạt câu trả lời trung thực** — ngược hẳn thứ dự án này
muốn. Câu thoái thác trả `None` và bị loại khỏi trung bình.

**Lệch 2 — Context Precision gọi model một lần cho cả k đoạn**, không phải k lần. Bản gốc
là 250 lần gọi mỗi đêm với 50 câu, trên một bộ eval mà chính runner ghi là "CHAY TON TIEN
THAT". Đổi lại: người chấm nhìn cả 5 đoạn cùng lúc nên so được chúng với nhau — vừa là
điểm yếu (một đoạn tệ trông khá hơn khi đứng cạnh đoạn tệ hơn) vừa là điểm mạnh (độ liên
quan vốn là một khái niệm so sánh).

**Lệch 3 — giữ cả hai bản faithfulness.** Bản cũ cho điểm tổng 1,0/0,5/0,0; bản mới đếm
từng ý. Không thay thế, vì đổi cách đo sẽ làm mọi con số cũ hết so sánh được. Và giữ cả
hai cho thêm một thứ: xem hai người chấm có đồng ý không.

Lần chạy đầu cho thấy họ **không** đồng ý: 0,870 so với 0,930. Chênh lệch dồn vào nhóm
`quy_trinh` (bản tổng 0,700 trong khi ctx_recall 0,900) — bốn câu quy trình bị bản tổng
chấm 0,5 dù ngữ cảnh đầy đủ. Đó là vấn đề hiệu chuẩn **của người chấm**, chưa có bằng
chứng nào nói bot sai.

## 20. Lần chạy đầu — 11/09/2026, 50 câu

```
  TRUOT Faithfulness           0.870   (nguong 0.9)
  TRUOT Latency p95 (ms)      14031    (nguong 5000)
  ....  Neo trong ngu canh     0.864

RAGAS:
  DAT   Context Recall         0.857   (nguong 0.85, bo qua 2)
  DAT   Context Precision      0.801   (nguong 0.70, bo qua 3)
  DAT   Faithfulness (y)       0.930   (nguong 0.90, bo qua 3)
  ....  Answer Relevance       0.646   (tham khao, chua hieu chuan)
```

Bốn câu chết vì `APITimeoutError`, đếm riêng, không tính vào chỉ số nào.

**Bảng theo loại mới là thứ đáng đọc:**

| loại | n | faith | ctx_recall | ctx_prec | neo |
|---|---|---|---|---|---|
| `thuoc_tinh` | 10 | 1,000 | **1,000** | 0,933 | 1,000 |
| `tra_cuu` | 10 | 1,000 | **0,988** | 0,882 | 1,000 |
| `quy_trinh` | 10 | 0,700 | 0,900 | 0,809 | 0,900 |
| `giao_tap_hop` | 8 | 1,000 | **0,625** | 0,599 | 0,625 |
| `xuyen_ngon_ngu` | 5 | 0,500 | **0,600** | 0,625 | 0,600 |

Hai nhóm yếu hẳn là `giao_tap_hop` và `xuyen_ngon_ngu` — và đó **chính là hai nhóm mà
phần I đã sửa**. Trước khi kết luận bản sửa không ăn thua, phải đọc §21.

### 20.1 Answer Relevance không làm cổng chặn

0,646, dưới ngưỡng mượn 0,75. Nhưng nó là cosine giữa câu hỏi thật và các câu hỏi đoán
ngược từ câu trả lời, và **trị tuyệt đối của cosine phụ thuộc model nhúng và ngôn ngữ**.
Bộ này 36/50 câu tiếng Việt; 0,646 hoàn toàn có thể là mức bình thường của
`text-embedding-3-large` trên tiếng Việt chứ không phải dấu hiệu lạc đề. Chưa ai đo.

Đặt một ngưỡng mượn rồi để job đêm đỏ thường trực thì tệ hơn là không đặt — chính
`evals.yml` đã viết câu đó. Nên nó là dòng tham khảo, và điều kiện để thành cổng chặn ghi
thẳng trong `runner.py`: khoảng 5 lần chạy để biết nó dao động bao nhiêu.

## 21. Bộ eval đang đo MỘT ĐƯỜNG ỐNG KHÁC với đường chạy thật

Đây là phát hiện quan trọng nhất của đợt này, và nó làm mọi con số ở §20 phải đọc lại.

`runner.run_one()` gọi **thẳng** `knowledge.search(scope, row.question, K)` — đẩy nguyên
văn câu hỏi tiếng Việt vào truy hồi.

Đường chạy thật thì không vậy. Từ bản sửa ngày 10/09, model **tự viết truy vấn bằng tiếng
Anh** rồi mới gọi `search_knowledge_base`:

```
người dùng:  "Món nào dùng phô mai và mì ống?"
model viết:  "dishes that use cheese and pasta"      <- eval KHÔNG đi qua bước này
```

Nên bộ eval đo *"truy hồi tốt đến đâu khi nhận nguyên văn câu hỏi người dùng"* — đúng
thiết kế ban đầu, từ thời chưa có công cụ. Sau khi có công cụ, nó không còn đo cái
production làm.

Bằng chứng trực tiếp: `g031` *"Món nào dùng phô mai và mì ống?"* ở đây được
`ctx_recall = 0,00`. Cùng câu đó, chạy đầu-cuối qua bot thật ở §13, lấy đúng cả hai chunk
đáp án.

Hệ quả: **15/50 câu** (`giao_tap_hop` + `xuyen_ngon_ngu`) đang đo một đường mà production
không dùng, và chúng là hai nhóm điểm thấp nhất bảng. Con số 0,625 và 0,600 là **cận
dưới**, không phải chất lượng thật.

Hai đường sửa, chưa chọn:

1. **Thêm chế độ `--qua-cong-cu`** cho runner, chạy qua `handle_message` như §11 đã làm
   bằng script rời. Đo đúng thứ production làm. Đắt hơn và ồn hơn: model có thể gọi công
   cụ nhiều lần hoặc không gọi lần nào, nên độ trễ hết so sánh được với các lần trước.
2. **Giữ nguyên và đọc cho đúng**: đây là chỉ số của *tầng truy hồi*, không phải của *trợ
   lý*. Lúc đó phải đổi tên nhóm `xuyen_ngon_ngu`, vì thật ra nó đang đo "truy hồi xuyên
   ngôn ngữ KHÔNG có bước dịch" — một phép đo hợp lệ, chỉ không phải phép đo người ta
   tưởng khi đọc bảng.

**ĐÃ CHỌN VÀ ĐÃ LÀM — phương án 1, xem §23.** Và chế độ mới lộ ra một lỗi lớn hơn chính
lỗi nó được dựng lên để sửa.

## 22. Còn lại sau đợt này

1. **Chọn giữa hai đường ở §21.** Cho tới lúc đó bảng theo loại chỉ đọc được năm hàng trên.
2. **Năm chunk mục lục** (§18.3) đang khớp mọi câu hỏi có tên món trên đường BM25. Sửa ở
   `chunk.py`: đừng gộp tiêu đề liền nhau khi chúng đến từ trang mục lục.
3. **Hiệu chuẩn Answer Relevance** — cần khoảng 5 lần chạy.
4. **Người chấm tổng đang khắt khe với câu quy trình** (§19, lệch 3). Bốn câu bị chấm 0,5
   dù ngữ cảnh đầy đủ. Đọc bốn câu đó rồi sửa `JUDGE_INSTRUCTION`, hoặc bỏ bản tổng.
5. **`RERANK_PROVIDER=fake`** vẫn đứng đầu danh sách của §14 và không đổi.

## 23. Đã sửa §21 — và chế độ mới lộ ra một lỗi lớn hơn

`--qua-cong-cu` chạy qua `handle_message`, tức model tự viết truy vấn rồi mới gọi
`search_knowledge_base`. Bọc `ToolPort` bằng một lớp ghi lại, không vá đè lên nội tạng
của `tools/registry.py` — `Deps.tools` vốn đã là một chỗ nối được thiết kế sẵn.

Ngữ cảnh đem đi chấm là **văn bản công cụ trả về**, tức đúng thứ model nhìn thấy, chứ
không phải một bản ghép lại từ chunk.

### 23.1 Hai chỗ nó bắt được, đúng như dự đoán

| loại | trực tiếp | qua công cụ |
|---|---|---|
| `giao_tap_hop` | 0,625 | **0,938** |
| `xuyen_ngon_ngu` | 0,600 | **0,857** |

Bản sửa ngày 10/09 **có tác dụng thật**, và chế độ mặc định không thể nhìn thấy nó. Truy
vấn model tự viết, chép từ log:

```
"Sữa bí đỏ cần những nguyên liệu gì?"   ->  'pumpkin milk recipe ingredients'
"Món nào dùng phô mai và mì ống?"       ->  'recipes with cheese and pasta'
"Chính sách nghỉ phép năm..."           ->  'annual leave entitlement days'
```

### 23.2 Và hai chỗ nó phá vỡ, ngoài dự đoán

| loại | trực tiếp | qua công cụ |
|---|---|---|
| `thuoc_tinh` | 1,000 | **0,500** |
| `quy_trinh` | 0,900 | **0,520** |
| `tra_cuu` | 0,988 | **0,686** |

**12/50 câu model KHÔNG gọi công cụ lần nào.** Nó trả lời thẳng từ trí nhớ, không nguồn:

```
g015  "Nấu sữa bí đỏ thì luộc bí trong bao lâu?"
g021  "Làm thế nào để khoai sọ bớt ngứa khi sơ chế?"
g022  "Làm sao cho chuối xanh bớt chát?"
g014  "How long do I microwave the pasta?"
g019  "Luộc tai heo bao lâu khi làm nộm hoa chuối?"
```

Đây **đúng là cái bẫy của §11**, chỉ khác hình dạng câu hỏi. Mô tả công cụ hiện gọi tên
cạm bẫy "câu hỏi NGƯỢC — hỏi từ đặc điểm ra tên". Nhưng *"luộc bao lâu"* và *"làm sao
cho bớt chát"* không phải câu hỏi ngược — chúng trông y hệt **kiến thức nấu ăn phổ
thông**, và model tự tin trả lời từ trí nhớ.

Tái lập được: chạy lại riêng bốn câu thì `g015`, `g021`, `g022` vẫn không gọi, còn
`g046` thì có.

### 23.3 Điều này nói gì về hai chế độ

Chúng **không thay thế nhau, và cũng không phải cái này đúng hơn cái kia**:

- Chế độ mặc định đo **tầng truy hồi**. Nó luôn tra, nên nó không bao giờ thấy được lỗi
  "model không thèm tra".
- Chế độ qua công cụ đo **trợ lý thật**. Nó thấy lỗi đó, nhưng khi model không tra thì
  nó không nói được gì về chất lượng truy hồi.

Hai nhóm `thuoc_tinh` và `quy_trinh` đạt 1,000 và 0,900 ở chế độ mặc định — trông hoàn
hảo — trong khi **quá nửa số câu đó ngoài đời chưa từng chạm tới tài liệu**. Một bộ eval
chỉ chạy chế độ mặc định sẽ báo xanh mãi mãi cho một lỗi như vậy.

Nên job đêm chạy `--qua-cong-cu` (đo cái người dùng nhận được), còn chế độ mặc định giữ
lại để tách bạch: truy hồi kém, hay là chưa từng truy hồi.

### 23.4 Hai quả mìn gỡ được khi làm

**`DM_POLICY` mặc định là `pairing`.** Chế độ mới sinh `thread_id` mới cho mỗi câu, nên
tầng truy cập sẽ chặn sạch — `handle_message` trả về "không trả lời", và bộ eval sẽ chấm
50 chuỗi rỗng rồi in ra một báo cáo sai một cách tự tin. Máy này có `.env` đặt `open` nên
không thấy gì; **CI thì không đặt**, và `evals.yml` vừa được vá. Runner giờ ném lỗi khi
câu trả lời rỗng, thay vì chấm nó.

**`RL_USER_PER_MIN = 10`, mà CLI dùng đúng một `sender_id` cố định.** Ở tốc độ hiện tại
(~1,4 câu/phút) chưa chạm, nhưng hôm nào API nhanh lên thì bộ eval sẽ lặng lẽ đo bộ chặn
tần suất. Mỗi câu giờ mang `sender_id` riêng.

## 24. Việc tiếp theo, đã đổi thứ tự

1. **Mô tả công cụ chưa bao được câu "bao lâu / làm sao"** (§23.2). Đây là việc đòn bẩy
   cao nhất bây giờ: 12/50 câu đang trả lời không nguồn. Cách sửa đã có tiền lệ đo được
   ở §11 — gọi tên thêm một hình dạng câu hỏi, kèm ví dụ, và đo lại bằng
   `--qua-cong-cu`.
2. **`ngoai_kho` tụt còn 0,625** ở chế độ mới. Cần đọc bốn câu đó: có thể model đang
   dùng `web_search` để trả lời câu nội bộ — đúng thứ `_KHONG_TIM_THAY` được viết ra để
   ngăn.
3. Các mục còn lại của §22 giữ nguyên thứ tự.

---

# PHẦN IV — hai luật hệ thống về nguồn của câu trả lời

*11/09/2026. Cả hai do người dùng đặt ra thành luật, không phải suy ra từ phép đo.*

## 25. Luật 1 — không trả lời từ trí nhớ

> *"Không được trả lời từ trí nhớ, cần phải thông qua công cụ."*

Luật này **đã có sẵn** trong `SYSTEM_PROMPT` từ trước. Nó vẫn hỏng, và §23.2 đo được
12/50 câu model không gọi công cụ lần nào.

Lý do bản cũ không ăn giống hệt lý do mô tả công cụ hỏng hôm 10/09: nó buộc điều kiện
theo **sự tự tin** của model — *"kể cả câu bạn nghĩ mình đã biết"*. Với lớp câu này
model **luôn** tự tin, nên điều kiện đó tự vô hiệu đúng lúc cần nhất. Đây là lần thứ
hai cùng một cơ chế làm hỏng cùng một luật ở hai chỗ khác nhau.

Bản mới bỏ hẳn điều kiện, và gọi tên hai hình dạng câu hỏi hay bị bỏ qua — hỏi **một
con số** (*bao lâu, mấy độ*) và hỏi **một cách làm** (*làm sao để…*). Mô tả công cụ
nhận thêm hình dạng thứ hai này kèm một ví dụ cố ý nằm ngoài bộ đo.

Đo trên 52 câu, chế độ `--qua-cong-cu`:

| | trước | sau |
|---|---|---|
| Model gọi công cụ | 38/50 | **48/50** |
| Faithfulness | 0,630 | **0,880** |
| Faithfulness (ý) | 0,664 | **0,935** |
| Context Recall | 0,664 | **0,834** |
| Neo trong ngữ cảnh | 0,630 | **0,804** |
| `thuoc_tinh` ctx_recall | 0,500 | **0,900** |
| `quy_trinh` ctx_recall | 0,520 | **0,700** |

Không dòng nào được **thêm** vào `SYSTEM_PROMPT` — trần tầng `system` lúc đó chỉ còn
137 ký tự. Luật mới là bản **viết lại** của dòng cũ.

## 26. Luật 2 — lệch nhau thì lấy công cụ

> *"Chạy công cụ và có thể cả dùng bộ nhớ. Nếu câu hỏi chưa có trong bộ nhớ thì ưu
> tiên công cụ lấy thông tin mới nhất. Lệch nhau thì lấy trực tiếp từ công cụ."*

### 26.1 Một cổng chặn "phải khớp mới trả lời" sẽ chặn nhầm

Cách hiểu đầu tiên của đề xuất này là một cổng chặn: hai nguồn khớp mới được trả lời.
Nó nghe an toàn và nó **sai hướng**:

> *"Nghỉ phép năm được bao nhiêu ngày?"* — trí nhớ model nói 12 (luật lao động chung),
> tài liệu công ty ghi 15. Cổng chặn sẽ làm bot im lặng **đúng lúc nó đang cầm câu trả
> lời đúng**.

Tài liệu nội bộ khác kiến thức chung là chuyện **bình thường** — đó chính là lý do tổ
chức nạp tài liệu vào. Trí nhớ model không có thẩm quyền phủ quyết nó.

Đã chốt: **không chặn, lệch thì lấy công cụ.**

### 26.2 "Bộ nhớ" trong hệ thống này không phải kho đáp án

Cần nói rõ để không ai kỳ vọng nhầm. Bộ nhớ ở đây là:

```
L1   tin nhắn gần đây của thread
L2   tóm tắt hội thoại
L3   memory_fact — sự việc về NGƯỜI trong nhóm, mặc định TẮT
```

Nó **không** lưu đáp án đã tra. Với *"Luộc khoai sọ bao lâu?"* thì bộ nhớ không có gì
cả, nên theo chính luật này công cụ thắng — tức trùng với luật 1.

Chỗ luật 2 thật sự có tác dụng là khi hai bên **cùng có** và **mâu thuẫn**: một fact ai
đó lưu bằng `nhớ giúp:` từ tháng trước, còn tài liệu thì mới hơn.

### 26.3 Thứ tự tin cậy, viết vào `SYSTEM_PROMPT`

```
TÀI LIỆU NỘI BỘ  >  bộ nhớ đã lưu và hội thoại cũ  >  trí nhớ của model  >  web
```

Mâu thuẫn thì tài liệu thắng **và vẫn trả lời**, không im lặng, không hỏi lại.

Lại phải cắt trước khi thêm: trần tầng `system` còn 25 ký tự. Đã bỏ một dòng ở mục
OUTPUT FORMAT lặp lại nguyên luật đã có ở RULES — và công cụ cũng tự nói điều đó trong
`_KHONG_TIM_THAY`, đúng khoảnh khắc model vừa thấy kết quả rỗng. Còn 12 ký tự.

### 26.4 Đo luật này bằng chính mâu thuẫn có sẵn trong kho

Luật chống mâu thuẫn mà không có câu hỏi mâu thuẫn nào thì không đo được gì. Kho có
sẵn hai chỗ tự mâu thuẫn, và chúng là phép thử tốt:

```
SỮA BÍ ĐỎ    nguyên liệu ghi "Sữa đặc: 20ml"      cách làm ghi "400ml sữa đặc"
MỨT CHUỐI    bản tiếng Việt "200ml nước chanh"     bản tiếng Anh "20ml lemon juice"
```

Con số tiếng Việt của MỨT CHUỐI còn không cộng ra được: 200 + 30 + 480 = 710, trong
khi tài liệu nói đó là tỉ lệ cho 500ml.

Đây đúng là chỗ model dùng phán đoán riêng sẽ **âm thầm "sửa" cho hợp lý**, và người
dùng không bao giờ biết tài liệu của họ có vấn đề. Câu trả lời đúng là **nói ra cả
hai con số**. Hai câu này vào bộ golden thành nhóm `xung_dot`.

### 26.5 Phần chưa đo được

Đường **L3 fact mâu thuẫn với tài liệu** hiện chỉ là một luật trong prompt, chưa có
phép đo. Muốn đo thì phải gieo sẵn fact vào `memory_fact` rồi hỏi một câu mà tài liệu
nói khác — chưa làm. `MEMORY_IMPLICIT_ENABLED` đang tắt nên trong thực tế đường này
hiếm khi chạy tới.

## 27. Một chỉ số phạt nhầm đúng thứ vừa sửa được

Sau khi bật luật 1, nhóm `ngoai_kho` có Context Precision tụt còn **0,250**.

Không phải hồi quy. Câu ngoài kho thì **không có** đoạn nào liên quan tồn tại, nên khi
bot bắt đầu chịu đi tra, mọi đoạn lấy về đều không liên quan — và đó là hành vi ĐÚNG.
Chỉ số đang phạt đúng cái vừa sửa được.

Đã loại `ngoai_kho` khỏi Context Precision, y như đã loại khỏi Context Recall. Đúng/sai
của nhóm đó do Faithfulness chấm: nói "không tìm thấy" khi kho không có được 1,0.

## 28. Lần đo sau luật 2 — và vì sao KHÔNG được đọc nó như một hồi quy

52 câu, chế độ `--qua-cong-cu`:

```
  Model tu viet truy van   50/52
  Faithfulness             0,798
  Context Recall           0,781   (bo qua 4)
  Context Precision        0,826   (bo qua 6)
  Faithfulness (y)         0,876   (bo qua 1)
```

Nhóm `xung_dot` mới thêm: **ctx_recall 1,000 · ctx_prec 1,000 · neo 1,000**. Hai câu
mâu thuẫn được truy hồi hoàn hảo. `ngoai_kho` giờ hiện `—` ở cột precision, đúng như
§27 đã sửa.

Nhưng vài chỉ số **tụt** so với lần chạy trước luật 2, và nhóm `xuyen_ngon_ngu` tụt
mạnh nhất: faith 0,786 → **0,357**. Đừng đọc con số đó là hồi quy.

### 28.1 Người chấm coi bản DỊCH là bịa

Đo lại riêng bảy câu `xuyen_ngon_ngu`:

```
  Context Recall   0,857     <- ngu canh PHU DU dap an
  Faithfulness     0,357     <- nguoi cham van cham truot
```

Năm trong bảy câu có `ctx_recall = 1,00` mà vẫn bị chấm 0,5. Ngữ cảnh đủ, câu trả lời
bám ngữ cảnh, mà vẫn trượt — đó là mẫu hệ thống, không phải nhiễu.

Nguyên nhân nằm trong chính `faithfulness.py`: `JUDGE_INSTRUCTION` của nó **không có**
điều khoản song ngữ, trong khi `claim_faithfulness.py` viết sau thì có. Kho phần lớn
tiếng Anh, bot trả lời tiếng Việt, nên người chấm thấy mọi chi tiết đều "không có
trong tài liệu". Và `xuyen_ngon_ngu` đúng là nhóm bị nặng nhất — hỏi tiếng Việt, đáp
án chỉ nằm trong sách thuần Anh.

Đã thêm điều khoản đó. Đo lại bảy câu: danh sách câu kéo điểm co từ 6 xuống 4, `g039`
và `g042` thoát ra. **Nhưng ba câu vẫn 0,5 dù ngữ cảnh đầy đủ**, nên bản dịch không
phải toàn bộ câu chuyện. Chưa truy tiếp.

Bản vá này làm **mọi con số faithfulness trước 11/09/2026 hết so sánh được**. Đó là cái
giá phải trả để chỉ số thôi nói dối, và nó được ghi ngay trong docstring của tệp.

### 28.2 Biên độ dao động lớn hơn phần lớn chênh lệch ta đang đọc

Hai lần chạy **cùng một câu, cùng một mã nguồn**:

```
g043  "Món bánh pudding sô cô la làm thế nào?"   ctx_recall  1,00  ->  0,00
```

Không phải trường hợp cá biệt: `g031` đã dao động qua nhiều lần chạy suốt hai ngày, và
mỗi lần chạy lại có 1-4 câu chết vì `APITimeoutError` khác nhau.

Hệ quả cho người đọc tài liệu này: **một chênh lệch dưới khoảng 0,1 trên một nhóm bảy
câu không nói lên điều gì.** Muốn kết luận thì phải chạy lại vài lần, hoặc nhóm phải
đủ lớn. Các con số trong tài liệu này là n = 1 cho mỗi câu, và chúng được ghi để so
ĐỘ LỚN chứ không phải để so từng phần trăm.

Đây cũng là lý do `Answer Relevance` vẫn chưa làm cổng chặn (§20.1): điều kiện của nó
là khoảng 5 lần chạy, chính vì lý do này.

## 29. Việc còn lại, cập nhật 11/09 cuối ngày

1. **Ba câu `xuyen_ngon_ngu` vẫn bị chấm 0,5 dù ngữ cảnh đầy đủ** (§28.1). Đọc thẳng
   ba câu trả lời đó rồi quyết: người chấm còn thiếu điều khoản gì, hay bot thật sự
   đang thêm chi tiết ngoài tài liệu.
2. **`quy_trinh` có ctx_recall 0,517** trong khi model CÓ gọi công cụ. Tức truy hồi
   trượt, không phải quên tra — khác hẳn lỗi §23.2 và cần cách sửa khác. Ba câu
   "làm sao cho bớt chát / bớt ngứa / khử mùi hôi" đều 0,00.
3. **Chạy lại vài lần để biết biên độ dao động** (§28.2), trước khi tin bất kỳ chênh
   lệch nhỏ nào trong tài liệu này.
4. **Năm chunk mục lục** (§18.3) và **`RERANK_PROVIDER=fake`** (§14) vẫn nguyên vị trí.

## 30. `quy_trinh` không phải truy hồi trượt — mà là vòng hỏi lại bắn nhầm

Chẩn đoán ở §29 mục 2 **sai**. Chạy thẳng ba câu qua `handle_message` và in ra mọi thứ
model thấy, thay vì đọc con số:

```
[g022] "Làm sao cho chuối xanh bớt chát?"
  TRUY VAN  : 'reduce astringency green bananas how to remove bitterness before cooking'
  CONG CU   : KẾT QUẢ KHÔNG CHẮC — ... Hãy đưa NGUYÊN danh sách dưới đây ...
  BOT       : 1. BRAISED SNAILS  2. MỨT CHUỐI  3. CANH CHUỐI XANH  ...  8. Khác
              Bạn chọn mục nào?
```

Truy vấn model viết **rất tốt**. Truy hồi cũng không trượt. Cái chạy là **vòng hỏi lại
của §12** — và nó hỏi sai thứ.

Câu *"làm sao cho bớt chát"* không mơ hồ về **món nào**. Nó là câu hỏi **kỹ thuật**, và
đáp án (ngâm chanh + giấm) giống nhau ở mọi món — chính vì thế mà nhiều ứng viên cùng
về và khoảng cách cao. Bắt người dùng chọn một món là trả lời một câu họ không hỏi.

Và model **không thể** nhận ra điều đó, vì danh sách chỉ đưa **TÊN**, kèm một câu cấm
thẳng: *"ĐỪNG trả lời bằng nội dung các mục này."*

### 30.1 Bản sửa: cho model nhìn thấy nội dung, và nêu rõ hai nhánh

Danh sách giờ kèm trích đoạn 240 ký tự mỗi mục, và kết quả công cụ nói rõ:

```
CÓ    — các mục cùng nói MỘT điều      -> TRẢ LỜI LUÔN, nêu nguồn, ĐỪNG hỏi lại
KHÔNG — mỗi mục một đáp án riêng       -> đưa danh sách ra hỏi, KHÔNG kèm trích đoạn
```

Đo sau khi sửa, cùng câu g022:

> *"Gọt vỏ, cắt miếng rồi ngâm chuối trong nước có pha chanh hoặc giấm… (theo kho tài
> liệu nội bộ, mục CANH CHUỐI XANH / HẦM XƯƠNG và CÁ KHO THÂN / CHUỐI NON)"*

Đúng đáp án chuẩn, kèm nguồn. Và `g031` *"Món nào dùng phô mai và mì ống?"* vẫn ra danh
sách như cũ — hai nhánh không đạp nhau.

Lý do cũ của luật cấm vẫn đúng một nửa: đưa nội dung ra thì model có thể tự chọn lấy
một mục rồi trả lời, làm vòng hỏi lại thành vô nghĩa. Nhánh KHÔNG giữ nguyên rào đó.

### 30.2 Việc chọn nhánh KHÔNG tất định

Hai lượt trên cùng câu g022: một lượt trả lời thẳng, một lượt hỏi lại
*"Bạn muốn cách xử lý chung hay cách cho từng món cụ thể?"* — câu hỏi này hợp lý, chỉ
là không tất định. Đừng mong một nhánh cố định cho một câu hỏi cố định.

## 31. Luật cứng chỉ giữ được khoảng một nửa cho lớp câu này

Đây là chỗ phải nói thẳng, vì con số tổng đang đẹp hơn sự thật.

Lần chạy đủ bộ cho **50/52 câu có gọi công cụ**. Nhưng đó là một lần rút. Chạy lặp
riêng hai câu `g022`, `g023` — đúng hình dạng *"làm sao… / khử mùi…"* — ba lượt:

```
lượt 1   g022 KHÔNG gọi   g023 KHÔNG gọi
lượt 2   g022 có gọi      g023 có gọi
lượt 3   g022 KHÔNG gọi   g023 có gọi
                                      -> 3/6
```

Khi không gọi, câu trả lời là **kiến thức phổ thông thuần tuý**: *"ngâm nước vôi trong"*,
*"baking soda"* — không có chữ nào trong tài liệu. Đúng thứ luật §25 cấm.

### 31.1 Truy vấn còn bị nhiễm định kiến

Ngay cả khi có gọi, model nhét sẵn giả thuyết của nó vào truy vấn:

```
'how to remove astringency from green bananas soak salt water vinegar boiling baking soda'
'cách khử mùi hôi tai heo mẹo khử mùi tai heo luộc rửa bằng giấm muối baking soda'
```

Nó đang đi **tìm xác nhận** cho thứ nó đã tin, chứ không đặt câu hỏi mở. Truy vấn dài
và lệch như vậy còn kéo khoảng cách lên, tức làm chính vòng hỏi lại dễ bắn hơn.

### 31.2 Chỉnh câu chữ đã tới hạn

Lớp câu này đã được đánh ba lần, mỗi lần ở một tầng khác nhau:

```
mô tả công cụ   gọi tên cạm bẫy "MỘT CON SỐ / MỘT CÁCH LÀM" + ví dụ
SYSTEM_PROMPT   luật cứng, bỏ điều kiện theo sự tự tin
kết quả công cụ hai nhánh CÓ / KHÔNG
```

Tổng thể tiến rất xa (12/50 câu không tra → 2/52). Nhưng riêng hình dạng này vẫn 3/6,
và nó là hình dạng mà model có định kiến mạnh nhất. **Bản sửa tiếp theo không nên là
một câu chữ nữa.** Hai hướng có thật:

1. **Bắt buộc gọi công cụ ở tầng vòng lặp**, không để model tự quyết: với câu hỏi có
   dữ kiện, chặn lượt trả lời đầu nếu chưa có lần gọi `search_knowledge_base` nào.
   Đây là thay đổi kiến trúc, không phải prompt, nên nó cần một quyết định riêng.
2. **Nâng `effort` cho route `reply`.** Ghi chú trong `llm/models.py` nói đã thử
   `effort="medium"` ngày 07/09 và nó TỆ HƠN — nhưng phép đo đó có trước mọi thứ ở
   đây, và nó không đo tỉ lệ gọi công cụ.

Cho tới khi làm một trong hai, **đừng đọc con số 50/52 như một bảo đảm**: nó là một lần
rút từ một phân phối mà lớp câu này chỉ đạt khoảng một nửa.

## 32. Kết quả sau bản vá vòng hỏi lại

52 câu, `--qua-cong-cu`:

| | trước §30 | sau |
|---|---|---|
| `quy_trinh` ctx_recall | 0,517 | **0,900** |
| `giao_tap_hop` ctx_recall | 0,958 | **1,000** |
| `giao_tap_hop` faith | 0,875 | **1,000** |
| Context Recall | 0,781 | **0,835** |
| Context Precision | 0,826 | **0,902** |
| Neo trong ngữ cảnh | 0,750 | **0,812** |

Nhóm `giao_tap_hop` không hề hồi quy vì nhánh KHÔNG — nó còn lên tuyệt đối. Đây là
bằng chứng hai nhánh không đạp nhau.

## 33. `xuyen_ngon_ngu` faith 0,500 — một nửa là lỗi thước đo

Nhóm này vẫn faith 0,500 trong khi `ctx_recall = 0,857`. Đọc thẳng hai câu thay vì
đọc con số, và chúng hoá ra **khác hẳn nhau**:

### 33.1 `g045` — bot sai thật

```
"Món cánh gà cay làm sao?"
  TRUY VAN : []                    <- KHONG goi cong cu
  BOT      : "Nguyên liệu: 1 kg cánh gà, 2 muỗng canh tương ớt, 1 muỗng canh
              nước mắm, 1 muỗng canh mật ong..."
```

Bịa nguyên một công thức Việt Nam, trong khi tài liệu có `John's Easy Boneless Hot
Wings`. faith 0,00 là **chấm đúng**. Đây là lỗi §31 — luật cứng chỉ giữ được một nửa.

### 33.2 `g041` — người chấm sai

```
"Làm sao biết bít tết đã chín tới?"
  TRUY VAN : 'how to tell steak doneness'
  NGU CANH : 5683 ky tu | co '145'=True | co 'slit'=True | co 'Medium-rare'=True
  BOT      : "Dùng nhiệt kế: medium-rare khoảng 145°F (≈63°C)... rạch một khe nhỏ ở
              giữa: medium-rare rất hồng với viền hơi nâu (theo
              The_Open_Source_Cookbook_v0.4 — mục: How To Cook a Steak)"
```

Câu trả lời bám tài liệu **hoàn toàn**, trích nguồn đúng. Vẫn bị chấm 0,00.

Cơ chế: bot quy đổi `145°F ≈ 63°C`. Con số **63 không có** trong tài liệu, nên người
chấm coi đó là bịa. Đổi đơn vị không phải bịa — đã thêm điều khoản cho cả hai bản
chấm: giá trị quy đổi hoặc suy trực tiếp từ tài liệu vẫn tính là CÓ.

### 33.3 Không chứng minh được bản vá này có tác dụng

Phải nói thẳng: sau khi thêm điều khoản quy đổi, đo lại bảy câu vẫn ra **0,571** —
đúng bằng lần trước đó. Một lần chạy không đủ để nói bản vá có ăn hay không, vì biên
độ dao động (§28.2) lớn hơn hiệu ứng đang tìm.

Cái **chắc chắn** là: một trường hợp cụ thể đã được kiểm tận gốc và người chấm sai ở
đó. Cái **chưa chắc** là bản vá có nhấc được con số tổng hay không. Hai điều đó khác
nhau, và tài liệu này ghi cả hai.

Tới đây thì việc chỉnh người chấm nên DỪNG cho tới khi có §29 mục 3 — vài lần chạy để
biết biên độ. Chỉnh tiếp bằng n = 1 chỉ là đuổi theo nhiễu.

---

# PHẦN V — chốt chặn ở tầng vòng lặp

*11/09/2026. §31.2 nói bản sửa tiếp theo không nên là một câu chữ nữa. Đây là nó.*

## 34. Chặn 7 — chưa tra mà đã định trả lời

Vòng ReAct có sáu chặn cứng (số vòng, deadline, ngân sách, trần observation, người
dùng bấm dừng). Nay có chặn thứ bảy: **model định kết thúc lượt mà chưa gọi
`search_knowledge_base` lần nào** thì nhận một lời nhắc và được cho đi tiếp.

Vì sao ở tầng này chứ không phải thêm chữ vào prompt: lớp câu *"làm sao… / khử mùi…"*
đã bị đánh ở **cả ba tầng** câu chữ — mô tả công cụ gọi tên cạm bẫy, `SYSTEM_PROMPT`
có luật cứng, kết quả công cụ nêu hai nhánh — và nó **vẫn chỉ giữ được một nửa**
(§31). Chỉnh tiếp câu chữ là đuổi theo một thứ đã tới hạn.

Đo trên `handle_message` thật, ba lượt, hai câu:

```
                      trước    sau
g022 "làm sao cho bớt chát"     3/6     6/6
g023 "cách khử mùi hôi"
```

### 34.1 Bốn ràng buộc, mỗi cái chặn một kiểu hỏng

**Nhắc đúng MỘT lần.** Nhắc lại nhiều lần là dựng lại đúng vòng lặp mà luật 07/09 được
lập ra để chặn — bot cứ hỏi/nhắc mãi mà không làm gì.

**Không nhắc ở vòng cuối.** Vòng cuối không còn vòng nào để đọc kết quả trả về, nên
nhắc chỉ tốn một lượt gọi model mà vẫn ra đúng câu trả lời đó.

**Không nhắc khi kho chưa có tài liệu.** `search_knowledge_base` chỉ được khai khi đã
nạp tài liệu; chưa có gì để tra thì bắt tra là đốt một lượt gọi model cho không.

**KHÔNG tự phân loại câu hỏi.** Một bộ phân loại bằng từ khoá sẽ sai theo kiểu im lặng
— nó không biết *"cách khử mùi hôi tai heo"* là câu có dữ kiện còn *"bot tên gì"* thì
không. Model thì đọc cả đoạn hội thoại, nên lời nhắc nêu rõ **cả hai nhánh** và để nó
quyết.

### 34.2 Ca âm: bốn lượt không có dữ kiện

```
"Chào bạn"                         không tra  -> "Chào bạn"
"Cảm ơn nhé"                       không tra  -> "Không có gì."
"Bạn tên là gì?"                   không tra  -> "Mình là CP Assistant, gọi tắt là CP."
"Viết lại câu này cho gọn: ..."    không tra  -> ba phương án viết lại
```

Không lượt nào bị kéo đi tra. Chặn này không đánh vào hội thoại thường.

### 34.3 Một lỗi lộ ra người dùng, bắt được ở ca âm

Bản nhắc đầu tiên chỉ viết *"đừng nhắc tới nó trong câu trả lời"*. Model **trả lời
chính lời nhắc** thay vì trả lời người dùng:

```
người dùng: "Cảm ơn nhé"
bot:        "Mình đã hiểu: với câu có dữ kiện sẽ gọi search_knowledge_base trước,
             còn câu không có dữ kiện thì trả lời luôn."
```

Vừa vô nghĩa với người dùng, vừa **lộ tên công cụ** — phạm đúng luật *"không kể chuyện
hậu trường"* của `SYSTEM_PROMPT`.

Bản nhắc giờ mở đầu bằng `[NHẮC NỘI BỘ — người dùng KHÔNG nhìn thấy tin này]`, và nói
thẳng nhánh không-dữ-kiện là **gửi nguyên câu vừa soạn**, đừng soạn lại. Đo lại: sạch.

Bài học lặp lại: **ca âm bắt được lỗi mà ca dương không bao giờ thấy.** Nếu chỉ đo hai
câu `g022`/`g023` thì con số 6/6 đã trông như một thắng lợi trọn vẹn, trong khi mọi
lời chào trong nhóm đang nhận về một câu vô nghĩa.


## 35. Lần chạy đầu sau chặn 7 — và vì sao con số của nó vô nghĩa

```
  Context Recall     0,438
  giao_tap_hop       0,000
  xuyen_ngon_ngu     0,000
  Model tu viet truy van   25/52
```

Trông y hệt một hồi quy thảm khốc. **Không có gì hỏng cả.**

Dấu hiệu nhận ra: 27 câu hỏng là **một khối liền** từ `g026` tới hết bộ. Model không
hỏng theo khối liền — hạ tầng thì có.

```
DAILY_BUDGET_USD = 2          hôm nay đã tiêu 2,0062 USD / 3.392 lần gọi
```

Ngân sách ngày cạn giữa lượt chạy. Chặn ngân sách của vòng ReAct (chặn 3) làm đúng
việc của nó: dừng lại và trả câu xin lỗi mặc định. Nhưng bộ eval chấm câu xin lỗi đó
**như một câu trả lời tệ**, và in ra một báo cáo sai một cách tự tin.

Đây là **cùng một lớp lỗi** với `APITimeoutError` đã chặn trong `runner.main()` —
sự cố hạ tầng đội lốt sụp đổ chất lượng. Lần đó mất cả lượt chạy; lần này tệ
hơn, vì nó không mất gì mà lại **bịa ra một con số**.

Đã chặn: câu trả lời khớp `FALLBACK_TEXT` hoặc `CONFIG_ERROR_TEXT` thì đếm vào mục
"không chạy được", không tính vào chỉ số nào. So sánh theo TIỀN TỐ vì `_finish()` nối
thêm `INCOMPLETE_SUFFIX` khi dừng giữa chừng.

**Bài học, lần thứ tư trong ba ngày:** mỗi lần một con số tụt bất thường, việc đầu tiên
KHÔNG phải đi sửa hệ thống mà là hỏi thước đo có còn đo được không. Bốn lần đã xảy ra:
id chết sau khi nạp lại, câu hỏi mang tên mục vỡ, câu kỳ vọng 35 chunk, và bây giờ là
hết tiền giữa chừng.

Số liệu thật của chặn 7 vẫn là phép đo lặp ở §34: **3/6 → 6/6**, cộng bốn ca âm sạch.
Muốn có con số đủ bộ thì phải nâng `DAILY_BUDGET_USD` rồi chạy lại — chưa làm.
