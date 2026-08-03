from __future__ import annotations

import copy
import hashlib

import pytest

from src.core.canonical_identity import (
    CanonicalIdentityError,
    canonical_json,
    canonical_sha256,
    derive_sampling_seed,
    derive_state_id,
    derive_universe_id,
    document_identity_sha256,
    sampled_content_evidence_sha256,
    sampling_plan_sha256,
    validation_evidence_sha256,
)
from src.release.contracts import (
    ReleaseContractError,
    derive_release_seal,
    evaluate_release_item,
    release_item_predicate,
    validate_release_manifest_bindings,
)
from src.review.contracts import (
    REJECTION_REASONS,
    ReviewContractError,
    apply_stale_batch_item,
    apply_stale_review_state,
    derive_approval_eligibility,
    derive_evidence_binding,
    derive_review_decision_id,
    machine_approval_preconditions,
    source_approval_preconditions,
    validate_inspected_states,
    validate_review_transition,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _evidence_bindings() -> dict[str, str | None]:
    return {
        "source_sha256": _sha("source"),
        "payload_sha256": _sha("payload"),
        "validation_artifact_sha256": _sha("validation-file"),
        "validation_evidence_sha256": _sha("validation-evidence"),
        "sampling_plan_sha256": _sha("sampling-plan"),
    }


def _release_hashes() -> dict[str, str | None]:
    return {
        "payload_sha256": _sha("payload"),
        "validation_artifact_sha256": _sha("validation-file"),
        "validation_evidence_sha256": _sha("validation-evidence"),
        "review_decision_sha256": _sha("review-decision"),
        "validation_profile_sha256": _sha("profile"),
        "sampling_plan_sha256": _sha("sampling-plan"),
    }


def _release_manifest() -> dict[str, object]:
    artifact = {
        "path": "runs/batch/input-manifest.json",
        "sha256": _sha("manifest-artifact"),
    }
    profile = {
        "id": "v0.4-validation-p3",
        "schema_version": "1.2",
        "path": "data/configs/validation-profiles/v0.4-p3.json",
        "sha256": _sha("profile"),
    }
    sampling_profile = {
        "id": "v0.4-content-sampling-p3",
        "schema_version": "1.0",
        "path": "data/configs/content-sampling-profiles/v0.4-p3.json",
        "sha256": _sha("sampling-profile"),
    }
    first_bindings = _release_hashes()
    second_bindings = {
        **_release_hashes(),
        "payload_sha256": _sha("second-payload"),
        "review_decision_sha256": _sha("second-review"),
        "sampling_plan_sha256": None,
    }
    return {
        "schema_version": "1.0",
        "release_id": "release-1",
        "created_at": "2026-08-03T12:00:00Z",
        "batch_id": "20260803T120000Z-aaaaaaaa",
        "batch_manifest": artifact,
        "input_manifest": {
            **artifact,
            "path": "runs/batch/batch-manifest.json",
        },
        "validation_profile": profile,
        "content_sampling_profile": sampling_profile,
        "target": {
            "account_url": "https://example.blob.core.windows.net",
            "container": "cms",
            "prefix": "pricing",
        },
        "assurance": {
            "structural_scope": "all_source_proven_reachable_states",
            "content_claim": "sampled_state_content_consistency",
            "excluded_claims": [
                "unselected_state_content_consistency",
                "complete_pricing_fact_fidelity",
                "commercial_price_accuracy",
                "visual_equivalence",
            ],
        },
        "items": [
            {
                "item_id": "zh-cn/api-management",
                "resource_key": "api-management",
                "language": "zh-cn",
                "payload": {
                    "source_path": "runs/batch/outputs/zh-cn/api.json",
                    "release_path": "payloads/zh-cn/api.json",
                    "sha256": first_bindings["payload_sha256"],
                },
                "validation_path": "runs/batch/validation/zh-cn/api.json",
                "review_decision_path": "runs/batch/review/api.json",
                "review_decision_id": _sha("first-review-id"),
                "bindings": first_bindings,
                "coverage": {
                    "mode": "stratified_sample",
                    "universe_count": 20,
                    "selected_count": 12,
                    "untested_count": 8,
                },
                "target_blob": {
                    "container": "cms",
                    "name": "pricing/zh-cn/api.json",
                },
            },
            {
                "item_id": "en-us/event-grid",
                "resource_key": "event-grid",
                "language": "en-us",
                "payload": {
                    "source_path": "runs/batch/outputs/en-us/event.json",
                    "release_path": "payloads/en-us/event.json",
                    "sha256": second_bindings["payload_sha256"],
                },
                "validation_path": "runs/batch/validation/en-us/event.json",
                "review_decision_path": "runs/batch/review/event.json",
                "review_decision_id": _sha("second-review-id"),
                "bindings": second_bindings,
                "coverage": {
                    "mode": "full",
                    "universe_count": 1,
                    "selected_count": 1,
                    "untested_count": 0,
                },
                "target_blob": {
                    "container": "cms",
                    "name": "pricing/en-us/event.json",
                },
            },
        ],
    }


def _interactive_state_ids() -> tuple[str, str]:
    return (
        derive_state_id([("region", "china-east")]),
        derive_state_id([("region", "china-north")]),
    )


def _transition_values() -> dict[str, object]:
    states = _interactive_state_ids()
    return {
        "execution_status": "succeeded",
        "validation_status": "passed",
        "current_bindings": _evidence_bindings(),
        "decision_bindings": _evidence_bindings(),
        "source_quality_findings": [],
        "inspection_mode": "interactive",
        "inspected_states": [
            {"scope": "page_global"},
            {"scope": "interactive_state", "state_id": states[1]},
        ],
        "allowed_state_ids": states,
        "verdict": "approved",
        "reason": None,
    }


def test_canonical_json_and_self_identity_are_stable_and_utf8() -> None:
    left = {"z": "中国", "a": {"b": 1}, "decision_id": _sha("old")}
    right = {"decision_id": _sha("new"), "a": {"b": 1}, "z": "中国"}

    assert canonical_json({"z": "中国", "a": 1}) == '{"a":1,"z":"中国"}'
    assert document_identity_sha256(left, "decision_id") == (
        document_identity_sha256(right, "decision_id")
    )
    assert derive_review_decision_id(left) == derive_review_decision_id(right)


def test_self_identity_exclusion_is_top_level_only() -> None:
    document = {
        "decision_id": _sha("outer"),
        "nested": {"decision_id": _sha("nested")},
    }
    changed_nested = {
        "decision_id": _sha("other-outer"),
        "nested": {"decision_id": _sha("other-nested")},
    }

    assert document_identity_sha256(document, "decision_id") != (
        document_identity_sha256(changed_nested, "decision_id")
    )


def test_plan_and_sampled_evidence_named_identities_exclude_themselves() -> None:
    plan = {"schema_version": "1.0", "plan_sha256": _sha("old")}
    evidence = {"schema_version": "1.0", "evidence_sha256": _sha("old")}

    assert sampling_plan_sha256(plan) == sampling_plan_sha256({
        **plan,
        "plan_sha256": _sha("new"),
    })
    assert sampled_content_evidence_sha256(evidence) == (
        sampled_content_evidence_sha256({
            **evidence,
            "evidence_sha256": _sha("new"),
        })
    )


def test_canonical_identity_rejects_non_json_and_non_finite_values() -> None:
    with pytest.raises(CanonicalIdentityError, match="non-string"):
        canonical_sha256({1: "not-json"})
    with pytest.raises(CanonicalIdentityError, match="non-finite"):
        canonical_sha256({"value": float("nan")})


def test_state_and_universe_identity_preserve_source_order() -> None:
    first = derive_state_id([
        ("software", "linux"),
        ("region", "china-east"),
    ])
    same = derive_state_id([
        {"value": "linux", "filterKey": "software"},
        {"matchValues": "china-east", "filterKey": "region"},
    ])
    reordered = derive_state_id([
        ("region", "china-east"),
        ("software", "linux"),
    ])
    second = derive_state_id([("software", "windows")])

    assert first == same
    assert first != reordered
    assert derive_universe_id([first, second], first) != derive_universe_id(
        [second, first],
        first,
    )
    with pytest.raises(CanonicalIdentityError, match="duplicate filterKey"):
        derive_state_id([("region", "east"), ("region", "north")])
    with pytest.raises(CanonicalIdentityError, match="must belong"):
        derive_universe_id([first], second)


def test_sampling_seed_has_only_the_four_frozen_inputs() -> None:
    values = {
        "algorithm_version": "stratified-source-v1",
        "source_sha256": _sha("source"),
        "item_id": "zh-cn/api-management",
        "profile_sha256": _sha("profile"),
    }

    assert derive_sampling_seed(**values) == derive_sampling_seed(**dict(values))
    with pytest.raises(TypeError):
        derive_sampling_seed(**values, payload_sha256=_sha("payload"))
    assert derive_sampling_seed(**values) != derive_sampling_seed(
        **{**values, "source_sha256": _sha("different-source")}
    )


def test_validation_semantic_hash_ignores_batch_and_time_envelope() -> None:
    evidence = {
        "bindings": {"source_sha256": _sha("source")},
        "errors": [],
        "evidence_sha256": _sha("ignored-self-id"),
    }
    first = {
        "schema_version": "2.0",
        "batch_id": "batch-a",
        "item_id": "zh-cn/example",
        "status": "passed",
        "evidence_sha256": _sha("envelope-id"),
        "evidence": evidence,
    }
    second = {
        **first,
        "batch_id": "batch-b",
        "validated_at": "2099-01-01T00:00:00Z",
        "evidence_sha256": _sha("other-envelope-id"),
    }

    assert validation_evidence_sha256(first) == validation_evidence_sha256(second)
    second["evidence"] = {**evidence, "errors": [{"code": "mismatch"}]}
    assert validation_evidence_sha256(first) != validation_evidence_sha256(second)


def test_evidence_binding_is_not_applicable_bound_or_stale() -> None:
    current = _evidence_bindings()
    changed = {**current, "payload_sha256": _sha("new-payload")}

    assert derive_evidence_binding(current, None) == "not_applicable"
    assert derive_evidence_binding(current, dict(reversed(list(current.items())))) == "bound"
    assert derive_evidence_binding(current, changed) == "stale"


def test_evidence_bindings_are_closed_world() -> None:
    with pytest.raises(ReviewContractError) as caught:
        derive_evidence_binding(
            _evidence_bindings(),
            {**_evidence_bindings(), "batch_id": "not-a-binding"},
        )
    assert caught.value.code == "unknown_field"


def test_machine_and_source_preconditions_remain_separate() -> None:
    machine = machine_approval_preconditions("succeeded", "passed")
    source = source_approval_preconditions([])
    assert machine.to_dict() == {"eligible": True, "blockers": []}
    assert source.to_dict() == {"eligible": True, "blockers": []}

    failed_machine = machine_approval_preconditions("failed", "failed")
    finding_source = source_approval_preconditions([
        {"code": "SOURCE_ENCODING_DECLARATION_MISMATCH"},
        {"code": "SOURCE_MISSING_PANEL"},
    ])
    assert [item.code for item in failed_machine.blockers] == [
        "execution_not_succeeded",
        "machine_validation_not_passed",
    ]
    assert len(finding_source.blockers) == 2
    assert all(
        item.code == "unresolved_source_quality_finding"
        for item in finding_source.blockers
    )


def test_final_eligibility_requires_machine_source_binding_and_inspection() -> None:
    machine = machine_approval_preconditions("succeeded", "passed")
    source = source_approval_preconditions([])
    assert derive_approval_eligibility(
        machine=machine,
        source=source,
        evidence_binding="bound",
        inspected_states_valid=True,
    ).status == "eligible"
    blocked = derive_approval_eligibility(
        machine=machine,
        source=source,
        evidence_binding="stale",
        inspected_states_valid=False,
    )
    assert blocked.status == "blocked"
    assert [item.code for item in blocked.blockers] == [
        "review_evidence_not_bound",
        "invalid_inspected_states",
    ]


def test_interactive_inspection_accepts_reachable_state_and_page_global() -> None:
    states = _interactive_state_ids()
    inspected = validate_inspected_states(
        [
            {"scope": "page_global"},
            {"scope": "interactive_state", "state_id": states[0]},
        ],
        inspection_mode="interactive",
        allowed_state_ids=states,
    )

    assert [item.scope for item in inspected] == [
        "page_global",
        "interactive_state",
    ]


@pytest.mark.parametrize(
    ("values", "code"),
    [
        ([{"scope": "page_global"}], "missing_interactive_state"),
        ([{"scope": "full_content"}], "invalid_interactive_scope"),
        (
            [{"scope": "interactive_state", "state_id": _sha("unknown")}],
            "unreachable_inspected_state",
        ),
        (
            [{"scope": "page_global", "unexpected": True}],
            "unknown_field",
        ),
    ],
)
def test_interactive_inspection_fails_closed(
    values: list[dict[str, object]],
    code: str,
) -> None:
    with pytest.raises(ReviewContractError) as caught:
        validate_inspected_states(
            values,
            inspection_mode="interactive",
            allowed_state_ids=_interactive_state_ids(),
        )
    assert caught.value.code == code


def test_full_mode_requires_one_explicit_full_content_scope() -> None:
    inspected = validate_inspected_states(
        [{"scope": "full_content"}],
        inspection_mode="full",
    )
    assert inspected[0].to_dict() == {"scope": "full_content"}

    with pytest.raises(ReviewContractError) as caught:
        validate_inspected_states(
            [{"scope": "page_global"}],
            inspection_mode="full",
        )
    assert caught.value.code == "invalid_full_inspection"


def test_full_mode_review_transition_uses_no_sampling_plan() -> None:
    bindings = {**_evidence_bindings(), "sampling_plan_sha256": None}
    result = validate_review_transition(
        execution_status="succeeded",
        validation_status="passed",
        current_bindings=bindings,
        decision_bindings=bindings,
        source_quality_findings=[],
        inspection_mode="full",
        inspected_states=[{"scope": "full_content"}],
        verdict="approved",
        reason=None,
    )
    assert result.approval_eligibility.status == "eligible"
    assert result.inspected_states[0].scope == "full_content"


@pytest.mark.parametrize("verdict", ("approved", "rejected"))
def test_interactive_transition_requires_sampling_plan_binding(
    verdict: str,
) -> None:
    bindings = {**_evidence_bindings(), "sampling_plan_sha256": None}
    values = {
        **_transition_values(),
        "current_bindings": bindings,
        "decision_bindings": bindings,
        "verdict": verdict,
        "reason": "needs_clarification" if verdict == "rejected" else None,
    }

    with pytest.raises(ReviewContractError) as caught:
        validate_review_transition(**values)
    assert caught.value.code == "missing_sampling_plan_binding"


@pytest.mark.parametrize("verdict", ("approved", "rejected"))
def test_full_transition_forbids_sampling_plan_binding(verdict: str) -> None:
    bindings = _evidence_bindings()

    with pytest.raises(ReviewContractError) as caught:
        validate_review_transition(
            execution_status="succeeded",
            validation_status="passed",
            current_bindings=bindings,
            decision_bindings=bindings,
            source_quality_findings=[],
            inspection_mode="full",
            inspected_states=[{"scope": "full_content"}],
            verdict=verdict,
            reason=(
                "needs_clarification" if verdict == "rejected" else None
            ),
        )
    assert caught.value.code == "unexpected_sampling_plan_binding"


def test_approved_transition_requires_final_eligibility() -> None:
    result = validate_review_transition(**_transition_values())
    assert result.verdict == "approved"
    assert result.approval_eligibility.status == "eligible"
    assert result.evidence_binding == "bound"

    with_finding = {
        **_transition_values(),
        "source_quality_findings": [{"code": "SOURCE_DEFECT"}],
    }
    with pytest.raises(ReviewContractError) as caught:
        validate_review_transition(**with_finding)
    assert caught.value.code == "approval_not_eligible"


@pytest.mark.parametrize("reason", REJECTION_REASONS)
def test_each_stable_rejection_reason_is_accepted(reason: str) -> None:
    values = {
        **_transition_values(),
        "verdict": "rejected",
        "reason": reason,
        "source_quality_findings": [{"code": "SOURCE_DEFECT"}],
    }
    result = validate_review_transition(**values)
    assert result.verdict == "rejected"
    assert result.reason == reason
    assert result.approval_eligibility.status == "blocked"


def test_rejected_transition_requires_stable_reason() -> None:
    values = {
        **_transition_values(),
        "verdict": "rejected",
        "reason": "free-form",
    }
    with pytest.raises(ReviewContractError) as caught:
        validate_review_transition(**values)
    assert caught.value.code == "invalid_rejection_reason"


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        (
            {"execution_status": "failed", "verdict": "rejected", "reason": "extractor_defect"},
            "machine_preconditions_failed",
        ),
        (
            {"validation_status": "failed", "verdict": "rejected", "reason": "validator_defect"},
            "machine_preconditions_failed",
        ),
        (
            {
                "decision_bindings": {
                    **_evidence_bindings(),
                    "validation_evidence_sha256": _sha("stale"),
                }
            },
            "stale_review_evidence",
        ),
    ],
)
def test_machine_failure_and_stale_evidence_cannot_produce_decision(
    updates: dict[str, object],
    code: str,
) -> None:
    with pytest.raises(ReviewContractError) as caught:
        validate_review_transition(**{**_transition_values(), **updates})
    assert caught.value.code == code


