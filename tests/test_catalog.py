from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.catalog import (
    CatalogError,
    ProductCatalog,
    UnknownCategoryError,
    UnknownProductError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SCOPE = (
    "advisor",
    "api-management",
    "app-service",
    "automation",
    "azure-firewall",
    "azure-migrate",
    "azure-policy",
    "azure-update-management-center",
    "backup",
    "cloud-services",
    "cosmos-db",
    "database-migration",
    "databricks",
    "event-grid",
    "icp-new",
    "machine-learning",
    "managed-instance",
    "monitor",
    "network-watcher",
    "postgresql",
    "scheduler",
    "service-bus",
    "site-recovery",
    "sla-api-management",
    "sla-databricks",
    "sla-virtual-machines",
    "sql-database",
    "synapse-analytics",
    "traffic-manager",
    "virtual-machine-scale-sets",
    "virtual-machines",
)


def test_real_catalog_has_expected_scope_and_deterministic_item_order() -> None:
    catalog = ProductCatalog.load(PROJECT_ROOT)

    assert len(catalog.definitions) == 211
    assert catalog.scope_product_keys == EXPECTED_SCOPE

    first = catalog.select(all_products=True)
    second = catalog.select(all_products=True)
    assert first == second
    assert len(first) == 62
    assert [(item.product_key, item.language) for item in first] == [
        (product_key, language)
        for product_key in EXPECTED_SCOPE
        for language in ("zh-cn", "en-us")
    ]


def test_management_category_is_exactly_eight_bilingual_products() -> None:
    catalog = ProductCatalog.load(PROJECT_ROOT)
    items = catalog.select(category="management")

    expected_products = (
        "advisor",
        "automation",
        "azure-firewall",
        "azure-policy",
        "azure-update-management-center",
        "backup",
        "monitor",
        "scheduler",
    )
    assert len(items) == 16
    assert [(item.product_key, item.language) for item in items] == [
        (product_key, language)
        for product_key in expected_products
        for language in ("zh-cn", "en-us")
    ]


def test_single_product_always_selects_chinese_and_english() -> None:
    catalog = ProductCatalog.load(PROJECT_ROOT)

    items = catalog.select(product_key="service-bus")

    assert [(item.product_key, item.language) for item in items] == [
        ("service-bus", "zh-cn"),
        ("service-bus", "en-us"),
    ]


def test_explicit_products_preserve_requested_order_and_expand_both_languages() -> None:
    catalog = ProductCatalog.load(PROJECT_ROOT)

    items = catalog.select(
        product_keys=("service-bus", "api-management", "event-grid")
    )

    assert [(item.product_key, item.language) for item in items] == [
        (product_key, language)
        for product_key in ("service-bus", "api-management", "event-grid")
        for language in ("zh-cn", "en-us")
    ]


def test_explicit_products_reject_empty_duplicate_and_unknown_keys() -> None:
    catalog = ProductCatalog.load(PROJECT_ROOT)

    with pytest.raises(CatalogError, match="至少需要一个"):
        catalog.select(product_keys=())
    with pytest.raises(CatalogError, match="不能是单段文本"):
        catalog.select(product_keys="service-bus")
    with pytest.raises(CatalogError, match="必须是非空文本"):
        catalog.select(product_keys=("service-bus", ""))
    with pytest.raises(CatalogError, match="不能重复"):
        catalog.select(product_keys=("service-bus", "service-bus"))
    with pytest.raises(UnknownProductError, match="未知 Product Key"):
        catalog.select(product_keys=("service-bus", "does-not-exist"))


def test_support_article_type_can_be_selected_as_a_category() -> None:
    catalog = ProductCatalog.load(PROJECT_ROOT)

    items = catalog.select(category="SLA")

    assert len(items) == 6
    assert {item.product_key for item in items} == {
        "sla-api-management",
        "sla-databricks",
        "sla-virtual-machines",
    }


def test_event_grid_is_selected_even_though_reference_status_is_old() -> None:
    config_path = (
        PROJECT_ROOT
        / "data"
        / "configs"
        / "products-config"
        / "pricing"
        / "event-grid.json"
    )
    reference_data = json.loads(config_path.read_text(encoding="utf-8"))
    assert reference_data["capability_status"] == "known_unsupported"

    catalog = ProductCatalog.load(PROJECT_ROOT)
    items = catalog.select(product_key="event-grid")

    assert [item.language for item in items] == ["zh-cn", "en-us"]


def test_unknown_product_and_category_have_readable_errors() -> None:
    catalog = ProductCatalog.load(PROJECT_ROOT)

    with pytest.raises(UnknownProductError, match="未知 Product Key"):
        catalog.select(product_key="does-not-exist")
    with pytest.raises(UnknownCategoryError, match="没有 Category"):
        catalog.select(category="does-not-exist")


def test_duplicate_product_key_is_rejected(project_builder) -> None:
    project_root = project_builder()
    support_path = (
        project_root
        / "data"
        / "configs"
        / "products-config"
        / "support-articles"
        / "sample-product.json"
    )
    support_path.write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "product_key": "sample-product",
                "display_name": "duplicate",
                "slug": "sample-product",
                "page_model": "SupportArticlePage",
                "support_article_type": "SLA",
                "sources": {
                    language: {
                        "snapshot_path": "SupportArticles/SLA/sample/index.html"
                    }
                    for language in ("zh-cn", "en-us")
                },
                "extraction": {"semantic_strategy": "support_article"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="Product Key 重复"):
        ProductCatalog.load(project_root)


def test_source_path_cannot_escape_input_directory(project_builder) -> None:
    project_root = project_builder()
    config_path = (
        project_root
        / "data"
        / "configs"
        / "products-config"
        / "pricing"
        / "sample-product.json"
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["sources"]["zh-cn"]["snapshot_path"] = "../outside.html"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(CatalogError, match="越出输入目录"):
        ProductCatalog.load(project_root)
