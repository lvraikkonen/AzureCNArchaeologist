from __future__ import annotations

import copy
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from src.independent_fidelity.formal_target import (
    BATCH_MANIFEST_PATH,
    CANONICAL_BUNDLE_PREFIX,
    EXPECTED_STATE_IDS,
    FormalBindingError,
    INPUT_MANIFEST_PATH,
    InventoryEntry,
    NORMALIZED_INPUT_PATH,
    PAYLOAD_PATH,
    PRODUCT_DEFINITION_PATH,
    PROFILE_PATH,
    SAMPLED_EVIDENCE_PATH,
    SAMPLING_PLAN_PATH,
    SOFT_CATEGORY_PATH,
    SOURCE_PATH,
    ScopeGuardError,
    TARGET_BATCH_ID,
    TARGET_ITEM_ID,
    VALIDATION_PATH,
    bind_formal_target,
    compare_add_only_inventories,
    enforce_target_allowlist,
    inventory_regular_files,
    qualify_bound_target,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def formal_target():
    return bind_formal_target(ROOT)


def test_exact_formal_target_preflight_is_read_only_and_current(formal_target) -> None:
    assert formal_target.batch_manifest["revision"] == 1483
    assert formal_target.batch_item["status"]["execution"] == "succeeded"
    assert formal_target.batch_item["status"]["validation"] == "passed"
    assert formal_target.source_html == formal_target.normalized_html
    assert formal_target.l3a_summary["claim"] == (
        "sampled_state_content_consistency"
    )
    assert formal_target.l3a_summary["verdict"] == "passed"
    assert formal_target.l3a_summary["coverage"] == {
        "universe_count": 5,
        "selected_count": 5,
        "untested_count": 0,
    }
    assert tuple(
        state["state_id"]
        for state in formal_target.sampling_plan["state_universe"]["states"]
    ) == EXPECTED_STATE_IDS
    inventory_paths = {
        entry.relative_path for entry in formal_target.pre_record_inventory
    }
    assert "input-manifest.json" in inventory_paths
    assert "batch-manifest.json" in inventory_paths
    assert PAYLOAD_PATH.as_posix() in inventory_paths
    assert qualify_bound_target(formal_target).qualified is True


def test_v052_scope_guard_is_not_profile_qualification() -> None:
    enforce_target_allowlist(TARGET_BATCH_ID, TARGET_ITEM_ID)
    with pytest.raises(ScopeGuardError, match="only allows"):
        enforce_target_allowlist(TARGET_BATCH_ID, "en-us/api-management")
    with pytest.raises(ScopeGuardError, match="only allows"):
        enforce_target_allowlist("latest", TARGET_ITEM_ID)


def test_profile_not_qualified_is_separate_from_allowlist(formal_target) -> None:
    unsupported_item = copy.deepcopy(formal_target.batch_item)
    unsupported_item["strategy"] = "support_article"
    unsupported = replace(formal_target, batch_item=unsupported_item)
    qualification = qualify_bound_target(unsupported)
    assert qualification.qualified is False
    assert qualification.claim == "independent_source_content_fidelity"
    assert "not qualified" in qualification.reason


def _copy_preflight_fixture(destination: Path) -> None:
    repository_files = (
        INPUT_MANIFEST_PATH,
        BATCH_MANIFEST_PATH,
        SOURCE_PATH,
        NORMALIZED_INPUT_PATH,
        PRODUCT_DEFINITION_PATH,
        SOFT_CATEGORY_PATH,
        PROFILE_PATH,
    )
    run_files = (
        PAYLOAD_PATH,
        VALIDATION_PATH,
        SAMPLING_PLAN_PATH,
        SAMPLED_EVIDENCE_PATH,
    )
    schema_names = (
        "pipeline-input-manifest-2.0.schema.json",
        "pipeline-batch-manifest-2.0.schema.json",
        "pipeline-validation-2.1.schema.json",
        "batch-item-sampling-plan-1.0.schema.json",
        "sampled-content-evidence-1.0.schema.json",
        "independent-fidelity-profile-1.0.schema.json",
    )
    for relative in repository_files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    run_dir = ROOT / "runs" / TARGET_BATCH_ID
    target_run_dir = destination / "runs" / TARGET_BATCH_ID
    for relative in run_files:
        target = target_run_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(run_dir / relative, target)
    for name in schema_names:
        target = destination / "schemas" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "schemas" / name, target)


def test_frozen_source_drift_is_fatal_before_reconstruction(tmp_path: Path) -> None:
    _copy_preflight_fixture(tmp_path)
    source = tmp_path / SOURCE_PATH
    source.write_bytes(source.read_bytes() + b"<!-- drift -->")
    with pytest.raises(FormalBindingError) as raised:
        bind_formal_target(tmp_path)
    assert raised.value.code == "frozen_sha256_mismatch"
    assert SOURCE_PATH.as_posix() in str(raised.value)


def test_current_manifest_drift_is_fatal_before_reconstruction(
    tmp_path: Path,
) -> None:
    _copy_preflight_fixture(tmp_path)
    manifest = tmp_path / BATCH_MANIFEST_PATH
    manifest.write_bytes(manifest.read_bytes().replace(b'"revision": 1483', b'"revision": 1484'))
    with pytest.raises(FormalBindingError) as raised:
        bind_formal_target(tmp_path)
    assert raised.value.code == "frozen_sha256_mismatch"
    assert BATCH_MANIFEST_PATH.as_posix() in str(raised.value)


def test_closed_world_inventory_allows_only_new_canonical_bundle_files(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "outputs").mkdir(parents=True)
    (run_dir / "outputs/item.json").write_text("{}\n", encoding="utf-8")
    before = inventory_regular_files(run_dir)

    canonical = run_dir / CANONICAL_BUNDLE_PREFIX
    canonical.mkdir(parents=True)
    (canonical / "evidence.json").write_text("{}\n", encoding="utf-8")
    after = inventory_regular_files(run_dir)
    comparison = compare_add_only_inventories(before, after)
    assert comparison.valid is True
    assert comparison.allowed_additions == (
        f"{CANONICAL_BUNDLE_PREFIX.as_posix()}/evidence.json",
    )

    (run_dir / "outputs/item.json").write_text('{"drift":true}\n', encoding="utf-8")
    (run_dir / "unexpected.txt").write_text("new", encoding="utf-8")
    drifted = compare_add_only_inventories(
        before, inventory_regular_files(run_dir)
    )
    assert drifted.valid is False
    assert drifted.changed_paths == ("outputs/item.json",)
    assert drifted.additions_outside_prefix == ("unexpected.txt",)


def test_inventory_uses_regular_files_and_ignores_directories(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "nested").mkdir(parents=True)
    (run_dir / "nested/file.txt").write_text("evidence", encoding="utf-8")
    inventory = inventory_regular_files(run_dir)
    assert inventory == (
        InventoryEntry(
                relative_path="nested/file.txt",
                sha256=(
                    "ee8250fb76e094b34b471f13a73dbbe51d1ae142e9df59d7c0d31ec20f0a0a8e"
                ),
        ),
    )
