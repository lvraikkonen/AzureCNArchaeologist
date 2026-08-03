from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import pytest

from src.content_sampling.artifacts import artifact_json_sha256
from src.content_sampling.projector import PayloadContentProjector, ProjectionError
from src.content_sampling.semantic import diff_document, semantic_fingerprint
from src.content_sampling.state_sampler import TARGET_BUDGET, build_sampling_plan
from src.core.canonical_identity import (
    sampled_content_evidence_sha256,
    validation_evidence_sha256,
)
from src.core.cms_state_contract import CmsState
from src.core.product_catalog import sha256_file
from src.core.source_reachability import (
    ReachabilitySourceEvidence,
    ReachableCmsState,
    SourceReachability,
)
from src.core.validation_context import (
    CONTENT_SAMPLING_PROFILE_SPEC,
    ValidationContextRegistry,
)
from src.pipeline.models import BatchItem, InputManifest, PipelinePlan
from src.pipeline.state_store import (
    RepositoryLock,
    RepositoryLockError,
    StateStoreError,
    StateStore,
)
from src.review.contracts import (
    machine_approval_preconditions,
    source_approval_preconditions,
)


ROOT = Path(__file__).resolve().parents[1]
BATCH_ID = "20260803T120000Z-deadbeef"
CREATED_AT = "2026-08-03T12:00:00Z"
HEX = {
    "config": "1" * 64,
    "source": "2" * 64,
    "normalized": "3" * 64,
    "payload": "4" * 64,
}
FROZEN_PROVENANCE = {
    "schema_version": "1.0",
    "captured_at": CREATED_AT,
    "git_commit": "0" * 40,
    "dirty": False,
    "reproducible": True,
    "worktree_changes": [],
    "worktree_fingerprint": f"sha256:{'0' * 64}",
    "immutable_fingerprint": f"sha256:{'0' * 64}",
    "immutable_files": {},
}


def _sampling_profile_identity() -> dict[str, str]:
    return {
        "id": "v0.4-content-sampling-p3",
        "schema_version": "1.0",
        "path": CONTENT_SAMPLING_PROFILE_SPEC.relative_path,
        "sha256": sha256_file(ROOT / CONTENT_SAMPLING_PROFILE_SPEC.relative_path),
    }


def _source_evidence(region: str | None = None) -> ReachabilitySourceEvidence:
    return ReachabilitySourceEvidence(
        region_value=region,
        region_href=f"#{region}" if region is not None else None,
        software_value=None,
        software_href=None,
        software_panel_id=None,
        software_visible=True,
        category_value=None,
        category_href=None,
        category_panel_id=None,
    )


def _reachability(
    criteria: list[list[tuple[str, str]]],
    *,
    strategy: str,
    default_index: int = 0,
) -> SourceReachability:
    states = tuple(
        ReachableCmsState(
            cms_state=CmsState(tuple(item)),
            state_label_segments=tuple(value for _, value in item),
            mapping_key="/".join(value for _, value in item),
            source_evidence=_source_evidence(
                next((value for key, value in item if key == "region"), None)
            ),
            is_default=index == default_index,
        )
        for index, item in enumerate(criteria)
    )
    return SourceReachability(
        product_key="fixture",
        language="zh-cn",
        source_path="data/source.html",
        normalized_path="data/normalized.html",
        source_sha256=HEX["source"],
        normalized_sha256=HEX["normalized"],
        filter_definitions_union=(),
        ordered_states=states,
        default_state=states[default_index].cms_state,
        suppressed_options=(),
        unreachable_panel_ids=(),
        findings=(),
    )


def _item(strategy: str = "region_filter") -> BatchItem:
    return BatchItem(
        language="zh-cn",
        resource_key="fixture",
        product_key="fixture",
        resource_kind="current",
        page_model="FlexibleContentPage",
        capability_status="supported",
        config_path="data/configs/products/pricing/fixture.json",
        config_sha256=HEX["config"],
        source_availability="available",
        source_path="data/current_prod_html/zh-cn/pricing/details/fixture/index.html",
        source_sha256=HEX["source"],
        normalized_path="data/prod-html/zh-cn/pricing/fixture.html",
        normalized_sha256=HEX["normalized"],
        output_path="outputs/zh-cn/pricing/fixture.json",
        diagnostic_path="diagnostics/zh-cn/pricing/fixture.sidecar.json",
        validation_path="validation/zh-cn/pricing/fixture.validation.json",
        slug="fixture",
        strategy=strategy,
        catalog_categories=("fixture",),
        source_url="https://example.invalid/fixture",
    )


