from __future__ import annotations

import copy
import json
from argparse import Namespace
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from src.content_sampling.artifacts import artifact_json_sha256
from src.content_sampling.state_sampler import build_sampling_plan
from src.core.canonical_identity import validation_evidence_sha256
from src.pipeline.cli_commands import (
    pipeline_review_decide_command,
    pipeline_review_list_command,
)
from src.pipeline.models import BatchItem, summarize_batch_manifest
from src.pipeline.state_store import ManifestConflictError, RepositoryLock
from src.review.contracts import (
    classify_source_quality_findings,
    evaluate_source_findings,
    source_approval_preconditions,
)
from src.review.service import (
    ReviewDecisionRequest,
    ReviewService,
    ReviewServiceError,
)
from tests.test_v04_step4_slice_b_runtime import (
    BATCH_ID,
    HEX,
    ROOT,
    _evidence,
    _item,
    _reachability,
    _state_store_with_run,
    _validation_projection,
)


FIXED_NOW = "2026-08-03T12:45:00Z"


def _source_finding() -> dict[str, str]:
    return {
        "code": "SOURCE_DEFECT",
        "message": "Source markup requires upstream review.",
        "path": "$.contentGroups",
        "severity": "finding",
        "disposition": "unresolved",
    }


def _finding_policy() -> dict[str, object]:
    return json.loads(
        (ROOT / "data/configs/finding-code-policies/v0.4-p4.json").read_text(
            encoding="utf-8"
        )
    )


def _with_source_findings(
    validation: dict[str, Any],
    findings: list[dict[str, str]],
) -> dict[str, Any]:
    result = copy.deepcopy(validation)
    if result["schema_version"] == "2.1":
        classified = classify_source_quality_findings(findings, _finding_policy())
        result["evidence"]["source_quality_findings"] = classified
        result["evidence"]["approval_preconditions"]["source"] = (
            evaluate_source_findings(classified, _finding_policy()).to_dict()
        )
    else:
        result["evidence"]["source_quality_findings"] = findings
        result["evidence"]["approval_preconditions"]["source"] = (
            source_approval_preconditions(findings).to_dict()
        )
    result["evidence_sha256"] = validation_evidence_sha256(result)
    return result


def _reviewable_run(
    tmp_path: Path,
    *,
    source_findings: list[dict[str, str]] | None = None,
    validation_profile_id: str = "v0.4-validation-p3",
    item: BatchItem | None = None,
) -> tuple[ReviewService, Any, BatchItem, dict[str, Any]]:
    item = item or _item()
    store, frozen = _state_store_with_run(
        tmp_path,
        validation_profile_id=validation_profile_id,
        item=item,
    )
    criteria = [[("region", f"region-{index}")] for index in range(18)]
    from tests.test_v04_step4_slice_b_runtime import _sampling_profile_identity

    sampling_plan = build_sampling_plan(
        item_id=item.item_id,
        strategy=item.strategy,
        source_sha256=HEX["source"],
        source_reachability=_reachability(
            criteria,
            strategy=item.strategy,
            default_index=4,
        ),
        content_sampling_profile=_sampling_profile_identity(),
    )

    with RepositoryLock(store.lock_root, batch_id=BATCH_ID, command="slice-c-test"):
        manifest = store.read_manifest(BATCH_ID)
        manifest_item = manifest["items"][item.item_id]
        plan_path = manifest_item["artifacts"]["sampling_plan"]["path"]
        store.write_step4_artifact(
            BATCH_ID,
            "sampling_plan",
            sampling_plan,
            relative_path=plan_path,
        )
        evidence = _evidence(
            frozen=frozen,
            manifest_item=manifest_item,
            sampling_plan=sampling_plan,
        )
        evidence_path = manifest_item["artifacts"][
            "sampled_content_evidence"
        ]["path"]
        store.write_step4_artifact(
            BATCH_ID,
            "sampled_content_evidence",
            evidence,
            relative_path=evidence_path,
        )
        validation = _validation_projection(
            frozen=frozen,
            evidence=evidence,
            evidence_path=evidence_path,
        )
        if source_findings:
            validation = _with_source_findings(validation, source_findings)
        source_preconditions = validation["evidence"]["approval_preconditions"][
            "source"
        ]
        store.write_projection(
            BATCH_ID,
            "validation",
            validation,
            relative_path=manifest_item["artifacts"]["validation"]["path"],
        )
        validation_sha = artifact_json_sha256(validation)
        plan_sha = artifact_json_sha256(sampling_plan)
        evidence_sha = artifact_json_sha256(evidence)

        def mark_reviewable(value: dict[str, Any]) -> None:
            current = value["items"][item.item_id]
            current["status"].update({
                "execution": "succeeded",
                "validation": "passed",
                "review": "pending",
                "evidence_binding": "not_applicable",
                "approval_eligibility": (
                    "eligible"
                    if source_preconditions["eligible"]
                    else "blocked"
                ),
            })
            current["artifacts"]["payload"]["sha256"] = HEX["payload"]
            current["artifacts"]["sampling_plan"]["sha256"] = plan_sha
            current["artifacts"]["sampled_content_evidence"]["sha256"] = evidence_sha
            current["artifacts"]["validation"]["sha256"] = validation_sha
            value["status"] = "completed"
            value["summary"] = summarize_batch_manifest(value)

        store.update_manifest(
            BATCH_ID,
            mark_reviewable,
            expected_revision=manifest["revision"],
            changed_item_ids=(item.item_id,),
        )

    return (
        ReviewService(ROOT, state_store=store, now=lambda: FIXED_NOW),
        store,
        item,
        sampling_plan,
    )


