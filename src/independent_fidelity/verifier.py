"""Small independent reconstruction/comparison path for v0.5.1 fixtures.

This is deliberately not a production Batch verifier. It proves the frozen
contract, algorithm identities, counterexamples, and evidence projection before
the first formal ``api-management`` consumer in v0.5.2.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from bs4 import BeautifulSoup, NavigableString, Tag

from src.independent_fidelity.contracts import bytes_sha256
from src.independent_fidelity.verdict import aggregate_item_verdict
from src.independent_fidelity.versions import ALGORITHM_VERSIONS


CSS_GENERATED_SEMANTICS_RULE = "css-generated-semantics-v1"


class IndependentVerificationError(ValueError):
    """A controlled independent reconstruction cannot finish without guessing."""


@dataclass(frozen=True)
class VerificationRun:
    """Evidence semantics plus physical fragments awaiting bundle projection."""

    evidence: dict[str, Any]
    fragments: dict[str, str]


def apply_wire_transforms(
    source_html: str,
    rule_ids: tuple[str, ...] | list[str],
) -> tuple[str, list[str]]:
    """Apply independently implemented, explicitly declared wire rules only."""

    unknown = [rule_id for rule_id in rule_ids if rule_id != CSS_GENERATED_SEMANTICS_RULE]
    if unknown:
        raise IndependentVerificationError(
            f"Unsupported independent wire transform rule(s): {unknown}"
        )
    if CSS_GENERATED_SEMANTICS_RULE not in rule_ids:
        return source_html, []

    soup = BeautifulSoup(source_html, "html.parser")
    transformed = 0
    for icon in list(soup.select("i.icon-tick")):
        if icon.get_text(strip=True):
            continue
        icon.replace_with(NavigableString("✓"))
        transformed += 1
    applied = [CSS_GENERATED_SEMANTICS_RULE] if transformed else []
    return str(soup), applied


def reconstruct_state(source_html: str, locator: Mapping[str, Any]) -> str:
    """Reconstruct one fixture state using only frozen selectors and source DOM."""

    soup = BeautifulSoup(source_html, "html.parser")
    containers = soup.select(str(locator["container_selector"]))
    if len(containers) != 1 or not isinstance(containers[0], Tag):
        raise IndependentVerificationError(
            "State locator must resolve exactly one source container"
        )
    container = containers[0]
    selected: list[Tag] = []
    seen: set[int] = set()
    for selector in locator["content_selectors"]:
        matches = container.select(str(selector))
        if not matches:
            raise IndependentVerificationError(
                f"Content selector resolved no source node: {selector}"
            )
        for match in matches:
            marker = id(match)
            if marker not in seen:
                selected.append(match)
                seen.add(marker)
    for selector in locator["append_selectors"]:
        matches = soup.select(str(selector))
        if not matches:
            raise IndependentVerificationError(
                f"Append selector resolved no source node: {selector}"
            )
        for match in matches:
            marker = id(match)
            if marker not in seen:
                selected.append(match)
                seen.add(marker)
    return "".join(str(node) for node in selected)


def _dom(value: str) -> str:
    return str(BeautifulSoup(value, "html.parser"))


def _tag_structure(value: str) -> list[dict[str, Any]]:
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


def compare_html(expected: str, payload: str) -> list[dict[str, str]]:
    """Compare exact wire bytes plus DOM, tag structure, and visible text."""

    dimensions = (
        ("raw", expected, payload),
        ("dom", _dom(expected), _dom(payload)),
        (
            "tag_structure",
            repr(_tag_structure(expected)),
            repr(_tag_structure(payload)),
        ),
        ("visible_text", _visible_text(expected), _visible_text(payload)),
    )
    mismatches = []
    for dimension, expected_value, actual_value in dimensions:
        if expected_value == actual_value:
            continue
        mismatches.append(
            {
                "code": "content_mismatch",
                "dimension": dimension,
                "expected_sha256": bytes_sha256(expected_value.encode("utf-8")),
                "actual_sha256": bytes_sha256(actual_value.encode("utf-8")),
                "message": f"{dimension} comparison differs",
            }
        )
    return mismatches


def verify_fixture_states(
    *,
    source_html: str,
    payload_by_state: Mapping[str, str],
    basis: Mapping[str, Any],
    profile_identity: Mapping[str, str],
    transform_rules_by_state: Mapping[str, list[str]] | None = None,
) -> VerificationRun:
    """Run the minimal L3b path and return bundle-ready evidence semantics."""

    transform_rules_by_state = transform_rules_by_state or {}
    source_sha256 = bytes_sha256(source_html.encode("utf-8"))
    payload_sha256 = bytes_sha256(
        json.dumps(
            dict(payload_by_state),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    binding_error: str | None = None
    if source_sha256 != basis["source_identity"]["sha256"]:
        binding_error = "Frozen source identity does not match verifier input"
    elif payload_sha256 != basis["persisted_payload_identity"]["sha256"]:
        binding_error = "Persisted payload identity does not match verifier input"
    elif dict(profile_identity) != basis["verifier_profile"]:
        binding_error = "Verifier profile identity differs from Reconstruction Basis"
    elif any(basis[key] != value for key, value in ALGORITHM_VERSIONS.items()):
        binding_error = "Algorithm identity differs from Reconstruction Basis"
    state_evidence: list[dict[str, Any]] = []
    fragments: dict[str, str] = {}
    aggregate_mismatches: list[dict[str, str]] = []
    aggregate_errors: list[dict[str, str]] = []
    scope_verdicts: list[str] = []

    for index, state in enumerate(basis["states"], start=1):
        state_id = state["state_id"]
        prefix = f"state-{index:03d}"
        source_fragment = ""
        expected_fragment = ""
        payload_fragment = str(payload_by_state.get(state_id, ""))
        mismatches: list[dict[str, str]] = []
        blocking_errors: list[dict[str, str]] = []
        applied_rules: list[str] = []
        try:
            if binding_error is not None:
                raise IndependentVerificationError(binding_error)
            source_fragment = reconstruct_state(source_html, state["locator"])
            expected_fragment, applied_rules = apply_wire_transforms(
                source_fragment,
                transform_rules_by_state.get(state_id, []),
            )
            if state_id not in payload_by_state:
                raise IndependentVerificationError(
                    f"Persisted payload has no state: {state_id}"
                )
            mismatches = compare_html(expected_fragment, payload_fragment)
            verdict = "failed" if mismatches else "passed"
        except IndependentVerificationError as error:
            verdict = "blocked"
            blocking_errors = [
                {
                    "code": "independent_reconstruction_blocked",
                    "message": str(error),
                }
            ]
        scope_verdicts.append(verdict)
        aggregate_mismatches.extend(mismatches)
        aggregate_errors.extend(blocking_errors)
        source_path = f"fragments/{prefix}.source.html"
        expected_path = f"fragments/{prefix}.expected.html"
        payload_path = f"fragments/{prefix}.payload.html"
        diff_path = f"fragments/{prefix}.diff.html"
        fragments[source_path] = source_fragment
        fragments[expected_path] = expected_fragment
        fragments[payload_path] = payload_fragment
        state_evidence.append(
            {
                "state_id": state_id,
                "criteria": list(state["criteria"]),
                "locator": dict(state["locator"]),
                "verdict": verdict,
                "source": {
                    "path": source_path,
                    "sha256": bytes_sha256(source_fragment.encode("utf-8")),
                },
                "expected": {
                    "path": expected_path,
                    "sha256": bytes_sha256(expected_fragment.encode("utf-8")),
                },
                "payload": {
                    "path": payload_path,
                    "sha256": bytes_sha256(payload_fragment.encode("utf-8")),
                },
                "diff": {"path": diff_path},
                "applied_transform_rule_ids": applied_rules,
                "retained_table_ids": list(state["retained_table_ids"]),
                "removed_table_ids": list(state["removed_table_ids"]),
                "mismatches": mismatches,
                "blocking_errors": blocking_errors,
            }
        )

    verdict = aggregate_item_verdict(
        qualified=True,
        started=True,
        required_scope_verdicts=scope_verdicts,
    )
    passed = scope_verdicts.count("passed")
    failed = scope_verdicts.count("failed")
    blocked = scope_verdicts.count("blocked")
    evidence = {
        "schema_version": "1.0",
        "claim": "independent_source_content_fidelity",
        "verdict": verdict,
        "coverage": {
            "required": len(scope_verdicts),
            "completed": passed + failed,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
        },
        "identity": {
            "batch_id": basis["batch_binding"]["batch_id"],
            "item_id": basis["item_identity"]["item_id"],
            "language": basis["item_identity"]["language"],
            "resource_key": basis["item_identity"]["resource_key"],
            "product_key": basis["item_identity"]["product_key"],
        },
        "reconstruction_basis": dict(basis),
        "verifier_profile": dict(profile_identity),
        **ALGORITHM_VERSIONS,
        "states": state_evidence,
        "mismatches": aggregate_mismatches,
        "blocking_errors": aggregate_errors,
        "qualification_limitation": None,
        "blocked_reason": (
            aggregate_errors[0]["message"] if aggregate_errors else None
        ),
    }
    return VerificationRun(evidence=evidence, fragments=fragments)
