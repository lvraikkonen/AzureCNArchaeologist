"""Four-family Basis construction and direct L3b content comparison."""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from bs4 import BeautifulSoup, Tag

from src.independent_fidelity.contracts import (
    bytes_sha256,
    canonical_json,
    validate_basis,
    validate_evidence,
    with_basis_semantic_identity,
    with_evidence_semantic_identity,
)
from src.independent_fidelity.v053_adapters import (
    Reconstruction,
    ScopeReconstruction,
    reconstruct_page_family,
)
from src.independent_fidelity.v053_io import SafeReadError, strict_json_bytes
from src.independent_fidelity.v053_target import BoundV053Target
from src.independent_fidelity.verifier import VerificationRun


class V053VerificationBlocked(ValueError):
    """A trusted Basis exists, but one payload scope cannot be assigned."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _PayloadScope:
    fragment: str
    actual_assignment: Mapping[str, Any] | None = None
    blocking_errors: tuple[Mapping[str, str], ...] = ()


def reconstruct_bound_target(target: BoundV053Target) -> Reconstruction:
    return reconstruct_page_family(
        page_family=target.target.page_family,
        source_html=target.source_html,
        product_definition=target.product_definition,
        language=target.target.language,
        soft_category=target.soft_category,
        reconstruction_profile_version=(
            target.target_set.reconstruction_profile_version
        ),
    )


def build_basis(
    target: BoundV053Target,
    reconstruction: Reconstruction,
) -> dict[str, Any]:
    basis = {
        "schema_version": target.contract_schema_version,
        "basis_id": (
            f"v{target.target_set.profile_version}-{target.target_batch_id}-"
            f"{target.target.item_id.replace('/', '-')}-basis"
        ),
        "batch_binding": {
            "batch_id": target.target_batch_id,
            "input_manifest": target.input_manifest_identity.as_dict(),
            "batch_manifest": {
                **target.batch_manifest_identity.as_dict(),
                "revision": target.batch_revision,
            },
            "producer_commit": target.producer_commit,
        },
        "item_identity": {
            "item_id": target.target.item_id,
            "language": target.target.language,
            "resource_key": target.target.resource_key,
            "product_key": str(target.batch_item["product_key"]),
            "resource_kind": str(target.batch_item["resource"]["kind"]),
            "page_family": target.target.page_family,
        },
        "source_identity": target.source_identity.as_dict(),
        "product_definition_identity": (
            target.product_definition_identity.as_dict()
        ),
        "soft_category_identity": (
            target.soft_category_identity.as_dict()
            if target.soft_category_identity is not None
            else None
        ),
        "route_map_basis": (
            dict(reconstruction.route_map_basis)
            if reconstruction.route_map_basis is not None
            else None
        ),
        "persisted_payload_identity": {
            **target.payload_identity.as_dict(),
            "batch_revision": target.batch_revision,
        },
        "verifier_profile": dict(target.profile_identity),
        **target.algorithm_versions,
        "scopes": [scope.basis_dict() for scope in reconstruction.scopes],
    }
    return validate_basis(
        target.repository_root, with_basis_semantic_identity(basis)
    )


def _criteria_key(
    value: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (str(criterion["filterKey"]), str(criterion["matchValues"]))
        for criterion in value
    )


def _parse_group_criteria(value: Any, *, index: int) -> list[Mapping[str, str]]:
    if not isinstance(value, str):
        raise V053VerificationBlocked(
            "payload_scope_identity_invalid",
            f"contentGroups[{index}] filterCriteriaJson must be a string",
        )
    try:
        parsed = strict_json_bytes(
            value.encode("utf-8"),
            description=f"contentGroups[{index}].filterCriteriaJson",
            expected_type=list,
        )
    except SafeReadError as error:
        raise V053VerificationBlocked(
            "payload_scope_identity_invalid", str(error)
        ) from error
    if not parsed:
        raise V053VerificationBlocked(
            "payload_scope_identity_invalid",
            f"contentGroups[{index}] criteria cannot be empty",
        )
    criteria: list[Mapping[str, str]] = []
    for criterion in parsed:
        if (
            not isinstance(criterion, Mapping)
            or set(criterion) != {"filterKey", "matchValues"}
            or not isinstance(criterion.get("filterKey"), str)
            or not criterion["filterKey"]
            or not isinstance(criterion.get("matchValues"), str)
            or not criterion["matchValues"]
        ):
            raise V053VerificationBlocked(
                "payload_scope_identity_invalid",
                f"contentGroups[{index}] has a non-canonical criterion",
            )
        criteria.append(
            {
                "filterKey": criterion["filterKey"],
                "matchValues": criterion["matchValues"],
            }
        )
    keys = [criterion["filterKey"] for criterion in criteria]
    if len(keys) != len(set(keys)):
        raise V053VerificationBlocked(
            "payload_scope_identity_invalid",
            f"contentGroups[{index}] repeats a filterKey",
        )
    return criteria


def _error(code: str, message: str) -> Mapping[str, str]:
    return {"code": code, "message": message}


def _interactive_payload_scopes(
    reconstruction: Reconstruction,
    payload: Mapping[str, Any],
) -> Mapping[str, _PayloadScope]:
    expected = [
        scope for scope in reconstruction.scopes if scope.scope_kind == "interactive"
    ]
    expected_by_key = {
        _criteria_key(scope.criteria): scope for scope in expected
    }
    groups = payload.get("contentGroups")
    if not isinstance(groups, list):
        error = _error(
            "payload_scope_domain_invalid",
            "Persisted payload contentGroups must be an array",
        )
        return {
            scope.scope_key: _PayloadScope("", blocking_errors=(error,))
            for scope in expected
        }

    observed: dict[tuple[tuple[str, str], ...], list[Mapping[str, Any]]] = {}
    global_errors: list[Mapping[str, str]] = []
    for index, group in enumerate(groups):
        if not isinstance(group, Mapping):
            global_errors.append(
                _error(
                    "payload_scope_identity_invalid",
                    f"contentGroups[{index}] must be an object",
                )
            )
            continue
        try:
            criteria = _parse_group_criteria(
                group.get("filterCriteriaJson"), index=index
            )
        except V053VerificationBlocked as error:
            global_errors.append(_error(error.code, str(error)))
            continue
        key = _criteria_key(criteria)
        if key not in expected_by_key:
            global_errors.append(
                _error(
                    "payload_scope_domain_mismatch",
                    f"contentGroups[{index}] criteria are outside the Source domain: "
                    f"{criteria!r}",
                )
            )
            continue
        observed.setdefault(key, []).append(
            {"index": index, "group": group, "criteria": criteria}
        )

    results: dict[str, _PayloadScope] = {}
    for expected_index, scope in enumerate(expected):
        key = _criteria_key(scope.criteria)
        matches = observed.get(key, [])
        errors = list(global_errors)
        if not matches:
            errors.append(
                _error(
                    "payload_scope_missing",
                    f"Persisted payload has no scope {scope.scope_key!r}",
                )
            )
            results[scope.scope_key] = _PayloadScope(
                "", blocking_errors=tuple(errors)
            )
            continue
        if len(matches) != 1:
            errors.append(
                _error(
                    "payload_scope_identity_ambiguous",
                    f"Persisted payload repeats scope {scope.scope_key!r}",
                )
            )
            results[scope.scope_key] = _PayloadScope(
                "", blocking_errors=tuple(errors)
            )
            continue
        match = matches[0]
        group = match["group"]
        fragment = group.get("content")
        if not isinstance(fragment, str):
            errors.append(
                _error(
                    "payload_scope_content_invalid",
                    f"Persisted content for {scope.scope_key!r} must be a string",
                )
            )
            fragment = ""
        results[scope.scope_key] = _PayloadScope(
            fragment,
            actual_assignment={
                "criteria": list(match["criteria"]),
                "group_name": group.get("groupName"),
                "position": int(match["index"]) + 1,
                "sort_order": group.get("sortOrder"),
            },
            blocking_errors=tuple(errors),
        )
    return results


def _payload_scopes(
    reconstruction: Reconstruction,
    payload: Mapping[str, Any],
) -> Mapping[str, _PayloadScope]:
    result = dict(_interactive_payload_scopes(reconstruction, payload))
    for scope in reconstruction.scopes:
        if scope.scope_kind == "interactive":
            continue
        field = (
            "baseContent"
            if scope.payload_locator == "baseContent"
            else "mainContent"
        )
        fragment = payload.get(field)
        if not isinstance(fragment, str):
            result[scope.scope_key] = _PayloadScope(
                "",
                blocking_errors=(
                    _error(
                        "payload_scope_content_invalid",
                        f"Persisted payload {field} must be a string",
                    ),
                ),
            )
        else:
            result[scope.scope_key] = _PayloadScope(fragment)
    return result


def _normalized_attribute(value: Any) -> Any:
    if isinstance(value, list):
        return [str(item) for item in value]
    return str(value)


def _business_semantics(value: str) -> Mapping[str, Any]:
    soup = BeautifulSoup(value, "html.parser")
    nodes = []
    for tag in soup.find_all(True):
        attributes = {
            str(key): _normalized_attribute(tag.attrs[key])
            for key in sorted(tag.attrs)
        }
        nodes.append({"tag": tag.name, "attributes": attributes})
    tables = []
    for table in soup.find_all("table"):
        rows = []
        for row in table.find_all("tr"):
            rows.append(
                [
                    cell.get_text(" ", strip=True)
                    for cell in row.find_all(["th", "td"])
                ]
            )
        tables.append({"id": table.get("id"), "rows": rows})
    links_and_media = []
    for tag in soup.find_all(["a", "img", "source"]):
        links_and_media.append(
            {
                "tag": tag.name,
                "href": tag.get("href"),
                "src": tag.get("src"),
                "srcset": tag.get("srcset"),
                "text": tag.get_text(" ", strip=True),
            }
        )
    return {
        "nodes": nodes,
        "tables": tables,
        "links_and_media": links_and_media,
    }


def _tag_structure(value: str) -> Sequence[Mapping[str, Any]]:
    soup = BeautifulSoup(value, "html.parser")
    return [
        {
            "name": tag.name,
            "attributes": sorted(str(key) for key in tag.attrs),
        }
        for tag in soup.find_all(True)
    ]


def _visible_text(value: str) -> str:
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)


def _mismatch(
    dimension: str,
    expected: Any,
    actual: Any,
    message: str,
) -> Mapping[str, str]:
    expected_value = expected if isinstance(expected, str) else canonical_json(expected)
    actual_value = actual if isinstance(actual, str) else canonical_json(actual)
    return {
        "code": "content_mismatch",
        "dimension": dimension,
        "expected_sha256": bytes_sha256(expected_value.encode("utf-8")),
        "actual_sha256": bytes_sha256(actual_value.encode("utf-8")),
        "message": message,
    }


def compare_content(expected: str, actual: str) -> list[Mapping[str, str]]:
    """Compare direct bytes, DOM, order, text, and business attributes."""

    dimensions: Sequence[tuple[str, Any, Any]] = (
        ("raw", expected, actual),
        (
            "dom",
            str(BeautifulSoup(expected, "html.parser")),
            str(BeautifulSoup(actual, "html.parser")),
        ),
        ("tag_structure", _tag_structure(expected), _tag_structure(actual)),
        ("visible_text", _visible_text(expected), _visible_text(actual)),
        (
            "business_semantics",
            _business_semantics(expected),
            _business_semantics(actual),
        ),
    )
    mismatches: list[Mapping[str, str]] = []
    for dimension, expected_value, actual_value in dimensions:
        if expected_value == actual_value:
            continue
        mismatches.append(
            _mismatch(
                dimension,
                expected_value,
                actual_value,
                f"{dimension} comparison differs",
            )
        )
    return mismatches


def _table_ids(value: str) -> list[str | None]:
    return [
        str(table["id"]) if table.has_attr("id") else None
        for table in BeautifulSoup(value, "html.parser").find_all("table")
    ]


def _readable_diff(expected: str, actual: str) -> str:
    def lines(value: str) -> list[str]:
        expanded = re.sub(r">(?=<)", ">\n", value)
        return [line + "\n" for line in expanded.splitlines()]

    return "".join(
        difflib.unified_diff(
            lines(expected),
            lines(actual),
            fromfile="expected",
            tofile="payload",
            lineterm="\n",
        )
    )


def _scope_evidence(
    scope: ScopeReconstruction,
    payload: _PayloadScope,
    *,
    index: int,
    expected_position: int | None,
) -> tuple[Mapping[str, Any], Mapping[str, str]]:
    prefix = f"scope-{index:03d}"
    source_path = f"fragments/{prefix}.source.html.txt"
    expected_path = f"fragments/{prefix}.expected.html.txt"
    payload_path = f"fragments/{prefix}.payload.html.txt"
    diff_path = f"fragments/{prefix}.diff.txt"
    mismatches: list[Mapping[str, str]] = []
    blocking_errors = list(payload.blocking_errors)
    if not blocking_errors:
        mismatches.extend(
            compare_content(scope.expected_fragment, payload.fragment)
        )
        actual_tables = _table_ids(payload.fragment)
        expected_tables = list(scope.retained_table_ids)
        if (
            scope.retained_table_ids or scope.removed_table_ids
        ) and actual_tables != expected_tables:
            mismatches.append(
                _mismatch(
                    "table_ownership",
                    expected_tables,
                    actual_tables,
                    "Persisted table ownership/order differs from Source projection",
                )
            )
        if expected_position is not None:
            expected_assignment = {
                "criteria": [dict(value) for value in scope.criteria],
                "group_name": scope.expected_group_name,
                "position": expected_position,
                "sort_order": expected_position,
            }
            actual_assignment = dict(payload.actual_assignment or {})
            if actual_assignment != expected_assignment:
                mismatches.append(
                    _mismatch(
                        "state_assignment",
                        expected_assignment,
                        actual_assignment,
                        "Persisted state identity, label, or order differs from Source authority",
                    )
                )
    verdict = "blocked" if blocking_errors else "failed" if mismatches else "passed"
    diff_content = _readable_diff(scope.expected_fragment, payload.fragment)
    fragments = {
        source_path: scope.source_fragment,
        expected_path: scope.expected_fragment,
        payload_path: payload.fragment,
        diff_path: diff_content,
    }
    return (
        {
            **scope.basis_dict(),
            "verdict": verdict,
            "source": {
                "path": source_path,
                "sha256": bytes_sha256(scope.source_fragment.encode("utf-8")),
            },
            "expected": {
                "path": expected_path,
                "sha256": bytes_sha256(scope.expected_fragment.encode("utf-8")),
            },
            "payload": {
                "path": payload_path,
                "sha256": bytes_sha256(payload.fragment.encode("utf-8")),
            },
            "diff": {
                "path": diff_path,
                "sha256": bytes_sha256(diff_content.encode("utf-8")),
            },
            "applied_transform_rule_ids": list(
                scope.applied_transform_rule_ids
            ),
            "mismatches": mismatches,
            "blocking_errors": blocking_errors,
        },
        fragments,
    )


def verify_reconstruction(
    target: BoundV053Target,
    reconstruction: Reconstruction,
    *,
    payload: Mapping[str, Any] | None = None,
) -> VerificationRun:
    selected_payload = payload if payload is not None else target.payload
    basis = build_basis(target, reconstruction)
    payload_scopes = _payload_scopes(reconstruction, selected_payload)
    scope_evidence: list[Mapping[str, Any]] = []
    fragments: dict[str, str] = {}
    interactive_position = 0
    for index, scope in enumerate(reconstruction.scopes, start=1):
        expected_position: int | None = None
        if scope.scope_kind == "interactive":
            interactive_position += 1
            expected_position = interactive_position
        evidence, scope_fragments = _scope_evidence(
            scope,
            payload_scopes[scope.scope_key],
            index=index,
            expected_position=expected_position,
        )
        scope_evidence.append(evidence)
        fragments.update(scope_fragments)
    verdicts = [str(scope["verdict"]) for scope in scope_evidence]
    verdict = (
        "failed"
        if "failed" in verdicts
        else "blocked"
        if "blocked" in verdicts
        else "passed"
    )
    mismatches = [
        mismatch
        for scope in scope_evidence
        for mismatch in scope["mismatches"]
    ]
    blocking_errors = [
        error
        for scope in scope_evidence
        for error in scope["blocking_errors"]
    ]
    evidence = {
        "schema_version": target.contract_schema_version,
        "claim": "independent_source_content_fidelity",
        "verdict": verdict,
        "coverage": {
            "required": len(verdicts),
            "completed": sum(value != "blocked" for value in verdicts),
            "passed": verdicts.count("passed"),
            "failed": verdicts.count("failed"),
            "blocked": verdicts.count("blocked"),
        },
        "identity": {
            "batch_id": target.target_batch_id,
            "item_id": target.target.item_id,
            "language": target.target.language,
            "resource_key": target.target.resource_key,
            "product_key": str(target.batch_item["product_key"]),
            "page_family": target.target.page_family,
        },
        "reconstruction_basis": basis,
        "verifier_profile": dict(target.profile_identity),
        **target.algorithm_versions,
        "scopes": scope_evidence,
        "mismatches": mismatches,
        "blocking_errors": blocking_errors,
        "claim_limitations": list(target.target.claim_limitations),
        "blocked_reason": (
            blocking_errors[0]["message"] if blocking_errors else None
        ),
    }
    validated = validate_evidence(
        target.repository_root, with_evidence_semantic_identity(evidence)
    )
    return VerificationRun(
        evidence=validated,
        fragments=fragments,
        projection_warnings=tuple(reconstruction.warnings),
    )


def verify_bound_target(target: BoundV053Target) -> VerificationRun:
    return verify_reconstruction(target, reconstruct_bound_target(target))
