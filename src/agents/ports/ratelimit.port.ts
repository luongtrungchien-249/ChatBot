import type { ThreadScope } from '../domain/thread.js';

export type LimitVerdict =
  | { allowed: true }
  | { allowed: false; retryAfterMs: number; tier: 'user' | 'thread' | 'global' };

export interface RateLimitPort {
  check(scope: ThreadScope, senderId: string): Promise<LimitVerdict>;
  /** Chot chan CUNG theo ngan sach ngay, khong phai alert. */
  withinDailyBudget(): Promise<boolean>;
}
