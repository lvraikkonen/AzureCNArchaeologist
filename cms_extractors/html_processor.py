#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML处理器模块
提供HTML清洗、处理和优化功能
"""

from typing import List, Optional
from bs4 import BeautifulSoup, Comment, NavigableString, Tag


class HTMLProcessor:
    """HTML处理器 - 负责HTML清洗和处理"""
    
    def __init__(self, region_filter=None):
        """
        初始化HTML处理器
        
        Args:
            region_filter: 区域过滤器实例
        """
        self.region_filter = region_filter
    
    def clean_html(self, soup: BeautifulSoup) -> BeautifulSoup:
        """
        清洗HTML，移除不需要的元素
        
        Args:
            soup: 原始BeautifulSoup对象
            
        Returns:
            清洗后的BeautifulSoup对象
        """
        # 复制整个soup，然后进行清洗
        cleaned_soup = BeautifulSoup(str(soup), 'html.parser')
        
        # 1. 移除不需要的元素
        self._remove_unwanted_elements(cleaned_soup)
        
        # 2. 清洗样式和脚本
        self._clean_styles_and_scripts(cleaned_soup)
        
        # 3. 移除导航和交互元素
        self._remove_navigation_elements(cleaned_soup)
        
        # 4. 展开和清理tab结构，保留所有内容
        self._flatten_tab_structures(cleaned_soup)
        
        # 5. 清理属性但保留内容
        self._clean_attributes_keep_content(cleaned_soup)
        
        return cleaned_soup
    
    def _remove_unwanted_elements(self, soup: BeautifulSoup):
        """移除不需要的元素"""
        
        # 移除脚本和样式相关
        unwanted_selectors = [
            'script', 'noscript', 'style', 'link[rel="stylesheet"]',
            'meta[http-equiv]', 'meta[name="viewport"]'
        ]
        
        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()
        
        # 移除注释
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
    
    def _clean_styles_and_scripts(self, soup: BeautifulSoup):
        """清理样式和脚本"""
        
        # 移除内联样式属性
        for tag in soup.find_all():
            if tag.get('style'):
                del tag['style']
            
            # 移除事件处理器
            attrs_to_remove = []
            for attr in tag.attrs:
                if attr.startswith('on'):  # onclick, onload, etc.
                    attrs_to_remove.append(attr)
            
            for attr in attrs_to_remove:
                del tag[attr]
    
    def _remove_navigation_elements(self, soup: BeautifulSoup):
        """移除导航和交互元素"""
        
        # 移除导航相关的class和元素
        navigation_classes = [
            'bread-crumb', 'left-navigation-select', 'documentation-navigation',
            'acn-header-container', 'public_footerpage', 'region-container',
            'software-kind-container', 'dropdown-container', 'dropdown-box'
        ]
        
        for class_name in navigation_classes:
            for element in soup.find_all(class_=class_name):
                element.decompose()
        
        # 移除导航标签
        for tag in soup.find_all(['nav', 'header', 'footer']):
            tag.decompose()
        
        # 移除表单元素
        for tag in soup.find_all(['form', 'input', 'select', 'option', 'button', 'textarea']):
            tag.decompose()
    
    def _flatten_tab_structures(self, soup: BeautifulSoup):
        """展开tab结构，保留所有内容"""
        
        print("    📂 展开tab结构，保留所有内容...")
        
        # 移除tab导航，但保留内容
        for tab_nav in soup.find_all('ul', class_='tab-nav'):
            tab_nav.decompose()
        
        # 展开tab内容面板
        tab_panels = soup.find_all('div', class_='tab-panel')
        
        for panel in tab_panels:
            # 将面板内容提升到父级
            if panel.parent:
                # 获取面板中的所有子元素
                children = list(panel.children)
                
                # 将子元素插入到面板的位置
                for child in children:
                    if hasattr(child, 'extract'):
                        child.extract()
                        panel.insert_before(child)
                
                # 移除空的面板容器
                panel.decompose()
        
        # 处理其他可能的tab容器
        tab_containers = soup.find_all('div', class_=lambda x: x and any(
            keyword in ' '.join(x) for keyword in ['tab-content', 'tab-container', 'technical-azure-selector']
        ))
        
        for container in tab_containers:
            if container.parent:
                children = list(container.children)
                for child in children:
                    if hasattr(child, 'extract'):
                        child.extract()
                        container.insert_before(child)
                container.decompose()
    
    def _clean_attributes_keep_content(self, soup: BeautifulSoup):
        """清理属性但保留内容结构"""
        
        # 要保留的重要属性
        important_attrs = {'id', 'class', 'href', 'src', 'alt', 'title', 'colspan', 'rowspan'}
        
        # 要保留的重要class（会进一步过滤）
        important_classes = {
            'common-banner', 'common-banner-image', 'common-banner-title',
            'pricing-page-section', 'more-detail', 'storage-specific-content',
            'icon', 'icon-plus'  # 保留FAQ展开图标的class
        }
        
        for tag in soup.find_all():
            if not hasattr(tag, 'attrs'):
                continue
                
            # 移除不重要的属性
            attrs_to_remove = []
            for attr in tag.attrs:
                if attr not in important_attrs:
                    attrs_to_remove.append(attr)
            
            for attr in attrs_to_remove:
                del tag[attr]
            
            # 过滤class属性
            if tag.get('class'):
                current_classes = tag['class'] if isinstance(tag['class'], list) else [tag['class']]
                filtered_classes = [cls for cls in current_classes if cls in important_classes]
                if filtered_classes:
                    tag['class'] = filtered_classes
                else:
                    if 'class' in tag.attrs:
                        del tag['class']
    
    def remove_empty_containers(self, soup: BeautifulSoup):
        """移除空的容器"""
        
        # 多次清理，因为移除某些元素后可能产生新的空容器
        for _ in range(3):
            empty_elements = []
            
            for element in soup.find_all(['div', 'section', 'article', 'span']):
                # 检查元素是否为空
                if not element.get_text(strip=True) and not element.find_all(['img', 'input', 'button', 'table']):
                    empty_elements.append(element)
            
            for element in empty_elements:
                element.decompose()
                
            if not empty_elements:  # 如果没有找到空元素，跳出循环
                break
    
    def copy_table_structure(self, original_table: Tag, new_table: Tag, soup: BeautifulSoup):
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
    
    def is_navigation_element(self, element: Tag) -> bool:
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
    
    def create_simple_element(self, original_element: Tag, soup: BeautifulSoup, 
                             table_class: str = "pricing-table") -> Optional[Tag]:
        """创建简化的内容元素，减少嵌套"""
        
        if not original_element or not hasattr(original_element, 'name') or not original_element.name:
            return None
        
        try:
            # 创建新元素
            new_element = soup.new_tag(original_element.name)
            
            # 只保留最重要的属性
            if original_element.get('id'):
                new_element['id'] = original_element['id']
            
            if original_element.name == 'table':
                new_element['class'] = table_class
                # 保留colspan和rowspan
                for attr in ['colspan', 'rowspan']:
                    if original_element.get(attr):
                        new_element[attr] = original_element[attr]
            
            # 针对不同元素类型进行处理
            if original_element.name == 'table':
                # 表格特殊处理：保持完整结构
                self.copy_table_structure(original_element, new_element, soup)
            
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
                            link_element = self.create_simple_element(child, soup, table_class)
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
                            link_element = self.create_simple_element(child, soup, table_class)
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
                # 列表：保留结构但简化，也要处理链接
                for li in original_element.find_all('li', recursive=False):
                    new_li = soup.new_tag('li')
                    
                    # 检查li中是否有链接
                    if li.find('a'):
                        for child in li.children:
                            if hasattr(child, 'name') and child.name == 'a':
                                link_element = self.create_simple_element(child, soup, table_class)
                                if link_element:
                                    new_li.append(link_element)
                            elif hasattr(child, 'strip'):
                                text = child.strip()
                                if text:
                                    new_li.append(text)
                    else:
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