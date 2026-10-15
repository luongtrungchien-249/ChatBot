import pytest

from agents.domain.errors import BudgetExceeded, UpstreamError, UpstreamTimeout
from agents.domain.telemetry import upstream_failure


@pytest.mark.parametrize(
    "status,kind",
    [
        (401, "auth"),
        (403, "auth"),
        (429, "throttled"),
        (503, "server"),
        (400, "client"),
        (None, "unknown"),
    ],
)
def test_upstream_cause_uses_structural_error(status: int | None, kind: str) -> None:
    result = upstream_failure(UpstreamError("llm", status))
    assert result is not None and result.service == "llm" and result.kind == kind


def test_timeout_and_unknown_service_do_not_export_arbitrary_strings() -> None:
    result = upstream_failure(UpstreamTimeout("embed"))
    assert result is not None and result.kind == "timeout" and result.service == "embed"
    result = upstream_failure(UpstreamError("private-service-query", 500))
    assert result is not None and result.service == "unknown"
    assert upstream_failure(BudgetExceeded()) is None
