import { describe, it, expect, vi } from 'vitest';
import { generate, type GenerateDeps, type ReactEvent } from '../../src/agents/pipeline/stages/12-generate.js';
import type { LlmResult, ToolCall } from '../../src/agents/ports/llm.port.js';
import type { LoggerPort } from '../../src/agents/ports/logger.port.js';
import type { ToolDefinition, ToolResult } from '../../src/agents/ports/tool.port.js';

/**
 * Vong ReAct la cho de bien thanh vong dot tien khong day. Nam chan cung duoi day
 * phai duoc chung minh, khong phai tin la co.
 */
const silentLogger: LoggerPort = {
  debug: () => {},
  info: () => {},
  warn: () => {},
  error: () => {},
  child: () => silentLogger,
};

const ctx = { scope: { platform: 'web' as const, threadId: 't1' }, senderId: 'u1', traceId: 'tr1' };
const prompt = { system: 'SYS', messages: [{ role: 'user' as const, content: 'hoi gi do' }], trimmed: {} };

const usage = { inputTokens: 10, outputTokens: 5, cacheReadTokens: 0, cacheWriteTokens: 0 };

const answer = (text: string): LlmResult => ({
  text,
  toolCalls: [],
  usage,
  finishReason: 'stop',
});

const wantsTools = (...names: string[]): LlmResult => ({
  text: '',
  toolCalls: names.map((name, i) => ({ id: `call-${i}`, name, input: { query: 'x' } })),
  usage,
  finishReason: 'tool_calls',
});

const TOOL_DEF: ToolDefinition = {
  name: 'web_search',
  description: 'tim web',
  parameters: { type: 'object' },
  requirements: { rateLimit: '-', costPerCall: '-', timeoutMs: 1000 },
  returns: '-',
  failureModes: [],
};

function makeDeps(replies: LlmResult[], over: Partial<GenerateDeps> = {}) {
  const events: ReactEvent[] = [];
  let call = 0;

  const deps: GenerateDeps = {
    llm: {
      reply: vi.fn(async () => replies[Math.min(call++, replies.length - 1)]!),
      cheap: vi.fn(async () => ''),
    },
    tools: {
      specs: () => [TOOL_DEF],
      callMany: vi.fn(
        async (calls: readonly ToolCall[]): Promise<readonly ToolResult[]> =>
          calls.map((c) => ({
            toolCallId: c.id,
            name: c.name,
            content: `<ket_qua_cong_cu>ket qua cho ${c.name}</ket_qua_cong_cu>`,
            ok: true,
            latencyMs: 5,
          })),
      ),
    },
    rateLimit: { check: async () => ({ allowed: true }), withinDailyBudget: async () => true },
    maxTokens: 16_000,
    effort: 'low',
    maxIterations: 5,
    maxToolCalls: 8,
    deadlineMs: 60_000,
    onEvent: (e) => events.push(e),
    ...over,
  };

  return { deps, events };
}

describe('vong ReAct — duong hanh phuc', () => {
  it('khong goi cong cu thi tra loi ngay, dung mot vong', async () => {
    const { deps } = makeDeps([answer('Deadline la 30/11.')]);

    const res = await generate(deps, prompt, ctx, silentLogger);

    expect(res).toEqual({ ok: true, value: 'Deadline la 30/11.' });
    expect(deps.llm.reply).toHaveBeenCalledTimes(1);
    expect(deps.tools.callMany).not.toHaveBeenCalled();
  });

  it('goi cong cu roi tra loi: hai vong, ket qua vao role tool', async () => {
    const { deps, events } = makeDeps([wantsTools('web_search'), answer('Hom nay Ha Noi 30 do.')]);

    const res = await generate(deps, prompt, ctx, silentLogger);

    expect(res).toEqual({ ok: true, value: 'Hom nay Ha Noi 30 do.' });
    expect(deps.tools.callMany).toHaveBeenCalledTimes(1);

    // Luot thu hai phai mang theo ca luot assistant co toolCalls lan luot tool.
    const second = vi.mocked(deps.llm.reply).mock.calls[1]?.[0];
    const roles = second?.messages.map((m) => m.role);
    expect(roles).toEqual(['user', 'assistant', 'tool']);

    expect(events.map((e) => e.type)).toEqual(['tool_call', 'observation']);
  });

  it('parallel tool calling: nhieu cong cu trong MOT luot, mot lan callMany', async () => {
    const { deps, events } = makeDeps([
      wantsTools('web_search', 'paper_search'),
      answer('Xong.'),
    ]);

    await generate(deps, prompt, ctx, silentLogger);

    // Mot lan goi voi CA HAI — khong phai hai lan goi tuan tu.
    expect(deps.tools.callMany).toHaveBeenCalledTimes(1);
    expect(vi.mocked(deps.tools.callMany).mock.calls[0]?.[0]).toHaveLength(2);

    // Ca hai ket qua vao CUNG mot luot tiep theo.
    const second = vi.mocked(deps.llm.reply).mock.calls[1]?.[0];
    expect(second?.messages.filter((m) => m.role === 'tool')).toHaveLength(2);

    const toolEvent = events.find((e) => e.type === 'tool_call');
    expect(toolEvent).toMatchObject({ tools: ['web_search', 'paper_search'] });
  });
});

