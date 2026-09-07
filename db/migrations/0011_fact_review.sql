-- Duyet SAU cho fact bot tu ghi (human-on-the-loop).
--
-- L3 implicit da viet xong tu Giai doan 7 nhung MAC DINH TAT, va ly do ghi trong
-- code rat ro: "day la tinh nang ghi thong tin ve NGUOI CO TEN ma khong ai bam nut
-- dong y". Dieu kien de bat no khong phai la them mot lop chan nua — ba lop da co
-- (loai cau cua bot, ten phai co trong lo, confidence >= 0.8). Dieu kien la phai
-- NHIN THAY duoc bot da tu ghi gi, va bo duoc cai sai.
--
-- `cli memory` in ra moi fact, nhung khong phan biet duoc cai nao da co nguoi xem.
-- Hai cot nay lam duoc dieu do, va chung chi co nghia voi source='implicit':
-- fact explicit la do chinh nguoi dung noi ra, khong ai phai duyet loi cua ho.

ALTER TABLE memory_fact ADD COLUMN reviewed_at TIMESTAMPTZ;
ALTER TABLE memory_fact ADD COLUMN reviewed_by TEXT;

-- Truy van chinh cua `cli review`: fact tu dong, con hieu luc, chua ai xem.
CREATE INDEX ON memory_fact (platform, thread_id)
  WHERE source = 'implicit' AND revoked_at IS NULL AND reviewed_at IS NULL;
