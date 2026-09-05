export type ThreadSummary = {
  threadId: string;
  lastText: string;
  lastAt: string;
  messageCount: number;
};

export type Message = { text: string; fromBot: boolean; at: string };

export type WebEvent =
  | { type: 'typing' }
  | { type: 'thought'; iteration: number; text: string }
  | { type: 'tool_call'; iteration: number; tools: readonly string[] }
  | { type: 'observation'; iteration: number; tool: string; ok: boolean; latencyMs: number }
  | { type: 'final'; text: string }
  | { type: 'error'; text: string };

/** Mot buoc trong vong ReAct, de hien duoi khung chat. */
export type ReactStep = { kind: 'thought' | 'tool_call' | 'observation'; text: string; ok: boolean };

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  threads: () => fetch('/api/threads').then(json<ThreadSummary[]>),
  messages: (threadId: string) =>
    fetch(`/api/threads/${encodeURIComponent(threadId)}/messages`).then(json<Message[]>),
  send: (threadId: string, text: string) =>
    fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ threadId, text }),
    }).then(json<{ messageId?: string; duplicate?: boolean }>),
};

/**
 * Mo SSE cho mot thread. Tra ve ham dong.
 *
 * Khong stream tung token: cau tra loi ve nguyen khoi. Doi lai, kenh nay se cho
 * su kien ReAct (thought / tool_call / observation) o giai doan 2B — voi mot agent
 * co tool, xem no dang lam gi con ro hon xem tung chu hien ra.
 */
export function openStream(threadId: string, onEvent: (e: WebEvent) => void): () => void {
  const source = new EventSource(`/api/stream/${encodeURIComponent(threadId)}`);
  source.onmessage = (ev) => {
    try {
      onEvent(JSON.parse(ev.data) as WebEvent);
    } catch {
      // Bo qua khung khong parse duoc thay vi lam sap ca giao dien.
    }
  };
  return () => source.close();
}