def test_replacement_decision_requires_exact_supersession_identity() -> None:
    decision_id = _sha("current-decision")
    result = validate_review_transition(
        **_transition_values(),
        current_decision_id=decision_id,
        supersedes_decision_id=decision_id,
    )
    assert result.verdict == "approved"

    with pytest.raises(ReviewContractError) as caught:
        validate_review_transition(
            **_transition_values(),
            current_decision_id=decision_id,
            supersedes_decision_id=_sha("wrong-decision"),
        )
    assert caught.value.code == "invalid_supersession"


def test_stale_state_reset_is_pure_and_retains_append_only_reference() -> None:
    original = {
        "review": "approved",
        "evidence_binding": "bound",
        "approval_eligibility": "eligible",
        "current_review_decision": {
            "path": "review/decisions/decision.json",
            "sha256": _sha("decision"),
        },
    }
    reset = apply_stale_review_state(original)

    assert reset == {
        **original,
        "review": "pending",
        "evidence_binding": "stale",
        "approval_eligibility": "blocked",
    }
    assert original["review"] == "approved"
    assert reset["current_review_decision"] == original["current_review_decision"]


def test_stale_batch_item_reset_uses_manifest_locations_and_is_pure() -> None:
    reference = {
        "path": "review/decisions/decision.json",
        "sha256": _sha("decision"),
    }
    artifact = {"path": "artifact.json", "sha256": _sha("artifact")}
    item = {
        "item_id": "zh-cn/example",
        "identity": {"language": "zh-cn", "resource_key": "example"},
        "product_key": "example",
        "resource": {
            "kind": "current",
            "slug": "example",
            "version_key": None,
            "version_label": None,
        },
        "page_model": "FlexibleContentPage",
        "strategy": "region_filter",
        "status": {
            "execution": "succeeded",
            "validation": "passed",
            "review": "approved",
            "publication": "not_published",
            "evidence_binding": "bound",
            "approval_eligibility": "eligible",
            "release": "not_released",
        },
        "checkpoints": {},
        "artifacts": {
            "normalized_input": artifact,
            "payload": artifact,
            "diagnostic": artifact,
            "validation": artifact,
            "parseability": artifact,
            "sampling_plan": artifact,
            "sampled_content_evidence": artifact,
            "current_review_decision": reference,
        },
        "error": None,
    }
    stale = apply_stale_batch_item(item)

    assert stale["status"] == {
        **item["status"],
        "review": "pending",
        "evidence_binding": "stale",
        "approval_eligibility": "blocked",
    }
    assert stale["artifacts"]["current_review_decision"] == reference
    assert stale["artifacts"] is not item["artifacts"]
    assert item["status"]["review"] == "approved"

    invalid = {**item, "status": {**item["status"], "unknown": True}}
    with pytest.raises(ReviewContractError) as caught:
        apply_stale_batch_item(invalid)
    assert caught.value.code == "unknown_field"


