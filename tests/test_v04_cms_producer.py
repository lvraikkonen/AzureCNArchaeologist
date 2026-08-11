from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from src.core.cms_state_contract import CmsState
from src.core.scoped_source_content import (
    ScopedSourceContentError,
    extract_software_scoped_prefix,
)
from src.core.source_reachability import (
    ReachabilityFilterDefinition,
    ReachabilityOption,
    ReachabilitySourceEvidence,
    ReachableCmsState,
    SourceReachability,
)
from src.detectors.filter_detector import FilterDetector
from src.detectors.tab_detector import TabDetector
from src.strategies.complex_content_strategy import ComplexContentStrategy
from src.utils.content.section_extractor import (
    CommonSectionBoundaryError,
    SectionExtractor,
    is_exact_owned_faq_documentation_boundary,
)
from src.utils.content.flexible_builder import FlexibleBuilder


def _filter_html(
    region_options: str,
    desktop_region_links: str,
) -> BeautifulSoup:
    return BeautifulSoup(
        f"""
        <div class="dropdown-container software-kind-container" style="display: none">
          <label>Software category:</label>
          <select id="software-box">
            <option selected value="Internal Product" data-href="#tabContent1">Internal</option>
          </select>
        </div>
        <div class="dropdown-container region-container">
          <label>Region:</label>
          <div class="dropdown-box os-tab-nav hidden-sm hidden-xs">
            <span class="selected-item">China East 2</span>
            <ol class="tab-items">{desktop_region_links}</ol>
          </div>
          <select id="region-box">{region_options}</select>
        </div>
        """,
        "html.parser",
    )


def _core_filter_analysis() -> dict:
    return FilterDetector().detect_filters(
        _filter_html(
            """
            <option value="north-china" data-href="#north-china">China North</option>
            <option selected value="east-china2" data-href="#east-china2">China East 2</option>
            """,
            """
            <li><a id="north-china" data-href="#north-china">China North</a></li>
            <li class="active"><a id="east-china2" data-href="#east-china2">China East 2</a></li>
            """,
        )
    )


def _base_metadata() -> dict[str, str]:
    return {
        "Title": "Example",
        "MetaTitle": "",
        "MetaDescription": "",
        "MetaKeywords": "",
        "Slug": "example",
        "Language": "en-us",
        "MSServiceName": "example",
    }


def _sparse_source_reachability() -> SourceReachability:
    region_definition = ReachabilityFilterDefinition(
        filter_key="region",
        filter_type="dropdown",
        display_name="Region",
        options=(
            ReachabilityOption(
                "east-china2",
                "China East 2",
                "#east-china2",
                True,
            ),
            ReachabilityOption(
                "north-china",
                "China North",
                "#north-china",
                False,
            ),
        ),
    )
    category_definition = ReachabilityFilterDefinition(
        filter_key="category",
        filter_type="tab",
        display_name="Category",
        options=(
            ReachabilityOption(
                "tabContent1-2",
                "Memory",
                "#tabContent1-2",
                True,
                parent_value="Internal Product",
                parent_panel_id="tabContent1",
            ),
            ReachabilityOption(
                "tabContent1-1",
                "General",
                "#tabContent1-1",
                False,
                parent_value="Internal Product",
                parent_panel_id="tabContent1",
            ),
        ),
    )
    state_specs = (
        ("east-china2", "tabContent1-2", "China East 2", "Memory", True),
        ("east-china2", "tabContent1-1", "China East 2", "General", False),
        # The source proves no north-china × memory state.
        ("north-china", "tabContent1-1", "China North", "General", False),
    )
    states = tuple(
        ReachableCmsState(
            cms_state=CmsState(
                (
                    ("region", region),
                    ("category", category),
                )
            ),
            state_label_segments=(region_label, category_label),
            mapping_key=f"{region}_Internal Product_{category}",
            source_evidence=ReachabilitySourceEvidence(
                region_value=region,
                region_href=f"#{region}",
                software_value="Internal Product",
                software_href="#tabContent1",
                software_panel_id="tabContent1",
                software_visible=False,
                category_value=category,
                category_href=f"#{category}",
                category_panel_id=category,
            ),
            is_default=is_default,
        )
        for (
            region,
            category,
            region_label,
            category_label,
            is_default,
        ) in state_specs
    )
    return SourceReachability(
        product_key="example",
        language="en-us",
        source_path="source.html",
        normalized_path="normalized.html",
        source_sha256="a" * 64,
        normalized_sha256="a" * 64,
        filter_definitions_union=(region_definition, category_definition),
        ordered_states=states,
        default_state=states[0].cms_state,
        suppressed_options=(),
        unreachable_panel_ids=(),
        findings=(),
    )


