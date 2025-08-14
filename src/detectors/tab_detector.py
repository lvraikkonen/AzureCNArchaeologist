#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tab结构检测器

基于实际HTML结构检测Azure中国区页面的tab结构：
- 主容器：.technical-azure-selector.pricing-detail-tab.tab-dropdown
- Tab内容：.tab-content > .tab-panel
- Category tabs：.os-tab-nav.category-tabs
- 数据映射：data-href与内容ID的对应关系
"""

from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup, Tag

from ..core.logging import get_logger

logger = get_logger(__name__)


class TabDetector:
    """
    Azure中国区页面Tab结构检测器。
    
    基于实际HTML结构精确检测：
    - 主容器：.technical-azure-selector.pricing-detail-tab.tab-dropdown
    - Tab面板：.tab-content > .tab-panel#tabContentX
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
        
        # 查找 .tab-content 容器
        tab_content = soup.find('div', class_='tab-content')
        if not tab_content:
            logger.info("⚠ 未找到 .tab-content 容器")
            return content_groups
        
        # 查找其中的主要分组容器 .tab-panel#tabContentN
        import re
        tab_panels = tab_content.find_all('div', {
            'class': 'tab-panel',
            'id': re.compile(r'^tabContent\d+$')  # 只匹配主要分组，不包含子级
        })
        
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
        
        # 查找 .tab-content 容器
        tab_content = soup.find('div', class_='tab-content')
        if not tab_content:
            logger.info("⚠ 未找到 .tab-content 容器")
            return all_category_tabs
        
        # 查找所有tabContentN分组
        import re
        tab_panels = tab_content.find_all('div', {
            'class': 'tab-panel',
            'id': re.compile(r'^tabContent\d+$')
        })
        
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
        
        # 在该分组内查找 .os-tab-nav.category-tabs
        nav_elements = group_element.find_all('ul', class_=lambda x: x and 'os-tab-nav' in x and 'category-tabs' in x)
        
        for nav in nav_elements:
            # 检查是否隐藏在小屏幕（只统计桌面版本的tab）
            nav_classes = nav.get('class', [])
            if 'hidden-xs' in nav_classes and 'hidden-sm' in nav_classes:
                # 这是桌面版本，查找其中的选项
                links = nav.find_all('a')
                for link in links:
                    href = link.get('data-href', '')
                    link_id = link.get('id', '')
                    label = link.get_text().strip()
                    
                    if href and label:
                        category_tabs.append({
                            "href": href,
                            "id": link_id,
                            "label": label
                        })
        
        return category_tabs