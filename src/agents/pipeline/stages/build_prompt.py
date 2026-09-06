"""Stage 11: dung ngu canh theo nam vung cua so do Context Engineering.

Toan bo logic nam o agents/prompt/context.py — stage nay chi la diem noi, de vung
ngu canh con dung duoc o cho khac (vong ReAct o stage generate dung lai chinh no
de ghep observation vao giua cac vong).
"""

from ...ports.logger import LoggerPort
from ...prompt.context import ContextEnvelope, ContextInput, build_context


def build_prompt(data: ContextInput, logger: LoggerPort) -> ContextEnvelope:
    return build_context(data, logger)
