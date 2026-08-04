"""Immutable Release promotion and upload gate for Step 4 Slice E."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.canonical_identity import canonical_json_bytes
from src.core.product_catalog import sha256_file
from src.core.settings import settings
from src.core.validation_context import ValidationContextRegistry
from src.pipeline.models import summarize_batch_manifest, utc_now
from src.pipeline.state_store import (
    ManifestConflictError,
    ManifestValidationError,
    RepositoryLock,
    StateStore,
)
from src.release.contracts import (
    ReleaseContractError,
    ReleaseHashBindings,
    derive_publication_receipt_id,
    derive_release_content_sha256,
    derive_release_seal,
    evaluate_release_item,
    validate_release_manifest_bindings,
)
from src.review.contracts import ReviewContractError, derive_evidence_binding
from src.review.service import ReviewService


RELEASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ReleaseServiceError(RuntimeError):
    """A Release operation failed with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ReleaseBuildResult:
    batch_id: str
    release_id: str
    release_manifest_path: str
    release_manifest_sha256: str
    release_seal: str
    release_content_sha256: str
    item_ids: tuple[str, ...]
    committed_revision: int
    recovered: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "release_id": self.release_id,
            "release_manifest_path": self.release_manifest_path,
            "release_manifest_sha256": self.release_manifest_sha256,
            "release_seal": self.release_seal,
            "release_content_sha256": self.release_content_sha256,
            "item_ids": list(self.item_ids),
            "committed_revision": self.committed_revision,
            "recovered": self.recovered,
        }


@dataclass(frozen=True)
class ReleaseVerifyResult:
    batch_id: str
    release_id: str
    release_manifest_path: str
    release_manifest_sha256: str
    release_seal: str
    release_content_sha256: str
    item_ids: tuple[str, ...]
    registered: bool
    manifest: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "release_id": self.release_id,
            "release_manifest_path": self.release_manifest_path,
            "release_manifest_sha256": self.release_manifest_sha256,
            "release_seal": self.release_seal,
            "release_content_sha256": self.release_content_sha256,
            "item_ids": list(self.item_ids),
            "registered": self.registered,
        }


@dataclass(frozen=True)
class RemoteBlobIdentity:
    account_url: str
    container: str
    name: str
    sha256: str
    content_length: int
    etag: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_url": self.account_url,
            "container": self.container,
            "name": self.name,
            "sha256": self.sha256,
            "content_length": self.content_length,
            "etag": self.etag,
        }


@dataclass(frozen=True)
class ReleaseUploadResult:
    batch_id: str
    release_id: str
    release_manifest_path: str
    release_manifest_sha256: str
    release_seal: str
    dry_run: bool
    item_ids: tuple[str, ...]
    remote_blobs: tuple[Mapping[str, Any], ...]
    publication_receipt_path: str | None = None
    publication_receipt_sha256: str | None = None
    committed_revision: int | None = None
    idempotent: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "release_id": self.release_id,
            "release_manifest_path": self.release_manifest_path,
            "release_manifest_sha256": self.release_manifest_sha256,
            "release_seal": self.release_seal,
            "dry_run": self.dry_run,
            "item_ids": list(self.item_ids),
            "remote_blobs": [dict(value) for value in self.remote_blobs],
            "publication_receipt_path": self.publication_receipt_path,
            "publication_receipt_sha256": self.publication_receipt_sha256,
            "committed_revision": self.committed_revision,
            "idempotent": self.idempotent,
        }


def _error(code: str, message: str) -> ReleaseServiceError:
    return ReleaseServiceError(code, message)


def _artifact(path: str, sha256: str) -> dict[str, str]:
    return {"path": path, "sha256": sha256}


def _join_blob(prefix: str, relative: str) -> str:
    clean_prefix = prefix.strip("/")
    clean_relative = relative.strip("/")
    return f"{clean_prefix}/{clean_relative}" if clean_prefix else clean_relative