def test_filter_detector_uses_desktop_order_and_moves_default_first():
    desktop_links = """
        <li><a id="north-china3" data-href="#north-china3">China North 3</a></li>
        <li class="active"><a id="east-china2" data-href="#east-china2">China East 2</a></li>
        <li><a id="north-china2" data-href="#north-china2">China North 2</a></li>
        <li><a id="east-china" data-href="#east-china">China East</a></li>
        <li><a id="north-china" data-href="#north-china">China North</a></li>
    """
    first = FilterDetector().detect_filters(
        _filter_html(
            """
            <option value="north-china3" data-href="#north-china3">China North 3</option>
            <option selected value="east-china2" data-href="#east-china2">China East 2</option>
            <option value="north-china2" data-href="#north-china2">China North 2</option>
            <option value="east-china" data-href="#east-china">China East</option>
            <option value="north-china" data-href="#north-china">China North</option>
            """,
            desktop_links,
        )
    )
    second = FilterDetector().detect_filters(
        _filter_html(
            """
            <option selected value="east-china2" data-href="#east-china2">China East 2</option>
            <option value="north-china2" data-href="#north-china2">China North 2</option>
            <option value="east-china" data-href="#east-china">China East</option>
            <option value="north-china" data-href="#north-china">China North</option>
            <option value="north-china3" data-href="#north-china3">China North 3</option>
            """,
            desktop_links,
        )
    )

    assert first["has_software"] is True
    assert first["software_visible"] is False
    assert [item["value"] for item in first["software_options"]] == [
        "Internal Product"
    ]
    assert first["software_options"][0]["is_default"] is True
    expected_regions = [
        "east-china2",
        "north-china3",
        "north-china2",
        "east-china",
        "north-china",
    ]
    assert [item["value"] for item in first["region_options"]] == expected_regions
    assert [item["value"] for item in second["region_options"]] == expected_regions
    assert first["region_options"][0]["is_default"] is True


def test_filter_detector_ignores_stale_summary_when_explicit_defaults_agree():
    analysis = FilterDetector().detect_filters(
        _filter_html(
            """
            <option value="east-china2" data-href="#east-china2">China East 2</option>
            <option selected value="north-china3" data-href="#north-china3">China North 3</option>
            """,
            """
            <li><a id="east-china2" data-href="#east-china2">China East 2</a></li>
            <li class="active"><a id="north-china3" data-href="#north-china3">China North 3</a></li>
            """,
        )
    )

    assert analysis["region_default_value"] == "north-china3"
    assert analysis["region_options"][0] == {
        "value": "north-china3",
        "href": "#north-china3",
        "label": "China North 3",
        "is_default": True,
    }


def test_filter_detector_uses_region_target_as_canonical_machine_value():
    analysis = FilterDetector().detect_filters(
        _filter_html(
            """
            <option selected value="north-china3" data-href="#east-china3">China East 3</option>
            <option value="north-china3" data-href="#north-china3">China North 3</option>
            """,
            """
            <li class="active"><a id="east-china3" data-href="#east-china3">China East 3</a></li>
            <li><a id="north-china3" data-href="#north-china3">China North 3</a></li>
            """,
        )
    )

    assert analysis["region_default_value"] == "east-china3"
    assert [option["value"] for option in analysis["region_options"]] == [
        "east-china3",
        "north-china3",
    ]


