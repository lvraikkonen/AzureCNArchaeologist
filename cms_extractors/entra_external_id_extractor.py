#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Microsoft Entra External ID页面CMS导入HTML提取器
基于模块化架构，继承BaseCMSExtractor提供Microsoft Entra External ID特定功能
"""

import argparse
import os
from typing import Dict, List, Optional, Set, Any
from bs4 import BeautifulSoup

from .base_cms_extractor import BaseCMSExtractor


class MicrosoftEntraExternalIDCMSExtractor(BaseCMSExtractor):
    """Microsoft Entra External ID页面CMS HTML提取器"""
    
    def __init__(self, config_file: str = "soft-category.json", 
                 output_dir: str = "entra_external_id_output"):
        """
        初始化Microsoft Entra External ID CMS提取器
        
        Args:
            config_file: 配置文件路径
            output_dir: 输出目录
        """
        super().__init__(config_file, output_dir, "Microsoft Entra External ID")
    
    @property
    def important_section_titles(self) -> Set[str]:
        """获取Microsoft Entra External ID重要的section标题集合"""
        return {
            "定价详细信息", "定价详情", "pricing details",
            "常见问题", "faq", "frequently asked questions",
            "支持和服务级别协议", "support", "sla", "service level agreement",
            # Microsoft Entra External ID特有的
            "Microsoft Entra External ID定价", "entra external id pricing",
            "外部身份验证", "external authentication", "身份管理", "identity management", 
            "用户认证", "user authentication", "多租户", "multi-tenant",
            "消费者身份", "consumer identity", "B2C", "企业身份", "enterprise identity",
            "月活跃用户", "monthly active users", "MAU", "存储的用户对象", "stored user objects",
            "高级功能", "premium features", "基础", "basic", "标准", "standard",
            "自定义策略", "custom policies", "条件访问", "conditional access"
        }
    
    def get_product_specific_config(self) -> Dict[str, Any]:
        """获取Microsoft Entra External ID产品特定配置"""
        return {
            "table_class": "entra-external-id-pricing-table",
            "banner_class": "entra-external-id-product-banner",
            "content_class": "entra-external-id-pricing-content"
        }
    
    def extract_product_banner(self, soup: BeautifulSoup, content_soup: BeautifulSoup) -> List:
        """提取Microsoft Entra External ID产品横幅"""
        
        banners = []
        
        # 查找产品名称和描述
        product_headers = soup.find_all(['h1', 'h2'], string=lambda text: 
            text and any(keyword in text.lower() for keyword in 
                        ['microsoft entra external id', 'external id', '外部身份验证', '身份管理']))
        
        for header in product_headers:
            banner_div = content_soup.new_tag('div', **{'class': 'entra-external-id-product-banner'})
            
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
        """获取Microsoft Entra External ID产品特定的CSS样式"""
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
        
        .entra-external-id-pricing-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1.5rem;
            background-color: white;
        }
        
        .entra-external-id-pricing-table th,
        .entra-external-id-pricing-table td {
            border: 1px solid #ddd;
            padding: 0.75rem;
            text-align: left;
        }
        
        .entra-external-id-pricing-table th {
            background-color: #f8f9fa;
            font-weight: bold;
            color: #333;
        }
        
        .entra-external-id-pricing-table tr:nth-child(even) {
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
    parser = argparse.ArgumentParser(description="Microsoft Entra External ID CMS HTML提取器")
    parser.add_argument("html_file", help="源HTML文件路径")
    parser.add_argument("-r", "--region", required=True, help="目标区域")
    parser.add_argument("-o", "--output", default="entra_external_id_output", help="输出目录")
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
        extractor = MicrosoftEntraExternalIDCMSExtractor(args.config, args.output)
        result = extractor.extract_cms_html_for_region(args.html_file, args.region)
        
        if result["success"]:
            output_file = extractor.save_cms_html(result, args.region, args.filename)
            print(f"✅ Microsoft Entra External ID CMS HTML提取完成！")
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