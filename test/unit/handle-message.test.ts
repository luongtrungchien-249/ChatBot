import { describe, it, expect, vi } from 'vitest';
import { handleMessage, type Deps } from '../../src/agents/pipeline/handle-message.js';
import type { InboundMessage } from '../../src/agents/domain/message.js';
import type { LoggerPort } from '../../src/agents/ports/logger.port.js';
import { HELP_TEXT } from '../../src/agents/pipeline/stages/02-mention.js';
import { BUDGET_EXCEEDED_TEXT } from '../../src/agents/pipeline/stages/05-budget-guard.js';
import { CONFIG_ERROR_TEXT, FALLBACK_TEXT } from '../../src/agents/pipeline/stages/12-generate.js';
import { isRetryable } from '../../src/agents/domain/errors.js';

/**
 * Duong ong chay duoc HOAN TOAN khong can Postgres, Redis hay API key.
 * Do la ly do ton tai cua agents/ports — neu test nay bat dau can Docker thi
 * mot rang buoc kien truc da bi pha o dau do.
 */
const BOT = 'Chien_Assistant';

const silentLogger: LoggerPort = {
  debug: () => {},
  info: () => {},
  warn: () => {},
  error: () => {},
  child: () => silentLogger,
};

function makeMsg(over: Partial<InboundMessage> = {}): InboundMessage {
  return {
    platform: 'cli',
    threadId: 't1',
    senderId: 'u1',
    senderName: 'Nam',
    text: 'deadline bao cao quy 3 la ngay nao',
    isGroup: false,
    mentionedBot: true,
    attachments: [],
    messageId: 'm1',
    timestamp: 0,
    traceId: 'tr1',
    ...over,
  };
}

function makeDeps(over: Partial<Deps> = {}) {
  const sent: { text: string }[] = [];
  const appended: { text: string; fromBot: boolean }[] = [];

  const deps: Deps = {
    llm: {
      reply: vi.fn(async () => ({
        text: 'Deadline la ngay 30/11.',
        toolCalls: [],
        usage: { inputTokens: 10, outputTokens: 5, cacheReadTokens: 0, cacheWriteTokens: 0 },
      })),
      cheap: vi.fn(async () => ''),
    },
    memory: {
      append: vi.fn(async (_s, m) => {
        appended.push({ text: m.text, fromBot: m.fromBot });
      }),
      recent: vi.fn(async () => []),
      summary: async () => null,
      facts: async () => [],
      remember: async () => undefined,
      forget: async () => [],
      list: async () => [],
    },
    knowledge: { search: async () => [] },
    channel: {
      maxMessageChars: 4000,
      typing: vi.fn(async () => {}),
      send: vi.fn(async (_s, text) => {
        sent.push({ text });
      }),
    },
    rateLimit: {
      check: async () => ({ allowed: true }),
      withinDailyBudget: vi.fn(async () => true),
    },
    clock: { now: () => new Date(0) },
    logger: silentLogger,
    accessRules: { groupPolicy: 'open', dmPolicy: 'open', allowedThreads: new Set() },
    botName: BOT,
    reply: { maxTokens: 16_000, effort: 'low' },
    recentLimit: 15,
    ...over,
  };

  return { deps, sent, appended };
}