def test_tab_detector_moves_active_tab_first_and_preserves_other_order():
    soup = BeautifulSoup(
        """
        <div class="technical-azure-selector pricing-detail-tab">
          <div class="tab-content"><div class="tab-panel" id="tabContent1">
            <div class="category-container"><span class="category-title">Category:</span>
              <ul class="os-tab-nav category-tabs hidden-xs hidden-sm">
                <li><a data-href="#tabContent1-3" id="three">Three</a></li>
                <li class="active"><a data-href="#tabContent1-2" id="two">Two</a></li>
                <li><a data-href="#tabContent1-4" id="four">Four</a></li>
                <li><a data-href="#tabContent1-1" id="one">One</a></li>
              </ul>
            </div>
            <div class="tab-content">
              <div class="tab-panel" id="tabContent1-1">one</div>
              <div class="tab-panel" id="tabContent1-2">two</div>
              <div class="tab-panel" id="tabContent1-4">four</div>
            </div>
          </div></div>
        </div>
        """,
        "html.parser",
    )

    analysis = TabDetector().detect_tabs(soup)
    assert [tab["href"] for tab in analysis["category_tabs"]] == [
        "#tabContent1-2",
        "#tabContent1-3",
        "#tabContent1-4",
        "#tabContent1-1",
    ]
    assert analysis["category_tabs"][0]["is_default"] is True
    assert analysis["category_tabs"][0]["target_exists"] is True
    assert analysis["category_tabs"][1]["target_exists"] is False
    assert analysis["category_display_name"] == "Category"


def test_region_page_exposes_only_region_and_uses_compact_nested_json():
    analysis = _core_filter_analysis()
    builder = FlexibleBuilder()
    groups = builder.build_region_content_groups(
        {
            "north-china": "<table><tr><td>¥2</td></tr></table>",
            "east-china2": "<table><tr><td>¥1</td></tr></table>",
        },
        analysis,
    )
    payload = builder.build_flexible_page(
        _base_metadata(),
        [],
        {
            "baseContent": "",
            "contentGroups": groups,
            "strategy_type": "region_filter",
            "filter_analysis": analysis,
            "tab_analysis": {},
        },
    )

    config_text = payload["pageConfig"]["filtersJsonConfig"]
    definitions = json.loads(config_text)["filterDefinitions"]
    assert '": "' not in config_text
    assert '", "' not in config_text
    assert [definition["filterKey"] for definition in definitions] == ["region"]
    assert [option["value"] for option in definitions[0]["options"]] == [
        "east-china2",
        "north-china",
    ]
    assert [group["groupName"] for group in groups] == [
        "China East 2",
        "China North",
    ]
    assert groups[0]["filterCriteriaJson"] == (
        '[{"filterKey":"region","matchValues":"east-china2"}]'
    )


def test_complex_page_materializes_only_source_proven_sparse_relation():
    source_reachability = _sparse_source_reachability()
    mapping = {
        state.cms_state: {
            "shared_content": "",
            "content": (
                "<table><tr><td>"
                f"{state.mapping_key}"
                "</td></tr></table>"
            ),
        }
        for state in source_reachability.ordered_states
    }

    builder = FlexibleBuilder()
    groups = builder.build_complex_content_groups(
        source_reachability, mapping
    )
    payload = builder.build_flexible_page(
        _base_metadata(),
        [],
        {
            "baseContent": "",
            "contentGroups": groups,
            "strategy_type": "complex",
            "source_reachability": source_reachability,
        },
    )

    assert len(groups) == 3
    assert [group["sortOrder"] for group in groups] == [1, 2, 3]
    assert all(group["isActive"] is True for group in groups)
    assert all("sharedContent" not in group for group in groups)
    criteria = [json.loads(group["filterCriteriaJson"]) for group in groups]
    assert all(
        [criterion["filterKey"] for criterion in state]
        == ["region", "category"]
        for state in criteria
    )
    definitions = json.loads(
        payload["pageConfig"]["filtersJsonConfig"]
    )["filterDefinitions"]
    assert [definition["filterKey"] for definition in definitions] == [
        "region",
        "category",
    ]
    assert [group["groupName"] for group in groups] == [
        "China East 2 - Memory",
        "China East 2 - General",
        "China North - General",
    ]


