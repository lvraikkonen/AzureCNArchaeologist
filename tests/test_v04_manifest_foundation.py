"""Fail-closed integration tests for v0.4 Manifest 2.0 foundations."""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest

import scripts.build_v04_p2_planning_overlay as overlay_builder
import scripts.build_v04_p2_validation_profile as profile_builder
from src.core.product_catalog import sha256_file
from src.core.validation_context import (
    ARTIFACT_SPECS,
    P1_PLANNING_BASELINE_SPEC,
    P1_VALIDATION_PROFILE_SPEC,
    P2_AMENDED_ITEM_IDS,
    P3_SUCCESSOR_VALIDATION_PROFILE_SPEC,
    P3_SUCCESSOR_VALIDATION_CONTRACT_SPECS,
    P2_VALIDATION_PROFILE_SPEC,
    P3_VALIDATION_CONTRACT_SPECS,
    P3_VALIDATION_PROFILE_SPEC,
    ValidationContextError,
    ValidationContextRegistry,
)
from src.pipeline.models import BatchManifest, InputManifest, PipelinePlan
from src.pipeline.planner import PipelinePlanner
from src.pipeline.state_store import (
    ImmutableManifestError,
    ManifestValidationError,
    RepositoryLock,
    StateStore,
)


ROOT = Path(__file__).resolve().parents[1]
BATCH_ID = "20260722T120000Z-deadbeef"
CREATED_AT = "2026-07-22T12:00:00Z"
FROZEN_PROVENANCE = {
    "schema_version": "1.0",
    "captured_at": CREATED_AT,
    "git_commit": "0" * 40,
    "dirty": False,
    "reproducible": True,
    "worktree_changes": [],
    "worktree_fingerprint": f"sha256:{'0' * 64}",
    "immutable_fingerprint": f"sha256:{'0' * 64}",
    "immutable_files": {},
}


@lru_cache(maxsize=1)
def _manifest() -> InputManifest:
    registry = ValidationContextRegistry(ROOT)
    # Keep this state-store fixture independent of the intentionally edited
    # Databricks/SSIS snapshots while still exercising an amended Product
    # Definition through service-bus.
    plan = PipelinePlanner(ROOT).plan(
        "group", group="integration", language="zh-cn"
    )
    registry.assert_plan_matches_baseline(plan)
    frozen = registry.freeze()
    return InputManifest.from_plan(
        BATCH_ID,
        plan,
        FROZEN_PROVENANCE,
        created_at=CREATED_AT,
        planning=frozen["planning"],
        validation_context=frozen["validation_context"],
    )


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _copy_registry_artifacts(root: Path) -> None:
    copied: set[str] = set()
    for specification in ARTIFACT_SPECS:
        for relative_path in (
            specification.relative_path,
            specification.schema_path,
        ):
            if relative_path in copied:
                continue
            copied.add(relative_path)
            target = root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative_path, target)
    for specification in (
        *P3_VALIDATION_CONTRACT_SPECS,
        *P3_SUCCESSOR_VALIDATION_CONTRACT_SPECS,
    ):
        relative_path = specification.relative_path
        if relative_path in copied:
            continue
        copied.add(relative_path)
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative_path, target)


def test_real_manifest_20_round_trip_replays_frozen_context() -> None:
    registry = ValidationContextRegistry(ROOT)
    frozen = registry.freeze()
    registry.verify_frozen(frozen["planning"], frozen["validation_context"])

    with tempfile.TemporaryDirectory() as directory:
        store = StateStore(ROOT, runs_dir=Path(directory) / "runs")
        store.create_run(_manifest())
        input_manifest = store.read_input_manifest(BATCH_ID)
        batch_manifest = store.read_manifest(BATCH_ID)

        assert input_manifest["schema_version"] == "2.0"
        assert batch_manifest["schema_version"] == "2.0"
        assert batch_manifest["planning"] == input_manifest["planning"]
        assert (
            batch_manifest["validation_context"]
            == input_manifest["validation_context"]
        )
        assert input_manifest["summary"] == {
            "total": 4,
            "runnable": 2,
            "skipped": 2,
            "known_unsupported": 2,
            "source_unavailable": 0,
        }


