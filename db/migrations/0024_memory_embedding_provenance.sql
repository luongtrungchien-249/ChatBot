-- Legacy facts remain available for explicit listing/audit/deletion. Their
-- unknown vectors must not be compared to a guessed current model identity.
ALTER TABLE memory_fact
  ADD COLUMN embedding_provider TEXT,
  ADD COLUMN embedding_model TEXT,
  ADD COLUMN embedding_dim INTEGER,
  ADD COLUMN embedding_revision TEXT;

ALTER TABLE memory_fact ADD CONSTRAINT memory_fact_embedding_identity_complete CHECK (
  (embedding_provider IS NULL AND embedding_model IS NULL AND embedding_dim IS NULL
   AND embedding_revision IS NULL)
  OR
  (embedding_provider IS NOT NULL AND length(trim(embedding_provider)) > 0
   AND embedding_model IS NOT NULL AND length(trim(embedding_model)) > 0
   AND embedding_dim IS NOT NULL AND embedding_dim > 0
   AND embedding_revision IS NOT NULL AND length(trim(embedding_revision)) > 0)
);

COMMENT ON COLUMN memory_fact.embedding_provider IS
  'NULL is unknown provenance. Never infer from timestamp, dimension, or current environment.';
