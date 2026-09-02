CREATE TABLE usage_log (
  id BIGSERIAL PRIMARY KEY,
  trace_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  thread_id TEXT NOT NULL,
  sender_id TEXT NOT NULL,
  route TEXT NOT NULL,
  model TEXT NOT NULL,
  input_tokens INT,
  output_tokens INT,
  cache_read_tokens INT,
  cache_write_tokens INT,
  cost_usd NUMERIC(10,6),
  latency_ms INT,
  ok BOOLEAN NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON usage_log (created_at);
CREATE INDEX ON usage_log (platform, thread_id, created_at);

CREATE TABLE thread_allowlist (
  platform TEXT NOT NULL,
  thread_id TEXT NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('open','allowlist','disabled')),
  added_by TEXT NOT NULL,
  added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (platform, thread_id)
);

-- Bang theo doi migration da chay (dung boi src/main/cli.ts migrate).
CREATE TABLE schema_migration (
  filename   TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
