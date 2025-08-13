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

from ..core.data_models import (
    TabAnalysis, Tab, TabNavigation, TabContent
)
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
        检测页面中的tab结构（基于实际HTML结构）。
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            tab分析结果字典
        """
        logger.info("🔍 开始检测tab结构...")
        
        # 检测主容器
        main_container = self._detect_main_container(soup)
        
        # 检测tab面板
        tab_panels = self._detect_tab_panels(soup)
        
        # 检测category tabs
        category_tabs = self._detect_category_tabs(soup)
        
        result = {
            "has_main_container": main_container["exists"],
            "has_tabs": len(tab_panels) > 0,
            "tab_panels": [panel["id"] for panel in tab_panels],
            "category_tabs": category_tabs,
            "has_complex_tabs": len(category_tabs) > 0
        }
        
        logger.info(f"✅ tab检测完成: container={result['has_main_container']}, panels={len(result['tab_panels'])}, categories={len(result['category_tabs'])}")
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
        检测tab面板：.tab-content > .tab-panel
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            [{"id": str, "element": Tag}]
        """
        logger.info("🔍 检测tab面板...")
        
        panels = []
        
        # 查找 .tab-content 容器
        tab_content = soup.find('div', class_='tab-content')
        if not tab_content:
            logger.info("⚠ 未找到 .tab-content 容器")
            return panels
        
        # 查找其中的 .tab-panel
        tab_panels = tab_content.find_all('div', class_='tab-panel')
        
        for panel in tab_panels:
            panel_id = panel.get('id', '')
            if panel_id:
                panels.append({
                    "id": panel_id,
                    "element": panel
                })
                logger.info(f"✅ 找到 tab-panel: {panel_id}")
        
        logger.info(f"✅ 检测到 {len(panels)} 个tab面板")
        return panels
    
    def _detect_category_tabs(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        检测category tabs：.os-tab-nav.category-tabs
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            [{"href": str, "id": str, "label": str}]
        """
        logger.info("🔍 检测category tabs...")
        
        category_tabs = []
        
        # 查找 .os-tab-nav.category-tabs（可能还有其他class）
        nav_elements = soup.find_all('ul', class_=lambda x: x and 'os-tab-nav' in x and 'category-tabs' in x)
        
        for nav in nav_elements:
            # 检查是否隐藏在小屏幕
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
                        logger.info(f"✅ 找到 category tab: {label} -> {href}")
        
        logger.info(f"✅ 检测到 {len(category_tabs)} 个category tabs")
        return category_tabs
    
    # 保留兼容性方法（不再使用）
    def detect_tab_structures(self, soup: BeautifulSoup) -> TabAnalysis:
        """
        兼容性方法 - 不再使用，请使用 detect_tabs()
        """
        logger.warning("⚠ detect_tab_structures() 已废弃，请使用 detect_tabs()")
        return TabAnalysis(has_tabs=False)