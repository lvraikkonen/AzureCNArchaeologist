#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强型CMS提取器
基于新的分模块提取需求，提取Banner、描述、Q&A、各区域内容等模块
"""

import json
import re
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Tag
from pathlib import Path
from datetime import datetime


class EnhancedCMSExtractor:
    """增强型CMS提取器 - 按模块提取页面内容"""
    
    def __init__(self, output_dir: str = "enhanced_cms_output", config_file: str = "soft-category.json"):
        """
        初始化增强型CMS提取器
        
        Args:
            output_dir: 输出目录
            config_file: 配置文件路径
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
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
        
        # 文件名到产品名称的映射表
        self.filename_to_product_mapping = {
            "anomaly-detector-index.html": "Anomaly Detector",
            "api-management-index.html": "API Management",
            "cosmos-db-index.html": "Azure Cosmos DB",
            "machine-learning-index.html": "Machine Learning Server",
            "mysql-index.html": "Azure Database for MySQL",
            "postgresql-index.html": "Azure Database for PostgreSQL",
            "power-bi-embedded-index.html": "Power BI Embedded",
            "search-index.html": "Azure Search",
            "ssis-index.html": "Data Factory SSIS",
            "storage-files-index.html": "Storage Files",
            "sql-database-index.html": "SQL Database",
            "microsoft-entra-external-id-index.html": "Microsoft Entra External ID",
            "data-factory-index.html": "Data Factory Data Pipeline",
            "cognitive-services-index.html": "Cognitive Services"
        }
        
        print(f"✓ 增强型CMS提取器初始化完成")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"📋 支持的产品数量: {len(self.filename_to_product_mapping)}")
    
    def detect_product_name(self, html_file_path: str) -> str:
        """
        从HTML文件路径检测产品名称
        
        Args:
            html_file_path: HTML文件路径
            
        Returns:
            产品名称（如果找到映射）或空字符串
        """
        
        # 提取文件名
        filename = Path(html_file_path).name
        
        # 查找直接映射
        if filename in self.filename_to_product_mapping:
            product_name = self.filename_to_product_mapping[filename]
            print(f"🔍 检测到产品: {filename} -> {product_name}")
            return product_name
        
        # 尝试模糊匹配（例如处理变体文件名）
        for mapped_filename, product_name in self.filename_to_product_mapping.items():
            # 提取核心名称部分（去掉-index.html后缀）
            mapped_core = mapped_filename.replace('-index.html', '')
            file_core = filename.replace('-index.html', '')
            
            if mapped_core == file_core:
                print(f"🔍 模糊匹配到产品: {filename} -> {product_name}")
                return product_name
        
        # 如果都没有找到，尝试从文件名推断
        inferred_name = self._infer_product_name_from_filename(filename)
        if inferred_name:
            print(f"🔍 推断产品名称: {filename} -> {inferred_name}")
            return inferred_name
        
        print(f"⚠️ 未找到产品映射: {filename}")
        return ""
    
    def _infer_product_name_from_filename(self, filename: str) -> str:
        """
        从文件名推断产品名称
        
        Args:
            filename: 文件名
            
        Returns:
            推断的产品名称
        """
        
        # 移除后缀
        core_name = filename.replace('-index.html', '').replace('.html', '')
        
        # 特殊情况处理
        special_cases = {
            'storage-files': 'Storage Files',
            'api-management': 'API Management',
            'power-bi-embedded': 'Power BI Embedded',
            'machine-learning': 'Machine Learning Server',
            'anomaly-detector': 'Anomaly Detector',
            'sql-database': 'SQL Database',
            'microsoft-entra-external-id': 'Microsoft Entra External ID',
            'data-factory': 'Data Factory Data Pipeline',
            'cognitive-services': 'Cognitive Services'
        }
        
        if core_name in special_cases:
            return special_cases[core_name]
        
        # 通用规则：将连字符替换为空格，每个单词首字母大写
        words = core_name.split('-')
        title_case_words = []
        
        for word in words:
            # 特殊单词处理
            if word.lower() == 'mysql':
                title_case_words.append('MySQL')
            elif word.lower() == 'postgresql':
                title_case_words.append('PostgreSQL')
            elif word.lower() == 'cosmos':
                title_case_words.append('Cosmos')
            elif word.lower() == 'db':
                title_case_words.append('DB')
            elif word.lower() == 'azure':
                title_case_words.append('Azure')
            elif word.lower() == 'ssis':
                title_case_words.append('SSIS')
            else:
                title_case_words.append(word.capitalize())
        
        result = ' '.join(title_case_words)
        
        # 如果结果包含数据库相关词汇，添加Azure前缀
        if any(db_word in result.lower() for db_word in ['mysql', 'postgresql', 'cosmos']):
            if not result.startswith('Azure'):
                result = 'Azure Database for ' + result
        
        return result
    
    def extract_cms_content(self, html_file_path: str, url: str = "") -> Dict[str, Any]:
        """
        提取CMS所需的分模块内容
        
        Args:
            html_file_path: HTML文件路径
            url: 页面URL（用于提取slug）
            
        Returns:
            包含所有模块内容的字典
        """
        
        print(f"\n🔧 开始提取增强型CMS内容")
        print(f"📁 源文件: {html_file_path}")
        print(f"🔗 URL: {url}")
        print("=" * 70)
        
        try:
            # 读取HTML文件
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 预处理图片路径
            processed_soup = self._preprocess_image_paths(soup)
            
            # 提取各个模块
            result = {
                "Title": self._extract_title(processed_soup),
                "MetaDescription": self._extract_meta_description(processed_soup),
                "MetaKeywords": self._extract_meta_keywords(processed_soup),
                "MSServiceName": self._extract_ms_service_name(processed_soup),
                "Slug": self._extract_slug(url),
                "DescriptionContent": self._extract_description_content(processed_soup),
                "Language": self._detect_language(processed_soup),
                "NavigationTitle": self._extract_navigation_title(processed_soup),
                "BannerContent": self._extract_banner_content(processed_soup),
                "QaContent": self._extract_qa_content(processed_soup),
                "HasRegion": self._check_has_region(processed_soup),
                "NoRegionContent": ""
            }
            
            # 检查是否有区域选择
            if result["HasRegion"]:
                # 提取各区域内容
                region_contents = self._extract_region_contents(processed_soup, html_file_path)
                result.update(region_contents)
            else:
                # 没有区域选择，提取主体内容到NoRegionContent
                result["NoRegionContent"] = self._extract_no_region_content(processed_soup)
            
            # 清理所有Content字段中的多余标签和符号
            content_fields = ["DescriptionContent", "BannerContent", "QaContent", "NoRegionContent"]
            
            # 动态添加实际存在的区域内容字段
            for field_name in result.keys():
                if field_name.endswith("Content") and field_name not in content_fields:
                    content_fields.append(field_name)
            
            for field in content_fields:
                if field in result and result[field]:
                    result[field] = self._clean_html_content(result[field])
            
            # 添加提取元数据
            result["extraction_metadata"] = {
                "extracted_at": datetime.now().isoformat(),
                "source_file": html_file_path,
                "extractor_version": "enhanced_cms_v1.0"
            }
            
            print(f"\n✅ 增强型CMS内容提取完成！")
            print(f"📊 包含区域: {result['HasRegion']}")
            print(f"📄 Banner长度: {len(result['BannerContent'])} 字符")
            print(f"📄 Q&A长度: {len(result['QaContent'])} 字符")
            
            return result
            
        except Exception as e:
            print(f"❌ 提取失败: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
    
    def _preprocess_image_paths(self, soup: BeautifulSoup) -> BeautifulSoup:
        """预处理图片路径，添加{img_hostname}占位符"""
        
        print("🖼️ 预处理图片路径...")
        
        # 处理img标签的src属性
        img_count = 0
        for img in soup.find_all('img'):
            src = img.get('src')
            if src and src.startswith('/'):
                img['src'] = f"{{img_hostname}}{src}"
                img_count += 1
        
        # 处理style属性中的background-image
        style_count = 0
        for element in soup.find_all(style=True):
            style = element.get('style', '')
            if 'background-image:' in style and 'url(' in style:
                # 匹配 url("/path/to/image") 或 url('/path/to/image')
                pattern = r'url\(["\']?(/[^"\']*)["\']?\)'
                def replace_url(match):
                    path = match.group(1)
                    return f'url("{{img_hostname}}{path}")'
                
                new_style = re.sub(pattern, replace_url, style)
                if new_style != style:
                    element['style'] = new_style
                    style_count += 1
        
        # 处理data-config属性中的图片路径
        data_config_count = 0
        for element in soup.find_all(attrs={'data-config': True}):
            data_config = element.get('data-config', '')
            if data_config and ('backgroundImage' in data_config or 'background-image' in data_config):
                # 匹配 backgroundImage 或 background-image 后面的图片路径
                # 支持格式：'backgroundImage':'/path/to/image' 或 "backgroundImage":"/path/to/image"
                pattern = r'(["\'](?:backgroundImage|background-image)["\']:\s*["\'])(/[^"\']*?)(["\'])'
                def replace_bg_image(match):
                    prefix = match.group(1)
                    path = match.group(2)
                    suffix = match.group(3)
                    return f'{prefix}{{img_hostname}}{path}{suffix}'
                
                new_data_config = re.sub(pattern, replace_bg_image, data_config)
                if new_data_config != data_config:
                    element['data-config'] = new_data_config
                    data_config_count += 1
        
        print(f"  ✓ 处理了 {img_count} 个img标签、{style_count} 个style属性和 {data_config_count} 个data-config属性")
        
        return soup
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取页面标题"""
        
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True)
        return ""
    
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
    
    def _extract_description_content(self, soup: BeautifulSoup) -> str:
        """提取Banner下第一个section作为描述内容"""
        
        print("📝 提取描述内容...")
        
        # 查找banner后的第一个内容section
        banner = soup.find('div', class_='common-banner')
        if banner:
            # 查找banner后的第一个pricing-page-section或section
            next_section = banner.find_next_sibling('div', class_='pricing-page-section')
            if next_section:
                return str(next_section)
            
            # 如果没有找到pricing-page-section，查找普通section
            next_section = banner.find_next_sibling('section')
            if next_section:
                return str(next_section)
        
        # 如果没有找到banner，尝试查找第一个pricing-page-section
        first_pricing_section = soup.find('div', class_='pricing-page-section')
        if first_pricing_section:
            return str(first_pricing_section)
        
        # 最后尝试查找第一个section
        first_section = soup.find('section')
        if first_section:
            return str(first_section)
        
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
    
    def _extract_banner_content(self, soup: BeautifulSoup) -> str:
        """提取Banner内容"""
        
        print("🎨 提取Banner内容...")
        
        banner = soup.find('div', class_='common-banner')
        if banner:
            # 标准化图片格式
            standardized_banner = self._standardize_banner_images(banner)
            return str(standardized_banner)
        
        return ""
    
    def _standardize_banner_images(self, banner: Tag) -> str:
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
    
    def _extract_background_image(self, banner: Tag) -> str:
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
            pattern = r'background-image:\s*url\(["\']?([^"\']*)["\']?\)'
            match = re.search(pattern, style)
            if match:
                return match.group(1)
        
        return ""
    
    def _extract_icon_image(self, banner: Tag) -> str:
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
    
    def _extract_banner_text_content(self, banner: Tag) -> str:
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
            h2_copy = h2_tag.__copy__()
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
        html_content = str(soup)
        support_comment_pattern = r'<!--BEGIN: Support and service code chunk-->(.*?)<!--END: Support and service code chunk-->'
        support_matches = re.findall(support_comment_pattern, html_content, re.DOTALL)
        if support_matches:
            for match in support_matches:
                # 解析注释中的HTML内容
                if match.strip() and not match.strip().startswith('<!--'):
                    qa_content += f"<!-- 支持信息 -->{match}<!-- /支持信息 -->"
                    print("  ✓ 找到注释中的支持信息")
        
        return qa_content
    
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
        
        return available_regions
    
    def _extract_region_contents(self, soup: BeautifulSoup, html_file_path: str = "") -> Dict[str, str]:
        """提取各区域的内容"""
        
        print("🌏 提取各区域内容...")
        
        region_contents = {}
        
        # 动态检测HTML中实际存在的区域
        available_regions = self._detect_available_regions(soup)
        print(f"  🔍 检测到的区域: {list(available_regions.keys())}")
        
        # 只处理实际存在的区域
        for region_id, region_name in available_regions.items():
            if region_id in self.region_mapping:
                content_key = self.region_mapping[region_id]
                content = self._extract_single_region_content(soup, region_id, html_file_path)
                if content:
                    region_contents[content_key] = content
                    print(f"  ✓ 提取 {region_name} 内容: {len(content)} 字符")
        
        return region_contents
    
    def _extract_single_region_content(self, soup: BeautifulSoup, region_id: str, html_file_path: str = "") -> str:
        """提取单个区域的内容，基于现有的区域筛选逻辑"""
        
        try:
            # 创建一个副本用于区域筛选
            region_soup = BeautifulSoup(str(soup), 'html.parser')
            
            # 导入现有的区域筛选逻辑
            from ..core.config_manager import ConfigManager
            
            # 创建配置管理器
            config_manager = ConfigManager(self.config_file)
            
            # 检测产品名称
            product_name = self.detect_product_name(html_file_path)
            if not product_name:
                product_name = "API Management"  # 默认值
            
            # 设置活跃区域并应用筛选
            config_manager.region_filter.set_active_region(region_id, product_name)
            
            # 应用区域筛选 - 隐藏不属于当前区域的表格
            filtered_count, retained_count, retained_table_ids = self._apply_region_filtering_to_soup(
                region_soup, region_id, config_manager
            )
            
            # 提取主要内容区域
            main_content = self._extract_main_content_for_region(region_soup)
            
            return str(main_content) if main_content else ""
            
        except Exception as e:
            print(f"    ⚠ 区域 {region_id} 内容提取失败: {e}")
            return ""
    
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
    
    def save_cms_content(self, content: Dict[str, Any], filename: str = "") -> str:
        """保存CMS内容到JSON文件"""
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"enhanced_cms_content_{timestamp}.json"
        
        if not filename.endswith('.json'):
            filename += '.json'
        
        file_path = self.output_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 CMS内容已保存: {file_path}")
        print(f"📊 内容大小: {len(json.dumps(content, ensure_ascii=False)):,} 字符")
        
        return str(file_path)
    
    def _apply_region_filtering_to_soup(self, soup: BeautifulSoup, region_id: str, config_manager) -> tuple:
        """应用区域筛选到soup对象"""
        
        # 查找所有表格
        tables = soup.find_all('table')
        filtered_count = 0
        retained_count = 0
        retained_table_ids = []
        
        for table in tables:
            table_id = table.get('id', '')
            if table_id:
                # 检查是否应该过滤此表格（区域信息已经在set_active_region中设置）
                should_filter = config_manager.region_filter.should_filter_table(table_id)
                
                if should_filter:
                    # 隐藏表格
                    table.decompose()
                    filtered_count += 1
                else:
                    # 保留表格
                    retained_count += 1
                    retained_table_ids.append(table_id)
        
        return filtered_count, retained_count, retained_table_ids
    
    def _extract_main_content_for_region(self, soup: BeautifulSoup) -> BeautifulSoup:
        """提取区域的主要内容"""
        
        # 创建新的内容容器
        content_soup = BeautifulSoup("", 'html.parser')
        
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
                break
        
        return content_soup
    
    def process_html_file(self, html_file_path: str, url: str = "", 
                         output_filename: str = "") -> Dict[str, Any]:
        """
        处理HTML文件，提取并保存CMS内容
        
        Args:
            html_file_path: HTML文件路径
            url: 页面URL
            output_filename: 输出文件名（可选）
            
        Returns:
            提取的内容字典
        """
        
        # 提取内容
        content = self.extract_cms_content(html_file_path, url)
        
        if "error" not in content:
            # 保存内容
            output_path = self.save_cms_content(content, output_filename)
            content["output_file"] = output_path
        
        return content