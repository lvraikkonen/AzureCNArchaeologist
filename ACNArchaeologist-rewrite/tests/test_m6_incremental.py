from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from src.cli import main
from src.core.catalog import ProcessingItem, ProductCatalog
from src.incremental.change_detection import (
    ChangeDetectionError,
    detect_html_changes,
    detect_incremental_changes,
)
from src.incremental.product_definition_changes import (
    build_product_definition_baseline,
)
from src.incremental.reprocessing import find_reprocessing_chain
from src.incremental.state import (
    end_product_without_delivery,
    find_open_incremental_batch,
)
from src.pipeline import coordinator
from src.pipeline.coordinator import (
    PipelineRunError,
    reprocess_incremental_product,
    resume_run,
    run_incremental,
)
from src.pipeline.source_input import SourceInput
from src.extractors.strategy_extractor import extract_processing_item_with_usage
from src.release import ReleaseError, build_delta_release, verify_release
from src.review import (
    ReviewWorkbenchService,
    create_review_decision,
    prepare_review_queue,
)
from tests.m2_helpers import real_catalog


def _freeze_baseline(catalog: ProductCatalog) -> None:
    report = SourceInput(catalog).freeze(catalog.select(all_products=True))
    assert report.succeeded


def _source_path(catalog: ProductCatalog, item: ProcessingItem) -> Path:
    return (catalog.project_root / "data" / "current_prod_html").joinpath(
        *item.source_relative_path.parts
    )


def _frozen_path(catalog: ProductCatalog, item: ProcessingItem) -> Path:
    return (catalog.project_root / "data" / "prod-html").joinpath(
        *item.frozen_relative_path.parts
    )


def _item(catalog: ProductCatalog, product_key: str, language: str) -> ProcessingItem:
    return next(
        item
        for item in catalog.select(product_key=product_key)
        if item.language == language
    )


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _prepare_incremental_config(
    catalog: ProductCatalog,
    *,
    previous_rows: list[dict],
    current_rows: list[dict],
    usage_items: list[dict] | None = None,
) -> None:
    _write_json(
        catalog.project_root / "data" / "configs" / "soft-category.json",
        previous_rows,
    )
    _write_json(
        catalog.project_root / "data" / "current_prod_html" / "soft-category.json",
        current_rows,
    )
    _write_json(
        catalog.project_root / "data" / "state" / "product-definitions.json",
        build_product_definition_baseline(
            catalog,
            source_run_name="accepted-baseline",
        ),
    )
    if usage_items is not None:
        _write_json(
            catalog.project_root / "data" / "state" / "soft-category-usage.json",
            {"schema_version": "1.0", "items": usage_items},
        )


def _simple_payload(product_key: str, language: str) -> dict:
    title = f"{product_key} {language}"
    return {
        "title": title,
        "metaTitle": "",
        "metaDescription": "",
        "metaKeywords": "",
        "slug": product_key,
        "language": language,
        "baseContent": f"<div>{product_key} {language} pricing</div>",
        "contentGroups": [],
        "commonSections": [
            {
                "sectionType": "Banner",
                "sectionTitle": "",
                "content": f"<div>{product_key} banner</div>",
                "sortOrder": 1,
                "isActive": True,
            }
        ],
        "pageConfig": {
            "displayTitle": title,
            "pageIcon": "{base_url}/Static/Favicon/favicon.ico",
            "leftNavigationIdentifier": product_key,
            "pageType": "Simple",
            "enableFilters": False,
            "filtersJsonConfig": '{"filterDefinitions": []}',
        },
    }


def _passed_check(name: str, product_key: str, language: str) -> dict:
    return {
        "check": name,
        "status": "passed",
        "product_key": product_key,
        "language": language,
        "scope": "测试中的完整检查",
        "differences" if name == "L3a" else "fields": [],
    }


def test_identical_snapshot_has_no_changes_and_exposes_no_digest_codes(
    project_builder,
) -> None:
    project_root = project_builder(
        [{"product_key": "first-product"}, {"product_key": "second-product"}]
    )
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)

    plan = detect_html_changes(catalog)

    assert plan.has_changes is False
    assert plan.affected_product_count == 0
    assert plan.affected_item_count == 0
    assert plan.unchanged_product_keys == ("first-product", "second-product")
    serialized = json.dumps(plan.as_dict(), ensure_ascii=False).lower()
    assert "sha256" not in serialized
    assert "fingerprint" not in serialized
    assert "digest" not in serialized
    assert "checksum" not in serialized


