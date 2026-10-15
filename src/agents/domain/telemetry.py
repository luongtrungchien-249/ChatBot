"""Content-free, bounded measurements returned by the reply pipeline."""

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .errors import BotError, UpstreamError, UpstreamTimeout

FailureService: TypeAlias = Literal["llm", "embed", "rerank", "db", "unknown"]
FailureKind: TypeAlias = Literal["timeout", "auth", "throttled", "server", "client", "unknown"]


@dataclass(frozen=True, slots=True)
class UpstreamFailure:
    service: FailureService
    kind: FailureKind


def upstream_failure(error: BotError) -> UpstreamFailure | None:
    """Only classify evidence already provided by the domain error, never text."""
    if not isinstance(error, UpstreamError | UpstreamTimeout):
        return None
    service: FailureService = "unknown"
    for known in ("llm", "embed", "rerank", "db"):
        if error.service == known:
            service = known
    if isinstance(error, UpstreamTimeout):
        return UpstreamFailure(service, "timeout")
    status = error.status
    kind: FailureKind = "unknown"
    if status in (401, 403):
        kind = "auth"
    elif status == 429:
        kind = "throttled"
    elif status is not None and 500 <= status <= 599:
        kind = "server"
    elif status is not None and 400 <= status <= 499:
        kind = "client"
    return UpstreamFailure(service, kind)


GenerationReason: TypeAlias = Literal[
    "answer", "error", "budget", "deadline", "user_stopped", "max_iterations"
]
TurnReason: TypeAlias = (
    GenerationReason
    | Literal[
        "unknown", "ignored_access", "ignored_mention", "help", "command", "rate_limited", "poetry"
    ]
)


@dataclass(frozen=True, slots=True)
class GenerationStats:
    reason: GenerationReason = "error"
    iterations: int = 0
    tool_calls: int = 0
    tool_errors: int = 0
    retrieved_chunks: int = 0


@dataclass(frozen=True, slots=True)
class TurnDetails:
    reason: TurnReason = "unknown"
    #: None means unmeasured, not a successful/non-fallback reply.
    fallback: bool | None = None
    #: ReAct only; poetry's separate generation path is deliberately not inferred.
    generation: GenerationStats | None = None
    failure: UpstreamFailure | None = None
    #: Separate from ReAct iterations/tool calls; includes poetry reply/judge attempts.
    poetry_calls: int | None = None


RagOutcome: TypeAlias = Literal[
    "found", "empty", "filtered", "uncertain", "error", "cancelled", "unknown"
]


@dataclass(frozen=True, slots=True)
class RagObservation:
    """One knowledge-tool invocation, not an inferred final answer verdict."""

    outcome: RagOutcome
    retrieval_degraded: bool = False
    rerank_degraded: bool = False
    low_confidence: bool = False
