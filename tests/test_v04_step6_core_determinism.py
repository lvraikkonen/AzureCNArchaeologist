from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.regression.core import CORE_ITEM_IDS, CoreRegressionError, json_sha256, read_json
from src.regression.determinism import (
    COMPARATOR_ID,
    _compare_snapshots,
    normalize_sampled_content,
    normalize_validation,
    write_determinism_record,
)


ROOT = Path(__file__).resolve().parents[1]
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64


def _sample_plan() -> dict[str, object]:
    return {
        "algorithm_version": "source-ordered-stratified-sampling-v1",
        "content_sampling_profile": {
            "id": "v0.4-content-sampling-p3",
            "path": "data/configs/content-sampling-profiles/v0.4-p3.json",
            "schema_version": "1.0",
            "sha256": SHA_A,
        },
        "coverage": {
            "assurance": "sampled_state_content_consistency",
            "mode": "stratified_sample",
            "selected_count": 1,
            "universe_count": 1,
            "untested_count": 0,
        },
        "item_id": "zh-cn/api-management",
        "plan_sha256": SHA_B,
        "schema_version": "1.0",
        "seed": SHA_C,
        "selected_states": [{"state_id": SHA_D, "criteria": [["region", "east-china"]]}],
        "source_sha256": SHA_A,
        "state_universe": {
            "default_state_id": SHA_D,
            "states": [{"state_id": SHA_D, "criteria": [["region", "east-china"]]}],
            "universe_id": SHA_C,
        },
        "strata": [
            {
                "criteria": [["region", "east-china"]],
                "kind": "source_proven_region",
                "state_ids": [SHA_D],
                "stratum_id": SHA_B,
            }
        ],
        "strategy": "region_filter",
        "target_budget": 12,
        "effective_budget": 12,
    }


def _sampled() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "item_id": "zh-cn/api-management",
        "mode": "stratified_sample",
        "coverage": {
            "assurance": "sampled_state_content_consistency",
            "mode": "stratified_sample",
            "seed": SHA_C,
            "selected_count": 1,
            "selected_state_ids": [SHA_D],
            "strata": [SHA_B],
            "universe_count": 1,
            "untested_count": 0,
        },
        "structure_validation": {
            "status": "passed",
            "checked_count": 1,
            "universe_count": 1,
            "errors": [],
        },
        "page_global_comparison": {
            "status": "matched",
            "source_fingerprint": SHA_A,
            "payload_fingerprint": SHA_A,
            "diff_reference": "runs/a/runtime-only.json",
        },
        "full_content_comparison": None,
        "samples": [
            {
                "state": {"state_id": SHA_D, "criteria": [["region", "east-china"]]},
                "status": "matched",
                "source_fingerprint": SHA_B,
                "payload_fingerprint": SHA_B,
                "diff_reference": None,
            }
        ],
        "errors": [],
        "warnings": [{"code": "advisory", "path": "$.x", "message": "left"}],
        "bindings": {},
        "evidence_sha256": SHA_A,
    }


def _validation() -> dict[str, object]:
    return {
        "schema_version": "2.1",
        "batch_id": "20260805T000000Z-aaaaaaaa",
        "item_id": "zh-cn/api-management",
        "status": "passed",
        "evidence_sha256": SHA_A,
        "evidence": {
            "verdict": "passed",
            "bindings": {
                "validation_profile": {"id": "v0.4-validation-p3-successor", "sha256": SHA_A},
                "content_sampling_profile": {"id": "v0.4-content-sampling-p3", "sha256": SHA_B},
                "finding_code_policy_identity": {"id": "v0.4-finding-code-policy-p4", "sha256": SHA_C},
            },
            "structure_validation": {
                "status": "passed",
                "checked_count": 1,
                "total_count": 1,
            },
            "content_validation": {
                "status": "passed",
                "claim": "sampled_state_content_consistency",
                "coverage": {
                    "assurance": "sampled_state_content_consistency",
                    "mode": "stratified_sample",
                    "selected_count": 1,
                    "selected_state_ids": [SHA_D],
                    "universe_count": 1,
                    "untested_count": 0,
                },
            },
            "source_quality_findings": [
                {
                    "code": "empty_optional_content",
                    "path": "$.articleDescription",
                    "classification": "advisory",
                    "message": "runtime wording",
                }
            ],
            "approval_preconditions": {
                "machine": {"eligible": True, "blockers": []},
                "source": {"eligible": True, "blockers": []},
            },
            "errors": [],
            "warnings": [],
        },
    }


def _snapshot(batch_id: str) -> dict[str, object]:
    item = {
        "item_id": "zh-cn/api-management",
        "frozen_item": {"item_id": "zh-cn/api-management", "source": {"sha256": SHA_A}},
        "payload_sha256": SHA_A,
        "sampling_plan_sha256": SHA_B,
        "sampled_content_semantic_sha256": SHA_C,
        "validation_semantic_identity": SHA_D,
        "promotion_inputs_sha256": "e" * 64,
        "integrity": {
            "payload_artifact_sha256": SHA_A,
            "sampled_content_artifact_sha256": SHA_B,
            "sampled_content_evidence_sha256": SHA_C,
            "validation_artifact_sha256": SHA_D,
            "validation_evidence_sha256": "e" * 64,
            "sampling_plan_artifact_sha256": "f" * 64,
            "sampling_plan_sha256": SHA_B,
        },
    }
    items = []
    for item_id in CORE_ITEM_IDS:
        next_item = copy.deepcopy(item)
        next_item["item_id"] = item_id
        next_item["frozen_item"]["item_id"] = item_id
        items.append(next_item)
    return {
        "batch_id": batch_id,
        "provenance": {
            "git_commit": SHA_A,
            "worktree_fingerprint": "sha256:" + SHA_B,
            "immutable_fingerprint": "sha256:" + SHA_C,
        },
        "planning": {"planning_baseline": {"sha256": SHA_A}},
        "validation_context": {"validation_profile": {"sha256": SHA_A}},
        "frozen_inputs": {"soft_category": {"sha256": SHA_A}},
        "summary": {
            "status": "completed",
            "total": 8,
            "execution_succeeded": 8,
            "validation_passed": 8,
            "review_pending": 8,
            "not_released": 8,
            "not_published": 8,
        },
        "items": items,
    }


