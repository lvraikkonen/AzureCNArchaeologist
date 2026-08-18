"""Classification helpers retained for copied Strategy fallback methods."""

from __future__ import annotations

from collections.abc import Iterable

from bs4 import Tag


def classify_pricing_section(section: Tag) -> str:
    classes = set(section.get("class", []))
    text = section.get_text(" ", strip=True).casefold()
    if "more-detail" in classes or section.select_one(".more-detail") is not None:
        return "faq"
    if any(
        phrase in text
        for phrase in (
            "支持和服务级别协议",
            "support & sla",
            "support and sla",
            "service level agreement",
        )
    ):
        return "sla"
    return "content"


def filter_sections_by_type(
    sections: Iterable[Tag], *, include_types: list[str]
) -> list[Tag]:
    allowed = set(include_types)
    return [
        section
        for section in sections
        if classify_pricing_section(section) in allowed
    ]
