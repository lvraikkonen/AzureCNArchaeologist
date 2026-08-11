"""Closed-world contract tests for v0.4 Step 4 Slice A."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

import scripts.build_v04_p3_validation_profile as profile_builder
from src.core.canonical_identity import (
    derive_sampling_seed,
    derive_state_id,
    derive_universe_id,
    document_identity_sha256,
    sampled_content_evidence_sha256,
    sampling_plan_sha256,
    validation_evidence_sha256,
)
from src.core.product_catalog import sha256_file
from src.core.validation_context import ValidationContextError
from src.pipeline.state_store import ManifestValidationError, StateStore
from src.release.contracts import derive_publication_receipt_id
from src.review.contracts import source_approval_preconditions


ROOT = Path(__file__).resolve().parents[1]
BATCH_ID = "20260803T120000Z-deadbeef"

SCHEMA_PATHS = {
    "content_sampling_profile": (
        "schemas/content-sampling-profile-1.0.schema.json"
    ),
    "sampling_plan": "schemas/batch-item-sampling-plan-1.0.schema.json",
    "sampled_evidence": "schemas/sampled-content-evidence-1.0.schema.json",
    "validation": "schemas/pipeline-validation-2.0.schema.json",
    "review": "schemas/review-decision-1.0.schema.json",
    "release": "schemas/release-manifest-1.0.schema.json",
    "release_11": "schemas/release-manifest-1.1.schema.json",
    "publication_receipt": "schemas/publication-receipt-1.0.schema.json",
    "validation_profile": "schemas/validation-profile-1.2.schema.json",
}


def _read_json(relative_path: str) -> dict[str, Any]:
    value = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _validator(name: str) -> Draft202012Validator:
    schema = _read_json(SCHEMA_PATHS[name])
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _artifact(label: str) -> dict[str, str]:
    return {
        "path": f"evidence/{label}.json",
        "sha256": _sha(label),
    }


def _sampling_profile_identity() -> dict[str, str]:
    return {
        "id": "v0.4-content-sampling-p3",
        "schema_version": "1.0",
        "path": "data/configs/content-sampling-profiles/v0.4-p3.json",
        "sha256": sha256_file(
            ROOT / "data/configs/content-sampling-profiles/v0.4-p3.json"
        ),
    }


def _validation_profile_identity() -> dict[str, str]:
    return {
        "id": "v0.4-validation-p3",
        "schema_version": "1.2",
        "path": "data/configs/validation-profiles/v0.4-p3.json",
        "sha256": sha256_file(
            ROOT / "data/configs/validation-profiles/v0.4-p3.json"
        ),
    }


def _successor_validation_profile_identity() -> dict[str, str]:
    return {
        "id": "v0.4-validation-p3-successor",
        "schema_version": "1.3",
        "path": "data/configs/validation-profiles/v0.4-p3-successor.json",
        "sha256": sha256_file(
            ROOT / "data/configs/validation-profiles/v0.4-p3-successor.json"
        ),
    }


def _finding_code_policy_identity() -> dict[str, str]:
    return {
        "id": "v0.4-finding-code-policy-p4",
        "schema_version": "1.0",
        "path": "data/configs/finding-code-policies/v0.4-p4.json",
        "sha256": sha256_file(
            ROOT / "data/configs/finding-code-policies/v0.4-p4.json"
        ),
    }


def _state() -> dict[str, Any]:
    criteria = [["region", "china-east"]]
    return {"state_id": derive_state_id(criteria), "criteria": criteria}


def _coverage(*, mode: str = "stratified_sample") -> dict[str, Any]:
    return {
        "mode": mode,
        "universe_count": 13 if mode == "stratified_sample" else 1,
        "selected_count": 1,
        "untested_count": 12 if mode == "stratified_sample" else 0,
        "seed": _sha("seed") if mode == "stratified_sample" else None,
        "strata": [_sha("east-stratum")] if mode == "stratified_sample" else [],
        "selected_state_ids": (
            [_state()["state_id"]] if mode == "stratified_sample" else []
        ),
        "assurance": "sampled_state_content_consistency",
    }


def _bindings(*, with_plan: bool = True) -> dict[str, Any]:
    return {
        "source": _artifact("source"),
        "normalized_input": _artifact("normalized"),
        "payload": _artifact("payload"),
        "soft_category": _artifact("soft-category"),
        "validation_profile": _validation_profile_identity(),
        "content_sampling_profile": _sampling_profile_identity(),
        "sampling_plan": (
            {
                "path": "validation/zh-cn/pricing/api-management.sampling-plan.json",
                "artifact_sha256": _sha("plan-artifact"),
                "plan_sha256": _sha("plan-semantic"),
            }
            if with_plan
            else None
        ),
    }


def _sampling_plan() -> dict[str, Any]:
    state = _state()
    profile = _sampling_profile_identity()
    return {
        "schema_version": "1.0",
        "plan_sha256": _sha("plan-semantic"),
        "item_id": "zh-cn/api-management",
        "strategy": "region_filter",
        "source_sha256": _sha("source"),
        "content_sampling_profile": profile,
        "algorithm_version": "source-ordered-stratified-sampling-v1",
        "state_universe": {
            "universe_id": derive_universe_id(
                [state["state_id"]], state["state_id"]
            ),
            "default_state_id": state["state_id"],
            "states": [state],
        },
        "strata": [
            {
                "stratum_id": _sha("east-stratum"),
                "kind": "source_proven_region",
                "criteria": [["region", "china-east"]],
                "state_ids": [state["state_id"]],
            }
        ],
        "seed": derive_sampling_seed(
            algorithm_version="source-ordered-stratified-sampling-v1",
            source_sha256=_sha("source"),
            item_id="zh-cn/api-management",
            profile_sha256=profile["sha256"],
        ),
        "target_budget": 12,
        "effective_budget": 12,
        "selected_states": [state],
        "coverage": {
            "mode": "stratified_sample",
            "universe_count": 1,
            "selected_count": 1,
            "untested_count": 0,
            "assurance": "sampled_state_content_consistency",
        },
    }


def _matched_comparison() -> dict[str, Any]:
    return {
        "status": "matched",
        "source_fingerprint": _sha("content"),
        "payload_fingerprint": _sha("content"),
        "diff_reference": None,
    }


def _sampled_evidence() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "evidence_sha256": _sha("sampled-evidence"),
        "item_id": "zh-cn/api-management",
        "mode": "stratified_sample",
        "bindings": _bindings(),
        "coverage": _coverage(),
        "structure_validation": {
            "status": "passed",
            "universe_count": 13,
            "checked_count": 13,
            "errors": [],
        },
        "page_global_comparison": _matched_comparison(),
        "full_content_comparison": None,
        "samples": [
            {
                "state": _state(),
                "source_fingerprint": _sha("state-content"),
                "payload_fingerprint": _sha("state-content"),
                "status": "matched",
                "diff_reference": None,
            }
        ],
        "errors": [],
        "warnings": [],
    }


def _validation() -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "batch_id": BATCH_ID,
        "item_id": "zh-cn/api-management",
        "status": "passed",
        "evidence_sha256": _sha("validation-evidence"),
        "evidence": {
            "verdict": "passed",
            "bindings": _bindings(),
            "structure_validation": {
                "status": "passed",
                "checked_count": 13,
                "total_count": 13,
            },
            "content_validation": {
                "status": "passed",
                "sampled_content_evidence": {
                    "path": (
                        "validation/zh-cn/pricing/"
                        "api-management.sampled-content-evidence.json"
                    ),
                    "artifact_sha256": _sha("sampled-evidence-artifact"),
                    "evidence_sha256": _sha("sampled-evidence"),
                },
                "coverage": _coverage(),
                "claim": "sampled_state_content_consistency",
            },
            "source_quality_findings": [],
            "approval_preconditions": {
                "machine": {"eligible": True, "blockers": []},
                "source": {"eligible": True, "blockers": []},
            },
            "errors": [],
            "warnings": [],
        },
    }


def _review_decision() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "decision_id": _sha("decision"),
        "batch_id": BATCH_ID,
        "item_id": "zh-cn/api-management",
        "resource_key": "api-management",
        "language": "zh-cn",
        "reviewer": "reviewer@example.com",
        "decided_at": "2026-08-03T12:30:00Z",
        "verdict": "approved",
        "reason": None,
        "notes": "Source and persisted payload inspected.",
        "bindings": {
            "source_sha256": _sha("source"),
            "payload_sha256": _sha("payload"),
            "validation_artifact_sha256": _sha("validation-artifact"),
            "validation_evidence_sha256": _sha("validation-evidence"),
            "sampling_plan_sha256": _sha("plan-artifact"),
        },
        "inspected_states": [
            {"scope": "interactive_state", "state_id": _state()["state_id"]},
            {"scope": "page_global"},
        ],
        "supersedes_decision_id": None,
    }


def _release_manifest() -> dict[str, Any]:
    validation_profile = _validation_profile_identity()
    sampling_profile = _sampling_profile_identity()
    return {
        "schema_version": "1.0",
        "release_id": "release-20260803-01",
        "created_at": "2026-08-03T13:00:00Z",
        "batch_id": BATCH_ID,
        "batch_manifest": _artifact("batch-manifest"),
        "input_manifest": _artifact("input-manifest"),
        "validation_profile": validation_profile,
        "content_sampling_profile": sampling_profile,
        "target": {
            "account_url": "https://example.blob.core.chinacloudapi.cn",
            "container": "cms",
            "prefix": "releases/release-20260803-01",
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
                    "source_path": (
                        "runs/20260803T120000Z-deadbeef/outputs/zh-cn/"
                        "pricing/api-management.json"
                    ),
                    "release_path": (
                        "payloads/zh-cn/pricing/api-management.json"
                    ),
                    "sha256": _sha("payload"),
                },
                "validation_path": (
                    "runs/20260803T120000Z-deadbeef/validation/zh-cn/"
                    "pricing/api-management.validation.json"
                ),
                "review_decision_path": (
                    "runs/20260803T120000Z-deadbeef/review/decisions/"
                    "decision.json"
                ),
                "review_decision_id": _sha("decision"),
                "bindings": {
                    "payload_sha256": _sha("payload"),
                    "validation_artifact_sha256": _sha(
                        "validation-artifact"
                    ),
                    "validation_evidence_sha256": _sha(
                        "validation-evidence"
                    ),
                    "review_decision_sha256": _sha("review-artifact"),
                    "validation_profile_sha256": validation_profile["sha256"],
                    "sampling_plan_sha256": _sha("plan-artifact"),
                },
                "coverage": {
                    "mode": "stratified_sample",
                    "universe_count": 13,
                    "selected_count": 1,
                    "untested_count": 12,
                },
                "target_blob": {
                    "container": "cms",
                    "name": (
                        "releases/release-20260803-01/zh-cn/pricing/"
                        "api-management.json"
                    ),
                },
            }
        ],
    }


def _release_manifest_11() -> dict[str, Any]:
    manifest = _release_manifest()
    validation_profile = _successor_validation_profile_identity()
    manifest["schema_version"] = "1.1"
    manifest["validation_profile"] = validation_profile
    manifest["finding_code_policy_identity"] = _finding_code_policy_identity()
    manifest["items"][0]["bindings"]["validation_profile_sha256"] = (
        validation_profile["sha256"]
    )
    return manifest


def _publication_receipt() -> dict[str, Any]:
    receipt = {
        "schema_version": "1.0",
        "receipt_id": _sha("receipt"),
        "published_at": "2026-08-03T13:30:00Z",
        "batch_id": BATCH_ID,
        "release_id": "release-20260803-01",
        "release_manifest": _artifact("release-manifest"),
        "release_seal": _sha("release-seal"),
        "target": {
            "account_url": "https://example.blob.core.chinacloudapi.cn",
            "container": "cms",
            "prefix": "releases/release-20260803-01",
        },
        "items": [
            {
                "item_id": "zh-cn/api-management",
                "resource_key": "api-management",
                "language": "zh-cn",
                "payload": {
                    "release_path": (
                        "output/releases/release-20260803-01/payloads/"
                        "zh-cn/pricing/api-management.json"
                    ),
                    "sha256": _sha("payload"),
                },
                "target_blob": {
                    "container": "cms",
                    "name": (
                        "releases/release-20260803-01/zh-cn/pricing/"
                        "api-management.json"
                    ),
                },
                "remote": {
                    "account_url": "https://example.blob.core.chinacloudapi.cn",
                    "container": "cms",
                    "name": (
                        "releases/release-20260803-01/zh-cn/pricing/"
                        "api-management.json"
                    ),
                    "sha256": _sha("payload"),
                    "content_length": 123,
                    "etag": "0xABC",
                },
            }
        ],
    }
    receipt["receipt_id"] = derive_publication_receipt_id(receipt)
    return receipt


def _documents() -> dict[str, dict[str, Any]]:
    return {
        "content_sampling_profile": _read_json(
            "data/configs/content-sampling-profiles/v0.4-p3.json"
        ),
        "sampling_plan": _sampling_plan(),
        "sampled_evidence": _sampled_evidence(),
        "validation": _validation(),
        "review": _review_decision(),
        "release": _release_manifest(),
        "release_11": _release_manifest_11(),
        "publication_receipt": _publication_receipt(),
        "validation_profile": _read_json(
            "data/configs/validation-profiles/v0.4-p3.json"
        ),
    }


@pytest.mark.parametrize("name", tuple(SCHEMA_PATHS))
def test_step4_contract_accepts_reviewed_document(name: str) -> None:
    _validator(name).validate(_documents()[name])


@pytest.mark.parametrize("name", tuple(SCHEMA_PATHS))
def test_step4_contract_rejects_unknown_root_field(name: str) -> None:
    document = copy.deepcopy(_documents()[name])
    document["unexpected"] = True
    with pytest.raises(Exception, match="Additional properties"):
        _validator(name).validate(document)


@pytest.mark.parametrize("name", tuple(SCHEMA_PATHS))
def test_step4_contract_rejects_missing_required_field(name: str) -> None:
    document = copy.deepcopy(_documents()[name])
    document.pop(next(iter(document)))
    with pytest.raises(Exception, match="required property"):
        _validator(name).validate(document)


@pytest.mark.parametrize(
    ("name", "path"),
    (
        ("content_sampling_profile", ("selection_policy",)),
        ("sampling_plan", ("state_universe",)),
        ("sampled_evidence", ("bindings",)),
        ("validation", ("evidence", "approval_preconditions")),
        ("review", ("bindings",)),
        ("release", ("items", 0, "bindings")),
        ("publication_receipt", ("items", 0, "remote")),
        ("validation_profile", ("content_sampling_profile",)),
    ),
)
def test_step4_contract_rejects_unknown_nested_field(
    name: str,
    path: tuple[str | int, ...],
) -> None:
    document: Any = copy.deepcopy(_documents()[name])
    for part in path:
        document = document[part]
    document["unexpected"] = True
    with pytest.raises(Exception, match="Additional properties"):
        _validator(name).validate(_documents_with_replacement(name, path, document))


def _documents_with_replacement(
    name: str,
    path: tuple[str | int, ...],
    replacement: Any,
) -> dict[str, Any]:
    document = copy.deepcopy(_documents()[name])
    cursor: Any = document
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = replacement
    return document


@pytest.mark.parametrize(
    ("name", "path"),
    (
        ("sampling_plan", ("plan_sha256",)),
        ("sampled_evidence", ("evidence_sha256",)),
        ("validation", ("evidence_sha256",)),
        ("review", ("decision_id",)),
        ("release", ("items", 0, "bindings", "payload_sha256")),
        ("publication_receipt", ("release_seal",)),
    ),
)
def test_step4_contract_rejects_noncanonical_sha256(
    name: str,
    path: tuple[str | int, ...],
) -> None:
    with pytest.raises(Exception, match="does not match"):
        _validator(name).validate(
            _documents_with_replacement(name, path, "A" * 64)
        )


@pytest.mark.parametrize(
    ("name", "path", "value"),
    (
        ("sampled_evidence", ("bindings", "source", "path"), "../source"),
        ("validation", ("evidence", "bindings", "payload", "path"), "/tmp/payload"),
        ("release", ("items", 0, "payload", "release_path"), "../../payload"),
        ("publication_receipt", ("items", 0, "payload", "release_path"), "../payload"),
    ),
)
def test_step4_contract_rejects_unsafe_relative_path(
    name: str,
    path: tuple[str | int, ...],
    value: str,
) -> None:
    with pytest.raises(Exception):
        _validator(name).validate(
            _documents_with_replacement(name, path, value)
        )


def test_content_sampling_profile_freezes_adaptive_twelve_rules() -> None:
    profile = _documents()["content_sampling_profile"]
    assert profile["target_budget"] == 12
    assert profile["mandatory_anchors"] == ["default_state"]
    assert profile["strategy_rules"]["complex"] == {
        "coverage_mode": "stratified_sample",
        "sampling_plan": "required",
        "stratum_dimension": "actual_parent_branch",
        "parent_branch_definition": (
            "ordered_criteria_prefix_excluding_leaf"
        ),
        "minimum_per_stratum": 1,
        "cartesian_expansion": "forbidden",
    }
    assert profile["selection_policy"] == {
        "small_universe": "select_all_when_universe_lte_effective_budget",
        "forced_coverage_over_budget": "expand_effective_budget",
        "first_pass": "one_per_stratum_by_seed_state_hash",
        "stratum_order": "source_first_appearance",
        "within_stratum_rank": (
            "sha256-canonical-json-array-seed-state-id"
        ),
        "remainder": "stable_stratum_round_robin",
        "output_order": "source_order",
    }
    assert profile["seed_derivation"]["ordered_inputs"] == [
        "algorithm_version",
        "source_sha256",
        "item_id",
        "profile_sha256",
    ]
    assert "payload_sha256" in profile["seed_derivation"]["excluded_inputs"]
    assert profile["comparison_policy"]["replacement_draw"] == "forbidden"


@pytest.mark.parametrize(
    ("strategy", "wrong_kind"),
    (
        ("region_filter", "actual_parent_branch"),
        ("complex", "source_proven_region"),
    ),
)
def test_sampling_plan_strategy_rejects_wrong_stratum_kind(
    strategy: str,
    wrong_kind: str,
) -> None:
    document = _sampling_plan()
    document["strategy"] = strategy
    document["strata"][0]["kind"] = wrong_kind
    with pytest.raises(Exception):
        _validator("sampling_plan").validate(document)


def test_sampling_plan_uses_stratified_mode_when_every_state_is_selected() -> None:
    document = _sampling_plan()
    assert document["coverage"] == {
        "mode": "stratified_sample",
        "universe_count": 1,
        "selected_count": 1,
        "untested_count": 0,
        "assurance": "sampled_state_content_consistency",
    }
    _validator("sampling_plan").validate(document)

    document["coverage"]["mode"] = "full"
    with pytest.raises(Exception):
        _validator("sampling_plan").validate(document)


def test_full_mode_evidence_requires_no_sampling_plan_or_states() -> None:
    document = _sampled_evidence()
    document["mode"] = "full"
    document["bindings"] = _bindings(with_plan=False)
    document["coverage"] = _coverage(mode="full")
    document["full_content_comparison"] = _matched_comparison()
    document["samples"] = []
    _validator("sampled_evidence").validate(document)

    document["bindings"]["sampling_plan"] = {
        "path": "evidence/plan.json",
        "artifact_sha256": _sha("plan-artifact"),
        "plan_sha256": _sha("plan-semantic"),
    }
    with pytest.raises(Exception):
        _validator("sampled_evidence").validate(document)


def test_full_mode_evidence_forbids_untested_content() -> None:
    document = _sampled_evidence()
    document["mode"] = "full"
    document["bindings"] = _bindings(with_plan=False)
    document["coverage"] = _coverage(mode="full")
    document["coverage"].update({
        "universe_count": 20,
        "selected_count": 1,
        "untested_count": 19,
    })
    document["structure_validation"].update({
        "universe_count": 20,
        "checked_count": 20,
    })
    document["full_content_comparison"] = _matched_comparison()
    document["samples"] = []
    with pytest.raises(Exception):
        _validator("sampled_evidence").validate(document)


def test_sampled_evidence_mode_must_match_coverage_mode() -> None:
    document = _sampled_evidence()
    document["coverage"]["mode"] = "full"
    with pytest.raises(Exception):
        _validator("sampled_evidence").validate(document)


def test_full_mode_cannot_retain_any_stratified_evidence_fields() -> None:
    document = _sampled_evidence()
    document["mode"] = "full"
    document["coverage"]["mode"] = "full"
    assert document["bindings"]["sampling_plan"] is not None
    assert document["coverage"]["seed"] is not None
    assert document["coverage"]["strata"]
    assert document["coverage"]["selected_state_ids"]
    assert document["full_content_comparison"] is None
    assert document["samples"]
    with pytest.raises(Exception):
        _validator("sampled_evidence").validate(document)


@pytest.mark.parametrize("field", ("source_fingerprint", "payload_fingerprint"))
def test_matched_sample_requires_both_fingerprints(field: str) -> None:
    document = _sampled_evidence()
    document["samples"][0][field] = None
    with pytest.raises(Exception):
        _validator("sampled_evidence").validate(document)


def test_stratified_evidence_requires_page_global_comparison() -> None:
    document = _sampled_evidence()
    document["page_global_comparison"] = {
        "status": "not_applicable",
        "source_fingerprint": None,
        "payload_fingerprint": None,
        "diff_reference": None,
    }
    with pytest.raises(Exception):
        _validator("sampled_evidence").validate(document)


def test_page_global_mismatch_requires_fingerprints_and_diff_artifact() -> None:
    document = _sampled_evidence()
    document["page_global_comparison"] = {
        "status": "mismatched",
        "source_fingerprint": _sha("source-page-global"),
        "payload_fingerprint": _sha("payload-page-global"),
        "diff_reference": _artifact("page-global-diff"),
    }
    _validator("sampled_evidence").validate(document)

    document["page_global_comparison"]["diff_reference"] = None
    with pytest.raises(Exception):
        _validator("sampled_evidence").validate(document)


def test_validation_20_has_time_free_semantic_evidence_and_preconditions() -> None:
    document = _validation()
    assert set(document) == {
        "schema_version",
        "batch_id",
        "item_id",
        "status",
        "evidence_sha256",
        "evidence",
    }
    assert set(document["evidence"]["approval_preconditions"]) == {
        "machine",
        "source",
    }
    document["validated_at"] = "2026-08-03T12:30:00Z"
    with pytest.raises(Exception, match="Additional properties"):
        _validator("validation").validate(document)


def test_state_store_accepts_validation_1_and_2_without_upgrading_1() -> None:
    store = StateStore(ROOT)
    validation_1 = {
        "schema_version": "1.0",
        "batch_id": BATCH_ID,
        "item_id": "zh-cn/api-management",
        "validated_at": "2026-08-03T12:30:00Z",
        "status": "passed",
        "errors": [],
        "warnings": [],
    }
    original = copy.deepcopy(validation_1)
    store.validate_document(validation_1, "validation")
    assert validation_1 == original

    validation_2 = _validation()
    validation_2["evidence_sha256"] = validation_evidence_sha256(validation_2)
    store.validate_document(validation_2, "validation")


def test_state_store_reads_both_validation_versions_read_only(
    tmp_path: Path,
) -> None:
    store = StateStore(ROOT, runs_dir=tmp_path / "runs")
    validation_1 = {
        "schema_version": "1.0",
        "batch_id": BATCH_ID,
        "item_id": "zh-cn/legacy",
        "validated_at": "2026-08-03T12:30:00Z",
        "status": "passed",
        "errors": [],
        "warnings": [],
    }
    validation_2 = _validation()
    validation_2["evidence_sha256"] = validation_evidence_sha256(validation_2)

    for name, document in (
        ("legacy.validation.json", validation_1),
        ("p3.validation.json", validation_2),
    ):
        relative = Path("validation/zh-cn/pricing") / name
        path = store.run_dir(BATCH_ID) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        assert store.read_projection(
            BATCH_ID,
            "validation",
            relative_path=relative,
        ) == document


def test_warm_projection_cache_replays_p3_profile_bindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = StateStore(ROOT, runs_dir=tmp_path / "runs")
    document = _validation()
    document["evidence_sha256"] = validation_evidence_sha256(document)
    relative = Path("validation/zh-cn/pricing/p3.validation.json")
    path = store.run_dir(BATCH_ID) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    store.read_projection(BATCH_ID, "validation", relative_path=relative)

    def drifted_profile(*args: object, **kwargs: object) -> dict[str, Any]:
        raise ValidationContextError("P3 profile SHA-256 drifted")

    monkeypatch.setattr(
        store._validation_context,
        "document_for_identity",
        drifted_profile,
    )
    with pytest.raises(ManifestValidationError, match="P3 profile.*drifted"):
        store.read_projection(BATCH_ID, "validation", relative_path=relative)


def test_state_store_replays_p3_profile_hashes_and_self_identities() -> None:
    store = StateStore(ROOT)
    plan = _sampling_plan()
    plan["plan_sha256"] = sampling_plan_sha256(plan)
    store.validate_document(plan, "sampling_plan")

    changed = copy.deepcopy(plan)
    changed["source_sha256"] = _sha("changed-source")
    with pytest.raises(ManifestValidationError, match="canonical body"):
        store.validate_document(changed, "sampling_plan")

    evidence = _sampled_evidence()
    evidence["evidence_sha256"] = sampled_content_evidence_sha256(evidence)
    store.validate_document(evidence, "sampled_content_evidence")
    evidence["bindings"]["validation_profile"]["sha256"] = "0" * 64
    evidence["evidence_sha256"] = sampled_content_evidence_sha256(evidence)
    with pytest.raises(ManifestValidationError, match="SHA-256 drifted"):
        store.validate_document(evidence, "sampled_content_evidence")


@pytest.mark.parametrize(
    ("field", "message"),
    (
        ("state", "state_id does not match"),
        ("universe", "universe_id does not match"),
        ("seed", "seed does not match"),
        ("coverage", "universe_count must equal"),
    ),
)
def test_sampling_plan_replays_derived_identities_and_counts(
    field: str,
    message: str,
) -> None:
    plan = _sampling_plan()
    if field == "state":
        plan["state_universe"]["states"][0]["state_id"] = _sha("forged")
    elif field == "universe":
        plan["state_universe"]["universe_id"] = _sha("forged")
    elif field == "seed":
        plan["seed"] = _sha("forged")
    else:
        plan["coverage"]["universe_count"] = 99
    plan["plan_sha256"] = sampling_plan_sha256(plan)

    with pytest.raises(ManifestValidationError, match=message):
        StateStore(ROOT).validate_document(plan, "sampling_plan")


def _two_state_sampling_plan(*, reverse_selection: bool = False) -> dict[str, Any]:
    plan = _sampling_plan()
    west = {
        "criteria": [["region", "china-west"]],
    }
    west["state_id"] = derive_state_id(west["criteria"])
    states = [plan["state_universe"]["states"][0], west]
    plan["state_universe"]["states"] = states
    plan["state_universe"]["universe_id"] = derive_universe_id(
        [state["state_id"] for state in states],
        plan["state_universe"]["default_state_id"],
    )
    plan["strata"][0]["state_ids"] = [
        state["state_id"] for state in states
    ]
    plan["selected_states"] = list(reversed(states)) if reverse_selection else [west]
    plan["coverage"].update({
        "universe_count": 2,
        "selected_count": len(plan["selected_states"]),
        "untested_count": 2 - len(plan["selected_states"]),
    })
    plan["plan_sha256"] = sampling_plan_sha256(plan)
    return plan


def test_sampling_plan_requires_default_anchor_and_source_order() -> None:
    without_default = _two_state_sampling_plan()
    with pytest.raises(ManifestValidationError, match="default state"):
        StateStore(ROOT).validate_document(without_default, "sampling_plan")

    reversed_selection = _two_state_sampling_plan(reverse_selection=True)
    with pytest.raises(ManifestValidationError, match="Source order"):
        StateStore(ROOT).validate_document(reversed_selection, "sampling_plan")


def test_sampling_plan_effective_budget_cannot_drop_below_twelve() -> None:
    plan = _sampling_plan()
    plan["effective_budget"] = 11
    with pytest.raises(Exception):
        _validator("sampling_plan").validate(plan)


def _thirteen_region_strata_plan() -> dict[str, Any]:
    plan = _sampling_plan()
    states = []
    strata = []
    for index in range(13):
        criteria = [["region", f"china-region-{index:02d}"]]
        state = {
            "state_id": derive_state_id(criteria),
            "criteria": criteria,
        }
        states.append(state)
        strata.append({
            "stratum_id": _sha(f"region-stratum-{index:02d}"),
            "kind": "source_proven_region",
            "criteria": criteria,
            "state_ids": [state["state_id"]],
        })
    plan["state_universe"] = {
        "universe_id": derive_universe_id(
            [state["state_id"] for state in states],
            states[0]["state_id"],
        ),
        "default_state_id": states[0]["state_id"],
        "states": states,
    }
    plan["strata"] = strata
    plan["selected_states"] = states[:12]
    plan["coverage"].update({
        "universe_count": 13,
        "selected_count": 12,
        "untested_count": 1,
    })
    plan["plan_sha256"] = sampling_plan_sha256(plan)
    return plan


def test_forced_strata_coverage_expands_effective_budget_over_twelve() -> None:
    plan = _thirteen_region_strata_plan()
    with pytest.raises(ManifestValidationError, match=r"strata\[12\]"):
        StateStore(ROOT).validate_document(plan, "sampling_plan")

    plan["effective_budget"] = 13
    plan["selected_states"] = plan["state_universe"]["states"]
    plan["coverage"].update({
        "selected_count": 13,
        "untested_count": 0,
    })
    plan["plan_sha256"] = sampling_plan_sha256(plan)
    StateStore(ROOT).validate_document(plan, "sampling_plan")


def test_sampling_strata_are_a_source_ordered_strategy_partition() -> None:
    plan = _thirteen_region_strata_plan()
    plan["strata"][1]["state_ids"].append(
        plan["state_universe"]["default_state_id"]
    )
    plan["plan_sha256"] = sampling_plan_sha256(plan)
    with pytest.raises(
        ManifestValidationError,
        match="state_ids.*Source order|source-proven region|partition",
    ):
        StateStore(ROOT).validate_document(plan, "sampling_plan")

    plan = _thirteen_region_strata_plan()
    plan["effective_budget"] = 13
    plan["selected_states"] = plan["state_universe"]["states"]
    plan["coverage"].update({
        "selected_count": 13,
        "untested_count": 0,
    })
    plan["strata"][0], plan["strata"][1] = (
        plan["strata"][1],
        plan["strata"][0],
    )
    plan["plan_sha256"] = sampling_plan_sha256(plan)
    with pytest.raises(ManifestValidationError, match="first-appearance"):
        StateStore(ROOT).validate_document(plan, "sampling_plan")

    plan = _sampling_plan()
    states = []
    for tier in ("basic", "premium"):
        criteria = [["region", "china-east"], ["tier", tier]]
        states.append({
            "state_id": derive_state_id(criteria),
            "criteria": criteria,
        })
    plan["state_universe"] = {
        "universe_id": derive_universe_id(
            [state["state_id"] for state in states],
            states[0]["state_id"],
        ),
        "default_state_id": states[0]["state_id"],
        "states": states,
    }
    plan["strata"][0]["criteria"] = [["region", "china-east"]]
    plan["strata"][0]["state_ids"] = [
        state["state_id"] for state in reversed(states)
    ]
    plan["selected_states"] = states
    plan["coverage"].update({
        "universe_count": 2,
        "selected_count": 2,
        "untested_count": 0,
    })
    plan["plan_sha256"] = sampling_plan_sha256(plan)
    with pytest.raises(ManifestValidationError, match="state_ids.*Source order"):
        StateStore(ROOT).validate_document(plan, "sampling_plan")


def test_complex_strata_bind_exact_criteria_parent_prefix() -> None:
    plan = _sampling_plan()
    criteria = [["region", "china-east"], ["tier", "basic"]]
    state = {"state_id": derive_state_id(criteria), "criteria": criteria}
    plan["strategy"] = "complex"
    plan["state_universe"] = {
        "universe_id": derive_universe_id(
            [state["state_id"]], state["state_id"]
        ),
        "default_state_id": state["state_id"],
        "states": [state],
    }
    plan["strata"] = [{
        "stratum_id": _sha("complex-parent"),
        "kind": "actual_parent_branch",
        "criteria": criteria[:-1],
        "state_ids": [state["state_id"]],
    }]
    plan["selected_states"] = [state]
    plan["plan_sha256"] = sampling_plan_sha256(plan)
    StateStore(ROOT).validate_document(plan, "sampling_plan")

    plan["strata"][0]["criteria"] = [["region", "china-north"]]
    plan["plan_sha256"] = sampling_plan_sha256(plan)
    with pytest.raises(ManifestValidationError, match=r"criteria\[:-1\]"):
        StateStore(ROOT).validate_document(plan, "sampling_plan")


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("coverage", "universe_count must equal"),
        ("selected_ids", "selected_count must equal"),
        ("structure", "every reachable state checked"),
        ("fingerprint", "identical fingerprints"),
        ("sample_id", "samples must exactly follow"),
    ),
)
def test_sampled_evidence_replays_coverage_structure_and_comparisons(
    mutation: str,
    message: str,
) -> None:
    evidence = _sampled_evidence()
    if mutation == "coverage":
        evidence["coverage"]["universe_count"] = 99
    elif mutation == "selected_ids":
        evidence["coverage"].update({
            "universe_count": 14,
            "selected_count": 2,
        })
    elif mutation == "structure":
        evidence["structure_validation"]["checked_count"] = 0
    elif mutation == "fingerprint":
        evidence["page_global_comparison"]["payload_fingerprint"] = _sha(
            "different"
        )
    else:
        criteria = [["region", "china-west"]]
        evidence["samples"][0]["state"] = {
            "state_id": derive_state_id(criteria),
            "criteria": criteria,
        }
    evidence["evidence_sha256"] = sampled_content_evidence_sha256(evidence)

    with pytest.raises(ManifestValidationError, match=message):
        StateStore(ROOT).validate_document(
            evidence,
            "sampled_content_evidence",
        )


def test_sampled_evidence_structure_status_and_errors_are_consistent() -> None:
    evidence = _sampled_evidence()
    evidence["structure_validation"]["status"] = "failed"
    evidence["evidence_sha256"] = sampled_content_evidence_sha256(evidence)
    with pytest.raises(ManifestValidationError, match="requires at least one"):
        StateStore(ROOT).validate_document(
            evidence,
            "sampled_content_evidence",
        )


def test_validation_replays_coverage_and_complete_structure_scope() -> None:
    validation = _validation()
    validation["evidence"]["structure_validation"]["checked_count"] = 0
    validation["evidence_sha256"] = validation_evidence_sha256(validation)
    with pytest.raises(ManifestValidationError, match="every reachable state"):
        StateStore(ROOT).validate_document(validation, "validation")

    validation = _validation()
    validation["evidence"]["content_validation"]["coverage"][
        "universe_count"
    ] = 99
    validation["evidence_sha256"] = validation_evidence_sha256(validation)
    with pytest.raises(ManifestValidationError, match="universe_count must equal"):
        StateStore(ROOT).validate_document(validation, "validation")


def test_full_coverage_cannot_leave_untested_content() -> None:
    validation = _validation()
    bindings = validation["evidence"]["bindings"]
    coverage = validation["evidence"]["content_validation"]["coverage"]
    bindings["sampling_plan"] = None
    coverage.update({
        "mode": "full",
        "universe_count": 20,
        "selected_count": 1,
        "untested_count": 19,
        "seed": None,
        "strata": [],
        "selected_state_ids": [],
    })
    validation["evidence"]["structure_validation"].update({
        "checked_count": 20,
        "total_count": 20,
    })
    with pytest.raises(Exception):
        _validator("validation").validate(validation)

    coverage["untested_count"] = 0
    validation["evidence_sha256"] = validation_evidence_sha256(validation)
    with pytest.raises(ManifestValidationError, match="universe_count must equal"):
        StateStore(ROOT).validate_document(validation, "validation")


def test_review_decision_item_id_binds_language_and_resource() -> None:
    decision = _review_decision()
    decision["item_id"] = "en-us/other"
    decision["decision_id"] = document_identity_sha256(
        decision,
        "decision_id",
    )
    with pytest.raises(ManifestValidationError, match="language/resource_key"):
        StateStore(ROOT).validate_document(decision, "review_decision")


@pytest.mark.parametrize(
    ("language", "resource_key"),
    (
        ("en-us", "sla-sql-data--v1-5"),
        ("zh-cn", "sla-cdn--v1-1"),
    ),
)
def test_review_decision_accepts_historical_resource_key(
    language: str,
    resource_key: str,
) -> None:
    decision = _review_decision()
    decision.update({
        "item_id": f"{language}/{resource_key}",
        "resource_key": resource_key,
        "language": language,
    })
    decision["decision_id"] = document_identity_sha256(
        decision,
        "decision_id",
    )

    StateStore(ROOT).validate_document(decision, "review_decision")


@pytest.mark.parametrize(
    "resource_key",
    (
        "sla-sql-data--draft",
        "sla-sql-data--v1-",
        "sla-sql-data--v1-5--v2",
    ),
)
def test_review_decision_rejects_malformed_historical_resource_key(
    resource_key: str,
) -> None:
    decision = _review_decision()
    decision["resource_key"] = resource_key
    decision["item_id"] = f"zh-cn/{resource_key}"
    decision["decision_id"] = document_identity_sha256(
        decision,
        "decision_id",
    )

    with pytest.raises(ManifestValidationError, match="resource_key"):
        StateStore(ROOT).validate_document(decision, "review_decision")


@pytest.mark.parametrize("name", ("sampled_evidence", "validation"))
def test_runtime_evidence_rejects_a_p2_validation_profile_binding(
    name: str,
) -> None:
    document = _documents()[name]
    bindings = (
        document["bindings"]
        if name == "sampled_evidence"
        else document["evidence"]["bindings"]
    )
    bindings["validation_profile"] = {
        "id": "v0.4-validation-p2",
        "schema_version": "1.1",
        "path": "data/configs/validation-profiles/v0.4-p2.json",
        "sha256": _sha("p2-validation-profile"),
    }
    with pytest.raises(Exception):
        _validator(name).validate(document)


@pytest.mark.parametrize("name", ("sampled_evidence", "validation"))
def test_p3_evidence_requires_the_frozen_soft_category_artifact(
    name: str,
) -> None:
    document = _documents()[name]
    bindings = (
        document["bindings"]
        if name == "sampled_evidence"
        else document["evidence"]["bindings"]
    )
    bindings["soft_category"] = None
    with pytest.raises(Exception):
        _validator(name).validate(document)


def test_validation_20_accepts_a_full_mode_without_sampling_fields() -> None:
    document = _validation()
    document["evidence"]["bindings"]["sampling_plan"] = None
    document["evidence"]["content_validation"]["coverage"] = _coverage(
        mode="full"
    )
    _validator("validation").validate(document)


def test_validation_20_full_mode_rejects_stratified_bindings() -> None:
    document = _validation()
    document["evidence"]["content_validation"]["coverage"]["mode"] = "full"
    with pytest.raises(Exception):
        _validator("validation").validate(document)


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("evidence", "bindings", "sampling_plan"), None),
        (("evidence", "content_validation", "coverage", "seed"), None),
        (("evidence", "content_validation", "coverage", "strata"), []),
        (
            (
                "evidence",
                "content_validation",
                "coverage",
                "selected_state_ids",
            ),
            [],
        ),
    ),
)
def test_validation_20_stratified_mode_requires_sampling_fields(
    path: tuple[str, ...],
    value: Any,
) -> None:
    with pytest.raises(Exception):
        _validator("validation").validate(
            _documents_with_replacement("validation", path, value)
        )


def test_source_finding_blocks_source_precondition_without_machine_failure() -> None:
    document = _validation()
    document["evidence"]["source_quality_findings"] = [
        {
            "code": "charset_declaration_not_utf8",
            "message": "Source charset declaration requires review.",
            "path": "source_quality_findings[0]",
            "severity": "finding",
            "disposition": "unresolved",
        }
    ]
    document["evidence"]["approval_preconditions"]["source"] = {
        "eligible": False,
        "blockers": [
            {
                "code": "unresolved_source_quality_finding",
                "message": "An unresolved Source Quality Finding blocks approval.",
                "path": "source_quality_findings[0]",
            }
        ],
    }
    _validator("validation").validate(document)
    assert document["status"] == "passed"


def test_source_finding_cannot_leave_source_precondition_eligible() -> None:
    document = _validation()
    document["evidence"]["source_quality_findings"] = [
        {
            "code": "charset_declaration_not_utf8",
            "message": "Source charset declaration requires review.",
            "path": "source_quality_findings[0]",
            "severity": "finding",
            "disposition": "unresolved",
        }
    ]
    with pytest.raises(Exception):
        _validator("validation").validate(document)


def test_state_store_requires_one_canonical_blocker_per_source_finding() -> None:
    document = _validation()
    findings = [
        {
            "code": code,
            "message": f"{code} requires review.",
            "path": f"source_quality_findings[{index}]",
            "severity": "finding",
            "disposition": "unresolved",
        }
        for index, code in enumerate(
            ("charset_declaration_not_utf8", "charset_declarations_conflict")
        )
    ]
    document["evidence"]["source_quality_findings"] = findings
    document["evidence"]["approval_preconditions"]["source"] = (
        source_approval_preconditions(findings).to_dict()
    )
    document["evidence_sha256"] = validation_evidence_sha256(document)
    StateStore(ROOT).validate_document(document, "validation")

    document["evidence"]["approval_preconditions"]["source"][
        "blockers"
    ].pop()
    document["evidence_sha256"] = validation_evidence_sha256(document)
    with pytest.raises(ManifestValidationError, match="all unresolved"):
        StateStore(ROOT).validate_document(document, "validation")


@pytest.mark.parametrize("result", ("structure_validation", "content_validation"))
def test_passed_validation_requires_each_machine_result_to_pass(
    result: str,
) -> None:
    document = _validation()
    document["evidence"][result]["status"] = "failed"
    with pytest.raises(Exception):
        _validator("validation").validate(document)


def test_failed_validation_requires_at_least_one_failed_machine_result() -> None:
    document = _validation()
    document["status"] = "failed"
    document["evidence"]["verdict"] = "failed"
    document["evidence"]["errors"] = [
        {
            "code": "machine_validation_failed",
            "message": "Machine validation failed.",
            "path": "evidence",
        }
    ]
    document["evidence"]["approval_preconditions"]["machine"] = {
        "eligible": False,
        "blockers": [
            {
                "code": "machine_validation_not_passed",
                "message": "Machine Validation must pass.",
                "path": "status.validation",
            }
        ],
    }
    with pytest.raises(Exception):
        _validator("validation").validate(document)


@pytest.mark.parametrize(
    "reason",
    (
        "upstream_source",
        "product_config",
        "extractor_defect",
        "validator_defect",
        "needs_clarification",
    ),
)
def test_review_rejection_requires_a_stable_reason(reason: str) -> None:
    decision = _review_decision()
    decision["verdict"] = "rejected"
    decision["reason"] = reason
    _validator("review").validate(decision)

    decision["reason"] = None
    with pytest.raises(Exception):
        _validator("review").validate(decision)


def test_review_inspection_scope_controls_state_id() -> None:
    decision = _review_decision()
    decision["inspected_states"] = [{"scope": "page_global", "state_id": _sha("x")}]
    with pytest.raises(Exception):
        _validator("review").validate(decision)

    decision["inspected_states"] = [{"scope": "interactive_state"}]
    with pytest.raises(Exception, match="required property"):
        _validator("review").validate(decision)


def test_review_inspection_mode_controls_sampling_plan_binding() -> None:
    decision = _review_decision()
    decision["bindings"]["sampling_plan_sha256"] = None
    with pytest.raises(Exception):
        _validator("review").validate(decision)

    decision["inspected_states"] = [{"scope": "full_content"}]
    _validator("review").validate(decision)

    decision["bindings"]["sampling_plan_sha256"] = _sha("unexpected-plan")
    with pytest.raises(Exception):
        _validator("review").validate(decision)

    decision["bindings"]["sampling_plan_sha256"] = None
    decision["inspected_states"] = [{"scope": "page_global"}]
    with pytest.raises(Exception):
        _validator("review").validate(decision)


def test_release_manifest_forbids_an_embedded_seal() -> None:
    manifest = _release_manifest()
    manifest["seal"] = _sha("seal")
    with pytest.raises(Exception, match="Additional properties"):
        _validator("release").validate(manifest)


def test_release_manifest_11_requires_successor_profile_and_policy() -> None:
    manifest = _release_manifest_11()

    _validator("release_11").validate(manifest)
    StateStore(ROOT).validate_document(manifest, "release_manifest")

    legacy_profile = copy.deepcopy(manifest)
    legacy_profile["validation_profile"] = _validation_profile_identity()
    legacy_profile["items"][0]["bindings"]["validation_profile_sha256"] = (
        legacy_profile["validation_profile"]["sha256"]
    )
    with pytest.raises(Exception):
        _validator("release_11").validate(legacy_profile)

    missing_policy = copy.deepcopy(manifest)
    missing_policy.pop("finding_code_policy_identity")
    with pytest.raises(Exception):
        _validator("release_11").validate(missing_policy)


def test_release_coverage_mode_controls_sampling_plan_binding() -> None:
    manifest = _release_manifest()
    item = manifest["items"][0]
    item["bindings"]["sampling_plan_sha256"] = None
    with pytest.raises(Exception):
        _validator("release").validate(manifest)

    item["coverage"] = {
        "mode": "full",
        "universe_count": 1,
        "selected_count": 1,
        "untested_count": 0,
    }
    _validator("release").validate(manifest)


def test_state_store_applies_release_cross_binding_invariants() -> None:
    store = StateStore(ROOT)
    manifest = _release_manifest()
    store.validate_document(manifest, "release_manifest")

    manifest["items"][0]["payload"]["sha256"] = _sha("other-payload")
    with pytest.raises(
        ManifestValidationError,
        match="release_payload_binding_mismatch",
    ):
        store.validate_document(manifest, "release_manifest")


def test_release_full_coverage_cannot_leave_untested_items() -> None:
    manifest = _release_manifest()
    item = manifest["items"][0]
    item["bindings"]["sampling_plan_sha256"] = None
    item["coverage"] = {
        "mode": "full",
        "universe_count": 20,
        "selected_count": 1,
        "untested_count": 19,
    }
    with pytest.raises(Exception):
        _validator("release").validate(manifest)

    item["coverage"]["untested_count"] = 0
    with pytest.raises(ManifestValidationError, match="coverage_count_mismatch"):
        StateStore(ROOT).validate_document(manifest, "release_manifest")


def test_p3_profile_binds_p2_sampling_profile_and_new_contract_hashes() -> None:
    profile = _documents()["validation_profile"]
    assert profile["base_profile"] == {
        "id": "v0.4-validation-p2",
        "schema_version": "1.1",
        "path": "data/configs/validation-profiles/v0.4-p2.json",
        "sha256": sha256_file(
            ROOT / "data/configs/validation-profiles/v0.4-p2.json"
        ),
    }
    assert profile["content_sampling_profile"] == _sampling_profile_identity()
    assert set(profile["contracts"]) == {
        "product_definition",
        "flexible_content",
        "support_article",
        "diagnostic_sidecar",
        "source_html_structure_audit",
        "content_sampling_profile",
        "pipeline_validation",
        "batch_item_sampling_plan",
        "sampled_content_evidence",
    }
    for identity in profile["contracts"].values():
        assert sha256_file(ROOT / identity["path"]) == identity["sha256"]


def test_p3_builder_is_deterministic_and_default_mode_is_check_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    assert profile_builder.build_document() == _documents()["validation_profile"]
    assert profile_builder.build() == _documents()["validation_profile"]

    missing_output = tmp_path / "v0.4-p3.json"
    monkeypatch.setattr(profile_builder, "P3_PROFILE_PATH", str(missing_output))
    writes: list[Path] = []
    original_atomic_write = profile_builder._atomic_write

    def tracking_write(path: Path, rendered: str) -> None:
        writes.append(path)
        original_atomic_write(path, rendered)

    monkeypatch.setattr(profile_builder, "_atomic_write", tracking_write)
    with pytest.raises(
        profile_builder.ValidationProfileBuildError,
        match="missing or stale",
    ):
        profile_builder.build()
    assert writes == []
    assert not missing_output.exists()

    profile_builder.build(write_reviewed=True)
    assert writes == [missing_output]
    assert _read_json("data/configs/validation-profiles/v0.4-p3.json") == json.loads(
        missing_output.read_text(encoding="utf-8")
    )


def test_p3_builder_rejects_nested_sampling_profile_drift() -> None:
    drifted = profile_builder.build_content_sampling_profile_document()
    drifted["target_budget"] = 13
    with pytest.raises(
        profile_builder.ValidationProfileBuildError,
        match="Nested Content Sampling Profile identity drifted",
    ):
        profile_builder.build_validation_profile_document(drifted)
