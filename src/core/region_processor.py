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


class RegionProcessor:
    """区域处理逻辑，从BaseCMSExtractor中提取"""

    def __init__(self, config_file: str = "data/configs/soft-category.json"):
        self.config_file = config_file
        self.region_config = self._load_region_config()
        print(f"✓ 区域处理器初始化完成")
        print(f"📁 区域配置文件: {config_file}")

    def _load_region_config(self) -> Dict[str, Any]:
        """加载区域配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    raw_config = json.load(f)

                # 如果配置是数组格式，转换为字典格式
                if isinstance(raw_config, list):
                    config = self._convert_array_config_to_dict(raw_config)
                    print(f"📋 加载区域配置: {len(raw_config)} 个配置项，转换为 {len(config)} 个产品")
                else:
                    config = raw_config
                    print(f"📋 加载区域配置: {len(config)} 个产品")

                return config
            except Exception as e:
                print(f"⚠ 加载区域配置失败: {e}")
                return {}
        else:
            print(f"⚠ 区域配置文件不存在: {self.config_file}")
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
            product_key = self._normalize_product_name(os_name)

            if product_key not in dict_config:
                dict_config[product_key] = {}

            dict_config[product_key][region] = table_ids

        return dict_config

    def _normalize_product_name(self, os_name: str) -> str:
        """标准化产品名称为文件名格式"""
        # 产品名称映射表
        name_mapping = {
            'API Management': 'api-management-index',
            'Azure Database for MySQL': 'mysql-index',
            'Azure Cosmos DB': 'cosmos-db-index',
            'Storage Files': 'storage-files-index',
            'Data Factory SSIS': 'ssis-index',
            'Power BI Embedded': 'power-bi-embedded-index',
            'Cognitive Services': 'cognitive-services-index',
            'Anomaly Detector': 'anomaly-detector-index',
            'Machine Learning Server': 'machine-learning-server-index',
            'Azure_Data_Lake_Storage_Gen': 'storage_data-lake_index',
            'databricks': 'databricks-index'
        }

        return name_mapping.get(os_name, os_name.lower().replace(' ', '-'))

    def detect_available_regions(self, soup: BeautifulSoup) -> List[str]:
        """动态检测HTML中实际存在的区域"""
        print("🔍 检测可用区域...")
        
        detected_regions = set()
        
        # 方法1: 检查region-container类
        region_containers = soup.find_all(class_='region-container')
        for container in region_containers:
            region_id = container.get('id')
            if region_id:
                detected_regions.add(region_id)
        
        # 方法2: 检查data-region属性
        region_elements = soup.find_all(attrs={'data-region': True})
        for element in region_elements:
            region_id = element.get('data-region')
            if region_id:
                detected_regions.add(region_id)
        
        # 方法3: 检查常见的区域ID模式
        common_region_patterns = [
            'china-north', 'china-east',
            'china-north2', 'china-east2',
            'china-north3', 'china-east3',
        ]
        
        for pattern in common_region_patterns:
            elements = soup.find_all(id=lambda x: x and pattern in x.lower())
            if elements:
                detected_regions.add(pattern)
        
        # 方法4: 检查select选项中的区域
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
        print(f"  ✓ 检测到 {len(detected_list)} 个区域: {detected_list}")
        
        return detected_list

    def extract_region_contents(self, soup: BeautifulSoup, html_file_path: str) -> Dict[str, Any]:
        """提取各区域的内容 - 保持完整HTML格式"""
        print("🌏 提取区域内容...")
        
        region_contents = {}
        
        # 获取文件名用于区域配置查询
        filename = Path(html_file_path).stem
        
        # 检测可用区域
        available_regions = self.detect_available_regions(soup)
        
        if not available_regions:
            print("  ℹ 未检测到具体区域，使用全局内容")
            region_contents['global'] = self._extract_global_content(soup)
            return region_contents
        
        # 为每个区域提取内容
        for region_id in available_regions:
            print(f"  📍 处理区域: {region_id}")
            
            try:
                # 应用区域筛选
                region_soup = self.apply_region_filtering(soup, region_id, filename)
                
                # 提取完整的HTML内容而不是分解的结构
                region_html = self._extract_region_html_content(region_soup, region_id)
                
                region_contents[region_id] = region_html
                
            except Exception as e:
                print(f"  ⚠ 区域 {region_id} 内容提取失败: {e}")
                continue
        
        print(f"  ✓ 成功提取 {len(region_contents)} 个区域的内容")
        return region_contents

    def apply_region_filtering(self, soup: BeautifulSoup, region_id: str, 
                             filename: str = "") -> BeautifulSoup:
        """应用区域筛选到soup对象"""
        print(f"🔧 应用区域筛选: {region_id}")
        
        # 创建soup的副本
        filtered_soup = BeautifulSoup(str(soup), 'html.parser')
        
        # 检查是否有该产品的区域配置
        product_config = self.region_config.get(filename, {})
        
        if not product_config:
            print(f"  ℹ 产品 {filename} 无区域配置，保留所有内容")
            return filtered_soup
        
        region_tables = product_config.get(region_id, [])
        
        if not region_tables:
            print(f"  ℹ 区域 {region_id} 无特定表格配置，保留所有表格")
            return filtered_soup
        
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

            for element in elements:
                # 移除表格及其相关的前置内容
                self._remove_table_with_related_content(element, clean_table_id)
                tables_removed += 1
                removed_table_ids.append(table_id)

        if tables_removed > 0:
            print(f"  ✓ 移除了 {tables_removed} 个区域特定表格: {removed_table_ids}")

        # 在filtered_soup中添加一个隐藏的元数据标签，记录被移除的table IDs
        if removed_table_ids:
            metadata_comment = filtered_soup.new_string(f"<!-- Removed table IDs for region {region_id}: {', '.join(removed_table_ids)} -->")
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
            
        # 检查是否是重要的产品标题（全局保护）
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            title_text = element.get_text(strip=True)
            # 使用更智能的标题识别，而非硬编码列表
            if self._is_global_product_title(title_text):
                return 'global_title'
            elif self._is_section_title(title_text):
                return 'section_title'
                
        # 检查tags-date的类型
        if element.name == 'div' and 'tags-date' in element.get('class', []):
            return self._classify_tags_date(element)
            
        # 其他元素
        return 'content'
    
    def _is_global_product_title(self, title_text: str) -> bool:
        """判断是否是全局产品标题（应保护）"""
        # 检查是否是主要产品/服务名称
        global_patterns = [
            r'^API\s*管理$',
            r'^API\s*Management$', 
            r'^Azure\s+Database',
            r'^Cosmos\s*DB$',
            r'^MySQL$',
            r'^PostgreSQL$'
        ]
        
        import re
        for pattern in global_patterns:
            if re.match(pattern, title_text, re.IGNORECASE):
                return True
        return False
    
    def _is_section_title(self, title_text: str) -> bool:
        """判断是否是功能区段标题"""
        section_keywords = ['Gateway', '网关', '定价', 'Pricing', '功能', 'Features']
        return any(keyword in title_text for keyword in section_keywords)
    
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

    def _extract_global_content(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """提取全局内容（无区域区分）"""
        return {
            'type': 'global',
            'pricing_tables': self._extract_pricing_tables_simple(soup),
            'content_summary': self._get_content_summary(soup)
        }

    def _extract_region_html_content(self, soup: BeautifulSoup, region_id: str) -> str:
        """提取区域的完整HTML内容 - 针对pricing-detail-tab结构优化"""
        print(f"    📄 提取区域 {region_id} 的完整HTML内容")
        
        # 构建HTML结构，匹配原始tab-content格式
        html_parts = []
        html_parts.append('<div class="tab-content">')
        html_parts.append('<div class="tab-panel" id="tabContent1">')
        
        # 查找pricing-detail-tab结构中的主要内容
        pricing_detail_tab = soup.find(class_='technical-azure-selector pricing-detail-tab')
        content_extracted = False
        
        if pricing_detail_tab:
            print(f"    🎯 发现pricing-detail-tab结构，提取完整内容")
            # 在pricing-detail-tab中查找tab-content
            tab_content = pricing_detail_tab.find(class_='tab-content')
            if tab_content:
                # 查找第一个tab-panel中的pricing-page-section
                tab_panel = tab_content.find('div', {'id': 'tabContent1'}) or tab_content.find(class_='tab-panel')
                if tab_panel:
                    pricing_section = tab_panel.find(class_='pricing-page-section')
                    if pricing_section:
                        # 验证是否包含关键元素
                        has_h2 = pricing_section.find('h2') is not None
                        has_tags_date = pricing_section.find(class_='tags-date') is not None
                        
                        print(f"    📋 内容验证: H2={has_h2}, tags-date={has_tags_date}")
                        
                        # 提取完整的pricing-page-section内容
                        section_html = self._preserve_important_content(str(pricing_section))
                        html_parts.append(section_html)
                        content_extracted = True
        
        # 如果没有找到pricing-detail-tab结构，使用回退方案
        if not content_extracted:
            print(f"    🔄 使用回退方案：查找全局tab-content")
            tab_content_containers = soup.find_all(class_='tab-content')
            
            for tab_content in tab_content_containers:
                pricing_sections = tab_content.find_all(class_='pricing-page-section')
                for section in pricing_sections:
                    # 跳过包含more-detail的section（FAQ内容）
                    if section.find(class_='more-detail'):
                        continue
                    
                    # 验证并提取内容
                    has_h2 = section.find('h2') is not None
                    has_tags_date = section.find(class_='tags-date') is not None
                    print(f"    📋 回退内容验证: H2={has_h2}, tags-date={has_tags_date}")
                    
                    section_html = self._preserve_important_content(str(section))
                    html_parts.append(section_html)
                    content_extracted = True
                    break
                
                if content_extracted:
                    break
        
        # 如果仍然没有内容，使用最后的回退方案
        if not content_extracted:
            print(f"    🚨 使用最终回退方案：查找任意pricing-page-section")
            pricing_sections = soup.find_all(class_='pricing-page-section')
            for section in pricing_sections:
                if section.find(class_='more-detail'):
                    continue
                section_html = self._preserve_important_content(str(section))
                html_parts.append(section_html)
                content_extracted = True
                break
        
        # 添加tab控制结构
        html_parts.append('<div class="technical-azure-selector tab-control-selector" style="min-height: 400px;">')
        html_parts.append('<div class="tab-control-container tab-active" id="tabContent1">')
        html_parts.append('<!-- Content extracted from tab-content pricing-page-section -->')
        html_parts.append('</div>')  # tab-control-container
        html_parts.append('</div>')  # technical-azure-selector
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

    def _extract_region_pricing_tables(self, soup: BeautifulSoup, region_id: str) -> List[Dict[str, Any]]:
        """提取区域特定的定价表格"""
        pricing_tables = []
        
        # 查找定价相关的表格
        tables = soup.find_all('table')
        
        for i, table in enumerate(tables):
            table_text = table.get_text(strip=True)
            
            # 检查是否为定价表格
            if self._is_pricing_table(table_text):
                table_info = {
                    'table_id': f"table_{region_id}_{i}",
                    'region': region_id,
                    'content': table_text[:1000],  # 限制内容长度
                    'row_count': len(table.find_all('tr')),
                    'has_pricing': any(keyword in table_text.lower() 
                                     for keyword in ['￥', '$', '价格', 'price', '费用'])
                }
                
                pricing_tables.append(table_info)
        
        return pricing_tables

    def _extract_region_features(self, soup: BeautifulSoup, region_id: str) -> List[str]:
        """提取区域特定的功能可用性"""
        features = []
        
        # 查找功能列表
        feature_lists = soup.find_all(['ul', 'ol'])
        
        for ul in feature_lists:
            # 检查是否为功能列表
            ul_text = ul.get_text(strip=True).lower()
            if any(keyword in ul_text for keyword in ['功能', 'feature', '特性', '支持']):
                items = ul.find_all('li')
                for item in items[:10]:  # 限制数量
                    item_text = item.get_text(strip=True)
                    if len(item_text) > 5:  # 过滤过短的内容
                        features.append(item_text)
        
        return features

    def _extract_region_notes(self, soup: BeautifulSoup, region_id: str) -> List[str]:
        """提取区域特定的说明信息"""
        notes = []
        
        # 查找包含区域信息的段落
        paragraphs = soup.find_all('p')
        
        for p in paragraphs:
            p_text = p.get_text(strip=True)
            
            # 检查是否包含区域相关信息
            if any(keyword in p_text.lower() for keyword in 
                  ['区域', 'region', '地区', '可用性', 'availability']):
                if len(p_text) > 20:  # 过滤过短的内容
                    notes.append(p_text[:200])  # 限制长度
        
        return notes

    def _is_pricing_table(self, table_text: str) -> bool:
        """判断是否为定价表格"""
        pricing_keywords = [
            '价格', 'price', '定价', 'pricing', '费用', 'cost', 
            '￥', '$', '元', '美元', 'usd', 'rmb', 'cny'
        ]
        
        text_lower = table_text.lower()
        return any(keyword in text_lower for keyword in pricing_keywords)

    def _extract_pricing_tables_simple(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """简单的定价表格提取"""
        pricing_tables = []
        tables = soup.find_all('table')
        
        for i, table in enumerate(tables):
            table_text = table.get_text(strip=True)
            
            if self._is_pricing_table(table_text):
                pricing_tables.append({
                    'table_id': f"global_table_{i}",
                    'content': table_text[:500],  # 限制内容长度
                    'row_count': len(table.find_all('tr'))
                })
        
        return pricing_tables

    def _get_content_summary(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """获取内容摘要"""
        return {
            'total_tables': len(soup.find_all('table')),
            'total_lists': len(soup.find_all(['ul', 'ol'])),
            'total_headings': len(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])),
            'has_forms': len(soup.find_all('form')) > 0,
            'has_scripts': len(soup.find_all('script')) > 0
        }

    def get_region_mapping(self) -> Dict[str, str]:
        """获取区域映射关系"""
        # 标准的Azure China区域映射
        return {
            'north-china': '中国北部',
            'esat-china': '中国东部', 
            'north-china2': '中国北部 2',
            'esat-china2': '中国东部 2',
            'north-china3': '中国北部 3',
            'esat-china3': '中国东部 3', 
        }

    def normalize_region_id(self, region_id: str) -> str:
        """标准化区域ID"""
        # 转换为小写并替换常见变体
        normalized = region_id.lower().strip()
        
        # 处理常见的区域名称变体
        region_variants = {
            'cn-north': 'china-north',
            'cn-east': 'china-east', 
            'cn-south': 'china-south',
            '北京': 'beijing',
            '上海': 'shanghai',
            '广州': 'guangzhou',
            '深圳': 'shenzhen'
        }
        
        return region_variants.get(normalized, normalized)

    def validate_region_config(self) -> Dict[str, Any]:
        """验证区域配置的完整性"""
        validation_result = {
            'is_valid': True,
            'total_products': len(self.region_config),
            'total_regions': set(),
            'issues': []
        }
        
        for product, regions in self.region_config.items():
            if not isinstance(regions, dict):
                validation_result['issues'].append(f"产品 {product} 的配置不是字典格式")
                validation_result['is_valid'] = False
                continue
                
            for region_id, table_ids in regions.items():
                validation_result['total_regions'].add(region_id)
                
                if not isinstance(table_ids, list):
                    validation_result['issues'].append(
                        f"产品 {product} 区域 {region_id} 的表格ID不是列表格式"
                    )
                    validation_result['is_valid'] = False
        
        validation_result['total_regions'] = len(validation_result['total_regions'])
        
        return validation_result

    def get_statistics(self) -> Dict[str, Any]:
        """获取区域处理统计信息"""
        stats = {
            'total_products_configured': len(self.region_config),
            'regions_by_product': {},
            'most_common_regions': {},
            'total_table_exclusions': 0
        }
        
        all_regions = []
        
        # 检查region_config是否为字典格式
        if not isinstance(self.region_config, dict):
            return stats
            
        for product, regions in self.region_config.items():
            if isinstance(regions, dict):
                product_regions = list(regions.keys())
                stats['regions_by_product'][product] = len(product_regions)
                all_regions.extend(product_regions)
                
                # 统计表格排除数量
                for table_list in regions.values():
                    if isinstance(table_list, list):
                        stats['total_table_exclusions'] += len(table_list)
            else:
                # 如果regions不是字典，跳过
                stats['regions_by_product'][product] = 0
        
        # 统计最常见的区域
        from collections import Counter
        region_counts = Counter(all_regions)
        stats['most_common_regions'] = dict(region_counts.most_common(10))
        
        return stats