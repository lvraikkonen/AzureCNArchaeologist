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
    COMPLEX_FILTER = "ComplexFilter"  # 暂不实现

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
            "title": self._clean_title(data.get("Title", "")),
            "slug": data.get("Slug", product_name),
            "metaTitle": self._generate_meta_title(data, product_name),
            "metaDescription": data.get("MetaDescription", ""),
            "metaKeywords": data.get("MetaKeywords", ""),
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
            
        return flexible_data
    
    def _determine_page_type(self, data: Dict[str, Any]) -> PageType:
        """
        判断页面类型
        
        Args:
            data: 提取数据
            
        Returns:
            PageType: 页面类型
        """
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
    
    def _generate_meta_title(self, data: Dict[str, Any], product_name: str) -> str:
        """
        生成SEO标题
        
        Args:
            data: 提取数据
            product_name: 产品名称
            
        Returns:
            str: SEO标题
        """
        base_title = self._clean_title(data.get("Title", product_name))
        return f"定价-{base_title}-Azure 云计算"
    
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
    
    def _build_common_sections(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        构建公共区块
        
        Args:
            data: 提取数据
            
        Returns:
            List[Dict[str, Any]]: 公共区块列表
        """
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
        # 对于简单页面，将NoRegionContent作为基础内容
        base_content = data.get("NoRegionContent", "")
        
        # 如果没有NoRegionContent，尝试使用其他可用内容
        if not base_content.strip():
            # 尝试从区域内容中获取（可能是错误分类的简单页面）
            for field_name in ["NorthChinaContent", "EastChinaContent"]:
                content = data.get(field_name, "")
                if content.strip():
                    base_content = content
                    break
        
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