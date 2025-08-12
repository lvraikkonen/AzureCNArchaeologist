#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单静态策略
处理Type A页面：简单静态页面，如Event Grid、Service Bus等
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.strategies.base_strategy import BaseStrategy
from src.core.logging import get_logger

logger = get_logger(__name__)


class SimpleStaticStrategy(BaseStrategy):
    """
    简单静态策略
    Type A: 简单静态页面处理 - Event Grid类型
    
    特点：
    - 没有区域筛选或复杂交互
    - 内容相对固定，不需要动态筛选
    - 主要包含：Banner、描述、主要内容、FAQ
    - Event Grid、Service Bus是此策略的典型代表
    """

    def __init__(self, product_config: Dict[str, Any], html_file_path: str = ""):
        """
        初始化简单静态策略
        
        Args:
            product_config: 产品配置信息
            html_file_path: HTML文件路径
        """
        super().__init__(product_config, html_file_path)
        self.strategy_name = "simple_static"
        logger.info(f"📄 初始化简单静态策略: {self._get_product_key()}")

    def extract(self, soup: BeautifulSoup, url: str = "") -> Dict[str, Any]:
        """
        执行简单静态策略的提取逻辑
        
        Args:
            soup: BeautifulSoup解析的HTML对象
            url: 源URL
            
        Returns:
            提取的CMS内容数据
        """
        logger.info("🚀 开始简单静态策略提取...")
        
        # 1. 提取基础内容（Title, Banner, Description, QA等）
        data = self._extract_base_content(soup, url)
        
        # 2. 设置简单页面标识
        data["HasRegion"] = False
        data["NoRegionContent"] = self._extract_main_content(soup)
        
        # 3. 清空区域内容字段（简单页面不需要）
        region_fields = [
            "NorthChinaContent", "NorthChina2Content", "NorthChina3Content",
            "EastChinaContent", "EastChina2Content", "EastChina3Content"
        ]
        for field in region_fields:
            data[field] = ""
        
        # 4. 验证提取结果
        data = self._validate_extraction_result(data)
        
        logger.info("✅ 简单静态策略提取完成")
        return data

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """
        提取主要内容作为NoRegionContent
        
        基于HTML结构分析：
        1. 优先选择：<tab-control-container> 层内的所有内容
        2. 备选方案：DescriptionContent后面的 <pricing-page-section> 层内容
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            主要内容HTML字符串
        """
        logger.info("📝 提取主要内容...")
        
        try:
            # 方案1: 查找 tab-control-container 
            logger.info("🔍 方案1: 查找 tab-control-container...")
            tab_containers = soup.find_all(class_='tab-control-container')
            if tab_containers:
                main_content = ""
                for container in tab_containers:
                    main_content += self._clean_html_content(str(container))
                    print(f"✓ 找到tab-control-container内容")
                return main_content
            
            # 方案2: 查找 DescriptionContent 后面的 pricing-page-section
            logger.info("🔍 方案2: 查找 pricing-page-section...")
            pricing_sections = soup.find_all(class_='pricing-page-section')
            
            if pricing_sections:
                main_content = ""
                # 跳过第一个pricing-page-section（通常是DescriptionContent）
                # 提取后面的pricing-page-section作为主要内容
                for i, section in enumerate(pricing_sections):
                    if i > 0:  # 跳过第一个
                        section_text = section.get_text().lower()
                        # 确保不是banner或导航内容
                        if not any(skip_text in section_text for skip_text in [
                            'banner', 'navigation', 'nav'
                        ]):
                            main_content += self._clean_html_content(str(section))
                            print(f"✓ 找到第{i+1}个pricing-page-section内容")
                
                if main_content:
                    return main_content
            
            # 方案3: 备用方案 - 查找其他可能的内容容器
            logger.info("🔍 方案3: 使用备用内容提取...")
            fallback_selectors = [
                '.main-content',
                '.content-area', 
                '.primary-content',
                'main',
                '.page-content'
            ]
            
            for selector in fallback_selectors:
                elements = soup.select(selector)
                for element in elements:
                    if len(element.get_text(strip=True)) > 100:  # 至少100个字符
                        main_content = self._clean_html_content(str(element))
                        print(f"✓ 使用备用内容，选择器: {selector}")
                        return main_content
            
            logger.info("⚠ 未找到合适的主要内容")
            return ""
            
        except Exception as e:
            logger.info(f"⚠ 主要内容提取失败: {e}")
            return ""