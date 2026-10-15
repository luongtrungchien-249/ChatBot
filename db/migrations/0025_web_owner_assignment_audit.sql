-- Existing owners remain unchanged. Legacy assignment requires an explicit manifest.
ALTER TABLE web_thread_access ADD COLUMN owner_assignment JSONB;
