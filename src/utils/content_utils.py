#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容处理工具函数
处理主要内容区域提取、section标题识别、banner处理等
"""

import re
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup, Tag


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