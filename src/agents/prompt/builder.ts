import type { RetrievedChunk } from '../ports/knowledge.port.js';
import type { Fact } from '../ports/memory.port.js';
import type { StoredMessage } from '../domain/message.js';
import { SYSTEM_PROMPT } from './system.js';
import { trimToBudget } from './budget.js';

/**
 * Thu tu: thong tin ON DINH truoc, thong tin TUOI sau.
 * Vua hop co che chu y cua model, vua tan dung prompt caching cho phan dau it doi.
 * Vi tri: system -> L4 -> L3 -> L2 -> L1 -> cau hoi.
 */

/** Chan chunk tu thoat khoi hop bang cach viet the dong cua chinh no. */
function sanitize(content: string): string {
  return content.replace(/<\/?tai_lieu[^>]*>/gi, '');
}

export function renderKnowledge(chunks: readonly RetrievedChunk[]): string {
  if (chunks.length === 0) return '';
  const body = chunks
    .map(
      (c) =>
        `<tai_lieu id="${c.chunkId}" nguon="${c.docTitle}" muc="${c.section ?? ''}">\n` +
        `${sanitize(c.content)}\n</tai_lieu>`,
    )
    .join('\n');
  return trimToBudget(body, 'knowledge').text;
}

export function renderFacts(facts: readonly Fact[]): string {
  if (facts.length === 0) return '';
  const body = `<ghi_nho>\n${facts.map((f) => `- ${f.content}`).join('\n')}\n</ghi_nho>`;
  return trimToBudget(body, 'facts').text;
}

export function renderRecent(messages: readonly StoredMessage[], isGroup: boolean): string {
  const body = messages
    .map((m) => (isGroup ? `[${m.senderName}]: ${m.text}` : m.text))
    .join('\n');
  return trimToBudget(body, 'recent').text;
}

export { SYSTEM_PROMPT };
