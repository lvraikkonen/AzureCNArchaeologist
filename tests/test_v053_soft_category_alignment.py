from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

from src.core.region_processor import RegionProcessor
from src.core.soft_category_config import SoftCategoryConfigEntry
from src.core.strict_soft_category_projection import StrictSoftCategoryProjector
from src.independent_fidelity.api_management import normalize_config_table_ids


def test_all_three_lanes_preserve_first_occurrence_order() -> None:
    raw = [" #remove ", "#keep", "remove", "#later", "#keep"]
    independent, warnings = normalize_config_table_ids(
        raw,
        entry_index=7,
        software_value="Product",
        region="region-a",
    )
    production_entry = SoftCategoryConfigEntry(
        entry_index=7,
        software_value="Product",
        region_value="region-a",
        raw_table_ids=tuple(raw),
        table_ids=("remove", "keep", "remove", "later", "keep"),
    )
    assert independent == ("remove", "keep", "later")
    assert production_entry.unique_table_ids == independent
    assert [warning["normalized_table_id"] for warning in warnings] == [
        "remove",
        "keep",
    ]
    assert all(
        warning["handling"] == "first_occurrence_ordered_unique"
        for warning in warnings
    )


def test_strict_l3a_projection_is_invariant_to_later_row_duplicates(
    tmp_path: Path,
) -> None:
    config = tmp_path / "data/configs/soft-category.json"
    config.parent.mkdir(parents=True)
    source = BeautifulSoup(
        '<div id="panel">'
        '<div class="scroll-table"><table id="remove"><tr><td>¥ 1</td></tr></table></div>'
        '<div class="scroll-table"><table id="keep"><tr><td>¥ 2</td></tr></table></div>'
        "</div>",
        "html.parser",
    )

    def project(table_ids: list[str]):
        config.write_text(
            json.dumps(
                [
                    {
                        "os": "Product",
                        "region": "region-a",
                        "tableIDs": table_ids,
                    }
                ]
            ),
            encoding="utf-8",
        )
        return StrictSoftCategoryProjector(tmp_path).project(
            source,
            source_panel_id="panel",
            software_value="Product",
            region_value="region-a",
        )

    unique = project(["#remove"])
    duplicate = project(["#remove", "#remove"])
    assert duplicate.output_html == unique.output_html
    assert duplicate.matching_entries[0].table_ids == ("remove",)


def test_region_filter_production_content_is_duplicate_invariant() -> None:
    source = BeautifulSoup(
        "<html><body><div><table id=remove><tr><td>¥ 1</td></tr></table>"
        "<table id=keep><tr><td>¥ 2</td></tr></table></div></body></html>",
        "html.parser",
    )
    processor = RegionProcessor()
    processor.region_config = {"Product": {"region-a": ["#remove"]}}
    unique = processor.apply_region_filtering(source, "region-a", "Product")
    processor.region_config = {
        "Product": {"region-a": ["#remove", "#remove"]}
    }
    duplicate = processor.apply_region_filtering(source, "region-a", "Product")
    assert str(duplicate) == str(unique)

