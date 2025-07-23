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
from src.utils.html_utils import (
    create_simple_element, preprocess_image_paths, clean_html_content
)
from src.utils.faq_utils import extract_qa_content
from src.utils.content_utils import (
    find_main_content_area, extract_banner_text_content, 
    extract_structured_content
)
from src.utils.validation_utils import validate_extracted_data
from src.utils.large_html_utils import LargeHTMLProcessor


class EnhancedCMSExtractor:
    """增强型CMS提取器 - 整合所有最佳功能"""

    def __init__(self, output_dir: str, config_file: str = ""):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
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
        extracted_data["Title"] = self._extract_page_title(main_content or soup)
        
        # 2. 提取Meta信息
        extracted_data["MetaDescription"] = self._extract_meta_description(soup)
        extracted_data["MetaKeywords"] = self._extract_meta_keywords(soup)
        extracted_data["MSServiceName"] = self._extract_ms_service_name(soup)
        extracted_data["Slug"] = self._extract_slug(url)
        extracted_data["Language"] = self._detect_language(soup)
        
        # 3. 提取Banner内容
        banner_content = self._extract_banner_content(main_content or soup)
        extracted_data["BannerContent"] = self._format_html_content(banner_content)
        extracted_data["NavigationTitle"] = self._extract_navigation_title(soup)
        
        # 4. 提取描述内容
        description_content = self._extract_description_content(main_content or soup, important_section_titles)
        extracted_data["DescriptionContent"] = self._format_html_content(description_content)
        
        # 5. 提取定价表格
        extracted_data["PricingTables"] = self._extract_pricing_tables(main_content or soup)
        
        # 6. 提取Q&A内容（对齐重构前的QaContent字段）
        extracted_data["QaContent"] = extract_qa_content(main_content or soup)
        
        # 7. 检查区域并提取区域内容
        extracted_data["HasRegion"] = self._check_has_region(soup)
        
        if extracted_data["HasRegion"]:
            # 提取各区域内容
            regional_content = self.region_processor.extract_region_contents(
                soup, html_file_path
            )
            extracted_data["RegionalContent"] = regional_content
            
            # 映射到具体的区域字段
            region_mapping = {
                "china-north": "NorthChinaContent",
                "china-north-2": "NorthChina2Content",
                "china-north-3": "NorthChina3Content",
                "china-east": "EastChinaContent",
                "china-east-2": "EastChina2Content",
                "china-east-3": "EastChina3Content"
            }
            
            for region_key, field_name in region_mapping.items():
                if region_key in regional_content:
                    extracted_data[field_name] = regional_content[region_key]
        else:
            # 没有区域选择，提取主体内容到NoRegionContent
            extracted_data["NoRegionContent"] = self._extract_no_region_content(soup)
        
        # 8. 提取结构化内容
        structured_content = extract_structured_content(main_content or soup, important_section_titles)
        extracted_data["ServiceTiers"] = structured_content.get("sections", [])
        
        # 8. 添加提取元数据
        extracted_data["extraction_metadata"] = {
            "extractor_version": "enhanced_v2.0",
            "processing_mode": "standard",
            "content_sections_found": len(structured_content.get("sections", [])),
            "pricing_tables_found": len(extracted_data["PricingTables"]),
            "regions_detected": len(extracted_data["RegionalContent"]),
            "faq_length": len(extracted_data["FAQ"]),
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
        print(f"  ❓ FAQ: {'✓' if extracted_data['FAQ'] else '✗'}")
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

    def _extract_banner_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """提取Banner内容"""
        print("  🎯 提取Banner内容...")
        
        # 查找banner相关元素
        banner_selectors = [
            '.banner', '.hero', '.jumbotron', '.page-header', 
            'header', '.product-banner', '.intro-section', '.common-banner'
        ]
        
        for selector in banner_selectors:
            banner = soup.select_one(selector)
            if banner:
                # 创建简化的banner内容
                simplified_banner = BeautifulSoup("<div class='banner-content'></div>", 'html.parser')
                banner_div = simplified_banner.find('div')
                
                # 提取banner文本内容
                banner_info = extract_banner_text_content(banner)
                
                if banner_info.get('title'):
                    title_elem = simplified_banner.new_tag('h2', **{'class': 'banner-title'})
                    title_elem.string = banner_info['title']
                    banner_div.append(title_elem)
                
                if banner_info.get('description'):
                    desc_elem = simplified_banner.new_tag('div', **{'class': 'banner-description'})
                    desc_elem.string = banner_info['description']
                    banner_div.append(desc_elem)
                
                if banner_info.get('features'):
                    features_ul = simplified_banner.new_tag('ul', **{'class': 'banner-features'})
                    for feature in banner_info['features'][:5]:  # 最多5个特性
                        li = simplified_banner.new_tag('li')
                        li.string = feature
                        features_ul.append(li)
                    banner_div.append(features_ul)
                
                return simplified_banner
        
        print("    ⚠ 未找到Banner内容")
        return BeautifulSoup("", 'html.parser')

    def _extract_description_content(self, soup: BeautifulSoup, 
                                   important_section_titles: List[str]) -> BeautifulSoup:
        """提取描述内容"""
        print("  📝 提取描述内容...")
        
        simplified_content = BeautifulSoup("<div class='description-content'></div>", 'html.parser')
        content_div = simplified_content.find('div')
        
        # 查找重要的section
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        
        sections_found = 0
        for heading in headings:
            # 检查是否为重要标题
            heading_text = heading.get_text(strip=True).lower()
            
            is_important = any(
                title.lower() in heading_text 
                for title in important_section_titles
            ) if important_section_titles else True
            
            if is_important and sections_found < 5:  # 最多5个重要section
                # 创建section
                section_div = simplified_content.new_tag('div', **{'class': 'content-section'})
                
                # 添加标题
                section_title = simplified_content.new_tag(heading.name)
                section_title.string = heading.get_text(strip=True)
                section_div.append(section_title)
                
                # 收集该section下的内容
                next_sibling = heading.find_next_sibling()
                content_parts = []
                
                while (next_sibling and 
                       next_sibling.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'] and
                       len(content_parts) < 3):  # 最多3个段落
                    
                    if next_sibling.name in ['p', 'div', 'ul', 'ol']:
                        simple_element = create_simple_element(next_sibling, simplified_content)
                        if simple_element:
                            content_parts.append(simple_element)
                    
                    next_sibling = next_sibling.find_next_sibling()
                
                # 添加内容到section
                for part in content_parts:
                    section_div.append(part)
                
                if section_div.get_text(strip=True):  # 只添加有内容的section
                    content_div.append(section_div)
                    sections_found += 1
        
        if sections_found == 0:
            print("    ⚠ 未找到重要的描述内容")
        else:
            print(f"    ✓ 找到 {sections_found} 个重要section")
        
        return simplified_content

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
                from src.utils.html_utils import copy_table_structure
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
        
        return False
    
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