import type { ThreadScope } from '../agents/domain/thread.js';
import type { LlmUsage } from '../agents/ports/llm.port.js';
import { query } from '../infra/db.js';
import { logger } from '../infra/logger.js';
import { costDayKey } from '../infra/ratelimit.js';
import { redis } from '../infra/redis.js';
import { MODELS, type Route } from './models.js';

/**
 * Ghi token in/out/cache moi lan goi -> usage_log + cost:day.
 *
 * cache_read_tokens bang 0 suot nghia la prompt caching DANG KHONG AN, va ban
 * dang tra gia day du cho ~600 token system prompt o moi cau hoi ma khong he biet.
 * Do la ly do cot nay ton tai.
 */

const COST_DAY_TTL_SECONDS = 172_800; // 48h, xem section 6.5

/**
 * USD cho mot lan goi.
 *
 * Gia cache lay tu priceCachedIn cua tung model, khong dung he so uoc chung:
 * ti le cached/input khac nhau theo model va theo thoi diem.
 *
 * usage.inputTokens theo hop dong LlmPort la phan tinh gia DAY DU (da tru phan
 * doc tu cache) — llm/openai.client.ts chiu trach nhiem chuan hoa.
 *
 * OpenAI khong tinh phi ghi cache nen cacheWriteTokens luon 0; cot van giu trong
 * usage_log de khong phai doi schema neu doi nha cung cap.
 */
export function costOf(route: Route, usage: LlmUsage): number {
  const { priceIn, priceCachedIn, priceOut } = MODELS[route];
  const perMillion =
    usage.inputTokens * priceIn +
    usage.cacheReadTokens * priceCachedIn +
    usage.outputTokens * priceOut;
  return perMillion / 1_000_000;
}

export type UsageRecord = Readonly<{
  route: Route;
  usage: LlmUsage;
  scope: ThreadScope;
  senderId: string;
  traceId: string;
  latencyMs: number;
  ok: boolean;
}>;

/**
 * Ghi mot lan goi. KHONG duoc nem loi ra ngoai: hong ke toan thi van phai tra loi
 * nguoi dung, nhung phai hien trong log de con biet ma sua.
 */
export async function record(r: UsageRecord): Promise<number> {
  const cost = costOf(r.route, r.usage);

  try {
    await query(
      `INSERT INTO usage_log
         (trace_id, platform, thread_id, sender_id, route, model,
          input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
          cost_usd, latency_ms, ok)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)`,
      [
        r.traceId,
        r.scope.platform,
        r.scope.threadId,
        r.senderId,
        r.route,
        MODELS[r.route].id,
        r.usage.inputTokens,
        r.usage.outputTokens,
        r.usage.cacheReadTokens,
        r.usage.cacheWriteTokens,
        cost,
        r.latencyMs,
        r.ok,
      ],
    );

    // Chot chan ngan sach doc khoa nay (infra/ratelimit.ts).
    const key = costDayKey();
    await redis.incrbyfloat(key, cost);
    await redis.expire(key, COST_DAY_TTL_SECONDS);
  } catch (err) {
    logger.error(
      { traceId: r.traceId, err: err instanceof Error ? err.message : String(err) },
      'khong ghi duoc usage_log — ngan sach ngay dang bi dem thieu',
    );
  }

  return cost;
}
