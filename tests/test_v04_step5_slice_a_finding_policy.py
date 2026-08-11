from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from src.core.canonical_identity import validation_evidence_sha256
from src.core.product_catalog import sha256_file
from src.core.validation_context import ValidationContextRegistry
from src.pipeline.state_store import ManifestValidationError, StateStore
from src.review.contracts import (
    FINDING_CODE_POLICY_IDENTITY,
    LEGACY_FINDING_POLICY_ID,
    LEGACY_P3_PROFILE_IDENTITY,
    SUCCESSOR_P3_PROFILE_IDENTITY,
    ReviewContractError,
    classify_source_quality_findings,
    evaluate_source_findings,
    machine_approval_preconditions,
    resolve_finding_policy,
    source_approval_preconditions,
)


ROOT = Path(__file__).resolve().parents[1]
BATCH_ID = "20260804T120000Z-deadbeef"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _policy() -> dict[str, object]:
    return json.loads(
        (ROOT / "data/configs/finding-code-policies/v0.4-p4.json").read_text(
            encoding="utf-8"
        )
    )


def _finding(code: str) -> dict[str, str]:
    return {
        "code": code,
        "message": f"{code} requires policy evaluation.",
        "path": "$.fixture",
        "severity": "finding",
        "disposition": "unresolved",
    }


def _successor_identities() -> tuple[
    dict[str, str],
    dict[str, str],
    dict[str, str],
]:
    registry = ValidationContextRegistry(ROOT)
    frozen = registry.freeze(validation_profile_id="v0.4-validation-p3-successor")
    profile = frozen["validation_context"]["validation_profile"]
    sampling = registry.content_sampling_profile_identity_for(profile)
    policy = registry.finding_code_policy_identity_for(profile)
    assert sampling is not None
    assert policy is not None
    return profile, sampling, policy


def _validation_21(source_findings: list[dict[str, str]]) -> dict[str, object]:
    profile, sampling, policy_identity = _successor_identities()
    finding_policy = _policy()
    classified = classify_source_quality_findings(
        source_findings,
        finding_policy,
    )
    coverage = {
        "mode": "full",
        "universe_count": 1,
        "selected_count": 1,
        "untested_count": 0,
        "seed": None,
        "strata": [],
        "selected_state_ids": [],
        "assurance": "sampled_state_content_consistency",
    }
    validation = {
        "schema_version": "2.1",
        "batch_id": BATCH_ID,
        "item_id": "zh-cn/fixture",
        "status": "passed",
        "evidence_sha256": "0" * 64,
        "evidence": {
            "verdict": "passed",
            "bindings": {
                "source": {"path": "data/source.html", "sha256": _sha("source")},
                "normalized_input": {
                    "path": "data/normalized.html",
                    "sha256": _sha("normalized"),
                },
                "payload": {
                    "path": "runs/batch/outputs/zh-cn/fixture.json",
                    "sha256": _sha("payload"),
                },
                "soft_category": {
                    "path": "data/configs/soft-category.json",
                    "sha256": sha256_file(ROOT / "data/configs/soft-category.json"),
                },
                "validation_profile": profile,
                "content_sampling_profile": sampling,
                "sampling_plan": None,
                "finding_code_policy_identity": policy_identity,
            },
            "structure_validation": {
                "status": "passed",
                "checked_count": 1,
                "total_count": 1,
            },
            "content_validation": {
                "status": "passed",
                "sampled_content_evidence": {
                    "path": "validation/zh-cn/fixture.sampled-content.json",
                    "artifact_sha256": _sha("sampled-artifact"),
                    "evidence_sha256": _sha("sampled-evidence"),
                },
                "coverage": coverage,
                "claim": "sampled_state_content_consistency",
            },
            "source_quality_findings": classified,
            "approval_preconditions": {
                "machine": machine_approval_preconditions(
                    "succeeded",
                    "passed",
                ).to_dict(),
                "source": evaluate_source_findings(
                    classified,
                    finding_policy,
                ).to_dict(),
            },
            "errors": [],
            "warnings": [],
        },
    }
    validation["evidence_sha256"] = validation_evidence_sha256(validation)
    return validation


def test_successor_profile_is_active_and_legacy_p3_remains_explicit() -> None:
    registry = ValidationContextRegistry(ROOT)

    active = registry.freeze()
    legacy = registry.freeze(validation_profile_id="v0.4-validation-p3")
    successor = registry.freeze(validation_profile_id="v0.4-validation-p3-successor")

    assert active["validation_context"]["validation_profile"]["id"] == (
        "v0.4-validation-p3-successor"
    )
    assert legacy["validation_context"]["validation_profile"]["id"] == (
        "v0.4-validation-p3"
    )
    assert successor["validation_context"]["validation_profile"]["id"] == (
        "v0.4-validation-p3-successor"
    )
    registry.verify_frozen(successor["planning"], successor["validation_context"])


