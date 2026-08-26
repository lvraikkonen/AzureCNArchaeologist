"""SupportArticlePage extraction for SLA, legal, ICP and PSR snapshots."""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from typing import Any

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from src.strategies.base_strategy import BaseStrategy
from src.utils.html.normalization import normalize_html


logger = logging.getLogger(__name__)


class SupportArticleStrategy(BaseStrategy):
    SUPPORT_TYPES = ("SLA", "LEGAL", "ICP", "PSR")
    UI_SELECTORS = (
        "#content_feedback", ".content-feedback", ".select", ".left-navigation-select",
        ".bookmark", ".loader", ".tags", "select", "script", "style", "tags",
    )
    METADATA_SELECTORS = (".tags-date", ".wacn-date", ".ms-date")

    def __init__(self, product_config: dict[str, Any], html_file_path: str = "") -> None:
        super().__init__(product_config, html_file_path)
        self.support_article_type = product_config.get("support_article_type", "")
        if self.support_article_type not in self.SUPPORT_TYPES:
            raise ValueError(f"Invalid support_article_type: {self.support_article_type!r}")

    def extract_flexible_content(self, soup: BeautifulSoup, url: str = "") -> dict[str, Any]:
        content = self._find_content(soup)
        payload = {
            "title": self._extract_title(content, soup),
            "slug": self.product_config.get("slug", ""),
            "metaTitle": self._meta(soup, "title"),
            "metaDescription": self._meta(soup, "description"),
            "metaKeywords": self._meta(soup, "keywords"),
            "pageType": self.support_article_type,
            "lastModifiedDate": self._extract_last_modified(content),
            "articleDescription": self._extract_article_description(content, url),
            "mainContent": self._extract_main_content(content, url),
        }
        logger.info(f"SupportArticlePage extracted: {payload['title']} ({payload['pageType']})")
        return payload

    def extract_common_sections(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        return []

    @staticmethod
    def _find_content(soup: BeautifulSoup) -> Tag:
        return soup.select_one("div.pure-content") or soup.body or soup

    @staticmethod
    def _extract_title(content: Tag, soup: BeautifulSoup) -> str:
        h1 = content.find("h1")
        if h1:
            return h1.get_text(" ", strip=True)
        title = soup.find("title")
        return re.sub(r"\s*\|\s*Azure\s*$", "", title.get_text(" ", strip=True)) if title else ""

    @staticmethod
    def _meta(soup: BeautifulSoup, name: str) -> str:
        if name == "title":
            tag = soup.find("title")
            return tag.get_text(" ", strip=True) if tag else ""
        tag = soup.find("meta", attrs={"name": re.compile(f"^{re.escape(name)}$", re.I)})
        return str(tag.get("content", "")).strip() if tag else ""

    @staticmethod
    def _extract_last_modified(content: Tag) -> str:
        date = content.select_one(".wacn-date, .ms-date")
        if not date:
            return ""
        text = date.get_text(" ", strip=True)
        return re.sub(
            r"^(?:最后更新(?:时间|日期)|更新时间|Last\s+updated|Updated)\s*[：:]?\s*",
            "",
            text,
            flags=re.I,
        ).strip()

    def _extract_article_description(self, content: Tag, source_url: str) -> str:
        description_nodes, _main_nodes = self._article_nodes(content)
        wrapper = BeautifulSoup("<div></div>", "html.parser").div
        self._append_nodes(wrapper, description_nodes)
        self._clean_fragment(wrapper, source_url)
        return normalize_html(wrapper.decode_contents())

    def _extract_main_content(self, content: Tag, source_url: str) -> str:
        _description_nodes, main_nodes = self._article_nodes(content)
        wrapper = BeautifulSoup("<div></div>", "html.parser").div
        self._append_nodes(wrapper, main_nodes)
        self._clean_fragment(wrapper, source_url)
        if not wrapper.get_text(" ", strip=True) and not wrapper.select("img, video, audio, table, iframe"):
            return ""
        return normalize_html(wrapper.decode_contents())

    @staticmethod
    def _article_nodes(
        content: Tag,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
        """Resolve one direct, singly wrapped, or headingless article body."""

        h1s = content.find_all("h1")
        if len(h1s) != 1 or h1s[0].parent is not content:
            return (), ()

        direct_nodes = list(content.children)
        h1 = h1s[0]
        h1_index = direct_nodes.index(h1)

        h2s = content.find_all("h2")
        if h2s:
            first_h2 = h2s[0]
            headings = content.find_all(["h1", "h2"])
            if not headings or headings[0] is not h1:
                return (), ()

            body = first_h2.parent
            if not isinstance(body, Tag):
                return (), ()
            if body is not content and content not in body.parents:
                return (), ()
            if any(heading is not first_h2 and body not in heading.parents for heading in h2s):
                return (), ()

            body_nodes = list(body.children)
            first_h2_index = body_nodes.index(first_h2)
            if body is content:
                description_start = h1_index + 1
            else:
                description_start = 0
            return (
                tuple(body_nodes[description_start:first_h2_index]),
                tuple(body_nodes[first_h2_index:]),
            )

        # A short support article without section headings has no separate
        # description. Everything after its title is the required main body.
        return (), tuple(direct_nodes[h1_index + 1 :])

    @staticmethod
    def _append_nodes(wrapper: Tag, nodes: tuple[Any, ...]) -> None:
        for node in nodes:
            if isinstance(node, Comment):
                continue
            if isinstance(node, Tag):
                if node.get("id") == "content_feedback" or "content-feedback" in node.get(
                    "class", []
                ):
                    break
                wrapper.append(deepcopy(node))
            elif isinstance(node, NavigableString) and str(node).strip():
                wrapper.append(NavigableString(str(node)))

    def _clean_fragment(self, fragment: Tag, source_url: str) -> None:
        for selector in (*self.UI_SELECTORS, *self.METADATA_SELECTORS):
            for element in fragment.select(selector):
                element.decompose()
        del source_url
