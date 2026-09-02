/** Hard cap token tung tang. Xem bang trong ARCHITECTURE.md section 7.3. */
export const TOKEN_BUDGET = {
  system: 400,
  knowledge: 1500,
  facts: 200,
  summary: 400,
  recent: 1200,
  question: 200,
} as const;

export type BudgetLayer = keyof typeof TOKEN_BUDGET;

export type TrimResult = Readonly<{
  text: string;
  trimmedTokens: number;
}>;

/**
 * Vuot cap thi cat DUNG tang do, khong dung tang khac.
 * Luon tra ve so token da cat de ghi log — khong co log thi khong bao gio hieu
 * tai sao bot quen mat cau hoi truoc do.
 *
 * TODO(tuan-1): thay uoc luong 4 ky tu/token bang messages.count_tokens.
 */
export function trimToBudget(text: string, layer: BudgetLayer): TrimResult {
  const limitChars = TOKEN_BUDGET[layer] * 4;
  if (text.length <= limitChars) return { text, trimmedTokens: 0 };
  return {
    text: text.slice(0, limitChars),
    trimmedTokens: Math.ceil((text.length - limitChars) / 4),
  };
}
