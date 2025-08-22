#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
复杂内容策略 - 基于新架构创建
处理复杂的多筛选器和tab组合，如Cloud Services类型页面
全新实现，基于新工具类架构
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
from src.detectors.tab_detector import TabDetector
from src.core.logging import get_logger

logger = get_logger(__name__)


class ComplexContentStrategy(BaseStrategy):
    """
    复杂内容策略 - 新架构实现
    Type C: 复杂页面处理 - Cloud Services类型
    
    特点：
    - 具有多种筛选器组合：软件类别、地区、category tabs等
    - 复杂的交互和内容映射关系
    - 需要处理多维度内容组合
    - 使用新工具类架构：ContentExtractor + SectionExtractor + FlexibleBuilder + FilterDetector + TabDetector
    """

    def __init__(self, product_config: Dict[str, Any], html_file_path: str = ""):
        """
        初始化复杂内容策略
        
        Args:
            product_config: 产品配置信息
            html_file_path: HTML文件路径
        """
        super().__init__(product_config, html_file_path)
        self.strategy_name = "complex_content"
        
        # 初始化工具类
        self.content_extractor = ContentExtractor()
        self.section_extractor = SectionExtractor()
        self.flexible_builder = FlexibleBuilder()
        self.extraction_validator = ExtractionValidator()
        
        # 初始化检测器
        self.filter_detector = FilterDetector()
        self.tab_detector = TabDetector()
        
        # 初始化区域处理器（用于表格筛选）
        self.region_processor = RegionProcessor()
        
        logger.info(f"🔧 初始化复杂内容策略: {self._get_product_key()}")

    def extract_flexible_content(self, soup: BeautifulSoup, url: str = "") -> Dict[str, Any]:
        """
        执行flexible JSON格式提取逻辑
        
        Args:
            soup: BeautifulSoup解析的HTML对象
            url: 源URL
            
        Returns:
            flexible JSON格式的提取数据
        """
        logger.info("🔧 开始复杂内容策略提取（flexible JSON格式）...")
        
        # 1. 使用ContentExtractor提取基础元数据
        base_metadata = self.content_extractor.extract_base_metadata(soup, url, self.html_file_path)
        
        # 2. 使用SectionExtractor提取commonSections
        common_sections = self.section_extractor.extract_all_sections(soup)
        
        # 3. 分析筛选器和tab结构
        filter_analysis = self.filter_detector.detect_filters(soup)
        tab_analysis = self.tab_detector.detect_tabs(soup)
        
        # 4. 提取复杂内容映射
        content_mapping = self._extract_complex_content_mapping(soup, filter_analysis, tab_analysis)
        
        # 5. 使用FlexibleBuilder构建复杂内容组
        content_groups = self.flexible_builder.build_complex_content_groups(
            filter_analysis, tab_analysis, content_mapping
        )

        # 6. 构建策略特定内容
        strategy_content = {
            "baseContent": "",  # 复杂页面主要内容在contentGroups中
            "contentGroups": content_groups,
            "strategy_type": "complex",
            "filter_analysis": filter_analysis,  # 传递筛选器分析结果
            "tab_analysis": tab_analysis  # 传递tab分析结果
        }
        
        # 7. 使用FlexibleBuilder构建完整的flexible JSON
        flexible_data = self.flexible_builder.build_flexible_page(
            base_metadata, common_sections, strategy_content
        )
        
        # 8. 验证flexible JSON结果
        flexible_data = self.extraction_validator.validate_flexible_json(flexible_data)
        
        logger.info("✅ 复杂内容策略提取完成（flexible JSON格式）")
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

    def _extract_complex_main_content(self, soup: BeautifulSoup, 
                                    filter_analysis: Dict[str, Any], 
                                    tab_analysis: Dict[str, Any]) -> str:
        """
        提取复杂页面的主要内容（简化版，用于传统CMS格式）
        
        Args:
            soup: BeautifulSoup对象
            filter_analysis: 筛选器分析结果
            tab_analysis: Tab分析结果
            
        Returns:
            主要内容HTML字符串
        """
        logger.info("📝 提取复杂页面主要内容...")
        
        try:
            main_content = ""
            
            # 1. 优先查找technical-azure-selector主容器
            main_container = soup.find('div', class_='technical-azure-selector')
            if main_container:
                # 获取所有内容组（tabContent分组）
                content_groups = tab_analysis.get("content_groups", [])
                
                if content_groups:
                    # 提取第一个内容组的内容作为示例
                    first_group = content_groups[0]
                    group_id = first_group.get("id", "")
                    
                    group_element = soup.find('div', id=group_id)
                    if group_element:
                        # 过滤QA等重复内容
                        content_text = group_element.get_text().lower()
                        if not any(skip_text in content_text for skip_text in [
                            '常见问题', 'faq', '支持和服务级别协议'
                        ]):
                            main_content = str(group_element)
                            logger.info(f"✓ 找到复杂页面主容器内容（{group_id}）")
                            return main_content
                
                # 如果没有找到分组，返回整个主容器
                main_content = str(main_container)
                logger.info("✓ 找到复杂页面主容器内容（完整）")
                return main_content
            
            # 2. 备用方案：查找pricing-page-section
            pricing_sections = soup.find_all('div', class_='pricing-page-section')
            if pricing_sections:
                for i, section in enumerate(pricing_sections):
                    if i > 0:  # 跳过第一个（通常是描述）
                        section_text = section.get_text().lower()
                        if not any(skip_text in section_text for skip_text in [
                            'banner', 'navigation', 'nav', '常见问题', 'faq'
                        ]):
                            main_content += str(section)
                
                if main_content:
                    logger.info("✓ 使用pricing-page-section备用方案")
                    return main_content
            
            # 3. 最后备用方案：使用ContentExtractor
            main_content = self.content_extractor.extract_main_content(soup)
            if main_content:
                logger.info("✓ 使用ContentExtractor备用方案")
                return main_content
            
            logger.info("⚠ 未找到合适的复杂页面主要内容")
            return ""
            
        except Exception as e:
            logger.info(f"⚠ 复杂页面主要内容提取失败: {e}")
            return ""

    def _extract_complex_content_mapping(self, soup: BeautifulSoup,
                                       filter_analysis: Dict[str, Any],
                                       tab_analysis: Dict[str, Any]) -> Dict[str, str]:
        """
        提取复杂页面的内容映射关系（带区域筛选）
        
        Args:
            soup: BeautifulSoup对象
            filter_analysis: 筛选器分析结果
            tab_analysis: Tab分析结果
            
        Returns:
            内容映射字典
        """
        logger.info("🗺️ 提取复杂页面内容映射（支持区域筛选）...")
        
        content_mapping = {}
        
        try:
            # 获取用于区域筛选的OS名称
            os_name = self.region_processor.get_os_name_for_region_filtering(
                product_config=self.product_config,
                filter_analysis=filter_analysis,
                html_file_path=self.html_file_path
            )
            
            if not os_name:
                logger.warning("⚠ 无法获取有效的OS名称，将跳过区域表格筛选")
            else:
                logger.info(f"🎯 使用OS名称 '{os_name}' 进行区域表格筛选")
            
            # 获取region选项
            region_options = filter_analysis.get("region_options", [])
            software_options = filter_analysis.get("software_options", [])
            category_tabs = tab_analysis.get("category_tabs", [])
            
            # 如果没有区域选项，使用默认
            if not region_options:
                region_options = [{"value": "default", "label": "默认"}]
            
            # 构建多维度映射
            for region in region_options:
                region_id = region.get("value", "")
                
                if software_options:
                    # 有软件筛选器的情况
                    for software in software_options:
                        software_id = software.get("value", "")
                        
                        if category_tabs:
                            # 有category tabs的情况 - 三维映射
                            for tab in category_tabs:
                                tab_id = tab.get("href", "").replace("#", "")
                                content_key = f"{region_id}_{software_id}_{tab_id}"
                                
                                # 尝试找到对应的内容并应用区域筛选
                                content = self._find_content_by_mapping(soup, region_id, software_id, tab_id, os_name)
                                if content:
                                    content_mapping[content_key] = content
                        else:
                            # 只有region + software - 二维映射
                            content_key = f"{region_id}_{software_id}"
                            content = self._find_content_by_mapping(soup, region_id, software_id, None, os_name)
                            if content:
                                content_mapping[content_key] = content
                elif category_tabs:
                    # 只有region + category tabs - 二维映射
                    for tab in category_tabs:
                        tab_id = tab.get("href", "").replace("#", "")
                        content_key = f"{region_id}_{tab_id}"
                        content = self._find_content_by_mapping(soup, region_id, None, tab_id, os_name)
                        if content:
                            content_mapping[content_key] = content
                else:
                    # 只有region - 一维映射
                    content_key = region_id
                    content = self._find_content_by_mapping(soup, region_id, None, None, os_name)
                    if content:
                        content_mapping[content_key] = content
            
            logger.info(f"✓ 构建了 {len(content_mapping)} 个内容映射")
            return content_mapping
            
        except Exception as e:
            logger.info(f"⚠ 内容映射提取失败: {e}")
            return {}

    def _find_content_by_mapping(self, soup: BeautifulSoup, 
                               region_id: str = None,
                               software_id: str = None, 
                               tab_id: str = None,
                               os_name: str = None) -> str:
        """
        根据映射关系查找对应内容（支持区域表格筛选）
        
        Args:
            soup: BeautifulSoup对象
            region_id: 区域ID
            software_id: 软件ID
            tab_id: Tab ID
            os_name: OS名称，用于区域筛选
            
        Returns:
            找到的内容HTML字符串（经过区域筛选）
        """
        try:
            # 首先从原始soup中找到基础内容
            base_content = None
            
            # 1. 如果有tab_id，优先查找tab对应内容
            if tab_id:
                base_content = soup.find('div', id=tab_id)
                if base_content:
                    logger.info(f"✓ 找到tab内容: {tab_id}")
            
            # 2. 如果有software_id，查找对应的tabContent分组
            if not base_content and software_id:
                content_groups = soup.find_all('div', class_='tab-panel')
                for group in content_groups:
                    group_id = group.get('id', '')
                    if 'tabContent' in group_id:
                        base_content = group
                        logger.info(f"✓ 找到软件内容组: {group_id}")
                        break
            
            # 3. 默认返回主要内容区域
            if not base_content:
                base_content = soup.find('div', class_='technical-azure-selector')
                if base_content:
                    logger.info("✓ 使用主要内容区域")
            
            if not base_content:
                logger.warning("⚠ 未找到任何基础内容")
                return ""
            
            # 应用区域筛选（如果有region_id和os_name）
            if region_id and os_name:
                logger.info(f"🔍 对内容应用区域筛选: region={region_id}, os={os_name}")
                # 创建包含找到内容的临时soup
                temp_soup = BeautifulSoup(str(base_content), 'html.parser')
                # 应用区域筛选
                filtered_soup = self.region_processor.apply_region_filtering(temp_soup, region_id, os_name)
                return str(filtered_soup)
            else:
                # 没有区域信息，直接返回原始内容
                if not region_id:
                    logger.info("ℹ 无区域ID，跳过区域筛选")
                if not os_name:
                    logger.info("ℹ 无OS名称，跳过区域筛选")
                return str(base_content)
            
        except Exception as e:
            logger.info(f"⚠ 内容查找失败: {e}")
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