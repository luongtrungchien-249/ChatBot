import type { BotError } from '../../domain/errors.js';
import type { CallContext, LlmMessage, LlmPort } from '../../ports/llm.port.js';
import type { LoggerPort } from '../../ports/logger.port.js';
import type { RateLimitPort } from '../../ports/ratelimit.port.js';
import { toSpec, type ToolPort } from '../../ports/tool.port.js';
import { err, ok, type Result } from '../../../shared/result.js';
import type { BuiltPrompt } from './11-build-prompt.js';

/**
 * Stage 12: vong ReAct — Thought -> Action -> Observation -> lap.
 *
 * VONG NAY NAM TRONG PIPELINE, KHONG THAY THE PIPELINE. Stage 1-11 van lo policy,
 * chong trung, ngan sach, dung ngu canh; stage 13-15 van lo gui va ghi so. ReAct
 * khong tu co lop an toan nao trong so do.
 *
 * Nam chan cung. Thieu cai nao cung thanh vong dot tien khong day:
 *   1. So vong toi da
 *   2. Tong so loi goi cong cu
 *   3. Deadline treo dong ho
 *   4. Ngan sach ngay — kiem tra lai TRUOC MOI VONG, vi mot cau hoi gio co the
 *      ton nhieu lan goi model
 *   5. Tran kich thuoc observation (ap trong tools/guard.ts)
 */
export const FALLBACK_TEXT =
  'Xin lỗi, mình đang bị chậm nên chưa trả lời được câu này. Bạn thử hỏi lại sau một chút nhé.';

export const CONFIG_ERROR_TEXT =
  'Mình đang gặp trục trặc kỹ thuật ở phía hệ thống, chưa trả lời được. Bạn báo giúp người quản trị nhé.';

/** Het vong ma chua co cau tra loi. KHONG im lang, va KHONG noi doi la da tim xong. */
const INCOMPLETE_SUFFIX =
  '\n\n(Mình phải dừng tra cứu ở đây nên câu trả lời có thể chưa đầy đủ.)';

/** Doc HTTP status tu loi cua SDK ma khong phai import SDK (L1: agents khong biet llm). */
function statusOf(error: unknown): number | undefined {
  if (typeof error === 'object' && error !== null && 'status' in error) {
    const { status } = error as { status: unknown };
    if (typeof status === 'number') return status;
  }
  return undefined;
}

/** Su kien de UI hien duoc bot dang lam gi. Adapter nao khong quan tam thi bo qua. */
export type ReactEvent =
  | { type: 'thought'; iteration: number; text: string }
  | { type: 'tool_call'; iteration: number; tools: readonly string[] }
  | { type: 'observation'; iteration: number; tool: string; ok: boolean; latencyMs: number };

export type GenerateDeps = Readonly<{
  llm: LlmPort;
  tools: ToolPort;
  rateLimit: RateLimitPort;
  maxTokens: number;
  effort: 'low' | 'medium' | 'high';
  maxIterations: number;
  maxToolCalls: number;
  deadlineMs: number;
  /** Khong await: bao tien do khong duoc chan duong tra loi. */
  onEvent?: (event: ReactEvent) => void;
}>;

