"""Small, selection-free helpers for inline CSS declarations."""

from __future__ import annotations

import re


_DISPLAY_NONE = re.compile(r"\s*display\s*:\s*none\s*(?:!\s*important\s*)?", re.I)


def without_display_none(style: str) -> str:
    """Remove only display:none declarations, preserving other CSS verbatim.

    This is used on source nodes already selected for a region, not by the
    global HTML normalizer (which must still detect hidden Payload content).
    Semicolons in comments, strings, and functions are not declaration ends.
    """

    kept: list[str] = []
    changed = False
    for declaration in _declarations(style):
        candidate = re.sub(r"/\*.*?\*/", "", declaration, flags=re.S)
        if _DISPLAY_NONE.fullmatch(candidate.rstrip("; \t\r\n")):
            changed = True
        else:
            kept.append(declaration)
    if not changed:
        return style
    result = "".join(kept).strip()
    return result if result.strip("; \t\r\n") else ""


def _declarations(style: str) -> list[str]:
    result: list[str] = []
    start = index = depth = 0
    quote = ""
    while index < len(style):
        char = style[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = ""
        elif style.startswith("/*", index):
            end = style.find("*/", index + 2)
            if end < 0:
                break
            index = end + 2
            continue
        elif char in "\"'":
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == ";" and depth == 0:
            result.append(style[start : index + 1])
            start = index + 1
        index += 1
    result.append(style[start:])
    return result
