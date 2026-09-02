export type LlmRole = 'user' | 'assistant';
export type LlmMessage = Readonly<{ role: LlmRole; content: string }>;

export type ToolSpec = Readonly<{
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}>;

export type LlmUsage = Readonly<{
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens: number;
  cacheWriteTokens: number;
}>;

export type LlmResult = Readonly<{
  text: string;
  toolCalls: readonly { name: string; input: Record<string, unknown> }[];
  usage: LlmUsage;
}>;

export interface LlmPort {
  /** Duong phan hoi chinh. system phai la HANG SO de prompt caching an. */
  reply(req: {
    system: string;
    messages: readonly LlmMessage[];
    maxTokens: number;
    effort: 'low' | 'medium' | 'high';
    tools?: readonly ToolSpec[];
    traceId: string;
  }): Promise<LlmResult>;

  /** Model re, chay async: rewrite / summarize / extract-facts. */
  cheap(req: {
    system: string;
    input: string;
    maxTokens: number;
    traceId: string;
  }): Promise<string>;
}