def _schema_record() -> dict[str, object]:
    left = _snapshot("20260805T000000Z-aaaaaaaa")
    right = _snapshot("20260805T000001Z-bbbbbbbb")
    comparison = _compare_snapshots(left, right)
    record = {
        "schema_version": "1.0",
        "record_type": COMPARATOR_ID,
        "comparator": {
            "id": COMPARATOR_ID,
            "sampled_normalization": "core-determinism-sampled-normalization-v1",
            "validation_normalization": "core-determinism-validation-normalization-v1",
            "promotion_inputs_normalization": "core-determinism-promotion-inputs-v1",
        },
        "left": {
            "batch_id": left["batch_id"],
            "provenance": left["provenance"],
            "summary": left["summary"],
        },
        "right": {
            "batch_id": right["batch_id"],
            "provenance": right["provenance"],
            "summary": right["summary"],
        },
        "common_inputs": {
            "planning": left["planning"],
            "validation_context": left["validation_context"],
            "frozen_inputs": left["frozen_inputs"],
            "items": [
                {"item_id": item["item_id"], "frozen_item_sha256": json_sha256(item["frozen_item"])}
                for item in left["items"]
            ],
        },
        "comparison": comparison,
        "record_sha256": "",
    }
    record["record_sha256"] = json_sha256(
        {key: value for key, value in record.items() if key != "record_sha256"}
    )
    return record


def test_sampled_semantic_identity_ignores_runtime_metadata_messages() -> None:
    sampled = _sampled()
    plan = _sample_plan()
    left = normalize_sampled_content(
        item_id="zh-cn/api-management",
        sampled=sampled,
        plan=plan,
    )
    drifted = copy.deepcopy(sampled)
    drifted["page_global_comparison"]["diff_reference"] = "runs/b/other.json"
    drifted["warnings"][0]["message"] = "right"
    right = normalize_sampled_content(
        item_id="zh-cn/api-management",
        sampled=drifted,
        plan=plan,
    )

    assert json_sha256(left) == json_sha256(right)


def test_sampled_semantic_identity_detects_business_fingerprint_drift() -> None:
    sampled = _sampled()
    plan = _sample_plan()
    left = normalize_sampled_content(
        item_id="zh-cn/api-management",
        sampled=sampled,
        plan=plan,
    )
    drifted = copy.deepcopy(sampled)
    drifted["samples"][0]["payload_fingerprint"] = "0" * 64
    right = normalize_sampled_content(
        item_id="zh-cn/api-management",
        sampled=drifted,
        plan=plan,
    )

    assert json_sha256(left) != json_sha256(right)


def test_validation_semantic_identity_uses_stable_finding_triples() -> None:
    sampled_hash = json_sha256(
        normalize_sampled_content(
            item_id="zh-cn/api-management",
            sampled=_sampled(),
            plan=_sample_plan(),
        )
    )
    left = normalize_validation(
        item_id="zh-cn/api-management",
        validation=_validation(),
        sampled_content_semantic_sha256=sampled_hash,
    )
    drifted = _validation()
    drifted["evidence"]["source_quality_findings"][0]["message"] = "different words"
    right = normalize_validation(
        item_id="zh-cn/api-management",
        validation=drifted,
        sampled_content_semantic_sha256=sampled_hash,
    )

    assert json_sha256(left) == json_sha256(right)

    changed = _validation()
    changed["evidence"]["source_quality_findings"][0]["classification"] = "approval_blocking"
    changed_identity = normalize_validation(
        item_id="zh-cn/api-management",
        validation=changed,
        sampled_content_semantic_sha256=sampled_hash,
    )
    assert json_sha256(left) != json_sha256(changed_identity)


def test_compare_snapshots_detects_semantic_drift() -> None:
    left = _snapshot("20260805T000000Z-aaaaaaaa")
    right = _snapshot("20260805T000001Z-bbbbbbbb")
    right["items"][2]["validation_semantic_identity"] = "0" * 64

    with pytest.raises(CoreRegressionError, match="validation_semantic_identity"):
        _compare_snapshots(left, right)


def test_determinism_record_schema_is_closed_world() -> None:
    schema = read_json(ROOT / "schemas/step6-core-determinism-record-1.0.schema.json")
    Draft202012Validator.check_schema(schema)
    record = _schema_record()
    validator = Draft202012Validator(schema)

    assert not list(validator.iter_errors(record))

    record["unexpected"] = True
    errors = list(validator.iter_errors(record))
    assert errors
    assert any("Additional properties" in error.message for error in errors)


def test_determinism_record_write_once_refuses_different_bytes(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    record = _schema_record()
    write_determinism_record(path, record)
    write_determinism_record(path, record)

    changed = copy.deepcopy(record)
    changed["comparison"]["items"][0]["payload_sha256"] = "0" * 64
    with pytest.raises(CoreRegressionError, match="already exists"):
        write_determinism_record(path, changed)

    assert json.loads(path.read_text(encoding="utf-8")) == record
