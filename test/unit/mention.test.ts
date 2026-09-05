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
    expect(resolveMention({ ...base, text: 'chao ca nha' }, 'Chien_Assistant').reply).toBe(false);
  });

  it('trong DM thi luon tra loi', () => {
    const v = resolveMention({ ...base, isGroup: false, text: 'hello' }, 'Chien_Assistant');
    expect(v).toEqual({ reply: true, text: 'hello', empty: false });
  });

  it('fallback regex bat duoc khi payload khong co truong mention', () => {
    const v = resolveMention({ ...base, text: '@chien assistant gia ve bao nhieu' }, 'Chien_Assistant');
    expect(v.reply).toBe(true);
  });

  it('boc mention xong rong thi danh dau empty', () => {
    const v = resolveMention({ ...base, mentionedBot: true, text: '@Chien_Assistant' }, 'Chien_Assistant');
    expect(v).toMatchObject({ reply: true, empty: true });
  });

  it('regex khong an nham ten khac', () => {
    // '@Chien_Assistant2' la mot nguoi dung KHAC, khong phai bot.
    expect(mentionRegex('Chien_Assistant').test('@Chien_Assistant2')).toBe(false);
    expect(mentionRegex('Chien_Assistant').test('@Chien_Assistant')).toBe(true);
    // \p{L} chan ca chu co dau, khong chi [A-Za-z].
    expect(mentionRegex('Chien_Assistant').test('@Chiến Assistantừ')).toBe(false);
  });

  /**
   * BOT_MENTION_NAME viet khong dau vi nen tang thuong khong cho dat ten co dau,
   * nhung nguoi Viet GO CO DAU. Truot cac case nay nghia la bot im lang truoc
   * dung cach goi tu nhien nhat.
   */
  it('bat duoc mention go CO DAU du ten dang ky khong dau', () => {
    for (const text of [
      '@Chiến Assistant giá bao nhiêu',
      '@Chiến_Assistant giá bao nhiêu',
      '@chiến assistant deadline?',
    ]) {
      expect(resolveMention({ ...base, text }, 'Chien_Assistant').reply, text).toBe(true);
    }
  });

  it('boc dung doan mention co dau ra khoi cau hoi', () => {
    const v = resolveMention(
      { ...base, text: '@Chiến Assistant giá vé bao nhiêu' },
      'Chien_Assistant',
    );
    expect(v).toEqual({ reply: true, text: 'giá vé bao nhiêu', empty: false });
  });
});
