from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from src.core.contract_validator import ContractValidator


ROOT = Path(__file__).resolve().parents[1]
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
FIXED_TIME = "2026-01-01T00:00:00+00:00"


def _artifact(path: str, sha256: str = SHA_A) -> dict[str, str]:
    return {"path": path, "sha256": sha256}


def _strict_projection_summary() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "projection_algorithms": [
            "strict-soft-category-leaf-state-v1"
        ],
        "applicability_configs": [{
            "path": "data/configs/soft-category.json",
            "sha256": SHA_A,
        }],
        "state_count": 1,
        "evidence_sha256s": [SHA_B],
        "aggregate_sha256": SHA_C,
    }


def _shared_projection_summary() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "projection_algorithms": [
            "exact-table-id-nearest-scroll-table-v1"
        ],
        "applicability_configs": [{
            "path": "data/configs/soft-category.json",
            "sha256": SHA_A,
        }],
        "evidence_sha256s": [SHA_B],
        "aggregate_sha256": SHA_C,
    }


def _strict_projection_failure(
    phase: str = "attach",
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "code": "soft_category_fixture_failure",
        "phase": phase,
        "state_scope": {
            "region": "north-china3",
            "software": "fixture-software",
            "source_panel_id": "tabContent1",
        },
        "configuration": {
            "path": "data/configs/soft-category.json",
            "sha256": SHA_A,
        },
        "source_inventory": {
            "source_panel_id": "tabContent1",
            "source_table_count": 1,
            "source_idless_table_count": 0,
            "source_table_ids": ["fixture-table"],
            "source_html_sha256": SHA_B,
        },
        "evidence": {
            "fixture": True,
        },
    }


def _sidecar(
    strategy_type: str,
    page_model: str,
    *,
    execution: str = "succeeded",
    validation: str = "passed",
    error: dict[str, str] | None = None,
) -> dict[str, Any]:
    selected = strategy_type != "not_selected"
    strategy: dict[str, Any] = {
        "type": strategy_type,
        "processor": (
            "FixtureProcessor" if selected else "not_selected"
        ),
    }
    if selected:
        strategy.update({
            "complexity_score": 0.5,
            "features": ["fixture"],
        })
    return {
        "schema_version": "1.2",
        "product_key": "fixture-product",
        "resource": {
            "kind": "current",
            "resource_key": "fixture-product",
            "slug": "fixture-product",
            "version_key": None,
            "version_label": None,
        },
        "language": "zh-cn",
        "page_model": page_model,
        "contract": {
            "name": page_model,
            "version": (
                "1.1"
                if page_model == "FlexibleContentPage"
                else "1.0"
            ),
            "schema_sha256": SHA_A,
        },
        "source": _artifact("data/current_prod_html/fixture.html"),
        "normalized_input": _artifact(
            "data/prod-html/fixture.html"
        ),
        "payload": (
            _artifact("output/fixture.json", SHA_B)
            if execution == "succeeded"
            else None
        ),
        "strategy": strategy,
        "status": {
            "execution": execution,
            "validation": validation,
            "review": "not_requested",
            "publication": "not_published",
        },
        "validation": {
            "errors": [],
            "warnings": [],
        },
        "timing": {
            "started_at": FIXED_TIME,
            "completed_at": FIXED_TIME,
            "duration_ms": 1,
        },
        "error": error,
        "input_assurance": {
            "status": "passed",
            "encoding": "utf-8-strict",
            "has_utf8_bom": False,
            "source_normalized_byte_identical": True,
            "source_findings": [],
            "reconstruction_parseability": None,
            "source_html_structure": None,
        },
    }


def _structured_error() -> dict[str, str]:
    return {
        "code": "fixture_failure",
        "stage": "extraction",
        "message": "fixture failure",
    }


def _validation_errors(value: dict[str, Any]) -> list[str]:
    result = ContractValidator(ROOT).validate_sidecar(value)
    return [
        f"{issue.path}: {issue.message}"
        for issue in result.errors
    ]


def _assert_valid(value: dict[str, Any]) -> None:
    assert not (errors := _validation_errors(value)), errors


def _assert_invalid(value: dict[str, Any]) -> None:
    assert _validation_errors(value)


