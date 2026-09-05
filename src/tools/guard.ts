import { sanitize } from '../agents/prompt/builder.js';
import { trimToBudget } from '../agents/prompt/budget.js';
import { logger } from '../infra/logger.js';

/**
 * Lop bao ve cho ket qua cong cu.
 *
 * ARCHITECTURE.md section 7.2 chi tinh injection qua tai lieu do ADMIN nap. Web
 * search dua vao van ban do NGUOI LA soan, va trong vong ReAct thi observation do
 * lai quyet dinh hanh dong tiep theo — injection duoc khuech dai.
 *
 * CO Y KHONG CHAN theo tu khoa. Chan bang danh sach tu vua de vuot (viet lai mot
 * chut la lot), vua tao cam giac an toan gia khien nguoi ta bo qua cac lop that su
 * co tac dung: boc the, noi ro trong RULES rang do la du lieu, va khong bao gio
 * dua ket qua cong cu vao role 'system'.
 *
 * Ham nay ton tai de AUDIT: biet co ai dang thu, va thu bang cach nao.
 */
const INJECTION_PATTERNS: readonly (readonly [name: string, pattern: RegExp])[] = [
  ['bo-qua-huong-dan', /\b(bỏ qua|phớt lờ|quên)\s+(mọi\s+)?(hướng dẫn|chỉ dẫn|quy tắc|luật)/i],
  ['ignore-instructions', /\bignore\s+(all\s+|previous\s+|prior\s+|above\s+)+(instructions?|rules?)/i],
  ['doi-vai', /\b(bây giờ|từ giờ)\s+(bạn|mày)\s+(là|thành)\b/i],
  ['you-are-now', /\byou\s+are\s+now\b|\bact\s+as\s+(a\s+)?(dan|jailbreak)/i],
  ['lo-system-prompt', /\b(in ra|hiển thị|tiết lộ|cho xem)\s+.{0,20}(system prompt|prompt hệ thống)/i],
  ['reveal-prompt', /\b(reveal|print|show|repeat)\s+.{0,20}(system prompt|your instructions)/i],
  ['che-do-dac-biet', /\b(chế độ|mode)\s+(nhà phát triển|developer|god|unrestricted)/i],
  ['gia-danh-quan-tri', /\b(tôi là|mình là)\s+(quản trị viên|admin|người tạo ra bạn)/i],
];

export type InjectionScan = Readonly<{ suspicious: boolean; patterns: readonly string[] }>;

export function detectInjection(text: string): InjectionScan {
  const hits = INJECTION_PATTERNS.filter(([, pattern]) => pattern.test(text)).map(([name]) => name);
  return { suspicious: hits.length > 0, patterns: hits };
}

/**
 * Boc ket qua cong cu thanh mot khoi du lieu an toan de dua vao prompt.
 *
 * Ba viec, theo dung thu tu:
 *   1. sanitize()  — bo the dong gia, chan noi dung tu thoat khoi hop.
 *   2. cat theo tran tang 'tool' — mot trang web dai khong duoc nuot ca cua so.
 *   3. boc trong <ket_qua_cong_cu> — RULES trong system prompt noi ro day la
 *      DU LIEU, khong phai chi thi.
 */
export function wrapObservation(args: {
  toolName: string;
  source: string;
  content: string;
  traceId: string;
}): string {
  const scan = detectInjection(args.content);
  if (scan.suspicious) {
    logger.warn(
      { traceId: args.traceId, tool: args.toolName, source: args.source, patterns: scan.patterns },
      'ket qua cong cu chua mau giong prompt injection — ghi nhan de audit, KHONG chan',
    );
  }

  const clean = trimToBudget(sanitize(args.content), 'tool');
  if (clean.trimmedTokens > 0) {
    logger.info(
      { traceId: args.traceId, tool: args.toolName, trimmedTokens: clean.trimmedTokens },
      'ket qua cong cu vuot tran, da cat',
    );
  }

  const flag = scan.suspicious ? ' canh_bao="chua_cau_ra_lenh"' : '';
  return `<ket_qua_cong_cu cong_cu="${args.toolName}" nguon="${args.source}"${flag}>\n${clean.text}\n</ket_qua_cong_cu>`;
}