def _review_state_id(plan: dict[str, Any]) -> str:
    selected = {
        state["state_id"]
        for state in plan["selected_states"]
    }
    for state in plan["state_universe"]["states"]:
        if state["state_id"] not in selected:
            return state["state_id"]
    return plan["state_universe"]["states"][0]["state_id"]


def _approve_request(
    store: Any,
    item: BatchItem,
    state_id: str,
) -> ReviewDecisionRequest:
    return ReviewDecisionRequest(
        batch_id=BATCH_ID,
        item_id=item.item_id,
        expected_revision=store.read_manifest(BATCH_ID)["revision"],
        reviewer=" reviewer@example.com ",
        verdict="approved",
        inspected_states=(
            {"scope": "page_global"},
            {"scope": "interactive_state", "state_id": state_id},
        ),
    )


def test_review_service_approves_reachable_state_and_writes_queue_2(
    tmp_path: Path,
) -> None:
    service, store, item, plan = _reviewable_run(tmp_path)
    inspected_state = _review_state_id(plan)

    result = service.decide(_approve_request(store, item, inspected_state))

    assert result.review == "approved"
    assert result.evidence_binding == "bound"
    assert result.approval_eligibility == "eligible"
    manifest = store.read_manifest(BATCH_ID)
    current = manifest["items"][item.item_id]
    assert current["artifacts"]["current_review_decision"] == {
        "path": result.decision_path,
        "sha256": result.decision_sha256,
    }
    decision = store.read_review_decision(
        BATCH_ID,
        relative_path=result.decision_path,
    )
    assert decision["reviewer"] == "reviewer@example.com"
    assert decision["inspected_states"][1]["state_id"] == inspected_state

    queue = service.list_items(BATCH_ID, status="all")
    assert queue["schema_version"] == "2.0"
    assert queue["summary"]["approved"] == 1
    assert queue["summary"]["approval_eligible"] == 1
    assert queue["items"][0]["inspection"]["state_universe"] == (
        plan["state_universe"]["states"]
    )


