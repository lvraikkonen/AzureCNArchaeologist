from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

from src.core.payload_contract import PRICING_PAYLOAD_FIELDS
from src.extractors.strategy_extractor import _strategy_config, extract_processing_item
from src.strategies.simple_static_strategy import SimpleStaticStrategy
from tests.m2_helpers import PROJECT_ROOT, real_catalog, service_bus_source_path


def test_all_four_copied_core_strategy_files_are_kept_in_strategy_directory() -> None:
    strategy_root = PROJECT_ROOT / "src" / "strategies"

    assert {
        "simple_static_strategy.py",
        "region_filter_strategy.py",
        "complex_content_strategy.py",
        "support_article_strategy.py",
    }.issubset({path.name for path in strategy_root.glob("*_strategy.py")})
    assert not (PROJECT_ROOT / "src" / "acn_archaeologist").exists()


def test_service_bus_uses_copied_simple_static_strategy() -> None:
    assert SimpleStaticStrategy.__module__ == "src.strategies.simple_static_strategy"


def test_reference_status_and_historical_digests_are_not_passed_to_strategy() -> None:
    catalog = real_catalog()
    config = _strategy_config(catalog.get_definition("service-bus"))
    serialized = json.dumps(config)

    assert "capability_status" not in serialized
    assert "sha256" not in serialized.casefold()
    assert "checksum" not in serialized.casefold()
    assert "digest" not in serialized.casefold()


def test_service_bus_bilingual_extraction_is_deterministic_and_complete() -> None:
    catalog = real_catalog()

    for item in catalog.select(product_key="service-bus"):
        first = extract_processing_item(catalog, item)
        second = extract_processing_item(catalog, item)

        assert first == second
        assert tuple(first) == PRICING_PAYLOAD_FIELDS
        assert first["slug"] == "service-bus"
        assert first["language"] == item.language
        assert first["contentGroups"] == []
        assert [section["sectionType"] for section in first["commonSections"]] == [
            "Banner",
            "ProductDescription",
            "Qa",
        ]
        assert all(
            section["sectionTitle"] == section["sectionType"]
            for section in first["commonSections"]
        )
        assert first["pageConfig"]["pageType"] == "Simple"
        assert first["pageConfig"]["enableFilters"] is False

        source = BeautifulSoup(service_bus_source_path(item.language).read_bytes(), "html.parser")
        source_ticks = len(
            source.select("div.technical-azure-selector i.icon-tick")
        )
        assert first["baseContent"].count("✓") == source_ticks
        assert not BeautifulSoup(first["baseContent"], "html.parser").select(
            "i.icon-tick"
        )


def test_business_payload_contains_no_diagnostic_fields() -> None:
    catalog = real_catalog()
    item = catalog.select(product_key="service-bus")[0]
    payload = extract_processing_item(catalog, item)

    assert not {
        "validation",
        "quality_score",
        "extraction_metadata",
        "source_path",
        "error",
    } & set(payload)
