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
        """提取各区域的内容"""
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
                
                # 提取区域特定内容
                region_content = {
                    'region_id': region_id,
                    'pricing_tables': self._extract_region_pricing_tables(region_soup, region_id),
                    'feature_availability': self._extract_region_features(region_soup, region_id),
                    'region_notes': self._extract_region_notes(region_soup, region_id)
                }
                
                region_contents[region_id] = region_content
                
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

    def _remove_table_with_related_content(self, table_element, table_id: str):
        """移除表格及其相关的前置内容（标题、说明等）"""

        print(f"    🗑️ 移除表格及相关内容: {table_id}")

        # 收集要移除的元素
        elements_to_remove = [table_element]

        # 向前查找相关的前置内容
        current = table_element.previous_sibling

        while current:
            if hasattr(current, 'name'):
                # 如果是标签元素
                if current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    # 找到标题，添加到移除列表并停止
                    elements_to_remove.append(current)
                    print(f"      📋 移除相关标题: {current.name} - {current.get_text(strip=True)[:50]}")
                    break
                elif current.name == 'p':
                    # 说明文字，添加到移除列表
                    elements_to_remove.append(current)
                    print(f"      📝 移除相关说明: {current.get_text(strip=True)[:50]}")
                elif current.name == 'div' and 'tags-date' in current.get('class', []):
                    # 价格说明div，添加到移除列表
                    elements_to_remove.append(current)
                    print(f"      💰 移除价格说明: {current.get_text(strip=True)[:50]}")
                elif current.name == 'br':
                    # 换行符，添加到移除列表
                    elements_to_remove.append(current)
                elif current.name in ['table', 'div'] and current.get('id'):
                    # 遇到其他有ID的重要元素，停止
                    break
            elif hasattr(current, 'string') and current.string and current.string.strip():
                # 如果是有内容的文本节点，停止
                break

            current = current.previous_sibling

        # 移除所有收集到的元素
        for element in elements_to_remove:
            try:
                element.decompose()
            except Exception as e:
                print(f"      ⚠ 移除元素失败: {e}")

    def _extract_global_content(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """提取全局内容（无区域区分）"""
        return {
            'type': 'global',
            'pricing_tables': self._extract_pricing_tables_simple(soup),
            'content_summary': self._get_content_summary(soup)
        }

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
            'china-north': '中国北部',
            'china-east': '中国东部', 
            'china-south': '中国南部',
            'china-north-2': '中国北部2',
            'china-east-2': '中国东部2',
            'beijing': '北京',
            'shanghai': '上海',
            'guangzhou': '广州',
            'shenzhen': '深圳'
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