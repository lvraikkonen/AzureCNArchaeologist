from __future__ import annotations

import json
from copy import deepcopy

from tests.m2_helpers import PROJECT_ROOT
from tests.m3_helpers import l3b_report, product_payload


def test_l3b_passes_all_three_new_m3_representatives_in_both_languages(tmp_path) -> None:
    for product_key in ("api-management", "databricks", "icp-new"):
        for language in ("zh-cn", "en-us"):
            report = l3b_report(
                tmp_path,
                product_key=product_key,
                language=language,
                payload=product_payload(product_key, language),
            )
            assert report["status"] == "passed", report


def test_region_l3b_detects_content_swapped_between_two_regions(tmp_path) -> None:
    payload = product_payload("api-management")
    payload["contentGroups"][0]["content"], payload["contentGroups"][3]["content"] = (
        payload["contentGroups"][3]["content"],
        payload["contentGroups"][0]["content"],
    )

    report = l3b_report(
        tmp_path,
        product_key="api-management",
        language="zh-cn",
        payload=payload,
    )

    assert report["status"] == "failed"
    assert {
        "contentGroups[0].content",
        "contentGroups[3].content",
    }.issubset(
        {
            field["payload_path"]
            for field in report["fields"]
            if field["status"] == "failed"
        }
    )


def test_region_l3b_detects_state_label_and_condition_drift(tmp_path) -> None:
    payload = product_payload("api-management")
    payload["contentGroups"][0]["groupName"] = "错误区域"
    payload["contentGroups"][0]["filterCriteriaJson"] = (
        '[{"filterKey":"region","matchValues":"north-china"}]'
    )

    report = l3b_report(
        tmp_path,
        product_key="api-management",
        language="zh-cn",
        payload=payload,
    )

    failed = {
        field["payload_path"]
        for field in report["fields"]
        if field["status"] == "failed"
    }
    assert "contentGroups[0].groupName" in failed
    assert "contentGroups[0].filterCriteriaJson" in failed


def test_l3b_independently_checks_active_and_default_filter_options(tmp_path) -> None:
    payload = product_payload("api-management")
    config = json.loads(payload["pageConfig"]["filtersJsonConfig"])
    config["filterDefinitions"][0]["options"][0]["isDefault"] = False
    payload["pageConfig"]["filtersJsonConfig"] = json.dumps(
        config,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    report = l3b_report(
        tmp_path,
        product_key="api-management",
        language="zh-cn",
        payload=payload,
    )

    assert report["status"] == "failed"
    assert next(
        field
        for field in report["fields"]
        if field["payload_path"] == "pageConfig.filtersJsonConfig"
    )["status"] == "failed"


def test_l3b_independently_checks_category_option_status(tmp_path) -> None:
    payload = product_payload("databricks")
    config = json.loads(payload["pageConfig"]["filtersJsonConfig"])
    category = next(
        definition
        for definition in config["filterDefinitions"]
        if definition["filterKey"] == "category"
    )
    category["options"][0]["isDefault"] = False
    payload["pageConfig"]["filtersJsonConfig"] = json.dumps(
        config,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    report = l3b_report(
        tmp_path,
        product_key="databricks",
        language="zh-cn",
        payload=payload,
    )

    assert report["status"] == "failed"
    assert next(
        field
        for field in report["fields"]
        if field["payload_path"] == "pageConfig.filtersJsonConfig"
    )["status"] == "failed"


def test_complex_l3b_detects_truncated_category_content(tmp_path) -> None:
    payload = product_payload("databricks")
    payload["contentGroups"][4]["content"] = payload["contentGroups"][4][
        "content"
    ][:-200]

    report = l3b_report(
        tmp_path,
        product_key="databricks",
        language="zh-cn",
        payload=payload,
    )

    assert report["status"] == "failed"
    field = next(
        item
        for item in report["fields"]
        if item["payload_path"] == "contentGroups[4].content"
    )
    assert field["status"] == "failed"
    assert field["difference"]["actual_length"] < field["difference"]["expected_length"]


def test_complex_l3b_detects_shared_content_copied_from_wrong_region(tmp_path) -> None:
    payload = product_payload("databricks")
    payload["contentGroups"][9]["sharedContent"] = payload["contentGroups"][0][
        "sharedContent"
    ]

    report = l3b_report(
        tmp_path,
        product_key="databricks",
        language="zh-cn",
        payload=payload,
    )

    assert report["status"] == "failed"
    assert next(
        field
        for field in report["fields"]
        if field["payload_path"] == "contentGroups[9].sharedContent"
    )["status"] == "failed"


def test_complex_l3b_blocks_when_configured_table_name_is_not_in_source(tmp_path) -> None:
    config = json.loads(
        (PROJECT_ROOT / "data" / "configs" / "soft-category.json").read_text(
            encoding="utf-8-sig"
        )
    )
    changed = deepcopy(config)
    row = next(
        item
        for item in changed
        if item.get("os") == "databricks"
        and item.get("region") == "north-china3"
    )
    row["tableIDs"] = ["#table-name-not-present-in-source"]
    config_path = tmp_path / "soft-category.json"
    config_path.write_text(
        json.dumps(changed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report = l3b_report(
        tmp_path,
        product_key="databricks",
        language="zh-cn",
        payload=product_payload("databricks"),
        soft_category_path=config_path,
    )

    assert report["status"] == "blocked"
    assert "实际为 0 个" in report["error"]


def test_support_l3b_detects_truncated_article_body(tmp_path) -> None:
    payload = product_payload("icp-new")
    payload["mainContent"] = payload["mainContent"][:-300]

    report = l3b_report(
        tmp_path,
        product_key="icp-new",
        language="zh-cn",
        payload=payload,
    )

    assert report["status"] == "failed"
    assert next(
        field for field in report["fields"] if field["payload_path"] == "mainContent"
    )["status"] == "failed"
