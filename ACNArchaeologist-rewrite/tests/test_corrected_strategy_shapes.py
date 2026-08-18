from __future__ import annotations

import json
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
    )


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
