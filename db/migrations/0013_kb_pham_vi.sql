-- Pham vi tai lieu: nhom nao doc duoc tai lieu nao.
--
-- Lo hong: `kb_document` va `kb_chunk` khong co cot nao gioi han pham vi, `search.py`
-- khong nhan ThreadScope, va `run_knowledge_search` tham chi khong co tham so pham
-- vi. Nghia la MOI NHOM trong allowlist doc duoc TOAN BO moi tai lieu.
--
-- Dieu nay lech han voi chuan ma chinh du an dat ra o cho khac: ThreadScope la tham
-- so BAT BUOC, DUNG DAU tren moi truy van `memory_fact`, dung rieng lam hang rao
-- chong ro giua cac nhom (L4b, cuong che bang ops/guard_sql.py). Ky uc thi co hang
-- rao, tai lieu thi khong.
--
-- Chua gay hai vi moi co mot nhom. No thanh lo hong that vao dung ngay co nhom thu
-- hai va mot tai lieu khong danh cho ho.
--
-- MAC DINH 'chung' — co y. Doi mac dinh thanh "khoa" se lam moi tai lieu da nap bien
-- mat khoi ket qua tim kiem ngay sau khi chay migration nay, va trieu chung se la
-- "bot quen het tai lieu" chu khong phai mot loi. Mo mac dinh, khoa khi duoc yeu cau.

ALTER TABLE kb_document
  ADD COLUMN pham_vi TEXT NOT NULL DEFAULT 'chung';

COMMENT ON COLUMN kb_document.pham_vi IS
  '''chung'' = moi nhom doc duoc. Khac di = scope_key cua DUNG mot thread duoc doc.';

CREATE INDEX kb_document_pham_vi_idx ON kb_document (pham_vi);
