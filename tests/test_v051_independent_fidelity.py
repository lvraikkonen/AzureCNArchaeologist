from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from src.independent_fidelity.bundle import (
    EvidenceBundleError,
    build_evidence_bundle,
    verify_evidence_bundle,
)
from src.independent_fidelity.contracts import (
    ContractError,
    evidence_is_current,
    validate_basis,
    validate_evidence,
    validate_profile,
)
from src.independent_fidelity.firewall import check_static_dependencies
from src.independent_fidelity.fixture import (
    PAYLOAD_BY_STATE,
    SOURCE_HTML,
    controlled_basis,
    mutate_basis_locator,
    profile_document,
    profile_identity,
    rebind_fixture_basis,
)
from src.independent_fidelity.verdict import (
    ClaimStateError,
    aggregate_item_verdict,
)
from src.independent_fidelity.verifier import (
    apply_wire_transforms,
    compare_html,
    verify_fixture_states,
)
from src.independent_fidelity.versions import ALGORITHM_VERSIONS


ROOT = Path(__file__).resolve().parents[1]
L3A_PASSED = {
    "claim": "strategy_replay_consistency",
    "verdict": "passed",
    "coverage": "2/2",
    "evidence_reference": "fixtures/l3a.validation.json",
}


def _passing_run():
    basis = controlled_basis(ROOT)
    return verify_fixture_states(
        source_html=SOURCE_HTML,
        payload_by_state=PAYLOAD_BY_STATE,
        basis=basis,
        profile_identity=profile_identity(ROOT),
    )


@pytest.mark.parametrize(
    ("qualified", "started", "scopes", "runtime_error", "expected"),
    [
        (False, False, (), False, "not_qualified"),
        (True, False, (), False, "not_run"),
        (True, True, ("passed", "passed"), False, "passed"),
        (True, True, ("passed", "blocked"), False, "blocked"),
        (True, True, ("failed", "blocked"), False, "failed"),
        (True, True, ("passed",), True, "blocked"),
        (True, True, (), False, "blocked"),
    ],
)
def test_item_level_verdict_aggregation(
    qualified: bool,
    started: bool,
    scopes: tuple[str, ...],
    runtime_error: bool,
    expected: str,
) -> None:
    assert aggregate_item_verdict(
        qualified=qualified,
        started=started,
        required_scope_verdicts=scopes,
        runtime_error=runtime_error,
    ) == expected


@pytest.mark.parametrize(
    ("qualified", "started", "scopes", "runtime_error"),
    [
        (False, True, (), False),
        (False, False, ("passed",), False),
        (True, False, ("passed",), False),
        (True, False, (), True),
        (True, True, ("not_run",), False),
    ],
)
def test_execution_preconditions_cannot_mix_with_executed_results(
    qualified: bool,
    started: bool,
    scopes: tuple[str, ...],
    runtime_error: bool,
) -> None:
    with pytest.raises(ClaimStateError):
        aggregate_item_verdict(
            qualified=qualified,
            started=started,
            required_scope_verdicts=scopes,
            runtime_error=runtime_error,
        )


def test_minimal_profile_and_basis_contracts_are_closed_world() -> None:
    profile = validate_profile(ROOT, profile_document(ROOT))
    basis = validate_basis(ROOT, controlled_basis(ROOT))
    assert profile["verdicts"] == [
        "passed",
        "failed",
        "blocked",
        "not_qualified",
        "not_run",
    ]
    assert set(ALGORITHM_VERSIONS).issubset(profile)
    assert basis["batch_binding"]["input_manifest"]["path"].endswith(
        "input-manifest.json"
    )
    assert basis["batch_binding"]["batch_manifest"]["revision"] == 1
    assert basis["persisted_payload_identity"]["batch_revision"] == 1

    extra = copy.deepcopy(profile)
    extra["future_gate_policy"] = "premature"
    with pytest.raises(ContractError, match="Additional properties"):
        validate_profile(ROOT, extra)
    missing = copy.deepcopy(basis)
    missing.pop("source_identity")
    with pytest.raises(ContractError, match="required property"):
        validate_basis(ROOT, missing)


def test_controlled_fixture_passes_independent_reconstruction() -> None:
    run = _passing_run()
    assert run.evidence["verdict"] == "passed"
    assert run.evidence["coverage"] == {
        "required": 2,
        "completed": 2,
        "passed": 2,
        "failed": 0,
        "blocked": 0,
    }


