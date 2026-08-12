from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import src.independent_fidelity.v053_bundle as bundle_module
from src.independent_fidelity.bundle import verify_evidence_bundle
from src.independent_fidelity.v053_bundle import V053BundleError, verify_bundle
from src.independent_fidelity.v053_recorder import record_target, verify_target
from src.independent_fidelity.v053_target import V053BindingError, bind_batch_item


ROOT = Path(__file__).resolve().parents[1]
BATCH_ID = "20260811T171630Z-e80afabe"
ITEM_ID = "zh-cn/api-management"
HISTORICAL_BUNDLE = (
    ROOT
    / "runs"
    / BATCH_ID
    / "independent-fidelity/zh-cn/pricing/api-management"
)


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _mutate_payload(repository: Path, mutate) -> None:
    run = repository / "runs" / BATCH_ID
    manifest_path = run / "batch-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    binding = manifest["items"][ITEM_ID]["artifacts"]["payload"]
    payload_path = run / binding["path"]
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    mutate(payload)
    payload_bytes = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    payload_path.write_bytes(payload_bytes)
    import hashlib

    binding["sha256"] = hashlib.sha256(payload_bytes).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )


def test_generic_manifest_binding_and_canonical_path(
    v053_binding_repository: Path,
) -> None:
    target = bind_batch_item(
        v053_binding_repository, batch_id=BATCH_ID, item_id=ITEM_ID
    )
    assert target.producer_commit == "a" * 40
    assert target.target.page_family == "region_filter"
    assert target.canonical_bundle_root == (
        target.run_dir
        / "independent-fidelity/zh-cn/pricing/api-management"
    )
    assert target.payload_identity.path == (
        f"runs/{BATCH_ID}/outputs/zh-cn/pricing/api-management.json"
    )


def test_record_verify_and_second_record_are_read_only(
    v053_binding_repository: Path,
) -> None:
    first = record_target(
        v053_binding_repository,
        batch_id=BATCH_ID,
        item_id=ITEM_ID,
        require_clean_repository=False,
    )
    assert first.exit_code == 0
    assert first.outcome == "passed"
    assert first.coverage == {
        "required": 5,
        "completed": 5,
        "passed": 5,
        "failed": 0,
        "blocked": 0,
    }
    bundle = Path(first.bundle_path)
    assert not (bundle / "review.html").exists()
    assert len(_files(bundle)) == 21
    assert verify_bundle(v053_binding_repository, bundle)["schema_version"] == "1.1"
    before = _files(bundle)

    verified = verify_target(
        v053_binding_repository, batch_id=BATCH_ID, item_id=ITEM_ID
    )
    assert verified.exit_code == 0
    assert verified.outcome == "passed"
    second = record_target(
        v053_binding_repository,
        batch_id=BATCH_ID,
        item_id=ITEM_ID,
        require_clean_repository=False,
    )
    assert second.outcome == "existing-current/read-only"
    assert second.evidence_semantic_sha256 == first.evidence_semantic_sha256
    assert _files(bundle) == before


@pytest.mark.parametrize(
    ("mutate", "verdict", "count_key"),
    [
        (
            lambda payload: payload["contentGroups"][0].__setitem__(
                "content", payload["contentGroups"][0]["content"] + "<p>wrong</p>"
            ),
            "failed",
            "failed",
        ),
        (
            lambda payload: payload.__setitem__("contentGroups", {}),
            "blocked",
            "blocked",
        ),
    ],
)
def test_negative_bundles_are_immutable(
    v053_binding_repository: Path,
    mutate,
    verdict: str,
    count_key: str,
) -> None:
    _mutate_payload(v053_binding_repository, mutate)
    first = record_target(
        v053_binding_repository,
        batch_id=BATCH_ID,
        item_id=ITEM_ID,
        require_clean_repository=False,
    )
    assert first.exit_code == 2
    assert first.outcome == verdict
    assert first.coverage[count_key] > 0
    bundle = Path(first.bundle_path)
    before = _files(bundle)
    second = record_target(
        v053_binding_repository,
        batch_id=BATCH_ID,
        item_id=ITEM_ID,
        require_clean_repository=False,
    )
    assert second.outcome == "existing-current/read-only"
    assert second.exit_code == 2
    assert second.verdict == verdict
    assert _files(bundle) == before


