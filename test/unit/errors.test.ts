import { describe, it, expect } from 'vitest';
import { isConfigError, isRetryable, isSilent } from '../../src/agents/domain/errors.js';

/**
 * Bang hanh vi loi o ARCHITECTURE.md section 9.
 *
 * Case quan trong nhat: 401. Gop no vao "loi upstream, cu retry di" vua ton ba lan
 * goi vo ich, vua lam nguoi dung nhan cau "thu lai sau" cho mot thu khong bao gio
 * tu khoi — trieu chung nhin y het "bot khong hieu tieng Viet".
 */
describe('isRetryable', () => {
  it('KHONG retry loi cau hinh 401/403', () => {
    expect(isRetryable({ kind: 'upstream_error', service: 'llm', status: 401 })).toBe(false);
    expect(isRetryable({ kind: 'upstream_error', service: 'llm', status: 403 })).toBe(false);
  });

  it('KHONG retry 4xx khac — gui lai y het thi hong y het', () => {
    expect(isRetryable({ kind: 'upstream_error', service: 'llm', status: 400 })).toBe(false);
    expect(isRetryable({ kind: 'upstream_error', service: 'llm', status: 404 })).toBe(false);
  });

  it('CO retry 429 va 5xx — day moi that su la tam thoi', () => {
    for (const status of [429, 500, 502, 503, 529]) {
      expect(isRetryable({ kind: 'upstream_error', service: 'llm', status }), String(status)).toBe(
        true,
      );
    }
  });

  it('khong ro status thi van retry — loi mang thuong khong co status', () => {
    expect(isRetryable({ kind: 'upstream_error', service: 'llm' })).toBe(true);
  });

  it('timeout KHONG retry — nguoi dung da nhan cau fallback roi', () => {
    expect(isRetryable({ kind: 'upstream_timeout', service: 'llm' })).toBe(false);
  });

  it('cac loai loi khac khong bao gio retry', () => {
    expect(isRetryable({ kind: 'budget_exceeded' })).toBe(false);
    expect(isRetryable({ kind: 'not_allowed' })).toBe(false);
    expect(isRetryable({ kind: 'rate_limited', retryAfterMs: 1000 })).toBe(false);
  });
});

describe('isConfigError', () => {
  it('chi 401 va 403 moi la loi cau hinh', () => {
    expect(isConfigError({ kind: 'upstream_error', service: 'llm', status: 401 })).toBe(true);
    expect(isConfigError({ kind: 'upstream_error', service: 'llm', status: 403 })).toBe(true);
    expect(isConfigError({ kind: 'upstream_error', service: 'llm', status: 500 })).toBe(false);
    expect(isConfigError({ kind: 'upstream_timeout', service: 'llm' })).toBe(false);
  });
});

describe('isSilent', () => {
  it('khong duoc phep va payload hong thi im lang hoan toan', () => {
    expect(isSilent({ kind: 'not_allowed' })).toBe(true);
    expect(isSilent({ kind: 'bad_payload', detail: 'x' })).toBe(true);
    expect(isSilent({ kind: 'budget_exceeded' })).toBe(false);
  });
});
