#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强型CMS提取器
整合所有最佳功能的主力提取器，支持大型HTML文件处理
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.core.product_manager import ProductManager
from src.core.region_processor import RegionProcessor
from src.core.config_manager import ConfigManager
from src.utils.html.element_creator import create_simple_element
from src.utils.html.cleaner import clean_html_content
from src.utils.media.image_processor import preprocess_image_paths
from src.utils.content.content_utils import (
    extract_qa_content, find_main_content_area, extract_banner_text_content, 
    extract_structured_content
)
from src.utils.data.validation_utils import validate_extracted_data
from src.utils.common.large_html_utils import LargeHTMLProcessor


class EnhancedCMSExtractor:
    """增强型CMS提取器 - 整合所有最佳功能"""

    def __init__(self, output_dir: str, config_file: str = ""):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = config_file

        # 区域映射
        self.region_mapping = {
            "north-china": "NorthChinaContent",
            "north-china2": "NorthChina2Content",
            "north-china3": "NorthChina3Content",
            "east-china": "EastChinaContent",
            "east-china2": "EastChina2Content",
            "east-china3": "EastChina3Content"
        }

        # 区域中文名映射
        self.region_names = {
            "north-china": "中国北部",
            "north-china2": "中国北部2",
            "north-china3": "中国北部3",
            "east-china": "中国东部",
            "east-china2": "中国东部2",
            "east-china3": "中国东部3"
        }

        # 初始化核心组件
        self.product_manager = ProductManager()
        self.region_processor = RegionProcessor(config_file)
        self.config_manager = ConfigManager()
        self.large_html_processor = LargeHTMLProcessor()

        print(f"🚀 增强型CMS提取器初始化完成")
        print(f"📁 输出目录: {self.output_dir}")

    def extract_cms_content(self, html_file_path: str, url: str = "") -> Dict[str, Any]:
        """提取CMS内容 - 智能处理大型文件"""
        
        print(f"\n🔧 开始提取增强型CMS内容")
        print(f"📁 源文件: {html_file_path}")

        # 检测产品类型
        product_key = self._detect_product_key_from_path(html_file_path)
        
        if not product_key:
            print("⚠ 无法检测产品类型，使用通用提取逻辑")
            product_key = "unknown"

        # 获取处理策略
        try:
            strategy = self.product_manager.get_processing_strategy(html_file_path, product_key)
            print(f"📊 文件大小: {strategy['size_mb']:.2f} MB")
            print(f"🚀 处理策略: {strategy['strategy']}")
        except Exception as e:
            print(f"⚠ 无法获取处理策略: {e}")
            strategy = {"strategy": "normal", "size_mb": 0}

        if strategy['strategy'] == 'streaming':
            return self._extract_with_streaming(html_file_path, url, strategy, product_key)
        elif strategy['strategy'] == 'chunked':
            return self._extract_with_chunking(html_file_path, url, strategy, product_key)
        else:
            return self._extract_normal(html_file_path, url, product_key)

    def _extract_normal(self, html_file_path: str, url: str, product_key: str) -> Dict[str, Any]:
        """标准提取模式"""
        print("📄 使用标准处理模式...")
        
        try:
            # 读取HTML文件
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
                
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 预处理图片路径
            soup = preprocess_image_paths(soup)
            
            # 提取内容
            extracted_data = self._extract_content_from_soup(
                soup, html_file_path, url, product_key
            )
            
            return extracted_data
            
        except Exception as e:
            print(f"❌ 标准提取失败: {e}")
            return self._create_error_result(str(e))

    def _extract_with_chunking(self, html_file_path: str, url: str,
                              strategy: Dict[str, Any], product_key: str) -> Dict[str, Any]:
        """分块处理模式"""
        print("🧩 使用分块处理模式...")
        
        try:
            # 监控内存使用
            initial_memory = self.large_html_processor.monitor_memory_usage()
            print(f"  🧠 初始内存使用: {initial_memory:.1f}MB")
            
            # 读取HTML文件
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
                
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 预处理图片路径
            soup = preprocess_image_paths(soup)
            
            # 提取内容（与标准模式相同）
            extracted_data = self._extract_content_from_soup(
                soup, html_file_path, url, product_key
            )
            
            # 检查内存使用
            final_memory = self.large_html_processor.monitor_memory_usage()
            memory_used = final_memory - initial_memory
            print(f"  🧠 内存增长: {memory_used:.1f}MB")
            
            extracted_data["processing_info"] = {
                "mode": "chunked",
                "file_size_mb": strategy.get('size_mb', 0),
                "memory_used_mb": memory_used,
                "processing_time": datetime.now().isoformat()
            }
            
            return extracted_data
            
        except Exception as e:
            print(f"❌ 分块提取失败: {e}")
            return self._create_error_result(str(e))

    def _extract_with_streaming(self, html_file_path: str, url: str,
                               strategy: Dict[str, Any], product_key: str) -> Dict[str, Any]:
        """流式处理模式（为大型文件预留）"""
        print("🌊 使用流式处理模式...")
        
        # 目前使用分块处理的逻辑，未来可以实现真正的流式处理
        result = self._extract_with_chunking(html_file_path, url, strategy, product_key)
        if "processing_info" in result:
            result["processing_info"]["mode"] = "streaming"
        
        print("  ⚠ 流式处理功能开发中，当前使用优化的分块处理")
        
        return result

    def _extract_content_from_soup(self, soup: BeautifulSoup, html_file_path: str, 
                                  url: str, product_key: str) -> Dict[str, Any]:
        """从BeautifulSoup对象中提取内容"""
        
        print("🔍 开始内容提取...")
        
        # 获取产品配置
        try:
            product_config = self.product_manager.get_product_config(product_key)
            important_section_titles = self.product_manager.get_important_section_titles(product_key)
        except (ValueError, AttributeError) as e:
            print(f"⚠ 无法获取产品配置: {e}")
            product_config = {}
            important_section_titles = []
        
        # 查找主要内容区域
        main_content = find_main_content_area(soup)
        
        # 初始化提取结果（对齐重构前的字段结构）
        extracted_data = {
            "product_key": product_key,
            "source_file": str(html_file_path),
            "source_url": url or self._get_default_url(product_key),
            "extraction_timestamp": datetime.now().isoformat(),
            "Title": "",
            "MetaDescription": "",
            "MetaKeywords": "",
            "MSServiceName": "",
            "Slug": "",
            "DescriptionContent": "",
            "Language": "",
            "NavigationTitle": "",
            "BannerContent": "",
            "QaContent": "",
            "HasRegion": False,
            "NoRegionContent": "",
            "NorthChinaContent": "",
            "NorthChina2Content": "",
            "NorthChina3Content": "",
            "EastChinaContent": "",
            "EastChina2Content": "",
            "EastChina3Content": "",
            "PricingTables": [],
            "RegionalContent": {},
            "ServiceTiers": [],
            "extraction_metadata": {}
        }
        
        # 1. 提取标题
        print("🏷️ 提取标题...")
        extracted_data["Title"] = self._extract_page_title(main_content or soup)

        # 2. 提取Meta信息
        print("📋 提取Meta信息...")
        extracted_data["MetaDescription"] = self._extract_meta_description(soup)
        extracted_data["MetaKeywords"] = self._extract_meta_keywords(soup)
        extracted_data["MSServiceName"] = self._extract_ms_service_name(soup)
        extracted_data["Slug"] = self._extract_slug(url)
        extracted_data["Language"] = self._detect_language(soup)

        # 3. 提取Banner内容
        print("🎯 提取Banner内容...")
        banner_content = self._extract_banner_content(main_content or soup)
        extracted_data["BannerContent"] = self._clean_html_content(banner_content)
        extracted_data["NavigationTitle"] = self._extract_navigation_title(soup)

        # 4. 提取描述内容
        print("📝 提取描述内容...")
        description_content = self._extract_description_content(main_content or soup, important_section_titles)
        extracted_data["DescriptionContent"] = self._clean_html_content(description_content)

        # 5. 检查区域并提取区域内容（包含tab结构检测）
        print("🌏 检查区域并提取区域内容...")
        extracted_data["HasRegion"] = self._check_has_region(soup)

        if extracted_data["HasRegion"]:
            # 提取各区域内容（包含tab结构检测）
            region_contents = self._extract_region_contents(soup, html_file_path)
            extracted_data.update(region_contents)

            # 同时保存到RegionalContent字段用于兼容性
            extracted_data["RegionalContent"] = region_contents
        else:
            # 没有区域选择，提取主体内容到NoRegionContent
            # 检测是否有 tab 结构
            tab_structure = self._detect_tab_structure(soup)
            if tab_structure:
                # 有 tab 结构，提取 tab 内容数组
                no_region_tabs = self._extract_no_region_content_with_tabs(soup, tab_structure)
                extracted_data["NoRegionContent"] = no_region_tabs
            else:
                # 无 tab 结构，使用传统方式
                extracted_data["NoRegionContent"] = self._extract_no_region_content(soup)

        # 6. 提取Q&A内容
        print("❓ 提取Q&A内容...")
        extracted_data["QaContent"] = self._extract_qa_content(main_content or soup)

        # 7. 提取定价表格和结构化内容
        print("📋 提取定价表格...")
        extracted_data["PricingTables"] = self._extract_pricing_tables(main_content or soup)

        print("🛠️ 提取结构化内容...")
        structured_content = extract_structured_content(main_content or soup, important_section_titles)
        extracted_data["ServiceTiers"] = structured_content.get("sections", [])

        # 8. 添加提取元数据
        extracted_data["extraction_metadata"] = {
            "extractor_version": "enhanced_v2.0",
            "processing_mode": "standard",
            "content_sections_found": len(structured_content.get("sections", [])),
            "pricing_tables_found": len(extracted_data["PricingTables"]),
            "regions_detected": len(extracted_data["RegionalContent"]),
            "faq_length": len(extracted_data["QaContent"]),
            "has_banner": bool(extracted_data["BannerContent"]),
            "product_config_used": product_key != "unknown"
        }
        
        # 9. 验证提取的数据
        if product_config:
            try:
                validation_result = validate_extracted_data(extracted_data, product_config)
                extracted_data["validation"] = validation_result
                
                if not validation_result["is_valid"]:
                    print(f"⚠ 数据验证发现问题: {validation_result['errors']}")
            except Exception as e:
                print(f"⚠ 数据验证失败: {e}")
        
        print(f"✅ 内容提取完成")
        print(f"  📊 标题: {'✓' if extracted_data['Title'] else '✗'}")
        print(f"  🎯 Banner: {'✓' if extracted_data['BannerContent'] else '✗'}")  
        print(f"  📝 描述: {'✓' if extracted_data['DescriptionContent'] else '✗'}")
        print(f"  📋 定价表格: {len(extracted_data['PricingTables'])} 个")
        print(f"  ❓ FAQ: {'✓' if extracted_data['QaContent'] else '✗'}")
        print(f"  🌏 区域: {len(extracted_data['RegionalContent'])} 个")
        
        return extracted_data

    def _extract_page_title(self, soup: BeautifulSoup) -> str:
        """提取页面标题"""
        # 优先查找页面title标签
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            if title and len(title) > 0:
                return title
        
        # 查找主要标题元素
        main_heading = soup.find(['h1', 'h2'])
        if main_heading:
            return main_heading.get_text(strip=True)
        
        return ""

    def _extract_banner_content(self, soup: BeautifulSoup) -> str:
        """提取Banner内容"""
        print("  🎯 提取Banner内容...")

        banner = soup.find('div', class_='common-banner')
        if banner:
            # 标准化图片格式
            standardized_banner = self._standardize_banner_images(banner)
            return standardized_banner

        print("    ⚠ 未找到Banner内容")
        return ""

    def _standardize_banner_images(self, banner) -> str:
        """标准化Banner中的图片格式，保留文本内容"""

        # 提取背景图片
        background_image = self._extract_background_image(banner)

        # 提取图标
        icon_image = self._extract_icon_image(banner)

        # 提取文本内容
        text_content = self._extract_banner_text_content(banner)

        # 生成标准化HTML
        if background_image or icon_image or text_content:
            standardized_html = ""

            # 添加背景图片div
            if background_image:
                standardized_html += f'<div class="common-banner-image" style="background-image: url(&quot;{background_image}&quot;);">'
            else:
                standardized_html += '<div class="common-banner-image">'

            # 添加图标
            if icon_image:
                standardized_html += f'<img src="{icon_image}" alt="imgAlt">'

            # 添加文本内容
            if text_content:
                standardized_html += text_content

            standardized_html += '</div>'

            return standardized_html

        # 如果没有找到任何内容，返回原始banner
        return str(banner)

    def _extract_background_image(self, banner) -> str:
        """从banner中提取背景图片URL"""

        # 查找data-config属性
        data_config = banner.get('data-config', '')
        if data_config:
            # 使用正则表达式提取backgroundImage
            import re
            pattern = r'["\']backgroundImage["\']:\s*["\']([^"\']*)["\']'
            match = re.search(pattern, data_config)
            if match:
                return match.group(1)

        # 查找style属性中的background-image
        style = banner.get('style', '')
        if 'background-image' in style:
            import re
            pattern = r'background-image:\s*url\(["\']?([^"\']*)["\']?\)'
            match = re.search(pattern, style)
            if match:
                return match.group(1)

        return ""

    def _extract_icon_image(self, banner) -> str:
        """从banner中提取图标图片URL"""

        # 首先查找img标签
        img_tag = banner.find('img')
        if img_tag:
            src = img_tag.get('src', '')
            if src:
                return src

        # 如果没有找到img标签，查找svg标签
        svg_tag = banner.find('svg')
        if svg_tag:
            # 检查svg标签是否有id属性，通常包含产品信息
            svg_id = svg_tag.get('id', '')
            if svg_id:
                # 为svg生成一个占位符路径，基于id
                # 例如：svg-storage/files -> storage-files的图标
                if 'svg-' in svg_id:
                    product_name = svg_id.replace('svg-', '').replace('\\', '-')
                    return f"{{img_hostname}}/Images/marketing-resource/css/{product_name}_icon.svg"

            # 检查svg内部的symbol元素
            symbol_tag = svg_tag.find('symbol')
            if symbol_tag:
                symbol_id = symbol_tag.get('id', '')
                if symbol_id and 'svg-' in symbol_id:
                    product_name = symbol_id.replace('svg-', '').replace('\\', '-')
                    return f"{{img_hostname}}/Images/marketing-resource/css/{product_name}_icon.svg"

        return ""

    def _extract_banner_text_content(self, banner) -> str:
        """从banner中提取文本内容（标题、描述等）"""

        # 查找common-banner-title容器
        title_container = banner.find('div', class_='common-banner-title')
        if not title_container:
            return ""

        text_content = ""

        # 提取主标题 (h2)
        h2_tag = title_container.find('h2')
        if h2_tag:
            # 创建h2标签的副本，移除img标签
            from copy import copy
            h2_copy = copy(h2_tag)
            for img in h2_copy.find_all('img'):
                img.decompose()
            text_content += str(h2_copy)

        # 提取副标题 (h4)
        h4_tag = title_container.find('h4')
        if h4_tag:
            text_content += str(h4_tag)

        # 提取其他标题级别 (h3, h5, h6)
        for tag_name in ['h3', 'h5', 'h6']:
            tag = title_container.find(tag_name)
            if tag:
                text_content += str(tag)

        return text_content

    def _clean_html_content(self, content: str) -> str:
        """清理HTML内容中的多余标签和符号"""

        if not content:
            return content

        import re

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

    def _extract_qa_content(self, soup: BeautifulSoup) -> str:
        """提取Q&A内容以及支持和服务级别协议内容"""

        print("❓ 提取Q&A内容...")

        qa_content = ""

        # 现有的FAQ提取逻辑
        faq_containers = [
            soup.find('div', class_='faq'),
            soup.find('div', class_='qa'),
            soup.find('section', class_='faq'),
            soup.find('section', class_='qa')
        ]

        for container in faq_containers:
            if container:
                qa_content += str(container)

        # 查找包含FAQ结构的列表
        faq_lists = soup.find_all('ul', class_='faq-list')
        if faq_lists:
            # 如果有多个FAQ列表，合并它们
            for faq_list in faq_lists:
                qa_content += str(faq_list)

        # 查找包含icon-plus的列表（FAQ展开图标）
        for ul in soup.find_all('ul'):
            if ul.find('i', class_='icon-plus'):
                qa_content += str(ul)

        # 新增：提取支持和服务级别协议内容
        print("🛠️ 提取支持和服务级别协议内容...")

        # 查找支持和服务级别协议部分
        support_sections = soup.find_all('div', class_='pricing-page-section')
        for section in support_sections:
            h2_tag = section.find('h2')
            if h2_tag and '支持和服务级别协议' in h2_tag.get_text(strip=True):
                qa_content += str(section)
                print("  ✓ 找到支持和服务级别协议部分")
                break

        # 查找注释中的支持信息（可选）
        import re
        html_content = str(soup)
        support_comment_pattern = r'<!--BEGIN: Support and service code chunk-->(.*?)<!--END: Support and service code chunk-->'
        support_matches = re.findall(support_comment_pattern, html_content, re.DOTALL)
        if support_matches:
            for match in support_matches:
                # 解析注释中的HTML内容
                if match.strip() and not match.strip().startswith('<!--'):
                    qa_content += f"<!-- 支持信息 -->{match}<!-- /支持信息 -->"
                    print("  ✓ 找到注释中的支持信息")

        return self._clean_html_content(qa_content)

    def _extract_description_content(self, soup: BeautifulSoup,
                                   important_section_titles: List[str]) -> str:
        """提取Banner下第一个section作为描述内容"""
        print("  📝 提取描述内容...")

        # 查找banner后的第一个内容section
        banner = soup.find('div', class_='common-banner')
        if banner:
            # 查找banner后的第一个pricing-page-section或section
            next_section = banner.find_next_sibling('div', class_='pricing-page-section')
            if next_section:
                print("    ✓ 找到banner后的pricing-page-section")
                return str(next_section)

            # 如果没有找到pricing-page-section，查找普通section
            next_section = banner.find_next_sibling('section')
            if next_section:
                print("    ✓ 找到banner后的section")
                return str(next_section)

        # 如果没有找到banner，尝试查找第一个pricing-page-section
        first_pricing_section = soup.find('div', class_='pricing-page-section')
        if first_pricing_section:
            print("    ✓ 找到第一个pricing-page-section")
            return str(first_pricing_section)

        # 最后尝试查找第一个section
        first_section = soup.find('section')
        if first_section:
            print("    ✓ 找到第一个section")
            return str(first_section)

        print("    ⚠ 未找到描述内容")
        return ""

    def _extract_pricing_tables(self, soup: BeautifulSoup) -> List[str]:
        """提取定价表格"""
        print("  📋 提取定价表格...")
        
        pricing_tables = []
        tables = soup.find_all('table')
        
        for i, table in enumerate(tables):
            table_text = table.get_text(strip=True)
            
            # 检查是否为定价表格
            if self._is_pricing_table(table_text):
                # 创建简化的表格
                simplified_table = BeautifulSoup("<table></table>", 'html.parser')
                table_elem = simplified_table.find('table')
                table_elem['class'] = ['pricing-table']
                
                # 复制表格结构
                from src.utils.html.element_creator import copy_table_structure
                copy_table_structure(table, table_elem, simplified_table)
                
                pricing_tables.append(str(simplified_table))
        
        print(f"    ✓ 找到 {len(pricing_tables)} 个定价表格")
        return pricing_tables

    def _is_pricing_table(self, table_text: str) -> bool:
        """判断是否为定价表格"""
        pricing_keywords = [
            '价格', 'price', '定价', 'pricing', '费用', 'cost', 
            '￥', '$', '元', '美元', 'usd', 'rmb', 'cny'
        ]
        
        text_lower = table_text.lower()
        return any(keyword in text_lower for keyword in pricing_keywords)

    def _format_html_content(self, soup: BeautifulSoup) -> str:
        """格式化HTML内容"""
        if not soup or not soup.get_text(strip=True):
            return ""
        
        html_str = str(soup)
        return clean_html_content(html_str)

    def _detect_product_key_from_path(self, html_file_path: str) -> Optional[str]:
        """从文件路径检测产品类型"""
        try:
            return self.product_manager.detect_product_from_filename(html_file_path)
        except Exception as e:
            print(f"⚠ 产品类型检测失败: {e}")
            return None

    def _get_default_url(self, product_key: str) -> str:
        """获取产品默认URL"""
        try:
            return self.product_manager.get_product_url(product_key)
        except Exception:
            return f"https://www.azure.cn/pricing/details/{product_key}/"

    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """创建错误结果"""
        return {
            "error": True,
            "error_message": error_message,
            "extraction_timestamp": datetime.now().isoformat(),
            "Title": "",
            "BannerContent": "",
            "DescriptionContent": "",
            "PricingTables": [],
            "FAQ": "",
            "RegionalContent": {},
            "ServiceTiers": [],
            "extraction_metadata": {
                "extractor_version": "enhanced_v2.0",
                "processing_failed": True
            }
        }

    def get_statistics(self) -> Dict[str, Any]:
        """获取提取器统计信息"""
        stats = {
            "extractor_type": "EnhancedCMSExtractor",
            "version": "2.0",
            "large_file_support": True,
            "streaming_support": "development"
        }
        
        try:
            stats["supported_products"] = len(self.product_manager.get_supported_products())
            stats["cache_stats"] = self.product_manager.get_cache_stats()
        except Exception as e:
            print(f"⚠ 获取产品管理器统计失败: {e}")
            stats["supported_products"] = 0
            stats["cache_stats"] = {}
        
        try:
            stats["region_processor_stats"] = self.region_processor.get_statistics()
        except Exception as e:
            print(f"⚠ 获取区域处理器统计失败: {e}")
            stats["region_processor_stats"] = {}
            
        return stats
    
    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        """提取Meta描述"""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            return meta_desc.get('content', '')
        return ""
    
    def _extract_meta_keywords(self, soup: BeautifulSoup) -> str:
        """提取Meta关键词"""
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords:
            return meta_keywords.get('content', '')
        return ""
    
    def _extract_ms_service_name(self, soup: BeautifulSoup) -> str:
        """提取MSServiceName字段，从pure-content div内的tags元素中的ms.service属性"""
        print("🏷️ 提取MSServiceName...")
        
        # 查找pure-content div
        pure_content_div = soup.find('div', class_='pure-content')
        if pure_content_div:
            # 在pure-content div内查找tags元素
            tags_element = pure_content_div.find('tags')
            if tags_element:
                # 提取ms.service属性值
                ms_service = tags_element.get('ms.service', '')
                if ms_service:
                    print(f"  ✓ 找到MSServiceName: {ms_service}")
                    return ms_service
                else:
                    print("  ⚠ tags元素中没有ms.service属性")
            else:
                print("  ⚠ pure-content div中没有找到tags元素")
        else:
            print("  ⚠ 没有找到pure-content div")
        
        return ""
    
    def _extract_slug(self, url: str) -> str:
        """从URL提取slug"""
        if not url:
            return ""
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path = parsed.path
            
            # 提取/details/之后到/index.html之前的内容，用-连接
            # 例如 /pricing/details/storage/files/index.html -> storage-files
            # 例如 /pricing/details/api-management/index.html -> api-management
            if '/details/' in path:
                # 找到/details/之后的部分
                after_details = path.split('/details/')[1]
                
                # 移除/index.html后缀
                if after_details.endswith('/index.html'):
                    after_details = after_details[:-11]  # 移除'/index.html'
                elif after_details.endswith('/'):
                    after_details = after_details[:-1]  # 移除末尾的'/'
                
                # 分割路径并用-连接
                path_parts = [p for p in after_details.split('/') if p]
                if path_parts:
                    return '-'.join(path_parts)
        except:
            pass
        
        return ""
    
    def _detect_language(self, soup: BeautifulSoup) -> str:
        """检测页面语言"""
        # 检查html标签的lang属性
        html_tag = soup.find('html')
        if html_tag:
            lang = html_tag.get('lang', '')
            if 'en' in lang.lower():
                return 'en-US'
        
        # 默认返回中文
        return 'zh-CN'
    
    def _extract_navigation_title(self, soup: BeautifulSoup) -> str:
        """提取导航标题"""
        # 查找common-banner-title > h2
        banner_title = soup.find('div', class_='common-banner-title')
        if banner_title:
            h2 = banner_title.find('h2')
            if h2:
                return h2.get_text(strip=True)
        
        # 备用方案：查找页面主标题
        main_title = soup.find('h1')
        if main_title:
            return main_title.get_text(strip=True)
        
        return ""
    
    def _check_has_region(self, soup: BeautifulSoup) -> bool:
        """检查页面是否有区域选择"""
        print("🌍 检查区域选择...")
        
        # 查找区域选择相关的元素
        region_indicators = [
            soup.find('div', class_='region-container'),
            soup.find('select', class_='region-selector'),
            soup.find('div', class_='software-kind'),
            soup.find('div', attrs={'data-region': True})
        ]
        
        for indicator in region_indicators:
            if indicator:
                print(f"  ✓ 发现区域选择器: {indicator.name}")
                return True
        
        # 检查是否有多个区域相关的属性
        region_elements = soup.find_all(attrs={'data-region': True})
        if len(region_elements) > 1:
            print(f"  ✓ 发现 {len(region_elements)} 个区域元素")
            return True

        # 检查表格ID中是否包含区域信息（如 east3, north3）
        tables_with_regions = soup.find_all('table', id=lambda x: x and any(region in x for region in ['east3', 'north3', 'east-china', 'north-china']))
        if tables_with_regions:
            print(f"  ✓ 发现 {len(tables_with_regions)} 个包含区域信息的表格")
            return True

        print("  ℹ 未发现区域选择器")
        return False

    def _detect_available_regions(self, soup: BeautifulSoup) -> Dict[str, str]:
        """动态检测HTML中实际存在的区域"""
        available_regions = {}

        # 检查区域选择器中的选项
        region_selectors = soup.find_all('a', {'data-href': True}) + soup.find_all('option', {'data-href': True})

        for selector in region_selectors:
            data_href = selector.get('data-href', '').replace('#', '')
            if data_href and data_href.startswith(('north-china', 'east-china')):
                region_text = selector.get_text(strip=True)
                available_regions[data_href] = region_text
                print(f"    🔍 发现区域选择器: {data_href} -> {region_text}")

        # 如果没有找到传统的区域选择器，从表格ID中提取区域信息
        if not available_regions:
            tables = soup.find_all('table', id=True)
            region_patterns = {
                'east3': 'east-china3',
                'north3': 'north-china3',
                'east-china': 'east-china',
                'north-china': 'north-china',
                'east-china2': 'east-china2',
                'north-china2': 'north-china2'
            }

            detected_regions = set()
            for table in tables:
                table_id = table.get('id', '')
                for pattern, region_id in region_patterns.items():
                    if pattern in table_id:
                        detected_regions.add(region_id)

            # 将检测到的区域添加到结果中
            for region_id in detected_regions:
                region_name = self.region_names.get(region_id, region_id)
                available_regions[region_id] = region_name

        # 如果仍然只检测到少数区域，尝试从配置文件中获取完整的区域列表
        if len(available_regions) < 4:  # 如果少于4个区域，可能是不完整的
            print(f"    ℹ 只检测到 {len(available_regions)} 个区域，尝试从配置文件获取完整列表")
            config_regions = self._get_regions_from_config()
            if config_regions:
                print(f"    📋 从配置文件获取到 {len(config_regions)} 个区域")
                available_regions.update(config_regions)

        return available_regions

    def _get_regions_from_config(self) -> Dict[str, str]:
        """从配置文件中获取区域列表"""
        config_regions = {}

        # 从区域处理器的配置中获取 Data Lake Storage 的区域
        for filename, product_config in self.region_processor.region_config.items():
            if 'storage_data-lake' in filename or 'data-lake' in filename:
                for region_id in product_config.keys():
                    if region_id in self.region_mapping:
                        region_name = self.region_names.get(region_id, region_id)
                        config_regions[region_id] = region_name
                break

        return config_regions

    def _detect_tab_structure(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """检测页面中的 tab 结构"""
        tab_structure = []

        # 查找 tab 导航元素
        tab_nav = soup.find('ul', class_='os-tab-nav')
        if not tab_nav:
            # 也尝试查找其他可能的 tab 导航结构
            tab_nav = soup.find('ul', class_=lambda x: x and 'tab-nav' in x)

        if not tab_nav:
            return tab_structure

        # 遍历所有 tab 链接
        tab_links = tab_nav.find_all('a')
        for link in tab_links:
            tab_name = link.get_text(strip=True)
            data_href = link.get('data-href', '')

            if tab_name and data_href:
                # 移除 # 前缀获取内容 ID
                content_id = data_href.lstrip('#')

                tab_info = {
                    'tabName': tab_name,
                    'contentId': content_id
                }
                tab_structure.append(tab_info)
                print(f"    📋 发现 tab: {tab_name} -> {content_id}")

        return tab_structure

    def _extract_region_contents(self, soup: BeautifulSoup, html_file_path: str = "") -> Dict[str, Any]:
        """提取各区域的内容，支持 tab 结构，使用 region_processor 的核心功能"""

        print("🌏 提取各区域内容...")

        region_contents = {}

        # 检测 tab 结构
        tab_structure = self._detect_tab_structure(soup)
        has_tabs = len(tab_structure) > 0

        if has_tabs:
            print(f"  📂 检测到 tab 结构: {[tab['tabName'] for tab in tab_structure]}")

            # 使用 region_processor 检测可用区域
            available_regions = self.region_processor.detect_available_regions(soup)
            print(f"  🔍 检测到的区域: {available_regions}")

            # 为每个区域提取 tab 内容
            for region_id in available_regions:
                if region_id in self.region_mapping:
                    content_key = self.region_mapping[region_id]
                    region_name = self.region_names.get(region_id, region_id)

                    # 提取 tab 内容数组
                    content = self._extract_region_content_with_tabs(soup, region_id, tab_structure, html_file_path)
                    if content:
                        region_contents[content_key] = content
                        print(f"  ✓ 提取 {region_name} tab 内容: {len(content)} 个 tab")
        else:
            print("  📄 未检测到 tab 结构，使用 region_processor 的标准提取方式")

            # 使用 region_processor 的标准提取功能
            processor_results = self.region_processor.extract_region_contents(soup, html_file_path)

            # 转换为 enhanced_cms_extractor 期望的格式
            for region_id, region_data in processor_results.items():
                if region_id in self.region_mapping:
                    content_key = self.region_mapping[region_id]
                    # 将结构化数据转换为 HTML 字符串
                    content = self._convert_region_data_to_html(region_data)
                    if content:
                        region_contents[content_key] = self._clean_html_content(content)
                        print(f"  ✓ 提取 {region_id} 内容: {len(content)} 字符")

        return region_contents

    def _convert_region_data_to_html(self, region_data: Dict[str, Any]) -> str:
        """将 region_processor 的结构化数据转换为 HTML 字符串"""
        if not region_data:
            return ""

        html_parts = []

        # 添加定价表格
        pricing_tables = region_data.get('pricing_tables', [])
        if pricing_tables:
            html_parts.append("<div class='pricing-tables'>")
            for table in pricing_tables:
                if isinstance(table, dict) and 'content' in table:
                    html_parts.append(table['content'])
            html_parts.append("</div>")

        # 添加功能可用性信息
        features = region_data.get('feature_availability', [])
        if features:
            html_parts.append("<div class='feature-availability'>")
            for feature in features:
                if isinstance(feature, str):
                    html_parts.append(f"<p>{feature}</p>")
            html_parts.append("</div>")

        # 添加区域说明
        notes = region_data.get('region_notes', [])
        if notes:
            html_parts.append("<div class='region-notes'>")
            for note in notes:
                if isinstance(note, str):
                    html_parts.append(f"<p>{note}</p>")
            html_parts.append("</div>")

        return "\n".join(html_parts)

    def _extract_region_content_with_tabs(self, soup: BeautifulSoup, region_id: str,
                                        tab_structure: List[Dict[str, str]],
                                        html_file_path: str) -> List[Dict[str, str]]:
        """提取指定区域的 tab 内容"""
        print(f"  🔍 提取区域 {region_id} 的 tab 内容...")

        region_content = []

        if not tab_structure:
            # 没有 tab 结构，提取整体内容
            content = self._extract_single_region_content(soup, region_id, html_file_path)
            return [{"tabName": "全部内容", "content": self._clean_html_content(content)}]

        # 获取文件名用于区域处理器
        filename = Path(html_file_path).stem if html_file_path else ""

        # 为每个 tab 提取内容
        for tab_info in tab_structure:
            tab_name = tab_info['tabName']
            content_id = tab_info['contentId']

            print(f"    📂 处理 tab: {tab_name} (ID: {content_id})")

            # 查找对应的 tab 内容区域
            tab_content_div = soup.find('div', id=content_id)
            if not tab_content_div:
                print(f"      ⚠ 未找到 tab 内容区域: {content_id}")
                continue

            # 创建该 tab 的副本进行处理
            tab_soup = BeautifulSoup(str(tab_content_div), 'html.parser')

            # 使用 region_processor 应用区域筛选
            try:
                filtered_content = self.region_processor.apply_region_filtering(tab_soup, region_id, filename)
                content_str = str(filtered_content) if filtered_content else ""
            except Exception as e:
                print(f"      ⚠ 区域筛选失败: {e}")
                content_str = str(tab_soup)

            # 提取处理后的内容并清理HTML
            tab_content = {
                'tabName': tab_name,
                'content': self._clean_html_content(content_str)
            }

            region_content.append(tab_content)
            print(f"      ✓ tab {tab_name} 内容提取完成")

        return region_content

    def _get_region_exclude_tables(self, region_id: str, html_file_path: str) -> List[str]:
        """获取指定区域需要排除的表格ID列表"""
        filename = Path(html_file_path).stem if html_file_path else ""
        product_config = self.region_processor.region_config.get(filename, {})
        return product_config.get(region_id, [])

    def _apply_region_filtering_to_tab(self, tab_soup: BeautifulSoup, exclude_tables: List[str]) -> BeautifulSoup:
        """对 tab 内容应用区域筛选"""

        if not exclude_tables:
            return tab_soup

        # 查找所有表格
        tables = tab_soup.find_all('table')

        for table in tables:
            table_id = table.get('id', '')
            if table_id:
                # 检查是否在排除列表中（添加 # 前缀进行匹配）
                table_id_with_hash = f"#{table_id}"
                if table_id_with_hash in exclude_tables:
                    # 移除表格及其容器
                    container = table.find_parent('div', class_='scroll-table')
                    if container:
                        container.decompose()
                    else:
                        table.decompose()
                    print(f"        ✗ 移除表格: {table_id}")
                else:
                    print(f"        ✓ 保留表格: {table_id}")

        return tab_soup

    def _extract_single_region_content(self, soup: BeautifulSoup, region_id: str, html_file_path: str = "") -> str:
        """提取单个区域的内容，基于现有的区域筛选逻辑"""

        try:
            # 创建一个副本用于区域筛选
            region_soup = BeautifulSoup(str(soup), 'html.parser')

            # 获取产品配置信息
            filename = Path(html_file_path).stem if html_file_path else ""
            product_config = self.region_processor.region_config.get(filename, {})
            region_tables = product_config.get(region_id, [])

            # 应用区域筛选 - 使用区域处理器
            filtered_soup = self.region_processor.apply_region_filtering(
                region_soup, region_id, filename
            )

            # 提取主要内容区域
            main_content = self._extract_main_content_for_region(filtered_soup)

            # 在内容中添加table ID信息
            content_str = str(main_content) if main_content else ""

            # 添加区域和表格过滤信息的注释
            if region_tables:
                filter_info = f"<!-- Region: {region_id}, Filtered table IDs: {', '.join(region_tables)} -->"
                content_str = filter_info + "\n" + content_str
            else:
                filter_info = f"<!-- Region: {region_id}, No table filtering applied -->"
                content_str = filter_info + "\n" + content_str

            return content_str

        except Exception as e:
            print(f"    ⚠ 区域 {region_id} 内容提取失败: {e}")
            return ""

    def _extract_main_content_for_region(self, soup: BeautifulSoup) -> BeautifulSoup:
        """提取区域的主要内容"""

        # 查找主要内容区域
        main_content_selectors = [
            '.tab-content',
            '.pricing-page-section',
            '.content',
            'main'
        ]

        for selector in main_content_selectors:
            elements = soup.select(selector)
            if elements:
                # 只取第一个匹配的元素，避免重复
                element = elements[0]
                # 直接返回该元素的副本
                return BeautifulSoup(str(element), 'html.parser')

        # 如果没有找到特定选择器，返回整个body内容
        body = soup.find('body')
        if body:
            return BeautifulSoup(str(body), 'html.parser')

        return BeautifulSoup("", 'html.parser')

    def _extract_no_region_content_with_tabs(self, soup: BeautifulSoup, tab_structure: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """提取无区域页面的 tab 内容"""
        print("📂 提取无区域 tab 内容...")

        no_region_content = []

        if not tab_structure:
            # 没有 tab 结构，提取整体内容
            content = self._extract_no_region_content(soup)
            return [{"tabName": "全部内容", "content": self._clean_html_content(content)}]

        # 为每个 tab 提取内容
        for tab_info in tab_structure:
            tab_name = tab_info['tabName']
            content_id = tab_info['contentId']

            print(f"    📂 处理 tab: {tab_name} (ID: {content_id})")

            # 查找对应的 tab 内容区域
            tab_content_div = soup.find('div', id=content_id)
            if not tab_content_div:
                print(f"      ⚠ 未找到 tab 内容区域: {content_id}")
                continue

            # 提取 tab 内容并清理HTML
            tab_content = {
                'tabName': tab_name,
                'content': self._clean_html_content(str(tab_content_div))
            }

            no_region_content.append(tab_content)
            print(f"      ✓ tab {tab_name} 内容提取完成")

        return no_region_content

    def _extract_no_region_content(self, soup: BeautifulSoup) -> str:
        """提取无区域页面的主体内容"""
        print("📄 提取无区域主体内容...")
        
        # 查找主要内容区域
        main_content_selectors = [
            'main',
            '.main-content',
            '.content',
            '.page-content',
            '.pricing-content'
        ]
        
        for selector in main_content_selectors:
            element = soup.select_one(selector)
            if element:
                return str(element)
        
        # 如果没有找到特定的主内容区域，提取body中除了header、nav、footer外的内容
        body = soup.find('body')
        if body:
            # 复制body内容
            content_soup = BeautifulSoup(str(body), 'html.parser')
            
            # 移除不需要的部分
            for unwanted in content_soup.find_all(['header', 'nav', 'footer']):
                unwanted.decompose()
            
            return str(content_soup)
        
        return ""