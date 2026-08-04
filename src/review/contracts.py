"""Pure Step 4 review invariants.

This module owns no files and performs no lifecycle mutation.  It validates
closed-world review inputs and returns immutable results that a later review
service can persist under the repository lock.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

from src.core.canonical_identity import (
    document_identity_sha256,
    require_sha256,
)


EVIDENCE_BINDINGS = ("not_applicable", "bound", "stale")
APPROVAL_ELIGIBILITY_STATUSES = ("blocked", "eligible")
REVIEW_STATUSES = ("not_requested", "pending", "approved", "rejected")
REVIEW_VERDICTS = ("approved", "rejected")
REJECTION_REASONS = (
    "upstream_source",
    "product_config",
    "extractor_defect",
    "validator_defect",
    "needs_clarification",
)
INSPECTION_SCOPES = ("interactive_state", "page_global", "full_content")
INSPECTION_MODES = ("interactive", "full")
FINDING_CLASSIFICATIONS = ("advisory", "approval_blocking", "unknown")
LEGACY_P3_PROFILE_IDENTITY = {
    "id": "v0.4-validation-p3",
    "schema_version": "1.2",
    "path": "data/configs/validation-profiles/v0.4-p3.json",
    "sha256": "fbbfa8bd937779748e86f48f738af5c561f164bf2e10615efe2515d45ba3ae1b",
}
SUCCESSOR_P3_PROFILE_IDENTITY = {
    "id": "v0.4-validation-p3-successor",
    "schema_version": "1.3",
    "path": "data/configs/validation-profiles/v0.4-p3-successor.json",
    "sha256": "e45ad2ba22c1a9ee91d735f18177f3e0824b01806793573112e8f15f26f94d82",
}
FINDING_CODE_POLICY_IDENTITY = {
    "id": "v0.4-finding-code-policy-p4",
    "schema_version": "1.0",
    "path": "data/configs/finding-code-policies/v0.4-p4.json",
    "sha256": "bed3c18a753a7e3d7a3c00ec6d690a953e3794e1f43472508290637f9266a06b",
}
LEGACY_FINDING_POLICY_ID = "legacy-all-source-findings-block-v1"


class ReviewContractError(ValueError):
    """A review-domain input or transition violates a frozen invariant."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _contract_error(code: str, message: str) -> None:
    raise ReviewContractError(code, message)


