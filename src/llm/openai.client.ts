import OpenAI from 'openai';
import type { LlmPort, LlmResult, LlmUsage, ToolSpec } from '../agents/ports/llm.port.js';
import { config } from '../config/index.js';
import { logger } from '../infra/logger.js';
import { record } from './cost-meter.js';
import { MODELS, REPLY_TIMEOUT_MS, type Route } from './models.js';

/**
 * Boc SDK OpenAI, implement LlmPort. Day la NOI DUY NHAT trong codebase biet
 * ten nha cung cap. Doi provider = viet lai mot file nay, agents/ khong doi mot dong.
 */
const client = new OpenAI({ apiKey: config.OPENAI_API_KEY });

const EMPTY_USAGE: LlmUsage = {
  inputTokens: 0,
  outputTokens: 0,
  cacheReadTokens: 0,
  cacheWriteTokens: 0,
};

/**
 * Chuan hoa usage cua OpenAI ve hop dong cua LlmPort.
 *
 * BAY: prompt_tokens cua OpenAI la TONG input, DA BAO GOM phan doc tu cache.
 * Hop dong LlmUsage.inputTokens la phan tinh gia day du, nen phai tru ra.
 * Cong ca hai vao rieng nhau se tinh tien thua phan cache.
 *
 * OpenAI khong tinh phi ghi cache -> cacheWriteTokens luon 0 (cot van giu trong
 * usage_log de khong phai doi schema neu sau nay doi nha cung cap).
 */
function toUsage(u: OpenAI.Completions.CompletionUsage | undefined): LlmUsage {
  if (!u) return EMPTY_USAGE;
  const cached = u.prompt_tokens_details?.cached_tokens ?? 0;
  return {
    inputTokens: Math.max(0, u.prompt_tokens - cached),
    outputTokens: u.completion_tokens,
    cacheReadTokens: cached,
    cacheWriteTokens: 0,
  };
}

function toOpenAiTools(tools: readonly ToolSpec[]): OpenAI.Chat.ChatCompletionTool[] {
  return tools.map((t) => ({
    type: 'function',
    function: { name: t.name, description: t.description, parameters: t.inputSchema },
  }));
}

function parseToolCalls(
  message: OpenAI.Chat.ChatCompletionMessage,
  traceId: string,
): LlmResult['toolCalls'] {
  const out: { name: string; input: Record<string, unknown> }[] = [];
  for (const call of message.tool_calls ?? []) {
    if (call.type !== 'function') continue;
    try {
      // Luon JSON.parse, khong bao gio so khop chuoi tho tren arguments.
      out.push({ name: call.function.name, input: JSON.parse(call.function.arguments) });
    } catch {
      logger.error({ traceId, tool: call.function.name }, 'arguments cua tool khong phai JSON hop le');
    }
  }
  return out;
}

/** Gom phan lap lai cua reply() va cheap(): do thoi gian, ghi cost du thanh hay bai. */
async function measured<T>(
  route: Route,
  ctx: { scope: LlmUsageCtx['scope']; senderId: string; traceId: string },
  call: () => Promise<{ value: T; usage: LlmUsage }>,
): Promise<T> {
  const started = Date.now();
  let usage = EMPTY_USAGE;
  let ok = false;
  try {
    const res = await call();
    usage = res.usage;
    ok = true;
    return res.value;
  } finally {
    // L6: moi loi goi ra ngoai deu duoc do cost, ke ca lan that bai.
    await record({
      route,
      usage,
      scope: ctx.scope,
      senderId: ctx.senderId,
      traceId: ctx.traceId,
      latencyMs: Date.now() - started,
      ok,
    });
  }
}

type LlmUsageCtx = Parameters<LlmPort['reply']>[0]['ctx'];

export const llm: LlmPort = {
  async reply(req) {
    const model = MODELS.reply;

    return measured('reply', req.ctx, async () => {
      const res = await client.chat.completions.create(
        {
          model: model.id,
          // KHONG phai max_tokens: model reasoning dung max_completion_tokens,
          // va token reasoning an vao cap nay. Xem canh bao trong models.ts.
          max_completion_tokens: req.maxTokens,
          reasoning_effort: req.effort,
          messages: [
            // system dat dau va la HANG SO -> prompt caching bat duoc tien to nay.
            { role: 'system', content: req.system },
            ...req.messages.map((m) => ({ role: m.role, content: m.content })),
          ],
          ...(req.tools ? { tools: toOpenAiTools(req.tools) } : {}),
        },
        { timeout: REPLY_TIMEOUT_MS, maxRetries: 0 },
      );

      const usage = toUsage(res.usage);
      const choice = res.choices[0];
      if (!choice) throw new Error('OpenAI tra ve response khong co choice nao');

      const text = choice.message.content ?? '';

      // Cap het truoc khi model kip viet cau tra loi: content rong, khong loi nao
      // duoc nem. Phai bat o day, neu khong bot se "im lang" mot cach bi an.
      if (choice.finish_reason === 'length' && text === '') {
        logger.error(
          {
            traceId: req.ctx.traceId,
            maxCompletionTokens: req.maxTokens,
            reasoningTokens: res.usage?.completion_tokens_details?.reasoning_tokens,
          },
          'het max_completion_tokens truoc khi co cau tra loi — nang cap trong models.ts',
        );
      }

      return {
        value: { text, toolCalls: parseToolCalls(choice.message, req.ctx.traceId), usage },
        usage,
      };
    });
  },

  async cheap(req) {
    const model = MODELS[req.route];

    return measured(req.route, req.ctx, async () => {
      const res = await client.chat.completions.create({
        model: model.id,
        max_completion_tokens: req.maxTokens,
        reasoning_effort: model.effort,
        messages: [
          { role: 'system', content: req.system },
          { role: 'user', content: req.input },
        ],
      });

      return { value: res.choices[0]?.message.content ?? '', usage: toUsage(res.usage) };
    });
  },
};
