-- L1/L2: Postgres la nguon that, Redis chi la cache doc.
-- Xem ARCHITECTURE.md section 6.1 (sua loi mat du lieu trong plan goc).

CREATE TABLE inbound_message (
  platform     TEXT NOT NULL,
  message_id   TEXT NOT NULL,
  thread_id    TEXT NOT NULL,
  sender_id    TEXT NOT NULL,
  sender_name  TEXT NOT NULL,
  text         TEXT NOT NULL,
  is_group     BOOLEAN NOT NULL,
  reply_to_id  TEXT,
  summarized   BOOLEAN NOT NULL DEFAULT FALSE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (platform, message_id)
);
CREATE INDEX ON inbound_message (platform, thread_id, created_at DESC);
CREATE INDEX ON inbound_message (platform, thread_id) WHERE NOT summarized;

CREATE TABLE thread_summary (
  platform    TEXT NOT NULL,
  thread_id   TEXT NOT NULL,
  summary     TEXT NOT NULL,
  msg_count   INT  NOT NULL DEFAULT 0,
  gen_count   INT  NOT NULL DEFAULT 0,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (platform, thread_id)
);
