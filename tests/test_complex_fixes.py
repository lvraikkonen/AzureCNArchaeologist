from __future__ import annotations

from bs4 import BeautifulSoup
import pytest

from src.core.complex_table_index import (
    IndexedFragmentProjector,
    applicable_exclusions_for_software,
)
from src.core.region_processor import RegionProjectionError
from src.detectors.filter_detector import FilterDetector
from src.detectors.tab_detector import TabDetector
from src.machine_checks.independent_source import _read_categories, _read_filter
from src.utils.content.flexible_builder import FlexibleBuilder


def test_category_detector_allows_a_software_panel_without_category_tabs() -> None:
    soup = BeautifulSoup(
        """
        <div class="technical-azure-selector pricing-detail-tab">
          <div class="tab-content">
            <div id="tabContent1" class="tab-panel">
              <div class="tab-content"><table id="price"></table></div>
            </div>
          </div>
        </div>
        """,
        "html.parser",
    )

    detector = TabDetector()

    assert detector.detect_grouped_tabs(soup) == {}
    assert detector.detect_tabs(soup)["content_groups"] == [
        {
            "id": "tabContent1",
            "has_category_tabs": False,
            "category_tabs_count": 0,
        }
    ]


def test_complex_index_removes_every_distinct_unit_for_one_table_id() -> None:
    soup = BeautifulSoup(
        """
        <div id="leaf">
          <div class="scroll-table">
            <table id="remove-all"></table>
            <table id="remove-all"></table>
          </div>
          <div class="scroll-table" data-table-id="remove-all">
            <table id="another-marker"></table>
          </div>
          <div class="scroll-table"><table id="keep"></table></div>
        </div>
        """,
        "html.parser",
    )
    leaf = soup.find("div", id="leaf")
    assert leaf is not None
    projector = IndexedFragmentProjector.build(
        [leaf],
        relevant_table_ids=frozenset({"remove-all"}),
    )

    projected = BeautifulSoup(projector.project(("remove-all",)), "html.parser")

    assert projected.find(id="remove-all") is None
    assert projected.find(id="another-marker") is None
    assert projected.find(id="keep") is not None
    assert projector.table_ids == frozenset({"remove-all"})


def test_complex_index_rejects_a_config_id_bound_to_non_table_content() -> None:
    soup = BeautifulSoup('<div id="leaf"><div id="bad"></div></div>', "html.parser")
    leaf = soup.find("div", id="leaf")
    assert leaf is not None

    with pytest.raises(RegionProjectionError, match="不是表格"):
        IndexedFragmentProjector.build(
            [leaf],
            relevant_table_ids=frozenset({"bad"}),
        )


def test_complex_index_blocks_a_config_row_with_zero_software_matches() -> None:
    soup = BeautifulSoup('<div id="leaf"><table id="present"></table></div>', "html.parser")
    leaf = soup.find("div", id="leaf")
    assert leaf is not None
    projector = IndexedFragmentProjector.build(
        [leaf],
        relevant_table_ids=frozenset({"missing"}),
    )

    with pytest.raises(RegionProjectionError, match="当前 Software"):
        applicable_exclusions_for_software([projector], ("missing",))


def test_complex_source_confirmed_empty_state_is_serialized_as_empty_content() -> None:
    soup = BeautifulSoup(
        '<div id="leaf"><!-- retained source marker --><div><br/></div></div>',
        "html.parser",
    )
    leaf = soup.find("div", id="leaf")
    assert leaf is not None
    projector = IndexedFragmentProjector.build(
        [leaf],
        relevant_table_ids=frozenset(),
    )

    assert projector.project(()) == ""
    assert FlexibleBuilder.build_complex_content_groups(
        [
            {
                "criteria": (("region", "east-china"),),
                "labels": ("中国东部",),
                "content": "",
            }
        ]
    )[0]["content"] == ""


