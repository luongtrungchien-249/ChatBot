-- Last explicit vector rebuild only; normal fact content/lifecycle remain unchanged.
-- All-data deletion removes this metadata with its fact row.
ALTER TABLE memory_fact ADD COLUMN embedding_rebuild_audit JSONB;
