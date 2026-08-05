from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.regression.core import (
    BASELINE_ROOT,
    CORE_GROUP,
    CORE_ITEM_IDS,
    CorePlanner,
    CoreRegressionError,
    build_baseline_documents,
    json_sha256,
    promote_baseline_candidate,
    read_json,
    render_json,
    verify_baseline,
    verify_fixture_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
CORE_BASELINE_BATCH_ID = "20260805T094417Z-d1b25bff"


def test_core_fixture_manifest_is_current_and_closed_world() -> None:
    manifest = verify_fixture_manifest(ROOT)

    assert manifest["matrix_id"] == CORE_GROUP
    assert manifest["expected_item_ids"] == list(CORE_ITEM_IDS)
    assert [item["item_id"] for item in manifest["items"]] == list(CORE_ITEM_IDS)
    assert {item["strategy"] for item in manifest["items"]} == {
        "simple_static",
        "region_filter",
        "complex",
        "support_article",
    }
    assert all(item["resource_kind"] == "current" for item in manifest["items"])
    assert all(item["capability_status"] == "supported" for item in manifest["items"])

    icp_items = [
        item for item in manifest["items"] if item["resource_key"] == "icp-faq"
    ]
    assert len(icp_items) == 2
    assert {item["language"] for item in icp_items} == {"zh-cn", "en-us"}
    assert len({item["source"]["sha256"] for item in icp_items}) == 1
    assert len({item["normalized_input"]["sha256"] for item in icp_items}) == 1
    assert all("controlled_source_reuse" in item for item in icp_items)
    assert all(
        item["controlled_source_reuse"]["claim"]
        == "separate_language_batch_items_without_english_translation_assertion"
        for item in icp_items
    )


def test_core_planner_returns_exact_group_plan() -> None:
    plan = CorePlanner(ROOT).plan(scope="group", group=CORE_GROUP, language="both")

    assert plan.scope == {"kind": "group", "group": CORE_GROUP}
    assert plan.languages == ("zh-cn", "en-us")
    assert tuple(item.item_id for item in plan.items) == CORE_ITEM_IDS
    assert plan.summary == {
        "total": 8,
        "runnable": 8,
        "skipped": 0,
        "known_unsupported": 0,
        "source_unavailable": 0,
    }


@pytest.mark.parametrize(
    ("scope", "group", "language"),
    [
        ("all", None, "both"),
        ("group", "integration", "both"),
        ("group", CORE_GROUP, "zh-cn"),
    ],
)
def test_core_planner_rejects_non_core_scope(
    scope: str,
    group: str | None,
    language: str,
) -> None:
    with pytest.raises(CoreRegressionError):
        CorePlanner(ROOT).plan(scope=scope, group=group, language=language)


def test_fixture_hash_drift_fails_closed(tmp_path: Path) -> None:
    drifted = copy.deepcopy(read_json(ROOT / "tests/fixtures/v0.4/core/fixture-manifest.json"))
    drifted["items"][0]["source"]["sha256"] = "0" * 64
    fixture_path = tmp_path / "fixture-manifest.json"
    fixture_path.write_text(render_json(drifted), encoding="utf-8")

    with pytest.raises(CoreRegressionError, match="drifted"):
        verify_fixture_manifest(ROOT, fixture_path)


def test_candidate_promotion_requires_exact_sha(tmp_path: Path) -> None:
    proposed = {"schema_version": "1.0", "value": "candidate"}
    rendered = render_json(proposed)
    new_sha = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    candidate_dir = tmp_path / "candidate"
    proposed_path = candidate_dir / "proposed" / "baseline-manifest.json"
    proposed_path.parent.mkdir(parents=True)
    proposed_path.write_text(rendered, encoding="utf-8")
    candidate = {
        "schema_version": "1.0",
        "candidate_id": "candidate",
        "baseline_id": "v0.4-step6-core-baseline",
        "source_batch_id": "20260805T000000Z-deadbeef",
        "reason": "unit-test",
        "generated_at": "2026-08-05T00:00:00Z",
        "baseline_root": BASELINE_ROOT.as_posix(),
        "files": [
            {
                "path": "baseline-manifest.json",
                "old_sha256": None,
                "new_sha256": new_sha,
                "status": "added",
            }
        ],
        "candidate_sha256": "0" * 64,
    }
    candidate["candidate_sha256"] = json_sha256(
        {key: value for key, value in candidate.items() if key != "candidate_sha256"}
    )
    (candidate_dir / "candidate-manifest.json").write_text(
        render_json(candidate),
        encoding="utf-8",
    )

    with pytest.raises(CoreRegressionError, match="Candidate SHA"):
        promote_baseline_candidate(
            ROOT,
            candidate_dir=candidate_dir,
            expected_sha256="1" * 64,
        )


def test_candidate_schema_is_closed_world() -> None:
    schema = read_json(ROOT / "schemas/step6-core-baseline-candidate-1.0.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    candidate = {
        "schema_version": "1.0",
        "candidate_id": "candidate",
        "baseline_id": "v0.4-step6-core-baseline",
        "source_batch_id": "20260805T000000Z-deadbeef",
        "reason": "unit-test",
        "generated_at": "2026-08-05T00:00:00Z",
        "baseline_root": BASELINE_ROOT.as_posix(),
        "files": [],
        "candidate_sha256": "0" * 64,
        "unexpected": True,
    }

    errors = list(validator.iter_errors(candidate))
    assert errors
    assert any("Additional properties" in error.message for error in errors)


def test_committed_core_baselines_are_complete_and_self_consistent() -> None:
    manifest = verify_baseline(ROOT)

    assert manifest["source_batch_id"] == CORE_BASELINE_BATCH_ID
    assert [item["item_id"] for item in manifest["items"]] == list(CORE_ITEM_IDS)
    assert {
        item["validation"]["validation_profile"]["id"]
        for item in (
            read_json(ROOT / BASELINE_ROOT / entry["content_baseline"])
            for entry in manifest["items"]
        )
    } == {"v0.4-validation-p3-successor"}
    assert all(
        item["validation"]["finding_code_policy"]["id"]
        == "v0.4-finding-code-policy-p4"
        for item in (
            read_json(ROOT / BASELINE_ROOT / entry["content_baseline"])
            for entry in manifest["items"]
        )
    )


def test_core_baseline_batch_rebuilds_committed_baseline_documents() -> None:
    run_dir = ROOT / "runs" / CORE_BASELINE_BATCH_ID
    if not run_dir.is_dir():
        pytest.skip(f"Core baseline batch is not present locally: {CORE_BASELINE_BATCH_ID}")

    expected = {
        path.relative_to(ROOT / BASELINE_ROOT).as_posix(): read_json(path)
        for path in sorted((ROOT / BASELINE_ROOT).rglob("*.json"))
    }
    actual = build_baseline_documents(
        ROOT,
        runs_dir=Path("runs"),
        batch_id=CORE_BASELINE_BATCH_ID,
        reason="establish-v0.4-step6-core-baseline",
    )

    assert actual == expected


def test_service_bus_baseline_declares_sampling_not_applicable() -> None:
    for language in ("zh-cn", "en-us"):
        baseline = read_json(
            ROOT / BASELINE_ROOT / language / "service-bus.content.json"
        )
        assert baseline["sampling_semantics"] == "not_applicable"
        assert baseline["sampling_plan"] is None
        assert baseline["content_mode"] == "full_content"
        assert baseline["sampled_evidence_mode"] == "full"


def test_icp_faq_baseline_freezes_support_article_boundaries() -> None:
    for language in ("zh-cn", "en-us"):
        payload = read_json(ROOT / BASELINE_ROOT / language / "icp-faq.payload.json")
        assert set(payload) == {
            "title",
            "slug",
            "pageType",
            "articleDescription",
            "mainContent",
        }
        assert payload["slug"] == "icp-faq"
        assert payload["pageType"] == "ICP"
        assert payload["mainContent"].startswith("<h2>")
