-- NULL means not measured; historical turns must not gain invented zeros.
ALTER TABLE turn_telemetry ADD COLUMN poetry_calls INTEGER;
ALTER TABLE turn_telemetry ADD CONSTRAINT turn_poetry_calls_nonnegative
  CHECK (poetry_calls IS NULL OR poetry_calls >= 0);
