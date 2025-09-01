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
        
        # 3.1 获取按软件组分类的tabs（用于修复映射构建）
        grouped_tabs = self.tab_detector.detect_grouped_tabs(soup)
        
        # 4. 提取复杂内容映射（传入按组分类的tabs）
        content_mapping = self._extract_complex_content_mapping(soup, filter_analysis, tab_analysis, grouped_tabs)
        
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
                                       tab_analysis: Dict[str, Any],
                                       grouped_tabs: Dict[str, List[Dict[str, Any]]] = None) -> Dict[str, Dict[str, str]]:
        """
        提取复杂页面的内容映射关系（带区域筛选和共享内容）
        
        Args:
            soup: BeautifulSoup对象
            filter_analysis: 筛选器分析结果
            tab_analysis: Tab分析结果
            
        Returns:
            增强的内容映射字典，包含具体内容和共享内容
            格式: {content_key: {"content": "...", "shared_content": "..."}}
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

            # 🔧 修复关键逻辑：使用按组分类的tabs而非全局tabs
            if software_options and grouped_tabs:
                logger.info("🎯 使用软件组内独立tabs进行映射（修复后逻辑）")
                
                # 按软件进行分组映射
                for software in software_options:
                    software_id = software.get("value", "")
                    current_os_name = software_to_os_mapping.get(software_id, all_os_names[0] if all_os_names else "")
                    
                    # 获取当前软件对应的tabContent ID
                    target_tab_content_id = self._get_software_tab_content_id(software_id)
                    if not target_tab_content_id:
                        logger.warning(f"⚠ 无法获取软件'{software_id}'对应的tabContent ID")
                        continue
                    
                    # 获取当前软件组内的独立tabs
                    software_tabs = grouped_tabs.get(target_tab_content_id, [])
                    logger.info(f"🔍 软件'{software_id}'({target_tab_content_id})有 {len(software_tabs)} 个独立tabs")
                    
                    for region in region_options:
                        region_id = region.get("value", "")
                        
                        if software_tabs:
                            # 只与当前软件组内的tabs组合
                            for tab in software_tabs:
                                tab_id = tab.get("href", "").replace("#", "")
                                content_key = f"{region_id}_{software_id}_{tab_id}"
                                
                                content_result = self._find_content_by_mapping(soup, region_id, software_id, tab_id, current_os_name)
                                if content_result and (content_result.get("content") or content_result.get("shared_content")):
                                    content_mapping[content_key] = content_result
                                    logger.info(f"✓ 创建映射: {content_key} (软件组内独立tab)")
                        else:
                            # 软件组内没有tabs，只做region + software二维映射
                            content_key = f"{region_id}_{software_id}"
                            content_result = self._find_content_by_mapping(soup, region_id, software_id, None, current_os_name)
                            if content_result and (content_result.get("content") or content_result.get("shared_content")):
                                content_mapping[content_key] = content_result
                                logger.info(f"✓ 创建映射: {content_key} (无tabs的软件组)")
                                
            else:
                # 🔄 回退逻辑：使用原来的映射方式（保持兼容性）
                logger.info("🔄 使用回退映射逻辑（原有逻辑）")
                
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
                                    content_result = self._find_content_by_mapping(soup, region_id, software_id, tab_id, current_os_name)
                                    if content_result and (content_result.get("content") or content_result.get("shared_content")):
                                        content_mapping[content_key] = content_result
                            else:
                                # 只有region + software - 二维映射
                                content_key = f"{region_id}_{software_id}"
                                content_result = self._find_content_by_mapping(soup, region_id, software_id, None, current_os_name)
                                if content_result and (content_result.get("content") or content_result.get("shared_content")):
                                    content_mapping[content_key] = content_result
                    elif category_tabs:
                        # 只有region + category tabs - 二维映射
                        # 使用第一个OS名称（如果有的话）
                        fallback_os_name = all_os_names[0] if all_os_names else ""
                        for tab in category_tabs:
                            tab_id = tab.get("href", "").replace("#", "")
                            content_key = f"{region_id}_{tab_id}"
                            content_result = self._find_content_by_mapping(soup, region_id, None, tab_id, fallback_os_name)
                            if content_result and (content_result.get("content") or content_result.get("shared_content")):
                                content_mapping[content_key] = content_result
                    else:
                        # 只有region - 一维映射
                        # 使用第一个OS名称（如果有的话）
                        fallback_os_name = all_os_names[0] if all_os_names else ""
                        content_key = region_id
                        content_result = self._find_content_by_mapping(soup, region_id, None, None, fallback_os_name)
                        if content_result and (content_result.get("content") or content_result.get("shared_content")):
                            content_mapping[content_key] = content_result
            
            logger.info(f"✓ 构建了 {len(content_mapping)} 个内容映射")
            return content_mapping
            
        except Exception as e:
            logger.info(f"⚠ 内容映射提取失败: {e}")
            return {}

    def _extract_shared_content_for_tab_container(self, soup: BeautifulSoup, container_id: str) -> str:
        """
        提取指定Tab容器中的共享内容区域
        
        共享内容区域位于Tab导航之后、具体Tab内容之前，通常包含：
        - 定价说明标题 
        - 计费模式说明
        - 价格总览表
        - 重要注释和说明
        
        Args:
            soup: BeautifulSoup对象
            container_id: Tab容器ID（如'tabContent1', 'tabContent2'等）
            
        Returns:
            共享内容区域的HTML字符串
        """
        logger.info(f"🔍 提取Tab容器 '{container_id}' 的共享内容区域...")
        
        try:
            # 查找指定的Tab容器
            tab_container = soup.find('div', id=container_id)
            if not tab_container:
                logger.warning(f"⚠ 未找到Tab容器: {container_id}")
                return ""
            
            shared_content = ""
            
            # 方法1: 查找Tab导航后、第一个tab-panel前的内容
            # 这是最常见的共享内容位置
            tab_content_div = tab_container.find('div', class_='tab-content')
            if tab_content_div:
                # 遍历tab-content下的直接子元素
                for child in tab_content_div.children:
                    if hasattr(child, 'name') and child.name:
                        # 如果遇到第一个tab-panel，停止收集
                        if child.name == 'div' and child.get('class') and 'tab-panel' in child.get('class'):
                            break
                        # 否则收集这个元素作为共享内容
                        shared_content += str(child)
                        
                        # 特别处理：查找重要的定价表格和说明
                        if child.name in ['h2', 'h3', 'table', 'div']:
                            element_text = child.get_text(strip=True).lower()
                            if any(keyword in element_text for keyword in ['定价详细信息', 'dbu价格', '现用现付', '价格总览']):
                                logger.info(f"✓ 找到重要共享内容元素: {child.name} - {element_text[:50]}...")
            
            # 方法2: 如果没找到tab-content结构，查找容器内非tab-panel的直接内容
            if not shared_content:
                logger.info(f"🔄 使用备选方法提取 '{container_id}' 的共享内容...")
                
                # 查找容器内的直接子元素，但跳过导航和tab-panel
                for child in tab_container.children:
                    if hasattr(child, 'name') and child.name:
                        # 跳过导航相关元素
                        if child.get('class'):
                            classes = ' '.join(child.get('class', []))
                            if any(nav_class in classes for nav_class in ['category-container', 'tab-nav', 'category-tabs']):
                                continue
                        
                        # 如果是tab-panel，停止收集（开始进入具体tab内容）
                        if child.name == 'div' and child.get('class') and 'tab-panel' in child.get('class'):
                            break
                            
                        # 收集非导航、非tab-panel的内容作为共享内容
                        if child.name in ['h1', 'h2', 'h3', 'p', 'div', 'table', 'ul', 'ol']:
                            shared_content += str(child)
                            logger.info(f"✓ 备选方法收集共享内容: {child.name}")
            
            # 内容质量验证
            if shared_content:
                # 简单清理
                shared_content = clean_html_content(shared_content)
                content_text = BeautifulSoup(shared_content, 'html.parser').get_text(strip=True)
                
                if len(content_text) > 20:  # 确保不是空内容
                    logger.info(f"✅ 成功提取 '{container_id}' 共享内容，长度: {len(content_text)} 字符")
                    return shared_content
                else:
                    logger.warning(f"⚠ '{container_id}' 共享内容过短，可能提取不完整")
            else:
                logger.warning(f"⚠ 未在 '{container_id}' 中找到共享内容区域")
            
            return shared_content
            
        except Exception as e:
            logger.error(f"❌ 提取 '{container_id}' 共享内容失败: {e}")
            return ""

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
                               os_name: Optional[str] = None) -> Dict[str, str]:
        """
        根据映射关系查找对应内容（支持区域表格筛选和共享内容提取）

        Args:
            soup: BeautifulSoup对象
            region_id: 区域ID
            software_id: 软件ID
            tab_id: Tab ID
            os_name: OS名称，用于区域筛选

        Returns:
            包含具体内容和共享内容的字典: {"content": "...", "shared_content": "..."}
        """
        try:
            # 首先从原始soup中找到基础内容
            base_content = None
            main_container_id = None  # 跟踪主容器ID以便提取共享内容

            # 1. 如果有tab_id，优先查找tab对应内容
            if tab_id:
                base_content = soup.find('div', id=tab_id)
                if base_content:
                    logger.info(f"✓ 找到tab内容: {tab_id}")
                    # 推断主容器ID (如tabContent1-1的主容器是tabContent1)
                    if '-' in tab_id:
                        main_container_id = tab_id.split('-')[0]

            # 2. 如果有software_id，根据软件选项的data-href查找对应的tabContent分组
            if not base_content and software_id:
                # 从filter_analysis中获取软件选项的data-href信息
                target_tab_content_id = self._get_software_tab_content_id(software_id)
                main_container_id = target_tab_content_id  # 保存主容器ID

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
                                main_container_id = group_id
                                logger.info(f"✓ 找到软件内容组（回退）: {group_id}")
                                break
            
            # 3. 默认返回主要内容区域
            if not base_content:
                base_content = soup.find('div', class_='technical-azure-selector')
                if base_content:
                    logger.info("✓ 使用主要内容区域")
                    main_container_id = "technical-azure-selector"  # 标记为技术选择器
            
            if not base_content:
                logger.warning("⚠ 未找到任何基础内容")
                return {"content": "", "shared_content": ""}
            
            # 提取共享内容（如果有主容器ID）
            shared_content = ""
            if main_container_id and main_container_id != "technical-azure-selector":
                shared_content = self._extract_shared_content_for_tab_container(soup, main_container_id)
            
            # 准备返回的具体内容
            final_content = ""
            
            # 应用区域筛选（如果有region_id和os_name）
            if region_id and os_name:
                logger.info(f"🔍 对内容应用区域筛选: region={region_id}, os={os_name}")
                # 创建包含找到内容的临时soup
                temp_soup = BeautifulSoup(str(base_content), 'html.parser')
                # 应用区域筛选
                filtered_soup = self.region_processor.apply_region_filtering(temp_soup, region_id, os_name)
                final_content = str(filtered_soup)
            else:
                # 没有区域信息，直接返回原始内容
                if not region_id:
                    logger.info("ℹ 无区域ID，跳过区域筛选")
                if not os_name:
                    logger.info("ℹ 无OS名称，跳过区域筛选")
                final_content = str(base_content)
            
            return {
                "content": final_content,
                "shared_content": shared_content
            }
            
        except Exception as e:
            logger.info(f"⚠ 内容查找失败: {e}")
            return {"content": "", "shared_content": ""}

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