from __future__ import annotations

import json
from copy import deepcopy

from bs4 import BeautifulSoup
import pytest

from src.core.catalog import ProductCatalog
from src.core.payload_contract import payload_json_bytes
from src.extractors.strategy_extractor import _strategy_config, extract_processing_item
from src.machine_checks.l3b import run_l3b
from src.strategies.complex_content_strategy import ComplexContentStrategy
from src.utils.html.normalization import normalize_html, parse_html_bytes
from tests.m2_helpers import PROJECT_ROOT


@pytest.fixture(params=("zh-cn", "en-us"))
def language(request):
    return request.param


@pytest.fixture
def catalog():
    reference = ProductCatalog.load(PROJECT_ROOT)
    return ProductCatalog(
        PROJECT_ROOT, reference.definitions, ("purview",), reference.languages
    )


def _source_path(language):
    return PROJECT_ROOT / "data" / "prod-html" / language / "pricing" / "purview.html"


def _source(language):
    path = _source_path(language)
    return parse_html_bytes(path.read_bytes(), source_name=str(path))


def _payload(catalog, language):
    item = next(
        item for item in catalog.select(product_key="purview")
        if item.language == language
    )
    return extract_processing_item(catalog, item)


def _strategy(catalog, language, *, product_key="purview"):
    config = _strategy_config(
        catalog.get_definition("purview"),
        language=language,
        project_root=PROJECT_ROOT,
    )
    config["product_key"] = product_key
    return ComplexContentStrategy(config, str(_source_path(language)))


def _check(tmp_path, payload, language, *, source_path=None, product_key="purview"):
    payload_path = tmp_path / f"{language}.json"
    payload_path.write_bytes(payload_json_bytes(payload))
    return run_l3b(
        frozen_html_path=source_path or _source_path(language),
        payload_path=payload_path,
        product_key=product_key,
        language=language,
        semantic_strategy="complex",
        soft_category_path=PROJECT_ROOT / "data" / "configs" / "soft-category.json",
    )


def _prose(node):
    return [
        " ".join(element.get_text(" ", strip=True).split())
        for element in node.select("h3, h4, p")
    ]


def test_purview_appends_both_applications_to_each_category(catalog, language, tmp_path):
    source = _source(language)
    payload = _payload(catalog, language)
    primary_ids = ["tabContent1-1", "tabContent1-2", "tabContent1-3"]
    applications = source.find(id="tabContent1-4").parent.parent.parent
    introduction = source.select_one("#tabContent1 > .tab-content > .scroll-table")
    application_tables = [
        table
        for target in ("tabContent1-4", "tabContent1-5")
        for table in source.find(id=target).find_all("table")
    ]
    definitions = json.loads(payload["pageConfig"]["filtersJsonConfig"])[
        "filterDefinitions"
    ]
    categories = next(row for row in definitions if row["filterKey"] == "category")

    assert [option["value"] for option in categories["options"]] == primary_ids
    assert len(payload["contentGroups"]) == 3
    for group, target, table_count in zip(
        payload["contentGroups"], primary_ids, (3, 4, 3)
    ):
        criteria = json.loads(group["filterCriteriaJson"])
        assert next(
            row["matchValues"] for row in criteria if row["filterKey"] == "category"
        ) == target
        content = BeautifulSoup(group["content"], "html.parser")
        panel = content.find(id=target)
        assert panel is not None
        assert content.select(".tab-panel") == [panel]
        assert not content.select(".tab-nav, .pricing-detail-tab, select")
        # The obsolete English navigation comment must not retain these IDs either.
        assert "tabContent1-4" not in group["content"]
        assert "tabContent1-5" not in group["content"]
        assert _prose(panel) == _prose(source.find(id=target)) + _prose(applications)
        expected_tables = source.find(id=target).find_all("table") + application_tables
        assert len(panel.find_all("table")) == table_count
        assert [normalize_html(str(table)) for table in panel.find_all("table")] == [
            normalize_html(str(table)) for table in expected_tables
        ]
        assert group["sharedContent"] == normalize_html(str(introduction))

    report = _check(tmp_path, payload, language)
    assert report["status"] == "passed"
    assert all(
        "tabContent1-4、tabContent1-5" in field["source_boundary"]
        for field in report["fields"]
        if field["payload_path"].startswith("contentGroups[")
        and field["payload_path"].endswith("].content")
    )


