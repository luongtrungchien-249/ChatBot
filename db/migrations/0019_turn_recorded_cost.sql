-- Only usage records linked to this trace; this is an estimate, not an invoice.
-- Historical turns and turns without linked usage remain NULL (unmeasured).
ALTER TABLE turn_telemetry
  ADD COLUMN recorded_cost_usd NUMERIC(18,6) CHECK (recorded_cost_usd >= 0);
