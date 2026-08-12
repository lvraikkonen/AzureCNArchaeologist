"""Formal v0.5.2 wire materialization, alignment, and L3b comparison."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence

from bs4 import BeautifulSoup

from src.independent_fidelity.api_management import (
    ApiManagementReconstruction,
    EXPECTED_REMOVED_TABLE_IDS,
    EXPECTED_RETAINED_TABLE_IDS,
    LOCATOR,
    ReconstructedState,
    derive_state_id,
    reconstruct_bound_api_management,
)
from src.independent_fidelity.contracts import (
    bytes_sha256,
    validate_basis,
    with_basis_semantic_identity,
)
from src.independent_fidelity.formal_target import (
    BATCH_MANIFEST_PATH,
    FROZEN_SHA256,
    INPUT_MANIFEST_PATH,
    PAYLOAD_PATH,
    PRODUCT_DEFINITION_PATH,
    PROFILE_PATH,
    SOFT_CATEGORY_PATH,
    SOURCE_PATH,
    TARGET_BATCH_ID,
    TARGET_BATCH_REVISION,
    TARGET_ITEM_ID,
    TARGET_LANGUAGE,
    TARGET_PRODUCT_KEY,
    TARGET_RESOURCE_KEY,
    BoundFormalTarget,
    EXPECTED_REGIONS,
    EXPECTED_STATE_IDS,
)
from src.independent_fidelity.verdict import aggregate_item_verdict
from src.independent_fidelity.verifier import VerificationRun, compare_html
from src.independent_fidelity.versions import ALGORITHM_VERSIONS


class FormalVerificationBlocked(ValueError):
    """State identity or formal materialization is insufficient to compare."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class _DuplicateJsonKey(ValueError):
    pass


def _blocked(code: str, message: str) -> FormalVerificationBlocked:
    return FormalVerificationBlocked(code, message)


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


def materialize_cms_wire(projected_html: str) -> tuple[str, list[str]]:
    """Apply independent-cms-wire-v1 for this frozen formal page.

    The formal fragments contain none of the declared content-affecting inputs,
    so ``applied_transform_rule_ids`` is empty.  Basic parse/serialize already
    happened during reconstruction; deterministic whitespace compaction remains
    part of the wire algorithm rather than a named content rule.
    """

    soup = BeautifulSoup(projected_html, "html.parser")
    unsupported_inputs: list[str] = []
    if soup.select("i.icon-tick"):
        unsupported_inputs.append("icon-tick")
    if soup.select('img[src^="/"]'):
        unsupported_inputs.append("root-relative-image")
    if soup.select("[data-config]"):
        unsupported_inputs.append("data-config-asset")
    if any("url(" in str(tag.get("style", "")).lower() for tag in soup.find_all(True)):
        unsupported_inputs.append("style-url")
    if unsupported_inputs:
        raise _blocked(
            "unexpected_wire_transform_input",
            "Formal api-management fragment unexpectedly requires content rules: "
            f"{unsupported_inputs!r}",
        )
    value = re.sub(r"\n+", " ", projected_html)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"<div>\s*</div>", "", value)
    value = re.sub(r">\s+<", "><", value)
    return value.strip(), []


def align_payload_content_groups(
    reconstruction: ApiManagementReconstruction,
    payload: Mapping[str, Any],
) -> dict[str, str]:
    """Align persisted groups by a unique Region identity, never by index."""

    groups = payload.get("contentGroups")
    if not isinstance(groups, list) or len(groups) != len(reconstruction.states):
        raise _blocked(
            "payload_state_domain_mismatch",
            "Persisted payload must contain exactly five contentGroups",
        )
    by_state_id: dict[str, str] = {}
    observed_order: list[str] = []
    source_by_state_id = {state.state_id: state for state in reconstruction.states}
    for index, group in enumerate(groups):
        if not isinstance(group, Mapping):
            raise _blocked(
                "payload_state_identity_invalid",
                f"contentGroups[{index}] must be an object",
            )
        raw_criteria = group.get("filterCriteriaJson")
        if not isinstance(raw_criteria, str):
            raise _blocked(
                "payload_state_identity_invalid",
                f"contentGroups[{index}] filterCriteriaJson must be a string",
            )
        try:
            criteria = json.loads(raw_criteria, object_pairs_hook=_object_pairs)
        except (json.JSONDecodeError, _DuplicateJsonKey) as error:
            raise _blocked(
                "payload_state_identity_invalid",
                f"contentGroups[{index}] has invalid criteria JSON: {error}",
            ) from error
        if (
            not isinstance(criteria, list)
            or len(criteria) != 1
            or not isinstance(criteria[0], Mapping)
            or set(criteria[0]) != {"filterKey", "matchValues"}
            or criteria[0].get("filterKey") != "region"
            or not isinstance(criteria[0].get("matchValues"), str)
            or not criteria[0]["matchValues"]
        ):
            raise _blocked(
                "payload_state_identity_invalid",
                f"contentGroups[{index}] must have one exact Region criterion",
            )
        region = str(criteria[0]["matchValues"])
        state_id = derive_state_id(region)
        state = source_by_state_id.get(state_id)
        if state is None or state.region != region:
            raise _blocked(
                "payload_state_domain_mismatch",
                f"contentGroups[{index}] Region {region!r} is outside Source domain",
            )
        if state_id in by_state_id:
            raise _blocked(
                "payload_state_identity_ambiguous",
                f"Persisted payload repeats Region state {region!r}",
            )
        if group.get("groupName") != state.label:
            raise _blocked(
                "payload_state_label_mismatch",
                f"Persisted groupName for Region {region!r} differs from desktop label",
            )
        content = group.get("content")
        if not isinstance(content, str):
            raise _blocked(
                "payload_state_content_invalid",
                f"Persisted content for Region {region!r} must be a string",
            )
        by_state_id[state_id] = content
        observed_order.append(state_id)
    expected_order = [state.state_id for state in reconstruction.states]
    if observed_order != expected_order or set(by_state_id) != set(expected_order):
        raise _blocked(
            "payload_state_order_mismatch",
            "Persisted payload Region order/domain differs from Source default-first order",
        )
    return by_state_id


