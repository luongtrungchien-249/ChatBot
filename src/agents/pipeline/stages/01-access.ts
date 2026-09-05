import { scopeOf, type InboundMessage } from '../../domain/message.js';
import { isAllowed, type AccessRules } from '../../policy/access.js';

/**
 * Stage 1: allowlist. Khong duoc phep -> dung, IM LANG.
 *
 * Im lang co chu dich: tra loi "ban khong co quyen" trong mot nhom la ba lan sai —
 * lo ra rang bot dang o day, moi nguoi la thu tiep, va ton mot tin nhan cho moi
 * tin rac. Xem bang hanh vi loi o ARCHITECTURE.md section 9.
 */
export function checkAccess(msg: InboundMessage, rules: AccessRules): boolean {
  return isAllowed(scopeOf(msg), msg.isGroup, rules);
}
