from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

from cli import release_build_command, release_verify_command, upload_command
from src.core.product_catalog import sha256_file
from src.pipeline.models import summarize_batch_manifest
from src.pipeline.state_store import ManifestConflictError, RepositoryLock
from src.release.contracts import (
    derive_publication_receipt_id,
    derive_release_content_sha256,
)
from src.release.service import (
    ReleaseService,
    ReleaseServiceError,
    RemoteBlobIdentity,
)
from src.review.contracts import derive_review_decision_id
from tests import test_v04_step4_slice_b_runtime as slice_b
from tests.test_v04_step4_slice_b_runtime import BATCH_ID, ROOT
from tests.test_v04_step4_slice_c_review_service import (
    _approve_request,
    _review_state_id,
    _reviewable_run,
    _source_finding,
)


FIXED_RELEASE_NOW = "2026-08-03T15:00:00Z"
FIXED_RECEIPT_NOW = "2026-08-03T15:05:00Z"


class FakeBlobTransport:
    def __init__(self, *, fail_after_write: bool = False) -> None:
        self.fail_after_write = fail_after_write
        self.blobs: dict[str, bytes] = {}
        self.calls: list[str] = []

    def upload_or_verify(
        self,
        local_path: Path,
        *,
        blob_name: str,
        expected_sha256: str,
    ) -> RemoteBlobIdentity:
        self.calls.append(blob_name)
        data = local_path.read_bytes()
        actual_sha = hashlib.sha256(data).hexdigest()
        assert actual_sha == expected_sha256
        if blob_name in self.blobs:
            if hashlib.sha256(self.blobs[blob_name]).hexdigest() != expected_sha256:
                raise ReleaseServiceError(
                    "remote_blob_conflict",
                    "existing blob differs",
                )
        else:
            self.blobs[blob_name] = data
            if self.fail_after_write:
                self.fail_after_write = False
                raise ReleaseServiceError(
                    "simulated_upload_failure",
                    "upload interrupted after remote write",
                )
        return RemoteBlobIdentity(
            account_url="https://example.blob.core.windows.net",
            container="cms",
            name=blob_name,
            sha256=expected_sha256,
            content_length=len(data),
            etag=f"etag-{len(data)}",
        )


@pytest.fixture()
def release_id() -> str:
    value = f"pytest-{uuid.uuid4().hex[:8]}"
    yield value
    shutil.rmtree(ROOT / "output" / "releases" / value, ignore_errors=True)
    shutil.rmtree(ROOT / "output" / "pytest-runs" / value, ignore_errors=True)


def _releaseable_run(
    tmp_path: Path,
    *,
    release_id: str,
    validation_profile_id: str = "v0.4-validation-p3",
) -> tuple[ReleaseService, Any, Any, str]:
    payload_bytes = b'{"title":"Release fixture"}\n'
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    runs_root = ROOT / "output" / "pytest-runs" / release_id
    original_payload_sha = slice_b.HEX["payload"]
    slice_b.HEX["payload"] = payload_sha256
    try:
        review, store, item, plan = _reviewable_run(
            runs_root,
            validation_profile_id=validation_profile_id,
        )
    finally:
        slice_b.HEX["payload"] = original_payload_sha
    payload_path = store.run_dir(BATCH_ID) / item.output_path
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_bytes(payload_bytes)
    review.decide(_approve_request(store, item, _review_state_id(plan)))
    service = ReleaseService(
        ROOT,
        runs_dir=store.runs_dir,
        state_store=store,
        review_service=review,
        now=lambda: FIXED_RELEASE_NOW,
    )
    return service, store, item, release_id