describe('vong ReAct — nam chan cung', () => {
  it('chan 1: het so vong thi dung va noi ro la chua day du', async () => {
    // Model doi hoi cong cu mai mai.
    const { deps } = makeDeps([wantsTools('web_search')], { maxIterations: 3 });

    const res = await generate(deps, prompt, ctx, silentLogger);

    expect(deps.llm.reply).toHaveBeenCalledTimes(3);
    // Vong cuoi KHONG duoc dua tool nua, de model buoc phai ket luan.
    expect(vi.mocked(deps.llm.reply).mock.calls[2]?.[0].tools).toBeUndefined();
    expect(res.ok).toBe(false); // khong co van ban nao -> bao loi de gui fallback
  });

  it('chan 1b: het vong nhung DA co van ban thi tra ve kem ghi chu', async () => {
    const withText: LlmResult = { ...wantsTools('web_search'), text: 'Minh tim duoc mot phan.' };
    const { deps } = makeDeps([withText], { maxIterations: 2 });

    const res = await generate(deps, prompt, ctx, silentLogger);

    expect(res.ok).toBe(true);
    if (res.ok) {
      expect(res.value).toContain('Minh tim duoc mot phan.');
      expect(res.value).toContain('chưa đầy đủ');
    }
  });

  it('chan 2: khong bao gio vuot tong so loi goi cong cu', async () => {
    const { deps } = makeDeps([wantsTools('web_search', 'paper_search')], {
      maxIterations: 5,
      maxToolCalls: 3,
    });

    await generate(deps, prompt, ctx, silentLogger);

    const total = vi
      .mocked(deps.tools.callMany)
      .mock.calls.reduce((sum, [calls]) => sum + calls.length, 0);
    expect(total).toBeLessThanOrEqual(3);
  });

  it('chan 3: qua deadline thi dung, khong bat dau vong moi', async () => {
    const { deps } = makeDeps([wantsTools('web_search')], { deadlineMs: -1 });

    const res = await generate(deps, prompt, ctx, silentLogger);

    expect(deps.llm.reply).not.toHaveBeenCalled();
    expect(res.ok).toBe(false);
  });

  it('chan 4: ngan sach duoc kiem tra lai TRUOC MOI VONG', async () => {
    const withinDailyBudget = vi.fn(async () => true);
    const { deps } = makeDeps([wantsTools('web_search'), wantsTools('web_search'), answer('Xong.')], {
      rateLimit: { check: async () => ({ allowed: true }), withinDailyBudget },
    });

    await generate(deps, prompt, ctx, silentLogger);

    // Ba vong -> ba lan kiem tra. Mot lan o stage 5 la khong du: mot cau hoi gio
    // co the ton nhieu lan goi model.
    expect(withinDailyBudget).toHaveBeenCalledTimes(3);
  });

  it('chan 4b: het ngan sach giua chung thi dung ngay', async () => {
    let calls = 0;
    const withinDailyBudget = vi.fn(async () => {
      calls += 1;
      return calls === 1; // vong dau con tien, vong sau het
    });
    const withText: LlmResult = { ...wantsTools('web_search'), text: 'Mot phan ket qua.' };
    const { deps } = makeDeps([withText], {
      rateLimit: { check: async () => ({ allowed: true }), withinDailyBudget },
    });

    const res = await generate(deps, prompt, ctx, silentLogger);

    expect(deps.llm.reply).toHaveBeenCalledTimes(1);
    expect(res.ok).toBe(true);
    if (res.ok) expect(res.value).toContain('chưa đầy đủ');
  });
});

describe('vong ReAct — loi', () => {
  it('cong cu that bai van tra ket qua, vong lap di tiep', async () => {
    const { deps, events } = makeDeps([wantsTools('web_search'), answer('Minh chua tra cuu duoc.')]);
    deps.tools.callMany = vi.fn(async (calls: readonly ToolCall[]) =>
      calls.map((c) => ({
        toolCallId: c.id,
        name: c.name,
        content: 'Cong cu loi.',
        ok: false,
        latencyMs: 3,
      })),
    );

    const res = await generate(deps, prompt, ctx, silentLogger);

    expect(res).toEqual({ ok: true, value: 'Minh chua tra cuu duoc.' });
    expect(events.some((e) => e.type === 'observation' && !e.ok)).toBe(true);
  });

  it('401 khong duoc phan loai thanh timeout', async () => {
    const { deps } = makeDeps([answer('x')]);
    deps.llm.reply = vi.fn(async () => {
      throw Object.assign(new Error('401 Incorrect API key'), { status: 401 });
    });

    const res = await generate(deps, prompt, ctx, silentLogger);

    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.error).toEqual({ kind: 'upstream_error', service: 'llm', status: 401 });
  });

  it('khong co cong cu nao bat thi khong gui tham so tools', async () => {
    const { deps } = makeDeps([answer('Tra loi bang kien thuc san co.')], {
      tools: { specs: () => [], callMany: vi.fn(async () => []) },
    });

    await generate(deps, prompt, ctx, silentLogger);

    expect(vi.mocked(deps.llm.reply).mock.calls[0]?.[0].tools).toBeUndefined();
  });
});
