-- One row per actual knowledge-tool attempt, not per final answer/unique turn.
-- Store no query, document text, scope identifier, or tool output.
CREATE TABLE rag_telemetry (
  id BIGSERIAL PRIMARY KEY,
  trace_id TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('web', 'cli', 'zalo_bot')),
  outcome TEXT NOT NULL CHECK (outcome IN
    ('found', 'empty', 'filtered', 'uncertain', 'error', 'cancelled', 'unknown')),
  retrieval_degraded BOOLEAN NOT NULL,
  rerank_degraded BOOLEAN NOT NULL,
  low_confidence BOOLEAN NOT NULL,
  latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX rag_telemetry_created_idx ON rag_telemetry(created_at);
CREATE INDEX rag_telemetry_trace_idx ON rag_telemetry(trace_id);
