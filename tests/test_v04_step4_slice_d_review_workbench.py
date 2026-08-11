from __future__ import annotations

import json
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.review.service import ReviewDecisionRequest
from src.review.workbench import ReviewWorkbenchError, ReviewWorkbenchService
from src.review.workbench_server import (
    ReviewWorkbenchRequestHandler,
)
from tests.test_v04_step4_slice_c_review_service import (
    FIXED_NOW,
    _approve_request,
    _review_state_id,
    _reviewable_run,
)
from tests.test_v04_step4_slice_b_runtime import BATCH_ID, ROOT


SCHEMA_PATHS = {
    "projection": "schemas/dashboard-review-workbench-projection-1.0.schema.json",
    "evidence": "schemas/dashboard-review-item-evidence-1.0.schema.json",
    "history": "schemas/dashboard-review-history-index-1.0.schema.json",
}


def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((ROOT / SCHEMA_PATHS[name]).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _workbench(tmp_path: Path) -> tuple[ReviewWorkbenchService, Any, Any, dict[str, Any]]:
    review, store, item, plan = _reviewable_run(tmp_path)
    return (
        ReviewWorkbenchService(ROOT, review_service=review, now=lambda: FIXED_NOW),
        store,
        item,
        plan,
    )


def test_workbench_projection_is_closed_world_and_derives_release_readiness(
    tmp_path: Path,
) -> None:
    workbench, store, item, plan = _workbench(tmp_path)

    pending = workbench.build_projection(BATCH_ID)
    _validator("projection").validate(pending)
    assert pending["summary"]["items"]["pending"] == 1
    assert pending["summary"]["items"]["release_ready_count"] == 0
    assert pending["items"][0]["release_ready"] is False

    before = store.read_manifest(BATCH_ID)
    assert before["release_manifests"] == []
    assert before["publication_receipts"] == []
    workbench.review.decide(_approve_request(store, item, _review_state_id(plan)))

    approved = workbench.build_projection(BATCH_ID)
    _validator("projection").validate(approved)
    assert approved["summary"]["items"]["approved"] == 1
    assert approved["summary"]["items"]["release_ready_count"] == 1
    assert approved["summary"]["products"]["release_ready_count"] == 1
    after = store.read_manifest(BATCH_ID)
    assert after["release_manifests"] == []
    assert after["publication_receipts"] == []

    approved["unexpected"] = True
    with pytest.raises(Exception, match="Additional properties"):
        _validator("projection").validate(approved)


def test_workbench_projection_exposes_source_warning_accounting(
    tmp_path: Path,
) -> None:
    review, store, item, _ = _reviewable_run(
        tmp_path,
        validation_profile_id="v0.4-validation-p3-successor",
        source_findings=[{
            "code": "SOURCE_CHARSET_DECLARATION_NOT_UTF8",
            "message": "Source charset declaration is advisory.",
            "path": "$.fixture",
            "severity": "finding",
            "disposition": "unresolved",
        }],
    )
    workbench = ReviewWorkbenchService(ROOT, review_service=review, now=lambda: FIXED_NOW)

    projection = workbench.build_projection(BATCH_ID)
    _validator("projection").validate(projection)
    assert projection["summary"]["items"]["source_warning_count"] == 1
    assert projection["summary"]["items"]["approval_blocked_count"] == 0
    assert projection["items"][0]["source_warning"] is True

    evidence = workbench.get_item_evidence(
        BATCH_ID,
        language=item.language,
        resource_key=item.resource_key,
    )
    _validator("evidence").validate(evidence)
    assert evidence["source_quality_findings"][0]["classification"] == "advisory"


def test_item_evidence_exposes_supersession_history_without_scanning(
    tmp_path: Path,
) -> None:
    workbench, store, item, plan = _workbench(tmp_path)
    first = workbench.review.decide(_approve_request(store, item, _review_state_id(plan)))
    second = workbench.review.decide(
        ReviewDecisionRequest(
            batch_id=BATCH_ID,
            item_id=item.item_id,
            expected_revision=store.read_manifest(BATCH_ID)["revision"],
            reviewer="reviewer@example.com",
            verdict="rejected",
            reason="needs_clarification",
            notes="Fixture rejection.",
            inspected_states=(
                {
                    "scope": "interactive_state",
                    "state_id": plan["state_universe"]["states"][0]["state_id"],
                },
            ),
        )
    )

    evidence = workbench.get_item_evidence(
        BATCH_ID,
        language=item.language,
        resource_key=item.resource_key,
    )
    _validator("evidence").validate(evidence)
    assert evidence["decisions"]["current"]["decision_id"] == second.decision_id
    assert [
        decision["decision_id"] for decision in evidence["decisions"]["history"]
    ] == [second.decision_id, first.decision_id]
    assert evidence["manual_preview"]["status"] == "unavailable"

    (store.run_dir(BATCH_ID) / first.decision_path).unlink()
    with pytest.raises(ReviewWorkbenchError, match="missing"):
        workbench.get_item_evidence(
            BATCH_ID,
            language=item.language,
            resource_key=item.resource_key,
        )


def test_history_index_is_explicit_and_closed_world(tmp_path: Path) -> None:
    workbench, _, _, _ = _workbench(tmp_path)
    history_path = tmp_path / "history.json"
    history = {
        "schema_version": "1.0",
        "batches": [{"batch_id": BATCH_ID, "label": "fixture"}],
    }
    history_path.write_text(json.dumps(history), encoding="utf-8")

    selection = workbench.selection([BATCH_ID], history_index_path=history_path)
    assert selection.history_index == history
    _validator("history").validate(history)

    drifted = {
        "schema_version": "1.0",
        "batches": [{"batch_id": "20260803T120001Z-feedface"}],
    }
    history_path.write_text(json.dumps(drifted), encoding="utf-8")
    with pytest.raises(ReviewWorkbenchError, match="not in the explicit allowlist"):
        workbench.selection([BATCH_ID], history_index_path=history_path)

    drifted["unexpected"] = True
    with pytest.raises(Exception, match="Additional properties"):
        _validator("history").validate(drifted)


def _handler(headers: dict[str, str]) -> Any:
    handler = object.__new__(ReviewWorkbenchRequestHandler)
    message = Message()
    for key, value in headers.items():
        message[key] = value
    handler.headers = message
    handler.server = SimpleNamespace(
        server_address=("127.0.0.1", 8765),
        dashboard_origin="http://127.0.0.1:3000",
        token="test-token",
    )
    handler.sent = None
    handler._send_json = lambda value, status=HTTPStatus.OK: setattr(
        handler,
        "sent",
        (status, value),
    )
    return handler


def test_loopback_bridge_requires_origin_host_and_bearer_token() -> None:
    valid = _handler({
        "Host": "127.0.0.1:8765",
        "Origin": "http://127.0.0.1:3000",
        "Authorization": "Bearer test-token",
    })
    assert valid._validate_host_and_origin() is True
    assert valid._validate_authorization() is True

    bad_origin = _handler({
        "Host": "127.0.0.1:8765",
        "Origin": "http://evil.invalid",
        "Authorization": "Bearer test-token",
    })
    assert bad_origin._validate_host_and_origin() is False
    assert bad_origin.sent[0] == HTTPStatus.FORBIDDEN
    assert bad_origin.sent[1]["error"]["code"] == "invalid_origin"

    bad_token = _handler({
        "Host": "127.0.0.1:8765",
        "Origin": "http://127.0.0.1:3000",
        "Authorization": "Bearer wrong",
    })
    assert bad_token._validate_authorization() is False
    assert bad_token.sent[0] == HTTPStatus.UNAUTHORIZED

    request = ReviewWorkbenchRequestHandler._decision_request(
        batch_id=BATCH_ID,
        item_id="zh-cn/fixture",
        document={
            "expected_revision": 4,
            "reviewer": "reviewer@example.com",
            "verdict": "approved",
            "reason": None,
            "notes": "",
            "inspected_states": [{"scope": "interactive_state", "state_id": "a" * 64}],
        },
    )
    assert request.item_id == "zh-cn/fixture"
    with pytest.raises(ReviewWorkbenchError, match="Unknown decision request field"):
        ReviewWorkbenchRequestHandler._decision_request(
            batch_id=BATCH_ID,
            item_id="zh-cn/fixture",
            document={
                "expected_revision": 4,
                "reviewer": "reviewer@example.com",
                "verdict": "approved",
                "reason": None,
                "notes": "",
                "inspected_states": [],
                "path": "../batch-manifest.json",
            },
        )
