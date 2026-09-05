import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import fastifyStatic from '@fastify/static';
import Fastify from 'fastify';
import { registerWebRoutes } from '../adapters/web/routes.js';
import { config } from '../config/index.js';
import { closeDb } from '../infra/db.js';
import { logger } from '../infra/logger.js';
import { closeQueues } from '../infra/queue.js';
import { closeRedis } from '../infra/redis.js';

/**
 * Process `api`: nhan webhook / request tu giao dien, tra 200 duoi 2s roi thoi.
 * TUYET DOI khong cho LLM o day — pipeline chay ben worker.
 *
 * TODO(tuan-2): route webhook Zalo. TODO(tuan-3): Meta + HMAC tren RAW body.
 */
// Khong dung loggerInstance cua Fastify: no lam hep kieu FastifyInstance nen moi
// ham nhan `app` phai keo theo kieu logger cua pino. Tu log bang hook vua giu duoc
// lop redact, vua kiem soat duoc dinh dang.
const app = Fastify({ logger: false, trustProxy: false });

app.addHook('onResponse', async (req, reply) => {
  logger.info(
    { method: req.method, url: req.url, status: reply.statusCode, ms: Math.round(reply.elapsedTime) },
    'http',
  );
});

registerWebRoutes(app);

// Ban build cua Vite. O che do dev thi Vite tu phuc vu (port rieng) va proxy /api
// sang day, nen thu muc nay chua ton tai — khong sao.
const WEB_DIST = resolve(process.cwd(), 'web/dist');
if (existsSync(WEB_DIST)) {
  await app.register(fastifyStatic, { root: WEB_DIST });
  app.setNotFoundHandler((req, reply) => {
    if (req.url.startsWith('/api/')) return reply.code(404).send({ error: 'khong co route nay' });
    return reply.sendFile('index.html'); // SPA
  });
  logger.info({ dir: WEB_DIST }, 'phuc vu giao dien da build');
} else {
  logger.info('chua co web/dist — chay `npm run dev:web` de mo giao dien o che do dev');
}

await app.listen({ port: config.WEB_PORT, host: config.WEB_BIND });
logger.info({ url: `http://${config.WEB_BIND}:${config.WEB_PORT}` }, 'api da chay');

for (const signal of ['SIGINT', 'SIGTERM'] as const) {
  process.on(signal, () => {
    void (async () => {
      await app.close();
      await Promise.allSettled([closeQueues(), closeDb(), closeRedis()]);
      process.exit(0);
    })();
  });
}
