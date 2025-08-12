#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础策略抽象类
定义所有提取策略的通用接口和共用方法
"""
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
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
from src.core.logging import get_logger

logger = get_logger(__name__)


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
            "DescriptionContent": "",
            "Language": "zh-cn",
            "QaContent": "",
            "PricingTables": [],
            "ServiceTiers": [],
            "LastModified": "",
            "RegionalContent": {},
        }

        # 1. 提取标题
        logger.info("🏷️ 提取标题...")
        base_data["Title"] = self._extract_page_title(soup)
        
        # 2. 提取Meta信息
        logger.info("📋 提取Meta信息...")
        base_data["MetaTitle"] = self._extract_meta_title(soup)
        base_data["MetaDescription"] = self._extract_meta_description(soup)
        base_data["MetaKeywords"] = self._extract_meta_keywords(soup)
        base_data["MSServiceName"] = self._extract_ms_service_name(soup)
        base_data["Slug"] = self._extract_slug(url)

        # 3. 提取Banner内容
        logger.info("🎨 提取Banner内容...")
        banner_content = self._extract_banner_content(soup)
        base_data["BannerContent"] = self._clean_html_content(banner_content)

        # 4. 提取描述内容
        logger.info("📝 提取描述内容...")
        base_data["DescriptionContent"] = self._extract_description_content(main_content or soup)

        # 5. 提取FAQ内容
        logger.info("❓ 提取FAQ内容...")
        qa_content = self._extract_qa_content(soup)
        base_data["QaContent"] = self._clean_html_content(qa_content)

        # 6. 提取其他元数据
        base_data["LastModified"] = self._extract_last_modified(soup)

        return base_data

    def _extract_page_title(self, soup: BeautifulSoup) -> str:
        """提取页面标题"""
        # 优先查找页面title标签
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            logger.info(f"Get page title: {title}")
            if title and len(title) > 0:
                return title
        #
        # # 查找主要标题元素
        # main_heading = soup.find(['h1', 'h2'])
        # if main_heading:
        #     return main_heading.get_text(strip=True)
        
        return ""

    def _extract_meta_title(self, soup: BeautifulSoup) -> str:
        """提取Meta描述"""
        meta_title = soup.find('meta', attrs={'name': 'title'})
        if meta_title:
            return meta_title.get('content', '')
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
        """提取MSServiceName字段，从pure-content div内的tags元素中的ms.service属性"""
        # 查找pure-content div
        pure_content_div = soup.find('div', class_='pure-content')
        if pure_content_div:
            # 在pure-content div内查找tags元素
            tags_element = pure_content_div.find('tags')
            if tags_element:
                # 提取ms.service属性值
                ms_service = tags_element.get('ms.service', '')
                if ms_service:
                    logger.info(f"  ✓ 找到MSServiceName: {ms_service}")
                    return ms_service
                else:
                    logger.info("  ⚠ tags元素中没有ms.service属性")
            else:
                logger.info("  ⚠ pure-content div中没有找到tags元素")
        else:
            logger.info("  ⚠ 没有找到pure-content div")

        return ""

    def _extract_slug(self, url: str) -> str:
        """从URL提取slug"""
        """从URL提取slug"""
        if not url:
            return ""

        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path = parsed.path

            logger.info(f"Extracting slug from url: {url}")

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
                    return '_'.join(path_parts)
        except:
            pass

        return ""

    def _extract_description_content(self, soup: BeautifulSoup) -> str:
        """提取描述内容 - Banner后第一个pricing-page-section的内容，但排除FAQ"""
        
        # 首先查找Banner元素
        banner = soup.find('div', {'class': ['common-banner', 'col-top-banner']})
        if banner:
            # 从Banner后面查找第一个pricing-page-section
            current = banner
            while current:
                current = current.find_next_sibling()
                if current and current.name == 'div' and 'pricing-page-section' in current.get('class', []):
                    # 检查是否是FAQ内容(包含more-detail或支持和服务级别协议)
                    content_text = current.get_text().strip()
                    if ('more-detail' in str(current) or 
                        '支持和服务级别协议' in content_text or
                        '常见问题' in content_text):
                        continue  # 跳过FAQ内容，查找下一个section
                    
                    # 找到合适的描述section，返回清理后的内容
                    return self._clean_html_content(str(current))
        
        # 备用方案：尝试传统选择器
        desc_selectors = [
            '.description',
            '.product-description', 
            '.intro',
            '.summary',
            'section.overview'
        ]
        
        for selector in desc_selectors:
            element = soup.select_one(selector)
            if element:
                return self._clean_html_content(str(element))
        
        return ""

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

    def _extract_banner_content(self, soup: BeautifulSoup) -> str:
        """
        提取Banner内容
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            Banner HTML内容字符串
        """
        try:
            # 寻找常见的banner选择器
            banner_selectors = [
                'div.common-banner',
                'div.common-banner-image', 
                '.banner',
                '.hero',
                '.page-banner',
                '.product-banner'
            ]
            
            for selector in banner_selectors:
                banner = soup.select_one(selector)
                if banner:
                    # 标准化图片格式
                    standardized_banner = self._standardize_banner_images(banner)
                    print(f"🎨 找到Banner内容，选择器: {selector}")
                    return standardized_banner
            
            print("⚠ 未找到Banner内容")
            return ""
            
        except Exception as e:
            print(f"⚠ Banner内容提取失败: {e}")
            return ""

    def _standardize_banner_images(self, banner) -> str:
        """
        标准化Banner中的图片格式，保留文本内容
        
        Args:
            banner: Banner元素
            
        Returns:
            标准化的HTML字符串
        """
        try:
            # 创建banner的副本避免修改原始DOM
            import copy
            banner_copy = copy.copy(banner)
            
            # 处理img标签
            for img in banner_copy.find_all('img'):
                src = img.get('src', '')
                if src:
                    # 标准化图片路径
                    if not src.startswith('http'):
                        img['src'] = f"{{img_hostname}}{src}"
            
            # 处理style中的background-image
            if banner_copy.get('style'):
                style = banner_copy['style']
                if 'background-image' in style:
                    # 标准化背景图片路径
                    import re
                    style = re.sub(r'url\(["\']?([^"\']*)["\']?\)', 
                                 lambda m: f'url("{{{img_hostname}}}{m.group(1)}")' if not m.group(1).startswith('http') else m.group(0), 
                                 style)
                    banner_copy['style'] = style
            
            return str(banner_copy)
            
        except Exception as e:
            print(f"⚠ Banner图片标准化失败: {e}")
            return str(banner)

    def _extract_qa_content(self, soup: BeautifulSoup) -> str:
        """
        提取Q&A内容以及支持和服务级别协议内容
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            Q&A内容HTML字符串
        """
        try:
            print("🔍 提取Q&A内容...")
            qa_content = ""
            
            # 1. 查找标准FAQ容器
            faq_containers = [
                soup.find('div', class_='faq'),
                soup.find('div', class_='qa'),
                soup.find('section', class_='faq'),
                soup.find('section', class_='qa')
            ]
            
            for container in faq_containers:
                if container:
                    qa_content += str(container)
                    
            # 2. 查找more-detail容器
            more_detail_containers = soup.find_all('div', class_='more-detail')
            for container in more_detail_containers:
                if container:
                    qa_content += str(container)
                    print(f"✓ 找到more-detail容器")
            
            # 3. 查找包含FAQ结构的列表
            faq_lists = soup.find_all('ul', class_='faq-list')
            for faq_list in faq_lists:
                if faq_list:
                    qa_content += str(faq_list)
            
            # 4. 查找pricing-page-section中的支持和SLA内容（排除定价内容）
            pricing_sections = soup.find_all('div', class_='pricing-page-section')
            for section in pricing_sections:
                section_text = section.get_text().lower()
                # 只提取明确的支持和SLA部分，排除包含定价表格的部分
                if ('支持和服务级别协议' in section_text or 'sla' in section_text) and not any(price_indicator in section_text for price_indicator in ['￥', '价格', '每单位', '小时', '开发人员基本标准']):
                    qa_content += str(section)
                    print(f"✓ 找到pricing-page-section支持/SLA内容")
            
            # 5. 查找accordion-style的FAQ
            accordion_items = soup.find_all(['div', 'section'], class_=['accordion-item', 'faq-item'])
            for item in accordion_items:
                if item:
                    qa_content += str(item)
            
            # 6. 如果以上都没找到，查找包含特定FAQ问题的元素
            if not qa_content:
                faq_questions = [
                    '开发人员层的用途是什么',
                    '我是否可以在自己的数据中心',
                    '什么是"单位"',
                    '什么是"网关部署"'
                ]
                
                for question in faq_questions:
                    elements = soup.find_all(string=lambda text: text and question in text)
                    for element in elements:
                        # 找到包含问题的最近的容器
                        parent = element.parent
                        while parent and parent.name not in ['div', 'section', 'article']:
                            parent = parent.parent
                        
                        if parent:
                            # 查找父级的pricing-page-section或more-detail容器
                            container = parent
                            for _ in range(5):  # 最多向上查找5层
                                if container.get('class') and any(cls in ['pricing-page-section', 'more-detail'] 
                                                                 for cls in container.get('class', [])):
                                    qa_content += str(container)
                                    print(f"✓ 找到FAQ问题容器: {question[:20]}...")
                                    break
                                if container.parent:
                                    container = container.parent
                                else:
                                    break
            
            print(f"✓ 提取了 {len(qa_content)} 字符的Q&A内容")
            return qa_content
            
        except Exception as e:
            print(f"⚠ Q&A内容提取失败: {e}")
            return ""