def _source_blocked_run_with_forged_approval(
    release_id: str,
) -> tuple[ReleaseService, Any, Any, str]:
    payload_bytes = b'{"title":"Release fixture"}\n'
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    runs_root = ROOT / "output" / "pytest-runs" / release_id
    original_payload_sha = slice_b.HEX["payload"]
    slice_b.HEX["payload"] = payload_sha256
    try:
        review, store, item, plan = _reviewable_run(
            runs_root,
            source_findings=[_source_finding()],
        )
    finally:
        slice_b.HEX["payload"] = original_payload_sha
    payload_path = store.run_dir(BATCH_ID) / item.output_path
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_bytes(payload_bytes)
    snapshot = review.evidence_snapshot(BATCH_ID, item.item_id)
    inspected_state = _review_state_id(plan)
    decision_body: dict[str, Any] = {
        "schema_version": "1.0",
        "decision_id": "0" * 64,
        "batch_id": BATCH_ID,
        "item_id": item.item_id,
        "resource_key": item.resource_key,
        "language": item.language,
        "reviewer": "forged@example.com",
        "decided_at": FIXED_RELEASE_NOW,
        "verdict": "approved",
        "reason": None,
        "notes": "Forged legacy approval for release gate regression.",
        "bindings": snapshot.current_bindings.to_dict(),
        "inspected_states": [
            {"scope": "page_global"},
            {"scope": "interactive_state", "state_id": inspected_state},
        ],
        "supersedes_decision_id": None,
    }
    decision_body["decision_id"] = derive_review_decision_id(decision_body)
    decision_path = (
        Path("review", "decisions", item.language, item.resource_key)
        / f"{decision_body['decision_id']}.json"
    ).as_posix()
    with RepositoryLock(store.lock_root, batch_id=BATCH_ID, command="forge-review"):
        path = store.write_review_decision(
            BATCH_ID,
            decision_body,
            relative_path=decision_path,
        )
        decision_sha256 = sha256_file(path)
        manifest = store.read_manifest(BATCH_ID)

        def forge(value: dict[str, Any]) -> None:
            current = value["items"][item.item_id]
            current["artifacts"]["current_review_decision"] = {
                "path": decision_path,
                "sha256": decision_sha256,
            }
            current["status"]["review"] = "approved"
            current["status"]["evidence_binding"] = "bound"
            current["status"]["approval_eligibility"] = "eligible"
            value["summary"] = summarize_batch_manifest(value)

        store.update_manifest(
            BATCH_ID,
            forge,
            expected_revision=manifest["revision"],
            changed_item_ids=(item.item_id,),
        )
    service = ReleaseService(
        ROOT,
        runs_dir=store.runs_dir,
        state_store=store,
        review_service=review,
        now=lambda: FIXED_RELEASE_NOW,
    )
    return service, store, item, release_id


def _build_release(
    service: ReleaseService,
    store: Any,
    item: Any,
    release_id: str,
) -> Any:
    return service.build_release(
        batch_id=BATCH_ID,
        release_id=release_id,
        item_ids=(item.item_id,),
        expected_revision=store.read_manifest(BATCH_ID)["revision"],
        account_url="https://example.blob.core.windows.net",
        container="cms",
        prefix="prod",
    )