def build_api_management_basis(
    target: BoundFormalTarget,
    reconstruction: ApiManagementReconstruction,
) -> dict[str, Any]:
    """Build the existing closed-world Reconstruction Basis 1.0 contract."""

    basis = {
        "schema_version": "1.0",
        "basis_id": "v0.5.2-zh-cn-api-management-formal-basis",
        "batch_binding": {
            "batch_id": TARGET_BATCH_ID,
            "input_manifest": {
                "path": INPUT_MANIFEST_PATH.as_posix(),
                "sha256": FROZEN_SHA256[INPUT_MANIFEST_PATH.as_posix()],
            },
            "batch_manifest": {
                "path": BATCH_MANIFEST_PATH.as_posix(),
                "sha256": FROZEN_SHA256[BATCH_MANIFEST_PATH.as_posix()],
                "revision": TARGET_BATCH_REVISION,
            },
        },
        "item_identity": {
            "item_id": TARGET_ITEM_ID,
            "language": TARGET_LANGUAGE,
            "resource_key": TARGET_RESOURCE_KEY,
            "product_key": TARGET_PRODUCT_KEY,
            "resource_kind": "current",
        },
        "source_identity": {
            "path": SOURCE_PATH.as_posix(),
            "sha256": FROZEN_SHA256[SOURCE_PATH.as_posix()],
        },
        "product_definition_identity": {
            "path": PRODUCT_DEFINITION_PATH.as_posix(),
            "sha256": FROZEN_SHA256[PRODUCT_DEFINITION_PATH.as_posix()],
        },
        "soft_category_identity": {
            "path": SOFT_CATEGORY_PATH.as_posix(),
            "sha256": FROZEN_SHA256[SOFT_CATEGORY_PATH.as_posix()],
        },
        "route_map_identity": None,
        "persisted_payload_identity": {
            "path": PAYLOAD_PATH.as_posix(),
            "sha256": FROZEN_SHA256[PAYLOAD_PATH.as_posix()],
            "batch_revision": TARGET_BATCH_REVISION,
        },
        "verifier_profile": {
            "id": target.profile_identity["id"],
            "version": target.profile_identity["version"],
            "path": PROFILE_PATH.as_posix(),
            "sha256": FROZEN_SHA256[PROFILE_PATH.as_posix()],
        },
        **ALGORITHM_VERSIONS,
        "states": [
            {
                "state_id": state.state_id,
                "criteria": [dict(criterion) for criterion in state.criteria],
                "locator": {
                    "container_selector": state.locator["container_selector"],
                    "content_selectors": list(
                        state.locator["content_selectors"]
                    ),
                    "append_selectors": list(state.locator["append_selectors"]),
                },
                "retained_table_ids": list(state.retained_table_ids),
                "removed_table_ids": list(state.removed_table_ids),
            }
            for state in reconstruction.states
        ],
    }
    return validate_basis(
        target.repository_root, with_basis_semantic_identity(basis)
    )


