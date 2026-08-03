"""Registry integration tests for the inactive v0.4 P3 contracts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from src.core.validation_context import (
    ARTIFACT_SPECS,
    CONTENT_SAMPLING_PROFILE_SPEC,
    P2_VALIDATION_PROFILE_SPEC,
    P3_VALIDATION_PROFILE_SPEC,
    P3_VALIDATION_CONTRACT_SPECS,
    ValidationContextError,
    ValidationContextRegistry,
)


ROOT = Path(__file__).resolve().parents[1]


def _copy_registry(root: Path) -> None:
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
    for specification in P3_VALIDATION_CONTRACT_SPECS:
        relative_path = specification.relative_path
        if relative_path in copied:
            continue
        copied.add(relative_path)
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative_path, target)


P3_RUNTIME_CONTRACT_NAMES = (
    "content_sampling_profile",
    "pipeline_validation",
    "batch_item_sampling_plan",
    "sampled_content_evidence",
)


def _p3_contract_path(name: str) -> str:
    return next(
        specification
        for specification in P3_VALIDATION_CONTRACT_SPECS
        if specification.name == name
    ).relative_path


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_p3_is_registered_but_p2_remains_the_active_default() -> None:
    registry = ValidationContextRegistry(ROOT)

    active = registry.freeze()
    assert active["validation_context"]["validation_profile"]["id"] == (
        "v0.4-validation-p2"
    )

    p3 = registry.freeze(validation_profile_id="v0.4-validation-p3")
    identity = p3["validation_context"]["validation_profile"]
    assert identity == registry._identity(P3_VALIDATION_PROFILE_SPEC)
    registry.verify_frozen(p3["planning"], p3["validation_context"])

    sampling = registry.content_sampling_profile_for(identity)
    assert sampling is not None
    assert sampling["profile_id"] == "v0.4-content-sampling-p3"
    assert registry.content_sampling_profile_for(
        active["validation_context"]["validation_profile"]
    ) is None


def test_explicit_profile_selection_is_closed_world() -> None:
    registry = ValidationContextRegistry(ROOT)

    with pytest.raises(ValidationContextError, match="Unknown Validation Profile"):
        registry.freeze(validation_profile_id="v0.4-validation-unknown")


@pytest.mark.parametrize(
    "profile_id",
    (
        "v0.4-validation-p1",
        "v0.4-validation-p2",
        "v0.4-validation-p3",
    ),
)
def test_every_registered_profile_identity_replays(profile_id: str) -> None:
    registry = ValidationContextRegistry(ROOT)

    frozen = registry.freeze(validation_profile_id=profile_id)

    assert frozen["validation_context"]["validation_profile"]["id"] == profile_id
    registry.verify_frozen(frozen["planning"], frozen["validation_context"])


@pytest.mark.parametrize(
    "specification",
    (P2_VALIDATION_PROFILE_SPEC, CONTENT_SAMPLING_PROFILE_SPEC),
)
def test_p3_replay_detects_nested_dependency_drift(
    tmp_path: Path,
    specification: object,
) -> None:
    _copy_registry(tmp_path)
    registry = ValidationContextRegistry(tmp_path)
    frozen = registry.freeze(validation_profile_id="v0.4-validation-p3")
    registry.verify_frozen(
        frozen["planning"], frozen["validation_context"]
    )

    relative_path = specification.relative_path  # type: ignore[attr-defined]
    path = tmp_path / relative_path
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(ValidationContextError, match="SHA-256 drifted"):
        registry.verify_frozen(
            frozen["planning"], frozen["validation_context"]
        )


def test_p3_document_can_be_resolved_from_its_frozen_identity() -> None:
    registry = ValidationContextRegistry(ROOT)
    frozen = registry.freeze(validation_profile_id="v0.4-validation-p3")
    identity = frozen["validation_context"]["validation_profile"]

    document = registry.document_for_identity("validation_profile", identity)

    assert document["profile_id"] == "v0.4-validation-p3"
    assert document["base_profile"]["id"] == "v0.4-validation-p2"
    assert document["content_sampling_profile"]["id"] == (
        "v0.4-content-sampling-p3"
    )
    assert registry._identity(P2_VALIDATION_PROFILE_SPEC)["id"] == (
        "v0.4-validation-p2"
    )


@pytest.mark.parametrize("contract_name", P3_RUNTIME_CONTRACT_NAMES)
def test_p3_contract_replay_rejects_a_missing_artifact(
    tmp_path: Path,
    contract_name: str,
) -> None:
    _copy_registry(tmp_path)
    registry = ValidationContextRegistry(tmp_path)
    frozen = registry.freeze(validation_profile_id="v0.4-validation-p3")
    (tmp_path / _p3_contract_path(contract_name)).unlink()

    with pytest.raises(ValidationContextError, match="missing"):
        registry.verify_frozen(
            frozen["planning"], frozen["validation_context"]
        )


@pytest.mark.parametrize("contract_name", P3_RUNTIME_CONTRACT_NAMES)
def test_p3_contract_replay_rejects_artifact_byte_drift(
    tmp_path: Path,
    contract_name: str,
) -> None:
    _copy_registry(tmp_path)
    registry = ValidationContextRegistry(tmp_path)
    frozen = registry.freeze(validation_profile_id="v0.4-validation-p3")
    path = tmp_path / _p3_contract_path(contract_name)
    path.write_text(
        path.read_text(encoding="utf-8") + " ",
        encoding="utf-8",
    )

    with pytest.raises(
        ValidationContextError,
        match=rf"P3 contract {contract_name} SHA-256 drifted",
    ):
        registry.verify_frozen(
            frozen["planning"], frozen["validation_context"]
        )


@pytest.mark.parametrize("contract_name", P3_RUNTIME_CONTRACT_NAMES)
def test_p3_contract_replay_rejects_profile_path_drift(
    tmp_path: Path,
    contract_name: str,
) -> None:
    _copy_registry(tmp_path)
    profile_path = tmp_path / P3_VALIDATION_PROFILE_SPEC.relative_path
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["contracts"][contract_name]["path"] = (
        "schemas/pipeline-validation-1.0.schema.json"
    )
    _write_json(profile_path, profile)

    with pytest.raises(
        ValidationContextError,
        match=rf"P3 contract {contract_name} path drifted",
    ):
        ValidationContextRegistry(tmp_path).freeze(
            validation_profile_id="v0.4-validation-p3"
        )


@pytest.mark.parametrize("contract_name", P3_RUNTIME_CONTRACT_NAMES)
def test_p3_contract_replay_rejects_schema_version_drift(
    tmp_path: Path,
    contract_name: str,
) -> None:
    _copy_registry(tmp_path)
    profile_path = tmp_path / P3_VALIDATION_PROFILE_SPEC.relative_path
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["contracts"][contract_name]["schema_version"] = "9.9"
    _write_json(profile_path, profile)

    with pytest.raises(
        ValidationContextError,
        match=rf"P3 contract {contract_name} schema version drifted",
    ):
        ValidationContextRegistry(tmp_path).freeze(
            validation_profile_id="v0.4-validation-p3"
        )


def test_p3_contract_replay_rejects_a_symlink_artifact(
    tmp_path: Path,
) -> None:
    _copy_registry(tmp_path)
    registry = ValidationContextRegistry(tmp_path)
    frozen = registry.freeze(validation_profile_id="v0.4-validation-p3")
    path = tmp_path / _p3_contract_path("pipeline_validation")
    replacement = path.with_name("pipeline-validation-copy.schema.json")
    shutil.copy2(path, replacement)
    path.unlink()
    path.symlink_to(replacement.name)

    with pytest.raises(ValidationContextError, match="non-symlink"):
        registry.verify_frozen(
            frozen["planning"], frozen["validation_context"]
        )
