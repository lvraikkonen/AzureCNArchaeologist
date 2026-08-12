from __future__ import annotations

import hashlib
import json
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace

from src.independent_fidelity.v053_recorder import record_target
from src.review.independent_fidelity import build_independent_fidelity_view
from src.review.workbench_server import ReviewWorkbenchRequestHandler


BATCH_ID = "20260811T171630Z-e80afabe"
ITEM_ID = "zh-cn/api-management"


def _mutate_first_scope(repository: Path) -> None:
    run = repository / "runs" / BATCH_ID
    manifest_path = run / "batch-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    binding = manifest["items"][ITEM_ID]["artifacts"]["payload"]
    payload_path = run / binding["path"]
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["contentGroups"][0]["content"] += "<script>alert('escaped')</script>"
    payload_bytes = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    payload_path.write_bytes(payload_bytes)
    binding["sha256"] = hashlib.sha256(payload_bytes).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _view(repository: Path) -> dict:
    run = repository / "runs" / BATCH_ID
    manifest = json.loads(
        (run / "batch-manifest.json").read_text(encoding="utf-8")
    )
    return build_independent_fidelity_view(
        repository,
        run_dir=run,
        batch_id=BATCH_ID,
        item_id=ITEM_ID,
        payload_artifact=manifest["items"][ITEM_ID]["artifacts"]["payload"],
    )


def test_workbench_builds_transient_l3b_view_from_temporary_bundle(
    v053_binding_repository: Path,
) -> None:
    missing = _view(v053_binding_repository)
    assert missing["status"] == "not_recorded"
    assert missing["evidence_identity"] is None
    assert missing["scopes"] == []

    recorded = record_target(
        v053_binding_repository,
        batch_id=BATCH_ID,
        item_id=ITEM_ID,
        require_clean_repository=False,
    )
    assert recorded.outcome == "passed"
    view = _view(v053_binding_repository)
    assert view["status"] == "passed"
    assert view["l3b"]["coverage"] == {
        "required": 5,
        "completed": 5,
        "passed": 5,
        "failed": 0,
        "blocked": 0,
    }
    assert view["evidence_identity"]["path"].endswith(
        "/independent-fidelity/zh-cn/pricing/api-management/evidence.json"
    )
    assert len(view["scopes"]) == 5
    scope = view["scopes"][0]
    assert scope["criteria"]
    assert scope["source_locator"]["boundary"]
    assert "retained_table_ids" in scope and "removed_table_ids" in scope
    assert isinstance(scope["source"], str)
    assert isinstance(scope["expected"], str)
    assert isinstance(scope["payload"], str)
    assert isinstance(scope["diff"], str)


def test_workbench_preserves_negative_text_and_marks_corruption_invalid(
    v053_binding_repository: Path,
) -> None:
    _mutate_first_scope(v053_binding_repository)
    recorded = record_target(
        v053_binding_repository,
        batch_id=BATCH_ID,
        item_id=ITEM_ID,
        require_clean_repository=False,
    )
    assert recorded.outcome == "failed"
    failed = _view(v053_binding_repository)
    assert failed["status"] == "failed"
    assert failed["l3b"]["reason"] == (
        "Canonical Evidence contains 1 failed scope(s) and 0 blocked scope(s)."
    )
    failed_scope = next(
        scope for scope in failed["scopes"] if scope["verdict"] == "failed"
    )
    assert "<script>alert('escaped')</script>" in failed_scope["payload"]
    assert "comparison differs" in failed_scope["reason"]

    fragment = (
        v053_binding_repository
        / "runs"
        / BATCH_ID
        / "independent-fidelity/zh-cn/pricing/api-management/fragments"
        / "scope-001.payload.html.txt"
    )
    fragment.write_text("corrupt", encoding="utf-8")
    invalid = _view(v053_binding_repository)
    assert invalid["status"] == "invalid"
    assert invalid["evidence_identity"] is None
    assert invalid["scopes"] == []


def _handler(path: str, service: object) -> ReviewWorkbenchRequestHandler:
    handler = object.__new__(ReviewWorkbenchRequestHandler)
    headers = Message()
    headers["Host"] = "127.0.0.1:8765"
    headers["Origin"] = "http://127.0.0.1:3000"
    headers["Authorization"] = "Bearer test-token"
    handler.headers = headers
    handler.path = path
    handler.server = SimpleNamespace(
        server_address=("127.0.0.1", 8765),
        dashboard_origin="http://127.0.0.1:3000",
        token="test-token",
        selection=SimpleNamespace(batch_ids=(BATCH_ID,), history_index=None),
        service=service,
    )
    handler.sent = None
    handler._send_json = lambda value, status=HTTPStatus.OK: setattr(
        handler, "sent", (status, value)
    )
    return handler


def test_independent_fidelity_bridge_route_is_get_only() -> None:
    expected = {"schema_version": "1.0", "status": "not_recorded"}
    service = SimpleNamespace(
        get_independent_fidelity=lambda *args, **kwargs: expected
    )
    path = (
        f"/v1/batches/{BATCH_ID}/items/zh-cn/api-management/"
        "independent-fidelity"
    )
    get_handler = _handler(path, service)
    get_handler.do_GET()
    assert get_handler.sent == (HTTPStatus.OK, expected)

    post_handler = _handler(path, service)
    post_handler.do_POST()
    assert post_handler.sent[0] == HTTPStatus.NOT_FOUND
    assert post_handler.sent[1]["error"]["code"] == "not_found"