def test_warm_manifest_cache_cannot_conceal_input_tampering() -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = StateStore(ROOT, runs_dir=Path(directory) / "runs")
        run_dir = store.create_run(_manifest())
        store.read_manifest(BATCH_ID)

        input_path = run_dir / "input-manifest.json"
        input_path.write_text(
            input_path.read_text(encoding="utf-8") + " ", encoding="utf-8"
        )

        with RepositoryLock(
            store.lock_root,
            batch_id=BATCH_ID,
            command="manifest-foundation-test",
        ):
            with pytest.raises(ImmutableManifestError, match="hash mismatch"):
                store.update_manifest(
                    BATCH_ID,
                    lambda value: value.update({"status": "running"}),
                    expected_revision=0,
                )


def test_warm_reads_skip_full_schema_revalidation(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = StateStore(ROOT, runs_dir=Path(directory) / "runs")
        store.create_run(_manifest())

        def unexpected_revalidation(*args: object, **kwargs: object) -> None:
            raise AssertionError("unchanged validated bytes were fully revalidated")

        monkeypatch.setattr(store, "_validate", unexpected_revalidation)
        monkeypatch.setattr(
            store._validation_context,
            "_validate_schema",
            unexpected_revalidation,
        )

        # create_run cached documents only after successful validation.  A
        # subsequent read still hashes every document/context artifact, but
        # unchanged bytes do not traverse either full JSON Schema again.
        batch = store.read_manifest(BATCH_ID)
        assert batch["schema_version"] == "2.0"


def test_mixed_input_and_batch_manifest_versions_are_rejected() -> None:
    input_v2 = _manifest().to_dict()
    input_v1 = copy.deepcopy(input_v2)
    input_v1["schema_version"] = "1.0"
    input_v1.pop("planning")
    input_v1.pop("validation_context")
    input_v1.pop("frozen_inputs", None)
    for item in input_v1["items"]:
        item["artifacts"].pop("parseability")

    batch_v2 = BatchManifest.from_input_manifest(input_v2).to_dict()

    with tempfile.TemporaryDirectory() as directory:
        store = StateStore(ROOT, runs_dir=Path(directory) / "runs")
        run_dir = store.run_dir(BATCH_ID)
        input_path = run_dir / "input-manifest.json"
        _write_json(input_path, input_v1)
        batch_v2["input_manifest"]["sha256"] = sha256_file(input_path)
        _write_json(run_dir / "batch-manifest.json", batch_v2)

        # Prove both documents independently satisfy their declared schemas;
        # only pairing different immutable-manifest generations is forbidden.
        store.validate_document(input_v1, "input")
        store.validate_document(batch_v2, "batch")
        with pytest.raises(
            ImmutableManifestError, match="schema versions differ"
        ):
            store.read_manifest(BATCH_ID)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("id", "v0.4-validation-p1"),
        ("schema_version", "1.0"),
        ("path", "data/configs/validation-profiles/redirect.json"),
    ),
)
def test_frozen_context_identity_rejects_unregistered_discriminator(
    field: str,
    value: str,
) -> None:
    redirected = _manifest().to_dict()
    redirected["validation_context"]["validation_profile"][field] = value

    store = StateStore(ROOT)
    with pytest.raises(
        ManifestValidationError, match="not in the closed-world registry"
    ):
        store.validate_document(redirected, "input")


def test_frozen_context_sha_drift_is_rejected() -> None:
    drifted = _manifest().to_dict()
    drifted["validation_context"]["validation_profile"]["sha256"] = "0" * 64

    store = StateStore(ROOT)
    with pytest.raises(ManifestValidationError, match="SHA-256 drifted"):
        store.validate_document(drifted, "input")


def test_warm_context_cache_cannot_conceal_artifact_drift() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _copy_registry_artifacts(root)

        registry = ValidationContextRegistry(root)
        frozen = registry.freeze()
        registry.verify_frozen(
            frozen["planning"], frozen["validation_context"]
        )

        profile = root / P2_VALIDATION_PROFILE_SPEC.relative_path
        profile.write_text(
            profile.read_text(encoding="utf-8") + " ", encoding="utf-8"
        )

        with pytest.raises(ValidationContextError, match="SHA-256 drifted"):
            registry.verify_frozen(
                frozen["planning"], frozen["validation_context"]
            )


def test_planning_baseline_rejects_a_silently_shrunken_plan() -> None:
    registry = ValidationContextRegistry(ROOT)
    plan = PipelinePlanner(ROOT).plan()
    shrunken = PipelinePlan(
        scope=plan.scope,
        languages=plan.languages,
        items=plan.items[:-1],
    )

    with pytest.raises(
        ValidationContextError,
        match="missing from current plan",
    ):
        registry.assert_plan_matches_baseline(shrunken)


