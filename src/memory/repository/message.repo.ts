import type { StoredMessage } from '../../agents/domain/message.js';
import type { ThreadScope } from '../../agents/domain/thread.js';
import type { NewMessage } from '../../agents/ports/memory.port.js';
import { query } from '../../infra/db.js';
import { logger } from '../../infra/logger.js';
import { redis } from '../../infra/redis.js';

/**
 * L1 — 15 tin gan nhat.
 *
 * POSTGRES LA NGUON THAT, REDIS CHI LA CACHE DOC. Day la ban sua loi mat du lieu
 * cua ke hoach goc (ARCHITECTURE.md section 6.1): ke hoach cu de Redis giu tin
 * chua nen voi TTL 2h, nen mot nhom im lang qua dem la mat sach.
 *
 * Cache truot thi doc lai DB — khong mat gi, chi cham hon mot chut.
 */
const CACHE_TTL_SECONDS = 7_200; // 2h, xem section 6.5

const ctxKey = (scope: ThreadScope): string => `ctx:${scope.platform}:${scope.threadId}`;

type Row = {
  sender_id: string;
  sender_name: string;
  text: string;
  created_at: Date;
  from_bot: boolean;
};

const toStored = (r: Row): StoredMessage => ({
  senderId: r.sender_id,
  senderName: r.sender_name,
  text: r.text,
  createdAt: r.created_at,
  fromBot: r.from_bot,
});

export const messageRepo = {
  async append(scope: ThreadScope, msg: NewMessage): Promise<void> {
    // ON CONFLICT DO NOTHING: khoa chinh (platform, message_id) la lop chong trung
    // thu BA, song lau hon TTL cua Redis. Job retry khong duoc tao ban ghi thu hai.
    const rows = await query<Row>(
      `INSERT INTO inbound_message
         (platform, message_id, thread_id, sender_id, sender_name, text, is_group, reply_to_id, from_bot)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
       ON CONFLICT (platform, message_id) DO NOTHING
       RETURNING sender_id, sender_name, text, created_at, from_bot`,
      [
        scope.platform,
        msg.messageId,
        scope.threadId,
        msg.senderId,
        msg.senderName,
        msg.text,
        msg.isGroup,
        msg.replyToId ?? null,
        msg.fromBot,
      ],
    );

    const inserted = rows[0];
    if (!inserted) return; // da co roi, cache cung da co

    try {
      const key = ctxKey(scope);
      await redis.lpush(key, JSON.stringify(toStored(inserted)));
      await redis.ltrim(key, 0, 49);
      await redis.expire(key, CACHE_TTL_SECONDS);
    } catch (err) {
      // Cache hong khong duoc lam hong duong ghi: nguon that da ghi xong roi.
      logger.warn(
        { err: err instanceof Error ? err.message : String(err) },
        'khong day duoc cache L1, bo qua',
      );
    }
  },

  /** Tra ve theo thu tu THOI GIAN TANG DAN — dung thu tu doc cua mot hoi thoai. */
  async recent(scope: ThreadScope, limit: number): Promise<StoredMessage[]> {
    const key = ctxKey(scope);

    try {
      const cached = await redis.lrange(key, 0, limit - 1);
      if (cached.length >= limit) {
        return cached
          .map((s) => JSON.parse(s) as StoredMessage)
          .map((m) => ({ ...m, createdAt: new Date(m.createdAt) }))
          .reverse();
      }
    } catch (err) {
      logger.warn(
        { err: err instanceof Error ? err.message : String(err) },
        'doc cache L1 that bai, doc thang DB',
      );
    }

    const rows = await query<Row>(
      `SELECT sender_id, sender_name, text, created_at, from_bot
         FROM inbound_message
        WHERE platform = $1 AND thread_id = $2
        ORDER BY created_at DESC
        LIMIT $3`,
      [scope.platform, scope.threadId, limit],
    );

    const newestFirst = rows.map(toStored);

    // Nong lai cache. Thieu buoc nay thi cache chi duoc nap boi append(), nen sau
    // moi lan khoi dong lai process (hoac sau khi TTL het) no nguoi han cho toi khi
    // du 15 tin moi duoc ghi — nghia la gan nhu khong bao gio am.
    //
    // Thread ngan hon `limit` van doc thang DB moi lan: khong the biet tu Redis la
    // danh sach ngan vi thread it tin hay vi cache thieu. Truy van co index tren
    // (platform, thread_id, created_at DESC) nen chuyen do khong dang mot giao thuc
    // danh dau "day du" rieng.
    if (newestFirst.length > 0) {
      try {
        await redis
          .multi()
          .del(key)
          .rpush(key, ...newestFirst.map((m) => JSON.stringify(m)))
          .expire(key, CACHE_TTL_SECONDS)
          .exec();
      } catch (err) {
        logger.warn(
          { err: err instanceof Error ? err.message : String(err) },
          'khong nong lai duoc cache L1, bo qua',
        );
      }
    }

    return newestFirst.reverse();
  },
};
