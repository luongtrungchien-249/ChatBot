import { publishProgress, webChannel } from '../adapters/web/send.js';
import type { ReactEvent } from '../agents/pipeline/stages/12-generate.js';
import type { InboundMessage } from '../agents/domain/message.js';
import { isRetryable } from '../agents/domain/errors.js';
import { handleMessage } from '../agents/pipeline/handle-message.js';
import type { ChannelPort } from '../agents/ports/channel.port.js';
import type { Platform } from '../agents/domain/thread.js';
import { hasReplied, markReplied } from '../infra/dedupe.js';
import { logger } from '../infra/logger.js';
import { createReplyWorker, REPLY_CONCURRENCY } from '../infra/queue.js';
import { buildContainer } from './container.js';

/**
 * BullMQ worker cho queue `reply`.
 *
 * Chong trung va co "da tra loi" nam O DAY, khong o handle-message: chung la ha
 * tang, va pipeline phai test duoc ma khong can Redis.
 */
const container = await buildContainer();

/**
 * TODO(tuan-2): dang ky ChannelPort cua zalo-bot; TODO(tuan-3): messenger.
 * CLI khong di qua hang doi (xem cli.ts) nen khong co mat o day.
 */
const channels: Partial<Record<Platform, ChannelPort>> = {
  web: webChannel,
};

const worker = createReplyWorker(async (job) => {
  const msg: InboundMessage = job.data;
  const log = logger.child({ traceId: msg.traceId, jobId: job.id });

  // Retry cua BullMQ khong duoc phep gui tin nhan thu hai cho cung mot message_id.
  // Thieu co nay, mot su co 5xx bien thanh bot spam nhom.
  if (await hasReplied(msg.platform, msg.messageId)) {
    log.warn('da tra loi tin nay roi, bo qua lan retry');
    return;
  }

  const channel = channels[msg.platform];
  if (!channel) {
    // Khong nem loi: retry cung se that bai y het, chi ton them ba lan.
    log.error({ platform: msg.platform }, 'chua co ChannelPort cho nen tang nay');
    return;
  }

  // Chi kenh web hien duoc tien do. Zalo/Messenger khong co cho de ve, nen bo qua.
  const onReactEvent =
    msg.platform === 'web'
      ? (event: ReactEvent): void => publishProgress(msg.threadId, event)
      : undefined;

  const result = await handleMessage(msg, {
    ...container,
    channel,
    ...(onReactEvent ? { onReactEvent } : {}),
  });

  if (result.ok) {
    if (result.replied) await markReplied(msg.platform, msg.messageId);
    return;
  }

  // Nguoi dung da nhan cau fallback roi. Danh dau truoc khi nem, de lan retry
  // khong gui them tin thu hai.
  await markReplied(msg.platform, msg.messageId);

  if (isRetryable(result.error)) {
    throw new Error(`upstream loi, de BullMQ retry: ${JSON.stringify(result.error)}`);
  }

  log.warn({ error: result.error }, 'that bai nhung khong retry');
});

logger.info({ concurrency: REPLY_CONCURRENCY }, 'worker reply da chay');

for (const signal of ['SIGINT', 'SIGTERM'] as const) {
  process.on(signal, () => {
    void worker.close().then(() => process.exit(0));
  });
}
