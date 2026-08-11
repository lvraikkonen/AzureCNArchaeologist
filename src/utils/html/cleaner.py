#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML内容清理工具
纯HTML清理函数
"""

import re
from typing import Any


CMS_HTML_SEMANTIC_MATERIALIZATION_VERSION = "css-generated-semantics-v1"
ICON_TICK_TEXT = "✓"

_HTML_COMMENT_PATTERN = re.compile(r"(<!--.*?-->)", re.DOTALL)
_EMPTY_ITALIC_PATTERN = re.compile(
    r"<i\b(?P<attributes>[^>]*)>\s*</i\s*>",
    re.IGNORECASE,
)
_CLASS_ATTRIBUTE_PATTERN = re.compile(
    r'''\bclass\s*=\s*(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)')''',
    re.IGNORECASE | re.DOTALL,
)


def materialize_css_generated_semantics(content: str) -> str:
    """Make supported CSS-only glyph semantics portable in CMS HTML.

    Azure pricing tables use an empty ``i.icon-tick`` element whose visible
    check mark is supplied by the source site's icon font.  CMS fragments must
    remain meaningful without that external CSS dependency, so live empty
    elements are replaced by a literal check mark.  HTML comments are source
    history rather than live DOM and are deliberately left untouched.
    """

    if not content or "icon-tick" not in content.casefold():
        return content

    def replace_empty_icon(match: re.Match[str]) -> str:
        attributes = match.group("attributes")
        class_match = _CLASS_ATTRIBUTE_PATTERN.search(attributes)
        if class_match is None:
            return match.group(0)
        class_value = (
            class_match.group("double")
            if class_match.group("double") is not None
            else class_match.group("single")
        )
        if "icon-tick" not in str(class_value).split():
            return match.group(0)
        return ICON_TICK_TEXT

    parts = _HTML_COMMENT_PATTERN.split(content)
    for index in range(0, len(parts), 2):
        parts[index] = _EMPTY_ITALIC_PATTERN.sub(
            replace_empty_icon,
            parts[index],
        )
    return "".join(parts)


def materialize_cms_html_fields(
    payload: dict[str, Any],
    page_model: str,
) -> None:
    """Materialize CSS-only semantics at the final CMS payload boundary.

    Source-derived HTML and its frozen wire hashes deliberately remain
    untouched.  Only closed-world Business Payload HTML fields receive this
    portability projection immediately before persistence (and in the
    validation replay path).
    """

    def materialize_field(owner: dict[str, Any], key: str) -> None:
        value = owner.get(key)
        if isinstance(value, str):
            owner[key] = materialize_css_generated_semantics(value)

    if page_model == "FlexibleContentPage":
        materialize_field(payload, "baseContent")
        groups = payload.get("contentGroups")
        if isinstance(groups, list):
            for group in groups:
                if not isinstance(group, dict):
                    continue
                materialize_field(group, "content")
                materialize_field(group, "sharedContent")
        sections = payload.get("commonSections")
        if isinstance(sections, list):
            for section in sections:
                if isinstance(section, dict):
                    materialize_field(section, "content")
        return
    if page_model == "SupportArticlePage":
        materialize_field(payload, "mainContent")
        return
    raise ValueError(f"Unsupported CMS page model: {page_model!r}")


def clean_html_content(content: str) -> str:
    """
    清理HTML内容中的多余标签和符号
    
    Args:
        content: 原始HTML内容
        
    Returns:
        清理后的HTML内容
    """
    if not content:
        return content

    # 移除多余的换行符和空白符
    content = re.sub(r'\n+', ' ', content)  # 将多个换行符替换为单个空格
    content = re.sub(r'\s+', ' ', content)  # 将多个空白符替换为单个空格

    # 移除多余的div标签包装（保留有用的class和id）
    # 只移除纯粹的包装div，保留有意义的div
    content = re.sub(r'<div>\s*</div>', '', content)  # 移除空的div标签

    # 清理标签间的多余空白
    content = re.sub(r'>\s+<', '><', content)  # 移除标签间的空白

    # 移除开头和结尾的空白
    content = content.strip()

    return content


__all__ = [
    "CMS_HTML_SEMANTIC_MATERIALIZATION_VERSION",
    "ICON_TICK_TEXT",
    "clean_html_content",
    "materialize_cms_html_fields",
    "materialize_css_generated_semantics",
]
