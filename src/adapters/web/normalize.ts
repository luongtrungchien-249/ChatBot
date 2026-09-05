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

/**
 * Su kien day xuong SSE. UI hien duoc bot dang lam gi, khong chi cau tra loi cuoi.
 *
 * Khong stream tung token: LlmPort chua co streaming, va vong ReAct xen ke tool call
 * lam streaming roi. Doi lai, voi mot agent co cong cu thi xem no dang GOI GI con ro
 * hon xem tung chu hien ra.
 */
export type WebEvent =
  | { type: 'typing' }
  | { type: 'thought'; iteration: number; text: string }
  | { type: 'tool_call'; iteration: number; tools: readonly string[] }
  | { type: 'observation'; iteration: number; tool: string; ok: boolean; latencyMs: number }
  | { type: 'final'; text: string }
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
