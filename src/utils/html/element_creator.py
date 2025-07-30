#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML元素创建和处理工具
纯HTML处理函数，无业务逻辑依赖
"""

from typing import Optional
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
            # 列表：保留结构但简化（移除FAQ依赖，纯HTML处理）
            for li in original_element.find_all('li', recursive=False):
                new_li = soup.new_tag('li')

                if li.find('a') and not li.find('i', class_='icon icon-plus'):
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