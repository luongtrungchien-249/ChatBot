import type { ThreadScope } from '../domain/thread.js';

export type GroupPolicy = 'allowlist' | 'open' | 'disabled';
export type DmPolicy = 'pairing' | 'allowlist' | 'open' | 'disabled';

export type AccessRules = Readonly<{
  groupPolicy: GroupPolicy;
  dmPolicy: DmPolicy;
  allowedThreads: ReadonlySet<string>;
}>;

/**
 * Giai doan dau LUON de allowlist. Mo 'open' chi khi da co rate limit + cost control.
 * TODO(tuan-2): doc allowlist tu bang thread_allowlist thay vi config tinh.
 */
export function isAllowed(scope: ThreadScope, isGroup: boolean, rules: AccessRules): boolean {
  const policy = isGroup ? rules.groupPolicy : rules.dmPolicy;
  if (policy === 'disabled') return false;
  if (policy === 'open') return true;
  return rules.allowedThreads.has(`${scope.platform}:${scope.threadId}`);
}
