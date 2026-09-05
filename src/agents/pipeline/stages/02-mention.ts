import type { InboundMessage } from '../../domain/message.js';
import { resolveMention } from '../../policy/mention.js';

/**
 * Stage 2: trong nhom ma khong duoc mention -> dung. Boc ten bot ra khoi cau hoi.
 */
export type MentionOutcome =
  | { kind: 'ignore' }
  /** Duoc goi nhung khong hoi gi — tra loi huong dan thay vi im lang kho hieu. */
  | { kind: 'help' }
  | { kind: 'ask'; text: string };

export const HELP_TEXT =
  'Mình là Chiến Assistant. Bạn cứ nhắn kèm câu hỏi, ví dụ "@Chien_Assistant deadline báo cáo quý 3 là ngày nào".';

export function resolveMentionStage(msg: InboundMessage, botName: string): MentionOutcome {
  const verdict = resolveMention(msg, botName);
  if (!verdict.reply) return { kind: 'ignore' };
  if (verdict.empty) return { kind: 'help' };
  return { kind: 'ask', text: verdict.text };
}
