"""Source-neutral price-bearing semantics for trusted HTML fragments.

The classifier is deliberately independent from both source extraction and
payload collection.  It answers one narrow question about an already selected
HTML fragment so source projection evidence and CMS contract validation use
the same meaning of ``price-bearing``.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


PRICE_BEARING_CLASSIFIER_VERSION = "html-price-bearing-v1"

_VISIBLE_PRICE_TOKEN = re.compile(
    r"[￥¥$€£]|(?<![\w])(?:CNY|RMB|USD|free)(?![\w])|免费",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d")
_HIDDEN_CLASSES = frozenset({"hidden", "d-none"})


def is_price_bearing_html(html: object) -> bool:
    """Return whether visible HTML carries an actual price/rate signal."""

    if not isinstance(html, str):
        return False
    try:
        soup = BeautifulSoup(html, "html.parser")
    except (TypeError, ValueError):
        return False

    for element in list(
        soup.find_all(["script", "style", "template", "noscript"])
    ):
        element.decompose()
    for element in list(soup.find_all(True)):
        if element.parent is None:
            continue
        style = re.sub(
            r"\s+",
            "",
            str(element.get("style") or "").lower(),
        )
        classes = {
            str(value).lower()
            for value in (element.get("class") or ())
        }
        if (
            element.has_attr("hidden")
            or str(element.get("aria-hidden") or "").lower() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
            or bool(classes.intersection(_HIDDEN_CLASSES))
        ):
            element.decompose()

    visible_text = " ".join(soup.stripped_strings).replace("\xa0", " ")
    if _VISIBLE_PRICE_TOKEN.search(visible_text):
        return True
    return any(
        table_text and _NUMBER.search(table_text)
        for table in soup.find_all("table")
        if (table_text := table.get_text(" ", strip=True))
    )


__all__ = [
    "PRICE_BEARING_CLASSIFIER_VERSION",
    "is_price_bearing_html",
]
