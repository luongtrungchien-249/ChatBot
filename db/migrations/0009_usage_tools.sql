-- Phan biet luot CO tra cuu voi luot khong, de muc tieu do tre co nghia.
--
-- Muc tieu "p95 < 5s" duoc viet TRUOC khi co cong cu nao. Mot luot co tra cuu bat
-- buoc hai lan goi model (quyet dinh goi cong cu -> doc ket qua -> viet tra loi)
-- cong thoi gian chay cong cu; ep no xuong 5s la ep bo tra cuu. Nhung `usage_log`
-- khong phan biet duoc hai loai, nen khong ai biet minh dang truot cai nao.
--
-- Con mot lo hong thu hai, lon hon: `latency_ms` la do tre cua MOT LAN GOI, con thu
-- nguoi dung cam nhan la ca luot. Hai thu do khac nhau vai lan khi vong ReAct chay
-- nhieu vong. Sua bang cach ghi CA cong cu vao bang nay (route = 'tool'), roi cong
-- theo `trace_id` — moi lan goi trong mot luot deu mang cung mot trace_id (luat L8).
--
-- Sau buoc nay, do tre THAT cua mot luot la:
--     SELECT trace_id, sum(latency_ms), bool_or(used_tools)
--       FROM usage_log GROUP BY trace_id;

ALTER TABLE usage_log ADD COLUMN used_tools BOOLEAN NOT NULL DEFAULT FALSE;

-- Cong theo trace_id la truy van chinh cua bang nay tu gio.
CREATE INDEX ON usage_log (trace_id);
