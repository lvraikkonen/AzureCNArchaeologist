#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Azure Storage Files页面CMS导入HTML提取器 (重构版)
基于模块化架构，继承BaseCMSExtractor提供Azure Storage Files特定功能
"""

import argparse
import os
from typing import Dict, List, Optional, Set, Any
from bs4 import BeautifulSoup

from .base_cms_extractor import BaseCMSExtractor


class AzureStorageFilesCMSExtractor(BaseCMSExtractor):
    """Azure Storage Files页面CMS HTML提取器 - 重构版"""
    
    def __init__(self, config_file: str = "soft-category.json", 
                 output_dir: str = "storage_files_output"):
        """
        初始化Azure Storage Files CMS提取器
        
        Args:
            config_file: 配置文件路径
            output_dir: 输出目录
        """
        super().__init__(config_file, output_dir, "Azure Storage Files")
    
    @property
    def important_section_titles(self) -> Set[str]:
        """获取Azure Storage Files重要的section标题集合"""
        config = self.config_manager.get_product_config(self.product_name)
        return config.get("important_section_titles", {
            "定价详细信息", "定价详情", "pricing details",
            "了解存储选项", "存储选项", "storage options",
            "数据存储价格", "存储价格", "data storage pricing", "storage pricing",
            "事务和数据传输价格", "事务价格", "transaction pricing", "数据传输价格",
            "文件同步价格", "同步价格", "file sync pricing",
            "常见问题", "faq", "frequently asked questions",
            # 存储冗余类型标题
            "lrs", "grs", "zrs", "ragrs", "gzrs", "ra-grs",
            "本地冗余存储", "地理冗余存储", "区域冗余存储", 
            "读取访问地理冗余存储", "地理区域冗余存储"
        })
    
    def get_product_specific_config(self) -> Dict[str, Any]:
        """获取Azure Storage Files产品特定配置"""
        return {
            "table_class": "storage-files-pricing-table",
            "banner_class": "storage-files-product-banner",
            "content_class": "storage-files-pricing-content"
        }
    
    def extract_product_banner(self, soup: BeautifulSoup, content_soup: BeautifulSoup) -> List:
        """提取Azure Storage Files产品横幅"""
        
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
        """获取Azure Storage Files特定的CSS样式"""
        return self.config_manager.get_css_template(self.product_name, region_name)
    
    def save_cms_html(self, result: Dict[str, Any], region: str, custom_filename: str = "") -> str:
        """保存Azure Storage Files CMS HTML文件（重写以添加Storage Files特定信息）"""
        
        if not result["success"]:
            print(f"❌ 无法保存失败的提取结果")
            return ""
        
        # 调用父类方法保存文件
        file_path = super().save_cms_html(result, region, custom_filename)
        
        # 显示Azure Storage Files特定的验证信息
        verification = result.get("verification", {})
        
        # 显示找到的重要section标题
        if "important_section_titles" in verification:
            titles = verification["important_section_titles"]
            if titles:
                print(f"📋 保留的section标题: {titles}")
        
        # 显示找到的存储冗余类型标题
        if "redundancy_type_titles" in verification:
            redundancy_titles = verification["redundancy_type_titles"]
            if redundancy_titles:
                print(f"🔧 保留的存储类型标题: {redundancy_titles}")
        
        # 显示Storage Files特定关键词
        if "storage_keywords_found" in verification:
            keywords = verification["storage_keywords_found"]
            print(f"🔍 检测到Storage Files关键词: {keywords}")
        
        if "storage_table_count" in verification:
            table_count = verification["storage_table_count"]
            print(f"📊 Storage Files定价表: {table_count} 个")
        
        # 显示结构完整性信息
        if verification.get("has_section_structure", False):
            print("✅ section结构完整")
        
        if verification.get("has_redundancy_structure", False):
            print("✅ 存储冗余类型结构完整")
        
        return file_path


def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description="Azure Storage Files页面CMS HTML提取器 (重构版)")
    parser.add_argument("html_file", help="Azure Storage Files HTML源文件路径")
    parser.add_argument("-r", "--region", default="north-china3", help="目标区域")
    parser.add_argument("-a", "--all-regions", action="store_true", help="提取所有区域")
    parser.add_argument("-c", "--config", default="soft-category.json", help="配置文件路径")
    parser.add_argument("-o", "--output", default="storage_files_output", help="输出目录")
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
        # 创建Azure Storage Files CMS提取器
        extractor = AzureStorageFilesCMSExtractor(args.config, args.output)
        
        # 显示版本信息
        print("🚀 Azure Storage Files页面CMS HTML提取器 v2.0 (重构版)")
        print("📄 基于模块化架构，专门生成适合CMS导入的干净HTML文件")
        print("🎯 特性: 模块化设计、区域过滤、内容清洗、CMS优化、保留section标题、保留存储冗余类型标题")
        
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
        
        print("\n🎉 Azure Storage Files CMS HTML提取任务完成！")
        print("📄 生成的HTML文件可直接导入CMS系统")
        print("📋 现在包含完整的section标题结构")
        print("🔧 现在包含存储冗余类型标题（LRS、GRS等）")
        print("🏗️ 使用模块化架构，维护更加便捷")
        print("💡 建议检查输出文件确认质量")
        return 0
        
    except Exception as e:
        print(f"❌ 提取过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())