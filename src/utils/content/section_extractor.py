#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专门section提取器
抽离Banner、Description、QA的具体提取逻辑，支持flexible JSON的commonSections格式
"""

import sys
import copy
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

from src.core.logging import get_logger
from src.utils.html.cleaner import clean_html_content

logger = get_logger(__name__)


class SectionExtractor:
    """专门section提取器 - 提取Banner、Description、QA等特定section内容"""

    def __init__(self):
        """初始化section提取器"""
        logger.info("🔧 初始化SectionExtractor")

    def extract_all_sections(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        提取所有commonSections
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            commonSections列表，每个元素包含sectionType和content
        """
        logger.info("🔍 提取所有commonSections...")
        
        sections = []
        
        # 1. 提取Banner
        banner_content = self.extract_banner(soup)
        if banner_content:
            sections.append({
                "sectionType": "Banner",
                "content": banner_content
            })
        
        # 2. 提取Description
        description_content = self.extract_description(soup)
        if description_content:
            sections.append({
                "sectionType": "Description",
                "content": description_content
            })
        
        # 3. 提取QA
        qa_content = self.extract_qa(soup)
        if qa_content:
            sections.append({
                "sectionType": "Qa",
                "content": qa_content
            })
        
        logger.info(f"✓ 提取了 {len(sections)} 个commonSections")
        return sections

    def extract_banner(self, soup: BeautifulSoup) -> str:
        """
        提取Banner内容
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            Banner HTML内容字符串
        """
        logger.info("🎨 提取Banner内容...")
        
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
                    logger.info(f"✓ 找到Banner内容，选择器: {selector}")
                    return standardized_banner
            
            logger.info("⚠ 未找到Banner内容")
            return ""
            
        except Exception as e:
            logger.info(f"⚠ Banner内容提取失败: {e}")
            return ""

    def extract_description(self, soup: BeautifulSoup) -> str:
        """
        提取描述内容
        Banner后第一个pricing-page-section的内容，但排除FAQ
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            描述内容HTML字符串
        """
        logger.info("📝 提取描述内容...")
        
        try:
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
                        clean_content = clean_html_content(str(current))
                        logger.info(f"✓ 找到描述内容，长度: {len(clean_content)}")
                        return clean_content
            
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
                    clean_content = clean_html_content(str(element))
                    logger.info(f"✓ 使用备用描述选择器: {selector}")
                    return clean_content
            
            logger.info("⚠ 未找到描述内容")
            return ""
            
        except Exception as e:
            logger.info(f"⚠ 描述内容提取失败: {e}")
            return ""

    def extract_qa(self, soup: BeautifulSoup) -> str:
        """
        提取Q&A内容以及支持和服务级别协议内容
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            Q&A内容HTML字符串
        """
        logger.info("❓ 提取Q&A内容...")
        
        try:
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
                    logger.info(f"✓ 找到more-detail容器")
            
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
                    logger.info(f"✓ 找到pricing-page-section支持/SLA内容")
            
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
                                    logger.info(f"✓ 找到FAQ问题容器: {question[:20]}...")
                                    break
                                if container.parent:
                                    container = container.parent
                                else:
                                    break
            
            # 清理QA内容
            if qa_content:
                clean_qa = clean_html_content(qa_content)
                logger.info(f"✓ 提取了 {len(clean_qa)} 字符的Q&A内容")
                return clean_qa
            else:
                logger.info("⚠ 未找到Q&A内容")
                return ""
            
        except Exception as e:
            logger.info(f"⚠ Q&A内容提取失败: {e}")
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
                    style = re.sub(r'url\(["\']?([^"\']*)["\']?\)', 
                                 lambda m: f'url("{{{img_hostname}}}{m.group(1)}")' if not m.group(1).startswith('http') else m.group(0), 
                                 style)
                    banner_copy['style'] = style
            
            return clean_html_content(str(banner_copy))
            
        except Exception as e:
            logger.info(f"⚠ Banner图片标准化失败: {e}")
            return clean_html_content(str(banner))