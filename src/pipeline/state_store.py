"""Schema-validated, atomic JSON state and repository-wide advisory locking."""

from __future__ import annotations

import copy
import errno
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

from src.core.product_catalog import sha256_file
from src.core.validation_context import ValidationContextError, ValidationContextRegistry
from src.pipeline.models import BatchManifest, InputManifest, utc_now

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
        "validation": {"1.0": "pipeline-validation-1.0.schema.json"},
        "review": {"1.0": "pipeline-review-queue-1.0.schema.json"},
        "report": {"1.0": "pipeline-batch-report-1.0.schema.json"},
    }

    def __init__(self, root: str | Path = ".", runs_dir: str | Path = "runs") -> None:
        self.root = Path(root).resolve()
        candidate = Path(runs_dir)
        self.runs_dir = candidate.resolve() if candidate.is_absolute() else (self.root / candidate).resolve()
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
        self._validate(frozen, "input")
        batch_id = frozen["batch_id"]
        directory = self.run_dir(batch_id)
        if directory.exists():
            raise StateStoreError(f"Batch already exists: {batch_id}")
        for relative in ("outputs", "diagnostics", "validation", "review", "logs"):
            (directory / relative).mkdir(parents=True, exist_ok=False)

        self.write_input_manifest(batch_id, frozen)
        mutable = (
            BatchManifest.from_input_manifest(frozen).to_dict()
            if batch_manifest is None
            else batch_manifest.to_dict() if isinstance(batch_manifest, BatchManifest)
            else copy.deepcopy(dict(batch_manifest))
        )
        mutable["input_manifest"] = {
            "path": "input-manifest.json",
            "sha256": sha256_file(directory / "input-manifest.json"),
        }
        if mutable.get("schema_version") != "2.0":
            raise ImmutableManifestError("New pipeline runs require Batch Manifest 2.0")
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
        path = self.run_dir(batch_id) / "batch-manifest.json"
        # The on-disk Batch/Input pair is authoritative.  Always replay it
        # before a mutation so a warm cache cannot conceal manifest tampering
        # and then overwrite that evidence with a fresh revision.
        current = copy.deepcopy(self.read_manifest(batch_id))
        if current.get("schema_version") != "2.0":
            raise ImmutableManifestError(
                "Pipeline Manifest 1.x is read-only; new mutation requires a 2.0 run"
            )
        if expected_revision is not None and current["revision"] != expected_revision:
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
        ):
            if candidate.get(immutable_key) != current.get(immutable_key):
                raise ImmutableManifestError(f"Mutable manifest cannot change {immutable_key}")
        if set(candidate.get("items", {})) != set(current.get("items", {})):
            raise ImmutableManifestError("Mutable manifest cannot add or remove Batch Items")
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
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(path, value)
        return path

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
        if verify_context:
            self._verify_frozen_context(value, kind)

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

    @staticmethod
    def _validate_semantics(value: Mapping[str, Any], kind: str) -> None:
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
        payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
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
