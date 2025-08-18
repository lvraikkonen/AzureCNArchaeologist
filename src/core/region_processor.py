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
        
        # 优先级1: 隐藏软件筛选器的value（最准确）
        if (filter_analysis and 
            filter_analysis.get('software_options') and 
            len(filter_analysis['software_options']) > 0):
            os_name = filter_analysis['software_options'][0].get('value', '').strip()
            if os_name:
                logger.info(f"✅ 使用软件筛选器OS名称: '{os_name}'")
                return os_name
        
        # 优先级2: 产品配置的display_name（配置驱动）
        if product_config and 'display_name' in product_config:
            display_name = product_config['display_name'].strip()
            if display_name:
                logger.info(f"✅ 使用产品配置display_name: '{display_name}'")
                return display_name
        
        # 优先级3: 从文件路径推断（最后回退）
        if html_file_path:
            filename = Path(html_file_path).stem
            if filename.endswith('-index'):
                product_key = filename[:-6]
            else:
                product_key = filename
            
            # 尝试通过推断获取OS名称
            fallback_name = self._fallback_name_inference(product_key)
            logger.warning(f"⚠ 使用回退推断OS名称: '{product_key}' → '{fallback_name}'")
            return fallback_name
        
        logger.error("❌ 无法获取有效的OS名称，所有方法都失败")
        return ""
    
    def _fallback_name_inference(self, product_key: str) -> str:
        """
        从产品键推断OS名称的回退逻辑
        
        Args:
            product_key: 产品键（如"api-management"）
            
        Returns:
            推断的OS名称（如"API Management"）
        """
        if not product_key:
            return ""
        
        # 简单的反向推断逻辑
        words = product_key.replace('-', ' ').replace('_', ' ').split()
        
        # 特殊大写规则
        capitalized_words = []
        for word in words:
            if word.upper() in ['API', 'ML', 'AI', 'DB', 'BI', 'SSIS']:
                capitalized_words.append(word.upper())
            else:
                capitalized_words.append(word.capitalize())
        
        inferred_name = ' '.join(capitalized_words)
        logger.debug(f"名称推断: '{product_key}' → '{inferred_name}'")
        return inferred_name

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
            product_key = self._normalize_product_name(os_name)

            if product_key not in dict_config:
                dict_config[product_key] = {}

            dict_config[product_key][region] = table_ids

        return dict_config

    def _normalize_product_name(self, os_name: str) -> str:
        """
        标准化产品名称为文件名格式（动态推断，避免硬编码映射）
        
        Args:
            os_name: 产品的完整名称（如"API Management"）
            
        Returns:
            标准化的产品键（如"api-management"）
        """
        if not os_name:
            return ""
        
        # 动态转换逻辑，避免硬编码映射
        normalized = os_name.lower()
        
        # 移除常见前缀
        prefixes_to_remove = ['azure ', 'microsoft ', 'azure database for ']
        for prefix in prefixes_to_remove:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        
        # 处理特殊字符和空格
        normalized = normalized.replace(' ', '-').replace('_', '-')
        
        # 移除多余的连字符
        while '--' in normalized:
            normalized = normalized.replace('--', '-')
        
        normalized = normalized.strip('-')
        
        logger.debug(f"产品名称标准化: '{os_name}' → '{normalized}'")
        return normalized

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
        
        # 获取用于区域筛选的OS名称（支持多优先级回退）
        os_name = self.get_os_name_for_region_filtering(
            product_config=product_config,
            filter_analysis=filter_analysis,
            html_file_path=html_file_path
        )
        
        if not os_name:
            logger.warning("⚠ 无法获取有效的OS名称，跳过区域筛选")
            region_contents['global'] = self._extract_global_content(soup)
            return region_contents
        
        # 检测可用区域
        available_regions = self.detect_available_regions(soup)
        
        if not available_regions:
            logger.info("ℹ 未检测到具体区域，使用全局内容")
            region_contents['global'] = self._extract_global_content(soup)
            return region_contents
        
        logger.info(f"🎯 使用OS名称 '{os_name}' 进行区域筛选，检测到 {len(available_regions)} 个区域")
        
        # 为每个区域提取内容
        for region_id in available_regions:
            logger.info(f"处理区域: {region_id}")

            try:
                # 应用区域筛选（使用动态OS名称）
                region_soup = self.apply_region_filtering(soup, region_id, os_name)

                # 提取完整的HTML内容而不是分解的结构
                region_html = self._extract_region_html_content(region_soup, region_id)

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
            else:
                # 尝试标准化名称查找
                normalized_os_name = self._normalize_product_name(os_name)
                if normalized_os_name in self.region_config:
                    product_config = self.region_config[normalized_os_name]
                    logger.info(f"✅ 通过标准化名称找到配置: '{os_name}' → '{normalized_os_name}': {list(product_config.keys()) if isinstance(product_config, dict) else 'N/A'}")
                else:
                    logger.warning(f"⚠ 在字典格式配置中未找到: '{os_name}' 或 '{normalized_os_name}', 可用键: {list(self.region_config.keys())[:10]}...")
        
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
        logger.debug(f"提取区域 {region_id} 的完整HTML内容")
        
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