def test_review_service_approves_historical_resource_key(tmp_path: Path) -> None:
    historical_item = replace(
        _item(),
        resource_key="sla-sql-data--v1-5",
        product_key="sla-sql-data",
        resource_kind="historical_version",
        normalized_path=(
            "data/prod-html/zh-cn/SupportArticles/SLA/"
            "sla-sql-data--v1-5.html"
        ),
        output_path=(
            "outputs/zh-cn/SupportArticles/SLA/sla-sql-data--v1-5.json"
        ),
        diagnostic_path=(
            "diagnostics/zh-cn/SupportArticles/SLA/"
            "sla-sql-data--v1-5.sidecar.json"
        ),
        validation_path=(
            "validation/zh-cn/SupportArticles/SLA/"
            "sla-sql-data--v1-5.validation.json"
        ),
        slug="sla-sql-data-v1-5",
        version_key="v1-5",
        version_label="1.5",
    )
    service, store, item, plan = _reviewable_run(
        tmp_path,
        item=historical_item,
    )

    result = service.decide(
        _approve_request(store, item, _review_state_id(plan))
    )

    assert result.review == "approved"
    assert result.item_id == "zh-cn/sla-sql-data--v1-5"
    assert result.decision_path.startswith(
        "review/decisions/zh-cn/sla-sql-data--v1-5/"
    )
    decision = store.read_review_decision(
        BATCH_ID,
        relative_path=result.decision_path,
    )
    assert decision["resource_key"] == "sla-sql-data--v1-5"


def test_rejected_decision_replaces_current_decision_with_supersession(
    tmp_path: Path,
) -> None:
    service, store, item, plan = _reviewable_run(tmp_path)
    first = service.decide(
        _approve_request(store, item, _review_state_id(plan))
    )
    second = service.decide(
        ReviewDecisionRequest(
            batch_id=BATCH_ID,
            item_id=item.item_id,
            expected_revision=store.read_manifest(BATCH_ID)["revision"],
            reviewer="reviewer@example.com",
            verdict="rejected",
            reason="validator_defect",
            notes="Comparison needs validator follow-up.",
            inspected_states=(
                {
                    "scope": "interactive_state",
                    "state_id": plan["state_universe"]["states"][0]["state_id"],
                },
            ),
        )
    )

    assert second.review == "rejected"
    decision = store.read_review_decision(
        BATCH_ID,
        relative_path=second.decision_path,
    )
    assert decision["supersedes_decision_id"] == first.decision_id
    assert decision["reason"] == "validator_defect"
    assert store.read_manifest(BATCH_ID)["items"][item.item_id]["status"][
        "review"
    ] == "rejected"


def test_source_findings_block_approval_but_allow_rejection(tmp_path: Path) -> None:
    service, store, item, plan = _reviewable_run(
        tmp_path,
        source_findings=[_source_finding()],
    )
    state_id = plan["state_universe"]["states"][0]["state_id"]

    with pytest.raises(ReviewServiceError) as caught:
        service.decide(_approve_request(store, item, state_id))
    assert caught.value.code == "approval_not_eligible"

    rejected = service.decide(
        ReviewDecisionRequest(
            batch_id=BATCH_ID,
            item_id=item.item_id,
            expected_revision=store.read_manifest(BATCH_ID)["revision"],
            reviewer="reviewer@example.com",
            verdict="rejected",
            reason="upstream_source",
            inspected_states=(
                {"scope": "interactive_state", "state_id": state_id},
            ),
        )
    )
    assert rejected.review == "rejected"
    queue = service.list_items(BATCH_ID, status="all")
    assert queue["summary"]["approval_blocked_count"] == 1
    assert queue["summary"]["source_warning_count"] == 0
    assert queue["items"][0]["approval_blockers"][0]["code"] == (
        "unresolved_source_quality_finding"
    )
    assert queue["items"][0]["approval_blocked"] is True


