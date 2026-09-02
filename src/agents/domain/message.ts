import type { Platform, ThreadScope } from './thread.js';

export type Attachment = Readonly<{
  kind: 'image' | 'file' | 'audio' | 'video' | 'sticker' | 'unknown';
  url?: string;
  mimeType?: string;
}>;

/** Hop dong chung giua adapter va agents. Agents khong biet Zalo hay Messenger la gi. */
export type InboundMessage = Readonly<{
  platform: Platform;
  threadId: string;
  senderId: string;
  senderName: string;
  text: string;
  isGroup: boolean;
  mentionedBot: boolean;
  replyTo?: { id: string; text: string };
  /** Phase 1: chua xu ly. Bot tra loi "minh chua xem duoc anh". Khong de truong chet. */
  attachments: readonly Attachment[];
  messageId: string;
  timestamp: number;
  traceId: string;
}>;

export type OutboundMessage = Readonly<{
  threadId: string;
  text: string;
  replyTo?: string;
}>;

export type StoredMessage = Readonly<{
  senderId: string;
  senderName: string;
  text: string;
  createdAt: Date;
  fromBot: boolean;
}>;

export function scopeOf(msg: InboundMessage): ThreadScope {
  return { platform: msg.platform, threadId: msg.threadId };
}
