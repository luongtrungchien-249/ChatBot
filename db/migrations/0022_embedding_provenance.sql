-- Unknown legacy vectors stay unknown. Never infer their model from dimension,
-- current environment, ingestion timestamp, or a successful similarity search.
ALTER TABLE kb_document
  ADD COLUMN embedding_provider TEXT,
  ADD COLUMN embedding_model TEXT,
  ADD COLUMN embedding_dim INTEGER,
  ADD COLUMN embedding_revision TEXT,
  ADD COLUMN embedding_provenance TEXT,
  ADD COLUMN embedding_attested_by TEXT,
  ADD COLUMN embedding_attestation_evidence TEXT,
  ADD COLUMN embedding_attested_at TIMESTAMPTZ;

ALTER TABLE kb_document ADD CONSTRAINT kb_document_embedding_identity_complete CHECK (
  (embedding_provider IS NULL AND embedding_model IS NULL AND embedding_dim IS NULL
   AND embedding_revision IS NULL AND embedding_provenance IS NULL)
  OR
  (embedding_provider IS NOT NULL AND length(trim(embedding_provider)) > 0
   AND embedding_model IS NOT NULL AND length(trim(embedding_model)) > 0
   AND embedding_dim IS NOT NULL AND embedding_dim > 0
   AND embedding_revision IS NOT NULL AND length(trim(embedding_revision)) > 0
   AND embedding_provenance IS NOT NULL AND embedding_provenance IN ('ingested', 'attested'))
);

ALTER TABLE kb_document ADD CONSTRAINT kb_document_embedding_attestation_complete CHECK (
  (embedding_provenance IS DISTINCT FROM 'attested'
   AND embedding_attested_by IS NULL AND embedding_attestation_evidence IS NULL
   AND embedding_attested_at IS NULL)
  OR
  (embedding_provenance = 'attested'
   AND embedding_attested_by IS NOT NULL AND length(trim(embedding_attested_by)) > 0
   AND embedding_attestation_evidence IS NOT NULL
   AND length(trim(embedding_attestation_evidence)) > 0
   AND embedding_attested_at IS NOT NULL)
);

COMMENT ON COLUMN kb_document.embedding_provenance IS
  'All chunks of an atomic document version share this identity. NULL means unknown; '
  'attested records an explicit operator claim, not independently verified model provenance.';
