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

from src.core.product_catalog import sha256_file
from src.core.validation_context import (
    ARTIFACT_SPECS,
    ValidationContextError,
    ValidationContextRegistry,
)
from src.pipeline.models import BatchManifest, InputManifest, PipelinePlan
from src.pipeline.planner import PipelinePlanner
from src.pipeline.state_store import (
    ImmutableManifestError,
    ManifestValidationError,
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
    plan = PipelinePlanner(ROOT).plan("all", language="zh-cn")
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
            "total": 217,
            "runnable": 190,
            "skipped": 27,
            "known_unsupported": 27,
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

        with pytest.raises(ImmutableManifestError, match="hash mismatch"):
            store.update_manifest(
                BATCH_ID, lambda value: value.update({"status": "running"})
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


def test_frozen_context_identity_cannot_redirect_to_another_path() -> None:
    redirected = _manifest().to_dict()
    redirected["validation_context"]["validation_profile"]["path"] = (
        "data/configs/validation-profiles/redirect.json"
    )

    store = StateStore(ROOT)
    with pytest.raises(
        ManifestValidationError, match="closed-world registry path"
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

        registry = ValidationContextRegistry(root)
        frozen = registry.freeze()
        registry.verify_frozen(
            frozen["planning"], frozen["validation_context"]
        )

        profile = root / next(
            specification.relative_path
            for specification in ARTIFACT_SPECS
            if specification.key == "validation_profile"
        )
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
    plan = PipelinePlanner(ROOT).plan()
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
