CREATE TABLE turn_telemetry (
  trace_id TEXT PRIMARY KEY,
  platform TEXT NOT NULL,
  outcome TEXT NOT NULL CHECK (outcome IN ('completed', 'error')),
  latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
  queue_wait_ms BIGINT NOT NULL CHECK (queue_wait_ms >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX turn_telemetry_created_idx ON turn_telemetry(created_at);
