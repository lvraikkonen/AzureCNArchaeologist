#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlexibleContent导出器
负责将提取的数据导出为CMS FlexibleContentPage JSON Schema 1.1格式
支持Simple和RegionFilter页面类型，优先满足CMS团队高优先级需求
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

class PageType(Enum):
    """页面类型枚举"""
    SIMPLE = "Simple"
    REGION_FILTER = "RegionFilter" 
    COMPLEX_FILTER = "ComplexFilter"

class SectionType(Enum):
    """公共区块类型枚举"""
    BANNER = "Banner"
    PRODUCT_DESCRIPTION = "ProductDescription"
    QA = "Qa"

class FlexibleContentExporter:
    """FlexibleContentPage JSON Schema 1.1 导出器"""
    
    def __init__(self, output_dir: str = "output"):
        """
        初始化FlexibleContent导出器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 区域映射配置
        self.region_mapping = {
            "NorthChinaContent": {
                "key": "north-china",
                "label": "中国北部",
                "order": 1
            },
            "NorthChina2Content": {
                "key": "north-china-2",
                "label": "中国北部 2",
                "order": 2
            },
            "NorthChina3Content": {
                "key": "north-china-3", 
                "label": "中国北部 3",
                "order": 3
            },
            "EastChinaContent": {
                "key": "east-china",
                "label": "中国东部",
                "order": 4
            },
            "EastChina2Content": {
                "key": "east-china-2",
                "label": "中国东部 2", 
                "order": 5
            },
            "EastChina3Content": {
                "key": "east-china-3",
                "label": "中国东部 3",
                "order": 6
            }
        }
    
    def export_flexible_content(self, data: Dict[str, Any], product_name: str) -> str:
        """
        导出为FlexibleContentPage格式
        
        Args:
            data: 提取的原始数据
            product_name: 产品名称
            
        Returns:
            str: 导出文件路径
        """
        # 生成时间戳文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{product_name}_flexible_content_{timestamp}.json"
        filepath = self.output_dir / filename
        
        # 转换为FlexibleContentPage格式
        flexible_data = self._convert_to_flexible_format(data, product_name)
        
        # 写入JSON文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(flexible_data, f, ensure_ascii=False, indent=2)
        
        return str(filepath)
    
    def _convert_to_flexible_format(self, data: Dict[str, Any], product_name: str) -> Dict[str, Any]:
        """
        将提取数据转换为FlexibleContentPage格式
        
        Args:
            data: 原始提取数据
            product_name: 产品名称
            
        Returns:
            Dict[str, Any]: FlexibleContentPage格式数据
        """
        # 判断页面类型
        page_type = self._determine_page_type(data)
        
        # 生成基础页面信息
        flexible_data = {
            "title": self._clean_title(data.get("title", "")),
            "slug": data.get("slug", product_name),
            "metaTitle": data.get("metaTitle", ""),
            "metaDescription": data.get("metaDescription", ""),
            "metaKeywords": data.get("metaKeywords", ""),
            "pageConfig": self._build_page_config(data, page_type, product_name),
            "commonSections": self._build_common_sections(data),
            "baseContent": "",
            "contentGroups": []
        }
        
        # 根据页面类型处理内容
        if page_type == PageType.SIMPLE:
            flexible_data["baseContent"] = self._build_simple_base_content(data)
            
        elif page_type == PageType.REGION_FILTER:
            flexible_data["contentGroups"] = self._build_region_content_groups(data)
            
        elif page_type == PageType.COMPLEX_FILTER:
            # 复杂筛选器类型：如果data中已有contentGroups，直接使用；否则构建
            if "contentGroups" in data and data["contentGroups"]:
                flexible_data["contentGroups"] = data["contentGroups"]
            else:
                flexible_data["contentGroups"] = self._build_complex_content_groups(data)
            # 更新pageConfig为复杂类型
            flexible_data["pageConfig"]["enableFilters"] = True
            if "pageConfig" in data and data["pageConfig"]:
                flexible_data["pageConfig"].update(data["pageConfig"])
            
        return flexible_data
    
    def _determine_page_type(self, data: Dict[str, Any]) -> PageType:
        """
        判断页面类型
        
        Args:
            data: 提取数据
            
        Returns:
            PageType: 页面类型
        """
        # 检查是否是复杂内容类型（有contentGroups或者策略类型为complex）
        strategy_type = data.get("strategy_type", "")
        if strategy_type == "complex_content" or data.get("contentGroups"):
            return PageType.COMPLEX_FILTER
        
        # 检查是否有区域内容
        has_region = data.get("HasRegion", False)
        
        # 检查区域内容字段
        region_fields = ["NorthChinaContent", "EastChinaContent", "NorthChina2Content", 
                        "EastChina2Content", "NorthChina3Content", "EastChina3Content"]
        
        has_region_content = any(data.get(field, "").strip() for field in region_fields)
        
        if has_region or has_region_content:
            return PageType.REGION_FILTER
        else:
            return PageType.SIMPLE
    
    def _clean_title(self, title: str) -> str:
        """
        清理标题，移除英文重复部分
        
        Args:
            title: 原始标题
            
        Returns:
            str: 清理后的标题
        """
        # 移除常见的重复英文模式，如 "API 管理API Management"
        title = re.sub(r'([A-Za-z\s]+)([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s*$', r'\1', title.strip())
        return title.strip()
    
    def _build_page_config(self, data: Dict[str, Any], page_type: PageType, product_name: str) -> Dict[str, Any]:
        """
        构建页面配置
        
        Args:
            data: 提取数据
            page_type: 页面类型
            product_name: 产品名称
            
        Returns:
            Dict[str, Any]: 页面配置
        """
        config = {
            "pageType": page_type.value,
            "displayTitle": self._clean_title(data.get("Title", "")),
            "pageIcon": "{base_url}/Static/Favicon/favicon.ico",
            "leftNavigationIdentifier": data.get("MSServiceName", product_name)
        }
        
        # 根据页面类型设置筛选器
        if page_type == PageType.REGION_FILTER:
            config["enableFilters"] = True
            config["filtersJsonConfig"] = self._build_region_filters_config(data)
        elif page_type == PageType.COMPLEX_FILTER:
            config["enableFilters"] = True
            # 如果数据中有预构建的filtersJsonConfig，使用它；否则构建默认配置
            if "pageConfig" in data and "filtersJsonConfig" in data["pageConfig"]:
                config["filtersJsonConfig"] = data["pageConfig"]["filtersJsonConfig"]
            else:
                config["filtersJsonConfig"] = self._build_complex_filters_config(data)
        else:
            config["enableFilters"] = False
            
        return config
    
    def _build_region_filters_config(self, data: Dict[str, Any]) -> str:
        """
        构建区域筛选器配置
        
        Args:
            data: 提取数据
            
        Returns:
            str: 筛选器配置JSON字符串
        """
        # 获取可用区域
        available_regions = []
        default_region = None
        
        for field_name, region_info in self.region_mapping.items():
            if data.get(field_name, "").strip():
                region_option = {
                    "value": region_info["key"],
                    "label": region_info["label"],
                    "isDefault": False,
                    "order": region_info["order"],
                    "isActive": True
                }
                available_regions.append(region_option)
                
                # 设置第一个有内容的区域为默认
                if default_region is None:
                    default_region = region_info["key"]
                    region_option["isDefault"] = True
        
        # 按order排序
        available_regions.sort(key=lambda x: x["order"])
        
        filters_config = {
            "filterDefinitions": [
                {
                    "filterKey": "region",
                    "filterName": "地区",
                    "filterType": "Dropdown",
                    "isRequired": False,
                    "defaultValue": default_region or "north-china",
                    "order": 1,
                    "options": available_regions
                }
            ]
        }
        
        return json.dumps(filters_config, ensure_ascii=False, separators=(',', ':'))
    
    def _build_complex_filters_config(self, data: Dict[str, Any]) -> str:
        """
        构建复杂筛选器配置 - 从实际检测结果获取选项
        
        Args:
            data: 提取数据
            
        Returns:
            str: 筛选器配置JSON字符串
        """
        filter_definitions = []
        
        # 从complexity_analysis中获取检测到的筛选器信息
        complexity_analysis = data.get("complexity_analysis", {})
        
        # 如果有filter_analysis或tab_analysis，从中提取实际选项
        if "filter_analysis" in data:
            filter_analysis = data["filter_analysis"]
            
            # 构建区域筛选器（如果存在）
            if filter_analysis.get("has_region", False):
                region_options = filter_analysis.get("region_options", [])
                if region_options:
                    region_filter_options = []
                    default_region = None
                    
                    for i, option in enumerate(region_options):
                        region_option = {
                            "value": option.get("value", f"region-{i}"),
                            "label": option.get("label", option.get("text", f"区域{i+1}")),
                            "order": i + 1
                        }
                        region_filter_options.append(region_option)
                        
                        # 设置第一个为默认
                        if default_region is None:
                            default_region = region_option["value"]
                    
                    filter_definitions.append({
                        "filterKey": "region",
                        "filterName": "地区",
                        "filterType": "Dropdown",
                        "isRequired": False,
                        "defaultValue": default_region,
                        "order": 1,
                        "options": region_filter_options
                    })
            
            # 构建软件类别筛选器（如果存在且可见）
            if filter_analysis.get("has_software", False):
                software_options = filter_analysis.get("software_options", [])
                if software_options:
                    software_filter_options = []
                    default_software = None
                    
                    for i, option in enumerate(software_options):
                        software_option = {
                            "value": option.get("value", f"software-{i}"),
                            "label": option.get("label", option.get("text", f"软件{i+1}")),
                            "order": i + 1
                        }
                        software_filter_options.append(software_option)
                        
                        if default_software is None:
                            default_software = software_option["value"]
                    
                    filter_definitions.append({
                        "filterKey": "software",
                        "filterName": "软件类别",
                        "filterType": "Dropdown",
                        "isRequired": False,
                        "defaultValue": default_software,
                        "order": 2,
                        "options": software_filter_options
                    })
        
        # 构建category筛选器（如果有tab分析结果）
        if "tab_analysis" in data:
            tab_analysis = data["tab_analysis"]
            
            if tab_analysis.get("has_tabs", False):
                category_tabs = tab_analysis.get("category_tabs", [])
                if category_tabs:
                    category_filter_options = []
                    default_category = None
                    
                    for i, tab in enumerate(category_tabs):
                        # 从tab的href或其他属性提取value
                        tab_href = tab.get("href", "").replace("#", "")
                        tab_value = tab.get("value", tab_href or f"category-{i}")
                        tab_label = tab.get("text", tab.get("label", f"类别{i+1}"))
                        
                        category_option = {
                            "value": tab_value,
                            "label": tab_label,
                            "order": i + 1
                        }
                        category_filter_options.append(category_option)
                        
                        if default_category is None:
                            default_category = category_option["value"]
                    
                    filter_definitions.append({
                        "filterKey": "category",
                        "filterName": "类别",
                        "filterType": "Dropdown",
                        "isRequired": False,
                        "defaultValue": default_category,
                        "order": len(filter_definitions) + 1,
                        "options": category_filter_options
                    })
        
        filters_config = {
            "filterDefinitions": filter_definitions
        }
        
        return json.dumps(filters_config, ensure_ascii=False, separators=(',', ':'))
    
    def _build_common_sections(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        构建公共区块
        
        Args:
            data: 提取数据
            
        Returns:
            List[Dict[str, Any]]: 公共区块列表
        """
        # 新架构：直接使用commonSections数据
        if "commonSections" in data and isinstance(data["commonSections"], list):
            sections = []
            for section in data["commonSections"]:
                if isinstance(section, dict) and "content" in section:
                    # 将新架构的section转换为FlexibleContentPage格式
                    section_data = {
                        "sectionType": section.get("sectionType", "Banner"),
                        "sectionTitle": section.get("sectionTitle", ""),
                        "content": self._process_placeholders(section.get("content", "")),
                        "sortOrder": section.get("sortOrder", 1),
                        "isActive": section.get("isActive", True)
                    }
                    sections.append(section_data)
            return sections
        
        # 回退到旧架构的处理方式
        sections = []
        
        # Banner区块
        banner_content = data.get("BannerContent", "")
        if banner_content.strip():
            sections.append({
                "sectionType": SectionType.BANNER.value,
                "sectionTitle": "产品横幅",
                "content": self._process_placeholders(banner_content),
                "sortOrder": 1,
                "isActive": True
            })
        
        # 产品描述区块
        desc_content = data.get("DescriptionContent", "")
        if desc_content.strip():
            sections.append({
                "sectionType": SectionType.PRODUCT_DESCRIPTION.value,
                "sectionTitle": "产品描述", 
                "content": self._process_placeholders(desc_content),
                "sortOrder": 2,
                "isActive": True
            })
        
        # Q&A区块
        qa_content = data.get("QaContent", "")
        if qa_content.strip():
            sections.append({
                "sectionType": SectionType.QA.value,
                "sectionTitle": "常见问题",
                "content": self._process_placeholders(qa_content),
                "sortOrder": 3,
                "isActive": True
            })
        
        return sections
    
    def _build_simple_base_content(self, data: Dict[str, Any]) -> str:
        """
        构建简单页面的基础内容
        
        Args:
            data: 提取数据
            
        Returns:
            str: 基础内容HTML
        """
        # 对于简单页面，使用baseContent字段（新架构）
        base_content = data.get("baseContent", "")
        
        # 如果没有baseContent，尝试使用遗留字段NoRegionContent
        if not base_content.strip():
            base_content = data.get("NoRegionContent", "")
            
        # 如果仍然没有内容，尝试从区域内容中获取（可能是错误分类的简单页面）
        if not base_content.strip():
            for field_name in ["NorthChinaContent", "EastChinaContent"]:
                content = data.get(field_name, "")
                if content.strip():
                    base_content = content
                    break
        
        # 对于简单页面，需要过滤掉QA内容，因为QA内容已经在commonSections中
        base_content = self._filter_qa_from_content(base_content)
        
        return self._process_placeholders(base_content)
    
    def _build_region_content_groups(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        构建区域内容组
        
        Args:
            data: 提取数据
            
        Returns:
            List[Dict[str, Any]]: 内容组列表
        """
        content_groups = []
        sort_order = 1
        
        for field_name, region_info in self.region_mapping.items():
            content = data.get(field_name, "")
            if content.strip():
                content_groups.append({
                    "groupName": region_info["label"],
                    "filterCriteriaJson": json.dumps([{
                        "filterKey": "region",
                        "matchValues": region_info["key"]
                    }], ensure_ascii=False, separators=(',', ':')),
                    "content": self._process_placeholders(content),
                    "sortOrder": sort_order,
                    "isActive": True
                })
                sort_order += 1
        
        return content_groups
    
    def _build_complex_content_groups(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        构建复杂筛选器内容组
        
        Args:
            data: 提取数据
            
        Returns:
            List[Dict[str, Any]]: 复杂内容组列表
        """
        content_groups = []
        
        # 如果数据中已经有contentGroups，直接返回
        if "contentGroups" in data and data["contentGroups"]:
            return data["contentGroups"]
        
        # 否则，尝试从传统格式构建（作为后备方案）
        # 这里可以根据复杂度分析结果构建内容组
        complexity_analysis = data.get("complexity_analysis", {})
        
        if complexity_analysis.get("has_filters", False) or complexity_analysis.get("has_tabs", False):
            # 如果有筛选器或tabs，构建基础内容组
            base_content = data.get("NoRegionContent", "")
            if base_content.strip():
                content_groups.append({
                    "groupName": "默认内容",
                    "filterCriteriaJson": "[]",
                    "content": self._process_placeholders(base_content),
                    "sortOrder": 1,
                    "isActive": True
                })
        
        return content_groups
    
    def _filter_qa_from_content(self, content: str) -> str:
        """
        从内容中过滤掉QA部分，避免与commonSections重复
        
        Args:
            content: 原始内容
            
        Returns:
            str: 过滤后的内容
        """
        if not content:
            return ""
        
        import re
        from bs4 import BeautifulSoup
        
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # 查找并移除more-detail容器（FAQ内容）
            qa_containers = soup.find_all('div', class_='more-detail')
            for container in qa_containers:
                container.extract()
            
            # 查找并移除包含"常见问题"的pricing-page-section
            sections = soup.find_all('div', class_='pricing-page-section')
            for section in sections:
                h2_tag = section.find('h2')
                if h2_tag and '常见问题' in h2_tag.get_text():
                    section.extract()
                elif section.find('div', class_='more-detail'):
                    # 如果section内包含more-detail，也移除
                    section.extract()
            
            # 移除支持和SLA部分，因为这通常也在QA中
            for section in soup.find_all('div', class_='pricing-page-section'):
                h2_tag = section.find('h2')
                if h2_tag and ('支持和服务级别协议' in h2_tag.get_text() or '支持' in h2_tag.get_text()):
                    section.extract()
            
            return str(soup)
            
        except Exception:
            # 如果解析失败，使用简单的正则表达式过滤
            # 移除more-detail div块
            content = re.sub(r'<div class="more-detail">.*?</div>', '', content, flags=re.DOTALL)
            # 移除包含"常见问题"的section
            content = re.sub(r'<div class="pricing-page-section">.*?<h2>\s*常见问题.*?</div>', '', content, flags=re.DOTALL)
            return content
    
    def _process_placeholders(self, content: str) -> str:
        """
        处理占位符，统一替换为{base_url}
        
        Args:
            content: 原始内容
            
        Returns:
            str: 处理后的内容
        """
        if not content:
            return ""
            
        # 替换各种图片主机名占位符为统一的{base_url}
        content = re.sub(r'\{img_hostname\}', '{base_url}', content)
        content = re.sub(r'\{img_url\}', '{base_url}', content)
        
        return content