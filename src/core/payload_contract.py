"""Business Payload contracts and deterministic JSON representation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PRICING_PAYLOAD_FIELDS = (
    "title",
    "metaTitle",
    "metaDescription",
    "metaKeywords",
    "slug",
    "language",
    "baseContent",
    "contentGroups",
    "commonSections",
    "pageConfig",
)
SUPPORT_ARTICLE_FIELDS = (
    "title",
    "slug",
    "metaTitle",
    "metaDescription",
    "metaKeywords",
    "pageType",
    "lastModifiedDate",
    "articleDescription",
    "mainContent",
)
COMMON_SECTION_FIELDS = (
    "sectionType",
    "sectionTitle",
    "content",
    "sortOrder",
    "isActive",
)
CONTENT_GROUP_FIELDS = (
    "groupName",
    "filterCriteriaJson",
    "content",
    "sortOrder",
    "isActive",
)
PAGE_CONFIG_FIELDS = (
    "displayTitle",
    "pageIcon",
    "leftNavigationIdentifier",
    "pageType",
    "enableFilters",
    "filtersJsonConfig",
)
LEGACY_PAYLOAD_CONTRACT_VERSION = "1.0"
SOFTWARE_REGION_OPTION_CONTRACT_VERSION = "1.1"
CURRENT_PAYLOAD_CONTRACT_VERSION = "1.2"
FILTER_KEYS_WITH_OPTION_STATUS_BY_CONTRACT = {
    LEGACY_PAYLOAD_CONTRACT_VERSION: frozenset(),
    SOFTWARE_REGION_OPTION_CONTRACT_VERSION: frozenset({"software", "region"}),
    CURRENT_PAYLOAD_CONTRACT_VERSION: frozenset(
        {"software", "region", "category"}
    ),
}
PAYLOAD_CONTRACT_VERSIONS = frozenset(
    FILTER_KEYS_WITH_OPTION_STATUS_BY_CONTRACT
)


class PayloadContractError(ValueError):
    """A Business Payload does not match the declared CMS contract."""


def validate_pricing_payload(
    payload: dict[str, Any],
    *,
    product_key: str,
    language: str,
    semantic_strategy: str,
    payload_contract_version: str = CURRENT_PAYLOAD_CONTRACT_VERSION,
) -> None:
    if payload_contract_version not in PAYLOAD_CONTRACT_VERSIONS:
        raise PayloadContractError(
            f"未知 Pricing Payload 合同版本：{payload_contract_version!r}。"
        )
    _require_exact_fields(payload, PRICING_PAYLOAD_FIELDS, "Payload")
    for field in (
        "title",
        "metaTitle",
        "metaDescription",
        "metaKeywords",
        "slug",
        "language",
        "baseContent",
    ):
        if not isinstance(payload[field], str):
            raise PayloadContractError(f"Payload.{field} 必须是文本。")
    if not payload["title"].strip():
        raise PayloadContractError("Payload.title 不能为空。")
    if payload["slug"] != product_key:
        raise PayloadContractError(
            f"Payload.slug 应为 {product_key}，实际为 {payload['slug']}。"
        )
    if payload["language"] != language:
        raise PayloadContractError(
            f"Payload.language 应为 {language}，实际为 {payload['language']}。"
        )

    groups = payload["contentGroups"]
    if not isinstance(groups, list):
        raise PayloadContractError("Payload.contentGroups 必须是列表。")
    if semantic_strategy == "simple_static":
        if not payload["baseContent"].strip():
            raise PayloadContractError("Simple 页面 baseContent 不能为空。")
        if groups:
            raise PayloadContractError("Simple 页面 contentGroups 必须为空列表。")
    elif semantic_strategy in {"region_filter", "complex"}:
        if not groups:
            raise PayloadContractError("筛选页面必须至少包含一个 Content Group。")
    else:
        raise PayloadContractError(
            f"Pricing Payload 使用未知 Strategy：{semantic_strategy!r}。"
        )

    criteria_rows = _validate_content_groups(groups, semantic_strategy)
    _validate_common_sections(
        payload["commonSections"],
        payload_contract_version=payload_contract_version,
    )
    filter_domains = _validate_page_config(
        payload["pageConfig"],
        payload_title=payload["title"],
        semantic_strategy=semantic_strategy,
        payload_contract_version=payload_contract_version,
    )
    expected_criteria_keys = tuple(filter_domains)
    for group_index, criteria in enumerate(criteria_rows):
        actual_criteria_keys = tuple(key for key, _value in criteria)
        allowed_criteria_keys = {expected_criteria_keys}
        if semantic_strategy == "complex" and expected_criteria_keys[-1:] == (
            "category",
        ):
            allowed_criteria_keys.add(expected_criteria_keys[:-1])
        if actual_criteria_keys not in allowed_criteria_keys:
            raise PayloadContractError(
                f"contentGroups[{group_index}] 的筛选条件种类或顺序"
                "与页面筛选器不一致。"
            )
        for key, value in criteria:
            if key not in filter_domains:
                raise PayloadContractError(
                    f"contentGroups[{group_index}] 使用未声明筛选器 {key!r}。"
                )
            if value not in filter_domains[key]:
                raise PayloadContractError(
                    f"contentGroups[{group_index}] 的 {key}={value!r} "
                    "不在页面筛选选项中。"
                )
    if len(criteria_rows) != len(set(criteria_rows)):
        raise PayloadContractError("Content Group 筛选条件不得重复。")


def validate_simple_pricing_payload(
    payload: dict[str, Any],
    *,
    product_key: str,
    language: str,
    payload_contract_version: str = CURRENT_PAYLOAD_CONTRACT_VERSION,
) -> None:
    validate_pricing_payload(
        payload,
        product_key=product_key,
        language=language,
        semantic_strategy="simple_static",
        payload_contract_version=payload_contract_version,
    )


def validate_support_article_payload(
    payload: dict[str, Any],
    *,
    product_key: str,
    expected_slug: str | None = None,
    support_article_type: str,
) -> None:
    _require_exact_fields(payload, SUPPORT_ARTICLE_FIELDS, "Payload")
    for field in SUPPORT_ARTICLE_FIELDS:
        if not isinstance(payload[field], str):
            raise PayloadContractError(f"Payload.{field} 必须是文本。")
    if not payload["title"].strip() or not payload["mainContent"].strip():
        raise PayloadContractError(
            "Support Article 的 title 和 mainContent 不能为空。"
        )
    required_slug = expected_slug if expected_slug is not None else product_key
    if payload["slug"] != required_slug:
        raise PayloadContractError(
            f"Payload.slug 应为 {required_slug}，实际为 {payload['slug']}。"
        )
    if payload["pageType"] != support_article_type:
        raise PayloadContractError(
            f"Payload.pageType 应为 {support_article_type}，"
            f"实际为 {payload['pageType']}。"
        )


def payload_json_bytes(payload: dict[str, Any]) -> bytes:
    """Return the one stable on-disk representation of a Business Payload."""

    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")


def load_payload(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PayloadContractError(f"无法读取正式 Payload {path}：{error}") from error
    if not isinstance(value, dict):
        raise PayloadContractError(f"正式 Payload 顶层必须是对象：{path}。")
    return value


def _validate_content_groups(
    groups: list[Any], semantic_strategy: str
) -> list[tuple[tuple[str, str], ...]]:
    criteria_rows: list[tuple[tuple[str, str], ...]] = []
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            raise PayloadContractError(f"contentGroups[{index}] 必须是对象。")
        actual_fields = tuple(group)
        allowed_fields = (
            CONTENT_GROUP_FIELDS,
            CONTENT_GROUP_FIELDS + ("sharedContent",),
        )
        if actual_fields not in allowed_fields:
            raise PayloadContractError(
                f"contentGroups[{index}] 字段或顺序不正确：{list(actual_fields)}。"
            )
        if "sharedContent" in group and semantic_strategy != "complex":
            raise PayloadContractError("只有 Complex 页面可以包含 sharedContent。")
        for field in ("groupName", "filterCriteriaJson", "content"):
            if not isinstance(group[field], str):
                raise PayloadContractError(
                    f"contentGroups[{index}].{field} 必须是文本。"
                )
        shared = group.get("sharedContent", "")
        if not isinstance(shared, str):
            raise PayloadContractError(
                f"contentGroups[{index}].sharedContent 必须是文本。"
            )
        if not group["groupName"].strip() or (
            semantic_strategy != "complex"
            and not (group["content"].strip() or shared.strip())
        ):
            raise PayloadContractError(
                f"contentGroups[{index}] 缺少名称或源内容。"
            )
        if group["sortOrder"] != index + 1 or group["isActive"] is not True:
            raise PayloadContractError(
                f"contentGroups[{index}] 的顺序或启用状态不正确。"
            )
        try:
            raw_criteria = json.loads(group["filterCriteriaJson"])
        except json.JSONDecodeError as error:
            raise PayloadContractError(
                f"contentGroups[{index}].filterCriteriaJson 不是 JSON：{error}"
            ) from error
        if not isinstance(raw_criteria, list) or not raw_criteria:
            raise PayloadContractError(
                f"contentGroups[{index}] 必须包含筛选条件。"
            )
        criteria: list[tuple[str, str]] = []
        for criterion in raw_criteria:
            if not isinstance(criterion, dict) or tuple(criterion) != (
                "filterKey",
                "matchValues",
            ):
                raise PayloadContractError(
                    f"contentGroups[{index}] 的筛选条件字段不正确。"
                )
            key = criterion["filterKey"]
            value = criterion["matchValues"]
            if not isinstance(key, str) or not key or not isinstance(value, str) or not value:
                raise PayloadContractError(
                    f"contentGroups[{index}] 的筛选条件必须是非空文本。"
                )
            criteria.append((key, value))
        criteria_rows.append(tuple(criteria))
    return criteria_rows


def _validate_common_sections(
    value: Any,
    *,
    payload_contract_version: str,
) -> None:
    if not isinstance(value, list):
        raise PayloadContractError("Payload.commonSections 必须是列表。")
    actual_types = [
        section.get("sectionType")
        for section in value
        if isinstance(section, dict)
    ]
    allowed_order = ["Banner", "ProductDescription", "Qa"]
    if (
        not actual_types
        or actual_types[0] != "Banner"
        or len(actual_types) != len(value)
        or len(actual_types) != len(set(actual_types))
        or actual_types != [item for item in allowed_order if item in actual_types]
    ):
        raise PayloadContractError(
            "Pricing commonSections 必须以 Banner 开始，并按源页面实际存在的 "
            "ProductDescription、Qa 顺序排列。"
        )
    for index, section in enumerate(value):
        if not isinstance(section, dict):
            raise PayloadContractError(f"commonSections[{index}] 必须是对象。")
        _require_exact_fields(
            section, COMMON_SECTION_FIELDS, f"commonSections[{index}]"
        )
        if not isinstance(section["content"], str) or not section["content"].strip():
            raise PayloadContractError(
                f"commonSections[{index}].content 必须是非空文本。"
            )
        expected_title = (
            ""
            if payload_contract_version == LEGACY_PAYLOAD_CONTRACT_VERSION
            else section["sectionType"]
        )
        if section["sectionTitle"] != expected_title:
            raise PayloadContractError(
                f"commonSections[{index}].sectionTitle 不符合 "
                f"Pricing Payload 合同 {payload_contract_version}。"
            )
        if section["sortOrder"] != index + 1 or section["isActive"] is not True:
            raise PayloadContractError(
                f"commonSections[{index}] 的顺序或启用状态不正确。"
            )


def _validate_page_config(
    value: Any,
    *,
    payload_title: str,
    semantic_strategy: str,
    payload_contract_version: str,
) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict):
        raise PayloadContractError("Payload.pageConfig 必须是对象。")
    _require_exact_fields(value, PAGE_CONFIG_FIELDS, "pageConfig")
    if value["displayTitle"] != payload_title:
        raise PayloadContractError("pageConfig.displayTitle 必须等于 Payload.title。")
    if value["pageIcon"] != "{base_url}/Static/Favicon/favicon.ico":
        raise PayloadContractError("pageConfig.pageIcon 不符合约定。")
    if not isinstance(value["leftNavigationIdentifier"], str) or not value[
        "leftNavigationIdentifier"
    ].strip():
        raise PayloadContractError("pageConfig.leftNavigationIdentifier 不能为空。")
    expectations = {
        "simple_static": ("Simple", False, ((),)),
        "region_filter": ("RegionFilter", True, (("region",),)),
        "complex": (
            "ComplexFilter",
            True,
            (
                ("region",),
                ("software", "region"),
                ("region", "category"),
                ("software", "region", "category"),
            ),
        ),
    }
    expected_page_type, expected_enabled, allowed_key_orders = expectations[
        semantic_strategy
    ]
    if value["pageType"] != expected_page_type or value["enableFilters"] is not expected_enabled:
        raise PayloadContractError("pageConfig 与生产 Strategy 不一致。")
    try:
        filter_config = json.loads(value["filtersJsonConfig"])
    except (TypeError, json.JSONDecodeError) as error:
        raise PayloadContractError(f"filtersJsonConfig 不是 JSON：{error}") from error
    if not isinstance(filter_config, dict) or tuple(filter_config) != (
        "filterDefinitions",
    ):
        raise PayloadContractError("filtersJsonConfig 顶层字段不正确。")
    definitions = filter_config["filterDefinitions"]
    if not isinstance(definitions, list):
        raise PayloadContractError("filterDefinitions 必须是列表。")
    actual_keys = tuple(
        definition.get("filterKey")
        for definition in definitions
        if isinstance(definition, dict)
    )
    if actual_keys not in allowed_key_orders:
        raise PayloadContractError("筛选器种类或顺序与 Strategy 不一致。")
    domains: dict[str, tuple[str, ...]] = {}
    for index, definition in enumerate(definitions):
        if not isinstance(definition, dict) or tuple(definition) != (
            "filterKey",
            "filterType",
            "displayName",
            "options",
        ):
            raise PayloadContractError(
                f"filterDefinitions[{index}] 字段或顺序不正确。"
            )
        options = definition["options"]
        if not isinstance(options, list) or not options:
            raise PayloadContractError(
                f"filterDefinitions[{index}] 没有筛选选项。"
            )
        values: list[str] = []
        for option_index, option in enumerate(options):
            filter_key = definition["filterKey"]
            option_status_keys = FILTER_KEYS_WITH_OPTION_STATUS_BY_CONTRACT[
                payload_contract_version
            ]
            if filter_key in option_status_keys:
                expected_option_fields = (
                    ("value", "label", "href", "isActive", "isDefault")
                    if option_index == 0
                    else ("value", "label", "href", "isActive")
                )
            else:
                expected_option_fields = ("value", "label", "href")
            if not isinstance(option, dict) or tuple(option) != expected_option_fields:
                raise PayloadContractError(
                    f"filterDefinitions[{index}].options[{option_index}] "
                    "字段或顺序不正确。"
                )
            if any(
                not isinstance(option[field], str) or not option[field]
                for field in ("value", "label", "href")
            ):
                raise PayloadContractError("筛选选项必须是非空文本。")
            if filter_key in option_status_keys:
                if option["isActive"] is not True:
                    raise PayloadContractError(
                        f"{filter_key} 筛选选项必须启用。"
                    )
                if option_index == 0 and option["isDefault"] is not True:
                    raise PayloadContractError(
                        f"{filter_key} 筛选器的第一个选项必须是默认项。"
                    )
            values.append(option["value"])
        if len(values) != len(set(values)):
            raise PayloadContractError("同一个筛选器不能包含重复值。")
        domains[definition["filterKey"]] = tuple(values)
    return domains


def _require_exact_fields(
    value: dict[str, Any], expected_fields: tuple[str, ...], location: str
) -> None:
    actual = tuple(value)
    if actual != expected_fields:
        missing = [field for field in expected_fields if field not in value]
        extra = [field for field in value if field not in expected_fields]
        raise PayloadContractError(
            f"{location} 字段或顺序不正确；缺少 {missing}，多出 {extra}，"
            f"实际顺序为 {list(actual)}。"
        )
