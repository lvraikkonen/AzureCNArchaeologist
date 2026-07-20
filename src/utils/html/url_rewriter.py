"""Rewrite URLs embedded in extracted HTML fragments to the CMS base-url convention."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


SKIPPED_PREFIXES = ("#", "mailto:", "tel:", "data:", "javascript:", "{base_url}")
STYLE_URL_PATTERN = re.compile(r"url\(\s*([\"']?)(.*?)\1\s*\)", re.IGNORECASE)


def split_srcset(value: str) -> list[str]:
    """Split candidates without treating the first data-URI comma as a separator."""
    candidates: list[str] = []
    current: list[str] = []
    data_uri_header_open = False
    candidate_start = True
    for index, character in enumerate(value):
        if candidate_start and character.isspace():
            continue
        if candidate_start:
            data_uri_header_open = value[index:].lower().startswith("data:")
            candidate_start = False
        if character == ",":
            if data_uri_header_open:
                current.append(character)
                data_uri_header_open = False
                continue
            candidate = "".join(current).strip()
            if candidate:
                candidates.append(candidate)
            current = []
            data_uri_header_open = False
            candidate_start = True
            continue
        current.append(character)
    candidate = "".join(current).strip()
    if candidate:
        candidates.append(candidate)
    return candidates


def rewrite_url(value: str, source_url: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if not normalized or normalized.lower().startswith(SKIPPED_PREFIXES):
        return normalized
    resolved = urljoin(source_url, normalized)
    parsed = urlparse(resolved)
    host = parsed.hostname or ""
    if host == "azure.cn" or host.endswith(".azure.cn"):
        suffix = parsed.path or "/"
        if parsed.query:
            suffix += f"?{parsed.query}"
        if parsed.fragment:
            suffix += f"#{parsed.fragment}"
        return "{base_url}" + (suffix if suffix.startswith("/") else f"/{suffix}")
    return normalized if not parsed.scheme else resolved


def rewrite_fragment_urls(fragment: BeautifulSoup | Tag, source_url: str) -> None:
    for tag in fragment.find_all(True):
        for attribute in ("href", "src"):
            if tag.has_attr(attribute):
                tag[attribute] = rewrite_url(str(tag[attribute]), source_url)
        if tag.has_attr("srcset"):
            rewritten = []
            for candidate in split_srcset(str(tag["srcset"])):
                parts = candidate.strip().split()
                if parts:
                    parts[0] = rewrite_url(parts[0], source_url)
                rewritten.append(" ".join(parts))
            tag["srcset"] = ", ".join(rewritten)
        if tag.has_attr("style"):
            tag["style"] = STYLE_URL_PATTERN.sub(
                lambda match: f"url({match.group(1)}{rewrite_url(match.group(2), source_url)}{match.group(1)})",
                str(tag["style"]),
            )
