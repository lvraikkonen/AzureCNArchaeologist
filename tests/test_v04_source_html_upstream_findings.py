from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.build_v04_source_html_findings import (
    REPORT_JSON,
    REPORT_MARKDOWN,
    build_report,
    render_markdown,
)


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_BLOCKING_STRUCTURE_LANGUAGE_ITEMS = {
    ("container-apps", "zh-cn"),
    ("data-lake-storage", "zh-cn"),
    ("event-hubs", "zh-cn"),
    ("event-hubs", "en-us"),
    ("managed-instance", "zh-cn"),
    ("managed-instance", "en-us"),
    ("sql-database", "zh-cn"),
    ("sql-database", "en-us"),
    ("sql-edge", "en-us"),
    ("storage-files", "zh-cn"),
}

EXPECTED_BLOCKING_STRUCTURE_COUNTS = {
    "SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT": 5,
    "SOURCE_HTML_CONTENT_WITHOUT_EXACT_COMMON_BOUNDARY": 1,
    "SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION": 3,
    "SOURCE_HTML_POST_SELECTOR_SUPPORT_SECTION_UNCLASSIFIED": 1,
    "SOURCE_HTML_PRICING_TABLE_SECTION_WITHOUT_OWN_HEADING": 1,
}


def test_upstream_findings_report_is_deterministic_and_current() -> None:
    generated = build_report(ROOT)
    persisted = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert generated == persisted
    assert render_markdown(generated) == REPORT_MARKDOWN.read_text(
        encoding="utf-8"
    )
    assert "timestamp" not in json.dumps(generated)
    assert "run_id" not in json.dumps(generated)


def test_confirmed_and_review_only_products_remain_separate() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert report["survey"]["canonical_sources_surveyed"] == 368
    assert report["survey"]["simple_static_sources_surveyed"] == 62
    assert report["summary"] == {
        "confirmed_product_keys": [
            "dns",
            "service-fabric",
            "virtual-wan",
        ],
        "confirmed_language_findings": 6,
        "blocking_structure_product_keys": [
            "container-apps",
            "data-lake-storage",
            "event-hubs",
            "managed-instance",
            "sql-database",
            "sql-edge",
            "storage-files",
        ],
        "blocking_structure_language_items": 10,
        "blocking_structure_findings": 11,
        "blocking_structure_findings_by_code": (
            EXPECTED_BLOCKING_STRUCTURE_COUNTS
        ),
        "needs_review_product_keys": ["route-server", "sql-edge"],
        "needs_review_language_items": 4,
    }
    assert all(
        item["duplicate_id"] == "tabContent1"
        and item["reference_count"] == 0
        and item["references"] == []
        and item["finding_code"]
        == "SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT"
        for item in report["confirmed_blocking_findings"]
    )
    assert all(
        item["reference_count"] == 2
        and item["finding_code"]
        == "SOURCE_HTML_DUPLICATE_ID_SCOPE_NEEDS_REVIEW"
        and "single_static_base_content_boundary_not_proven"
        in item["review_reasons"]
        for item in report["needs_upstream_structure_review"]
    )

    blocking_structure = report["blocking_source_structure_findings"]
    assert len(blocking_structure) == 11
    assert {
        (item["product_key"], item["language"])
        for item in blocking_structure
    } == EXPECTED_BLOCKING_STRUCTURE_LANGUAGE_ITEMS
    counts: dict[str, int] = {}
    for item in blocking_structure:
        counts[item["finding_code"]] = (
            counts.get(item["finding_code"], 0) + 1
        )
        assert item["status"] == "confirmed_blocking"
        assert item["payload_generation_allowed"] is False
        assert item["upstream_suggestion"] is not None
        assert item["upstream_suggestion"]["action"]
        assert item["upstream_suggestion"]["description"]
        assert item["evidence"]
        assert item["lines"] == [
            evidence["line"] for evidence in item["evidence"]
        ]
        assert item["safety_checks"]
    assert counts == EXPECTED_BLOCKING_STRUCTURE_COUNTS


def test_report_source_identities_match_canonical_files() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    for item in (
        report["confirmed_blocking_findings"]
        + report["blocking_source_structure_findings"]
        + report["needs_upstream_structure_review"]
    ):
        source = ROOT / item["source"]["path"]
        raw = source.read_bytes()
        assert len(raw) == item["source"]["size_bytes"]
        assert hashlib.sha256(raw).hexdigest() == item["source"]["sha256"]


def test_filter_state_controls_are_absent_from_source_structure_inventory() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    recorded = {
        item["product_key"]
        for item in (
            report["confirmed_blocking_findings"]
            + report["blocking_source_structure_findings"]
            + report["needs_upstream_structure_review"]
        )
    }

    assert recorded.isdisjoint({"api-management", "cloud-services"})
