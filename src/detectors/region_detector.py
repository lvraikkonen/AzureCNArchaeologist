#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
区域检测器

专门负责检测页面中的区域选择器和可用区域，与现有的RegionProcessor
协同工作，提供更详细的区域分析信息。
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from bs4 import BeautifulSoup, Tag

from ..core.data_models import (
    RegionAnalysis, RegionSelector, Region
)


class RegionDetector:
    """
    区域检测器。
    
    负责识别和分析页面中的区域相关元素，包括：
    - 区域选择器（下拉框、单选按钮等）
    - 可用区域列表
    - 区域内容容器
    - 区域激活状态
    """
    
    def __init__(self):
        """初始化区域检测器。"""
        # 区域关键词映射
        self.region_keywords = {
            # 中文区域名称
            '中国北部': 'china-north',
            '中国东部': 'china-east', 
            '中国北部2': 'china-north2',
            '中国东部2': 'china-east2',
            '中国北部3': 'china-north3',
            '中国东部3': 'china-east3',
            # 英文区域名称
            'china north': 'china-north',
            'china east': 'china-east',
            'north china': 'china-north',
            'east china': 'china-east',
            # 简化名称
            '华北': 'china-north',
            '华东': 'china-east',
            '北部': 'china-north',
            '东部': 'china-east'
        }
        
        # 区域选择器模式
        self.region_selector_patterns = [
            # 直接的区域选择器
            'select[name*="region"]',
            'select[id*="region"]', 
            'select[class*="region"]',
            
            # 自定义区域选择器
            '.region-selector',
            '.region-dropdown',
            '#region-select',
            '[data-region]',
            
            # Azure China特定模式
            '.pricing-dropdown',
            '.region-pricing-dropdown',
            '.software-kind select',  # Azure特有的区域容器
            
            # 区域容器内的选择器
            '.region-container select',
            '.region-container input[type="radio"]',
            
            # 通用模式
            'button[data-toggle*="region"]',
            'div[data-region-selector]'
        ]
        
        # 区域内容容器模式
        self.region_container_patterns = [
            '.region-container',
            '[data-region]',
            '[id*="region"]',
            '[class*="region"]'
        ]
    
    def detect_regions(self, soup: BeautifulSoup) -> RegionAnalysis:
        """
        检测页面中的区域信息。
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            RegionAnalysis对象，包含所有检测到的区域信息
        """
        # 检测区域选择器
        region_selectors = self._detect_region_selectors(soup)
        
        # 检测可用区域
        available_regions = self._detect_available_regions(soup, region_selectors)
        
        # 检测区域内容容器
        region_containers = self._detect_region_containers(soup)
        
        # 分析区域激活状态
        active_regions = self._detect_active_regions(soup, available_regions)
        
        # 检测默认区域
        default_region = self._detect_default_region(region_selectors, available_regions)
        
        # 创建分析结果
        has_regions = len(available_regions) > 0 or len(region_selectors) > 0
        
        return RegionAnalysis(
            has_regions=has_regions,
            regions=available_regions,
            region_selectors=region_selectors,
            region_selector_found=len(region_selectors) > 0,
            active_regions=active_regions,
            default_region=default_region,
            region_containers=region_containers,
            region_count=len(available_regions)
        )
    
    def _detect_region_selectors(self, soup: BeautifulSoup) -> List[RegionSelector]:
        """检测区域选择器。"""
        selectors = []
        found_elements = set()  # 避免重复检测
        
        for pattern in self.region_selector_patterns:
            try:
                elements = soup.select(pattern)
                for element in elements:
                    # 生成元素唯一标识
                    element_key = self._get_element_key(element)
                    if element_key in found_elements:
                        continue
                    found_elements.add(element_key)
                    
                    # 验证是否是有效的区域选择器
                    if self._is_valid_region_selector(element):
                        selector = self._create_region_selector(element, pattern)
                        if selector:
                            selectors.append(selector)
                            
            except Exception:
                # 无效选择器，继续下一个
                continue
        
        return selectors
    
    def _detect_available_regions(self, soup: BeautifulSoup, 
                                 region_selectors: List[RegionSelector]) -> List[Region]:
        """检测可用区域。"""
        regions = []
        found_region_ids = set()
        
        # 方法1：从区域选择器中提取区域
        for selector in region_selectors:
            selector_regions = self._extract_regions_from_selector(selector)
            for region in selector_regions:
                if region.region_id not in found_region_ids:
                    found_region_ids.add(region.region_id)
                    regions.append(region)
        
        # 方法2：通过HTML结构检测区域
        structure_regions = self._detect_regions_from_structure(soup)
        for region in structure_regions:
            if region.region_id not in found_region_ids:
                found_region_ids.add(region.region_id)
                regions.append(region)
        
        # 方法3：通过文本内容检测区域
        if not regions:  # 只有在前面方法没找到时才使用
            text_regions = self._detect_regions_from_text(soup)
            for region in text_regions:
                if region.region_id not in found_region_ids:
                    found_region_ids.add(region.region_id)
                    regions.append(region)
        
        return regions
    
    def _detect_region_containers(self, soup: BeautifulSoup) -> List[Tag]:
        """检测区域内容容器。"""
        containers = []
        
        for pattern in self.region_container_patterns:
            try:
                elements = soup.select(pattern)
                containers.extend(elements)
            except Exception:
                continue
        
        # 去重
        unique_containers = []
        seen_elements = set()
        for container in containers:
            element_key = self._get_element_key(container)
            if element_key not in seen_elements:
                seen_elements.add(element_key)
                unique_containers.append(container)
        
        return unique_containers
    
    def _detect_active_regions(self, soup: BeautifulSoup, 
                             regions: List[Region]) -> List[str]:
        """检测当前激活的区域。"""
        active_regions = []
        
        # 检查选择器的选中状态
        for pattern in self.region_selector_patterns:
            try:
                elements = soup.select(pattern)
                for element in elements:
                    if element.name == 'select':
                        # 检查选中的option
                        selected_option = element.find('option', selected=True)
                        if selected_option:
                            value = selected_option.get('value', '')
                            if value:
                                active_regions.append(value)
                    elif element.name == 'input' and element.get('type') == 'radio':
                        # 检查选中的radio按钮
                        if element.get('checked'):
                            value = element.get('value', '')
                            if value:
                                active_regions.append(value)
            except Exception:
                continue
        
        # 检查URL参数或默认状态
        if not active_regions and regions:
            # 默认使用第一个区域
            active_regions.append(regions[0].region_id)
        
        return list(set(active_regions))  # 去重
    
    def _detect_default_region(self, selectors: List[RegionSelector], 
                             regions: List[Region]) -> Optional[str]:
        """检测默认区域。"""
        # 从选择器中查找默认值
        for selector in selectors:
            if selector.default_option:
                return selector.default_option
        
        # 使用第一个可用区域作为默认
        if regions:
            return regions[0].region_id
        
        # 使用常见的默认区域
        return 'china-north'
    
    def _is_valid_region_selector(self, element: Tag) -> bool:
        """验证是否是有效的区域选择器。"""
        # 检查元素类型
        if element.name not in ['select', 'input', 'button', 'div']:
            return False
        
        # 检查是否包含区域相关内容
        element_text = element.get_text().lower()
        element_attrs = ' '.join([str(v) for v in element.attrs.values()]).lower()
        
        region_indicators = [
            'region', '区域', 'china', '中国', '北部', '东部', 
            'north', 'east', '华北', '华东'
        ]
        
        has_region_indicator = (
            any(indicator in element_text for indicator in region_indicators) or
            any(indicator in element_attrs for indicator in region_indicators)
        )
        
        if not has_region_indicator:
            return False
        
        # 检查功能性（对于select和input）
        if element.name == 'select':
            options = element.find_all('option')
            return len(options) > 1
        elif element.name == 'input' and element.get('type') == 'radio':
            # 检查是否有同组的其他radio按钮
            name = element.get('name')
            if name:
                parent = element.find_parent()
                if parent:
                    same_group = parent.find_all('input', {'name': name, 'type': 'radio'})
                    return len(same_group) > 1
        
        return True
    
    def _create_region_selector(self, element: Tag, pattern: str) -> Optional[RegionSelector]:
        """创建区域选择器对象。"""
        try:
            selector_id = element.get('id', '')
            selector_type = element.name
            
            # 提取选项
            options = []
            default_option = None
            
            if element.name == 'select':
                option_elements = element.find_all('option')
                for option in option_elements:
                    value = option.get('value', '').strip()
                    text = option.get_text().strip()
                    
                    if not value or value in ['', '请选择', '加载中...']:
                        if text and text not in ['请选择', '加载中...']:
                            value = self._normalize_region_name(text)
                    
                    if value:
                        options.append(value)
                        # 检查是否是默认选项
                        if option.get('selected') or '默认' in text:
                            default_option = value
                            
            elif element.name == 'input' and element.get('type') == 'radio':
                # Radio按钮组
                name = element.get('name')
                if name:
                    parent = element.find_parent()
                    if parent:
                        radio_group = parent.find_all('input', {'name': name, 'type': 'radio'})
                        for radio in radio_group:
                            value = radio.get('value', '').strip()
                            if value:
                                options.append(value)
                                if radio.get('checked'):
                                    default_option = value
            
            # 如果没有提取到选项，使用默认区域
            if not options:
                options = ['china-north', 'china-east']
            
            return RegionSelector(
                element=element,
                selector_id=selector_id or f"region-selector-{hash(str(element))}"[:8],
                selector_type=selector_type,
                pattern=pattern,
                options=options,
                default_option=default_option or options[0] if options else None,
                is_active=True
            )
            
        except Exception:
            return None
    
    def _extract_regions_from_selector(self, selector: RegionSelector) -> List[Region]:
        """从选择器中提取区域对象。"""
        regions = []
        
        for option in selector.options:
            region_id = self._normalize_region_name(option)
            region_name = self._get_region_display_name(region_id)
            
            region = Region(
                region_id=region_id,
                region_name=region_name,
                region_code=region_id,
                is_available=True,
                is_default=(option == selector.default_option)
            )
            regions.append(region)
        
        return regions
    
    def _detect_regions_from_structure(self, soup: BeautifulSoup) -> List[Region]:
        """通过HTML结构检测区域。"""
        regions = []
        
        # 检测区域容器的ID模式
        common_region_patterns = [
            'china-north', 'china-east', 
            'china-north2', 'china-east2',
            'china-north3', 'china-east3',
            'north-china', 'east-china'
        ]
        
        for pattern in common_region_patterns:
            # 查找包含区域ID的元素
            elements = soup.find_all(id=lambda x: x and pattern in x.lower())
            if elements:
                region_id = pattern
                region_name = self._get_region_display_name(region_id)
                
                region = Region(
                    region_id=region_id,
                    region_name=region_name,
                    region_code=region_id,
                    is_available=True,
                    is_default=(pattern == 'china-north')  # 默认北部为主要区域
                )
                regions.append(region)
        
        return regions
    
    def _detect_regions_from_text(self, soup: BeautifulSoup) -> List[Region]:
        """通过文本内容检测区域。"""
        regions = []
        page_text = soup.get_text()
        
        found_regions = set()
        for keyword, region_id in self.region_keywords.items():
            if keyword in page_text:
                found_regions.add(region_id)
        
        for region_id in found_regions:
            region_name = self._get_region_display_name(region_id)
            region = Region(
                region_id=region_id,
                region_name=region_name,
                region_code=region_id,
                is_available=True,
                is_default=(region_id == 'china-north')
            )
            regions.append(region)
        
        return regions
    
    def _normalize_region_name(self, name: str) -> str:
        """标准化区域名称。"""
        name_lower = name.lower().strip()
        
        # 直接映射
        if name_lower in self.region_keywords:
            return self.region_keywords[name_lower]
        
        # 模糊匹配
        for keyword, region_id in self.region_keywords.items():
            if keyword.lower() in name_lower:
                return region_id
        
        # 如果无法匹配，尝试从名称推断
        if 'north' in name_lower or '北' in name_lower:
            if '2' in name_lower:
                return 'china-north2'
            elif '3' in name_lower:
                return 'china-north3'
            else:
                return 'china-north'
        elif 'east' in name_lower or '东' in name_lower:
            if '2' in name_lower:
                return 'china-east2'
            elif '3' in name_lower:
                return 'china-east3'
            else:
                return 'china-east'
        
        # 默认返回原名称（小写化）
        return name_lower.replace(' ', '-')
    
    def _get_region_display_name(self, region_id: str) -> str:
        """获取区域显示名称。"""
        display_names = {
            'china-north': '中国北部',
            'china-east': '中国东部',
            'china-north2': '中国北部2',  
            'china-east2': '中国东部2',
            'china-north3': '中国北部3',
            'china-east3': '中国东部3',
            'north-china': '中国北部',
            'east-china': '中国东部'
        }
        
        return display_names.get(region_id, region_id.replace('-', ' ').title())
    
    def _get_element_key(self, element: Tag) -> str:
        """获取元素的唯一标识符。"""
        # 使用元素的位置和属性创建唯一key
        attrs = {}
        for attr in ['id', 'name', 'class']:
            value = element.get(attr)
            if value:
                attrs[attr] = str(value)
        
        return f"{element.name}:{hash(str(element))}:{str(attrs)}"