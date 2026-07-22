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

    def __init__(self, root: str | Path = ".", *, timeout: float = 0.0, poll_interval: float = 0.1) -> None:
        self.root = Path(root).resolve()
        self.path = self.root / "runs" / ".pipeline.lock"
        self.timeout = max(0.0, timeout)
        self.poll_interval = max(0.01, poll_interval)
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
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as error:
                if error.errno not in (errno.EACCES, errno.EAGAIN):
                    stream.close()
                    raise RepositoryLockError(f"Unable to acquire repository lock: {error}") from error
                if time.monotonic() >= deadline:
                    stream.close()
                    raise RepositoryLockError(f"Repository pipeline lock is held: {self.path}") from error
                time.sleep(min(self.poll_interval, max(0.0, deadline - time.monotonic())))
        stream.seek(0)
        stream.truncate()
        stream.write(json.dumps({"pid": os.getpid(), "acquired_at": utc_now()}, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
        self._stream = stream
        return self

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
    def is_locked(cls, root: str | Path = ".") -> bool:
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
                    return True
                raise RepositoryLockError(f"Unable to probe repository lock: {error}") from error
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            return False
        finally:
            stream.close()


class StateStore:
    """Persist immutable inputs, mutable truth, and rebuildable projections."""

    SCHEMAS = {
        "input": "pipeline-input-manifest-1.0.schema.json",
        "batch": "pipeline-batch-manifest-1.0.schema.json",
        "validation": "pipeline-validation-1.0.schema.json",
        "review": "pipeline-review-queue-1.0.schema.json",
        "report": "pipeline-batch-report-1.0.schema.json",
    }

    def __init__(self, root: str | Path = ".", runs_dir: str | Path = "runs") -> None:
        self.root = Path(root).resolve()
        candidate = Path(runs_dir)
        self.runs_dir = candidate.resolve() if candidate.is_absolute() else (self.root / candidate).resolve()
        self.schema_dir = self.root / "schemas"
        self._validators: dict[str, Draft202012Validator] = {}
        self._manifest_cache: dict[str, dict[str, Any]] = {}
        self._batch_item_validator: Draft202012Validator | None = None

    def run_dir(self, batch_id: str) -> Path:
        self._validate_batch_id(batch_id)
        return self.runs_dir / batch_id

    def create_run(
        self,
        input_manifest: InputManifest | Mapping[str, Any],
        batch_manifest: BatchManifest | Mapping[str, Any] | None = None,
    ) -> Path:
        frozen = input_manifest.to_dict() if isinstance(input_manifest, InputManifest) else copy.deepcopy(dict(input_manifest))
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
        self._write_new(directory / "batch-manifest.json", mutable, "batch")
        self._manifest_cache[batch_id] = copy.deepcopy(mutable)
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
        return self._read(self.run_dir(batch_id) / "input-manifest.json", "input")

    def read_manifest(self, batch_id: str) -> dict[str, Any]:
        value = self._read(self.run_dir(batch_id) / "batch-manifest.json", "batch")
        frozen_path = self.run_dir(batch_id) / value["input_manifest"]["path"]
        if not frozen_path.is_file() or sha256_file(frozen_path) != value["input_manifest"]["sha256"]:
            raise ImmutableManifestError(f"Input manifest hash mismatch for batch {batch_id}")
        self._manifest_cache[batch_id] = copy.deepcopy(value)
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
        current = copy.deepcopy(
            self._manifest_cache.get(batch_id) or self.read_manifest(batch_id)
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

        for immutable_key in ("schema_version", "batch_id", "created_at", "input_manifest"):
            if candidate.get(immutable_key) != current.get(immutable_key):
                raise ImmutableManifestError(f"Mutable manifest cannot change {immutable_key}")
        if set(candidate.get("items", {})) != set(current.get("items", {})):
            raise ImmutableManifestError("Mutable manifest cannot add or remove Batch Items")
        candidate["revision"] = current["revision"] + 1
        candidate["updated_at"] = utc_now()
        if changed_item_ids is None:
            self._validate(candidate, "batch")
        else:
            self._validate_batch_incremental(candidate, current, changed_item_ids)
        self._atomic_write(path, candidate)
        self._manifest_cache[batch_id] = copy.deepcopy(candidate)
        return copy.deepcopy(candidate)

    def _validate_batch_incremental(
        self,
        candidate: Mapping[str, Any],
        current: Mapping[str, Any],
        declared_item_ids: Iterable[str],
    ) -> None:
        """Apply the Batch Manifest schema to the root and changed items only.

        The repository lock gives a mutator exclusive ownership. Comparing the
        candidate with the cached, fully validated revision ensures callers
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
        self._raise_validation_errors(self._validator("batch").iter_errors(root), "batch")

        validator = self._batch_item_schema_validator()
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

    def _read(self, path: Path, kind: str) -> dict[str, Any]:
        if not path.is_file():
            raise UnknownBatchError(f"Pipeline state does not exist: {path}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise StateStoreError(f"Unable to read pipeline state {path}: {error}") from error
        self._validate(value, kind)
        return value

    def _write_new(self, path: Path, value: Mapping[str, Any], kind: str) -> None:
        if path.exists():
            raise StateStoreError(f"Pipeline state already exists: {path}")
        self._validate(value, kind)
        self._atomic_write(path, value)

    def _validate(self, value: Mapping[str, Any], kind: str) -> None:
        validator = self._validator(kind)
        self._raise_validation_errors(validator.iter_errors(value), kind)
        self._validate_semantics(value, kind)

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

    def _batch_item_schema_validator(self) -> Draft202012Validator:
        if self._batch_item_validator is None:
            batch_schema = self._validator("batch").schema
            item_schema = {
                "$schema": batch_schema.get("$schema"),
                "$defs": batch_schema["$defs"],
                "$ref": "#/$defs/item",
            }
            self._batch_item_validator = Draft202012Validator(
                item_schema, format_checker=FormatChecker()
            )
        return self._batch_item_validator

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

    def _validator(self, kind: str) -> Draft202012Validator:
        if kind not in self.SCHEMAS:
            raise StateStoreError(f"Unknown pipeline schema kind: {kind}")
        if kind not in self._validators:
            path = self.schema_dir / self.SCHEMAS[kind]
            try:
                schema = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise StateStoreError(f"Unable to load pipeline schema {path}: {error}") from error
            Draft202012Validator.check_schema(schema)
            self._validators[kind] = Draft202012Validator(schema, format_checker=FormatChecker())
        return self._validators[kind]

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
