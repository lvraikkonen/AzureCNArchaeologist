from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "experiments"
    / "v0.4.1-dom-equivalence"
    / "compare_zh_cn.py"
)


def _load_experiment():
    name = "v041_dom_equivalence_experiment"
    specification = importlib.util.spec_from_file_location(name, SCRIPT)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


EXPERIMENT = _load_experiment()


def test_desktop_default_remains_authoritative_with_mobile_conflict() -> None:
    soup = BeautifulSoup(
        """
        <div class="technical-azure-selector pricing-detail-tab">
          <div class="dropdown-container region-container">
            <div class="dropdown-box os-tab-nav">
              <span class="selected-item">中国东部 2</span>
              <ol class="tab-items">
                <li class="active"><a data-href="#east-china2">中国东部 2</a></li>
                <li><a data-href="#north-china3">中国北部 3</a></li>
              </ol>
            </div>
            <select id="region-box">
              <option data-href="#east-china2" value="east-china2" selected>中国东部 2</option>
              <option data-href="#north-china3" value="north-china3" selected>中国北部 3</option>
            </select>
          </div>
          <a id="east-china2"></a>
          <a id="north-china3"></a>
        </div>
        """,
        "html.parser",
    )
    root = soup.select_one(".technical-azure-selector")
    assert isinstance(root, Tag)

    observation = EXPERIMENT._discover_control(root, "region")

    assert observation["desktop_default_status"] == "unique"
    assert observation["desktop_default"]["value"] == "east-china2"
    assert observation["mobile_selected_hrefs"] == [
        "#east-china2",
        "#north-china3",
    ]
    assert [item["value"] for item in observation["options"]] == [
        "east-china2",
        "north-china3",
    ]


def test_soft_category_projection_removes_only_owned_wrapper() -> None:
    soup = BeautifulSoup(
        """
        <div id="scope">
          <div class="scroll-table"><h3>old</h3><table id="remove-me"></table></div>
          <div class="scroll-table"><h3>keep</h3><table id="keep-me"></table></div>
        </div>
        """,
        "html.parser",
    )
    scope = soup.select_one("#scope")
    assert isinstance(scope, Tag)

    evidence = EXPERIMENT._remove_configured_tables(scope, ["remove-me"])

    assert evidence == {
        "removed_table_ids": ["remove-me"],
        "ambiguous_table_ids": [],
        "multi_table_wrapper_ids": [],
        "projection_complete": True,
    }
    assert scope.select_one("#remove-me") is None
    assert scope.select_one("#keep-me") is not None
    assert [item.get_text(strip=True) for item in scope.select("h3")] == ["keep"]


def test_category_locator_suppresses_missing_aggregate_target() -> None:
    soup = BeautifulSoup(
        """
        <div class="tab-panel" id="software-panel">
          <ol class="tab-nav">
            <li class="active"><a data-href="#missing-all">全部</a></li>
            <li><a data-href="#category-one">类别一</a></li>
          </ol>
          <div class="tab-panel" id="category-one"><table id="one"></table></div>
        </div>
        """,
        "html.parser",
    )
    panel = soup.select_one("#software-panel")
    assert isinstance(panel, Tag)

    options, findings = EXPERIMENT._category_options(panel)

    assert [item["value"] for item in options] == ["category-one"]
    assert any(
        finding["code"] == "non_materialized_aggregate_tab"
        for finding in findings
    )


def test_controlled_swap_detects_both_wrong_states() -> None:
    first = (("region", "east-china"),)
    second = (("region", "east-china2"),)
    source = {
        first: {"html": "<div><table id='east'></table></div>"},
        second: {"html": "<div><table id='east2'></table></div>"},
    }
    payload = {
        first: "<div><table id='east'></table></div>",
        second: "<div><table id='east2'></table></div>",
    }

    result = EXPERIMENT._swap_mutation(
        product_key="sample",
        source_url="https://www.azure.cn/pricing/details/sample/",
        source=source,
        payload=payload,
    )

    assert result is not None
    assert result["detected"] is True
    assert len(result["detected_states"]) == 2


def test_independent_semantic_materializer_changes_only_live_empty_ticks() -> None:
    source = (
        '<p><i class="icon icon-tick"></i>'
        "<!-- <i class='icon-tick'></i> -->"
        '<i class="icon-tick">existing</i>'
        '<i class="foo-icon-tick"></i></p>'
    )

    materialized, evidence = EXPERIMENT._expected_cms_wire_html(source)

    assert materialized == (
        "<p>✓"
        "<!-- <i class='icon-tick'></i> -->"
        '<i class="icon-tick">existing</i>'
        '<i class="foo-icon-tick"></i></p>'
    )
    assert evidence == {
        "algorithm_version": "css-generated-semantics-v1",
        "transformation_count": 1,
        "rules": [
            {
                "source": "live empty i.icon-tick",
                "replacement_text": "✓",
                "count": 1,
            }
        ],
    }


def test_comparison_separates_physical_source_from_expected_cms_wire(
    tmp_path: Path,
) -> None:
    fragment_root = tmp_path / "fragments"
    comparison = EXPERIMENT._write_comparison(
        product_key="sample",
        field="base-content",
        key=(),
        source={
            "html": '<table><tr><td><i class="icon icon-tick"></i></td></tr></table>',
            "locator": {"kind": "test"},
        },
        payload_html="<table><tr><td>✓</td></tr></table>",
        source_url="https://www.azure.cn/pricing/details/sample/",
        fragment_root=fragment_root,
    )

    assert comparison["raw_equal"] is False
    assert comparison["wire_equal"] is True
    assert comparison["source_raw_dom_equal"] is False
    assert comparison["dom_equal"] is True
    assert comparison["source_raw_visible_text_equal"] is False
    assert comparison["visible_text_equal"] is True
    assert comparison["semantic_materialization"]["transformation_count"] == 1
    assert comparison["expected_source_fragment"] is not None
    assert comparison["source_to_payload_diff"] is not None
    assert comparison["diff"] is None

    experiment_root = fragment_root.parent
    expected_path = experiment_root / comparison["expected_source_fragment"]
    raw_diff_path = experiment_root / comparison["source_to_payload_diff"]
    assert expected_path.read_text(encoding="utf-8") == (
        "<table><tr><td>✓</td></tr></table>"
    )
    assert raw_diff_path.is_file()
