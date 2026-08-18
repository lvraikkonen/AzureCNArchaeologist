"""L3b: independently locate source fragments and compare all business HTML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.payload_contract import load_payload
from src.machine_checks.independent_source import (
    locate_pricing_source,
    locate_support_source,
)
from src.machine_checks.readable_diff import text_difference
from src.utils.html.normalization import normalize_html, parse_html_bytes


def run_l3b(
    *,
    frozen_html_path: Path,
    payload_path: Path,
    product_key: str,
    language: str,
    page_model: str = "FlexibleContentPage",
    semantic_strategy: str = "simple_static",
    soft_category_path: Path | None = None,
    page_global_source_boundary: str | None = None,
) -> dict[str, Any]:
    """Compare persisted content against a fresh independent source walk."""

    try:
        soup = parse_html_bytes(
            frozen_html_path.read_bytes(), source_name=str(frozen_html_path)
        )
        payload = load_payload(payload_path)
        if page_model == "SupportArticlePage":
            expected = locate_support_source(soup)
        elif page_model == "FlexibleContentPage":
            expected = locate_pricing_source(
                soup,
                semantic_strategy=semantic_strategy,
                language=language,
                soft_category_path=soft_category_path,
                page_global_source_boundary=page_global_source_boundary,
            )
        else:
            raise ValueError(f"未知页面类型：{page_model}。")
    except Exception as error:
        return {
            "check": "L3b",
            "status": "blocked",
            "product_key": product_key,
            "language": language,
            "scope": "全部业务 HTML 字段",
            "fields": [],
            "error": f"无法独立确定源片段：{error}",
        }

    fields: list[dict[str, Any]] = []
    if page_model == "SupportArticlePage":
        _compare_html_field(
            fields,
            payload_path="articleDescription",
            source_boundary="h1 与首个 h2 之间的直接说明段落",
            expected=expected["articleDescription"],
            actual=payload.get("articleDescription"),
        )
        _compare_html_field(
            fields,
            payload_path="mainContent",
            source_boundary="首个直接 h2 至反馈控件之前的完整文章主体",
            expected=expected["mainContent"],
            actual=payload.get("mainContent"),
        )
    else:
        _compare_pricing(fields, expected=expected, payload=payload)

    status = (
        "passed"
        if fields and all(field["status"] == "passed" for field in fields)
        else "failed"
    )
    return {
        "check": "L3b",
        "status": status,
        "product_key": product_key,
        "language": language,
        "scope": "全部业务 HTML 字段",
        "fields": fields,
    }


def _compare_pricing(
    fields: list[dict[str, Any]],
    *,
    expected: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    _compare_html_field(
        fields,
        payload_path="baseContent",
        source_boundary=(
            "完整静态定价主体"
            if expected["baseContent"]
            else "筛选页面没有单独的全局正文"
        ),
        expected=expected["baseContent"],
        actual=payload.get("baseContent"),
    )
    _compare_content_groups(
        fields,
        expected=expected["contentGroups"],
        actual=payload.get("contentGroups"),
    )
    _compare_common_sections(
        fields,
        expected=expected["commonSections"],
        actual=payload.get("commonSections"),
    )
    if "filtersJsonConfig" in expected:
        page_config = payload.get("pageConfig")
        actual_filter_config = (
            page_config.get("filtersJsonConfig")
            if isinstance(page_config, dict)
            else None
        )
        _compare_value(
            fields,
            payload_path="pageConfig.filtersJsonConfig",
            source_boundary="独立读取的筛选器名称、顺序、默认项和值域",
            expected=expected["filtersJsonConfig"],
            actual=actual_filter_config,
        )


def _compare_content_groups(
    fields: list[dict[str, Any]],
    *,
    expected: list[dict[str, Any]],
    actual: Any,
) -> None:
    if not expected:
        _compare_value(
            fields,
            payload_path="contentGroups",
            source_boundary="静态定价主体没有可选择页面状态",
            expected=[],
            actual=actual,
        )
        return
    if not isinstance(actual, list):
        _compare_value(
            fields,
            payload_path="contentGroups",
            source_boundary="独立读取的全部源页面可选择状态",
            expected=f"包含 {len(expected)} 个状态的列表",
            actual=type(actual).__name__,
        )
        return
    _compare_value(
        fields,
        payload_path="contentGroups",
        source_boundary="独立读取的全部源页面可选择状态",
        expected=len(expected),
        actual=len(actual),
        expected_label="expected_count",
        actual_label="actual_count",
    )
    for index, expected_group in enumerate(expected):
        actual_group = actual[index] if index < len(actual) else None
        for field_name in ("groupName", "filterCriteriaJson"):
            _compare_value(
                fields,
                payload_path=f"contentGroups[{index}].{field_name}",
                source_boundary="源筛选控件声明的状态名称与机器条件",
                expected=expected_group[field_name],
                actual=(
                    actual_group.get(field_name)
                    if isinstance(actual_group, dict)
                    else None
                ),
            )
        _compare_html_field(
            fields,
            payload_path=f"contentGroups[{index}].content",
            source_boundary="该状态对应的完整定价内容面板",
            expected=expected_group["content"],
            actual=(
                actual_group.get("content")
                if isinstance(actual_group, dict)
                else None
            ),
        )
        if "sharedContent" in expected_group or (
            isinstance(actual_group, dict) and "sharedContent" in actual_group
        ):
            _compare_html_field(
                fields,
                payload_path=f"contentGroups[{index}].sharedContent",
                source_boundary=(
                    "Category 面板之前、按当前区域配置投影的公共定价内容"
                ),
                expected=expected_group.get("sharedContent", ""),
                actual=(
                    actual_group.get("sharedContent")
                    if isinstance(actual_group, dict)
                    else None
                ),
            )


def _compare_common_sections(
    fields: list[dict[str, Any]],
    *,
    expected: list[dict[str, str]],
    actual: Any,
) -> None:
    if not isinstance(actual, list):
        _compare_value(
            fields,
            payload_path="commonSections",
            source_boundary="Banner、产品说明、FAQ 与 SLA",
            expected=f"包含 {len(expected)} 个区块的列表",
            actual=type(actual).__name__,
        )
        return
    if len(actual) != len(expected):
        _compare_value(
            fields,
            payload_path="commonSections",
            source_boundary="Banner、产品说明、FAQ 与 SLA",
            expected=len(expected),
            actual=len(actual),
            expected_label="expected_count",
            actual_label="actual_count",
        )
    for index, expected_section in enumerate(expected):
        actual_section = actual[index] if index < len(actual) else None
        _compare_value(
            fields,
            payload_path=f"commonSections[{index}].sectionType",
            source_boundary=expected_section["source_boundary"],
            expected=expected_section["sectionType"],
            actual=(
                actual_section.get("sectionType")
                if isinstance(actual_section, dict)
                else None
            ),
            emit_when_equal=False,
        )
        _compare_html_field(
            fields,
            payload_path=f"commonSections[{index}].content",
            source_boundary=expected_section["source_boundary"],
            expected=expected_section["content"],
            actual=(
                actual_section.get("content")
                if isinstance(actual_section, dict)
                else None
            ),
        )


def _compare_html_field(
    fields: list[dict[str, Any]],
    *,
    payload_path: str,
    source_boundary: str,
    expected: str,
    actual: Any,
) -> None:
    if not isinstance(actual, str):
        fields.append(
            {
                "payload_path": payload_path,
                "source_boundary": source_boundary,
                "status": "failed",
                "difference": {
                    "expected": "HTML 文本",
                    "actual": type(actual).__name__,
                },
            }
        )
        return
    normalized_expected = normalize_html(expected)
    normalized_actual = normalize_html(actual)
    result: dict[str, Any] = {
        "payload_path": payload_path,
        "source_boundary": source_boundary,
        "status": (
            "passed" if normalized_expected == normalized_actual else "failed"
        ),
    }
    if normalized_expected != normalized_actual:
        result["difference"] = text_difference(
            normalized_expected,
            normalized_actual,
        )
    fields.append(result)


def _compare_value(
    fields: list[dict[str, Any]],
    *,
    payload_path: str,
    source_boundary: str,
    expected: Any,
    actual: Any,
    expected_label: str = "expected",
    actual_label: str = "actual",
    emit_when_equal: bool = True,
) -> None:
    equal = expected == actual
    if equal and not emit_when_equal:
        return
    result: dict[str, Any] = {
        "payload_path": payload_path,
        "source_boundary": source_boundary,
        "status": "passed" if equal else "failed",
    }
    if not equal:
        result["difference"] = {
            expected_label: expected,
            actual_label: actual,
        }
    fields.append(result)
