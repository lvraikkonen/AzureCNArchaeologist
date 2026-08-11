"""Candidate and closed-world tests for the v0.5.1 Core successor."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.core.product_catalog import sha256_file
from src.regression.core import (
    CORE_ITEM_IDS,
    V04_CORE_SPEC,
    V05_CORE_SPEC,
    CoreRegressionError,
    build_fixture_manifest,
    json_sha256,
    promote_fixture_candidate,
    read_json,
    render_json,
)


ROOT = Path(__file__).resolve().parents[1]


def test_v05_core_successor_uses_disjoint_artifact_paths() -> None:
    assert V05_CORE_SPEC.fixture_manifest_path != (
        V04_CORE_SPEC.fixture_manifest_path
    )
    assert V05_CORE_SPEC.baseline_root != V04_CORE_SPEC.baseline_root
    assert V05_CORE_SPEC.candidate_root != V04_CORE_SPEC.candidate_root
    assert V05_CORE_SPEC.predecessor_fixture_path == (
        V04_CORE_SPEC.fixture_manifest_path
    )
    assert V05_CORE_SPEC.predecessor_baseline_path == (
        V04_CORE_SPEC.baseline_manifest_path
    )


def test_v05_core_fixture_candidate_is_closed_world_and_current() -> None:
    candidate = build_fixture_manifest(ROOT, V05_CORE_SPEC)
    schema = read_json(ROOT / V05_CORE_SPEC.fixture_schema)
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(candidate))
    assert errors == []

    assert candidate["manifest_id"] == "v0.5.1-core-fixture"
    assert candidate["matrix_id"] == "v0.5-core-strategy-matrix"
    assert candidate["expected_item_ids"] == list(CORE_ITEM_IDS)
    assert [item["item_id"] for item in candidate["items"]] == list(
        CORE_ITEM_IDS
    )
    assert candidate["frozen_inputs"]["planning_baseline"] == {
        "id": "v0.5.1-planning-baseline",
        "schema_version": "2.0",
        "path": "data/baselines/v0.5/planning-baseline.json",
        "sha256": sha256_file(
            ROOT / "data/baselines/v0.5/planning-baseline.json"
        ),
    }
    assert candidate["predecessor_fixture"]["sha256"] == sha256_file(
        ROOT / V04_CORE_SPEC.fixture_manifest_path
    )


def test_v05_core_fixture_candidate_declares_only_four_reviewed_changes() -> None:
    candidate = build_fixture_manifest(ROOT, V05_CORE_SPEC)
    changes = candidate["reviewed_input_changes"]
    assert [change["change_id"] for change in changes] == [
        "V051-CORE-PLANNING-SUCCESSOR",
        "V051-CORE-SOFT-CATEGORY",
        "V051-CORE-CLOUD-SERVICES-EN-US",
        "V051-CORE-CLOUD-SERVICES-ZH-CN",
    ]
    assert [change["kind"] for change in changes] == [
        "planning_baseline",
        "soft_category",
        "source_snapshot",
        "source_snapshot",
    ]
    assert all(
        change["prior"] != change["successor"] for change in changes
    )


def test_v05_fixture_promotion_requires_exact_candidate_sha(
    tmp_path: Path,
) -> None:
    candidate = build_fixture_manifest(ROOT, V05_CORE_SPEC)
    path = tmp_path / "fixture-manifest.candidate.json"
    path.write_text(render_json(candidate), encoding="utf-8")

    with pytest.raises(
        CoreRegressionError,
        match="Fixture candidate SHA does not match expected SHA",
    ):
        promote_fixture_candidate(
            ROOT,
            candidate_path=path,
            expected_sha256="0" * 64,
            specification=V05_CORE_SPEC,
        )

    drifted = copy.deepcopy(candidate)
    drifted["description"] += " drift"
    assert json_sha256(drifted) != json_sha256(candidate)
