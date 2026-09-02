import type { InboundMessage } from '../domain/message.js';
import type { BotError } from '../domain/errors.js';

/**
 * Orchestrator. Doc file nay la hieu ca he thong.
 * 15 stage, moi stage mot file thuan trong ./stages/ va test rieng duoc.
 * Xem ARCHITECTURE.md section 5.3.
 */
export type HandleResult =
  | { ok: true; replied: boolean }
  | { ok: false; error: BotError };

export interface Deps {
  // TODO(tuan-1): cac port duoc tiem tu src/main/container.ts
  //   llm, memory, knowledge, channel, rateLimit, clock, logger
}

export async function handleMessage(_msg: InboundMessage, _deps: Deps): Promise<HandleResult> {
  //  1. access        Thread co trong allowlist? Khong -> dung, im lang.
  //  2. mention       is_group && !mentioned_bot -> dung. Boc @nam_chatbot.
  //  3. command       memory / quen / help -> tra loi LUON, khong goi LLM.
  //  4. ratelimit     user 10/phut, thread 30/phut, global theo budget.
  //  5. budget-guard  Chi tieu hom nay > nguong -> tu choi lich su. CHOT CHAN CUNG.
  //  6. persist       Ghi tin vao Postgres (nguon that) + day Redis cache.
  //  7. typing        channel.typing() — khong await.
  //  8. rewrite       Cau hoi thieu ngu canh -> viet lai bang L1 (Haiku).
  //  9. retrieve      knowledge.search() khi model goi tool hoac heuristic bat.
  // 10. recall        L2 summary + L3 facts (luon kem ThreadScope).
  // 11. build-prompt  Ghep theo section 7.3, ap hard cap tung tang.
  // 12. generate      llm.reply() — timeout 15s, co fallback.
  // 13. respond       channel.send() — tu chunk.
  // 14. account       cost-meter -> usage_log.
  // 15. schedule      Day job tom tat / trich fact vao queue maintenance. KHONG chay tai day.
  throw new Error('TODO(tuan-1): chua trien khai');
}
