from __future__ import annotations

from bs4 import BeautifulSoup
import pytest

from src.core.extraction_coordinator import ExtractionCoordinator


@pytest.mark.parametrize(
    (
        "product_key",
        "expected_group_count",
        "expected_base_tables",
        "expected_strategy",
    ),
    [
        ("automation", 4, 0, "region_filter"),
        ("monitor", 30, 0, "complex"),
        ("traffic-manager", 0, 2, "simple_static"),
        ("azure-policy", 0, 0, "simple_static"),
        ("advisor", 0, 0, "simple_static"),
        ("azure-migrate", 0, 1, "simple_static"),
        ("key-vault", 6, 0, "region_filter"),
        ("container-registry", 0, 3, "simple_static"),
        ("container-instances", 3, 0, "region_filter"),
    ],
)
def test_round_two_reported_product_extracts_and_validates(
    tmp_path,
    product_key: str,
    expected_group_count: int,
    expected_base_tables: int,
    expected_strategy: str,
) -> None:
    result = ExtractionCoordinator(str(tmp_path)).coordinate_extraction(
        product_key,
        "zh-cn",
    )

    assert result.succeeded
    assert result.payload is not None
    assert result.sidecar["status"]["execution"] == "succeeded"
    assert result.sidecar["status"]["validation"] == "passed"
    assert result.sidecar["strategy"]["type"] == expected_strategy
    assert len(result.payload["contentGroups"]) == expected_group_count
    assert len(
        BeautifulSoup(
            result.payload["baseContent"], "html.parser"
        ).select("table")
    ) == expected_base_tables

    if product_key in {"azure-policy", "advisor"}:
        assert result.payload["baseContent"]
        assert [
            section["sectionType"]
            for section in result.payload["commonSections"]
        ] == ["Banner", "Qa"]
    if product_key == "container-instances":
        assert result.payload["baseContent"]
        assert "Pricing Example" in result.payload["baseContent"] or (
            "定价示例" in result.payload["baseContent"]
        )


@pytest.mark.parametrize(
    ("product_key", "expected_tables_per_group"),
    [
        ("automation", 1),
        ("key-vault", 1),
        ("container-instances", 1),
    ],
)
def test_round_two_region_payloads_keep_price_tables(
    tmp_path,
    product_key: str,
    expected_tables_per_group: int,
) -> None:
    result = ExtractionCoordinator(str(tmp_path)).coordinate_extraction(
        product_key,
        "zh-cn",
    )

    assert result.succeeded
    assert result.payload is not None
    for group in result.payload["contentGroups"]:
        assert len(
            BeautifulSoup(group["content"], "html.parser").select(
                "table"
            )
        ) >= expected_tables_per_group


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_latest_event_hubs_source_footnote_blocks_before_payload(
    tmp_path,
    language: str,
) -> None:
    result = ExtractionCoordinator(str(tmp_path)).coordinate_extraction(
        "event-hubs",
        language,
    )

    assert not result.succeeded
    assert result.payload is None
    assert result.sidecar["error"]["code"] == "SOURCE_HTML_STRUCTURE_BLOCKED"
    assert result.sidecar["validation"]["errors"][0]["code"] == (
        "SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION"
    )
