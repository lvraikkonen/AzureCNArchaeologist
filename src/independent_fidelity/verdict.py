"""Item-level L3 claim aggregation frozen by the v0.5.1 plan."""

from __future__ import annotations

from collections.abc import Iterable


CLAIM_VERDICTS = {
    "passed",
    "failed",
    "blocked",
    "not_qualified",
    "not_run",
}
EXECUTED_SCOPE_VERDICTS = {"passed", "failed", "blocked"}


class ClaimStateError(ValueError):
    """Claim execution state and scope results form an impossible mixture."""


def aggregate_item_verdict(
    *,
    qualified: bool,
    started: bool,
    required_scope_verdicts: Iterable[str] = (),
    runtime_error: bool = False,
) -> str:
    """Aggregate required scopes using failed > blocked > passed.

    ``not_qualified`` and ``not_run`` are execution-precondition results. Once
    execution starts, the result is necessarily failed, blocked, or passed.
    """

    scopes = tuple(required_scope_verdicts)
    invalid = [value for value in scopes if value not in EXECUTED_SCOPE_VERDICTS]
    if invalid:
        raise ClaimStateError(f"Invalid executed scope verdict(s): {invalid}")
    if not qualified:
        if started or scopes or runtime_error:
            raise ClaimStateError(
                "not_qualified cannot be mixed with executed scope results"
            )
        return "not_qualified"
    if not started:
        if scopes or runtime_error:
            raise ClaimStateError(
                "not_run cannot be mixed with executed scope results"
            )
        return "not_run"
    if "failed" in scopes:
        return "failed"
    if runtime_error or not scopes or "blocked" in scopes:
        return "blocked"
    if all(value == "passed" for value in scopes):
        return "passed"
    raise ClaimStateError("Unable to aggregate required scope verdicts")
