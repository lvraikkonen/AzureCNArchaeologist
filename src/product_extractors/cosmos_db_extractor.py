#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Azure Cosmos DB页面CMS导入HTML提取器
基于模块化架构，继承BaseCMSExtractor提供Cosmos DB特定功能
"""

import argparse
import os
from typing import Dict, List, Optional, Set, Any
from bs4 import BeautifulSoup

from ..core.base_cms_extractor import BaseCMSExtractor


class CosmosDBCMSExtractor(BaseCMSExtractor):
    """Azure Cosmos DB页面CMS HTML提取器"""
    
    def __init__(self, config_file: str = "soft-category.json", 
                 output_dir: str = "cosmos_db_output"):
        """
        初始化Cosmos DB CMS提取器
        
        Args:
            config_file: 配置文件路径
            output_dir: 输出目录
        """
        super().__init__(config_file, output_dir, "Azure Cosmos DB")
    
    @property
    def important_section_titles(self) -> Set[str]:
        """获取Cosmos DB重要的section标题集合"""
        return {
            "定价详细信息", "定价详情", "pricing details",
            "常见问题", "faq", "frequently asked questions",
            "支持和服务级别协议", "support", "sla", "service level agreement",
            # Cosmos DB特有的
            "Azure Cosmos DB定价", "cosmos db pricing", "cosmosdb pricing",
            "请求单位", "request units", "ru", "吞吐量", "throughput",
            "预配吞吐量", "provisioned throughput", "无服务器", "serverless",
            "自动缩放", "autoscale", "标准", "standard", "预留容量", "reserved capacity",
            "多区域写入", "multi-region writes", "多主数据库", "multi-master",
            "存储", "storage", "备份", "backup", "还原", "restore",
            "SQL API", "MongoDB API", "Cassandra API", "Gremlin API", "Table API",
            "分析存储", "analytical storage", "Synapse Link", "全局分发", "global distribution",
            "专用网关", "dedicated gateway", "计算", "compute", "事务", "transaction"
        }
    
    def get_product_specific_config(self) -> Dict[str, Any]:
        """获取Cosmos DB产品特定配置"""
        return {
            "table_class": "cosmos-db-pricing-table",
            "banner_class": "cosmos-db-product-banner",
            "content_class": "cosmos-db-pricing-content"
        }
    
    def extract_product_banner(self, soup: BeautifulSoup, content_soup: BeautifulSoup) -> List:
        """提取Cosmos DB产品横幅"""
        
        banners = []
        
        # 查找产品名称和描述
        product_headers = soup.find_all(['h1', 'h2'], string=lambda text: 
            text and any(keyword in text.lower() for keyword in 
                        ['cosmos db', 'cosmosdb', 'azure cosmos', '数据库', 'nosql']))
        
        for header in product_headers:
            banner_div = content_soup.new_tag('div', **{'class': 'cosmos-db-product-banner'})
            
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
        """获取Cosmos DB产品特定的CSS样式"""
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
        
        .cosmos-db-pricing-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1.5rem;
            background-color: white;
        }
        
        .cosmos-db-pricing-table th,
        .cosmos-db-pricing-table td {
            border: 1px solid #ddd;
            padding: 0.75rem;
            text-align: left;
        }
        
        .cosmos-db-pricing-table th {
            background-color: #f8f9fa;
            font-weight: bold;
            color: #333;
        }
        
        .cosmos-db-pricing-table tr:nth-child(even) {
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
    parser = argparse.ArgumentParser(description="Azure Cosmos DB CMS HTML提取器")
    parser.add_argument("html_file", help="源HTML文件路径")
    parser.add_argument("-r", "--region", required=True, help="目标区域")
    parser.add_argument("-o", "--output", default="cosmos_db_output", help="输出目录")
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
        extractor = CosmosDBCMSExtractor(args.config, args.output)
        result = extractor.extract_cms_html_for_region(args.html_file, args.region)
        
        if result["success"]:
            output_file = extractor.save_cms_html(result, args.region, args.filename)
            print(f"✅ Azure Cosmos DB CMS HTML提取完成！")
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