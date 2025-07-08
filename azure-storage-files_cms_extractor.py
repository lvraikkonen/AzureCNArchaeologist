#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Azure Storage Files页面CMS导入HTML提取器
基于MySQL提取器架构，专门处理Azure Files产品页面的内容提取和区域化处理
修改版：保留重要的section标题
"""

import json
import os
import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup, Comment, NavigableString, Tag

# 导入现有的处理模块
try:
    from utils.enhanced_html_processor import (
        RegionFilterProcessor, 
        FixedHTMLProcessor, 
        verify_table_content
    )
except ImportError:
    print("❌ 无法导入HTML处理器，请确保utils/enhanced_html_processor.py存在")
    exit(1)


class AzureStorageFilesCMSExtractor:
    """Azure Storage Files页面CMS HTML提取器"""
    
    def __init__(self, config_file: str = "soft-category.json", output_dir: str = "storage_files_output"):
        self.config_file = config_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 区域映射
        self.region_names = {
            "north-china": "中国北部",
            "east-china": "中国东部",
            "north-china2": "中国北部2", 
            "east-china2": "中国东部2",
            "north-china3": "中国北部3",
            "east-china3": "中国东部3"
        }
        
        # 重要的section标题，需要保留
        self.important_section_titles = {
            "定价详细信息", "定价详情", "pricing details",
            "了解存储选项", "存储选项", "storage options",
            "数据存储价格", "存储价格", "data storage pricing", "storage pricing",
            "事务和数据传输价格", "事务价格", "transaction pricing", "数据传输价格",
            "文件同步价格", "同步价格", "file sync pricing",
            "常见问题", "faq", "frequently asked questions"
        }
        
        # 存储冗余类型标题，也是重要的section标题
        self.storage_redundancy_titles = {
            "lrs", "grs", "zrs", "ragrs", "gzrs", "ra-grs",
            "本地冗余存储", "地理冗余存储", "区域冗余存储", 
            "读取访问地理冗余存储", "地理区域冗余存储"
        }
        
        # 初始化处理器
        self.region_filter = RegionFilterProcessor(config_file)
        self.html_processor = FixedHTMLProcessor(self.region_filter)
        self.original_soup = None  # 用于保存原始HTML的soup对象
        
        print(f"✓ Azure Storage Files CMS提取器初始化完成")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"🌍 支持区域: {list(self.region_names.keys())}")
    
    def extract_cms_html_for_region(self, html_file_path: str, region: str) -> Dict[str, any]:
        """为指定区域提取CMS友好的HTML"""
        
        print(f"\n🔧 开始提取Azure Storage Files CMS HTML")
        print(f"📁 源文件: {html_file_path}")
        print(f"🌍 目标区域: {region} ({self.region_names.get(region, region)})")
        print("=" * 70)
        
        if not os.path.exists(html_file_path):
            raise FileNotFoundError(f"HTML文件不存在: {html_file_path}")
        
        if region not in self.region_names:
            raise ValueError(f"不支持的区域: {region}。支持的区域: {list(self.region_names.keys())}")
        
        start_time = datetime.now()
        
        try:
            # 1. 加载和解析HTML
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            # 保存原始soup的引用，用于提取meta信息
            self.original_soup = BeautifulSoup(html_content, 'html.parser')
            print(f"✓ HTML文件加载成功，大小: {len(html_content):,} 字符")
            
            # 2. 设置区域过滤器
            self.region_filter.set_active_region(region, "Storage Files")
            
            # 3. 提取和清洗内容
            cleaned_soup = self._extract_and_clean_files_content(soup, region)
            
            # 4. 应用区域过滤
            filtered_count, retained_count = self._apply_region_filtering(cleaned_soup, region)
            
            # 5. 进一步清洗以适应CMS
            cms_ready_soup = self._prepare_for_cms(cleaned_soup, region)
            
            # 6. 生成最终HTML
            final_html = self._build_final_html(cms_ready_soup, region)
            
            # 7. 验证结果
            verification = self._verify_extraction_result(final_html)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = {
                "success": True,
                "region": {
                    "id": region,
                    "name": self.region_names[region]
                },
                "html_content": final_html,
                "statistics": {
                    "original_size": len(html_content),
                    "final_size": len(final_html),
                    "compression_ratio": round(len(final_html) / len(html_content), 3),
                    "filtered_tables": filtered_count,
                    "retained_tables": retained_count,
                    "processing_time": processing_time
                },
                "verification": verification,
                "extraction_info": {
                    "source_file": html_file_path,
                    "extracted_at": start_time.isoformat(),
                    "extraction_method": "cms_optimized_storage_files",
                    "version": "1.2_files_cms_with_redundancy_titles"
                }
            }
            
            print(f"\n✅ Azure Storage Files CMS HTML提取完成！")
            print(f"📄 压缩比: {result['statistics']['compression_ratio']*100:.1f}%")
            print(f"📊 保留表格: {retained_count} 个")
            print(f"⏱️ 处理时间: {processing_time:.2f}秒")
            
            return result
            
        except Exception as e:
            print(f"❌ 提取失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "region": {"id": region, "name": self.region_names.get(region, region)}
            }
    
    def _extract_and_clean_files_content(self, soup: BeautifulSoup, region: str) -> BeautifulSoup:
        """提取和清洗Azure Files特定内容，保留完整的页面内容"""
        
        print("🧹 第一步：提取和清洗Azure Files完整内容...")
        
        # 复制整个soup，然后进行清洗
        cleaned_soup = BeautifulSoup(str(soup), 'html.parser')
        
        # 1. 移除不需要的元素（但保留所有内容）
        self._remove_unwanted_elements(cleaned_soup)
        
        # 2. 清洗样式和脚本
        self._clean_styles_and_scripts(cleaned_soup)
        
        # 3. 移除导航和交互元素
        self._remove_navigation_elements(cleaned_soup)
        
        # 4. 展开和清理tab结构，保留所有内容
        self._flatten_tab_structures(cleaned_soup)
        
        # 5. 清理属性但保留内容
        self._clean_attributes_keep_content(cleaned_soup)
        
        # 6. 提取主要内容区域
        main_content = self._extract_files_main_content_area(cleaned_soup)
        
        print("  ✓ Azure Files完整内容提取和清洗完成")
        
        return main_content
    
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
        
        print("    📂 展开Azure Files tab结构，保留所有内容...")
        
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
            'pricing-page-section', 'more-detail', 'storage-specific-content'
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
    
    def _is_important_section_title(self, element: Tag) -> bool:
        """判断是否为重要的section标题，需要保留"""
        
        if not element or not hasattr(element, 'get_text'):
            return False
        
        title_text = element.get_text(strip=True).lower()
        
        # 检查是否匹配重要的section标题
        for important_title in self.important_section_titles:
            if important_title.lower() in title_text:
                print(f"    ✓ 保留重要section标题: {title_text}")
                return True
        
        # 特别检查存储冗余类型标题（如 LRS, GRS 等）
        # 这些通常是单独的短标题，需要精确匹配
        if len(title_text) <= 10:  # 很短的标题
            for redundancy_type in self.storage_redundancy_titles:
                if title_text == redundancy_type.lower():
                    print(f"    ✓ 保留存储冗余类型标题: {title_text}")
                    return True
        
        return False
    
    def _extract_files_main_content_area(self, soup: BeautifulSoup) -> BeautifulSoup:
        """提取Azure Files主要内容区域，减少div嵌套，保留重要section标题"""
        
        print("    🎯 提取Azure Files主要内容区域...")
        
        # 创建新的内容容器
        content_soup = BeautifulSoup("", 'html.parser')
        
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
        
        # 直接提取内容元素，不添加额外包装
        content_elements = []
        
        # 1. 提取产品横幅（Azure Files特定）
        banner = main_area.find('div', class_='common-banner')
        if banner:
            # 直接提取横幅文本内容，不创建复杂结构
            h2 = banner.find('h2')
            h4 = banner.find('h4')
            
            if h2:
                title_h1 = content_soup.new_tag('h1')
                title_h1.string = h2.get_text(strip=True)
                content_elements.append(title_h1)
            
            if h4:
                desc_p = content_soup.new_tag('p')
                desc_p.string = h4.get_text(strip=True)
                content_elements.append(desc_p)
        
        # 2. 提取Azure Files特定内容
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
            
            # 检查是否为重要的section标题 - 优先保留
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                if self._is_important_section_title(element):
                    # 重要标题，直接保留
                    clean_element = self._create_simple_element(element, content_soup)
                    if clean_element:
                        content_elements.append(clean_element)
                    processed_elements.add(id(element))
                    continue
                elif self._is_storage_table_related_title(element):
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
        print(f"    ✓ 提取了 {elements_count} 个Azure Files内容元素（简化结构，保留section标题）")
        
        return content_soup
    
    def _is_storage_table_related_title(self, element: Tag) -> bool:
        """判断是否为存储相关表格标题（避免重复提取），但不过滤重要的section标题"""
        
        # 首先检查是否为重要的section标题，如果是则不过滤
        if self._is_important_section_title(element):
            return False
        
        # 检查标题文本是否包含存储表格相关关键词
        title_text = element.get_text(strip=True).lower()
        
        # 只有非常具体的表格标题才过滤，避免过滤重要的section标题
        # 移除了存储冗余类型关键词，因为它们是重要的section标题
        specific_table_keywords = [
            '系列', 'tier', '层级', '实例', 'gen', 'v2', 'v3', 'v4'
        ]
        
        # 只有当标题很短且包含具体表格关键词时才认为是表格标题
        if len(title_text) < 50 and any(keyword in title_text for keyword in specific_table_keywords):
            # 检查是否靠近表格
            next_sibling = element.find_next_sibling()
            if next_sibling and next_sibling.name == 'table':
                return True
            
            # 检查是否在包含表格的容器中
            parent_with_table = element.find_parent()
            if parent_with_table and parent_with_table.find('table'):
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
            
            if original_element.name == 'table':
                new_element['class'] = 'storage-files-pricing-table'
                # 保留colspan和rowspan
                for attr in ['colspan', 'rowspan']:
                    if original_element.get(attr):
                        new_element[attr] = original_element[attr]
            
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
                # 列表：保留结构但简化，也要处理链接
                for li in original_element.find_all('li', recursive=False):
                    new_li = soup.new_tag('li')
                    
                    # 检查li中是否有链接
                    if li.find('a'):
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
    
    def _apply_region_filtering(self, soup: BeautifulSoup, region: str) -> Tuple[int, int]:
        """应用区域过滤"""
        
        print(f"🔍 第二步：应用区域过滤 (区域: {region})...")
        
        # 统计过滤前的表格数量
        all_tables = soup.find_all('table')
        total_tables = len(all_tables)
        
        # 应用过滤
        filtered_count = 0
        tables_to_remove = []
        
        for table in all_tables:
            table_id = table.get('id', '')
            if table_id and self.region_filter.should_filter_table(table_id):
                tables_to_remove.append(table)
                filtered_count += 1
        
        # 移除被过滤的表格及其标题
        for table in tables_to_remove:
            # 移除前面的标题（如果存在）
            prev_sibling = table.find_previous_sibling()
            if prev_sibling and prev_sibling.name in ['h2', 'h3', 'h4'] and prev_sibling.get('class') == ['table-title']:
                prev_sibling.decompose()
            
            table.decompose()
        
        retained_count = total_tables - filtered_count
        
        print(f"  📊 过滤了 {filtered_count} 个表格，保留 {retained_count} 个表格")
        
        return filtered_count, retained_count
    
    def _prepare_for_cms(self, soup: BeautifulSoup, region: str) -> BeautifulSoup:
        """为CMS做最后的准备，保持简洁结构"""
        
        print("✨ 第三步：CMS优化（简化结构）...")
        
        # 移除空的容器
        self._remove_empty_containers(soup)
        
        # 确保表格有适当的样式类
        for table in soup.find_all('table'):
            if 'storage-files-pricing-table' not in table.get('class', []):
                table['class'] = 'storage-files-pricing-table'
        
        # 只添加一个简单的区域标识，而不是复杂的包装结构
        region_p = soup.new_tag('p', **{'class': 'region-info'})
        region_p.string = f"区域: {self.region_names[region]}"
        
        # 将区域信息插入到最前面
        if soup.contents:
            soup.insert(0, region_p)
        else:
            soup.append(region_p)
        
        print("  ✓ CMS优化完成（简洁结构）")
        
        return soup
    
    def _remove_empty_containers(self, soup: BeautifulSoup):
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
    
    def _build_final_html(self, soup: BeautifulSoup, region: str) -> str:
        """构建最终的HTML输出"""
        
        print("🏗️ 第四步：构建最终HTML...")
        
        region_name = self.region_names[region]
        
        # 构建完整的HTML文档
        html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Azure Storage Files 定价 - {region_name}</title>
    <meta name="description" content="Azure Storage Files 在{region_name}的定价信息">
    <style>
        /* CMS友好的基础样式 */
        .product-banner {{
            margin-bottom: 2rem;
            padding: 1rem;
            background-color: #f8f9fa;
            border-left: 4px solid #0078d4;
        }}
        
        .product-title {{
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 0.5rem;
            color: #0078d4;
        }}
        
        .product-description {{
            color: #666;
            line-height: 1.5;
        }}
        
        .region-info {{
            background-color: #e7f3ff;
            padding: 0.5rem 1rem;
            margin-bottom: 1rem;
            border-radius: 4px;
            font-size: 0.9rem;
            color: #0078d4;
        }}
        
        .pricing-content {{
            margin-bottom: 2rem;
        }}
        
        .table-title {{
            font-size: 1.2rem;
            margin: 1.5rem 0 0.5rem 0;
            color: #333;
            border-bottom: 1px solid #ddd;
            padding-bottom: 0.5rem;
        }}
        
        .storage-files-pricing-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1.5rem;
            background-color: white;
        }}
        
        .storage-files-pricing-table th,
        .storage-files-pricing-table td {{
            border: 1px solid #ddd;
            padding: 0.75rem;
            text-align: left;
        }}
        
        .storage-files-pricing-table th {{
            background-color: #f8f9fa;
            font-weight: bold;
            color: #333;
        }}
        
        .storage-files-pricing-table tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        
        /* Section标题样式 */
        h2 {{
            font-size: 1.4rem;
            color: #0078d4;
            margin: 2rem 0 1rem 0;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 0.5rem;
        }}
        
        h3 {{
            font-size: 1.2rem;
            color: #333;
            margin: 1.5rem 0 1rem 0;
            border-left: 4px solid #0078d4;
            padding-left: 0.5rem;
        }}
        
        .storage-tier-section {{
            margin-top: 2rem;
            padding: 1rem;
            background-color: #f0f8ff;
            border-radius: 4px;
        }}
        
        .storage-tier-title {{
            font-size: 1.2rem;
            margin-bottom: 0.5rem;
            color: #0078d4;
        }}
        
        .hot-tier {{
            border-left: 4px solid #ff6b35;
        }}
        
        .cool-tier {{
            border-left: 4px solid #4dabf7;
        }}
        
        .transaction-section {{
            margin-top: 2rem;
        }}
        
        .transaction-title {{
            font-size: 1.3rem;
            margin-bottom: 1rem;
            color: #0078d4;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 0.5rem;
        }}
        
        .bandwidth-section {{
            margin-top: 2rem;
            padding: 1rem;
            background-color: #fff8e7;
            border-radius: 4px;
        }}
        
        .bandwidth-title {{
            font-size: 1.2rem;
            margin-bottom: 0.5rem;
            color: #e67e22;
        }}
        
        .bandwidth-content {{
            margin-bottom: 0.5rem;
            color: #333;
            line-height: 1.5;
        }}
    </style>
</head>
<body>
{str(soup)}
</body>
</html>"""
        
        print("  ✓ HTML文档构建完成")
        
        return html_template
    
    def _verify_extraction_result(self, html_content: str) -> Dict[str, any]:
        """验证提取结果"""
        
        verification_soup = BeautifulSoup(html_content, 'html.parser')
        
        verification = {
            "has_main_content": bool(verification_soup.find('p', class_='region-info')),
            "has_region_info": bool(verification_soup.find('p', class_='region-info')), 
            "table_count": len(verification_soup.find_all('table', class_='storage-files-pricing-table')),
            "paragraph_count": len(verification_soup.find_all('p')),
            "heading_count": len(verification_soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])),
            "list_count": len(verification_soup.find_all(['ul', 'ol'])),
            "link_count": len(verification_soup.find_all('a')),
            "text_length": len(verification_soup.get_text(strip=True)),
            "html_size": len(html_content),
            "is_valid_html": html_content.strip().startswith('<!DOCTYPE html>')
        }
        
        # 检查是否包含重要的section标题
        important_titles_found = []
        for title in ['定价详细信息', '了解存储选项', '数据存储价格', '事务和数据传输价格']:
            if title in html_content:
                important_titles_found.append(title)
        
        # 检查存储冗余类型标题
        redundancy_titles_found = []
        for redundancy in ['LRS', 'GRS', 'ZRS', 'GZRS', 'RA-GRS']:
            if f'>{redundancy}<' in html_content or f'>{redundancy.lower()}<' in html_content:
                redundancy_titles_found.append(redundancy)
        
        verification["important_section_titles"] = important_titles_found
        verification["redundancy_type_titles"] = redundancy_titles_found
        verification["has_section_structure"] = len(important_titles_found) > 0
        verification["has_redundancy_structure"] = len(redundancy_titles_found) > 0
        
        # 验证表格内容
        table_verification = verify_table_content(html_content)
        verification.update(table_verification)
        
        # 内容完整性检查
        verification["content_completeness"] = {
            "has_text_content": verification["text_length"] > 1000,  # 至少1000字符
            "has_structured_content": verification["table_count"] > 0 and verification["paragraph_count"] > 0,
            "has_navigation_structure": verification["heading_count"] > 0,
            "has_interactive_content": verification["link_count"] > 0,
            "has_section_titles": verification["has_section_structure"],
            "has_redundancy_titles": verification["has_redundancy_structure"]
        }
        
        return verification
    
    def save_cms_html(self, result: Dict[str, any], region: str, custom_filename: str = "") -> str:
        """保存CMS HTML文件"""
        
        if not result["success"]:
            print(f"❌ 无法保存失败的提取结果")
            return ""
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if custom_filename:
            filename = custom_filename
        else:
            filename = f"storage_files_{region}_cms_{timestamp}.html"
        
        file_path = self.output_dir / filename
        
        # 保存HTML文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(result["html_content"])
        
        print(f"\n💾 CMS HTML已保存: {file_path}")
        print(f"📄 文件大小: {result['statistics']['final_size']:,} 字节")
        print(f"📊 压缩比: {result['statistics']['compression_ratio']*100:.1f}%")
        
        # 显示找到的重要section标题
        if "important_section_titles" in result["verification"]:
            titles = result["verification"]["important_section_titles"]
            print(f"📋 保留的section标题: {titles}")
        
        # 显示找到的存储冗余类型标题
        if "redundancy_type_titles" in result["verification"]:
            redundancy_titles = result["verification"]["redundancy_type_titles"]
            if redundancy_titles:
                print(f"🔧 保留的存储类型标题: {redundancy_titles}")
        
        # 保存统计信息
        stats_path = file_path.with_suffix('.stats.json')
        stats_data = {
            "region": result["region"],
            "statistics": result["statistics"],
            "verification": result["verification"],
            "extraction_info": result["extraction_info"]
        }
        
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f, ensure_ascii=False, indent=2)
        
        print(f"📋 统计信息: {stats_path}")
        
        return str(file_path)
    
    def extract_all_regions_cms(self, html_file_path: str, 
                               regions: Optional[List[str]] = None) -> Dict[str, Dict]:
        """批量提取所有区域的CMS HTML"""
        
        if regions is None:
            regions = list(self.region_names.keys())
        
        print(f"\n🌍 开始批量Azure Storage Files CMS HTML提取 {len(regions)} 个区域")
        print(f"区域列表: {[self.region_names.get(r, r) for r in regions]}")
        
        batch_results = {}
        successful_count = 0
        total_size = 0
        
        for i, region in enumerate(regions, 1):
            print(f"\n{'='*70}")
            print(f"处理区域 {i}/{len(regions)}: {self.region_names.get(region, region)} ({region})")
            print(f"{'='*70}")
            
            try:
                result = self.extract_cms_html_for_region(html_file_path, region)
                
                if result["success"]:
                    output_file = self.save_cms_html(result, region)
                    result["output_file"] = output_file
                    successful_count += 1
                    total_size += result["statistics"]["final_size"]
                    
                    print(f"✅ {self.region_names.get(region, region)} CMS HTML提取完成")
                else:
                    print(f"❌ {self.region_names.get(region, region)} 提取失败")
                
                batch_results[region] = result
                
            except Exception as e:
                print(f"❌ {self.region_names.get(region, region)} 处理异常: {e}")
                batch_results[region] = {
                    "success": False,
                    "error": str(e),
                    "region": {"id": region, "name": self.region_names.get(region, region)}
                }
        
        # 生成批量处理总结
        self._generate_batch_cms_summary(batch_results, successful_count, len(regions), total_size)
        
        return batch_results
    
    def _generate_batch_cms_summary(self, results: Dict, successful_count: int, 
                                   total_count: int, total_size: int):
        """生成批量CMS处理总结"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_path = self.output_dir / f"storage_files_cms_batch_summary_{timestamp}.json"
        
        summary = {
            "batch_info": {
                "processed_at": datetime.now().isoformat(),
                "extraction_version": "1.2_files_cms_with_redundancy_titles",
                "product": "Azure Storage Files",
                "total_regions": total_count,
                "successful_regions": successful_count,
                "failed_regions": total_count - successful_count,
                "total_output_size": total_size
            },
            "regions": {}
        }
        
        total_tables = 0
        
        for region, result in results.items():
            region_name = self.region_names.get(region, region)
            
            if result.get("success", False):
                verification = result["verification"]
                statistics = result["statistics"]
                
                total_tables += verification.get("table_count", 0)
                
                summary["regions"][region] = {
                    "name": region_name,
                    "status": "success",
                    "file_size": statistics["final_size"],
                    "compression_ratio": statistics["compression_ratio"],
                    "table_count": verification.get("table_count", 0),
                    "section_titles": verification.get("important_section_titles", []),
                    "redundancy_titles": verification.get("redundancy_type_titles", []),
                    "has_section_structure": verification.get("has_section_structure", False),
                    "has_redundancy_structure": verification.get("has_redundancy_structure", False),
                    "output_file": result.get("output_file", "")
                }
            else:
                summary["regions"][region] = {
                    "name": region_name,
                    "status": "failed",
                    "error": result.get("error", "未知错误")
                }
        
        summary["aggregate_stats"] = {
            "total_tables": total_tables,
            "average_file_size": round(total_size / successful_count, 0) if successful_count > 0 else 0,
            "average_tables_per_region": round(total_tables / successful_count, 1) if successful_count > 0 else 0
        }
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"\n📋 Azure Storage Files CMS批量处理总结:")
        print(f"✅ 成功: {successful_count}/{total_count} 个区域")
        print(f"📊 总定价表: {total_tables} 个")
        print(f"📄 总文件大小: {total_size:,} 字节")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"📊 总结报告: {summary_path}")


def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description="Azure Storage Files页面CMS HTML提取器")
    parser.add_argument("html_file", help="Azure Storage Files HTML源文件路径")
    parser.add_argument("-r", "--region", default="north-china3", help="目标区域")
    parser.add_argument("-a", "--all-regions", action="store_true", help="提取所有区域")
    parser.add_argument("-c", "--config", default="soft-category.json", help="配置文件路径")
    parser.add_argument("-o", "--output", default="storage_files_output", help="输出目录")
    parser.add_argument("--regions", nargs="+", help="指定要提取的区域列表")
    parser.add_argument("--filename", help="指定输出文件名")
    
    args = parser.parse_args()
    
    # 验证输入文件
    if not os.path.exists(args.html_file):
        print(f"❌ HTML文件不存在: {args.html_file}")
        return 1
    
    # 验证配置文件
    if not os.path.exists(args.config):
        print(f"❌ 配置文件不存在: {args.config}")
        return 1
    
    try:
        # 创建CMS提取器
        extractor = AzureStorageFilesCMSExtractor(args.config, args.output)
        
        # 显示版本信息
        print("🚀 Azure Storage Files页面CMS HTML提取器 v1.2")
        print("📄 专门生成适合CMS导入的干净HTML文件")
        print("🎯 特性: 区域过滤、内容清洗、CMS优化、保留section标题、保留存储冗余类型标题")
        
        if args.all_regions:
            # 批量提取所有区域
            regions = args.regions or list(extractor.region_names.keys())
            results = extractor.extract_all_regions_cms(args.html_file, regions)
            
        else:
            # 提取单个区域
            if args.region not in extractor.region_names:
                print(f"❌ 不支持的区域: {args.region}")
                print(f"支持的区域: {list(extractor.region_names.keys())}")
                return 1
            
            result = extractor.extract_cms_html_for_region(args.html_file, args.region)
            
            if result["success"]:
                output_file = extractor.save_cms_html(result, args.region, args.filename)
                print(f"✅ 单个区域CMS HTML提取完成: {output_file}")
            else:
                print(f"❌ 提取失败: {result.get('error', '未知错误')}")
                return 1
        
        print("\n🎉 Azure Storage Files CMS HTML提取任务完成！")
        print("📄 生成的HTML文件可直接导入CMS系统")
        print("📋 现在包含完整的section标题结构")
        print("🔧 现在包含存储冗余类型标题（LRS、GRS等）")
        print("💡 建议检查输出文件确认质量")
        return 0
        
    except Exception as e:
        print(f"❌ 提取过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())