def test_complex_builder_rejects_incomplete_state_mapping():
    with pytest.raises(ValueError, match="must equal"):
        FlexibleBuilder().build_complex_content_groups(
            _sparse_source_reachability(), {}
        )


def test_complex_builder_preserves_mixed_paths_with_missing_category():
    source_reachability = _sparse_source_reachability()
    first = source_reachability.ordered_states[0]
    region_only = ReachableCmsState(
        cms_state=CmsState((("region", "north-china"),)),
        state_label_segments=("China North",),
        mapping_key="north-china_Internal Product",
        source_evidence=ReachabilitySourceEvidence(
            region_value="north-china",
            region_href="#north-china",
            software_value="Internal Product",
            software_href="#tabContent1",
            software_panel_id="tabContent1",
            software_visible=False,
            category_value=None,
            category_href=None,
            category_panel_id=None,
        ),
        is_default=False,
    )
    mixed = replace(
        source_reachability,
        ordered_states=(first, region_only),
    )
    mapping = {
        state.cms_state: {
            "shared_content": "",
            "content": f"<div>{state.mapping_key}</div>",
        }
        for state in mixed.ordered_states
    }

    groups = FlexibleBuilder().build_complex_content_groups(mixed, mapping)

    assert groups[1]["groupName"] == "China North"
    assert json.loads(groups[1]["filterCriteriaJson"]) == [
        {"filterKey": "region", "matchValues": "north-china"}
    ]


def test_complex_builder_rejects_unclassified_shared_content():
    source_reachability = _sparse_source_reachability()
    mapping = {
        state.cms_state: {
            "shared_content": "<p>global fragment</p>",
            "content": "<table><tr><td>¥1</td></tr></table>",
        }
        for state in source_reachability.ordered_states
    }
    with pytest.raises(ValueError, match="Unclassified shared content"):
        FlexibleBuilder().build_complex_content_groups(
            source_reachability, mapping
        )


def test_unvalidated_experiment_prunes_missing_all_for_any_product():
    soup = BeautifulSoup(
        '<div id="tabContent1-1">General</div>', "html.parser"
    )
    all_tab = {
        "href": "#tabContent1-0",
        "label": "All",
        "is_default": True,
        "target_exists": False,
    }
    general_tab = {
        "href": "#tabContent1-1",
        "label": "General",
        "is_default": False,
        "target_exists": True,
    }
    missing_specific = {
        "href": "#tabContent1-2",
        "label": "Memory",
        "is_default": False,
        "target_exists": False,
    }
    analysis = {
        "category_tabs": [all_tab, general_tab, missing_specific],
        "total_category_tabs": 3,
        "has_tabs": True,
        "has_complex_tabs": True,
    }
    grouped = {
        "tabContent1": copy.deepcopy(analysis["category_tabs"])
    }
    strategy = object.__new__(ComplexContentStrategy)
    strategy.product_config = {"product_key": "cloud-services"}
    strategy._remove_missing_aggregate_tabs_for_unvalidated_experiment(
        soup, analysis, grouped
    )

    assert [tab["label"] for tab in analysis["category_tabs"]] == [
        "General",
        "Memory",
    ]
    assert analysis["category_tabs"][0]["is_default"] is True
    assert analysis["category_tabs"][1]["target_exists"] is False

    non_cloud = object.__new__(ComplexContentStrategy)
    non_cloud.product_config = {"product_key": "another-product"}
    non_cloud_analysis = {
        "category_tabs": [
            copy.deepcopy(all_tab),
            copy.deepcopy(general_tab),
        ],
        "total_category_tabs": 2,
        "has_tabs": True,
        "has_complex_tabs": True,
    }
    non_cloud_grouped = {
        "tabContent1": copy.deepcopy(
            non_cloud_analysis["category_tabs"]
        )
    }
    non_cloud._remove_missing_aggregate_tabs_for_unvalidated_experiment(
        soup, non_cloud_analysis, non_cloud_grouped
    )
    assert [
        tab["label"] for tab in non_cloud_analysis["category_tabs"]
    ] == ["General"]
    assert non_cloud_analysis["category_tabs"][0]["is_default"] is True


