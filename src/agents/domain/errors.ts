/** Taxonomy loi. Xem bang hanh vi trong ARCHITECTURE.md section 9. */
export type BotError =
  | { kind: 'rate_limited'; retryAfterMs: number }
  | { kind: 'budget_exceeded' }
  | { kind: 'not_allowed' }
  | { kind: 'upstream_timeout'; service: 'llm' | 'embed' | 'rerank' | 'db' }
  | { kind: 'upstream_error'; service: string; status?: number }
  | { kind: 'bad_payload'; detail: string };

/** Loi nao dang duoc retry job. upstream_timeout thi KHONG: nguoi dung da nhan fallback roi. */
export function isRetryable(e: BotError): boolean {
  return e.kind === 'upstream_error';
}

/** Loi nao im lang hoan toan trong nhom. */
export function isSilent(e: BotError): boolean {
  return e.kind === 'not_allowed' || e.kind === 'bad_payload';
}
