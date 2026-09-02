/**
 * MOT cho duy nhat khai model. Khong rai model ID khap code.
 * Gia (USD / 1M token) de cost-meter tinh cost_usd. Xem ARCHITECTURE.md section 8.
 */
export const MODELS = {
  reply: {
    id: 'claude-opus-5',
    effort: 'low' as const,
    maxTokens: 2000,
    priceIn: 5,
    priceOut: 25,
  },
  rewrite: { id: 'claude-haiku-4-5', maxTokens: 200, priceIn: 1, priceOut: 5 },
  summarize: { id: 'claude-haiku-4-5', maxTokens: 800, priceIn: 1, priceOut: 5 },
  extractFacts: { id: 'claude-haiku-4-5', maxTokens: 500, priceIn: 1, priceOut: 5 },
} as const;

export type Route = keyof typeof MODELS;

/** Timeout duong phan hoi. Qua nguong nay -> cau fallback ngan, khong im lang. */
export const REPLY_TIMEOUT_MS = 15_000;
