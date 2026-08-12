"""Add-only recorder and read-only replay verifier for the v0.5.2 target."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.independent_fidelity.api_management import (
    ApiManagementReconstruction,
    ApiManagementReconstructionError,
    reconstruct_bound_api_management,
)
from src.independent_fidelity.bundle import (
    EvidenceBundleError,
    build_evidence_bundle,
    verify_evidence_bundle,
)
from src.independent_fidelity.contracts import (
    bytes_sha256,
    evidence_is_current,
    with_evidence_semantic_identity,
)
from src.independent_fidelity.formal_target import (
    CANONICAL_BUNDLE_PREFIX,
    TARGET_BATCH_ID,
    TARGET_ITEM_ID,
    BoundFormalTarget,
    FormalBindingError,
    InventoryComparison,
    ProfileQualification,
    ScopeGuardError,
    bind_formal_target,
    compare_add_only_inventories,
    inventory_regular_files,
    qualify_bound_target,
)
from src.independent_fidelity.formal_verifier import (
    FormalVerificationBlocked,
    blocked_verification_run,
    verify_reconstructed_api_management,
)
from src.independent_fidelity.verifier import VerificationRun
from src.independent_fidelity.versions import ALGORITHM_VERSIONS


N_A = "N/A"


@dataclass(frozen=True)
class OperationResult:
    action: str
    outcome: str
    exit_code: int
    code: str
    reason: str
    claim: str | None = None
    profile_id: str | None = None
    verdict: str | None = None
    coverage: Mapping[str, int] | None = None
    evidence_semantic_sha256: str | None = None
    evidence_artifact_sha256: str | None = None
    projection_sha256: str | None = None
    evidence_path: Path | None = None
    review_path: Path | None = None
    repository_head: str | None = None
    l3a_summary: Mapping[str, Any] | None = None
    warnings: tuple[Mapping[str, Any], ...] = ()
    inventory_comparison: InventoryComparison | None = None

    def console_fields(self) -> tuple[tuple[str, str], ...]:
        coverage = (
            json.dumps(
                dict(self.coverage),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            if self.coverage is not None
            else N_A
        )
        l3a_verdict = (
            str(self.l3a_summary.get("verdict"))
            if self.l3a_summary is not None
            else N_A
        )
        warning_details = (
            json.dumps(
                list(self.warnings),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            if self.warnings
            else N_A
        )
        return (
            ("action", self.action),
            ("outcome", self.outcome),
            ("exit", str(self.exit_code)),
            ("code", self.code),
            ("reason", self.reason),
            ("claim", self.claim or N_A),
            ("profile", self.profile_id or N_A),
            ("l3a_verdict", l3a_verdict),
            ("l3b_verdict", self.verdict or N_A),
            ("coverage", coverage),
            (
                "evidence_semantic_sha256",
                self.evidence_semantic_sha256 or N_A,
            ),
            (
                "evidence_artifact_sha256",
                self.evidence_artifact_sha256 or N_A,
            ),
            ("projection_sha256", self.projection_sha256 or N_A),
            (
                "evidence_path",
                str(self.evidence_path.resolve())
                if self.evidence_path is not None
                else N_A,
            ),
            (
                "review_path",
                str(self.review_path.resolve())
                if self.review_path is not None
                else N_A,
            ),
            ("repository_head", self.repository_head or N_A),
            ("configuration_hygiene_warnings", str(len(self.warnings))),
            ("configuration_hygiene_warning_details", warning_details),
        )


def _no_bundle_result(
    *,
    action: str,
    outcome: str,
    exit_code: int,
    code: str,
    reason: str,
    qualification: ProfileQualification | None = None,
    target: BoundFormalTarget | None = None,
    repository_head: str | None = None,
) -> OperationResult:
    return OperationResult(
        action=action,
        outcome=outcome,
        exit_code=exit_code,
        code=code,
        reason=reason,
        claim=(qualification.claim if qualification is not None else None),
        profile_id=(
            str(qualification.profile_identity["id"])
            if qualification is not None
            else None
        ),
        repository_head=repository_head,
        l3a_summary=(target.l3a_summary if target is not None else None),
    )


def _git_head(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _require_clean_repository(root: Path) -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        raise FormalBindingError(
            "git_status_failed",
            f"Unable to prove clean implementation worktree: {status.stderr.strip()}",
        )
    if status.stdout:
        raise FormalBindingError(
            "implementation_worktree_dirty",
            "Formal Evidence generation requires a truly clean worktree",
        )
    head = _git_head(root)
    if head is None:
        raise FormalBindingError(
            "implementation_commit_unavailable",
            "Formal Evidence generation requires a committed implementation HEAD",
        )
    return head


def _bundle_file_set(
    bundle_root: Path,
    evidence: Mapping[str, Any],
) -> set[str]:
    expected = {"evidence.json", "review.html"}
    for state in evidence["states"]:
        for key in ("source", "expected", "payload"):
            path = str(state[key]["path"])
            if not path.endswith(".html.txt"):
                raise EvidenceBundleError(
                    f"Executable-looking raw fragment suffix is forbidden: {path}"
                )
            expected.add(path)
        expected.add(str(state["diff"]["path"]))

    actual: set[str] = set()
    for path in sorted(bundle_root.rglob("*")):
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise EvidenceBundleError(
                f"Evidence bundle contains a symbolic link: {path}"
            )
        if stat.S_ISREG(metadata.st_mode):
            actual.add(path.relative_to(bundle_root).as_posix())
    if actual != expected:
        raise EvidenceBundleError(
            "Evidence bundle closed-world file set differs: "
            f"missing={sorted(expected - actual)!r}, extra={sorted(actual - expected)!r}"
        )
    return actual


def _compute_run(
    target: BoundFormalTarget,
) -> tuple[VerificationRun, ApiManagementReconstruction | None]:
    reconstruction: ApiManagementReconstruction | None = None
    try:
        reconstruction = reconstruct_bound_api_management(target)
        run = verify_reconstructed_api_management(target, reconstruction)
    except ApiManagementReconstructionError as error:
        run = blocked_verification_run(target, error)
    except FormalVerificationBlocked as error:
        run = blocked_verification_run(
            target, error, reconstruction=reconstruction
        )
    return run, reconstruction


def _verify_current_bundle(
    target: BoundFormalTarget,
    bundle_root: Path,
) -> tuple[dict[str, Any], tuple[Mapping[str, Any], ...]]:
    if bundle_root.is_symlink() or not bundle_root.is_dir():
        raise EvidenceBundleError(
            f"Canonical Evidence bundle is not a regular directory: {bundle_root}"
        )
    evidence = verify_evidence_bundle(target.repository_root, bundle_root)
    _bundle_file_set(bundle_root, evidence)
    try:
        fresh_run, _ = _compute_run(target)
    except Exception as error:
        raise EvidenceBundleError(
            f"Cannot replay the current formal binding: {error}"
        ) from error
    current_basis = fresh_run.evidence["reconstruction_basis"]
    if not evidence_is_current(
        evidence,
        current_basis,
        target.profile_identity,
        ALGORITHM_VERSIONS,
    ):
        raise EvidenceBundleError(
            "Existing Evidence is stale for the current formal binding/profile/algorithms"
        )
    fresh_identity = with_evidence_semantic_identity(fresh_run.evidence)[
        "evidence_semantic_identity"
    ]
    if evidence["evidence_semantic_identity"] != fresh_identity:
        raise EvidenceBundleError(
            "Existing Evidence differs from deterministic replay for the same binding"
        )
    return evidence, tuple(fresh_run.projection_warnings)


def _result_from_bundle(
    *,
    action: str,
    outcome: str,
    code: str,
    reason: str,
    target: BoundFormalTarget,
    bundle_root: Path,
    evidence: Mapping[str, Any],
    repository_head: str | None,
    warnings: Sequence[Mapping[str, Any]] = (),
    inventory_comparison: InventoryComparison | None = None,
) -> OperationResult:
    verdict = str(evidence["verdict"])
    return OperationResult(
        action=action,
        outcome=outcome,
        exit_code=0 if verdict == "passed" else 2,
        code=code,
        reason=reason,
        claim=str(evidence["claim"]),
        profile_id=str(evidence["verifier_profile"]["id"]),
        verdict=verdict,
        coverage=dict(evidence["coverage"]),
        evidence_semantic_sha256=str(
            evidence["evidence_semantic_identity"]["sha256"]
        ),
        evidence_artifact_sha256=bytes_sha256(
            (bundle_root / "evidence.json").read_bytes()
        ),
        projection_sha256=str(
            evidence["review_projection_artifact_identity"]["sha256"]
        ),
        evidence_path=(bundle_root / "evidence.json").resolve(),
        review_path=(bundle_root / "review.html").resolve(),
        repository_head=repository_head,
        l3a_summary=target.l3a_summary,
        warnings=tuple(warnings),
        inventory_comparison=inventory_comparison,
    )


def _atomic_build_and_promote(
    target: BoundFormalTarget,
    run: VerificationRun,
    bundle_root: Path,
    *,
    style_variant: str,
) -> dict[str, Any]:
    parent = bundle_root.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{bundle_root.name}.tmp-", dir=parent)
    )
    try:
        evidence = build_evidence_bundle(
            temporary,
            repository_root=target.repository_root,
            run=run,
            l3a_summary=target.l3a_summary,
            style_variant=style_variant,
        )
        verify_evidence_bundle(target.repository_root, temporary)
        _bundle_file_set(temporary, evidence)
        if bundle_root.exists() or bundle_root.is_symlink():
            raise EvidenceBundleError(
                f"Canonical Evidence path appeared during record: {bundle_root}"
            )
        os.rename(temporary, bundle_root)
        return evidence
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def _bind_and_qualify(
    repository_root: str | Path,
    *,
    action: str,
    batch_id: str,
    item_id: str,
) -> tuple[BoundFormalTarget, ProfileQualification] | OperationResult:
    try:
        target = bind_formal_target(
            repository_root, batch_id=batch_id, item_id=item_id
        )
    except ScopeGuardError as error:
        return _no_bundle_result(
            action=action,
            outcome="scope_guard",
            exit_code=2,
            code="v052_target_not_allowlisted",
            reason=str(error),
        )
    except FormalBindingError as error:
        return _no_bundle_result(
            action=action,
            outcome="fatal",
            exit_code=1,
            code=error.code,
            reason=str(error),
        )
    qualification = qualify_bound_target(target)
    if not qualification.qualified:
        return _no_bundle_result(
            action=action,
            outcome="not_qualified",
            exit_code=2,
            code="profile_not_qualified",
            reason=qualification.reason,
            qualification=qualification,
            target=target,
            repository_head=_git_head(target.repository_root),
        )
    return target, qualification


def verify_formal_target(
    repository_root: str | Path,
    *,
    batch_id: str = TARGET_BATCH_ID,
    item_id: str = TARGET_ITEM_ID,
    bundle_root: str | Path | None = None,
) -> OperationResult:
    bound = _bind_and_qualify(
        repository_root,
        action="verify",
        batch_id=batch_id,
        item_id=item_id,
    )
    if isinstance(bound, OperationResult):
        return bound
    target, qualification = bound
    bundle = (
        Path(bundle_root).resolve()
        if bundle_root is not None
        else (target.run_dir / CANONICAL_BUNDLE_PREFIX).resolve()
    )
    if not bundle.exists() and not bundle.is_symlink():
        return _no_bundle_result(
            action="verify",
            outcome="fatal",
            exit_code=1,
            code="canonical_bundle_missing",
            reason=f"Canonical Evidence bundle does not exist: {bundle}",
            qualification=qualification,
            target=target,
            repository_head=_git_head(target.repository_root),
        )
    try:
        evidence, warnings = _verify_current_bundle(target, bundle)
    except (EvidenceBundleError, ApiManagementReconstructionError) as error:
        return _no_bundle_result(
            action="verify",
            outcome="stale_or_corrupt",
            exit_code=1,
            code="canonical_bundle_stale_or_corrupt",
            reason=str(error),
            qualification=qualification,
            target=target,
            repository_head=_git_head(target.repository_root),
        )
    return _result_from_bundle(
        action="verify",
        outcome=str(evidence["verdict"]),
        code="canonical_bundle_verified",
        reason="Canonical Evidence bundle is complete, current, and hash-valid",
        target=target,
        bundle_root=bundle,
        evidence=evidence,
        repository_head=_git_head(target.repository_root),
        warnings=warnings,
    )


def record_formal_target(
    repository_root: str | Path,
    *,
    batch_id: str = TARGET_BATCH_ID,
    item_id: str = TARGET_ITEM_ID,
    bundle_root: str | Path | None = None,
    require_clean_repository: bool = True,
    style_variant: str = "v0.5.2-formal-v1",
) -> OperationResult:
    bound = _bind_and_qualify(
        repository_root,
        action="record",
        batch_id=batch_id,
        item_id=item_id,
    )
    if isinstance(bound, OperationResult):
        return bound
    target, qualification = bound
    bundle = (
        Path(bundle_root).resolve()
        if bundle_root is not None
        else (target.run_dir / CANONICAL_BUNDLE_PREFIX).resolve()
    )
    if bundle.exists() or bundle.is_symlink():
        verified = verify_formal_target(
            repository_root,
            batch_id=batch_id,
            item_id=item_id,
            bundle_root=bundle,
        )
        if verified.exit_code == 1:
            return OperationResult(
                **{
                    **verified.__dict__,
                    "action": "record",
                    "outcome": "stale_or_corrupt",
                }
            )
        return OperationResult(
            **{
                **verified.__dict__,
                "action": "record",
                "outcome": "existing_current",
                "code": "existing_current_bundle_verified",
                "reason": (
                    "Existing canonical bundle verified read-only; no bytes rewritten"
                ),
            }
        )

    try:
        repository_head = (
            _require_clean_repository(target.repository_root)
            if require_clean_repository
            else _git_head(target.repository_root)
        )
    except FormalBindingError as error:
        return _no_bundle_result(
            action="record",
            outcome="fatal",
            exit_code=1,
            code=error.code,
            reason=str(error),
            qualification=qualification,
            target=target,
            repository_head=_git_head(target.repository_root),
        )

    try:
        run, _ = _compute_run(target)
        evidence = _atomic_build_and_promote(
            target,
            run,
            bundle,
            style_variant=style_variant,
        )
    except Exception as error:
        return _no_bundle_result(
            action="record",
            outcome="fatal",
            exit_code=1,
            code="formal_record_failed",
            reason=str(error),
            qualification=qualification,
            target=target,
            repository_head=repository_head,
        )

    inventory_comparison: InventoryComparison | None = None
    try:
        bundle.relative_to(target.run_dir)
    except ValueError:
        pass
    else:
        after = inventory_regular_files(target.run_dir)
        inventory_comparison = compare_add_only_inventories(
            target.pre_record_inventory,
            after,
        )
        if not inventory_comparison.valid:
            return _no_bundle_result(
                action="record",
                outcome="fatal",
                exit_code=1,
                code="batch_add_only_inventory_failed",
                reason=json.dumps(
                    inventory_comparison.to_dict(),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                qualification=qualification,
                target=target,
                repository_head=repository_head,
            )
    return _result_from_bundle(
        action="record",
        outcome=str(evidence["verdict"]),
        code="canonical_bundle_recorded",
        reason="Canonical Evidence bundle generated, verified, and atomically promoted",
        target=target,
        bundle_root=bundle,
        evidence=evidence,
        repository_head=repository_head,
        warnings=run.projection_warnings,
        inventory_comparison=inventory_comparison,
    )