def test_mobile_controls_do_not_define_complex_machine_domains() -> None:
    soup = BeautifulSoup(
        """
        <div class="technical-azure-selector pricing-detail-tab">
          <div class="dropdown-container software-kind-container">
            <label>Software</label>
            <span class="selected-item">Linux</span>
            <select id="software-box"
                    class="dropdown-select software-box hidden-lg hidden-md">
              <option value="Windows" data-href="#tabContent2" selected>
                incorrect mobile default and label
              </option>
              <option value="unused" data-href="#mobile-only">mobile only</option>
              <option value="Linux" data-href="#tabContent1">mobile Linux</option>
            </select>
            <ul class="dropdown-box os-tab-nav hidden-xs hidden-sm">
              <li class="tab-items active">
                <a id="desktop-linux" data-href="#tabContent1">Linux</a>
              </li>
              <li class="tab-items">
                <a id="desktop-windows" data-href="#tabContent2">Windows</a>
              </li>
            </ul>
          </div>
          <div class="dropdown-container region-container">
            <label>Region</label>
            <span class="selected-item">China East</span>
            <select id="region-box"
                    class="dropdown-select region-box hidden-lg hidden-md">
              <option value="wrong" data-herf="#wrong" selected>wrong</option>
            </select>
            <ul class="dropdown-box os-tab-nav hidden-xs hidden-sm">
              <li class="tab-items active">
                <a data-href="#east-china">China East</a>
              </li>
              <li class="tab-items">
                <a data-href="#north-china">China North</a>
              </li>
            </ul>
          </div>
          <div class="tab-content">
            <div id="tabContent1" class="tab-panel">
              <div class="category-container">
                <span class="category-title">Category</span>
                <span class="selected-item">General purpose</span>
                <select class="category-tabs hidden-lg hidden-md">
                  <option data-herf="#wrong" selected>wrong mobile category</option>
                </select>
                <ul class="os-tab-nav category-tabs hidden-xs hidden-sm">
                  <li class="active">
                    <a data-href="#tabContent1-1">General purpose</a>
                  </li>
                  <li><a data-href="#tabContent1-2">Compute optimized</a></li>
                </ul>
              </div>
              <div class="tab-content">
                <div id="tabContent1-1" class="tab-panel"></div>
                <div id="tabContent1-2" class="tab-panel"></div>
              </div>
            </div>
            <div id="tabContent2" class="tab-panel">
              <div class="tab-content"></div>
            </div>
          </div>
        </div>
        """,
        "html.parser",
    )
    pricing = soup.select_one("div.technical-azure-selector")
    linux_panel = soup.find("div", id="tabContent1")
    assert pricing is not None and linux_panel is not None

    detected = FilterDetector().detect_filters(soup)
    assert [
        (option["value"], option["href"], option["label"])
        for option in detected["software_options"]
    ] == [
        ("Linux", "#tabContent1", "Linux"),
        ("Windows", "#tabContent2", "Windows"),
    ]
    assert [
        (option["value"], option["label"])
        for option in detected["region_options"]
    ] == [
        ("east-china", "China East"),
        ("north-china", "China North"),
    ]
    grouped = TabDetector().detect_grouped_tabs(soup)
    assert [
        (option["href"], option["label"])
        for option in grouped["tabContent1"]
    ] == [
        ("#tabContent1-1", "General purpose"),
        ("#tabContent1-2", "Compute optimized"),
    ]

    independent_software = _read_filter(pricing, "software")
    independent_region = _read_filter(pricing, "region")
    independent_category = _read_categories(linux_panel)
    assert independent_software["options"] == [
        {"value": "Linux", "label": "Linux", "href": "#tabContent1"},
        {"value": "Windows", "label": "Windows", "href": "#tabContent2"},
    ]
    assert independent_region["options"] == [
        {
            "value": "east-china",
            "label": "China East",
            "href": "#east-china",
        },
        {
            "value": "north-china",
            "label": "China North",
            "href": "#north-china",
        },
    ]
    assert independent_category["options"] == [
        {
            "value": "tabContent1-1",
            "label": "General purpose",
            "href": "#tabContent1-1",
        },
        {
            "value": "tabContent1-2",
            "label": "Compute optimized",
            "href": "#tabContent1-2",
        },
    ]


def test_software_desktop_target_requires_one_mobile_semantic_value() -> None:
    soup = BeautifulSoup(
        """
        <div class="dropdown-container software-kind-container">
          <select id="software-box" class="hidden-lg hidden-md">
            <option value="Linux" data-href="#tabContent1">Linux</option>
            <option value="Other" data-href="#tabContent1">Other</option>
          </select>
          <ul class="dropdown-box os-tab-nav hidden-xs hidden-sm">
            <li class="tab-items active">
              <a data-href="#tabContent1">Linux</a>
            </li>
          </ul>
        </div>
        """,
        "html.parser",
    )

    with pytest.raises(ValueError, match="option.value"):
        FilterDetector().detect_filters(soup)


@pytest.mark.parametrize(
    ("east_class", "north_class", "summary", "expected"),
    [
        ("", "active", "China East", "north-china"),
        ("active", "active", "China East", "east-china"),
        ("", "", "China East", "east-china"),
        ("active", "", "stale summary", "east-china"),
    ],
)
def test_desktop_default_markers_precede_summary_fallback(
    east_class: str,
    north_class: str,
    summary: str,
    expected: str,
) -> None:
    soup = BeautifulSoup(
        f"""
        <div class="technical-azure-selector pricing-detail-tab">
          <div class="dropdown-container region-container">
            <span class="selected-item">{summary}</span>
            <ul class="dropdown-box os-tab-nav hidden-xs hidden-sm">
              <li class="tab-items {east_class}">
                <a data-href="#east-china">China East</a>
              </li>
              <li class="tab-items {north_class}">
                <a data-href="#north-china">China North</a>
              </li>
            </ul>
          </div>
        </div>
        """,
        "html.parser",
    )
    pricing = soup.select_one("div.technical-azure-selector")
    assert pricing is not None

    production = FilterDetector()._detect_region_filter(soup)
    independent = _read_filter(pricing, "region")

    assert production["default_value"] == expected
    assert production["options"][0]["value"] == expected
    assert independent["options"][0]["value"] == expected
