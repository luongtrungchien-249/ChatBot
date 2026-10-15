-- Moi Web thread co dung mot owner. Khong them reader cho toi khi san pham can chia se.
-- Thread cu khong duoc tu dong gan owner: can backfill co bang chung truoc khi enforce.
CREATE TABLE web_thread_access (
  thread_id  TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX web_thread_access_user_idx
  ON web_thread_access (user_id, created_at DESC);
