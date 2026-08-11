from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.regression.planning_v05 import (
    BASELINE_SCHEMA,
    CANDIDATE_SCHEMA,
    EXPECTED_CHANGED_ITEM_IDS,
    PlanningBaselineError,
    build_planning_baseline,
    create_planning_candidate,
    promote_planning_candidate,
)


ROOT = Path(__file__).resolve().parents[1]


def test_v05_planning_baseline_is_closed_world_and_identity_light() -> None:
    baseline = build_planning_baseline(ROOT)

    assert baseline["summary"] == {
        "total": 434,
        "runnable": 383,
        "skipped": 51,
        "known_unsupported": 50,
        "source_unavailable": 1,
    }
    assert baseline["accounting"] == {
        "reviewed_items": 434,
        "coverage": "434/434",
        "runnable": 383,
        "skipped": 51,
    }
    assert baseline["predecessor"]["planning_baseline"]["id"] == (
        "v0.4-p2-product-definition-identity-overlay"
    )
    assert len(baseline["items"]) == 434
    assert tuple(change["item_id"] for change in baseline["changes"]) == (
        EXPECTED_CHANGED_ITEM_IDS
    )
    assert all(change["denominator_impact"] == 1 for change in baseline["changes"])
    assert sum(
        item["planned_state"] == "runnable" for item in baseline["items"]
    ) == 383
    forbidden_item_keys = {
        "source",
        "normalized_input",
        "product_definition",
        "payload",
        "sha256",
    }
    assert all(
        not (forbidden_item_keys & set(item)) for item in baseline["items"]
    )


def test_v05_planning_schemas_are_valid_and_closed_world() -> None:
    for relative_path in (BASELINE_SCHEMA, CANDIDATE_SCHEMA):
        schema = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)

    baseline = build_planning_baseline(ROOT)
    baseline["unexpected"] = True
    schema = json.loads((ROOT / BASELINE_SCHEMA).read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(baseline))


def test_planning_candidate_is_deterministic_and_has_exact_four_item_diff(
    tmp_path: Path,
) -> None:
    first_dir, first = create_planning_candidate(
        ROOT, candidate_root=tmp_path / "candidates"
    )
    second_dir, second = create_planning_candidate(
        ROOT, candidate_root=tmp_path / "candidates"
    )

    assert first_dir == second_dir
    assert first == second
    state_diff = json.loads(
        (first_dir / first["state_diff"]["path"]).read_text(encoding="utf-8")
    )
    assert tuple(
        change["item_id"] for change in state_diff["changed_items"]
    ) == EXPECTED_CHANGED_ITEM_IDS
    assert state_diff["unchanged_item_count"] == 430


def test_planning_candidate_promotion_requires_exact_sha(tmp_path: Path) -> None:
    candidate_dir, candidate = create_planning_candidate(
        ROOT, candidate_root=tmp_path / "candidates"
    )
    isolated = tmp_path / "isolated"
    schema_target = isolated / CANDIDATE_SCHEMA
    schema_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / CANDIDATE_SCHEMA, schema_target)
    baseline_schema_target = isolated / BASELINE_SCHEMA
    baseline_schema_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / BASELINE_SCHEMA, baseline_schema_target)

    with pytest.raises(PlanningBaselineError, match="Candidate SHA"):
        promote_planning_candidate(
            isolated,
            candidate_dir=candidate_dir,
            expected_sha256="0" * 64,
        )

    promoted = promote_planning_candidate(
        isolated,
        candidate_dir=candidate_dir,
        expected_sha256=candidate["candidate_sha256"],
    )
    target = isolated / promoted["target_path"]
    assert target.is_file()
    assert json.loads(target.read_text(encoding="utf-8"))[
        "baseline_id"
    ] == "v0.5.1-planning-baseline"
