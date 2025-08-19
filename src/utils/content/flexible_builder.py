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
            # 基础元数据
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
            "pageConfig": strategy_content.get("pageConfig", self._get_default_page_config()),
            
            # 元数据
            "extractionMetadata": {
                "extractorVersion": "flexible_v1.0",
                "extractionTimestamp": datetime.now().isoformat(),
                "strategyUsed": strategy_content.get("strategy_type", "unknown"),
                "schemaVersion": "1.1"
            }
        }
        
        logger.info(f"✓ 构建完成，包含 {len(common_sections)} 个commonSections，{len(strategy_content.get('contentGroups', []))} 个contentGroups")
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
                    "content": content if isinstance(content, str) else str(content)
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
                                content_group = {
                                    "groupName": group_name,
                                    "filterCriteriaJson": json.dumps([
                                        {"filterKey": "region", "matchValues": [region_id]},
                                        {"filterKey": "software", "matchValues": [software_id]},
                                        {"filterKey": "category", "matchValues": [tab_name]}
                                    ], ensure_ascii=False),
                                    "content": clean_html_content(content_mapping[content_key])
                                }
                                content_groups.append(content_group)
                    else:
                        # 只有软件筛选器，无category tabs
                        group_name = f"{region_name} - {software_name}"
                        content_key = f"{region_id}_{software_id}"
                        
                        if content_key in content_mapping:
                            content_group = {
                                "groupName": group_name,
                                "filterCriteriaJson": json.dumps([
                                    {"filterKey": "region", "matchValues": [region_id]},
                                    {"filterKey": "software", "matchValues": [software_id]}
                                ], ensure_ascii=False),
                                "content": clean_html_content(content_mapping[content_key])
                            }
                            content_groups.append(content_group)
            elif category_tabs:
                # 只有region和category tabs，无软件筛选器
                for tab in category_tabs:
                    tab_id = tab.get("href", "").replace("#", "")
                    tab_name = tab.get("label", tab_id)
                    
                    group_name = f"{region_name} - {tab_name}"
                    content_key = f"{region_id}_{tab_id}"
                    
                    if content_key in content_mapping:
                        content_group = {
                            "groupName": group_name,
                            "filterCriteriaJson": json.dumps([
                                {"filterKey": "region", "matchValues": [region_id]},
                                {"filterKey": "category", "matchValues": [tab_name]}
                            ], ensure_ascii=False),
                            "content": clean_html_content(content_mapping[content_key])
                        }
                        content_groups.append(content_group)
        
        logger.info(f"✓ 构建了 {len(content_groups)} 个复杂内容组")
        return content_groups

    def build_page_config(self, 
                         filter_analysis: Dict[str, Any],
                         tab_analysis: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        构建页面配置
        
        Args:
            filter_analysis: 筛选器分析结果
            tab_analysis: Tab分析结果（可选）
            
        Returns:
            pageConfig字典
        """
        logger.info("⚙️ 构建页面配置...")
        
        # 检查是否有可见的筛选器
        has_visible_filters = (
            filter_analysis.get("region_visible", False) or 
            filter_analysis.get("software_visible", False)
        )
        
        if not has_visible_filters:
            return self._get_default_page_config()
        
        # 构建筛选器定义
        filter_definitions = []
        
        # 地区筛选器
        if filter_analysis.get("region_visible", False):
            region_options = filter_analysis.get("region_options", [])
            if region_options:
                filter_definitions.append({
                    "filterKey": "region",
                    "displayName": "地区",
                    "filterType": "dropdown",
                    "options": [
                        {
                            "value": option.get("value", ""),
                            "label": option.get("label", ""),
                            "href": option.get("href", "")
                        }
                        for option in region_options
                    ]
                })
        
        # 软件筛选器
        if filter_analysis.get("software_visible", False):
            software_options = filter_analysis.get("software_options", [])
            if software_options:
                filter_definitions.append({
                    "filterKey": "software",
                    "displayName": "软件类别",
                    "filterType": "dropdown",
                    "options": [
                        {
                            "value": option.get("value", ""),
                            "label": option.get("label", ""),
                            "href": option.get("href", "")
                        }
                        for option in software_options
                    ]
                })
        
        # Category tabs（如果有）
        if tab_analysis and tab_analysis.get("category_tabs"):
            category_options = [
                {
                    "value": tab.get("href", "").replace("#", ""),
                    "label": tab.get("label", ""),
                    "href": tab.get("href", "")
                }
                for tab in tab_analysis.get("category_tabs", [])
            ]
            
            if category_options:
                filter_definitions.append({
                    "filterKey": "category",
                    "displayName": "类别",
                    "filterType": "tabs",
                    "options": category_options
                })
        
        filters_config = {
            "filterDefinitions": filter_definitions
        }
        
        page_config = {
            "enableFilters": True,
            "filtersJsonConfig": json.dumps(filters_config, ensure_ascii=False)
        }
        
        logger.info(f"✓ 构建页面配置，包含 {len(filter_definitions)} 个筛选器")
        return page_config

    def _get_default_page_config(self) -> Dict[str, Any]:
        """
        获取默认页面配置（无筛选器）
        
        Returns:
            默认pageConfig字典
        """
        return {
            "enableFilters": False,
            "filtersJsonConfig": json.dumps({"filterDefinitions": []}, ensure_ascii=False)
        }