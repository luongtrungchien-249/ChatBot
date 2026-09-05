import { scopeOf, type InboundMessage } from '../domain/message.js';
import { isConfigError, type BotError } from '../domain/errors.js';
import type { AccessRules } from '../policy/access.js';
import type { ChannelPort } from '../ports/channel.port.js';
import type { ClockPort } from '../ports/clock.port.js';
import type { KnowledgePort } from '../ports/knowledge.port.js';
import type { LlmPort } from '../ports/llm.port.js';
import type { LoggerPort } from '../ports/logger.port.js';
import type { MemoryPort } from '../ports/memory.port.js';
import type { RateLimitPort } from '../ports/ratelimit.port.js';
import { checkAccess } from './stages/01-access.js';
import { HELP_TEXT, resolveMentionStage } from './stages/02-mention.js';
import { BUDGET_EXCEEDED_TEXT, checkBudget } from './stages/05-budget-guard.js';
import { persistInbound, persistOutbound } from './stages/06-persist.js';
import { startTyping } from './stages/07-typing.js';
import { buildPrompt } from './stages/11-build-prompt.js';
import { CONFIG_ERROR_TEXT, FALLBACK_TEXT, generate } from './stages/12-generate.js';
import { respond } from './stages/13-respond.js';

/**
 * Orchestrator. Doc file nay la hieu ca he thong.
 *
 * 15 stage, moi stage mot file thuan trong ./stages/ va test rieng duoc.
 * Xem ARCHITECTURE.md section 5.3.
 *
 * Cac stage chua den luot duoc BO QUA TUONG MINH, khong xoa, de doc file nay van
 * thay du hinh dang cuoi cung cua duong ong.
 *
 * Chong trung va co "da tra loi" (dedupe / markReplied) nam o worker, khong o day:
 * chung la ha tang, va handle-message phai test duoc ma khong can Redis.
 */
export type HandleResult =
  | { ok: true; replied: boolean }
  | { ok: false; error: BotError };

export interface Deps {
  llm: LlmPort;
  memory: MemoryPort;
  knowledge: KnowledgePort;
  channel: ChannelPort;
  rateLimit: RateLimitPort;
  clock: ClockPort;
  logger: LoggerPort;
  accessRules: AccessRules;
  botName: string;
  /** Tu llm/models.ts — agents/ khong duoc import llm/ nen container tiem vao. */
  reply: { maxTokens: number; effort: 'low' | 'medium' | 'high' };
  /** So tin gan nhat lay lam L1. Section 6.1 chot 15. */
  recentLimit: number;
}

export async function handleMessage(msg: InboundMessage, deps: Deps): Promise<HandleResult> {
  const log = deps.logger.child({ traceId: msg.traceId, platform: msg.platform });
  const scope = scopeOf(msg);
  const ctx = { scope, senderId: msg.senderId, traceId: msg.traceId };

  //  1. access — khong duoc phep thi dung, IM LANG.
  if (!checkAccess(msg, deps.accessRules)) {
    log.info({ threadId: msg.threadId }, 'thread khong trong allowlist, bo qua');
    return { ok: true, replied: false };
  }

  //  2. mention
  const mention = resolveMentionStage(msg, deps.botName);
  if (mention.kind === 'ignore') return { ok: true, replied: false };
  if (mention.kind === 'help') {
    await respond(deps.channel, scope, HELP_TEXT, msg.messageId);
    return { ok: true, replied: true };
  }

  //  3. command   TODO(tuan-5): memory / quen / help -> tra loi luon, khong goi LLM.
  //               Stage nay dung TRUOC ratelimit co chu dich: nguoi dung phai xoa
  //               duoc memory cua minh ngay ca khi dang bi rate limit.
  //  4. ratelimit TODO(tuan-2): user 10/phut, thread 30/phut.

  //  5. budget-guard — CHOT CHAN CUNG, khong phai alert.
  if (!(await checkBudget(deps.rateLimit))) {
    await respond(deps.channel, scope, BUDGET_EXCEEDED_TEXT, msg.messageId);
    return { ok: true, replied: true };
  }

  //  6. persist — ghi TRUOC khi goi model, de cau hoi khong bien mat khi API hong.
  await persistInbound(deps.memory, msg);

  //  7. typing — khong await.
  startTyping(deps.channel, scope, log);

  //  8. rewrite  TODO(tuan-4): cau hoi thieu ngu canh -> viet lai bang model re.
  //  9. retrieve TODO(tuan-4): tro thanh tool search_knowledge_base trong vong ReAct.
  // 10. recall   TODO(tuan-5): L2 summary + L3 facts (luon kem ThreadScope).

  // L1 thi da co tu tuan 1. Postgres la nguon that, cache Redis chi la he qua.
  const recent = await deps.memory.recent(scope, deps.recentLimit);

  // 11. build-prompt
  const prompt = buildPrompt(
    {
      question: mention.text,
      isGroup: msg.isGroup,
      recent,
      summary: null,
      facts: [],
      chunks: [],
    },
    log,
  );

  // 12. generate — giai doan 2 thay cho nay bang vong ReAct.
  const result = await generate(
    { llm: deps.llm, maxTokens: deps.reply.maxTokens, effort: deps.reply.effort },
    prompt,
    ctx,
    log,
  );

  if (!result.ok) {
    // Im lang trong nhom trong nhu bot chet va nguoi dung se spam mention.
    // Nhung cung khong duoc bao "thu lai sau" cho mot loi cau hinh: thu lai se
    // hong y het, va nguoi dung se tuong bot khong hieu minh noi gi.
    const text = isConfigError(result.error) ? CONFIG_ERROR_TEXT : FALLBACK_TEXT;
    await respond(deps.channel, scope, text, msg.messageId);
    // Van bao loi ra ngoai de worker quyet dinh retry (chi upstream_error moi retry,
    // xem isRetryable trong domain/errors.ts). Co 'replied:' chan gui lan hai.
    return { ok: false, error: result.error };
  }

  // 13. respond
  await respond(deps.channel, scope, result.value, msg.messageId);
  await persistOutbound(deps.memory, scope, msg.messageId, deps.botName, result.value);

  // 14. account  Da ghi trong llm/cost-meter.ts ngay tai lan goi. Stage rieng cho
  //              usage_log theo thread se hoan thien o tuan 2.
  // 15. schedule TODO(tuan-5): day job tom tat / trich fact vao queue maintenance.
  //              KHONG chay tai day.

  return { ok: true, replied: true };
}
