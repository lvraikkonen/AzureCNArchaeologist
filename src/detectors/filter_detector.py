#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
筛选器检测器

专门负责检测页面中的各种筛选器类型和配置，包括区域筛选器、
操作系统筛选器、服务层级筛选器等。
"""

from typing import List, Dict, Any, Optional, Set
from bs4 import BeautifulSoup, Tag

from ..core.data_models import (
    FilterAnalysis, FilterType, Filter, RegionFilter
)


class FilterDetector:
    """
    筛选器检测器。
    
    负责识别和分析页面中的各种筛选器元素，包括：
    - 区域筛选器
    - 操作系统/软件筛选器  
    - 服务层级筛选器
    - 存储类型筛选器
    """
    
    def __init__(self):
        """初始化筛选器检测器。"""
        self.region_keywords = [
            '选择区域', '区域选择', '中国北部', '中国东部', 'china north', 'china east',
            'region selector', '华北', '华东', '北部', '东部'
        ]
        
        self.os_keywords = [
            'windows', 'linux', 'ubuntu', 'centos', 'redhat', 'suse',
            '操作系统', '软件', 'os', 'software'
        ]
        
        self.tier_keywords = [
            'basic', 'standard', 'premium', 'enterprise', 
            '基本', '标准', '高级', '企业', '层级', 'tier'
        ]
    
    def detect_filters(self, soup: BeautifulSoup) -> FilterAnalysis:
        """
        检测页面中的所有筛选器。
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            FilterAnalysis对象，包含所有检测到的筛选器信息
        """
        filters = []
        primary_filter_type = None
        
        # 检测区域筛选器
        region_filters = self.detect_region_filters(soup)
        if region_filters:
            filters.extend(region_filters)
            primary_filter_type = FilterType.REGION
        
        # 检测其他筛选器
        other_filters = self.detect_other_filters(soup)
        if other_filters:
            filters.extend(other_filters)
            # 如果没有区域筛选器，以第一个其他筛选器为主
            if not primary_filter_type and other_filters:
                primary_filter_type = other_filters[0].filter_type
        
        # 创建分析结果
        return FilterAnalysis(
            has_filters=len(filters) > 0,
            filters=filters,
            primary_filter_type=primary_filter_type or FilterType.NONE,
            filter_count=len(filters)
        )
    
    def detect_region_filters(self, soup: BeautifulSoup) -> List[RegionFilter]:
        """
        检测区域筛选器。
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            检测到的区域筛选器列表
        """
        region_filters = []
        
        # 常见的区域筛选器选择器
        region_selectors = [
            # Dropdown选择器
            'select[name*="region"]',
            'select[id*="region"]',
            'select[class*="region"]',
            
            # 自定义区域选择器
            '.region-selector',
            '.region-dropdown',
            '#region-select',
            '[data-region]',
            
            # Azure特定模式
            '.pricing-dropdown',
            '.region-pricing-dropdown',
            'button[data-toggle*="region"]',
            
            # 包含区域容器的select
            '.region-container select',
            '.software-kind select'  # Azure China特有
        ]
        
        found_selectors = set()  # 去重
        
        for selector in region_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    # 避免重复检测同一个元素
                    element_key = self._get_element_key(element)
                    if element_key in found_selectors:
                        continue
                    found_selectors.add(element_key)
                    
                    # 验证是否是功能性的区域筛选器
                    if self._is_functional_region_filter(element, soup):
                        region_filter = self._create_region_filter(element, soup)
                        if region_filter:
                            region_filters.append(region_filter)
                            
            except Exception:
                # 无效选择器，继续下一个
                continue
        
        # 如果没有找到具体的筛选器元素，但页面包含区域关键词，创建一个基础区域筛选器
        if not region_filters and self._has_region_keywords(soup):
            region_filters.append(RegionFilter(
                filter_type=FilterType.REGION,
                element_id="text-based-region",
                element_type="text",
                selector="text-based",
                options=['china-north', 'china-east'],  # 默认区域
                is_active=True,
                default_value=None
            ))
        
        return region_filters
    
    def detect_other_filters(self, soup: BeautifulSoup) -> List[Filter]:
        """
        检测非区域的其他筛选器。
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            检测到的其他筛选器列表
        """
        other_filters = []
        
        # 操作系统/软件筛选器
        os_filters = self._detect_os_filters(soup)
        other_filters.extend(os_filters)
        
        # 服务层级筛选器
        tier_filters = self._detect_tier_filters(soup)
        other_filters.extend(tier_filters)
        
        # 存储类型筛选器
        storage_filters = self._detect_storage_filters(soup)
        other_filters.extend(storage_filters)
        
        # 通用筛选器（作为补充）
        generic_filters = self._detect_generic_filters(soup)
        other_filters.extend(generic_filters)
        
        return other_filters
    
    def _detect_os_filters(self, soup: BeautifulSoup) -> List[Filter]:
        """检测操作系统/软件类型筛选器。"""
        os_filters = []
        
        # 操作系统筛选器选择器
        os_selectors = [
            'select[name*="os"]:not([name*="region"])',
            'select[id*="software"]',
            'select.software-box',
            'select[name*="software"]:not([name*="region"])',
            'input[type="radio"][name*="os"]',
            'input[type="radio"][name*="software"]'
        ]
        
        found_elements = set()
        
        for selector in os_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    element_key = self._get_element_key(element)
                    if element_key in found_elements:
                        continue
                    found_elements.add(element_key)
                    
                    if self._is_functional_filter(element):
                        filter_obj = self._create_generic_filter(
                            element, FilterType.OS, soup
                        )
                        if filter_obj:
                            os_filters.append(filter_obj)
                            
            except Exception:
                continue
        
        return os_filters
    
    def _detect_tier_filters(self, soup: BeautifulSoup) -> List[Filter]:
        """检测服务层级筛选器。"""
        tier_filters = []
        
        tier_selectors = [
            'select[name*="tier"]:not([name*="region"])',
            'select[id*="tier"]',
            'select[name*="plan"]:not([name*="region"])',
            'select[id*="plan"]',
            'input[type="radio"][name*="tier"]',
            'input[type="radio"][name*="plan"]'
        ]
        
        found_elements = set()
        
        for selector in tier_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    element_key = self._get_element_key(element)
                    if element_key in found_elements:
                        continue
                    found_elements.add(element_key)
                    
                    if self._is_functional_filter(element):
                        filter_obj = self._create_generic_filter(
                            element, FilterType.TIER, soup
                        )
                        if filter_obj:
                            tier_filters.append(filter_obj)
                            
            except Exception:
                continue
        
        return tier_filters
    
    def _detect_storage_filters(self, soup: BeautifulSoup) -> List[Filter]:
        """检测存储类型筛选器。"""
        storage_filters = []
        
        storage_selectors = [
            'select[name*="storage"]:not([name*="region"])',
            'select[id*="storage"]',
            'select[name*="type"]:not([name*="region"])',
            'input[type="radio"][name*="storage"]',
            'input[type="radio"][name*="type"]'
        ]
        
        found_elements = set()
        
        for selector in storage_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    element_key = self._get_element_key(element)
                    if element_key in found_elements:
                        continue
                    found_elements.add(element_key)
                    
                    if self._is_functional_filter(element):
                        filter_obj = self._create_generic_filter(
                            element, FilterType.STORAGE, soup
                        )
                        if filter_obj:
                            storage_filters.append(filter_obj)
                            
            except Exception:
                continue
        
        return storage_filters
    
    def _detect_generic_filters(self, soup: BeautifulSoup) -> List[Filter]:
        """检测通用筛选器。"""
        generic_filters = []
        
        # 通用筛选器选择器（排除已检测的类型）
        generic_selectors = [
            '.filter-dropdown select:not([name*="region"]):not([name*="os"]):not([name*="tier"])',
            '.pricing-filter select:not([name*="region"]):not([name*="os"]):not([name*="tier"])',
            '.service-filter select:not([name*="region"]):not([name*="os"]):not([name*="tier"])',
            '.filter-group select:not([name*="region"]):not([name*="os"]):not([name*="tier"])'
        ]
        
        found_elements = set()
        
        for selector in generic_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    element_key = self._get_element_key(element)
                    if element_key in found_elements:
                        continue
                    found_elements.add(element_key)
                    
                    if self._is_functional_filter(element):
                        filter_obj = self._create_generic_filter(
                            element, FilterType.OTHER, soup
                        )
                        if filter_obj:
                            generic_filters.append(filter_obj)
                            
            except Exception:
                continue
        
        return generic_filters
    
    def _is_functional_region_filter(self, element: Tag, soup: BeautifulSoup) -> bool:
        """检查是否是功能性的区域筛选器。"""
        # 基本功能性检查
        if not self._is_functional_filter(element):
            return False
        
        # 区域特定检查
        element_text = element.get_text().lower()
        element_attrs = str(element).lower()
        
        # 检查是否包含区域相关内容
        has_region_content = (
            any(keyword in element_text for keyword in self.region_keywords) or
            any(keyword in element_attrs for keyword in ['region', 'china', '区域'])
        )
        
        return has_region_content
    
    def _is_functional_filter(self, element: Tag) -> bool:
        """检查元素是否是功能性筛选器。"""
        if element.name == 'select':
            # 检查选项数量
            options = element.find_all('option')
            if len(options) <= 1:
                return False
            
            # 检查是否有实际选项（排除加载状态）
            option_texts = [opt.get_text().strip() for opt in options]
            non_empty_options = [text for text in option_texts 
                               if text and '加载中' not in text and '请选择' not in text]
            
            return len(non_empty_options) > 1
            
        elif element.name == 'input' and element.get('type') == 'radio':
            # Radio按钮组检查
            name = element.get('name')
            if name:
                # 查找同组的其他radio按钮
                same_group = element.find_parent().find_all('input', {'name': name, 'type': 'radio'})
                return len(same_group) > 1
        
        return False
    
    def _create_region_filter(self, element: Tag, soup: BeautifulSoup) -> Optional[RegionFilter]:
        """创建区域筛选器对象。"""
        try:
            element_id = element.get('id', '')
            element_type = element.name
            selector = self._generate_selector(element)
            
            # 提取选项
            options = []
            if element.name == 'select':
                option_elements = element.find_all('option')
                for option in option_elements:
                    value = option.get('value', '').strip()
                    text = option.get_text().strip()
                    if value and value not in ['', '请选择', '加载中...']:
                        options.append(value)
                    elif text and text not in ['请选择', '加载中...']:
                        options.append(text)
            
            # 如果没有明确选项，使用默认区域
            if not options:
                options = ['china-north', 'china-east']
            
            return RegionFilter(
                filter_type=FilterType.REGION,
                element_id=element_id or f"region-filter-{hash(str(element))}"[:8],
                element_type=element_type,
                selector=selector,
                options=options,
                is_active=True,
                default_value=options[0] if options else None
            )
            
        except Exception:
            return None
    
    def _create_generic_filter(self, element: Tag, filter_type: FilterType, 
                             soup: BeautifulSoup) -> Optional[Filter]:
        """创建通用筛选器对象。"""
        try:
            element_id = element.get('id', '')
            element_type = element.name
            selector = self._generate_selector(element)
            
            # 提取选项
            options = []
            if element.name == 'select':
                option_elements = element.find_all('option')
                for option in option_elements:
                    value = option.get('value', '').strip()
                    text = option.get_text().strip()
                    if value and value not in ['', '请选择', '加载中...']:
                        options.append(value)
                    elif text and text not in ['请选择', '加载中...']:
                        options.append(text)
            elif element.name == 'input' and element.get('type') == 'radio':
                # Radio按钮组
                name = element.get('name')
                if name:
                    radio_group = soup.find_all('input', {'name': name, 'type': 'radio'})
                    for radio in radio_group:
                        value = radio.get('value', '').strip()
                        if value:
                            options.append(value)
            
            return Filter(
                filter_type=filter_type,
                element_id=element_id or f"{filter_type.value}-filter-{hash(str(element))}"[:8],
                element_type=element_type,
                selector=selector,
                options=options,
                is_active=True,
                default_value=options[0] if options else None
            )
            
        except Exception:
            return None
    
    def _get_element_key(self, element: Tag) -> str:
        """获取元素的唯一标识符。"""
        # 使用元素的位置和属性创建唯一key
        attrs = {}
        for attr in ['id', 'name', 'class']:
            value = element.get(attr)
            if value:
                attrs[attr] = str(value)
        
        return f"{element.name}:{hash(str(element))}:{str(attrs)}"
    
    def _generate_selector(self, element: Tag) -> str:
        """为元素生成CSS选择器。"""
        selectors = []
        
        # ID选择器优先
        if element.get('id'):
            return f"#{element.get('id')}"
        
        # 标签名
        selectors.append(element.name)
        
        # Class选择器
        if element.get('class'):
            classes = element.get('class')
            if isinstance(classes, list):
                for cls in classes:
                    selectors.append(f".{cls}")
            else:
                selectors.append(f".{classes}")
        
        # Name属性
        if element.get('name'):
            return f"{element.name}[name='{element.get('name')}']"
        
        return ''.join(selectors) if selectors else element.name
    
    def _has_region_keywords(self, soup: BeautifulSoup) -> bool:
        """检查页面是否包含区域关键词。"""
        page_text = soup.get_text().lower()
        return any(keyword.lower() in page_text for keyword in self.region_keywords)