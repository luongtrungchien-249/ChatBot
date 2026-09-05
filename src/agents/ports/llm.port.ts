import type { ThreadScope } from '../domain/thread.js';

/**
 * Mot lan model muon goi cong cu.
 *
 * `id` la BAT BUOC: OpenAI doi moi ket qua tra ve phai khop `tool_call_id` cua
 * loi goi tuong ung. Thieu mot cai la ca request 400.
 */
export type ToolCall = Readonly<{
  id: string;
  name: string;
  input: Record<string, unknown>;
}>;

/**
 * Mot luot trong hoi thoai gui len model.
 *
 * Union chu khong phai { role, content } phang: luot assistant co the KHONG co van
 * ban ma chi co loi goi tool, va luot tool phai mang theo toolCallId. Kieu phang
 * khong bieu dien duoc vong ReAct.
 */
export type LlmMessage =
  | Readonly<{ role: 'user'; content: string }>
  | Readonly<{ role: 'assistant'; content: string; toolCalls?: readonly ToolCall[] }>
  | Readonly<{ role: 'tool'; toolCallId: string; content: string }>;

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
  toolCalls: readonly ToolCall[];
  usage: LlmUsage;
  /** 'tool_calls' = model muon goi cong cu roi hoi tiep; 'stop' = da xong. */
  finishReason: 'stop' | 'tool_calls' | 'length' | 'other';
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
