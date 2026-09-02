import type { InboundMessage } from '../domain/message.js';

/**
 * Phat hien mention HAI LOP: truong mention trong payload + fallback regex.
 * Payload cac nen tang khong dong nhat va hay doi — mot lop la khong du.
 */
export function mentionRegex(botName: string): RegExp {
  const escaped = botName.replace(/[.*+?^${}()|[\]\]/g, '\$&').replace(/_/g, '[_\s]?');
  return new RegExp(`@${escaped}`, 'i');
}

export type MentionVerdict =
  | { reply: false }
  | { reply: true; text: string; empty: boolean };

export function resolveMention(msg: InboundMessage, botName: string): MentionVerdict {
  const re = mentionRegex(botName);
  const mentioned = msg.mentionedBot || re.test(msg.text);

  if (msg.isGroup && !mentioned) return { reply: false };

  const stripped = msg.text.replace(re, ' ').replace(/\s+/g, ' ').trim();
  return { reply: true, text: stripped, empty: stripped.length === 0 };
}
