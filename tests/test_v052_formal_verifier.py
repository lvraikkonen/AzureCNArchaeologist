from __future__ import annotations

import copy
from pathlib import Path

import pytest

from src.independent_fidelity.api_management import (
    reconstruct_bound_api_management,
)
from src.independent_fidelity.contracts import validate_basis
from src.independent_fidelity.formal_target import (
    BATCH_MANIFEST_PATH,
    FROZEN_SHA256,
    INPUT_MANIFEST_PATH,
    PAYLOAD_PATH,
    PROFILE_PATH,
    TARGET_BATCH_REVISION,
    bind_formal_target,
)
from src.independent_fidelity.formal_verifier import (
    FormalVerificationBlocked,
    align_payload_content_groups,
    materialize_cms_wire,
    verify_bound_api_management,
    verify_reconstructed_api_management,
)
from src.independent_fidelity.versions import ALGORITHM_VERSIONS


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bound_target():
    return bind_formal_target(ROOT)


@pytest.fixture(scope="module")
def reconstruction(bound_target):
    return reconstruct_bound_api_management(bound_target)


def test_formal_happy_path_matches_all_five_persisted_groups(bound_target) -> None:
    run = verify_bound_api_management(bound_target)
    assert run.evidence["verdict"] == "passed"
    assert run.evidence["coverage"] == {
        "required": 5,
        "completed": 5,
        "passed": 5,
        "failed": 0,
        "blocked": 0,
    }
    assert run.evidence["mismatches"] == []
    assert run.evidence["blocking_errors"] == []
    assert "l3a" not in run.evidence
    for state in run.evidence["states"]:
        assert state["verdict"] == "passed"
        assert state["applied_transform_rule_ids"] == []
        assert state["source"]["path"].endswith(".source.html.txt")
        assert state["expected"]["path"].endswith(".expected.html.txt")
        assert state["payload"]["path"].endswith(".payload.html.txt")
        assert run.fragments[state["expected"]["path"]] == run.fragments[
            state["payload"]["path"]
        ]
        assert run.fragments[state["source"]["path"]] != run.fragments[
            state["expected"]["path"]
        ]


def test_formal_basis_binds_both_manifests_current_payload_and_algorithms(
    bound_target,
) -> None:
    basis = verify_bound_api_management(bound_target).evidence[
        "reconstruction_basis"
    ]
    assert validate_basis(ROOT, basis) == basis
    assert basis["batch_binding"] == {
        "batch_id": "20260811T171630Z-e80afabe",
        "input_manifest": {
            "path": INPUT_MANIFEST_PATH.as_posix(),
            "sha256": FROZEN_SHA256[INPUT_MANIFEST_PATH.as_posix()],
        },
        "batch_manifest": {
            "path": BATCH_MANIFEST_PATH.as_posix(),
            "sha256": FROZEN_SHA256[BATCH_MANIFEST_PATH.as_posix()],
            "revision": TARGET_BATCH_REVISION,
        },
    }
    assert basis["persisted_payload_identity"] == {
        "path": PAYLOAD_PATH.as_posix(),
        "sha256": FROZEN_SHA256[PAYLOAD_PATH.as_posix()],
        "batch_revision": TARGET_BATCH_REVISION,
    }
    assert basis["verifier_profile"]["path"] == PROFILE_PATH.as_posix()
    assert all(basis[key] == value for key, value in ALGORITHM_VERSIONS.items())


def test_confirmed_content_mismatch_fails_at_all_four_comparison_layers(
    bound_target, reconstruction
) -> None:
    payload = copy.deepcopy(bound_target.payload)
    content = payload["contentGroups"][0]["content"]
    assert "<h2> API 管理 </h2>" in content
    payload["contentGroups"][0]["content"] = content.replace(
        "<h2> API 管理 </h2>", "<h3>错误 ownership</h3>", 1
    )
    run = verify_reconstructed_api_management(
        bound_target, reconstruction, payload=payload
    )
    assert run.evidence["verdict"] == "failed"
    assert run.evidence["coverage"] == {
        "required": 5,
        "completed": 5,
        "passed": 4,
        "failed": 1,
        "blocked": 0,
    }
    first = run.evidence["states"][0]
    assert first["verdict"] == "failed"
    assert {mismatch["dimension"] for mismatch in first["mismatches"]} == {
        "raw",
        "dom",
        "tag_structure",
        "visible_text",
    }


@pytest.mark.parametrize(
    "mutation",
    ["reordered", "duplicate", "extra_criterion", "unknown_region"],
)
def test_payload_state_domain_must_align_uniquely_by_region(
    bound_target, reconstruction, mutation: str
) -> None:
    payload = copy.deepcopy(bound_target.payload)
    groups = payload["contentGroups"]
    if mutation == "reordered":
        groups[0], groups[1] = groups[1], groups[0]
    elif mutation == "duplicate":
        groups[1]["filterCriteriaJson"] = groups[0]["filterCriteriaJson"]
        groups[1]["groupName"] = groups[0]["groupName"]
    elif mutation == "extra_criterion":
        groups[0]["filterCriteriaJson"] = (
            '[{"filterKey":"region","matchValues":"east-china2"},'
            '{"filterKey":"software","matchValues":"API Management"}]'
        )
    else:
        groups[0]["filterCriteriaJson"] = (
            '[{"filterKey":"region","matchValues":"moon"}]'
        )
    with pytest.raises(FormalVerificationBlocked):
        align_payload_content_groups(reconstruction, payload)


def test_payload_group_name_must_match_desktop_label(
    bound_target, reconstruction
) -> None:
    payload = copy.deepcopy(bound_target.payload)
    payload["contentGroups"][0]["groupName"] = "mobile label is not authority"
    with pytest.raises(FormalVerificationBlocked) as raised:
        align_payload_content_groups(reconstruction, payload)
    assert raised.value.code == "payload_state_label_mismatch"


@pytest.mark.parametrize(
    ("fragment", "token"),
    [
        ('<div><i class="icon-tick"></i></div>', "icon-tick"),
        ('<div><img src="/asset.png"></div>', "root-relative-image"),
        ('<div data-config="/asset.json"></div>', "data-config-asset"),
        ('<div style="background:url(/asset.png)"></div>', "style-url"),
    ],
)
def test_unexpected_content_affecting_wire_inputs_block(fragment: str, token: str) -> None:
    with pytest.raises(FormalVerificationBlocked) as raised:
        materialize_cms_wire(fragment)
    assert raised.value.code == "unexpected_wire_transform_input"
    assert token in str(raised.value)


def test_wire_compaction_is_deterministic_and_has_no_applied_rule() -> None:
    fragment = "<div>\n  <p> one   two </p>\n</div>"
    first = materialize_cms_wire(fragment)
    second = materialize_cms_wire(fragment)
    assert first == second == ("<div><p> one two </p></div>", [])


def test_formal_verification_replay_is_deterministic(bound_target) -> None:
    first = verify_bound_api_management(bound_target)
    second = verify_bound_api_management(bound_target)
    assert first.evidence == second.evidence
    assert first.fragments == second.fragments
    assert first.projection_warnings == second.projection_warnings
