import type { StoredMessage } from '../../domain/message.js';
import type { LlmMessage } from '../../ports/llm.port.js';
import type { Fact } from '../../ports/memory.port.js';
import type { RetrievedChunk } from '../../ports/knowledge.port.js';
import type { LoggerPort } from '../../ports/logger.port.js';
import { renderFacts, renderKnowledge, renderRecent, SYSTEM_PROMPT } from '../../prompt/builder.js';
import { trimToBudget } from '../../prompt/budget.js';

/**
 * Stage 11: ghep ngu canh theo ARCHITECTURE.md section 7.3.
 *
 * Thu tu: thong tin ON DINH truoc, thong tin TUOI sau. Vua hop co che chu y cua
 * model, vua giu tien to on dinh cho prompt caching.
 *
 * MOI tang bi cat deu duoc ghi log. Khong co log thi khong bao gio hieu tai sao
 * bot quen mat cau hoi truoc do — no chi don gian tra loi lac de.
 */
export type PromptInput = Readonly<{
  question: string;
  isGroup: boolean;
  recent: readonly StoredMessage[];
  summary: string | null;
  facts: readonly Fact[];
  chunks: readonly RetrievedChunk[];
}>;

export type BuiltPrompt = Readonly<{
  system: string;
  messages: readonly LlmMessage[];
}>;

export function buildPrompt(input: PromptInput, logger: LoggerPort): BuiltPrompt {
  const parts: string[] = [];

  const knowledge = renderKnowledge(input.chunks);
  if (knowledge) parts.push(knowledge);

  const facts = renderFacts(input.facts);
  if (facts) parts.push(facts);

  if (input.summary) {
    const trimmed = trimToBudget(input.summary, 'summary');
    if (trimmed.trimmedTokens > 0) {
      logger.warn({ layer: 'summary', trimmedTokens: trimmed.trimmedTokens }, 'cat bot ngu canh');
    }
    parts.push(`<tom_tat_truoc_do>\n${trimmed.text}\n</tom_tat_truoc_do>`);
  }

  if (input.recent.length > 0) {
    parts.push(`<hoi_thoai_gan_day>\n${renderRecent(input.recent, input.isGroup)}\n</hoi_thoai_gan_day>`);
  }

  const question = trimToBudget(input.question, 'question');
  if (question.trimmedTokens > 0) {
    logger.warn({ layer: 'question', trimmedTokens: question.trimmedTokens }, 'cau hoi qua dai, da cat');
  }
  parts.push(question.text);

  return {
    system: SYSTEM_PROMPT,
    messages: [{ role: 'user', content: parts.join('\n\n') }],
  };
}
