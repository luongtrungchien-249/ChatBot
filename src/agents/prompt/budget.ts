import { truncateAtBoundary } from '../../shared/chunk-text.js';

/**
 * Tran an toan cho tung tang prompt.
 *
 * KHONG con la "ngan sach" theo nghia section 7.3 nua. Bang goc (system 400,
 * knowledge 1500, recent 1200, tong ~4000) duoc tinh cho gia Opus 5 la $5/1M input.
 * gpt-5-mini co cua so 400.000 token va gia $0,25/1M — re hon 20 lan — nen cat bot
 * ngu canh la danh doi chat luong cau tra loi lay vai xu. Khong dang.
 *
 * Cac con so duoi day dat cao den muc trong van hanh binh thuong KHONG BAO GIO cat:
 * 15 tin nhan gan nhat hiem khi qua 2000 token, rerank tra ve 3-5 chunk (~4000).
 * Chung ton tai nhu mot CAU DAO, khong phai mot chinh sach.
 *
 * Vi sao van giu cau dao: o 400.000 token thi MOT request ton $0,10. Mot tai lieu
 * dai lot vao prompt, hoac mot vong lap hong, la du dot ngan sach ngay trong vai
 * chuc lan goi. Muon bo han thi sua cac so nay thanh Number.MAX_SAFE_INTEGER —
 * nhung luc do chot chan duy nhat con lai la DAILY_BUDGET_USD.
 *
 * Luu y ve chat luong, khong phai chi phi: nhoi them ngu canh khong lam cau tra loi
 * tot hon vo han. Duong ong rerank (top 3-5 + nguong) ton tai de gui IT va DUNG,
 * chu khong phai gui nhieu.
 */
export const TOKEN_BUDGET = {
  /**
   * Hang so ta tu viet nen day la cap THAT SU, khong phai cau dao.
   *
   * Nang 700 -> 2600 khi system prompt duoc viet lai theo 5 khoi ROLE / CAPABILITY /
   * RULES / CONSTRAINTS / OUTPUT FORMAT cong phan few-shot.
   *
   * Do that hien tai: 1470 token (do bang ops/calibrate-tokens.mjs). Van DUOI nguong
   * 2048 cua gpt-5-mini nen prompt caching VAN CHUA an — cache_read_tokens con bang 0.
   * KHONG keo dai prompt chi de vuot nguong: o gia $0,25/1M input, cache tiet kiem
   * duoc khoang $0,0003 moi cau, khong dang de lam prompt te di.
   */
  system: 2_600,
  knowledge: 20_000,
  facts: 4_000,
  summary: 4_000,
  recent: 20_000,
  question: 8_000,
  /** Ket qua mot lan goi cong cu. Mot trang web dai khong duoc nuot ca cua so. */
  tool: 12_000,
} as const;

/**
 * So ky tu tren mot token.
 *
 * 3,40 la SO DO DUOC, khong phai so doan: chay ops/calibrate-tokens.mjs tren mau
 * tieng Viet that (hoi thoai nhom, van ban hanh chinh, cau hoi ky thuat) voi
 * gpt-5-mini, ngay 06/09/2026 — ket qua 3,23 / 3,26 / 3,78, trung binh 3,40.
 *
 * Truoc do dat 3 theo phong doan va no uoc luong DU 13%: SYSTEM_PROMPT 4991 ky tu
 * ra 1664 token uoc luong nhung chi 1470 token that.
 *
 * Do lai khi doi model — moi model mot tokenizer.
 *
 * Khong dem token that o day: agents/ khong duoc import llm/ (L1), va them mot lan
 * goi mang cho moi tang moi cau tra loi thi hong muc tieu p95 < 5s.
 */
export const CHARS_PER_TOKEN = 3.4;

export type BudgetLayer = keyof typeof TOKEN_BUDGET;

export type TrimResult = Readonly<{
  text: string;
  trimmedTokens: number;
}>;

/**
 * Vuot tran thi cat DUNG tang do, khong dung tang khac.
 * Luon tra ve so token da cat de ghi log — mot lan cat la mot tin hieu bat thuong
 * can xem, khong phai chuyen binh thuong.
 */
export function trimToBudget(text: string, layer: BudgetLayer): TrimResult {
  const limitChars = TOKEN_BUDGET[layer] * CHARS_PER_TOKEN;
  if (text.length <= limitChars) return { text, trimmedTokens: 0 };

  const kept = truncateAtBoundary(text, limitChars);
  return {
    text: kept,
    trimmedTokens: Math.ceil((text.length - kept.length) / CHARS_PER_TOKEN),
  };
}
