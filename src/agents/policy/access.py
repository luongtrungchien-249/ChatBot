"""Giai doan dau LUON de allowlist.

Mo 'open' chi khi da co rate limit + cost control.
"""

from dataclasses import dataclass
from typing import Literal

from ..domain.thread import ThreadScope, scope_key

#: Tu vung chinh sach truy cap. Dinh nghia o DAY chu khong o config/schema.py, va
#: config import nguoc len — vi day la khai niem cua mien nghiep vu, con config chi
#: la cho kiem tra chuoi trong .env co thuoc tap nay khong.
#:
#: Dat o config thi agents/ phai import config de biet kieu cua chinh no, va luat L1
#: "agents khong doc config" khong con cuong che duoc — canary trong
#: ops/canary_import_rules.py se khong bao gio do vi luat da bi khoet mot lo.
GroupPolicy = Literal["allowlist", "open", "disabled"]
DmPolicy = Literal["pairing", "allowlist", "open", "disabled"]


@dataclass(frozen=True, slots=True)
class AccessRules:
    group_policy: GroupPolicy
    dm_policy: DmPolicy
    allowed_threads: frozenset[str]


def is_allowed(scope: ThreadScope, is_group: bool, rules: AccessRules) -> bool:
    policy: str = rules.group_policy if is_group else rules.dm_policy
    if policy == "disabled":
        return False
    if policy == "open":
        return True
    # allowlist va pairing deu doi thread phai duoc them tu truoc.
    # `allowed_threads` do main/container.py nap tu bang thread_allowlist moi luot
    # (infra/allowlist.py). Ham nay van thuan: no khong biet Postgres ton tai.
    return scope_key(scope) in rules.allowed_threads
