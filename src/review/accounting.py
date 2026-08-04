"""Read-only Step 5 review accounting projections."""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any


FINDING_CLASSIFICATIONS = ("advisory", "approval_blocking", "unknown")


def finding_summary(value: Mapping[str, Any]) -> dict[str, str]:
    """Project Source Finding evidence without dropping classification."""

    result = {
        "code": str(value.get("code", "SOURCE_QUALITY_FINDING")),
        "message": str(value.get("message", value.get("code", "Source Finding"))),
        "path": str(value.get("path", "$")),
    }
    classification = value.get("classification")
    if classification in FINDING_CLASSIFICATIONS:
        result["classification"] = str(classification)
    return result


def is_source_warning(finding: Mapping[str, Any]) -> bool:
    return finding.get("classification") == "advisory"


def item_accounting(
    *,
    status: Mapping[str, Any],
    source_quality_findings: Sequence[Mapping[str, Any]],
    approval_blockers: Sequence[Mapping[str, Any]],
    release_ready: bool | None = None,
) -> dict[str, bool]:
    machine_failed = status.get("validation") == "failed"
    approval_blocked = (
        status.get("validation") == "passed" and bool(approval_blockers)
    )
    current_release_ready = (
        status.get("execution") == "succeeded"
        and status.get("validation") == "passed"
        and status.get("approval_eligibility") == "eligible"
        and status.get("review") == "approved"
        and status.get("evidence_binding") == "bound"
    )
    return {
        "source_warning": any(is_source_warning(finding) for finding in source_quality_findings),
        "approval_blocked": approval_blocked,
        "machine_failed": machine_failed,
        "release_ready": current_release_ready if release_ready is None else bool(release_ready),
    }


def merge_item_accounting(item: Mapping[str, Any], *, release_ready: bool | None = None) -> dict[str, Any]:
    result = copy.deepcopy(dict(item))
    flags = item_accounting(
        status=result["status"],
        source_quality_findings=result.get("source_quality_findings", []),
        approval_blockers=result.get("approval_blockers", []),
        release_ready=release_ready,
    )
    result.update(flags)
    return result


def summarize_review_items(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "total": len(items),
        "reviewable": sum(
            item["status"]["evidence_binding"] != "stale" for item in items
        ),
        "pending": sum(item["status"]["review"] == "pending" for item in items),
        "approved": sum(item["status"]["review"] == "approved" for item in items),
        "rejected": sum(item["status"]["review"] == "rejected" for item in items),
        "evidence_bound": sum(
            item["status"]["evidence_binding"] == "bound" for item in items
        ),
        "evidence_stale": sum(
            item["status"]["evidence_binding"] == "stale" for item in items
        ),
        "evidence_not_applicable": sum(
            item["status"]["evidence_binding"] == "not_applicable" for item in items
        ),
        "approval_eligible": sum(
            item["status"]["approval_eligibility"] == "eligible" for item in items
        ),
        "approval_blocked_count": sum(bool(item.get("approval_blocked")) for item in items),
        "source_warning_count": sum(bool(item.get("source_warning")) for item in items),
        "machine_failed_count": sum(bool(item.get("machine_failed")) for item in items),
        "release_ready_count": sum(bool(item.get("release_ready")) for item in items),
    }


def legacy_review_summary(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Keep old Review Queue 2.0 projections read-only valid."""

    return {
        "total": len(items),
        "reviewable": sum(
            item["status"]["evidence_binding"] != "stale" for item in items
        ),
        "pending": sum(item["status"]["review"] == "pending" for item in items),
        "approved": sum(item["status"]["review"] == "approved" for item in items),
        "rejected": sum(item["status"]["review"] == "rejected" for item in items),
        "evidence_bound": sum(
            item["status"]["evidence_binding"] == "bound" for item in items
        ),
        "evidence_stale": sum(
            item["status"]["evidence_binding"] == "stale" for item in items
        ),
        "evidence_not_applicable": sum(
            item["status"]["evidence_binding"] == "not_applicable" for item in items
        ),
        "approval_eligible": sum(
            item["status"]["approval_eligibility"] == "eligible" for item in items
        ),
        "approval_blocked": sum(
            item["status"]["approval_eligibility"] == "blocked" for item in items
        ),
        "source_blocked": sum(bool(item["source_quality_findings"]) for item in items),
    }
