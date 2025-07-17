#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一CMS提取器命令行入口
支持多产品、多区域的Azure页面CMS HTML提取功能
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# 添加当前目录到Python路径以支持模块导入
sys.path.insert(0, str(Path(__file__).parent))

def print_logo():
    """打印项目LOGO - Claude Code风格"""
    logo = """
  ╭─────────────────────────────────────────────────────────────────╮
  │                                                                 │
  │      ░█████╗░░█████╗░███╗░░██╗                                  │
  │      ██╔══██╗██╔══██╗████╗░██║                                  │
  │      ███████║██║░░╚═╝██╔██╗██║                                  │
  │      ██╔══██║██║░░██╗██║╚████║                                  │
  │      ██║░░██║╚█████╔╝██║░╚███║                                  │
  │      ╚═╝░░╚═╝░╚════╝░╚═╝░░╚══╝                                  │
  │                                                                 │
  │    ██████╗░███████╗███████╗██╗███╗░░██╗███████╗                │
  │    ██╔══██╗██╔════╝██╔════╝██║████╗░██║██╔════╝                │
  │    ██████╔╝█████╗░░█████╗░░██║██╔██╗██║█████╗░░                │
  │    ██╔══██╗██╔══╝░░██╔══╝░░██║██║╚████║██╔══╝░░                │
  │    ██║░░██║███████╗██║░░░░░██║██║░╚███║███████╗                │
  │    ╚═╝░░╚═╝╚══════╝╚═╝░░░░░╚═╝╚═╝░░╚══╝╚══════╝                │
  │                                                                 │
  │                      ✨ ACN REFINE ✨                           │
  │               Azure China Networks Refiner v2.0                │
  │                                                                 │
  │           🔍 Intelligent CMS Content Extraction Tool           │
  │                                                                 │
  │   ┌─ Supported Products ──────────────────────────────────────┐ │
  │   │  🗄️  MySQL Database    📁 Storage Files   🐘 Postgresql    │ │
  │   │  🤖  AnomalyDetector   📊 Power BI Embedded  🔧 SSIS       | |
  │   │  🔐  Entra External ID 🌐 Cosmos DB        🔍 Search       | |
  │   │  🔗  API Management                                        | |
  │   └───────────────────────────────────────────────────────────┘ │
  │                                                                 │
  │   ┌─ Supported Regions ───────────────────────────────────────┐ │
  │   │  🏢 North China • East China • North China 2            │ │
  │   │  🏢 East China 2 • North China 3 • East China 3         │ │
  │   └─────────────────────────────────────────────────────────────┘ │
  │                                                                 │
  │   ┌─ Key Features ────────────────────────────────────────────┐ │
  │   │  ⚡ Modular Architecture   🔄 Batch Processing             │ │
  │   │  ✅ Quality Verification   🎨 CMS Optimization             │ │
  │   │  🌐 Multi-Region Support   📊 Statistical Reports          │ │
  │   └────────────────────────────────────────────────────── ────┘ │
  │                                                                 │
  ╰─────────────────────────────────────────────────────────────────╯

     Built with ❤️  using modular architecture
     Generates clean HTML optimized for CMS import
     Supports region filtering, content cleaning & quality validation
    
"""
    print(logo)

try:
    from cms_extractors import (
        MySQLCMSExtractor,
        AzureStorageFilesCMSExtractor,
        PostgreSQLCMSExtractor,
        AnomalyDetectorCMSExtractor,
        PowerBIEmbeddedCMSExtractor,
        SSISCMSExtractor,
        MicrosoftEntraExternalIDCMSExtractor,
        CosmosDBCMSExtractor,
        AzureSearchCMSExtractor,
        APIManagementCMSExtractor,
        ConfigManager
    )
    from cms_extractors.enhanced_cms_extractor import EnhancedCMSExtractor
except ImportError as e:
    print_logo()
    print(f"❌ 模块导入失败: {e}")
    print("💡 请确保在正确的Python环境中运行:")
    print("   conda activate azure-calculator")
    print("   或使用: /Users/lvshuo/miniforge3/envs/azure-calculator/bin/python")
    sys.exit(1)


