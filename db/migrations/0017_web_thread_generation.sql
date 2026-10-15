-- Non-content tombstones invalidate queued work after a user deletes a thread.
CREATE TABLE web_thread_generation (
  thread_id TEXT PRIMARY KEY,
  generation BIGINT NOT NULL DEFAULT 0 CHECK (generation >= 0)
);
