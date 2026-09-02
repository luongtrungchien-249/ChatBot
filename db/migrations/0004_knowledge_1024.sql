-- L4 RAG. So chieu nam trong TEN file: doi dim = migration moi, khong sua file nay.

CREATE TABLE kb_document (
  id          BIGSERIAL PRIMARY KEY,
  title       TEXT NOT NULL,
  source_path TEXT NOT NULL,
  version     INT  NOT NULL DEFAULT 1,
  checksum    TEXT NOT NULL,
  ingested_by TEXT NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_path, version)
);

CREATE TABLE kb_chunk (
  id           BIGSERIAL PRIMARY KEY,
  doc_id       BIGINT NOT NULL REFERENCES kb_document(id) ON DELETE CASCADE,
  ord          INT  NOT NULL,
  section      TEXT,
  page         INT,
  content      TEXT NOT NULL,
  embed_input  TEXT NOT NULL,
  embedding    VECTOR(1024) NOT NULL,
  tsv          tsvector GENERATED ALWAYS AS (vn_tsv(content)) STORED,
  token_count  INT NOT NULL,
  UNIQUE (doc_id, ord)
);

CREATE INDEX ON kb_chunk USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON kb_chunk USING gin (tsv);
