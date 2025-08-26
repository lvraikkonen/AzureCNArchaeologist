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
from src.utils.html import cleaner

from .logging import get_logger

logger = get_logger(__name__)


class RegionProcessor:
    """区域处理逻辑"""

    def __init__(self, config_file: str = "data/configs/soft-category.json"):
        self.config_file = config_file
        self.region_config = self._load_region_config()
        logger.info(f"✓ 区域处理器初始化完成")
        logger.info(f"📁 区域配置文件: {config_file}")
    
    def get_os_names_for_region_filtering(self, filter_analysis: Dict[str, Any] = None) -> List[str]:
        """
        从FilterDetector的软件筛选器获取所有OS名称（支持Complex策略的多软件选项）
        
        Args:
            filter_analysis: FilterDetector分析结果
            
        Returns:
            用于soft-category.json查找的OS名称列表
        """
        logger.info("🔍 从软件筛选器获取所有OS名称...")
        
        # 验证filter_analysis参数
        if not filter_analysis:
            logger.error("❌ filter_analysis参数为空")
            return []
            
        software_options = filter_analysis.get('software_options', [])
        if not software_options:
            logger.error("❌ filter_analysis中无software_options")
            return []
            
        # 提取所有软件选项的value
        os_names = []
        for i, option in enumerate(software_options):
            if not isinstance(option, dict):
                logger.warning(f"⚠ 软件选项[{i}]格式错误: {type(option)}")
                continue
                
            os_name = option.get('value', '').strip()
            if os_name:
                os_names.append(os_name)
            else:
                logger.warning(f"⚠ 软件选项[{i}]的value为空")
                
        if os_names:
            logger.info(f"✅ 成功获取 {len(os_names)} 个OS名称: {os_names}")
        else:
            logger.error("❌ 未获取到任何有效的OS名称")
            
        return os_names
    
    def get_os_name_for_region_filtering(self, product_config: Dict[str, Any] = None, 
                                       filter_analysis: Dict[str, Any] = None,
                                       html_file_path: str = "") -> str:
        """
        获取单个OS名称（兼容RegionFilter策略，返回第一个OS名称）
        
        Args:
            product_config: 产品配置字典（保留兼容性）
            filter_analysis: FilterDetector分析结果
            html_file_path: HTML文件路径（保留兼容性）
            
        Returns:
            用于soft-category.json查找的OS名称
        """
        os_names = self.get_os_names_for_region_filtering(filter_analysis)
        if os_names:
            os_name = os_names[0]
            logger.info(f"✅ 返回第一个OS名称: '{os_name}'")
            return os_name
        else:
            logger.error("❌ 无法获取有效的OS名称")
            return ""

    def get_regions_from_filter_analysis(self, filter_analysis: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        从filter_analysis参数中获取可用区域列表

        Args:
            filter_analysis: FilterDetector分析结果，包含region_options

        Returns:
            区域ID列表，从region_options中的value字段提取
        """
        logger.info("🌏 从filter_analysis获取可用区域...")

        # 验证filter_analysis参数
        if not filter_analysis:
            logger.error("❌ filter_analysis参数为空，回退到HTML检测")
            return []

        region_options = filter_analysis.get('region_options', [])
        if not region_options:
            logger.error("❌ filter_analysis中无region_options，回退到HTML检测")
            return []

        # 提取所有区域选项的value
        available_regions = []
        for i, option in enumerate(region_options):
            if not isinstance(option, dict):
                logger.warning(f"⚠ 区域选项[{i}]格式错误: {type(option)}")
                continue

            region_value = option.get('value', '').strip()
            if region_value:
                available_regions.append(region_value)
            else:
                logger.warning(f"⚠ 区域选项[{i}]的value为空")

        if available_regions:
            logger.info(f"✅ 成功从filter_analysis获取 {len(available_regions)} 个区域: {available_regions}")
        else:
            logger.error("❌ 未从filter_analysis获取到任何有效的区域")

        return available_regions

    def _load_region_config(self) -> Dict[str, Any]:
        """加载并优化区域配置文件，预处理为高效查找格式"""
        if not os.path.exists(self.config_file):
            logger.error(f"⚠ 区域配置文件不存在: {self.config_file}")
            return {}
            
        try:
            # 处理UTF-8 BOM编码问题
            with open(self.config_file, 'r', encoding='utf-8-sig') as f:
                raw_config = json.load(f)
                
            # 验证配置格式
            if not isinstance(raw_config, list):
                logger.error(f"⚠ 配置文件格式错误，期望数组格式，得到: {type(raw_config)}")
                return {}
                
            # 转换为高效查找格式
            config = self._convert_array_config_to_dict(raw_config)
            logger.info(f"✅ 加载区域配置: {len(raw_config)} 个配置项，转换为 {len(config)} 个产品")
            
            # 验证转换结果
            self._validate_converted_config(config)
            
            return config
            
        except json.JSONDecodeError as e:
            logger.error(f"⚠ JSON解析失败: {e}")
            return {}
        except Exception as e:
            logger.error(f"⚠ 加载区域配置失败: {e}")
            return {}

    def _convert_array_config_to_dict(self, array_config: List[Dict[str, Any]]) -> Dict[str, Any]:
        """将数组格式的配置转换为高效查找的字典格式"""
        dict_config = {}
        invalid_items = 0
        total_table_ids = 0
        
        for item in array_config:
            if not isinstance(item, dict):
                invalid_items += 1
                continue
                
            os_name = item.get('os', '').strip()
            region = item.get('region', '').strip()
            table_ids = item.get('tableIDs', [])
            
            # 验证必需字段
            if not os_name or not region:
                invalid_items += 1
                logger.debug(f"⚠ 跳过无效配置项: os='{os_name}', region='{region}'")
                continue
                
            # 验证tableIDs格式
            if not isinstance(table_ids, list):
                invalid_items += 1
                logger.debug(f"⚠ 跳过无效tableIDs格式: {type(table_ids)}")
                continue
                
            # 初始化产品配置
            if os_name not in dict_config:
                dict_config[os_name] = {}
                
            # 存储区域配置
            dict_config[os_name][region] = table_ids
            total_table_ids += len(table_ids)
            
        # 记录转换统计
        if invalid_items > 0:
            logger.warning(f"⚠ 跳过了 {invalid_items} 个无效配置项")
            
        logger.info(f"📊 转换统计: {len(dict_config)} 个产品, 总计 {total_table_ids} 个表格规则")
        return dict_config

    def _validate_converted_config(self, config: Dict[str, Any]) -> None:
        """验证转换后的配置数据结构"""
        if not config:
            logger.warning("⚠ 转换后的配置为空")
            return
            
        # 验证配置结构
        for product, regions in config.items():
            if not isinstance(regions, dict):
                logger.error(f"❌ 产品 '{product}' 的区域配置格式错误")
                continue
                
            for region, table_ids in regions.items():
                if not isinstance(table_ids, list):
                    logger.error(f"❌ 产品 '{product}' 区域 '{region}' 的表格ID格式错误")
                    
        logger.debug(f"✅ 配置验证完成: {len(config)} 个产品配置有效")

    def extract_region_contents(self, soup: BeautifulSoup, html_file_path: str, 
                              filter_analysis: Dict[str, Any] = None,
                              product_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        提取各区域的内容 - 保持完整HTML格式
        
        Args:
            soup: BeautifulSoup对象
            html_file_path: HTML文件路径
            filter_analysis: FilterDetector分析结果（包含软件筛选信息和地区筛选信息）
            product_config: 产品配置字典
            
        Returns:
            区域内容映射字典
        """
        logger.info("🌏 提取区域内容...")
        
        region_contents = {}
        
        # 获取用于区域筛选的OS名称
        os_name = self.get_os_name_for_region_filtering(
            product_config=product_config,
            filter_analysis=filter_analysis,
            html_file_path=html_file_path
        )
        
        # 从filter_analysis参数中获取可用区域
        available_regions = self.get_regions_from_filter_analysis(filter_analysis)
        
        logger.info(f"🎯 使用OS名称 '{os_name}' 进行区域筛选，检测到 {len(available_regions)} 个区域")
        
        # 为每个区域提取内容
        for region_id in available_regions:
            logger.info(f"处理区域: {region_id}")

            try:
                # 应用区域筛选
                region_soup = self.apply_region_filtering(soup, region_id, os_name)

                # 提取region的HTML内容
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
        应用区域筛选到soup对象
        
        Args:
            soup: BeautifulSoup对象
            region_id: 区域ID
            os_name: 产品OS名称
            
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
        
        # 优化的表格移除逻辑
        tables_removed = 0
        removed_table_ids = []
        failed_table_ids = []

        for table_id in region_tables:
            logger.debug(f"🔍 尝试移除表格: {table_id}")
            
            # 改进的表格查找策略
            element = self._find_table_element(filtered_soup, table_id)
            
            if element:
                try:
                    # 移除表格及其相关的前置内容
                    self._remove_table_with_related_content(element, table_id)
                    tables_removed += 1
                    removed_table_ids.append(table_id)
                    logger.debug(f"✅ 成功移除表格: {table_id}")
                except Exception as e:
                    logger.error(f"❌ 移除表格失败 {table_id}: {e}")
                    failed_table_ids.append(table_id)
            else:
                logger.warning(f"⚠ 未找到要移除的表格: {table_id}")
                failed_table_ids.append(table_id)

        # 记录筛选后的内容统计
        filtered_tables = len(filtered_soup.find_all('table'))
        filtered_content_length = len(str(filtered_soup))
        
        logger.info(f"🔍 筛选后统计: {filtered_tables} 个表格, 内容长度 {filtered_content_length} 字符")
        logger.info(f"📊 筛选效果: 移除了 {tables_removed} 个表格, 内容减少 {original_content_length - filtered_content_length} 字符")
        
        # 详细的筛选结果报告
        if removed_table_ids:
            logger.info(f"✅ 成功移除表格 ({len(removed_table_ids)}个): {removed_table_ids}")
        
        if failed_table_ids:
            logger.warning(f"⚠ 移除失败的表格 ({len(failed_table_ids)}个): {failed_table_ids}")
            
        # 筛选效果验证
        success_rate = (tables_removed / len(region_tables) * 100) if region_tables else 0
        logger.info(f"📈 表格筛选成功率: {success_rate:.1f}% ({tables_removed}/{len(region_tables)})")
        
        if success_rate < 50:
            logger.warning("⚠ 表格筛选成功率较低，可能存在ID匹配问题")

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

    def _find_table_element(self, soup: BeautifulSoup, table_id: str):
        """
        改进的表格元素查找方法，支持多种ID格式匹配
        
        Args:
            soup: BeautifulSoup对象
            table_id: 表格ID（可能带#号或不带#号）
            
        Returns:
            找到的表格元素，未找到则返回None
        """
        # 标准化table_id（移除#号）
        clean_id = table_id.replace('#', '') if table_id.startswith('#') else table_id
        
        # 策略1: 直接按clean_id查找
        element = soup.find(id=clean_id)
        if element:
            logger.debug(f"  策略1成功: 找到ID为 '{clean_id}' 的元素")
            return element
            
        # 策略2: 按原始table_id查找（处理特殊格式）
        if table_id != clean_id:
            element = soup.find(id=table_id)
            if element:
                logger.debug(f"  策略2成功: 找到ID为 '{table_id}' 的元素")
                return element
                
        # 策略3: 查找所有表格，然后匹配ID
        all_tables = soup.find_all('table')
        for table in all_tables:
            table_element_id = table.get('id', '')
            if table_element_id == clean_id or table_element_id == table_id:
                logger.debug(f"  策略3成功: 在表格中找到ID '{table_element_id}'")
                return table
                
        # 策略4: 模糊匹配（处理ID中可能的变体）
        for table in all_tables:
            table_element_id = table.get('id', '')
            # 移除可能的#号进行比较
            normalized_element_id = table_element_id.replace('#', '')
            if normalized_element_id == clean_id:
                logger.debug(f"  策略4成功: 模糊匹配找到ID '{table_element_id}'")
                return table
                
        # 策略5: 查找任何包含该ID的元素（不限于表格）
        element = soup.find(attrs={'id': clean_id})
        if element:
            logger.debug(f"  策略5成功: 找到非表格元素ID '{clean_id}'，类型: {element.name}")
            return element
            
        logger.debug(f"  所有策略失败: 未找到ID为 '{table_id}' 的元素")
        return None

    
    def _remove_table_with_related_content(self, table_element, table_id: str):
        """移除表格及其所在的scroll-table容器"""
        logger.debug(f"🗑️ 移除表格及相关内容: {table_id}")

        try:
            # 查找包含该表格的scroll-table容器
            scroll_table_container = self._find_scroll_table_container(table_element)

            if scroll_table_container:
                # 移除整个scroll-table容器
                container_info = self._get_container_info(scroll_table_container)
                scroll_table_container.decompose()
                logger.debug(f"✅ 移除scroll-table容器成功: {table_id} - {container_info}")
            else:
                # 如果找不到scroll-table容器，只移除表格本身
                table_element.decompose()
                logger.debug(f"✅ 移除表格成功（未找到容器）: {table_id}")

        except Exception as e:
            logger.error(f"❌ 表格移除失败 {table_id}: {e}")
            raise

    def _find_scroll_table_container(self, table_element):
        """查找包含表格的scroll-table容器"""
        try:
            # 从表格元素开始向上查找父元素
            current = table_element.parent

            while current:
                # 检查当前元素是否是scroll-table容器
                if (hasattr(current, 'attrs') and
                    current.attrs and
                    current.attrs.get('class') and
                    'scroll-table' in current.attrs.get('class', [])):
                    return current

                # 继续向上查找
                current = current.parent

            return None

        except Exception as e:
            logger.debug(f"查找scroll-table容器时出错: {e}")
            return None

    def _get_container_info(self, container):
        """获取容器的简要信息用于日志"""
        try:
            if not container:
                return "无容器"

            # 尝试获取容器中的标题
            h3_element = None
            if hasattr(container, 'find'):
                h3_element = container.find('h3')

            if h3_element and hasattr(h3_element, 'get_text'):
                title = h3_element.get_text().strip()[:50]  # 限制长度
                return f"标题: {title}"
            else:
                return "无标题"

        except Exception as e:
            logger.debug(f"获取容器信息时出错: {e}")
            return "信息获取失败"

    def _extract_region_html_content(self, soup: BeautifulSoup, region_id: str, product_config: Optional[Dict[str, Any]] = None) -> str:
        """简化的区域HTML内容提取方法"""
        logger.debug(f"提取区域 {region_id} 的HTML内容")
        
        # 查找主要内容区域
        content_html = ""
        
        # 方案1: 查找tab-content结构
        tab_content = soup.find(class_='tab-content')
        if tab_content:
            content_html = str(tab_content)
            logger.debug("✓ 使用tab-content结构")
        else:
            # 方案2: 查找pricing-page-section
            pricing_sections = soup.find_all(class_='pricing-page-section')
            if pricing_sections:
                # 排除FAQ部分
                non_faq_sections = [s for s in pricing_sections if hasattr(s, 'find') and not s.find(class_='more-detail')]
                if non_faq_sections:
                    content_html = ''.join(str(section) for section in non_faq_sections)
                    logger.debug(f"✓ 使用 {len(non_faq_sections)} 个pricing-page-section")
            else:
                # 方案3: 返回整个body内容（最后的回退）
                if soup.body:
                    content_html = str(soup.body)
                    logger.debug("✓ 使用完整body内容作为回退")
        
        # 清理并返回
        result_html = cleaner.clean_html_content(content_html)
        logger.debug(f"✓ 区域HTML内容长度: {len(result_html)} 字符")
        return result_html