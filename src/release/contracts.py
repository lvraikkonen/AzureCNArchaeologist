"""Pure promotion and release identity invariants for Step 4."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.core.canonical_identity import (
    canonical_sha256,
    document_identity_sha256,
    require_sha256,
)


class ReleaseContractError(ValueError):
    """A release candidate or identity violates the frozen contract."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _contract_error(code: str, message: str) -> None:
    raise ReleaseContractError(code, message)


def _closed_mapping(
    value: Any,
    *,
    fields: frozenset[str],
    context: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _contract_error("invalid_object", f"{context} must be an object")
    if any(not isinstance(key, str) for key in value):
        _contract_error(
            "invalid_object_key",
            f"{context} keys must be strings",
        )
    keys = set(value)
    missing = fields - keys
    unknown = keys - fields
    if missing:
        _contract_error(
            "missing_field",
            f"{context} is missing fields: {', '.join(sorted(missing))}",
        )
    if unknown:
        _contract_error(
            "unknown_field",
            f"{context} has unknown fields: {', '.join(sorted(unknown))}",
        )
    return value


def _enum(value: Any, allowed: Sequence[str], *, field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        _contract_error(
            "invalid_enum",
            f"{field} must be one of {', '.join(allowed)}",
        )
    return value


@dataclass(frozen=True)
class ReleaseHashBindings:
    """All mutable run identities frozen into one Release item."""

    payload_sha256: str
    validation_artifact_sha256: str
    validation_evidence_sha256: str
    review_decision_sha256: str
    validation_profile_sha256: str
    sampling_plan_sha256: str | None

    def __post_init__(self) -> None:
        for field in (
            "payload_sha256",
            "validation_artifact_sha256",
            "validation_evidence_sha256",
            "review_decision_sha256",
            "validation_profile_sha256",
        ):
            try:
                require_sha256(getattr(self, field), field=field)
            except ValueError as error:
                _contract_error("invalid_sha256", str(error))
        if self.sampling_plan_sha256 is not None:
            try:
                require_sha256(
                    self.sampling_plan_sha256,
                    field="sampling_plan_sha256",
                )
            except ValueError as error:
                _contract_error("invalid_sha256", str(error))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ReleaseHashBindings":
        parsed = _closed_mapping(
            value,
            fields=frozenset({
                "payload_sha256",
                "validation_artifact_sha256",
                "validation_evidence_sha256",
                "review_decision_sha256",
                "validation_profile_sha256",
                "sampling_plan_sha256",
            }),
            context="release hash bindings",
        )
        return cls(
            payload_sha256=parsed["payload_sha256"],
            validation_artifact_sha256=parsed[
                "validation_artifact_sha256"
            ],
            validation_evidence_sha256=parsed[
                "validation_evidence_sha256"
            ],
            review_decision_sha256=parsed["review_decision_sha256"],
            validation_profile_sha256=parsed[
                "validation_profile_sha256"
            ],
            sampling_plan_sha256=parsed["sampling_plan_sha256"],
        )

    def to_dict(self) -> dict[str, str | None]:
        return {
            "payload_sha256": self.payload_sha256,
            "validation_artifact_sha256": self.validation_artifact_sha256,
            "validation_evidence_sha256": self.validation_evidence_sha256,
            "review_decision_sha256": self.review_decision_sha256,
            "validation_profile_sha256": self.validation_profile_sha256,
            "sampling_plan_sha256": self.sampling_plan_sha256,
        }


def _hash_bindings(
    value: ReleaseHashBindings | Mapping[str, Any],
) -> ReleaseHashBindings:
    if isinstance(value, ReleaseHashBindings):
        return value
    return ReleaseHashBindings.from_mapping(value)


@dataclass(frozen=True)
class ReleaseBlocker:
    code: str
    message: str


@dataclass(frozen=True)
class ReleaseEligibility:
    eligible: bool
    blockers: tuple[ReleaseBlocker, ...]

    def __post_init__(self) -> None:
        if self.eligible != (not self.blockers):
            _contract_error(
                "inconsistent_release_eligibility",
                "eligible must be true exactly when blockers are empty",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "blockers": [
                {"code": blocker.code, "message": blocker.message}
                for blocker in self.blockers
            ],
        }


def evaluate_release_item(
    *,
    execution_status: str,
    validation_status: str,
    evidence_binding: str,
    approval_eligibility: str,
    review_status: str,
    current_hashes: ReleaseHashBindings | Mapping[str, Any],
    release_hashes: ReleaseHashBindings | Mapping[str, Any],
) -> ReleaseEligibility:
    """Evaluate every mandatory promotion gate in deterministic order."""

    execution = _enum(
        execution_status,
        ("pending", "running", "succeeded", "failed", "skipped"),
        field="execution_status",
    )
    validation = _enum(
        validation_status,
        ("not_run", "passed", "failed"),
        field="validation_status",
    )
    binding = _enum(
        evidence_binding,
        ("not_applicable", "bound", "stale"),
        field="evidence_binding",
    )
    approval = _enum(
        approval_eligibility,
        ("blocked", "eligible"),
        field="approval_eligibility",
    )
    review = _enum(
        review_status,
        ("not_requested", "pending", "approved", "rejected"),
        field="review_status",
    )
    current = _hash_bindings(current_hashes)
    candidate = _hash_bindings(release_hashes)

    blockers: list[ReleaseBlocker] = []
    if execution != "succeeded":
        blockers.append(ReleaseBlocker(
            "execution_not_succeeded",
            "Release requires successful extraction execution",
        ))
    if validation != "passed":
        blockers.append(ReleaseBlocker(
            "validation_not_passed",
            "Release requires passed machine validation",
        ))
    if binding != "bound":
        blockers.append(ReleaseBlocker(
            "evidence_not_bound",
            "Release requires a Review Decision bound to current evidence",
        ))
    if approval != "eligible":
        blockers.append(ReleaseBlocker(
            "approval_not_eligible",
            "Release requires final approval eligibility",
        ))
    if review != "approved":
        blockers.append(ReleaseBlocker(
            "review_not_approved",
            "Release requires the current approved Review Decision",
        ))
    if candidate != current:
        blockers.append(ReleaseBlocker(
            "current_hash_mismatch",
            "Release hashes must exactly match all current Batch Item hashes",
        ))
    return ReleaseEligibility(not blockers, tuple(blockers))


def release_item_predicate(**values: Any) -> bool:
    """Boolean adapter for the complete release item gate."""

    return evaluate_release_item(**values).eligible


is_release_item_eligible = release_item_predicate


def _non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        _contract_error(
            "invalid_string",
            f"{field} must be a non-empty string",
        )
    return value


def _relative_path(value: Any, *, field: str) -> str:
    path = _non_empty_string(value, field=field)
    if path.startswith("/") or ".." in path.split("/"):
        _contract_error(
            "invalid_relative_path",
            f"{field} must be a repository-relative path without '..'",
        )
    return path


def _artifact(value: Any, *, field: str) -> Mapping[str, Any]:
    artifact = _closed_mapping(
        value,
        fields=frozenset({"path", "sha256"}),
        context=field,
    )
    _relative_path(artifact["path"], field=f"{field}.path")
    try:
        require_sha256(artifact["sha256"], field=f"{field}.sha256")
    except ValueError as error:
        _contract_error("invalid_sha256", str(error))
    return artifact


def _profile_identity(value: Any, *, field: str) -> Mapping[str, Any]:
    identity = _closed_mapping(
        value,
        fields=frozenset({"id", "schema_version", "path", "sha256"}),
        context=field,
    )
    _non_empty_string(identity["id"], field=f"{field}.id")
    _non_empty_string(
        identity["schema_version"],
        field=f"{field}.schema_version",
    )
    _relative_path(identity["path"], field=f"{field}.path")
    try:
        require_sha256(identity["sha256"], field=f"{field}.sha256")
    except ValueError as error:
        _contract_error("invalid_sha256", str(error))
    return identity


def _coverage_count(value: Any, *, field: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _contract_error(
            "invalid_coverage_count",
            f"{field} must be an integer greater than or equal to {minimum}",
        )
    return value


def validate_release_manifest_bindings(manifest: Mapping[str, Any]) -> bool:
    """Fail closed on cross-field identities in a Release Manifest 1.0.

    JSON Schema owns wire-shape validation.  This pure semantic pass repeats
    the closed-world boundaries it consumes and proves that each Release item
    is internally bound to the single profile and Blob target at the envelope.
    """

    document = _closed_mapping(
        manifest,
        fields=frozenset({
            "schema_version",
            "release_id",
            "created_at",
            "batch_id",
            "batch_manifest",
            "input_manifest",
            "validation_profile",
            "content_sampling_profile",
            "target",
            "assurance",
            "items",
        }),
        context="Release Manifest",
    )
    if document["schema_version"] != "1.0":
        _contract_error(
            "invalid_schema_version",
            "Release Manifest schema_version must be 1.0",
        )
    for field in ("release_id", "created_at", "batch_id"):
        _non_empty_string(document[field], field=field)
    _artifact(document["batch_manifest"], field="batch_manifest")
    _artifact(document["input_manifest"], field="input_manifest")
    validation_profile = _profile_identity(
        document["validation_profile"],
        field="validation_profile",
    )
    _profile_identity(
        document["content_sampling_profile"],
        field="content_sampling_profile",
    )
    target = _closed_mapping(
        document["target"],
        fields=frozenset({"account_url", "container", "prefix"}),
        context="target",
    )
    _non_empty_string(target["account_url"], field="target.account_url")
    target_container = _non_empty_string(
        target["container"],
        field="target.container",
    )
    if not isinstance(target["prefix"], str):
        _contract_error(
            "invalid_string",
            "target.prefix must be a string",
        )
    if target["prefix"].startswith("/") or ".." in target["prefix"].split("/"):
        _contract_error(
            "invalid_relative_path",
            "target.prefix must not be absolute or contain '..'",
        )
    assurance = _closed_mapping(
        document["assurance"],
        fields=frozenset({
            "structural_scope",
            "content_claim",
            "excluded_claims",
        }),
        context="assurance",
    )
    if (
        isinstance(assurance["excluded_claims"], (str, bytes, Mapping))
        or not isinstance(assurance["excluded_claims"], Sequence)
    ):
        _contract_error(
            "invalid_excluded_claims",
            "assurance.excluded_claims must be an array",
        )

    items = document["items"]
    if isinstance(items, (str, bytes, Mapping)) or not isinstance(
        items, Sequence
    ):
        _contract_error("invalid_release_items", "items must be an array")
    if not items:
        _contract_error(
            "empty_release_items",
            "Release Manifest items cannot be empty",
        )
    item_fields = frozenset({
        "item_id",
        "resource_key",
        "language",
        "payload",
        "validation_path",
        "review_decision_path",
        "review_decision_id",
        "bindings",
        "coverage",
        "target_blob",
    })
    parsed_items = tuple(
        _closed_mapping(
            item,
            fields=item_fields,
            context=f"items[{index}]",
        )
        for index, item in enumerate(items)
    )
    item_ids = [
        _non_empty_string(item["item_id"], field=f"items[{index}].item_id")
        for index, item in enumerate(parsed_items)
    ]
    if len(set(item_ids)) != len(item_ids):
        _contract_error(
            "duplicate_release_item_id",
            "Release Manifest item_id values must be unique",
        )

    release_paths: list[str] = []
    target_blobs: list[tuple[str, str]] = []
    for index, item in enumerate(parsed_items):
        resource_key = _non_empty_string(
            item["resource_key"],
            field=f"items[{index}].resource_key",
        )
        language = _enum(
            item["language"],
            ("zh-cn", "en-us"),
            field=f"items[{index}].language",
        )
        if item["item_id"] != f"{language}/{resource_key}":
            _contract_error(
                "release_item_identity_mismatch",
                "Release item_id must equal language/resource_key",
            )
        payload = _closed_mapping(
            item["payload"],
            fields=frozenset({"source_path", "release_path", "sha256"}),
            context=f"items[{index}].payload",
        )
        _relative_path(
            payload["source_path"],
            field=f"items[{index}].payload.source_path",
        )
        release_path = _relative_path(
            payload["release_path"],
            field=f"items[{index}].payload.release_path",
        )
        try:
            payload_sha256 = require_sha256(
                payload["sha256"],
                field=f"items[{index}].payload.sha256",
            )
            require_sha256(
                item["review_decision_id"],
                field=f"items[{index}].review_decision_id",
            )
        except ValueError as error:
            _contract_error("invalid_sha256", str(error))
        _relative_path(
            item["validation_path"],
            field=f"items[{index}].validation_path",
        )
        _relative_path(
            item["review_decision_path"],
            field=f"items[{index}].review_decision_path",
        )
        bindings = _hash_bindings(item["bindings"])
        if payload_sha256 != bindings.payload_sha256:
            _contract_error(
                "release_payload_binding_mismatch",
                "Payload artifact SHA must equal bindings.payload_sha256",
            )
        if (
            bindings.validation_profile_sha256
            != validation_profile["sha256"]
        ):
            _contract_error(
                "release_validation_profile_binding_mismatch",
                "Item Validation Profile SHA must equal the envelope profile SHA",
            )

        coverage = _closed_mapping(
            item["coverage"],
            fields=frozenset({
                "mode",
                "universe_count",
                "selected_count",
                "untested_count",
            }),
            context=f"items[{index}].coverage",
        )
        mode = _enum(
            coverage["mode"],
            ("full", "stratified_sample"),
            field=f"items[{index}].coverage.mode",
        )
        universe_count = _coverage_count(
            coverage["universe_count"],
            field=f"items[{index}].coverage.universe_count",
            minimum=1,
        )
        selected_count = _coverage_count(
            coverage["selected_count"],
            field=f"items[{index}].coverage.selected_count",
            minimum=1,
        )
        untested_count = _coverage_count(
            coverage["untested_count"],
            field=f"items[{index}].coverage.untested_count",
            minimum=0,
        )
        if universe_count != selected_count + untested_count:
            _contract_error(
                "release_coverage_count_mismatch",
                "Coverage universe_count must equal selected_count plus untested_count",
            )
        if mode == "full" and (
            selected_count != universe_count or untested_count != 0
        ):
            _contract_error(
                "release_full_coverage_incomplete",
                "Full coverage must select the entire universe with no untested items",
            )
        if mode == "full" and bindings.sampling_plan_sha256 is not None:
            _contract_error(
                "release_full_sampling_plan_forbidden",
                "Full coverage must not bind a Sampling Plan SHA",
            )
        if (
            mode == "stratified_sample"
            and bindings.sampling_plan_sha256 is None
        ):
            _contract_error(
                "release_stratified_sampling_plan_required",
                "Stratified coverage requires a Sampling Plan SHA",
            )

        target_blob = _closed_mapping(
            item["target_blob"],
            fields=frozenset({"container", "name"}),
            context=f"items[{index}].target_blob",
        )
        blob_container = _non_empty_string(
            target_blob["container"],
            field=f"items[{index}].target_blob.container",
        )
        blob_name = _relative_path(
            target_blob["name"],
            field=f"items[{index}].target_blob.name",
        )
        if blob_container != target_container:
            _contract_error(
                "release_target_container_mismatch",
                "Item target Blob container must equal the envelope target container",
            )
        release_paths.append(release_path)
        target_blobs.append((blob_container, blob_name))

    if len(set(release_paths)) != len(release_paths):
        _contract_error(
            "duplicate_release_path",
            "Release payload release_path values must be unique",
        )
    if len(set(target_blobs)) != len(target_blobs):
        _contract_error(
            "duplicate_target_blob_identity",
            "Release target Blob identities must be unique",
        )
    return True


def derive_release_content_sha256(manifest: Mapping[str, Any]) -> str:
    """Hash the Batch-bound payload identities independent of target/time."""

    validate_release_manifest_bindings(manifest)
    return canonical_sha256({
        "batch_id": manifest["batch_id"],
        "payloads": [
            {
                "item_id": item["item_id"],
                "payload_sha256": item["payload"]["sha256"],
            }
            for item in sorted(manifest["items"], key=lambda value: value["item_id"])
        ],
    })


def validate_publication_receipt_bindings(receipt: Mapping[str, Any]) -> bool:
    """Fail closed on Publication Receipt 1.0 identities."""

    document = _closed_mapping(
        receipt,
        fields=frozenset({
            "schema_version",
            "receipt_id",
            "published_at",
            "batch_id",
            "release_id",
            "release_manifest",
            "release_seal",
            "target",
            "items",
        }),
        context="Publication Receipt",
    )
    if document["schema_version"] != "1.0":
        _contract_error(
            "invalid_schema_version",
            "Publication Receipt schema_version must be 1.0",
        )
    for field in ("receipt_id", "published_at", "batch_id", "release_id"):
        _non_empty_string(document[field], field=field)
    try:
        require_sha256(document["receipt_id"], field="receipt_id")
        require_sha256(document["release_seal"], field="release_seal")
    except ValueError as error:
        _contract_error("invalid_sha256", str(error))
    _artifact(document["release_manifest"], field="release_manifest")
    target = _closed_mapping(
        document["target"],
        fields=frozenset({"account_url", "container", "prefix"}),
        context="target",
    )
    _non_empty_string(target["account_url"], field="target.account_url")
    target_container = _non_empty_string(
        target["container"],
        field="target.container",
    )
    if not isinstance(target["prefix"], str):
        _contract_error(
            "invalid_string",
            "target.prefix must be a string",
        )
    if target["prefix"].startswith("/") or ".." in target["prefix"].split("/"):
        _contract_error(
            "invalid_relative_path",
            "target.prefix must not be absolute or contain '..'",
        )

    items = document["items"]
    if isinstance(items, (str, bytes, Mapping)) or not isinstance(
        items, Sequence
    ):
        _contract_error("invalid_receipt_items", "items must be an array")
    if not items:
        _contract_error(
            "empty_receipt_items",
            "Publication Receipt items cannot be empty",
        )
    item_fields = frozenset({
        "item_id",
        "resource_key",
        "language",
        "payload",
        "target_blob",
        "remote",
    })
    parsed_items = tuple(
        _closed_mapping(
            item,
            fields=item_fields,
            context=f"items[{index}]",
        )
        for index, item in enumerate(items)
    )
    item_ids: list[str] = []
    remote_blobs: list[tuple[str, str]] = []
    for index, item in enumerate(parsed_items):
        resource_key = _non_empty_string(
            item["resource_key"],
            field=f"items[{index}].resource_key",
        )
        language = _enum(
            item["language"],
            ("zh-cn", "en-us"),
            field=f"items[{index}].language",
        )
        item_id = _non_empty_string(
            item["item_id"],
            field=f"items[{index}].item_id",
        )
        if item_id != f"{language}/{resource_key}":
            _contract_error(
                "receipt_item_identity_mismatch",
                "Publication Receipt item_id must equal language/resource_key",
            )
        item_ids.append(item_id)
        payload = _closed_mapping(
            item["payload"],
            fields=frozenset({"release_path", "sha256"}),
            context=f"items[{index}].payload",
        )
        _relative_path(
            payload["release_path"],
            field=f"items[{index}].payload.release_path",
        )
        try:
            payload_sha256 = require_sha256(
                payload["sha256"],
                field=f"items[{index}].payload.sha256",
            )
        except ValueError as error:
            _contract_error("invalid_sha256", str(error))
        target_blob = _closed_mapping(
            item["target_blob"],
            fields=frozenset({"container", "name"}),
            context=f"items[{index}].target_blob",
        )
        blob_container = _non_empty_string(
            target_blob["container"],
            field=f"items[{index}].target_blob.container",
        )
        blob_name = _relative_path(
            target_blob["name"],
            field=f"items[{index}].target_blob.name",
        )
        if blob_container != target_container:
            _contract_error(
                "receipt_target_container_mismatch",
                "Receipt target Blob container must equal the envelope target",
            )
        remote = _closed_mapping(
            item["remote"],
            fields=frozenset({
                "account_url",
                "container",
                "name",
                "sha256",
                "content_length",
                "etag",
            }),
            context=f"items[{index}].remote",
        )
        if remote["account_url"] != target["account_url"]:
            _contract_error(
                "receipt_remote_account_mismatch",
                "Remote account URL must equal the frozen target",
            )
        if remote["container"] != blob_container or remote["name"] != blob_name:
            _contract_error(
                "receipt_remote_blob_mismatch",
                "Remote Blob identity must equal target_blob",
            )
        try:
            remote_sha256 = require_sha256(
                remote["sha256"],
                field=f"items[{index}].remote.sha256",
            )
        except ValueError as error:
            _contract_error("invalid_sha256", str(error))
        if remote_sha256 != payload_sha256:
            _contract_error(
                "receipt_remote_payload_mismatch",
                "Remote SHA-256 must equal payload SHA-256",
            )
        if (
            isinstance(remote["content_length"], bool)
            or not isinstance(remote["content_length"], int)
            or remote["content_length"] < 0
        ):
            _contract_error(
                "invalid_content_length",
                "remote.content_length must be a non-negative integer",
            )
        _non_empty_string(remote["etag"], field=f"items[{index}].remote.etag")
        remote_blobs.append((blob_container, blob_name))
    if len(set(item_ids)) != len(item_ids):
        _contract_error(
            "duplicate_receipt_item_id",
            "Publication Receipt item_id values must be unique",
        )
    if len(set(remote_blobs)) != len(remote_blobs):
        _contract_error(
            "duplicate_receipt_blob_identity",
            "Publication Receipt remote Blob identities must be unique",
        )
    if document["receipt_id"] != derive_publication_receipt_id(document):
        _contract_error(
            "receipt_identity_mismatch",
            "Publication Receipt identity does not match its canonical body",
        )
    return True


def derive_publication_receipt_id(receipt: Mapping[str, Any]) -> str:
    """Hash a Publication Receipt while excluding its self identity."""

    return document_identity_sha256(receipt, "receipt_id")


def derive_release_seal(
    manifest_sha256: str,
    payload_hashes_by_item: Mapping[str, str],
) -> str:
    """Bind a Release Manifest file hash and item-sorted payload hashes."""

    try:
        manifest = require_sha256(
            manifest_sha256,
            field="manifest_sha256",
        )
    except ValueError as error:
        _contract_error("invalid_sha256", str(error))
    if not isinstance(payload_hashes_by_item, Mapping):
        _contract_error(
            "invalid_payload_hashes",
            "payload_hashes_by_item must be an object",
        )
    if not payload_hashes_by_item:
        _contract_error(
            "empty_release",
            "A Release seal requires at least one payload",
        )
    if any(not isinstance(item_id, str) for item_id in payload_hashes_by_item):
        _contract_error(
            "invalid_item_id",
            "Release payload item IDs must be strings",
        )
    payloads: list[dict[str, str]] = []
    for item_id in sorted(payload_hashes_by_item):
        if not isinstance(item_id, str) or not item_id:
            _contract_error(
                "invalid_item_id",
                "Release payload item IDs must be non-empty strings",
            )
        try:
            payload_sha256 = require_sha256(
                payload_hashes_by_item[item_id],
                field=f"payload_hashes_by_item[{item_id!r}]",
            )
        except ValueError as error:
            _contract_error("invalid_sha256", str(error))
        payloads.append({
            "item_id": item_id,
            "payload_sha256": payload_sha256,
        })
    return canonical_sha256({
        "manifest_sha256": manifest,
        "payloads": payloads,
    })


release_seal = derive_release_seal


__all__ = [
    "ReleaseBlocker",
    "ReleaseContractError",
    "ReleaseEligibility",
    "ReleaseHashBindings",
    "derive_publication_receipt_id",
    "derive_release_content_sha256",
    "derive_release_seal",
    "evaluate_release_item",
    "is_release_item_eligible",
    "release_item_predicate",
    "release_seal",
    "validate_publication_receipt_bindings",
    "validate_release_manifest_bindings",
]
