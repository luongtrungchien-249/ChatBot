/**
 * Che secret truoc khi ghi log. Chay tren MOI dong log (xem infra/logger.ts).
 *
 * Nguyen tac: tha che nham con hon de lot. Mot token Zalo lot vao log tap trung
 * la mot token phai thu hoi, khong phai mot dong log xau.
 *
 * Thu tu quan trong: mau cu the truoc, mau chung sau. Email di truoc so dien thoai
 * vi '0912345678@vd.com' se bi mau so dien thoai an mat phan truoc @.
 */

type Rule = readonly [pattern: RegExp, replacement: string];

const RULES: readonly Rule[] = [
  // Chuoi ket noi co mat khau: postgres://user:pass@host
  [/\b(postgres|postgresql|redis|rediss|amqp|mongodb):\/\/[^:@\s/]+:[^@\s]+@/gi, '$1://***:***@'],

  // API key ho 'sk-': OpenAI (sk-proj-, sk-svcacct-, sk-), Anthropic (sk-ant-).
  // Bat ca ho thay vi liet ke tung tien to — doi nha cung cap thi khong phai nho
  // quay lai sua cho nay. (Da tung sot: sau khi chuyen sang OpenAI, mau sk-ant-
  // cu khong con bat duoc key nao.)
  [/\bsk-[A-Za-z0-9_-]{12,}/g, 'sk-***'],

  // Tavily (tool web search, giai doan 2)
  [/\btvly-[A-Za-z0-9_-]{8,}/g, 'tvly-***'],

  // Meta / Facebook page access token
  [/\bEAA[A-Za-z0-9]{20,}/g, 'EAA***'],

  // Zalo Bot Platform token: numeric_id:secret
  [/(?<!\d)\d{6,}:[A-Za-z0-9_-]{16,}/g, '***:***'],

  // Header uy quyen
  [/\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}/gi, '$1 ***'],

  // Email — giu lai ten mien de con debug duoc
  [/[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})/g, '***@$1'],

  // So dien thoai Viet Nam: +84xxxxxxxxx hoac 0xxxxxxxxx
  [/(?<!\d)(?:\+84|0)\d{9}(?!\d)/g, '***'],
];

export function redact(input: string): string {
  let out = input;
  for (const [pattern, replacement] of RULES) out = out.replace(pattern, replacement);
  return out;
}

/**
 * Che secret trong ca object long nhau — pino log object, khong chi log chuoi.
 * Giu nguyen hinh dang; chi thay the cac gia tri chuoi.
 */
export function redactDeep<T>(value: T): T {
  if (typeof value === 'string') return redact(value) as T;
  if (Array.isArray(value)) return value.map(redactDeep) as T;
  if (value !== null && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) out[k] = redactDeep(v);
    return out as T;
  }
  return value;
}
