#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础策略抽象类
定义所有提取策略的通用接口和共用方法
"""

import os
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.utils.html.element_creator import create_simple_element
from src.utils.html.cleaner import clean_html_content
from src.utils.media.image_processor import preprocess_image_paths
from src.utils.content.content_utils import (
    extract_qa_content, find_main_content_area, extract_banner_text_content, 
    extract_structured_content
)
from src.utils.data.validation_utils import validate_extracted_data


class BaseStrategy(ABC):
    """基础策略抽象类，所有提取策略的基础"""

    def __init__(self, product_config: Dict[str, Any], html_file_path: str = ""):
        """
        初始化基础策略
        
        Args:
            product_config: 产品配置信息
            html_file_path: HTML文件路径
        """
        self.product_config = product_config
        self.html_file_path = html_file_path

    @abstractmethod
    def extract(self, soup: BeautifulSoup, url: str = "") -> Dict[str, Any]:
        """
        执行具体的提取逻辑
        
        Args:
            soup: BeautifulSoup解析的HTML对象
            url: 源URL
            
        Returns:
            提取的CMS内容数据
        """
        pass

    def _extract_base_content(self, soup: BeautifulSoup, url: str = "") -> Dict[str, Any]:
        """
        提取所有策略共用的基础内容
        包括：Title, Meta信息, Banner, Description等通用字段
        
        Args:
            soup: BeautifulSoup解析的HTML对象
            url: 源URL
            
        Returns:
            基础内容字典
        """
        print("🔍 提取基础内容...")

        # 查找主要内容区域
        main_content = find_main_content_area(soup)
        
        # 初始化基础数据结构
        base_data = {
            "source_file": str(self.html_file_path),
            "source_url": url or self._get_default_url(),
            "extraction_timestamp": datetime.now().isoformat(),
            "Title": "",
            "MetaDescription": "",
            "MetaKeywords": "",
            "MSServiceName": "",
            "Slug": "",
            "BannerContent": "",
            "NavigationTitle": "",
            "DescriptionContent": "",
            "Language": "zh-cn",
            "QaContent": "",
            "PricingTables": [],
            "ServiceTiers": [],
            "LastModified": "",
            "RegionalContent": {},
        }

        # 1. 提取标题
        print("🏷️ 提取标题...")
        base_data["Title"] = self._extract_page_title(main_content or soup)
        
        # 2. 提取Meta信息
        print("📋 提取Meta信息...")
        base_data["MetaDescription"] = self._extract_meta_description(soup)
        base_data["MetaKeywords"] = self._extract_meta_keywords(soup)
        base_data["MSServiceName"] = self._extract_ms_service_name(soup)
        base_data["Slug"] = self._extract_slug(url)

        # 3. 提取Banner内容
        print("🎨 提取Banner内容...")
        banner_content = extract_banner_text_content(main_content or soup)
        base_data["BannerContent"] = self._clean_html_content(banner_content)
        base_data["NavigationTitle"] = self._extract_navigation_title(soup)

        # 4. 提取描述内容
        print("📝 提取描述内容...")
        base_data["DescriptionContent"] = self._extract_description_content(main_content or soup)

        # 5. 提取FAQ内容
        print("❓ 提取FAQ内容...")
        base_data["QaContent"] = extract_qa_content(main_content or soup)

        # 6. 提取定价表格
        print("💰 提取定价表格...")
        base_data["PricingTables"] = self._extract_pricing_tables(main_content or soup)

        # 7. 提取其他元数据
        base_data["LastModified"] = self._extract_last_modified(soup)

        return base_data

    def _extract_page_title(self, soup: BeautifulSoup) -> str:
        """提取页面标题"""
        # 优先查找页面title标签
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            if title and len(title) > 0:
                return title
        
        # 查找主要标题元素
        main_heading = soup.find(['h1', 'h2'])
        if main_heading:
            return main_heading.get_text(strip=True)
        
        return ""

    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        """提取Meta描述"""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            return meta_desc.get('content', '')
        return ""

    def _extract_meta_keywords(self, soup: BeautifulSoup) -> str:
        """提取Meta关键词"""
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords:
            return meta_keywords.get('content', '')
        return ""

    def _extract_ms_service_name(self, soup: BeautifulSoup) -> str:
        """提取微软服务名称"""
        # 从URL或页面内容推断服务名称
        if hasattr(self, 'product_config') and 'service_name' in self.product_config:
            return self.product_config['service_name']
        
        # 从文件路径推断
        if self.html_file_path:
            file_name = Path(self.html_file_path).stem
            if file_name.endswith('-index'):
                return file_name[:-6]  # 移除'-index'后缀
        
        return ""

    def _extract_slug(self, url: str) -> str:
        """从URL提取slug"""
        if not url:
            return ""
        
        # 从URL提取最后一个路径段作为slug
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split('/') if p]
            if path_parts:
                return path_parts[-1]
        except:
            pass
        
        return ""

    def _extract_navigation_title(self, soup: BeautifulSoup) -> str:
        """提取导航标题"""
        # 查找导航相关的标题元素
        nav_selectors = [
            'nav .title',
            '.navigation-title',
            '.breadcrumb .current',
            '.page-header .title'
        ]
        
        for selector in nav_selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        
        return ""

    def _extract_description_content(self, soup: BeautifulSoup) -> str:
        """提取描述内容"""
        # 查找描述内容的候选元素
        desc_selectors = [
            '.description',
            '.product-description',
            '.intro',
            '.summary',
            'section.overview',
            '.content-section:first-of-type'
        ]
        
        for selector in desc_selectors:
            element = soup.select_one(selector)
            if element:
                return self._clean_html_content(str(element))
        
        # 如果没有找到特定的描述区域，尝试提取第一个段落
        first_paragraph = soup.find('p')
        if first_paragraph:
            return self._clean_html_content(str(first_paragraph))
        
        return ""

    def _extract_pricing_tables(self, soup: BeautifulSoup) -> List[str]:
        """提取定价表格"""
        tables = []
        
        # 查找定价相关的表格
        pricing_tables = soup.find_all(['table', 'div'], 
                                     class_=lambda x: x and any(
                                         keyword in x.lower() 
                                         for keyword in ['pricing', 'price', 'cost', 'tier']
                                     ))
        
        for table in pricing_tables:
            clean_table = self._clean_html_content(str(table))
            if clean_table:
                tables.append(clean_table)
        
        return tables

    def _extract_last_modified(self, soup: BeautifulSoup) -> str:
        """提取最后修改时间"""
        # 查找最后修改时间的元数据
        modified_selectors = [
            'meta[name="last-modified"]',
            'meta[property="article:modified_time"]',
            '.last-updated',
            '.modified-date'
        ]
        
        for selector in modified_selectors:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    return element.get('content', '')
                else:
                    return element.get_text(strip=True)
        
        return ""

    def _clean_html_content(self, content: str) -> str:
        """清理HTML内容"""
        if not content:
            return ""
        
        try:
            return clean_html_content(content)
        except Exception as e:
            print(f"⚠ HTML清理失败: {e}")
            return content

    def _get_default_url(self) -> str:
        """获取默认URL"""
        if hasattr(self, 'product_config') and 'default_url' in self.product_config:
            return self.product_config['default_url']
        
        # 从文件路径推断URL
        if self.html_file_path:
            file_name = Path(self.html_file_path).stem
            if file_name.endswith('-index'):
                service_name = file_name[:-6]
                return f"https://www.azure.cn/pricing/details/{service_name}/"
        
        return ""

    def _validate_extraction_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证提取结果
        
        Args:
            data: 提取的数据
            
        Returns:
            验证后的数据，包含validation字段
        """
        print("✅ 验证提取结果...")
        
        try:
            validation_result = validate_extracted_data(data, self.product_config)
            data["validation"] = validation_result
        except Exception as e:
            print(f"⚠ 验证失败: {e}")
            data["validation"] = {
                "is_valid": False,
                "errors": [str(e)],
                "warnings": []
            }
        
        # 添加提取元数据
        data["extraction_metadata"] = {
            "extractor_version": "enhanced_v3.0",
            "extraction_timestamp": datetime.now().isoformat(),
            "strategy_used": getattr(self, 'strategy_name', 'unknown'),
            "processing_mode": "strategy_based"
        }
        
        return data

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