def test_unknown_strategy_and_missing_tab_target_fail_closed():
    builder = FlexibleBuilder()
    with pytest.raises(ValueError, match="Unknown semantic strategy"):
        builder.build_flexible_page(
            _base_metadata(),
            [],
            {
                "baseContent": "",
                "contentGroups": [],
                "strategy_type": "unknown",
            },
        )

    strategy = object.__new__(ComplexContentStrategy)
    with pytest.raises(ValueError, match="Missing target panel"):
        strategy._find_content_by_mapping(
            BeautifulSoup("<div></div>", "html.parser"),
            tab_id="missing",
        )


def test_formal_complex_extraction_cannot_omit_source_reachability():
    strategy = object.__new__(ComplexContentStrategy)
    with pytest.raises(TypeError, match="source_reachability"):
        strategy.extract_flexible_content(
            BeautifulSoup("<div></div>", "html.parser")
        )


@pytest.mark.parametrize("wrapper_class", ["tab-content", "tabContent"])
def test_formal_shared_content_uses_only_direct_category_wrapper(
    wrapper_class: str,
) -> None:
    soup = BeautifulSoup(
        f"""
        <div class="tab-panel" id="tabContent2">
          <div class="category-container-container">Category navigation</div>
          <div class="{wrapper_class}">
            <div class="tab-panel" id="tabContent2-1">
              <div class="tab-content">
                <p>Concrete Category content, never shared.</p>
              </div>
            </div>
          </div>
        </div>
        """,
        "html.parser",
    )
    assert (
        extract_software_scoped_prefix(
            soup,
            "tabContent2",
            expected_category_panel_ids=("tabContent2-1",),
        )
        is None
    )


def test_formal_shared_content_never_recurses_into_category_target() -> None:
    soup = BeautifulSoup(
        """
        <div class="tab-panel" id="tabContent2">
          <div class="category-container-container">Category navigation</div>
          <div class="other-wrapper">
            <div class="tab-panel" id="tabContent2-1">
              <div class="tab-content"><p>Category content.</p></div>
            </div>
          </div>
        </div>
        """,
        "html.parser",
    )
    with pytest.raises(
        ScopedSourceContentError, match="direct Category wrapper"
    ):
        extract_software_scoped_prefix(
            soup,
            "tabContent2",
            expected_category_panel_ids=("tabContent2-1",),
        )


def test_formal_shared_content_stops_at_first_direct_category_panel() -> None:
    soup = BeautifulSoup(
        """
        <div class="tab-panel" id="tabContent2">
          <div class="tab-content">
            <p>Software-scoped introduction.</p>
            <div class="tab-panel" id="tabContent2-1">
              <p>Concrete Category content.</p>
            </div>
          </div>
        </div>
        """,
        "html.parser",
    )
    prefix = extract_software_scoped_prefix(
        soup,
        "tabContent2",
        expected_category_panel_ids=("tabContent2-1",),
    )

    assert prefix is not None
    assert "Software-scoped introduction." in prefix.source_html
    assert "Concrete Category content." not in prefix.source_html


