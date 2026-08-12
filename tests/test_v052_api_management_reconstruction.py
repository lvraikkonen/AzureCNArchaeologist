from __future__ import annotations

import copy
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from src.independent_fidelity.api_management import (
    ApiManagementReconstructionError,
    ROW_WARNING_CODE,
    SOURCE_TABLE_IDS,
    normalize_config_table_ids,
    reconstruct_api_management,
    reconstruct_bound_api_management,
)
from src.independent_fidelity.formal_target import (
    EXPECTED_REGIONS,
    EXPECTED_STATE_IDS,
    bind_formal_target,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bound_target():
    return bind_formal_target(ROOT)


def _reconstruct(bound_target, *, source_html=None, soft_category=None):
    return reconstruct_api_management(
        source_html=source_html or bound_target.source_html,
        soft_category=(
            soft_category
            if soft_category is not None
            else bound_target.soft_category
        ),
        sampling_plan=bound_target.sampling_plan,
    )


def test_real_source_reconstructs_desktop_default_first_five_state_universe(
    bound_target,
) -> None:
    result = reconstruct_bound_api_management(bound_target)
    assert result.software_value == "API Management"
    assert result.desktop_default_region == "east-china2"
    assert result.source_table_ids == SOURCE_TABLE_IDS
    assert tuple(state.region for state in result.states) == EXPECTED_REGIONS
    assert tuple(state.state_id for state in result.states) == EXPECTED_STATE_IDS
    assert tuple(state.label for state in result.states) == (
        "中国东部 2",
        "中国北部3",
        "中国北部 2",
        "中国东部",
        "中国北部",
    )
    assert result.hygiene_warnings == ()


def test_real_source_state_ownership_is_an_exact_table_partition(
    bound_target,
) -> None:
    result = reconstruct_bound_api_management(bound_target)
    source_fragments = {state.source_fragment for state in result.states}
    assert len(source_fragments) == 1
    for state in result.states:
        assert set(state.retained_table_ids).isdisjoint(state.removed_table_ids)
        assert set(state.retained_table_ids).union(
            state.removed_table_ids
        ) == set(SOURCE_TABLE_IDS)
        projected = BeautifulSoup(state.projected_fragment, "html.parser")
        assert tuple(
            str(table["id"]) for table in projected.find_all("table")
        ) == state.retained_table_ids
        assert all(
            projected.find(id=table_id) is None
            for table_id in state.removed_table_ids
        )
        assert state.locator == {
            "container_selector": (
                "div.technical-azure-selector.pricing-detail-tab"
            ),
            "content_selectors": ["div.tab-content"],
            "append_selectors": [],
        }


def test_mobile_default_markers_are_ignored_without_warning(bound_target) -> None:
    soup = BeautifulSoup(bound_target.source_html, "html.parser")
    options = soup.select("select#region-box > option")
    for option in options:
        option.attrs.pop("selected", None)
    first = options[0]
    second = options[1]
    first["selected"] = "selected"
    second["selected"] = "selected"
    result = _reconstruct(bound_target, source_html=str(soup))
    assert result.desktop_default_region == "east-china2"
    assert tuple(state.region for state in result.states) == EXPECTED_REGIONS
    assert result.hygiene_warnings == ()


@pytest.mark.parametrize("mode", ["missing", "duplicate"])
def test_desktop_default_must_be_unique(bound_target, mode: str) -> None:
    soup = BeautifulSoup(bound_target.source_html, "html.parser")
    items = soup.select(
        "div.region-container div.dropdown-box.hidden-sm.hidden-xs "
        "ol.tab-items > li"
    )
    for item in items:
        item.attrs["class"] = [
            value for value in item.get("class", []) if value != "active"
        ]
    if mode == "duplicate":
        items[0]["class"] = ["active"]
        items[1]["class"] = ["active"]
    with pytest.raises(ApiManagementReconstructionError) as raised:
        _reconstruct(bound_target, source_html=str(soup))
    assert raised.value.code == "desktop_region_default_ambiguous"


def test_mobile_machine_domain_target_drift_is_blocked(bound_target) -> None:
    soup = BeautifulSoup(bound_target.source_html, "html.parser")
    option = soup.select("select#region-box > option")[0]
    option["value"] = "unexpected-region"
    option["data-href"] = "#unexpected-region"
    with pytest.raises(ApiManagementReconstructionError) as raised:
        _reconstruct(bound_target, source_html=str(soup))
    assert raised.value.code == "mobile_region_domain_target_mismatch"


def test_duplicate_exact_soft_category_row_is_blocked(bound_target) -> None:
    config = copy.deepcopy(bound_target.soft_category)
    config.append(copy.deepcopy(config[236]))
    with pytest.raises(ApiManagementReconstructionError) as raised:
        _reconstruct(bound_target, soft_category=config)
    assert raised.value.code == "soft_category_exact_row_ambiguous"
    assert "236" in str(raised.value)


@pytest.mark.parametrize(
    ("raw", "expected_positions"),
    [
        (["#A", "#A", "#B"], [1]),
        (["#A", "#B", "#A"], [2]),
    ],
)
def test_duplicate_ids_in_one_row_are_ordered_unique_warning_only(
    raw: list[str], expected_positions: list[int]
) -> None:
    normalized, warnings = normalize_config_table_ids(
        raw,
        entry_index=42,
        software_value="API Management",
        region="east-china2",
    )
    assert normalized == ("A", "B")
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning["code"] == ROW_WARNING_CODE
    assert warning["first_position"] == 0
    assert warning["duplicate_positions"] == expected_positions
    assert warning["handling"] == "first_occurrence_ordered_unique"
    assert warning["verdict_effect"] == "none"


def test_config_reference_to_missing_source_table_is_blocked(bound_target) -> None:
    config = copy.deepcopy(bound_target.soft_category)
    config[236]["tableIDs"] = ["#not-in-source"]
    with pytest.raises(ApiManagementReconstructionError) as raised:
        _reconstruct(bound_target, soft_category=config)
    assert raised.value.code == "soft_category_source_table_missing"


def test_duplicate_source_dom_id_is_blocked(bound_target) -> None:
    soup = BeautifulSoup(bound_target.source_html, "html.parser")
    content = soup.select_one(
        "div.technical-azure-selector.pricing-detail-tab div.tab-content"
    )
    assert content is not None
    duplicate = soup.new_tag("table", id="API-Management-preview")
    content.append(duplicate)
    with pytest.raises(ApiManagementReconstructionError) as raised:
        _reconstruct(bound_target, source_html=str(soup))
    assert raised.value.code == "source_table_dom_id_ambiguous"


def test_nested_scroll_table_ownership_is_blocked(bound_target) -> None:
    soup = BeautifulSoup(bound_target.source_html, "html.parser")
    table = soup.find("table", id="API-Management-preview2")
    assert table is not None
    inner = soup.new_tag("div", attrs={"class": "scroll-table"})
    outer = soup.new_tag("div", attrs={"class": "scroll-table"})
    table.wrap(inner)
    inner.wrap(outer)
    with pytest.raises(ApiManagementReconstructionError) as raised:
        _reconstruct(bound_target, source_html=str(soup))
    assert raised.value.code == "source_table_wrapper_ambiguous"
