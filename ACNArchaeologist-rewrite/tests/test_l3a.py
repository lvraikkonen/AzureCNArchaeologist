from __future__ import annotations

from copy import deepcopy

from src.machine_checks.l3a import run_l3a
from tests.m2_helpers import service_bus_payload, write_payload


def test_l3a_passes_for_fresh_repeat_extraction(tmp_path) -> None:
    payload = service_bus_payload()
    path = write_payload(tmp_path / "payload.json", payload)

    report = run_l3a(
        payload_path=path,
        extract_again=lambda: deepcopy(payload),
        product_key="service-bus",
        language="zh-cn",
    )

    assert report["status"] == "passed"
    assert report["differences"] == []


def test_l3a_detects_list_order_change(tmp_path) -> None:
    payload = service_bus_payload()
    path = write_payload(tmp_path / "payload.json", payload)
    repeated = deepcopy(payload)
    repeated["commonSections"][0], repeated["commonSections"][1] = (
        repeated["commonSections"][1],
        repeated["commonSections"][0],
    )

    report = run_l3a(
        payload_path=path,
        extract_again=lambda: repeated,
        product_key="service-bus",
        language="zh-cn",
    )

    assert report["status"] == "failed"
    assert any(
        difference["path"].startswith("$.commonSections[0]")
        for difference in report["differences"]
    )


def test_l3a_detects_missing_content_group_and_extra_time_field(tmp_path) -> None:
    payload = service_bus_payload()
    payload["contentGroups"] = [
        {"groupName": "first", "content": "<p>one</p>"},
        {"groupName": "second", "content": "<p>two</p>"},
    ]
    path = write_payload(tmp_path / "payload.json", payload)
    repeated = deepcopy(payload)
    repeated["contentGroups"].pop()
    repeated["extraction_time"] = "changes every run"

    report = run_l3a(
        payload_path=path,
        extract_again=lambda: repeated,
        product_key="service-bus",
        language="zh-cn",
    )

    assert report["status"] == "failed"
    paths = {difference["path"] for difference in report["differences"]}
    assert "$.contentGroups" in paths
    assert "$.extraction_time" in paths


def test_l3a_reports_blocked_when_repeat_extraction_cannot_run(tmp_path) -> None:
    path = write_payload(tmp_path / "payload.json", service_bus_payload())

    def fail() -> dict:
        raise ValueError("受控的第二次抽取失败")

    report = run_l3a(
        payload_path=path,
        extract_again=fail,
        product_key="service-bus",
        language="zh-cn",
    )

    assert report["status"] == "blocked"
    assert "受控的第二次抽取失败" in report["error"]

