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
PROFILE_SCHEMAS = {
    "1.0": PROFILE_SCHEMA,
    "1.1": "schemas/independent-fidelity-profile-1.1.schema.json",
    "1.2": "schemas/independent-fidelity-profile-1.2.schema.json",
}
BASIS_SCHEMAS = {
    "1.0": BASIS_SCHEMA,
    "1.1": "schemas/independent-fidelity-basis-1.1.schema.json",
    "1.2": "schemas/independent-fidelity-basis-1.2.schema.json",
}
EVIDENCE_SCHEMAS = {
    "1.0": EVIDENCE_SCHEMA,
    "1.1": "schemas/independent-fidelity-evidence-1.1.schema.json",
    "1.2": "schemas/independent-fidelity-evidence-1.2.schema.json",
}
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


def _versioned_schema(
    value: Mapping[str, Any],
    schemas: Mapping[str, str],
    *,
    contract: str,
) -> str:
    version = value.get("schema_version")
    if not isinstance(version, str) or version not in schemas:
        raise ContractError(
            f"Unsupported {contract} schema_version: {version!r}"
        )
    return schemas[version]


def validate_profile(
    root: str | Path, value: Mapping[str, Any]
) -> dict[str, Any]:
    return _validate(
        root,
        _versioned_schema(value, PROFILE_SCHEMAS, contract="Profile"),
        value,
    )


def validate_basis(
    root: str | Path, value: Mapping[str, Any]
) -> dict[str, Any]:
    validated = _validate(
        root,
        _versioned_schema(
            value, BASIS_SCHEMAS, contract="Reconstruction Basis"
        ),
        value,
    )
    expected = semantic_sha256(_basis_semantic_object(validated))
    if validated["basis_semantic_identity"]["sha256"] != expected:
        raise ContractError("Reconstruction Basis semantic identity drifted")
    if validated["schema_version"] in {"1.1", "1.2"}:
        _validate_basis_v11_semantics(validated)
    return validated