def test_common_sections_use_physical_order_and_close_missing_gaps():
    complete = BeautifulSoup(
        """
        <div class="common-banner"><p>Banner</p></div>
        <div class="pricing-page-section"><p>A complete product description.</p></div>
        <div class="technical-azure-selector pricing-detail-tab"><p>Main pricing</p></div>
        <div class="more-detail"><p>FAQ answer</p></div>
        <div class="pricing-page-section"><h2>SLA</h2><p>Support terms</p></div>
        """,
        "html.parser",
    )
    sections = SectionExtractor().extract_all_sections(complete)
    assert [section["sectionType"] for section in sections] == [
        "Banner",
        "ProductDescription",
        "Qa",
    ]
    assert [section["sortOrder"] for section in sections] == [1, 2, 3]

    missing_description = BeautifulSoup(
        """
        <div class="common-banner"><p>Banner</p></div>
        <div class="technical-azure-selector pricing-detail-tab"><p>Main pricing</p></div>
        <div class="more-detail"><p>FAQ answer</p></div>
        """,
        "html.parser",
    )
    sections = SectionExtractor().extract_all_sections(missing_description)
    assert [section["sectionType"] for section in sections] == [
        "Banner",
        "Qa",
    ]
    assert [section["sortOrder"] for section in sections] == [1, 2]


def test_common_sections_follow_reversed_source_order():
    soup = BeautifulSoup(
        """
        <div class="more-detail"><p>FAQ answer</p></div>
        <div class="common-banner"><p>Banner</p></div>
        <div class="pricing-page-section">
          <p>A complete product description.</p>
        </div>
        <div class="technical-azure-selector pricing-detail-tab">
          <p>Main pricing</p>
        </div>
        """,
        "html.parser",
    )

    sections = SectionExtractor().extract_all_sections(soup)

    assert [section["sectionType"] for section in sections] == [
        "Qa",
        "Banner",
        "ProductDescription",
    ]
    assert [section["sortOrder"] for section in sections] == [1, 2, 3]


def test_multiple_qa_nodes_keep_source_order_and_stable_section_order():
    soup = BeautifulSoup(
        """
        <div class="more-detail"><p>First FAQ answer</p></div>
        <div class="more-detail"><p>Second FAQ answer</p></div>
        <div class="common-banner"><p>Banner</p></div>
        <div class="technical-azure-selector pricing-detail-tab">
          <p>Main pricing</p>
        </div>
        """,
        "html.parser",
    )
    extractor = SectionExtractor()

    first_run = extractor.extract_all_sections(soup)
    second_run = extractor.extract_all_sections(soup)

    assert first_run == second_run
    assert [section["sectionType"] for section in first_run] == [
        "Qa",
        "Banner",
    ]
    assert [section["sortOrder"] for section in first_run] == [1, 2]
    qa_content = first_run[0]["content"]
    assert qa_content.index("First FAQ answer") < qa_content.index(
        "Second FAQ answer"
    )


def test_databricks_zh_source_uses_only_exact_safe_qa_nodes():
    source_path = (
        Path(__file__).parents[1]
        / "data"
        / "prod-html"
        / "zh-cn"
        / "pricing"
        / "databricks.html"
    )
    source_bytes = source_path.read_bytes()

    soup = BeautifulSoup(source_bytes.decode("utf-8"), "html.parser")
    sections = SectionExtractor().extract_all_sections(soup)

    section_types = [section["sectionType"] for section in sections]
    assert section_types[0] == "Banner"
    assert section_types[-1] == "Qa"
    assert section_types in (
        ["Banner", "Qa"],
        ["Banner", "ProductDescription", "Qa"],
    )
    assert [section["sortOrder"] for section in sections] == list(
        range(1, len(sections) + 1)
    )
    qa_content = sections[-1]["content"]
    qa_soup = BeautifulSoup(qa_content, "html.parser")
    assert "常见问题" in qa_soup.get_text(" ", strip=True)
    assert "支持和服务级别协议" in qa_soup.get_text(" ", strip=True)
    assert len(qa_soup.select("div.more-detail")) == 1
    assert len(qa_soup.select("div.pricing-page-section")) == 1
    assert not qa_soup.select(
        ".technical-azure-selector, .pricing-detail-tab"
    )
    assert "databricks-data-analysis" not in qa_content
    assert "databricks-data-analysis-n3" not in qa_content


