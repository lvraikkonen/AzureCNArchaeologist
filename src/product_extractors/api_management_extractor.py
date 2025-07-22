#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Azure API Management页面CMS导入HTML提取器
基于模块化架构，继承BaseCMSExtractor提供API Management特定功能
"""

import argparse
import os
from typing import Dict, List, Optional, Set, Any
from bs4 import BeautifulSoup

from ..core.base_cms_extractor import BaseCMSExtractor


class APIManagementCMSExtractor(BaseCMSExtractor):
    """Azure API Management页面CMS HTML提取器"""
    
    def __init__(self, config_file: str = "soft-category.json", 
                 output_dir: str = "api_management_output"):
        """
        初始化API Management CMS提取器
        
        Args:
            config_file: 配置文件路径
            output_dir: 输出目录
        """
        super().__init__(config_file, output_dir, "API Management")
    
    @property
    def important_section_titles(self) -> Set[str]:
        """获取API Management重要的section标题集合"""
        return {
            "定价详细信息", "定价详情", "pricing details",
            "常见问题", "faq", "frequently asked questions",
            "支持和服务级别协议", "support", "sla", "service level agreement",
            # API Management特有的
            "Azure API Management定价", "api management pricing", "apim pricing",
            "开发人员", "developer", "基本", "basic", "标准", "standard", "高级", "premium",
            "消费", "consumption", "隔离", "isolated", "自托管网关", "self-hosted gateway",
            "API调用", "api calls", "请求", "requests", "吞吐量", "throughput",
            "网关", "gateway", "门户", "portal", "开发人员门户", "developer portal",
            "策略", "policies", "转换", "transformations", "缓存", "caching",
            "分析", "analytics", "监视", "monitoring", "日志记录", "logging",
            "安全", "security", "身份验证", "authentication", "授权", "authorization",
            "OAuth", "JWT", "证书", "certificates", "IP筛选", "ip filtering",
            "虚拟网络", "virtual network", "vnet", "专用终结点", "private endpoint",
            "多区域", "multi-region", "可用性区域", "availability zones",
            "备份", "backup", "还原", "restore", "版本控制", "versioning",
            "修订", "revisions", "产品", "products", "订阅", "subscriptions"
        }
    
    def get_product_specific_config(self) -> Dict[str, Any]:
        """获取API Management产品特定配置"""
        return {
            "table_class": "api-management-pricing-table",
            "banner_class": "api-management-product-banner",
            "content_class": "api-management-pricing-content"
        }
    
    def extract_product_banner(self, soup: BeautifulSoup, content_soup: BeautifulSoup) -> List:
        """提取API Management产品横幅"""
        
        banners = []
        
        # 查找产品名称和描述
        product_headers = soup.find_all(['h1', 'h2'], string=lambda text: 
            text and any(keyword in text.lower() for keyword in 
                        ['api management', 'apim', 'api 管理', 'api网关', 'api gateway']))
        
        for header in product_headers:
            banner_div = content_soup.new_tag('div', **{'class': 'api-management-product-banner'})
            
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
        """获取API Management产品特定的CSS样式"""
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
        
        .api-management-pricing-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1.5rem;
            background-color: white;
        }
        
        .api-management-pricing-table th,
        .api-management-pricing-table td {
            border: 1px solid #ddd;
            padding: 0.75rem;
            text-align: left;
        }
        
        .api-management-pricing-table th {
            background-color: #f8f9fa;
            font-weight: bold;
            color: #333;
        }
        
        .api-management-pricing-table tr:nth-child(even) {
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
    parser = argparse.ArgumentParser(description="Azure API Management CMS HTML提取器")
    parser.add_argument("html_file", help="源HTML文件路径")
    parser.add_argument("-r", "--region", required=True, help="目标区域")
    parser.add_argument("-o", "--output", default="api_management_output", help="输出目录")
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
        extractor = APIManagementCMSExtractor(args.config, args.output)
        result = extractor.extract_cms_html_for_region(args.html_file, args.region)
        
        if result["success"]:
            output_file = extractor.save_cms_html(result, args.region, args.filename)
            print(f"✅ Azure API Management CMS HTML提取完成！")
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
