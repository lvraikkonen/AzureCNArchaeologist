#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tab结构检测器

专门负责检测页面中的Tab导航结构和内容区域，区分区域导航
和内容组织导航，提供详细的Tab分析信息。
"""

from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup, Tag

from ..core.data_models import (
    TabAnalysis, Tab, TabNavigation, TabContent
)


class TabDetector:
    """
    Tab结构检测器。
    
    负责识别和分析页面中的Tab结构，包括：
    - Tab导航元素
    - Tab内容区域
    - Tab类型分类（内容组织 vs 区域选择）
    - Tab激活状态和关联关系
    """
    
    def __init__(self):
        """初始化Tab检测器。"""
        # 区域相关关键词（用于过滤区域导航）
        self.region_keywords = [
            '中国', 'china', '北部', 'north', '东部', 'east', 
            '华北', '华东', 'region', '区域'
        ]
        
        # Azure China特定的Tab导航选择器
        self.azure_tab_nav_selectors = [
            '.tab-items',           # Azure custom tab navigation
            'ol.tab-items',         # Ordered list tab items
            '.category-tabs',       # Category tab navigation
            '.os-tab-nav'          # OS tab navigation
        ]
        
        # 标准Tab导航选择器
        self.standard_tab_nav_selectors = [
            '.nav-tabs',
            '.nav-pills', 
            '.tab-nav',
            '.tabs',
            'ul[role="tablist"]',
            '.pricing-tabs',
            '.service-tabs',
            '.product-tabs'
        ]
        
        # 交互式Tab元素选择器
        self.interactive_tab_selectors = [
            'button[role="tab"]',
            'a[role="tab"]',
            '[data-toggle="tab"]',
            '[data-bs-toggle="tab"]'  # Bootstrap 5
        ]
        
        # Tab内容区域选择器
        self.tab_content_selectors = [
            '.tab-content',
            '.tab-panel',
            '.tab-pane',
            '[role="tabpanel"]'
        ]
    
    def detect_tab_structures(self, soup: BeautifulSoup) -> TabAnalysis:
        """
        检测页面中的Tab结构。
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            TabAnalysis对象，包含所有检测到的Tab信息
        """
        tabs = []
        navigations = []
        content_areas = []
        
        # 检测Tab导航
        tab_navigations = self._detect_tab_navigations(soup)
        navigations.extend(tab_navigations)
        
        # 检测Tab内容区域
        tab_contents = self._detect_tab_content_areas(soup)
        content_areas.extend(tab_contents)
        
        # 从导航中提取具体的Tab
        for navigation in navigations:
            nav_tabs = self._extract_tabs_from_navigation(navigation, soup)
            tabs.extend(nav_tabs)
        
        # 建立Tab与内容的关联关系
        self._establish_tab_content_relationships(tabs, content_areas)
        
        # 过滤掉区域导航（只保留内容组织的Tab）
        content_tabs = self._filter_content_tabs(tabs, navigations)
        content_navigations = [nav for nav in navigations 
                             if not self._is_region_navigation(nav, soup)]
        
        # 创建分析结果
        has_tabs = len(content_tabs) > 0
        
        return TabAnalysis(
            has_tabs=has_tabs,
            tabs=content_tabs,
            tab_count=len(content_tabs),
            navigations=content_navigations,
            content_areas=content_areas,
            tab_types=self._classify_tab_types(content_tabs)
        )
    
    def _detect_tab_navigations(self, soup: BeautifulSoup) -> List[TabNavigation]:
        """检测Tab导航结构。"""
        navigations = []
        
        # 检测Azure特定的Tab导航
        azure_navs = self._detect_azure_tab_navigations(soup)
        navigations.extend(azure_navs)
        
        # 检测标准Tab导航
        standard_navs = self._detect_standard_tab_navigations(soup)
        navigations.extend(standard_navs)
        
        # 检测交互式Tab导航
        interactive_navs = self._detect_interactive_tab_navigations(soup)
        navigations.extend(interactive_navs)
        
        # 去重（避免同一个导航被多次检测）
        unique_navigations = self._deduplicate_navigations(navigations)
        
        return unique_navigations
    
    def _detect_azure_tab_navigations(self, soup: BeautifulSoup) -> List[TabNavigation]:
        """检测Azure特定的Tab导航。"""
        navigations = []
        
        for selector in self.azure_tab_nav_selectors:
            nav_elements = soup.select(selector)
            for nav in nav_elements:
                # 跳过隐藏的导航（移动端专用）
                nav_classes = nav.get('class', [])
                if any(cls in nav_classes for cls in ['hidden-md', 'hidden-lg']):
                    continue
                
                # 检查是否有足够的Tab项
                tab_items = nav.select('li, option')
                if len(tab_items) > 1:
                    navigation = TabNavigation(
                        element=nav,
                        navigation_type="azure_custom",
                        selector=selector,
                        tab_items=tab_items,
                        is_active=True
                    )
                    navigations.append(navigation)
        
        return navigations
    
    def _detect_standard_tab_navigations(self, soup: BeautifulSoup) -> List[TabNavigation]:
        """检测标准Tab导航。"""
        navigations = []
        
        for selector in self.standard_tab_nav_selectors:
            nav_elements = soup.select(selector)
            for nav in nav_elements:
                # 查找Tab项
                tab_items = nav.select('li, a, button')
                if len(tab_items) > 1:
                    navigation = TabNavigation(
                        element=nav,
                        navigation_type="standard",
                        selector=selector,
                        tab_items=tab_items,
                        is_active=True
                    )
                    navigations.append(navigation)
        
        return navigations
    
    def _detect_interactive_tab_navigations(self, soup: BeautifulSoup) -> List[TabNavigation]:
        """检测交互式Tab导航。"""
        navigations = []
        
        # 查找所有交互式Tab元素
        interactive_elements = []
        for selector in self.interactive_tab_selectors:
            elements = soup.select(selector)
            interactive_elements.extend(elements)
        
        if len(interactive_elements) > 1:
            # 尝试找到它们的共同父容器
            parent_containers = set()
            for element in interactive_elements:
                parent = element.find_parent()
                if parent:
                    parent_containers.add(parent)
            
            # 如果有共同父容器，创建导航对象
            for container in parent_containers:
                container_interactive_tabs = [elem for elem in interactive_elements 
                                            if elem.find_parent() == container]
                if len(container_interactive_tabs) > 1:
                    navigation = TabNavigation(
                        element=container,
                        navigation_type="interactive",
                        selector="interactive_tabs",
                        tab_items=container_interactive_tabs,
                        is_active=True
                    )
                    navigations.append(navigation)
        
        return navigations
    
    def _detect_tab_content_areas(self, soup: BeautifulSoup) -> List[TabContent]:
        """检测Tab内容区域。"""
        content_areas = []
        
        for selector in self.tab_content_selectors:
            content_elements = soup.select(selector)
            for content in content_elements:
                content_area = TabContent(
                    element=content,
                    content_id=content.get('id', ''),
                    selector=selector,
                    is_active=self._is_active_content(content),
                    associated_tab_id=self._extract_associated_tab_id(content)
                )
                content_areas.append(content_area)
        
        return content_areas
    
    def _extract_tabs_from_navigation(self, navigation: TabNavigation, 
                                    soup: BeautifulSoup) -> List[Tab]:
        """从导航中提取具体的Tab。"""
        tabs = []
        
        for i, item in enumerate(navigation.tab_items):
            # 提取Tab信息
            tab_id = item.get('id', f"tab-{i}")
            tab_text = item.get_text().strip()
            tab_href = item.get('href', '')
            tab_target = self._extract_tab_target(item)
            
            # 检查是否是激活状态
            is_active = self._is_active_tab(item)
            
            tab = Tab(
                tab_id=tab_id,
                tab_text=tab_text,
                tab_href=tab_href,
                target_content_id=tab_target,
                is_active=is_active,
                element=item,
                navigation=navigation
            )
            tabs.append(tab)
        
        return tabs
    
    def _establish_tab_content_relationships(self, tabs: List[Tab], 
                                           content_areas: List[TabContent]) -> None:
        """建立Tab与内容区域的关联关系。"""
        for tab in tabs:
            # 通过ID或其他属性匹配内容区域
            for content in content_areas:
                if self._is_tab_content_match(tab, content):
                    tab.content_area = content
                    content.associated_tab = tab
                    break
    
    def _filter_content_tabs(self, tabs: List[Tab], 
                           navigations: List[TabNavigation]) -> List[Tab]:
        """过滤掉区域导航，只保留内容组织的Tab。"""
        content_tabs = []
        
        for tab in tabs:
            navigation = tab.navigation
            if not self._is_region_navigation(navigation, None):
                content_tabs.append(tab)
        
        return content_tabs
    
    def _is_region_navigation(self, navigation: TabNavigation, 
                            soup: Optional[BeautifulSoup]) -> bool:
        """判断是否是区域导航（而非内容组织导航）。"""
        if not navigation or not navigation.tab_items:
            return False
        
        # 提取所有Tab文本
        tab_texts = [item.get_text().strip().lower() for item in navigation.tab_items]
        
        # 计算包含区域关键词的Tab比例
        region_tab_count = 0
        for text in tab_texts:
            if any(keyword.lower() in text for keyword in self.region_keywords):
                region_tab_count += 1
        
        # 如果80%以上的Tab包含区域关键词，认为是区域导航
        if len(tab_texts) > 0:
            region_ratio = region_tab_count / len(tab_texts)
            return region_ratio >= 0.8
        
        return False
    
    def _classify_tab_types(self, tabs: List[Tab]) -> List[str]:
        """分类Tab类型。"""
        tab_types = set()
        
        for tab in tabs:
            tab_text = tab.tab_text.lower()
            
            # 服务层级类型
            if any(keyword in tab_text for keyword in 
                   ['basic', 'standard', 'premium', 'enterprise', '基本', '标准', '高级', '企业']):
                tab_types.add('service_tier')
            
            # 操作系统类型
            elif any(keyword in tab_text for keyword in 
                     ['windows', 'linux', 'ubuntu', 'centos']):
                tab_types.add('operating_system')
            
            # 定价模型类型
            elif any(keyword in tab_text for keyword in 
                     ['预付费', '按使用付费', 'pay-as-you-go', '包年包月']):
                tab_types.add('pricing_model')
            
            # 服务版本类型
            elif any(keyword in tab_text for keyword in 
                     ['v1', 'v2', 'v3', 'version', '版本']):
                tab_types.add('service_version')
            
            # 通用内容类型
            else:
                tab_types.add('content_organization')
        
        return list(tab_types)
    
    def _deduplicate_navigations(self, navigations: List[TabNavigation]) -> List[TabNavigation]:
        """去重导航列表。"""
        unique_navigations = []
        seen_elements = set()
        
        for nav in navigations:
            element_key = str(nav.element)
            if element_key not in seen_elements:
                seen_elements.add(element_key)
                unique_navigations.append(nav)
        
        return unique_navigations
    
    def _is_active_tab(self, item: Tag) -> bool:
        """检查Tab是否处于激活状态。"""
        # 检查class中的active标记
        classes = item.get('class', [])
        if isinstance(classes, list):
            return 'active' in classes or 'current' in classes
        elif isinstance(classes, str):
            return 'active' in classes or 'current' in classes
        
        # 检查aria-selected属性
        aria_selected = item.get('aria-selected', '').lower()
        if aria_selected == 'true':
            return True
        
        return False
    
    def _is_active_content(self, content: Tag) -> bool:
        """检查内容区域是否处于激活状态。"""
        # 检查class中的active标记
        classes = content.get('class', [])
        if isinstance(classes, list):
            return 'active' in classes or 'show' in classes
        elif isinstance(classes, str):
            return 'active' in classes or 'show' in classes
        
        return False
    
    def _extract_tab_target(self, item: Tag) -> str:
        """提取Tab的目标内容ID。"""
        # 检查href属性
        href = item.get('href', '')
        if href.startswith('#'):
            return href[1:]  # 去掉#号
        
        # 检查data-target属性
        data_target = item.get('data-target', '')
        if data_target.startswith('#'):
            return data_target[1:]
        
        # 检查data-bs-target属性（Bootstrap 5）
        bs_target = item.get('data-bs-target', '')
        if bs_target.startswith('#'):
            return bs_target[1:]
        
        # 检查aria-controls属性
        aria_controls = item.get('aria-controls', '')
        if aria_controls:
            return aria_controls
        
        return ''
    
    def _extract_associated_tab_id(self, content: Tag) -> str:
        """提取内容区域关联的Tab ID。"""
        # 检查aria-labelledby属性
        aria_labelledby = content.get('aria-labelledby', '')
        if aria_labelledby:
            return aria_labelledby
        
        # 检查id属性（通常与Tab的target匹配）
        content_id = content.get('id', '')
        if content_id:
            return content_id
        
        return ''
    
    def _is_tab_content_match(self, tab: Tab, content: TabContent) -> bool:
        """检查Tab和内容区域是否匹配。"""
        # 通过target_content_id匹配
        if tab.target_content_id and content.content_id:
            return tab.target_content_id == content.content_id
        
        # 通过associated_tab_id匹配
        if content.associated_tab_id and tab.tab_id:
            return content.associated_tab_id == tab.tab_id
        
        return False