def test_planning_baseline_rejects_frozen_input_identity_drift() -> None:
    registry = ValidationContextRegistry(ROOT)
    plan = PipelinePlanner(ROOT).plan(
        "group", group="integration", language="zh-cn"
    )
    changed = replace(plan.items[0], source_sha256="0" * 64)
    drifted = PipelinePlan(
        scope=plan.scope,
        languages=plan.languages,
        items=(changed, *plan.items[1:]),
    )

    with pytest.raises(
        ValidationContextError,
        match="source identity drifted",
    ):
        registry.assert_plan_matches_baseline(drifted)


def test_p2_effective_baseline_changes_exactly_four_definition_hashes() -> None:
    p1_path = ROOT / P1_PLANNING_BASELINE_SPEC.relative_path
    assert sha256_file(p1_path) == (
        "47e721642df8bdbab16eb62643dcb64aff0578fa8685bd8ab4b8070d1f25f8c8"
    )
    p1 = json.loads(p1_path.read_text(encoding="utf-8"))
    effective = ValidationContextRegistry(ROOT).effective_planning_baseline()
    assert len(p1["items"]) == len(effective["items"]) == 434
    assert effective["accounting"] == p1["accounting"] == {
        "denominator": 379,
        "retained_runnable": 379,
        "reviewed_non_runnable": 0,
        "accounted": 379,
        "coverage": "379/379",
    }

    changed: list[str] = []
    for before, after in zip(p1["items"], effective["items"], strict=True):
        assert before["item_id"] == after["item_id"]
        if before == after:
            continue
        changed.append(before["item_id"])
        restored = copy.deepcopy(after)
        restored["product_definition"]["sha256"] = before[
            "product_definition"
        ]["sha256"]
        assert restored == before
    assert tuple(changed) == P2_AMENDED_ITEM_IDS


def test_freeze_defaults_to_successor_but_historical_p1_identity_replays() -> None:
    registry = ValidationContextRegistry(ROOT)
    frozen = registry.freeze()
    assert frozen["planning"]["baseline"]["id"] == (
        "v0.4-p2-product-definition-identity-overlay"
    )
    assert frozen["validation_context"]["validation_profile"] == {
        "id": "v0.4-validation-p3-successor",
        "schema_version": "1.3",
        "path": P3_SUCCESSOR_VALIDATION_PROFILE_SPEC.relative_path,
        "sha256": sha256_file(
            ROOT / P3_SUCCESSOR_VALIDATION_PROFILE_SPEC.relative_path
        ),
    }

    p1 = json.loads(
        (ROOT / P1_PLANNING_BASELINE_SPEC.relative_path).read_text(
            encoding="utf-8"
        )
    )
    historical_planning = {
        "baseline": {
            "id": p1["baseline_id"],
            "schema_version": p1["schema_version"],
            "path": P1_PLANNING_BASELINE_SPEC.relative_path,
            "sha256": sha256_file(
                ROOT / P1_PLANNING_BASELINE_SPEC.relative_path
            ),
        },
        "baseline_accounting": p1["accounting"],
    }
    p1_profile = json.loads(
        (ROOT / P1_VALIDATION_PROFILE_SPEC.relative_path).read_text(
            encoding="utf-8"
        )
    )
    assert sha256_file(
        ROOT / P1_VALIDATION_PROFILE_SPEC.relative_path
    ) == (
        "e314a973d7ed9eafd442ed34db1ec47452ad6c364dd092af608ba8cd71c6e602"
    )
    historical_context = copy.deepcopy(frozen["validation_context"])
    historical_context["validation_profile"] = {
        "id": p1_profile["profile_id"],
        "schema_version": p1_profile["schema_version"],
        "path": P1_VALIDATION_PROFILE_SPEC.relative_path,
        "sha256": sha256_file(
            ROOT / P1_VALIDATION_PROFILE_SPEC.relative_path
        ),
    }
    registry.verify_frozen(
        historical_planning, historical_context
    )
    # Re-reading both active artifacts after both P1 artifacts proves that the
    # document cache is scoped by artifact path, not merely logical key.
    registry.verify_frozen(
        frozen["planning"], frozen["validation_context"]
    )


