"""Schema-validated, atomic JSON state and repository-wide advisory locking."""

from __future__ import annotations

import copy
import errno
import hashlib
import json
import os
import secrets
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, IO

from jsonschema import Draft202012Validator, FormatChecker

from src.core.canonical_identity import (
    CanonicalIdentityError,
    derive_sampling_seed,
    derive_state_id,
    derive_universe_id,
    document_identity_sha256,
    validation_evidence_sha256,
)
from src.core.product_catalog import sha256_file
from src.core.validation_context import ValidationContextError, ValidationContextRegistry
from src.content_sampling.artifacts import artifact_json_sha256, artifact_json_text
from src.pipeline.models import BatchManifest, InputManifest, utc_now
from src.release.contracts import (
    ReleaseContractError,
    validate_publication_receipt_bindings,
    validate_release_manifest_bindings,
)
from src.review.contracts import (
    LEGACY_P3_PROFILE_IDENTITY,
    ReviewContractError,
    SUCCESSOR_P3_PROFILE_IDENTITY,
    evaluate_source_findings,
    resolve_finding_policy,
    classify_source_quality_findings,
    machine_approval_preconditions,
    source_approval_preconditions,
)

try:  # pragma: no cover - exercised on the platform that provides it
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None  # type: ignore[assignment]


class StateStoreError(RuntimeError):
    """Fatal pipeline state persistence error."""


class UnknownBatchError(StateStoreError):
    """The requested batch directory or manifest does not exist."""


class ImmutableManifestError(StateStoreError):
    """An attempt was made to replace the immutable input manifest."""


class ManifestConflictError(StateStoreError):
    """The caller attempted to update a stale batch manifest revision."""


def _serialized_json_payload(value: Mapping[str, Any]) -> str:
    """Return the exact bytes-on-disk JSON representation used by the store."""

    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _serialized_json_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        _serialized_json_payload(value).encode("utf-8")
    ).hexdigest()


def _validate_coverage_counts(
    coverage: Mapping[str, Any],
    *,
    context: str,
    selected_state_ids: list[str] | None = None,
) -> None:
    """Validate coverage arithmetic that JSON Schema cannot express."""

    universe_count = coverage["universe_count"]
    selected_count = coverage["selected_count"]
    untested_count = coverage["untested_count"]
    if universe_count != selected_count + untested_count:
        raise ManifestValidationError(
            f"{context} universe_count must equal selected_count plus "
            "untested_count"
        )
    if coverage["mode"] == "full" and (
        selected_count != universe_count or untested_count != 0
    ):
        raise ManifestValidationError(
            f"{context} full coverage must select the entire universe"
        )
    if (
        selected_state_ids is not None
        and coverage["mode"] == "stratified_sample"
        and len(selected_state_ids) != selected_count
    ):
        raise ManifestValidationError(
            f"{context} selected_count must equal selected_state_ids length"
        )


def _validate_structure_counts(
    structure: Mapping[str, Any],
    *,
    coverage_universe_count: int,
    total_field: str,
    context: str,
) -> None:
    total_count = structure[total_field]
    checked_count = structure["checked_count"]
    if total_count != coverage_universe_count:
        raise ManifestValidationError(
            f"{context} total must equal content coverage universe_count"
        )
    if checked_count > total_count:
        raise ManifestValidationError(
            f"{context} checked_count cannot exceed its total"
        )
    if structure["status"] == "passed" and checked_count != total_count:
        raise ManifestValidationError(
            f"{context} passed status requires every reachable state checked"
        )
    if "errors" in structure:
        errors = structure["errors"]
        if structure["status"] == "passed" and errors:
            raise ManifestValidationError(
                f"{context} passed status cannot contain errors"
            )
        if structure["status"] == "failed" and not errors:
            raise ManifestValidationError(
                f"{context} failed status requires at least one error"
            )


def _validate_comparison_identity(
    comparison: Mapping[str, Any],
    *,
    context: str,
) -> None:
    status = comparison["status"]
    source = comparison["source_fingerprint"]
    payload = comparison["payload_fingerprint"]
    if status == "matched" and source != payload:
        raise ManifestValidationError(
            f"{context} matched status requires identical fingerprints"
        )
    if status == "mismatched" and source == payload:
        raise ManifestValidationError(
            f"{context} mismatched status requires different fingerprints"
        )


class ManifestValidationError(StateStoreError):
    """A state document failed its versioned JSON Schema."""


class RepositoryLockError(StateStoreError):
    """Another mutable pipeline command owns the repository lock."""


def generate_batch_id(
    now: datetime | None = None,
    random_hex: str | None = None,
) -> str:
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    suffix = random_hex or secrets.token_hex(4)
    if len(suffix) != 8 or any(character not in "0123456789abcdef" for character in suffix):
        raise ValueError("batch id suffix must be exactly eight lowercase hexadecimal characters")
    return f"{moment.strftime('%Y%m%dT%H%M%SZ')}-{suffix}"


