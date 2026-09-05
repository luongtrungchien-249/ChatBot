import type { InboundMessage } from '../domain/message.js';

/**
 * Phat hien mention HAI LOP: truong mention trong payload + fallback regex.
 * Payload cac nen tang khong dong nhat va hay doi — mot lop la khong du.
 */

/**
 * Moi nguyen am tieng Viet co the xuat hien co dau hoac khong.
 *
 * BOT_MENTION_NAME viet khong dau ('Chien_Assistant') vi nen tang thuong khong
 * cho dat ten co dau, nhung nguoi Viet GO CO DAU: "@Chiến Assistant". Khong co
 * bang nay thi bot im lang truoc dung cach goi tu nhien nhat — va im lang trong
 * nhom trong nhu bot chet.
 *
 * Mo rong ngay trong regex (thay vi bo dau ca hai ben roi so sanh) de con boc
 * dung doan mention ra khoi cau hoi: bo dau lam doi do dai chuoi, chi so lech het.
 */
const VIETNAMESE_VARIANTS: Readonly<Record<string, string>> = {
  a: 'aàáảãạăằắẳẵặâầấẩẫậ',
  d: 'dđ',
  e: 'eèéẻẽẹêềếểễệ',
  i: 'iìíỉĩị',
  o: 'oòóỏõọôồốổỗộơờớởỡợ',
  u: 'uùúủũụưừứửữự',
  y: 'yỳýỷỹỵ',
};

function expandVietnamese(char: string): string {
  const variants = VIETNAMESE_VARIANTS[char.toLowerCase()];
  return variants === undefined ? char : `[${variants}]`;
}

export function mentionRegex(botName: string): RegExp {
  const escaped = botName
    .replace(/[.*+?^${}()|[\]\\]/g, '\\$&') // escape ky tu dac biet TRUOC
    .split('')
    .map(expandVietnamese) // roi moi mo rong nguyen am co dau
    .join('')
    .replace(/_/g, '[_\\s]?'); // cuoi cung: gach duoi = khoang trang

  // (?![\p{L}\p{N}_]) chan '@Chien_Assistant2' va '@Chien_Assistantx' — do la
  // nguoi dung khac, khong phai bot. Dung \p{L} thay \w de chan ca chu co dau.
  return new RegExp(`@${escaped}(?![\\p{L}\\p{N}_])`, 'iu');
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
