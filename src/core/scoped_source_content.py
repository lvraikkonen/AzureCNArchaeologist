"""Production-only source boundaries for Pricing page content."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup, Tag

from src.utils.html.normalization import normalize_html


STATIC_FORMAL_SELECTOR_PAGE_GLOBAL_BOUNDARY = (
    "sole_static_formal_selector_before_common_sections"
)
AFTER_FINAL_FORMAL_SELECTOR_BOUNDARY = (
    "after_final_formal_selector_before_common_sections"
)
_PRICING_HEADING = re.compile(
    r"(?:定价详细信息|pricing\s+details?)",
    re.IGNORECASE,
)


class PageBodyBoundaryError(ValueError):
    """The production Strategy cannot identify a unique Pricing body."""


@dataclass(frozen=True)
class PricingBoundary:
    """Exact source nodes owned by one Pricing body."""

    html: str
    anchors: tuple[Tag, ...]
    formal_root: Tag | None


def locate_formal_pricing_boundary(soup: BeautifulSoup) -> PricingBoundary:
    pure = _one(soup.select("div.pure-content"), "pure-content")
    root = _one(_outer_formal_roots(pure), "正式定价选择器")
    return PricingBoundary(
        html=normalize_html(str(root)),
        anchors=(root,),
        formal_root=root,
    )


def locate_simple_pricing_boundary(
    soup: BeautifulSoup,
    product_config: dict[str, Any],
    *,
    language: str,
) -> PricingBoundary:
    """Locate one static body from an exact supported Simple page shape."""

    _validate_declared_language(soup, language)
    pure = _one(soup.select("div.pure-content"), "pure-content")
    banner = _one(pure.select("div.common-banner"), "Banner")
    formal_roots = _outer_formal_roots(pure)
    configured = _configured_boundary(product_config)

    if formal_roots:
        root = _one(formal_roots, "静态定价主体")
        if "pricing-detail-tab" in root.get("class", []) or root.select_one(
            ".region-container, .software-kind-container, "
            ".category-container-container"
        ) is not None:
            raise PageBodyBoundaryError(
                "Simple 页面定价主体包含区域、软件或 Category 状态控件。"
            )
        if configured not in {
            None,
            STATIC_FORMAL_SELECTOR_PAGE_GLOBAL_BOUNDARY,
        }:
            raise PageBodyBoundaryError(
                f"Simple 页面声明了不适用的正文边界 {configured!r}。"
            )
        return PricingBoundary(
            html=normalize_html(str(root)),
            anchors=(root,),
            formal_root=root,
        )

    if configured == STATIC_FORMAL_SELECTOR_PAGE_GLOBAL_BOUNDARY:
        raise PageBodyBoundaryError("配置要求静态定价选择器，但源页面没有该节点。")
    if configured is not None:
        raise PageBodyBoundaryError(
            f"Simple 页面声明了不适用的正文边界 {configured!r}。"
        )

    direct = [child for child in pure.children if isinstance(child, Tag)]
    try:
        banner_index = direct.index(banner)
    except ValueError as error:
        raise PageBodyBoundaryError("Banner 必须是 pure-content 的直接子节点。") from error
    page_nodes = [node for node in direct[banner_index + 1 :] if _is_material(node)]
    first_common = next(
        (index for index, node in enumerate(page_nodes) if is_common_section_boundary(node)),
        len(page_nodes),
    )
    before_common = page_nodes[:first_common]
    after_common = page_nodes[first_common:]
    if any(not is_common_section_boundary(node) for node in after_common):
        raise PageBodyBoundaryError(
            "Simple 页面在 FAQ/SLA 之后还有无法归属的业务内容。"
        )

    heading_index = next(
        (
            index
            for index, node in enumerate(before_common)
            if node.name in {"h1", "h2", "h3", "h4", "h5", "h6"}
            and _PRICING_HEADING.fullmatch(
                node.get_text(" ", strip=True).strip(" \t\r\n:：")
            )
        ),
        None,
    )
    if heading_index is not None:
        anchors = tuple(before_common[heading_index:])
        if not anchors or not any(node.find("table") is not None for node in anchors):
            raise PageBodyBoundaryError(
                "无包装 Pricing 正文必须从明确的定价标题开始并包含价格表。"
            )
        return PricingBoundary(
            html=normalize_html("".join(str(node) for node in anchors)),
            anchors=anchors,
            formal_root=None,
        )

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
        and after_common
    ):
        node = static_table_sections[0]
        return PricingBoundary(
            html=normalize_html(str(node)),
            anchors=(node,),
            formal_root=None,
        )

    free_statements = [
        node
        for node in before_common
        if node.name == "div"
        and set(node.get("class", [])) == {"pricing-page-section"}
        and node.get_text(" ", strip=True)
        and node.find(
            [
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "table",
                "select",
                "button",
                "form",
            ]
        )
        is None
        and node.select_one(
            ".technical-azure-selector, .pricing-detail-tab, .more-detail"
        )
        is None
    ]
    if len(before_common) == 1 and free_statements == before_common and after_common:
        node = free_statements[0]
        return PricingBoundary(
            html=normalize_html(str(node)),
            anchors=(node,),
            formal_root=None,
        )

    raise PageBodyBoundaryError(
        "Simple 页面没有唯一的静态选择器、定价标题范围或免费说明正文。"
    )


def resolve_page_global_base_content(
    soup: BeautifulSoup,
    product_config: dict[str, Any],
    *,
    language: str,
) -> str:
    """Resolve explicitly declared content outside a filtered Pricing selector."""

    _validate_declared_language(soup, language, allow_incorrect_body_marker=True)
    boundary = _configured_boundary(product_config)
    if boundary is None:
        return ""
    if boundary != AFTER_FINAL_FORMAL_SELECTOR_BOUNDARY:
        raise PageBodyBoundaryError(
            f"筛选页面声明了不适用的正文边界 {boundary!r}。"
        )

    pure = _one(soup.select("div.pure-content"), "pure-content")
    root = _one(_outer_formal_roots(pure), "正式定价选择器")
    if root.parent is not pure:
        raise PageBodyBoundaryError(
            "选择器之后的页面正文要求正式定价选择器是 pure-content 的直接子节点。"
        )

    fragments: list[Tag] = []
    common_started = False
    for sibling in root.next_siblings:
        if not isinstance(sibling, Tag) or not _is_material(sibling):
            continue
        if is_common_section_boundary(sibling):
            common_started = True
            continue
        if common_started:
            raise PageBodyBoundaryError("FAQ/SLA 之后还有无法归属的业务内容。")
        fragments.append(sibling)
    if not fragments:
        raise PageBodyBoundaryError("配置声明选择器之后有页面正文，但源片段为空。")
    return normalize_html("".join(str(fragment) for fragment in fragments))


def is_common_section_boundary(node: Tag) -> bool:
    if node.name != "div" or "pricing-page-section" not in node.get("class", []):
        return False
    text = node.get_text(" ", strip=True).casefold()
    if node.select_one(".more-detail") is not None:
        return True
    headings = " ".join(
        heading.get_text(" ", strip=True).casefold()
        for heading in node.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    )
    return any(
        phrase in headings or phrase in text
        for phrase in (
            "常见问题",
            "faq",
            "frequently asked questions",
            "支持和服务级别协议",
            "support & sla",
            "support and sla",
            "service level agreement",
        )
    )


def _outer_formal_roots(pure: Tag) -> list[Tag]:
    roots: list[Tag] = []
    for candidate in pure.select("div.technical-azure-selector"):
        nested = False
        for parent in candidate.parents:
            if parent is pure:
                break
            if isinstance(parent, Tag) and "technical-azure-selector" in parent.get(
                "class", []
            ):
                nested = True
                break
        if not nested:
            roots.append(candidate)
    return roots


def _configured_boundary(product_config: dict[str, Any]) -> str | None:
    extraction = product_config.get("extraction")
    page_global = (
        extraction.get("page_global_content") if isinstance(extraction, dict) else None
    )
    if page_global is None:
        return None
    if not isinstance(page_global, dict):
        raise PageBodyBoundaryError("page_global_content 必须是对象。")
    boundary = page_global.get("source_boundary")
    if not isinstance(boundary, str) or not boundary:
        raise PageBodyBoundaryError("page_global_content 缺少可读 source_boundary。")
    return boundary


def _validate_declared_language(
    soup: BeautifulSoup,
    language: str,
    *,
    allow_incorrect_body_marker: bool = False,
) -> None:
    if language not in {"zh-cn", "en-us"}:
        raise PageBodyBoundaryError(f"未知处理语言 {language!r}。")
    if allow_incorrect_body_marker:
        return
    body = soup.find("body")
    markers = body.get("class", []) if isinstance(body, Tag) else []
    if language not in markers:
        raise PageBodyBoundaryError(
            f"Simple 源页面 body class 与处理语言 {language} 不一致。"
        )


def _is_material(node: Tag) -> bool:
    if node.name in {"script", "style", "template", "tags"}:
        return False
    classes = set(node.get("class", []))
    if "left-navigation-select" in classes or "hide-info" in classes:
        return False
    return bool(
        node.get_text(" ", strip=True)
        or node.find(["img", "video", "audio", "table", "iframe"]) is not None
    )


def _one(candidates: list[Tag], name: str) -> Tag:
    if len(candidates) != 1:
        raise PageBodyBoundaryError(
            f"源页面必须恰好包含一个{name}；实际为 {len(candidates)} 个。"
        )
    return candidates[0]
