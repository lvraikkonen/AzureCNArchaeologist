from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from src.core.catalog import ProductCatalog
from src.core.payload_contract import payload_json_bytes
from src.core.scoped_source_content import (
    PageBodyBoundaryError,
    locate_simple_pricing_boundary,
)
from src.detectors.tab_detector import TabDetector
from src.extractors.strategy_extractor import (
    _strategy_config,
    extract_processing_item,
)
from src.machine_checks.l3b import run_l3b


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("zh-cn", "en-us")
UNWRAPPED_SIMPLE_PRODUCTS = (
    "azure-bastion",
    "azure-nat-gateway",
    "bot-services",
    "core-control-plane",
    "data-factory",
    "firewall-manager",
    "kubernetes-service",
    "route-server",
    "sql-edge",
    "storage",
)


def _upstream_source(
    catalog: ProductCatalog,
    product_key: str,
    language: str,
) -> Path:
    definition = catalog.get_definition(product_key)
    return (
        catalog.project_root
        / "data"
        / "current_prod_html"
        / language
        / definition.source_for(language).snapshot_path
    )


def _extract_upstream(
    tmp_path: Path,
    *,
    product_key: str,
    language: str,
):
    catalog = ProductCatalog.load(PROJECT_ROOT)
    if product_key not in catalog.scope_product_keys:
        catalog = ProductCatalog(
            catalog.project_root,
            catalog.definitions,
            tuple(sorted((*catalog.scope_product_keys, product_key))),
            catalog.languages,
            catalog.strategy_overrides,
        )
    item = next(
        item
        for item in catalog.select(product_key=product_key)
        if item.language == language
    )
    source_path = _upstream_source(catalog, product_key, language)
    frozen_root = tmp_path / f"{product_key}-{language}-frozen"
    frozen_path = frozen_root.joinpath(*item.frozen_relative_path.parts)
    frozen_path.parent.mkdir(parents=True)
    frozen_path.write_bytes(source_path.read_bytes())
    payload = extract_processing_item(
        catalog,
        item,
        frozen_root=frozen_root,
        soft_category_path=(
            PROJECT_ROOT
            / "data"
            / "current_prod_html"
            / "soft-category.json"
        ),
    )
    return catalog, item, source_path, payload


def _l3b(
    tmp_path: Path,
    *,
    catalog: ProductCatalog,
    item,
    source_path: Path,
    payload: dict,
) -> dict:
    payload_path = tmp_path / f"{item.product_key}-{item.language}.json"
    payload_path.write_bytes(payload_json_bytes(payload))
    definition = catalog.get_definition(item.product_key)
    return run_l3b(
        frozen_html_path=source_path,
        payload_path=payload_path,
        product_key=item.product_key,
        language=item.language,
        page_model=definition.page_model,
        semantic_strategy=item.semantic_strategy,
        soft_category_path=(
            PROJECT_ROOT
            / "data"
            / "current_prod_html"
            / "soft-category.json"
        ),
        page_global_source_boundary=definition.page_global_source_boundary,
        region_content_rules=[
            rule.as_dict() for rule in definition.region_content_rules
        ] or None,
    )


@pytest.mark.parametrize("language", LANGUAGES)
def test_hdinsight_description_preserves_sla_mentions_and_all_intro_sections(tmp_path, language):
    catalog, item, source_path, payload = _extract_upstream(
        tmp_path, product_key="hdinsight", language=language
    )
    assert [s["sectionType"] for s in payload["commonSections"]] == [
        "Banner", "ProductDescription", "Qa"
    ]
    description = BeautifulSoup(payload["commonSections"][1]["content"], "html.parser")
    text = description.get_text(" ", strip=True)
    markers = (
        ["Azure HDInsight", "服务特征", "组件", "支持和服务级别协议", "定价详细信息"]
        if language == "zh-cn"
        else ["Azure HDInsight", "Service features", "Components", "Support and SLA", "Pricing Details"]
    )
    assert all(marker in text for marker in markers)
    assert _l3b(tmp_path, catalog=catalog, item=item, source_path=source_path, payload=payload)["status"] == "passed"

    # A partial description must fail even when ProductDescription still exists.
    description.find("p").decompose()
    incomplete = deepcopy(payload)
    incomplete["commonSections"][1]["content"] = str(description)
    assert _l3b(tmp_path, catalog=catalog, item=item, source_path=source_path, payload=incomplete)["status"] == "failed"


