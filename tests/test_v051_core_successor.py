"""Candidate and closed-world tests for the v0.5.1 Core successor."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.core.product_catalog import sha256_file
from src.regression.core import (
    CORE_ITEM_IDS,
    V04_CORE_SPEC,
    V05_CORE_SPEC,
    CorePlanner,
    CoreRegressionError,
    build_fixture_manifest,
    json_sha256,
    promote_fixture_candidate,
    read_json,
    render_json,
    verify_baseline,
    verify_fixture_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
V05_CORE_BASELINE_BATCH_ID = "20260811T161324Z-64d20210"


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


def test_promoted_v05_core_fixture_is_exact_and_current() -> None:
    fixture_path = ROOT / V05_CORE_SPEC.fixture_manifest_path
    assert sha256_file(fixture_path) == (
        "881ca58bf893d5fe32e2bd65d6e508cf21fa72e5fec0ad35ff09a97eea0cdd67"
    )
    fixture = verify_fixture_manifest(ROOT, specification=V05_CORE_SPEC)
    assert json_sha256(fixture) == (
        "f6f8f82224408472aff308abd399ae00857d62bab2960d650cb888d0638dbb5c"
    )

    plan = CorePlanner(ROOT, specification=V05_CORE_SPEC).plan()
    assert plan.scope == {
        "kind": "group",
        "group": V05_CORE_SPEC.group,
    }
    assert plan.languages == ("zh-cn", "en-us")
    assert tuple(item.item_id for item in plan.items) == CORE_ITEM_IDS
    assert plan.summary == {
        "total": 8,
        "runnable": 8,
        "skipped": 0,
        "known_unsupported": 0,
        "source_unavailable": 0,
    }


def test_promoted_v05_core_baseline_is_exact_and_current() -> None:
    baseline_path = ROOT / V05_CORE_SPEC.baseline_manifest_path
    assert sha256_file(baseline_path) == (
        "c7a58b61e943f0918ec960ccdf6fb010dfa0d01a5b265817f8f9ecc5ae6fb622"
    )

    baseline = verify_baseline(ROOT, specification=V05_CORE_SPEC)
    assert baseline["source_batch_id"] == V05_CORE_BASELINE_BATCH_ID
    assert [item["item_id"] for item in baseline["items"]] == list(
        CORE_ITEM_IDS
    )
    assert baseline["frozen_inputs"]["planning_baseline"] == {
        "id": "v0.5.1-planning-baseline",
        "schema_version": "2.0",
        "path": "data/baselines/v0.5/planning-baseline.json",
        "sha256": "7855b23961faac8ece8505a2ad09e6964d28298167331e83e2ca14c02e350958",
    }
    assert baseline["predecessor_baseline"] == {
        "id": "v0.4-step6-core-baseline",
        "schema_version": "1.0",
        "path": "tests/fixtures/v0.4/core/baselines/baseline-manifest.json",
        "sha256": "46e16e1735ab35530cbec38613a19fad77bf519431a898104aa6e8a739167209",
    }

    baseline_root = ROOT / V05_CORE_SPEC.baseline_root
    rows = [
        f"{path.relative_to(baseline_root).as_posix()}\0"
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}"
        for path in sorted(baseline_root.rglob("*"))
        if path.is_file()
    ]
    assert len(rows) == 17
    assert hashlib.sha256("\n".join(rows).encode()).hexdigest() == (
        "fdc86c4461af4cd7f90b3be358da5112b11ebae694d3ff17d4b5ec8f3b18ce41"
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
