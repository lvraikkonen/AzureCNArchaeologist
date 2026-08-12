"""Immutable v0.5.3 Evidence bundle writer and read-only verifier."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any, Mapping

from src.independent_fidelity.contracts import (
    bytes_sha256,
    validate_evidence,
)
from src.independent_fidelity.v053_io import (
    SafeReadError,
    read_regular_bytes,
    safe_relative_path,
    strict_json_bytes,
)
from src.independent_fidelity.verifier import VerificationRun


class V053BundleError(ValueError):
    """An Evidence bundle is incomplete, unsafe, or internally inconsistent."""


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _referenced_files(evidence: Mapping[str, Any]) -> set[str]:
    paths = {"evidence.json"}
    for scope in evidence["scopes"]:
        for key in ("source", "expected", "payload", "diff"):
            raw = scope[key]["path"]
            try:
                relative = safe_relative_path(raw)
            except SafeReadError as error:
                raise V053BundleError(str(error)) from error
            value = relative.as_posix()
            if value in paths:
                raise V053BundleError(
                    f"Evidence repeats a physical artifact path: {value}"
                )
            paths.add(value)
    return paths


def _physical_files(bundle_root: Path) -> set[str]:
    if bundle_root.is_symlink() or not bundle_root.is_dir():
        raise V053BundleError(
            f"Evidence bundle is not a regular directory: {bundle_root}"
        )
    files: set[str] = set()
    for path in sorted(bundle_root.rglob("*")):
        try:
            mode = path.lstat().st_mode
        except OSError as error:
            raise V053BundleError(f"Cannot inspect bundle path {path}: {error}") from error
        if stat.S_ISLNK(mode):
            raise V053BundleError(f"Evidence bundle contains a symlink: {path}")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise V053BundleError(
                f"Evidence bundle contains a non-regular file: {path}"
            )
        files.add(path.relative_to(bundle_root).as_posix())
    return files


def bundle_inventory(bundle_root: str | Path) -> Mapping[str, str]:
    candidate = Path(bundle_root)
    if candidate.is_symlink():
        raise V053BundleError(f"Evidence bundle cannot be a symlink: {candidate}")
    root = candidate.resolve()
    return {
        path: bytes_sha256(read_regular_bytes(root, path))
        for path in sorted(_physical_files(root))
    }


def verify_bundle(
    repository_root: str | Path,
    bundle_root: str | Path,
) -> dict[str, Any]:
    candidate = Path(bundle_root)
    if candidate.is_symlink():
        raise V053BundleError(f"Evidence bundle cannot be a symlink: {candidate}")
    root = candidate.resolve()
    try:
        raw_evidence = read_regular_bytes(root, "evidence.json")
        evidence = strict_json_bytes(
            raw_evidence,
            description=f"{root}/evidence.json",
            expected_type=dict,
        )
    except SafeReadError as error:
        raise V053BundleError(str(error)) from error
    try:
        validated = validate_evidence(repository_root, evidence)
    except ValueError as error:
        raise V053BundleError(f"Evidence contract is invalid: {error}") from error
    if validated.get("schema_version") != "1.1":
        raise V053BundleError(
            "v0.5.3 bundle verification requires Evidence schema_version 1.1"
        )
    expected_files = _referenced_files(validated)
    actual_files = _physical_files(root)
    if actual_files != expected_files:
        raise V053BundleError(
            "Evidence bundle file set differs from canonical references: "
            f"missing={sorted(expected_files - actual_files)!r}, "
            f"unexpected={sorted(actual_files - expected_files)!r}"
        )
    for scope in validated["scopes"]:
        for key in ("source", "expected", "payload"):
            reference = scope[key]
            try:
                data = read_regular_bytes(root, reference["path"])
            except SafeReadError as error:
                raise V053BundleError(str(error)) from error
            actual = bytes_sha256(data)
            if actual != reference["sha256"]:
                raise V053BundleError(
                    f"Fragment SHA-256 mismatch for {reference['path']}: "
                    f"expected={reference['sha256']}, actual={actual}"
                )
        diff_path = scope["diff"]["path"]
        try:
            diff = read_regular_bytes(root, diff_path)
            diff.decode("utf-8")
        except (SafeReadError, UnicodeDecodeError) as error:
            raise V053BundleError(
                f"Readable diff is missing or invalid: {diff_path}: {error}"
            ) from error
        actual_diff_sha = bytes_sha256(diff)
        if actual_diff_sha != scope["diff"]["sha256"]:
            raise V053BundleError(
                f"Diff SHA-256 mismatch for {diff_path}: "
                f"expected={scope['diff']['sha256']}, actual={actual_diff_sha}"
            )
    return validated


def build_bundle(
    bundle_root: str | Path,
    *,
    repository_root: str | Path,
    run: VerificationRun,
) -> dict[str, Any]:
    root = Path(bundle_root)
    if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
        raise V053BundleError(
            "Bundle build root must be an existing empty regular directory"
        )
    evidence = dict(run.evidence)
    expected_files = _referenced_files(evidence)
    if set(run.fragments) != expected_files - {"evidence.json"}:
        raise V053BundleError(
            "Verification fragments differ from Evidence artifact references"
        )
    for relative, content in sorted(run.fragments.items()):
        try:
            safe = safe_relative_path(relative)
        except SafeReadError as error:
            raise V053BundleError(str(error)) from error
        path = root / safe
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))
    (root / "evidence.json").write_bytes(_json_bytes(evidence))
    return verify_bundle(repository_root, root)


def atomic_promote_bundle(
    canonical_root: str | Path,
    *,
    repository_root: str | Path,
    run: VerificationRun,
) -> dict[str, Any]:
    import shutil
    import tempfile

    canonical = Path(canonical_root)
    parent = canonical.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{canonical.name}.tmp-", dir=parent)
    )
    try:
        evidence = build_bundle(
            temporary,
            repository_root=repository_root,
            run=run,
        )
        if canonical.exists() or canonical.is_symlink():
            raise V053BundleError(
                f"Canonical Evidence path appeared during record: {canonical}"
            )
        os.rename(temporary, canonical)
        return evidence
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
