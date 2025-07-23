#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML处理工具函数
从ContentExtractor中提取的纯工具函数，去除业务逻辑依赖
"""

import re
from typing import Optional, Set, List
from bs4 import BeautifulSoup, Tag


def create_simple_element(original_element: Tag, soup: BeautifulSoup) -> Optional[Tag]:
    """
    创建简化的内容元素，减少嵌套
    
    Args:
        original_element: 原始HTML元素
        soup: BeautifulSoup对象
        
    Returns:
        简化后的HTML元素
    """
    if not original_element or not hasattr(original_element, 'name') or not original_element.name:
        return None

    try:
        # 创建新元素
        new_element = soup.new_tag(original_element.name)

        # 只保留最重要的属性
        if original_element.get('id'):
            new_element['id'] = original_element['id']

        # 针对不同元素类型进行处理
        if original_element.name == 'table':
            # 表格特殊处理：保持完整结构
            copy_table_structure(original_element, new_element, soup)

        elif original_element.name == 'a':
            # 链接特殊处理：保留href和文本
            href = original_element.get('href')
            if href:
                new_element['href'] = href

            # 保留aria-label等可访问性属性
            for attr in ['aria-label', 'title', 'target']:
                if original_element.get(attr):
                    new_element[attr] = original_element[attr]

            # 复制链接文本
            link_text = original_element.get_text(strip=True)
            if link_text:
                new_element.string = link_text

        elif original_element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            # 标题：保留文本，但也检查是否包含链接
            if original_element.find('a'):
                # 如果标题中包含链接，保持结构
                for child in original_element.children:
                    if hasattr(child, 'name') and child.name == 'a':
                        link_element = create_simple_element(child, soup)
                        if link_element:
                            new_element.append(link_element)
                    elif hasattr(child, 'strip'):
                        text = child.strip()
                        if text:
                            new_element.append(text)
            else:
                # 普通标题，只保留文本
                text_content = original_element.get_text(strip=True)
                if text_content:
                    new_element.string = text_content

        elif original_element.name == 'p':
            # 段落：可能包含链接，需要保持结构
            if original_element.find('a'):
                # 段落中包含链接，保持混合内容
                for child in original_element.children:
                    if hasattr(child, 'name') and child.name == 'a':
                        link_element = create_simple_element(child, soup)
                        if link_element:
                            new_element.append(link_element)
                    elif hasattr(child, 'strip'):
                        text = child.strip()
                        if text:
                            new_element.append(text)
            else:
                # 普通段落，只保留文本
                text_content = original_element.get_text(strip=True)
                if text_content:
                    new_element.string = text_content

        elif original_element.name in ['ul', 'ol']:
            # 列表：保留结构但简化
            for li in original_element.find_all('li', recursive=False):
                new_li = soup.new_tag('li')

                # 检查是否为FAQ结构 - 使用faq_utils
                from .faq_utils import is_faq_item, process_faq_item

                if is_faq_item(li):
                    # 处理FAQ项
                    process_faq_item(li, new_li, soup)
                elif li.find('a') and not li.find('i', class_='icon icon-plus'):
                    # 普通包含链接的列表项
                    for child in li.children:
                        if hasattr(child, 'name') and child.name == 'a':
                            link_element = create_simple_element(child, soup)
                            if link_element:
                                new_li.append(link_element)
                        elif hasattr(child, 'strip'):
                            text = child.strip()
                            if text:
                                new_li.append(text)
                else:
                    # 普通列表项
                    li_text = li.get_text(strip=True)
                    if li_text:
                        new_li.string = li_text

                if new_li.get_text(strip=True) or new_li.find_all():
                    new_element.append(new_li)

        else:
            # 其他元素：提取文本内容
            text_content = original_element.get_text(strip=True)
            if text_content:
                new_element.string = text_content

        return new_element if (new_element.get_text(strip=True) or new_element.find_all()) else None

    except Exception as e:
        print(f"    ⚠ 创建简化元素失败: {e}")
        return None


def copy_table_structure(original_table: Tag, new_table: Tag, soup: BeautifulSoup):
    """
    复制表格结构，确保完整性
    
    Args:
        original_table: 原始表格
        new_table: 新表格
        soup: BeautifulSoup对象
    """
    # 直接复制所有行
    for tr in original_table.find_all('tr'):
        new_tr = soup.new_tag('tr')

        # 复制所有单元格
        for cell in tr.find_all(['th', 'td']):
            new_cell = soup.new_tag(cell.name)

            # 保留重要属性
            for attr in ['colspan', 'rowspan']:
                if cell.get(attr):
                    new_cell[attr] = cell[attr]

            # 复制单元格文本
            cell_text = cell.get_text(strip=True)
            if cell_text:
                new_cell.string = cell_text

            new_tr.append(new_cell)

        if new_tr.find_all():  # 只添加非空行
            new_table.append(new_tr)


def is_navigation_element(element: Tag) -> bool:
    """
    判断是否为导航元素
    
    Args:
        element: HTML元素
        
    Returns:
        是否为导航元素
    """
    if not hasattr(element, 'get'):
        return False

    # 检查class属性
    classes = element.get('class', [])
    if isinstance(classes, str):
        classes = [classes]

    navigation_keywords = [
        'nav', 'menu', 'breadcrumb', 'tab-nav', 'dropdown', 'region-container',
        'software-kind', 'header', 'footer', 'sidebar'
    ]

    for class_name in classes:
        if any(keyword in class_name.lower() for keyword in navigation_keywords):
            return True

    return False


def clean_html_content(content: str) -> str:
    """
    清理HTML内容中的多余标签和符号
    
    Args:
        content: 原始HTML内容
        
    Returns:
        清理后的HTML内容
    """
    if not content:
        return content

    # 移除多余的换行符和空白符
    content = re.sub(r'\n+', ' ', content)  # 将多个换行符替换为单个空格
    content = re.sub(r'\s+', ' ', content)  # 将多个空白符替换为单个空格

    # 移除多余的div标签包装（保留有用的class和id）
    # 只移除纯粹的包装div，保留有意义的div
    content = re.sub(r'<div>\s*</div>', '', content)  # 移除空的div标签

    # 清理标签间的多余空白
    content = re.sub(r'>\s+<', '><', content)  # 移除标签间的空白

    # 移除开头和结尾的空白
    content = content.strip()

    return content


def preprocess_image_paths(soup: BeautifulSoup) -> BeautifulSoup:
    """
    预处理图片路径，添加{img_hostname}占位符
    
    Args:
        soup: BeautifulSoup对象
        
    Returns:
        处理后的BeautifulSoup对象
    """
    print("🖼️ 预处理图片路径...")

    # 处理img标签的src属性
    img_count = 0
    for img in soup.find_all('img'):
        src = img.get('src')
        if src and src.startswith('/'):
            img['src'] = f"{{img_hostname}}{src}"
            img_count += 1

    # 处理style属性中的background-image
    style_count = 0
    for element in soup.find_all(style=True):
        style = element.get('style', '')
        if 'background-image:' in style and 'url(' in style:
            # 匹配 url("/path/to/image") 或 url('/path/to/image')
            pattern = r'url\(["\']?(/[^"\']*?)["\']?\)'
            def replace_url(match):
                path = match.group(1)
                return f'url("{{{img_hostname}}}{path}")'

            new_style = re.sub(pattern, replace_url, style)
            if new_style != style:
                element['style'] = new_style
                style_count += 1

    # 处理data-config属性中的图片路径
    data_config_count = 0
    for element in soup.find_all(attrs={'data-config': True}):
        data_config = element.get('data-config', '')
        if data_config and ('backgroundImage' in data_config or 'background-image' in data_config):
            # 匹配 backgroundImage 或 background-image 后面的图片路径
            pattern = r'(["\'](backgroundImage|background-image)["\']:\s*["\'])(/[^"\']*?)(["\'])'
            def replace_bg_image(match):
                prefix = match.group(1)
                path = match.group(3)
                suffix = match.group(4)
                return f'{prefix}{{img_hostname}}{path}{suffix}'

            new_data_config = re.sub(pattern, replace_bg_image, data_config)
            if new_data_config != data_config:
                element['data-config'] = new_data_config
                data_config_count += 1

    print(f"  ✓ 处理了 {img_count} 个img标签、{style_count} 个style属性和 {data_config_count} 个data-config属性")

    return soup