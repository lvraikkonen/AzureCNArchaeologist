"""Metadata extraction used by the copied production Strategies."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup


class MetadataExtractionError(ValueError):
    """Required page metadata is missing or ambiguous."""


class ContentExtractor:
    def __init__(self, expected_language: str | None = None) -> None:
        if expected_language is not None and expected_language not in {
            "zh-cn",
            "en-us",
        }:
            raise MetadataExtractionError(
                f"处理语言必须是 zh-cn 或 en-us，实际为 {expected_language!r}。"
            )
        self.expected_language = expected_language

    def extract_base_metadata(
        self,
        soup: BeautifulSoup,
        url: str = "",
        html_file_path: str = "",
    ) -> dict[str, Any]:
        return {
            "Title": self.extract_title(soup),
            "MetaTitle": self._meta_content(soup, "title"),
            "MetaDescription": self._meta_content(soup, "description"),
            "MetaKeywords": self._meta_content(soup, "keywords"),
            "MSServiceName": self.extract_ms_service_name(soup),
            "Slug": self.extract_slug(url or self._get_default_url(html_file_path)),
            "Language": self.extract_language(
                soup, expected_language=self.expected_language
            ),
            "LastModified": self.extract_last_modified(soup),
        }

    @staticmethod
    def extract_title(soup: BeautifulSoup) -> str:
        title = soup.find("title")
        value = title.get_text(strip=True) if title is not None else ""
        if not value:
            raise MetadataExtractionError("源页面缺少非空 title。")
        return value

    @staticmethod
    def _meta_content(soup: BeautifulSoup, name: str) -> str:
        element = soup.find("meta", attrs={"name": name})
        return str(element.get("content", "")) if element is not None else ""

    @staticmethod
    def extract_ms_service_name(soup: BeautifulSoup) -> str:
        tags = soup.select_one("div.pure-content tags")
        value = str(tags.get("ms.service", "")) if tags is not None else ""
        if not value:
            raise MetadataExtractionError("源页面缺少 tags.ms.service。")
        return value

    @staticmethod
    def extract_slug(url: str) -> str:
        path = urlparse(url).path
        if "/details/" not in path:
            raise MetadataExtractionError(f"无法从源 URL 确定 Pricing slug：{url}。")
        remainder = path.split("/details/", 1)[1]
        if remainder.endswith("/index.html"):
            remainder = remainder[: -len("/index.html")]
        remainder = remainder.strip("/")
        parts = [part for part in remainder.split("/") if part]
        if not parts:
            raise MetadataExtractionError(f"源 URL 中没有 Pricing slug：{url}。")
        return "_".join(parts)

    @staticmethod
    def extract_language(
        soup: BeautifulSoup,
        expected_language: str | None = None,
    ) -> str:
        if expected_language is not None:
            return expected_language
        body = soup.find("body")
        classes = body.get("class", []) if body is not None else []
        languages = [value for value in classes if value in {"zh-cn", "en-us"}]
        if len(languages) != 1:
            raise MetadataExtractionError(
                "body class 必须明确包含且只包含一个语言：zh-cn 或 en-us。"
            )
        return languages[0]

    @staticmethod
    def extract_last_modified(soup: BeautifulSoup) -> str:
        for selector in (
            'meta[name="last-modified"]',
            'meta[property="article:modified_time"]',
            ".last-updated",
            ".modified-date",
        ):
            element = soup.select_one(selector)
            if element is None:
                continue
            if element.name == "meta":
                return str(element.get("content", ""))
            return element.get_text(strip=True)
        return ""

    @staticmethod
    def extract_main_content(soup: BeautifulSoup) -> str:
        candidates = soup.select("div.technical-azure-selector")
        if len(candidates) != 1:
            return ""
        return str(candidates[0])

    @staticmethod
    def _get_default_url(html_file_path: str) -> str:
        if not html_file_path:
            return ""
        product_key = Path(html_file_path).stem
        return f"https://www.azure.cn/pricing/details/{product_key}/"
