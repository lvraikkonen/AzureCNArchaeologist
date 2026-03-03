#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
支持文章策略 - 用于 SLA、ICP备案、法律和公安备案页面的提取策略

输出 SupportArticlePage 格式的扁平 JSON，包含：
title, slug, metaTitle, metaDescription, metaKeywords,
pageType, lastModifiedDate, articleDescription, mainContent
"""

import re
import sys
from pathlib import Path
from typing import Dict, Any, List
from bs4 import BeautifulSoup, Tag

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.strategies.base_strategy import BaseStrategy
from src.core.logging import get_logger

logger = get_logger(__name__)


class SupportArticleStrategy(BaseStrategy):
    """支持文章页面提取策略 (SLA/ICP/Legal/公安备案)"""

    SUPPORT_CATEGORIES = ("sla", "icp", "legal", "public-security-registration")

    def __init__(self, product_config: Dict[str, Any], html_file_path: str = ""):
        super().__init__(product_config, html_file_path)
        self.category = product_config.get("category", "")
        logger.info(f"初始化 SupportArticleStrategy, category={self.category}")

    def extract_flexible_content(self, soup: BeautifulSoup, url: str = "") -> Dict[str, Any]:
        """提取支持文章页面内容，返回扁平 JSON 格式"""
        logger.info("开始提取 SupportArticlePage 内容")

        content_div = self._find_content_div(soup)

        title = self._extract_title(content_div, soup)
        slug = self._extract_slug()
        meta_title = self._extract_meta_title(soup)
        meta_description = self._extract_meta_description(soup)
        meta_keywords = self._extract_meta_keywords(soup)
        page_type = self.category
        last_modified = self._extract_last_modified(content_div)
        article_desc = self._extract_article_description(content_div)
        main_content = self._extract_main_content(content_div)

        result = {
            "title": title,
            "slug": slug,
            "metaTitle": meta_title,
            "metaDescription": meta_description,
            "metaKeywords": meta_keywords,
            "pageType": page_type,
            "lastModifiedDate": last_modified,
            "articleDescription": article_desc,
            "mainContent": main_content,
        }

        logger.info(f"SupportArticlePage 提取完成: title={title}, pageType={page_type}")
        return result

    def extract_common_sections(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """支持文章页面不使用 commonSections，返回空列表"""
        return []

    # --- 内容定位 ---

    def _find_content_div(self, soup: BeautifulSoup) -> Tag:
        """定位主内容区域 div.col-md-8.pure-content"""
        content_div = soup.find("div", class_="pure-content")
        if not content_div:
            logger.warning("未找到 pure-content div，使用整个 body")
            content_div = soup.find("body") or soup
        return content_div

    # --- 元数据提取 ---

    def _extract_title(self, content_div: Tag, soup: BeautifulSoup) -> str:
        """从 h1 标签提取标题"""
        h1 = content_div.find("h1")
        if h1:
            return h1.get_text(strip=True)
        title_tag = soup.find("title")
        if title_tag:
            # 去掉 " | Azure" 后缀
            text = title_tag.get_text(strip=True)
            return re.sub(r"\s*\|\s*Azure\s*$", "", text)
        return ""

    def _extract_slug(self) -> str:
        """从产品配置获取 slug"""
        return self.product_config.get("slug", "")

    def _extract_meta_title(self, soup: BeautifulSoup) -> str:
        tag = soup.find("title")
        return tag.get_text(strip=True) if tag else ""

    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            return meta.get("content", "").strip()
        return ""

    def _extract_meta_keywords(self, soup: BeautifulSoup) -> str:
        meta = soup.find("meta", attrs={"name": "keywords"})
        if meta:
            return meta.get("content", "").strip()
        return ""

    def _extract_last_modified(self, content_div: Tag) -> str:
        """
        从 div.tags-date 提取最后修改日期。
        格式如 "最后更新时间：2025年07月" → "2025年07月"
        """
        tags_date = content_div.find("div", class_="tags-date")
        if tags_date:
            wacn_date = tags_date.find("div", class_="wacn-date")
            if wacn_date:
                text = wacn_date.get_text(strip=True)
                # 去掉 "最后更新时间：" 前缀
                text = re.sub(r"^最后更新时间[：:]?\s*", "", text)
                return text
        return ""

    # --- 内容提取 ---

    def _extract_article_description(self, content_div: Tag) -> str:
        """
        提取 articleDescription：h1 之后、第一个 h2 之前的 <p> 元素。
        排除包含 <tags> 的 <p> 和 tags-date div。
        """
        h1 = content_div.find("h1")
        if not h1:
            return ""

        desc_parts = []
        for sibling in h1.next_siblings:
            if isinstance(sibling, Tag):
                # 跳过 tags-date div
                if sibling.name == "div" and "tags-date" in sibling.get("class", []):
                    continue
                # 遇到 h2 则停止
                if sibling.name == "h2":
                    break
                # 收集 p 元素（排除包含 tags 的）
                if sibling.name == "p" and not sibling.find("tags"):
                    desc_parts.append(str(sibling))

        return "".join(desc_parts)

    def _extract_main_content(self, content_div: Tag) -> str:
        """
        提取 mainContent：从第一个 <h2> 开始到内容结束。
        排除页面 UI 元素（select/loader/feedback 等）。
        """
        first_h2 = content_div.find("h2")
        if not first_h2:
            return ""

        content_parts = []
        current = first_h2
        while current:
            if isinstance(current, Tag):
                # 排除非内容元素
                if self._is_ui_element(current):
                    current = current.next_sibling
                    continue
                content_parts.append(str(current))
            current = current.next_sibling

        return "".join(content_parts)

    def _is_ui_element(self, tag: Tag) -> bool:
        """判断是否为页面 UI 元素（非内容）"""
        classes = tag.get("class", [])
        if tag.get("id") == "content_feedback":
            return True
        ui_classes = {"select", "left-navigation-select", "bookmark", "loader"}
        if ui_classes.intersection(classes):
            return True
        return False
