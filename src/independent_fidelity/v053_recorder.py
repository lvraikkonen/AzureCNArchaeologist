"""No-overwrite record/verify operations for v0.5.3 target bundles."""

from __future__ import annotations

import subprocess
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.independent_fidelity.contracts import bytes_sha256, evidence_is_current
from src.independent_fidelity.targets import (
    DEFAULT_TARGET_SET_ID,
    TargetSetError,
    load_target_set,
)
from src.independent_fidelity.v053_adapters import AdapterError
from src.independent_fidelity.v053_bundle import (
    V053BundleError,
    atomic_promote_bundle,
    bundle_inventory,
    verify_bundle,
)
from src.independent_fidelity.v053_io import SafeReadError, read_regular_bytes
from src.independent_fidelity.v053_target import (
    BoundV053Target,
    V053BindingError,
    bind_batch_item,
)
from src.independent_fidelity.v053_verifier import (
    build_basis,
    reconstruct_bound_target,
    verify_reconstruction,
)


@dataclass(frozen=True)
class V053OperationResult:
    action: str
    outcome: str
    exit_code: int
    code: str
    reason: str
    batch_id: str
    item_id: str
    role: str | None = None
    owner: str | None = None
    qualified: bool | None = None
    verdict: str | None = None
    coverage: Mapping[str, Any] | None = None
    evidence_semantic_sha256: str | None = None
    evidence_artifact_sha256: str | None = None
    evidence_path: str | None = None
    bundle_path: str | None = None
    producer_commit: str | None = None
    repository_head: str | None = None
    l3a_summary: Mapping[str, Any] | None = None
    claim_limitations: tuple[str, ...] = ()
    warnings: tuple[Mapping[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class V053SetResult:
    action: str
    batch_id: str
    exit_code: int
    results: tuple[V053OperationResult, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "batch_id": self.batch_id,
            "exit_code": self.exit_code,
            "results": [result.as_dict() for result in self.results],
        }


def _git_head(root: Path) -> str | None:
    process = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return process.stdout.strip() if process.returncode == 0 else None


def _require_formal_repository(target: BoundV053Target) -> str:
    head = _git_head(target.repository_root)
    if head != target.producer_commit:
        raise V053BindingError(
            "producer_commit_mismatch",
            "Repository HEAD must equal the Batch producer commit before record: "
            f"expected={target.producer_commit}, actual={head}",
        )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=target.repository_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        raise V053BindingError(
            "repository_status_unavailable", status.stderr.strip()
        )
    if status.stdout:
        raise V053BindingError(
            "repository_not_clean",
            "Formal Evidence record requires a clean worktree",
        )
    if head is None:
        raise V053BindingError(
            "repository_head_unavailable", "Cannot resolve repository HEAD"
        )
    return head


def _result(
    *,
    action: str,
    outcome: str,
    exit_code: int,
    code: str,
    reason: str,
    batch_id: str,
    item_id: str,
    target: BoundV053Target | None = None,
    evidence: Mapping[str, Any] | None = None,
    warnings: Sequence[Mapping[str, Any]] = (),
) -> V053OperationResult:
    bundle = target.canonical_bundle_root if target is not None else None
    evidence_path = bundle / "evidence.json" if bundle is not None else None
    artifact_sha = None
    if evidence is not None and bundle is not None:
        try:
            artifact_sha = bytes_sha256(
                read_regular_bytes(bundle, "evidence.json")
            )
        except SafeReadError:
            artifact_sha = None
    definition = target.target if target is not None else None
    return V053OperationResult(
        action=action,
        outcome=outcome,
        exit_code=exit_code,
        code=code,
        reason=reason,
        batch_id=batch_id,
        item_id=item_id,
        role=definition.role if definition is not None else None,
        owner=definition.owner if definition is not None else None,
        qualified=(
            None
            if target is None or outcome == "fatal"
            else outcome != "not_qualified"
        ),
        verdict=str(evidence["verdict"]) if evidence is not None else None,
        coverage=dict(evidence["coverage"]) if evidence is not None else None,
        evidence_semantic_sha256=(
            str(evidence["evidence_semantic_identity"]["sha256"])
            if evidence is not None
            else None
        ),
        evidence_artifact_sha256=artifact_sha,
        evidence_path=str(evidence_path.resolve()) if artifact_sha else None,
        bundle_path=(
            str(bundle.resolve())
            if bundle is not None and (bundle.exists() or bundle.is_symlink())
            else None
        ),
        producer_commit=target.producer_commit if target is not None else None,
        repository_head=(
            _git_head(target.repository_root) if target is not None else None
        ),
        l3a_summary=target.l3a_summary if target is not None else None,
        claim_limitations=(
            definition.claim_limitations if definition is not None else ()
        ),
        warnings=tuple(warnings),
    )


def _bind(
    root: str | Path,
    *,
    action: str,
    batch_id: str,
    item_id: str,
    target_set_id: str,
) -> BoundV053Target | V053OperationResult:
    try:
        return bind_batch_item(
            root,
            batch_id=batch_id,
            item_id=item_id,
            target_set_id=target_set_id,
        )
    except TargetSetError as error:
        return _result(
            action=action,
            outcome="not_target",
            exit_code=2,
            code="v053_target_not_allowlisted",
            reason=str(error),
            batch_id=batch_id,
            item_id=item_id,
        )
    except V053BindingError as error:
        return _result(
            action=action,
            outcome="fatal",
            exit_code=1,
            code=error.code,
            reason=str(error),
            batch_id=batch_id,
            item_id=item_id,
        )
    except Exception as error:
        return _result(
            action=action,
            outcome="fatal",
            exit_code=1,
            code="formal_binding_failed",
            reason=str(error),
            batch_id=batch_id,
            item_id=item_id,
        )


def _reconstruct(
    target: BoundV053Target,
    *,
    action: str,
) -> Any | V053OperationResult:
    try:
        return reconstruct_bound_target(target)
    except AdapterError as error:
        if error.qualification:
            owner = target.target.owner
            suffix = f"; owner={owner}" if owner else ""
            return _result(
                action=action,
                outcome="not_qualified",
                exit_code=2,
                code=error.code,
                reason=f"{error}{suffix}",
                batch_id=target.target_batch_id,
                item_id=target.target.item_id,
                target=target,
            )
        return _result(
            action=action,
            outcome="fatal",
            exit_code=1,
            code=error.code,
            reason=(
                "Formal scope derivation cannot complete without guessing: "
                f"{error}"
            ),
            batch_id=target.target_batch_id,
            item_id=target.target.item_id,
            target=target,
        )


def _verify_current(
    target: BoundV053Target,
    reconstruction: Any,
) -> tuple[dict[str, Any], tuple[Mapping[str, Any], ...]]:
    bundle = target.canonical_bundle_root
    evidence = verify_bundle(target.repository_root, bundle)
    current_basis = build_basis(target, reconstruction)
    if not evidence_is_current(
        evidence,
        current_basis,
        target.profile_identity,
        target.algorithm_versions,
    ):
        raise V053BundleError(
            "Existing Evidence is stale for the current Batch binding/profile/algorithms"
        )
    replay = verify_reconstruction(target, reconstruction)
    if (
        evidence["evidence_semantic_identity"]
        != replay.evidence["evidence_semantic_identity"]
    ):
        raise V053BundleError(
            "Existing Evidence differs from deterministic replay for the same binding"
        )
    return evidence, tuple(replay.projection_warnings)


def _prepare_bundle_parent(target: BoundV053Target) -> None:
    canonical = target.canonical_bundle_root
    try:
        relative_parent = canonical.parent.relative_to(target.run_dir)
    except ValueError as error:
        raise V053BundleError("Canonical bundle path escapes the Batch") from error
    cursor = target.run_dir
    for part in relative_parent.parts:
        cursor = cursor / part
        if not cursor.exists() and not cursor.is_symlink():
            cursor.mkdir()
        metadata = cursor.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise V053BundleError(
                f"Canonical bundle parent is not a regular directory: {cursor}"
            )


def verify_target(
    repository_root: str | Path,
    *,
    batch_id: str,
    item_id: str,
    target_set_id: str = DEFAULT_TARGET_SET_ID,
) -> V053OperationResult:
    bound = _bind(
        repository_root,
        action="verify",
        batch_id=batch_id,
        item_id=item_id,
        target_set_id=target_set_id,
    )
    if isinstance(bound, V053OperationResult):
        return bound
    reconstruction = _reconstruct(bound, action="verify")
    if isinstance(reconstruction, V053OperationResult):
        return reconstruction
    bundle = bound.canonical_bundle_root
    if not bundle.exists() and not bundle.is_symlink():
        return _result(
            action="verify",
            outcome="fatal",
            exit_code=1,
            code="canonical_bundle_missing",
            reason=f"Canonical Evidence bundle does not exist: {bundle}",
            batch_id=batch_id,
            item_id=item_id,
            target=bound,
        )
    try:
        evidence, warnings = _verify_current(bound, reconstruction)
    except Exception as error:
        return _result(
            action="verify",
            outcome="stale_or_corrupt",
            exit_code=1,
            code="canonical_bundle_stale_or_corrupt",
            reason=str(error),
            batch_id=batch_id,
            item_id=item_id,
            target=bound,
        )
    return _result(
        action="verify",
        outcome=str(evidence["verdict"]),
        exit_code=0 if evidence["verdict"] == "passed" else 2,
        code="canonical_bundle_verified",
        reason="Canonical Evidence bundle is complete, current, and hash-valid",
        batch_id=batch_id,
        item_id=item_id,
        target=bound,
        evidence=evidence,
        warnings=warnings,
    )


def record_target(
    repository_root: str | Path,
    *,
    batch_id: str,
    item_id: str,
    require_clean_repository: bool = True,
    target_set_id: str = DEFAULT_TARGET_SET_ID,
) -> V053OperationResult:
    bound = _bind(
        repository_root,
        action="record",
        batch_id=batch_id,
        item_id=item_id,
        target_set_id=target_set_id,
    )
    if isinstance(bound, V053OperationResult):
        return bound
    reconstruction = _reconstruct(bound, action="record")
    if isinstance(reconstruction, V053OperationResult):
        return reconstruction
    bundle = bound.canonical_bundle_root
    if bundle.exists() or bundle.is_symlink():
        try:
            before = bundle_inventory(bundle)
            evidence, warnings = _verify_current(bound, reconstruction)
            after = bundle_inventory(bundle)
            if before != after:
                raise V053BundleError(
                    "Read-only verification changed the target bundle"
                )
        except Exception as error:
            return _result(
                action="record",
                outcome="stale_or_corrupt",
                exit_code=1,
                code="canonical_bundle_stale_or_corrupt",
                reason=str(error),
                batch_id=batch_id,
                item_id=item_id,
                target=bound,
            )
        return _result(
            action="record",
            outcome="existing-current/read-only",
            exit_code=0 if evidence["verdict"] == "passed" else 2,
            code="existing_current_bundle_verified",
            reason="Existing canonical bundle verified read-only; no bytes rewritten",
            batch_id=batch_id,
            item_id=item_id,
            target=bound,
            evidence=evidence,
            warnings=warnings,
        )

    if require_clean_repository:
        try:
            _require_formal_repository(bound)
        except V053BindingError as error:
            return _result(
                action="record",
                outcome="fatal",
                exit_code=1,
                code=error.code,
                reason=str(error),
                batch_id=batch_id,
                item_id=item_id,
                target=bound,
            )
    try:
        run = verify_reconstruction(bound, reconstruction)
        _prepare_bundle_parent(bound)
        evidence = atomic_promote_bundle(
            bundle,
            repository_root=bound.repository_root,
            run=run,
        )
        verify_bundle(bound.repository_root, bundle)
    except Exception as error:
        return _result(
            action="record",
            outcome="fatal",
            exit_code=1,
            code="formal_record_failed",
            reason=str(error),
            batch_id=batch_id,
            item_id=item_id,
            target=bound,
        )
    return _result(
        action="record",
        outcome=str(evidence["verdict"]),
        exit_code=0 if evidence["verdict"] == "passed" else 2,
        code="canonical_bundle_recorded",
        reason="Canonical Evidence generated, verified, and atomically promoted",
        batch_id=batch_id,
        item_id=item_id,
        target=bound,
        evidence=evidence,
        warnings=run.projection_warnings,
    )


def operate_target_set(
    repository_root: str | Path,
    *,
    action: str,
    batch_id: str,
    require_clean_repository: bool = True,
    target_set_id: str = DEFAULT_TARGET_SET_ID,
) -> V053SetResult:
    if action not in {"record", "verify"}:
        raise ValueError(f"Unsupported target-set action: {action}")
    try:
        targets = load_target_set(repository_root, target_set_id)
    except Exception as error:
        result = _result(
            action=action,
            outcome="fatal",
            exit_code=1,
            code="target_set_invalid",
            reason=str(error),
            batch_id=batch_id,
            item_id="*",
        )
        return V053SetResult(action, batch_id, 1, (result,))
    results = []
    for target in targets:
        if action == "record":
            result = record_target(
                repository_root,
                batch_id=batch_id,
                item_id=target.item_id,
                require_clean_repository=require_clean_repository,
                target_set_id=target_set_id,
            )
        else:
            result = verify_target(
                repository_root,
                batch_id=batch_id,
                item_id=target.item_id,
                target_set_id=target_set_id,
            )
        results.append(result)
    exit_code = (
        1
        if any(result.exit_code == 1 for result in results)
        else 2
        if any(result.exit_code == 2 for result in results)
        else 0
    )
    return V053SetResult(action, batch_id, exit_code, tuple(results))
