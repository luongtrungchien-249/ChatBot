"""Stage 2: trong nhom ma khong duoc mention -> dung. Boc ten bot ra khoi cau hoi."""

from dataclasses import dataclass
from typing import TypeAlias

from ...domain.message import InboundMessage
from ...policy.mention import Reply, primary_name, resolve_mention


@dataclass(frozen=True, slots=True)
class Ignore:
    pass


@dataclass(frozen=True, slots=True)
class ShowHelp:
    """Duoc goi nhung khong hoi gi — tra loi huong dan thay vi im lang kho hieu."""


@dataclass(frozen=True, slots=True)
class Ask:
    text: str


MentionOutcome: TypeAlias = Ignore | ShowHelp | Ask


def help_text(bot_names: str) -> str:
    """Ham chu khong phai hang so: ten bot nam o BOT_MENTION_NAME va da doi mot lan.

    Hardcode o day thi lan sau doi ten, cau huong dan se chi cho nguoi dung mot cach
    goi KHONG con hoat dong.
    """
    return (
        f'Bạn cứ nhắn kèm câu hỏi nhé, ví dụ "@{primary_name(bot_names)} '
        f'deadline báo cáo quý 3 là ngày nào".'
    )


def resolve_mention_stage(msg: InboundMessage, bot_names: str) -> MentionOutcome:
    verdict = resolve_mention(msg, bot_names)
    if not isinstance(verdict, Reply):
        return Ignore()
    if verdict.empty:
        return ShowHelp()
    return Ask(text=verdict.text)
