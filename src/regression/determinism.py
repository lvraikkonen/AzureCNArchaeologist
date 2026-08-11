"""Step 6 Slice B Core deterministic run comparison.

This module reads two completed Core pipeline runs, verifies each run's local
artifact bindings, and writes a versioned acceptance record for the normalized
semantic identities required by v0.4 Step 6B.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from src.content_sampling.artifacts import artifact_json_sha256
from src.core.product_catalog import sha256_file
from src.pipeline.provenance import ProvenanceProvider
from src.pipeline.state_store import StateStore
from src.regression.core import (
    CORE_ITEM_IDS,
    V04_CORE_SPEC,
    CoreSpecification,
    CoreRegressionError,
    json_sha256,
    read_json,
    render_json,
    write_json,
    _artifact,
    _validate_schema,
)


DETERMINISM_RECORD_SCHEMA = "schemas/step6-core-determinism-record-1.0.schema.json"
COMPARATOR_ID = "core-determinism-comparator-v1"
SAMPLED_NORMALIZATION_ID = "core-determinism-sampled-normalization-v1"
VALIDATION_NORMALIZATION_ID = "core-determinism-validation-normalization-v1"
PROMOTION_INPUTS_NORMALIZATION_ID = "core-determinism-promotion-inputs-v1"


def _stable_issue(issue: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "code": issue.get("code"),
        "path": issue.get("semantic_path") or issue.get("path"),
        "classification": issue.get("classification"),
        "status": issue.get("status"),
    }


def _stable_issues(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    return [_stable_issue(value) for value in values if isinstance(value, Mapping)]


def _comparison_identity(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "status": value.get("status"),
        "source_fingerprint": value.get("source_fingerprint"),
        "payload_fingerprint": value.get("payload_fingerprint"),
    }


def _state_identity(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "state_id": state.get("state_id"),
        "criteria": copy.deepcopy(state.get("criteria", [])),
    }


def _plan_identity(plan: Mapping[str, Any] | None) -> dict[str, Any]:
    if plan is None:
        return {
            "status": "not_applicable",
            "algorithm_version": None,
            "plan_sha256": None,
            "seed": None,
            "coverage": None,
            "state_universe": {
                "universe_id": None,
                "default_state_id": None,
                "ordered_state_ids": [],
                "states": [],
            },
            "selected_states": [],
            "strata": [],
        }
    states = [_state_identity(state) for state in plan["state_universe"]["states"]]
    selected = [_state_identity(state) for state in plan["selected_states"]]
    return {
        "status": "applicable",
        "algorithm_version": plan["algorithm_version"],
        "plan_sha256": plan["plan_sha256"],
        "seed": plan["seed"],
        "coverage": copy.deepcopy(plan["coverage"]),
        "state_universe": {
            "universe_id": plan["state_universe"]["universe_id"],
            "default_state_id": plan["state_universe"]["default_state_id"],
            "ordered_state_ids": [state["state_id"] for state in states],
            "states": states,
        },
        "selected_states": selected,
        "strata": [
            {
                "stratum_id": stratum.get("stratum_id"),
                "kind": stratum.get("kind"),
                "criteria": copy.deepcopy(stratum.get("criteria", [])),
                "state_ids": list(stratum.get("state_ids", [])),
            }
            for stratum in plan.get("strata", [])
        ],
    }


def normalize_sampled_content(
    *,
    item_id: str,
    sampled: Mapping[str, Any],
    plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    plan_identity = _plan_identity(plan)
    samples = [
        {
            "state": _state_identity(sample["state"]),
            "comparison": _comparison_identity(sample),
        }
        for sample in sampled.get("samples", [])
    ]
    return {
        "normalization_algorithm": SAMPLED_NORMALIZATION_ID,
        "item_id": item_id,
        "sampled_schema_version": sampled["schema_version"],
        "mode": sampled["mode"],
        "coverage": copy.deepcopy(sampled["coverage"]),
        "structure_validation": {
            "status": sampled["structure_validation"]["status"],
            "checked_count": sampled["structure_validation"]["checked_count"],
            "universe_count": sampled["structure_validation"]["universe_count"],
            "errors": _stable_issues(sampled["structure_validation"].get("errors", [])),
        },
        "page_global_comparison": _comparison_identity(
            sampled["page_global_comparison"]
        ),
        "full_content_comparison": _comparison_identity(
            sampled.get("full_content_comparison")
        ),
        "sampling_plan": plan_identity,
        "state_universe": plan_identity["state_universe"],
        "selected_states": plan_identity["selected_states"],
        "samples": samples,
        "errors": _stable_issues(sampled.get("errors", [])),
        "warnings": _stable_issues(sampled.get("warnings", [])),
    }


def normalize_validation(
    *,
    item_id: str,
    validation: Mapping[str, Any],
    sampled_content_semantic_sha256: str,
) -> dict[str, Any]:
    evidence = validation["evidence"]
    content = evidence["content_validation"]
    return {
        "normalization_algorithm": VALIDATION_NORMALIZATION_ID,
        "item_id": item_id,
        "sampled_content_semantic_sha256": sampled_content_semantic_sha256,
        "validation_schema_version": validation["schema_version"],
        "status": validation["status"],
        "verdict": evidence["verdict"],
        "structure_validation": {
            "status": evidence["structure_validation"]["status"],
            "checked_count": evidence["structure_validation"]["checked_count"],
            "total_count": evidence["structure_validation"]["total_count"],
        },
        "content_validation": {
            "status": content["status"],
            "claim": content["claim"],
            "coverage": copy.deepcopy(content["coverage"]),
        },
        "bindings": {
            "validation_profile": copy.deepcopy(
                evidence["bindings"]["validation_profile"]
            ),
            "content_sampling_profile": copy.deepcopy(
                evidence["bindings"]["content_sampling_profile"]
            ),
            "finding_code_policy_identity": copy.deepcopy(
                evidence["bindings"].get("finding_code_policy_identity")
            ),
        },
        "source_quality_findings": _stable_issues(
            evidence.get("source_quality_findings", [])
        ),
        "approval_preconditions": copy.deepcopy(
            evidence["approval_preconditions"]
        ),
        "errors": _stable_issues(evidence.get("errors", [])),
        "warnings": _stable_issues(evidence.get("warnings", [])),
    }


def normalize_promotion_inputs(
    *,
    review_item: Mapping[str, Any],
    sampled_content_semantic_sha256: str,
    validation_semantic_identity: str,
) -> dict[str, Any]:
    bindings = review_item["bindings"]
    status = review_item["status"]
    return {
        "normalization_algorithm": PROMOTION_INPUTS_NORMALIZATION_ID,
        "item_id": review_item["item_id"],
        "status": {
            "execution": status["execution"],
            "validation": status["validation"],
            "review": status["review"],
            "publication": status["publication"],
            "release": status["release"],
            "evidence_binding": status["evidence_binding"],
            "approval_eligibility": status["approval_eligibility"],
        },
        "flags": {
            "source_warning": review_item["source_warning"],
            "approval_blocked": review_item["approval_blocked"],
            "machine_failed": review_item["machine_failed"],
            "release_ready": review_item["release_ready"],
        },
        "bindings": {
            "source_sha256": bindings["source_sha256"],
            "payload_sha256": bindings["payload_sha256"],
            "validation_evidence_sha256": bindings["validation_evidence_sha256"],
            "sampling_plan_sha256": bindings["sampling_plan_sha256"],
        },
        "sampled_content_semantic_sha256": sampled_content_semantic_sha256,
        "validation_semantic_identity": validation_semantic_identity,
    }


def _run_provenance(input_manifest: Mapping[str, Any]) -> dict[str, Any]:
    provenance = input_manifest["provenance"]
    if provenance["dirty"] or not provenance["reproducible"] or provenance["worktree_changes"]:
        raise CoreRegressionError("Core determinism runs must freeze clean provenance")
    return {
        "git_commit": provenance["git_commit"],
        "worktree_fingerprint": provenance["worktree_fingerprint"],
        "immutable_fingerprint": provenance["immutable_fingerprint"],
    }


def _frozen_item_identity(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "item_id": item["item_id"],
        "language": item["identity"]["language"],
        "resource_key": item["identity"]["resource_key"],
        "product_key": item["product_key"],
        "resource": copy.deepcopy(item["resource"]),
        "strategy": item["strategy"],
        "page_model": item["page_model"],
        "catalog_categories": list(item["catalog_categories"]),
        "support_article_type": item["support_article_type"],
        "config": copy.deepcopy(item["config"]),
        "source": copy.deepcopy(item["source"]),
        "normalized_input": copy.deepcopy(item["normalized_input"]),
        "soft_category": copy.deepcopy(
            item.get("soft_category", item.get("frozen_inputs", {}))
        ),
    }


def _review_item_by_id(review_queue: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(item["item_id"]): item for item in review_queue["items"]}


def _verify_no_lifecycle_outputs(manifest: Mapping[str, Any], review_item: Mapping[str, Any]) -> None:
    if manifest.get("release_manifests") or manifest.get("publication_receipts"):
        raise CoreRegressionError("Core determinism runs must not contain releases or publications")
    status = review_item["status"]
    if (
        status["review"] != "pending"
        or status["release"] != "not_released"
        or status["publication"] != "not_published"
    ):
        raise CoreRegressionError(
            f"Core determinism item has lifecycle state: {review_item['item_id']}"
        )
    if review_item["artifacts"].get("current_review_decision") is not None:
        raise CoreRegressionError(
            f"Core determinism item has a Review Decision: {review_item['item_id']}"
        )


def _verify_review_binding(
    *,
    item_id: str,
    manifest_item: Mapping[str, Any],
    review_item: Mapping[str, Any],
    validation: Mapping[str, Any],
    sampled: Mapping[str, Any],
    plan: Mapping[str, Any] | None,
) -> None:
    if review_item["artifacts"]["payload"] != manifest_item["artifacts"]["payload"]:
        raise CoreRegressionError(f"Review payload binding drifted: {item_id}")
    if review_item["artifacts"]["validation"] != manifest_item["artifacts"]["validation"]:
        raise CoreRegressionError(f"Review validation binding drifted: {item_id}")
    if review_item["artifacts"]["sampled_content_evidence"] != manifest_item["artifacts"]["sampled_content_evidence"]:
        raise CoreRegressionError(f"Review sampled evidence binding drifted: {item_id}")
    if review_item["artifacts"]["sampling_plan"] != manifest_item["artifacts"].get("sampling_plan"):
        raise CoreRegressionError(f"Review sampling plan binding drifted: {item_id}")

    bindings = review_item["bindings"]
    if bindings["payload_sha256"] != manifest_item["artifacts"]["payload"]["sha256"]:
        raise CoreRegressionError(f"Review payload SHA binding drifted: {item_id}")
    if bindings["source_sha256"] != validation["evidence"]["bindings"]["source"]["sha256"]:
        raise CoreRegressionError(f"Review source SHA binding drifted: {item_id}")
    if bindings["validation_artifact_sha256"] != manifest_item["artifacts"]["validation"]["sha256"]:
        raise CoreRegressionError(f"Review validation artifact binding drifted: {item_id}")
    if bindings["validation_evidence_sha256"] != validation["evidence_sha256"]:
        raise CoreRegressionError(f"Review validation evidence binding drifted: {item_id}")
    expected_plan_sha = plan["plan_sha256"] if plan is not None else None
    if bindings["sampling_plan_sha256"] != expected_plan_sha:
        raise CoreRegressionError(f"Review plan identity binding drifted: {item_id}")
    if validation["evidence"]["content_validation"]["sampled_content_evidence"]["evidence_sha256"] != sampled["evidence_sha256"]:
        raise CoreRegressionError(f"Validation sampled evidence identity binding drifted: {item_id}")


def load_core_run_snapshot(
    root: Path,
    *,
    runs_dir: Path,
    batch_id: str,
    specification: CoreSpecification = V04_CORE_SPEC,
) -> dict[str, Any]:
    root = root.resolve()
    runs_dir = runs_dir.resolve() if runs_dir.is_absolute() else root / runs_dir
    store = StateStore(root, runs_dir=runs_dir)
    run_dir = store.run_dir(batch_id)
    manifest = store.read_manifest(batch_id)
    input_manifest = store.read_input_manifest(batch_id)
    review_queue = store.read_projection(batch_id, "review")
    review_by_id = _review_item_by_id(review_queue)

    if manifest["status"] != "completed":
        raise CoreRegressionError(f"Core determinism run is not completed: {batch_id}")
    if input_manifest["scope"] != {
        "kind": "group",
        "group": specification.group,
    }:
        raise CoreRegressionError(f"Batch is not a Core batch: {batch_id}")
    if list(input_manifest["languages"]) != ["zh-cn", "en-us"]:
        raise CoreRegressionError(f"Batch is not bilingual: {batch_id}")
    if [item["item_id"] for item in input_manifest["items"]] != list(CORE_ITEM_IDS):
        raise CoreRegressionError(f"Batch item set is not the Core closed world: {batch_id}")
    if manifest["summary"]["total"] != 8 or manifest["summary"]["runnable"] != 8:
        raise CoreRegressionError(f"Core determinism run summary is not exact 8/8: {batch_id}")
    if (
        manifest["summary"]["execution_succeeded"] != 8
        or manifest["summary"]["validation_passed"] != 8
    ):
        raise CoreRegressionError(f"Core determinism run did not pass 8/8: {batch_id}")

    frozen_items = {item["item_id"]: item for item in input_manifest["items"]}
    items = []
    for item_id in CORE_ITEM_IDS:
        manifest_item = manifest["items"][item_id]
        review_item = review_by_id[item_id]
        if manifest_item["status"]["execution"] != "succeeded":
            raise CoreRegressionError(f"Core item execution did not succeed: {item_id}")
        if manifest_item["status"]["validation"] != "passed":
            raise CoreRegressionError(f"Core item validation did not pass: {item_id}")
        _verify_no_lifecycle_outputs(manifest, review_item)

        payload = _artifact(root, run_dir, manifest_item["artifacts"]["payload"])
        validation_ref = manifest_item["artifacts"]["validation"]
        validation = store.read_projection(
            batch_id,
            "validation",
            relative_path=validation_ref["path"],
        )
        if sha256_file(run_dir / validation_ref["path"]) != validation_ref["sha256"]:
            raise CoreRegressionError(f"Validation artifact hash drifted: {item_id}")

        sampled_ref = manifest_item["artifacts"]["sampled_content_evidence"]
        sampled = store.read_step4_artifact(
            batch_id,
            "sampled_content_evidence",
            relative_path=sampled_ref["path"],
        )
        if artifact_json_sha256(sampled) != sampled_ref["sha256"]:
            raise CoreRegressionError(f"Sampled evidence artifact hash drifted: {item_id}")

        plan_ref = manifest_item["artifacts"].get("sampling_plan")
        plan = None
        if plan_ref is not None:
            plan = store.read_step4_artifact(
                batch_id,
                "sampling_plan",
                relative_path=plan_ref["path"],
            )
            if artifact_json_sha256(plan) != plan_ref["sha256"]:
                raise CoreRegressionError(f"Sampling plan artifact hash drifted: {item_id}")
            if plan["plan_sha256"] != validation["evidence"]["bindings"]["sampling_plan"]["plan_sha256"]:
                raise CoreRegressionError(f"Sampling plan identity binding drifted: {item_id}")
        elif validation["evidence"]["bindings"]["sampling_plan"] is not None:
            raise CoreRegressionError(f"Full-mode item unexpectedly has plan binding: {item_id}")

        content_binding = validation["evidence"]["content_validation"]["sampled_content_evidence"]
        if (
            content_binding["path"] != sampled_ref["path"]
            or content_binding["artifact_sha256"] != sampled_ref["sha256"]
            or content_binding["evidence_sha256"] != sampled["evidence_sha256"]
        ):
            raise CoreRegressionError(f"Validation sampled evidence binding drifted: {item_id}")
        payload_binding = validation["evidence"]["bindings"]["payload"]
        if (
            payload_binding["path"] != manifest_item["artifacts"]["payload"]["path"]
            or payload_binding["sha256"] != payload["sha256"]
        ):
            raise CoreRegressionError(f"Validation payload binding drifted: {item_id}")
        if validation["evidence"]["bindings"]["normalized_input"] != frozen_items[item_id]["normalized_input"]:
            raise CoreRegressionError(f"Validation normalized input binding drifted: {item_id}")

        _verify_review_binding(
            item_id=item_id,
            manifest_item=manifest_item,
            review_item=review_item,
            validation=validation,
            sampled=sampled,
            plan=plan,
        )

        sampled_normalized = normalize_sampled_content(
            item_id=item_id,
            sampled=sampled,
            plan=plan,
        )
        sampled_semantic_sha = json_sha256(sampled_normalized)
        validation_normalized = normalize_validation(
            item_id=item_id,
            validation=validation,
            sampled_content_semantic_sha256=sampled_semantic_sha,
        )
        validation_semantic_sha = json_sha256(validation_normalized)
        promotion_inputs = normalize_promotion_inputs(
            review_item=review_item,
            sampled_content_semantic_sha256=sampled_semantic_sha,
            validation_semantic_identity=validation_semantic_sha,
        )
        items.append(
            {
                "item_id": item_id,
                "frozen_item": _frozen_item_identity(frozen_items[item_id]),
                "payload_sha256": payload["sha256"],
                "sampling_plan_sha256": plan["plan_sha256"] if plan is not None else None,
                "sampled_content_semantic_sha256": sampled_semantic_sha,
                "validation_semantic_identity": validation_semantic_sha,
                "promotion_inputs_sha256": json_sha256(promotion_inputs),
                "sampled_normalized": sampled_normalized,
                "validation_normalized": validation_normalized,
                "promotion_inputs": promotion_inputs,
                "integrity": {
                    "payload_artifact_sha256": payload["sha256"],
                    "sampled_content_artifact_sha256": sampled_ref["sha256"],
                    "sampled_content_evidence_sha256": sampled["evidence_sha256"],
                    "validation_artifact_sha256": validation_ref["sha256"],
                    "validation_evidence_sha256": validation["evidence_sha256"],
                    "sampling_plan_artifact_sha256": (
                        plan_ref["sha256"] if plan_ref is not None else None
                    ),
                    "sampling_plan_sha256": plan["plan_sha256"] if plan is not None else None,
                },
            }
        )

    return {
        "batch_id": batch_id,
        "provenance": _run_provenance(input_manifest),
        "planning": copy.deepcopy(input_manifest["planning"]),
        "validation_context": copy.deepcopy(input_manifest["validation_context"]),
        "frozen_inputs": copy.deepcopy(input_manifest.get("frozen_inputs", {})),
        "summary": {
            "status": manifest["status"],
            "total": manifest["summary"]["total"],
            "execution_succeeded": manifest["summary"]["execution_succeeded"],
            "validation_passed": manifest["summary"]["validation_passed"],
            "review_pending": manifest["summary"]["review_pending"],
            "not_released": manifest["summary"]["not_released"],
            "not_published": manifest["summary"]["not_published"],
        },
        "items": items,
    }


def _compare_snapshots(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    specification: CoreSpecification = V04_CORE_SPEC,
) -> dict[str, Any]:
    if left["batch_id"] == right["batch_id"]:
        raise CoreRegressionError("Core determinism comparison requires two distinct batch IDs")
    for key in ("git_commit", "worktree_fingerprint", "immutable_fingerprint"):
        if left["provenance"][key] != right["provenance"][key]:
            raise CoreRegressionError(f"Core run provenance mismatch: {key}")
    for key in ("planning", "validation_context", "frozen_inputs"):
        if left[key] != right[key]:
            raise CoreRegressionError(f"Core run frozen context mismatch: {key}")

    left_items = {item["item_id"]: item for item in left["items"]}
    right_items = {item["item_id"]: item for item in right["items"]}
    records = []
    for item_id in CORE_ITEM_IDS:
        left_item = left_items[item_id]
        right_item = right_items[item_id]
        for key in (
            "frozen_item",
            "payload_sha256",
            "sampling_plan_sha256",
            "sampled_content_semantic_sha256",
            "validation_semantic_identity",
            "promotion_inputs_sha256",
        ):
            if left_item[key] != right_item[key]:
                raise CoreRegressionError(f"Core determinism mismatch for {item_id}: {key}")
        records.append(
            {
                "item_id": item_id,
                "payload_sha256": left_item["payload_sha256"],
                "sampling_plan_sha256": left_item["sampling_plan_sha256"],
                "sampled_content_semantic_sha256": left_item[
                    "sampled_content_semantic_sha256"
                ],
                "validation_semantic_identity": left_item[
                    "validation_semantic_identity"
                ],
                "promotion_inputs_sha256": left_item["promotion_inputs_sha256"],
                "left_integrity": copy.deepcopy(left_item["integrity"]),
                "right_integrity": copy.deepcopy(right_item["integrity"]),
            }
        )
    return {
        "status": "passed",
        "total_items": len(records),
        "matched_items": len(records),
        "items": records,
    }


def _verify_current_clean_context(root: Path, snapshot: Mapping[str, Any]) -> None:
    current = ProvenanceProvider(root).capture(allow_dirty=False)
    for key in ("git_commit", "worktree_fingerprint", "immutable_fingerprint"):
        if current[key] != snapshot["provenance"][key]:
            raise CoreRegressionError(f"Current repository context differs from Core runs: {key}")


def build_determinism_record(
    root: Path,
    *,
    runs_dir: Path,
    left_batch_id: str,
    right_batch_id: str,
    require_current_clean_context: bool = True,
    specification: CoreSpecification = V04_CORE_SPEC,
) -> dict[str, Any]:
    root = root.resolve()
    left = load_core_run_snapshot(
        root,
        runs_dir=runs_dir,
        batch_id=left_batch_id,
        specification=specification,
    )
    right = load_core_run_snapshot(
        root,
        runs_dir=runs_dir,
        batch_id=right_batch_id,
        specification=specification,
    )
    if require_current_clean_context:
        _verify_current_clean_context(root, left)
    comparison = _compare_snapshots(
        left, right, specification=specification
    )
    record = {
        "schema_version": "1.0",
        "record_type": COMPARATOR_ID,
        "comparator": {
            "id": COMPARATOR_ID,
            "sampled_normalization": SAMPLED_NORMALIZATION_ID,
            "validation_normalization": VALIDATION_NORMALIZATION_ID,
            "promotion_inputs_normalization": PROMOTION_INPUTS_NORMALIZATION_ID,
        },
        "left": {
            "batch_id": left["batch_id"],
            "provenance": copy.deepcopy(left["provenance"]),
            "summary": copy.deepcopy(left["summary"]),
        },
        "right": {
            "batch_id": right["batch_id"],
            "provenance": copy.deepcopy(right["provenance"]),
            "summary": copy.deepcopy(right["summary"]),
        },
        "common_inputs": {
            "planning": copy.deepcopy(left["planning"]),
            "validation_context": copy.deepcopy(left["validation_context"]),
            "frozen_inputs": copy.deepcopy(left["frozen_inputs"]),
            "items": [
                {
                    "item_id": item["item_id"],
                    "frozen_item_sha256": json_sha256(item["frozen_item"]),
                }
                for item in left["items"]
            ],
        },
        "comparison": comparison,
        "record_sha256": "",
    }
    record["record_sha256"] = json_sha256(
        {key: value for key, value in record.items() if key != "record_sha256"}
    )
    _validate_schema(root, DETERMINISM_RECORD_SCHEMA, record)
    return record


def write_determinism_record(path: Path, record: Mapping[str, Any]) -> None:
    rendered = render_json(record)
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current != rendered:
            raise CoreRegressionError(f"Determinism record already exists with different bytes: {path}")
        return
    write_json(path, record)


def create_determinism_record(
    root: Path,
    *,
    runs_dir: Path,
    left_batch_id: str,
    right_batch_id: str,
    output_path: Path,
    specification: CoreSpecification = V04_CORE_SPEC,
) -> dict[str, Any]:
    record = build_determinism_record(
        root,
        runs_dir=runs_dir,
        left_batch_id=left_batch_id,
        right_batch_id=right_batch_id,
        specification=specification,
    )
    write_determinism_record(output_path, record)
    return record


def verify_determinism_record(
    root: Path,
    *,
    runs_dir: Path,
    record_path: Path,
    specification: CoreSpecification = V04_CORE_SPEC,
) -> dict[str, Any]:
    record = read_json(record_path)
    _validate_schema(root, DETERMINISM_RECORD_SCHEMA, record)
    expected_sha = json_sha256(
        {key: value for key, value in record.items() if key != "record_sha256"}
    )
    if record["record_sha256"] != expected_sha:
        raise CoreRegressionError("Determinism record self hash drifted")
    rebuilt = build_determinism_record(
        root,
        runs_dir=runs_dir,
        left_batch_id=record["left"]["batch_id"],
        right_batch_id=record["right"]["batch_id"],
        require_current_clean_context=False,
        specification=specification,
    )
    if rebuilt != record:
        raise CoreRegressionError("Determinism record no longer matches its run evidence")
    return record


__all__ = [
    "COMPARATOR_ID",
    "CoreRegressionError",
    "build_determinism_record",
    "create_determinism_record",
    "load_core_run_snapshot",
    "normalize_promotion_inputs",
    "normalize_sampled_content",
    "normalize_validation",
    "verify_determinism_record",
]