@pytest.mark.parametrize("language", LANGUAGES)
def test_managed_disks_has_visible_retained_tables_and_only_regional_descriptions(tmp_path, language):
    catalog, item, source_path, payload = _extract_upstream(
        tmp_path, product_key="storage-managed-disks", language=language
    )
    assert [key for key, definition in catalog.definitions.items() if definition.region_content_rules] == ["storage-managed-disks"]
    allowed = {
        "isn3": {"north-china3"},
        "notn3": {"east-china3", "east-china2", "north-china2", "east-china", "north-china"},
        "ise3": {"east-china3"},
        "note3": {"north-china3", "east-china2", "north-china2"},
        "zone1": {"east-china", "north-china"},
    }
    expected_tables = {
        "north-china3": {"region3", "ZRS"},
        "east-china3": {"region3"},
        "east-china2": {"region2"},
        "north-china2": {"region2"},
        "east-china": {"base"},
        "north-china": {"base"},
    }
    assert len(payload["contentGroups"]) == 6
    for group in payload["contentGroups"]:
        region = json.loads(group["filterCriteriaJson"])[0]["matchValues"]
        html = BeautifulSoup(group["content"], "html.parser")
        for class_name, visible_regions in allowed.items():
            assert bool(html.select(f"div.{class_name}")) == (region in visible_regions)
        for suffix in ("base", "region2", "region3", "ZRS"):
            table_id = "managed-disks-premium" + ("" if suffix == "base" else f"-{suffix}")
            assert bool(html.find("table", id=table_id)) == (suffix in expected_tables[region])
        for table in html.find_all("table"):
            for node in [table, *table.parents]:
                assert not re.search(r"display\s*:\s*none", str(node.get("style", "")), re.I)
    assert _l3b(tmp_path, catalog=catalog, item=item, source_path=source_path, payload=payload)["status"] == "passed"

    for mutation in ("rehide-table", "wrong-region-note", "missing-table"):
        changed = deepcopy(payload)
        north = next(g for g in changed["contentGroups"] if '"north-china3"' in g["filterCriteriaJson"])
        html = BeautifulSoup(north["content"], "html.parser")
        if mutation == "rehide-table":
            html.find(id="managed-disks-premium-region3")["style"] = "display:none"
        elif mutation == "missing-table":
            html.find(id="managed-disks-premium-ZRS").decompose()
        else:
            note = html.new_tag("div", attrs={"class": "notn3"})
            note.string = "Wrong region description"
            html.div.append(note)
        north["content"] = str(html)
        assert _l3b(tmp_path, catalog=catalog, item=item, source_path=source_path, payload=changed)["status"] == "failed", mutation


def test_processing_scope_uses_product_definition_strategies_directly() -> None:
    scope = json.loads(
        (
            PROJECT_ROOT / "data" / "configs" / "processing-scope.json"
        ).read_text(encoding="utf-8")
    )
    catalog = ProductCatalog.load(PROJECT_ROOT)

    assert "strategy_overrides" not in scope
    assert catalog.strategy_overrides == {}
    assert catalog.effective_strategy("event-grid") == "simple_static"
    assert catalog.effective_strategy("monitor") == "complex"


