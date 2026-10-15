-- Additive; unknown historical causes remain NULL, never inferred from text.
ALTER TABLE turn_telemetry
  ADD COLUMN failure_service TEXT CHECK (failure_service IN ('llm','embed','rerank','db','unknown')),
  ADD COLUMN failure_kind TEXT CHECK (failure_kind IN ('timeout','auth','throttled','server','client','unknown')),
  ADD CONSTRAINT turn_failure_pair CHECK ((failure_service IS NULL) = (failure_kind IS NULL));