def test_successor_advisory_finding_is_eligible_before_and_after_review(
    tmp_path: Path,
) -> None:
    service, store, item, plan = _reviewable_run(
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

    queue = service.list_items(BATCH_ID, status="all")
    assert queue["items"][0]["status"]["approval_eligibility"] == "eligible"
    assert queue["items"][0]["approval_blockers"] == []
    assert queue["summary"]["source_warning_count"] == 1
    assert queue["summary"]["approval_blocked_count"] == 0
    assert queue["items"][0]["source_warning"] is True
    assert queue["items"][0]["source_quality_findings"][0]["code"] == (
        "SOURCE_CHARSET_DECLARATION_NOT_UTF8"
    )
    assert queue["items"][0]["source_quality_findings"][0]["classification"] == (
        "advisory"
    )

    result = service.decide(
        _approve_request(store, item, _review_state_id(plan))
    )

    assert result.review == "approved"
    assert result.approval_eligibility == "eligible"
    assert result.source_warnings[0]["code"] == "SOURCE_CHARSET_DECLARATION_NOT_UTF8"
    decision = store.read_review_decision(
        BATCH_ID,
        relative_path=result.decision_path,
    )
    validation_ref = service.evidence_snapshot(BATCH_ID, item.item_id).validation
    assert decision["bindings"]["validation_evidence_sha256"] == (
        validation_ref["evidence_sha256"]
    )


def test_lifecycle_after_validation_preserves_exact_and_marks_drift_stale(
    tmp_path: Path,
) -> None:
    service, store, item, plan = _reviewable_run(tmp_path)
    service.decide(_approve_request(store, item, _review_state_id(plan)))
    manifest = store.read_manifest(BATCH_ID)
    current = manifest["items"][item.item_id]
    validation = store.read_projection(
        BATCH_ID,
        "validation",
        relative_path=current["artifacts"]["validation"]["path"],
    )

    exact = service.lifecycle_after_validation(
        batch_id=BATCH_ID,
        item=item,
        manifest_item=current,
        validation_projection=validation,
    )
    assert exact == {
        "review": "approved",
        "evidence_binding": "bound",
        "approval_eligibility": "eligible",
    }

    drifted = copy.deepcopy(current)
    drifted["artifacts"]["validation"]["sha256"] = "9" * 64
    stale = service.lifecycle_after_validation(
        batch_id=BATCH_ID,
        item=item,
        manifest_item=drifted,
        validation_projection=validation,
    )
    assert stale == {
        "review": "pending",
        "evidence_binding": "stale",
        "approval_eligibility": "eligible",
    }


def test_revision_conflict_happens_before_decision_file_is_written(
    tmp_path: Path,
) -> None:
    service, store, item, plan = _reviewable_run(tmp_path)
    request = _approve_request(store, item, _review_state_id(plan))
    stale = ReviewDecisionRequest(
        **{
            **request.__dict__,
            "expected_revision": request.expected_revision - 1,
        }
    )

    with pytest.raises(ManifestConflictError):
        service.decide(stale)

    decisions = list((store.run_dir(BATCH_ID) / "review" / "decisions").glob("**/*.json"))
    assert decisions == []


def test_review_cli_list_and_decide_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    service, store, item, plan = _reviewable_run(tmp_path)
    runs_dir = store.runs_dir
    list_code = pipeline_review_list_command(
        Namespace(
            batch_id=BATCH_ID,
            runs_dir=runs_dir,
            status="pending",
            item_id=None,
            json=True,
        )
    )
    assert list_code == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["schema_version"] == "2.0"
    assert listed["summary"]["pending"] == 1

    state_id = plan["state_universe"]["states"][0]["state_id"]
    decide_code = pipeline_review_decide_command(
        Namespace(
            batch_id=BATCH_ID,
            runs_dir=runs_dir,
            item_id=item.item_id,
            expected_revision=str(store.read_manifest(BATCH_ID)["revision"]),
            reviewer="reviewer@example.com",
            verdict="approved",
            reason=None,
            notes="",
            full_content=False,
            inspect_state=[state_id],
            inspect_page_global=True,
            json=True,
        )
    )
    assert decide_code == 0
    decided = json.loads(capsys.readouterr().out)
    assert decided["review"] == "approved"


def test_review_cli_parameter_errors_return_two(capsys: pytest.CaptureFixture[str]) -> None:
    code = pipeline_review_decide_command(
        Namespace(
            batch_id=BATCH_ID,
            runs_dir="runs",
            item_id="zh-cn/fixture",
            expected_revision="not-an-int",
            reviewer="reviewer@example.com",
            verdict="approved",
            reason=None,
            notes="",
            full_content=False,
            inspect_state=None,
            inspect_page_global=False,
            json=False,
        )
    )

    assert code == 2
    assert "ARGUMENT_ERROR" in capsys.readouterr().err
