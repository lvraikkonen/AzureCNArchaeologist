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
    FilterType, Filter
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