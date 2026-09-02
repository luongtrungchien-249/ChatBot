import type { ThreadScope } from '../domain/thread.js';

export interface ChannelPort {
  typing(scope: ThreadScope): Promise<void>;
  /** Tu chunk theo maxMessageChars. Agents khong hardcode gioi han cua tung nen tang. */
  send(scope: ThreadScope, text: string, replyTo?: string): Promise<void>;
  readonly maxMessageChars: number;
}
