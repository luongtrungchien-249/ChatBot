-- BM25 phai nhin thay CA TIEU DE MUC, khong chi than bai.
--
-- Loi: `tsv` duoc sinh tu `content`, ma `content` la than cua muc — dong tieu de da
-- bi tach ra thanh cot `section` tu luc cat chunk. Hau qua: tai lieu co muc "Nghi
-- phep nam" nhung than muc khong lap lai cum tu do, nen cau hoi "nghi phep nam bao
-- nhieu ngay" khong khop MOT tu nao ben duong lexical.
--
-- Duong vector khong dinh loi nay vi no embed `embed_input` (da co duong dan tieu
-- de). Nen trieu chung la "tim kiem lai lai" chu khong phai "tim kiem hong" — dung
-- loai im lang ma hybrid search sinh ra de tranh.
--
-- Sua: sinh tsv tu `embed_input`. Cot do la `[Ten tai lieu > Muc]\n<than>`, tuc la
-- chua ca hai. `content` giu nguyen van cho trich dan, khong dong toi.
--
-- Chi tien, khong sua file cu: 0004 giu nguyen, day la mot buoc moi.

DROP INDEX IF EXISTS kb_chunk_tsv_idx;

ALTER TABLE kb_chunk DROP COLUMN tsv;
ALTER TABLE kb_chunk
  ADD COLUMN tsv tsvector GENERATED ALWAYS AS (vn_tsv(embed_input)) STORED;

CREATE INDEX kb_chunk_tsv_idx ON kb_chunk USING gin (tsv);