describe('handleMessage', () => {
  it('duong hanh phuc: tra loi, ghi ca cau hoi lan cau tra loi', async () => {
    const { deps, sent, appended } = makeDeps();

    const res = await handleMessage(makeMsg(), deps);

    expect(res).toEqual({ ok: true, replied: true });
    expect(sent).toEqual([{ text: 'Deadline la ngay 30/11.' }]);
    // Thieu ban ghi fromBot thi L2 sau nay se nen mot doan doc thoai.
    expect(appended).toEqual([
      { text: 'deadline bao cao quy 3 la ngay nao', fromBot: false },
      { text: 'Deadline la ngay 30/11.', fromBot: true },
    ]);
  });

  it('thread ngoai allowlist: IM LANG, khong goi model', async () => {
    const { deps, sent } = makeDeps({
      accessRules: { groupPolicy: 'allowlist', dmPolicy: 'allowlist', allowedThreads: new Set() },
    });

    const res = await handleMessage(makeMsg(), deps);

    expect(res).toEqual({ ok: true, replied: false });
    expect(sent).toEqual([]);
    expect(deps.llm.reply).not.toHaveBeenCalled();
  });

  it('trong nhom ma khong mention: dung, khong goi model', async () => {
    const { deps, sent } = makeDeps();

    const res = await handleMessage(
      makeMsg({ isGroup: true, mentionedBot: false, text: 'chao ca nha' }),
      deps,
    );

    expect(res).toEqual({ ok: true, replied: false });
    expect(sent).toEqual([]);
    expect(deps.llm.reply).not.toHaveBeenCalled();
  });

  it('mention xong rong: tra huong dan, khong goi model', async () => {
    const { deps, sent } = makeDeps();

    const res = await handleMessage(
      makeMsg({ isGroup: true, mentionedBot: true, text: '@Chien_Assistant' }),
      deps,
    );

    expect(res).toEqual({ ok: true, replied: true });
    expect(sent).toEqual([{ text: HELP_TEXT }]);
    expect(deps.llm.reply).not.toHaveBeenCalled();
  });

  it('het ngan sach: chot chan CUNG, tu choi truoc khi goi model', async () => {
    const { deps, sent } = makeDeps();
    deps.rateLimit.withinDailyBudget = vi.fn(async () => false);

    const res = await handleMessage(makeMsg(), deps);

    expect(res).toEqual({ ok: true, replied: true });
    expect(sent).toEqual([{ text: BUDGET_EXCEEDED_TEXT }]);
    expect(deps.llm.reply).not.toHaveBeenCalled();
  });

  it('budget-guard chay TRUOC persist — khong ghi tin khi da het ngan sach', async () => {
    const { deps, appended } = makeDeps();
    deps.rateLimit.withinDailyBudget = vi.fn(async () => false);

    await handleMessage(makeMsg(), deps);

    expect(appended).toEqual([]);
  });

  it('model loi: gui fallback chu KHONG im lang, va bao loi ra ngoai', async () => {
    const { deps, sent } = makeDeps();
    deps.llm.reply = vi.fn(async () => {
      throw new Error('connection timeout');
    });

    const res = await handleMessage(makeMsg(), deps);

    expect(sent).toEqual([{ text: FALLBACK_TEXT }]);
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.error).toEqual({ kind: 'upstream_timeout', service: 'llm' });
  });

  it('API key sai: noi that la truc trac he thong, KHONG bao "thu lai sau"', async () => {
    const { deps, sent } = makeDeps();
    deps.llm.reply = vi.fn(async () => {
      // Hinh dang loi cua SDK: co truong status.
      throw Object.assign(new Error('401 Incorrect API key provided'), { status: 401 });
    });

    const res = await handleMessage(makeMsg(), deps);

    // Bao "thu lai sau" cho mot khoa sai la noi doi: thu bao nhieu lan cung hong.
    expect(sent).toEqual([{ text: CONFIG_ERROR_TEXT }]);
    expect(res.ok).toBe(false);
    if (!res.ok) {
      expect(res.error).toEqual({ kind: 'upstream_error', service: 'llm', status: 401 });
      // Va tuyet doi khong duoc retry.
      expect(isRetryable(res.error)).toBe(false);
    }
  });

  it('loi 5xx: bao thu lai sau, va DUOC retry', async () => {
    const { deps, sent } = makeDeps();
    deps.llm.reply = vi.fn(async () => {
      throw Object.assign(new Error('503 service unavailable'), { status: 503 });
    });

    const res = await handleMessage(makeMsg(), deps);

    expect(sent).toEqual([{ text: FALLBACK_TEXT }]);
    expect(res.ok).toBe(false);
    if (!res.ok) expect(isRetryable(res.error)).toBe(true);
  });

  it('model tra chuoi rong: coi la loi, khong gui tin rong', async () => {
    const { deps, sent } = makeDeps();
    deps.llm.reply = vi.fn(async () => ({
      text: '   ',
      toolCalls: [],
      usage: { inputTokens: 10, outputTokens: 0, cacheReadTokens: 0, cacheWriteTokens: 0 },
    }));

    const res = await handleMessage(makeMsg(), deps);

    expect(res.ok).toBe(false);
    expect(sent).toEqual([{ text: FALLBACK_TEXT }]);
  });

  it('ghi tin TRUOC khi goi model, de cau hoi khong bien mat khi API hong', async () => {
    const { deps, appended } = makeDeps();
    deps.llm.reply = vi.fn(async () => {
      throw new Error('500 upstream');
    });

    await handleMessage(makeMsg(), deps);

    expect(appended).toEqual([{ text: 'deadline bao cao quy 3 la ngay nao', fromBot: false }]);
  });

  it('typing khong duoc chan duong phan hoi', async () => {
    const { deps, sent } = makeDeps();
    deps.channel.typing = vi.fn(() => new Promise<void>(() => {})); // khong bao gio resolve

    const res = await handleMessage(makeMsg(), deps);

    expect(res).toEqual({ ok: true, replied: true });
    expect(sent).toHaveLength(1);
  });

  it('typing loi khong lam hong ca luot', async () => {
    const { deps, sent } = makeDeps();
    deps.channel.typing = vi.fn(async () => {
      throw new Error('kenh khong ho tro typing');
    });

    const res = await handleMessage(makeMsg(), deps);

    expect(res).toEqual({ ok: true, replied: true });
    expect(sent).toHaveLength(1);
  });
});
