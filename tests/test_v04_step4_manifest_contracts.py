"""Slice A additive contracts for Manifest 2.0 lifecycle state."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from src.core.product_catalog import sha256_file
from src.core.validation_context import ValidationContextRegistry
from src.pipeline.coordinator import PipelineCoordinator
from src.pipeline.models import (
    BatchItem,
    BatchManifest,
    InputManifest,
    PipelinePlan,
    summarize_batch_manifest,
)
from src.pipeline.planner import PipelinePlanner, PlanningError
from src.pipeline.state_store import (
    ImmutableManifestError,
    ManifestConflictError,
    ManifestValidationError,
    RepositoryLock,
    RepositoryLockError,
    StateStore,
    StateStoreError,
)


ROOT = Path(__file__).resolve().parents[1]
BATCH_ID = "20260803T120000Z-deadbeef"
CREATED_AT = "2026-08-03T12:00:00Z"


def _provenance() -> dict[str, object]:
    return {
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


def _item(resource_key: str, strategy: str) -> BatchItem:
    return BatchItem(
        language="zh-cn",
        resource_key=resource_key,
        product_key=resource_key,
        resource_kind="current",
        page_model="FlexibleContentPage",
        capability_status="supported",
        config_path=f"data/configs/products/pricing/{resource_key}.json",
        config_sha256="1" * 64,
        source_availability="available",
        source_path=(
            f"data/current_prod_html/zh-cn/pricing/details/{resource_key}/index.html"
        ),
        source_sha256="2" * 64,
        normalized_path=f"data/prod-html/zh-cn/pricing/{resource_key}.html",
        normalized_sha256="2" * 64,
        output_path=f"outputs/zh-cn/pricing/{resource_key}.json",
        diagnostic_path=(
            f"diagnostics/zh-cn/pricing/{resource_key}.sidecar.json"
        ),
        validation_path=(
            f"validation/zh-cn/pricing/{resource_key}.validation.json"
        ),
        slug=resource_key,
        strategy=strategy,
    )


def _input_manifest() -> InputManifest:
    frozen_context = ValidationContextRegistry(ROOT).freeze()
    soft_category = ROOT / "data/configs/soft-category.json"
    plan = PipelinePlan(
        scope={"kind": "all"},
        languages=("zh-cn",),
        items=(
            _item("interactive", "region_filter"),
            _item("full-mode", "simple_static"),
        ),
        frozen_inputs={
            "soft_category": {
                "path": "data/configs/soft-category.json",
                "sha256": sha256_file(soft_category),
            }
        },
    )
    return InputManifest.from_plan(
        BATCH_ID,
        plan,
        _provenance(),
        created_at=CREATED_AT,
        planning=frozen_context["planning"],
        validation_context=frozen_context["validation_context"],
    )


def _create_run(tmp_path: Path) -> tuple[StateStore, dict[str, object]]:
    store = StateStore(ROOT, runs_dir=tmp_path / "runs")
    store.create_run(_input_manifest())
    return store, store.read_manifest(BATCH_ID)


def _repository_lock(store: StateStore) -> RepositoryLock:
    return RepositoryLock(
        store.lock_root,
        batch_id=BATCH_ID,
        command="step4-manifest-contract-test",
    )


def test_new_manifests_freeze_soft_category_and_initialize_step4_state(
    tmp_path: Path,
) -> None:
    store, batch = _create_run(tmp_path)
    frozen = store.read_input_manifest(BATCH_ID)

    expected_frozen_inputs = {
        "soft_category": {
            "path": "data/configs/soft-category.json",
            "sha256": sha256_file(ROOT / "data/configs/soft-category.json"),
        }
    }
    assert frozen["frozen_inputs"] == expected_frozen_inputs
    assert batch["frozen_inputs"] == expected_frozen_inputs
    assert batch["release_manifests"] == []
    assert batch["publication_receipts"] == []

    interactive = batch["items"]["zh-cn/interactive"]
    assert interactive["status"] == {
        "execution": "pending",
        "validation": "not_run",
        "review": "not_requested",
        "publication": "not_published",
        "evidence_binding": "not_applicable",
        "approval_eligibility": "blocked",
        "release": "not_released",
    }
    assert interactive["artifacts"]["sampling_plan"] == {
        "path": "validation/zh-cn/pricing/interactive.sampling-plan.json",
        "sha256": None,
    }
    assert interactive["artifacts"]["sampled_content_evidence"] == {
        "path": (
            "validation/zh-cn/pricing/"
            "interactive.sampled-content-evidence.json"
        ),
        "sha256": None,
    }
    assert interactive["artifacts"]["current_review_decision"] is None

    full_mode = batch["items"]["zh-cn/full-mode"]
    assert full_mode["artifacts"]["sampling_plan"] is None
    assert full_mode["artifacts"]["sampled_content_evidence"] == {
        "path": (
            "validation/zh-cn/pricing/"
            "full-mode.sampled-content-evidence.json"
        ),
        "sha256": None,
    }
    assert full_mode["artifacts"]["current_review_decision"] is None


def test_real_planner_freezes_current_canonical_soft_category_identity() -> None:
    plan = PipelinePlanner(ROOT).plan(
        "group", group="integration", language="zh-cn"
    )

    assert plan.frozen_inputs == {
        "soft_category": {
            "path": "data/configs/soft-category.json",
            "sha256": sha256_file(ROOT / "data/configs/soft-category.json"),
        }
    }


def test_new_planning_fails_when_soft_category_input_is_missing(
    tmp_path: Path,
) -> None:
    with pytest.raises(PlanningError, match="soft-category input is missing"):
        PipelinePlanner(tmp_path)._frozen_repository_inputs()


def test_legacy_manifest_20_without_additive_fields_remains_readable(
    tmp_path: Path,
) -> None:
    frozen = _input_manifest().to_dict()
    frozen.pop("frozen_inputs")
    batch = BatchManifest.from_input_manifest(frozen).to_dict()
    batch.pop("release_manifests")
    batch.pop("publication_receipts")
    for item in batch["items"].values():
        item["status"].pop("evidence_binding")
        item["status"].pop("approval_eligibility")
        item["status"].pop("release")
        item["artifacts"].pop("sampling_plan")
        item["artifacts"].pop("sampled_content_evidence")
        item["artifacts"].pop("current_review_decision")

    store = StateStore(ROOT, runs_dir=tmp_path / "runs")
    with pytest.raises(
        ImmutableManifestError,
        match="New pipeline runs require frozen_inputs",
    ):
        store.create_run(frozen, batch)
    run_dir = store.run_dir(BATCH_ID)
    run_dir.mkdir(parents=True)
    input_path = run_dir / "input-manifest.json"
    input_path.write_text(
        json.dumps(frozen, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    batch["input_manifest"] = {
        "path": "input-manifest.json",
        "sha256": sha256_file(input_path),
    }
    (run_dir / "batch-manifest.json").write_text(
        json.dumps(batch, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert "frozen_inputs" not in store.read_input_manifest(BATCH_ID)
    restored = store.read_manifest(BATCH_ID)
    assert "frozen_inputs" not in restored
    assert "release_manifests" not in restored

    summary = summarize_batch_manifest(restored)
    assert summary["evidence_not_applicable"] == 2
    assert summary["approval_blocked"] == 2
    assert summary["not_released"] == 2
    assert summary["review_approved"] == 0
    assert summary["review_rejected"] == 0

    with _repository_lock(store):
        with pytest.raises(
            ImmutableManifestError,
            match="optional Step 4 status",
        ):
            store.update_manifest(
                BATCH_ID,
                lambda value: value["items"]["zh-cn/interactive"][
                    "status"
                ].update({"evidence_binding": "not_applicable"}),
                expected_revision=restored["revision"],
            )
        with pytest.raises(ImmutableManifestError, match="release_manifests"):
            store.update_manifest(
                BATCH_ID,
                lambda value: value.update({"release_manifests": []}),
                expected_revision=restored["revision"],
            )


def test_frozen_inputs_are_replayed_and_immutable(tmp_path: Path) -> None:
    store, batch = _create_run(tmp_path)

    with _repository_lock(store):
        with pytest.raises(ImmutableManifestError, match="frozen_inputs"):
            store.update_manifest(
                BATCH_ID,
                lambda value: value["frozen_inputs"]["soft_category"].update(
                    {"sha256": "0" * 64}
                ),
                expected_revision=batch["revision"],
            )

    drifted = _input_manifest().to_dict()
    drifted["frozen_inputs"]["soft_category"]["sha256"] = "0" * 64
    with pytest.raises(ManifestValidationError, match="soft-category.*drifted"):
        store.validate_document(drifted, "input")


def test_manifest_mutation_requires_lock_and_expected_revision(
    tmp_path: Path,
) -> None:
    store, batch = _create_run(tmp_path)

    with pytest.raises(ManifestConflictError, match="expected_revision"):
        store.update_manifest(
            BATCH_ID,
            lambda value: value.update({"status": "running"}),
        )
    with pytest.raises(RepositoryLockError, match="RepositoryLock"):
        store.update_manifest(
            BATCH_ID,
            lambda value: value.update({"status": "running"}),
            expected_revision=batch["revision"],
        )

    with _repository_lock(store):
        updated = store.update_manifest(
            BATCH_ID,
            lambda value: value.update({"status": "running"}),
            expected_revision=batch["revision"],
        )
    assert updated["revision"] == batch["revision"] + 1


def test_custom_new_batch_must_exactly_match_input_and_rejection_is_atomic(
    tmp_path: Path,
) -> None:
    frozen = _input_manifest().to_dict()
    custom = BatchManifest.from_input_manifest(frozen).to_dict()
    custom["items"]["zh-cn/interactive"]["product_key"] = "other"
    store = StateStore(ROOT, runs_dir=tmp_path / "runs")

    with pytest.raises(ImmutableManifestError, match="exactly equal"):
        store.create_run(frozen, custom)
    assert not store.run_dir(BATCH_ID).exists()

    store.create_run(frozen)
    assert store.read_manifest(BATCH_ID)["items"]["zh-cn/interactive"][
        "product_key"
    ] == "interactive"


@pytest.mark.parametrize(
    "mutation",
    ("batch_id", "created_at", "summary", "item_identity", "step4_state"),
)
def test_custom_new_batch_cannot_override_any_canonical_initial_state(
    tmp_path: Path,
    mutation: str,
) -> None:
    frozen = _input_manifest().to_dict()
    custom = BatchManifest.from_input_manifest(frozen).to_dict()
    if mutation == "batch_id":
        custom["batch_id"] = "20260803T120001Z-deadbeef"
    elif mutation == "created_at":
        custom["created_at"] = "2026-08-03T12:00:01Z"
    elif mutation == "summary":
        custom["summary"]["total"] = 99
    elif mutation == "item_identity":
        custom["items"]["zh-cn/interactive"]["identity"][
            "resource_key"
        ] = "other"
    else:
        custom["items"]["zh-cn/interactive"]["status"][
            "approval_eligibility"
        ] = "eligible"
    store = StateStore(ROOT, runs_dir=tmp_path / mutation / "runs")

    with pytest.raises(ImmutableManifestError, match="exactly equal"):
        store.create_run(frozen, custom)
    assert not store.run_dir(BATCH_ID).exists()


def test_new_run_cannot_activate_registered_p3_before_slice_b(
    tmp_path: Path,
) -> None:
    frozen = _input_manifest().to_dict()
    frozen["validation_context"] = ValidationContextRegistry(ROOT).freeze(
        validation_profile_id="v0.4-validation-p3"
    )["validation_context"]
    store = StateStore(ROOT, runs_dir=tmp_path / "runs")

    with pytest.raises(ImmutableManifestError, match="active P2"):
        store.create_run(frozen)
    assert not store.run_dir(BATCH_ID).exists()


def test_p3_batch_cannot_write_a_validation_1_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = StateStore(ROOT, runs_dir=tmp_path / "runs")
    p3_context = ValidationContextRegistry(ROOT).freeze(
        validation_profile_id="v0.4-validation-p3"
    )["validation_context"]
    monkeypatch.setattr(
        store,
        "read_manifest",
        lambda batch_id: {"validation_context": p3_context},
    )
    validation_1 = {
        "schema_version": "1.0",
        "batch_id": BATCH_ID,
        "item_id": "zh-cn/interactive",
        "validated_at": "2026-08-03T12:30:00Z",
        "status": "passed",
        "errors": [],
        "warnings": [],
    }

    with _repository_lock(store):
        with pytest.raises(StateStoreError, match="does not match"):
            store.write_projection(
                BATCH_ID,
                "validation",
                validation_1,
                relative_path=(
                    "validation/zh-cn/pricing/interactive.validation.json"
                ),
            )


def test_release_and_publication_references_are_append_only(
    tmp_path: Path,
) -> None:
    store, batch = _create_run(tmp_path)
    release = {
        "path": "releases/release-a/release-manifest.json",
        "sha256": "3" * 64,
    }
    receipt = {
        "path": "publication/receipts/receipt-a.json",
        "sha256": "4" * 64,
    }

    def append_references(value: dict[str, Any]) -> None:
        value["release_manifests"].append(release)
        value["publication_receipts"].append(receipt)

    with _repository_lock(store):
        updated = store.update_manifest(
            BATCH_ID,
            append_references,
            expected_revision=batch["revision"],
        )
        assert updated["release_manifests"] == [release]
        assert updated["publication_receipts"] == [receipt]

        with pytest.raises(ImmutableManifestError, match="append-only"):
            store.update_manifest(
                BATCH_ID,
                lambda value: value.update({"release_manifests": []}),
                expected_revision=updated["revision"],
            )


def test_additive_manifest_fields_remain_closed_world(tmp_path: Path) -> None:
    store, batch = _create_run(tmp_path)
    invalid_frozen = _input_manifest().to_dict()
    invalid_frozen["frozen_inputs"]["unexpected"] = {}
    with pytest.raises(ManifestValidationError, match="unexpected"):
        store.validate_document(invalid_frozen, "input")

    invalid_batch = copy.deepcopy(batch)
    invalid_batch["items"]["zh-cn/interactive"]["status"][
        "evidence_binding"
    ] = "unknown"
    with pytest.raises(ManifestValidationError, match="unknown"):
        store.validate_document(invalid_batch, "batch")

    unbound_decision = copy.deepcopy(batch)
    unbound_decision["items"]["zh-cn/interactive"]["artifacts"][
        "current_review_decision"
    ] = {
        "path": "review/decisions/decision.json",
        "sha256": None,
    }
    with pytest.raises(
        ManifestValidationError,
        match="current_review_decision",
    ):
        store.validate_document(unbound_decision, "batch")


def test_manifest_status_projects_to_legacy_sidecar_contract() -> None:
    status = {
        "execution": "succeeded",
        "validation": "passed",
        "review": "pending",
        "publication": "not_published",
        "evidence_binding": "bound",
        "approval_eligibility": "eligible",
        "release": "not_released",
    }
    projected = PipelineCoordinator._sidecar_status_projection(status)
    assert projected == {
        "execution": "succeeded",
        "validation": "passed",
        "review": "pending",
        "publication": "not_published",
    }

    sidecar_schema = json.loads(
        (ROOT / "schemas/diagnostic-sidecar-1.2.schema.json").read_text(
            encoding="utf-8"
        )
    )
    status_validator = Draft202012Validator(
        sidecar_schema["properties"]["status"]
    )
    status_validator.validate(projected)
    with pytest.raises(ValidationError):
        status_validator.validate(status)


def test_slice_a_cannot_write_a_p3_runtime_validation(
    tmp_path: Path,
) -> None:
    store, _ = _create_run(tmp_path)

    with pytest.raises(StateStoreError, match="Slice B"):
        store.write_projection(
            BATCH_ID,
            "validation",
            {
                "schema_version": "2.0",
                "batch_id": BATCH_ID,
            },
            relative_path=(
                "validation/zh-cn/pricing/"
                "interactive.validation.json"
            ),
        )
