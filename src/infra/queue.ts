import { Queue, Worker, type Processor } from 'bullmq';
import { Redis } from 'ioredis';
import type { InboundMessage } from '../agents/domain/message.js';
import type { Platform } from '../agents/domain/thread.js';
import { config } from '../config/index.js';
import { logger } from './logger.js';

/**
 * Ba queue TACH BIET. Khong tron: mot job ingest 10 phut khong duoc phep chan
 * mot cau tra loi.
 */
export const QUEUE = {
  reply: 'reply',
  maintenance: 'maintenance',
  ingest: 'ingest',
} as const;

/**
 * FIFO theo thread.
 *
 * ARCHITECTURE.md section 5.2 viet `group: '{platform}:{threadId}'` — nhung `group`
 * la tinh nang cua BullMQ **Pro** (tra phi), khong co trong ban OSS. Da kiem tra
 * toan bo typings bullmq 5.81.4: khong co truong nao ten group.
 *
 * Khong co FIFO per-thread thi hai tin lien tiep trong mot nhom chay song song va
 * bot TRA LOI SAI THU TU — dung van de section 5.2 neu ra.
 *
 * Giai phap tuan 1: tuan tu toan cuc. Tran thong luong ~240 cau/gio o truong hop
 * xau nhat (timeout 15s moi cau), trong khi muc tieu la 200-1000 cau mot NGAY.
 * Khi nao cham tran thi chon: mua BullMQ Pro, hoac tu khoa phan tan per-thread
 * bang Redis. Khong giai quyet som mot van de chua co.
 */
export const REPLY_CONCURRENCY = 1;

/** BullMQ bat buoc maxRetriesPerRequest: null — khong dung chung client voi infra/redis.ts. */
function connection(): Redis {
  return new Redis(config.REDIS_URL, { maxRetriesPerRequest: null });
}

const defaultJobOptions = {
  attempts: 3,
  backoff: { type: 'exponential', delay: 2000 },
  removeOnComplete: { count: 1_000 },
  removeOnFail: { count: 5_000 },
} as const;

export const replyQueue = new Queue<InboundMessage>(QUEUE.reply, {
  connection: connection(),
  defaultJobOptions,
});

export const maintenanceQueue = new Queue(QUEUE.maintenance, {
  connection: connection(),
  defaultJobOptions,
});

export const ingestQueue = new Queue(QUEUE.ingest, {
  connection: connection(),
  defaultJobOptions,
});

/**
 * jobId = khoa chinh cua tin nhan. Lop chong trung thu HAI, sau SET NX o dedupe.ts.
 *
 * Dung '-' chu KHONG dung ':' — BullMQ tu choi jobId co dau hai cham
 * ("Custom Id cannot contain :") vi no dung ':' lam phan cach trong khoa Redis.
 * Cac khoa Redis khac trong du an van dung ':' binh thuong; rang buoc nay chi cua
 * rieng jobId.
 */
export function jobIdFor(platform: Platform, messageId: string): string {
  return `${platform}-${messageId}`;
}

export async function enqueueReply(msg: InboundMessage): Promise<void> {
  await replyQueue.add(QUEUE.reply, msg, { jobId: jobIdFor(msg.platform, msg.messageId) });
}

export function createReplyWorker(
  processor: Processor<InboundMessage, void>,
): Worker<InboundMessage, void> {
  const worker = new Worker<InboundMessage, void>(QUEUE.reply, processor, {
    connection: connection(),
    concurrency: REPLY_CONCURRENCY,
  });

  worker.on('failed', (job, err) => {
    logger.error({ jobId: job?.id, attempts: job?.attemptsMade, err: err.message }, 'job that bai');
  });

  return worker;
}

export async function closeQueues(): Promise<void> {
  await Promise.all([replyQueue.close(), maintenanceQueue.close(), ingestQueue.close()]);
}
