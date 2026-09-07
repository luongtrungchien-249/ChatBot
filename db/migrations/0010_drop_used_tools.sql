-- Bo cot `used_tools` — no vua SAI vua THUA. Them o 0009, bo o day cung ngay.
--
-- Y dinh ban dau: danh dau luot nao co tra cuu, de tach muc tieu do tre. Cai dat:
-- danh dau khi lan goi model DUOC TRAO cong cu.
--
-- Do thu ngay sau khi viet: ba luot "Xin chao", "Tim giup toi bai bao...", "Cam on
-- nhe" deu ra `used_tools = true`. Dung — vi vong ReAct trao cong cu cho GAN NHU MOI
-- lan goi, ke ca mot loi chao. Cot do khong tach duoc gi.
--
-- Va no thua: `route = 'tool'` (them o 0009 cung dot) da noi dung dieu can biet —
-- mot luot co tra cuu la mot luot co it nhat mot dong route='tool'. Truy van dung la:
--
--     SELECT trace_id, bool_or(route = 'tool'), sum(latency_ms)
--       FROM usage_log WHERE route IN ('reply','tool') GROUP BY trace_id;
--
-- Giu lai mot cot luon FALSE la de mot cai bay: nguoi doc sau se tin no.
-- Index tren trace_id (cung o 0009) thi GIU — do la phan co gia tri that.

ALTER TABLE usage_log DROP COLUMN used_tools;