def _validate_basis_v11_semantics(basis: Mapping[str, Any]) -> None:
    family = basis["item_identity"]["page_family"]
    soft_category = basis["soft_category_identity"]
    route_map = basis["route_map_basis"]
    if family in {"region_filter", "complex"}:
        if soft_category is None or route_map is not None:
            raise ContractError(
                f"{family} requires soft-category and forbids route-map basis"
            )
    elif family == "support_article":
        if soft_category is not None or route_map is None:
            raise ContractError(
                "support_article requires route-map basis and forbids soft-category"
            )
    elif soft_category is not None or route_map is not None:
        raise ContractError(
            "simple_static forbids soft-category and route-map basis"
        )

    scopes = basis["scopes"]
    scope_keys = [scope["scope_key"] for scope in scopes]
    if len(scope_keys) != len(set(scope_keys)):
        raise ContractError("Reconstruction Basis scope keys must be unique")
    scope_kinds = [scope["scope_kind"] for scope in scopes]
    if family == "region_filter" and set(scope_kinds) != {"interactive"}:
        raise ContractError("region_filter requires only interactive scopes")
    if family == "complex" and (
        "interactive" not in scope_kinds
        or any(kind not in {"interactive", "page_global"} for kind in scope_kinds)
        or scope_kinds.count("page_global") > 1
    ):
        raise ContractError(
            "complex requires interactive scopes and at most one page_global scope"
        )
    if family in {"simple_static", "support_article"} and scope_kinds != [
        "full_content"
    ]:
        raise ContractError(f"{family} requires exactly one full_content scope")
    for scope in scopes:
        kind = scope["scope_kind"]
        key = scope["scope_key"]
        criteria = scope["criteria"]
        payload_locator = scope["payload_locator"]
        retained = set(scope["retained_table_ids"])
        removed = set(scope["removed_table_ids"])
        if retained.intersection(removed):
            raise ContractError(
                f"Scope {key!r} retains and removes the same table ID"
            )
        criterion_keys = [value["filterKey"] for value in criteria]
        if len(criterion_keys) != len(set(criterion_keys)):
            raise ContractError(f"Scope {key!r} repeats a filterKey")
        if kind == "interactive":
            expected_key = "interactive:" + "|".join(
                f"{value['filterKey']}={value['matchValues']}"
                for value in criteria
            )
            if key != expected_key or not criteria:
                raise ContractError(
                    "interactive scope requires a readable key and criteria"
                )
            if payload_locator != "contentGroups[].content":
                raise ContractError(
                    "interactive scope must bind contentGroups[].content"
                )
            if scope["expected_group_name"] is None:
                raise ContractError(
                    "interactive scope requires its Source-derived group name"
                )
            if scope["source_locator"]["kind"] != "selector":
                raise ContractError(
                    "interactive scope requires a selector Source locator"
                )
        elif kind == "page_global":
            if key != "page_global" or criteria:
                raise ContractError(
                    "page_global scope must use its exact key and no criteria"
                )
            if payload_locator != "baseContent":
                raise ContractError("page_global scope must bind baseContent")
            if (
                scope["expected_group_name"] is not None
                or scope["source_locator"]["kind"]
                != "post_selector_siblings"
            ):
                raise ContractError(
                    "page_global scope has an invalid group name or Source locator"
                )
        else:
            if key != "full_content" or criteria:
                raise ContractError(
                    "full_content scope must use its exact key and no criteria"
                )
            expected_locator = (
                "mainContent" if family == "support_article" else "baseContent"
            )
            if payload_locator != expected_locator:
                raise ContractError(
                    f"{family} full_content must bind {expected_locator}"
                )
            expected_kind = (
                "support_main_content"
                if family == "support_article"
                else "selector"
            )
            if (
                scope["expected_group_name"] is not None
                or scope["source_locator"]["kind"] != expected_kind
            ):
                raise ContractError(
                    f"{family} full_content has an invalid group name or Source locator"
                )

    if route_map is not None:
        routes = [entry["source_route"] for entry in route_map["entries"]]
        if len(routes) != len(set(routes)):
            raise ContractError("Route-map basis repeats a Source route")


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

    if value.get("schema_version") in {"1.1", "1.2"}:
        return _evidence_semantic_object_v11(value)

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


