"""Strict configuration and JSON helpers for the quarantined experiment lane."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


PRODUCT_KEY = "virtual-machines"
LANGUAGES = ("zh-cn", "en-us")
CONFIG_RELATIVE_PATH = Path("data/configs/experimental-extraction-exceptions.json")
CONFIG_SCHEMA_RELATIVE_PATH = Path("schemas/experimental-extraction-exceptions-1.0.schema.json")
MANIFEST_SCHEMA_RELATIVE_PATH = Path("schemas/experimental-extraction-manifest-1.0.schema.json")
CANDIDATE_SCHEMA_RELATIVE_PATH = Path("schemas/experimental-payload-candidate-1.0.schema.json")
MANIFEST_FILENAME = "experiment-manifest.json"
CANDIDATE_FILENAME = "virtual-machines.unvalidated.json"
EXPERIMENT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SEMVER_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class ExperimentalExtractionError(RuntimeError):
    """A fail-closed error in the experimental extraction lane."""


@dataclass(frozen=True)
class LoadedException:
    value: dict[str, Any]
    config_path: Path
    config_sha256: str
    schema_path: Path
    schema_sha256: str
    project_version: str


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def read_json(path: Path) -> Any:
    try:
        text = path.read_bytes().decode("utf-8", errors="strict")
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number: {value}")
            ),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ExperimentalExtractionError(f"Invalid JSON artifact {path}: {error}") from error


def read_json_object(path: Path) -> dict[str, Any]:
    value = read_json(path)
    if not isinstance(value, dict):
        raise ExperimentalExtractionError(f"JSON artifact must be an object: {path}")
    return value


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                value,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


def resolve_repository_file(root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ExperimentalExtractionError(f"Unsafe repository-relative path: {relative_path}")
    repository_root = root.resolve()
    lexical = repository_root / relative
    current = repository_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ExperimentalExtractionError(f"Symlinks are forbidden for experimental inputs: {relative_path}")
    try:
        resolved = lexical.resolve(strict=True)
        resolved.relative_to(repository_root)
    except (OSError, ValueError) as error:
        raise ExperimentalExtractionError(f"Experimental input is missing or escapes the repository: {relative_path}") from error
    if not resolved.is_file():
        raise ExperimentalExtractionError(f"Experimental input is not a regular file: {relative_path}")
    return resolved


def read_limited_bytes(path: Path, *, expected_bytes: int, max_bytes: int) -> bytes:
    try:
        stat_size = path.stat().st_size
    except OSError as error:
        raise ExperimentalExtractionError(f"Cannot stat experimental source: {path}") from error
    if stat_size != expected_bytes:
        raise ExperimentalExtractionError(
            f"Experimental source byte count changed: expected {expected_bytes}, found {stat_size}"
        )
    if stat_size > max_bytes:
        raise ExperimentalExtractionError(
            f"Experimental source exceeds the fixed input limit: {stat_size} > {max_bytes}"
        )
    try:
        with path.open("rb") as handle:
            value = handle.read(max_bytes + 1)
    except OSError as error:
        raise ExperimentalExtractionError(f"Cannot read experimental source: {path}") from error
    if len(value) > max_bytes:
        raise ExperimentalExtractionError("Experimental source grew beyond the fixed input limit while reading")
    if len(value) != expected_bytes:
        raise ExperimentalExtractionError("Experimental source changed while reading")
    return value


def validate_schema(value: Any, schema_path: Path, label: str) -> None:
    schema = read_json_object(schema_path)
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        raise ExperimentalExtractionError(f"Invalid {label} schema: {error}") from error
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    if not errors:
        return
    rendered = []
    for error in errors:
        location = "$" + "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}"
            for part in error.absolute_path
        )
        rendered.append(f"{location}: {error.message}")
    raise ExperimentalExtractionError(f"{label} schema validation failed: {'; '.join(rendered)}")


def validate_experiment_id(experiment_id: str) -> str:
    if not EXPERIMENT_ID_PATTERN.fullmatch(experiment_id):
        raise ExperimentalExtractionError(
            "experiment-id must match ^[a-z0-9][a-z0-9._-]{0,63}$"
        )
    return experiment_id


def _project_version(root: Path) -> str:
    path = root / "pyproject.toml"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ExperimentalExtractionError(f"Cannot read project version from {path}: {error}") from error
    in_project = False
    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            in_project = line == "[project]"
            continue
        if in_project:
            match = re.fullmatch(r'version\s*=\s*"([^"]+)"', line)
            if match:
                version = match.group(1)
                if not SEMVER_PATTERN.fullmatch(version):
                    raise ExperimentalExtractionError(f"Project version is not strict SemVer: {version}")
                return version
    raise ExperimentalExtractionError(f"[project].version is missing from {path}")


def _version_tuple(version: str) -> tuple[int, int, int]:
    match = SEMVER_PATTERN.fullmatch(version)
    if not match:
        raise ExperimentalExtractionError(f"Invalid expiry project version: {version}")
    return tuple(int(part) for part in match.groups())


def load_exception(root: str | Path) -> LoadedException:
    repository_root = Path(root).resolve()
    config_path = repository_root / CONFIG_RELATIVE_PATH
    schema_path = repository_root / CONFIG_SCHEMA_RELATIVE_PATH
    config = read_json_object(config_path)
    validate_schema(config, schema_path, "experimental exception config")

    exceptions = config.get("exceptions")
    if not isinstance(exceptions, dict) or set(exceptions) != {PRODUCT_KEY}:
        raise ExperimentalExtractionError("Exception config must contain only virtual-machines")
    value = exceptions[PRODUCT_KEY]
    if not isinstance(value, dict):
        raise ExperimentalExtractionError("virtual-machines exception must be an object")

    limits = value["limits"]
    for language in LANGUAGES:
        source = value["sources"][language]
        expected_resolved = (
            Path("data/current_prod_html") / language / source["snapshot_path"]
        ).as_posix()
        if source["resolved_path"] != expected_resolved:
            raise ExperimentalExtractionError(
                f"Configured source path does not resolve from the Product Definition for {language}"
            )
        if source["bytes"] > limits["max_source_bytes"]:
            raise ExperimentalExtractionError(
                f"Configured source exceeds the fixed input limit for {language}"
            )

    current_version = _project_version(repository_root)
    expiry_version = value["expiry"]["project_version_at_least"]
    if _version_tuple(current_version) >= _version_tuple(expiry_version):
        raise ExperimentalExtractionError(
            f"Experimental exception expired at project version {expiry_version}"
        )

    return LoadedException(
        value=deepcopy(value),
        config_path=config_path,
        config_sha256=sha256_file(config_path),
        schema_path=schema_path,
        schema_sha256=sha256_file(schema_path),
        project_version=current_version,
    )


def repository_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise ExperimentalExtractionError(f"Artifact escapes repository root: {path}") from error
