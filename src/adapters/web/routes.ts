import { Redis } from 'ioredis';
import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import { config } from '../../config/index.js';
import { claim } from '../../infra/dedupe.js';
import { query } from '../../infra/db.js';
import { logger } from '../../infra/logger.js';
import { enqueueReply } from '../../infra/queue.js';
import { normalizeWebInput, webChannelKey, type WebChatBody } from './normalize.js';

/**
 * L5: adapter chi lam 4 viec — verify -> chuan hoa -> enqueue -> gui tra loi.
 * Khong goi LLM, khong tu chay pipeline.
 */

/**
 * D17: chi localhost. Chua co auth, nen mo ra ngoai la ai trong mang cung dot
 * duoc ngan sach. Kiem tra o tang route chu khong chi dua vao bind address —
 * mot reverse proxy dat truoc se lam bind address vo nghia.
 */
const LOCAL_ADDRESSES = new Set(['127.0.0.1', '::1', '::ffff:127.0.0.1']);

function requireLocalhost(req: FastifyRequest, reply: FastifyReply): boolean {
  if (LOCAL_ADDRESSES.has(req.ip)) return true;
  logger.warn({ ip: req.ip }, 'tu choi truy cap khong phai localhost');
  void reply.code(403).send({ error: 'chi cho phep truy cap tu localhost' });
  return false;
}

type ThreadRow = { thread_id: string; last_text: string; last_at: Date; message_count: string };
type MessageRow = { text: string; from_bot: boolean; created_at: Date };

export function registerWebRoutes(app: FastifyInstance): void {
  app.addHook('onRequest', async (req, reply) => {
    if (req.url.startsWith('/api/')) requireLocalhost(req, reply);
  });

  app.get('/api/health', async () => ({ ok: true }));

  /** Danh sach hoi thoai cho sidebar. Doc tu Postgres, khong phai localStorage. */
  app.get('/api/threads', async () => {
    const rows = await query<ThreadRow>(
      `SELECT DISTINCT ON (thread_id)
              thread_id,
              first_value(text)       OVER w AS last_text,
              first_value(created_at) OVER w AS last_at,
              count(*)                OVER (PARTITION BY thread_id) AS message_count
         FROM inbound_message
        WHERE platform = 'web'
       WINDOW w AS (PARTITION BY thread_id ORDER BY created_at DESC)
        ORDER BY thread_id, last_at DESC`,
      [],
    );

    return rows
      .map((r) => ({
        threadId: r.thread_id,
        lastText: r.last_text,
        lastAt: r.last_at,
        messageCount: Number(r.message_count),
      }))
      .sort((a, b) => b.lastAt.getTime() - a.lastAt.getTime());
  });

  app.get('/api/threads/:threadId/messages', async (req) => {
    const { threadId } = req.params as { threadId: string };
    const rows = await query<MessageRow>(
      `SELECT text, from_bot, created_at
         FROM inbound_message
        WHERE platform = 'web' AND thread_id = $1
        ORDER BY created_at`,
      [threadId],
    );
    return rows.map((r) => ({ text: r.text, fromBot: r.from_bot, at: r.created_at }));
  });

  /** Tra 202 ngay roi thoi — cau tra loi ve qua SSE. Khong cho LLM o day. */
  app.post('/api/chat', async (req, reply) => {
    const body = req.body as Partial<WebChatBody>;
    if (typeof body?.threadId !== 'string' || typeof body?.text !== 'string') {
      return reply.code(400).send({ error: 'can threadId va text' });
    }
    if (body.text.trim() === '') {
      return reply.code(400).send({ error: 'text rong' });
    }

    const msg = normalizeWebInput({ threadId: body.threadId, text: body.text });

    // Lop chong trung thu nhat: SET NX atomic.
    if (!(await claim(msg.platform, msg.messageId))) {
      return reply.code(202).send({ duplicate: true });
    }

    await enqueueReply(msg);
    logger.info({ traceId: msg.traceId, threadId: msg.threadId }, 'da xep hang cau hoi tu web');

    return reply.code(202).send({ messageId: msg.messageId, traceId: msg.traceId });
  });

  /**
   * SSE. Moi ket noi mot Redis client rieng: o che do subscribe, ioredis khong
   * chay duoc lenh nao khac tren cung connection.
   */
  app.get('/api/stream/:threadId', async (req, reply) => {
    const { threadId } = req.params as { threadId: string };

    reply.raw.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    });
    reply.raw.write(': connected\n\n');

    const subscriber = new Redis(config.REDIS_URL, { maxRetriesPerRequest: null });
    await subscriber.subscribe(webChannelKey(threadId));

    subscriber.on('message', (_channel, payload) => {
      reply.raw.write(`data: ${payload}\n\n`);
    });

    // Giu ket noi song qua proxy hay cat idle.
    const heartbeat = setInterval(() => reply.raw.write(': ping\n\n'), 20_000);

    req.raw.on('close', () => {
      clearInterval(heartbeat);
      void subscriber.quit();
    });

    // Khong return: giu stream mo cho toi khi client dong.
    return reply;
  });
}
