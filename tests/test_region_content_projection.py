from __future__ import annotations

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from src.core.catalog import CatalogError, ProductCatalog
from src.core.complex_table_index import IndexedFragmentProjector
from src.core.region_processor import (
    RegionProcessor,
    RegionProjectionError,
    _description_rules,
    project_fragment_for_region,
)
from src.machine_checks.independent_source import (
    IndependentSourceError,
    _build_independent_fragment_index,
    _independent_description_rules,
    _project_independent_fragment_index,
    _project_one,
)
from src.utils.html.inline_styles import without_display_none
from src.pipeline.coordinator import run_scope
from src.review import ReviewError, ReviewWorkbenchService, prepare_review_queue


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        ("display:none", ""),
        (" DISPLAY : NONE ! important ; ", ""),
        ("display/**/:/*initial*/none !important;", ""),
        ("color: red; display:none; width:100%", "color: red; width:100%"),
        ("display:block;display:none", "display:block;"),
        ("--display:none;visibility:hidden", "--display:none;visibility:hidden"),
        ('content:"display:none;";display:none', 'content:"display:none;";'),
        (
            'background:url("data:image/svg+xml;a;b"); display:none; color:red',
            'background:url("data:image/svg+xml;a;b"); color:red',
        ),
        ("display:none; /* display:none; */ color:blue;", "/* display:none; */ color:blue;"),
        (" display:table; color:red ", " display:table; color:red "),
    ],
)
def test_inline_display_removal_preserves_other_declarations(style, expected):
    assert without_display_none(style) == expected


@pytest.mark.parametrize("mode", ["region", "complex", "independent-region", "independent-complex"])
def test_retained_tables_are_visible_without_unhiding_unrelated_content(mode):
    soup = BeautifulSoup(
        """<div id="body" style="display: NONE !important; color:blue">
          <p id="hidden-note" style="display:none">Unrelated UI</p>
          <div class="scroll-table" style="width:100%;display:none">
            <table id="keep" style="display:none; border:0">
              <tr><td colspan="2">Full price</td></tr>
            </table>
          </div>
          <table id="remove" style="display:none"><tr><td>Wrong price</td></tr></table>
        </div>""",
        "html.parser",
    )
    body = soup.div
    original = str(body)
    if mode == "region":
        html = project_fragment_for_region(body, source_scope=body, excluded_table_ids=("remove",))
    elif mode == "complex":
        html = IndexedFragmentProjector.build(
            [body], relevant_table_ids=frozenset({"remove"})
        ).project(("remove",))
    elif mode == "independent-region":
        html = _project_one(body, source_scope=body, excluded=("remove",))
    else:
        index = _build_independent_fragment_index([body], relevant_table_ids=frozenset({"remove"}))
        html = _project_independent_fragment_index(index, ("remove",))
    result = BeautifulSoup(html, "html.parser")
    assert result.find(id="remove") is None
    table = result.find(id="keep")
    assert table["style"] == "border:0"
    assert table.td["colspan"] == "2"
    assert table.get_text(strip=True) == "Full price"
    assert table.parent["style"] == "width:100%;"
    assert result.find(id="body")["style"] == "color:blue"
    assert result.find(id="hidden-note")["style"] == "display:none"
    assert str(body) == original


@pytest.mark.parametrize(
    "rules",
    [
        None,
        {},
        [{"class_name": "isn3 div", "visible_regions": ["north-china3"]}],
        [{"class_name": "isn3", "visible_regions": []}],
        [{"class_name": "isn3", "visible_regions": ["north-china3", "north-china3"]}],
        [{"class_name": "isn3", "visible_regions": ["China North 3"]}],
        [{"class_name": "isn3", "visible_regions": ["north-china3"], "guess": True}],
        [{"class_name": "isn3", "visible_regions": ["north-china3"]}] * 2,
    ],
)
def test_catalog_rejects_invalid_region_description_rules(project_builder, rules):
    root = project_builder([{"product_key": "sample-product", "semantic_strategy": "region_filter"}])
    path = root / "data/configs/products-config/pricing/sample-product.json"
    config = json.loads(path.read_text())
    config["extraction"]["region_content_rules"] = rules
    path.write_text(json.dumps(config))
    with pytest.raises(CatalogError):
        ProductCatalog.load(root)


def test_catalog_rejects_rules_on_a_strategy_that_cannot_apply_them(project_builder):
    root = project_builder()
    path = root / "data/configs/products-config/pricing/sample-product.json"
    config = json.loads(path.read_text())
    config["extraction"]["region_content_rules"] = [
        {"class_name": "isn3", "visible_regions": ["north-china3"]}
    ]
    path.write_text(json.dumps(config))
    with pytest.raises(CatalogError, match="只支持 region_filter"):
        ProductCatalog.load(root)


