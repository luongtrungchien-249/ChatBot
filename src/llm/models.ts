/**
 * MOT cho duy nhat khai model. Khong rai model ID khap code.
 * Gia (USD / 1M token) de cost-meter tinh cost_usd. Xem ARCHITECTURE.md section 8.
 *
 * Nha cung cap: OpenAI. gpt-5-mini la ban ke nhiem chinh thuc cua o4-mini va re hon
 * han (0,25 so voi 1,10 input; 2,00 so voi 4,40 output).
 *
 * Hien tai MOI route dung chung mot model — dung mot agent hoi dap. Khi nao tach
 * multi-agent, ba route async (rewrite/summarize/extractFacts) nen ha xuong
 * gpt-5-nano ($0,05 / $0,40): viec co hoc, khoi luong lon, khong nhay latency.
 * Doi cho nay la doi mot file.
 */

/** gpt-5-mini: context 400K, max output 128K. */
const GPT_5_MINI = {
  id: 'gpt-5-mini',
  priceIn: 0.25,
  priceCachedIn: 0.025,
  priceOut: 2.0,
} as const;

/**
 * CANH BAO ve max_completion_tokens tren model reasoning.
 *
 * Token reasoning tinh VAO max_completion_tokens va tinh tien theo gia output.
 * Dat cap qua thap thi API tra ve content RONG voi finish_reason 'length' —
 * khong loi, khong ngoai le, chi la cau tra loi bien mat. Day chinh la ly do
 * cac cap duoi day rong rai hon nhieu so voi do dai van ban mong doi.
 *
 * Nang cap khong ton them tien: output tinh theo token THUC SINH RA, khong theo cap.
 * Do dai cau tra loi kiem soat bang system prompt ("duoi 4-5 cau"), khong bang cap.
 */
export const MODELS = {
  reply: {
    ...GPT_5_MINI,
    effort: 'low' as const,
    maxTokens: 16_000,
  },
  rewrite: { ...GPT_5_MINI, effort: 'low' as const, maxTokens: 2_000 },
  summarize: { ...GPT_5_MINI, effort: 'low' as const, maxTokens: 4_000 },
  extractFacts: { ...GPT_5_MINI, effort: 'low' as const, maxTokens: 4_000 },
} as const;

export type Route = keyof typeof MODELS;

/** Timeout duong phan hoi. Qua nguong nay -> cau fallback ngan, khong im lang. */
export const REPLY_TIMEOUT_MS = 15_000;
