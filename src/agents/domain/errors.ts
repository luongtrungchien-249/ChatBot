/** Taxonomy loi. Xem bang hanh vi trong ARCHITECTURE.md section 9. */
export type BotError =
  | { kind: 'rate_limited'; retryAfterMs: number }
  | { kind: 'budget_exceeded' }
  | { kind: 'not_allowed' }
  | { kind: 'upstream_timeout'; service: 'llm' | 'embed' | 'rerank' | 'db' }
  | { kind: 'upstream_error'; service: string; status?: number }
  | { kind: 'bad_payload'; detail: string };

/**
 * Loi cau hinh: khoa sai, het han, khong du quyen.
 *
 * Khac han loi tam thoi o cho: THU LAI KHONG BAO GIO HET. Phai co nguoi sua
 * bien moi truong. Gop chung voi 5xx la vua ton ba lan retry vo ich, vua noi doi
 * nguoi dung rang "thu lai sau di".
 */
export function isConfigError(e: BotError): boolean {
  return e.kind === 'upstream_error' && (e.status === 401 || e.status === 403);
}

/**
 * Loi nao dang duoc retry job.
 *
 * - upstream_timeout: KHONG. Nguoi dung da nhan cau fallback roi.
 * - 401/403: KHONG. Retry mot cau hinh sai ba lan van sai ba lan.
 * - 4xx khac (400 payload hong): KHONG. Gui lai y het thi hong y het.
 * - 429 va 5xx: CO. Day moi that su la tam thoi.
 * - Khong ro status: CO, cho huong loi cua su nghi ngo (loi mang thuong khong co status).
 */
export function isRetryable(e: BotError): boolean {
  if (e.kind !== 'upstream_error') return false;
  if (e.status === undefined) return true;
  return e.status === 429 || e.status >= 500;
}

/** Loi nao im lang hoan toan trong nhom. */
export function isSilent(e: BotError): boolean {
  return e.kind === 'not_allowed' || e.kind === 'bad_payload';
}
