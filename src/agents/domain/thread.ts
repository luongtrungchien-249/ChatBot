/**
 * ThreadScope — khoa chong ro ri memory cross-group.
 *
 * Khong bao gio truyen platform + threadId roi rac. Truyen mot object.
 * Ly do: khong ai quen tham so thu hai cua mot object ca.
 */
export type Platform = 'zalo_bot' | 'zalo_personal' | 'messenger' | 'cli' | 'web';

export type ThreadScope = Readonly<{
  platform: Platform;
  threadId: string;
}>;

export function scopeKey(scope: ThreadScope): string {
  return `${scope.platform}:${scope.threadId}`;
}

/** subject_id trong memory_fact: 'user:xxx' hoac 'thread:xxx'. */
export function userSubject(senderId: string): string {
  return `user:${senderId}`;
}

export function threadSubject(threadId: string): string {
  return `thread:${threadId}`;
}