def _evidence_semantic_object_v11(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    scopes = []
    for scope in value["scopes"]:
        scopes.append(
            {
                "scope_key": scope["scope_key"],
                "scope_kind": scope["scope_kind"],
                "criteria": scope["criteria"],
                "source_locator": scope["source_locator"],
                "payload_locator": scope["payload_locator"],
                "expected_group_name": scope["expected_group_name"],
                "verdict": scope["verdict"],
                "source_sha256": scope["source"]["sha256"],
                "expected_sha256": scope["expected"]["sha256"],
                "payload_sha256": scope["payload"]["sha256"],
                "applied_transform_rule_ids": scope[
                    "applied_transform_rule_ids"
                ],
                "retained_table_ids": scope["retained_table_ids"],
                "removed_table_ids": scope["removed_table_ids"],
                "mismatches": scope["mismatches"],
                "blocking_errors": scope["blocking_errors"],
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
        "scopes": scopes,
        "mismatches": value["mismatches"],
        "blocking_errors": value["blocking_errors"],
        "claim_limitations": value["claim_limitations"],
        "blocked_reason": value["blocked_reason"],
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
    validated = _validate(
        root,
        _versioned_schema(
            value, EVIDENCE_SCHEMAS, contract="Independent Fidelity Evidence"
        ),
        value,
    )
    if validated["schema_version"] in {"1.1", "1.2"}:
        return _validate_evidence_v11(root, validated)
    return _validate_evidence_v10(root, validated)


def _validate_evidence_v10(
    root: str | Path, validated: dict[str, Any]
) -> dict[str, Any]:
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


def _validate_evidence_v11(
    root: str | Path, validated: dict[str, Any]
) -> dict[str, Any]:
    basis = validate_basis(root, validated["reconstruction_basis"])
    if basis["schema_version"] != validated["schema_version"]:
        raise ContractError(
            "Evidence and Reconstruction Basis schema versions must match"
        )
    expected = semantic_sha256(evidence_semantic_object(validated))
    if validated["evidence_semantic_identity"]["sha256"] != expected:
        raise ContractError("Independent Fidelity Evidence semantic identity drifted")
    if validated["identity"]["batch_id"] != basis["batch_binding"]["batch_id"]:
        raise ContractError("Evidence Batch identity differs from Reconstruction Basis")
    for key in (
        "item_id",
        "language",
        "resource_key",
        "product_key",
        "page_family",
    ):
        if validated["identity"][key] != basis["item_identity"][key]:
            raise ContractError(
                f"Evidence {key} differs from Reconstruction Basis"
            )
    if validated["verifier_profile"] != basis["verifier_profile"]:
        raise ContractError(
            "Evidence verifier profile differs from Reconstruction Basis"
        )
    for key in (
        "reconstruction_profile_version",
        "wire_transform_version",
        "comparison_version",
    ):
        if validated[key] != basis[key]:
            raise ContractError(f"Evidence {key} differs from Reconstruction Basis")

    scopes = validated["scopes"]
    basis_scopes = basis["scopes"]
    if len(scopes) != len(basis_scopes):
        raise ContractError("Evidence scope count differs from Reconstruction Basis")
    basis_fields = (
        "scope_key",
        "scope_kind",
        "criteria",
        "source_locator",
        "payload_locator",
        "expected_group_name",
        "retained_table_ids",
        "removed_table_ids",
    )
    for scope, basis_scope in zip(scopes, basis_scopes, strict=True):
        for key in basis_fields:
            if scope[key] != basis_scope[key]:
                raise ContractError(
                    f"Evidence scope {key} differs from Reconstruction Basis"
                )
        if scope["verdict"] == "passed" and (
            scope["mismatches"] or scope["blocking_errors"]
        ):
            raise ContractError("passed scope cannot contain failures")
        if scope["verdict"] == "failed" and not scope["mismatches"]:
            raise ContractError("failed scope must contain a mismatch")
        if scope["verdict"] == "failed" and scope["blocking_errors"]:
            raise ContractError("failed scope cannot contain a blocking error")
        if scope["verdict"] == "blocked" and not scope["blocking_errors"]:
            raise ContractError("blocked scope must contain a blocking error")
        if scope["verdict"] == "blocked" and scope["mismatches"]:
            raise ContractError("blocked scope cannot contain a mismatch")

    scope_verdicts = [scope["verdict"] for scope in scopes]
    counts = {
        "required": len(scopes),
        "completed": sum(verdict != "blocked" for verdict in scope_verdicts),
        "passed": scope_verdicts.count("passed"),
        "failed": scope_verdicts.count("failed"),
        "blocked": scope_verdicts.count("blocked"),
    }
    if validated["coverage"] != counts:
        raise ContractError("Evidence coverage does not match per-scope verdicts")
    expected_verdict = (
        "failed"
        if "failed" in scope_verdicts
        else "blocked"
        if "blocked" in scope_verdicts
        else "passed"
    )
    if validated["verdict"] != expected_verdict:
        raise ContractError("Evidence item verdict does not match per-scope verdicts")
    if validated["mismatches"] != [
        mismatch for scope in scopes for mismatch in scope["mismatches"]
    ]:
        raise ContractError("Evidence aggregate mismatches differ from scope evidence")
    if validated["blocking_errors"] != [
        error for scope in scopes for error in scope["blocking_errors"]
    ]:
        raise ContractError(
            "Evidence aggregate blocking errors differ from scope evidence"
        )
    expected_blocked_reason = (
        validated["blocking_errors"][0]["message"]
        if validated["blocking_errors"]
        else None
    )
    if validated["blocked_reason"] != expected_blocked_reason:
        raise ContractError("Evidence blocked_reason differs from scope evidence")
    if validated["verdict"] == "passed" and (
        validated["mismatches"] or validated["blocking_errors"]
    ):
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
