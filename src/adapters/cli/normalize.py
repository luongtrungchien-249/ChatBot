"""Adapter thu BA. Cach duy nhat de lam Phase 0 khi chua co token Zalo/Meta.

Day khong phai do choi: neu agents/ chi chay duoc khi co webhook that thi kien truc
da sai tu dau. Cung dung lam adapter tham chieu — Zalo va web phai chuan hoa
ra DUNG hinh dang nay.
"""

import time
import uuid

from agents.domain.message import InboundMessage

CLI_THREAD_ID = "local"
CLI_SENDER_ID = "local-user"
#: Terminal khong co gioi han that su.
CLI_MAX_MESSAGE_CHARS = 4_000


def normalize_cli_input(line: str, sender_name: str = "Bạn") -> InboundMessage:
    return InboundMessage(
        platform="cli",
        thread_id=CLI_THREAD_ID,
        sender_id=CLI_SENDER_ID,
        sender_name=sender_name,
        text=line,
        # DM: khong can mention. Xem policy/mention.py — ngoai nhom thi luon tra loi.
        is_group=False,
        mentioned_bot=True,
        message_id=str(uuid.uuid4()),
        timestamp=int(time.time() * 1000),
        # L8: mot trace_id cho moi tin, xuyen suot moi log cua luot nay.
        trace_id=str(uuid.uuid4()),
    )