class UnifiedCMSExtractor:
    """统一CMS提取器 - 支持多产品处理"""
    
    # 支持的产品映射
    SUPPORTED_PRODUCTS = {
        "mysql": {
            "name": "Azure Database for MySQL",
            "display_name": "MySQL数据库",
            "class": MySQLCMSExtractor,
            "default_files": ["mysql-index.html"],
            "icon": "🗄️"
        },
        "storage-files": {
            "name": "Azure Storage Files", 
            "display_name": "文件存储",
            "class": AzureStorageFilesCMSExtractor,
            "default_files": ["storage-files-index.html"],
            "icon": "📁"
        },
        "postgresql": {
            "name": "Azure Database for PostgreSQL",
            "display_name": "PostgreSQL数据库", 
            "class": PostgreSQLCMSExtractor,
            "default_files": ["postgresql-index.html"],
            "icon": "🐘"
        },
        "anomaly-detector": {
            "name": "AI异常检测器",
            "display_name": "AI异常检测器",
            "class": AnomalyDetectorCMSExtractor,
            "default_files": ["anomaly-detector-index.html"],
            "icon": "🤖",
        },
        "power-bi-embedded": {
            "name": "Power BI嵌入式分析",
            "display_name": "Power BI Embedded",
            "class": PowerBIEmbeddedCMSExtractor,
            "default_files": ["power-bi-embedded-index.html"],
            "icon": "📊",
        },
        "ssis": {
            "name": "数据工厂SSIS",
            "display_name": "Data Factory SSIS",
            "class": SSISCMSExtractor,
            "default_files": ["ssis-index.html"],
            "icon": "🔧", 
        },
        "microsoft-entra-external-id": {
            "name": "Microsoft Entra External ID",
            "display_name": "Microsoft Entra External ID",
            "class": MicrosoftEntraExternalIDCMSExtractor,
            "default_files": ["microsoft-entra-external-id-index.html"],
            "icon": "🔐",
            "has_regional_pricing": False,  # 各区统一定价，无区域差异
        },
        "cosmos-db": {
            "name": "Azure Cosmos DB",
            "display_name": "Azure Cosmos DB",
            "class": CosmosDBCMSExtractor,
            "default_files": ["cosmos-db-index.html"],
            "icon": "🌐",
        },
        "search": {
            "name": "Azure 认知搜索",
            "display_name": "Azure 认知搜索",
            "class": AzureSearchCMSExtractor,
            "default_files": ["search-index.html"],
            "icon": "🔍",
        },
        "api-management": {
            "name": "Azure API Management",
            "display_name": "Azure API Management",
            "class": APIManagementCMSExtractor,
            "default_files": ["api-management-index.html"],
            "icon": "🔗",
        }
    }
    
    def __init__(self, config_file: str = "soft-category.json"):
        """
        初始化统一CMS提取器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config_manager = ConfigManager(config_file)
        
        print("🎯 系统初始化完成")
        print(f"📋 已加载 {len(self.SUPPORTED_PRODUCTS)} 个产品支持")
        print(f"🌍 已配置 {len(self.config_manager.get_supported_regions())} 个区域")
        print("─" * 70)
    
    def extract_product(self, product: str, html_file: str, region: str, 
                       output_dir: str, custom_filename: str = "") -> Dict:
        """
        提取指定产品的CMS HTML
        
        Args:
            product: 产品类型 (mysql, storage-files)
            html_file: 源HTML文件路径
            region: 目标区域
            output_dir: 输出目录
            custom_filename: 自定义文件名
            
        Returns:
            提取结果字典
        """
        
        if product not in self.SUPPORTED_PRODUCTS:
            raise ValueError(f"不支持的产品: {product}。支持的产品: {list(self.SUPPORTED_PRODUCTS.keys())}")
        
        if not os.path.exists(html_file):
            raise FileNotFoundError(f"HTML文件不存在: {html_file}")
        
        if region not in self.config_manager.get_supported_regions():
            raise ValueError(f"不支持的区域: {region}。支持的区域: {self.config_manager.get_supported_regions()}")
        
        # 获取产品信息
        product_info = self.SUPPORTED_PRODUCTS[product]
        extractor_class = product_info["class"]
        
        print(f"\n{product_info['icon']} 开始提取 {product_info['display_name']} CMS HTML")
        print(f"📁 源文件: {html_file}")
        print(f"🌍 目标区域: {region} ({self.config_manager.get_region_display_name(region)})")
        print(f"📂 输出目录: {output_dir}")
        print("═" * 70)
        
        # 创建提取器实例
        extractor = extractor_class(self.config_file, output_dir)
        
        # 执行提取
        result = extractor.extract_cms_html_for_region(html_file, region)
        
        if result["success"]:
            # 保存结果
            output_file = extractor.save_cms_html(result, region, custom_filename)
            result["output_file"] = output_file
            
            print(f"\n✅ {product_info['display_name']} CMS HTML提取完成！")
            print(f"📄 输出文件: {output_file}")
        else:
            print(f"\n❌ {product_info['display_name']} 提取失败: {result.get('error', '未知错误')}")
        
        return result
    
    def extract_batch(self, product: str, html_file: str, regions: List[str], 
                     output_dir: str) -> Dict[str, Dict]:
        """
        批量提取多个区域的CMS HTML
        
        Args:
            product: 产品类型
            html_file: 源HTML文件路径
            regions: 区域列表
            output_dir: 输出目录
            
        Returns:
            批量提取结果字典
        """
        
        if product not in self.SUPPORTED_PRODUCTS:
            raise ValueError(f"不支持的产品: {product}")
        
        if not os.path.exists(html_file):
            raise FileNotFoundError(f"HTML文件不存在: {html_file}")
        
        # 获取产品信息
        product_info = self.SUPPORTED_PRODUCTS[product]
        extractor_class = product_info["class"]
        
        # 检查是否有区域定价差异
        has_regional_pricing = product_info.get("has_regional_pricing", True)
        
        if not has_regional_pricing:
            # 无区域差异，生成单个allregion文件
            print(f"\n🌍 {product_info['display_name']} 使用全球统一定价")
            print(f"📁 源文件: {html_file}")
            print(f"📄 将生成单个HTML文件 (allregion)")
            print(f"📂 输出目录: {output_dir}")
            print("═" * 70)
            
            # 创建提取器实例
            extractor = extractor_class(self.config_file, output_dir)
            
            # 生成单个allregion文件（使用第一个区域作为模板）
            result = extractor.extract_cms_html_for_region(html_file, regions[0] if regions else "north-china")
            
            if result["success"]:
                # 修改区域信息为allregion
                result["region"] = {
                    "id": "allregion",
                    "name": "全球统一定价"
                }
                
                # 保存文件
                output_file = extractor.save_cms_html(result, "allregion")
                result["output_file"] = output_file
                
                print(f"✅ {product_info['display_name']} 全球统一定价HTML提取完成")
            else:
                print(f"❌ {product_info['display_name']} 提取失败")
            
            return {"allregion": result}
        
        else:
            # 有区域差异，按现有逻辑处理
            # 创建提取器实例以获取产品名称
            extractor = extractor_class(self.config_file, output_dir)
            product_name = extractor.product_name

            # 获取该产品实际支持的区域
            product_supported_regions = self.config_manager.get_product_supported_regions(product_name)

            if not product_supported_regions:
                print(f"⚠️ 产品 {product_info['display_name']} 在配置中没有找到支持的区域")
                print(f"💡 将使用所有标准区域进行处理")
                product_supported_regions = self.config_manager.get_supported_regions()

            # 过滤出该产品实际支持的区域
            valid_regions = [r for r in regions if r in product_supported_regions]
            unsupported_regions = [r for r in regions if r not in product_supported_regions]

            if unsupported_regions:
                print(f"⚠️ 产品 {product_info['display_name']} 不支持以下区域: {unsupported_regions}")
                print(f"✅ 将处理支持的区域: {valid_regions}")

            if not valid_regions:
                print(f"❌ 没有找到产品 {product_info['display_name']} 支持的区域")
                return {}

            print(f"\n🌍 开始批量提取 {product_info['display_name']} CMS HTML")
            print(f"📁 源文件: {html_file}")
            print(f"🎯 产品支持的区域: {len(product_supported_regions)} 个")
            print(f"🎯 实际处理区域: {len(valid_regions)} 个")
            for region in valid_regions:
                print(f"   • {region} ({self.config_manager.get_region_display_name(region)})")
            print(f"📂 输出目录: {output_dir}")
            print("═" * 70)

            # 执行批量提取（只处理支持的区域）
            batch_results = extractor.extract_all_regions_cms(html_file, valid_regions)

            return batch_results
    
    def extract_multi_product(self, html_dir: str, output_base_dir: str, 
                             regions: Optional[List[str]] = None,
                             products: Optional[List[str]] = None) -> Dict[str, Dict]:
        """
        多产品批量提取
        
        Args:
            html_dir: HTML文件目录
            output_base_dir: 输出基础目录
            regions: 区域列表（默认所有区域）
            products: 产品列表（默认所有产品）
            
        Returns:
            多产品提取结果字典
        """
        
        if regions is None:
            regions = self.config_manager.get_supported_regions()
        
        if products is None:
            products = list(self.SUPPORTED_PRODUCTS.keys())
        
        # 验证产品
        invalid_products = [p for p in products if p not in self.SUPPORTED_PRODUCTS]
        if invalid_products:
            raise ValueError(f"不支持的产品: {invalid_products}")
        
        print(f"\n🏭 开始多产品批量提取")
        print(f"📁 HTML目录: {html_dir}")
        print(f"📂 输出基础目录: {output_base_dir}")
        
        print(f"\n🎯 产品列表 ({len(products)} 个):")
        for product in products:
            info = self.SUPPORTED_PRODUCTS[product]
            print(f"   {info['icon']} {product} - {info['display_name']}")
        
        print(f"\n🌍 区域列表 ({len(regions)} 个):")
        for region in regions:
            print(f"   • {region} ({self.config_manager.get_region_display_name(region)})")
        
        print("═" * 70)
        
        all_results = {}
        
        for i, product in enumerate(products, 1):
            product_info = self.SUPPORTED_PRODUCTS[product]
            
            print(f"\n{'═'*70}")
            print(f"{product_info['icon']} 处理产品 [{i}/{len(products)}]: {product_info['display_name']}")
            print(f"{'═'*70}")
            
            # 查找对应的HTML文件
            html_file = self._find_html_file(html_dir, product)
            if not html_file:
                print(f"⚠️  跳过产品 {product}: 未找到对应的HTML文件")
                expected_files = self.SUPPORTED_PRODUCTS[product]["default_files"]
                print(f"   预期文件: {', '.join(expected_files)}")
                all_results[product] = {
                    "success": False,
                    "error": "HTML文件不存在",
                    "expected_files": expected_files
                }
                continue
            
            # 创建产品特定的输出目录
            product_output_dir = os.path.join(output_base_dir, f"{product}_cms_output")
            os.makedirs(product_output_dir, exist_ok=True)
            
            try:
                # 批量提取该产品的所有区域
                batch_results = self.extract_batch(product, html_file, regions, product_output_dir)
                all_results[product] = {
                    "success": True,
                    "html_file": html_file,
                    "output_dir": product_output_dir,
                    "regions": batch_results
                }
                
                # 统计成功率
                if "allregion" in batch_results:
                    # 无区域差异的产品
                    success = batch_results["allregion"].get("success", False)
                    print(f"✅ {product_info['display_name']} 完成: {'成功' if success else '失败'} (全球统一定价)")
                else:
                    # 有区域差异的产品
                    successful_regions = sum(1 for r in batch_results.values() if r.get("success", False))
                    print(f"✅ {product_info['display_name']} 完成: {successful_regions}/{len(regions)} 个区域成功")
                
            except Exception as e:
                print(f"❌ {product_info['display_name']} 处理失败: {e}")
                all_results[product] = {
                    "success": False,
                    "error": str(e),
                    "html_file": html_file
                }
        
        # 生成总结报告
        self._generate_multi_product_summary(all_results, output_base_dir)
        
        return all_results
    
    def _find_html_file(self, html_dir: str, product: str) -> Optional[str]:
        """
        查找产品对应的HTML文件
        
        Args:
            html_dir: HTML文件目录
            product: 产品类型
            
        Returns:
            HTML文件路径，如果未找到返回None
        """
        
        default_files = self.SUPPORTED_PRODUCTS[product]["default_files"]
        
        for filename in default_files:
            file_path = os.path.join(html_dir, filename)
            if os.path.exists(file_path):
                return file_path
        
        return None
    
    def _generate_multi_product_summary(self, results: Dict, output_base_dir: str):
        """
        生成多产品处理总结报告
        
        Args:
            results: 处理结果字典
            output_base_dir: 输出基础目录
        """
        
        from datetime import datetime
        import json
        
        summary = {
            "processing_info": {
                "processed_at": datetime.now().isoformat(),
                "extraction_version": "2.0_unified_cli",
                "extractor_name": "Azure CN Archaeologist",
                "total_products": len(results),
                "successful_products": sum(1 for r in results.values() if r.get("success", False))
            },
            "products": results,
            "overall_statistics": {
                "total_regions_processed": 0,
                "successful_extractions": 0,
                "failed_extractions": 0
            }
        }
        
        # 计算总体统计
        for product, result in results.items():
            if result.get("success", False) and "regions" in result:
                regions_data = result["regions"]
                summary["overall_statistics"]["total_regions_processed"] += len(regions_data)
                summary["overall_statistics"]["successful_extractions"] += sum(
                    1 for r in regions_data.values() if r.get("success", False)
                )
                summary["overall_statistics"]["failed_extractions"] += sum(
                    1 for r in regions_data.values() if not r.get("success", False)
                )
        
        # 保存总结报告
        summary_path = os.path.join(output_base_dir, f"acn_refine_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        os.makedirs(output_base_dir, exist_ok=True)
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"\n📋 多产品处理总结:")
        print(f"✅ 成功产品: {summary['processing_info']['successful_products']}/{summary['processing_info']['total_products']}")
        print(f"📊 总提取次数: {summary['overall_statistics']['successful_extractions']}")
        print(f"❌ 失败次数: {summary['overall_statistics']['failed_extractions']}")
        print(f"📁 输出目录: {output_base_dir}")
        print(f"📊 总结报告: {summary_path}")


def main():
    """主程序入口"""
    
    # 首先显示LOGO
    print_logo()
    
    parser = argparse.ArgumentParser(
        description="ACN REFINE - Azure China Networks Refiner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
🌟 使用示例:
  
  单产品单区域提取:
    %(prog)s mysql prod-html/mysql-index.html -r north-china3 -o mysql_output
    
  单产品多区域提取:
    %(prog)s storage-files prod-html/storage-files-index.html -a -o storage_output
    
  全球统一定价产品提取:
    %(prog)s microsoft-entra-external-id prod-html/microsoft-entra-external-id-index.html -a -o output
    
  指定多个区域:
    %(prog)s mysql prod-html/mysql-index.html --regions north-china3 east-china2 -o output
    
  多产品批量提取:
    %(prog)s --multi-product -i prod-html -o multi_output
    
  增强型CMS JSON导出 (新功能):
    %(prog)s mysql prod-html/mysql-index.html --export-json --url https://www.azure.cn/pricing/details/mysql/
    %(prog)s --multi-product -i prod-html --export-json --json-output-dir json_output
    
  列出支持的产品和区域:
    %(prog)s --list-products
    %(prog)s --list-regions

🎯 支持的产品:
  mysql                      - 🗄️  Azure Database for MySQL (MySQL数据库)
  storage-files              - 📁 Azure Storage Files (文件存储)
  postgresql                 - 🐘 Azure Database for PostgreSQL (PostgreSQL数据库)
  anomaly-detector           - 🤖 AI异常检测器 (Anomaly Detector)
  power-bi-embedded          - 📊 Power BI嵌入式分析 (Power BI Embedded)
  ssis                       - 🔧 数据工厂SSIS (Data Factory SSIS)
  microsoft-entra-external-id - 🔐 Microsoft Entra External ID
  cosmos-db                  - 🌐 Azure Cosmos DB
  search                     - 🔍 Azure 认知搜索 (Azure Cognitive Search)
  api-management             - 🔗 Azure API Management (API管理)
  
🌍 支持的区域:
  north-china, east-china, north-china2, east-china2, north-china3, east-china3
        """
    )
    
    # 基础参数
    parser.add_argument("product", nargs="?", choices=list(UnifiedCMSExtractor.SUPPORTED_PRODUCTS.keys()),
                       help="产品类型")
    parser.add_argument("html_file", nargs="?", help="HTML源文件路径")
    
    # 区域参数
    parser.add_argument("-r", "--region", help="目标区域 (单区域模式)")
    parser.add_argument("-a", "--all-regions", action="store_true", help="提取所有区域")
    parser.add_argument("--regions", nargs="+", help="指定要提取的区域列表")
    
    # 输出参数
    parser.add_argument("-o", "--output", default="cms_output", help="输出目录 (默认: cms_output)")
    parser.add_argument("--filename", help="指定输出文件名")
    
    # 配置参数
    parser.add_argument("-c", "--config", default="soft-category.json", help="配置文件路径")
    
    # 多产品模式
    parser.add_argument("--multi-product", action="store_true", help="多产品批量提取模式")
    parser.add_argument("-i", "--input-dir", help="HTML文件输入目录 (多产品模式)")
    parser.add_argument("--products", nargs="+", help="指定要处理的产品列表 (多产品模式)")
    
    # 信息查询
    parser.add_argument("--list-products", action="store_true", help="列出支持的产品")
    parser.add_argument("--list-regions", action="store_true", help="列出支持的区域")
    
    # 增强型CMS JSON导出
    parser.add_argument("--export-json", action="store_true", help="导出增强型CMS JSON格式（包含Banner、Q&A、各区域内容等模块）")
    parser.add_argument("--url", help="页面URL（用于提取slug，JSON导出模式）")
    parser.add_argument("--json-output-dir", default="enhanced_cms_output", help="JSON输出目录（默认: enhanced_cms_output）")
    
    args = parser.parse_args()
    
    # 验证配置文件
    if not os.path.exists(args.config):
        print(f"❌ 配置文件不存在: {args.config}")
        return 1
    
    try:
        # 创建统一提取器
        extractor = UnifiedCMSExtractor(args.config)
        
        # 处理信息查询
        if args.list_products:
            print("\n📋 支持的产品:")
            print("─" * 70)
            for key, info in UnifiedCMSExtractor.SUPPORTED_PRODUCTS.items():
                print(f"  {info['icon']} {key:15} - {info['display_name']}")
                print(f"    {'':15}   技术名称: {info['name']}")
                print(f"    {'':15}   默认文件: {', '.join(info['default_files'])}")
                print()
            return 0
        
        if args.list_regions:
            print("\n🌍 支持的区域:")
            print("─" * 70)
            for region in extractor.config_manager.get_supported_regions():
                region_name = extractor.config_manager.get_region_display_name(region)
                print(f"  🏢 {region:15} - {region_name}")
            return 0
        
        # 多产品模式
        if args.multi_product:
            if not args.input_dir:
                print("❌ 多产品模式需要指定输入目录 (-i/--input-dir)")
                return 1
            
            if not os.path.exists(args.input_dir):
                print(f"❌ 输入目录不存在: {args.input_dir}")
                return 1
            
            # 确定区域列表
            if args.all_regions:
                regions = extractor.config_manager.get_supported_regions()
            elif args.regions:
                regions = args.regions
            else:
                regions = extractor.config_manager.get_supported_regions()
                print(f"ℹ️  未指定区域，使用所有支持的区域: {len(regions)} 个")
            
            # 确定产品列表
            products = args.products or list(UnifiedCMSExtractor.SUPPORTED_PRODUCTS.keys())
            
            # 执行多产品提取
            results = extractor.extract_multi_product(args.input_dir, args.output, regions, products)
            
            # 显示结果
            successful_products = sum(1 for r in results.values() if r.get("success", False))
            print(f"\n🎉 多产品提取完成！")
            print(f"✅ 成功: {successful_products}/{len(products)} 个产品")
            
            # 显示详细结果
            for product, result in results.items():
                if result.get("success", False):
                    if "regions" in result and "allregion" in result["regions"]:
                        print(f"   🔐 {product}: 全球统一定价 HTML 已生成")
                    else:
                        region_count = len(result.get("regions", {}))
                        print(f"   📊 {product}: {region_count} 个区域文件已生成")
            
            return 0
        
        # 检查是否使用增强型JSON导出
        if args.export_json:
            return handle_enhanced_json_export(args)
        
        # 单产品模式
        if not args.product:
            print("❌ 请指定产品类型，或使用 --multi-product 进行多产品提取")
            print("💡 使用 --list-products 查看支持的产品")
            return 1
        
        if not args.html_file:
            print("❌ 请指定HTML源文件路径")
            return 1
        
        # 确定区域列表
        if args.all_regions:
            regions = extractor.config_manager.get_supported_regions()
            # 批量提取
            results = extractor.extract_batch(args.product, args.html_file, regions, args.output)
            
            if "allregion" in results:
                # 无区域差异的产品
                success = results["allregion"].get("success", False)
                print(f"\n🎉 批量提取完成！")
                print(f"✅ {'成功' if success else '失败'}: 全球统一定价 HTML 已生成")
            else:
                # 有区域差异的产品
                successful_count = sum(1 for r in results.values() if r.get("success", False))
                print(f"\n🎉 批量提取完成！")
                print(f"✅ 成功: {successful_count}/{len(regions)} 个区域")
            
        elif args.regions:
            # 指定区域列表批量提取
            results = extractor.extract_batch(args.product, args.html_file, args.regions, args.output)
            
            if "allregion" in results:
                # 无区域差异的产品
                success = results["allregion"].get("success", False)
                print(f"\n🎉 批量提取完成！")
                print(f"✅ {'成功' if success else '失败'}: 全球统一定价 HTML 已生成")
            else:
                # 有区域差异的产品
                successful_count = sum(1 for r in results.values() if r.get("success", False))
                print(f"\n🎉 批量提取完成！")
                print(f"✅ 成功: {successful_count}/{len(args.regions)} 个区域")
            
        elif args.region:
            # 单区域提取
            result = extractor.extract_product(args.product, args.html_file, args.region, 
                                             args.output, args.filename)
            
            if result["success"]:
                print(f"✅ 单区域提取完成")
            else:
                print(f"❌ 提取失败: {result.get('error', '未知错误')}")
                return 1
        else:
            print("❌ 请指定区域 (-r)、所有区域 (-a) 或区域列表 (--regions)")
            return 1
        
        print("\n" + "═" * 70)
        print("🎊 任务完成！生成的HTML文件已针对CMS导入进行优化")
        print("📝 文件特点: 干净结构 • 区域过滤 • 质量验证 • 响应式样式")
        print("💡 建议在导入CMS前预览检查文件质量")
        print("═" * 70)
        
        return 0
        
    except Exception as e:
        print(f"❌ 提取过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


def handle_enhanced_json_export(args):
    """处理增强型JSON导出功能"""
    
    print("\n🆕 增强型CMS JSON导出模式")
    print("📋 导出内容: Banner、描述、Q&A、各区域内容、元数据等")
    print("═" * 70)
    
    # 创建增强型提取器
    enhanced_extractor = EnhancedCMSExtractor(output_dir=args.json_output_dir)
    
    if args.multi_product:
        # 多产品JSON导出
        if not args.input_dir:
            print("❌ 多产品模式需要指定输入目录 (-i/--input-dir)")
            return 1
        
        if not os.path.exists(args.input_dir):
            print(f"❌ 输入目录不存在: {args.input_dir}")
            return 1
        
        print(f"🔧 批量处理目录: {args.input_dir}")
        print(f"📁 JSON输出目录: {args.json_output_dir}")
        
        # 获取所有HTML文件
        html_files = []
        for filename in os.listdir(args.input_dir):
            if filename.endswith('.html'):
                html_files.append(os.path.join(args.input_dir, filename))
        
        if not html_files:
            print(f"❌ 在目录 {args.input_dir} 中未找到HTML文件")
            return 1
        
        print(f"📊 找到 {len(html_files)} 个HTML文件")
        
        successful_count = 0
        failed_files = []
        
        for i, html_file in enumerate(html_files, 1):
            print(f"\n处理文件 {i}/{len(html_files)}: {os.path.basename(html_file)}")
            
            try:
                # 生成URL（如果可以推断的话）
                url = generate_url_from_filename(html_file) if not args.url else args.url
                
                # 生成输出文件名
                file_stem = Path(html_file).stem
                output_filename = f"{file_stem}_enhanced_cms.json"
                
                # 提取内容
                content = enhanced_extractor.process_html_file(
                    html_file_path=html_file,
                    url=url,
                    output_filename=output_filename
                )
                
                if "error" in content:
                    print(f"❌ 提取失败: {content['error']}")
                    failed_files.append(html_file)
                else:
                    print(f"✅ 提取成功！")
                    successful_count += 1
                    print_json_export_summary(content)
                    
            except Exception as e:
                print(f"❌ 处理异常: {e}")
                failed_files.append(html_file)
        
        # 批量处理总结
        print(f"\n📊 批量JSON导出完成:")
        print(f"✅ 成功: {successful_count} 个文件")
        print(f"❌ 失败: {len(failed_files)} 个文件")
        
        if failed_files:
            print(f"\n失败文件列表:")
            for file in failed_files:
                print(f"  - {os.path.basename(file)}")
        
        return 0 if successful_count > 0 else 1
    
    else:
        # 单文件JSON导出
        if not args.product:
            print("❌ 请指定产品类型或使用 --multi-product 进行批量导出")
            return 1
        
        if not args.html_file:
            print("❌ 请指定HTML源文件路径")
            return 1
        
        if not os.path.exists(args.html_file):
            print(f"❌ 文件不存在: {args.html_file}")
            return 1
        
        print(f"🔧 处理单个文件: {args.html_file}")
        
        # 提取内容
        content = enhanced_extractor.process_html_file(
            html_file_path=args.html_file,
            url=args.url or "",
            output_filename=args.filename or ""
        )
        
        if "error" in content:
            print(f"❌ 提取失败: {content['error']}")
            return 1
        else:
            print(f"✅ 提取成功！")
            print_json_export_summary(content)
            return 0


def generate_url_from_filename(html_file):
    """根据文件名生成可能的URL"""
    
    filename = os.path.basename(html_file)
    
    # 移除-index.html后缀
    if filename.endswith('-index.html'):
        slug = filename.replace('-index.html', '')
        return f"https://www.azure.cn/pricing/details/{slug}/"
    
    return ""


def print_json_export_summary(content):
    """打印JSON导出摘要"""
    
    print(f"\n📋 JSON导出摘要:")
    print(f"  标题: {content.get('Title', 'N/A')}")
    print(f"  语言: {content.get('Language', 'N/A')}")
    print(f"  Slug: {content.get('Slug', 'N/A')}")
    print(f"  包含区域: {content.get('HasRegion', False)}")
    
    # 内容长度统计
    content_stats = {
        'Banner': len(content.get('BannerContent', '')),
        'Description': len(content.get('DescriptionContent', '')),
        'Q&A': len(content.get('QaContent', '')),
        'NoRegion': len(content.get('NoRegionContent', ''))
    }
    
    # 区域内容统计
    region_keys = ['NorthChinaContent', 'NorthChina2Content', 'NorthChina3Content', 
                   'EastChinaContent', 'EastChina2Content', 'EastChina3Content']
    
    for key in region_keys:
        if key in content:
            region_name = key.replace('Content', '')
            content_stats[region_name] = len(content.get(key, ''))
    
    print(f"\n📊 内容长度统计:")
    for section, length in content_stats.items():
        if length > 0:
            print(f"  {section}: {length:,} 字符")


if __name__ == "__main__":
    exit(main())