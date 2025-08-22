#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用内容提取器
抽离BaseStrategy中的Title、Meta、主内容提取逻辑，支持传统CMS和flexible JSON双格式需求
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

from src.core.logging import get_logger
from src.utils.content.content_utils import find_main_content_area

logger = get_logger(__name__)


class ContentExtractor:
    """通用内容提取器 - 提取标题、Meta信息和主要内容"""

    def __init__(self):
        """初始化内容提取器"""
        logger.info("🔧 初始化ContentExtractor")

    def extract_base_metadata(self, soup: BeautifulSoup, url: str = "", html_file_path: str = "") -> Dict[str, Any]:
        """
        提取基础元数据信息
        
        Args:
            soup: BeautifulSoup解析的HTML对象
            url: 源URL
            html_file_path: HTML文件路径
            
        Returns:
            基础元数据字典
        """
        logger.info("🔍 提取基础元数据...")

        # 初始化基础数据结构
        metadata = {
            "source_file": str(html_file_path),
            "source_url": url or self._get_default_url(html_file_path),
            "extraction_timestamp": datetime.now().isoformat(),
            "Title": "",
            "MetaTitle": "",
            "MetaDescription": "",
            "MetaKeywords": "", 
            "MSServiceName": "",
            "Slug": "",
            "Language": "zh-cn",
            "LastModified": ""
        }

        # 1. 提取标题
        metadata["Title"] = self.extract_title(soup)
        
        # 2. 提取Meta信息
        metadata["MetaTitle"] = self.extract_meta_title(soup)
        metadata["MetaDescription"] = self.extract_meta_description(soup)
        metadata["MetaKeywords"] = self.extract_meta_keywords(soup)
        metadata["MSServiceName"] = self.extract_ms_service_name(soup)
        metadata["Slug"] = self.extract_slug(url)
        metadata["Language"] = self.extract_language(soup)
        
        # 3. 提取其他元数据
        metadata["LastModified"] = self.extract_last_modified(soup)

        return metadata

    def extract_title(self, soup: BeautifulSoup) -> str:
        """
        提取页面标题
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            页面标题字符串
        """
        # 优先查找页面title标签
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            logger.info(f"✓ 提取页面标题: {title}")
            if title and len(title) > 0:
                return title
        
        logger.info("⚠ 未找到页面标题")
        return ""

    def extract_meta_title(self, soup: BeautifulSoup) -> str:
        """
        提取Meta标题
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            Meta标题字符串
        """
        meta_title = soup.find('meta', attrs={'name': 'title'})
        if meta_title:
            title = meta_title.get('content', '')
            logger.info(f"✓ 提取Meta标题: {title}")
            return title
        return ""

    def extract_meta_description(self, soup: BeautifulSoup) -> str:
        """
        提取Meta描述
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            Meta描述字符串
        """
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            desc = meta_desc.get('content', '')
            logger.info(f"✓ 提取Meta描述: {desc[:50]}...")
            return desc
        return ""

    def extract_meta_keywords(self, soup: BeautifulSoup) -> str:
        """
        提取Meta关键词
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            Meta关键词字符串
        """
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords:
            keywords = meta_keywords.get('content', '')
            logger.info(f"✓ 提取Meta关键词: {keywords}")
            return keywords
        return ""

    def extract_ms_service_name(self, soup: BeautifulSoup) -> str:
        """
        提取微软服务名称
        从pure-content div内的tags元素中的ms.service属性
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            MSServiceName字符串
        """
        # 查找pure-content div
        pure_content_div = soup.find('div', class_='pure-content')
        if pure_content_div:
            # 在pure-content div内查找tags元素
            tags_element = pure_content_div.find('tags')
            if tags_element:
                # 提取ms.service属性值
                ms_service = tags_element.get('ms.service', '')
                if ms_service:
                    logger.info(f"✓ 提取MSServiceName: {ms_service}")
                    return ms_service
                else:
                    logger.info("⚠ tags元素中没有ms.service属性")
            else:
                logger.info("⚠ pure-content div中没有找到tags元素")
        else:
            logger.info("⚠ 没有找到pure-content div")

        return ""

    def extract_slug(self, url: str) -> str:
        """
        从URL提取slug
        
        Args:
            url: 源URL
            
        Returns:
            slug字符串
        """
        if not url:
            return ""

        try:
            parsed = urlparse(url)
            path = parsed.path

            logger.info(f"从URL提取slug: {url}")

            # 提取/details/之后到/index.html之前的内容，用-连接
            # 例如 /pricing/details/storage/files/index.html -> storage-files
            # 例如 /pricing/details/api-management/index.html -> api-management
            if '/details/' in path:
                # 找到/details/之后的部分
                after_details = path.split('/details/')[1]

                # 移除/index.html后缀
                if after_details.endswith('/index.html'):
                    after_details = after_details[:-11]  # 移除'/index.html'
                elif after_details.endswith('/'):
                    after_details = after_details[:-1]  # 移除末尾的'/'

                # 分割路径并用_连接
                path_parts = [p for p in after_details.split('/') if p]
                if path_parts:
                    slug = '_'.join(path_parts)
                    logger.info(f"✓ 提取slug: {slug}")
                    return slug
        except Exception as e:
            logger.info(f"⚠ slug提取失败: {e}")

        return ""
    
    def extract_language(self, soup: BeautifulSoup) -> str:
        """
        提取页面语言
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            页面语言字符串
        """
        body = soup.find("body")
        if body and body.has_attr("class"):
            return body["class"][0]
        return "zh-cn"

    def extract_last_modified(self, soup: BeautifulSoup) -> str:
        """
        提取最后修改时间
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            最后修改时间字符串
        """
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
                    modified = element.get('content', '')
                    logger.info(f"✓ 提取最后修改时间: {modified}")
                    return modified
                else:
                    modified = element.get_text(strip=True)
                    logger.info(f"✓ 提取最后修改时间: {modified}")
                    return modified
        
        return ""

    def extract_main_content(self, soup: BeautifulSoup) -> str:
        """
        提取主要内容区域
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            主要内容HTML字符串
        """
        logger.info("📝 提取主要内容区域...")
        
        try:
            # 查找主要内容区域
            main_content = find_main_content_area(soup)
            if main_content:
                content_html = str(main_content)
                logger.info(f"✓ 找到主要内容区域，长度: {len(content_html)}")
                return content_html
            
            logger.info("⚠ 未找到主要内容区域")
            return ""
            
        except Exception as e:
            logger.info(f"⚠ 主要内容提取失败: {e}")
            return ""

    def _get_default_url(self, html_file_path: str) -> str:
        """
        获取默认URL
        
        Args:
            html_file_path: HTML文件路径
            
        Returns:
            默认URL字符串
        """
        # 从文件路径推断URL
        if html_file_path:
            file_name = Path(html_file_path).stem
            if file_name.endswith('-index'):
                service_name = file_name[:-6]
                return f"https://www.azure.cn/pricing/details/{service_name}/"
        
        return ""