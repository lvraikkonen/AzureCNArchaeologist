from __future__ import annotations

import ast
from copy import deepcopy

from bs4 import BeautifulSoup

from src.machine_checks.l3b import run_l3b
from tests.m2_helpers import (
    PROJECT_ROOT,
    service_bus_payload,
    service_bus_source_path,
    write_payload,
)


def _check(tmp_path, payload, *, source_path=None):
    payload_path = write_payload(tmp_path / "payload.json", payload)
    return run_l3b(
        frozen_html_path=source_path or service_bus_source_path(),
        payload_path=payload_path,
        product_key="service-bus",
        language="zh-cn",
    )


def test_l3b_passes_all_business_html_fields(tmp_path) -> None:
    report = _check(tmp_path, service_bus_payload())

    assert report["status"] == "passed"
    assert report["scope"] == "全部业务 HTML 字段"
    assert {field["payload_path"] for field in report["fields"]} == {
        "baseContent",
        "contentGroups",
        "commonSections[0].content",
        "commonSections[1].content",
        "commonSections[2].content",
    }
    assert all(field["status"] == "passed" for field in report["fields"])


def test_l3b_detects_truncated_pricing_body(tmp_path) -> None:
    payload = service_bus_payload()
    payload["baseContent"] = payload["baseContent"][:-200]

    report = _check(tmp_path, payload)

    assert report["status"] == "failed"
    difference = next(
        field for field in report["fields"] if field["payload_path"] == "baseContent"
    )["difference"]
    assert difference["actual_length"] < difference["expected_length"]


def test_l3b_detects_faq_mixed_into_base_content(tmp_path) -> None:
    payload = service_bus_payload()
    payload["baseContent"] += payload["commonSections"][2]["content"]

    report = _check(tmp_path, payload)

    assert report["status"] == "failed"
    assert next(
        field for field in report["fields"] if field["payload_path"] == "baseContent"
    )["status"] == "failed"


def test_l3b_detects_swapped_common_section_content(tmp_path) -> None:
    payload = service_bus_payload()
    payload["commonSections"][0]["content"], payload["commonSections"][1]["content"] = (
        payload["commonSections"][1]["content"],
        payload["commonSections"][0]["content"],
    )

    report = _check(tmp_path, payload)

    failed_paths = {
        field["payload_path"]
        for field in report["fields"]
        if field["status"] == "failed"
    }
    assert "commonSections[0].content" in failed_paths
    assert "commonSections[1].content" in failed_paths


def test_l3b_detects_empty_payload_when_source_is_not_empty(tmp_path) -> None:
    payload = service_bus_payload()
    payload["baseContent"] = ""

    report = _check(tmp_path, payload)

    assert report["status"] == "failed"
    assert next(
        field for field in report["fields"] if field["payload_path"] == "baseContent"
    )["status"] == "failed"


def test_l3b_blocks_ambiguous_source_boundary(tmp_path) -> None:
    soup = BeautifulSoup(service_bus_source_path().read_bytes(), "html.parser")
    pure_content = soup.select_one("div.pure-content")
    pricing_body = soup.select_one("div.technical-azure-selector")
    assert pure_content is not None and pricing_body is not None
    pure_content.append(deepcopy(pricing_body))
    source_path = tmp_path / "ambiguous.html"
    source_path.write_text(str(soup), encoding="utf-8")

    report = _check(tmp_path, service_bus_payload(), source_path=source_path)

    assert report["status"] == "blocked"
    assert "实际为 2 个" in report["error"]


def test_l3b_has_no_production_strategy_or_selection_imports() -> None:
    imports: set[str] = set()
    for relative_path in ("l3b.py", "independent_source.py"):
        path = PROJECT_ROOT / "src" / "machine_checks" / relative_path
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)

    forbidden_prefixes = (
        "src.strategies",
        "src.extractors",
        "src.detectors",
        "src.utils.content",
        "src.core.scoped_source_content",
        "src.core.region_processor",
        "src.core.soft_category",
    )
    assert not {
        module
        for module in imports
        if module.startswith(forbidden_prefixes)
    }
