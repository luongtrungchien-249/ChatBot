-- Tim kiem chi duoc nhin BAN MOI NHAT cua moi tai lieu.
--
-- Loi: `pipeline.py` co y bat bien theo phien ban — nap lai mot tep voi noi dung
-- khac se tao `version + 1` va GIU NGUYEN ban cu. Ly do rat dung: mot cau tra loi
-- da trich dan chunk 42 thi chunk 42 phai con nguyen van do, sua tai cho la lam moi
-- trich dan cu noi doi.
--
-- Nhung `search.py` lai truy van `FROM kb_chunk c JOIN kb_document d ON d.id =
-- c.doc_id` — KHONG co dieu kien loc phien ban nao. Va khong cho nao trong toan bo
-- ma nguon xoa hay danh dau ban cu.
--
-- Hau qua: ngay lan nap lai DAU TIEN, ket qua tim kiem tron chunk cua v1 voi v2 —
-- noi dung cu va moi cung xuat hien, trung lap, va bot trich dan ca thu da bi thay
-- the. Khong loi nao bao ra.
--
-- Chua lo vi `kb_chunk` dang rong. Nhung thay doi chunker ngay 08/09 BAT BUOC phai
-- nap lai, nen day la cai bay nam ngay tren duong di.
--
-- Chon cot BOOLEAN chu khong phai subquery `max(version)` trong moi truy van: cot
-- danh index duoc va doc ra y dinh ngay tu ten. Bat bien can giu: voi moi
-- source_path chi duoc co DUNG MOT dong `la_ban_moi_nhat = true`.

ALTER TABLE kb_document
  ADD COLUMN la_ban_moi_nhat BOOLEAN NOT NULL DEFAULT true;

-- Du lieu cu (neu co): chi ban version cao nhat cua moi source_path duoc giu true.
UPDATE kb_document d
   SET la_ban_moi_nhat = false
 WHERE d.version < (
         SELECT max(x.version) FROM kb_document x WHERE x.source_path = d.source_path
       );

-- Cuong che bat bien bang CHINH CSDL, khong bang ky luat cua nguoi viet code:
-- mot lan quen UPDATE trong pipeline se bi chan o day thay vi lam hong ket qua tim
-- kiem mot cach im lang.
CREATE UNIQUE INDEX kb_document_mot_ban_moi_nhat
    ON kb_document (source_path)
 WHERE la_ban_moi_nhat;

CREATE INDEX kb_document_la_ban_moi_nhat_idx ON kb_document (la_ban_moi_nhat);
