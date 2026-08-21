"""Independent source-fragment reconstruction for L3b.

This module deliberately does not import production Strategies, detectors,
content selectors, builders, or region projection code.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from src.core.payload_contract import (
    CURRENT_PAYLOAD_CONTRACT_VERSION,
    FILTER_KEYS_WITH_OPTION_STATUS_BY_CONTRACT,
    PAYLOAD_CONTRACT_VERSIONS,
)
from src.utils.html.normalization import normalize_html


class IndependentSourceError(ValueError):
    """The source does not prove one unambiguous Payload reconstruction."""


def locate_pricing_source(
    soup: BeautifulSoup,
    *,
    semantic_strategy: str,
    language: str,
    soft_category_path: Path | None,
    page_global_source_boundary: str | None = None,
    payload_contract_version: str = CURRENT_PAYLOAD_CONTRACT_VERSION,
) -> dict[str, Any]:
    if payload_contract_version not in PAYLOAD_CONTRACT_VERSIONS:
        raise IndependentSourceError(
            f"L3b 不认识 Payload 合同版本 {payload_contract_version!r}。"
        )
    pure = _one(soup.select("div.pure-content"), "pure-content")
    if semantic_strategy == "simple_static":
        boundary = _simple_pricing_boundary(
            soup,
            pure,
            language=language,
            configured_boundary=page_global_source_boundary,
        )
        return {
            "baseContent": boundary["html"],
            "contentGroups": [],
            "commonSections": _pricing_common_sections(
                pure, boundary["anchors"]
            ),
        }

    if soft_category_path is None:
        raise IndependentSourceError("筛选页面缺少可信区域配置路径。")
    pricing = _one(_outer_pricing_roots(pure), "定价选择器")
    if "pricing-detail-tab" not in pricing.get("class", []):
        raise IndependentSourceError("筛选页面的定价选择器缺少 pricing-detail-tab。")
    common_sections = _pricing_common_sections(pure, (pricing,))
    base_content = _filtered_page_global_content(
        pure,
        pricing,
        configured_boundary=page_global_source_boundary,
    )
    region_control = _read_filter(pricing, "region")
    software_control = _read_filter(pricing, "software")
    if not region_control["visible"]:
        raise IndependentSourceError("筛选页面没有可见区域控件。")
    config_rows = _read_soft_category(soft_category_path)

    if semantic_strategy == "region_filter":
        if software_control["visible"] or len(software_control["options"]) != 1:
            raise IndependentSourceError(
                "RegionFilter 必须声明一个隐藏软件选项。"
            )
        software = software_control["options"][0]["value"]
        direct_bodies = [
            child
            for child in pricing.children
            if isinstance(child, Tag) and "tab-content" in child.get("class", [])
        ]
        direct_static_bodies = [
            child
            for child in pricing.children
            if isinstance(child, Tag)
            and "technical-azure-selector" in child.get("class", [])
            and "tab-control-selector" in child.get("class", [])
        ]
        source_body = _one(
            direct_bodies + direct_static_bodies, "区域定价主体"
        )
        groups: list[dict[str, Any]] = []
        for region in region_control["options"]:
            excluded = _config_row(config_rows, software, region["value"])
            content = _project_one(
                source_body,
                source_scope=pricing,
                excluded=excluded,
            )
            groups.append(
                {
                    "groupName": region["label"],
                    "filterCriteriaJson": _compact_json(
                        [
                            {
                                "filterKey": "region",
                                "matchValues": region["value"],
                            }
                        ]
                    ),
                    "content": content,
                }
            )
        definitions = [
            _filter_definition(
                region_control,
                "region",
                "dropdown",
                payload_contract_version=payload_contract_version,
            )
        ]
        return {
            "baseContent": base_content,
            "contentGroups": groups,
            "commonSections": common_sections,
            "filtersJsonConfig": _compact_json(
                {"filterDefinitions": definitions}
            ),
        }

    if semantic_strategy != "complex":
        raise IndependentSourceError(
            f"L3b 不认识 Pricing Strategy {semantic_strategy!r}。"
        )
    software_options = software_control["options"]
    if not software_options:
        raise IndependentSourceError("Complex 页面没有软件选项。")
    if not software_control["visible"] and len(software_options) != 1:
        raise IndependentSourceError(
            "Complex 隐藏软件筛选器必须恰好有一个选项。"
        )
    dynamic_content = [
        child
        for child in pricing.children
        if isinstance(child, Tag) and "tab-content" in child.get("class", [])
    ]
    static_content = [
        child
        for child in pricing.children
        if isinstance(child, Tag)
        and "technical-azure-selector" in child.get("class", [])
        and "tab-control-selector" in child.get("class", [])
    ]
    top_content = _one(
        dynamic_content + static_content,
        "软件内容容器",
    )
    groups: list[dict[str, Any]] = []
    category_catalog: list[dict[str, str]] = []
    category_by_value: dict[str, dict[str, str]] = {}
    seen_software_values: set[str] = set()
    seen_software_targets: set[str] = set()
    prepared_scopes: list[
        tuple[
            dict[str, str],
            list[tuple[dict[str, str] | None, dict[str, Any]]],
            dict[str, Any],
            dict[str, tuple[str, ...]],
        ]
    ] = []
    for software_option in software_options:
        software = software_option["value"]
        software_target = software_option["href"].removeprefix("#")
        if software in seen_software_values or software_target in seen_software_targets:
            raise IndependentSourceError("软件选项的值或目标重复。")
        seen_software_values.add(software)
        seen_software_targets.add(software_target)
        software_panel = _one(
            top_content.find_all("div", id=software_target, recursive=False),
            f"软件内容面板 {software_target}",
        )
        raw_category_control = _read_categories(software_panel)
        category_control, leaves, shared_fragments = _independent_content_leaves(
            raw_category_control,
            software_panel,
        )
        if len(software_options) == 1:
            shared_fragments = [
                *shared_fragments,
                *_independent_single_software_trailing_fragments(software_panel),
            ]
        exclusions_by_region = {
            region["value"]: _config_row(
                config_rows,
                software,
                region["value"],
            )
            for region in region_control["options"]
        }
        relevant_table_ids = frozenset(
            table_id
            for exclusions in exclusions_by_region.values()
            for table_id in exclusions
        )
        indexed_leaves = [
            (
                category,
                _build_independent_fragment_index(
                    [panel],
                    relevant_table_ids=relevant_table_ids,
                ),
            )
            for category, panel in leaves
        ]
        shared_index = _build_independent_fragment_index(
            shared_fragments,
            relevant_table_ids=relevant_table_ids,
        )
        indexes = [
            shared_index,
            *(index for _category, index in indexed_leaves),
        ]
        applicable_by_region = {
            region: _independent_applicable_exclusions(indexes, exclusions)
            for region, exclusions in exclusions_by_region.items()
        }
        prepared_scopes.append(
            (
                software_option,
                indexed_leaves,
                shared_index,
                applicable_by_region,
            )
        )
        for category in category_control["options"]:
            existing = category_by_value.get(category["value"])
            if existing is not None:
                if existing != category:
                    raise IndependentSourceError(
                        "相同 Category target 在不同 Software 中使用了不同名称。"
                    )
                continue
            category_by_value[category["value"]] = category
            category_catalog.append(category)

    for (
        software_option,
        indexed_leaves,
        shared_index,
        applicable_by_region,
    ) in prepared_scopes:
        software = software_option["value"]
        for region in region_control["options"]:
            applicable_exclusions = applicable_by_region[region["value"]]
            shared_content = _project_independent_fragment_index(
                shared_index,
                applicable_exclusions,
            )
            for category, index in indexed_leaves:
                content = _project_independent_fragment_index(
                    index,
                    applicable_exclusions,
                )
                criteria = []
                labels = []
                if software_control["visible"]:
                    criteria.append(
                        {"filterKey": "software", "matchValues": software}
                    )
                    labels.append(software_option["label"])
                criteria.append(
                    {
                        "filterKey": "region",
                        "matchValues": region["value"],
                    }
                )
                labels.append(region["label"])
                if category is not None:
                    criteria.append(
                        {
                            "filterKey": "category",
                            "matchValues": category["value"],
                        }
                    )
                    labels.append(category["label"])
                group = {
                    "groupName": " - ".join(labels),
                    "filterCriteriaJson": _compact_json(criteria),
                    "content": content,
                }
                if shared_content:
                    group["sharedContent"] = shared_content
                groups.append(group)
    definitions = []
    if software_control["visible"]:
        definitions.append(
            _filter_definition(
                software_control,
                "software",
                "dropdown",
                payload_contract_version=payload_contract_version,
            )
        )
    definitions.append(
        _filter_definition(
            region_control,
            "region",
            "dropdown",
            payload_contract_version=payload_contract_version,
        )
    )
    if category_catalog:
        definitions.append(
            _filter_definition(
                {
                    "visible": True,
                    "display_name": raw_category_control["display_name"],
                    "options": category_catalog,
                },
                "category",
                "tab",
                payload_contract_version=payload_contract_version,
            )
        )
    return {
        "baseContent": base_content,
        "contentGroups": groups,
        "commonSections": common_sections,
        "filtersJsonConfig": _compact_json({"filterDefinitions": definitions}),
    }


def locate_support_source(soup: BeautifulSoup) -> dict[str, str]:
    pure = _one(soup.select("div.pure-content"), "Support Article pure-content")
    direct_nodes = list(pure.children)
    h1_indexes = [
        index
        for index, node in enumerate(direct_nodes)
        if isinstance(node, Tag) and node.name == "h1"
    ]
    h2_indexes = [
        index
        for index, node in enumerate(direct_nodes)
        if isinstance(node, Tag) and node.name == "h2"
    ]
    if len(h1_indexes) != 1 or not h2_indexes or h1_indexes[0] >= h2_indexes[0]:
        raise IndependentSourceError(
            "Support Article 必须有一个直接 h1，并在其后至少有一个直接 h2。"
        )
    h1_index = h1_indexes[0]
    first_h2_index = h2_indexes[0]

    description_holder = BeautifulSoup("<div></div>", "html.parser").div
    assert description_holder is not None
    for node in direct_nodes[h1_index + 1 : first_h2_index]:
        if isinstance(node, Tag) and node.name == "p":
            description_holder.append(deepcopy(node))
    _remove_support_ui(description_holder)

    main_holder = BeautifulSoup("<div></div>", "html.parser").div
    assert main_holder is not None
    for node in direct_nodes[first_h2_index:]:
        if isinstance(node, Comment):
            continue
        if isinstance(node, Tag):
            if node.get("id") == "content_feedback":
                break
            main_holder.append(deepcopy(node))
        elif isinstance(node, NavigableString) and str(node).strip():
            main_holder.append(NavigableString(str(node)))
    _remove_support_ui(main_holder)
    main_content = normalize_html(main_holder.decode_contents())
    if not main_content:
        raise IndependentSourceError("Support Article 主体为空。")
    return {
        "articleDescription": normalize_html(
            description_holder.decode_contents()
        ),
        "mainContent": main_content,
    }


def _simple_pricing_boundary(
    soup: BeautifulSoup,
    pure: Tag,
    *,
    language: str,
    configured_boundary: str | None,
) -> dict[str, Any]:
    body = soup.find("body")
    if not isinstance(body, Tag) or language not in body.get("class", []):
        raise IndependentSourceError(
            f"Simple 源页面 body class 与处理语言 {language} 不一致。"
        )
    banner = _one(pure.select("div.common-banner"), "Banner")
    formal_roots = _outer_pricing_roots(pure)
    static_boundary = "sole_static_formal_selector_before_common_sections"
    if formal_roots:
        pricing = _one(formal_roots, "静态定价主体")
        if "pricing-detail-tab" in pricing.get("class", []) or pricing.select_one(
            ".region-container, .software-kind-container, "
            ".category-container-container"
        ) is not None:
            raise IndependentSourceError("Simple 定价主体实际包含可选择状态。")
        if configured_boundary not in {None, static_boundary}:
            raise IndependentSourceError(
                f"Simple 声明了不适用的源正文边界 {configured_boundary!r}。"
            )
        return {
            "html": normalize_html(str(pricing)),
            "anchors": (pricing,),
        }
    if configured_boundary == static_boundary:
        raise IndependentSourceError("配置要求静态定价选择器，但源页面没有。")
    if configured_boundary is not None:
        raise IndependentSourceError(
            f"Simple 声明了不适用的源正文边界 {configured_boundary!r}。"
        )

    direct = [child for child in pure.children if isinstance(child, Tag)]
    try:
        banner_index = direct.index(banner)
    except ValueError as error:
        raise IndependentSourceError("Banner 必须是 pure-content 的直接子节点。") from error
    material = [
        node for node in direct[banner_index + 1 :] if _independent_is_material(node)
    ]
    first_common = next(
        (
            index
            for index, node in enumerate(material)
            if _independent_qa_role(node, ()) is not None
        ),
        len(material),
    )
    before_common = material[:first_common]
    if any(
        _independent_qa_role(node, ()) is None
        for node in material[first_common:]
    ):
        raise IndependentSourceError("Simple 页面在 FAQ/SLA 之后还有无法归属的内容。")

    pricing_heading = re.compile(
        r"(?:定价详细信息|pricing\s+details?)", re.IGNORECASE
    )
    heading_index = next(
        (
            index
            for index, node in enumerate(before_common)
            if node.name in {"h1", "h2", "h3", "h4", "h5", "h6"}
            and pricing_heading.fullmatch(
                node.get_text(" ", strip=True).strip(" \t\r\n:：")
            )
        ),
        None,
    )
    if heading_index is not None:
        anchors = tuple(before_common[heading_index:])
        if not anchors or not any(node.find("table") is not None for node in anchors):
            raise IndependentSourceError("无包装定价正文必须包含价格表。")
        return {
            "html": normalize_html("".join(str(node) for node in anchors)),
            "anchors": anchors,
        }

    static_table_sections = [
        node
        for node in before_common
        if node.name == "div"
        and set(node.get("class", [])) == {"pricing-page-section"}
        and node.get_text(" ", strip=True)
        and node.find("table") is not None
        and node.select_one(
            ".technical-azure-selector, .pricing-detail-tab, "
            ".region-container, .software-kind-container, "
            ".category-container-container, .category-container, "
            ".tab-container-container, select, form"
        )
        is None
    ]
    if (
        len(before_common) == 1
        and static_table_sections == before_common
        and material[first_common:]
    ):
        return {
            "html": normalize_html(str(static_table_sections[0])),
            "anchors": (static_table_sections[0],),
        }

    free_statements = [
        node
        for node in before_common
        if node.name == "div"
        and set(node.get("class", [])) == {"pricing-page-section"}
        and node.get_text(" ", strip=True)
        and node.find(
            ["h1", "h2", "h3", "h4", "h5", "h6", "table", "select", "button", "form"]
        )
        is None
        and node.select_one(
            ".technical-azure-selector, .pricing-detail-tab, .more-detail"
        )
        is None
    ]
    if len(before_common) == 1 and free_statements == before_common and material[first_common:]:
        return {
            "html": normalize_html(str(free_statements[0])),
            "anchors": (free_statements[0],),
        }
    raise IndependentSourceError(
        "Simple 页面没有唯一的静态选择器、定价标题范围或免费说明正文。"
    )


def _outer_pricing_roots(pure: Tag) -> list[Tag]:
    roots: list[Tag] = []
    for candidate in pure.select("div.technical-azure-selector"):
        if not any(
            isinstance(parent, Tag)
            and parent is not pure
            and "technical-azure-selector" in parent.get("class", [])
            for parent in candidate.parents
        ):
            roots.append(candidate)
    return roots


def _filtered_page_global_content(
    pure: Tag,
    pricing: Tag,
    *,
    configured_boundary: str | None,
) -> str:
    if configured_boundary is None:
        return ""
    if configured_boundary != "after_final_formal_selector_before_common_sections":
        raise IndependentSourceError(
            f"筛选页面声明了不适用的源正文边界 {configured_boundary!r}。"
        )
    if pricing.parent is not pure:
        raise IndependentSourceError(
            "选择器后正文要求定价选择器是 pure-content 的直接子节点。"
        )
    fragments: list[Tag] = []
    common_started = False
    for sibling in pricing.next_siblings:
        if not isinstance(sibling, Tag) or not _independent_is_material(sibling):
            continue
        if _independent_qa_role(sibling, (pricing,)) is not None:
            common_started = True
            continue
        if common_started:
            raise IndependentSourceError("FAQ/SLA 之后还有无法归属的内容。")
        fragments.append(sibling)
    if not fragments:
        raise IndependentSourceError("配置声明选择器后有页面正文，但源片段为空。")
    return normalize_html("".join(str(fragment) for fragment in fragments))


def _pricing_common_sections(
    pure: Tag, pricing_anchors: tuple[Tag, ...]
) -> list[dict[str, str]]:
    ordered_tags = [node for node in pure.descendants if isinstance(node, Tag)]
    positions = {id(node): index for index, node in enumerate(ordered_tags)}
    if any(id(anchor) not in positions for anchor in pricing_anchors):
        raise IndependentSourceError("定价正文不属于当前 pure-content。")
    first_anchor = min(pricing_anchors, key=lambda node: positions[id(node)])
    last_anchor = max(pricing_anchors, key=lambda node: positions[id(node)])
    banner = _one(pure.select("div.common-banner"), "Banner")
    if positions[id(banner)] >= positions[id(first_anchor)]:
        raise IndependentSourceError("Banner 没有位于定价选择器之前。")
    sections = [
        {
            "sectionType": "Banner",
            "source_boundary": "定价范围中的唯一 Banner",
            "content": normalize_html(str(banner)),
        }
    ]
    description_content = _independent_description_projection(
        pure, banner, first_anchor
    )
    if description_content:
        sections.append(
            {
                "sectionType": "ProductDescription",
                "source_boundary": "Banner 后、定价正文前的实际产品说明",
                "content": description_content,
            }
        )

    candidates: list[tuple[Tag, str]] = []
    for node in pure.select("div.pricing-page-section"):
        if positions[id(node)] <= positions[id(last_anchor)]:
            continue
        if any(any(parent is anchor for parent in node.parents) for anchor in pricing_anchors):
            continue
        role = _independent_qa_role(node, pricing_anchors)
        if role is not None:
            candidates.append((node, role))
    for role in ("faq", "sla"):
        if sum(item_role == role for _node, item_role in candidates) > 1:
            raise IndependentSourceError(f"源页面包含多个独立 {role.upper()} 区块。")
    candidates.sort(key=lambda item: positions[id(item[0])])
    roles = [role for _node, role in candidates]
    if roles not in ([], ["faq"], ["sla"], ["faq", "sla"]):
        raise IndependentSourceError("FAQ 与 SLA 的源顺序不正确。")
    qa_fragments: list[str] = []
    for node, role in candidates:
        if role == "faq":
            faq_parts = [
                child
                for child in node.children
                if isinstance(child, Tag) and "more-detail" in child.get("class", [])
            ]
            qa_fragments.append(str(_one(faq_parts, "FAQ more-detail")))
        else:
            qa_fragments.append(str(node))
    if qa_fragments:
        sections.append(
            {
                "sectionType": "Qa",
                "source_boundary": "定价正文后实际存在的 FAQ 和/或 SLA",
                "content": normalize_html("".join(qa_fragments)),
            }
        )
    return sections


def _independent_description_projection(
    pure: Tag, banner: Tag, first_anchor: Tag
) -> str:
    banner_child = _direct_child(pure, banner)
    anchor_child = _direct_child(pure, first_anchor)
    direct = [child for child in pure.children if isinstance(child, Tag)]
    banner_index = direct.index(banner_child)
    anchor_index = direct.index(anchor_child)
    if banner_index >= anchor_index:
        raise IndependentSourceError("产品说明的源范围顺序不正确。")
    fragments = [
        str(node)
        for node in direct[banner_index + 1 : anchor_index]
        if _independent_is_material(node)
        and _independent_qa_role(node, ()) is None
    ]
    if anchor_child is not first_anchor:
        clone = deepcopy(anchor_child)
        roots = _outer_pricing_roots(clone)
        selector = _one(roots, "包住定价正文的选择器")
        for sibling in list(selector.next_siblings):
            sibling.extract()
        selector.extract()
        prefix = normalize_html(str(clone))
        if prefix:
            fragments.append(prefix)
    if not fragments:
        return ""
    result = normalize_html("".join(fragments))
    parsed = BeautifulSoup(result, "html.parser")
    if not parsed.get_text(" ", strip=True) and parsed.select_one(
        "img, video, audio, table, iframe"
    ) is None:
        return ""
    return result


def _independent_qa_role(
    node: Tag, pricing_anchors: tuple[Tag, ...]
) -> str | None:
    if any(node is anchor or anchor in node.descendants for anchor in pricing_anchors):
        return None
    text = node.get_text(" ", strip=True).casefold()
    headings = " ".join(
        heading.get_text(" ", strip=True).casefold()
        for heading in node.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    )
    if node.select_one(".more-detail") is not None or any(
        phrase in headings
        for phrase in ("常见问题", "faq", "frequently asked questions")
    ):
        return "faq"
    if any(
        phrase in headings or phrase in text
        for phrase in (
            "支持和服务级别协议",
            "support & sla",
            "support and sla",
            "service level agreement",
        )
    ):
        return "sla"
    return None


def _direct_child(pure: Tag, node: Tag) -> Tag:
    current = node
    while current.parent is not pure:
        if not isinstance(current.parent, Tag):
            raise IndependentSourceError("源节点不属于 pure-content。")
        current = current.parent
    return current


def _independent_is_material(node: Tag) -> bool:
    if node.name in {"script", "style", "template", "tags"}:
        return False
    classes = set(node.get("class", []))
    if "left-navigation-select" in classes or "hide-info" in classes:
        return False
    return bool(
        node.get_text(" ", strip=True)
        or node.find(["img", "video", "audio", "table", "iframe"]) is not None
    )


def _read_filter(pricing: Tag, kind: str) -> dict[str, Any]:
    class_name = "region-container" if kind == "region" else "software-kind-container"
    container = _one(
        pricing.select(f"div.dropdown-container.{class_name}"),
        f"{kind} 筛选器",
    )
    software_values_by_target: dict[str, list[str]] = {}
    if kind == "software":
        mobile_selects = container.select(
            "select#software-box.hidden-lg.hidden-md"
        )
        if len(mobile_selects) != 1:
            raise IndependentSourceError(
                "Software 需要唯一的移动端 select 提供 option.value 语义键。"
            )
        for option in mobile_selects[0].find_all("option", recursive=False):
            target = str(option.get("data-href", "")).strip()
            value = str(option.get("value", "")).strip()
            if target and value:
                software_values_by_target.setdefault(target, []).append(value)
    elif kind != "region":
        raise IndependentSourceError(f"未知筛选器类型：{kind}。")

    desktop_links = container.select(
        ".dropdown-box.os-tab-nav.hidden-xs.hidden-sm "
        ".tab-items a[data-href]"
    )
    if not desktop_links:
        raise IndependentSourceError(f"{kind} 筛选器没有桌面端选项。")
    desktop_rows: list[dict[str, str]] = []
    desktop_defaults: list[str] = []
    for link in desktop_links:
        href = str(link.get("data-href", "")).strip()
        label = " ".join(link.get_text(" ", strip=True).split())
        if not href.startswith("#") or not href.removeprefix("#") or not label:
            raise IndependentSourceError(
                f"{kind} 桌面端选项缺少内容目标或显示名称。"
            )
        if kind == "region":
            value = href.removeprefix("#")
        else:
            semantic_values = software_values_by_target.get(href, [])
            if len(semantic_values) != 1:
                raise IndependentSourceError(
                    "Software 桌面端选项无法按 target 唯一取得 "
                    "移动端 option.value 语义键。"
                )
            value = semantic_values[0]
        desktop_rows.append({"value": value, "label": label, "href": href})
        parent = link.find_parent("li")
        if isinstance(parent, Tag) and set(parent.get("class", [])) & {
            "active",
            "selected",
            "selected-item",
        }:
            desktop_defaults.append(value)
    values = [row["value"] for row in desktop_rows]
    labels = [row["label"] for row in desktop_rows]
    hrefs = [row["href"] for row in desktop_rows]
    if len(values) != len(set(values)):
        raise IndependentSourceError(f"{kind} 桌面端选项包含重复机器值。")
    if len(labels) != len(set(labels)):
        raise IndependentSourceError(f"{kind} 桌面端选项包含重复名称。")
    if len(hrefs) != len(set(hrefs)):
        raise IndependentSourceError(f"{kind} 桌面端选项包含重复内容目标。")
    selected_item = container.select_one("span.selected-item")
    selected_label = (
        " ".join(selected_item.get_text(" ", strip=True).split())
        if isinstance(selected_item, Tag)
        else ""
    )
    default = _independent_desktop_default(
        desktop_rows,
        desktop_defaults,
        selected_label=selected_label,
        context=f"{kind} 筛选器",
    )
    default_row = _one(
        [row for row in desktop_rows if row["value"] == default],
        f"{kind} 默认选项",
    )
    ordered = [default_row] + [row for row in desktop_rows if row is not default_row]
    label_tag = container.find("label")
    display_name = (
        label_tag.get_text(" ", strip=True).rstrip(":：").strip()
        if isinstance(label_tag, Tag)
        else kind.title()
    )
    compact_style = re.sub(r"\s+", "", str(container.get("style", "")).casefold())
    return {
        "visible": "display:none" not in compact_style,
        "display_name": display_name,
        "options": ordered,
    }


def _independent_desktop_default(
    rows: list[dict[str, str]],
    marked_values: list[str],
    *,
    selected_label: str,
    context: str,
) -> str:
    """Resolve one default using desktop markers and its visible summary."""

    # A unique state marker is explicit source evidence.  The summary is only
    # needed when markers are absent or when several stale markers coexist.
    defaults = list(dict.fromkeys(marked_values))
    if len(defaults) == 1:
        return defaults[0]
    if not defaults and len(rows) == 1:
        return rows[0]["value"]

    summary_matches = [
        row["value"]
        for row in rows
        if selected_label and row["label"] == selected_label
    ]
    if len(summary_matches) != 1:
        raise IndependentSourceError(
            f"{context}的当前项摘要无法唯一对应桌面端选项。"
        )
    summary_default = summary_matches[0]
    if defaults and summary_default not in defaults:
        raise IndependentSourceError(
            f"{context}声明了多个无法消歧的桌面端默认项。"
        )
    return summary_default


def _read_categories(software_panel: Tag) -> dict[str, Any]:
    navs = software_panel.select("ul.os-tab-nav.category-tabs.hidden-xs.hidden-sm")
    if not navs:
        if software_panel.select_one("ul.category-tabs, select.category-tabs") is not None:
            raise IndependentSourceError(
                "Category 控件存在但没有唯一可读的桌面导航。"
            )
        return {
            "visible": False,
            "display_name": "Category",
            "options": [],
            "default": None,
        }
    nav = _one(navs, "桌面 Category 导航")
    rows: list[dict[str, str]] = []
    defaults: list[str] = []
    for link in nav.find_all("a"):
        href = str(link.get("data-href", "")).strip()
        value = href.removeprefix("#")
        label = " ".join(link.get_text(" ", strip=True).split())
        if not value or not label or any(row["value"] == value for row in rows):
            raise IndependentSourceError("Category 选项缺少目标、名称或重复。")
        rows.append({"value": value, "label": label, "href": href})
        parent = link.find_parent("li")
        if isinstance(parent, Tag) and set(parent.get("class", [])) & {
            "active",
            "selected",
            "selected-item",
        }:
            defaults.append(value)
    labels = [row["label"] for row in rows]
    if len(labels) != len(set(labels)):
        raise IndependentSourceError("Category 桌面端选项包含重复名称。")
    selected_item = software_panel.select_one(
        ".category-container span.selected-item"
    )
    selected_label = (
        " ".join(selected_item.get_text(" ", strip=True).split())
        if isinstance(selected_item, Tag)
        else ""
    )
    default = _independent_desktop_default(
        rows,
        defaults,
        selected_label=selected_label,
        context="Category",
    )
    default_row = _one(
        [row for row in rows if row["value"] == default],
        "Category 默认选项",
    )
    ordered = [default_row] + [row for row in rows if row is not default_row]
    title = software_panel.select_one(".category-container .category-title")
    display_name = (
        title.get_text(" ", strip=True).rstrip(":：").strip()
        if isinstance(title, Tag)
        else "Category"
    )
    return {
        "visible": True,
        "display_name": display_name,
        "options": ordered,
        "default": default_row["value"],
    }


def _independent_content_leaves(
    category_control: dict[str, Any], software_panel: Tag
) -> tuple[
    dict[str, Any],
    list[tuple[dict[str, str] | None, Tag]],
    list[Tag],
]:
    options = list(category_control["options"])
    if not options:
        bodies = [
            child
            for child in software_panel.children
            if isinstance(child, Tag)
            and (
                "tab-content" in child.get("class", [])
                or "tabContent" in child.get("class", [])
            )
        ]
        body = _one(bodies, "无 Category 软件内容主体")
        return category_control, [(None, body)], []

    expected_ids = [option["value"] for option in options]
    target_matches = {
        value: software_panel.find_all(id=value) for value in expected_ids
    }
    missing = [
        index
        for index, value in enumerate(expected_ids)
        if not target_matches[value]
    ]
    first = options[0]
    if missing:
        if (
            missing != [0]
            or first["label"].casefold() not in {"all", "全部"}
            or category_control.get("default") != first["value"]
            or len(options) == 1
        ):
            raise IndependentSourceError(
                "Category 控件包含无法证明的缺失内容目标。"
            )
        material = options[1:]
    else:
        material = options
    if not material:
        raise IndependentSourceError("Category 没有可交付的实体内容选项。")

    panels = [
        _one(target_matches[option["value"]], f"Category 内容面板 {option['value']}")
        for option in material
    ]
    parent = panels[0].parent
    if not isinstance(parent, Tag) or any(
        panel.parent is not parent for panel in panels
    ):
        raise IndependentSourceError("Category target 没有唯一共同直接父节点。")
    actual_panels = [
        child
        for child in parent.children
        if isinstance(child, Tag)
        and "tab-panel" in child.get("class", [])
        and child.get("id")
    ]
    actual_ids = [str(panel.get("id")) for panel in actual_panels]
    material_ids = [option["value"] for option in material]
    if actual_ids != material_ids or any(
        actual is not expected
        for actual, expected in zip(actual_panels, panels)
    ):
        raise IndependentSourceError(
            "Category 控件与共同父节点的直接内容面板不是完整有序集合。"
        )

    shared_fragments: list[Tag] = []
    for child in parent.children:
        if child is panels[0]:
            break
        if isinstance(child, Tag) and child.select_one(
            "ul.os-tab-nav.category-tabs, select.category-tabs"
        ) is None:
            shared_fragments.append(child)
    return (
        {
            "visible": True,
            "display_name": category_control["display_name"],
            "options": material,
        },
        list(zip(material, panels)),
        shared_fragments,
    )


def _independent_single_software_trailing_fragments(
    software_panel: Tag,
) -> list[Tag]:
    container = software_panel.parent
    if not isinstance(container, Tag):
        return []
    direct_panels = [
        child
        for child in container.children
        if isinstance(child, Tag) and "tab-panel" in child.get("class", [])
    ]
    if len(direct_panels) != 1 or direct_panels[0] is not software_panel:
        return []

    fragments: list[Tag] = []
    after_panel = False
    for child in container.children:
        if child is software_panel:
            after_panel = True
            continue
        if after_panel and isinstance(child, Tag):
            fragments.append(child)
    return fragments


def _read_soft_category(path: Path) -> dict[tuple[str, str], tuple[str, ...]]:
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IndependentSourceError(
            f"L3b 无法读取可信区域配置 {path}：{error}"
        ) from error
    if not isinstance(raw, list):
        raise IndependentSourceError("可信区域配置顶层不是列表。")
    result: dict[tuple[str, str], tuple[str, ...]] = {}
    for row in raw:
        if not isinstance(row, dict):
            raise IndependentSourceError("可信区域配置包含非对象记录。")
        software = row.get("os")
        region = row.get("region")
        table_ids = row.get("tableIDs")
        if not isinstance(software, str) or not isinstance(region, str) or not isinstance(table_ids, list):
            raise IndependentSourceError("可信区域配置记录字段不完整。")
        key = (software.strip(), region.strip())
        if key in result:
            raise IndependentSourceError(
                f"可信区域配置重复声明 software={key[0]!r}、region={key[1]!r}。"
            )
        normalized: list[str] = []
        for table_id in table_ids:
            if not isinstance(table_id, str) or not table_id.strip().removeprefix("#"):
                raise IndependentSourceError("可信区域配置包含空表格名称。")
            value = table_id.strip().removeprefix("#")
            if value not in normalized:
                normalized.append(value)
        result[key] = tuple(normalized)
    return result


def _config_row(
    rows: dict[tuple[str, str], tuple[str, ...]],
    software: str,
    region: str,
) -> tuple[str, ...]:
    key = (software, region)
    return rows.get(key, ())


def _build_independent_fragment_index(
    fragments: list[Tag],
    *,
    relevant_table_ids: frozenset[str],
) -> dict[str, Any]:
    holder = BeautifulSoup("<div></div>", "html.parser").div
    assert holder is not None
    for fragment in fragments:
        holder.append(deepcopy(fragment))

    units_by_id: dict[str, list[Tag]] = {}
    for candidate in holder.find_all(
        lambda tag: isinstance(tag, Tag)
        and any(
            str(tag.get(attribute, "")).strip() in relevant_table_ids
            for attribute in ("id", "data-table-id")
        )
    ):
        if "scroll-table" in candidate.get("class", []):
            unit = candidate
        else:
            wrapper = candidate.find_parent(
                lambda tag: isinstance(tag, Tag)
                and tag.name == "div"
                and "scroll-table" in tag.get("class", [])
            )
            unit = wrapper if isinstance(wrapper, Tag) else candidate
        if unit.name != "table" and "scroll-table" not in unit.get("class", []):
            raise IndependentSourceError(
                "配置名称指向的不是 table 或 scroll-table 物理单元。"
            )
        identifiers = {
            str(candidate.get(attribute, "")).strip()
            for attribute in ("id", "data-table-id")
            if str(candidate.get(attribute, "")).strip() in relevant_table_ids
        }
        for table_id in identifiers:
            units = units_by_id.setdefault(table_id, [])
            if all(unit is not existing for existing in units):
                units.append(unit)

    return {
        "holder": holder,
        "paths": {
            table_id: tuple(
                _independent_element_path(holder, unit) for unit in units
            )
            for table_id, units in units_by_id.items()
        },
    }


def _independent_applicable_exclusions(
    indexes: list[dict[str, Any]],
    excluded: tuple[str, ...],
) -> tuple[str, ...]:
    available = {
        table_id
        for index in indexes
        for table_id in index["paths"]
    }
    applicable = tuple(table_id for table_id in excluded if table_id in available)
    if excluded and not applicable:
        raise IndependentSourceError(
            "该配置记录在当前 Software 的所有内容叶子中没有对应任何物理表格单元，"
            "实际为 0 个。"
        )
    return applicable


def _project_independent_fragment_index(
    index: dict[str, Any],
    excluded: tuple[str, ...],
) -> str:
    clone = deepcopy(index["holder"])
    selected_paths = {
        path
        for table_id in excluded
        for path in index["paths"].get(table_id, ())
    }
    outermost: list[tuple[int, ...]] = []
    for path in sorted(selected_paths, key=lambda item: (len(item), item)):
        if any(path[: len(parent)] == parent for parent in outermost):
            continue
        outermost.append(path)
    units = [
        _resolve_independent_element_path(clone, path) for path in outermost
    ]
    for unit in units:
        unit.decompose()
    if not (
        clone.get_text(" ", strip=True)
        or clone.select_one("img, video, audio, table, iframe")
    ):
        return ""
    return normalize_html(clone.decode_contents())


def _independent_element_path(root: Tag, node: Tag) -> tuple[int, ...]:
    indexes: list[int] = []
    current = node
    while current is not root:
        parent = current.parent
        if not isinstance(parent, Tag):
            raise IndependentSourceError("表格物理单元不在独立待投影片段内。")
        children = [child for child in parent.children if isinstance(child, Tag)]
        indexes.append(
            next(
                index
                for index, child in enumerate(children)
                if child is current
            )
        )
        current = parent
    return tuple(reversed(indexes))


def _resolve_independent_element_path(root: Tag, path: tuple[int, ...]) -> Tag:
    current = root
    for index in path:
        children = [child for child in current.children if isinstance(child, Tag)]
        if index >= len(children):
            raise IndependentSourceError(
                "独立投影片段的元素路径与 preflight 索引不一致。"
            )
        current = children[index]
    return current


def _project_one(
    fragment: Tag,
    *,
    source_scope: Tag,
    excluded: tuple[str, ...],
    targets_already_validated: bool = False,
) -> str:
    applicable = excluded
    if not targets_already_validated:
        applicable = _validate_targets(source_scope, excluded)
    clone = deepcopy(fragment)
    _remove_targets(clone, applicable)
    return normalize_html(str(clone))


def _project_many(fragments: list[Tag], *, excluded: tuple[str, ...]) -> str:
    holder = BeautifulSoup("<div></div>", "html.parser").div
    assert holder is not None
    for fragment in fragments:
        holder.append(deepcopy(fragment))
    _remove_targets(holder, excluded)
    return normalize_html(holder.decode_contents())


def _validate_targets(scope: Tag, excluded: tuple[str, ...]) -> tuple[str, ...]:
    matched_count = 0
    applicable: list[str] = []
    for table_id in excluded:
        units = _independent_units(scope, table_id)
        if len(units) > 1:
            raise IndependentSourceError(
                f"配置表格 {table_id!r} 在源定价范围内最多对应一个物理表格单元，"
                f"实际为 {len(units)} 个。"
            )
        if units:
            matched_count += 1
            applicable.append(table_id)
    if excluded and matched_count == 0:
        raise IndependentSourceError(
            "该配置记录在当前源定价范围内没有对应任何物理表格单元，"
            "实际为 0 个。"
        )
    return tuple(applicable)


def _remove_targets(scope: Tag, excluded: tuple[str, ...]) -> None:
    for table_id in excluded:
        units = _independent_units(scope, table_id)
        if len(units) > 1:
            raise IndependentSourceError(
                f"配置表格 {table_id!r} 在待核对片段中对应多个表格单元。"
            )
        if units:
            units[0].decompose()


def _independent_units(scope: Tag, table_id: str) -> list[Tag]:
    nodes = list(scope.find_all(attrs={"id": table_id}))
    nodes.extend(scope.find_all(attrs={"data-table-id": table_id}))
    units: list[Tag] = []
    for node in nodes:
        if "scroll-table" in node.get("class", []):
            unit = node
        else:
            wrapper = node.find_parent(
                lambda tag: isinstance(tag, Tag)
                and tag.name == "div"
                and "scroll-table" in tag.get("class", [])
            )
            unit = wrapper if isinstance(wrapper, Tag) else node
        if unit.name != "table" and "scroll-table" not in unit.get("class", []):
            raise IndependentSourceError(
                f"名称 {table_id!r} 没有指向表格单元。"
            )
        if all(unit is not prior for prior in units):
            units.append(unit)
    return units


def _filter_definition(
    control: dict[str, Any],
    key: str,
    filter_type: str,
    *,
    payload_contract_version: str,
) -> dict[str, Any]:
    options: list[dict[str, Any]] = []
    for index, source_option in enumerate(control["options"]):
        option: dict[str, Any] = {
            "value": source_option["value"],
            "label": source_option["label"],
            "href": source_option["href"],
        }
        if key in FILTER_KEYS_WITH_OPTION_STATUS_BY_CONTRACT[
            payload_contract_version
        ]:
            option["isActive"] = True
            if index == 0:
                option["isDefault"] = True
        options.append(option)
    return {
        "filterKey": key,
        "filterType": filter_type,
        "displayName": control["display_name"],
        "options": options,
    }


def _remove_support_ui(fragment: Tag) -> None:
    selectors = (
        "#content_feedback",
        ".content-feedback",
        ".select",
        ".left-navigation-select",
        ".bookmark",
        ".loader",
        ".tags",
        "select",
        "script",
        "style",
        "tags",
    )
    for selector in selectors:
        for node in fragment.select(selector):
            node.decompose()


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _one(candidates: list[Tag], name: str) -> Tag:
    if len(candidates) != 1:
        raise IndependentSourceError(
            f"应恰好找到一个{name}，实际为 {len(candidates)} 个。"
        )
    return candidates[0]