def test_azure_firewall_ul_is_the_product_description() -> None:
    source_path = (
        Path(__file__).parents[1]
        / "data"
        / "prod-html"
        / "zh-cn"
        / "pricing"
        / "azure-firewall.html"
    )
    soup = BeautifulSoup(source_path.read_bytes(), "html.parser")

    sections = SectionExtractor().extract_all_sections(soup)

    assert [section["sectionType"] for section in sections] == [
        "Banner",
        "ProductDescription",
        "Qa",
    ]
    description = next(
        section["content"]
        for section in sections
        if section["sectionType"] == "ProductDescription"
    )
    description_soup = BeautifulSoup(description, "html.parser")
    description_root = description_soup.find("ul", class_="ul")
    assert description_root is not None
    assert description_root.parent is description_soup
    assert "本机防火墙功能" in description_root.get_text(" ", strip=True)
    assert description_soup.select_one(".technical-azure-selector") is None


def test_exact_faq_documentation_wrapper_is_emitted_whole() -> None:
    soup = BeautifulSoup(
        """
        <div class="technical-azure-selector pricing-detail-tab">
          <p>Main pricing</p>
        </div>
        <div class="pricing-page-section">
          <div class="more-detail">
            <h2>FAQ</h2>
            <p>One answer.</p>
          </div>
          <p>See the <a href="/docs/product-faq/">product FAQ</a>.</p>
        </div>
        """,
        "html.parser",
    )
    wrapper = soup.select_one("div.pricing-page-section")

    assert wrapper is not None
    assert is_exact_owned_faq_documentation_boundary(wrapper) is True

    qa_content = SectionExtractor().extract_qa(soup)
    qa_soup = BeautifulSoup(qa_content, "html.parser")
    emitted_wrapper = qa_soup.select_one("div.pricing-page-section")
    assert emitted_wrapper is not None
    assert emitted_wrapper.select_one("div.more-detail") is not None
    documentation_link = emitted_wrapper.select_one(
        ":scope > p > a[href='/docs/product-faq/']"
    )
    assert documentation_link is not None
    assert documentation_link.get_text(" ", strip=True) == "product FAQ"


@pytest.mark.parametrize(
    "product",
    ("managed-instance", "sql-database"),
)
@pytest.mark.parametrize("language", ("zh-cn", "en-us"))
def test_real_faq_documentation_link_is_preserved_in_qa(
    product: str,
    language: str,
) -> None:
    source_path = (
        Path(__file__).parents[1]
        / "data"
        / "prod-html"
        / language
        / "pricing"
        / f"{product}.html"
    )
    soup = BeautifulSoup(source_path.read_text(encoding="utf-8"), "html.parser")
    wrappers = [
        section
        for section in soup.select("div.pricing-page-section")
        if is_exact_owned_faq_documentation_boundary(section)
    ]

    assert len(wrappers) == 1
    source_link = wrappers[0].select_one(":scope > p > a[href]")
    assert source_link is not None
    qa_soup = BeautifulSoup(SectionExtractor().extract_qa(soup), "html.parser")
    emitted_link = qa_soup.find("a", href=source_link["href"])
    assert emitted_link is not None
    assert emitted_link.get_text(" ", strip=True) == source_link.get_text(
        " ", strip=True
    )
    assert emitted_link.find_parent(
        "div", class_="pricing-page-section"
    ) is not None


def test_qa_candidate_inside_pricing_subtree_fails_closed():
    soup = BeautifulSoup(
        """
        <div class="technical-azure-selector pricing-detail-tab">
          <div class="more-detail"><h2>FAQ</h2><p>Answer</p></div>
        </div>
        """,
        "html.parser",
    )

    with pytest.raises(
        CommonSectionBoundaryError,
        match="nested inside a formal pricing subtree",
    ):
        SectionExtractor().extract_qa(soup)


def test_qa_rejects_parent_child_candidate_overlap():
    soup = BeautifulSoup(
        """
        <div class="pricing-page-section">
          <h2>Support &amp; SLA</h2>
          <div class="more-detail"><h2>FAQ</h2><p>Answer</p></div>
        </div>
        """,
        "html.parser",
    )

    with pytest.raises(
        CommonSectionBoundaryError,
        match="overlap by ancestry",
    ):
        SectionExtractor().extract_qa(soup)
