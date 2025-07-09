#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容提取器模块
提供HTML内容提取和结构化功能
"""

from typing import List, Optional, Callable, Set
from bs4 import BeautifulSoup, Tag


class ContentExtractor:
    """内容提取器 - 负责从HTML中提取有意义的内容"""
    
    def __init__(self):
        """初始化内容提取器"""
        pass
    
    def extract_main_content(self, soup: BeautifulSoup, 
                           important_section_titles: Set[str],
                           extract_banner_callback: Callable) -> BeautifulSoup:
        """
        提取主要内容区域，减少div嵌套
        
        Args:
            soup: 已清洗的BeautifulSoup对象
            important_section_titles: 重要的section标题集合
            extract_banner_callback: 提取横幅的回调函数
            
        Returns:
            提取后的主要内容BeautifulSoup对象
        """
        
        print("    🎯 提取主要内容区域...")
        
        # 创建新的内容容器
        content_soup = BeautifulSoup("", 'html.parser')
        
        # 查找主要内容区域
        main_area = self._find_main_content_area(soup)
        
        # 直接提取内容元素，不添加额外包装
        content_elements = []
        
        # 1. 提取产品横幅
        banner_elements = extract_banner_callback(main_area, content_soup)
        if banner_elements:
            content_elements.extend(banner_elements)
        
        # 2. 提取其他内容
        content_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'table', 'a']
        
        processed_elements = set()
        
        for element in main_area.find_all(content_tags):
            # 避免重复处理
            if id(element) in processed_elements:
                continue
            
            # 跳过空元素
            if not element.get_text(strip=True):
                continue
            
            # 跳过导航相关元素
            if self._is_navigation_element(element):
                continue
            
            # 跳过已经处理过的横幅内容
            if element.find_parent('div', class_='common-banner'):
                continue
            
            # 跳过表格内部的元素（避免重复处理）
            if element.find_parent('table'):
                continue
            
            # 跳过已经被FAQ处理过的元素（避免重复处理）
            if element.find_parent('li') and element.find_parent('li').find('i', class_='icon icon-plus'):
                continue
            
            # 检查是否为重要的section标题 - 优先保留
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                if self._is_important_section_title(element, important_section_titles):
                    # 重要标题，直接保留
                    clean_element = self._create_simple_element(element, content_soup)
                    if clean_element:
                        content_elements.append(clean_element)
                    processed_elements.add(id(element))
                    continue
                elif self._is_table_related_title(element, important_section_titles):
                    # 普通表格标题，跳过以避免重复
                    continue
            
            # 只处理独立的链接，跳过嵌套在其他元素中的链接
            if element.name == 'a' and element.find_parent(['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                continue
            
            # 直接复制有意义的元素
            clean_element = self._create_simple_element(element, content_soup)
            if clean_element:
                content_elements.append(clean_element)
                
            # 标记已处理
            processed_elements.add(id(element))
        
        # 将所有内容元素直接添加到soup中，不添加额外包装
        for element in content_elements:
            content_soup.append(element)
        
        elements_count = len(content_elements)
        print(f"    ✓ 提取了 {elements_count} 个内容元素（简化结构）")
        
        return content_soup
    
    def _find_main_content_area(self, soup: BeautifulSoup) -> BeautifulSoup:
        """查找主要内容区域"""
        
        # 查找主要内容区域
        main_content_areas = [
            soup.find('main'),
            soup.find('div', class_='main-content'),
            soup.find('div', class_='content'),
            soup.find('body')
        ]
        
        main_area = None
        for area in main_content_areas:
            if area:
                main_area = area
                break
        
        if not main_area:
            main_area = soup
            
        return main_area
    
    def _is_important_section_title(self, element: Tag, important_section_titles: Set[str]) -> bool:
        """判断是否为重要的section标题，需要保留"""
        
        if not element or not hasattr(element, 'get_text'):
            return False
        
        title_text = element.get_text(strip=True).lower()
        
        # 检查是否匹配重要的section标题
        for important_title in important_section_titles:
            if important_title.lower() in title_text:
                print(f"    ✓ 保留重要section标题: {title_text}")
                return True
        
        return False
    
    def _is_table_related_title(self, element: Tag, important_section_titles: Set[str]) -> bool:
        """判断是否为表格相关标题（避免重复提取），但不过滤重要的section标题"""
        
        # 首先检查是否为重要的section标题，如果是则不过滤
        if self._is_important_section_title(element, important_section_titles):
            return False
        
        # 检查标题文本是否包含表格相关关键词
        title_text = element.get_text(strip=True).lower()
        table_keywords = ['系列', 'tier', '层级', '实例', 'gen', 'v2', 'v3', 'v4']
        
        if any(keyword in title_text for keyword in table_keywords):
            # 检查是否靠近表格
            next_sibling = element.find_next_sibling()
            if next_sibling and next_sibling.name == 'table':
                return True
            
            # 检查是否在包含表格的容器中
            parent_with_table = element.find_parent()
            if parent_with_table and parent_with_table.find('table'):
                return True
        
        return False
    
    def _is_navigation_element(self, element: Tag) -> bool:
        """判断是否为导航元素"""
        
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
    
    def _create_simple_element(self, original_element: Tag, soup: BeautifulSoup) -> Optional[Tag]:
        """创建简化的内容元素，减少嵌套"""
        
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
                self._copy_table_structure(original_element, new_element, soup)
            
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
                            link_element = self._create_simple_element(child, soup)
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
                            link_element = self._create_simple_element(child, soup)
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
                # 列表：保留结构但简化，也要处理链接，特别处理FAQ结构
                # print(f"    📋 处理列表元素: {original_element.name}, 包含 {len(original_element.find_all('li', recursive=False))} 个列表项")
                
                # 检查是否为FAQ列表
                is_faq_list = any(self._is_faq_item(li) for li in original_element.find_all('li', recursive=False))
                
                # 如果是FAQ列表，添加特殊class
                if is_faq_list:
                    new_element['class'] = 'faq-list'
                
                for li in original_element.find_all('li', recursive=False):
                    new_li = soup.new_tag('li')
                    
                    # 检查是否为FAQ结构 (有icon和div结构) - 优先检查
                    if self._is_faq_item(li):
                        # 处理FAQ项
                        # print(f"    ✓ 发现FAQ项，正在处理...")
                        self._process_faq_item(li, new_li, soup)
                    elif li.find('a') and not li.find('i', class_='icon icon-plus'):
                        # 普通包含链接的列表项（排除FAQ项）
                        # print(f"    📎 处理包含链接的列表项")
                        for child in li.children:
                            if hasattr(child, 'name') and child.name == 'a':
                                link_element = self._create_simple_element(child, soup)
                                if link_element:
                                    new_li.append(link_element)
                            elif hasattr(child, 'strip'):
                                text = child.strip()
                                if text:
                                    new_li.append(text)
                    else:
                        # 普通列表项
                        # print(f"    📄 处理普通列表项")
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
    
    def _copy_table_structure(self, original_table: Tag, new_table: Tag, soup: BeautifulSoup):
        """复制表格结构，确保完整性"""
        
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
    
    def _is_faq_item(self, li: Tag) -> bool:
        """检查是否为FAQ项结构"""
        
        # 检查是否有icon和div结构
        has_icon = li.find('i', class_='icon icon-plus')
        has_div = li.find('div')
        
        if has_icon and has_div:
            # 检查div内是否有a标签（问题）和section标签（答案）
            div = li.find('div')
            has_question = div.find('a')
            has_answer = div.find('section')
            
            # print(f"    🔍 FAQ检查: icon={bool(has_icon)}, div={bool(has_div)}, question={bool(has_question)}, answer={bool(has_answer)}")
            
            return bool(has_question and has_answer)
        
        return False
    
    def _process_faq_item(self, li: Tag, new_li: Tag, soup: BeautifulSoup):
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