@pytest.mark.parametrize("language", LANGUAGES)
def test_corrected_event_grid_is_a_complete_simple_page(
    tmp_path: Path,
    language: str,
) -> None:
    catalog, item, source_path, payload = _extract_upstream(
        tmp_path,
        product_key="event-grid",
        language=language,
    )

    assert item.semantic_strategy == "simple_static"
    assert payload["pageConfig"]["pageType"] == "Simple"
    assert payload["contentGroups"] == []
    base_content = BeautifulSoup(payload["baseContent"], "html.parser")
    assert len(base_content.find_all("table")) == 3
    assert _l3b(
        tmp_path,
        catalog=catalog,
        item=item,
        source_path=source_path,
        payload=payload,
    )["status"] == "passed"


def test_event_grid_simple_table_boundary_rejects_state_controls() -> None:
    catalog = ProductCatalog.load(PROJECT_ROOT)
    definition = catalog.get_definition("event-grid")
    source_path = _upstream_source(catalog, "event-grid", "zh-cn")
    soup = BeautifulSoup(source_path.read_bytes(), "html.parser")
    pricing_section = soup.select_one(
        "div.pure-content > div.pricing-page-section"
    )
    assert pricing_section is not None
    pricing_section.append(soup.new_tag("select"))
    config = _strategy_config(
        definition,
        semantic_strategy="simple_static",
        language="zh-cn",
    )

    with pytest.raises(PageBodyBoundaryError, match="没有唯一"):
        locate_simple_pricing_boundary(
            soup,
            config,
            language="zh-cn",
        )


@pytest.mark.parametrize("product_key", UNWRAPPED_SIMPLE_PRODUCTS)
@pytest.mark.parametrize("language", LANGUAGES)
def test_confirmed_unwrapped_simple_pages_match_independent_l3b(
    tmp_path: Path,
    product_key: str,
    language: str,
) -> None:
    catalog, item, source_path, payload = _extract_upstream(
        tmp_path,
        product_key=product_key,
        language=language,
    )

    assert item.semantic_strategy == "simple_static"
    assert payload["pageConfig"]["pageType"] == "Simple"
    assert payload["baseContent"]
    assert payload["contentGroups"] == []
    assert _l3b(
        tmp_path,
        catalog=catalog,
        item=item,
        source_path=source_path,
        payload=payload,
    )["status"] == "passed"

    section_types = [
        section["sectionType"] for section in payload["commonSections"]
    ]
    if product_key in {"bot-services", "core-control-plane"}:
        assert section_types == ["Banner"]
    if product_key == "data-factory":
        assert len(
            BeautifulSoup(payload["baseContent"], "html.parser").select(
                "div.pricing-page-section"
            )
        ) == 3
    if product_key == "kubernetes-service":
        assert section_types == ["Banner", "Qa"]


@pytest.mark.parametrize(
    ("language", "heading"),
    (("zh-cn", "详细信息"), ("en-us", "More information")),
)
def test_azure_functions_preserves_declared_page_global_details(
    tmp_path: Path,
    language: str,
    heading: str,
) -> None:
    catalog, item, source_path, payload = _extract_upstream(
        tmp_path,
        product_key="azure-functions",
        language=language,
    )

    assert heading in BeautifulSoup(
        payload["baseContent"], "html.parser"
    ).get_text(" ", strip=True)
    assert _l3b(
        tmp_path,
        catalog=catalog,
        item=item,
        source_path=source_path,
        payload=payload,
    )["status"] == "passed"


@pytest.mark.parametrize("language", LANGUAGES)
def test_active_directory_ds_preserves_support_and_sla(
    tmp_path: Path,
    language: str,
) -> None:
    catalog, item, source_path, payload = _extract_upstream(
        tmp_path,
        product_key="active-directory-ds",
        language=language,
    )

    qa_sections = [
        section
        for section in payload["commonSections"]
        if section["sectionType"] == "Qa"
    ]
    assert len(qa_sections) == 1
    assert "sla" in BeautifulSoup(
        qa_sections[0]["content"], "html.parser"
    ).get_text(" ", strip=True).casefold()
    assert _l3b(
        tmp_path,
        catalog=catalog,
        item=item,
        source_path=source_path,
        payload=payload,
    )["status"] == "passed"


