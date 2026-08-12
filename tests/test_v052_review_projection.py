from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from src.independent_fidelity.api_management import (
    ROW_WARNING_CODE,
    reconstruct_bound_api_management,
)
from src.independent_fidelity.bundle import (
    EvidenceBundleError,
    build_evidence_bundle,
    verify_evidence_bundle,
    verify_inert_projection,
)
from src.independent_fidelity.formal_target import bind_formal_target
from src.independent_fidelity.formal_verifier import (
    verify_bound_api_management,
    verify_reconstructed_api_management,
)


ROOT = Path(__file__).resolve().parents[1]
EXACT_CSP = (
    "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; "
    "img-src 'none'; media-src 'none'; font-src 'none'; connect-src 'none'; "
    "object-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none';"
)


@pytest.fixture(scope="module")
def bound_target():
    return bind_formal_target(ROOT)


def _build(bundle: Path, target, run=None, *, style="formal-test"):
    selected_run = run if run is not None else verify_bound_api_management(target)
    return build_evidence_bundle(
        bundle,
        repository_root=ROOT,
        run=selected_run,
        l3a_summary=target.l3a_summary,
        style_variant=style,
    )


def test_review_projects_exact_l3a_and_l3b_claim_owners(
    bound_target, tmp_path: Path
) -> None:
    bundle = tmp_path / "bundle"
    evidence = _build(bundle, bound_target)
    review = (bundle / "review.html").read_text(encoding="utf-8")
    assert "L3a / current Machine Validation" in review
    assert "sampled_state_content_consistency" in review
    assert "5/5 selected; untested=0" in review
    for reference in (
        bound_target.l3a_summary["validation"],
        bound_target.l3a_summary["sampling_plan"],
        bound_target.l3a_summary["sampled_content_evidence"],
    ):
        assert reference["path"] in review
        assert reference["sha256"] in review
    assert "L3b / Independent Fidelity" in review
    assert "independent_source_content_fidelity" in review
    assert evidence["reconstruction_basis"]["basis_id"] in review
    assert evidence["reconstruction_basis"]["basis_semantic_identity"][
        "sha256"
    ] in review
    assert evidence["verifier_profile"]["sha256"] in review
    assert evidence["reconstruction_profile_version"] in review
    assert evidence["wire_transform_version"] in review
    assert evidence["comparison_version"] in review
    assert evidence["evidence_semantic_identity"]["sha256"] in review

    stored = json.loads((bundle / "evidence.json").read_text(encoding="utf-8"))
    assert "l3a" not in stored
    assert "sampled_state_content_consistency" not in json.dumps(stored)


def test_review_and_all_diffs_have_exact_csp_and_only_same_document_anchors(
    bound_target, tmp_path: Path
) -> None:
    bundle = tmp_path / "bundle"
    evidence = _build(bundle, bound_target)
    projection_paths = [
        bundle / reference["path"]
        for reference in evidence["review_projection_artifact_identity"][
            "artifacts"
        ]
    ]
    assert len(projection_paths) == 6
    for path in projection_paths:
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        csp = soup.select('meta[http-equiv="Content-Security-Policy"]')
        assert len(csp) == 1
        assert csp[0]["content"] == EXACT_CSP
        assert not soup.find_all(
            [
                "script",
                "form",
                "img",
                "video",
                "audio",
                "iframe",
                "object",
                "embed",
                "link",
                "base",
            ]
        )
        for anchor in soup.find_all("a", href=True):
            assert str(anchor["href"]).startswith("#")
    verify_inert_projection(bundle, evidence)
    assert verify_evidence_bundle(ROOT, bundle) == evidence


def test_hygiene_warning_changes_only_projection_identity(
    bound_target, tmp_path: Path
) -> None:
    baseline_run = verify_bound_api_management(bound_target)
    baseline = _build(tmp_path / "baseline", bound_target, baseline_run)

    config = copy.deepcopy(bound_target.soft_category)
    config[236]["tableIDs"] = [
        "#API-Management-preview2",
        " #API-Management-preview2 ",
    ]
    warning_target = replace(bound_target, soft_category=config)
    reconstruction = reconstruct_bound_api_management(warning_target)
    assert len(reconstruction.hygiene_warnings) == 1
    warning_run = verify_reconstructed_api_management(
        warning_target, reconstruction
    )
    warned = _build(tmp_path / "warned", warning_target, warning_run)
    review = (tmp_path / "warned/review.html").read_text(encoding="utf-8")

    assert warning_run.evidence["verdict"] == "passed"
    assert baseline["evidence_semantic_identity"] == warned[
        "evidence_semantic_identity"
    ]
    assert baseline["review_projection_artifact_identity"] != warned[
        "review_projection_artifact_identity"
    ]
    assert "Configuration Hygiene" in review
    assert ROW_WARNING_CODE in review
    warning_projection = json.loads(
        BeautifulSoup(review, "html.parser")
        .select_one("#configuration-hygiene pre")
        .get_text()
    )[0]
    assert warning_projection["first_position"] == 0
    assert warning_projection["duplicate_positions"] == [1]
    assert warning_projection["handling"] == "first_occurrence_ordered_unique"
    assert warning_projection["verdict_effect"] == "none"


def test_layout_only_change_preserves_semantics_but_changes_projection(
    bound_target, tmp_path: Path
) -> None:
    run = verify_bound_api_management(bound_target)
    first = _build(tmp_path / "first", bound_target, run, style="layout-a")
    second = _build(tmp_path / "second", bound_target, run, style="layout-b")
    assert first["evidence_semantic_identity"] == second[
        "evidence_semantic_identity"
    ]
    assert first["review_projection_artifact_identity"] != second[
        "review_projection_artifact_identity"
    ]


def test_inert_verifier_rejects_external_navigation_even_with_valid_csp(
    bound_target, tmp_path: Path
) -> None:
    bundle = tmp_path / "bundle"
    evidence = _build(bundle, bound_target)
    review_path = bundle / "review.html"
    review = review_path.read_text(encoding="utf-8")
    review_path.write_text(
        review.replace('href="#state-001"', 'href="https://evil.example"', 1),
        encoding="utf-8",
    )
    with pytest.raises(EvidenceBundleError, match="same-document anchor"):
        verify_inert_projection(bundle, evidence)


def test_raw_fragments_are_non_executable_html_text_files(
    bound_target, tmp_path: Path
) -> None:
    bundle = tmp_path / "bundle"
    evidence = _build(bundle, bound_target)
    for state in evidence["states"]:
        for owner in ("source", "expected", "payload"):
            path = state[owner]["path"]
            assert path.endswith(".html.txt")
            fragment = bundle / path
            assert fragment.is_file()
            assert fragment.suffix == ".txt"
