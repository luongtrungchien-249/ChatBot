import type { Platform } from '../agents/domain/thread.js';
import { redis } from './redis.js';

/**
 * Chong trung tin nhan va chong gui tra loi hai lan.
 *
 * SET NX la ATOMIC. Tuyet doi khong viet GET roi SET: hai webhook cua Meta ve
 * cung luc se cung thay "chua co" va bot tra loi hai lan.
 *
 * Day la lop 1. Lop 2 la jobId cua BullMQ (infra/queue.ts), lop 3 la khoa chinh
 * (platform, message_id) cua bang inbound_message — song lau hon TTL Redis.
 */
const DEDUP_TTL_SECONDS = 600; // 10 phut, xem section 6.5
const REPLIED_TTL_SECONDS = 3600; // 1 gio

const dedupKey = (platform: Platform, messageId: string): string =>
  `dedup:${platform}:${messageId}`;

const repliedKey = (platform: Platform, messageId: string): string =>
  `replied:${platform}:${messageId}`;

/** true = ban gianh duoc quyen xu ly tin nay. false = ai do da gianh truoc. */
export async function claim(platform: Platform, messageId: string): Promise<boolean> {
  const res = await redis.set(dedupKey(platform, messageId), '1', 'EX', DEDUP_TTL_SECONDS, 'NX');
  return res === 'OK';
}

/**
 * Danh dau da tra loi. Phai goi TRUOC khi cho phep retry.
 *
 * Thieu co nay, mot su co 5xx bien thanh bot spam nhom — dung cai lam nguoi ta
 * kick bot ra (ARCHITECTURE.md section 9).
 */
export async function markReplied(platform: Platform, messageId: string): Promise<void> {
  await redis.set(repliedKey(platform, messageId), '1', 'EX', REPLIED_TTL_SECONDS);
}

export async function hasReplied(platform: Platform, messageId: string): Promise<boolean> {
  return (await redis.exists(repliedKey(platform, messageId))) === 1;
}