export async function generate(
  deps: GenerateDeps,
  prompt: BuiltPrompt,
  ctx: CallContext,
  logger: LoggerPort,
): Promise<Result<string, BotError>> {
  const deadline = Date.now() + deps.deadlineMs;
  const specs = deps.tools.specs().map(toSpec);
  const messages: LlmMessage[] = [...prompt.messages];

  let toolCallsUsed = 0;
  let lastText = '';

  for (let iteration = 1; iteration <= deps.maxIterations; iteration += 1) {
    // Chan 4: ngan sach kiem tra lai MOI VONG, khong phai mot lan o stage 5.
    if (!(await deps.rateLimit.withinDailyBudget())) {
      logger.warn({ iteration }, 'het ngan sach giua vong ReAct — dung lai');
      return finish(lastText, true, logger, { reason: 'budget', iteration });
    }

    // Chan 3: deadline. Con qua it thoi gian thi dung, dung bat dau mot vong nua.
    if (Date.now() > deadline) {
      logger.warn({ iteration }, 'het deadline ReAct');
      return finish(lastText, true, logger, { reason: 'deadline', iteration });
    }

    // Het luot goi cong cu thi van cho model noi not, nhung khong dua tool nua.
    const outOfToolCalls = toolCallsUsed >= deps.maxToolCalls;
    const lastIteration = iteration === deps.maxIterations;
    const offerTools = specs.length > 0 && !outOfToolCalls && !lastIteration;

    let result;
    try {
      result = await deps.llm.reply({
        system: prompt.system,
        messages,
        maxTokens: deps.maxTokens,
        effort: deps.effort,
        ...(offerTools ? { tools: specs } : {}),
        ctx,
      });
    } catch (e) {
      return err(classify(e, logger));
    }

    if (result.text !== '') lastText = result.text;

    // Model da tra loi xong, khong goi them cong cu nao.
    if (result.toolCalls.length === 0) {
      if (result.text.trim() === '') {
        logger.error({ iteration, usage: result.usage }, 'model tra ve chuoi rong');
        return err({ kind: 'upstream_error', service: 'llm' });
      }
      logger.info({ iteration, toolCallsUsed }, 'ReAct ket thuc');
      return ok(result.text);
    }

    // --- Co loi goi cong cu: Action ---
    const calls = result.toolCalls.slice(0, deps.maxToolCalls - toolCallsUsed);
    toolCallsUsed += calls.length;

    if (result.text !== '') {
      deps.onEvent?.({ type: 'thought', iteration, text: result.text });
    }
    deps.onEvent?.({ type: 'tool_call', iteration, tools: calls.map((c) => c.name) });

    // Luot assistant phai mang DUNG cac tool call, neu khong ket qua se khong khop.
    messages.push({ role: 'assistant', content: result.text, toolCalls: calls });

    // --- Observation: chay SONG SONG, tra ve DU so ket qua ---
    const observations = await deps.tools.callMany(calls, ctx);

    for (const obs of observations) {
      deps.onEvent?.({
        type: 'observation',
        iteration,
        tool: obs.name,
        ok: obs.ok,
        latencyMs: obs.latencyMs,
      });
      // Ket qua cong cu vao role 'tool', TUYET DOI khong vao 'system': van ban nay
      // do nguoi la soan, khong duoc mang tham quyen cua he thong.
      messages.push({ role: 'tool', toolCallId: obs.toolCallId, content: obs.content });
    }
  }

  // Chan 1: het so vong.
  logger.warn({ toolCallsUsed }, 'het so vong ReAct');
  return finish(lastText, true, logger, { reason: 'max_iterations', iteration: deps.maxIterations });
}

/**
 * Ket thuc som. Co van ban thi tra ve kem ghi chu chua day du; khong co gi thi bao
 * loi de stage tren gui cau fallback.
 */
function finish(
  text: string,
  incomplete: boolean,
  logger: LoggerPort,
  meta: { reason: string; iteration: number },
): Result<string, BotError> {
  if (text.trim() === '') {
    logger.warn(meta, 'dung vong ReAct khi chua co van ban nao');
    return err({ kind: 'upstream_timeout', service: 'llm' });
  }
  return ok(incomplete ? text + INCOMPLETE_SUFFIX : text);
}

function classify(e: unknown, logger: LoggerPort): BotError {
  const message = e instanceof Error ? e.message : String(e);
  const status = statusOf(e);

  if (status === 401 || status === 403) {
    // Loi cua NGUOI VAN HANH, khong phai cua nguoi dung. Log to len: khong co dong
    // nay thi trieu chung o phia nguoi dung khong he chi ve nguyen nhan that.
    logger.error({ status, err: message }, 'API key sai hoac het quyen — KIEM TRA OPENAI_API_KEY');
  } else {
    logger.error({ status, err: message }, 'goi model that bai');
  }

  // Timeout KHONG retry: nguoi dung da nhan cau fallback roi.
  if (/timeout|aborted|ETIMEDOUT/i.test(message)) {
    return { kind: 'upstream_timeout', service: 'llm' };
  }

  return { kind: 'upstream_error', service: 'llm', ...(status === undefined ? {} : { status }) };
}