def test_html_changes_cli_states_its_incomplete_comparison_scope(
    project_builder,
) -> None:
    project_root = project_builder([{"product_key": "sample-product"}])
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main(
        ["html-changes", "--json"],
        project_root=project_root,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    result = json.loads(stdout.getvalue())
    assert result["status"] == "no_html_changes"
    assert result["comparison_scope"] == {
        "included": ["upstream_html_vs_frozen_html"],
        "not_yet_included": ["product_definitions", "soft_category"],
    }


@pytest.mark.parametrize("changed_language", ["zh-cn", "en-us"])
def test_one_language_change_plans_both_languages(
    project_builder,
    changed_language: str,
) -> None:
    project_root = project_builder([{"product_key": "sample-product"}])
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    changed_item = _item(catalog, "sample-product", changed_language)
    previous_frozen = _frozen_path(catalog, changed_item).read_bytes()
    _source_path(catalog, changed_item).write_bytes(b"new upstream content")

    plan = detect_html_changes(catalog)

    assert plan.affected_product_count == 1
    product = plan.affected_products[0]
    assert product.product_key == "sample-product"
    assert product.changed_languages == (changed_language,)
    assert product.changes[0].change_type == "modified"
    assert [item.language for item in product.processing_items] == [
        "zh-cn",
        "en-us",
    ]
    assert product.as_dict()["processing_item_ids"] == [
        "sample-product/zh-cn",
        "sample-product/en-us",
    ]
    assert "同时处理 zh-cn 和 en-us" in product.bilingual_processing_reason
    assert _frozen_path(catalog, changed_item).read_bytes() == previous_frozen


def test_only_changed_products_enter_the_bilingual_plan(project_builder) -> None:
    project_root = project_builder(
        [
            {"product_key": "first-product"},
            {"product_key": "second-product"},
            {"product_key": "unchanged-product"},
        ]
    )
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    _source_path(catalog, _item(catalog, "first-product", "zh-cn")).write_bytes(
        b"first changed"
    )
    _source_path(catalog, _item(catalog, "second-product", "en-us")).write_bytes(
        b"second changed"
    )

    plan = detect_html_changes(catalog)

    assert [product.product_key for product in plan.affected_products] == [
        "first-product",
        "second-product",
    ]
    assert plan.affected_item_count == 4
    assert plan.unchanged_product_keys == ("unchanged-product",)


def test_both_language_changes_still_create_exactly_one_bilingual_product_plan(
    project_builder,
) -> None:
    project_root = project_builder([{"product_key": "sample-product"}])
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    for language in ("zh-cn", "en-us"):
        _source_path(
            catalog, _item(catalog, "sample-product", language)
        ).write_bytes(f"changed {language}".encode())

    plan = detect_html_changes(catalog)

    assert plan.affected_product_count == 1
    assert plan.affected_item_count == 2
    product = plan.affected_products[0]
    assert product.changed_languages == ("zh-cn", "en-us")
    assert [change.change_type for change in product.changes] == [
        "modified",
        "modified",
    ]
    assert [item.language for item in product.processing_items] == [
        "zh-cn",
        "en-us",
    ]


def test_added_and_removed_files_are_reported_with_readable_paths(
    project_builder,
) -> None:
    project_root = project_builder(
        [{"product_key": "added-product"}, {"product_key": "removed-product"}]
    )
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    added_item = _item(catalog, "added-product", "zh-cn")
    removed_item = _item(catalog, "removed-product", "en-us")
    _frozen_path(catalog, added_item).unlink()
    _source_path(catalog, removed_item).unlink()

    plan = detect_html_changes(catalog)

    changes = {
        product.product_key: product.changes[0]
        for product in plan.affected_products
    }
    assert changes["added-product"].change_type == "added"
    assert changes["removed-product"].change_type == "removed"
    assert changes["added-product"].new_snapshot_path.startswith(
        "data/current_prod_html/zh-cn/"
    )
    assert changes["removed-product"].previous_frozen_path.startswith(
        "data/prod-html/en-us/"
    )


def test_change_detection_rejects_a_source_symlink(
    project_builder,
    tmp_path,
) -> None:
    project_root = project_builder([{"product_key": "sample-product"}])
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    source = _source_path(catalog, _item(catalog, "sample-product", "zh-cn"))
    outside = tmp_path / "outside.html"
    outside.write_bytes(b"outside")
    source.unlink()
    source.symlink_to(outside)

    with pytest.raises(ChangeDetectionError, match="越出规定目录|符号链接"):
        detect_html_changes(catalog)


def test_soft_category_format_only_change_does_not_plan_a_batch(
    project_builder,
) -> None:
    project_root = project_builder(
        [
            {
                "product_key": "region-product",
                "semantic_strategy": "region_filter",
            }
        ]
    )
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    _prepare_incremental_config(
        catalog,
        previous_rows=[
            {"os": "software-a", "region": "region-a", "tableIDs": ["#b", "a"]}
        ],
        current_rows=[
            {"region": "region-a", "tableIDs": ["a", "b"], "os": "software-a"}
        ],
    )

    plan = detect_incremental_changes(catalog)

    assert plan.has_changes is False
    assert plan.soft_category is not None
    assert plan.soft_category.text_changed is True
    assert plan.soft_category.business_mapping_changed is False
    assert plan.soft_category.impact_resolution == "no_business_change"


def test_soft_category_change_uses_actual_lookup_and_plans_both_languages(
    project_builder,
) -> None:
    project_root = project_builder(
        [
            {
                "product_key": "region-product",
                "semantic_strategy": "region_filter",
            },
            {"product_key": "simple-product"},
        ]
    )
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    usage_items = [
        {
            "product_key": "region-product",
            "language": language,
            "lookups": [
                {
                    "os": "software-a",
                    "region": "region-a",
                    "row_present": True,
                    "table_ids": ["old-table"],
                }
            ],
        }
        for language in ("zh-cn", "en-us")
    ]
    _prepare_incremental_config(
        catalog,
        previous_rows=[
            {
                "os": "software-a",
                "region": "region-a",
                "tableIDs": ["old-table"],
            }
        ],
        current_rows=[
            {
                "os": "software-a",
                "region": "region-a",
                "tableIDs": ["new-table"],
            }
        ],
        usage_items=usage_items,
    )

    plan = detect_incremental_changes(catalog)

    assert [product.product_key for product in plan.affected_products] == [
        "region-product"
    ]
    product = plan.affected_products[0]
    assert product.changed_languages == ()
    assert product.change_sources == ("soft_category",)
    assert [item.language for item in product.processing_items] == [
        "zh-cn",
        "en-us",
    ]
    assert plan.soft_category is not None
    assert plan.soft_category.impact_resolution == "actual_usage"


def test_new_mapping_affects_a_product_that_previously_looked_up_a_missing_row(
    project_builder,
) -> None:
    project_root = project_builder(
        [
            {
                "product_key": "region-product",
                "semantic_strategy": "region_filter",
            }
        ]
    )
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    _prepare_incremental_config(
        catalog,
        previous_rows=[],
        current_rows=[
            {
                "os": "software-a",
                "region": "region-a",
                "tableIDs": ["new-table"],
            }
        ],
        usage_items=[
            {
                "product_key": "region-product",
                "language": language,
                "lookups": [
                    {
                        "os": "software-a",
                        "region": "region-a",
                        "row_present": False,
                        "table_ids": [],
                    }
                ],
            }
            for language in ("zh-cn", "en-us")
        ],
    )

    plan = detect_incremental_changes(catalog)

    assert plan.affected_product_count == 1
    assert plan.soft_category is not None
    assert plan.soft_category.mapping_changes[0].change_type == "added"


def test_incomplete_usage_evidence_expands_to_every_possible_consumer(
    project_builder,
) -> None:
    project_root = project_builder(
        [
            {
                "product_key": "complex-product",
                "semantic_strategy": "complex",
            },
            {
                "product_key": "region-product",
                "semantic_strategy": "region_filter",
            },
            {"product_key": "simple-product"},
        ]
    )
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    _prepare_incremental_config(
        catalog,
        previous_rows=[],
        current_rows=[
            {"os": "unused", "region": "new", "tableIDs": ["table-a"]}
        ],
    )

    plan = detect_incremental_changes(catalog)

    assert [product.product_key for product in plan.affected_products] == [
        "complex-product",
        "region-product",
    ]
    assert plan.soft_category is not None
    assert (
        plan.soft_category.impact_resolution
        == "actual_usage_with_unknown_consumers"
    )
    assert "缺少完整记录" in plan.soft_category.impact_reason


def test_complete_products_remain_precise_when_another_consumer_is_unknown(
    project_builder,
) -> None:
    project_root = project_builder(
        [
            {
                "product_key": "complex-product",
                "semantic_strategy": "complex",
            },
            {
                "product_key": "region-product",
                "semantic_strategy": "region_filter",
            },
        ]
    )
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    _prepare_incremental_config(
        catalog,
        previous_rows=[],
        current_rows=[
            {"os": "changed", "region": "changed", "tableIDs": ["table-a"]}
        ],
        usage_items=[
            {
                "product_key": "region-product",
                "language": language,
                "lookups": [
                    {
                        "os": "known",
                        "region": "known",
                        "row_present": False,
                        "table_ids": [],
                    }
                ],
            }
            for language in ("zh-cn", "en-us")
        ],
    )

    plan = detect_incremental_changes(catalog)

    assert [product.product_key for product in plan.affected_products] == [
        "complex-product"
    ]


def test_processing_product_definition_change_is_a_bilingual_trigger(
    project_builder,
) -> None:
    project_root = project_builder([{"product_key": "sample-product"}])
    original_catalog = ProductCatalog.load(project_root)
    _freeze_baseline(original_catalog)
    _prepare_incremental_config(
        original_catalog,
        previous_rows=[],
        current_rows=[],
    )
    config_path = next(
        (
            project_root / "data" / "configs" / "products-config" / "pricing"
        ).glob("*.json")
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["extraction"]["semantic_strategy"] = "region_filter"
    _write_json(config_path, config)
    changed_catalog = ProductCatalog.load(project_root)

    plan = detect_incremental_changes(changed_catalog)

    assert plan.affected_product_count == 1
    product = plan.affected_products[0]
    assert product.change_sources == ("product_definition",)
    assert product.changed_languages == ()
    assert [item.language for item in product.processing_items] == [
        "zh-cn",
        "en-us",
    ]


def test_incremental_batch_uses_fixed_inputs_and_delta_release_closes_it(
    project_builder,
    tmp_path,
    monkeypatch,
) -> None:
    project_root = project_builder([{"product_key": "sample-product"}])
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    _prepare_incremental_config(
        catalog,
        previous_rows=[],
        current_rows=[],
    )
    changed_source = _source_path(
        catalog,
        _item(catalog, "sample-product", "zh-cn"),
    )
    changed_source.write_bytes(b"changed zh-cn source")
    monkeypatch.setattr(
        coordinator,
        "extract_processing_item",
        lambda selected_catalog, item: _simple_payload(
            item.product_key,
            item.language,
        ),
    )
    monkeypatch.setattr(
        coordinator,
        "run_l3a",
        lambda **kwargs: _passed_check(
            "L3a",
            kwargs["product_key"],
            kwargs["language"],
        ),
    )
    monkeypatch.setattr(
        coordinator,
        "run_l3b",
        lambda **kwargs: _passed_check(
            "L3b",
            kwargs["product_key"],
            kwargs["language"],
        ),
    )
    runs_root = tmp_path / "runs"
    reviews_root = tmp_path / "reviews"
    releases_root = tmp_path / "releases"

    result = run_incremental(
        catalog,
        run_name="changed-sample",
        runs_root=runs_root,
        releases_root=releases_root,
        parallel_jobs=2,
    )

    assert result.created_batch is True
    assert result.batch is not None
    assert result.batch.manifest["batch_kind"] == "incremental"
    assert result.batch.manifest["scope"]["product_keys"] == ["sample-product"]
    assert (result.batch.run_directory / "change-plan.json").is_file()
    for row in result.batch.manifest["items"]:
        frozen = result.batch.run_directory / row["frozen_html_path"]
        usage = result.batch.run_directory / row["configuration_usage"]["path"]
        assert frozen.is_file()
        assert usage.is_file()
    open_batch = find_open_incremental_batch(
        catalog,
        runs_root=runs_root,
        releases_root=releases_root,
    )
    assert open_batch is not None
    assert open_batch.unresolved_product_keys == ("sample-product",)
    with pytest.raises(PipelineRunError, match="尚未结束"):
        run_incremental(
            catalog,
            run_name="second-snapshot",
            runs_root=runs_root,
            releases_root=releases_root,
            parallel_jobs=2,
        )

    prepare_review_queue(
        catalog,
        run_name="changed-sample",
        review_id="changed-sample-review",
        runs_root=runs_root,
        reviews_root=reviews_root,
    )
    create_review_decision(
        catalog,
        review_id="changed-sample-review",
        product_key="sample-product",
        reviewer="Real Reviewer",
        decision="approved",
        inspected_languages=("zh-cn", "en-us"),
        inspected_materials=(
            "frozen-html",
            "payload",
            "l3a-report",
            "l3b-report",
        ),
        notes="Compared both languages.",
        reviews_root=reviews_root,
    )
    release = build_delta_release(
        catalog,
        review_id="changed-sample-review",
        release_id="changed-sample-delta",
        reviews_root=reviews_root,
        releases_root=releases_root,
        runs_root=runs_root,
    )

    assert release.manifest["release_kind"] == "delta"
    assert release.manifest["products"][0]["change_reasons"][
        "change_sources"
    ] == ["html"]
    assert verify_release(
        catalog,
        release_id="changed-sample-delta",
        reviews_root=reviews_root,
        releases_root=releases_root,
    )["status"] == "passed"
    assert find_open_incremental_batch(
        catalog,
        runs_root=runs_root,
        releases_root=releases_root,
    ) is None


def test_rejection_stays_unresolved_until_explicit_end_without_delivery(
    project_builder,
    tmp_path,
) -> None:
    project_root = project_builder([{"product_key": "sample-product"}])
    catalog = ProductCatalog.load(project_root)
    runs_root = tmp_path / "runs"
    run_directory = runs_root / "rejected-change"
    run_directory.mkdir(parents=True)
    _write_json(
        run_directory / "run.json",
        {
            "schema_version": "1.1",
            "run_name": "rejected-change",
            "batch_kind": "incremental",
            "scope": {"product_keys": ["sample-product"]},
        },
    )

    assert find_open_incremental_batch(
        catalog,
        runs_root=runs_root,
        releases_root=tmp_path / "releases",
    ) is not None
    decision_path = end_product_without_delivery(
        catalog,
        run_name="rejected-change",
        product_key="sample-product",
        reviewer="Real Reviewer",
        reason="Upstream content is not accepted for this delivery.",
        runs_root=runs_root,
        releases_root=tmp_path / "releases",
        closures_root=tmp_path / "closures",
    )

    assert decision_path.is_file()
    assert find_open_incremental_batch(
        catalog,
        runs_root=runs_root,
        releases_root=tmp_path / "releases",
        closures_root=tmp_path / "closures",
    ) is None


def test_rejected_product_can_be_reprocessed_repeatedly_in_the_same_batch(
    project_builder,
    tmp_path,
    monkeypatch,
) -> None:
    project_root = project_builder([{"product_key": "sample-product"}])
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    _prepare_incremental_config(
        catalog,
        previous_rows=[],
        current_rows=[],
    )
    changed_source = _source_path(
        catalog,
        _item(catalog, "sample-product", "zh-cn"),
    )
    changed_source.write_bytes(b"fixed input selected by the incremental batch")
    payload_version = {"value": "first incorrect result"}

    def current_payload(selected_catalog, item):
        payload = _simple_payload(item.product_key, item.language)
        payload["baseContent"] = f"<div>{payload_version['value']}</div>"
        return payload

    monkeypatch.setattr(coordinator, "extract_processing_item", current_payload)
    monkeypatch.setattr(
        coordinator,
        "run_l3a",
        lambda **kwargs: _passed_check(
            "L3a", kwargs["product_key"], kwargs["language"]
        ),
    )
    monkeypatch.setattr(
        coordinator,
        "run_l3b",
        lambda **kwargs: _passed_check(
            "L3b", kwargs["product_key"], kwargs["language"]
        ),
    )
    runs_root = tmp_path / "runs"
    reviews_root = tmp_path / "reviews"
    releases_root = tmp_path / "releases"

    original = run_incremental(
        catalog,
        run_name="original-change",
        runs_root=runs_root,
        releases_root=releases_root,
        parallel_jobs=2,
    )
    assert original.batch is not None
    original_directory = original.batch.run_directory
    original_payload = (
        original_directory / "payloads/zh-cn/pricing/sample-product.json"
    ).read_bytes()
    prepare_review_queue(
        catalog,
        run_name="original-change",
        review_id="original-rejection",
        runs_root=runs_root,
        reviews_root=reviews_root,
    )
    create_review_decision(
        catalog,
        review_id="original-rejection",
        product_key="sample-product",
        reviewer="First Reviewer",
        decision="rejected",
        inspected_languages=("zh-cn", "en-us"),
        inspected_materials=(
            "frozen-html",
            "payload",
            "l3a-report",
            "l3b-report",
        ),
        notes="The extracted content boundary is wrong.",
        reviews_root=reviews_root,
    )

    changed_source.write_bytes(b"later upstream content must not be used")
    baseline_before = _frozen_path(
        catalog,
        _item(catalog, "sample-product", "zh-cn"),
    ).read_bytes()
    payload_version["value"] = "second result still rejected"
    first_reprocessing = reprocess_incremental_product(
        catalog,
        incremental_run_name="original-change",
        product_key="sample-product",
        reprocessing_run_name="sample-reprocessing-one",
        requested_by="Pipeline Maintainer",
        reason="Corrected the first extraction defect.",
        rejected_review_id="original-rejection",
        runs_root=runs_root,
        reviews_root=reviews_root,
        releases_root=releases_root,
        parallel_jobs=2,
    )

    assert first_reprocessing.status == "passed"
    assert first_reprocessing.manifest["batch_kind"] == (
        "incremental_reprocessing"
    )
    assert first_reprocessing.manifest["incremental_reprocessing"] == {
        "incremental_run_name": "original-change",
        "incremental_run_directory": original_directory.as_posix(),
        "incremental_run_manifest_path": (
            original_directory / "run.json"
        ).as_posix(),
        "product_key": "sample-product",
        "previous_processing_run_name": "original-change",
        "previous_processing_run_directory": original_directory.as_posix(),
        "basis": "human_rejection",
        "rejected_review_id": "original-rejection",
        "rejected_decision_path": (
            reviews_root
            / "original-rejection"
            / "decisions"
            / "sample-product.json"
        ).as_posix(),
        "requested_by": "Pipeline Maintainer",
        "reason": "Corrected the first extraction defect.",
    }
    assert (
        _frozen_path(
            catalog,
            _item(catalog, "sample-product", "zh-cn"),
        ).read_bytes()
        == baseline_before
    )
    assert (
        first_reprocessing.run_directory
        / "inputs/prod-html/zh-cn/pricing/sample-product.html"
    ).read_bytes() == (
        original_directory
        / "inputs/prod-html/zh-cn/pricing/sample-product.html"
    ).read_bytes()
    assert (
        original_directory / "payloads/zh-cn/pricing/sample-product.json"
    ).read_bytes() == original_payload

    with pytest.raises(PipelineRunError, match="最新的处理记录"):
        reprocess_incremental_product(
            catalog,
            incremental_run_name="original-change",
            product_key="sample-product",
            reprocessing_run_name="stale-rejection-attempt",
            requested_by="Pipeline Maintainer",
            reason="Must not reuse an old rejection.",
            rejected_review_id="original-rejection",
            runs_root=runs_root,
            reviews_root=reviews_root,
            releases_root=releases_root,
            parallel_jobs=2,
        )

    prepare_review_queue(
        catalog,
        run_name="sample-reprocessing-one",
        review_id="second-rejection",
        runs_root=runs_root,
        reviews_root=reviews_root,
    )
    create_review_decision(
        catalog,
        review_id="second-rejection",
        product_key="sample-product",
        reviewer="Second Reviewer",
        decision="rejected",
        inspected_languages=("zh-cn", "en-us"),
        inspected_materials=(
            "frozen-html",
            "payload",
            "l3a-report",
            "l3b-report",
        ),
        notes="A second extraction defect remains.",
        reviews_root=reviews_root,
    )
    payload_version["value"] = "final corrected result"
    final_reprocessing = reprocess_incremental_product(
        catalog,
        incremental_run_name="original-change",
        product_key="sample-product",
        reprocessing_run_name="sample-reprocessing-two",
        requested_by="Pipeline Maintainer",
        reason="Corrected the remaining extraction defect.",
        rejected_review_id="second-rejection",
        runs_root=runs_root,
        reviews_root=reviews_root,
        releases_root=releases_root,
        parallel_jobs=2,
    )
    chain = find_reprocessing_chain(
        catalog,
        incremental_run_name="original-change",
        product_key="sample-product",
        runs_root=runs_root,
    )
    assert chain.processing_run_names == (
        "original-change",
        "sample-reprocessing-one",
        "sample-reprocessing-two",
    )

    prepare_review_queue(
        catalog,
        run_name="original-change",
        review_id="stale-approval",
        runs_root=runs_root,
        reviews_root=reviews_root,
    )
    create_review_decision(
        catalog,
        review_id="stale-approval",
        product_key="sample-product",
        reviewer="Stale Reviewer",
        decision="approved",
        inspected_languages=("zh-cn", "en-us"),
        inspected_materials=(
            "frozen-html",
            "payload",
            "l3a-report",
            "l3b-report",
        ),
        notes="This approval references an obsolete result.",
        reviews_root=reviews_root,
    )
    with pytest.raises(ReleaseError, match="当前没有尚未解决"):
        build_delta_release(
            catalog,
            review_id="stale-approval",
            release_id="stale-delta",
            reviews_root=reviews_root,
            releases_root=releases_root,
            runs_root=runs_root,
        )

    prepare_review_queue(
        catalog,
        run_name="sample-reprocessing-two",
        review_id="final-approval",
        runs_root=runs_root,
        reviews_root=reviews_root,
    )
    final_queue = json.loads(
        (reviews_root / "final-approval" / "queue.json").read_text(
            encoding="utf-8"
        )
    )
    assert final_queue["batch"]["incremental_run_name"] == "original-change"
    projection = ReviewWorkbenchService(
        catalog,
        review_id="final-approval",
        reviews_root=reviews_root,
    ).projection()
    assert projection["run_name"] == "sample-reprocessing-two"
    assert projection["batch_kind"] == "incremental_reprocessing"
    assert projection["incremental_run_name"] == "original-change"
    create_review_decision(
        catalog,
        review_id="final-approval",
        product_key="sample-product",
        reviewer="Final Reviewer",
        decision="approved",
        inspected_languages=("zh-cn", "en-us"),
        inspected_materials=(
            "frozen-html",
            "payload",
            "l3a-report",
            "l3b-report",
        ),
        notes="The corrected bilingual result is now accurate.",
        reviews_root=reviews_root,
    )
    release = build_delta_release(
        catalog,
        review_id="final-approval",
        release_id="corrected-delta",
        reviews_root=reviews_root,
        releases_root=releases_root,
        runs_root=runs_root,
    )

    assert release.manifest["source_review"]["run_name"] == (
        "sample-reprocessing-two"
    )
    assert release.manifest["source_review"]["incremental_run_name"] == (
        "original-change"
    )
    assert verify_release(
        catalog,
        release_id="corrected-delta",
        reviews_root=reviews_root,
        releases_root=releases_root,
    )["status"] == "passed"
    assert find_open_incremental_batch(
        catalog,
        runs_root=runs_root,
        releases_root=releases_root,
    ) is None


def test_passed_incremental_result_requires_a_real_rejection_before_reprocessing(
    project_builder,
    tmp_path,
    monkeypatch,
) -> None:
    project_root = project_builder([{"product_key": "sample-product"}])
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    _prepare_incremental_config(
        catalog,
        previous_rows=[],
        current_rows=[],
    )
    _source_path(
        catalog,
        _item(catalog, "sample-product", "zh-cn"),
    ).write_bytes(b"changed source")
    monkeypatch.setattr(
        coordinator,
        "extract_processing_item",
        lambda selected_catalog, item: _simple_payload(
            item.product_key, item.language
        ),
    )
    monkeypatch.setattr(
        coordinator,
        "run_l3a",
        lambda **kwargs: _passed_check(
            "L3a", kwargs["product_key"], kwargs["language"]
        ),
    )
    monkeypatch.setattr(
        coordinator,
        "run_l3b",
        lambda **kwargs: _passed_check(
            "L3b", kwargs["product_key"], kwargs["language"]
        ),
    )
    runs_root = tmp_path / "runs"
    run_incremental(
        catalog,
        run_name="passed-change",
        runs_root=runs_root,
        releases_root=tmp_path / "releases",
        parallel_jobs=2,
    )

    with pytest.raises(PipelineRunError, match="必须提供拒绝"):
        reprocess_incremental_product(
            catalog,
            incremental_run_name="passed-change",
            product_key="sample-product",
            reprocessing_run_name="unjustified-reprocessing",
            requested_by="Pipeline Maintainer",
            reason="No human rejection exists.",
            runs_root=runs_root,
            reviews_root=tmp_path / "reviews",
            releases_root=tmp_path / "releases",
            parallel_jobs=2,
        )


def test_machine_blocked_product_can_be_reprocessed_without_a_review_decision(
    project_builder,
    tmp_path,
    monkeypatch,
) -> None:
    project_root = project_builder([{"product_key": "sample-product"}])
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    _prepare_incremental_config(
        catalog,
        previous_rows=[],
        current_rows=[],
    )
    _source_path(
        catalog,
        _item(catalog, "sample-product", "zh-cn"),
    ).write_bytes(b"changed source")

    def blocked_extraction(selected_catalog, item):
        raise ValueError("controlled extraction defect")

    monkeypatch.setattr(
        coordinator,
        "extract_processing_item",
        blocked_extraction,
    )
    runs_root = tmp_path / "runs"
    reviews_root = tmp_path / "reviews"
    releases_root = tmp_path / "releases"
    original = run_incremental(
        catalog,
        run_name="machine-blocked-change",
        runs_root=runs_root,
        releases_root=releases_root,
        parallel_jobs=2,
    )
    assert original.batch is not None
    assert original.batch.status == "completed_with_issues"

    monkeypatch.setattr(
        coordinator,
        "extract_processing_item",
        lambda selected_catalog, item: _simple_payload(
            item.product_key, item.language
        ),
    )
    monkeypatch.setattr(
        coordinator,
        "run_l3a",
        lambda **kwargs: _passed_check(
            "L3a", kwargs["product_key"], kwargs["language"]
        ),
    )
    monkeypatch.setattr(
        coordinator,
        "run_l3b",
        lambda **kwargs: _passed_check(
            "L3b", kwargs["product_key"], kwargs["language"]
        ),
    )
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = main(
        [
            "incremental-reprocess-product",
            "--run-name",
            "machine-blocked-change",
            "--product",
            "sample-product",
            "--new-run-name",
            "machine-fix-result",
            "--requested-by",
            "Pipeline Maintainer",
            "--reason",
            "Fixed the controlled extraction defect.",
            "--parallel-jobs",
            "2",
            "--json",
        ],
        project_root=project_root,
        runs_root=runs_root,
        reviews_root=reviews_root,
        releases_root=releases_root,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    result = json.loads(stdout.getvalue())
    assert result["status"] == "passed"
    assert result["incremental_reprocessing"]["basis"] == (
        "machine_result_not_passed"
    )
    assert result["incremental_reprocessing"]["rejected_review_id"] is None


def test_reprocessing_stops_when_processing_product_definition_changed(
    project_builder,
    tmp_path,
    monkeypatch,
) -> None:
    project_root = project_builder([{"product_key": "sample-product"}])
    original_catalog = ProductCatalog.load(project_root)
    _freeze_baseline(original_catalog)
    _prepare_incremental_config(
        original_catalog,
        previous_rows=[],
        current_rows=[],
    )
    _source_path(
        original_catalog,
        _item(original_catalog, "sample-product", "zh-cn"),
    ).write_bytes(b"changed source")
    monkeypatch.setattr(
        coordinator,
        "extract_processing_item",
        lambda selected_catalog, item: (_ for _ in ()).throw(
            ValueError("controlled extraction defect")
        ),
    )
    runs_root = tmp_path / "runs"
    releases_root = tmp_path / "releases"
    run_incremental(
        original_catalog,
        run_name="definition-change",
        runs_root=runs_root,
        releases_root=releases_root,
        parallel_jobs=2,
    )

    config_path = (
        project_root
        / "data/configs/products-config/pricing/sample-product.json"
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["extraction"]["semantic_strategy"] = "region_filter"
    _write_json(config_path, config)
    changed_catalog = ProductCatalog.load(project_root)

    with pytest.raises(
        PipelineRunError,
        match="处理相关 Product Definition 已经变化",
    ):
        reprocess_incremental_product(
            changed_catalog,
            incremental_run_name="definition-change",
            product_key="sample-product",
            reprocessing_run_name="invalid-fixed-input-reprocessing",
            requested_by="Pipeline Maintainer",
            reason="This must not silently change the fixed input contract.",
            runs_root=runs_root,
            reviews_root=tmp_path / "reviews",
            releases_root=releases_root,
            parallel_jobs=2,
        )


def test_interrupted_reprocessing_input_copy_resumes_from_original_batch(
    project_builder,
    tmp_path,
    monkeypatch,
) -> None:
    project_root = project_builder([{"product_key": "sample-product"}])
    catalog = ProductCatalog.load(project_root)
    _freeze_baseline(catalog)
    _prepare_incremental_config(
        catalog,
        previous_rows=[],
        current_rows=[],
    )
    _source_path(
        catalog,
        _item(catalog, "sample-product", "zh-cn"),
    ).write_bytes(b"changed source")

    def blocked_extraction(selected_catalog, item):
        raise ValueError("controlled extraction defect")

    monkeypatch.setattr(
        coordinator,
        "extract_processing_item",
        blocked_extraction,
    )
    runs_root = tmp_path / "runs"
    releases_root = tmp_path / "releases"
    original = run_incremental(
        catalog,
        run_name="interrupted-input-copy",
        runs_root=runs_root,
        releases_root=releases_root,
        parallel_jobs=2,
    )
    assert original.batch is not None

    monkeypatch.setattr(
        coordinator,
        "extract_processing_item",
        lambda selected_catalog, item: _simple_payload(
            item.product_key, item.language
        ),
    )
    monkeypatch.setattr(
        coordinator,
        "run_l3a",
        lambda **kwargs: _passed_check(
            "L3a", kwargs["product_key"], kwargs["language"]
        ),
    )
    monkeypatch.setattr(
        coordinator,
        "run_l3b",
        lambda **kwargs: _passed_check(
            "L3b", kwargs["product_key"], kwargs["language"]
        ),
    )
    copy_input = coordinator._copy_or_confirm_new_bytes
    copy_count = 0

    def interrupt_fourth_copy(source, destination):
        nonlocal copy_count
        copy_count += 1
        if copy_count == 4:
            raise PipelineRunError("controlled input copy interruption")
        return copy_input(source, destination)

    monkeypatch.setattr(
        coordinator,
        "_copy_or_confirm_new_bytes",
        interrupt_fourth_copy,
    )
    with pytest.raises(PipelineRunError, match="controlled input copy interruption"):
        reprocess_incremental_product(
            catalog,
            incremental_run_name="interrupted-input-copy",
            product_key="sample-product",
            reprocessing_run_name="resumable-reprocessing",
            requested_by="Pipeline Maintainer",
            reason="Fixed the controlled extraction defect.",
            runs_root=runs_root,
            reviews_root=tmp_path / "reviews",
            releases_root=releases_root,
            parallel_jobs=2,
        )

    monkeypatch.setattr(
        coordinator,
        "_copy_or_confirm_new_bytes",
        copy_input,
    )
    resumed = resume_run(
        catalog,
        run_name="resumable-reprocessing",
        runs_root=runs_root,
        parallel_jobs=2,
    )

    assert resumed.status == "passed"
    assert resumed.manifest["resume_count"] == 1
    for language in ("zh-cn", "en-us"):
        relative = Path(
            f"inputs/prod-html/{language}/pricing/sample-product.html"
        )
        assert (resumed.run_directory / relative).read_bytes() == (
            original.batch.run_directory / relative
        ).read_bytes()


def test_real_region_extraction_records_present_and_missing_mapping_lookups() -> None:
    catalog = real_catalog()
    item = _item(catalog, "automation", "zh-cn")

    result = extract_processing_item_with_usage(catalog, item)

    assert result.soft_category_lookups
    assert all(lookup.software and lookup.region for lookup in result.soft_category_lookups)
    assert any(lookup.row_present for lookup in result.soft_category_lookups)
    assert any(not lookup.row_present for lookup in result.soft_category_lookups)
