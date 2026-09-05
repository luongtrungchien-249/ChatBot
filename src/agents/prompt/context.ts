import type { StoredMessage } from '../domain/message.js';
import type { LlmMessage } from '../ports/llm.port.js';
import type { RetrievedChunk } from '../ports/knowledge.port.js';
import type { LoggerPort } from '../ports/logger.port.js';
import type { Fact } from '../ports/memory.port.js';
import { trimToBudget, type BudgetLayer } from './budget.js';
import { renderFacts, renderKnowledge, renderRecent } from './builder.js';
import { SYSTEM_PROMPT } from './system.js';

/**
 * CONTEXT ENGINEERING — nam vung cua so ngu canh.
 *
 *   [ System ] [ History ] [ Current input ] [ Tools ] [ Output ]
 *     policy    recent/       current task     schemas   buffer
 *               relevant
 *
 * Nguyen tac xep: thong tin ON DINH truoc, thong tin TUOI sau. Vua hop co che chu y
 * cua model, vua giu duoc tien to on dinh cho prompt caching.
 *
 * MOT DIEM KHAC SO DO, ghi ra day de sau nay khong ai di "sua" nham: OpenAI render
 * `tools` thanh mot khoi RIENG cua request, khong chen vao mang `messages`. Vi vay
 * "Tools nam sau Current input" dung ve mat khai niem nhung KHONG dieu khien duoc
 * bang thu tu mang. Vung Tools o day chi mang y nghia ke toan ngan sach.
 *
 * Moi vung co tran rieng va ghi log phan bi cat. Mot lan cat la mot tin hieu bat
 * thuong can xem, khong phai chuyen binh thuong (xem budget.ts).
 */
export type ContextInput = Readonly<{
  question: string;
  isGroup: boolean;
  /** History: L1 tin gan nhat, L2 tom tat, L3 fact. */
  recent: readonly StoredMessage[];
  summary: string | null;
  facts: readonly Fact[];
  /** Knowledge di kem History vi cung la "thong tin nen", khong phai cau hoi. */
  chunks: readonly RetrievedChunk[];
}>;

export type ContextEnvelope = Readonly<{
  /** Vung System. */
  system: string;
  /** Vung History + Current input, da xep dung thu tu. */
  messages: readonly LlmMessage[];
  /** Ke toan: moi vung ton bao nhieu, cat mat bao nhieu. */
  trimmed: Readonly<Record<string, number>>;
}>;

/** Cat mot tang, ghi log neu co cat, tra ve van ban con lai. */
function fit(
  text: string,
  layer: BudgetLayer,
  logger: LoggerPort,
  trimmed: Record<string, number>,
): string {
  const result = trimToBudget(text, layer);
  if (result.trimmedTokens > 0) {
    trimmed[layer] = result.trimmedTokens;
    logger.warn(
      { layer, trimmedTokens: result.trimmedTokens },
      'cat bot ngu canh — kiem tra xem tran co con hop ly khong',
    );
  }
  return result.text;
}

export function buildContext(input: ContextInput, logger: LoggerPort): ContextEnvelope {
  const trimmed: Record<string, number> = {};

  // --- Vung HISTORY: on dinh nhat truoc, tuoi nhat sau ---
  const history: string[] = [];

  // L4 tai lieu: renderKnowledge da tu ap tran tang 'knowledge'.
  const knowledge = renderKnowledge(input.chunks);
  if (knowledge !== '') history.push(knowledge);

  // L3 fact: renderFacts da tu ap tran tang 'facts'.
  const facts = renderFacts(input.facts);
  if (facts !== '') history.push(facts);

  // L2 tom tat.
  if (input.summary !== null && input.summary !== '') {
    const summary = fit(input.summary, 'summary', logger, trimmed);
    history.push(`<tom_tat_truoc_do>\n${summary}\n</tom_tat_truoc_do>`);
  }

  // L1 tin nhan gan nhat — tuoi nhat trong vung History.
  if (input.recent.length > 0) {
    const recent = renderRecent(input.recent, input.isGroup);
    history.push(`<hoi_thoai_gan_day>\n${recent}\n</hoi_thoai_gan_day>`);
  }

  // --- Vung CURRENT INPUT: dat CUOI CUNG, sat cau tra loi nhat ---
  const question = fit(input.question, 'question', logger, trimmed);

  // History va Current input di trong hai message tach biet: model phan biet duoc
  // "nen" voi "viec can lam bay gio". Gop lam mot thi cau hoi chim trong ngu canh.
  const messages: LlmMessage[] =
    history.length === 0
      ? [{ role: 'user', content: question }]
      : [
          { role: 'user', content: history.join('\n\n') },
          { role: 'assistant', content: 'Mình đã đọc phần thông tin nền. Bạn hỏi gì?' },
          { role: 'user', content: question },
        ];

  return { system: SYSTEM_PROMPT, messages, trimmed };
}
