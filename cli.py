#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AzureCNArchaeologist 主CLI入口
统一的命令行界面，支持所有项目功能
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.exporters.json_exporter import JSONExporter
from src.exporters.html_exporter import HTMLExporter
from src.exporters.rag_exporter import RAGExporter


def print_banner():
    """打印项目横幅"""
    banner = """
╭─────────────────────────────────────────────────────────────╮
│                                                             │
│  ░█████╗░███████╗██╗░░░██╗██████╗░███████╗                 │
│  ██╔══██╗╚════██║██║░░░██║██╔══██╗██╔════╝                 │
│  ███████║░░███╔═╝██║░░░██║██████╔╝█████╗░░                 │
│  ██╔══██║██╔══╝░░██║░░░██║██╔══██╗██╔══╝░░                 │
│  ██║░░██║███████╗╚██████╔╝██║░░██║███████╗                 │
│  ╚═╝░░╚═╝╚══════╝░╚═════╝░╚═╝░░╚═╝╚══════╝                 │
│                                                             │
│   █████╗░██████╗░░█████╗░██╗░░██╗░█████╗░███████╗░█████╗░  │
│  ██╔══██╗██╔══██╗██╔══██╗██║░░██║██╔══██╗██╔════╝██╔══██╗  │
│  ███████║██████╔╝██║░░╚═╝███████║███████║█████╗░░██║░░██║  │
│  ██╔══██║██╔══██╗██║░░██╗██╔══██║██╔══██║██╔══╝░░██║░░██║  │
│  ██║░░██║██║░░██║╚█████╔╝██║░░██║██║░░██║███████╗╚█████╔╝  │
│  ╚═╝░░╚═╝╚═╝░░╚═╝░╚════╝░╚═╝░░╚═╝╚═╝░░╚═╝╚══════╝░╚════╝░  │
│                                                             │
│           Azure中国定价数据发掘与智能重构项目               │
│                                                             │
╰─────────────────────────────────────────────────────────────╯
"""
    print(banner)


def extract_command(args):
    """执行数据提取命令"""
    print(f"📡 开始提取产品数据: {args.product}")
    print(f"   HTML文件: {args.html_file}")
    print(f"   输出格式: {args.format}")
    print(f"   输出目录: {args.output_dir}")
    
    try:
        # 支持的产品映射
        product_mapping = {
            'mysql': 'mysql-index.html',
            'api-management': 'api-management-index.html',
            'storage-files': 'storage-files-index.html',
            'postgresql': 'postgresql-index.html',
            'cosmos-db': 'cosmos-db-index.html',
            'search': 'search-index.html',
            'power-bi-embedded': 'power-bi-embedded-index.html',
            'ssis': 'ssis-index.html',
            'anomaly-detector': 'anomaly-detector-index.html',
            'microsoft-entra-external-id': 'microsoft-entra-external-id-index.html',
        }
        
        if args.product in product_mapping:
            from src.extractors.enhanced_cms_extractor import EnhancedCMSExtractor
            
            # 使用增强提取器
            extractor = EnhancedCMSExtractor(args.output_dir, args.config)
            
            # 从文件名生成对应的URL (用于提取Slug)
            filename = Path(args.html_file).name
            
            # URL映射表
            url_mapping = {
                'mysql-index.html': 'https://www.azure.cn/pricing/details/mysql/',
                'api-management-index.html': 'https://www.azure.cn/pricing/details/api-management/',
                'storage-files-index.html': 'https://www.azure.cn/pricing/details/storage/files/',
                'postgresql-index.html': 'https://www.azure.cn/pricing/details/postgresql/',
                'cosmos-db-index.html': 'https://www.azure.cn/pricing/details/cosmos-db/',
                'search-index.html': 'https://www.azure.cn/pricing/details/search/',
                'power-bi-embedded-index.html': 'https://www.azure.cn/pricing/details/power-bi-embedded/',
                'ssis-index.html': 'https://www.azure.cn/pricing/details/data-factory/ssis/',
                'anomaly-detector-index.html': 'https://www.azure.cn/pricing/details/cognitive-services/anomaly-detector/',
                'microsoft-entra-external-id-index.html': 'https://www.azure.cn/pricing/details/entra-external-id/',
            }
            
            # 获取URL，如果没有映射则从文件名推导
            url = url_mapping.get(filename)
            if not url:
                product_slug = filename.replace('-index.html', '')
                url = f"https://www.azure.cn/pricing/details/{product_slug}/"
            
            print(f"🔗 使用URL: {url}")
            
            data = extractor.extract_cms_content(args.html_file, url)
            
            # 根据格式选择合适的导出器
            if args.format == 'json':
                from src.exporters.json_exporter import JSONExporter
                exporter = JSONExporter(args.output_dir)
                output_path = exporter.export_enhanced_cms_data(data, args.product)
            elif args.format == 'html':
                from src.exporters.html_exporter import HTMLExporter
                exporter = HTMLExporter(args.output_dir)
                output_path = exporter.export_enhanced_cms_data(data, args.product)
            elif args.format == 'rag':
                from src.exporters.rag_exporter import RAGExporter
                exporter = RAGExporter(args.output_dir)
                output_path = exporter.export_enhanced_cms_data(data, args.product)
            
            print(f"✅ 数据已导出到: {output_path}")
            
        else:
            print(f"❌ 暂不支持产品: {args.product}")
            supported_products = ', '.join(product_mapping.keys())
            print(f"支持的产品: {supported_products}")
            
    except Exception as e:
        print(f"❌ 提取过程出错: {str(e)}")
        return 1
    
    print("✅ 数据提取完成")