def test_release_build_seals_registered_manifest_and_payload(release_id: str, tmp_path: Path) -> None:
    service, store, item, release_id = _releaseable_run(
        tmp_path,
        release_id=release_id,
    )

    result = _build_release(service, store, item, release_id)

    manifest_path = ROOT / result.release_manifest_path
    release_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert release_manifest["schema_version"] == "1.0"
    assert manifest_path.read_bytes() == json.dumps(
        release_manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    assert result.release_manifest_sha256 == sha256_file(manifest_path)
    assert release_manifest["items"][0]["target_blob"]["name"] == (
        "prod/zh-cn/pricing/fixture.json"
    )
    assert store.read_manifest(BATCH_ID)["items"][item.item_id]["status"][
        "release"
    ] == "released"

    verified = service.verify_release(result.release_manifest_path)
    assert verified.release_seal == result.release_seal
    assert verified.registered


def test_successor_release_builds_manifest_11_and_upload_dry_run(
    release_id: str,
    tmp_path: Path,
) -> None:
    service, store, item, release_id = _releaseable_run(
        tmp_path,
        release_id=release_id,
        validation_profile_id="v0.4-validation-p3-successor",
    )

    result = _build_release(service, store, item, release_id)

    manifest = json.loads(
        (ROOT / result.release_manifest_path).read_text(encoding="utf-8")
    )
    assert manifest["schema_version"] == "1.1"
    assert manifest["validation_profile"]["id"] == (
        "v0.4-validation-p3-successor"
    )
    assert manifest["finding_code_policy_identity"]["id"] == (
        "v0.4-finding-code-policy-p4"
    )
    assert service.verify_release(result.release_manifest_path).registered

    uploaded = service.upload_release(result.release_manifest_path, dry_run=True)
    assert uploaded.dry_run


def test_release_rejects_legacy_approved_item_with_source_findings(
    release_id: str,
    tmp_path: Path,
) -> None:
    service, store, item, release_id = _source_blocked_run_with_forged_approval(
        release_id
    )

    with pytest.raises(ReleaseServiceError) as caught:
        _build_release(service, store, item, release_id)

    assert caught.value.code == "approval_eligibility_mismatch"


def test_release_build_rejects_pending_review_item(release_id: str, tmp_path: Path) -> None:
    payload_bytes = b'{"title":"Release fixture"}\n'
    runs_root = ROOT / "output" / "pytest-runs" / release_id
    original_payload_sha = slice_b.HEX["payload"]
    slice_b.HEX["payload"] = hashlib.sha256(payload_bytes).hexdigest()
    try:
        review, store, item, _plan = _reviewable_run(runs_root)
    finally:
        slice_b.HEX["payload"] = original_payload_sha
    payload_path = store.run_dir(BATCH_ID) / item.output_path
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_bytes(payload_bytes)
    service = ReleaseService(
        ROOT,
        runs_dir=store.runs_dir,
        state_store=store,
        review_service=review,
    )

    with pytest.raises(ReleaseServiceError) as caught:
        _build_release(service, store, item, release_id)
    assert caught.value.code in {
        "missing_current_review_decision",
        "release_item_not_eligible",
    }


def test_release_verify_rejects_payload_drift(release_id: str, tmp_path: Path) -> None:
    service, store, item, release_id = _releaseable_run(
        tmp_path,
        release_id=release_id,
    )
    result = _build_release(service, store, item, release_id)
    manifest = json.loads((ROOT / result.release_manifest_path).read_text(encoding="utf-8"))
    payload_path = ROOT / manifest["items"][0]["payload"]["release_path"]
    payload_path.write_text('{"title":"drifted"}\n', encoding="utf-8")

    with pytest.raises(ReleaseServiceError) as caught:
        service.verify_release(result.release_manifest_path)
    assert caught.value.code == "release_payload_hash_mismatch"


def test_release_content_identity_excludes_release_id_time_and_target(
    release_id: str,
    tmp_path: Path,
) -> None:
    service, store, item, release_id = _releaseable_run(
        tmp_path,
        release_id=release_id,
    )
    result = _build_release(service, store, item, release_id)
    manifest = json.loads((ROOT / result.release_manifest_path).read_text(encoding="utf-8"))
    changed = {
        **manifest,
        "release_id": "another-release",
        "created_at": "2099-01-01T00:00:00Z",
        "target": {
            "account_url": "https://other.blob.core.windows.net",
            "container": "other",
            "prefix": "other",
        },
        "items": [
            {
                **release_item,
                "target_blob": {
                    "container": "other",
                    "name": f"other/{release_item['item_id']}.json",
                },
            }
            for release_item in manifest["items"]
        ],
    }

    assert derive_release_content_sha256(changed) == result.release_content_sha256


def test_upload_failure_after_remote_write_does_not_publish_then_retry_is_idempotent(
    release_id: str,
    tmp_path: Path,
) -> None:
    service, store, item, release_id = _releaseable_run(
        tmp_path,
        release_id=release_id,
    )
    result = _build_release(service, store, item, release_id)
    failing = FakeBlobTransport(fail_after_write=True)

    with pytest.raises(ReleaseServiceError) as caught:
        service.upload_release(
            result.release_manifest_path,
            expected_revision=store.read_manifest(BATCH_ID)["revision"],
            transport=failing,
        )
    assert caught.value.code == "simulated_upload_failure"
    assert store.read_manifest(BATCH_ID)["items"][item.item_id]["status"][
        "publication"
    ] == "not_published"
    assert not (store.run_dir(BATCH_ID) / "publication" / "receipts").exists()

    service = ReleaseService(
        ROOT,
        runs_dir=store.runs_dir,
        state_store=store,
        review_service=service.review,
        now=lambda: FIXED_RECEIPT_NOW,
    )
    uploaded = service.upload_release(
        result.release_manifest_path,
        expected_revision=store.read_manifest(BATCH_ID)["revision"],
        transport=failing,
    )
    assert uploaded.publication_receipt_path
    receipt = store.read_publication_receipt(
        BATCH_ID,
        relative_path=uploaded.publication_receipt_path,
    )
    assert receipt["receipt_id"] == derive_publication_receipt_id(receipt)
    assert store.read_manifest(BATCH_ID)["items"][item.item_id]["status"][
        "publication"
    ] == "published"

    retry = service.upload_release(
        result.release_manifest_path,
        expected_revision=store.read_manifest(BATCH_ID)["revision"],
        transport=failing,
    )
    assert retry.idempotent
    assert retry.publication_receipt_sha256 == uploaded.publication_receipt_sha256


def test_upload_dry_run_never_calls_transport(release_id: str, tmp_path: Path) -> None:
    service, store, item, release_id = _releaseable_run(
        tmp_path,
        release_id=release_id,
    )
    result = _build_release(service, store, item, release_id)
    transport = FakeBlobTransport()

    dry_run = service.upload_release(
        result.release_manifest_path,
        dry_run=True,
        transport=transport,
    )

    assert dry_run.dry_run
    assert transport.calls == []
    assert store.read_manifest(BATCH_ID)["items"][item.item_id]["status"][
        "publication"
    ] == "not_published"


def test_release_cli_build_verify_and_upload_dry_run_json(
    release_id: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    service, store, item, release_id = _releaseable_run(
        tmp_path,
        release_id=release_id,
    )
    runs_dir = store.runs_dir
    build_code = release_build_command(
        Namespace(
            batch_id=BATCH_ID,
            release_id=release_id,
            item_id=[item.item_id],
            expected_revision=str(store.read_manifest(BATCH_ID)["revision"]),
            account_url="https://example.blob.core.windows.net",
            container="cms",
            prefix="prod",
            runs_dir=runs_dir,
            json=True,
        )
    )
    assert build_code == 0
    built = json.loads(capsys.readouterr().out)

    verify_code = release_verify_command(
        Namespace(
            release_manifest=built["release_manifest_path"],
            runs_dir=runs_dir,
            require_batch_reference=True,
            json=True,
        )
    )
    assert verify_code == 0
    verified = json.loads(capsys.readouterr().out)
    assert verified["registered"] is True

    upload_code = upload_command(
        Namespace(
            release_manifest=built["release_manifest_path"],
            expected_revision=None,
            dry_run=True,
            runs_dir=runs_dir,
            json=True,
        )
    )
    assert upload_code == 0
    uploaded = json.loads(capsys.readouterr().out)
    assert uploaded["dry_run"] is True

    assert service.verify_release(built["release_manifest_path"]).registered


def test_upload_requires_current_expected_revision(release_id: str, tmp_path: Path) -> None:
    service, store, item, release_id = _releaseable_run(
        tmp_path,
        release_id=release_id,
    )
    result = _build_release(service, store, item, release_id)

    with pytest.raises(ManifestConflictError):
        service.upload_release(
            result.release_manifest_path,
            expected_revision=store.read_manifest(BATCH_ID)["revision"] - 1,
            transport=FakeBlobTransport(),
        )