def _state_store_with_run(root: Path) -> tuple[StateStore, dict[str, object]]:
    registry = ValidationContextRegistry(ROOT)
    frozen = registry.freeze()
    item = _item()
    plan = PipelinePlan(
        scope={"kind": "group", "group": "fixture"},
        languages=("zh-cn",),
        items=(item,),
        frozen_inputs={
            "soft_category": {
                "path": "data/configs/soft-category.json",
                "sha256": sha256_file(ROOT / "data/configs/soft-category.json"),
            }
        },
    )
    manifest = InputManifest.from_plan(
        BATCH_ID,
        plan,
        FROZEN_PROVENANCE,
        created_at=CREATED_AT,
        planning=frozen["planning"],
        validation_context=frozen["validation_context"],
    )
    store = StateStore(ROOT, runs_dir=root / "runs")
    store.create_run(manifest)
    return store, frozen


def _coverage_from_plan(plan: dict[str, object]) -> dict[str, object]:
    coverage = dict(plan["coverage"])  # type: ignore[arg-type]
    coverage["seed"] = plan["seed"]
    coverage["strata"] = [
        stratum["stratum_id"] for stratum in plan["strata"]  # type: ignore[index]
    ]
    coverage["selected_state_ids"] = [
        state["state_id"] for state in plan["selected_states"]  # type: ignore[index]
    ]
    return coverage


def _comparison(value: object) -> dict[str, object]:
    fingerprint = semantic_fingerprint(value)
    return {
        "status": "matched",
        "source_fingerprint": fingerprint,
        "payload_fingerprint": fingerprint,
        "diff_reference": None,
    }


def _evidence(
    *,
    frozen: dict[str, object],
    manifest_item: dict[str, object],
    sampling_plan: dict[str, object],
) -> dict[str, object]:
    plan_path = manifest_item["artifacts"]["sampling_plan"]["path"]  # type: ignore[index]
    plan_artifact_sha256 = artifact_json_sha256(sampling_plan)
    coverage = _coverage_from_plan(sampling_plan)
    bindings = {
        "source": {"path": _item().source_path, "sha256": HEX["source"]},
        "normalized_input": {
            "path": _item().normalized_path,
            "sha256": HEX["normalized"],
        },
        "payload": {
            "path": _item().output_path,
            "sha256": HEX["payload"],
        },
        "soft_category": {
            "path": "data/configs/soft-category.json",
            "sha256": sha256_file(ROOT / "data/configs/soft-category.json"),
        },
        "validation_profile": frozen["validation_context"]["validation_profile"],  # type: ignore[index]
        "content_sampling_profile": _sampling_profile_identity(),
        "sampling_plan": {
            "path": plan_path,
            "artifact_sha256": plan_artifact_sha256,
            "plan_sha256": sampling_plan["plan_sha256"],
        },
    }
    samples = [
        {
            "state": copy.deepcopy(state),
            **_comparison({"content": f"<p>{index}</p>", "sharedContent": ""}),
        }
        for index, state in enumerate(sampling_plan["selected_states"])  # type: ignore[index]
    ]
    evidence = {
        "schema_version": "1.0",
        "evidence_sha256": "0" * 64,
        "item_id": "zh-cn/fixture",
        "mode": "stratified_sample",
        "bindings": bindings,
        "coverage": coverage,
        "structure_validation": {
            "status": "passed",
            "universe_count": coverage["universe_count"],
            "checked_count": coverage["universe_count"],
            "errors": [],
        },
        "page_global_comparison": _comparison({"title": "Fixture"}),
        "full_content_comparison": None,
        "samples": samples,
        "errors": [],
        "warnings": [],
    }
    evidence["evidence_sha256"] = sampled_content_evidence_sha256(evidence)
    return evidence


