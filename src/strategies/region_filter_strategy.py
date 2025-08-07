#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
区域筛选策略
处理Type B页面：具有区域筛选功能的页面，如API Management
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


class RegionFilterStrategy(BaseStrategy):
    """
    区域筛选策略
    Type B: 区域筛选页面处理 - API Management类型
    
    特点：
    - 具有区域筛选控件 (如中国北部、中国东部等)
    - 筛选器变化会改变内容显示
    - 需要提取每个区域的专门内容
    - API Management是此策略的典型代表
    """

    def __init__(self, product_config: Dict[str, Any], html_file_path: str = ""):
        """
        初始化区域筛选策略
        
        Args:
            product_config: 产品配置信息
            html_file_path: HTML文件路径
        """
        super().__init__(product_config, html_file_path)
        self.region_processor = RegionProcessor()
        print(f"🌍 初始化区域筛选策略: {self._get_product_key()}")

    def extract(self, soup: BeautifulSoup, url: str = "") -> Dict[str, Any]:
        """
        执行区域筛选策略的提取逻辑
        
        Args:
            soup: BeautifulSoup解析的HTML对象
            url: 源URL
            
        Returns:
            提取的CMS内容数据，包含区域特定内容
        """
        print(f"🌍 执行区域筛选策略提取...")
        
        # 1. 提取基础内容
        base_content = self._extract_base_content(soup, url)
        print(f"✅ 基础内容提取完成")
        
        # 2. 使用RegionProcessor进行区域处理
        try:
            region_content = self.region_processor.extract_region_contents(
                soup, self.html_file_path
            )
            print(f"🌍 区域内容提取完成: {len(region_content)} 个区域")
        except Exception as e:
            print(f"⚠ 区域内容提取失败: {e}")
            region_content = {}
        
        # 3. 转换区域内容为CMS格式
        cms_fields = self._convert_region_content_to_cms_format(region_content)
        
        # 4. 组合最终结果
        final_data = {
            **base_content,
            **cms_fields,
            "HasRegion": True,
            "RegionalContent": region_content,
            "extraction_strategy": "region_filter",
            "region_count": len(region_content),
            "supported_regions": list(region_content.keys()) if region_content else []
        }
        
        # 5. 验证提取结果
        final_data = self._validate_extraction_result(final_data)
        
        print(f"✅ 区域筛选策略提取完成")
        return final_data

    def _convert_region_content_to_cms_format(self, region_content: Dict[str, Any]) -> Dict[str, str]:
        """
        转换区域内容为CMS格式字段 - 生成结构化HTML格式
        
        Args:
            region_content: RegionProcessor提取的区域内容
            
        Returns:
            CMS格式的区域字段映射
        """
        cms_fields = {}
        
        # 区域ID到CMS字段的映射
        region_mapping = {
            "north-china": "NorthChinaContent",
            "east-china": "EastChinaContent", 
            "north-china2": "NorthChina2Content",
            "east-china2": "EastChina2Content",
            "north-china3": "NorthChina3Content",
            # 可以根据需要扩展更多区域
        }
        
        for region_id, content in region_content.items():
            field_name = region_mapping.get(region_id, f"{region_id.replace('-', '_').title()}Content")
            
            # 转换为结构化HTML格式
            html_content = self._format_region_content_as_html(content, region_id)
            cms_fields[field_name] = html_content
        
        print(f"🔄 区域内容转换完成: {len(cms_fields)} 个CMS字段")
        return cms_fields
    
    def _format_region_content_as_html(self, content, region_id: str) -> str:
        """
        将区域内容格式化为HTML结构 - 支持新的HTML字符串格式
        
        Args:
            content: 区域内容（可能是字典或HTML字符串）
            region_id: 区域ID
            
        Returns:
            格式化的HTML字符串
        """
        # 新格式：如果content已经是HTML字符串，直接返回
        if isinstance(content, str):
            print(f"    📄 使用HTML字符串格式，长度: {len(content)}")
            return content
        
        # 旧格式：如果是字典格式，按原来的逻辑处理
        if isinstance(content, dict):
            print(f"    📊 使用字典格式，包含: {list(content.keys())}")
            return self._format_region_dict_as_html(content, region_id)
        
        # 回退情况
        print(f"    ⚠ 未知内容格式: {type(content)}")
        return str(content)

    def _format_region_dict_as_html(self, content: Dict[str, Any], region_id: str) -> str:
        """
        将区域字典内容格式化为HTML结构（原逻辑保持不变）
        
        Args:
            content: 区域内容字典
            region_id: 区域ID
            
        Returns:
            格式化的HTML字符串
        """
        html_parts = []
        
        try:
            # 1. 定价表格部分
            if 'pricing_tables' in content and content['pricing_tables']:
                pricing_html = "<div class='pricing-tables'>"
                for table in content['pricing_tables']:
                    if isinstance(table, dict) and 'content' in table:
                        # 清理内容，移除多余的换行和空格
                        table_content = self._clean_content(table['content'])
                        pricing_html += f" {table_content}"
                pricing_html += " </div>"
                html_parts.append(pricing_html)
            
            # 2. FAQ/功能可用性部分  
            if 'feature_availability' in content and content['feature_availability']:
                faq_html = "<div class='feature-availability'>"
                for faq in content['feature_availability']:
                    cleaned_faq = self._clean_content(faq)
                    faq_html += f"<p>{cleaned_faq}</p>"
                faq_html += "</div>"
                html_parts.append(faq_html)
            
            # 3. 区域说明部分
            if 'region_notes' in content and content['region_notes']:
                notes_html = "<div class='region-notes'>"
                for note in content['region_notes']:
                    cleaned_note = self._clean_content(note)
                    notes_html += f"<p>{cleaned_note}</p>"
                notes_html += "</div>"
                html_parts.append(notes_html)
                
            # 如果没有结构化数据，尝试处理原始内容
            if not html_parts and isinstance(content, dict):
                if 'content' in content:
                    cleaned_content = self._clean_content(content['content'])
                    html_parts.append(f"<div class='pricing-content'>{cleaned_content}</div>")
                elif 'html' in content:
                    cleaned_html = self._clean_content(content['html'])
                    html_parts.append(cleaned_html)
            
            return "".join(html_parts)
            
        except Exception as e:
            print(f"⚠ 区域内容HTML格式化失败 ({region_id}): {e}")
            # 回退到简单字符串处理
            if isinstance(content, dict):
                return self._clean_content(str(content))
            else:
                return self._clean_content(str(content))
    
    def _clean_content(self, content: str) -> str:
        """
        清理内容，移除多余的标签和符号
        
        Args:
            content: 原始内容字符串
            
        Returns:
            清理后的内容
        """
        if not content:
            return ""
        
        import re
        
        # 移除多余的换行符和空格
        content = re.sub(r'\s+', ' ', content.strip())
        
        # 移除不必要的div标签（保留class的div）
        content = re.sub(r'<div(?!\s+class=)[^>]*>', '', content)
        content = re.sub(r'</div>', '', content)
        
        # 移除空的段落和多余的标签
        content = re.sub(r'<p>\s*</p>', '', content)
        content = re.sub(r'<span[^>]*></span>', '', content)
        
        # 清理多余的空格
        content = re.sub(r'\s+', ' ', content.strip())
        
        return content

    def _extract_base_content(self, soup: BeautifulSoup, url: str = "") -> Dict[str, Any]:
        """
        重写基础内容提取，针对区域筛选页面进行优化
        """
        print("🔍 提取区域筛选页面基础内容...")
        
        # 调用父类方法获取基础内容
        base_content = super()._extract_base_content(soup, url)
        
        # 为区域筛选页面添加特殊处理
        base_content["page_type"] = "region_filter"
        base_content["has_region_filter"] = True
        
        # 检测区域筛选器的存在
        region_filter_indicators = [
            '.region-selector',
            '.region-filter',
            '[data-region-filter]',
            'select[data-region]',
            '.dropdown-region'
        ]
        
        region_filter_found = False
        for selector in region_filter_indicators:
            if soup.select_one(selector):
                region_filter_found = True
                break
        
        base_content["region_filter_detected"] = region_filter_found
        
        return base_content