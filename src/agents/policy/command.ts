/**
 * Parse lenh TRUOC khi vao LLM. Stage nay dung truoc rate limit co chu y:
 * nguoi dung phai xoa duoc memory cua minh ngay ca khi dang bi rate limit.
 */
export type Command =
  | { kind: 'memory' }
  | { kind: 'forget'; pattern: string }
  | { kind: 'forget_all' }
  | { kind: 'confirm_forget'; token: string }
  | { kind: 'help' }
  | { kind: 'none' };

export function parseCommand(text: string): Command {
  const t = text.trim().toLowerCase();
  if (t === 'memory' || t === 'bo nho') return { kind: 'memory' };
  if (t === 'quen het' || t === 'quên hết') return { kind: 'forget_all' };
  if (t === 'help' || t === 'huong dan') return { kind: 'help' };

  const forget = /^(?:quen|quên)\s+(.+)$/i.exec(text.trim());
  if (forget?.[1]) return { kind: 'forget', pattern: forget[1] };

  return { kind: 'none' };
}
