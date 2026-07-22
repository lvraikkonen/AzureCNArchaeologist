"""Git and immutable-input provenance for reproducible pipeline runs."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.core.product_catalog import ProductCatalog, canonical_json, sha256_file
from src.pipeline.models import utc_now


class ProvenanceError(RuntimeError):
    """Fatal provenance could not be captured or verified."""


class GitHeadError(ProvenanceError):
    """The repository has no usable Git HEAD."""


class DirtyWorktreeError(ProvenanceError):
    """A clean worktree was required but material changes were present."""


class ProductIndexDriftError(ProvenanceError):
    """The checked-in Product Index does not match Product Definitions."""


class ProvenanceDriftError(ProvenanceError):
    """Frozen immutable inputs no longer match the repository."""

    def __init__(self, differences: Iterable[str]) -> None:
        self.differences = tuple(differences)
        super().__init__("Immutable pipeline provenance changed:\n- " + "\n- ".join(self.differences))


class ProvenanceProvider:
    """Capture and later compare only inputs that can affect pipeline results.

    A full non-generated worktree fingerprint is retained as evidence. Resume
    verification compares Git HEAD plus the explicit immutable input file map;
    normalized inputs and run artifacts are intentionally excluded.
    """

    DEFAULT_GENERATED_PREFIXES = ("runs/", "data/prod-html/")

    def __init__(
        self,
        root: str | Path = ".",
        *,
        generated_prefixes: Iterable[str] = DEFAULT_GENERATED_PREFIXES,
        clean_excluded_prefixes: Iterable[str] = ("runs/",),
    ) -> None:
        self.root = Path(root).resolve()
        self.generated_prefixes = tuple(self._prefix(value) for value in generated_prefixes)
        self.clean_excluded_prefixes = tuple(self._prefix(value) for value in clean_excluded_prefixes)

    def capture(self, *, allow_dirty: bool = False, validate_catalog: bool = True) -> dict[str, Any]:
        commit = self._git("rev-parse", "--verify", "HEAD").strip()
        if len(commit) != 40:
            raise GitHeadError("Git HEAD is not a full commit hash")

        changes = self._material_changes()
        if changes and not allow_dirty:
            raise DirtyWorktreeError(
                "Pipeline runs require a clean worktree; use --allow-dirty to freeze these changes: "
                + ", ".join(changes)
            )

        if validate_catalog:
            catalog = ProductCatalog(self.root)
            changed, _ = catalog.write_index(check=True)
            if changed:
                raise ProductIndexDriftError("data/configs/products-index.json is out of date")
            catalog.validate_contract_lock()

        worktree_files = self._worktree_files()
        worktree_hashes = self._hash_paths(worktree_files)
        immutable_files = self._immutable_files()
        immutable_hashes = self._hash_paths(immutable_files)
        return {
            "schema_version": "1.0",
            "captured_at": utc_now(),
            "git_commit": commit,
            "dirty": bool(changes),
            "reproducible": not changes,
            "worktree_changes": changes,
            "worktree_fingerprint": "sha256:" + hashlib.sha256(
                canonical_json(worktree_hashes).encode("utf-8")
            ).hexdigest(),
            "immutable_fingerprint": "sha256:" + hashlib.sha256(
                canonical_json(immutable_hashes).encode("utf-8")
            ).hexdigest(),
            "immutable_files": immutable_hashes,
        }

    def verify(self, frozen: Mapping[str, Any], *, validate_catalog: bool = True) -> None:
        differences: list[str] = []
        try:
            current_commit = self._git("rev-parse", "--verify", "HEAD").strip()
        except ProvenanceError as error:
            raise ProvenanceDriftError([str(error)]) from error
        if current_commit != frozen.get("git_commit"):
            differences.append(f"git_commit: expected {frozen.get('git_commit')}, found {current_commit}")

        expected_files = frozen.get("immutable_files")
        if not isinstance(expected_files, Mapping):
            differences.append("immutable_files: missing or invalid frozen file map")
        else:
            expected_fingerprint = "sha256:" + hashlib.sha256(
                canonical_json(dict(expected_files)).encode("utf-8")
            ).hexdigest()
            if frozen.get("immutable_fingerprint") != expected_fingerprint:
                differences.append("immutable_fingerprint: does not match frozen file map")
            current_files = set(self._immutable_files())
            for relative in sorted(current_files - set(expected_files)):
                differences.append(f"{relative}: unexpected immutable input")
            for relative, expected_hash in sorted(expected_files.items()):
                path = self.root / relative
                if not path.is_file():
                    differences.append(f"{relative}: missing")
                    continue
                actual_hash = sha256_file(path)
                if actual_hash != expected_hash:
                    differences.append(f"{relative}: sha256 changed")

        if validate_catalog:
            try:
                catalog = ProductCatalog(self.root)
                changed, _ = catalog.write_index(check=True)
                if changed:
                    differences.append("data/configs/products-index.json: derived index drift")
                catalog.validate_contract_lock()
            except Exception as error:  # catalog errors become stable fatal provenance errors
                differences.append(f"catalog/contracts: {error}")
        if differences:
            raise ProvenanceDriftError(differences)

    def _immutable_files(self) -> list[str]:
        candidates: set[str] = set()
        for relative in self._worktree_files():
            if self._has_prefix(relative, self.generated_prefixes):
                continue
            if (
                relative == "cli.py"
                or relative in {"pyproject.toml", "uv.lock"}
                or relative.startswith("src/")
                or relative.startswith("scripts/")
                or relative.startswith("schemas/")
                or relative.startswith("data/configs/")
                or relative.startswith("data/current_prod_html/")
            ):
                candidates.add(relative)

        lock_path = self.root / "schemas" / "contracts.lock.json"
        if lock_path.is_file():
            try:
                lock = json.loads(lock_path.read_text(encoding="utf-8"))
                for item in lock.get("upstream_contracts", []):
                    relative = item.get("path")
                    if isinstance(relative, str) and (self.root / relative).is_file():
                        candidates.add(relative)
            except (OSError, ValueError):
                pass
        return sorted(candidates)

    def _worktree_files(self) -> list[str]:
        output = self._git_bytes("ls-files", "-z", "--cached", "--others", "--exclude-standard")
        values = (value.decode("utf-8", "surrogateescape") for value in output.split(b"\0") if value)
        return sorted({
            value for value in values
            if not self._has_prefix(value, self.clean_excluded_prefixes) and (self.root / value).is_file()
        })

    def _material_changes(self) -> list[str]:
        output = self._git("status", "--porcelain=v1", "--untracked-files=all")
        changes: list[str] = []
        for line in output.splitlines():
            if len(line) < 4:
                continue
            path = line[3:]
            if " -> " in path:
                path = path.rsplit(" -> ", 1)[1]
            path = path.strip('"')
            if not self._has_prefix(path, self.clean_excluded_prefixes):
                changes.append(f"{line[:2]} {path}")
        return sorted(changes)

    def _hash_paths(self, relatives: Iterable[str]) -> dict[str, str]:
        return {relative: sha256_file(self.root / relative) for relative in sorted(relatives)}

    @staticmethod
    def _has_prefix(relative: str, prefixes: Iterable[str]) -> bool:
        normalized = relative.replace("\\", "/").lstrip("./")
        return any(normalized == prefix[:-1] or normalized.startswith(prefix) for prefix in prefixes)

    @staticmethod
    def _prefix(value: str) -> str:
        return value.replace("\\", "/").strip("/") + "/"

    def _git(self, *arguments: str) -> str:
        return self._git_bytes(*arguments).decode("utf-8", "replace")

    def _git_bytes(self, *arguments: str) -> bytes:
        try:
            result = subprocess.run(
                ("git", *arguments), cwd=self.root, check=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except OSError as error:
            raise ProvenanceError(f"Unable to execute git: {error}") from error
        if result.returncode != 0:
            message = result.stderr.decode("utf-8", "replace").strip()
            raise ProvenanceError(f"git {' '.join(arguments)} failed: {message}")
        return result.stdout
