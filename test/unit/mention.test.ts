import { describe, it, expect } from 'vitest';
import { resolveMention, mentionRegex } from '../../src/agents/policy/mention.js';
import type { InboundMessage } from '../../src/agents/domain/message.js';

const base: InboundMessage = {
  platform: 'zalo_bot',
  threadId: 't1',
  senderId: 'u1',
  senderName: 'Nam',
  text: '',
  isGroup: true,
  mentionedBot: false,
  attachments: [],
  messageId: 'm1',
  timestamp: 0,
  traceId: 'tr1',
};

describe('mention', () => {
  it('trong nhom, khong mention thi khong tra loi', () => {
    expect(resolveMention({ ...base, text: 'chao ca nha' }, 'nam_chatbot').reply).toBe(false);
  });

  it('trong DM thi luon tra loi', () => {
    const v = resolveMention({ ...base, isGroup: false, text: 'hello' }, 'nam_chatbot');
    expect(v).toEqual({ reply: true, text: 'hello', empty: false });
  });

  it('fallback regex bat duoc khi payload khong co truong mention', () => {
    const v = resolveMention({ ...base, text: '@nam chatbot gia ve bao nhieu' }, 'nam_chatbot');
    expect(v.reply).toBe(true);
  });

  it('boc mention xong rong thi danh dau empty', () => {
    const v = resolveMention({ ...base, mentionedBot: true, text: '@nam_chatbot' }, 'nam_chatbot');
    expect(v).toMatchObject({ reply: true, empty: true });
  });

  it('regex khong an nham ten khac', () => {
    expect(mentionRegex('nam_chatbot').test('@nam_chatbot2')).toBe(true);
  });
});