def test_release_predicate_requires_every_gate_and_current_hash() -> None:
    hashes = _release_hashes()
    values = {
        "execution_status": "succeeded",
        "validation_status": "passed",
        "evidence_binding": "bound",
        "approval_eligibility": "eligible",
        "review_status": "approved",
        "current_hashes": hashes,
        "release_hashes": dict(reversed(list(hashes.items()))),
    }
    assert release_item_predicate(**values)

    mismatch = {
        **hashes,
        "review_decision_sha256": _sha("superseded-review"),
    }
    result = evaluate_release_item(**{**values, "release_hashes": mismatch})
    assert not result.eligible
    assert [item.code for item in result.blockers] == [
        "current_hash_mismatch"
    ]


@pytest.mark.parametrize(
    ("field", "value", "blocker"),
    [
        ("execution_status", "failed", "execution_not_succeeded"),
        ("validation_status", "failed", "validation_not_passed"),
        ("evidence_binding", "stale", "evidence_not_bound"),
        ("approval_eligibility", "blocked", "approval_not_eligible"),
        ("review_status", "rejected", "review_not_approved"),
    ],
)
def test_each_release_lifecycle_gate_fails_closed(
    field: str,
    value: str,
    blocker: str,
) -> None:
    hashes = _release_hashes()
    candidate = {
        "execution_status": "succeeded",
        "validation_status": "passed",
        "evidence_binding": "bound",
        "approval_eligibility": "eligible",
        "review_status": "approved",
        "current_hashes": hashes,
        "release_hashes": hashes,
        field: value,
    }
    result = evaluate_release_item(**candidate)
    assert not result.eligible
    assert blocker in {item.code for item in result.blockers}