def test_purview_projection_keeps_the_source_dom_unchanged(catalog, language):
    source = _source(language)
    original = str(source)
    strategy = _strategy(catalog, language)
    url = catalog.get_definition("purview").source_for(language).url

    first = strategy.extract_flexible_content(source, url)
    second = strategy.extract_flexible_content(source, url)

    assert str(source) == original
    assert second == first


@pytest.mark.parametrize("mutation", (
    "remove_catalog_table", "remove_insights_table", "reverse_tables",
    "drop_shared_content", "restore_tab_wrapper",
))
def test_l3b_rejects_incomplete_or_reordered_purview_content(
    catalog, language, tmp_path, mutation
):
    payload = _payload(catalog, language)
    group = payload["contentGroups"][2]
    content = BeautifulSoup(group["content"], "html.parser")
    tables = content.find_all("table")
    if mutation == "remove_catalog_table":
        tables[-2].decompose()
    elif mutation == "remove_insights_table":
        tables[-1].decompose()
    elif mutation == "reverse_tables":
        tables[-2].insert_before(tables[-1].extract())
    elif mutation == "drop_shared_content":
        group["sharedContent"] = ""
    else:
        wrapper = content.new_tag("div", id="tabContent1-5")
        wrapper["class"] = ["tab-panel"]
        tables[-1].wrap(wrapper)
    group["content"] = str(content)

    report = _check(tmp_path, payload, language)

    assert report["status"] == "failed"
    field = "sharedContent" if mutation == "drop_shared_content" else "content"
    assert next(
        result for result in report["fields"]
        if result["payload_path"] == f"contentGroups[2].{field}"
    )["status"] == "failed"


def test_l3b_independently_detects_the_old_purview_omission(
    catalog, language, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        ComplexContentStrategy,
        "_purview_content_leaves",
        lambda _self, _software, leaves: (leaves, []),
    )
    payload = _payload(catalog, language)

    report = _check(tmp_path, payload, language)

    assert report["status"] == "failed"
    assert all(
        field["status"] == "failed"
        for field in report["fields"]
        if field["payload_path"].startswith("contentGroups[")
        and field["payload_path"].endswith(("].content", "].sharedContent"))
    )


@pytest.mark.parametrize("mutation", (
    "missing_panel", "duplicate_panel", "extra_panel", "wrong_navigation",
    "extra_block", "direct_text",
))
def test_purview_blocks_unproven_source_layouts(
    catalog, language, tmp_path, mutation
):
    payload = _payload(catalog, language)
    source = _source(language)
    last_panel = source.find(id="tabContent1-5")
    body = source.select_one("#tabContent1 > .tab-content")
    if mutation == "missing_panel":
        last_panel.decompose()
    elif mutation in {"duplicate_panel", "extra_panel"}:
        added = deepcopy(last_panel)
        if mutation == "extra_panel":
            added["id"] = "tabContent1-6"
        last_panel.parent.append(added)
    elif mutation == "wrong_navigation":
        source.select_one("ul.tab-nav a[data-href='#tabContent1-5']")[
            "data-href"
        ] = "#tabContent1-4"
    elif mutation == "extra_block":
        extra = source.new_tag("div")
        extra.string = "New pricing terms outside the approved blocks"
        body.append(extra)
    else:
        body.append("New direct pricing text")
    source_path = tmp_path / "changed-purview.html"
    source_path.write_text(str(source), encoding="utf-8")
    strategy = _strategy(catalog, language)
    url = catalog.get_definition("purview").source_for(language).url

    with pytest.raises(ValueError, match="Purview"):
        strategy.extract_flexible_content(source, url)
    report = _check(tmp_path, payload, language, source_path=source_path)
    assert report["status"] == "blocked"
    assert "Purview" in report["error"]


def test_purview_append_rule_does_not_apply_to_other_product_keys(
    catalog, language, tmp_path
):
    strategy = _strategy(catalog, language, product_key="other-product")
    source = _source(language)
    url = catalog.get_definition("purview").source_for(language).url

    payload = strategy.extract_flexible_content(source, url)

    assert [
        len(BeautifulSoup(group["content"], "html.parser").find_all("table"))
        for group in payload["contentGroups"]
    ] == [1, 2, 1]
    assert all("sharedContent" not in group for group in payload["contentGroups"])
    assert _check(
        tmp_path, payload, language, product_key="other-product"
    )["status"] == "passed"
