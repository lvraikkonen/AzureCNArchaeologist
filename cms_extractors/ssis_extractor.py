#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据工厂SSIS页面CMS导入HTML提取器 (重构版)
基于模块化架构，继承BaseCMSExtractor提供SSIS特定功能
"""

import argparse
import os
from typing import Dict, List, Optional, Set, Any
from bs4 import BeautifulSoup

from .base_cms_extractor import BaseCMSExtractor


class SSISCMSExtractor(BaseCMSExtractor):
    """数据工厂SSIS页面CMS HTML提取器 - 重构版"""
    
    def __init__(self, config_file: str = "soft-category.json", 
                 output_dir: str = "ssis_output"):
        """
        初始化SSIS CMS提取器
        
        Args:
            config_file: 配置文件路径
            output_dir: 输出目录
        """
        super().__init__(config_file, output_dir, "Data Factory SSIS")
    
    @property
    def important_section_titles(self) -> Set[str]:
        """获取SSIS重要的section标题集合"""
        return {
            "定价详细信息", "定价详情", "pricing details",
            "常见问题", "faq", "frequently asked questions",
            "支持和服务级别协议", "support", "sla", "service level agreement",
            # SSIS特有的
            "sql server integration services", "ssis", "数据工厂",
            "integration runtime", "集成运行时", "标准", "standard", "企业", "enterprise",
            "虚拟机", "virtual machine", "vm", "av2", "dv2", "dv3", "ev3", "ev4",
            "azure混合优惠", "azure hybrid benefit", "混合权益", "软件保障", "software assurance",
            "许可证", "license", "vcore", "虚拟核心", "内存", "memory", "临时存储", "temp storage",
            "etl", "数据集成", "data integration", "云托管", "cloud hosted"
        }
    
    def get_product_specific_config(self) -> Dict[str, Any]:
        """获取SSIS产品特定配置"""
        return {
            "table_class": "ssis-pricing-table",
            "banner_class": "ssis-product-banner",
            "content_class": "ssis-pricing-content"
        }
    
    def extract_product_banner(self, soup: BeautifulSoup, content_soup: BeautifulSoup) -> List:
        """提取SSIS产品横幅"""
        
        content_elements = []
        
        # 查找产品横幅
        banner = soup.find('div', class_='common-banner')
        if banner:
            # 直接提取横幅文本内容，不创建复杂结构
            h2 = banner.find('h2')
            h4 = banner.find('h4')
            
            if h2:
                title_h1 = content_soup.new_tag('h1')
                title_h1.string = h2.get_text(strip=True)
                content_elements.append(title_h1)
            
            if h4:
                desc_p = content_soup.new_tag('p')
                desc_p.string = h4.get_text(strip=True)
                content_elements.append(desc_p)
        
        return content_elements
    
    def get_css_styles(self, region_name: str) -> str:
        """获取SSIS特定的CSS样式"""
        
        base_styles = """
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
        
        .ssis-pricing-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1.5rem;
            background-color: white;
        }
        
        .ssis-pricing-table th,
        .ssis-pricing-table td {
            border: 1px solid #ddd;
            padding: 0.75rem;
            text-align: left;
        }
        
        .ssis-pricing-table th {
            background-color: #f8f9fa;
            font-weight: bold;
            color: #333;
        }
        
        .ssis-pricing-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        
        /* SSIS特有样式 */
        .vm-series-section {
            margin-top: 2rem;
            padding: 1rem;
            background-color: #f0f8ff;
            border-radius: 4px;
        }
        
        .edition-section {
            margin-top: 1.5rem;
            border-left: 4px solid #0078d4;
            padding-left: 1rem;
        }
        
        .hybrid-benefit {
            margin-top: 1rem;
            padding: 0.75rem;
            background-color: #e8f5e8;
            border-radius: 4px;
            border-left: 4px solid #28a745;
        }
        
        .pricing-note {
            margin-top: 1rem;
            padding: 0.5rem;
            background-color: #fff8e7;
            border-radius: 4px;
            border-left: 4px solid #ffa500;
            font-size: 0.9rem;
        }
        
        .faq-section {
            margin-top: 2rem;
        }
        
        .faq-title {
            font-size: 1.3rem;
            margin-bottom: 1rem;
            color: #0078d4;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 0.5rem;
        }
        
        /* FAQ 项目样式 - 只应用于 .faq-list */
        .faq-list li {
            margin-bottom: 1rem;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 0;
            list-style: none;
        }
        
        .faq-question {
            background-color: #f8f9fa;
            padding: 0.75rem;
            font-weight: bold;
            color: #333;
            border-bottom: 1px solid #e0e0e0;
            font-size: 1.05rem;
        }
        
        .faq-answer {
            padding: 0.75rem;
            line-height: 1.5;
            color: #666;
            background-color: #ffffff;
        }
        
        /* 普通列表样式 */
        ul {
            margin-bottom: 1rem;
            padding-left: 1.5rem;
        }
        
        ul li {
            margin-bottom: 0.5rem;
            line-height: 1.5;
        }
        
        /* Section标题样式 */
        h2 {
            font-size: 1.4rem;
            color: #0078d4;
            margin: 2rem 0 1rem 0;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 0.5rem;
        }
        
        h3 {
            font-size: 1.2rem;
            color: #333;
            margin: 1.5rem 0 1rem 0;
            border-left: 4px solid #0078d4;
            padding-left: 0.5rem;
        }
        
        h4 {
            font-size: 1.1rem;
            color: #555;
            margin: 1rem 0 0.5rem 0;
        }
        
        /* SSIS特色样式 */
        .ssis-feature {
            background: linear-gradient(135deg, #56ab2f 0%, #a8e6cf 100%);
            color: white;
            padding: 1rem;
            border-radius: 8px;
            margin: 1rem 0;
        }
        
        .vm-type {
            background-color: #e3f2fd;
            padding: 0.5rem;
            border-radius: 4px;
            font-weight: bold;
            display: inline-block;
            margin: 0.2rem;
        }
        
        .cost-savings {
            background-color: #c8e6c9;
            padding: 0.5rem;
            border-radius: 4px;
            color: #2e7d32;
            font-weight: bold;
        }"""
        
        return base_styles
    
    def save_cms_html(self, result: Dict[str, Any], region: str, custom_filename: str = "") -> str:
        """保存SSIS CMS HTML文件（重写以添加特定信息）"""
        
        if not result["success"]:
            print(f"❌ 无法保存失败的提取结果")
            return ""
        
        # 调用父类方法保存文件
        file_path = super().save_cms_html(result, region, custom_filename)
        
        # 显示SSIS特定的验证信息
        verification = result.get("verification", {})
        
        if "ssis_keywords_found" in verification:
            keywords = verification["ssis_keywords_found"]
            print(f"🔧 检测到SSIS关键词: {keywords}")
        
        if "vm_series_found" in verification:
            series = verification["vm_series_found"]
            print(f"💻 检测到VM系列: {series}")
        
        if "editions_found" in verification:
            editions = verification["editions_found"]
            print(f"📦 检测到版本: {editions}")
        
        if "hybrid_benefit_found" in verification:
            print(f"💰 包含Azure混合优惠信息: {verification['hybrid_benefit_found']}")
        
        return file_path


def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description="数据工厂SSIS页面CMS HTML提取器 (重构版)")
    parser.add_argument("html_file", help="SSIS HTML源文件路径")
    parser.add_argument("-r", "--region", default="north-china3", help="目标区域")
    parser.add_argument("-a", "--all-regions", action="store_true", help="提取所有区域")
    parser.add_argument("-c", "--config", default="soft-category.json", help="配置文件路径")
    parser.add_argument("-o", "--output", default="ssis_output", help="输出目录")
    parser.add_argument("--regions", nargs="+", help="指定要提取的区域列表")
    parser.add_argument("--filename", help="指定输出文件名")
    
    args = parser.parse_args()
    
    # 验证输入文件
    if not os.path.exists(args.html_file):
        print(f"❌ HTML文件不存在: {args.html_file}")
        return 1
    
    # 验证配置文件
    if not os.path.exists(args.config):
        print(f"❌ 配置文件不存在: {args.config}")
        return 1
    
    try:
        # 创建SSIS CMS提取器
        extractor = SSISCMSExtractor(args.config, args.output)
        
        # 显示版本信息
        print("🚀 数据工厂SSIS页面CMS HTML提取器 v2.0 (重构版)")
        print("📄 基于模块化架构，专门生成适合CMS导入的干净HTML文件")
        print("🎯 特性: 模块化设计、区域过滤、内容清洗、CMS优化")
        
        if args.all_regions:
            # 批量提取所有区域
            regions = args.regions or list(extractor.region_names.keys())
            results = extractor.extract_all_regions_cms(args.html_file, regions)
            
        else:
            # 提取单个区域
            if args.region not in extractor.region_names:
                print(f"❌ 不支持的区域: {args.region}")
                print(f"支持的区域: {list(extractor.region_names.keys())}")
                return 1
            
            result = extractor.extract_cms_html_for_region(args.html_file, args.region)
            
            if result["success"]:
                output_file = extractor.save_cms_html(result, args.region, args.filename)
                print(f"✅ 单个区域CMS HTML提取完成: {output_file}")
            else:
                print(f"❌ 提取失败: {result.get('error', '未知错误')}")
                return 1
        
        print("\n🎉 数据工厂SSIS CMS HTML提取任务完成！")
        print("📄 生成的HTML文件可直接导入CMS系统")
        print("🔧 使用模块化架构，维护更加便捷")
        print("💡 建议检查输出文件确认质量")
        return 0
        
    except Exception as e:
        print(f"❌ 提取过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())