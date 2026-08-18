"""The one HTML parser and normalization rule shared by extraction and checks."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


class HtmlInputError(ValueError):
    """Frozen HTML is empty or cannot provide the required document structure."""


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
_ROOT_RELATIVE_SRC_PATTERN = re.compile(
    r'''(?P<prefix>\bsrc\s*=\s*(?P<quote>["']))(?P<url>/[^"']*)(?P=quote)''',
    re.IGNORECASE,
)
_ROOT_IMAGES_PATH_PATTERN = re.compile(r"(?<!\{base_url\})/Images/")


def parse_html_bytes(content: bytes, *, source_name: str) -> BeautifulSoup:
    """Parse one non-empty Frozen HTML document with the standard parser."""

    if not content:
        raise HtmlInputError(f"Frozen HTML 为空：{source_name}。")
    soup = BeautifulSoup(content, "html.parser")
    if soup.find("html") is None or soup.find("body") is None:
        raise HtmlInputError(f"Frozen HTML 缺少 html 或 body：{source_name}。")
    return soup


def normalize_html(content: str) -> str:
    """Normalize a complete fragment without changing its element order."""

    if not isinstance(content, str):
        raise TypeError("HTML 片段必须是文本。")
    if not content:
        return ""

    normalized = re.sub(r"\s+", " ", content)
    normalized = re.sub(r"<div>\s*</div>", "", normalized)
    normalized = re.sub(r">\s+<", "><", normalized)
    normalized = _materialize_live_tick_icons(normalized)
    normalized = _rewrite_root_relative_image_sources(normalized)
    normalized = _ROOT_IMAGES_PATH_PATTERN.sub("{base_url}/Images/", normalized)
    return normalized.strip()


def _materialize_live_tick_icons(content: str) -> str:
    if "icon-tick" not in content.casefold():
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
        parts[index] = _EMPTY_ITALIC_PATTERN.sub(replace_empty_icon, parts[index])
    return "".join(parts)


def _rewrite_root_relative_image_sources(content: str) -> str:
    def replace_source(match: re.Match[str]) -> str:
        url = match.group("url")
        if url.startswith("//") or url.startswith("/{base_url}"):
            return match.group(0)
        return (
            f"{match.group('prefix')}{{base_url}}{url}"
            f"{match.group('quote')}"
        )

    return _ROOT_RELATIVE_SRC_PATTERN.sub(replace_source, content)