def test_release_hash_bindings_are_closed_world() -> None:
    hashes = _release_hashes()
    with pytest.raises(ReleaseContractError) as caught:
        evaluate_release_item(
            execution_status="succeeded",
            validation_status="passed",
            evidence_binding="bound",
            approval_eligibility="eligible",
            review_status="approved",
            current_hashes=hashes,
            release_hashes={**hashes, "source_sha256": _sha("source")},
        )
    assert caught.value.code == "unknown_field"


def test_release_manifest_semantic_bindings_are_valid() -> None:
    manifest = _release_manifest()

    assert validate_release_manifest_bindings(manifest)
    manifest["items"].reverse()
    assert validate_release_manifest_bindings(manifest)


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("empty_items", "empty_release_items"),
        ("duplicate_item_id", "duplicate_release_item_id"),
        ("item_identity", "release_item_identity_mismatch"),
        ("payload_binding", "release_payload_binding_mismatch"),
        (
            "validation_profile",
            "release_validation_profile_binding_mismatch",
        ),
        ("target_container", "release_target_container_mismatch"),
        ("coverage_counts", "release_coverage_count_mismatch"),
        ("full_incomplete", "release_full_coverage_incomplete"),
        ("full_plan", "release_full_sampling_plan_forbidden"),
        (
            "stratified_without_plan",
            "release_stratified_sampling_plan_required",
        ),
        ("duplicate_release_path", "duplicate_release_path"),
        ("duplicate_target_blob", "duplicate_target_blob_identity"),
        ("unknown_top_field", "unknown_field"),
    ],
)
def test_release_manifest_semantic_bindings_fail_closed(
    mutation: str,
    code: str,
) -> None:
    manifest = copy.deepcopy(_release_manifest())
    items = manifest["items"]
    first = items[0]
    second = items[1]

    if mutation == "empty_items":
        manifest["items"] = []
    elif mutation == "duplicate_item_id":
        second["item_id"] = first["item_id"]
        second["language"] = first["language"]
        second["resource_key"] = first["resource_key"]
    elif mutation == "item_identity":
        first["item_id"] = "zh-cn/not-api-management"
    elif mutation == "payload_binding":
        first["bindings"]["payload_sha256"] = _sha("different-payload")
    elif mutation == "validation_profile":
        first["bindings"]["validation_profile_sha256"] = _sha(
            "different-profile"
        )
    elif mutation == "target_container":
        first["target_blob"]["container"] = "other"
    elif mutation == "coverage_counts":
        first["coverage"]["universe_count"] = 21
    elif mutation == "full_incomplete":
        second["coverage"].update({
            "universe_count": 20,
            "selected_count": 1,
            "untested_count": 19,
        })
    elif mutation == "full_plan":
        second["bindings"]["sampling_plan_sha256"] = _sha("unexpected-plan")
    elif mutation == "stratified_without_plan":
        first["bindings"]["sampling_plan_sha256"] = None
    elif mutation == "duplicate_release_path":
        second["payload"]["release_path"] = first["payload"]["release_path"]
    elif mutation == "duplicate_target_blob":
        second["target_blob"] = copy.deepcopy(first["target_blob"])
    elif mutation == "unknown_top_field":
        manifest["seal"] = _sha("self-embedded-seal")
    else:  # pragma: no cover - the parameter table is closed-world.
        raise AssertionError(mutation)

    with pytest.raises(ReleaseContractError) as caught:
        validate_release_manifest_bindings(manifest)
    assert caught.value.code == code


def test_release_seal_uses_manifest_and_item_sorted_payload_hashes() -> None:
    manifest = _sha("release-manifest-file")
    first = {
        "zh-cn/z-resource": _sha("z-payload"),
        "en-us/a-resource": _sha("a-payload"),
    }
    second = dict(reversed(list(first.items())))

    assert derive_release_seal(manifest, first) == derive_release_seal(
        manifest,
        second,
    )
    assert derive_release_seal(manifest, first) != derive_release_seal(
        _sha("different-manifest"),
        first,
    )
