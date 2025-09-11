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
                "sectionTitle": "",  # Banner通常无标题
                "content": banner_content,
                "sortOrder": 1,
                "isActive": True
            })
        
        # 2. 提取Description
        description_content = self.extract_description(soup)
        if description_content:
            sections.append({
                "sectionType": "ProductDescription",
                "sectionTitle": "",  # Description通常无标题
                "content": description_content,
                "sortOrder": 1,
                "isActive": True
            })
        
        # 3. 提取QA
        qa_content = self.extract_qa(soup)
        if qa_content:
            sections.append({
                "sectionType": "Qa",
                "sectionTitle": "",  # QA通常内嵌标题
                "content": qa_content,
                "sortOrder": 1,
                "isActive": True
            })
        
        logger.info(f"✓ 提取了 {len(sections)} 个完整commonSections")
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
                    # 图片路径已由ExtractionCoordinator中的preprocess_image_paths全局处理
                    logger.info(f"✓ 找到Banner内容，选择器: {selector}")
                    return clean_html_content(str(banner))
            
            logger.info("⚠ 未找到Banner内容")
            return ""
            
        except Exception as e:
            logger.info(f"⚠ Banner内容提取失败: {e}")
            return ""

    def extract_description(self, soup: BeautifulSoup) -> str:
        """
        提取描述内容
        Banner后第一个有效描述元素的内容（支持pricing-page-section、ul等元素），但排除FAQ
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            描述内容HTML字符串
        """
        logger.info("📝 提取描述内容...")
        
        try:
            # 首先查找Banner元素
            banner = soup.find('div', {'class': ['common-banner', 'col-top-banner']})
            if not banner:
                logger.info("⚠ 未找到Banner元素")
                return ""

            # 查找technical-azure-selector元素作为边界
            main_content_selector = soup.find('div', class_='technical-azure-selector')

            # 方法1: 尝试找到第一个有效的描述元素
            current = banner
            while current:
                current = current.find_next_sibling()
                if not current:
                    break

                # 如果遇到technical-azure-selector，停止查找
                if (main_content_selector and current == main_content_selector):
                    break

                current_str = str(current)
                if ('technical-azure-selector' in current_str and
                    'pricing-detail-tab' in current_str):
                    break

                if current and hasattr(current, 'name'):
                    # 检查是否是pricing-page-section
                    if 'pricing-page-section' in current_str:
                        content_text = current.get_text().strip()
                        # 检查是否是FAQ内容(包含more-detail或支持和服务级别协议)
                        if ('more-detail' in current_str or
                            '支持和服务级别协议' in content_text or
                            '常见问题' in content_text or
                            'faq' in content_text.lower()):
                            continue  # 跳过FAQ内容，查找下一个section

                        # 找到合适的描述section
                        clean_content = clean_html_content(str(current))
                        logger.info(f"✓ 找到pricing-page-section描述内容，长度: {len(clean_content)}")
                        return clean_content

                    # 检查是否是ul/ol等描述元素
                    elif current.name in ['ul', 'ol']:
                        # 检查是否包含描述性内容（避免导航菜单）
                        content_text = current.get_text().strip()
                        if (len(content_text) > 50 and  # 内容足够长
                            not any(nav_indicator in content_text.lower() for nav_indicator in [
                                '导航', 'menu', 'nav', '首页', 'home'
                            ]) and
                            not any(faq_indicator in content_text for faq_indicator in [
                                '常见问题', 'faq', '支持和服务级别协议'
                            ])):
                            clean_content = clean_html_content(str(current))
                            logger.info(f"✓ 找到{current.name}描述内容，长度: {len(clean_content)}")
                            return clean_content

                    # 检查是否是其他描述容器
                    elif (current.name == 'div' and
                          any(desc_class in current_str for desc_class in [
                              'description', 'intro', 'summary', 'overview'
                          ])):
                        content_text = current.get_text().strip()
                        if (len(content_text) > 30 and
                            not any(faq_indicator in content_text for faq_indicator in [
                                '常见问题', 'faq', '支持和服务级别协议'
                            ])):
                            clean_content = clean_html_content(str(current))
                            logger.info(f"✓ 找到描述容器内容，长度: {len(clean_content)}")
                            return clean_content

            # 方法2: 如果没有找到单个描述元素，收集Banner后到technical-azure-selector之间的所有内容
            logger.info("📝 未找到单个描述元素，尝试收集区域内所有内容...")
            description_content = ""
            current = banner
            found_sections = 0

            while current:
                current = current.find_next_sibling()
                if not current:
                    break

                # 如果遇到technical-azure-selector，停止收集
                if (main_content_selector and current == main_content_selector):
                    break

                current_str = str(current)
                if ('technical-azure-selector' in current_str and
                    'pricing-detail-tab' in current_str):
                    break

                # 收集pricing-page-section或其他有意义的内容
                if ('pricing-page-section' in current_str or
                    (hasattr(current, 'name') and current.name in ['div', 'ul', 'ol', 'section', 'p'] and
                     len(current.get_text().strip()) > 30)):
                    # 排除FAQ内容
                    content_text = current.get_text().strip()
                    if not any(faq_indicator in content_text for faq_indicator in [
                        '常见问题', 'faq', '支持和服务级别协议', 'more-detail'
                    ]):
                        description_content += str(current)
                        found_sections += 1
                        logger.info(f"✓ 收集第{found_sections}个描述内容")

            if description_content:
                clean_content = clean_html_content(description_content)
                logger.info(f"✓ 收集了{found_sections}个描述sections，总长度: {len(clean_content)}")
                return clean_content

            logger.info("⚠ 未找到描述内容")
            return ""
            
        except Exception as e:
            logger.info(f"⚠ 描述内容提取失败: {e}")
            return ""

    def extract_qa(self, soup: BeautifulSoup) -> str:
        """
        提取Q&A内容以及支持和服务级别协议内容
        technical-azure-selector容器之后的所有pricing-page-section或者没有pricing-page-section包围的内容，
        包括额外信息、FAQ、SLA等，统一归类为QA内容

        Args:
            soup: BeautifulSoup对象

        Returns:
            Q&A内容HTML字符串
        """
        logger.info("❓ 提取Q&A内容...")

        try:
            qa_content = ""

            # 1. 查找technical-azure-selector元素（主要内容区域）
            main_content_selector = soup.find('div', class_='technical-azure-selector')

            if not main_content_selector:
                logger.info("⚠ 未找到technical-azure-selector元素，使用备用方法提取Q&A内容")
                # 备用方法：直接查找FAQ和SLA相关内容
                return self._extract_qa_fallback(soup)

            # 2. 首先收集technical-azure-selector容器后，非FAQ、SLA的页面内容，作为"额外信息"
            current = main_content_selector
            additional_info_sections = 0

            while current:
                current = current.find_next_sibling()
                if not current:
                    break

                current_str = str(current)
                if 'pricing-page-section' in current_str:
                    content_text = current.get_text().strip()
                    # 检查是否是FAQ或SLA内容
                    if not any(qa_indicator in content_text.lower() for qa_indicator in [
                        'faq', '常见问题', '支持和服务级别协议', 'sla', 'more-detail'
                    ]) and not 'more-detail' in current_str:
                        qa_content += str(current)
                        additional_info_sections += 1
                        logger.info(f"✓ 收集第{additional_info_sections}个额外信息section")

                # 收集其他有意义的非pricing-page-section内容
                elif (hasattr(current, 'name') and hasattr(current, 'get_text') and
                      len(current.get_text().strip()) > 5):
                    content_text = current.get_text().strip()
                    if not any(qa_indicator in content_text.lower() for qa_indicator in [
                        'faq', '常见问题', '支持和服务级别协议', 'sla'
                    ]):
                        qa_content += str(current)
                        additional_info_sections += 1
                        logger.info(f"✓ 收集第{additional_info_sections}个额外信息内容")

            # 3. 查找more-detail容器（FAQ内容）
            more_detail_containers = soup.find_all('div', class_='more-detail')
            faq_sections = 0
            for container in more_detail_containers:
                if container:
                    qa_content += str(container)
                    faq_sections += 1
                    logger.info(f"✓ 找到第{faq_sections}个more-detail容器（FAQ）")

            # 4. 查找pricing-page-section中的SLA内容
            pricing_sections = soup.find_all('div', class_='pricing-page-section')
            sla_sections = 0
            for section in pricing_sections:
                section_text = section.get_text().lower()
                # 直接提取明确的支持和SLA部分
                if '支持和服务级别协议' in section_text or 'sla' in section_text:
                    qa_content += str(section)
                    sla_sections += 1
                    logger.info(f"✓ 找到第{sla_sections}个pricing-page-section支持/SLA内容")

            # 5. 清理QA内容
            if qa_content:
                clean_qa = clean_html_content(qa_content)
                logger.info(f"✓ 提取了Q&A内容：{additional_info_sections}个额外信息，{faq_sections}个FAQ，{sla_sections}个SLA，总长度: {len(clean_qa)}")
                return clean_qa
            else:
                logger.info("⚠ 未找到Q&A内容")
                return ""

        except Exception as e:
            logger.info(f"⚠ Q&A内容提取失败: {e}")
            return ""

    def _extract_qa_fallback(self, soup: BeautifulSoup) -> str:
        """
        备用Q&A提取方法，当找不到technical-azure-selector时使用

        Args:
            soup: BeautifulSoup对象

        Returns:
            Q&A内容HTML字符串
        """
        logger.info("📝 使用备用方法提取Q&A内容...")

        try:
            qa_content = ""

            # 查找more-detail容器
            more_detail_containers = soup.find_all('div', class_='more-detail')
            for container in more_detail_containers:
                if container:
                    qa_content += str(container)
                    logger.info(f"✓ 找到more-detail容器")

            # 查找pricing-page-section中的支持和SLA内容
            pricing_sections = soup.find_all('div', class_='pricing-page-section')
            for section in pricing_sections:
                section_text = section.get_text().lower()
                if '支持和服务级别协议' in section_text or 'sla' in section_text:
                    qa_content += str(section)
                    logger.info(f"✓ 找到pricing-page-section支持/SLA内容")

            if qa_content:
                clean_qa = clean_html_content(qa_content)
                logger.info(f"✓ 备用方法提取了 {len(clean_qa)} 字符的Q&A内容")
                return clean_qa
            else:
                logger.info("⚠ 备用方法未找到Q&A内容")
                return ""

        except Exception as e:
            logger.info(f"⚠ 备用Q&A内容提取失败: {e}")
            return ""
