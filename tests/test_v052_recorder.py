from __future__ import annotations

import copy
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import src.independent_fidelity.recorder as recorder
from src.independent_fidelity.api_management import (
    reconstruct_bound_api_management,
)
from src.independent_fidelity.formal_target import (
    CANONICAL_BUNDLE_PREFIX,
    FormalBindingError,
    ProfileQualification,
    TARGET_BATCH_ID,
    TARGET_ITEM_ID,
    bind_formal_target,
    inventory_regular_files,
)
from src.independent_fidelity.formal_verifier import (
    FormalVerificationBlocked,
    blocked_verification_run,
    verify_reconstructed_api_management,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bound_target():
    return bind_formal_target(ROOT)


def _patch_target(monkeypatch: pytest.MonkeyPatch, target) -> None:
    monkeypatch.setattr(
        recorder,
        "bind_formal_target",
        lambda repository_root, *, batch_id, item_id: target,
    )


def _file_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_record_passes_then_existing_current_degrades_to_read_only_verify(
    bound_target, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_target(monkeypatch, bound_target)
    bundle = tmp_path / "bundle"
    first = recorder.record_formal_target(
        ROOT,
        bundle_root=bundle,
        require_clean_repository=False,
    )
    assert first.exit_code == 0
    assert first.outcome == "passed"
    assert first.verdict == "passed"
    assert first.coverage == {
        "required": 5,
        "completed": 5,
        "passed": 5,
        "failed": 0,
        "blocked": 0,
    }
    assert first.evidence_path == (bundle / "evidence.json").resolve()
    assert first.review_path == (bundle / "review.html").resolve()
    assert len(_file_bytes(bundle)) == 22

    before = _file_bytes(bundle)
    second = recorder.record_formal_target(
        ROOT,
        bundle_root=bundle,
        require_clean_repository=False,
    )
    assert second.exit_code == 0
    assert second.outcome == "existing_current"
    assert second.evidence_semantic_sha256 == first.evidence_semantic_sha256
    assert second.projection_sha256 == first.projection_sha256
    assert _file_bytes(bundle) == before


def test_failed_bundle_is_preserved_and_returns_exit_two(
    bound_target, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_target(monkeypatch, bound_target)
    reconstruction = reconstruct_bound_api_management(bound_target)
    payload = copy.deepcopy(bound_target.payload)
    payload["contentGroups"][0]["content"] += "<p>wrong state content</p>"
    failed_run = verify_reconstructed_api_management(
        bound_target,
        reconstruction,
        payload=payload,
    )
    monkeypatch.setattr(
        recorder,
        "_compute_run",
        lambda target: (failed_run, reconstruction),
    )
    bundle = tmp_path / "failed"
    first = recorder.record_formal_target(
        ROOT,
        bundle_root=bundle,
        require_clean_repository=False,
    )
    assert first.exit_code == 2
    assert first.outcome == "failed"
    assert first.coverage["failed"] == 1
    before = _file_bytes(bundle)
    second = recorder.record_formal_target(
        ROOT,
        bundle_root=bundle,
        require_clean_repository=False,
    )
    assert second.exit_code == 2
    assert second.outcome == "existing_current"
    assert second.verdict == "failed"
    assert _file_bytes(bundle) == before


def test_blocked_bundle_is_preserved_and_returns_exit_two(
    bound_target, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_target(monkeypatch, bound_target)
    reconstruction = reconstruct_bound_api_management(bound_target)
    blocked_run = blocked_verification_run(
        bound_target,
        FormalVerificationBlocked(
            "controlled_state_identity_block", "cannot align controlled state"
        ),
        reconstruction=reconstruction,
    )
    monkeypatch.setattr(
        recorder,
        "_compute_run",
        lambda target: (blocked_run, reconstruction),
    )
    bundle = tmp_path / "blocked"
    first = recorder.record_formal_target(
        ROOT,
        bundle_root=bundle,
        require_clean_repository=False,
    )
    assert first.exit_code == 2
    assert first.outcome == "blocked"
    assert first.coverage == {
        "required": 5,
        "completed": 0,
        "passed": 0,
        "failed": 0,
        "blocked": 5,
    }
    before = _file_bytes(bundle)
    second = recorder.record_formal_target(
        ROOT,
        bundle_root=bundle,
        require_clean_repository=False,
    )
    assert second.outcome == "existing_current"
    assert second.exit_code == 2
    assert _file_bytes(bundle) == before


def test_allowlist_and_not_qualified_results_have_no_fake_identities(
    bound_target, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scope = recorder.record_formal_target(
        ROOT,
        item_id="en-us/api-management",
        bundle_root=tmp_path / "scope",
        require_clean_repository=False,
    )
    assert scope.exit_code == 2
    assert scope.outcome == "scope_guard"
    assert scope.evidence_path is None
    assert dict(scope.console_fields())["evidence_semantic_sha256"] == "N/A"

    _patch_target(monkeypatch, bound_target)
    monkeypatch.setattr(
        recorder,
        "qualify_bound_target",
        lambda target: ProfileQualification(
            qualified=False,
            claim="independent_source_content_fidelity",
            profile_identity=target.profile_identity,
            reason="controlled unsupported family",
        ),
    )
    unqualified = recorder.record_formal_target(
        ROOT,
        bundle_root=tmp_path / "unqualified",
        require_clean_repository=False,
    )
    assert unqualified.exit_code == 2
    assert unqualified.outcome == "not_qualified"
    assert unqualified.verdict is None
    assert unqualified.evidence_path is None
    assert not (tmp_path / "unqualified").exists()


def test_fatal_binding_and_missing_verify_have_no_bundle_identities(
    bound_target, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        recorder,
        "bind_formal_target",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            FormalBindingError("controlled_binding_failure", "binding drift")
        ),
    )
    fatal = recorder.record_formal_target(
        ROOT,
        bundle_root=tmp_path / "fatal",
        require_clean_repository=False,
    )
    assert fatal.exit_code == 1
    assert fatal.code == "controlled_binding_failure"
    assert fatal.evidence_semantic_sha256 is None

    _patch_target(monkeypatch, bound_target)
    missing = recorder.verify_formal_target(
        ROOT, bundle_root=tmp_path / "missing"
    )
    assert missing.exit_code == 1
    assert missing.code == "canonical_bundle_missing"
    assert missing.review_path is None


def test_stale_or_corrupt_existing_bundle_is_never_repaired(
    bound_target, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_target(monkeypatch, bound_target)
    bundle = tmp_path / "bundle"
    recorded = recorder.record_formal_target(
        ROOT,
        bundle_root=bundle,
        require_clean_repository=False,
    )
    assert recorded.exit_code == 0
    fragment = bundle / "fragments/state-001.source.html.txt"
    fragment.write_text("corrupt", encoding="utf-8")
    corrupt_bytes = _file_bytes(bundle)
    repeated = recorder.record_formal_target(
        ROOT,
        bundle_root=bundle,
        require_clean_repository=False,
    )
    assert repeated.exit_code == 1
    assert repeated.outcome == "stale_or_corrupt"
    assert repeated.code == "canonical_bundle_stale_or_corrupt"
    assert _file_bytes(bundle) == corrupt_bytes


def test_closed_world_extra_file_makes_existing_bundle_corrupt(
    bound_target, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_target(monkeypatch, bound_target)
    bundle = tmp_path / "bundle"
    assert recorder.record_formal_target(
        ROOT,
        bundle_root=bundle,
        require_clean_repository=False,
    ).exit_code == 0
    (bundle / "extra.txt").write_text("not closed world", encoding="utf-8")
    result = recorder.verify_formal_target(ROOT, bundle_root=bundle)
    assert result.exit_code == 1
    assert result.outcome == "stale_or_corrupt"
    assert "extra" in result.reason


def test_atomic_build_failure_leaves_no_bundle_or_temporary_directory(
    bound_target, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_target(monkeypatch, bound_target)
    monkeypatch.setattr(
        recorder,
        "build_evidence_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("controlled render failure")
        ),
    )
    bundle = tmp_path / "atomic"
    result = recorder.record_formal_target(
        ROOT,
        bundle_root=bundle,
        require_clean_repository=False,
    )
    assert result.exit_code == 1
    assert result.code == "formal_record_failed"
    assert not bundle.exists()
    assert not list(tmp_path.glob(".atomic.tmp-*"))


def test_record_inside_controlled_run_proves_add_only_inventory(
    bound_target, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "protected.txt").write_text("unchanged", encoding="utf-8")
    controlled = replace(
        bound_target,
        run_dir=run_dir,
        pre_record_inventory=inventory_regular_files(run_dir),
    )
    _patch_target(monkeypatch, controlled)
    result = recorder.record_formal_target(
        ROOT,
        require_clean_repository=False,
    )
    assert result.exit_code == 0
    assert result.inventory_comparison is not None
    assert result.inventory_comparison.valid is True
    assert len(result.inventory_comparison.allowed_additions) == 22
    assert all(
        path.startswith(CANONICAL_BUNDLE_PREFIX.as_posix() + "/")
        for path in result.inventory_comparison.allowed_additions
    )
    assert (run_dir / "protected.txt").read_text(encoding="utf-8") == "unchanged"


def test_script_scope_guard_prints_na_paths_and_exit_two() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/v052_api_management_fidelity.py"),
            "record",
            "--batch-id",
            TARGET_BATCH_ID,
            "--item-id",
            "en-us/api-management",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "outcome=scope_guard" in result.stdout
    assert "evidence_path=N/A" in result.stdout
    assert "review_path=N/A" in result.stdout