@pytest.mark.parametrize(
    ("body_html", "visible"),
    [
        ('<div><p>No matching div</p></div>', ["north-china3"]),
        ('<div><div class="isn3">Note</div></div>', ["unknown-region"]),
        ('<div><div class="isn3"><table></table></div></div>', ["north-china3"]),
    ],
)
def test_description_rules_fail_closed_on_source_drift(body_html, visible):
    body = BeautifulSoup(body_html, "html.parser").div
    rules = [{"class_name": "isn3", "visible_regions": visible}]
    with pytest.raises(RegionProjectionError):
        _description_rules(body, regions=["north-china3"], rules=rules)
    with pytest.raises(IndependentSourceError):
        _independent_description_rules(body, regions={"north-china3"}, rules=rules)


@pytest.mark.parametrize("enabled", [False, True])
def test_description_rules_are_opt_in_per_product_and_do_not_mutate_source(tmp_path, enabled):
    soft = tmp_path / "soft-category.json"
    soft.write_text("[]")
    soup = BeautifulSoup(
        """<div class="technical-azure-selector pricing-detail-tab"><div class="tab-content">
          <div class="isn3" style="display:none">North 3 description</div>
          <div class="notn3">Other regions description</div>
          <span class="isn3">Not a description div</span>
          <table id="price"><tr><td>Price</td></tr></table>
        </div></div>""", "html.parser"
    )
    original = str(soup)
    config = {"extraction": {}}
    if enabled:
        config["extraction"]["region_content_rules"] = [
            {"class_name": "isn3", "visible_regions": ["north-china3"]},
            {"class_name": "notn3", "visible_regions": ["east-china3"]},
        ]
    result = RegionProcessor(soft).extract_region_contents(
        soup, "", product_config=config,
        filter_analysis={
            "region_visible": True, "software_visible": False,
            "software_options": [{"value": "Managed Disks"}],
            "region_options": [{"value": "east-china3"}, {"value": "north-china3"}],
        },
    )
    north = BeautifulSoup(result["north-china3"], "html.parser")
    east = BeautifulSoup(result["east-china3"], "html.parser")
    assert bool(north.select_one("div.notn3")) is (not enabled)
    assert bool(east.select_one("div.isn3")) is (not enabled)
    assert north.select_one("span.isn3") is not None
    assert east.select_one("span.isn3") is not None
    assert north.select_one("div.isn3").get("style") == (None if enabled else "display:none")
    assert str(soup) == original


def test_workbench_uses_rules_sealed_with_the_batch_not_later_config(project_builder):
    repository = Path(__file__).resolve().parents[1]
    reference = json.loads((repository / "data/configs/products-config/pricing/storage-managed-disks.json").read_text())
    sources = {}
    for language, config in reference["sources"].items():
        path = repository / "data/current_prod_html" / language / config["snapshot_path"]
        soup = BeautifulSoup(path.read_bytes(), "html.parser")
        body = soup.select_one("div.technical-azure-selector.pricing-detail-tab > div.tab-content")
        body.clear()
        # Keep real metadata/controls; a tiny body exercises every config rule.
        for rule in reference["extraction"]["region_content_rules"]:
            note = soup.new_tag("div", attrs={"class": rule["class_name"]})
            note.string = rule["class_name"]
            body.append(note)
        body.append(BeautifulSoup('<table id="price" style="display:none"><tr><td>Price</td></tr></table>', "html.parser").table)
        sources[language] = str(soup).encode()
    root = project_builder([{
        "product_key": "storage-managed-disks",
        "semantic_strategy": "region_filter",
        "source_contents": sources,
        "snapshot_paths": {language: value["snapshot_path"] for language, value in reference["sources"].items()},
    }])
    config_path = root / "data/configs/products-config/pricing/storage-managed-disks.json"
    config_path.write_text(json.dumps(reference))
    (root / "data/configs/soft-category.json").write_text("[]")
    catalog = ProductCatalog.load(root)
    batch = run_scope(catalog, run_name="region-rules", all_products=True, parallel_jobs=2)
    assert batch.succeeded, batch.manifest
    prepare_review_queue(catalog, run_name="region-rules", review_id="region-rules-review")

    reference["extraction"]["region_content_rules"][0]["visible_regions"] = ["east-china3"]
    config_path.write_text(json.dumps(reference))
    workbench = ReviewWorkbenchService(ProductCatalog.load(root), review_id="region-rules-review")
    evidence = workbench.product_evidence("storage-managed-disks")
    assert all(language["summary"]["matched"] == language["summary"]["comparisons"] for language in evidence["languages"])

    queue_path = root / "reviews/region-rules-review/queue.json"
    queue = json.loads(queue_path.read_text())
    queue["products"][0]["items"][0]["region_content_rules"] = []
    queue_path.write_text(json.dumps(queue))
    with pytest.raises(ReviewError, match="区域说明规则与 Batch"):
        workbench.product_evidence("storage-managed-disks")