def test_frozen_binding_drift_blocks_instead_of_comparing_unbound_bytes() -> None:
    run = verify_fixture_states(
        source_html=SOURCE_HTML + "<!-- drift -->",
        payload_by_state=PAYLOAD_BY_STATE,
        basis=controlled_basis(ROOT),
        profile_identity=profile_identity(ROOT),
    )
    assert run.evidence["verdict"] == "blocked"
    assert run.evidence["coverage"]["blocked"] == 2
    assert all(
        state["blocking_errors"][0]["code"]
        == "independent_reconstruction_blocked"
        for state in run.evidence["states"]
    )


def test_counterexample_swapping_state_content_preserves_criteria_but_fails() -> None:
    swapped = {
        "east": PAYLOAD_BY_STATE["north"],
        "north": PAYLOAD_BY_STATE["east"],
    }
    basis = rebind_fixture_basis(
        controlled_basis(ROOT), payload_by_state=swapped
    )
    run = verify_fixture_states(
        source_html=SOURCE_HTML,
        payload_by_state=swapped,
        basis=basis,
        profile_identity=profile_identity(ROOT),
    )
    assert run.evidence["verdict"] == "failed"
    assert run.evidence["coverage"]["failed"] == 2
    assert all(state["criteria"] for state in run.evidence["states"])


def test_counterexample_missing_one_source_node_fails() -> None:
    basis = mutate_basis_locator(
        controlled_basis(ROOT),
        state_id="east",
        content_selectors=[".price-copy"],
    )
    run = verify_fixture_states(
        source_html=SOURCE_HTML,
        payload_by_state=PAYLOAD_BY_STATE,
        basis=basis,
        profile_identity=profile_identity(ROOT),
    )
    assert run.evidence["verdict"] == "failed"
    assert run.evidence["states"][0]["verdict"] == "failed"


def test_counterexample_including_adjacent_source_node_fails() -> None:
    basis = mutate_basis_locator(
        controlled_basis(ROOT),
        state_id="east",
        append_selectors=["#faq-neighbor"],
    )
    run = verify_fixture_states(
        source_html=SOURCE_HTML,
        payload_by_state=PAYLOAD_BY_STATE,
        basis=basis,
        profile_identity=profile_identity(ROOT),
    )
    assert run.evidence["verdict"] == "failed"
    assert any(
        mismatch["dimension"] == "raw"
        for mismatch in run.evidence["states"][0]["mismatches"]
    )


def test_counterexample_declared_wire_rule_passes_undeclared_form_fails() -> None:
    source = '<p><i class="icon icon-tick"></i>Included</p>'
    payload = "<p>✓Included</p>"
    expected, applied = apply_wire_transforms(
        source, ["css-generated-semantics-v1"]
    )
    assert expected == payload
    assert applied == ["css-generated-semantics-v1"]
    assert compare_html(expected, payload) == []

    undeclared, applied = apply_wire_transforms(source, [])
    assert applied == []
    assert compare_html(undeclared, payload)


def test_l3a_can_pass_while_independent_l3b_fails(tmp_path: Path) -> None:
    swapped = {
        "east": PAYLOAD_BY_STATE["north"],
        "north": PAYLOAD_BY_STATE["east"],
    }
    basis = rebind_fixture_basis(
        controlled_basis(ROOT), payload_by_state=swapped
    )
    l3b = verify_fixture_states(
        source_html=SOURCE_HTML,
        payload_by_state=swapped,
        basis=basis,
        profile_identity=profile_identity(ROOT),
    )
    evidence = build_evidence_bundle(
        tmp_path / "independent-fidelity",
        repository_root=ROOT,
        run=l3b,
        l3a_summary=L3A_PASSED,
    )
    review = (tmp_path / "independent-fidelity/review.html").read_text(
        encoding="utf-8"
    )
    assert L3A_PASSED["verdict"] == "passed"
    assert evidence["verdict"] == "failed"
    assert "strategy_replay_consistency" in review
    assert "independent_source_content_fidelity" in review


