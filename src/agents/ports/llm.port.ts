import type { ThreadScope } from '../domain/thread.js';

export type LlmRole = 'user' | 'assistant';
export type LlmMessage = Readonly<{ role: LlmRole; content: string }>;

export type ToolSpec = Readonly<{
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}>;

export type LlmUsage = Readonly<{
  /**
   * Token input tinh gia DAY DU — da tru phan doc tu cache.
   * Nha cung cap bao cao khac nhau (OpenAI gop ca hai vao prompt_tokens), nen
   * viec chuan hoa thuoc ve implementation trong llm/, khong phai cho goi.
   */
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens: number;
  /** OpenAI khong tinh phi ghi cache -> luon 0. Giu cot de doi provider khong phai doi schema. */
  cacheWriteTokens: number;
}>;

export type LlmResult = Readonly<{
  text: string;
  toolCalls: readonly { name: string; input: Record<string, unknown> }[];
  usage: LlmUsage;
}>;

/**
 * Ai gay ra lan goi nay. Bat buoc o MOI lan goi vi L6: khong do duoc cost theo
 * thread va sender thi khong biet tien di dau, va bang usage_log (section 6.4)
 * khai ba cot nay NOT NULL.
 *
 * Di kem tung lan goi chu khong nam trong constructor, giong traceId: mot
 * LlmPort phuc vu moi thread, khong dung mot instance cho moi hoi thoai.
 */
export type CallContext = Readonly<{
  scope: ThreadScope;
  senderId: string;
  traceId: string;
}>;

export interface LlmPort {
  /** Duong phan hoi chinh. system phai la HANG SO de prompt caching an. */
  reply(req: {
    system: string;
    messages: readonly LlmMessage[];
    maxTokens: number;
    effort: 'low' | 'medium' | 'high';
    tools?: readonly ToolSpec[];
    ctx: CallContext;
  }): Promise<LlmResult>;

  /** Model re, chay async: rewrite / summarize / extract-facts. */
  cheap(req: {
    system: string;
    input: string;
    maxTokens: number;
    route: 'rewrite' | 'summarize' | 'extractFacts';
    ctx: CallContext;
  }): Promise<string>;
}
