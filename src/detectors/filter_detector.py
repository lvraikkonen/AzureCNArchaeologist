#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
筛选器检测器

基于实际HTML结构检测Azure中国区页面的筛选器，专门检测：
- 软件类别筛选器：.dropdown-container.software-kind-container
- 地区筛选器：.dropdown-container.region-container
- 隐藏状态和选项映射的精确提取
"""

from typing import List, Dict, Any, Optional, Set
from bs4 import BeautifulSoup, Tag

from ..core.data_models import (
    FilterAnalysis, FilterType, Filter
)
from ..core.logging import get_logger

logger = get_logger(__name__)


class FilterDetector:
    """
    Azure中国区页面筛选器检测器。
    
    基于实际HTML结构精确检测：
    - 软件类别筛选器：.dropdown-container.software-kind-container + #software-box
    - 地区筛选器：.dropdown-container.region-container + #region-box
    - 检测隐藏状态：style="display:none;"
    - 提取选项映射：data-href和value属性
    """
    
    def __init__(self):
        """初始化筛选器检测器。"""
        logger.info("初始化FilterDetector - 基于实际HTML结构")
    
    def detect_filters(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        检测页面中的筛选器（基于实际HTML结构）。
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            筛选器分析结果字典
        """
        logger.info("🔍 开始检测筛选器...")
        
        # 检测软件类别筛选器
        software_result = self._detect_software_kind_filter(soup)
        
        # 检测地区筛选器
        region_result = self._detect_region_filter(soup)
        
        result = {
            "has_region": region_result["exists"],
            "has_software": software_result["exists"],
            "region_visible": region_result["visible"],
            "software_visible": software_result["visible"],
            "region_options": region_result["options"],
            "software_options": software_result["options"]
        }
        
        logger.info(f"✅ 筛选器检测完成: region={result['has_region']}({result['region_visible']}), software={result['has_software']}({result['software_visible']})")
        return result
    
    def _detect_software_kind_filter(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        检测软件类别筛选器：.dropdown-container.software-kind-container
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            {
                "exists": bool,
                "visible": bool,
                "options": [{"value": str, "href": str, "label": str}]
            }
        """
        logger.info("🔍 检测软件类别筛选器...")
        
        # 查找 software-kind-container
        software_container = soup.find('div', class_='dropdown-container software-kind-container')
        
        if not software_container:
            logger.info("⚠ 未找到 software-kind-container")
            return {"exists": False, "visible": False, "options": []}
        
        logger.info("✅ 找到 software-kind-container")
        
        # 检查是否隐藏
        style = software_container.get('style', '')
        is_visible = 'display:none' not in style and 'display: none' not in style
        
        # 查找 #software-box select
        software_select = soup.find('select', id='software-box')
        options = []
        
        if software_select:
            logger.info("✅ 找到 #software-box")
            option_elements = software_select.find_all('option')
            
            for option in option_elements:
                value = option.get('value', '').strip()
                href = option.get('data-href', '').strip()
                label = option.get_text().strip()
                
                if value and label and '加载中' not in label and '请选择' not in label:
                    options.append({
                        "value": value,
                        "href": href,
                        "label": label
                    })
        
        logger.info(f"✅ 软件类别筛选器: visible={is_visible}, options={len(options)}")
        
        return {
            "exists": True,
            "visible": is_visible,
            "options": options
        }
    
    def _detect_region_filter(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        检测地区筛选器：.dropdown-container.region-container
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            {
                "exists": bool,
                "visible": bool,
                "options": [{"value": str, "href": str, "label": str}]
            }
        """
        logger.info("🔍 检测地区筛选器...")
        
        # 查找 region-container
        region_container = soup.find('div', class_='dropdown-container region-container')
        
        if not region_container:
            logger.info("⚠ 未找到 region-container")
            return {"exists": False, "visible": False, "options": []}
        
        logger.info("✅ 找到 region-container")
        
        # 检查是否隐藏
        style = region_container.get('style', '')
        is_visible = 'display:none' not in style and 'display: none' not in style
        
        # 查找 #region-box select
        region_select = soup.find('select', id='region-box')
        options = []
        
        if region_select:
            logger.info("✅ 找到 #region-box")
            option_elements = region_select.find_all('option')
            
            for option in option_elements:
                value = option.get('value', '').strip()
                href = option.get('data-href', '').strip()
                label = option.get_text().strip()
                
                if value and label and '加载中' not in label and '请选择' not in label:
                    options.append({
                        "value": value,
                        "href": href,
                        "label": label
                    })
        
        logger.info(f"✅ 地区筛选器: visible={is_visible}, options={len(options)}")
        
        return {
            "exists": True,
            "visible": is_visible,
            "options": options
        }
    
    # 保留兼容性方法（不再使用）
    def detect_region_filters(self, soup: BeautifulSoup) -> List[Filter]:
        """
        兼容性方法 - 不再使用，请使用 detect_filters()
        """
        logger.warning("⚠ detect_region_filters() 已废弃，请使用 detect_filters()")
        return []
    
    # 兼容性方法（不再使用）
    def detect_other_filters(self, soup: BeautifulSoup) -> List[Filter]:
        """
        兼容性方法 - 不再使用，请使用 detect_filters()
        """
        logger.warning("⚠ detect_other_filters() 已废弃，请使用 detect_filters()")
        return []
    
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
    
    def _create_region_filter(self, element: Tag, soup: BeautifulSoup) -> Optional[Filter]:
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
            
            return Filter(
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