import { randomUUID } from 'node:crypto';
import type { InboundMessage } from '../../agents/domain/message.js';

/**
 * Adapter thu tu. Mot phien chat web = mot threadId, nen ThreadScope dung lai y
 * nguyen — memory va hang rao chong ro ri cross-thread ap dung cho web ma khong
 * phai viet them dong nao.
 */
export type WebChatBody = Readonly<{ threadId: string; text: string }>;

export const WEB_SENDER_ID = 'web-user';
export const WEB_MAX_MESSAGE_CHARS = 8_000;

/** Kenh Redis pub/sub cho mot thread. api SUBSCRIBE, worker PUBLISH. */
export const webChannelKey = (threadId: string): string => `web:out:${threadId}`;

/** Su kien day xuong SSE. UI hien duoc bot dang lam gi, khong chi cau tra loi cuoi. */
export type WebEvent =
  | { type: 'typing' }
  | { type: 'final'; text: string }
  // TODO(giai-doan-2B): 'thought' | 'tool_call' | 'observation' cho vong ReAct.
  | { type: 'error'; text: string };

export function normalizeWebInput(body: WebChatBody): InboundMessage {
  return {
    platform: 'web',
    threadId: body.threadId,
    senderId: WEB_SENDER_ID,
    senderName: 'Bạn',
    text: body.text,
    // Web la hoi thoai 1-1: khong can mention.
    isGroup: false,
    mentionedBot: true,
    attachments: [],
    messageId: randomUUID(),
    timestamp: Date.now(),
    traceId: randomUUID(),
  };
}
