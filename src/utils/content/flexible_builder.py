#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flexible JSON构建器
构建符合CMS FlexibleContentPage Schema 1.1的数据结构，处理筛选器配置和内容组织逻辑
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

from src.core.logging import get_logger
from src.utils.html.cleaner import clean_html_content

logger = get_logger(__name__)


class FlexibleBuilder:
    """Flexible JSON构建器 - 构建符合CMS FlexibleContentPage Schema 1.1的数据结构"""

    def __init__(self):
        """初始化flexible JSON构建器"""
        logger.info("🔧 初始化FlexibleBuilder")

    def build_flexible_page(self, 
                           base_metadata: Dict[str, Any],
                           common_sections: List[Dict[str, str]],
                           strategy_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建完整的flexible JSON页面
        
        Args:
            base_metadata: 基础元数据
            common_sections: 通用sections列表
            strategy_content: 策略特定内容
            
        Returns:
            符合Schema 1.1的flexible JSON数据
        """
        logger.info("🏗️ 构建完整的flexible JSON页面...")
        
        flexible_data = {
            # 基础元数据 (适配ContentExtractor的键名)
            "title": base_metadata.get("Title", ""),
            "metaTitle": base_metadata.get("MetaTitle", ""),
            "metaDescription": base_metadata.get("MetaDescription", ""),
            "metaKeywords": base_metadata.get("MetaKeywords", ""),
            "slug": base_metadata.get("Slug", ""),
            "language": base_metadata.get("Language", "zh-cn"),
            
            # 主要内容
            "baseContent": strategy_content.get("baseContent", ""),
            "contentGroups": strategy_content.get("contentGroups", []),
            
            # 通用sections
            "commonSections": common_sections,
            
            # 页面配置
            "pageConfig": self._build_page_config(strategy_content, base_metadata),
        }
        
        logger.info(f"✓ 构建完成，包含 {len(common_sections)} 个commonSections, {len(strategy_content.get('contentGroups', []))} 个contentGroups")
        return flexible_data

    def build_simple_content_groups(self, base_content: str) -> List[Dict[str, Any]]:
        """
        构建简单内容组（用于SimpleStaticStrategy）
        
        Args:
            base_content: 基础内容HTML
            
        Returns:
            contentGroups列表（对简单页面通常为空）
        """
        logger.info("📋 构建简单内容组...")
        
        # 简单页面通常不需要contentGroups，内容放在baseContent中
        return []

    def build_region_content_groups(self, region_content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        构建地区内容组（用于RegionFilterStrategy）
        
        Args:
            region_content: 地区内容映射
            
        Returns:
            contentGroups列表
        """
        logger.info("🌍 构建地区内容组...")
        
        content_groups = []
        
        # 地区ID到显示名称的映射
        region_name_mapping = {
            "north-china": "中国北部",
            "north-china2": "中国北部 2",
            "north-china3": "中国北部 3",
            "east-china": "中国东部",
            "east-china2": "中国东部 2",
            "east-china3": "中国东部 3"
        }
        
        for region_id, content in region_content.items():
            if content:  # 只添加有内容的地区
                group_name = region_name_mapping.get(region_id, region_id.replace('-', ' ').title())
                
                content_group = {
                    "groupName": group_name,
                    "filterCriteriaJson": json.dumps([{
                        "filterKey": "region",
                        "matchValues": [region_id]
                    }], ensure_ascii=False),
                    "content": content if isinstance(content, str) else str(content),
                    "sortOrder": len(content_groups) + 1,
                    "isActive": True
                }
                
                content_groups.append(content_group)
                logger.info(f"✓ 添加地区内容组: {group_name}")
        
        logger.info(f"✓ 构建了 {len(content_groups)} 个地区内容组")
        return content_groups

    def build_complex_content_groups(self, 
                                   filter_analysis: Dict[str, Any],
                                   tab_analysis: Dict[str, Any],
                                   content_mapping: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        构建复杂内容组（用于ComplexContentStrategy）
        
        Args:
            filter_analysis: 筛选器分析结果
            tab_analysis: Tab分析结果
            content_mapping: 内容映射
            
        Returns:
            contentGroups列表
        """
        logger.info("🔧 构建复杂内容组...")
        
        content_groups = []
        
        # 根据筛选器和tab组合构建多维度内容组
        region_options = filter_analysis.get("region_options", [])
        software_options = filter_analysis.get("software_options", [])
        category_tabs = tab_analysis.get("category_tabs", [])
        
        # 构建多维度组合
        for region in region_options:
            region_id = region.get("value", "")
            region_name = region.get("label", region_id)
            
            if software_options:
                # 有软件筛选器的情况
                for software in software_options:
                    software_id = software.get("value", "")
                    software_name = software.get("label", software_id)
                    
                    if category_tabs:
                        # 有category tabs的情况
                        for tab in category_tabs:
                            tab_id = tab.get("href", "").replace("#", "")
                            tab_name = tab.get("label", tab_id)
                            
                            group_name = f"{region_name} - {software_name} - {tab_name}"
                            content_key = f"{region_id}_{software_id}_{tab_id}"
                            
                            if content_key in content_mapping:
                                content_result = content_mapping[content_key]
                                
                                content_group = {
                                    "groupName": group_name,
                                    "filterCriteriaJson": json.dumps([
                                        {"filterKey": "region", "matchValues": [region_id]},
                                        {"filterKey": "software", "matchValues": [software_id]},
                                        {"filterKey": "category", "matchValues": [tab_id]}
                                    ], ensure_ascii=False),
                                    "content": clean_html_content(content_result.get("content", "")),
                                    "sortOrder": len(content_groups) + 1,
                                    "isActive": True
                                }
                                
                                # 添加共享内容字段（如果存在）
                                shared_content = content_result.get("shared_content", "")
                                if shared_content:
                                    content_group["sharedContent"] = clean_html_content(shared_content)
                                    logger.info(f"✓ 为内容组 '{group_name}' 添加了共享内容")
                                content_groups.append(content_group)
                    else:
                        # 只有软件筛选器，无category tabs
                        group_name = f"{region_name} - {software_name}"
                        content_key = f"{region_id}_{software_id}"
                        
                        if content_key in content_mapping:
                            content_result = content_mapping[content_key]
                            
                            content_group = {
                                "groupName": group_name,
                                "filterCriteriaJson": json.dumps([
                                    {"filterKey": "region", "matchValues": [region_id]},
                                    {"filterKey": "software", "matchValues": [software_id]}
                                ], ensure_ascii=False),
                                "content": clean_html_content(content_result.get("content", "")),
                                "sortOrder": len(content_groups) + 1,
                                "isActive": True
                            }
                            
                            # 添加共享内容字段（如果存在）
                            shared_content = content_result.get("shared_content", "")
                            if shared_content:
                                content_group["sharedContent"] = clean_html_content(shared_content)
                                logger.info(f"✓ 为内容组 '{group_name}' 添加了共享内容")
                            content_groups.append(content_group)
            elif category_tabs:
                # 只有region和category tabs，无软件筛选器
                for tab in category_tabs:
                    tab_id = tab.get("href", "").replace("#", "")
                    tab_name = tab.get("label", tab_id)
                    
                    group_name = f"{region_name} - {tab_name}"
                    content_key = f"{region_id}_{tab_id}"
                    
                    if content_key in content_mapping:
                        content_result = content_mapping[content_key]
                        
                        content_group = {
                            "groupName": group_name,
                            "filterCriteriaJson": json.dumps([
                                {"filterKey": "region", "matchValues": [region_id]},
                                {"filterKey": "category", "matchValues": [tab_id]}
                            ], ensure_ascii=False),
                            "content": clean_html_content(content_result.get("content", "")),
                            "sortOrder": len(content_groups) + 1,
                            "isActive": True
                        }
                        
                        # 添加共享内容字段（如果存在）
                        shared_content = content_result.get("shared_content", "")
                        if shared_content:
                            content_group["sharedContent"] = clean_html_content(shared_content)
                            logger.info(f"✓ 为内容组 '{group_name}' 添加了共享内容")
                        content_groups.append(content_group)
        
        logger.info(f"✓ 构建了 {len(content_groups)} 个复杂内容组")
        return content_groups

    # def _determine_page_type(self, strategy_type: str, filter_analysis: Dict[str, Any] = None, tab_analysis: Dict[str, Any] = None) -> str:
    #     """
    #     根据策略类型和分析结果确定页面类型
    #
    #     Args:
    #         strategy_type: 策略类型
    #         filter_analysis: 筛选器分析结果
    #         tab_analysis: Tab分析结果
    #
    #     Returns:
    #         页面类型字符串
    #     """
    #     # 策略类型到页面类型的映射
    #     strategy_to_page_type = {
    #         "simple_static": "Simple",
    #         "region_filter": "RegionFilter",
    #         "complex": "ComplexFilter",
    #         "tab_content": "TabFilter",
    #         "region_tab": "RegionTabFilter",
    #         "multi_filter": "MultiFilter"
    #     }
    #
    #     return strategy_to_page_type.get(strategy_type, "Simple")
    
    # def _extract_display_title(self, base_metadata: Dict[str, Any] = None) -> str:
    #     """
    #     提取显示标题
    #
    #     Args:
    #         base_metadata: 基础元数据
    #
    #     Returns:
    #         显示标题字符串
    #     """
    #     if not base_metadata:
    #         return ""
    #
    #     title = base_metadata.get("Title", "")
    #     if title:
    #         # 清理标题，移除常见的重复模式
    #         import re
    #         title = re.sub(r'\s*[-–]\s*Azure[\w\s]*$', '', title.strip())
    #         title = re.sub(r'\s*定价\s*$', '', title.strip())
    #         return title.strip()
    #
    #     return ""
    
    # def _extract_left_nav_identifier(self, base_metadata: Dict[str, Any] = None) -> str:
    #     """
    #     提取左侧导航标识符
    #
    #     Args:
    #         base_metadata: 基础元数据
    #
    #     Returns:
    #         导航标识符字符串
    #     """
    #     if not base_metadata:
    #         return ""
    #
    #     # 优先使用MSServiceName
    #     ms_service_name = base_metadata.get("MSServiceName", "")
    #     if ms_service_name:
    #         return ms_service_name
    #
    #     # 从Slug推导
    #     slug = base_metadata.get("Slug", "")
    #     if slug:
    #         return slug
    #
    #     # 从source_file路径推导产品名称
    #     source_file = base_metadata.get("source_file", "")
    #     if source_file:
    #         from pathlib import Path
    #         filename = Path(source_file).stem
    #         if filename.endswith('-index'):
    #             return filename[:-6]
    #         return filename
    #
    #     return ""
    
    def _build_page_config(self, strategy_content: Dict[str, Any], base_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于策略类型构建正确的页面配置
        
        Args:
            strategy_content: 策略特定内容，包含strategy_type和filter_analysis
            base_metadata: 基础元数据，用于填充displayTitle和leftNavigationIdentifier
            
        Returns:
            正确的pageConfig字典
        """
        strategy_type = strategy_content.get("strategy_type", "unknown")
        filter_analysis = strategy_content.get("filter_analysis", {})
        tab_analysis = strategy_content.get("tab_analysis", {})
        
        # 基础配置 (从base_metadata中提取正确的值)
        page_config = {
            "displayTitle": base_metadata.get("Title", ""),
            "pageIcon": "{base_url}/Static/Favicon/favicon.ico",
            "leftNavigationIdentifier": base_metadata.get("MSServiceName", ""),
        }
        
        # 根据策略类型设置pageType和筛选器配置
        if strategy_type == "simple_static":
            page_config.update({
                "pageType": "Simple",
                "enableFilters": False,
                "filtersJsonConfig": json.dumps({"filterDefinitions": []}, ensure_ascii=False)
            })
        elif strategy_type == "region_filter":
            page_config.update({
                "pageType": "RegionFilter",
                "enableFilters": True,
                "filtersJsonConfig": self._build_filters_json_config(filter_analysis)
            })
        elif strategy_type == "complex":
            page_config.update({
                "pageType": "ComplexFilter",
                "enableFilters": True,
                "filtersJsonConfig": self._build_filters_json_config(filter_analysis, tab_analysis)
            })
        else:
            # 默认配置
            page_config.update({
                "pageType": "Simple",
                "enableFilters": False,
                "filtersJsonConfig": json.dumps({"filterDefinitions": []}, ensure_ascii=False)
            })
        
        return page_config

    def _build_filters_json_config(self, filter_analysis: Dict[str, Any] = None, tab_analysis: Dict[str, Any] = None) -> str:
        """
        基于筛选器分析构建filtersJsonConfig
        
        Args:
            filter_analysis: FilterDetector的分析结果
            tab_analysis: TabDetector的分析结果
            
        Returns:
            JSON格式的筛选器配置字符串
        """
        try:
            filter_definitions = []
            
            # 处理区域筛选器 (适配FilterDetector的平铺结构)
            if filter_analysis.get("region_visible", False):
                region_options_data = filter_analysis.get("region_options", [])
                region_options = []
                
                for option in region_options_data:
                    region_options.append({
                        "value": option.get("value", ""),
                        "label": option.get("label", ""),
                        "href": option.get("href", "")
                    })
                
                filter_definitions.append({
                    "filterKey": "region",
                    "filterType": "dropdown",
                    "displayName": "区域",
                    "options": region_options
                })
            
            # 处理软件类别筛选器 (适配FilterDetector的平铺结构)
            if filter_analysis.get("software_visible", False):
                software_options_data = filter_analysis.get("software_options", [])
                software_options = []
                
                for option in software_options_data:
                    software_options.append({
                        "value": option.get("value", ""),
                        "label": option.get("label", ""),
                        "href": option.get("href", "")
                    })
                
                filter_definitions.append({
                    "filterKey": "software",
                    "filterType": "dropdown",
                    "displayName": "软件类别", 
                    "options": software_options
                })

            # 处理Tab选项卡 Category Tabs (如果有)
            if tab_analysis and tab_analysis.get("category_tabs"):
                category_options = [
                    {
                        "value": tab.get("href", "").replace("#", ""),
                        "label": tab.get("label", "")
                    }
                    for tab in tab_analysis.get("category_tabs", [])
                ]

                if category_options:
                    filter_definitions.append({
                        "filterKey": "category",
                        "filterType": "tab",
                        "displayName": "类别",
                        "options": category_options
                    })
            
            filters_config = {
                "filterDefinitions": filter_definitions
            }
            
            return json.dumps(filters_config, ensure_ascii=False)
            
        except Exception as e:
            logger.warning(f"⚠️ 构建筛选器配置失败: {e}")
            return json.dumps({"filterDefinitions": []}, ensure_ascii=False)
