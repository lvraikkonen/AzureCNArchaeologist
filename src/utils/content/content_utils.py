#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容处理工具函数
处理主要内容区域提取、section标题识别、banner处理等
"""

import re
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup, Tag

from src.core.logging import get_logger

logger = get_logger(__name__)


def find_main_content_area(soup: BeautifulSoup) -> Optional[Tag]:
    """查找主要内容区域"""
    # 优先查找带有特定class或id的主要内容区域
    content_selectors = [
        'main',
        '[role="main"]',
        '.main-content',
        '.content',
        '#main-content',
        '#content',
        '.page-content'
    ]
    
    for selector in content_selectors:
        main_content = soup.select_one(selector)
        if main_content:
            return main_content
    
    # 如果没有找到，返回body
    return soup.find('body') or soup


def is_important_section_title(element: Tag, important_section_titles: List[str]) -> bool:
    """
    判断是否为重要的section标题
    
    Args:
        element: HTML元素
        important_section_titles: 重要section标题列表
        
    Returns:
        是否为重要标题
    """
    if not element or not hasattr(element, 'get_text'):
        return False
        
    element_text = element.get_text(strip=True).lower()
    
    # 检查是否包含重要的section标题关键词
    for title in important_section_titles:
        if title.lower() in element_text:
            return True
    
    return False


def extract_banner_text_content(banner: Tag) -> Dict[str, Any]:
    """
    从banner中提取文本内容（标题、描述等）
    
    Args:
        banner: banner HTML元素
        
    Returns:
        提取的banner内容字典
    """
    if not banner:
        return {}
    
    banner_content = {}
    
    # 提取标题 (h1, h2 等)
    title_element = banner.find(['h1', 'h2', 'h3'])
    if title_element:
        banner_content['title'] = title_element.get_text(strip=True)
    
    # 提取描述性段落
    paragraphs = banner.find_all('p')
    descriptions = []
    for p in paragraphs:
        text = p.get_text(strip=True)
        if text and len(text) > 10:  # 过滤过短的文本
            descriptions.append(text)
    
    if descriptions:
        banner_content['description'] = ' '.join(descriptions[:3])  # 最多3个段落
    
    # 提取链接
    links = banner.find_all('a', href=True)
    if links:
        banner_content['links'] = []
        for link in links[:5]:  # 最多5个链接
            link_text = link.get_text(strip=True)
            link_href = link.get('href')
            if link_text and link_href:
                banner_content['links'].append({
                    'text': link_text,
                    'href': link_href
                })
    
    # 提取列表项
    list_items = banner.find_all('li')
    if list_items:
        banner_content['features'] = []
        for li in list_items[:10]:  # 最多10个特性
            feature_text = li.get_text(strip=True)
            if feature_text and len(feature_text) > 5:
                banner_content['features'].append(feature_text)
    
    return banner_content


def standardize_banner_images(soup: BeautifulSoup) -> BeautifulSoup:
    """
    标准化banner中的图片，添加占位符
    
    Args:
        soup: BeautifulSoup对象
        
    Returns:
        处理后的BeautifulSoup对象
    """
    print("🖼️ 标准化banner图片...")
    
    # 查找banner区域
    banner_selectors = [
        '.banner',
        '.hero',
        '.jumbotron', 
        '.page-header',
        'header',
        '.product-banner'
    ]
    
    processed_count = 0
    
    for selector in banner_selectors:
        banners = soup.select(selector)
        
        for banner in banners:
            # 处理banner中的图片
            images = banner.find_all('img')
            
            for img in images:
                src = img.get('src')
                if src:
                    if src.startswith('/'):
                        img['src'] = f"{{img_hostname}}{src}"
                        processed_count += 1
                    elif not src.startswith(('http', 'https', 'data:')):
                        # 相对路径
                        img['src'] = f"{{img_hostname}}/{src}"
                        processed_count += 1
            
            # 处理background-image样式
            for element in banner.find_all(style=True):
                style = element.get('style', '')
                if 'background-image' in style:
                    # 替换相对路径
                    new_style = re.sub(
                        r'background-image:\s*url\(["\']?(/[^"\']*?)["\']?\)',
                        r'background-image: url("{img_hostname}\1")',
                        style
                    )
                    if new_style != style:
                        element['style'] = new_style
                        processed_count += 1
    
    if processed_count > 0:
        print(f"  ✓ 标准化了 {processed_count} 个banner图片")
    
    return soup


def extract_structured_content(soup: BeautifulSoup, 
                             important_section_titles: List[str]) -> Dict[str, Any]:
    """
    提取结构化内容，包括各个重要section
    
    Args:
        soup: BeautifulSoup对象
        important_section_titles: 重要section标题列表
        
    Returns:
        结构化内容字典
    """
    structured_content = {
        'sections': [],
        'pricing_tables': [],
        'feature_lists': [],
        'call_to_actions': []
    }
    
    # 提取重要sections
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    
    for heading in headings:
        if is_important_section_title(heading, important_section_titles):
            section_content = {
                'title': heading.get_text(strip=True),
                'level': heading.name,
                'content': ''
            }
            
            # 收集该标题下的内容
            next_sibling = heading.find_next_sibling()
            content_parts = []
            
            while next_sibling and next_sibling.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                if next_sibling.get_text(strip=True):
                    content_parts.append(next_sibling.get_text(strip=True))
                next_sibling = next_sibling.find_next_sibling()
            
            section_content['content'] = ' '.join(content_parts[:3])  # 限制内容长度
            structured_content['sections'].append(section_content)
    
    # 提取定价表格
    tables = soup.find_all('table')
    for table in tables:
        # 简单的表格内容提取
        table_text = table.get_text(strip=True)
        if any(keyword in table_text.lower() for keyword in ['价格', 'price', '费用', 'cost']):
            structured_content['pricing_tables'].append({
                'content': table_text[:500]  # 限制长度
            })
    
    # 提取特性列表
    feature_lists = soup.find_all(['ul', 'ol'])
    for ul in feature_lists:
        items = ul.find_all('li')
        if len(items) >= 2:  # 至少2个项目才算特性列表
            features = [li.get_text(strip=True) for li in items[:10]]  # 最多10个特性
            if any(len(f) > 10 for f in features):  # 过滤过短的特性
                structured_content['feature_lists'].append({
                    'items': features
                })
    
    # 提取行动号召链接
    cta_keywords = ['开始使用', '立即试用', '了解更多', 'get started', 'learn more', 'try now']
    links = soup.find_all('a', href=True)
    
    for link in links:
        link_text = link.get_text(strip=True).lower()
        if any(keyword.lower() in link_text for keyword in cta_keywords):
            structured_content['call_to_actions'].append({
                'text': link.get_text(strip=True),
                'href': link.get('href')
            })
    
    return structured_content


# ========== FAQ相关功能 ==========
# 从faq_utils.py合并过来的FAQ处理功能

def is_faq_item(li: Tag) -> bool:
    """检查是否为FAQ项结构"""
    # 检查是否有icon和div结构
    has_icon = li.find('i', class_='icon icon-plus')
    has_div = li.find('div')

    if has_icon and has_div:
        # 检查div内是否有a标签（问题）和section标签（答案）
        div = li.find('div')
        has_question = div.find('a')
        has_answer = div.find('section')

        return bool(has_question and has_answer)

    return False


def process_faq_item(li: Tag, new_li: Tag, soup: BeautifulSoup):
    """处理FAQ项，提取问题和答案，使用美化的HTML结构"""
    div = li.find('div')
    if not div:
        return

    # 提取问题
    question_a = div.find('a')
    if question_a:
        question_text = question_a.get_text(strip=True)
        if question_text:
            # 创建问题div容器
            question_div = soup.new_tag('div', **{'class': 'faq-question'})
            question_div.string = question_text
            new_li.append(question_div)

    # 提取答案
    answer_section = div.find('section')
    if answer_section:
        answer_text = answer_section.get_text(strip=True)
        if answer_text:
            # 创建答案div容器
            answer_div = soup.new_tag('div', **{'class': 'faq-answer'})
            answer_div.string = answer_text
            new_li.append(answer_div)


def extract_qa_content(soup: BeautifulSoup) -> str:
    """提取Q&A内容以及支持和服务级别协议内容"""
    logger.info("提取Q&A内容...")

    qa_sections = []
    
    # 查找常见问题部分
    faq_keywords = ['常见问题', 'faq', 'frequently asked questions', '问题解答']
    
    for keyword in faq_keywords:
        # 查找包含关键词的标题
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'], 
                                string=lambda text: text and keyword.lower() in text.lower())
        
        for heading in headings:
            # 查找标题后的内容
            content_element = heading.find_next_sibling()
            
            if content_element:
                qa_text = content_element.get_text(strip=True)
                if qa_text and len(qa_text) > 50:  # 过滤过短的内容
                    qa_sections.append({
                        'section': keyword,
                        'content': qa_text[:1000]  # 限制长度
                    })
    
    # 查找支持相关内容
    support_keywords = ['支持', 'support', '服务级别协议', 'sla', 'service level']
    
    for keyword in support_keywords:
        elements = soup.find_all(string=lambda text: text and keyword.lower() in text.lower())
        
        for element in elements[:3]:  # 限制数量
            parent = element.parent
            if parent:
                support_text = parent.get_text(strip=True)
                if support_text and len(support_text) > 30:
                    qa_sections.append({
                        'section': keyword,
                        'content': support_text[:500]
                    })
    
    # 合并所有Q&A内容
    if qa_sections:
        combined_qa = '\n\n'.join([f"## {section['section']}\n{section['content']}"
                                  for section in qa_sections[:5]])  # 限制为前5个
        logger.info(f"提取了 {len(qa_sections)} 个Q&A部分")
        return combined_qa
    else:
        logger.warning("未找到Q&A内容")
        return ""


# ========== Section分类功能 ==========

def classify_pricing_section(section: Tag) -> str:
    """
    智能分类pricing-page-section，判断section类型
    
    Args:
        section: BeautifulSoup的Tag对象，代表一个pricing-page-section
        
    Returns:
        section类型：'faq', 'sla', 'content', 'other'
    """
    if not section:
        return 'other'
    
    # 获取section的文本内容
    section_text = section.get_text().strip()
    section_html = str(section).lower()
    
    # FAQ相关的正则模式
    faq_patterns = [
        r'常见问题',
        r'FAQs',
        r'frequently\s+asked\s+questions',
        r'q\s*&\s*a',
        r'more-detail',  # 特殊class标识
    ]
    
    # SLA/支持相关的正则模式
    sla_patterns = [
        r'支持和服务级别协议',
        r'Support\s*&\s*sla',
        r'service\s+level\s+agreement',
    ]
    
    # 检查是否为FAQ类型
    for pattern in faq_patterns:
        if re.search(pattern, section_text, re.IGNORECASE):
            logger.debug(f"检测到FAQ section: {pattern}")
            return 'faq'
        if re.search(pattern, section_html):
            logger.debug(f"检测到FAQ section (HTML): {pattern}")
            return 'faq'
    
    # 检查是否为SLA/支持类型
    for pattern in sla_patterns:
        if re.search(pattern, section_text, re.IGNORECASE):
            logger.debug(f"检测到SLA section: {pattern}")
            return 'sla'
        if re.search(pattern, section_html):
            logger.debug(f"检测到SLA section (HTML): {pattern}")
            return 'sla'
    
    
    # 检查section长度，短内容可能是导航或其他
    if len(section_text.strip()) < 50:
        logger.debug("section内容过短，归类为other")
        return 'other'
    
    # 检查是否包含表格或结构化内容（通常是产品功能说明）
    if section.find('table') or section.find('ul') or section.find('ol'):
        # 如果有结构化内容但没有FAQ/SLA标识，很可能是产品内容
        logger.debug("检测到结构化内容，归类为content")
        return 'content'
    
    # 默认归类为content（产品相关内容）
    logger.debug("默认归类为content")
    return 'content'


def filter_sections_by_type(sections: List[Tag], 
                          include_types: List[str] = None, 
                          exclude_types: List[str] = None) -> List[Tag]:
    """
    根据类型过滤sections
    
    Args:
        sections: section列表
        include_types: 包含的类型列表
        exclude_types: 排除的类型列表
        
    Returns:
        过滤后的section列表
    """
    if not sections:
        return []
    
    filtered_sections = []
    
    for section in sections:
        section_type = classify_pricing_section(section)
        
        # 检查包含条件
        if include_types and section_type not in include_types:
            continue
            
        # 检查排除条件  
        if exclude_types and section_type in exclude_types:
            continue
            
        filtered_sections.append(section)
    
    return filtered_sections