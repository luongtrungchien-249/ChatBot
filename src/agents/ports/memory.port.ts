import type { ThreadScope } from '../domain/thread.js';
import type { StoredMessage } from '../domain/message.js';

export type Fact = Readonly<{
  id: string;
  subjectId: string;
  content: string;
  source: 'explicit' | 'implicit';
  confidence: number;
  createdAt: Date;
}>;

export type NewFact = Readonly<{
  subjectId: string;
  content: string;
  source: 'explicit' | 'implicit';
  confidence: number;
  createdBy: string;
}>;

/**
 * MOI phuong thuc nhan ThreadScope o tham so DAU TIEN.
 * Khong duoc them overload nao bo no. Day la hang rao chong ro ri, khong phai toi uu hoa.
 */
export interface MemoryPort {
  recent(scope: ThreadScope, limit: number): Promise<StoredMessage[]>;
  summary(scope: ThreadScope): Promise<string | null>;
  facts(scope: ThreadScope, subjectId: string, query: string): Promise<Fact[]>;
  remember(scope: ThreadScope, fact: NewFact): Promise<void>;
  /** Tra ve fact khop de HOI XAC NHAN truoc khi revoke. Khong xoa ngay. */
  forget(scope: ThreadScope, actorId: string, pattern: string): Promise<Fact[]>;
  list(scope: ThreadScope, subjectId: string): Promise<Fact[]>;
}
