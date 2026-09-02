import type { AccessRules } from '../agents/policy/access.js';
import { config } from './index.js';

/**
 * Chinh sach van hanh — tach khoi secret de commit duoc phan nay.
 * TODO(tuan-2): chuyen allowlist va admin sang bang thread_allowlist trong DB.
 */
export const allowedThreads: ReadonlySet<string> = new Set<string>([
  // 'zalo_bot:1234567890',
]);

/** Ai duoc sua/xoa fact subject 'thread:*' cua ca nhom. */
export const threadAdmins: ReadonlyMap<string, ReadonlySet<string>> = new Map();

export const accessRules: AccessRules = {
  groupPolicy: config.GROUP_POLICY,
  dmPolicy: config.DM_POLICY,
  allowedThreads,
};