def test_overlay_rejects_bilingual_transition_drift() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _copy_registry_artifacts(root)
        overlay_path = (
            root
            / "data/baselines/v0.4/"
            "p2-product-definition-identity-overlay.json"
        )
        overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
        overlay["amendments"][2]["product_definition"]["new_sha256"] = (
            "0" * 64
        )
        _write_json(overlay_path, overlay)

        with pytest.raises(
            ValidationContextError,
            match="differs by language",
        ):
            ValidationContextRegistry(root).effective_planning_baseline()


def test_warm_overlay_cache_cannot_conceal_nested_p1_drift() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _copy_registry_artifacts(root)
        registry = ValidationContextRegistry(root)
        frozen = registry.freeze()
        p1_path = root / P1_PLANNING_BASELINE_SPEC.relative_path
        p1_path.write_text(
            p1_path.read_text(encoding="utf-8") + " ",
            encoding="utf-8",
        )

        with pytest.raises(ValidationContextError, match="SHA-256 drifted"):
            registry.verify_frozen(
                frozen["planning"], frozen["validation_context"]
            )


def test_warm_profile_cache_cannot_conceal_historical_p1_drift() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _copy_registry_artifacts(root)
        registry = ValidationContextRegistry(root)
        frozen = registry.freeze()
        p1_profile_path = root / P1_VALIDATION_PROFILE_SPEC.relative_path
        p1_profile = json.loads(
            p1_profile_path.read_text(encoding="utf-8")
        )
        historical_context = copy.deepcopy(frozen["validation_context"])
        historical_context["validation_profile"] = {
            "id": p1_profile["profile_id"],
            "schema_version": p1_profile["schema_version"],
            "path": P1_VALIDATION_PROFILE_SPEC.relative_path,
            "sha256": sha256_file(p1_profile_path),
        }
        registry.verify_frozen(
            frozen["planning"], historical_context
        )
        p1_profile_path.write_text(
            p1_profile_path.read_text(encoding="utf-8") + " ",
            encoding="utf-8",
        )

        with pytest.raises(ValidationContextError, match="SHA-256 drifted"):
            registry.verify_frozen(
                frozen["planning"], historical_context
            )


def test_overlay_builder_is_check_only_unless_reviewed_write_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for relative_path in (
            overlay_builder.P1_BASELINE_PATH,
            overlay_builder.OVERLAY_SCHEMA_PATH,
            *overlay_builder.NEW_DEFINITION_SHA256,
        ):
            target = root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative_path, target)
        monkeypatch.setattr(overlay_builder, "ROOT", root)
        p1_before = sha256_file(root / overlay_builder.P1_BASELINE_PATH)

        with pytest.raises(
            overlay_builder.OverlayBuildError,
            match="--write-reviewed",
        ):
            overlay_builder.build()
        assert not (root / overlay_builder.OVERLAY_PATH).exists()

        value = overlay_builder.build(write_reviewed=True)
        assert len(value["amendments"]) == 4
        assert sha256_file(root / overlay_builder.P1_BASELINE_PATH) == p1_before
        overlay_builder.build()


def test_validation_profile_builder_is_check_only_and_preserves_p1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for relative_path in (
            profile_builder.P1_PROFILE_PATH,
            profile_builder.P1_PROFILE_SCHEMA_PATH,
            profile_builder.P2_PROFILE_SCHEMA_PATH,
            *(
                identity["path"]
                for identity in profile_builder.CONTRACTS.values()
            ),
        ):
            target = root / str(relative_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / str(relative_path), target)
        monkeypatch.setattr(profile_builder, "ROOT", root)
        p1_before = sha256_file(root / profile_builder.P1_PROFILE_PATH)
        p1_schema_before = sha256_file(
            root / profile_builder.P1_PROFILE_SCHEMA_PATH
        )

        with pytest.raises(
            profile_builder.ValidationProfileBuildError,
            match="--write-reviewed",
        ):
            profile_builder.build()
        assert not (root / profile_builder.P2_PROFILE_PATH).exists()

        value = profile_builder.build(write_reviewed=True)
        assert value["profile_id"] == "v0.4-validation-p2"
        assert value["contracts"]["diagnostic_sidecar"]["sha256"] == (
            "6d73b4fd334b2d4b61cf5c6009384e870b6ae7873e148dbf1e162448835b97c4"
        )
        assert value["semantic_assurance"] == (
            profile_builder.SEMANTIC_ASSURANCE
        )
        assert sha256_file(root / profile_builder.P1_PROFILE_PATH) == p1_before
        assert sha256_file(
            root / profile_builder.P1_PROFILE_SCHEMA_PATH
        ) == p1_schema_before
        profile_builder.build()
