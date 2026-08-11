"""Closed-world contract validation and minimal historical binding semantics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker


PROFILE_SCHEMA = "schemas/independent-fidelity-profile-1.0.schema.json"
BASIS_SCHEMA = "schemas/independent-fidelity-basis-1.0.schema.json"
EVIDENCE_SCHEMA = "schemas/independent-fidelity-evidence-1.0.schema.json"
SEMANTIC_IDENTITY_ALGORITHM = "sha256-canonical-json-v1"
PROJECTION_IDENTITY_ALGORITHM = "sha256-projection-artifacts-v1"


class ContractError(ValueError):
    """An independent-fidelity contract is invalid or internally inconsistent."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def semantic_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validate(
    root: str | Path,
    schema_path: str,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    root = Path(root).resolve()
    schema = json.loads((root / schema_path).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).iter_errors(value),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        details = "; ".join(
            f"{'/'.join(map(str, error.absolute_path)) or '$'}: {error.message}"
            for error in errors
        )
        raise ContractError(f"{schema_path} validation failed: {details}")
    return dict(value)


def validate_profile(
    root: str | Path, value: Mapping[str, Any]
) -> dict[str, Any]:
    return _validate(root, PROFILE_SCHEMA, value)


def validate_basis(
    root: str | Path, value: Mapping[str, Any]
) -> dict[str, Any]:
    validated = _validate(root, BASIS_SCHEMA, value)
    expected = semantic_sha256(_basis_semantic_object(validated))
    if validated["basis_semantic_identity"]["sha256"] != expected:
        raise ContractError("Reconstruction Basis semantic identity drifted")
    return validated


def _basis_semantic_object(basis: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in basis.items()
        if key != "basis_semantic_identity"
    }


def with_basis_semantic_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    basis = dict(value)
    basis["basis_semantic_identity"] = {
        "algorithm": SEMANTIC_IDENTITY_ALGORITHM,
        "sha256": semantic_sha256(_basis_semantic_object(basis)),
    }
    return basis