def _validation_projection(
    *,
    frozen: dict[str, object],
    evidence: dict[str, object],
    evidence_path: str,
) -> dict[str, object]:
    coverage = evidence["coverage"]
    evidence_artifact_sha256 = artifact_json_sha256(evidence)
    body = {
        "verdict": "passed",
        "bindings": evidence["bindings"],
        "structure_validation": {
            "status": "passed",
            "checked_count": coverage["universe_count"],  # type: ignore[index]
            "total_count": coverage["universe_count"],  # type: ignore[index]
        },
        "content_validation": {
            "status": "passed",
            "sampled_content_evidence": {
                "path": evidence_path,
                "artifact_sha256": evidence_artifact_sha256,
                "evidence_sha256": evidence["evidence_sha256"],
            },
            "coverage": coverage,
            "claim": "sampled_state_content_consistency",
        },
        "source_quality_findings": [],
        "approval_preconditions": {
            "machine": machine_approval_preconditions("succeeded", "passed").to_dict(),
            "source": source_approval_preconditions([]).to_dict(),
        },
        "errors": [],
        "warnings": [],
    }
    projection = {
        "schema_version": "2.0",
        "batch_id": BATCH_ID,
        "item_id": "zh-cn/fixture",
        "status": "passed",
        "evidence_sha256": "0" * 64,
        "evidence": body,
    }
    projection["evidence_sha256"] = validation_evidence_sha256(projection)
    assert frozen["validation_context"]["validation_profile"] == body["bindings"]["validation_profile"]  # type: ignore[index]
    return projection


def test_region_filter_sampling_is_source_ordered_and_schema_valid() -> None:
    criteria = [
        [("region", f"region-{index}")]
        for index in range(5)
    ]
    plan = build_sampling_plan(
        item_id="zh-cn/fixture",
        strategy="region_filter",
        source_sha256=HEX["source"],
        source_reachability=_reachability(criteria, strategy="region_filter", default_index=2),
        content_sampling_profile=_sampling_profile_identity(),
    )

    assert plan["coverage"] == {
        "mode": "stratified_sample",
        "universe_count": 5,
        "selected_count": 5,
        "untested_count": 0,
        "assurance": "sampled_state_content_consistency",
    }
    assert plan["effective_budget"] == TARGET_BUDGET
    assert plan["selected_states"] == plan["state_universe"]["states"]
    StateStore(ROOT).validate_document(plan, "sampling_plan")


def test_complex_sampling_uses_actual_parent_branches_and_expands_for_forced_coverage() -> None:
    criteria = [
        [("software", f"branch-{index}"), ("tier", "only")]
        for index in range(TARGET_BUDGET + 1)
    ]
    plan = build_sampling_plan(
        item_id="zh-cn/fixture",
        strategy="complex",
        source_sha256=HEX["source"],
        source_reachability=_reachability(criteria, strategy="complex"),
        content_sampling_profile=_sampling_profile_identity(),
    )

    assert len(plan["strata"]) == TARGET_BUDGET + 1
    assert plan["effective_budget"] == TARGET_BUDGET + 1
    assert plan["coverage"]["selected_count"] == TARGET_BUDGET + 1
    assert [
        stratum["criteria"] for stratum in plan["strata"]
    ] == [[["software", f"branch-{index}"]] for index in range(TARGET_BUDGET + 1)]
    StateStore(ROOT).validate_document(plan, "sampling_plan")


def test_sampling_seed_excludes_payload_batch_time_and_process_order() -> None:
    criteria = [[("region", f"region-{index}")] for index in range(18)]
    source = _reachability(criteria, strategy="region_filter", default_index=4)
    first = build_sampling_plan(
        item_id="zh-cn/fixture",
        strategy="region_filter",
        source_sha256=HEX["source"],
        source_reachability=source,
        content_sampling_profile=_sampling_profile_identity(),
    )
    second = build_sampling_plan(
        item_id="zh-cn/fixture",
        strategy="region_filter",
        source_sha256=HEX["source"],
        source_reachability=source,
        content_sampling_profile=_sampling_profile_identity(),
    )
    drifted_source = build_sampling_plan(
        item_id="zh-cn/fixture",
        strategy="region_filter",
        source_sha256="5" * 64,
        source_reachability=source,
        content_sampling_profile=_sampling_profile_identity(),
    )

    assert second == first
    assert first["seed"] != drifted_source["seed"]
    assert first["plan_sha256"] != drifted_source["plan_sha256"]


