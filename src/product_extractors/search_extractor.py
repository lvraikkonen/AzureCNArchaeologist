#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Azure Search页面CMS导入HTML提取器
基于模块化架构，继承BaseCMSExtractor提供Azure Search特定功能
"""

import argparse
import os
from typing import Dict, List, Optional, Set, Any
from bs4 import BeautifulSoup

from ..core.base_cms_extractor import BaseCMSExtractor


class AzureSearchCMSExtractor(BaseCMSExtractor):
    """Azure Search页面CMS HTML提取器"""
    
    def __init__(self, config_file: str = "soft-category.json", 
                 output_dir: str = "azure_search_output"):
        """
        初始化Azure Search CMS提取器
        
        Args:
            config_file: 配置文件路径
            output_dir: 输出目录
        """
        super().__init__(config_file, output_dir, "Azure 认知搜索")
    
    @property
    def important_section_titles(self) -> Set[str]:
        """获取Azure Search重要的section标题集合"""
        return {
            "定价详细信息", "定价详情", "pricing details",
            "常见问题", "faq", "frequently asked questions",
            "支持和服务级别协议", "support", "sla", "service level agreement",
            # Azure Search特有的
            "Azure 认知搜索定价", "azure cognitive search pricing", "search pricing",
            "搜索服务", "search service", "认知搜索", "cognitive search",
            "搜索单元", "search units", "存储", "storage", "查询", "queries",
            "免费层", "free tier", "基本", "basic", "标准", "standard", "高级", "premium",
            "搜索单位", "search unit", "文档", "documents", "索引", "index", "索引器", "indexers",
            "技能集", "skillsets", "知识存储", "knowledge store", "AI充实", "ai enrichment",
            "语义搜索", "semantic search", "专用数据平面", "dedicated data plane",
            "传输中加密", "encryption in transit", "静态加密", "encryption at rest",
            "认知服务", "cognitive services", "文本分析", "text analytics", "翻译", "translator"
        }
    
    def get_product_specific_config(self) -> Dict[str, Any]:
        """获取Azure Search产品特定配置"""
        return {
            "table_class": "azure-search-pricing-table",
            "banner_class": "azure-search-product-banner",
            "content_class": "azure-search-pricing-content"
        }
    
    def extract_product_banner(self, soup: BeautifulSoup, content_soup: BeautifulSoup) -> List:
        """提取Azure Search产品横幅"""
        
        banners = []
        
        # 查找产品名称和描述
        product_headers = soup.find_all(['h1', 'h2'], string=lambda text: 
            text and any(keyword in text.lower() for keyword in 
                        ['azure search', 'cognitive search', '认知搜索', '搜索服务', 'azure 认知搜索']))
        
        for header in product_headers:
            banner_div = content_soup.new_tag('div', **{'class': 'azure-search-product-banner'})
            
            # 添加标题
            title = content_soup.new_tag('h1')
            title.string = header.get_text().strip()
            banner_div.append(title)
            
            # 查找描述段落
            next_element = header.find_next(['p', 'div'])
            if next_element and len(next_element.get_text().strip()) > 20:
                desc = content_soup.new_tag('p', **{'class': 'product-description'})
                desc.string = next_element.get_text().strip()
                banner_div.append(desc)
            
            banners.append(banner_div)
        
        return banners
    
    def get_css_styles(self, region_name: str) -> str:
        """获取Azure Search产品特定的CSS样式"""
        return """
        /* CMS友好的基础样式 */
        .product-banner {
            margin-bottom: 2rem;
            padding: 1rem;
            background-color: #f8f9fa;
            border-left: 4px solid #0078d4;
        }
        
        .product-title {
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 0.5rem;
            color: #0078d4;
        }
        
        .product-description {
            color: #666;
            line-height: 1.5;
        }
        
        .region-info {
            background-color: #e7f3ff;
            padding: 0.5rem 1rem;
            margin-bottom: 1rem;
            border-radius: 4px;
            font-size: 0.9rem;
            color: #0078d4;
        }
        
        .pricing-content {
            margin-bottom: 2rem;
        }
        
        .table-title {
            font-size: 1.2rem;
            margin: 1.5rem 0 0.5rem 0;
            color: #333;
            border-bottom: 1px solid #ddd;
            padding-bottom: 0.5rem;
        }
        
        .azure-search-pricing-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1.5rem;
            background-color: white;
        }
        
        .azure-search-pricing-table th,
        .azure-search-pricing-table td {
            border: 1px solid #ddd;
            padding: 0.75rem;
            text-align: left;
        }
        
        .azure-search-pricing-table th {
            background-color: #f8f9fa;
            font-weight: bold;
            color: #333;
        }
        
        .azure-search-pricing-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        
        h2, h3, h4 {
            color: #333;
            margin: 1.5rem 0 1rem 0;
        }
        
        h2 {
            font-size: 1.4rem;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 0.5rem;
        }
        
        h3 {
            font-size: 1.2rem;
            border-left: 4px solid #0078d4;
            padding-left: 0.5rem;
        }
        
        ul, ol {
            margin-bottom: 1rem;
            padding-left: 1.5rem;
        }
        
        li {
            margin-bottom: 0.5rem;
            line-height: 1.5;
        }
        
        p {
            margin-bottom: 1rem;
            line-height: 1.5;
        }
        """


def main():
    """命令行入口点"""
    parser = argparse.ArgumentParser(description="Azure Search CMS HTML提取器")
    parser.add_argument("html_file", help="源HTML文件路径")
    parser.add_argument("-r", "--region", required=True, help="目标区域")
    parser.add_argument("-o", "--output", default="azure_search_output", help="输出目录")
    parser.add_argument("-c", "--config", default="soft-category.json", help="配置文件路径")
    parser.add_argument("--filename", help="指定输出文件名")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.html_file):
        print(f"❌ HTML文件不存在: {args.html_file}")
        return 1
    
    if not os.path.exists(args.config):
        print(f"❌ 配置文件不存在: {args.config}")
        return 1
    
    try:
        extractor = AzureSearchCMSExtractor(args.config, args.output)
        result = extractor.extract_cms_html_for_region(args.html_file, args.region)
        
        if result["success"]:
            output_file = extractor.save_cms_html(result, args.region, args.filename)
            print(f"✅ Azure Search CMS HTML提取完成！")
            print(f"📄 输出文件: {output_file}")
            return 0
        else:
            print(f"❌ 提取失败: {result.get('error', '未知错误')}")
            return 1
            
    except Exception as e:
        print(f"❌ 提取过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())