def test_finding_policy_classifies_advisory_blocking_and_unknown_codes() -> None:
    findings = [
        _finding("SOURCE_CHARSET_DECLARATION_NOT_UTF8"),
        _finding("source_confirmed_empty_state"),
        _finding("NEW_UNREVIEWED_CODE"),
    ]

    classified = classify_source_quality_findings(findings, _policy())
    result = evaluate_source_findings(classified, _policy())

    assert [finding["classification"] for finding in classified] == [
        "advisory",
        "approval_blocking",
        "unknown",
    ]
    assert [blocker.code for blocker in result.blockers] == [
        "approval_blocking_source_quality_finding",
        "unknown_source_quality_finding_code",
    ]


def test_legacy_blanket_source_rule_remains_unchanged() -> None:
    legacy = source_approval_preconditions([
        _finding("SOURCE_CHARSET_DECLARATION_NOT_UTF8")
    ])

    assert legacy.to_dict()["blockers"][0]["code"] == (
        "unresolved_source_quality_finding"
    )


def test_finding_policy_identity_matrix_is_closed_world() -> None:
    assert (
        resolve_finding_policy(
            validation_schema_version="2.0",
            validation_profile_identity=LEGACY_P3_PROFILE_IDENTITY,
            finding_code_policy_identity=None,
        )
        == LEGACY_FINDING_POLICY_ID
    )
    assert (
        resolve_finding_policy(
            validation_schema_version="2.1",
            validation_profile_identity=SUCCESSOR_P3_PROFILE_IDENTITY,
            finding_code_policy_identity=FINDING_CODE_POLICY_IDENTITY,
        )
        == "v0.4-finding-code-policy-p4"
    )

    illegal_pairs = (
        ("2.0", LEGACY_P3_PROFILE_IDENTITY, FINDING_CODE_POLICY_IDENTITY),
        ("2.1", LEGACY_P3_PROFILE_IDENTITY, None),
        ("2.0", SUCCESSOR_P3_PROFILE_IDENTITY, FINDING_CODE_POLICY_IDENTITY),
        ("2.1", SUCCESSOR_P3_PROFILE_IDENTITY, None),
        ("2.1", {**SUCCESSOR_P3_PROFILE_IDENTITY, "sha256": _sha("bad")}, FINDING_CODE_POLICY_IDENTITY),
    )
    for version, profile, policy in illegal_pairs:
        with pytest.raises(ReviewContractError) as caught:
            resolve_finding_policy(
                validation_schema_version=version,
                validation_profile_identity=profile,
                finding_code_policy_identity=policy,
            )
        assert caught.value.code == "finding_policy_identity_invalid"


def test_state_store_accepts_validation_21_with_advisory_findings() -> None:
    validation = _validation_21([
        _finding("SOURCE_CHARSET_DECLARATION_NOT_UTF8")
    ])

    StateStore(ROOT).validate_document(validation, "validation")

    assert validation["evidence"]["approval_preconditions"]["source"] == {
        "eligible": True,
        "blockers": [],
    }


def test_state_store_replays_validation_21_blocking_and_unknown_findings() -> None:
    validation = _validation_21([
        _finding("source_confirmed_empty_state"),
        _finding("NEW_UNREVIEWED_CODE"),
    ])

    StateStore(ROOT).validate_document(validation, "validation")

    assert [
        blocker["code"]
        for blocker in validation["evidence"]["approval_preconditions"]["source"][
            "blockers"
        ]
    ] == [
        "approval_blocking_source_quality_finding",
        "unknown_source_quality_finding_code",
    ]


def test_state_store_rejects_noncanonical_validation_21_classification() -> None:
    validation = _validation_21([
        _finding("SOURCE_CHARSET_DECLARATION_NOT_UTF8")
    ])
    drifted = copy.deepcopy(validation)
    drifted["evidence"]["source_quality_findings"][0]["classification"] = (
        "approval_blocking"
    )
    drifted["evidence_sha256"] = validation_evidence_sha256(drifted)

    with pytest.raises(
        ManifestValidationError,
        match="Source Quality Finding classifications are not canonical",
    ):
        StateStore(ROOT).validate_document(drifted, "validation")
