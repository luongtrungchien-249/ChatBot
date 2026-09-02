-- L3 Semantic memory. thread_id co mat trong MOI truy van: hang rao chong ro ri.

CREATE TABLE memory_fact (
  id           BIGSERIAL PRIMARY KEY,
  platform     TEXT NOT NULL,
  thread_id    TEXT NOT NULL,
  subject_id   TEXT NOT NULL,
  content      TEXT NOT NULL,
  embedding    VECTOR(1024) NOT NULL,
  source       TEXT NOT NULL CHECK (source IN ('explicit','implicit')),
  confidence   REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  created_by   TEXT NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at TIMESTAMPTZ,
  revoked_at   TIMESTAMPTZ,
  revoked_by   TEXT
);

CREATE INDEX ON memory_fact (platform, thread_id, subject_id) WHERE revoked_at IS NULL;
CREATE INDEX ON memory_fact USING hnsw (embedding vector_cosine_ops) WHERE revoked_at IS NULL;