def _blocked_basis(target: BoundFormalTarget) -> dict[str, Any]:
    """Use the trusted L3a/frozen required set when reconstruction blocks."""

    synthetic_states = []
    for state_id, region in zip(EXPECTED_STATE_IDS, EXPECTED_REGIONS, strict=True):
        synthetic_states.append(
            {
                "state_id": state_id,
                "criteria": [
                    {"filterKey": "region", "matchValues": region}
                ],
                "locator": {
                    "container_selector": LOCATOR["container_selector"],
                    "content_selectors": list(LOCATOR["content_selectors"]),
                    "append_selectors": list(LOCATOR["append_selectors"]),
                },
                "retained_table_ids": list(
                    EXPECTED_RETAINED_TABLE_IDS[region]
                ),
                "removed_table_ids": list(
                    EXPECTED_REMOVED_TABLE_IDS[region]
                ),
            }
        )
    basis = {
        "schema_version": "1.0",
        "basis_id": "v0.5.2-zh-cn-api-management-formal-basis",
        "batch_binding": {
            "batch_id": TARGET_BATCH_ID,
            "input_manifest": {
                "path": INPUT_MANIFEST_PATH.as_posix(),
                "sha256": FROZEN_SHA256[INPUT_MANIFEST_PATH.as_posix()],
            },
            "batch_manifest": {
                "path": BATCH_MANIFEST_PATH.as_posix(),
                "sha256": FROZEN_SHA256[BATCH_MANIFEST_PATH.as_posix()],
                "revision": TARGET_BATCH_REVISION,
            },
        },
        "item_identity": {
            "item_id": TARGET_ITEM_ID,
            "language": TARGET_LANGUAGE,
            "resource_key": TARGET_RESOURCE_KEY,
            "product_key": TARGET_PRODUCT_KEY,
            "resource_kind": "current",
        },
        "source_identity": {
            "path": SOURCE_PATH.as_posix(),
            "sha256": FROZEN_SHA256[SOURCE_PATH.as_posix()],
        },
        "product_definition_identity": {
            "path": PRODUCT_DEFINITION_PATH.as_posix(),
            "sha256": FROZEN_SHA256[PRODUCT_DEFINITION_PATH.as_posix()],
        },
        "soft_category_identity": {
            "path": SOFT_CATEGORY_PATH.as_posix(),
            "sha256": FROZEN_SHA256[SOFT_CATEGORY_PATH.as_posix()],
        },
        "route_map_identity": None,
        "persisted_payload_identity": {
            "path": PAYLOAD_PATH.as_posix(),
            "sha256": FROZEN_SHA256[PAYLOAD_PATH.as_posix()],
            "batch_revision": TARGET_BATCH_REVISION,
        },
        "verifier_profile": dict(target.profile_identity),
        **ALGORITHM_VERSIONS,
        "states": synthetic_states,
    }
    return validate_basis(
        target.repository_root, with_basis_semantic_identity(basis)
    )


def blocked_verification_run(
    target: BoundFormalTarget,
    error: Exception,
    *,
    reconstruction: ApiManagementReconstruction | None = None,
) -> VerificationRun:
    """Express a trustworthy post-binding inability as immutable Evidence."""

    code = str(getattr(error, "code", "independent_reconstruction_blocked"))
    message = str(error)
    basis = (
        build_api_management_basis(target, reconstruction)
        if reconstruction is not None
        else _blocked_basis(target)
    )
    states: list[dict[str, Any]] = []
    fragments: dict[str, str] = {}
    for index, basis_state in enumerate(basis["states"], start=1):
        prefix = f"state-{index:03d}"
        source_path = f"fragments/{prefix}.source.html.txt"
        expected_path = f"fragments/{prefix}.expected.html.txt"
        payload_path = f"fragments/{prefix}.payload.html.txt"
        diff_path = f"fragments/{prefix}.diff.html"
        source_fragment = ""
        if reconstruction is not None:
            source_fragment = reconstruction.states[index - 1].source_fragment
        fragments[source_path] = source_fragment
        fragments[expected_path] = ""
        fragments[payload_path] = ""
        states.append(
            {
                "state_id": basis_state["state_id"],
                "criteria": list(basis_state["criteria"]),
                "locator": dict(basis_state["locator"]),
                "verdict": "blocked",
                "source": {
                    "path": source_path,
                    "sha256": bytes_sha256(source_fragment.encode("utf-8")),
                },
                "expected": {
                    "path": expected_path,
                    "sha256": bytes_sha256(b""),
                },
                "payload": {
                    "path": payload_path,
                    "sha256": bytes_sha256(b""),
                },
                "diff": {"path": diff_path},
                "applied_transform_rule_ids": [],
                "retained_table_ids": list(
                    basis_state["retained_table_ids"]
                ),
                "removed_table_ids": list(
                    basis_state["removed_table_ids"]
                ),
                "mismatches": [],
                "blocking_errors": [{"code": code, "message": message}],
            }
        )
    blocking_errors = [
        item for state in states for item in state["blocking_errors"]
    ]
    evidence = {
        "schema_version": "1.0",
        "claim": "independent_source_content_fidelity",
        "verdict": "blocked",
        "coverage": {
            "required": len(states),
            "completed": 0,
            "passed": 0,
            "failed": 0,
            "blocked": len(states),
        },
        "identity": {
            "batch_id": TARGET_BATCH_ID,
            "item_id": TARGET_ITEM_ID,
            "language": TARGET_LANGUAGE,
            "resource_key": TARGET_RESOURCE_KEY,
            "product_key": TARGET_PRODUCT_KEY,
        },
        "reconstruction_basis": basis,
        "verifier_profile": dict(target.profile_identity),
        **ALGORITHM_VERSIONS,
        "states": states,
        "mismatches": [],
        "blocking_errors": blocking_errors,
        "qualification_limitation": None,
        "blocked_reason": message,
    }
    return VerificationRun(
        evidence=evidence,
        fragments=fragments,
        projection_warnings=(
            tuple(reconstruction.hygiene_warnings)
            if reconstruction is not None
            else ()
        ),
    )


