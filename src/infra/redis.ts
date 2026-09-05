import { Redis } from 'ioredis';
import { config } from '../config/index.js';
import { logger } from './logger.js';

/**
 * Client Redis dung chung cho cache va khoa (dedupe, ratelimit, ctx).
 * BullMQ KHONG dung client nay — no can maxRetriesPerRequest: null rieng,
 * xem infra/queue.ts.
 */
export const redis = new Redis(config.REDIS_URL, {
  lazyConnect: false,
  enableReadyCheck: true,
  retryStrategy: (times: number) => Math.min(times * 200, 5_000),
});

redis.on('error', (err: Error) => logger.error({ err: err.message }, 'redis loi'));
redis.on('ready', () => logger.info('redis san sang'));

export async function closeRedis(): Promise<void> {
  await redis.quit();
}