def test_semantic_fingerprint_normalizes_html_without_hiding_real_content_drift() -> None:
    assert semantic_fingerprint(
        "<DIV class='b a'>&nbsp;Price&nbsp;</DIV><!-- ignored -->"
    ) == semantic_fingerprint('<div class="a b"> Price </div>')

    source = "<table><tr><td>10</td></tr></table>"
    payload = "<table><tr><td>11</td></tr></table>"
    diff = diff_document(
        scope="page-global",
        source_value=source,
        payload_value=payload,
        source_fingerprint=semantic_fingerprint(source),
        payload_fingerprint=semantic_fingerprint(payload),
    )

    assert diff["source_fingerprint"] != diff["payload_fingerprint"]
    assert diff["differences"]


def test_payload_projector_requires_the_exact_selected_state_without_replacement() -> None:
    selected_state = {
        "state_id": "6" * 64,
        "criteria": [["region", "east-china"]],
    }
    payload = {
        "contentGroups": [
            {
                "filterCriteriaJson": json.dumps(
                    [{"filterKey": "region", "matchValues": "north-china"}]
                ),
                "content": "<p>wrong region</p>",
            }
        ]
    }

    with pytest.raises(ProjectionError, match="found 0"):
        PayloadContentProjector.state_content(payload, selected_state)


def test_state_store_writes_p3_step4_artifacts_once_and_validates_hashes() -> None:
    criteria = [[("region", f"region-{index}")] for index in range(3)]
    sampling_plan = build_sampling_plan(
        item_id="zh-cn/fixture",
        strategy="region_filter",
        source_sha256=HEX["source"],
        source_reachability=_reachability(criteria, strategy="region_filter"),
        content_sampling_profile=_sampling_profile_identity(),
    )

    with tempfile.TemporaryDirectory() as directory:
        store, frozen = _state_store_with_run(Path(directory))
        manifest_item = store.read_manifest(BATCH_ID)["items"]["zh-cn/fixture"]
        plan_path = manifest_item["artifacts"]["sampling_plan"]["path"]
        evidence = _evidence(
            frozen=frozen,
            manifest_item=manifest_item,
            sampling_plan=sampling_plan,
        )
        evidence_path = manifest_item["artifacts"]["sampled_content_evidence"]["path"]
        validation = _validation_projection(
            frozen=frozen,
            evidence=evidence,
            evidence_path=evidence_path,
        )

        with pytest.raises(RepositoryLockError):
            store.write_step4_artifact(
                BATCH_ID,
                "sampling_plan",
                sampling_plan,
                relative_path=plan_path,
            )

        with RepositoryLock(store.lock_root, batch_id=BATCH_ID, command="test"):
            stored_plan = store.write_step4_artifact(
                BATCH_ID,
                "sampling_plan",
                sampling_plan,
                relative_path=plan_path,
            )
            assert sha256_file(stored_plan) == artifact_json_sha256(sampling_plan)
            store.write_step4_artifact(
                BATCH_ID,
                "sampling_plan",
                sampling_plan,
                relative_path=plan_path,
            )
            stored_evidence = store.write_step4_artifact(
                BATCH_ID,
                "sampled_content_evidence",
                evidence,
                relative_path=evidence_path,
            )
            assert sha256_file(stored_evidence) == artifact_json_sha256(evidence)
            stored_validation = store.write_projection(
                BATCH_ID,
                "validation",
                validation,
                relative_path=manifest_item["artifacts"]["validation"]["path"],
            )
            assert sha256_file(stored_validation) == artifact_json_sha256(validation)

            drifted_plan = build_sampling_plan(
                item_id="zh-cn/fixture",
                strategy="region_filter",
                source_sha256="5" * 64,
                source_reachability=_reachability(criteria, strategy="region_filter"),
                content_sampling_profile=_sampling_profile_identity(),
            )
            with pytest.raises(StateStoreError, match="differs from deterministic replay"):
                store.write_step4_artifact(
                    BATCH_ID,
                    "sampling_plan",
                    drifted_plan,
                    relative_path=plan_path,
                )
