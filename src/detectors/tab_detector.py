#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tab结构检测器

基于实际HTML结构检测Azure中国区页面的tab结构：
- 主容器：.technical-azure-selector.pricing-detail-tab.tab-dropdown
- Tab内容：正式选择器的直接内容容器 > .tab-panel
- Category tabs：.os-tab-nav.category-tabs
- 数据映射：data-href与内容ID的对应关系
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


class TabDetector:
    """
    Azure中国区页面Tab结构检测器。
    
    基于实际HTML结构精确检测：
    - 主容器：.technical-azure-selector.pricing-detail-tab.tab-dropdown
    - Tab面板：正式定价选择器中的 .tab-panel#tabContentX
    - Category选项：.os-tab-nav.category-tabs 内的选项
    - 映射关系：data-href="#tabContent1-0" → <div id="tabContent1-0">
    """
    
    def __init__(self):
        """初始化Tab检测器。"""
        logger.info("初始化TabDetector - 基于实际HTML结构")
    
    def detect_tabs(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        检测页面中的tab结构（区分分组容器vs真实tab）。
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            {
                "has_main_container": bool,  # technical-azure-selector容器存在
                "has_tabs": bool,            # 有真实的category-tabs交互
                "content_groups": [...],     # 软件筛选器的分组容器
                "category_tabs": [...],      # 所有category-tabs的聚合
                "total_category_tabs": int,  # 真实tab总数
                "has_complex_tabs": bool     # 基于实际category-tabs的复杂度
            }
        """
        logger.info("🔍 开始检测tab结构...")
        
        # 检测主容器
        main_container = self._detect_main_container(soup)
        
        # 检测内容分组容器（tabContentN）
        content_groups = self._detect_tab_panels(soup)
        
        # 检测所有category tabs（真实tab结构）
        category_tabs = self._detect_category_tabs(soup)
        category_title = soup.select_one(
            ".category-container .category-title"
        )
        category_display_name = (
            category_title.get_text(" ", strip=True).rstrip(":：").strip()
            if category_title is not None
            else "Category"
        ) or "Category"
        
        # 统计真实tab数量
        total_category_tabs = len(category_tabs)
        
        # 判断是否有真实tab交互
        has_tabs = total_category_tabs > 0
        
        # 复杂度判断：有category-tabs就算复杂tab
        has_complex_tabs = total_category_tabs > 0
        
        result = {
            "has_main_container": main_container["exists"],
            "has_tabs": has_tabs,
            "content_groups": [{
                "id": group["id"],
                "has_category_tabs": group["has_category_tabs"],
                "category_tabs_count": group["category_tabs_count"]
            } for group in content_groups],
            "category_tabs": category_tabs,
            "category_display_name": category_display_name,
            "category_default_value": next(
                (
                    tab["href"].removeprefix("#")
                    for tab in category_tabs
                    if tab.get("is_default")
                ),
                None,
            ),
            "total_category_tabs": total_category_tabs,
            "has_complex_tabs": has_complex_tabs
        }
        
        logger.info(f"✅ tab检测完成: container={result['has_main_container']}, 分组={len(result['content_groups'])}, 真实tabs={result['total_category_tabs']}")
        return result
    
    def _detect_main_container(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        检测主容器：.technical-azure-selector.pricing-detail-tab.tab-dropdown
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            {
                "exists": bool,
                "element": Tag or None
            }
        """
        logger.info("🔍 检测technical-azure-selector主容器...")
        
        # 查找主容器（可能有不同的class组合）
        container = soup.find('div', class_=lambda x: x and 'technical-azure-selector' in x and 'pricing-detail-tab' in x)
        
        if container:
            logger.info("✅ 找到 technical-azure-selector 主容器")
            return {"exists": True, "element": container}
        else:
            logger.info("⚠ 未找到 technical-azure-selector 主容器")
            return {"exists": False, "element": None}
    
    def _detect_tab_panels(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        检测内容分组容器：tabContentN (软件筛选器的分组容器，非真实tab)
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            [{
                "id": str, 
                "element": Tag,
                "has_category_tabs": bool,
                "category_tabs_count": int
            }]
        """
        logger.info("🔍 检测内容分组容器...")
        
        content_groups = []
        
        tab_panels = self._top_level_tab_panels(soup)
        
        for panel in tab_panels:
            panel_id = panel.get('id', '')
            if panel_id:
                # 检测该分组内是否有真实的category-tabs
                category_tabs = self._detect_category_tabs_in_group(panel)
                
                content_groups.append({
                    "id": panel_id,
                    "element": panel,
                    "has_category_tabs": len(category_tabs) > 0,
                    "category_tabs_count": len(category_tabs)
                })
                logger.info(f"✅ 找到分组容器: {panel_id}, category-tabs: {len(category_tabs)}")
        
        logger.info(f"✅ 检测到 {len(content_groups)} 个内容分组")
        return content_groups

    def _top_level_tab_panels(self, soup: BeautifulSoup) -> List[Tag]:
        """Find software panels in either supported source layout.

        Most pages put ``tabContentN`` below a direct ``.tab-content``.
        Monitor puts the same proven software panel below a direct static
        ``.tab-control-selector``.  The panel identity, rather than the
        wrapper class, is the stable source contract.
        """

        main = self._detect_main_container(soup).get("element")
        if not isinstance(main, Tag):
            return []
        content_wrappers = [
            child
            for child in main.children
            if isinstance(child, Tag)
            and (
                "tab-content" in child.get("class", [])
                or (
                    "technical-azure-selector" in child.get("class", [])
                    and "tab-control-selector" in child.get("class", [])
                )
            )
        ]
        if not content_wrappers:
            return []
        if len(content_wrappers) != 1:
            raise ValueError("正式定价选择器没有唯一的软件内容容器")
        panels = [
            panel
            for panel in content_wrappers[0].find_all(
                "div",
                id=re.compile(r"^tabContent\d+$"),
                recursive=False,
            )
            if "tab-panel" in panel.get("class", [])
        ]
        panel_ids = [str(panel.get("id")) for panel in panels]
        if len(panel_ids) != len(set(panel_ids)):
            raise ValueError("软件内容面板包含重复 ID")
        return panels
    
    def _detect_category_tabs(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        检测所有category tabs（聚合所有分组内的真实tab结构）
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            [{"href": str, "id": str, "label": str, "group_id": str}]
        """
        logger.info("🔍 检测所有category tabs...")
        
        all_category_tabs = []
        
        tab_panels = self._top_level_tab_panels(soup)
        
        for panel in tab_panels:
            panel_id = panel.get('id', '')
            # 检测该分组内的category-tabs
            group_category_tabs = self._detect_category_tabs_in_group(panel)
            
            # 为每个tab添加分组信息
            for tab in group_category_tabs:
                tab["group_id"] = panel_id
                all_category_tabs.append(tab)
                logger.info(f"✅ 找到 category tab: {tab['label']} -> {tab['href']} (分组: {panel_id})")
        
        logger.info(f"✅ 检测到总计 {len(all_category_tabs)} 个category tabs")
        return all_category_tabs
    
    def _detect_category_tabs_in_group(self, group_element: Tag) -> List[Dict[str, Any]]:
        """
        检测特定分组内的category tabs：真实的tab结构
        
        Args:
            group_element: tabContentN 元素
            
        Returns:
            [{"href": str, "id": str, "label": str}]
        """
        category_tabs = []
        
        # 移动端 select 不参与 Category 集合或默认项验证。
        nav_elements = group_element.select(
            "ul.os-tab-nav.category-tabs.hidden-xs.hidden-sm"
        )
        if len(nav_elements) > 1:
            raise ValueError("Software 面板包含多个桌面端 Category 导航。")
        if nav_elements:
            for link in nav_elements[0].select("li a[data-href]"):
                href = str(link.get("data-href", "")).strip()
                link_id = str(link.get("id", "")).strip()
                label = " ".join(link.get_text(" ", strip=True).split())
                if not href.startswith("#") or not href.removeprefix("#") or not label:
                    raise ValueError("Category 桌面端选项缺少目标或名称。")
                target_id = href.removeprefix("#")
                parent = link.find_parent("li")
                category_tabs.append({
                    "href": href,
                    "id": link_id,
                    "label": label,
                    "target_exists": group_element.find(
                        id=target_id
                    ) is not None,
                    "desktop_default": bool(
                        parent is not None
                        and {
                            "active",
                            "selected",
                            "selected-item",
                        }.intersection(parent.get("class", []))
                    ),
                })

        hrefs = [tab["href"] for tab in category_tabs]
        labels = [tab["label"] for tab in category_tabs]
        if len(hrefs) != len(set(hrefs)):
            raise ValueError("Category 桌面端选项包含重复 target。")
        if len(labels) != len(set(labels)):
            raise ValueError("Category 桌面端选项包含重复名称。")

        desktop_defaults = [
            tab["href"]
            for tab in category_tabs
            if tab.pop("desktop_default", False)
        ]
        selected_item = group_element.select_one(
            ".category-container span.selected-item"
        )
        selected_label = (
            " ".join(selected_item.get_text(" ", strip=True).split())
            if selected_item is not None
            else ""
        )
        # A unique desktop state marker outranks a possibly stale summary.
        distinct_defaults = list(dict.fromkeys(desktop_defaults))
        if len(distinct_defaults) == 1:
            default_href = distinct_defaults[0]
        elif not distinct_defaults and len(category_tabs) == 1:
            default_href = category_tabs[0]["href"]
        elif category_tabs:
            summary_matches = [
                tab["href"]
                for tab in category_tabs
                if selected_label and tab["label"] == selected_label
            ]
            if len(summary_matches) != 1:
                raise ValueError("Category 当前项摘要无法唯一对应桌面端选项。")
            default_href = summary_matches[0]
            if distinct_defaults and default_href not in distinct_defaults:
                raise ValueError("Category 桌面端声明了多个无法消歧的默认项。")
        else:
            default_href = None

        if category_tabs and default_href is None:
            raise ValueError("Category 桌面端没有建立唯一默认项。")
        if not category_tabs:
            return []
        default_index = next(
            (
                index
                for index, tab in enumerate(category_tabs)
                if tab["href"] == default_href
            ),
            0,
        )
        category_tabs = (
            [category_tabs[default_index]]
            + category_tabs[:default_index]
            + category_tabs[default_index + 1:]
        )
        for tab in category_tabs:
            tab["is_default"] = tab["href"] == default_href
        return category_tabs
    
    def detect_grouped_tabs(self, soup: BeautifulSoup) -> Dict[str, List[Dict[str, Any]]]:
        """
        按软件组检测独立的category tabs结构
        
        专门为Complex策略设计，解决软件组内独立tab结构的识别问题。
        避免将不同软件组的tabs进行错误的交叉组合。
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            按软件组分类的tabs字典：
            {
                "tabContent1": [{"href": "#tabContent1-1", "id": "xxx", "label": "本地冗余"}, ...],
                "tabContent2": [{"href": "#tabContent2-1", "id": "xxx", "label": "本地冗余数据库"}, ...]
            }
        """
        logger.info("🔍 按软件组检测独立的category tabs结构...")
        
        grouped_tabs = {}
        
        tab_panels = self._top_level_tab_panels(soup)
        
        for panel in tab_panels:
            panel_id = panel.get('id', '')
            if panel_id:
                # 检测该分组内的category-tabs
                group_category_tabs = self._detect_category_tabs_in_group(panel)
                
                if group_category_tabs:
                    grouped_tabs[panel_id] = group_category_tabs
                    logger.info(f"✅ 软件组 {panel_id} 有 {len(group_category_tabs)} 个独立tabs")
                    for tab in group_category_tabs:
                        logger.info(f"   - {tab['label']} -> {tab['href']}")
                else:
                    logger.info(f"ℹ 软件组 {panel_id} 没有category-tabs")
        
        logger.info(f"✅ 按组检测完成，找到 {len(grouped_tabs)} 个软件组，总计 {sum(len(tabs) for tabs in grouped_tabs.values())} 个独立tabs")
        return grouped_tabs