def evidence_semantic_object(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return only verdict-bearing evidence semantics.

    Fragment paths and display-only diff artifacts are intentionally omitted;
    their content identities are represented by Source/Expected/Payload hashes,
    while report and diff rendering belong to the projection identity.
    """

    states = []
    for state in value["states"]:
        states.append(
            {
                "state_id": state["state_id"],
                "criteria": state["criteria"],
                "locator": state["locator"],
                "verdict": state["verdict"],
                "source_sha256": state["source"]["sha256"],
                "expected_sha256": state["expected"]["sha256"],
                "payload_sha256": state["payload"]["sha256"],
                "applied_transform_rule_ids": state[
                    "applied_transform_rule_ids"
                ],
                "retained_table_ids": state["retained_table_ids"],
                "removed_table_ids": state["removed_table_ids"],
                "mismatches": state["mismatches"],
                "blocking_errors": state["blocking_errors"],
            }
        )
    return {
        "schema_version": value["schema_version"],
        "claim": value["claim"],
        "verdict": value["verdict"],
        "coverage": value["coverage"],
        "identity": value["identity"],
        "reconstruction_basis": value["reconstruction_basis"],
        "verifier_profile": value["verifier_profile"],
        "reconstruction_profile_version": value[
            "reconstruction_profile_version"
        ],
        "wire_transform_version": value["wire_transform_version"],
        "comparison_version": value["comparison_version"],
        "states": states,
        "mismatches": value["mismatches"],
        "blocking_errors": value["blocking_errors"],
    }


def with_evidence_semantic_identity(
    value: Mapping[str, Any]
) -> dict[str, Any]:
    evidence = dict(value)
    evidence["evidence_semantic_identity"] = {
        "algorithm": SEMANTIC_IDENTITY_ALGORITHM,
        "sha256": semantic_sha256(evidence_semantic_object(evidence)),
    }
    return evidence


def validate_evidence(
    root: str | Path, value: Mapping[str, Any]
) -> dict[str, Any]:
    validated = _validate(root, EVIDENCE_SCHEMA, value)
    validate_basis(root, validated["reconstruction_basis"])
    expected = semantic_sha256(evidence_semantic_object(validated))
    if validated["evidence_semantic_identity"]["sha256"] != expected:
        raise ContractError("Independent Fidelity Evidence semantic identity drifted")
    basis = validated["reconstruction_basis"]
    if validated["identity"]["batch_id"] != basis["batch_binding"]["batch_id"]:
        raise ContractError("Evidence Batch identity differs from Reconstruction Basis")
    for key in ("item_id", "language", "resource_key", "product_key"):
        if validated["identity"][key] != basis["item_identity"][key]:
            raise ContractError(
                f"Evidence {key} differs from Reconstruction Basis"
            )
    if validated["verifier_profile"] != basis["verifier_profile"]:
        raise ContractError("Evidence verifier profile differs from Reconstruction Basis")
    for key in (
        "reconstruction_profile_version",
        "wire_transform_version",
        "comparison_version",
    ):
        if validated[key] != basis[key]:
            raise ContractError(f"Evidence {key} differs from Reconstruction Basis")

    states = validated["states"]
    basis_states = basis["states"]
    if len(states) != len(basis_states):
        raise ContractError("Evidence state count differs from Reconstruction Basis")
    for state, basis_state in zip(states, basis_states, strict=True):
        for key in (
            "state_id",
            "criteria",
            "locator",
            "retained_table_ids",
            "removed_table_ids",
        ):
            if state[key] != basis_state[key]:
                raise ContractError(
                    f"Evidence state {key} differs from Reconstruction Basis"
                )
        if state["verdict"] == "passed" and (
            state["mismatches"] or state["blocking_errors"]
        ):
            raise ContractError("passed state cannot contain failures")
        if state["verdict"] == "failed" and not state["mismatches"]:
            raise ContractError("failed state must contain a mismatch")
        if state["verdict"] == "blocked" and not state["blocking_errors"]:
            raise ContractError("blocked state must contain a blocking error")

    scope_verdicts = [state["verdict"] for state in states]
    counts = {
        "required": len(states),
        "completed": sum(value != "blocked" for value in scope_verdicts),
        "passed": scope_verdicts.count("passed"),
        "failed": scope_verdicts.count("failed"),
        "blocked": scope_verdicts.count("blocked"),
    }
    if validated["coverage"] != counts:
        raise ContractError("Evidence coverage does not match per-state verdicts")
    expected_verdict = (
        "failed"
        if "failed" in scope_verdicts
        else "blocked"
        if "blocked" in scope_verdicts
        else "passed"
    )
    if validated["verdict"] != expected_verdict:
        raise ContractError("Evidence item verdict does not match per-state verdicts")
    if validated["mismatches"] != [
        mismatch for state in states for mismatch in state["mismatches"]
    ]:
        raise ContractError("Evidence aggregate mismatches differ from state evidence")
    if validated["blocking_errors"] != [
        error for state in states for error in state["blocking_errors"]
    ]:
        raise ContractError("Evidence aggregate blocking errors differ from state evidence")
    projection = validated["review_projection_artifact_identity"]
    if projection["sha256"] != semantic_sha256(projection["artifacts"]):
        raise ContractError("Review projection artifact identity drifted")
    if validated["verdict"] == "passed":
        if validated["mismatches"] or validated["blocking_errors"]:
            raise ContractError("passed evidence cannot contain failures")
    return validated


def evidence_is_current(
    evidence: Mapping[str, Any],
    current_basis: Mapping[str, Any],
    current_profile_identity: Mapping[str, Any],
    current_algorithm_versions: Mapping[str, str],
) -> bool:
    """Old evidence stays historical but is current only for exact semantics."""

    return (
        evidence["reconstruction_basis"]["basis_semantic_identity"]
        == current_basis["basis_semantic_identity"]
        and evidence["verifier_profile"]
        == current_profile_identity
        and evidence["reconstruction_profile_version"]
        == current_algorithm_versions["reconstruction_profile_version"]
        and evidence["wire_transform_version"]
        == current_algorithm_versions["wire_transform_version"]
        and evidence["comparison_version"]
        == current_algorithm_versions["comparison_version"]
    )
