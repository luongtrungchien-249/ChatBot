-- Durable receipt before enqueue; payload is removed only after queue acceptance.
CREATE TABLE zalo_inbox (
  message_id TEXT PRIMARY KEY,
  payload JSONB,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  queued_at TIMESTAMPTZ,
  CHECK ((queued_at IS NULL) = (payload IS NOT NULL))
);
CREATE INDEX zalo_inbox_pending_idx ON zalo_inbox(received_at) WHERE queued_at IS NULL;
