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
from src.utils.content.content_utils import classify_pricing_section, filter_sections_by_type
from src.utils.html.cleaner import clean_html_content
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

        # 6. 构建策略特定内容，包含智能分类的baseContent
        # 对于复杂策略，如果没有有效的内容组，可以提取baseContent作为fallback
        base_content = ""
        if not content_groups or len(content_groups) == 0:
            logger.info("⚠ 未找到复杂内容组，尝试提取通用baseContent...")
            base_content = self._extract_main_content(soup)
        
        strategy_content = {
            "baseContent": base_content,  # 如果有内容组则为空，否则作为fallback
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

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """
        提取复杂页面的主要内容 - 使用智能分类逻辑
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            主要内容HTML字符串
        """
        logger.info("📝 提取复杂页面主要内容（智能分类模式）...")
        
        try:
            # 方案1: 查找technical-azure-selector内的pricing-page-section，使用智能分类
            logger.info("🔍 查找technical-azure-selector内容（智能分类）...")
            technical_selector = soup.find('div', class_='technical-azure-selector')
            if technical_selector:
                pricing_sections = technical_selector.find_all('div', class_='pricing-page-section')
                if pricing_sections:
                    # 使用智能分类过滤，只保留content类型的section
                    content_sections = filter_sections_by_type(
                        pricing_sections, 
                        include_types=['content']
                    )
                    
                    if content_sections:
                        main_content = ""
                        for section in content_sections:
                            main_content += str(section)
                            section_type = classify_pricing_section(section)
                            logger.info(f"✓ 添加复杂策略technical-azure-selector section (类型: {section_type})")
                        
                        logger.info(f"✓ 找到复杂策略technical-azure-selector内容，共{len(content_sections)}个content sections")
                        return clean_html_content(main_content)
                
                # 如果没有分类为content的section，返回整个主容器但过滤FAQ/SLA
                logger.info("🔍 返回整个technical-azure-selector容器...")
                all_sections = technical_selector.find_all('div', class_='pricing-page-section')
                
                filtered_main_content = ""
                for section in all_sections:
                    section_type = classify_pricing_section(section)
                    if section_type in ['content', 'other']:  # 包含other类型以确保不遗漏内容
                        filtered_main_content += str(section)
                        logger.info(f"✓ 添加{section_type}类型section到复杂策略内容")
                
                if filtered_main_content:
                    return clean_html_content(filtered_main_content)
                else:
                    # 最后fallback：返回完整主容器
                    return clean_html_content(str(technical_selector))
            
            # 方案2: 查找所有pricing-page-section，智能分类后处理
            logger.info("🔍 查找所有pricing-page-section（智能分类）...")
            all_pricing_sections = soup.find_all('div', class_='pricing-page-section')
            
            if all_pricing_sections:
                main_content = ""
                processed_sections = 0
                
                # 跳过第一个section（通常是Description），从第二个开始智能分类
                for section in all_pricing_sections[1:]:
                    section_type = classify_pricing_section(section)
                    
                    if section_type == 'content':
                        main_content += str(section)
                        processed_sections += 1
                        logger.info(f"✓ 添加复杂策略content section #{processed_sections}")
                    elif section_type in ['faq', 'sla']:
                        logger.info(f"⏩ 跳过{section_type} section（将由SectionExtractor处理）")
                    else:
                        logger.info(f"⏩ 跳过{section_type} section")
                
                if main_content:
                    logger.info(f"✓ 复杂策略智能分类完成，处理了{processed_sections}个content sections")
                    return clean_html_content(main_content)
            
            # 方案3: 使用ContentExtractor的主要内容提取
            logger.info("🔍 使用ContentExtractor主要内容提取...")
            main_content = self.content_extractor.extract_main_content(soup)
            if main_content:
                return clean_html_content(main_content)
            
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
            # 获取用于区域筛选的所有OS名称（支持多软件选项）
            all_os_names = self.region_processor.get_os_names_for_region_filtering(filter_analysis)

            if not all_os_names:
                logger.warning("⚠ 无法获取有效的OS名称，将跳过区域表格筛选")
            else:
                logger.info(f"🎯 获取到 {len(all_os_names)} 个OS名称用于区域筛选: {all_os_names}")

            # 获取region选项
            region_options = filter_analysis.get("region_options", [])
            software_options = filter_analysis.get("software_options", [])
            category_tabs = tab_analysis.get("category_tabs", [])

            # 如果没有区域选项，使用默认
            if not region_options:
                region_options = [{"value": "default", "label": "默认"}]

            # 构建软件ID到OS名称的映射
            software_to_os_mapping = {}
            if software_options and all_os_names:
                for i, software in enumerate(software_options):
                    software_id = software.get("value", "")
                    # 使用对应索引的OS名称，如果索引超出范围则使用第一个
                    os_name = all_os_names[i] if i < len(all_os_names) else all_os_names[0]
                    software_to_os_mapping[software_id] = os_name
                    logger.info(f"🔗 软件映射: '{software_id}' -> OS名称 '{os_name}'")

            # 构建多维度映射
            for region in region_options:
                region_id = region.get("value", "")

                if software_options:
                    # 有软件筛选器的情况
                    for software in software_options:
                        software_id = software.get("value", "")
                        # 获取当前软件对应的OS名称
                        current_os_name = software_to_os_mapping.get(software_id, all_os_names[0] if all_os_names else "")

                        if category_tabs:
                            # 有category tabs的情况 - 三维映射
                            for tab in category_tabs:
                                tab_id = tab.get("href", "").replace("#", "")
                                content_key = f"{region_id}_{software_id}_{tab_id}"

                                # 使用当前软件对应的OS名称进行区域筛选
                                content = self._find_content_by_mapping(soup, region_id, software_id, tab_id, current_os_name)
                                if content:
                                    content_mapping[content_key] = content
                        else:
                            # 只有region + software - 二维映射
                            content_key = f"{region_id}_{software_id}"
                            content = self._find_content_by_mapping(soup, region_id, software_id, None, current_os_name)
                            if content:
                                content_mapping[content_key] = content
                elif category_tabs:
                    # 只有region + category tabs - 二维映射
                    # 使用第一个OS名称（如果有的话）
                    fallback_os_name = all_os_names[0] if all_os_names else ""
                    for tab in category_tabs:
                        tab_id = tab.get("href", "").replace("#", "")
                        content_key = f"{region_id}_{tab_id}"
                        content = self._find_content_by_mapping(soup, region_id, None, tab_id, fallback_os_name)
                        if content:
                            content_mapping[content_key] = content
                else:
                    # 只有region - 一维映射
                    # 使用第一个OS名称（如果有的话）
                    fallback_os_name = all_os_names[0] if all_os_names else ""
                    content_key = region_id
                    content = self._find_content_by_mapping(soup, region_id, None, None, fallback_os_name)
                    if content:
                        content_mapping[content_key] = content
            
            logger.info(f"✓ 构建了 {len(content_mapping)} 个内容映射")
            return content_mapping
            
        except Exception as e:
            logger.info(f"⚠ 内容映射提取失败: {e}")
            return {}

    def _get_software_tab_content_id(self, software_id: str) -> Optional[str]:
        """
        根据软件ID获取对应的tabContent ID

        Args:
            software_id: 软件ID（如'App Windows', 'App Linux'）

        Returns:
            对应的tabContent ID（如'tabContent1', 'tabContent2'），如果未找到则返回None
        """
        try:
            # 重新检测筛选器以获取最新的软件选项信息
            with open(self.html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            soup = BeautifulSoup(html_content, 'html.parser')
            filter_analysis = self.filter_detector.detect_filters(soup)

            software_options = filter_analysis.get('software_options', [])
            for option in software_options:
                if option.get('value') == software_id:
                    data_href = option.get('href', '')
                    if data_href.startswith('#'):
                        target_id = data_href[1:]  # 移除#号
                        logger.info(f"🔗 软件'{software_id}'对应的tabContent ID: {target_id}")
                        return target_id
                    else:
                        logger.warning(f"⚠ 软件'{software_id}'的data-href格式异常: {data_href}")

            logger.warning(f"⚠ 未找到软件'{software_id}'对应的tabContent ID")
            return None

        except Exception as e:
            logger.error(f"❌ 获取软件tabContent ID失败: {e}")
            return None

    def _find_content_by_mapping(self, soup: BeautifulSoup,
                               region_id: Optional[str] = None,
                               software_id: Optional[str] = None,
                               tab_id: Optional[str] = None,
                               os_name: Optional[str] = None) -> str:
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

            # 2. 如果有software_id，根据软件选项的data-href查找对应的tabContent分组
            if not base_content and software_id:
                # 从filter_analysis中获取软件选项的data-href信息
                target_tab_content_id = self._get_software_tab_content_id(software_id)

                if target_tab_content_id:
                    # 根据data-href查找对应的tabContent
                    base_content = soup.find('div', id=target_tab_content_id)
                    if base_content:
                        logger.info(f"✓ 根据软件选项'{software_id}'的data-href找到内容组: {target_tab_content_id}")
                    else:
                        logger.warning(f"⚠ 未找到软件选项'{software_id}'对应的内容组: {target_tab_content_id}")

                # 如果还是没找到，回退到原来的逻辑
                if not base_content:
                    logger.info(f"🔄 回退到通用查找逻辑，软件ID: {software_id}")
                    content_groups = soup.find_all('div', class_='tab-panel')
                    for group in content_groups:
                        if hasattr(group, 'attrs') and group.attrs:
                            group_id = group.attrs.get('id', '')
                            if group_id and 'tabContent' in group_id:
                                base_content = group
                                logger.info(f"✓ 找到软件内容组（回退）: {group_id}")
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