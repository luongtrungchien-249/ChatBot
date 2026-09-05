import OpenAI from 'openai';
import type {
  LlmMessage,
  LlmPort,
  LlmResult,
  LlmUsage,
  ToolCall,
  ToolSpec,
} from '../agents/ports/llm.port.js';
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
): readonly ToolCall[] {
  const out: ToolCall[] = [];
  for (const call of message.tool_calls ?? []) {
    if (call.type !== 'function') continue;

    // arguments hong van phai tra ve loi goi, KHONG duoc bo qua: moi tool_call
    // deu can mot tool_result khop id, thieu mot cai la ca request sau 400.
    let input: Record<string, unknown> = {};
    try {
      // Luon JSON.parse, khong bao gio so khop chuoi tho tren arguments.
      input = JSON.parse(call.function.arguments) as Record<string, unknown>;
    } catch {
      logger.error(
        { traceId, tool: call.function.name },
        'arguments cua tool khong phai JSON hop le — goi voi input rong',
      );
    }
    out.push({ id: call.id, name: call.function.name, input });
  }
  return out;
}

/** Chuyen hop dong LlmMessage sang dang OpenAI. Union nen phai map tung nhanh. */
function toOpenAiMessages(
  system: string,
  messages: readonly LlmMessage[],
): OpenAI.Chat.ChatCompletionMessageParam[] {
  const out: OpenAI.Chat.ChatCompletionMessageParam[] = [
    // system dat dau va la HANG SO -> prompt caching bat duoc tien to nay.
    { role: 'system', content: system },
  ];

  for (const m of messages) {
    if (m.role === 'user') {
      out.push({ role: 'user', content: m.content });
    } else if (m.role === 'tool') {
      out.push({ role: 'tool', tool_call_id: m.toolCallId, content: m.content });
    } else if (m.toolCalls && m.toolCalls.length > 0) {
      out.push({
        role: 'assistant',
        content: m.content === '' ? null : m.content,
        tool_calls: m.toolCalls.map((c) => ({
          id: c.id,
          type: 'function' as const,
          function: { name: c.name, arguments: JSON.stringify(c.input) },
        })),
      });
    } else {
      out.push({ role: 'assistant', content: m.content });
    }
  }

  return out;
}

function toFinishReason(reason: string | null | undefined): LlmResult['finishReason'] {
  if (reason === 'stop' || reason === 'tool_calls' || reason === 'length') return reason;
  return 'other';
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
          messages: toOpenAiMessages(req.system, req.messages),
          ...(req.tools && req.tools.length > 0
            ? {
                tools: toOpenAiTools(req.tools),
                // Model tu quyet dinh goi hay khong. Ep goi (tool_choice: 'required')
                // se lam no goi ca khi cau hoi khong can tra cuu gi.
                tool_choice: 'auto' as const,
                // Parallel tool calling la MAC DINH cua OpenAI. Khong tat.
              }
            : {}),
        },
        { timeout: REPLY_TIMEOUT_MS, maxRetries: 0 },
      );

      const usage = toUsage(res.usage);
      const choice = res.choices[0];
      if (!choice) throw new Error('OpenAI tra ve response khong co choice nao');

      const text = choice.message.content ?? '';
      const toolCalls = parseToolCalls(choice.message, req.ctx.traceId);

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
        value: { text, toolCalls, usage, finishReason: toFinishReason(choice.finish_reason) },
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