def test_evidence_bundle_validates_references_hashes_and_contract(tmp_path: Path) -> None:
    bundle = tmp_path / "independent-fidelity"
    evidence = build_evidence_bundle(
        bundle,
        repository_root=ROOT,
        run=_passing_run(),
        l3a_summary=L3A_PASSED,
    )
    assert validate_evidence(ROOT, evidence) == evidence
    assert verify_evidence_bundle(ROOT, bundle) == evidence

    evidence_path = bundle / "evidence.json"
    drifted = json.loads(evidence_path.read_text(encoding="utf-8"))
    drifted["states"][0]["source"]["sha256"] = "0" * 64
    evidence_path.write_text(
        json.dumps(drifted, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(EvidenceBundleError):
        verify_evidence_bundle(ROOT, bundle)


def test_evidence_contract_rejects_extra_fields_and_bad_verdict(tmp_path: Path) -> None:
    evidence = build_evidence_bundle(
        tmp_path / "bundle",
        repository_root=ROOT,
        run=_passing_run(),
        l3a_summary=L3A_PASSED,
    )
    extra = copy.deepcopy(evidence)
    extra["manual_l3b_passed"] = True
    with pytest.raises(ContractError, match="Additional properties"):
        validate_evidence(ROOT, extra)

    bad_verdict = copy.deepcopy(evidence)
    bad_verdict["verdict"] = "warning"
    with pytest.raises(ContractError, match="not one of"):
        validate_evidence(ROOT, bad_verdict)


def test_semantic_identity_ignores_review_layout_but_projection_changes(
    tmp_path: Path,
) -> None:
    run = _passing_run()
    first = build_evidence_bundle(
        tmp_path / "first",
        repository_root=ROOT,
        run=run,
        l3a_summary=L3A_PASSED,
        style_variant="layout-a",
    )
    second = build_evidence_bundle(
        tmp_path / "second",
        repository_root=ROOT,
        run=run,
        l3a_summary=L3A_PASSED,
        style_variant="layout-b",
    )
    assert first["evidence_semantic_identity"] == second[
        "evidence_semantic_identity"
    ]
    assert first["review_projection_artifact_identity"] != second[
        "review_projection_artifact_identity"
    ]


def test_historical_evidence_stays_valid_but_is_not_current_after_binding_drift(
    tmp_path: Path,
) -> None:
    basis = controlled_basis(ROOT)
    evidence = build_evidence_bundle(
        tmp_path / "bundle",
        repository_root=ROOT,
        run=_passing_run(),
        l3a_summary=L3A_PASSED,
    )
    profile = profile_identity(ROOT)
    assert evidence_is_current(evidence, basis, profile, ALGORITHM_VERSIONS)

    successor = copy.deepcopy(basis)
    successor["persisted_payload_identity"]["sha256"] = "9" * 64
    successor.pop("basis_semantic_identity")
    from src.independent_fidelity.contracts import with_basis_semantic_identity

    successor = with_basis_semantic_identity(successor)
    assert validate_evidence(ROOT, evidence) == evidence
    assert not evidence_is_current(
        evidence, successor, profile, ALGORITHM_VERSIONS
    )


def test_review_projection_is_inert_for_malicious_fragment(tmp_path: Path) -> None:
    malicious = (
        '<script src="https://evil.example/x.js"></script>'
        '<img src="https://evil.example/x.png" onerror="alert(1)">'
        '<form action="https://evil.example/post"><button>send</button></form>'
        '<a href="https://evil.example/nav">navigate</a>'
    )
    payload = dict(PAYLOAD_BY_STATE)
    payload["east"] = PAYLOAD_BY_STATE["east"] + malicious
    source = SOURCE_HTML.replace(
        "</section>", malicious + "</section>", 1
    )
    basis = mutate_basis_locator(
        controlled_basis(ROOT),
        state_id="east",
        append_selectors=[
            "#state-east > script",
            "#state-east > img",
            "#state-east > form",
            "#state-east > a",
        ],
    )
    basis = rebind_fixture_basis(
        basis, source_html=source, payload_by_state=payload
    )
    run = verify_fixture_states(
        source_html=source,
        payload_by_state=payload,
        basis=basis,
        profile_identity=profile_identity(ROOT),
    )
    build_evidence_bundle(
        tmp_path / "bundle",
        repository_root=ROOT,
        run=run,
        l3a_summary=L3A_PASSED,
    )
    review = (tmp_path / "bundle/review.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(review, "html.parser")
    assert soup.select_one(
        'meta[http-equiv="Content-Security-Policy"]'
    ) is not None
    assert not soup.find_all(["script", "form", "iframe", "object", "img"])
    assert not soup.select("[onerror], [onclick], [onsubmit]")
    for tag in soup.find_all(href=True):
        assert str(tag["href"]).startswith("#")
    assert "&lt;script" in review
    assert "&lt;form" in review


def test_static_firewall_and_runtime_sentinel_pass() -> None:
    assert check_static_dependencies(ROOT) == []
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/check_independent_fidelity.py"),
            "--runtime-smoke",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "static_dependency_firewall=passed" in result.stdout
    assert "runtime_sentinel=passed" in result.stdout