def _closed_mapping(
    value: Any,
    *,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
    context: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _contract_error("invalid_object", f"{context} must be an object")
    if any(not isinstance(key, str) for key in value):
        _contract_error(
            "invalid_object_key",
            f"{context} keys must be strings",
        )
    keys = set(value)
    missing = required - keys
    unknown = keys - required - optional
    if missing:
        _contract_error(
            "missing_field",
            f"{context} is missing fields: {', '.join(sorted(missing))}",
        )
    if unknown:
        _contract_error(
            "unknown_field",
            f"{context} has unknown fields: {', '.join(sorted(unknown))}",
        )
    return value


def _enum(value: Any, allowed: Sequence[str], *, field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        _contract_error(
            "invalid_enum",
            f"{field} must be one of {', '.join(allowed)}",
        )
    return value


@dataclass(frozen=True)
class EvidenceBindings:
    """Hashes a Review Decision must bind to the current Batch Item."""

    source_sha256: str
    payload_sha256: str
    validation_artifact_sha256: str
    validation_evidence_sha256: str
    sampling_plan_sha256: str | None

    def __post_init__(self) -> None:
        for field in (
            "source_sha256",
            "payload_sha256",
            "validation_artifact_sha256",
            "validation_evidence_sha256",
        ):
            try:
                require_sha256(getattr(self, field), field=field)
            except ValueError as error:
                _contract_error("invalid_sha256", str(error))
        if self.sampling_plan_sha256 is not None:
            try:
                require_sha256(
                    self.sampling_plan_sha256,
                    field="sampling_plan_sha256",
                )
            except ValueError as error:
                _contract_error("invalid_sha256", str(error))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceBindings":
        parsed = _closed_mapping(
            value,
            required=frozenset({
                "source_sha256",
                "payload_sha256",
                "validation_artifact_sha256",
                "validation_evidence_sha256",
                "sampling_plan_sha256",
            }),
            context="evidence bindings",
        )
        return cls(
            source_sha256=parsed["source_sha256"],
            payload_sha256=parsed["payload_sha256"],
            validation_artifact_sha256=parsed[
                "validation_artifact_sha256"
            ],
            validation_evidence_sha256=parsed[
                "validation_evidence_sha256"
            ],
            sampling_plan_sha256=parsed["sampling_plan_sha256"],
        )

    def to_dict(self) -> dict[str, str | None]:
        return {
            "source_sha256": self.source_sha256,
            "payload_sha256": self.payload_sha256,
            "validation_artifact_sha256": self.validation_artifact_sha256,
            "validation_evidence_sha256": self.validation_evidence_sha256,
            "sampling_plan_sha256": self.sampling_plan_sha256,
        }


def _bindings(
    value: EvidenceBindings | Mapping[str, Any],
) -> EvidenceBindings:
    if isinstance(value, EvidenceBindings):
        return value
    return EvidenceBindings.from_mapping(value)


def derive_evidence_binding(
    current: EvidenceBindings | Mapping[str, Any],
    decision: EvidenceBindings | Mapping[str, Any] | None,
) -> Literal["not_applicable", "bound", "stale"]:
    """Classify the current decision against all current evidence hashes."""

    current_value = _bindings(current)
    if decision is None:
        return "not_applicable"
    return "bound" if _bindings(decision) == current_value else "stale"


def validate_sampling_plan_binding_mode(
    *,
    inspection_mode: str,
    current_bindings: EvidenceBindings | Mapping[str, Any],
    decision_bindings: EvidenceBindings | Mapping[str, Any],
) -> None:
    """Bind interactive/full inspection to the matching Sampling Plan mode."""

    mode = _enum(inspection_mode, INSPECTION_MODES, field="inspection_mode")
    current = _bindings(current_bindings)
    decision = _bindings(decision_bindings)
    plan_hashes = (
        current.sampling_plan_sha256,
        decision.sampling_plan_sha256,
    )
    if mode == "interactive" and any(value is None for value in plan_hashes):
        _contract_error(
            "missing_sampling_plan_binding",
            "Interactive review requires current and decision Sampling Plan hashes",
        )
    if mode == "full" and any(value is not None for value in plan_hashes):
        _contract_error(
            "unexpected_sampling_plan_binding",
            "Full-content review must not bind a Sampling Plan hash",
        )


def derive_review_decision_id(document: Mapping[str, Any]) -> str:
    """Derive a decision ID without allowing it to hash itself."""

    try:
        return document_identity_sha256(document, "decision_id")
    except ValueError as error:
        _contract_error("invalid_decision_document", str(error))


@dataclass(frozen=True)
class ApprovalBlocker:
    code: str
    message: str
    path: str

    def __post_init__(self) -> None:
        for field in ("code", "message", "path"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value:
                _contract_error(
                    "invalid_blocker",
                    f"Approval blocker {field} must be a non-empty string",
                )

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
        }


@dataclass(frozen=True)
class PreconditionResult:
    eligible: bool
    blockers: tuple[ApprovalBlocker, ...]

    def __post_init__(self) -> None:
        if self.eligible != (not self.blockers):
            _contract_error(
                "inconsistent_preconditions",
                "eligible must be true exactly when blockers are empty",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "blockers": [blocker.to_dict() for blocker in self.blockers],
        }


def machine_approval_preconditions(
    execution_status: str,
    validation_status: str,
) -> PreconditionResult:
    """Derive machine-owned approval blockers without a human override."""

    execution = _enum(
        execution_status,
        ("pending", "running", "succeeded", "failed", "skipped"),
        field="execution_status",
    )
    validation = _enum(
        validation_status,
        ("not_run", "passed", "failed"),
        field="validation_status",
    )
    blockers: list[ApprovalBlocker] = []
    if execution != "succeeded":
        blockers.append(ApprovalBlocker(
            code="execution_not_succeeded",
            message="Extraction execution has not succeeded",
            path="$.status.execution",
        ))
    if validation != "passed":
        blockers.append(ApprovalBlocker(
            code="machine_validation_not_passed",
            message="Machine validation has not passed",
            path="$.status.validation",
        ))
    return PreconditionResult(not blockers, tuple(blockers))


derive_machine_approval_preconditions = machine_approval_preconditions


def source_approval_preconditions(
    source_quality_findings: Sequence[Any],
) -> PreconditionResult:
    """Turn every unresolved Source Quality Finding into a blocker."""

    if isinstance(source_quality_findings, (str, bytes, Mapping)) or not isinstance(
        source_quality_findings, Sequence
    ):
        _contract_error(
            "invalid_source_findings",
            "source_quality_findings must be an ordered array",
        )
    blockers: list[ApprovalBlocker] = []
    for index, finding in enumerate(source_quality_findings):
        if not isinstance(finding, Mapping):
            _contract_error(
                "invalid_source_finding",
                f"source_quality_findings[{index}] must be an object",
            )
        code = finding.get("code")
        if not isinstance(code, str) or not code:
            _contract_error(
                "invalid_source_finding",
                f"source_quality_findings[{index}].code is required",
            )
        blockers.append(ApprovalBlocker(
            code="unresolved_source_quality_finding",
            message=f"Unresolved Source Quality Finding: {code}",
            path=f"$.source_quality_findings[{index}]",
        ))
    return PreconditionResult(not blockers, tuple(blockers))


derive_source_approval_preconditions = source_approval_preconditions


def resolve_finding_policy(
    *,
    validation_profile_identity: Mapping[str, Any],
    finding_code_policy_identity: Mapping[str, Any] | None,
) -> str:
    """Resolve the only legal profile/policy combinations.

    Legacy P3 2.0 has no policy artifact and keeps the blanket blocker rule.
    Successor P3 2.1 must bind the exact frozen policy identity.
    """

    profile = dict(validation_profile_identity)
    policy = (
        None
        if finding_code_policy_identity is None
        else dict(finding_code_policy_identity)
    )
    if profile == LEGACY_P3_PROFILE_IDENTITY and policy is None:
        return LEGACY_FINDING_POLICY_ID
    if profile == SUCCESSOR_P3_PROFILE_IDENTITY and policy == FINDING_CODE_POLICY_IDENTITY:
        return str(FINDING_CODE_POLICY_IDENTITY["id"])
    _contract_error(
        "finding_policy_identity_invalid",
        "Validation Profile and Finding Code Policy identity are not a legal pair",
    )


def _policy_classifications(policy: Mapping[str, Any]) -> Mapping[str, Any]:
    value = _closed_mapping(
        policy,
        required=frozenset({
            "schema_version",
            "policy_id",
            "status",
            "unknown_code_disposition",
            "classifications",
        }),
        context="Finding Code Policy",
    )
    if value["schema_version"] != "1.0" or value["policy_id"] != "v0.4-finding-code-policy-p4":
        _contract_error(
            "invalid_finding_code_policy",
            "Finding Code Policy identity is not supported",
        )
    if value["status"] != "frozen" or value["unknown_code_disposition"] != "fail_closed":
        _contract_error(
            "invalid_finding_code_policy",
            "Finding Code Policy must be frozen and fail closed for unknown codes",
        )
    classifications = value["classifications"]
    if not isinstance(classifications, Mapping):
        _contract_error(
            "invalid_finding_code_policy",
            "Finding Code Policy classifications must be an object",
        )
    for code, classification in classifications.items():
        if not isinstance(code, str) or not code:
            _contract_error(
                "invalid_finding_code_policy",
                "Finding Code Policy codes must be non-empty strings",
            )
        _enum(classification, FINDING_CLASSIFICATIONS[:2], field=f"classifications.{code}")
    return classifications


def classify_source_quality_findings(
    source_quality_findings: Sequence[Any],
    finding_code_policy: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Attach the frozen policy classification to every Source Quality Finding."""

    if isinstance(source_quality_findings, (str, bytes, Mapping)) or not isinstance(
        source_quality_findings, Sequence
    ):
        _contract_error(
            "invalid_source_findings",
            "source_quality_findings must be an ordered array",
        )
    classifications = _policy_classifications(finding_code_policy)
    result: list[dict[str, str]] = []
    for index, finding in enumerate(source_quality_findings):
        value = _closed_mapping(
            finding,
            required=frozenset({
                "code",
                "message",
                "path",
                "severity",
                "disposition",
            }),
            optional=frozenset({"classification"}),
            context=f"source_quality_findings[{index}]",
        )
        code = value["code"]
        if not isinstance(code, str) or not code:
            _contract_error(
                "invalid_source_finding",
                f"source_quality_findings[{index}].code is required",
            )
        classification = str(classifications.get(code, "unknown"))
        result.append({
            "code": code,
            "message": str(value["message"]),
            "path": str(value["path"]),
            "severity": str(value["severity"]),
            "disposition": str(value["disposition"]),
            "classification": classification,
        })
    return result


def evaluate_source_findings(
    source_quality_findings: Sequence[Any],
    finding_code_policy: Mapping[str, Any],
) -> PreconditionResult:
    """Derive source approval blockers from the frozen Finding Code Policy."""

    blockers: list[ApprovalBlocker] = []
    for index, finding in enumerate(
        classify_source_quality_findings(
            source_quality_findings,
            finding_code_policy,
        )
    ):
        code = finding["code"]
        classification = finding["classification"]
        path = f"$.source_quality_findings[{index}]"
        if classification == "approval_blocking":
            blockers.append(ApprovalBlocker(
                code="approval_blocking_source_quality_finding",
                message=f"Approval-blocking Source Quality Finding: {code}",
                path=path,
            ))
        elif classification == "unknown":
            blockers.append(ApprovalBlocker(
                code="unknown_source_quality_finding_code",
                message=f"Unknown Source Quality Finding code: {code}",
                path=path,
            ))
    return PreconditionResult(not blockers, tuple(blockers))


@dataclass(frozen=True)
class ApprovalEligibility:
    status: Literal["blocked", "eligible"]
    blockers: tuple[ApprovalBlocker, ...]

    def __post_init__(self) -> None:
        _enum(
            self.status,
            APPROVAL_ELIGIBILITY_STATUSES,
            field="approval eligibility",
        )
        if (self.status == "eligible") != (not self.blockers):
            _contract_error(
                "inconsistent_approval_eligibility",
                "eligible status must be used exactly when blockers are empty",
            )

    @property
    def eligible(self) -> bool:
        return self.status == "eligible"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "blockers": [blocker.to_dict() for blocker in self.blockers],
        }


def derive_approval_eligibility(
    *,
    machine: PreconditionResult,
    source: PreconditionResult,
    evidence_binding: str,
    inspected_states_valid: bool,
) -> ApprovalEligibility:
    """Combine machine, Source, binding, and inspection preconditions."""

    binding = _enum(
        evidence_binding,
        EVIDENCE_BINDINGS,
        field="evidence_binding",
    )
    if not isinstance(inspected_states_valid, bool):
        _contract_error(
            "invalid_inspection_result",
            "inspected_states_valid must be boolean",
        )
    blockers = [*machine.blockers, *source.blockers]
    if binding != "bound":
        blockers.append(ApprovalBlocker(
            code="review_evidence_not_bound",
            message="Review evidence does not bind all current hashes",
            path="$.evidence_binding",
        ))
    if not inspected_states_valid:
        blockers.append(ApprovalBlocker(
            code="invalid_inspected_states",
            message="Inspected states are not valid for this Batch Item",
            path="$.inspected_states",
        ))
    return ApprovalEligibility(
        status="blocked" if blockers else "eligible",
        blockers=tuple(blockers),
    )


derive_final_approval_eligibility = derive_approval_eligibility


@dataclass(frozen=True)
class InspectedState:
    scope: Literal["interactive_state", "page_global", "full_content"]
    state_id: str | None = None

    def __post_init__(self) -> None:
        scope = _enum(self.scope, INSPECTION_SCOPES, field="inspection scope")
        if scope == "interactive_state":
            if self.state_id is None:
                _contract_error(
                    "missing_state_id",
                    "interactive_state inspection requires state_id",
                )
            try:
                require_sha256(self.state_id, field="state_id")
            except ValueError as error:
                _contract_error("invalid_sha256", str(error))
        elif self.state_id is not None:
            _contract_error(
                "unexpected_state_id",
                f"{scope} inspection must not contain state_id",
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "InspectedState":
        parsed = _closed_mapping(
            value,
            required=frozenset({"scope"}),
            optional=frozenset({"state_id"}),
            context="inspected state",
        )
        return cls(
            scope=parsed["scope"],
            state_id=parsed.get("state_id"),
        )

    def to_dict(self) -> dict[str, str]:
        result = {"scope": self.scope}
        if self.state_id is not None:
            result["state_id"] = self.state_id
        return result


def validate_inspected_states(
    values: Sequence[InspectedState | Mapping[str, Any]],
    *,
    inspection_mode: str,
    allowed_state_ids: Sequence[str] = (),
) -> tuple[InspectedState, ...]:
    """Validate interactive identities or the explicit full-content scope."""

    mode = _enum(inspection_mode, INSPECTION_MODES, field="inspection_mode")
    if isinstance(values, (str, bytes, Mapping)) or not isinstance(
        values, Sequence
    ):
        _contract_error(
            "invalid_inspected_states",
            "inspected_states must be an ordered array",
        )
    parsed = tuple(
        value if isinstance(value, InspectedState) else InspectedState.from_mapping(value)
        for value in values
    )
    if not parsed:
        _contract_error(
            "empty_inspected_states",
            "At least one explicit inspection scope is required",
        )
    identities = [
        (value.scope, value.state_id)
        for value in parsed
    ]
    if len(set(identities)) != len(identities):
        _contract_error(
            "duplicate_inspected_state",
            "inspected_states cannot contain duplicate identities",
        )

    if isinstance(allowed_state_ids, (str, bytes)) or not isinstance(
        allowed_state_ids, Sequence
    ):
        _contract_error(
            "invalid_state_universe",
            "allowed_state_ids must be an ordered array",
        )
    try:
        allowed = tuple(
            require_sha256(value, field=f"allowed_state_ids[{index}]")
            for index, value in enumerate(allowed_state_ids)
        )
    except ValueError as error:
        _contract_error("invalid_sha256", str(error))
    if len(set(allowed)) != len(allowed):
        _contract_error(
            "duplicate_state_universe",
            "allowed_state_ids cannot contain duplicates",
        )

    if mode == "full":
        if allowed:
            _contract_error(
                "unexpected_state_universe",
                "full inspection does not accept interactive state identities",
            )
        if parsed != (InspectedState(scope="full_content"),):
            _contract_error(
                "invalid_full_inspection",
                "full inspection requires exactly the full_content scope",
            )
        return parsed

    if not allowed:
        _contract_error(
            "empty_state_universe",
            "interactive inspection requires a frozen state universe",
        )
    if any(value.scope == "full_content" for value in parsed):
        _contract_error(
            "invalid_interactive_scope",
            "interactive inspection cannot claim full_content",
        )
    interactive = [
        value for value in parsed if value.scope == "interactive_state"
    ]
    if not interactive:
        _contract_error(
            "missing_interactive_state",
            "interactive inspection must include at least one reachable state",
        )
    unknown = [
        value.state_id
        for value in interactive
        if value.state_id not in allowed
    ]
    if unknown:
        _contract_error(
            "unreachable_inspected_state",
            "inspected_states contains an identity outside frozen reachability",
        )
    return parsed


@dataclass(frozen=True)
class ReviewTransitionResult:
    verdict: Literal["approved", "rejected"]
    reason: str | None
    evidence_binding: Literal["bound"]
    approval_eligibility: ApprovalEligibility
    inspected_states: tuple[InspectedState, ...]


def validate_review_transition(
    *,
    execution_status: str,
    validation_status: str,
    current_bindings: EvidenceBindings | Mapping[str, Any],
    decision_bindings: EvidenceBindings | Mapping[str, Any],
    source_quality_findings: Sequence[Any],
    inspection_mode: str,
    inspected_states: Sequence[InspectedState | Mapping[str, Any]],
    allowed_state_ids: Sequence[str] = (),
    verdict: str,
    reason: str | None,
    current_decision_id: str | None = None,
    supersedes_decision_id: str | None = None,
) -> ReviewTransitionResult:
    """Validate one proposed append-only approved/rejected decision."""

    machine = machine_approval_preconditions(
        execution_status,
        validation_status,
    )
    if not machine.eligible:
        _contract_error(
            "machine_preconditions_failed",
            "Machine failure cannot be overridden by a Review Decision",
        )
    validate_sampling_plan_binding_mode(
        inspection_mode=inspection_mode,
        current_bindings=current_bindings,
        decision_bindings=decision_bindings,
    )
    binding = derive_evidence_binding(current_bindings, decision_bindings)
    if binding != "bound":
        _contract_error(
            "stale_review_evidence",
            "A Review Decision must bind all current evidence hashes",
        )
    normalized_states = validate_inspected_states(
        inspected_states,
        inspection_mode=inspection_mode,
        allowed_state_ids=allowed_state_ids,
    )
    normalized_verdict = _enum(verdict, REVIEW_VERDICTS, field="verdict")
    source = source_approval_preconditions(source_quality_findings)
    eligibility = derive_approval_eligibility(
        machine=machine,
        source=source,
        evidence_binding=binding,
        inspected_states_valid=True,
    )

    if current_decision_id is None:
        if supersedes_decision_id is not None:
            _contract_error(
                "unexpected_supersession",
                "A first Review Decision cannot supersede another decision",
            )
    else:
        try:
            require_sha256(current_decision_id, field="current_decision_id")
        except ValueError as error:
            _contract_error("invalid_sha256", str(error))
        if supersedes_decision_id != current_decision_id:
            _contract_error(
                "invalid_supersession",
                "A replacement decision must supersede the current decision",
            )

    if normalized_verdict == "approved":
        if reason is not None:
            _contract_error(
                "approved_reason_forbidden",
                "An approved decision must not contain a rejection reason",
            )
        if not eligibility.eligible:
            _contract_error(
                "approval_not_eligible",
                "An approved decision requires final approval eligibility",
            )
    else:
        if reason not in REJECTION_REASONS:
            _contract_error(
                "invalid_rejection_reason",
                "A rejected decision requires one stable rejection reason",
            )

    return ReviewTransitionResult(
        verdict=normalized_verdict,
        reason=reason,
        evidence_binding="bound",
        approval_eligibility=eligibility,
        inspected_states=normalized_states,
    )


@dataclass(frozen=True)
class ReviewLifecycleState:
    review: str
    evidence_binding: str
    approval_eligibility: str
    current_review_decision: Mapping[str, Any] | None

    def __post_init__(self) -> None:
        _enum(self.review, REVIEW_STATUSES, field="review")
        _enum(
            self.evidence_binding,
            EVIDENCE_BINDINGS,
            field="evidence_binding",
        )
        _enum(
            self.approval_eligibility,
            APPROVAL_ELIGIBILITY_STATUSES,
            field="approval_eligibility",
        )
        if self.current_review_decision is not None:
            parsed = _closed_mapping(
                self.current_review_decision,
                required=frozenset({"path", "sha256"}),
                context="current_review_decision",
            )
            path = parsed["path"]
            if not isinstance(path, str) or not path or path.startswith("/"):
                _contract_error(
                    "invalid_artifact_path",
                    "current_review_decision.path must be a relative path",
                )
            try:
                require_sha256(
                    parsed["sha256"],
                    field="current_review_decision.sha256",
                )
            except ValueError as error:
                _contract_error("invalid_sha256", str(error))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ReviewLifecycleState":
        parsed = _closed_mapping(
            value,
            required=frozenset({
                "review",
                "evidence_binding",
                "approval_eligibility",
                "current_review_decision",
            }),
            context="review lifecycle state",
        )
        return cls(
            review=parsed["review"],
            evidence_binding=parsed["evidence_binding"],
            approval_eligibility=parsed["approval_eligibility"],
            current_review_decision=parsed["current_review_decision"],
        )

    def to_dict(self) -> dict[str, Any]:
        reference = self.current_review_decision
        return {
            "review": self.review,
            "evidence_binding": self.evidence_binding,
            "approval_eligibility": self.approval_eligibility,
            "current_review_decision": (
                dict(reference) if reference is not None else None
            ),
        }


def mark_review_state_stale(state: ReviewLifecycleState) -> ReviewLifecycleState:
    """Return the authoritative lifecycle reset while retaining its reference."""

    return replace(
        state,
        review="pending",
        evidence_binding="stale",
        approval_eligibility="blocked",
    )


def apply_stale_review_state(value: Mapping[str, Any]) -> dict[str, Any]:
    """Closed-world Mapping adapter for :func:`mark_review_state_stale`."""

    return mark_review_state_stale(
        ReviewLifecycleState.from_mapping(value)
    ).to_dict()


apply_stale_state = apply_stale_review_state


def apply_stale_batch_item(item: Mapping[str, Any]) -> dict[str, Any]:
    """Purely reset one closed-world Manifest 2.0 Batch Item after drift.

    The append-only decision reference remains in ``artifacts`` so a later
    decision can name it in its supersession chain.  Only the three derived
    lifecycle fields are reset.
    """

    parsed_item = _closed_mapping(
        item,
        required=frozenset({
            "item_id",
            "identity",
            "product_key",
            "resource",
            "page_model",
            "strategy",
            "status",
            "checkpoints",
            "artifacts",
            "error",
        }),
        context="Batch Manifest item",
    )
    status = _closed_mapping(
        parsed_item["status"],
        required=frozenset({
            "execution",
            "validation",
            "review",
            "publication",
            "evidence_binding",
            "approval_eligibility",
            "release",
        }),
        context="Batch Manifest item status",
    )
    artifacts = _closed_mapping(
        parsed_item["artifacts"],
        required=frozenset({
            "normalized_input",
            "payload",
            "diagnostic",
            "validation",
            "parseability",
            "sampling_plan",
            "sampled_content_evidence",
            "current_review_decision",
        }),
        context="Batch Manifest item artifacts",
    )
    _enum(
        status["execution"],
        ("pending", "running", "succeeded", "failed", "skipped"),
        field="status.execution",
    )
    _enum(
        status["validation"],
        ("not_run", "passed", "failed"),
        field="status.validation",
    )
    _enum(
        status["publication"],
        ("not_published", "published"),
        field="status.publication",
    )
    _enum(
        status["release"],
        ("not_released", "released"),
        field="status.release",
    )
    lifecycle = ReviewLifecycleState(
        review=status["review"],
        evidence_binding=status["evidence_binding"],
        approval_eligibility=status["approval_eligibility"],
        current_review_decision=artifacts["current_review_decision"],
    )
    if lifecycle.current_review_decision is None:
        _contract_error(
            "missing_current_review_decision",
            "A stale reset requires the append-only current decision reference",
        )
    stale = mark_review_state_stale(lifecycle)
    result = copy.deepcopy(dict(parsed_item))
    result["status"]["review"] = stale.review
    result["status"]["evidence_binding"] = stale.evidence_binding
    result["status"]["approval_eligibility"] = stale.approval_eligibility
    return result


__all__ = [
    "APPROVAL_ELIGIBILITY_STATUSES",
    "ApprovalBlocker",
    "ApprovalEligibility",
    "EVIDENCE_BINDINGS",
    "EvidenceBindings",
    "FINDING_CLASSIFICATIONS",
    "FINDING_CODE_POLICY_IDENTITY",
    "INSPECTION_MODES",
    "INSPECTION_SCOPES",
    "InspectedState",
    "LEGACY_FINDING_POLICY_ID",
    "LEGACY_P3_PROFILE_IDENTITY",
    "PreconditionResult",
    "REJECTION_REASONS",
    "REVIEW_STATUSES",
    "REVIEW_VERDICTS",
    "ReviewContractError",
    "ReviewLifecycleState",
    "ReviewTransitionResult",
    "SUCCESSOR_P3_PROFILE_IDENTITY",
    "apply_stale_review_state",
    "apply_stale_state",
    "apply_stale_batch_item",
    "classify_source_quality_findings",
    "derive_approval_eligibility",
    "derive_evidence_binding",
    "derive_final_approval_eligibility",
    "derive_machine_approval_preconditions",
    "derive_review_decision_id",
    "derive_source_approval_preconditions",
    "evaluate_source_findings",
    "machine_approval_preconditions",
    "mark_review_state_stale",
    "resolve_finding_policy",
    "source_approval_preconditions",
    "validate_inspected_states",
    "validate_review_transition",
    "validate_sampling_plan_binding_mode",
]