class RepositoryLock:
    """An OS advisory lock shared by every mutating run in this repository."""

    def __init__(
        self,
        root: str | Path = ".",
        *,
        timeout: float = 0.0,
        poll_interval: float = 0.1,
        batch_id: str | None = None,
        command: str | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.path = self.root / "runs" / ".pipeline.lock"
        # The short-lived guard serializes main-lock handoff with owner metadata
        # publication. It is never held for the duration of a pipeline command.
        self.guard_path = self.root / "runs" / ".pipeline.lock.guard"
        self.timeout = max(0.0, timeout)
        self.poll_interval = max(0.01, poll_interval)
        self.batch_id = batch_id
        self.command = command
        self._stream: IO[str] | None = None

    @property
    def acquired(self) -> bool:
        return self._stream is not None

    def acquire(self) -> "RepositoryLock":
        if self._stream is not None:
            return self
        if fcntl is None:
            raise RepositoryLockError("OS advisory locking is unavailable on this platform")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+", encoding="utf-8")
        try:
            guard_stream = self.guard_path.open("a+", encoding="utf-8")
        except Exception:
            stream.close()
            raise
        deadline = time.monotonic() + self.timeout
        try:
            while True:
                wait_for: float | None = None
                fcntl.flock(guard_stream.fileno(), fcntl.LOCK_EX)
                try:
                    try:
                        fcntl.flock(
                            stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                        )
                    except OSError as error:
                        if error.errno not in (errno.EACCES, errno.EAGAIN):
                            stream.close()
                            raise RepositoryLockError(
                                f"Unable to acquire repository lock: {error}"
                            ) from error
                        if time.monotonic() >= deadline:
                            stream.close()
                            raise RepositoryLockError(
                                f"Repository pipeline lock is held: {self.path}"
                            ) from error
                        wait_for = min(
                            self.poll_interval,
                            max(0.0, deadline - time.monotonic()),
                        )
                    else:
                        try:
                            self._write_metadata(stream)
                        except Exception:
                            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                            stream.close()
                            raise
                        self._stream = stream
                        return self
                finally:
                    fcntl.flock(guard_stream.fileno(), fcntl.LOCK_UN)
                if wait_for is not None:
                    time.sleep(wait_for)
        finally:
            guard_stream.close()
            if self._stream is None and not stream.closed:
                stream.close()

    def _write_metadata(self, stream: IO[str]) -> None:
        metadata = {
            "schema_version": "1.0",
            "pid": os.getpid(),
            "acquired_at": utc_now(),
            "batch_id": self.batch_id,
            "command": self.command,
        }
        stream.seek(0)
        stream.truncate()
        stream.write(json.dumps(metadata, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())

    def release(self) -> None:
        stream, self._stream = self._stream, None
        if stream is None:
            return
        if fcntl is not None:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()

    def __enter__(self) -> "RepositoryLock":
        return self.acquire()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.release()

    @classmethod
    def is_locked(
        cls,
        root: str | Path = ".",
        *,
        batch_id: str | None = None,
    ) -> bool:
        """Return whether the repository, or a specific batch, owns a live lock.

        ``flock`` remains authoritative. Lock-file metadata is consulted only
        after a live owner is observed and is never sufficient on its own.
        Legacy or damaged metadata therefore remains a repository-wide lock,
        but cannot be treated as an effective lock for a particular batch.
        """
        if fcntl is None:
            return False
        path = Path(root).resolve() / "runs" / ".pipeline.lock"
        if not path.is_file():
            return False
        try:
            stream = path.open("r", encoding="utf-8")
        except OSError:
            return False
        try:
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                if error.errno in (errno.EACCES, errno.EAGAIN):
                    if batch_id is None:
                        return True
                    guard_path = path.with_name(f"{path.name}.guard")
                    if not guard_path.is_file():
                        return False
                    try:
                        guard_stream = guard_path.open("r", encoding="utf-8")
                    except OSError:
                        return False
                    try:
                        fcntl.flock(guard_stream.fileno(), fcntl.LOCK_SH)
                        try:
                            fcntl.flock(
                                stream.fileno(),
                                fcntl.LOCK_EX | fcntl.LOCK_NB,
                            )
                        except OSError as retry_error:
                            if retry_error.errno not in (
                                errno.EACCES,
                                errno.EAGAIN,
                            ):
                                raise RepositoryLockError(
                                    f"Unable to re-probe repository lock: "
                                    f"{retry_error}"
                                ) from retry_error
                            try:
                                stream.seek(0)
                                metadata = json.load(stream)
                            except (OSError, ValueError):
                                return False
                            return (
                                isinstance(metadata, dict)
                                and metadata.get("schema_version") == "1.0"
                                and metadata.get("batch_id") == batch_id
                            )
                        else:
                            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                            return False
                        finally:
                            fcntl.flock(
                                guard_stream.fileno(), fcntl.LOCK_UN
                            )
                    finally:
                        guard_stream.close()
                raise RepositoryLockError(f"Unable to probe repository lock: {error}") from error
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            return False
        finally:
            stream.close()

    @classmethod
    def is_owned_by_current_process(
        cls,
        root: str | Path = ".",
        *,
        batch_id: str,
    ) -> bool:
        """Return whether this process owns the live lock for ``batch_id``."""

        repository_root = Path(root).resolve()
        if not cls.is_locked(repository_root, batch_id=batch_id):
            return False
        path = repository_root / "runs" / ".pipeline.lock"
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return (
            isinstance(metadata, dict)
            and metadata.get("schema_version") == "1.0"
            and metadata.get("pid") == os.getpid()
            and metadata.get("batch_id") == batch_id
        )


class StateStore:
    """Persist immutable inputs, mutable truth, and rebuildable projections."""

    SCHEMAS = {
        "input": {
            "1.0": "pipeline-input-manifest-1.0.schema.json",
            "2.0": "pipeline-input-manifest-2.0.schema.json",
        },
        "batch": {
            "1.0": "pipeline-batch-manifest-1.0.schema.json",
            "2.0": "pipeline-batch-manifest-2.0.schema.json",
        },
        "validation": {
            "1.0": "pipeline-validation-1.0.schema.json",
            "2.0": "pipeline-validation-2.0.schema.json",
            "2.1": "pipeline-validation-2.1.schema.json",
        },
        "review": {
            "1.0": "pipeline-review-queue-1.0.schema.json",
            "2.0": "pipeline-review-queue-2.0.schema.json",
        },
        "report": {"1.0": "pipeline-batch-report-1.0.schema.json"},
        "content_sampling_profile": {
            "1.0": "content-sampling-profile-1.0.schema.json"
        },
        "sampling_plan": {
            "1.0": "batch-item-sampling-plan-1.0.schema.json"
        },
        "sampled_content_evidence": {
            "1.0": "sampled-content-evidence-1.0.schema.json"
        },
        "review_decision": {"1.0": "review-decision-1.0.schema.json"},
        "release_manifest": {
            "1.0": "release-manifest-1.0.schema.json",
            "1.1": "release-manifest-1.1.schema.json",
        },
        "publication_receipt": {"1.0": "publication-receipt-1.0.schema.json"},
    }

    def __init__(self, root: str | Path = ".", runs_dir: str | Path = "runs") -> None:
        self.root = Path(root).resolve()
        candidate = Path(runs_dir)
        self.runs_dir = candidate.resolve() if candidate.is_absolute() else (self.root / candidate).resolve()
        self.lock_root = self.runs_dir.parent
        self.schema_dir = self.root / "schemas"
        self._validators: dict[
            tuple[str, str, str], Draft202012Validator
        ] = {}
        self._batch_item_validators: dict[
            tuple[str, str], Draft202012Validator
        ] = {}
        self._document_cache: dict[
            tuple[Path, str], tuple[str, str, dict[str, Any]]
        ] = {}
        self._validation_context = ValidationContextRegistry(self.root)

    def run_dir(self, batch_id: str) -> Path:
        self._validate_batch_id(batch_id)
        return self.runs_dir / batch_id

    def create_run(
        self,
        input_manifest: InputManifest | Mapping[str, Any],
        batch_manifest: BatchManifest | Mapping[str, Any] | None = None,
    ) -> Path:
        frozen = input_manifest.to_dict() if isinstance(input_manifest, InputManifest) else copy.deepcopy(dict(input_manifest))
        if frozen.get("schema_version") != "2.0":
            raise ImmutableManifestError("New pipeline runs require Input Manifest 2.0")
        if "frozen_inputs" not in frozen:
            raise ImmutableManifestError(
                "New pipeline runs require frozen_inputs.soft_category; "
                "legacy Manifest 2.0 documents remain read-only compatible"
            )
        self._validate(frozen, "input")
        validation_context = frozen.get("validation_context")
        active_validation_context = self._validation_context.freeze()[
            "validation_context"
        ]
        if validation_context != active_validation_context:
            try:
                legacy_p3_validation_context = self._validation_context.freeze(
                    validation_profile_id="v0.4-validation-p3"
                )["validation_context"]
            except TypeError:
                legacy_p3_validation_context = None
            if validation_context != legacy_p3_validation_context:
                raise ImmutableManifestError(
                    "New pipeline runs must use the active Validation Context "
                    "or the explicit legacy P3 replay context"
                )
        batch_id = frozen["batch_id"]
        directory = self.run_dir(batch_id)
        if directory.exists():
            raise StateStoreError(f"Batch already exists: {batch_id}")

        input_reference = {
            "path": "input-manifest.json",
            "sha256": _serialized_json_sha256(frozen),
        }
        expected_new = BatchManifest.from_input_manifest(frozen).to_dict()
        expected_new["input_manifest"] = copy.deepcopy(input_reference)
        mutable = (
            copy.deepcopy(expected_new)
            if batch_manifest is None
            else batch_manifest.to_dict() if isinstance(batch_manifest, BatchManifest)
            else copy.deepcopy(dict(batch_manifest))
        )
        # The Input file reference is store-derived, not caller-controlled.
        mutable["input_manifest"] = copy.deepcopy(input_reference)
        if mutable.get("schema_version") != "2.0":
            raise ImmutableManifestError("New pipeline runs require Batch Manifest 2.0")
        if mutable != expected_new:
            raise ImmutableManifestError(
                "New Batch Manifest must exactly equal the canonical "
                "Input-derived initialization"
            )
        # Validate both documents and their derived file binding before any
        # directory is created.  A rejected custom Batch cannot strand a
        # half-created run that prevents a corrected retry.
        self._validate(mutable, "batch")

        for relative in ("outputs", "diagnostics", "validation", "review", "logs"):
            (directory / relative).mkdir(parents=True, exist_ok=False)

        self.write_input_manifest(batch_id, frozen)
        if sha256_file(directory / "input-manifest.json") != input_reference["sha256"]:
            raise StateStoreError(
                "Input Manifest file identity differs from its prevalidated binding"
            )
        self._write_new(directory / "batch-manifest.json", mutable, "batch")
        return directory

    def write_input_manifest(self, batch_id: str, value: InputManifest | Mapping[str, Any]) -> Path:
        path = self.run_dir(batch_id) / "input-manifest.json"
        document = value.to_dict() if isinstance(value, InputManifest) else copy.deepcopy(dict(value))
        if document.get("batch_id") != batch_id:
            raise ImmutableManifestError("Input manifest batch_id does not match its directory")
        if path.exists():
            raise ImmutableManifestError(f"Input manifest is write-once and already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_new(path, document, "input")
        return path

    def read_input_manifest(self, batch_id: str) -> dict[str, Any]:
        value = self._read(
            self.run_dir(batch_id) / "input-manifest.json",
            "input",
            verify_context=False,
        )
        if value.get("batch_id") != batch_id:
            raise ImmutableManifestError(
                f"Input Manifest batch_id does not match its directory: {batch_id}"
            )
        self._verify_frozen_context(value, "input")
        return value

    def read_manifest(self, batch_id: str) -> dict[str, Any]:
        value = self._read(
            self.run_dir(batch_id) / "batch-manifest.json",
            "batch",
            verify_context=False,
        )
        if value.get("batch_id") != batch_id:
            raise ImmutableManifestError(
                f"Batch Manifest batch_id does not match its directory: {batch_id}"
            )
        frozen_path = self.run_dir(batch_id) / value["input_manifest"]["path"]
        if (
            frozen_path.is_symlink()
            or not frozen_path.is_file()
            or sha256_file(frozen_path) != value["input_manifest"]["sha256"]
        ):
            raise ImmutableManifestError(f"Input manifest hash mismatch for batch {batch_id}")
        frozen = self._read(frozen_path, "input", verify_context=False)
        if frozen.get("batch_id") != batch_id:
            raise ImmutableManifestError(
                f"Input Manifest batch_id does not match its directory: {batch_id}"
            )
        if frozen.get("schema_version") != value.get("schema_version"):
            raise ImmutableManifestError(
                f"Input/Batch Manifest schema versions differ for {batch_id}"
            )
        if value.get("schema_version") == "2.0" and (
            value.get("planning") != frozen.get("planning")
            or value.get("validation_context") != frozen.get("validation_context")
            or value.get("frozen_inputs") != frozen.get("frozen_inputs")
        ):
            raise ImmutableManifestError(
                f"Batch Manifest frozen context differs from Input Manifest for {batch_id}"
            )
        self._verify_frozen_context(value, "batch")
        return value

    def update_manifest(
        self,
        batch_id: str,
        update: Callable[[dict[str, Any]], Mapping[str, Any] | None] | Mapping[str, Any],
        *,
        expected_revision: int | None = None,
        changed_item_ids: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        if expected_revision is None:
            raise ManifestConflictError(
                "Mutable manifest updates require expected_revision"
            )
        if not RepositoryLock.is_owned_by_current_process(
            self.lock_root,
            batch_id=batch_id,
        ):
            raise RepositoryLockError(
                f"Mutable manifest updates require the RepositoryLock for {batch_id}"
            )
        path = self.run_dir(batch_id) / "batch-manifest.json"
        # The on-disk Batch/Input pair is authoritative.  Always replay it
        # before a mutation so a warm cache cannot conceal manifest tampering
        # and then overwrite that evidence with a fresh revision.
        current = copy.deepcopy(self.read_manifest(batch_id))
        if current.get("schema_version") != "2.0":
            raise ImmutableManifestError(
                "Pipeline Manifest 1.x is read-only; new mutation requires a 2.0 run"
            )
        if current["revision"] != expected_revision:
            raise ManifestConflictError(
                f"Batch {batch_id} revision is {current['revision']}, expected {expected_revision}"
            )
        if callable(update):
            candidate = copy.deepcopy(current)
            returned = update(candidate)
            if returned is not None:
                candidate = copy.deepcopy(dict(returned))
        else:
            candidate = copy.deepcopy(dict(update))

        for immutable_key in (
            "schema_version",
            "batch_id",
            "created_at",
            "input_manifest",
            "planning",
            "validation_context",
            "frozen_inputs",
        ):
            if candidate.get(immutable_key) != current.get(immutable_key):
                raise ImmutableManifestError(f"Mutable manifest cannot change {immutable_key}")
        if set(candidate.get("items", {})) != set(current.get("items", {})):
            raise ImmutableManifestError("Mutable manifest cannot add or remove Batch Items")
        optional_item_fields = {
            "status": {
                "evidence_binding",
                "approval_eligibility",
                "release",
            },
            "artifacts": {
                "sampling_plan",
                "sampled_content_evidence",
                "current_review_decision",
            },
        }
        for item_id, previous_item in current.get("items", {}).items():
            proposed_item = candidate["items"][item_id]
            for container, optional_fields in optional_item_fields.items():
                previous_presence = optional_fields.intersection(
                    previous_item[container]
                )
                proposed_presence = optional_fields.intersection(
                    proposed_item[container]
                )
                if proposed_presence != previous_presence:
                    raise ImmutableManifestError(
                        "Mutable manifest cannot add or remove optional Step 4 "
                        f"{container} fields for {item_id}"
                    )
        for append_only_key in ("release_manifests", "publication_receipts"):
            if (append_only_key in candidate) != (append_only_key in current):
                raise ImmutableManifestError(
                    "Mutable manifest cannot add or remove optional Step 4 "
                    f"field {append_only_key}"
                )
            if append_only_key not in current:
                continue
            previous = list(current.get(append_only_key, []))
            proposed = list(candidate.get(append_only_key, []))
            if proposed[: len(previous)] != previous:
                raise ImmutableManifestError(
                    f"Mutable manifest cannot rewrite append-only {append_only_key}"
                )
        candidate["revision"] = current["revision"] + 1
        candidate["updated_at"] = utc_now()
        if changed_item_ids is None:
            # read_manifest() already replayed the immutable frozen context for
            # this mutation; the equality checks above prevent the candidate
            # from substituting it.
            self._validate(candidate, "batch", verify_context=False)
        else:
            self._validate_batch_incremental(candidate, current, changed_item_ids)
        self._atomic_write(path, candidate)
        self._cache_validated_document(path, candidate, "batch")
        return copy.deepcopy(candidate)

    def _validate_batch_incremental(
        self,
        candidate: Mapping[str, Any],
        current: Mapping[str, Any],
        declared_item_ids: Iterable[str],
    ) -> None:
        """Apply the Batch Manifest schema to the root and changed items only.

        The repository lock gives a mutator exclusive ownership. Comparing the
        candidate with the on-disk, fully validated revision ensures callers
        cannot hide an item mutation by omitting its identity.
        """
        declared = set(declared_item_ids)
        unknown = declared - set(candidate["items"])
        if unknown:
            raise ManifestValidationError(
                f"Incremental validation names unknown Batch Items: {sorted(unknown)}"
            )
        actual = {
            item_id
            for item_id, item in candidate["items"].items()
            if item != current["items"][item_id]
        }
        undeclared = actual - declared
        if undeclared:
            raise ManifestValidationError(
                f"Incremental update changed undeclared Batch Items: {sorted(undeclared)}"
            )

        root = copy.deepcopy(dict(candidate))
        root["items"] = {}
        version = str(candidate.get("schema_version", ""))
        self._raise_validation_errors(
            self._validator("batch", version).iter_errors(root), "batch"
        )

        validator = self._batch_item_schema_validator(version)
        for item_id in sorted(actual):
            item = candidate["items"][item_id]
            self._raise_validation_errors(
                validator.iter_errors(item), f"batch item {item_id}"
            )
            expected = f"{item['identity']['language']}/{item['identity']['resource_key']}"
            if item_id != item["item_id"] or item_id != expected:
                raise ManifestValidationError(
                    f"Batch item key does not match identity: {item_id}"
                )

    def write_projection(
        self,
        batch_id: str,
        kind: str,
        value: Mapping[str, Any],
        *,
        relative_path: str | Path | None = None,
    ) -> Path:
        if kind not in ("validation", "review", "report"):
            raise StateStoreError(f"Unknown projection kind: {kind}")
        if not RepositoryLock.is_owned_by_current_process(
            self.lock_root,
            batch_id=batch_id,
        ):
            raise RepositoryLockError(
                f"Projection writes require the RepositoryLock for {batch_id}"
            )
        if kind == "validation":
            manifest = self.read_manifest(batch_id)
            profile = dict(manifest["validation_context"]["validation_profile"])
            if profile == SUCCESSOR_P3_PROFILE_IDENTITY:
                expected_version = "2.1"
            elif profile == LEGACY_P3_PROFILE_IDENTITY:
                expected_version = "2.0"
            else:
                expected_version = "1.0"
            if value.get("schema_version") != expected_version:
                raise StateStoreError(
                    "Validation projection schema_version does not match the "
                    f"Batch Validation Profile {profile.get('id', '<missing>')}"
                )
        if kind == "review":
            manifest = self.read_manifest(batch_id)
            profile_id = manifest["validation_context"]["validation_profile"][
                "id"
            ]
            expected_version = (
                "2.0"
                if profile_id in (
                    "v0.4-validation-p3",
                    "v0.4-validation-p3-successor",
                )
                else "1.0"
            )
            if value.get("schema_version") != expected_version:
                raise StateStoreError(
                    "Review Queue schema_version does not match the "
                    f"Batch Validation Profile {profile_id}"
                )
        defaults = {
            "review": Path("review/review-queue.json"),
            "report": Path("batch-report.json"),
        }
        if relative_path is None:
            if kind == "validation":
                raise StateStoreError("validation projections require an item-relative path")
            relative = defaults[kind]
        else:
            relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise StateStoreError(f"Projection path must remain inside the run directory: {relative}")
        path = self.run_dir(batch_id) / relative
        if not self.run_dir(batch_id).is_dir():
            raise UnknownBatchError(f"Unknown batch: {batch_id}")
        if value.get("batch_id") != batch_id:
            raise ManifestValidationError("Projection batch_id does not match its run directory")
        self._validate(value, kind)
        if kind == "validation" and value.get("schema_version") in ("2.0", "2.1"):
            self._write_json_once(path, value, kind)
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(path, value)
        return path

    def write_step4_artifact(
        self,
        batch_id: str,
        kind: str,
        value: Mapping[str, Any],
        *,
        relative_path: str | Path,
    ) -> Path:
        if kind not in ("sampling_plan", "sampled_content_evidence"):
            raise StateStoreError(f"Unknown Step 4 artifact kind: {kind}")
        if not RepositoryLock.is_owned_by_current_process(
            self.lock_root,
            batch_id=batch_id,
        ):
            raise RepositoryLockError(
                f"Step 4 artifact writes require the RepositoryLock for {batch_id}"
            )
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise StateStoreError(
                f"Step 4 artifact path must remain inside the run directory: {relative}"
            )
        self._validate(value, kind)
        path = self.run_dir(batch_id) / relative
        self._write_json_once(path, value, kind)
        return path

    def read_step4_artifact(
        self,
        batch_id: str,
        kind: str,
        *,
        relative_path: str | Path,
    ) -> dict[str, Any]:
        if kind not in ("sampling_plan", "sampled_content_evidence"):
            raise StateStoreError(f"Unknown Step 4 artifact kind: {kind}")
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise StateStoreError(
                f"Step 4 artifact path must remain inside the run directory: {relative}"
            )
        return self._read(self.run_dir(batch_id) / relative, kind)

    def write_review_decision(
        self,
        batch_id: str,
        value: Mapping[str, Any],
        *,
        relative_path: str | Path,
    ) -> Path:
        if not RepositoryLock.is_owned_by_current_process(
            self.lock_root,
            batch_id=batch_id,
        ):
            raise RepositoryLockError(
                f"Review Decision writes require the RepositoryLock for {batch_id}"
            )
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise StateStoreError(
                "Review Decision path must remain inside the run directory: "
                f"{relative}"
            )
        expected = Path(
            "review",
            "decisions",
            str(value["language"]),
            str(value["resource_key"]),
            f"{value['decision_id']}.json",
        )
        if relative != expected:
            raise StateStoreError(
                "Review Decision path must be canonical: "
                f"{expected.as_posix()}"
            )
        self._validate(value, "review_decision")
        path = self.run_dir(batch_id) / relative
        self._write_json_once(path, value, "review_decision")
        return path

    def read_review_decision(
        self,
        batch_id: str,
        *,
        relative_path: str | Path,
    ) -> dict[str, Any]:
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise StateStoreError(
                "Review Decision path must remain inside the run directory: "
                f"{relative}"
            )
        if relative.parts[:2] != ("review", "decisions"):
            raise StateStoreError(
                f"Review Decision path is outside review/decisions: {relative}"
            )
        return self._read(self.run_dir(batch_id) / relative, "review_decision")

    def write_publication_receipt(
        self,
        batch_id: str,
        value: Mapping[str, Any],
        *,
        relative_path: str | Path,
    ) -> Path:
        if not RepositoryLock.is_owned_by_current_process(
            self.lock_root,
            batch_id=batch_id,
        ):
            raise RepositoryLockError(
                f"Publication Receipt writes require the RepositoryLock for {batch_id}"
            )
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise StateStoreError(
                "Publication Receipt path must remain inside the run directory: "
                f"{relative}"
            )
        expected = Path(
            "publication",
            "receipts",
            f"{value['release_id']}.publication-receipt.json",
        )
        if relative != expected:
            raise StateStoreError(
                "Publication Receipt path must be canonical: "
                f"{expected.as_posix()}"
            )
        if value.get("batch_id") != batch_id:
            raise ManifestValidationError(
                "Publication Receipt batch_id does not match its run directory"
            )
        self._validate(value, "publication_receipt")
        path = self.run_dir(batch_id) / relative
        self._write_json_once(path, value, "publication_receipt")
        return path

    def read_publication_receipt(
        self,
        batch_id: str,
        *,
        relative_path: str | Path,
    ) -> dict[str, Any]:
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise StateStoreError(
                "Publication Receipt path must remain inside the run directory: "
                f"{relative}"
            )
        if relative.parts[:2] != ("publication", "receipts"):
            raise StateStoreError(
                f"Publication Receipt path is outside publication/receipts: {relative}"
            )
        return self._read(
            self.run_dir(batch_id) / relative,
            "publication_receipt",
        )

    def write_json_artifact_once(
        self,
        batch_id: str,
        value: Mapping[str, Any],
        *,
        relative_path: str | Path,
    ) -> Path:
        if not RepositoryLock.is_owned_by_current_process(
            self.lock_root,
            batch_id=batch_id,
        ):
            raise RepositoryLockError(
                f"Artifact writes require the RepositoryLock for {batch_id}"
            )
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise StateStoreError(
                f"Artifact path must remain inside the run directory: {relative}"
            )
        path = self.run_dir(batch_id) / relative
        self._write_json_once(path, value, "artifact")
        return path

    def read_projection(
        self,
        batch_id: str,
        kind: str,
        *,
        relative_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Read and validate a persisted projection without rewriting it."""

        if kind not in ("validation", "review", "report"):
            raise StateStoreError(f"Unknown projection kind: {kind}")
        defaults = {
            "review": Path("review/review-queue.json"),
            "report": Path("batch-report.json"),
        }
        if relative_path is None:
            if kind == "validation":
                raise StateStoreError(
                    "validation projections require an item-relative path"
                )
            relative = defaults[kind]
        else:
            relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise StateStoreError(
                "Projection path must remain inside the run directory: "
                f"{relative}"
            )
        value = self._read(self.run_dir(batch_id) / relative, kind)
        if value.get("batch_id") != batch_id:
            raise ManifestValidationError(
                "Projection batch_id does not match its run directory"
            )
        return value

    def validate_document(self, value: Mapping[str, Any], kind: str) -> None:
        self._validate(value, kind)

    def _read(
        self,
        path: Path,
        kind: str,
        *,
        verify_context: bool = True,
    ) -> dict[str, Any]:
        if not path.is_file():
            raise UnknownBatchError(f"Pipeline state does not exist: {path}")
        document_sha256 = sha256_file(path)
        cache_key = (path.resolve(), kind)
        cached = self._document_cache.get(cache_key)
        if cached is not None and cached[0] == document_sha256:
            cached_value = cached[2]
            version = str(cached_value.get("schema_version", ""))
            schema_sha256 = sha256_file(self._schema_path(kind, version))
            if cached[1] == schema_sha256:
                value = copy.deepcopy(cached_value)
                self._verify_step4_profile_bindings(value, kind)
                if verify_context:
                    self._verify_frozen_context(value, kind)
                return value
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise StateStoreError(f"Unable to read pipeline state {path}: {error}") from error
        if sha256_file(path) != document_sha256:
            raise StateStoreError(
                f"Pipeline state changed while it was being read: {path}"
            )
        if not isinstance(value, dict):
            raise ManifestValidationError(
                f"Invalid {kind} document: root must be a JSON object"
            )
        self._validate(value, kind, verify_context=verify_context)
        self._cache_validated_document(
            path, value, kind, document_sha256=document_sha256
        )
        return value

    def _write_new(self, path: Path, value: Mapping[str, Any], kind: str) -> None:
        if path.exists():
            raise StateStoreError(f"Pipeline state already exists: {path}")
        if kind in ("input", "batch") and value.get("schema_version") != "2.0":
            raise ImmutableManifestError(
                f"New {kind} documents must use schema_version 2.0"
            )
        self._validate(value, kind)
        self._atomic_write(path, value)
        self._cache_validated_document(path, value, kind)

    def _validate(
        self,
        value: Mapping[str, Any],
        kind: str,
        *,
        verify_context: bool = True,
    ) -> None:
        version = str(value.get("schema_version", ""))
        validator = self._validator(kind, version)
        self._raise_validation_errors(validator.iter_errors(value), kind)
        self._validate_semantics(value, kind)
        self._verify_step4_profile_bindings(value, kind)
        if verify_context:
            self._verify_frozen_context(value, kind)

    def _verify_step4_profile_bindings(
        self,
        value: Mapping[str, Any],
        kind: str,
    ) -> None:
        identities: list[tuple[str, Mapping[str, Any]]] = []
        if kind == "sampling_plan":
            identities.append((
                "content_sampling_profile",
                value["content_sampling_profile"],
            ))
        elif kind == "sampled_content_evidence":
            bindings = value["bindings"]
            identities.extend((
                ("validation_profile", bindings["validation_profile"]),
                (
                    "content_sampling_profile",
                    bindings["content_sampling_profile"],
                ),
            ))
        elif kind == "validation" and value.get("schema_version") in ("2.0", "2.1"):
            bindings = value["evidence"]["bindings"]
            identities.extend((
                ("validation_profile", bindings["validation_profile"]),
                (
                    "content_sampling_profile",
                    bindings["content_sampling_profile"],
                ),
            ))
            if value.get("schema_version") == "2.1":
                identities.append((
                    "finding_code_policy",
                    bindings["finding_code_policy_identity"],
                ))
        elif kind == "release_manifest":
            identities.extend((
                ("validation_profile", value["validation_profile"]),
                (
                    "content_sampling_profile",
                    value["content_sampling_profile"],
                ),
            ))
            if value.get("schema_version") == "1.1":
                identities.append((
                    "finding_code_policy",
                    value["finding_code_policy_identity"],
                ))
        for key, identity in identities:
            try:
                self._validation_context.document_for_identity(key, identity)
            except ValidationContextError as error:
                raise ManifestValidationError(str(error)) from error
        if kind == "validation" and value.get("schema_version") == "2.1":
            bindings = value["evidence"]["bindings"]
            profile_identity = bindings["validation_profile"]
            expected_policy = self._validation_context.finding_code_policy_identity_for(
                profile_identity
            )
            if expected_policy != bindings["finding_code_policy_identity"]:
                raise ManifestValidationError(
                    "Validation 2.1 Finding Code Policy identity does not match "
                    "the frozen successor profile"
                )

    def _verify_frozen_context(
        self, value: Mapping[str, Any], kind: str
    ) -> None:
        if (
            kind not in ("input", "batch")
            or value.get("schema_version") != "2.0"
        ):
            return
        try:
            self._validation_context.verify_frozen(
                value["planning"], value["validation_context"]
            )
        except ValidationContextError as error:
            raise ManifestValidationError(str(error)) from error
        self._verify_frozen_inputs(value)

    def _verify_frozen_inputs(self, value: Mapping[str, Any]) -> None:
        """Replay optional repository inputs without upgrading legacy 2.0 state."""

        frozen_inputs = value.get("frozen_inputs")
        if frozen_inputs is None:
            return
        soft_category = frozen_inputs["soft_category"]
        relative = Path(soft_category["path"])
        candidate = self.root / relative
        try:
            candidate.resolve().relative_to(self.root)
        except (OSError, ValueError) as error:
            raise ManifestValidationError(
                "Frozen soft-category path escapes the repository"
            ) from error

        current = candidate
        while current != self.root:
            if current.is_symlink():
                raise ManifestValidationError(
                    "Frozen soft-category input must not traverse a symlink"
                )
            current = current.parent
        if not candidate.is_file():
            raise ManifestValidationError(
                f"Frozen soft-category input is not a regular file: {relative.as_posix()}"
            )
        if sha256_file(candidate) != soft_category["sha256"]:
            raise ManifestValidationError(
                "Frozen soft-category input SHA-256 drifted"
            )

    def _cache_validated_document(
        self,
        path: Path,
        value: Mapping[str, Any],
        kind: str,
        *,
        document_sha256: str | None = None,
    ) -> None:
        version = str(value.get("schema_version", ""))
        schema_sha256 = sha256_file(self._schema_path(kind, version))
        self._document_cache[(path.resolve(), kind)] = (
            document_sha256 or sha256_file(path),
            schema_sha256,
            copy.deepcopy(dict(value)),
        )

    @staticmethod
    def _raise_validation_errors(errors: Iterable[Any], label: str) -> None:
        errors = sorted(errors, key=lambda error: list(error.absolute_path))
        if errors:
            rendered = []
            for error in errors:
                location = "/".join(str(part) for part in error.absolute_path) or "$"
                rendered.append(f"{location}: {error.message}")
            raise ManifestValidationError(
                f"Invalid {label} document:\n- " + "\n- ".join(rendered)
            )

    def _batch_item_schema_validator(self, version: str) -> Draft202012Validator:
        schema_sha256 = sha256_file(self._schema_path("batch", version))
        cache_key = (version, schema_sha256)
        if cache_key not in self._batch_item_validators:
            batch_schema = self._validator("batch", version).schema
            item_schema = {
                "$schema": batch_schema.get("$schema"),
                "$defs": batch_schema["$defs"],
                "$ref": "#/$defs/item",
            }
            self._batch_item_validators[cache_key] = Draft202012Validator(
                item_schema, format_checker=FormatChecker()
            )
        return self._batch_item_validators[cache_key]

    def _validate_semantics(self, value: Mapping[str, Any], kind: str) -> None:
        if kind == "input":
            items = value["items"]
            item_ids = [item["item_id"] for item in items]
            if len(item_ids) != len(set(item_ids)):
                raise ManifestValidationError("Input manifest contains duplicate item identities")
            for item in items:
                expected = f"{item['identity']['language']}/{item['identity']['resource_key']}"
                if item["item_id"] != expected:
                    raise ManifestValidationError(f"Input item_id does not match identity: {item['item_id']}")
            runnable = sum(item["skip_reason"] is None for item in items)
            skipped = len(items) - runnable
            summary = value["summary"]
            expected_summary = {
                "total": len(items),
                "runnable": runnable,
                "skipped": skipped,
                "known_unsupported": sum(
                    bool(item["skip_reason"] and item["skip_reason"]["code"] == "KNOWN_UNSUPPORTED")
                    for item in items
                ),
                "source_unavailable": sum(
                    bool(item["skip_reason"] and item["skip_reason"]["code"] == "SOURCE_UNAVAILABLE")
                    for item in items
                ),
            }
            if summary != expected_summary:
                raise ManifestValidationError(f"Input summary does not match items: expected {expected_summary}")
            provenance = value["provenance"]
            if provenance["reproducible"] == provenance["dirty"]:
                raise ManifestValidationError("provenance reproducible must be the inverse of dirty")
        elif kind == "batch":
            for key, item in value["items"].items():
                expected = f"{item['identity']['language']}/{item['identity']['resource_key']}"
                if key != item["item_id"] or key != expected:
                    raise ManifestValidationError(f"Batch item key does not match identity: {key}")
        elif kind == "sampling_plan":
            expected = document_identity_sha256(value, "plan_sha256")
            if value["plan_sha256"] != expected:
                raise ManifestValidationError(
                    "Batch Item Sampling Plan identity does not match its canonical body"
                )
            try:
                universe_states = value["state_universe"]["states"]
                universe_state_ids: list[str] = []
                universe_by_id: dict[str, Mapping[str, Any]] = {}
                for index, state in enumerate(universe_states):
                    state_id = derive_state_id(state["criteria"])
                    if state["state_id"] != state_id:
                        raise ManifestValidationError(
                            "Batch Item Sampling Plan state_id does not match "
                            f"state_universe.states[{index}].criteria"
                        )
                    if state_id in universe_by_id:
                        raise ManifestValidationError(
                            "Batch Item Sampling Plan state universe contains "
                            "duplicate state identities"
                        )
                    universe_state_ids.append(state_id)
                    universe_by_id[state_id] = state

                expected_universe_id = derive_universe_id(
                    universe_state_ids,
                    value["state_universe"]["default_state_id"],
                )
                if value["state_universe"]["universe_id"] != expected_universe_id:
                    raise ManifestValidationError(
                        "Batch Item Sampling Plan universe_id does not match "
                        "the Source-ordered state universe"
                    )

                selected_state_ids: list[str] = []
                for index, state in enumerate(value["selected_states"]):
                    state_id = derive_state_id(state["criteria"])
                    if state["state_id"] != state_id:
                        raise ManifestValidationError(
                            "Batch Item Sampling Plan selected state_id does not "
                            f"match selected_states[{index}].criteria"
                        )
                    if state_id not in universe_by_id or state != universe_by_id[state_id]:
                        raise ManifestValidationError(
                            "Batch Item Sampling Plan selected_states must be exact "
                            "members of the state universe"
                        )
                    selected_state_ids.append(state_id)
                if len(set(selected_state_ids)) != len(selected_state_ids):
                    raise ManifestValidationError(
                        "Batch Item Sampling Plan selected_states contain duplicates"
                    )
                selected_indexes = [
                    universe_state_ids.index(state_id)
                    for state_id in selected_state_ids
                ]
                if selected_indexes != sorted(selected_indexes):
                    raise ManifestValidationError(
                        "Batch Item Sampling Plan selected_states must preserve "
                        "Source order"
                    )
                if (
                    value["state_universe"]["default_state_id"]
                    not in selected_state_ids
                ):
                    raise ManifestValidationError(
                        "Batch Item Sampling Plan must select the default state"
                    )

                universe_id_set = set(universe_state_ids)
                selected_id_set = set(selected_state_ids)
                seen_stratum_ids: set[str] = set()
                seen_stratum_criteria: set[
                    tuple[tuple[str, str], ...]
                ] = set()
                state_membership = {
                    state_id: 0 for state_id in universe_state_ids
                }
                source_first_indexes: list[int] = []
                for index, stratum in enumerate(value["strata"]):
                    member_id_list = stratum["state_ids"]
                    member_ids = set(member_id_list)
                    if not member_ids <= universe_id_set:
                        raise ManifestValidationError(
                            "Batch Item Sampling Plan strata may reference only "
                            "state universe identities"
                        )
                    if member_id_list != sorted(
                        member_id_list,
                        key=universe_state_ids.index,
                    ):
                        raise ManifestValidationError(
                            "Batch Item Sampling Plan stratum state_ids must "
                            "preserve Source order"
                        )
                    if not member_ids & selected_id_set:
                        raise ManifestValidationError(
                            "Batch Item Sampling Plan must select at least one "
                            f"state from strata[{index}]"
                        )
                    stratum_id = stratum["stratum_id"]
                    if stratum_id in seen_stratum_ids:
                        raise ManifestValidationError(
                            "Batch Item Sampling Plan stratum_id values must be unique"
                        )
                    seen_stratum_ids.add(stratum_id)
                    criteria_key = tuple(
                        (criterion[0], criterion[1])
                        for criterion in stratum["criteria"]
                    )
                    if criteria_key in seen_stratum_criteria:
                        raise ManifestValidationError(
                            "Batch Item Sampling Plan stratum criteria must be unique"
                        )
                    seen_stratum_criteria.add(criteria_key)

                    for state_id in member_ids:
                        state_membership[state_id] += 1
                        state_criteria = universe_by_id[state_id]["criteria"]
                        if value["strategy"] == "region_filter":
                            if (
                                len(stratum["criteria"]) != 1
                                or stratum["criteria"][0][0] != "region"
                                or stratum["criteria"][0] not in state_criteria
                            ):
                                raise ManifestValidationError(
                                    "RegionFilter strata must match each member's "
                                    "source-proven region criterion"
                                )
                        elif state_criteria[:-1] != stratum["criteria"]:
                            raise ManifestValidationError(
                                "Complex strata criteria must equal each member's "
                                "ordered criteria[:-1] parent branch"
                            )
                    source_first_indexes.append(min(
                        universe_state_ids.index(state_id)
                        for state_id in member_ids
                    ))
                if any(count != 1 for count in state_membership.values()):
                    raise ManifestValidationError(
                        "Batch Item Sampling Plan strata must partition the exact "
                        "state universe with one membership per state"
                    )
                if source_first_indexes != sorted(source_first_indexes):
                    raise ManifestValidationError(
                        "Batch Item Sampling Plan strata must preserve Source "
                        "first-appearance order"
                    )

                expected_seed = derive_sampling_seed(
                    algorithm_version=value["algorithm_version"],
                    source_sha256=value["source_sha256"],
                    item_id=value["item_id"],
                    profile_sha256=value["content_sampling_profile"]["sha256"],
                )
            except CanonicalIdentityError as error:
                raise ManifestValidationError(
                    f"Invalid Batch Item Sampling Plan identity: {error}"
                ) from error
            if value["seed"] != expected_seed:
                raise ManifestValidationError(
                    "Batch Item Sampling Plan seed does not match its frozen inputs"
                )

            coverage = value["coverage"]
            _validate_coverage_counts(
                coverage,
                context="Batch Item Sampling Plan coverage",
            )
            if coverage["universe_count"] != len(universe_state_ids):
                raise ManifestValidationError(
                    "Batch Item Sampling Plan universe_count must equal "
                    "state_universe.states length"
                )
            if coverage["selected_count"] != len(selected_state_ids):
                raise ManifestValidationError(
                    "Batch Item Sampling Plan selected_count must equal "
                    "selected_states length"
                )
            if value["effective_budget"] < value["target_budget"]:
                raise ManifestValidationError(
                    "Batch Item Sampling Plan effective_budget cannot be below "
                    "target_budget"
                )
            if coverage["selected_count"] > value["effective_budget"]:
                raise ManifestValidationError(
                    "Batch Item Sampling Plan selected_count cannot exceed "
                    "effective_budget"
                )
            if coverage["selected_count"] != min(
                coverage["universe_count"], value["effective_budget"]
            ):
                raise ManifestValidationError(
                    "Batch Item Sampling Plan must fill its effective budget or "
                    "select the entire smaller universe"
                )
        elif kind == "sampled_content_evidence":
            expected = document_identity_sha256(value, "evidence_sha256")
            if value["evidence_sha256"] != expected:
                raise ManifestValidationError(
                    "Sampled Content Evidence identity does not match its canonical body"
                )
            coverage = value["coverage"]
            selected_state_ids = coverage["selected_state_ids"]
            _validate_coverage_counts(
                coverage,
                context="Sampled Content Evidence coverage",
                selected_state_ids=selected_state_ids,
            )
            _validate_structure_counts(
                value["structure_validation"],
                coverage_universe_count=coverage["universe_count"],
                total_field="universe_count",
                context="Sampled Content Evidence structure validation",
            )
            _validate_comparison_identity(
                value["page_global_comparison"],
                context="Sampled Content Evidence page-global comparison",
            )
            if value["full_content_comparison"] is not None:
                _validate_comparison_identity(
                    value["full_content_comparison"],
                    context="Sampled Content Evidence full-content comparison",
                )
            sample_state_ids: list[str] = []
            try:
                for index, sample in enumerate(value["samples"]):
                    state = sample["state"]
                    state_id = derive_state_id(state["criteria"])
                    if state["state_id"] != state_id:
                        raise ManifestValidationError(
                            "Sampled Content Evidence sample state_id does not "
                            f"match samples[{index}].state.criteria"
                        )
                    sample_state_ids.append(state_id)
                    _validate_comparison_identity(
                        sample,
                        context=f"Sampled Content Evidence samples[{index}]",
                    )
            except CanonicalIdentityError as error:
                raise ManifestValidationError(
                    f"Invalid Sampled Content Evidence state identity: {error}"
                ) from error
            if value["mode"] == "stratified_sample" and (
                sample_state_ids != selected_state_ids
            ):
                raise ManifestValidationError(
                    "Sampled Content Evidence samples must exactly follow "
                    "coverage.selected_state_ids"
                )
        elif kind == "review_decision":
            expected = document_identity_sha256(value, "decision_id")
            if value["decision_id"] != expected:
                raise ManifestValidationError(
                    "Review Decision identity does not match its canonical body"
                )
            expected_item_id = f"{value['language']}/{value['resource_key']}"
            if value["item_id"] != expected_item_id:
                raise ManifestValidationError(
                    "Review Decision item_id must equal language/resource_key"
                )
        elif kind == "review" and value.get("schema_version") == "2.0":
            items = list(value["items"])
            expected_summary = {
                "total": len(items),
                "reviewable": sum(
                    item["status"]["evidence_binding"] != "stale"
                    for item in items
                ),
                "pending": sum(
                    item["status"]["review"] == "pending" for item in items
                ),
                "approved": sum(
                    item["status"]["review"] == "approved" for item in items
                ),
                "rejected": sum(
                    item["status"]["review"] == "rejected" for item in items
                ),
                "evidence_bound": sum(
                    item["status"]["evidence_binding"] == "bound"
                    for item in items
                ),
                "evidence_stale": sum(
                    item["status"]["evidence_binding"] == "stale"
                    for item in items
                ),
                "evidence_not_applicable": sum(
                    item["status"]["evidence_binding"] == "not_applicable"
                    for item in items
                ),
                "approval_eligible": sum(
                    item["status"]["approval_eligibility"] == "eligible"
                    for item in items
                ),
                "approval_blocked": sum(
                    item["status"]["approval_eligibility"] == "blocked"
                    for item in items
                ),
                "source_blocked": sum(
                    bool(item["source_quality_findings"]) for item in items
                ),
            }
            if value["summary"] != expected_summary:
                raise ManifestValidationError(
                    f"Review Queue 2.0 summary does not match items: expected {expected_summary}"
                )
            for item in items:
                expected_item_id = f"{item['language']}/{item['resource_key']}"
                if item["item_id"] != expected_item_id:
                    raise ManifestValidationError(
                        "Review Queue 2.0 item_id must equal language/resource_key"
                    )
                if item["inspection"]["mode"] == "interactive":
                    if item["artifacts"]["sampling_plan"] is None:
                        raise ManifestValidationError(
                            "Interactive Review Queue items require a Sampling Plan"
                        )
                    if not item["inspection"]["state_universe"]:
                        raise ManifestValidationError(
                            "Interactive Review Queue items require state_universe"
                        )
                else:
                    if item["artifacts"]["sampling_plan"] is not None:
                        raise ManifestValidationError(
                            "Full Review Queue items must not reference a Sampling Plan"
                        )
                    if item["inspection"]["state_universe"]:
                        raise ManifestValidationError(
                            "Full Review Queue items must not expose interactive states"
                        )
        elif kind == "validation" and value.get("schema_version") in ("2.0", "2.1"):
            version = str(value.get("schema_version"))
            if value["status"] != value["evidence"]["verdict"]:
                raise ManifestValidationError(
                    f"Validation {version} envelope status differs from its evidence verdict"
                )
            expected = validation_evidence_sha256(value)
            if value["evidence_sha256"] != expected:
                raise ManifestValidationError(
                    f"Validation {version} evidence identity does not match its canonical body"
                )
            coverage = value["evidence"]["content_validation"]["coverage"]
            _validate_coverage_counts(
                coverage,
                context=f"Validation {version} content coverage",
                selected_state_ids=coverage["selected_state_ids"],
            )
            _validate_structure_counts(
                value["evidence"]["structure_validation"],
                coverage_universe_count=coverage["universe_count"],
                total_field="total_count",
                context=f"Validation {version} structure validation",
            )
            try:
                expected_machine = machine_approval_preconditions(
                    "succeeded",
                    value["status"],
                ).to_dict()
                source_findings = value["evidence"]["source_quality_findings"]
                bindings = value["evidence"]["bindings"]
                if version == "2.1":
                    resolve_finding_policy(
                        validation_schema_version=version,
                        validation_profile_identity=bindings["validation_profile"],
                        finding_code_policy_identity=bindings[
                            "finding_code_policy_identity"
                        ],
                    )
                    finding_policy = self._validation_context.finding_code_policy_for(
                        bindings["validation_profile"]
                    )
                    if finding_policy is None:
                        raise ManifestValidationError(
                            "Validation 2.1 has no frozen Finding Code Policy"
                        )
                    expected_findings = classify_source_quality_findings(
                        source_findings,
                        finding_policy,
                    )
                    if source_findings != expected_findings:
                        raise ManifestValidationError(
                            "Validation 2.1 Source Quality Finding classifications "
                            "are not canonical"
                        )
                    expected_source = evaluate_source_findings(
                        source_findings,
                        finding_policy,
                    ).to_dict()
                else:
                    resolve_finding_policy(
                        validation_schema_version=version,
                        validation_profile_identity=bindings["validation_profile"],
                        finding_code_policy_identity=None,
                    )
                    expected_source = source_approval_preconditions(
                        source_findings
                    ).to_dict()
            except ReviewContractError as error:
                raise ManifestValidationError(
                    f"Invalid Validation {version} approval preconditions: {error}"
                ) from error
            preconditions = value["evidence"]["approval_preconditions"]
            if preconditions["machine"] != expected_machine:
                raise ManifestValidationError(
                    f"Validation {version} machine approval preconditions are not canonical"
                )
            if preconditions["source"] != expected_source:
                if version == "2.0":
                    raise ManifestValidationError(
                        "Validation 2.0 Source approval preconditions do not match "
                        "all unresolved Source Quality Findings"
                    )
                raise ManifestValidationError(
                    "Validation 2.1 Source approval preconditions are not canonical"
                )
        elif kind == "release_manifest":
            try:
                validate_release_manifest_bindings(value)
            except ReleaseContractError as error:
                raise ManifestValidationError(
                    f"Invalid Release Manifest binding ({error.code}): {error}"
                ) from error
        elif kind == "publication_receipt":
            try:
                validate_publication_receipt_bindings(value)
            except ReleaseContractError as error:
                raise ManifestValidationError(
                    f"Invalid Publication Receipt binding ({error.code}): {error}"
                ) from error

    def _validator(self, kind: str, version: str) -> Draft202012Validator:
        path = self._schema_path(kind, version)
        schema_sha256 = sha256_file(path)
        cache_key = (kind, version, schema_sha256)
        if cache_key not in self._validators:
            try:
                schema = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise StateStoreError(f"Unable to load pipeline schema {path}: {error}") from error
            Draft202012Validator.check_schema(schema)
            self._validators[cache_key] = Draft202012Validator(
                schema, format_checker=FormatChecker()
            )
        return self._validators[cache_key]

    def _schema_path(self, kind: str, version: str) -> Path:
        if kind not in self.SCHEMAS:
            raise StateStoreError(f"Unknown pipeline schema kind: {kind}")
        filename = self.SCHEMAS[kind].get(version)
        if filename is None:
            raise ManifestValidationError(
                f"Unsupported {kind} schema_version: {version or '<missing>'}"
            )
        return self.schema_dir / filename

    @staticmethod
    def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = _serialized_json_payload(value)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory_descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except Exception:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            raise

    def _write_json_once(
        self,
        path: Path,
        value: Mapping[str, Any],
        kind: str,
    ) -> None:
        try:
            relative_to_runs = path.resolve().relative_to(self.runs_dir)
        except ValueError as error:
            raise StateStoreError(
                f"Step 4 artifact path escapes the runs directory: {path}"
            ) from error
        if not relative_to_runs.parts:
            raise StateStoreError(f"Invalid Step 4 artifact path: {path}")
        batch_id = relative_to_runs.parts[0]
        self._validate_batch_id(batch_id)
        if not (self.runs_dir / batch_id).is_dir():
            raise UnknownBatchError(f"Unknown batch for artifact path: {path}")
        if path.is_symlink():
            raise StateStoreError(f"Step 4 artifact path is a symlink: {path}")
        current = path.parent
        while current != self.runs_dir and current != current.parent:
            if current.exists() and current.is_symlink():
                raise StateStoreError(
                    f"Step 4 artifact parent traverses a symlink: {current}"
                )
            current = current.parent
        payload = artifact_json_text(value)
        if path.exists():
            if not path.is_file():
                raise StateStoreError(f"Step 4 artifact target is not a file: {path}")
            try:
                existing = path.read_text(encoding="utf-8")
            except OSError as error:
                raise StateStoreError(f"Unable to read existing artifact {path}: {error}") from error
            if existing != payload:
                raise StateStoreError(
                    f"Existing {kind} artifact differs from deterministic replay: {path}"
                )
            if kind in self.SCHEMAS:
                cached = json.loads(existing)
                self._cache_validated_document(path, cached, kind)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(path, value)
        if sha256_file(path) != artifact_json_sha256(value):
            raise StateStoreError(f"Artifact hash changed while writing: {path}")
        if kind in self.SCHEMAS:
            self._cache_validated_document(path, value, kind)

    @staticmethod
    def _validate_batch_id(batch_id: str) -> None:
        if len(batch_id) != 25 or batch_id[8] != "T" or batch_id[15] != "Z" or batch_id[16] != "-":
            raise StateStoreError(f"Invalid batch id: {batch_id}")
        stamp, suffix = batch_id.split("-", 1)
        try:
            datetime.strptime(stamp, "%Y%m%dT%H%M%SZ")
        except ValueError as error:
            raise StateStoreError(f"Invalid batch id: {batch_id}") from error
        if len(suffix) != 8 or any(character not in "0123456789abcdef" for character in suffix):
            raise StateStoreError(f"Invalid batch id: {batch_id}")
