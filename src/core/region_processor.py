#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
区域处理器
从BaseCMSExtractor中提取的区域处理逻辑，去除复杂的继承关系
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from bs4 import BeautifulSoup, Tag

from .logging import get_logger

logger = get_logger(__name__)


class RegionProcessor:
    """区域处理逻辑，从BaseCMSExtractor中提取"""

    def __init__(self, config_file: str = "data/configs/soft-category.json"):
        self.config_file = config_file
        self.region_config = self._load_region_config()
        logger.info(f"✓ 区域处理器初始化完成")
        logger.info(f"📁 区域配置文件: {config_file}")
    
    def get_os_name_for_region_filtering(self, product_config: Dict[str, Any] = None, 
                                       filter_analysis: Dict[str, Any] = None,
                                       html_file_path: str = "") -> str:
        """
        获取用于区域筛选的产品OS名称，支持多优先级回退策略
        
        Args:
            product_config: 产品配置字典
            filter_analysis: FilterDetector分析结果
            html_file_path: HTML文件路径（回退使用）
            
        Returns:
            用于soft-category.json查找的OS名称
        """
        logger.info("🔍 获取区域筛选OS名称...")
        
        # 隐藏软件筛选器的value
        if (filter_analysis and 
            filter_analysis.get('software_options') and 
            len(filter_analysis['software_options']) > 0):
            os_name = filter_analysis['software_options'][0].get('value', '').strip()
            if os_name:
                logger.info(f"✅ 使用软件筛选器OS名称: '{os_name}'")
                return os_name
        
        logger.error("❌ 无法获取有效的OS名称，所有方法都失败")
        return ""

    def _load_region_config(self) -> Dict[str, Any]:
        """加载区域配置文件"""
        if os.path.exists(self.config_file):
            try:
                # 处理UTF-8 BOM编码问题
                with open(self.config_file, 'r', encoding='utf-8-sig') as f:
                    raw_config = json.load(f)

                # 如果配置是数组格式，转换为字典格式
                if isinstance(raw_config, list):
                    config = self._convert_array_config_to_dict(raw_config)
                    logger.info(f"加载区域配置: {len(raw_config)} 个配置项，转换为 {len(config)} 个产品")
                else:
                    config = raw_config
                    logger.info(f"📋 加载区域配置: {len(config)} 个产品")

                return config
            except Exception as e:
                logger.error(f"⚠ 加载区域配置失败: {e}")
                return {}
        else:
            logger.error(f"⚠ 区域配置文件不存在: {self.config_file}")
            return {}

    def _convert_array_config_to_dict(self, array_config: List[Dict[str, Any]]) -> Dict[str, Any]:
        """将数组格式的配置转换为字典格式"""
        dict_config = {}

        for item in array_config:
            if not isinstance(item, dict):
                continue

            os_name = item.get('os', '')
            region = item.get('region', '')
            table_ids = item.get('tableIDs', [])

            if not os_name or not region:
                continue

            # 标准化产品名称（转换为文件名格式）
            product_key = os_name

            if product_key not in dict_config:
                dict_config[product_key] = {}

            dict_config[product_key][region] = table_ids

        return dict_config

    def detect_available_regions(self, soup: BeautifulSoup) -> List[str]:
        """动态检测HTML中实际存在的区域"""
        logger.info("检测可用区域...")

        detected_regions = set()
        
        # 方法1: 检查region-container类
        region_containers = soup.find_all(class_='region-container')
        for container in region_containers:
            region_id = container.get('id')
            if region_id:
                detected_regions.add(region_id)
        
        # 方法2: 检查select选项中的区域
        region_selects = soup.find_all('select')
        for select in region_selects:
            select_id = select.get('id', '').lower()
            if 'region' in select_id or 'location' in select_id:
                options = select.find_all('option')
                for option in options:
                    value = option.get('value')
                    if value and len(value) > 2:  # 过滤空值和过短的值
                        detected_regions.add(value)
        
        detected_list = sorted(list(detected_regions))
        logger.info(f"检测到 {len(detected_list)} 个区域: {detected_list}")

        return detected_list

    def extract_region_contents(self, soup: BeautifulSoup, html_file_path: str, 
                              filter_analysis: Dict[str, Any] = None,
                              product_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        提取各区域的内容 - 保持完整HTML格式，支持动态OS名称解析
        
        Args:
            soup: BeautifulSoup对象
            html_file_path: HTML文件路径
            filter_analysis: FilterDetector分析结果（包含隐藏软件筛选器信息）
            product_config: 产品配置字典
            
        Returns:
            区域内容映射字典
        """
        logger.info("🌏 提取区域内容（增强版，支持动态OS解析）...")
        
        region_contents = {}
        
        # 获取用于区域筛选的OS名称
        os_name = self.get_os_name_for_region_filtering(
            product_config=product_config,
            filter_analysis=filter_analysis,
            html_file_path=html_file_path
        )
        
        # 检测可用区域
        available_regions = self.detect_available_regions(soup)
        
        logger.info(f"🎯 使用OS名称 '{os_name}' 进行区域筛选，检测到 {len(available_regions)} 个区域")
        
        # 为每个区域提取内容
        for region_id in available_regions:
            logger.info(f"处理区域: {region_id}")

            try:
                # 应用区域筛选（使用动态OS名称）
                region_soup = self.apply_region_filtering(soup, region_id, os_name)

                # 提取完整的HTML内容而不是分解的结构
                region_html = self._extract_region_html_content(region_soup, region_id, product_config)

                region_contents[region_id] = region_html

            except Exception as e:
                logger.warning(f"区域 {region_id} 内容提取失败: {e}")
                continue

        logger.info(f"✅ 成功提取 {len(region_contents)} 个区域的内容")
        return region_contents

    def apply_region_filtering(self, soup: BeautifulSoup, region_id: str,
                             os_name: str = "") -> BeautifulSoup:
        """
        应用区域筛选到soup对象（使用动态OS名称）
        
        Args:
            soup: BeautifulSoup对象
            region_id: 区域ID
            os_name: 产品OS名称（如"API Management"）
            
        Returns:
            筛选后的BeautifulSoup对象
        """
        logger.info(f"🔍 应用区域筛选: {region_id}，使用OS名称: '{os_name}'")

        # 创建soup的副本
        filtered_soup = BeautifulSoup(str(soup), 'html.parser')

        if not os_name:
            logger.warning("⚠ OS名称为空，无法进行区域筛选")
            return filtered_soup

        # 查找该OS在配置中的产品配置
        product_config = None
        
        # 如果region_config是字典格式（已转换），直接查找
        if isinstance(self.region_config, dict):
            # 检查是否直接有该OS名称的配置
            if os_name in self.region_config:
                product_config = self.region_config[os_name]
                logger.info(f"✅ 在字典格式配置中找到OS '{os_name}' 的配置: {list(product_config.keys()) if isinstance(product_config, dict) else 'N/A'}")

        # 如果region_config是列表格式（原始），遍历查找
        elif isinstance(self.region_config, list):
            for config_item in self.region_config:
                if isinstance(config_item, dict) and config_item.get('os') == os_name:
                    if not product_config:
                        product_config = {}
                    region = config_item.get('region')
                    table_ids = config_item.get('tableIDs', [])
                    if region:
                        product_config[region] = table_ids
            
            if product_config:
                logger.info(f"✅ 在列表格式配置中找到OS '{os_name}' 的配置: {list(product_config.keys())}")
            else:
                logger.warning(f"⚠ 在列表格式配置中未找到OS '{os_name}'")
        else:
            logger.error(f"❌ 无效的配置格式: {type(self.region_config)}")

        if not product_config:
            logger.info(f"📋 OS '{os_name}' 在soft-category.json中无区域配置，保留所有内容")
            return filtered_soup

        region_tables = product_config.get(region_id, [])

        if not region_tables:
            logger.info(f"📋 区域 '{region_id}' 对于OS '{os_name}' 无特定表格配置，保留所有表格")
            return filtered_soup
        
        # 记录筛选前的内容统计
        original_tables = len(filtered_soup.find_all('table'))
        original_content_length = len(str(filtered_soup))
        
        logger.info(f"🔍 筛选前统计: {original_tables} 个表格, 内容长度 {original_content_length} 字符")
        logger.info(f"📋 需要移除的表格IDs: {region_tables}")
        
        # 移除指定的表格
        tables_removed = 0
        removed_table_ids = []

        for table_id in region_tables:
            # 处理带#号和不带#号的table_id
            clean_table_id = table_id.replace('#', '') if table_id.startswith('#') else table_id

            # 查找元素（先尝试带#的ID，再尝试不带#的）
            elements = filtered_soup.find_all(id=clean_table_id)
            if not elements and not table_id.startswith('#'):
                # 如果没找到，尝试查找带#前缀的
                elements = filtered_soup.find_all(id=f"#{table_id}")

            if elements:
                for element in elements:
                    # 移除表格及其相关的前置内容
                    self._remove_table_with_related_content(element, clean_table_id)
                    tables_removed += 1
                    removed_table_ids.append(table_id)
            else:
                logger.warning(f"⚠ 未找到要移除的表格: {table_id}")

        # 记录筛选后的内容统计
        filtered_tables = len(filtered_soup.find_all('table'))
        filtered_content_length = len(str(filtered_soup))
        
        logger.info(f"🔍 筛选后统计: {filtered_tables} 个表格, 内容长度 {filtered_content_length} 字符")
        logger.info(f"📊 筛选效果: 移除了 {tables_removed} 个表格, 内容减少 {original_content_length - filtered_content_length} 字符")
        
        if tables_removed > 0:
            logger.info(f"✅ 成功移除表格: {removed_table_ids}")
        else:
            logger.warning(f"⚠ 未移除任何表格（可能表格ID不匹配）")

        # 在filtered_soup中添加一个隐藏的元数据标签，记录筛选过程
        metadata_info = {
            'region': region_id,
            'os_name': os_name,
            'removed_table_ids': removed_table_ids,
            'tables_before': original_tables,
            'tables_after': filtered_tables,
            'content_reduction': original_content_length - filtered_content_length
        }
        
        metadata_comment = filtered_soup.new_string(
            f"<!-- Region filtering applied: {metadata_info} -->"
        )
        if filtered_soup.body:
            filtered_soup.body.insert(0, metadata_comment)

        return filtered_soup

    def _analyze_pricing_section_structure(self, pricing_section):
        """分析pricing-page-section的结构，识别内容块"""
        content_blocks = []
        current_block = None
        
        for element in pricing_section.children:
            if hasattr(element, 'name'):
                if element.name == 'h2':
                    # 新的标题开始新的内容块
                    if current_block:
                        content_blocks.append(current_block)
                    current_block = {
                        'type': 'section',
                        'title': element,
                        'title_text': element.get_text(strip=True),
                        'elements': [element]
                    }
                elif current_block:
                    # 将元素归属到当前内容块
                    current_block['elements'].append(element)
                    
                    # 识别元素类型
                    if element.name == 'table':
                        current_block['has_table'] = True
                        current_block['table_id'] = element.get('id')
                    elif element.name == 'div' and 'tags-date' in element.get('class', []):
                        current_block['has_tags_date'] = True
        
        # 添加最后一个块
        if current_block:
            content_blocks.append(current_block)
            
        return content_blocks

    def _classify_content_relation(self, element, table_id: str):
        """分类内容与表格的关系"""
        if not hasattr(element, 'name'):
            return 'unrelated'

        # 如果是表格本身
        if element.name == 'table' and element.get('id') == table_id.replace('#', ''):
            return 'table'

        # 检查tags-date的类型
        if element.name == 'div' and 'tags-date' in element.get('class', []):
            return self._classify_tags_date(element)

        # 其他元素
        return 'content'

    def _classify_tags_date(self, tags_date_element) -> str:
        """分类tags-date元素的类型"""
        text = tags_date_element.get_text(strip=True)

        # 全局价格说明（应保护）
        global_pricing_patterns = [
            '*以下价格均为含税价格',
            '*每月价格估算基于',
            'prices are tax-inclusive',
            'monthly price estimates'
        ]

        for pattern in global_pricing_patterns:
            if pattern in text:
                return 'global_pricing_note'

        # 表格注释说明（应保留）- 包含脚注编号的说明
        if self._contains_footnote_references(text):
            return 'table_footnote_note'

        # 其他表格特定的说明（可能需要移除）
        return 'table_specific_note'
    
    def _contains_footnote_references(self, text: str) -> bool:
        """检查文本是否包含脚注引用（sup标签内容）"""
        import re
        # 检查是否包含类似 "1 要求在两个或更多区域" 或 "2 吞吐量数据仅供参考" 的模式
        footnote_patterns = [
            r'^\s*\d+\s*[\u4e00-\u9fff]',  # 数字开头后跟中文
            r'sup>\s*\d+\s*</sup',  # sup标签包含数字
            r'要求在.*区域.*部署',  # 区域部署要求
            r'吞吐量数据.*参考',  # 吞吐量说明
            r'开发者层.*付费',  # 开发者层说明
            r'高级层.*付费',  # 高级层说明
            r'仅适用于.*网关',  # 网关相关说明
            r'请使用.*缓存',  # 缓存说明
        ]
        
        for pattern in footnote_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _remove_table_with_related_content(self, table_element, table_id: str):
        """精确移除表格及其直接关联的内容，保护全局内容"""
        print(f"    🗑️ 精确移除表格: {table_id}")
        
        # 分析所在的pricing-page-section结构
        pricing_section = self._find_parent_pricing_section(table_element)
        if not pricing_section:
            # 回退到原有逻辑
            print(f"      ⚠ 未找到pricing-page-section，使用回退逻辑")
            self._remove_table_fallback(table_element, table_id)
            return
            
        # 分析结构并精确移除
        content_blocks = self._analyze_pricing_section_structure(pricing_section)
        
        elements_to_remove = []
        
        # 找到包含此表格的内容块
        target_block = None
        for block in content_blocks:
            if block.get('table_id') == table_id.replace('#', ''):
                target_block = block
                break
        
        if target_block:
            print(f"      📍 找到表格所在内容块: {target_block['title_text']}")
            
            for element in target_block['elements']:
                relation = self._classify_content_relation(element, table_id)
                
                if relation == 'table':
                    elements_to_remove.append(element)
                    print(f"      🗑️ 移除表格: {table_id}")
                elif relation == 'table_specific_note':
                    elements_to_remove.append(element)
                    print(f"      🗑️ 移除表格专属说明: {element.get_text(strip=True)[:50]}")
                elif relation == 'table_footnote_note':
                    print(f"      🛡️ 保护表格脚注说明: {element.get_text(strip=True)[:50]}")
                elif relation == 'global_title':
                    print(f"      🛡️ 保护全局标题: {element.get_text(strip=True)[:50]}")
                elif relation == 'global_pricing_note':
                    print(f"      🛡️ 保护全局价格说明: {element.get_text(strip=True)[:50]}")
                elif relation == 'section_title':
                    print(f"      🛡️ 保护区段标题: {element.get_text(strip=True)[:50]}")
        else:
            # 如果没有找到结构化的块，直接移除表格
            elements_to_remove.append(table_element)
            print(f"      ⚠ 未找到结构化块，仅移除表格本身")
        
        # 移除收集到的元素
        for element in elements_to_remove:
            try:
                element.decompose()
            except Exception as e:
                print(f"      ⚠ 移除元素失败: {e}")
    
    def _find_parent_pricing_section(self, element):
        """查找元素所在的pricing-page-section父节点"""
        current = element.parent
        while current:
            if (hasattr(current, 'get') and current.get('class') and 
                'pricing-page-section' in current.get('class')):
                return current
            current = current.parent
        return None
    
    def _remove_table_fallback(self, table_element, table_id: str):
        """回退的表格移除逻辑（简化版原逻辑）"""
        print(f"    🔄 使用回退移除逻辑: {table_id}")
        # 只移除表格本身，不移除其他内容
        try:
            table_element.decompose()
        except Exception as e:
            print(f"      ⚠ 表格移除失败: {e}")

    def _extract_region_html_content(self, soup: BeautifulSoup, region_id: str, product_config: Dict[str, Any] = None) -> str:
        """提取区域的完整HTML内容 - 针对pricing-detail-tab结构优化，支持额外sections"""
        logger.debug(f"提取区域 {region_id} 的完整HTML内容")
        
        # 构建HTML结构，匹配原始tab-content格式
        html_parts = []
        
        # 查找pricing-detail-tab结构中的主要内容
        pricing_detail_tab = soup.find(class_='technical-azure-selector pricing-detail-tab')
        content_extracted = False
        
        if pricing_detail_tab:
            print(f"    🎯 发现pricing-detail-tab结构，提取完整内容")
            # 在pricing-detail-tab中查找tab-content
            tab_content = pricing_detail_tab.find(class_='tab-content')
            if tab_content:
                # 查找第一个tab-panel
                tab_panel = tab_content.find('div', {'id': 'tabContent1'}) or tab_content.find(class_='tab-panel')
                if tab_panel:
                    # 提取tab-panel中所有内容，但不包括FAQ部分
                    content_elements = []
                    
                    # 遍历tab-panel的所有直接子元素
                    for element in tab_panel.children:
                        if hasattr(element, 'name'):
                            # 如果遇到包含FAQ的pricing-page-section，停止提取
                            if (element.name == 'div' and 
                                element.has_attr('class') and 
                                'pricing-page-section' in element.get('class', []) and
                                element.find(class_='more-detail')):
                                print(f"    ⏹️ 遇到FAQ部分，停止提取")
                                break
                            # 否则添加到内容元素中
                            content_elements.append(element)
                    
                    # 如果有内容元素，将它们组合起来
                    if content_elements:
                        for element in content_elements:
                            element_html = self._preserve_important_content(str(element))
                            if element_html.strip():
                                html_parts.append(element_html)
                        content_extracted = True
                        print(f"    ✓ 提取了 {len(content_elements)} 个内容元素")
        
        # 如果没有找到pricing-detail-tab结构，使用回退方案
        if not content_extracted:
            print(f"    🔄 使用回退方案：查找全局tab-content")
            tab_content_containers = soup.find_all(class_='tab-content')
            
            for tab_content in tab_content_containers:
                # 查找tab-panel
                tab_panels = tab_content.find_all('div', class_='tab-panel')
                if not tab_panels:
                    tab_panels = [tab_content]  # 如果没有明确的tab-panel，使用tab-content本身
                    
                for tab_panel in tab_panels:
                    content_elements = []
                    
                    # 遍历所有子元素，但不包括FAQ部分
                    for element in tab_panel.children:
                        if hasattr(element, 'name'):
                            # 如果遇到包含FAQ的section，停止提取
                            if (element.name == 'div' and 
                                element.has_attr('class') and 
                                'pricing-page-section' in element.get('class', []) and
                                element.find(class_='more-detail')):
                                break
                            content_elements.append(element)
                    
                    if content_elements:
                        for element in content_elements:
                            element_html = self._preserve_important_content(str(element))
                            if element_html.strip():
                                html_parts.append(element_html)
                        content_extracted = True
                        print(f"    ✓ 回退方案提取了 {len(content_elements)} 个内容元素")
                        break
                
                if content_extracted:
                    break
        
        # 如果仍然没有内容，使用最后的回退方案
        if not content_extracted:
            print(f"    🚨 使用最终回退方案：查找任意非FAQ的pricing-page-section")
            pricing_sections = soup.find_all(class_='pricing-page-section')
            for section in pricing_sections:
                if section.find(class_='more-detail'):
                    continue
                section_html = self._preserve_important_content(str(section))
                html_parts.append(section_html)
                content_extracted = True
                break
        
        # 提取并添加额外的sections（如果配置了的话）
        if product_config:
            extra_sections_html = self._extract_extra_sections(soup, product_config)
            if extra_sections_html:
                html_parts.append('<!-- Extra sections configured in product config -->')
                for extra_section in extra_sections_html:
                    html_parts.append(extra_section)
                logger.info(f"✅ 添加了 {len(extra_sections_html)} 个额外section到区域 {region_id}")
        
        html_parts.append('</div>')  # tab-panel
        html_parts.append('</div>')  # tab-content
        
        # 组合并清理HTML
        result_html = ''.join(html_parts)
        result_html = self._clean_html_content(result_html)
        
        print(f"    ✓ 构建区域HTML内容，长度: {len(result_html)} 字符")
        return result_html

    def _preserve_important_content(self, content: str) -> str:
        """保留重要内容的HTML处理 - 确保H2和tags-date不被误删"""
        if not content:
            return ""
        
        # 轻度清理，但保留重要结构
        import re
        # 只移除多余的换行符和制表符
        content = re.sub(r'\n+', ' ', content)
        content = re.sub(r'\t+', ' ', content)
        # 移除过多的连续空格，但保留基本空格
        content = re.sub(r'  +', ' ', content)
        # 清理首尾空格
        content = content.strip()
        
        return content

    def _clean_html_content(self, content: str) -> str:
        """清理HTML内容，移除多余的换行和空格"""
        if not content:
            return ""
        
        import re
        # 移除多余的换行符
        content = re.sub(r'\n+', ' ', content)
        # 移除多余的空格（保留单个空格）
        content = re.sub(r'\s+', ' ', content)
        # 移除标签之间的多余空格
        content = re.sub(r'>\s+<', '><', content)
        # 清理首尾空格
        content = content.strip()
        
        return content

    def _extract_extra_sections(self, soup: BeautifulSoup, product_config: Dict[str, Any] = None) -> List[str]:
        """
        根据产品配置提取额外的pricing-page-section
        
        Args:
            soup: BeautifulSoup对象
            product_config: 产品配置字典
            
        Returns:
            额外sections的HTML列表
        """
        extra_sections_html = []
        
        if not product_config:
            return extra_sections_html
            
        # 获取额外sections配置
        extra_sections_config = product_config.get('extraction_config', {}).get('extra_sections', [])
        
        if not extra_sections_config:
            return extra_sections_html
            
        logger.info(f"🔍 检测到 {len(extra_sections_config)} 个额外section配置")
        
        # 查找所有pricing-page-section
        all_sections = soup.find_all('div', class_='pricing-page-section')
        
        for config in extra_sections_config:
            title = config.get('title', '')
            section_type = config.get('type', 'content')
            include_in = config.get('include_in', '')
            
            if include_in != 'contentGroups':
                continue
                
            logger.debug(f"查找额外section: '{title}'")
            
            # 查找匹配标题的section
            matching_section = None
            for section in all_sections:
                section_text = section.get_text().strip()
                # 检查section的h2标题是否匹配
                h2_tag = section.find('h2')
                if h2_tag and title in h2_tag.get_text().strip():
                    matching_section = section
                    break
                # 或者检查整个section文本是否包含标题
                elif title in section_text:
                    matching_section = section
                    break
            
            if matching_section:
                # 使用 classify_pricing_section 验证类型
                from src.utils.content.content_utils import classify_pricing_section
                detected_type = classify_pricing_section(matching_section)
                
                if detected_type == section_type or section_type == 'any':
                    section_html = self._preserve_important_content(str(matching_section))
                    if section_html.strip():
                        extra_sections_html.append(section_html)
                        logger.info(f"✅ 成功提取额外section: '{title}' (类型: {detected_type})")
                else:
                    logger.warning(f"⚠ Section '{title}' 类型不匹配: 期望 {section_type}, 检测到 {detected_type}")
            else:
                logger.warning(f"⚠ 未找到标题为 '{title}' 的section")
        
        return extra_sections_html