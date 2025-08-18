#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单静态策略 - 适配新架构
处理Type A页面：简单静态页面，如Event Grid、Service Bus等
使用新工具类替代BaseStrategy继承逻辑
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
from src.utils.content.content_extractor import ContentExtractor
from src.utils.content.section_extractor import SectionExtractor
from src.utils.content.flexible_builder import FlexibleBuilder
from src.utils.data.extraction_validator import ExtractionValidator
from src.utils.html.cleaner import clean_html_content
from src.core.logging import get_logger

logger = get_logger(__name__)


class SimpleStaticStrategy(BaseStrategy):
    """
    简单静态策略 - 新架构适配
    Type A: 简单静态页面处理 - Event Grid类型
    
    特点：
    - 没有区域筛选或复杂交互
    - 内容相对固定，不需要动态筛选
    - 主要包含：Banner、描述、主要内容、FAQ
    - 使用新工具类架构：ContentExtractor + SectionExtractor + FlexibleBuilder
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
        
        # 初始化工具类
        self.content_extractor = ContentExtractor()
        self.section_extractor = SectionExtractor()
        self.flexible_builder = FlexibleBuilder()
        self.extraction_validator = ExtractionValidator()
        
        logger.info(f"📄 初始化简单静态策略: {self._get_product_key()}")

    def extract_flexible_content(self, soup: BeautifulSoup, url: str = "") -> Dict[str, Any]:
        """
        执行flexible JSON格式提取逻辑
        
        Args:
            soup: BeautifulSoup解析的HTML对象
            url: 源URL
            
        Returns:
            flexible JSON格式的提取数据
        """
        logger.info("🚀 开始简单静态策略提取（flexible JSON格式）...")
        
        # 1. 使用ContentExtractor提取基础元数据
        base_metadata = self.content_extractor.extract_base_metadata(soup, url, self.html_file_path)
        
        # 2. 使用SectionExtractor提取commonSections
        common_sections = self.section_extractor.extract_all_sections(soup)
        
        # 3. 构建策略特定内容
        strategy_content = {
            "baseContent": self._extract_main_content(soup),
            "contentGroups": self.flexible_builder.build_simple_content_groups(""),  # 简单页面无contentGroups
            "pageConfig": self.flexible_builder._get_default_page_config(),  # 无筛选器
            "strategy_type": "simple_static"
        }
        
        # 4. 使用FlexibleBuilder构建完整的flexible JSON
        flexible_data = self.flexible_builder.build_flexible_page(
            base_metadata, common_sections, strategy_content
        )
        
        # 5. 验证flexible JSON结果
        flexible_data = self.extraction_validator.validate_flexible_json(flexible_data)
        
        logger.info("✅ 简单静态策略提取完成（flexible JSON格式）")
        return flexible_data

    def extract_common_sections(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        提取通用sections（Banner、Description、QA等）
        
        Args:
            soup: BeautifulSoup解析的HTML对象
            
        Returns:
            commonSections列表
        """
        return self.section_extractor.extract_all_sections(soup)

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """
        提取主要内容（简单页面的baseContent）
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            主要内容HTML字符串
        """
        logger.info("📝 提取主要内容...")
        
        try:
            # 方案1: 查找technical-azure-selector内的pricing-page-section
            logger.info("🔍 方案1: 查找technical-azure-selector内容...")
            technical_selector = soup.find('div', class_='technical-azure-selector')
            if technical_selector:
                pricing_sections = technical_selector.find_all('div', class_='pricing-page-section')
                if pricing_sections:
                    main_content = ""
                    for section in pricing_sections:
                        # 过滤QA内容避免与commonSections重复
                        section_text = section.get_text().lower()
                        if not any(qa_indicator in section_text for qa_indicator in [
                            '常见问题', 'faq', '支持和服务级别协议', 'more-detail'
                        ]):
                            main_content += str(section)
                    
                    if main_content:
                        logger.info("✓ 找到technical-azure-selector内容")
                        return clean_html_content(main_content)
            
            # 方案2: 查找tab-control-container
            logger.info("🔍 方案2: 查找tab-control-container...")
            tab_containers = soup.find_all(class_='tab-control-container')
            if tab_containers:
                main_content = ""
                for container in tab_containers:
                    main_content += str(container)
                    logger.info("✓ 找到tab-control-container内容")
                return clean_html_content(main_content)
            
            # 方案3: 查找pricing-page-section（排除第一个描述内容）
            logger.info("🔍 方案3: 查找pricing-page-section...")
            pricing_sections = soup.find_all(class_='pricing-page-section')
            
            if pricing_sections:
                main_content = ""
                # 跳过第一个pricing-page-section（通常是DescriptionContent）
                for i, section in enumerate(pricing_sections):
                    if i > 0:  # 跳过第一个
                        section_text = section.get_text().lower()
                        # 过滤特殊内容
                        if not any(skip_text in section_text for skip_text in [
                            'banner', 'navigation', 'nav', '常见问题', 'faq'
                        ]):
                            main_content += str(section)
                            logger.info(f"✓ 找到第{i+1}个pricing-page-section内容")
                
                if main_content:
                    return clean_html_content(main_content)
            
            # 方案4: 使用ContentExtractor的主要内容提取
            logger.info("🔍 方案4: 使用ContentExtractor主要内容提取...")
            main_content = self.content_extractor.extract_main_content(soup)
            if main_content:
                return clean_html_content(main_content)
            
            logger.info("⚠ 未找到合适的主要内容")
            return ""
            
        except Exception as e:
            logger.info(f"⚠ 主要内容提取失败: {e}")
            return ""

    def _get_product_key(self) -> str:
        """获取产品键"""
        if hasattr(self, 'product_config') and 'product_key' in self.product_config:
            return self.product_config['product_key']
        
        # 从文件路径推断
        if self.html_file_path:
            file_name = Path(self.html_file_path).stem
            if file_name.endswith('-index'):
                return file_name[:-6]
        
        return "unknown"