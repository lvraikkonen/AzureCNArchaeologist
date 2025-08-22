#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
区域筛选策略 - 适配新架构
处理Type B页面：具有区域筛选功能的页面，如API Management
集成新工具类与现有RegionProcessor
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
from src.core.region_processor import RegionProcessor
from src.utils.content.content_extractor import ContentExtractor
from src.utils.content.section_extractor import SectionExtractor
from src.utils.content.flexible_builder import FlexibleBuilder
from src.utils.data.extraction_validator import ExtractionValidator
from src.detectors.filter_detector import FilterDetector

from src.core.logging import get_logger

logger = get_logger(__name__)


class RegionFilterStrategy(BaseStrategy):
    """
    区域筛选策略 - 新架构适配
    Type B: 区域筛选页面处理 - API Management类型
    
    特点：
    - 具有区域筛选控件 (如中国北部、中国东部等)
    - 筛选器变化会改变内容显示
    - 需要提取每个区域的专门内容
    - 使用新工具类架构：ContentExtractor + SectionExtractor + FlexibleBuilder + RegionProcessor
    """

    def __init__(self, product_config: Dict[str, Any], html_file_path: str = ""):
        """
        初始化区域筛选策略
        
        Args:
            product_config: 产品配置信息
            html_file_path: HTML文件路径
        """
        super().__init__(product_config, html_file_path)
        self.strategy_name = "region_filter"
        
        # 初始化工具类
        self.content_extractor = ContentExtractor()
        self.section_extractor = SectionExtractor()
        self.flexible_builder = FlexibleBuilder()
        self.extraction_validator = ExtractionValidator()
        
        # 保持现有区域处理逻辑
        self.region_processor = RegionProcessor()
        self.filter_detector = FilterDetector()
        
        logger.info(f"🌍 初始化区域筛选策略: {self._get_product_key()}")

    def extract_flexible_content(self, soup: BeautifulSoup, url: str = "") -> Dict[str, Any]:
        """
        执行flexible JSON格式提取逻辑
        
        Args:
            soup: BeautifulSoup解析的HTML对象
            url: 源URL
            
        Returns:
            flexible JSON格式的提取数据
        """
        logger.info("🌍 执行区域筛选策略提取（flexible JSON格式）...")
        
        # 1. 使用ContentExtractor提取基础元数据
        base_metadata = self.content_extractor.extract_base_metadata(soup, url, self.html_file_path)
        
        # 2. 使用SectionExtractor提取commonSections
        common_sections = self.section_extractor.extract_all_sections(soup)
        
        # 3. 使用FilterDetector获取筛选器信息
        filter_analysis = self.filter_detector.detect_filters(soup)
        
        # 4. 使用RegionProcessor提取区域内容（传递筛选器信息和产品配置）
        try:
            region_content = self.region_processor.extract_region_contents(
                soup, 
                self.html_file_path,
                filter_analysis=filter_analysis,
                product_config=self.product_config
            )
            logger.info(f"✅ 区域内容提取完成: {len(region_content)} 个区域")
        except Exception as e:
            logger.warning(f"⚠ 区域内容提取失败: {e}")
            region_content = {}
        
        # 5. 使用FlexibleBuilder构建地区内容组
        content_groups = self.flexible_builder.build_region_content_groups(region_content)
        
        # 6. 构建策略特定内容，包含所有必要的分析数据
        strategy_content = {
            "baseContent": "",  # 区域筛选页面主要内容在contentGroups中
            "contentGroups": content_groups,
            "strategy_type": "region_filter",
            "filter_analysis": filter_analysis,  # 传递筛选器分析结果
            "tab_analysis": {}  # 区域筛选策略通常不涉及复杂tab
        }
        
        # 7. 使用FlexibleBuilder构建完整的flexible JSON
        flexible_data = self.flexible_builder.build_flexible_page(
            base_metadata, common_sections, strategy_content
        )
        
        # 8. 验证flexible JSON结果
        flexible_data = self.extraction_validator.validate_flexible_json(flexible_data)
        
        logger.info("✅ 区域筛选策略提取完成（flexible JSON格式）")
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