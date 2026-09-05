import { randomUUID } from 'node:crypto';
import type { InboundMessage } from '../../agents/domain/message.js';

/**
 * Adapter thu BA. Cach duy nhat de lam Phase 0 khi chua co token Zalo/Meta.
 *
 * Day khong phai do choi: neu agents/ chi chay duoc khi co webhook that thi kien
 * truc da sai tu dau. Cung dung lam adapter tham chieu — Zalo va Messenger phai
 * chuan hoa ra DUNG hinh dang nay.
 */
const CLI_THREAD_ID = 'local';
const CLI_SENDER_ID = 'local-user';

export function normalizeCliInput(line: string, senderName = 'Ban'): InboundMessage {
  return {
    platform: 'cli',
    threadId: CLI_THREAD_ID,
    senderId: CLI_SENDER_ID,
    senderName,
    text: line,
    // DM: khong can mention. Xem policy/mention.ts — ngoai nhom thi luon tra loi.
    isGroup: false,
    mentionedBot: true,
    attachments: [],
    messageId: randomUUID(),
    timestamp: Date.now(),
    // L8: mot traceId cho moi tin, xuyen suot moi log cua luot nay.
    traceId: randomUUID(),
  };
}

/** ChannelPort cua CLI: in ra terminal. Khong co gioi han ky tu that su. */
export const CLI_MAX_MESSAGE_CHARS = 4_000;
