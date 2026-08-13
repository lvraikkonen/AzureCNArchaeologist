"""Read-only binding of one formal v0.5.3 Batch item."""

from __future__ import annotations

import json
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from src.independent_fidelity.contracts import bytes_sha256, validate_profile
from src.independent_fidelity.targets import (
    DEFAULT_TARGET_SET_ID,
    TargetDefinition,
    TargetSetRegistration,
    load_registered_target_sets,
    target_by_item_id,
    target_set_registration,
)
from src.independent_fidelity.versions import (
    algorithm_versions_for_reconstruction,
)
from src.independent_fidelity.v053_io import (
    SafeReadError,
    read_regular_bytes,
    safe_relative_path,
    strict_json_bytes,
)


_BATCH_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}$")
_GIT_OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_TERMINAL_BATCH_STATUSES = frozenset({"completed", "completed_with_failures"})
_L3A_VALIDATION_SCHEMAS = {
    "2.1": "pipeline-validation-2.1.schema.json",
    "2.2": "pipeline-validation-2.2.schema.json",
}


class V053BindingError(RuntimeError):
    """A formal Batch item cannot be trusted without guessing."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ArtifactIdentity:
    path: str
    sha256: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "sha256": self.sha256}


@dataclass(frozen=True)
class BoundV053Target:
    repository_root: Path
    run_dir: Path
    target: TargetDefinition
    input_manifest: Mapping[str, Any]
    batch_manifest: Mapping[str, Any]
    input_item: Mapping[str, Any]
    batch_item: Mapping[str, Any]
    source_html: str
    product_definition: Mapping[str, Any]
    soft_category: Sequence[Mapping[str, Any]] | None
    payload: Mapping[str, Any]
    profile: Mapping[str, Any]
    profile_identity: Mapping[str, str]
    source_identity: ArtifactIdentity
    product_definition_identity: ArtifactIdentity
    soft_category_identity: ArtifactIdentity | None
    payload_identity: ArtifactIdentity
    input_manifest_identity: ArtifactIdentity
    batch_manifest_identity: ArtifactIdentity
    producer_commit: str
    batch_revision: int
    l3a_summary: Mapping[str, Any]
    target_set: TargetSetRegistration = field(
        default_factory=target_set_registration
    )

    @property
    def canonical_bundle_root(self) -> Path:
        payload = Path(self.payload_identity.path)
        relative = payload.relative_to(f"runs/{self.target_batch_id}/outputs")
        return self.run_dir / "independent-fidelity" / relative.with_suffix("")

    @property
    def target_batch_id(self) -> str:
        return str(self.batch_manifest["batch_id"])

    @property
    def contract_schema_version(self) -> str:
        return self.target_set.contract_schema_version

    @property
    def algorithm_versions(self) -> Mapping[str, str]:
        return algorithm_versions_for_reconstruction(
            self.target_set.reconstruction_profile_version
        )


def _binding_error(code: str, message: str) -> V053BindingError:
    return V053BindingError(code, message)


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise _binding_error(code, message)


def _read(
    root: Path,
    relative: str | Path,
    *,
    code: str,
) -> bytes:
    try:
        return read_regular_bytes(root, relative)
    except SafeReadError as error:
        raise _binding_error(code, str(error)) from error


def _json(
    data: bytes,
    *,
    description: str,
    expected_type: type,
) -> Any:
    try:
        return strict_json_bytes(
            data,
            description=description,
            expected_type=expected_type,
        )
    except SafeReadError as error:
        raise _binding_error("invalid_bound_json", str(error)) from error


def _schema_validate(
    root: Path,
    value: Mapping[str, Any],
    schema_name: str,
) -> None:
    try:
        schema = json.loads(
            (root / "schemas" / schema_name).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).iter_errors(value),
            key=lambda error: list(error.absolute_path),
        )
    except (OSError, json.JSONDecodeError) as error:
        raise _binding_error(
            "schema_unavailable", f"Cannot load {schema_name}: {error}"
        ) from error
    if errors:
        details = "; ".join(
            f"{'/'.join(map(str, error.absolute_path)) or '$'}: {error.message}"
            for error in errors
        )
        raise _binding_error(
            "schema_validation_failed", f"{schema_name}: {details}"
        )


def _artifact(
    owner: Mapping[str, Any],
    key: str,
    *,
    description: str,
) -> tuple[Path, str]:
    value = owner.get(key)
    _require(
        isinstance(value, Mapping),
        "artifact_binding_missing",
        f"{description} has no {key!r} artifact binding",
    )
    raw_path = value.get("path")
    sha256 = value.get("sha256")
    _require(
        isinstance(raw_path, str)
        and isinstance(sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", sha256) is not None,
        "artifact_binding_invalid",
        f"{description} has an invalid {key!r} artifact binding",
    )
    try:
        relative = safe_relative_path(raw_path)
    except SafeReadError as error:
        raise _binding_error("artifact_binding_invalid", str(error)) from error
    return relative, sha256


def _read_bound_artifact(
    root: Path,
    relative: Path,
    expected_sha256: str,
    *,
    code: str,
) -> bytes:
    data = _read(root, relative, code=code)
    actual = bytes_sha256(data)
    if actual != expected_sha256:
        raise _binding_error(
            code,
            f"Bound artifact SHA-256 mismatch for {relative.as_posix()}: "
            f"expected={expected_sha256}, actual={actual}",
        )
    return data


def _one_input_item(
    manifest: Mapping[str, Any], item_id: str
) -> Mapping[str, Any]:
    matches = [
        item
        for item in manifest.get("items", [])
        if isinstance(item, Mapping) and item.get("item_id") == item_id
    ]
    _require(
        len(matches) == 1,
        "input_item_binding_invalid",
        f"Input Manifest must contain exactly one {item_id!r} item",
    )
    return matches[0]


def _expected_payload_path(
    target: TargetDefinition, product: Mapping[str, Any]
) -> Path:
    if target.page_family == "support_article":
        article_type = product.get("support_article_type")
        _require(
            article_type in {"SLA", "LEGAL", "ICP", "PSR"},
            "product_definition_mismatch",
            "SupportArticle Product Definition has no valid support_article_type",
        )
        return Path(
            f"outputs/{target.language}/SupportArticles/{article_type}/"
            f"{target.resource_key}.json"
        )
    return Path(
        f"outputs/{target.language}/pricing/{target.resource_key}.json"
    )


def _l3a_summary(
    *,
    repository_root: Path,
    run_dir: Path,
    batch_id: str,
    item_id: str,
    artifacts: Mapping[str, Any],
) -> Mapping[str, Any]:
    binding = artifacts.get("validation")
    if not isinstance(binding, Mapping) or not binding.get("sha256"):
        return {
            "claim": "sampled_state_content_consistency",
            "verdict": "not_recorded",
            "coverage": None,
            "validation": None,
        }
    relative, expected_sha = _artifact(
        artifacts, "validation", description="Batch item"
    )
    data = _read_bound_artifact(
        run_dir,
        relative,
        expected_sha,
        code="l3a_validation_binding_mismatch",
    )
    validation = _json(
        data,
        description=relative.as_posix(),
        expected_type=dict,
    )
    validation_version = str(validation.get("schema_version", ""))
    _require(
        validation_version in _L3A_VALIDATION_SCHEMAS,
        "l3a_validation_contract_unsupported",
        "L3a Validation must use a registered 2.1 or 2.2 contract",
    )
    _schema_validate(
        repository_root,
        validation,
        _L3A_VALIDATION_SCHEMAS[validation_version],
    )
    _require(
        validation.get("batch_id") == batch_id
        and validation.get("item_id") == item_id,
        "l3a_validation_binding_mismatch",
        "L3a Validation identity differs from the bound Batch item",
    )
    evidence = validation.get("evidence")
    content = (
        evidence.get("content_validation", {})
        if isinstance(evidence, Mapping)
        else {}
    )
    return {
        "claim": str(
            content.get("claim", "sampled_state_content_consistency")
        ),
        "verdict": str(
            evidence.get("verdict", validation.get("status", "not_recorded"))
            if isinstance(evidence, Mapping)
            else validation.get("status", "not_recorded")
        ),
        "coverage": (
            dict(content["coverage"])
            if isinstance(content.get("coverage"), Mapping)
            else None
        ),
        "validation": {
            "path": f"runs/{batch_id}/{relative.as_posix()}",
            "sha256": expected_sha,
            "evidence_sha256": validation.get("evidence_sha256"),
        },
    }


def bind_batch_item(
    repository_root: str | Path,
    *,
    batch_id: str,
    item_id: str,
    target_set_id: str = DEFAULT_TARGET_SET_ID,
) -> BoundV053Target:
    """Bind one target from current manifests without writing any artifact."""

    if _BATCH_ID.fullmatch(batch_id) is None:
        raise _binding_error("unsafe_batch_id", f"Invalid Batch ID: {batch_id!r}")
    root = Path(repository_root).resolve()
    load_registered_target_sets(root)
    registration = target_set_registration(target_set_id)
    target = target_by_item_id(
        root, item_id, target_set_id=registration.target_set_id
    )
    run_candidate = root / "runs" / batch_id
    for candidate in (root / "runs", run_candidate):
        try:
            metadata = candidate.lstat()
        except OSError as error:
            raise _binding_error(
                "batch_path_unreadable", f"Cannot inspect Batch path: {error}"
            ) from error
        if stat.S_ISLNK(metadata.st_mode):
            raise _binding_error(
                "batch_path_symlink_forbidden",
                f"Batch path contains a symbolic link: {candidate}",
            )
    run_dir = run_candidate.resolve()
    try:
        run_dir.relative_to(root)
    except ValueError as error:
        raise _binding_error(
            "unsafe_batch_path", "Batch directory escapes repository root"
        ) from error

    input_relative = Path("input-manifest.json")
    batch_relative = Path("batch-manifest.json")
    input_bytes = _read(
        run_dir, input_relative, code="input_manifest_unreadable"
    )
    batch_bytes = _read(
        run_dir, batch_relative, code="batch_manifest_unreadable"
    )
    input_manifest = _json(
        input_bytes,
        description=f"runs/{batch_id}/{input_relative.as_posix()}",
        expected_type=dict,
    )
    batch_manifest = _json(
        batch_bytes,
        description=f"runs/{batch_id}/{batch_relative.as_posix()}",
        expected_type=dict,
    )
    _schema_validate(
        root, input_manifest, "pipeline-input-manifest-2.0.schema.json"
    )
    _schema_validate(
        root, batch_manifest, "pipeline-batch-manifest-2.0.schema.json"
    )
    input_sha = bytes_sha256(input_bytes)
    batch_sha = bytes_sha256(batch_bytes)
    _require(
        input_manifest.get("batch_id") == batch_id
        and batch_manifest.get("batch_id") == batch_id,
        "batch_identity_mismatch",
        "Input/Batch Manifest identity differs from the requested Batch",
    )
    _require(
        batch_manifest.get("status") in _TERMINAL_BATCH_STATUSES,
        "batch_not_terminal",
        "Formal Evidence requires a completed Batch",
    )
    revision = batch_manifest.get("revision")
    _require(
        isinstance(revision, int) and revision >= 0,
        "batch_revision_invalid",
        "Batch Manifest revision is invalid",
    )
    manifest_binding = batch_manifest.get("input_manifest")
    _require(
        isinstance(manifest_binding, Mapping)
        and manifest_binding.get("path") == input_relative.as_posix()
        and manifest_binding.get("sha256") == input_sha,
        "input_manifest_binding_mismatch",
        "Batch Manifest does not bind the immutable Input Manifest",
    )

    provenance = input_manifest.get("provenance")
    producer_commit = (
        provenance.get("git_commit")
        if isinstance(provenance, Mapping)
        else None
    )
    _require(
        isinstance(provenance, Mapping)
        and provenance.get("reproducible") is True
        and provenance.get("dirty") is False
        and isinstance(producer_commit, str)
        and _GIT_OBJECT_ID.fullmatch(producer_commit) is not None,
        "producer_provenance_untrusted",
        "Input Manifest is not bound to a clean reproducible producer commit",
    )

    input_item = _one_input_item(input_manifest, item_id)
    batch_items = batch_manifest.get("items")
    batch_item = (
        batch_items.get(item_id) if isinstance(batch_items, Mapping) else None
    )
    _require(
        isinstance(batch_item, Mapping),
        "batch_item_binding_invalid",
        f"Batch Manifest has no item {item_id!r}",
    )
    expected_identity = {
        "language": target.language,
        "resource_key": target.resource_key,
    }
    expected_page_model = (
        "SupportArticlePage"
        if target.page_family == "support_article"
        else "FlexibleContentPage"
    )
    for item, owner in ((input_item, "Input"), (batch_item, "Batch")):
        _require(
            item.get("identity") == expected_identity
            and item.get("product_key") == target.resource_key
            and item.get("strategy") == target.page_family
            and item.get("page_model") == expected_page_model
            and item.get("resource", {}).get("kind") == "current",
            "item_identity_mismatch",
            f"{owner} Manifest item differs from the frozen target definition",
        )
    status = batch_item.get("status")
    _require(
        isinstance(status, Mapping)
        and status.get("execution") == "succeeded",
        "item_execution_untrusted",
        "Formal L3b binding requires execution=succeeded and a persisted payload",
    )

    source_path, source_sha = _artifact(
        input_item, "source", description="Input item"
    )
    normalized_path, normalized_sha = _artifact(
        input_item, "normalized_input", description="Input item"
    )
    config_path, config_sha = _artifact(
        input_item, "config", description="Input item"
    )
    source_bytes = _read_bound_artifact(
        root, source_path, source_sha, code="source_binding_mismatch"
    )
    normalized_bytes = _read_bound_artifact(
        root,
        normalized_path,
        normalized_sha,
        code="normalized_input_binding_mismatch",
    )
    _require(
        source_sha == normalized_sha and source_bytes == normalized_bytes,
        "source_normalized_input_mismatch",
        "Source and normalized input bytes differ for the formal item",
    )
    config_bytes = _read_bound_artifact(
        root,
        config_path,
        config_sha,
        code="product_definition_binding_mismatch",
    )
    product = _json(
        config_bytes,
        description=config_path.as_posix(),
        expected_type=dict,
    )
    _require(
        product.get("product_key") == target.resource_key
        and product.get("page_model") == expected_page_model
        and product.get("extraction", {}).get("semantic_strategy")
        == target.page_family,
        "product_definition_mismatch",
        "Product Definition differs from the target page family/model",
    )

    target_set_bytes = _read(
        root,
        registration.target_set_path,
        code="target_set_binding_mismatch",
    )
    target_set_sha = bytes_sha256(target_set_bytes)
    profile_bytes = _read(
        root, registration.profile_path, code="profile_binding_mismatch"
    )
    profile_sha = bytes_sha256(profile_bytes)
    profile = _json(
        profile_bytes,
        description=registration.profile_path.as_posix(),
        expected_type=dict,
    )
    try:
        validate_profile(root, profile)
    except ValueError as error:
        raise _binding_error(
            "profile_contract_invalid",
            f"Profile {registration.profile_schema_version} is invalid: {error}",
        ) from error
    supported_families = profile.get("qualification", {}).get(
        "supported_page_families"
    )
    _require(
        profile.get("schema_version") == registration.profile_schema_version
        and profile.get("profile_id") == registration.profile_id
        and profile.get("profile_version") == registration.profile_version
        and profile.get("reconstruction_profile_version")
        == registration.reconstruction_profile_version
        and isinstance(supported_families, list)
        and target.page_family in supported_families,
        "profile_identity_mismatch",
        "Registered Profile identity/family differs from the selected target set",
    )
    immutable_files = provenance.get("immutable_files", {})
    _require(
        isinstance(immutable_files, Mapping)
        and immutable_files.get(registration.target_set_path.as_posix())
        == target_set_sha
        and immutable_files.get(registration.profile_path.as_posix())
        == profile_sha
        and immutable_files.get(config_path.as_posix()) == config_sha,
        "producer_immutable_binding_mismatch",
        "Producer provenance does not bind target set/Profile/Product Definition bytes",
    )

    frozen = input_manifest.get("frozen_inputs", {}).get("soft_category")
    batch_frozen = batch_manifest.get("frozen_inputs", {}).get("soft_category")
    _require(
        isinstance(frozen, Mapping)
        and batch_frozen == frozen,
        "soft_category_binding_mismatch",
        "Input/Batch Manifest soft-category bindings differ",
    )
    soft_path_value = frozen.get("path")
    soft_sha = frozen.get("sha256")
    _require(
        isinstance(soft_path_value, str)
        and isinstance(soft_sha, str)
        and re.fullmatch(r"[0-9a-f]{64}", soft_sha) is not None,
        "soft_category_binding_mismatch",
        "Frozen soft-category binding is invalid",
    )
    soft_path = safe_relative_path(soft_path_value)
    soft_bytes = _read_bound_artifact(
        root,
        soft_path,
        soft_sha,
        code="soft_category_binding_mismatch",
    )
    loaded_soft = _json(
        soft_bytes,
        description=soft_path.as_posix(),
        expected_type=list,
    )
    uses_soft_category = target.page_family in {"region_filter", "complex"}
    soft_category = loaded_soft if uses_soft_category else None
    soft_identity = (
        ArtifactIdentity(soft_path.as_posix(), soft_sha)
        if uses_soft_category
        else None
    )

    artifacts = batch_item.get("artifacts")
    _require(
        isinstance(artifacts, Mapping),
        "payload_binding_missing",
        "Batch item has no artifact bindings",
    )
    payload_path, payload_sha = _artifact(
        artifacts, "payload", description="Batch item"
    )
    expected_payload_path = _expected_payload_path(target, product)
    _require(
        payload_path == expected_payload_path,
        "payload_path_mismatch",
        f"Payload path differs from the canonical item path: {payload_path}",
    )
    payload_bytes = _read_bound_artifact(
        run_dir,
        payload_path,
        payload_sha,
        code="payload_binding_mismatch",
    )
    payload = _json(
        payload_bytes,
        description=f"runs/{batch_id}/{payload_path.as_posix()}",
        expected_type=dict,
    )
    batch_normalized_path, batch_normalized_sha = _artifact(
        artifacts, "normalized_input", description="Batch item"
    )
    _require(
        batch_normalized_path == normalized_path
        and batch_normalized_sha == normalized_sha,
        "normalized_input_binding_mismatch",
        "Batch item does not bind the Input Manifest normalized bytes",
    )

    profile_identity = {
        "id": str(profile["profile_id"]),
        "version": str(profile["profile_version"]),
        "path": registration.profile_path.as_posix(),
        "sha256": profile_sha,
    }
    return BoundV053Target(
        repository_root=root,
        run_dir=run_dir,
        target=target,
        input_manifest=input_manifest,
        batch_manifest=batch_manifest,
        input_item=input_item,
        batch_item=batch_item,
        source_html=source_bytes.decode("utf-8-sig"),
        product_definition=product,
        soft_category=soft_category,
        payload=payload,
        profile=profile,
        profile_identity=profile_identity,
        source_identity=ArtifactIdentity(source_path.as_posix(), source_sha),
        product_definition_identity=ArtifactIdentity(
            config_path.as_posix(), config_sha
        ),
        soft_category_identity=soft_identity,
        payload_identity=ArtifactIdentity(
            f"runs/{batch_id}/{payload_path.as_posix()}", payload_sha
        ),
        input_manifest_identity=ArtifactIdentity(
            f"runs/{batch_id}/{input_relative.as_posix()}", input_sha
        ),
        batch_manifest_identity=ArtifactIdentity(
            f"runs/{batch_id}/{batch_relative.as_posix()}", batch_sha
        ),
        producer_commit=producer_commit,
        batch_revision=revision,
        l3a_summary=_l3a_summary(
            repository_root=root,
            run_dir=run_dir,
            batch_id=batch_id,
            item_id=item_id,
            artifacts=artifacts,
        ),
        target_set=registration,
    )
