"""SupportArticlePage extraction for SLA, legal, ICP and PSR snapshots."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from src.core.logging import get_logger
from src.strategies.base_strategy import BaseStrategy
from src.utils.html.url_rewriter import rewrite_fragment_urls


logger = get_logger(__name__)


class SupportArticleStrategy(BaseStrategy):
    SUPPORT_TYPES = ("SLA", "LEGAL", "ICP", "PSR")
    UI_SELECTORS = (
        "#content_feedback", ".content-feedback", ".select", ".left-navigation-select",
        ".bookmark", ".loader", ".tags", "select", "script", "style", "tags",
    )

    def __init__(self, product_config: dict[str, Any], html_file_path: str = "") -> None:
        super().__init__(product_config, html_file_path)
        self.support_article_type = product_config.get("support_article_type", "")
        self.url_route_map = product_config.get("extraction", {}).get("url_route_map", {})
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
        h1 = content.find("h1")
        if not h1:
            return ""
        wrapper = BeautifulSoup("<div></div>", "html.parser").div
        for element in h1.next_elements:
            if isinstance(element, Tag) and element.name == "h2":
                break
            if isinstance(element, Tag) and element.name == "p":
                clone = BeautifulSoup(str(element), "html.parser").find("p")
                if clone:
                    wrapper.append(clone)
        self._clean_fragment(wrapper, source_url)
        return wrapper.decode_contents()

    def _extract_main_content(self, content: Tag, source_url: str) -> str:
        first_h2 = content.find("h2")
        if not first_h2:
            return ""
        wrapper = BeautifulSoup("<div></div>", "html.parser").div
        current = first_h2
        while current is not None:
            if isinstance(current, Tag):
                clone = BeautifulSoup(str(current), "html.parser").find()
                if clone:
                    wrapper.append(clone)
            current = current.next_sibling
        self._clean_fragment(wrapper, source_url)
        if not wrapper.get_text(" ", strip=True) and not wrapper.select("img, video, audio, table, iframe"):
            return ""
        return wrapper.decode_contents().strip()

    def _clean_fragment(self, fragment: Tag, source_url: str) -> None:
        for selector in self.UI_SELECTORS:
            for element in fragment.select(selector):
                element.decompose()
        rewrite_fragment_urls(fragment, source_url, self.url_route_map)
