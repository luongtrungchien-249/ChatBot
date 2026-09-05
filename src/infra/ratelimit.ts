import type { ThreadScope } from '../agents/domain/thread.js';
import type { LimitVerdict, RateLimitPort } from '../agents/ports/ratelimit.port.js';
import { config } from '../config/index.js';
import { logger } from './logger.js';
import { redis } from './redis.js';

/**
 * Ngan sach ngay tinh theo gio Viet Nam, khong theo UTC: "hom nay" phai trung voi
 * hom nay cua nguoi dung, khong lech 7 tieng.
 */
const TIMEZONE = 'Asia/Ho_Chi_Minh';

const dayFormatter = new Intl.DateTimeFormat('en-CA', {
  timeZone: TIMEZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

/** cost:day:{YYYY-MM-DD}. Mot noi duy nhat dung khoa nay — llm/cost-meter.ts ghi, o day doc. */
export function costDayKey(now: Date = new Date()): string {
  return `cost:day:${dayFormatter.format(now)}`;
}

export async function spentToday(now: Date = new Date()): Promise<number> {
  const raw = await redis.get(costDayKey(now));
  return raw === null ? 0 : Number.parseFloat(raw);
}

export const rateLimit: RateLimitPort = {
  /**
   * TODO(tuan-2): token bucket bang Lua script (atomic), 3 tang:
   *   rl:u:{platform}:{sender_id}  10/phut
   *   rl:t:{platform}:{thread_id}  30/phut
   *   global theo ngan sach
   * Tuan 1 chi co CLI, mot nguoi dung, nen chua can. Khong lam som viec chua can.
   */
  async check(_scope: ThreadScope, _senderId: string): Promise<LimitVerdict> {
    return { allowed: true };
  },

  /**
   * CHOT CHAN CUNG, khong phai alert. Vuot ngan sach thi tu choi tra loi.
   *
   * "Mot nhom 50 nguoi nghich bot co the dot sach ngan sach thang trong mot buoi
   * chieu" — day la cho bien canh bao do thanh mot cau lenh if.
   */
  async withinDailyBudget(): Promise<boolean> {
    const spent = await spentToday();
    if (Number.isNaN(spent)) {
      logger.error({ key: costDayKey() }, 'cost:day khong doc duoc so — coi nhu het ngan sach');
      return false;
    }

    const within = spent < config.DAILY_BUDGET_USD;
    if (!within) {
      logger.warn({ spent, budget: config.DAILY_BUDGET_USD }, 'vuot ngan sach ngay, dung tra loi');
    }
    return within;
  },
};
