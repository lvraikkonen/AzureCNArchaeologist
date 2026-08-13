"""Read-only Workbench view over canonical v0.5.3 Evidence bundles."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from src.independent_fidelity.contracts import bytes_sha256
from src.independent_fidelity.targets import (
    TargetMembershipAmbiguousError,
    TargetSetError,
    resolve_registered_target,
)
from src.independent_fidelity.v053_bundle import V053BundleError, verify_bundle
from src.independent_fidelity.v053_io import (
    SafeReadError,
    read_regular_bytes,
    safe_relative_path,
)
from src.independent_fidelity.v053_target import (
    V053BindingError,
    bind_batch_item,
)


_DISPLAY_STATUSES = frozenset(
    {"passed", "failed", "blocked", "not_recorded", "invalid"}
)


def _empty_view(
    *,
    batch_id: str,
    item_id: str,
    status: str,
    reason: str,
    claim_limitations: Sequence[str] = (),
) -> dict[str, Any]:
    if status not in _DISPLAY_STATUSES:
        raise AssertionError(f"Unsupported Workbench L3b status: {status}")
    return {
        "schema_version": "1.0",
        "batch_id": batch_id,
        "item_id": item_id,
        "status": status,
        "evidence_identity": None,
        "l3b": {
            "claim": "independent_source_content_fidelity",
            "verdict": status,
            "coverage": None,
            "reason": reason,
            "claim_limitations": list(claim_limitations),
        },
        "scopes": [],
    }


def _bundle_root(
    run_dir: Path,
    payload_artifact: Mapping[str, Any],
) -> Path:
    raw_path = payload_artifact.get("path")
    if not isinstance(raw_path, str):
        raise V053BundleError("Batch item has no canonical payload path")
    try:
        payload_path = safe_relative_path(raw_path)
    except SafeReadError as error:
        raise V053BundleError(str(error)) from error
    try:
        relative = payload_path.relative_to("outputs")
    except ValueError as error:
        raise V053BundleError(
            f"Payload path is outside the canonical outputs root: {payload_path}"
        ) from error
    if payload_path.suffix != ".json" or len(relative.parts) < 3:
        raise V053BundleError(
            f"Payload path cannot identify a canonical Evidence bundle: {payload_path}"
        )
    return run_dir / "independent-fidelity" / relative.with_suffix("")


def _assert_current_binding(evidence: Mapping[str, Any], bound: Any) -> None:
    basis = evidence["reconstruction_basis"]
    expected_batch = {
        "batch_id": bound.target_batch_id,
        "input_manifest": bound.input_manifest_identity.as_dict(),
        "batch_manifest": {
            **bound.batch_manifest_identity.as_dict(),
            "revision": bound.batch_revision,
        },
        "producer_commit": bound.producer_commit,
    }
    expected_item = {
        "item_id": bound.target.item_id,
        "language": bound.target.language,
        "resource_key": bound.target.resource_key,
        "product_key": str(bound.batch_item["product_key"]),
        "resource_kind": str(bound.batch_item["resource"]["kind"]),
        "page_family": bound.target.page_family,
    }
    expected_payload = {
        **bound.payload_identity.as_dict(),
        "batch_revision": bound.batch_revision,
    }
    expected_soft_category = (
        bound.soft_category_identity.as_dict()
        if bound.soft_category_identity is not None
        else None
    )
    comparisons = {
        "Batch": (basis["batch_binding"], expected_batch),
        "item": (basis["item_identity"], expected_item),
        "Source": (basis["source_identity"], bound.source_identity.as_dict()),
        "Product Definition": (
            basis["product_definition_identity"],
            bound.product_definition_identity.as_dict(),
        ),
        "soft-category": (
            basis["soft_category_identity"],
            expected_soft_category,
        ),
        "payload": (basis["persisted_payload_identity"], expected_payload),
        "Profile": (basis["verifier_profile"], bound.profile_identity),
    }
    drifted = [
        label for label, (actual, expected) in comparisons.items() if actual != expected
    ]
    if drifted:
        raise V053BundleError(
            "Canonical Evidence is stale for current binding(s): "
            + ", ".join(drifted)
        )
    for key, expected in bound.algorithm_versions.items():
        if evidence.get(key) != expected or basis.get(key) != expected:
            raise V053BundleError(
                f"Canonical Evidence uses a stale {key} identity"
            )
    if evidence["claim_limitations"] != list(bound.target.claim_limitations):
        raise V053BundleError(
            "Canonical Evidence claim_limitations differ from the target set"
        )


def _read_text(bundle_root: Path, reference: Mapping[str, Any]) -> str:
    try:
        return read_regular_bytes(bundle_root, reference["path"]).decode("utf-8")
    except (KeyError, SafeReadError, UnicodeDecodeError) as error:
        raise V053BundleError(f"Cannot read Evidence display fragment: {error}") from error


def _scope_reason(scope: Mapping[str, Any]) -> str:
    if scope["verdict"] == "passed":
        return "All required direct content comparisons matched."
    issues = [
        f"{value.get('dimension', value['code'])}: {value['message']}"
        for value in [*scope["mismatches"], *scope["blocking_errors"]]
    ]
    return "; ".join(issues)


def _evidence_reason(evidence: Mapping[str, Any]) -> str:
    verdict = evidence["verdict"]
    coverage = evidence["coverage"]
    if verdict == "passed":
        return "All required scopes passed direct comparison."
    if verdict == "blocked":
        return evidence.get("blocked_reason") or (
            f"Canonical Evidence contains {coverage['blocked']} blocked scope(s)."
        )
    return (
        f"Canonical Evidence contains {coverage['failed']} failed scope(s)"
        f" and {coverage['blocked']} blocked scope(s)."
    )


def build_independent_fidelity_view(
    repository_root: str | Path,
    *,
    run_dir: str | Path,
    batch_id: str,
    item_id: str,
    payload_artifact: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a transient escaped-text view without replay or lifecycle writes."""

    root = Path(repository_root).resolve()
    current_run = Path(run_dir).resolve()
    try:
        registration, target = resolve_registered_target(root, item_id)
    except TargetMembershipAmbiguousError as error:
        return _empty_view(
            batch_id=batch_id,
            item_id=item_id,
            status="invalid",
            reason=str(error),
        )
    except TargetSetError as error:
        return _empty_view(
            batch_id=batch_id,
            item_id=item_id,
            status="not_recorded",
            reason=str(error),
        )

    try:
        bundle_root = _bundle_root(current_run, payload_artifact)
    except V053BundleError as error:
        return _empty_view(
            batch_id=batch_id,
            item_id=item_id,
            status="invalid",
            reason=str(error),
            claim_limitations=target.claim_limitations,
        )
    if not bundle_root.exists() and not bundle_root.is_symlink():
        return _empty_view(
            batch_id=batch_id,
            item_id=item_id,
            status="not_recorded",
            reason="No canonical Independent Fidelity Evidence bundle is recorded for this item.",
            claim_limitations=target.claim_limitations,
        )

    try:
        bound = bind_batch_item(
            root,
            batch_id=batch_id,
            item_id=item_id,
            target_set_id=registration.target_set_id,
        )
        if bound.run_dir != current_run or bound.canonical_bundle_root != bundle_root:
            raise V053BundleError(
                "Workbench Batch path differs from the canonical Evidence binding"
            )
        evidence = verify_bundle(root, bundle_root)
        _assert_current_binding(evidence, bound)
        scopes = []
        for scope in evidence["scopes"]:
            scopes.append(
                {
                    "scope_key": scope["scope_key"],
                    "scope_kind": scope["scope_kind"],
                    "criteria": scope["criteria"],
                    "source_locator": scope["source_locator"],
                    "payload_locator": scope["payload_locator"],
                    "expected_group_name": scope["expected_group_name"],
                    "verdict": scope["verdict"],
                    "source": _read_text(bundle_root, scope["source"]),
                    "expected": _read_text(bundle_root, scope["expected"]),
                    "payload": _read_text(bundle_root, scope["payload"]),
                    "diff": _read_text(bundle_root, scope["diff"]),
                    "applied_transform_rule_ids": scope[
                        "applied_transform_rule_ids"
                    ],
                    "retained_table_ids": scope["retained_table_ids"],
                    "removed_table_ids": scope["removed_table_ids"],
                    "mismatches": scope["mismatches"],
                    "blocking_errors": scope["blocking_errors"],
                    "reason": _scope_reason(scope),
                }
            )
        evidence_bytes = read_regular_bytes(bundle_root, "evidence.json")
        evidence_path = (bundle_root / "evidence.json").relative_to(root)
        return {
            "schema_version": "1.0",
            "batch_id": batch_id,
            "item_id": item_id,
            "status": evidence["verdict"],
            "evidence_identity": {
                "basis_id": evidence["reconstruction_basis"]["basis_id"],
                "path": evidence_path.as_posix(),
                "artifact_sha256": bytes_sha256(evidence_bytes),
                "semantic_sha256": evidence["evidence_semantic_identity"][
                    "sha256"
                ],
                "producer_commit": evidence["reconstruction_basis"][
                    "batch_binding"
                ]["producer_commit"],
            },
            "l3b": {
                "claim": evidence["claim"],
                "verdict": evidence["verdict"],
                "coverage": evidence["coverage"],
                "reason": _evidence_reason(evidence),
                "claim_limitations": evidence["claim_limitations"],
            },
            "scopes": scopes,
        }
    except (
        KeyError,
        V053BindingError,
        V053BundleError,
        OSError,
        ValueError,
    ) as error:
        return _empty_view(
            batch_id=batch_id,
            item_id=item_id,
            status="invalid",
            reason=str(error),
            claim_limitations=target.claim_limitations,
        )


__all__ = ["build_independent_fidelity_view"]