def _write_canonical_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def _read_json_object(path: Path, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _error(code, f"Unable to read JSON document: {path}") from error
    if not isinstance(value, dict):
        raise _error(code, f"JSON document must be an object: {path}")
    return value


class AzureReleaseBlobTransport:
    """Azure Blob transport that never overwrites release payload blobs."""

    def __init__(self, *, account_url: str, container: str) -> None:
        if not settings.AZURE_STORAGE_CONNECTION_STRING:
            raise _error(
                "missing_azure_storage_connection",
                "AZURE_STORAGE_CONNECTION_STRING is required for release upload",
            )
        try:
            from azure.core.exceptions import (
                ResourceExistsError,
                ResourceNotFoundError,
            )
            from azure.storage.blob import BlobServiceClient, ContentSettings
        except Exception as error:  # pragma: no cover - dependency import guard
            raise _error("azure_storage_unavailable", str(error)) from error
        self._resource_exists_error = ResourceExistsError
        self._resource_not_found_error = ResourceNotFoundError
        self._content_settings = ContentSettings
        self.account_url = account_url.rstrip("/")
        self.container = container
        self.service_client = BlobServiceClient.from_connection_string(
            settings.AZURE_STORAGE_CONNECTION_STRING
        )
        actual_url = str(getattr(self.service_client, "url", "")).rstrip("/")
        if actual_url and actual_url != self.account_url:
            raise _error(
                "azure_account_mismatch",
                "Azure credential account URL does not match the Release target",
            )
        self.container_client = self.service_client.get_container_client(container)
        try:
            self.container_client.get_container_properties()
        except ResourceNotFoundError as error:
            raise _error(
                "azure_container_missing",
                f"Release target container does not exist: {container}",
            ) from error

    def upload_or_verify(
        self,
        local_path: Path,
        *,
        blob_name: str,
        expected_sha256: str,
    ) -> RemoteBlobIdentity:
        blob_client = self.container_client.get_blob_client(blob_name)
        try:
            with local_path.open("rb") as stream:
                blob_client.upload_blob(
                    stream,
                    overwrite=False,
                    content_settings=self._content_settings(
                        content_type="application/json",
                        content_encoding="utf-8",
                    ),
                )
        except self._resource_exists_error:
            pass
        return self._verified_identity(
            blob_client,
            blob_name=blob_name,
            expected_sha256=expected_sha256,
        )

    def _verified_identity(
        self,
        blob_client: Any,
        *,
        blob_name: str,
        expected_sha256: str,
    ) -> RemoteBlobIdentity:
        try:
            data = blob_client.download_blob().readall()
            properties = blob_client.get_blob_properties()
        except self._resource_not_found_error as error:
            raise _error(
                "remote_blob_missing",
                f"Uploaded Blob cannot be re-read: {blob_name}",
            ) from error
        remote_sha256 = hashlib.sha256(data).hexdigest()
        if remote_sha256 != expected_sha256:
            raise _error(
                "remote_blob_conflict",
                f"Remote Blob content differs from Release payload: {blob_name}",
            )
        return RemoteBlobIdentity(
            account_url=self.account_url,
            container=self.container,
            name=blob_name,
            sha256=remote_sha256,
            content_length=int(getattr(properties, "size", len(data))),
            etag=str(getattr(properties, "etag", "")),
        )


class ReleaseService:
    """Authority for immutable Release build, verification, and upload."""

    def __init__(
        self,
        root: str | Path = ".",
        runs_dir: str | Path = "runs",
        *,
        state_store: StateStore | None = None,
        review_service: ReviewService | None = None,
        now: Callable[[], str] = utc_now,
    ) -> None:
        self.root = Path(root).resolve()
        self.store = state_store or StateStore(self.root, runs_dir)
        self.review = review_service or ReviewService(
            self.root,
            runs_dir,
            state_store=self.store,
        )
        self.validation_context = ValidationContextRegistry(self.root)
        self._now = now
        self.releases_root = self.root / "output" / "releases"

    def build_release(
        self,
        *,
        batch_id: str,
        release_id: str,
        item_ids: Sequence[str],
        expected_revision: int,
        account_url: str,
        container: str,
        prefix: str = "",
    ) -> ReleaseBuildResult:
        self._validate_release_id(release_id)
        selected_item_ids = self._normalize_item_ids(item_ids)
        with RepositoryLock(
            self.store.lock_root,
            batch_id=batch_id,
            command="release-build",
        ):
            manifest = self.store.read_manifest(batch_id)
            if manifest["revision"] != expected_revision:
                raise ManifestConflictError(
                    f"Batch {batch_id} revision is {manifest['revision']}, "
                    f"expected {expected_revision}"
                )
            if self._profile_id(manifest) != "v0.4-validation-p3":
                raise _error(
                    "unsupported_release_profile",
                    "Release build requires Validation Profile P3",
                )
            if manifest["status"] not in ("completed", "completed_with_failures"):
                raise _error(
                    "batch_not_terminal",
                    "Release build requires a completed Batch",
                )

            release_dir = self.releases_root / release_id
            release_manifest = release_dir / "release-manifest.json"
            if release_dir.exists():
                verified = self.verify_release(
                    release_manifest,
                    require_batch_reference=False,
                )
                if (
                    verified.batch_id == batch_id
                    and verified.release_id == release_id
                    and verified.item_ids == selected_item_ids
                    and dict(verified.manifest["target"]) == {
                        "account_url": account_url.rstrip("/"),
                        "container": container,
                        "prefix": prefix.strip("/"),
                    }
                ):
                    updated = self._register_release(
                        batch_id=batch_id,
                        release_id=release_id,
                        release_manifest_path=verified.release_manifest_path,
                        release_manifest_sha256=verified.release_manifest_sha256,
                        item_ids=selected_item_ids,
                        expected_revision=manifest["revision"],
                    )
                    return ReleaseBuildResult(
                        batch_id=batch_id,
                        release_id=release_id,
                        release_manifest_path=verified.release_manifest_path,
                        release_manifest_sha256=verified.release_manifest_sha256,
                        release_seal=verified.release_seal,
                        release_content_sha256=verified.release_content_sha256,
                        item_ids=selected_item_ids,
                        committed_revision=int(updated["revision"]),
                        recovered=True,
                    )
                raise _error(
                    "release_already_exists",
                    f"Release directory already exists: {release_dir}",
                )

            candidate_manifest = self._stage_release(
                batch_id=batch_id,
                release_id=release_id,
                item_ids=selected_item_ids,
                manifest=manifest,
                account_url=account_url.rstrip("/"),
                container=container,
                prefix=prefix.strip("/"),
            )
            manifest_sha256 = sha256_file(release_manifest)
            payload_hashes = {
                item["item_id"]: item["payload"]["sha256"]
                for item in candidate_manifest["items"]
            }
            release_seal = derive_release_seal(manifest_sha256, payload_hashes)
            release_content_sha256 = derive_release_content_sha256(
                candidate_manifest
            )
            updated = self._register_release(
                batch_id=batch_id,
                release_id=release_id,
                release_manifest_path=self._root_relative(release_manifest),
                release_manifest_sha256=manifest_sha256,
                item_ids=selected_item_ids,
                expected_revision=manifest["revision"],
            )
            return ReleaseBuildResult(
                batch_id=batch_id,
                release_id=release_id,
                release_manifest_path=self._root_relative(release_manifest),
                release_manifest_sha256=manifest_sha256,
                release_seal=release_seal,
                release_content_sha256=release_content_sha256,
                item_ids=selected_item_ids,
                committed_revision=int(updated["revision"]),
            )

    def verify_release(
        self,
        release_manifest_path: str | Path,
        *,
        require_batch_reference: bool = False,
    ) -> ReleaseVerifyResult:
        path = self._release_manifest_path(release_manifest_path)
        if path.name != "release-manifest.json":
            raise _error(
                "invalid_release_manifest_path",
                "Release verification requires output/releases/<release_id>/release-manifest.json",
            )
        release_dir = path.parent
        release_id = release_dir.name
        if release_dir.parent != self.releases_root:
            raise _error(
                "invalid_release_manifest_path",
                "Release Manifest must live under output/releases/<release_id>",
            )
        self._validate_release_id(release_id)
        self._assert_regular_file(path, label="Release Manifest")
        manifest = _read_json_object(path, code="release_manifest_unreadable")
        if manifest.get("release_id") != release_id:
            raise _error(
                "release_id_path_mismatch",
                "Release Manifest release_id must match its directory",
            )
        if path.read_bytes() != canonical_json_bytes(manifest):
            raise _error(
                "release_manifest_not_canonical",
                "Release Manifest bytes are not canonical JSON",
            )
        try:
            self.store.validate_document(manifest, "release_manifest")
            validate_release_manifest_bindings(manifest)
        except ReleaseContractError as error:
            raise _error(
                error.code,
                str(error),
            ) from error
        except ManifestValidationError as error:
            raise _error(
                "invalid_release_manifest",
                str(error),
            ) from error

        batch_id = str(manifest["batch_id"])
        current_manifest = self.store.read_manifest(batch_id)
        release_rel = self._root_relative(path)
        manifest_sha256 = sha256_file(path)
        registered = self._release_reference_is_current(
            current_manifest,
            release_rel,
            manifest_sha256,
            item_ids=tuple(item["item_id"] for item in manifest["items"]),
        )
        if require_batch_reference and not registered:
            raise _error(
                "release_not_registered",
                "Batch Manifest does not currently reference this Release",
            )

        self._verify_release_evidence_artifact(
            release_dir,
            manifest["batch_manifest"],
            label="batch_manifest",
        )
        self._verify_release_evidence_artifact(
            release_dir,
            manifest["input_manifest"],
            label="input_manifest",
        )
        for item in manifest["items"]:
            self._verify_release_item_files(
                release_dir,
                batch_id=batch_id,
                release_item=item,
                current_manifest=current_manifest,
            )

        payload_hashes = {
            item["item_id"]: item["payload"]["sha256"]
            for item in manifest["items"]
        }
        release_seal = derive_release_seal(manifest_sha256, payload_hashes)
        return ReleaseVerifyResult(
            batch_id=batch_id,
            release_id=release_id,
            release_manifest_path=release_rel,
            release_manifest_sha256=manifest_sha256,
            release_seal=release_seal,
            release_content_sha256=derive_release_content_sha256(manifest),
            item_ids=tuple(item["item_id"] for item in manifest["items"]),
            registered=registered,
            manifest=copy.deepcopy(manifest),
        )

    def upload_release(
        self,
        release_manifest_path: str | Path,
        *,
        expected_revision: int | None = None,
        dry_run: bool = False,
        transport: Any | None = None,
    ) -> ReleaseUploadResult:
        verified = self.verify_release(
            release_manifest_path,
            require_batch_reference=True,
        )
        manifest = verified.manifest
        if dry_run:
            return ReleaseUploadResult(
                batch_id=verified.batch_id,
                release_id=verified.release_id,
                release_manifest_path=verified.release_manifest_path,
                release_manifest_sha256=verified.release_manifest_sha256,
                release_seal=verified.release_seal,
                dry_run=True,
                item_ids=verified.item_ids,
                remote_blobs=tuple(
                    {
                        "account_url": manifest["target"]["account_url"],
                        "container": item["target_blob"]["container"],
                        "name": item["target_blob"]["name"],
                        "sha256": item["payload"]["sha256"],
                        "content_length": self._root_path(
                            item["payload"]["release_path"]
                        ).stat().st_size,
                        "etag": "[DRY_RUN]",
                    }
                    for item in manifest["items"]
                ),
            )
        if expected_revision is None:
            raise _error(
                "missing_expected_revision",
                "Release upload requires expected_revision",
            )
        blob_transport = transport or AzureReleaseBlobTransport(
            account_url=str(manifest["target"]["account_url"]),
            container=str(manifest["target"]["container"]),
        )
        remote_by_item: dict[str, RemoteBlobIdentity] = {}
        for item in manifest["items"]:
            payload_path = self._root_path(item["payload"]["release_path"])
            remote = blob_transport.upload_or_verify(
                payload_path,
                blob_name=str(item["target_blob"]["name"]),
                expected_sha256=str(item["payload"]["sha256"]),
            )
            expected_target = {
                "account_url": manifest["target"]["account_url"],
                "container": item["target_blob"]["container"],
                "name": item["target_blob"]["name"],
            }
            if {
                "account_url": remote.account_url,
                "container": remote.container,
                "name": remote.name,
            } != expected_target:
                raise _error(
                    "remote_identity_mismatch",
                    "Remote Blob identity differs from the Release target",
                )
            remote_by_item[str(item["item_id"])] = remote
        return self._commit_publication(
            verified=verified,
            remote_by_item=remote_by_item,
            expected_revision=expected_revision,
        )

    def _stage_release(
        self,
        *,
        batch_id: str,
        release_id: str,
        item_ids: tuple[str, ...],
        manifest: Mapping[str, Any],
        account_url: str,
        container: str,
        prefix: str,
    ) -> dict[str, Any]:
        self.releases_root.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{release_id}.",
                dir=self.releases_root,
            )
        )
        release_dir = self.releases_root / release_id
        try:
            evidence_dir = staging / "evidence"
            evidence_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(
                self.store.run_dir(batch_id) / "batch-manifest.json",
                evidence_dir / "batch-manifest.json",
            )
            shutil.copy2(
                self.store.run_dir(batch_id) / "input-manifest.json",
                evidence_dir / "input-manifest.json",
            )
            release_items: list[dict[str, Any]] = []
            for item_id in item_ids:
                release_items.append(
                    self._stage_release_item(
                        batch_id=batch_id,
                        release_id=release_id,
                        manifest=manifest,
                        item_id=item_id,
                        staging=staging,
                        container=container,
                        prefix=prefix,
                    )
                )
            validation_profile = dict(
                manifest["validation_context"]["validation_profile"]
            )
            sampling_profile = (
                self.validation_context.content_sampling_profile_identity_for(
                    validation_profile
                )
            )
            if sampling_profile is None:
                raise _error(
                    "missing_content_sampling_profile",
                    "Release build requires the P3 Content Sampling Profile",
                )
            release_manifest = {
                "schema_version": "1.0",
                "release_id": release_id,
                "created_at": self._now(),
                "batch_id": batch_id,
                "batch_manifest": _artifact(
                    f"output/releases/{release_id}/evidence/batch-manifest.json",
                    sha256_file(evidence_dir / "batch-manifest.json"),
                ),
                "input_manifest": _artifact(
                    f"output/releases/{release_id}/evidence/input-manifest.json",
                    sha256_file(evidence_dir / "input-manifest.json"),
                ),
                "validation_profile": validation_profile,
                "content_sampling_profile": sampling_profile,
                "target": {
                    "account_url": account_url,
                    "container": container,
                    "prefix": prefix,
                },
                "assurance": {
                    "structural_scope": "all_source_proven_reachable_states",
                    "content_claim": "sampled_state_content_consistency",
                    "excluded_claims": [
                        "unselected_state_content_consistency",
                        "complete_pricing_fact_fidelity",
                        "commercial_price_accuracy",
                        "visual_equivalence",
                    ],
                },
                "items": release_items,
            }
            self.store.validate_document(release_manifest, "release_manifest")
            _write_canonical_json(staging / "release-manifest.json", release_manifest)
            if release_dir.exists():
                raise _error(
                    "release_already_exists",
                    f"Release directory already exists: {release_dir}",
                )
            os.replace(staging, release_dir)
            return release_manifest
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise

    def _stage_release_item(
        self,
        *,
        batch_id: str,
        release_id: str,
        manifest: Mapping[str, Any],
        item_id: str,
        staging: Path,
        container: str,
        prefix: str,
    ) -> dict[str, Any]:
        if item_id not in manifest["items"]:
            raise _error("unknown_item", f"Unknown Batch Item: {item_id}")
        snapshot = self.review.evidence_snapshot(
            batch_id,
            item_id,
            manifest=manifest,
        )
        release_hashes = self._release_hashes(snapshot, manifest)
        self._assert_release_eligible(snapshot, release_hashes, manifest)
        manifest_item = snapshot.manifest_item
        if manifest_item["status"]["publication"] != "not_published":
            raise _error(
                "item_already_published",
                f"Published item cannot enter a new Release: {item_id}",
            )
        if manifest_item["status"]["release"] != "not_released":
            raise _error(
                "item_already_released",
                f"Released item cannot enter a new Release: {item_id}",
            )
        payload_ref = manifest_item["artifacts"]["payload"]
        source_relative = Path(payload_ref["path"])
        if source_relative.parts[:1] != ("outputs",):
            raise _error(
                "invalid_payload_artifact_path",
                f"Release payload must come from canonical outputs: {payload_ref['path']}",
            )
        source_path = self.store.run_dir(batch_id) / source_relative
        self._assert_regular_file(source_path, label=f"payload {item_id}")
        payload_sha256 = sha256_file(source_path)
        if payload_sha256 != release_hashes.payload_sha256:
            raise _error(
                "payload_hash_mismatch",
                f"Payload file hash does not match current evidence for {item_id}",
            )

        payload_inside_release = Path("payloads", *source_relative.parts[1:])
        staged_payload = staging / payload_inside_release
        staged_payload.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, staged_payload)
        if sha256_file(staged_payload) != payload_sha256:
            raise _error(
                "release_payload_copy_mismatch",
                f"Copied Release payload hash drifted for {item_id}",
            )
        release_path = (
            Path("output", "releases", release_id, payload_inside_release)
            .as_posix()
        )
        blob_relative = Path(*payload_inside_release.parts[1:]).as_posix()
        target_blob_name = _join_blob(prefix, blob_relative)
        coverage = snapshot.coverage
        decision = snapshot.current_decision
        if decision is None or snapshot.current_decision_reference is None:
            raise _error(
                "missing_current_review_decision",
                f"Release requires a current Review Decision for {item_id}",
            )
        return {
            "item_id": item_id,
            "resource_key": snapshot.item.resource_key,
            "language": snapshot.item.language,
            "payload": {
                "source_path": self._run_relative(batch_id, payload_ref["path"]),
                "release_path": release_path,
                "sha256": payload_sha256,
            },
            "validation_path": self._run_relative(
                batch_id,
                manifest_item["artifacts"]["validation"]["path"],
            ),
            "review_decision_path": self._run_relative(
                batch_id,
                snapshot.current_decision_reference["path"],
            ),
            "review_decision_id": decision["decision_id"],
            "bindings": release_hashes.to_dict(),
            "coverage": {
                "mode": coverage["mode"],
                "universe_count": coverage["universe_count"],
                "selected_count": coverage["selected_count"],
                "untested_count": coverage["untested_count"],
            },
            "target_blob": {
                "container": container,
                "name": target_blob_name,
            },
        }

    def _verify_release_item_files(
        self,
        release_dir: Path,
        *,
        batch_id: str,
        release_item: Mapping[str, Any],
        current_manifest: Mapping[str, Any],
    ) -> None:
        item_id = str(release_item["item_id"])
        release_path = self._root_path(release_item["payload"]["release_path"])
        self._assert_under(
            release_path,
            release_dir / "payloads",
            code="release_payload_path_invalid",
            message="Release payload path must stay under the Release payloads directory",
        )
        self._assert_regular_file(release_path, label=f"release payload {item_id}")
        if sha256_file(release_path) != release_item["payload"]["sha256"]:
            raise _error(
                "release_payload_hash_mismatch",
                f"Release payload hash drifted for {item_id}",
            )

        source_path = self._root_path(release_item["payload"]["source_path"])
        self._assert_under(
            source_path,
            self.store.run_dir(batch_id) / "outputs",
            code="release_source_path_invalid",
            message="Release source payload must come from canonical Batch outputs",
        )
        self._assert_regular_file(source_path, label=f"source payload {item_id}")
        if sha256_file(source_path) != release_item["payload"]["sha256"]:
            raise _error(
                "release_source_payload_hash_mismatch",
                f"Source payload hash drifted for {item_id}",
            )

        validation_path = self._root_path(release_item["validation_path"])
        self._assert_under(
            validation_path,
            self.store.run_dir(batch_id) / "validation",
            code="release_validation_path_invalid",
            message="Release validation path must stay under the Batch validation directory",
        )
        self._assert_regular_file(validation_path, label=f"validation {item_id}")
        if sha256_file(validation_path) != release_item["bindings"][
            "validation_artifact_sha256"
        ]:
            raise _error(
                "release_validation_hash_mismatch",
                f"Validation artifact hash drifted for {item_id}",
            )

        decision_path = self._root_path(release_item["review_decision_path"])
        self._assert_under(
            decision_path,
            self.store.run_dir(batch_id) / "review" / "decisions",
            code="release_review_decision_path_invalid",
            message="Release Review Decision path must stay under review/decisions",
        )
        self._assert_regular_file(
            decision_path,
            label=f"Review Decision {item_id}",
        )
        if sha256_file(decision_path) != release_item["bindings"][
            "review_decision_sha256"
        ]:
            raise _error(
                "release_review_decision_hash_mismatch",
                f"Review Decision hash drifted for {item_id}",
            )

        snapshot = self.review.evidence_snapshot(
            batch_id,
            item_id,
            manifest=current_manifest,
        )
        current_hashes = self._release_hashes(snapshot, current_manifest)
        candidate_hashes = ReleaseHashBindings.from_mapping(
            release_item["bindings"]
        )
        self._assert_release_eligible(snapshot, candidate_hashes, current_manifest)
        if current_hashes != candidate_hashes:
            raise _error(
                "current_hash_mismatch",
                f"Current Batch hashes differ from Release hashes for {item_id}",
            )
        self._verify_validation_children(snapshot, current_hashes)
        expected_coverage = {
            "mode": snapshot.coverage["mode"],
            "universe_count": snapshot.coverage["universe_count"],
            "selected_count": snapshot.coverage["selected_count"],
            "untested_count": snapshot.coverage["untested_count"],
        }
        if dict(release_item["coverage"]) != expected_coverage:
            raise _error(
                "release_coverage_mismatch",
                f"Release coverage differs from current validation evidence for {item_id}",
            )

    def _verify_validation_children(
        self,
        snapshot: Any,
        hashes: ReleaseHashBindings,
    ) -> None:
        evidence_ref = snapshot.manifest_item["artifacts"]["sampled_content_evidence"]
        if evidence_ref is None:
            raise _error(
                "missing_sampled_content_evidence",
                f"Sampled evidence is missing for {snapshot.item.item_id}",
            )
        evidence_path = self.store.run_dir(snapshot.batch_id) / evidence_ref["path"]
        self._assert_regular_file(
            evidence_path,
            label=f"sampled evidence {snapshot.item.item_id}",
        )
        if sha256_file(evidence_path) != evidence_ref["sha256"]:
            raise _error(
                "sampled_content_evidence_hash_mismatch",
                f"Sampled evidence artifact hash drifted for {snapshot.item.item_id}",
            )
        plan_ref = snapshot.manifest_item["artifacts"].get("sampling_plan")
        if hashes.sampling_plan_sha256 is None:
            if plan_ref is not None and plan_ref["sha256"] is not None:
                raise _error(
                    "unexpected_sampling_plan",
                    f"Full-mode Release item has a Sampling Plan for {snapshot.item.item_id}",
                )
            return
        if plan_ref is None or plan_ref["sha256"] is None:
            raise _error(
                "missing_sampling_plan",
                f"Release item is missing Sampling Plan artifact for {snapshot.item.item_id}",
            )
        plan_path = self.store.run_dir(snapshot.batch_id) / plan_ref["path"]
        self._assert_regular_file(
            plan_path,
            label=f"Sampling Plan {snapshot.item.item_id}",
        )
        if sha256_file(plan_path) != plan_ref["sha256"]:
            raise _error(
                "sampling_plan_artifact_hash_mismatch",
                f"Sampling Plan artifact hash drifted for {snapshot.item.item_id}",
            )
        if snapshot.sampling_plan is None:
            raise _error(
                "sampling_plan_binding_mismatch",
                f"Sampling Plan binding is missing for {snapshot.item.item_id}",
            )
        if snapshot.sampling_plan["plan_sha256"] != hashes.sampling_plan_sha256:
            raise _error(
                "sampling_plan_identity_mismatch",
                f"Sampling Plan semantic identity drifted for {snapshot.item.item_id}",
            )

    def _assert_release_eligible(
        self,
        snapshot: Any,
        release_hashes: ReleaseHashBindings,
        manifest: Mapping[str, Any],
    ) -> None:
        status = snapshot.manifest_item["status"]
        if snapshot.current_decision is None:
            raise _error(
                "missing_current_review_decision",
                f"Release requires a current Review Decision for {snapshot.item.item_id}",
            )
        try:
            binding = derive_evidence_binding(
                snapshot.current_bindings,
                snapshot.current_decision["bindings"],
            )
        except ReviewContractError as error:
            raise _error(error.code, str(error)) from error
        if binding != "bound":
            raise _error(
                "stale_review_evidence",
                f"Review Decision no longer binds current evidence for {snapshot.item.item_id}",
            )
        if snapshot.current_decision["verdict"] != "approved":
            raise _error(
                "review_not_approved",
                f"Release requires an approved Review Decision for {snapshot.item.item_id}",
            )
        current_hashes = self._release_hashes(snapshot, manifest)
        try:
            eligibility = evaluate_release_item(
                execution_status=status["execution"],
                validation_status=status["validation"],
                evidence_binding=status["evidence_binding"],
                approval_eligibility=status["approval_eligibility"],
                review_status=status["review"],
                current_hashes=current_hashes,
                release_hashes=release_hashes,
            )
        except ReleaseContractError as error:
            raise _error(error.code, str(error)) from error
        if not eligibility.eligible:
            blockers = ", ".join(blocker.code for blocker in eligibility.blockers)
            raise _error(
                "release_item_not_eligible",
                f"Batch Item cannot enter Release: {snapshot.item.item_id}: {blockers}",
            )

    def _release_hashes(
        self,
        snapshot: Any,
        manifest: Mapping[str, Any],
    ) -> ReleaseHashBindings:
        if snapshot.current_decision_reference is None:
            raise _error(
                "missing_current_review_decision",
                f"Release requires a current Review Decision for {snapshot.item.item_id}",
            )
        return ReleaseHashBindings(
            payload_sha256=snapshot.current_bindings.payload_sha256,
            validation_artifact_sha256=(
                snapshot.current_bindings.validation_artifact_sha256
            ),
            validation_evidence_sha256=(
                snapshot.current_bindings.validation_evidence_sha256
            ),
            review_decision_sha256=snapshot.current_decision_reference["sha256"],
            validation_profile_sha256=manifest["validation_context"][
                "validation_profile"
            ]["sha256"],
            sampling_plan_sha256=snapshot.current_bindings.sampling_plan_sha256,
        )

    def _register_release(
        self,
        *,
        batch_id: str,
        release_id: str,
        release_manifest_path: str,
        release_manifest_sha256: str,
        item_ids: tuple[str, ...],
        expected_revision: int,
    ) -> dict[str, Any]:
        current = self.store.read_manifest(batch_id)
        release_ref = {
            "path": release_manifest_path,
            "sha256": release_manifest_sha256,
        }
        if (
            release_ref in current.get("release_manifests", [])
            and all(
                current["items"][item_id]["status"]["release"] == "released"
                for item_id in item_ids
            )
        ):
            return current

        def mutate(value: dict[str, Any]) -> None:
            existing = list(value["release_manifests"])
            conflicting = [
                ref for ref in existing
                if ref["path"] == release_manifest_path and ref != release_ref
            ]
            if conflicting:
                raise _error(
                    "release_reference_conflict",
                    f"Release reference hash conflict for {release_id}",
                )
            if release_ref not in existing:
                value["release_manifests"] = [*existing, release_ref]
            for item_id in item_ids:
                value["items"][item_id]["status"]["release"] = "released"
            value["summary"] = summarize_batch_manifest(value)

        return self.store.update_manifest(
            batch_id,
            mutate,
            expected_revision=expected_revision,
            changed_item_ids=item_ids,
        )

    def _commit_publication(
        self,
        *,
        verified: ReleaseVerifyResult,
        remote_by_item: Mapping[str, RemoteBlobIdentity],
        expected_revision: int,
    ) -> ReleaseUploadResult:
        with RepositoryLock(
            self.store.lock_root,
            batch_id=verified.batch_id,
            command="release-upload",
        ):
            current = self.store.read_manifest(verified.batch_id)
            if current["revision"] != expected_revision:
                raise ManifestConflictError(
                    f"Batch {verified.batch_id} revision is {current['revision']}, "
                    f"expected {expected_revision}"
                )
            # Re-read after acquiring the lock so remote success cannot publish
            # against a stale local state.
            verified = self.verify_release(
                verified.release_manifest_path,
                require_batch_reference=True,
            )
            receipt_relative = Path(
                "publication",
                "receipts",
                f"{verified.release_id}.publication-receipt.json",
            ).as_posix()
            receipt_path = self.store.run_dir(verified.batch_id) / receipt_relative
            receipt: dict[str, Any]
            if receipt_path.exists():
                receipt = self.store.read_publication_receipt(
                    verified.batch_id,
                    relative_path=receipt_relative,
                )
            else:
                receipt = self._publication_receipt(
                    verified=verified,
                    remote_by_item=remote_by_item,
                )
                self.store.write_publication_receipt(
                    verified.batch_id,
                    receipt,
                    relative_path=receipt_relative,
                )
            receipt_sha256 = sha256_file(receipt_path)
            receipt_ref = {
                "path": receipt_relative,
                "sha256": receipt_sha256,
            }
            already_committed = (
                receipt_ref in current.get("publication_receipts", [])
                and all(
                    current["items"][item_id]["status"]["publication"]
                    == "published"
                    for item_id in verified.item_ids
                )
            )
            if already_committed:
                committed = current
                idempotent = True
            else:
                def mutate(value: dict[str, Any]) -> None:
                    existing = list(value["publication_receipts"])
                    conflicting = [
                        ref for ref in existing
                        if ref["path"] == receipt_relative and ref != receipt_ref
                    ]
                    if conflicting:
                        raise _error(
                            "publication_receipt_conflict",
                            f"Publication Receipt hash conflict for {verified.release_id}",
                        )
                    if receipt_ref not in existing:
                        value["publication_receipts"] = [*existing, receipt_ref]
                    for item_id in verified.item_ids:
                        value["items"][item_id]["status"][
                            "publication"
                        ] = "published"
                    value["summary"] = summarize_batch_manifest(value)

                committed = self.store.update_manifest(
                    verified.batch_id,
                    mutate,
                    expected_revision=expected_revision,
                    changed_item_ids=verified.item_ids,
                )
                idempotent = False
            return ReleaseUploadResult(
                batch_id=verified.batch_id,
                release_id=verified.release_id,
                release_manifest_path=verified.release_manifest_path,
                release_manifest_sha256=verified.release_manifest_sha256,
                release_seal=verified.release_seal,
                dry_run=False,
                item_ids=verified.item_ids,
                remote_blobs=tuple(
                    remote_by_item[item_id].to_dict()
                    for item_id in verified.item_ids
                ),
                publication_receipt_path=receipt_relative,
                publication_receipt_sha256=receipt_sha256,
                committed_revision=int(committed["revision"]),
                idempotent=idempotent,
            )

    def _publication_receipt(
        self,
        *,
        verified: ReleaseVerifyResult,
        remote_by_item: Mapping[str, RemoteBlobIdentity],
    ) -> dict[str, Any]:
        manifest = verified.manifest
        items = []
        for item in manifest["items"]:
            remote = remote_by_item[str(item["item_id"])]
            items.append({
                "item_id": item["item_id"],
                "resource_key": item["resource_key"],
                "language": item["language"],
                "payload": {
                    "release_path": item["payload"]["release_path"],
                    "sha256": item["payload"]["sha256"],
                },
                "target_blob": dict(item["target_blob"]),
                "remote": remote.to_dict(),
            })
        receipt = {
            "schema_version": "1.0",
            "receipt_id": "0" * 64,
            "published_at": self._now(),
            "batch_id": verified.batch_id,
            "release_id": verified.release_id,
            "release_manifest": {
                "path": verified.release_manifest_path,
                "sha256": verified.release_manifest_sha256,
            },
            "release_seal": verified.release_seal,
            "target": dict(manifest["target"]),
            "items": items,
        }
        receipt["receipt_id"] = derive_publication_receipt_id(receipt)
        self.store.validate_document(receipt, "publication_receipt")
        return receipt

    def _verify_release_evidence_artifact(
        self,
        release_dir: Path,
        artifact: Mapping[str, Any],
        *,
        label: str,
    ) -> None:
        path = self._root_path(artifact["path"])
        self._assert_under(
            path,
            release_dir / "evidence",
            code=f"{label}_path_invalid",
            message=f"{label} must stay under the Release evidence directory",
        )
        self._assert_regular_file(path, label=label)
        if sha256_file(path) != artifact["sha256"]:
            raise _error(
                f"{label}_hash_mismatch",
                f"{label} hash drifted",
            )

    def _release_reference_is_current(
        self,
        manifest: Mapping[str, Any],
        path: str,
        sha256: str,
        *,
        item_ids: tuple[str, ...],
    ) -> bool:
        ref = {"path": path, "sha256": sha256}
        return (
            ref in manifest.get("release_manifests", [])
            and all(
                manifest["items"][item_id]["status"]["release"] == "released"
                for item_id in item_ids
            )
        )

    def _release_manifest_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        absolute = candidate if candidate.is_absolute() else self.root / candidate
        try:
            resolved = absolute.resolve(strict=True)
        except OSError as error:
            raise _error(
                "release_manifest_missing",
                f"Release Manifest does not exist: {path}",
            ) from error
        self._assert_under(
            resolved,
            self.root,
            code="release_manifest_outside_repository",
            message="Release Manifest must stay inside the repository",
        )
        return resolved

    def _root_path(self, relative_path: str | Path) -> Path:
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise _error(
                "invalid_relative_path",
                f"Path must be repository-relative: {relative_path}",
            )
        return (self.root / relative).resolve()

    def _root_relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError as error:
            raise _error(
                "path_outside_repository",
                f"Path must stay inside repository: {path}",
            ) from error

    def _run_relative(self, batch_id: str, relative_path: str | Path) -> str:
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise _error(
                "invalid_run_relative_path",
                f"Run artifact path is not relative: {relative_path}",
            )
        return self._root_relative(self.store.run_dir(batch_id) / relative)

    @staticmethod
    def _assert_under(
        path: Path,
        root: Path,
        *,
        code: str,
        message: str,
    ) -> None:
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError as error:
            raise _error(code, message) from error

    def _assert_regular_file(self, path: Path, *, label: str) -> None:
        self._assert_under(
            path,
            self.root,
            code="path_outside_repository",
            message=f"{label} must stay inside repository",
        )
        current = path
        while current != self.root:
            if current.is_symlink():
                raise _error(
                    "symlink_forbidden",
                    f"{label} must not traverse a symlink: {path}",
                )
            current = current.parent
        if not path.is_file():
            raise _error(
                "artifact_missing",
                f"{label} is not a regular file: {path}",
            )

    @staticmethod
    def _normalize_item_ids(item_ids: Sequence[str]) -> tuple[str, ...]:
        if isinstance(item_ids, (str, bytes)) or not item_ids:
            raise _error(
                "missing_release_items",
                "Release build requires at least one explicit item",
            )
        normalized = tuple(str(item_id) for item_id in item_ids)
        if any(not item_id for item_id in normalized):
            raise _error("invalid_item_id", "Release item IDs must be non-empty")
        if len(set(normalized)) != len(normalized):
            raise _error(
                "duplicate_release_item_id",
                "Release item IDs must be unique",
            )
        return tuple(sorted(normalized))

    @staticmethod
    def _validate_release_id(release_id: str) -> None:
        if not isinstance(release_id, str) or not RELEASE_ID_PATTERN.fullmatch(
            release_id
        ):
            raise _error(
                "invalid_release_id",
                "release_id must match ^[A-Za-z0-9][A-Za-z0-9._-]*$",
            )

    @staticmethod
    def _profile_id(manifest: Mapping[str, Any]) -> str:
        profile = manifest.get("validation_context", {}).get("validation_profile", {})
        if isinstance(profile, Mapping):
            return str(profile.get("id", ""))
        return ""


__all__ = [
    "AzureReleaseBlobTransport",
    "ReleaseBuildResult",
    "ReleaseService",
    "ReleaseServiceError",
    "ReleaseUploadResult",
    "ReleaseVerifyResult",
    "RemoteBlobIdentity",
]
