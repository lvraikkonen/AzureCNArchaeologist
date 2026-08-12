from __future__ import annotations

import copy
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

import src.independent_fidelity.recorder as recorder
from src.independent_fidelity.api_management import (
    ApiManagementReconstructionError,
    ROW_WARNING_CODE,
    reconstruct_api_management,
    reconstruct_bound_api_management,
)
from src.independent_fidelity.bundle import (
    EvidenceBundleError,
    build_evidence_bundle,
    verify_evidence_bundle,
    verify_inert_projection,
)
from src.independent_fidelity.formal_target import (
    FormalBindingError,
    bind_formal_target,
)
from src.independent_fidelity.formal_verifier import (
    verify_bound_api_management,
    verify_reconstructed_api_management,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bound_target():
    return bind_formal_target(ROOT)


def _region_by_group(payload: dict) -> dict[str, dict]:
    return {
        json.loads(group["filterCriteriaJson"])[0]["matchValues"]: group
        for group in payload["contentGroups"]
    }


def test_real_common_mode_state_swap_passes_shared_replay_but_fails_l3b(
    bound_target,
) -> None:
    reconstruction = reconstruct_bound_api_management(bound_target)
    baseline = verify_reconstructed_api_management(
        bound_target, reconstruction
    )
    independent_expected = {
        state.region: baseline.fragments[
            baseline.evidence["states"][index]["expected"]["path"]
        ]
        for index, state in enumerate(reconstruction.states)
    }

    mutated_payload = copy.deepcopy(bound_target.payload)
    payload_groups = _region_by_group(mutated_payload)
    east2 = "east-china2"
    east1 = "east-china"
    payload_groups[east2]["content"], payload_groups[east1]["content"] = (
        payload_groups[east1]["content"],
        payload_groups[east2]["content"],
    )

    # This deliberately models the common-mode L3a lane: the replay candidate
    # and payload share the same wrong state mapping, so their comparison passes.
    shared_bug_replay = dict(independent_expected)
    shared_bug_replay[east2], shared_bug_replay[east1] = (
        shared_bug_replay[east1],
        shared_bug_replay[east2],
    )
    mutated_payload_by_region = {
        region: group["content"] for region, group in payload_groups.items()
    }
    l3a_replay_status = (
        "passed"
        if all(
            shared_bug_replay[region] == mutated_payload_by_region[region]
            for region in shared_bug_replay
        )
        else "failed"
    )
    assert l3a_replay_status == "passed"

    independent = verify_reconstructed_api_management(
        bound_target,
        reconstruction,
        payload=mutated_payload,
    )
    failed_regions = {
        state["criteria"][0]["matchValues"]
        for state in independent.evidence["states"]
        if state["verdict"] == "failed"
    }
    assert independent.evidence["verdict"] == "failed"
    assert independent.evidence["coverage"]["failed"] == 2
    assert failed_regions == {east2, east1}
    assert all(
        state["verdict"] == "passed"
        for state in independent.evidence["states"]
        if state["criteria"][0]["matchValues"] not in failed_regions
    )


@pytest.mark.parametrize(
    "table_ids",
    [
        [
            "#API-Management-preview",
            "#API-Management-preview",
            "#API-Management-gateway",
        ],
        [
            "#API-Management-preview",
            "#API-Management-gateway",
            "#API-Management-preview",
        ],
    ],
)
def test_duplicate_row_warning_replay_is_deterministic_and_nonblocking(
    bound_target, table_ids: list[str]
) -> None:
    config = copy.deepcopy(bound_target.soft_category)
    config[234]["tableIDs"] = table_ids
    first = reconstruct_api_management(
        source_html=bound_target.source_html,
        soft_category=config,
        sampling_plan=bound_target.sampling_plan,
        enforce_frozen_state_specs=False,
    )
    second = reconstruct_api_management(
        source_html=bound_target.source_html,
        soft_category=config,
        sampling_plan=bound_target.sampling_plan,
        enforce_frozen_state_specs=False,
    )
    assert first.hygiene_warnings == second.hygiene_warnings
    assert first.hygiene_warnings[0]["code"] == ROW_WARNING_CODE
    assert first.hygiene_warnings[0]["first_position"] == 0
    assert verify_reconstructed_api_management(
        replace(bound_target, soft_category=config), first
    ).evidence["verdict"] == "passed"


def test_scroll_table_wrapper_containing_multiple_tables_is_blocked(
    bound_target,
) -> None:
    soup = BeautifulSoup(bound_target.source_html, "html.parser")
    first = soup.find("table", id="API-Management-preview")
    second = soup.find("table", id="API-Management-preview2")
    assert first is not None and second is not None
    wrapper = soup.new_tag("div", attrs={"class": "scroll-table"})
    first.wrap(wrapper)
    wrapper.append(second.extract())
    with pytest.raises(ApiManagementReconstructionError) as raised:
        reconstruct_api_management(
            source_html=str(soup),
            soft_category=bound_target.soft_category,
            sampling_plan=bound_target.sampling_plan,
        )
    assert raised.value.code == "source_table_wrapper_ambiguous"


def _bundle(path: Path, target) -> dict:
    return build_evidence_bundle(
        path,
        repository_root=ROOT,
        run=verify_bound_api_management(target),
        l3a_summary=target.l3a_summary,
    )


def test_evidence_json_duplicate_keys_are_rejected(bound_target, tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _bundle(bundle, bound_target)
    evidence_path = bundle / "evidence.json"
    text = evidence_path.read_text(encoding="utf-8")
    evidence_path.write_text(
        text.replace(
            '  "claim": "independent_source_content_fidelity",',
            '  "claim": "independent_source_content_fidelity",\n'
            '  "claim": "independent_source_content_fidelity",',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(EvidenceBundleError, match="strict closed-world JSON"):
        verify_evidence_bundle(ROOT, bundle)


def test_fragment_symlink_is_rejected_before_hashing(bound_target, tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    evidence = _bundle(bundle, bound_target)
    source = bundle / evidence["states"][0]["source"]["path"]
    payload = bundle / evidence["states"][0]["payload"]["path"]
    source.unlink()
    source.symlink_to(payload.name)
    with pytest.raises(EvidenceBundleError, match="symbolic link"):
        verify_evidence_bundle(ROOT, bundle)


@pytest.mark.parametrize(
    "active_markup",
    [
        '<meta http-equiv="refresh" content="0;https://evil.example">',
        '<style>@import "https://evil.example/x.css";</style>',
        '<div style="background:url(https://evil.example/x.png)"></div>',
    ],
)
def test_inert_projection_rejects_indirect_network_or_navigation_markup(
    bound_target, tmp_path: Path, active_markup: str
) -> None:
    bundle = tmp_path / "bundle"
    evidence = _bundle(bundle, bound_target)
    review_path = bundle / "review.html"
    review_path.write_text(
        review_path.read_text(encoding="utf-8").replace(
            "</body>", active_markup + "</body>"
        ),
        encoding="utf-8",
    )
    with pytest.raises(EvidenceBundleError):
        verify_inert_projection(bundle, evidence)


def test_clean_repository_guard_rejects_tracked_and_untracked_drift(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(
        ["git", "config", "user.email", "codex@example.invalid"],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Codex Test"],
        cwd=repository,
        check=True,
    )
    tracked = repository / "tracked.txt"
    tracked.write_text("clean\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repository, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture"],
        cwd=repository,
        check=True,
    )
    assert recorder._require_clean_repository(repository)

    tracked.write_text("dirty\n", encoding="utf-8")
    with pytest.raises(FormalBindingError) as tracked_error:
        recorder._require_clean_repository(repository)
    assert tracked_error.value.code == "implementation_worktree_dirty"
    tracked.write_text("clean\n", encoding="utf-8")
    (repository / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(FormalBindingError) as untracked_error:
        recorder._require_clean_repository(repository)
    assert untracked_error.value.code == "implementation_worktree_dirty"


def test_record_and_verify_console_project_hygiene_warning_details(
    bound_target, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = copy.deepcopy(bound_target.soft_category)
    config[236]["tableIDs"] = [
        "#API-Management-preview2",
        "#API-Management-preview2",
    ]
    warning_target = replace(bound_target, soft_category=config)
    monkeypatch.setattr(
        recorder,
        "bind_formal_target",
        lambda repository_root, *, batch_id, item_id: warning_target,
    )
    bundle = tmp_path / "bundle"
    recorded = recorder.record_formal_target(
        ROOT,
        bundle_root=bundle,
        require_clean_repository=False,
    )
    assert recorded.exit_code == 0
    fields = dict(recorded.console_fields())
    assert fields["configuration_hygiene_warnings"] == "1"
    assert ROW_WARNING_CODE in fields["configuration_hygiene_warning_details"]

    verified = recorder.verify_formal_target(ROOT, bundle_root=bundle)
    verify_fields = dict(verified.console_fields())
    assert verified.exit_code == 0
    assert verify_fields["configuration_hygiene_warnings"] == "1"
    assert ROW_WARNING_CODE in verify_fields[
        "configuration_hygiene_warning_details"
    ]