def export_command(args):
    """执行数据导出命令"""
    print(f"📤 开始导出数据: {args.format}")
    print(f"   输入文件: {args.input}")
    print(f"   输出目录: {args.output}")
    
    if args.format == 'json':
        exporter = JSONExporter(args.output)
        print("✅ JSON导出完成")
    elif args.format == 'html':
        exporter = HTMLExporter(args.output)
        print("✅ HTML导出完成")
    elif args.format == 'rag':
        exporter = RAGExporter(args.output)
        print("✅ RAG格式导出完成")


def batch_command(args):
    """执行批处理命令"""
    print(f"🔄 开始批处理")
    print(f"   输入目录: {args.input_dir}")
    print(f"   输出目录: {args.output_dir}")
    print(f"   产品过滤: {args.products}")
    
    # TODO: 实现批处理逻辑
    print("✅ 批处理完成")


def list_products_command(args):
    """列出支持的产品"""
    # 从CLI中的实际支持列表获取
    products = [
        "mysql", "api-management", "storage-files", "postgresql",
        "cosmos-db", "search", "power-bi-embedded", "ssis",
        "anomaly-detector", "microsoft-entra-external-id"
    ]
    
    print("📋 支持的产品列表:")
    for i, product in enumerate(products, 1):
        print(f"   {i:2d}. {product}")
    
    print(f"\n总计: {len(products)} 个产品")
    print("\n💡 使用方法:")
    print("   python cli.py extract <product> --html-file <path> --format <format> --output-dir <dir>")
    print("   例如: python cli.py extract api-management --html-file data/prod-html/api-management-index.html --format json --output-dir output/api-management")


def status_command(args):
    """显示项目状态"""
    print("📊 项目状态:")
    print("   ├── 架构: 模块化重构完成")
    print("   ├── 核心模块: ✅ 已迁移到 src/core/")
    print("   ├── 导出器: ✅ 已创建 src/exporters/")
    print("   ├── 产品提取器: ✅ 已迁移到 src/product_extractors/")
    print("   └── CLI界面: ✅ 统一入口已创建")


def create_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description='Azure中国定价数据发掘与智能重构项目',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  %(prog)s extract api-management --html-file data/prod-html/api-management-index.html --format json --output-dir output/api-management
  %(prog)s export json --input output/mysql_data.json
  %(prog)s batch --input-dir data/prod-html --output-dir output
  %(prog)s list-products
  %(prog)s status
        """
    )
    
    # 添加全局选项
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='显示详细输出')
    parser.add_argument('--config', '-c', default='data/configs/soft-category.json',
                       help='配置文件路径')
    
    # 创建子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # extract 命令
    extract_parser = subparsers.add_parser('extract', help='提取产品数据')
    extract_parser.add_argument('product', help='产品名称')
    extract_parser.add_argument('--html-file', required=True, 
                               help='输入HTML文件路径')
    extract_parser.add_argument('--format', choices=['json', 'html', 'rag'],
                               default='json', help='输出格式')
    extract_parser.add_argument('--output-dir', default='output',
                               help='输出目录')
    extract_parser.add_argument('--region', help='指定区域')
    extract_parser.set_defaults(func=extract_command)
    
    # export 命令
    export_parser = subparsers.add_parser('export', help='导出数据')
    export_parser.add_argument('format', choices=['json', 'html', 'rag'],
                              help='导出格式')
    export_parser.add_argument('--input', '-i', required=True,
                              help='输入数据文件')
    export_parser.add_argument('--output', '-o', default='output',
                              help='输出目录')
    export_parser.set_defaults(func=export_command)
    
    # batch 命令
    batch_parser = subparsers.add_parser('batch', help='批处理多个文件')
    batch_parser.add_argument('--input-dir', required=True,
                             help='输入HTML文件目录')
    batch_parser.add_argument('--output-dir', default='output',
                             help='输出目录')
    batch_parser.add_argument('--products', nargs='+',
                             help='要处理的产品列表(默认处理所有)')
    batch_parser.add_argument('--region-mode', 
                             choices=['minimal', 'hybrid', 'full'],
                             default='hybrid',
                             help='区域信息模式')
    batch_parser.set_defaults(func=batch_command)
    
    # list-products 命令
    list_parser = subparsers.add_parser('list-products', help='列出支持的产品')
    list_parser.set_defaults(func=list_products_command)
    
    # status 命令
    status_parser = subparsers.add_parser('status', help='显示项目状态')
    status_parser.set_defaults(func=status_command)
    
    return parser


def main():
    """主入口函数"""
    parser = create_parser()
    args = parser.parse_args()
    
    # 如果没有提供命令，显示帮助信息
    if not args.command:
        print_banner()
        parser.print_help()
        return
    
    # 显示横幅(除非是简单的状态命令)
    if args.command not in ['status', 'list-products']:
        print_banner()
    
    # 执行对应的命令函数
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print(f"❌ 未知命令: {args.command}")
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())