@pytest.mark.parametrize("language", LANGUAGES)
def test_monitor_static_software_panel_is_a_complete_complex_page(
    tmp_path: Path,
    language: str,
) -> None:
    catalog, item, source_path, payload = _extract_upstream(
        tmp_path,
        product_key="monitor",
        language=language,
    )
    tabs = TabDetector().detect_tabs(
        BeautifulSoup(source_path.read_bytes(), "html.parser")
    )
    criteria = [
        json.loads(group["filterCriteriaJson"])
        for group in payload["contentGroups"]
    ]

    assert item.semantic_strategy == "complex"
    assert tabs["total_category_tabs"] == 5
    assert tabs["content_groups"] == [
        {
            "id": "tabContent1",
            "has_category_tabs": True,
            "category_tabs_count": 5,
        }
    ]
    assert payload["pageConfig"]["pageType"] == "ComplexFilter"
    assert len(payload["contentGroups"]) == 30
    assert {
        criterion[0]["matchValues"] for criterion in criteria
    } == {
        "east-china",
        "east-china2",
        "north-china",
        "north-china2",
        "north-china3",
        "east-china3",
    }
    assert {
        criterion[1]["matchValues"] for criterion in criteria
    } == {
        "tabContent1-1",
        "tabContent1-2",
        "tabContent1-3",
        "tabContent1-4",
        "tabContent1-5",
    }
    assert all(
        [row["filterKey"] for row in criterion] == ["region", "category"]
        for criterion in criteria
    )
    _, _, _, repeated_payload = _extract_upstream(
        tmp_path / "repeat",
        product_key="monitor",
        language=language,
    )
    assert payload_json_bytes(repeated_payload) == payload_json_bytes(payload)
    assert _l3b(
        tmp_path,
        catalog=catalog,
        item=item,
        source_path=source_path,
        payload=payload,
    )["status"] == "passed"


@pytest.mark.parametrize("language", LANGUAGES)
def test_postgresql_trailing_extended_support_is_region_shared_content(
    tmp_path: Path,
    language: str,
) -> None:
    catalog, item, source_path, payload = _extract_upstream(
        tmp_path,
        product_key="postgresql",
        language=language,
    )

    assert payload["baseContent"] == ""
    assert len(payload["contentGroups"]) == 18
    assert all("sharedContent" in group for group in payload["contentGroups"])

    east3 = "Azure_PostgreSQL_Database_Extended_Support_East3"
    other_regions = "Azure_PostgreSQL_Database_Extended_Support_E2N2N3"
    retained_tables = {
        "east-china3": {east3},
        "east-china2": {other_regions},
        "north-china2": {other_regions},
        "north-china3": {other_regions},
        "east-china": set(),
        "north-china": set(),
    }
    heading = "扩展支持" if language == "zh-cn" else "Extended Support"
    categories_by_region: dict[str, int] = {}
    for group in payload["contentGroups"]:
        criteria = json.loads(group["filterCriteriaJson"])
        assert [criterion["filterKey"] for criterion in criteria] == [
            "region",
            "category",
        ]
        region = criteria[0]["matchValues"]
        categories_by_region[region] = categories_by_region.get(region, 0) + 1
        shared_content = group["sharedContent"]
        assert heading in shared_content
        assert heading not in group["content"]
        actual_tables = {
            table_id
            for table_id in (east3, other_regions)
            if f'id="{table_id}"' in shared_content
        }
        assert actual_tables == retained_tables[region]

    assert categories_by_region == {
        "east-china3": 3,
        "east-china2": 3,
        "north-china2": 3,
        "north-china3": 3,
        "east-china": 3,
        "north-china": 3,
    }
    assert _l3b(
        tmp_path,
        catalog=catalog,
        item=item,
        source_path=source_path,
        payload=payload,
    )["status"] == "passed"
