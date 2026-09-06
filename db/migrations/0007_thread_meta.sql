-- Ten do NGUOI DUNG dat cho mot hoi thoai.
--
-- Bang rieng chu khong them cot vao inbound_message: ten thuoc ve CA THREAD, con
-- inbound_message la tung tin nhan. Nhet vao do se lap lai ten o moi dong va khong
-- co cho de dat ten cho thread chua co tin nao.
--
-- Khong dung thread_summary: bang do la tom tat do MODEL sinh (L2), doi theo hoi
-- thoai. Ten do nguoi dat thi khong duoc mot job nen tom tat ghi de len.
--
-- Khoa chinh (platform, thread_id) giong moi bang khac — ThreadScope la khoa chung
-- cua toan he thong, khong rieng gi web.

CREATE TABLE thread_meta (
  platform   TEXT NOT NULL,
  thread_id  TEXT NOT NULL,
  title      TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (platform, thread_id)
);
