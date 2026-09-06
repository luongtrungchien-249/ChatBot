"""Stage 1: allowlist. Khong duoc phep -> dung, IM LANG.

Im lang co chu dich: tra loi "ban khong co quyen" trong mot nhom la ba lan sai —
lo ra rang bot dang o day, moi nguoi la thu tiep, va ton mot tin nhan cho moi tin
rac. Xem bang hanh vi loi o ARCHITECTURE.md section 9.
"""

from ...domain.message import InboundMessage, scope_of
from ...policy.access import AccessRules, is_allowed


def check_access(msg: InboundMessage, rules: AccessRules) -> bool:
    return is_allowed(scope_of(msg), msg.is_group, rules)
