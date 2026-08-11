"""Focused tests for the read-only v0.5.1 reference Batch auditor."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.regression.reference_batch_v051 import (
    ReferenceBatchError,
    _materialize_planned_artifact,
    compare_batch_documents,
    failure_groups,
    load_regression_rationales,
    semantic_sha256,
    verify_review_queue_projection,
)


def _input_item(
    item_id: str,
    *,
    state: str = "runnable",
    source_sha: str = "1" * 64,
) -> dict[str, object]:
    language, resource = item_id.split("/", 1)
    return {
        "item_id": item_id,
        "capability_status": (
            "known_unsupported" if state == "known_unsupported" else "supported"
        ),
        "config": {"path": f"config/{resource}.json", "sha256": "2" * 64},
        "normalized_input": {
            "path": f"normalized/{language}/{resource}.html",
            "sha256": source_sha,
        },
        "page_model": "FlexibleContentPage",
        "product_key": resource,
        "resource": {"kind": "current", "slug": resource},
        "skip_reason": (
            {
                "code": "KNOWN_UNSUPPORTED",
                "message": "not_yet_qualified_for_extraction",
            }
            if state == "known_unsupported"
            else None
        ),
        "source": {
            "path": f"source/{language}/{resource}.html",
            "sha256": source_sha,
        },
        "strategy": "simple_static",
        "support_article_type": None,
    }


def _batch_item(
    item_id: str,
    *,
    execution: str,
    validation: str,
    payload_sha: str | None,
    code: str = "fixture_failure",
    message: str = "fixture failed closed",
) -> dict[str, object]:
    return {
        "item_id": item_id,
        "status": {"execution": execution, "validation": validation},
        "error": (
            {"stage": "extract", "code": code, "message": message}
            if execution == "failed"
            else None
        ),
        "artifacts": {
            "payload": {"path": f"outputs/{item_id}.json", "sha256": payload_sha}
        },
    }


def _input_manifest(*items: dict[str, object]) -> dict[str, object]:
    return {"items": list(items)}


def _batch_manifest(
    batch_id: str,
    *items: dict[str, object],
) -> dict[str, object]:
    return {
        "batch_id": batch_id,
        "items": {str(item["item_id"]): item for item in items},
    }


def test_reference_comparison_separates_inputs_outcomes_and_regressions() -> None:
    old_input = _input_manifest(
        _input_item("en-us/regressed"),
        _input_item("en-us/improved"),
        _input_item("en-us/new-scope", state="known_unsupported"),
    )
    new_input = _input_manifest(
        _input_item("en-us/regressed"),
        _input_item("en-us/improved"),
        _input_item("en-us/new-scope", source_sha="3" * 64),
    )
    old_batch = _batch_manifest(
        "20260809T030936Z-ce23e678",
        _batch_item(
            "en-us/regressed",
            execution="succeeded",
            validation="passed",
            payload_sha="4" * 64,
        ),
        _batch_item(
            "en-us/improved",
            execution="failed",
            validation="not_run",
            payload_sha=None,
        ),
        _batch_item(
            "en-us/new-scope",
            execution="skipped",
            validation="not_run",
            payload_sha=None,
        ),
    )
    new_batch = _batch_manifest(
        "20260811T180000Z-cafebabe",
        _batch_item(
            "en-us/regressed",
            execution="failed",
            validation="not_run",
            payload_sha=None,
        ),
        _batch_item(
            "en-us/improved",
            execution="succeeded",
            validation="passed",
            payload_sha="5" * 64,
        ),
        _batch_item(
            "en-us/new-scope",
            execution="failed",
            validation="not_run",
            payload_sha=None,
        ),
    )

    report = compare_batch_documents(
        old_input,
        old_batch,
        new_input,
        new_batch,
        regression_rationales={"en-us/regressed": "Reviewed fixture regression."},
    )

    assert report["membership"] == {
        "predecessor_count": 3,
        "current_count": 3,
        "common_count": 3,
        "added_item_ids": [],
        "removed_item_ids": [],
    }
    assert report["planning_transitions"] == [
        {
            "item_id": "en-us/new-scope",
            "old": "known_unsupported",
            "new": "runnable",
        }
    ]
    assert [row["item_id"] for row in report["input_identity_changes"]] == [
        "en-us/new-scope"
    ]
    assert report["improvements"] == ["en-us/improved"]
    assert report["regressions"][0]["explanation"] == (
        "Reviewed fixture regression."
    )
    assert report["unexplained_regression_item_ids"] == []
    assert {row["item_id"] for row in report["payload_sha_changes"]} == {
        "en-us/improved",
        "en-us/regressed",
    }


def test_reference_comparison_exposes_unexplained_regression() -> None:
    old_input = _input_manifest(_input_item("zh-cn/example"))
    new_input = _input_manifest(_input_item("zh-cn/example"))
    old_batch = _batch_manifest(
        "old",
        _batch_item(
            "zh-cn/example",
            execution="succeeded",
            validation="passed",
            payload_sha="6" * 64,
        ),
    )
    new_batch = _batch_manifest(
        "new",
        _batch_item(
            "zh-cn/example",
            execution="failed",
            validation="not_run",
            payload_sha=None,
        ),
    )

    report = compare_batch_documents(old_input, old_batch, new_input, new_batch)

    assert report["unexplained_regression_item_ids"] == ["zh-cn/example"]
    with pytest.raises(ReferenceBatchError, match="non-regressions"):
        compare_batch_documents(
            old_input,
            old_batch,
            new_input,
            new_batch,
            regression_rationales={"zh-cn/not-present": "invalid"},
        )


def test_failure_groups_are_stable_and_preserve_item_ids() -> None:
    items = {
        item_id: _batch_item(
            item_id,
            execution="failed",
            validation="not_run",
            payload_sha=None,
            code="same_code",
            message="same message",
        )
        for item_id in ("zh-cn/b", "en-us/a")
    }

    assert failure_groups(items) == [
        {
            "stage": "extract",
            "code": "same_code",
            "message": "same message",
            "count": 2,
            "item_ids": ["en-us/a", "zh-cn/b"],
        }
    ]


def test_regression_rationale_is_closed_world_and_bound(tmp_path: Path) -> None:
    rationale = {
        "schema_version": "1.0",
        "predecessor_batch_id": "old",
        "reference_batch_id": "new",
        "regressions": [
            {"item_id": "en-us/example", "explanation": "Reviewed."}
        ],
    }
    path = tmp_path / "rationale.json"
    path.write_text(json.dumps(rationale), encoding="utf-8")

    values, identity = load_regression_rationales(
        tmp_path,
        Path("rationale.json"),
        predecessor_batch_id="old",
        reference_batch_id="new",
    )

    assert values == {"en-us/example": "Reviewed."}
    assert identity is not None
    assert identity["path"] == "rationale.json"
    assert len(identity["sha256"]) == 64

    rationale["unexpected"] = True
    path.write_text(json.dumps(rationale), encoding="utf-8")
    with pytest.raises(ReferenceBatchError, match="closed-world"):
        load_regression_rationales(
            tmp_path,
            Path("rationale.json"),
            predecessor_batch_id="old",
            reference_batch_id="new",
        )


def test_semantic_identity_is_order_independent() -> None:
    assert semantic_sha256({"a": 1, "b": 2}) == semantic_sha256({"b": 2, "a": 1})


def test_review_queue_may_bind_earlier_revision_but_not_stale_items() -> None:
    item = _batch_item(
        "en-us/example",
        execution="succeeded",
        validation="passed",
        payload_sha="7" * 64,
    )
    batch = {
        "revision": 13,
        "items": {"en-us/example": item},
    }
    queue = {
        "manifest_revision": 10,
        "items": [
            {
                "item_id": "en-us/example",
                "status": item["status"],
                "artifacts": item["artifacts"],
            }
        ],
    }

    verify_review_queue_projection(
        queue,
        batch,
        expected_item_ids={"en-us/example"},
    )

    queue["manifest_revision"] = 14
    with pytest.raises(ReferenceBatchError, match="ahead"):
        verify_review_queue_projection(
            queue,
            batch,
            expected_item_ids={"en-us/example"},
        )

    queue["manifest_revision"] = 10
    queue["items"][0]["artifacts"] = {
        "payload": {"path": "outputs/drifted.json", "sha256": "8" * 64}
    }
    with pytest.raises(ReferenceBatchError, match="artifact is stale"):
        verify_review_queue_projection(
            queue,
            batch,
            expected_item_ids={"en-us/example"},
        )


def test_planned_artifact_materializes_observed_identity_when_sha_is_null(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "diagnostics" / "parseability.json"
    artifact_path.parent.mkdir()
    artifact_path.write_text('{"parseable": false}\n', encoding="utf-8")

    identity = _materialize_planned_artifact(
        tmp_path,
        {"path": "diagnostics/parseability.json", "sha256": None},
        label="fixture parseability",
    )

    assert identity == {
        "path": "diagnostics/parseability.json",
        "batch_manifest_sha256": None,
        "observed_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
    }

    with pytest.raises(ReferenceBatchError, match="bound SHA-256 drifted"):
        _materialize_planned_artifact(
            tmp_path,
            {
                "path": "diagnostics/parseability.json",
                "sha256": "0" * 64,
            },
            label="fixture parseability",
        )