def test_corrupt_existing_bundle_is_not_repaired(
    v053_binding_repository: Path,
) -> None:
    recorded = record_target(
        v053_binding_repository,
        batch_id=BATCH_ID,
        item_id=ITEM_ID,
        require_clean_repository=False,
    )
    bundle = Path(recorded.bundle_path)
    fragment = bundle / "fragments/scope-001.source.html.txt"
    fragment.write_text("corrupt", encoding="utf-8")
    corrupt = _files(bundle)
    repeated = record_target(
        v053_binding_repository,
        batch_id=BATCH_ID,
        item_id=ITEM_ID,
        require_clean_repository=False,
    )
    assert repeated.exit_code == 1
    assert repeated.outcome == "stale_or_corrupt"
    assert _files(bundle) == corrupt


def test_readable_diff_is_integrity_bound(
    v053_binding_repository: Path,
) -> None:
    recorded = record_target(
        v053_binding_repository,
        batch_id=BATCH_ID,
        item_id=ITEM_ID,
        require_clean_repository=False,
    )
    bundle = Path(recorded.bundle_path)
    diff = bundle / "fragments/scope-001.diff.txt"
    diff.write_text("misleading display diff", encoding="utf-8")
    with pytest.raises(V053BundleError, match="Diff SHA-256 mismatch"):
        verify_bundle(v053_binding_repository, bundle)


def test_fragment_and_bundle_symlinks_are_rejected(
    v053_binding_repository: Path,
) -> None:
    recorded = record_target(
        v053_binding_repository,
        batch_id=BATCH_ID,
        item_id=ITEM_ID,
        require_clean_repository=False,
    )
    bundle = Path(recorded.bundle_path)
    source = bundle / "fragments/scope-001.source.html.txt"
    payload = bundle / "fragments/scope-001.payload.html.txt"
    source.unlink()
    source.symlink_to(payload.name)
    with pytest.raises(V053BundleError, match="symlink"):
        verify_bundle(v053_binding_repository, bundle)

    alias = bundle.parent / "alias"
    alias.symlink_to(bundle, target_is_directory=True)
    with pytest.raises(V053BundleError, match="symlink"):
        verify_bundle(v053_binding_repository, alias)


def test_atomic_failure_never_promotes_partial_bundle(
    v053_binding_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args, **kwargs):
        raise V053BundleError("controlled build failure")

    monkeypatch.setattr(bundle_module, "build_bundle", fail)
    result = record_target(
        v053_binding_repository,
        batch_id=BATCH_ID,
        item_id=ITEM_ID,
        require_clean_repository=False,
    )
    assert result.exit_code == 1
    target = bind_batch_item(
        v053_binding_repository, batch_id=BATCH_ID, item_id=ITEM_ID
    )
    assert not target.canonical_bundle_root.exists()
    assert not list(target.canonical_bundle_root.parent.glob(".*.tmp-*"))


def test_binding_drift_and_non_target_never_create_bundle(
    v053_binding_repository: Path,
) -> None:
    target = bind_batch_item(
        v053_binding_repository, batch_id=BATCH_ID, item_id=ITEM_ID
    )
    source = v053_binding_repository / target.source_identity.path
    source.write_bytes(source.read_bytes() + b"<!-- drift -->")
    result = record_target(
        v053_binding_repository,
        batch_id=BATCH_ID,
        item_id=ITEM_ID,
        require_clean_repository=False,
    )
    assert result.exit_code == 1
    assert result.code == "source_binding_mismatch"
    assert not target.canonical_bundle_root.exists()

    outside = record_target(
        v053_binding_repository,
        batch_id=BATCH_ID,
        item_id="zh-cn/not-a-target",
        require_clean_repository=False,
    )
    assert outside.outcome == "not_target"
    assert outside.evidence_path is None


def test_duplicate_key_manifest_is_not_a_trusted_binding(
    v053_binding_repository: Path,
) -> None:
    manifest = (
        v053_binding_repository / "runs" / BATCH_ID / "input-manifest.json"
    )
    text = manifest.read_text(encoding="utf-8")
    marker = f'  "batch_id": "{BATCH_ID}",\n'
    assert text.count(marker) == 1
    manifest.write_text(text.replace(marker, marker + marker, 1), encoding="utf-8")
    with pytest.raises(V053BindingError) as raised:
        bind_batch_item(
            v053_binding_repository, batch_id=BATCH_ID, item_id=ITEM_ID
        )
    assert raised.value.code == "invalid_bound_json"


def test_historical_v052_bundle_remains_byte_stable_and_readable() -> None:
    before = _files(HISTORICAL_BUNDLE)
    evidence = verify_evidence_bundle(ROOT, HISTORICAL_BUNDLE)
    assert evidence["schema_version"] == "1.0"
    assert evidence["verdict"] == "passed"
    assert _files(HISTORICAL_BUNDLE) == before