def _state_evidence(
    state: ReconstructedState,
    *,
    index: int,
    payload_fragment: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    expected_fragment, applied_rules = materialize_cms_wire(
        state.projected_fragment
    )
    mismatches = compare_html(expected_fragment, payload_fragment)
    verdict = "failed" if mismatches else "passed"
    prefix = f"state-{index:03d}"
    source_path = f"fragments/{prefix}.source.html.txt"
    expected_path = f"fragments/{prefix}.expected.html.txt"
    payload_path = f"fragments/{prefix}.payload.html.txt"
    diff_path = f"fragments/{prefix}.diff.html"
    fragments = {
        source_path: state.source_fragment,
        expected_path: expected_fragment,
        payload_path: payload_fragment,
    }
    return (
        {
            "state_id": state.state_id,
            "criteria": [dict(criterion) for criterion in state.criteria],
            "locator": {
                "container_selector": state.locator["container_selector"],
                "content_selectors": list(state.locator["content_selectors"]),
                "append_selectors": list(state.locator["append_selectors"]),
            },
            "verdict": verdict,
            "source": {
                "path": source_path,
                "sha256": bytes_sha256(state.source_fragment.encode("utf-8")),
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
            "retained_table_ids": list(state.retained_table_ids),
            "removed_table_ids": list(state.removed_table_ids),
            "mismatches": mismatches,
            "blocking_errors": [],
        },
        fragments,
    )


def verify_reconstructed_api_management(
    target: BoundFormalTarget,
    reconstruction: ApiManagementReconstruction,
    *,
    payload: Mapping[str, Any] | None = None,
) -> VerificationRun:
    """Compare independently rebuilt states to uniquely aligned payload groups."""

    selected_payload = payload if payload is not None else target.payload
    payload_by_state = align_payload_content_groups(
        reconstruction, selected_payload
    )
    basis = build_api_management_basis(target, reconstruction)
    state_evidence: list[dict[str, Any]] = []
    fragments: dict[str, str] = {}
    for index, state in enumerate(reconstruction.states, start=1):
        evidence, state_fragments = _state_evidence(
            state,
            index=index,
            payload_fragment=payload_by_state[state.state_id],
        )
        state_evidence.append(evidence)
        fragments.update(state_fragments)
    scope_verdicts = [state["verdict"] for state in state_evidence]
    verdict = aggregate_item_verdict(
        qualified=True,
        started=True,
        required_scope_verdicts=scope_verdicts,
    )
    passed = scope_verdicts.count("passed")
    failed = scope_verdicts.count("failed")
    blocked = scope_verdicts.count("blocked")
    mismatches = [
        mismatch
        for state in state_evidence
        for mismatch in state["mismatches"]
    ]
    evidence = {
        "schema_version": "1.0",
        "claim": "independent_source_content_fidelity",
        "verdict": verdict,
        "coverage": {
            "required": len(state_evidence),
            "completed": passed + failed,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
        },
        "identity": {
            "batch_id": TARGET_BATCH_ID,
            "item_id": TARGET_ITEM_ID,
            "language": TARGET_LANGUAGE,
            "resource_key": TARGET_RESOURCE_KEY,
            "product_key": TARGET_PRODUCT_KEY,
        },
        "reconstruction_basis": basis,
        "verifier_profile": dict(target.profile_identity),
        **ALGORITHM_VERSIONS,
        "states": state_evidence,
        "mismatches": mismatches,
        "blocking_errors": [],
        "qualification_limitation": None,
        "blocked_reason": None,
    }
    return VerificationRun(
        evidence=evidence,
        fragments=fragments,
        projection_warnings=tuple(reconstruction.hygiene_warnings),
    )


def verify_bound_api_management(target: BoundFormalTarget) -> VerificationRun:
    reconstruction = reconstruct_bound_api_management(target)
    return verify_reconstructed_api_management(target, reconstruction)