def test_diagnostic_sidecar_schema_is_valid_draft_2020_12() -> None:
    schema = json.loads(
        (
            ROOT / "schemas/diagnostic-sidecar-1.2.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize(
    ("strategy_type", "page_model"),
    [
        ("simple_static", "FlexibleContentPage"),
        ("region_filter", "FlexibleContentPage"),
        ("complex", "FlexibleContentPage"),
        ("support_article", "SupportArticlePage"),
    ],
)
def test_closed_strategy_accepts_formal_success_producers(
    strategy_type: str,
    page_model: str,
) -> None:
    value = _sidecar(strategy_type, page_model)
    if strategy_type == "complex":
        value["strategy"][
            "region_projected_shared_content_evidence"
        ] = _shared_projection_summary()
        value["strategy"][
            "strict_soft_category_projection_evidence"
        ] = _strict_projection_summary()
    _assert_valid(value)


@pytest.mark.parametrize(
    ("strategy_type", "page_model"),
    [
        ("simple_static", "FlexibleContentPage"),
        ("region_filter", "FlexibleContentPage"),
        ("complex", "FlexibleContentPage"),
        ("support_article", "SupportArticlePage"),
    ],
)
def test_closed_strategy_accepts_formal_ordinary_failure_producers(
    strategy_type: str,
    page_model: str,
) -> None:
    _assert_valid(_sidecar(
        strategy_type,
        page_model,
        execution="failed",
        validation="not_run",
        error=_structured_error(),
    ))


def test_closed_strategy_accepts_catalog_skip_before_selection() -> None:
    _assert_valid(_sidecar(
        "not_selected",
        "FlexibleContentPage",
        execution="skipped",
        validation="not_run",
        error={
            "code": "known_unsupported",
            "stage": "catalog",
            "message": "fixture unsupported product",
        },
    ))


def test_strict_failure_accepts_extraction_and_preselection_paths() -> None:
    complex_failure = _sidecar(
        "complex",
        "FlexibleContentPage",
        execution="failed",
        validation="not_run",
        error=_structured_error(),
    )
    complex_failure["strategy"][
        "strict_soft_category_projection_failure"
    ] = _strict_projection_failure("strategy_replay")
    _assert_valid(complex_failure)

    preselection_failure = _sidecar(
        "not_selected",
        "FlexibleContentPage",
        execution="failed",
        validation="not_run",
        error=_structured_error(),
    )
    preselection_failure["strategy"][
        "strict_soft_category_projection_failure"
    ] = _strict_projection_failure("source_reachability")
    _assert_valid(preselection_failure)


@pytest.mark.parametrize(
    "phase",
    ["validation_replay", "bilingual_replay", "source_reachability"],
)
def test_strict_failure_accepts_post_extraction_validation_paths(
    phase: str,
) -> None:
    value = _sidecar(
        "complex",
        "FlexibleContentPage",
        execution="succeeded",
        validation="failed",
        error=None,
    )
    value["strategy"][
        "strict_soft_category_projection_failure"
    ] = _strict_projection_failure(phase)
    value["validation"]["errors"] = [{
        "code": "soft_category_fixture_failure",
        "path": "$.expected_reachability",
        "message": "fixture strict replay failure",
    }]
    _assert_valid(value)


def test_strategy_rejects_unknown_fields_and_types() -> None:
    unknown_field = _sidecar(
        "simple_static",
        "FlexibleContentPage",
    )
    unknown_field["strategy"]["policy_override"] = "forged"
    _assert_invalid(unknown_field)

    unknown_type = _sidecar(
        "simple_static",
        "FlexibleContentPage",
    )
    unknown_type["strategy"]["type"] = "large_file"
    _assert_invalid(unknown_type)


def test_source_html_structure_assurance_is_explicitly_required() -> None:
    missing = _sidecar("simple_static", "FlexibleContentPage")
    missing["input_assurance"].pop("source_html_structure")
    _assert_invalid(missing)


def test_region_projected_shared_evidence_requires_complex_success() -> None:
    valid = _sidecar("complex", "FlexibleContentPage")
    valid["strategy"][
        "region_projected_shared_content_evidence"
    ] = _shared_projection_summary()
    _assert_valid(valid)

    for strategy_type, page_model in (
        ("not_selected", "FlexibleContentPage"),
        ("simple_static", "FlexibleContentPage"),
        ("region_filter", "FlexibleContentPage"),
        ("support_article", "SupportArticlePage"),
    ):
        wrong_strategy = _sidecar(strategy_type, page_model)
        wrong_strategy["strategy"][
            "region_projected_shared_content_evidence"
        ] = _shared_projection_summary()
        _assert_invalid(wrong_strategy)

    wrong_page_model = deepcopy(valid)
    wrong_page_model["page_model"] = "SupportArticlePage"
    wrong_page_model["contract"]["name"] = "SupportArticlePage"
    wrong_page_model["contract"]["version"] = "1.0"
    _assert_invalid(wrong_page_model)

    failed_execution = deepcopy(valid)
    failed_execution["status"]["execution"] = "failed"
    failed_execution["status"]["validation"] = "not_run"
    failed_execution["payload"] = None
    failed_execution["error"] = _structured_error()
    _assert_invalid(failed_execution)

    succeeded_with_error = deepcopy(valid)
    succeeded_with_error["error"] = _structured_error()
    _assert_invalid(succeeded_with_error)


def test_strict_projection_evidence_rejects_contradictory_sidecars() -> None:
    valid = _sidecar("complex", "FlexibleContentPage")
    valid["strategy"][
        "strict_soft_category_projection_evidence"
    ] = _strict_projection_summary()
    _assert_valid(valid)

    wrong_strategy = deepcopy(valid)
    wrong_strategy["strategy"]["type"] = "region_filter"
    _assert_invalid(wrong_strategy)

    failed_execution = deepcopy(valid)
    failed_execution["status"]["execution"] = "failed"
    failed_execution["status"]["validation"] = "not_run"
    failed_execution["payload"] = None
    failed_execution["error"] = _structured_error()
    _assert_invalid(failed_execution)

    succeeded_with_error = deepcopy(valid)
    succeeded_with_error["error"] = _structured_error()
    _assert_invalid(succeeded_with_error)

    evidence_and_failure = deepcopy(valid)
    evidence_and_failure["status"]["validation"] = "failed"
    evidence_and_failure["strategy"][
        "strict_soft_category_projection_failure"
    ] = _strict_projection_failure("validation_replay")
    _assert_invalid(evidence_and_failure)


def test_strict_projection_failure_rejects_contradictory_sidecars() -> None:
    valid = _sidecar(
        "complex",
        "FlexibleContentPage",
        execution="failed",
        validation="not_run",
        error=_structured_error(),
    )
    valid["strategy"][
        "strict_soft_category_projection_failure"
    ] = _strict_projection_failure()
    _assert_valid(valid)

    wrong_strategy = deepcopy(valid)
    wrong_strategy["strategy"]["type"] = "support_article"
    _assert_invalid(wrong_strategy)

    failed_without_error = deepcopy(valid)
    failed_without_error["error"] = None
    _assert_invalid(failed_without_error)

    running = deepcopy(valid)
    running["status"]["execution"] = "running"
    _assert_invalid(running)

    succeeded_not_failed_validation = deepcopy(valid)
    succeeded_not_failed_validation["status"]["execution"] = "succeeded"
    succeeded_not_failed_validation["status"]["validation"] = "passed"
    succeeded_not_failed_validation["payload"] = _artifact(
        "output/fixture.json",
        SHA_B,
    )
    succeeded_not_failed_validation["error"] = None
    _assert_invalid(succeeded_not_failed_validation)

    succeeded_with_error = deepcopy(valid)
    succeeded_with_error["status"]["execution"] = "succeeded"
    succeeded_with_error["status"]["validation"] = "failed"
    succeeded_with_error["payload"] = _artifact(
        "output/fixture.json",
        SHA_B,
    )
    _assert_invalid(succeeded_with_error)

    preselection_after_success = deepcopy(succeeded_with_error)
    preselection_after_success["strategy"]["type"] = "not_selected"
    preselection_after_success["strategy"][
        "processor"
    ] = "not_selected"
    preselection_after_success["error"] = None
    _assert_invalid(preselection_after_success)

    preselection_after_attach = deepcopy(valid)
    preselection_after_attach["strategy"]["type"] = "not_selected"
    preselection_after_attach["strategy"]["processor"] = "not_selected"
    _assert_invalid(preselection_after_attach)

    attach_after_success = _sidecar(
        "complex",
        "FlexibleContentPage",
        execution="succeeded",
        validation="failed",
        error=None,
    )
    attach_after_success["strategy"][
        "strict_soft_category_projection_failure"
    ] = _strict_projection_failure("attach")
    _assert_invalid(attach_after_success)

    validation_during_extraction = deepcopy(valid)
    validation_during_extraction["strategy"][
        "strict_soft_category_projection_failure"
    ]["phase"] = "validation_replay"
    _assert_invalid(validation_during_extraction)
