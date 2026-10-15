-- Additive: old rows remain explicitly unmeasured; no invented historical values.
ALTER TABLE turn_telemetry
  ADD COLUMN reason TEXT NOT NULL DEFAULT 'unknown'
    CHECK (reason IN ('unknown', 'answer', 'error', 'budget', 'deadline',
      'user_stopped', 'max_iterations', 'ignored_access', 'ignored_mention',
      'help', 'command', 'rate_limited', 'poetry')),
  ADD COLUMN replied BOOLEAN,
  ADD COLUMN fallback BOOLEAN,
  ADD COLUMN react_iterations INTEGER CHECK (react_iterations >= 0),
  ADD COLUMN tool_calls INTEGER CHECK (tool_calls >= 0),
  ADD COLUMN tool_errors INTEGER CHECK (tool_errors >= 0 AND tool_errors <= tool_calls);
