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

# 初始化日志系统
from src.core import setup_logging, get_app_logger, log_user_operation

from src.exporters.json_exporter import JSONExporter
from src.exporters.html_exporter import HTMLExporter
from src.exporters.rag_exporter import RAGExporter
from src.exporters.flexible_content_exporter import FlexibleContentExporter


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
    logger = get_app_logger("cli.extract")

    logger.info(f"开始提取产品数据: {args.product}")
    logger.info(f"HTML文件: {args.html_file}")
    logger.info(f"输出格式: {args.format}")
    logger.info(f"输出目录: {args.output_dir}")

    print(f"📡 开始提取产品数据: {args.product}")
    print(f"   HTML文件: {args.html_file}")
    print(f"   输出格式: {args.format}")
    print(f"   输出目录: {args.output_dir}")

    # 记录用户操作
    log_user_operation(
        user="cli_user",
        action="数据提取",
        details={
            "product": args.product,
            "html_file": args.html_file,
            "format": args.format,
            "output_dir": args.output_dir
        }
    )

    try:
        # 使用产品管理器获取支持的产品列表
        from src.core.product_manager import ProductManager
        product_manager = ProductManager()
        
        # 检查产品是否支持
        supported_products = product_manager.get_supported_products()
        
        if args.product in supported_products:
            from src.extractors.enhanced_cms_extractor import EnhancedCMSExtractor
            
            # 使用增强提取器
            extractor = EnhancedCMSExtractor(args.output_dir, args.config)
            
            # 使用产品管理器获取URL
            url = product_manager.get_product_url(args.product)
            
            print(f"🔗 使用URL: {url}")
            
            data = extractor.extract_cms_content(args.html_file, url)
            
            # 根据格式选择合适的导出器
            if args.format == 'json':
                from src.exporters.flexible_content_exporter import FlexibleContentExporter
                exporter = FlexibleContentExporter(args.output_dir)
                output_path = exporter.export_flexible_content(data, args.product)
            if args.format == 'html':
                from src.exporters.html_exporter import HTMLExporter
                exporter = HTMLExporter(args.output_dir)
                output_path = exporter.export_enhanced_cms_data(data, args.product)
            elif args.format == 'rag':
                from src.exporters.rag_exporter import RAGExporter
                exporter = RAGExporter(args.output_dir)
                output_path = exporter.export_enhanced_cms_data(data, args.product)
            elif args.format == 'flexible':
                from src.exporters.flexible_content_exporter import FlexibleContentExporter
                exporter = FlexibleContentExporter(args.output_dir)
                output_path = exporter.export_flexible_content(data, args.product)
            
            print(f"✅ 数据已导出到: {output_path}")
            logger.info(f"数据已导出到: {output_path}")

            # 记录成功操作
            log_user_operation(
                user="cli_user",
                action="数据提取完成",
                details={
                    "product": args.product,
                    "output_path": str(output_path),
                    "format": args.format
                },
                status="成功"
            )

        else:
            error_msg = f"暂不支持产品: {args.product}"
            print(f"❌ {error_msg}")
            print(f"支持的产品: {', '.join(supported_products)}")
            logger.error(error_msg)

            # 记录失败操作
            log_user_operation(
                user="cli_user",
                action="数据提取",
                details={
                    "product": args.product,
                    "error": error_msg,
                    "supported_products": supported_products
                },
                status="失败"
            )

    except Exception as e:
        error_msg = f"提取过程出错: {str(e)}"
        print(f"❌ {error_msg}")
        logger.error(error_msg, exc_info=True)

        # 记录异常操作
        log_user_operation(
            user="cli_user",
            action="数据提取",
            details={
                "product": args.product,
                "error": str(e)
            },
            status="异常"
        )
        return 1

    print("✅ 数据提取完成")
    logger.info("数据提取完成")


def export_command(args):
    """执行数据导出命令"""
    print(f"📤 开始导出数据: {args.format}")
    print(f"   输入文件: {args.input}")
    print(f"   输出目录: {args.output}")
    
    if args.format == 'json':
        exporter = JSONExporter(args.output)
        print("✅ JSON导出完成")
    if args.format == 'html':
        exporter = HTMLExporter(args.output)
        print("✅ HTML导出完成")
    elif args.format == 'rag':
        exporter = RAGExporter(args.output)
        print("✅ RAG格式导出完成")
    elif args.format == 'flexible':
        exporter = FlexibleContentExporter(args.output)
        print("✅ JsonFlexibleContent格式导出完成")


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
    try:
        from src.core.product_manager import ProductManager
        product_manager = ProductManager()
        
        # 获取支持的产品列表
        products = product_manager.get_supported_products()
        
        # 按分类获取产品
        products_by_category = product_manager.get_products_by_category()
        
        print("📋 支持的产品列表（按分类）:")
        total_count = 0
        
        for category, product_list in products_by_category.items():
            if product_list:
                print(f"\n🔧 {category}:")
                for i, product in enumerate(product_list, 1):
                    display_name = product_manager.get_product_display_name(product)
                    print(f"   {total_count + i:2d}. {product} ({display_name})")
                total_count += len(product_list)
        
        print(f"\n📊 总计: {total_count} 个产品")
        print("\n💡 使用方法:")
        print("   python cli.py extract <product> --html-file <path> --format <format> --output-dir <dir>")
        print("   例如: python cli.py extract mysql --html-file data/prod-html/mysql-index.html --format json --output-dir output")
        
    except Exception as e:
        print(f"❌ 获取产品列表失败: {e}")
        # 备用产品列表
        products = [
            "mysql", "api-management", "storage-files", "postgresql",
            "cosmos-db", "search", "power-bi-embedded", "ssis",
            "anomaly-detector", "microsoft-entra-external-id"
        ]
        
        print("📋 支持的产品列表:")
        for i, product in enumerate(products, 1):
            print(f"   {i:2d}. {product}")
        
        print(f"\n总计: {len(products)} 个产品")


def copy_from_prod_command(args):
    """执行HTML文件自动复制命令"""
    logger = get_app_logger("cli.copy_from_prod")

    logger.info(f"开始HTML文件自动复制: 语言={args.language}, 分组={args.categories}")

    print(f"📁 开始HTML文件自动复制")
    print(f"   语言版本: {args.language}")
    if args.categories:
        print(f"   指定分组: {', '.join(args.categories)}")
    else:
        print(f"   处理所有分组")

    # 记录用户操作
    log_user_operation(
        user="cli_user",
        action="HTML文件自动复制",
        details={
            "language": args.language,
            "categories": args.categories,
            "base_dir": args.base_dir
        }
    )

    try:
        # 导入HTML复制脚本
        from scripts.auto_copy_html import HTMLFileCopier

        # 创建复制器
        copier = HTMLFileCopier(args.base_dir)

        # 根据参数运行
        if args.language == "both":
            results = copier.run_both_languages(args.categories)

            # 输出结果
            print(f"\n✅ 处理完成!")
            print(f"   中文版本: 成功 {results['zh-cn']['total_success']}, 失败 {results['zh-cn']['total_fail']}")
            print(f"   英文版本: 成功 {results['en-us']['total_success']}, 失败 {results['en-us']['total_fail']}")

            total_success = results['zh-cn']['total_success'] + results['en-us']['total_success']
            total_fail = results['zh-cn']['total_fail'] + results['en-us']['total_fail']
            print(f"   总计: 成功 {total_success}, 失败 {total_fail}")

            # 显示失败的分组
            if total_fail > 0:
                print("\n⚠️  失败的分组:")
                for lang, lang_results in results.items():
                    for category, stats in lang_results['categories'].items():
                        if stats['fail'] > 0:
                            print(f"     {lang}/{category}: {stats['fail']} 个失败")

            # 记录成功操作
            log_user_operation(
                user="cli_user",
                action="HTML文件自动复制完成",
                details={
                    "language": args.language,
                    "total_success": total_success,
                    "total_fail": total_fail,
                    "results": results
                },
                status="成功" if total_fail == 0 else "部分成功"
            )

        else:
            result = copier.run(args.language, args.categories)

            # 输出结果
            print(f"\n✅ 处理完成!")
            print(f"   语言: {args.language}")
            print(f"   成功: {result['total_success']} 个文件")
            print(f"   失败: {result['total_fail']} 个文件")

            if result['total_fail'] > 0:
                print("\n⚠️  失败的分组:")
                for category, stats in result['categories'].items():
                    if stats['fail'] > 0:
                        print(f"     {category}: {stats['fail']} 个失败")

            # 记录成功操作
            log_user_operation(
                user="cli_user",
                action="HTML文件自动复制完成",
                details={
                    "language": args.language,
                    "total_success": result['total_success'],
                    "total_fail": result['total_fail'],
                    "categories": result['categories']
                },
                status="成功" if result['total_fail'] == 0 else "部分成功"
            )

        logger.info("HTML文件自动复制完成")

    except Exception as e:
        error_msg = f"HTML文件复制过程出错: {str(e)}"
        print(f"❌ {error_msg}")
        logger.error(error_msg, exc_info=True)

        # 记录异常操作
        log_user_operation(
            user="cli_user",
            action="HTML文件自动复制",
            details={
                "language": args.language,
                "categories": args.categories,
                "error": str(e)
            },
            status="异常"
        )
        return 1


def status_command(args):
    """显示项目状态"""
    print("📊 项目状态:")
    print("   ├── 架构: 模块化重构完成")
    print("   ├── 核心模块: ✅ 已迁移到 src/core/")
    print("   ├── 导出器: ✅ 已创建 src/exporters/")
    print("   ├── 产品提取器: ✅ 已迁移到 src/product_extractors/")
    print("   ├── HTML复制脚本: ✅ 已创建 scripts/auto_copy_html.py")
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
  %(prog)s copy-from-prod --language both
  %(prog)s copy-from-prod --language zh-cn --categories database storage
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
    extract_parser.add_argument('--format', choices=['json', 'html', 'rag', 'flexible'],
                               default='json', help='输出格式')
    extract_parser.add_argument('--output-dir', default='output',
                               help='输出目录')
    extract_parser.add_argument('--region', help='指定区域')
    extract_parser.set_defaults(func=extract_command)
    
    # export 命令
    export_parser = subparsers.add_parser('export', help='导出数据')
    export_parser.add_argument('format', choices=['json', 'html', 'rag', 'flexible'],
                              help='导出格式')
    export_parser.add_argument('--input', '-i', required=True,
                              help='输入数据文件')
    export_parser.add_argument('--output', '-o', default='output',
                              help='输出目录')
    export_parser.set_defaults(func=export_command)
    
    # list-products 命令
    list_parser = subparsers.add_parser('list-products', help='列出支持的产品')
    list_parser.set_defaults(func=list_products_command)
    
    # copy-from-prod 命令
    copy_parser = subparsers.add_parser('copy-from-prod', help='从生产环境复制HTML文件')
    copy_parser.add_argument('--language', '-l', choices=['zh-cn', 'en-us', 'both'],
                            default='both', help='语言版本 (默认: both)')
    copy_parser.add_argument('--categories', '-c', nargs='+',
                            help='要处理的分组列表 (默认: 处理所有分组)')
    copy_parser.add_argument('--base-dir', '-d', default='.',
                            help='项目根目录 (默认: 当前目录)')
    copy_parser.set_defaults(func=copy_from_prod_command)

    # status 命令
    status_parser = subparsers.add_parser('status', help='显示项目状态')
    status_parser.set_defaults(func=status_command)

    return parser


def main():
    """主入口函数"""
    # 初始化日志系统
    try:
        setup_logging()
        logger = get_app_logger("cli.main")
        logger.info("AzureCN Archaeologist CLI 启动")
    except Exception as e:
        print(f"⚠ 日志系统初始化失败: {e}")
        # 继续执行，但没有日志功能
        logger = None

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

    if logger:
        logger.info(f"执行命令: {args.command}")

    # 执行对应的命令函数
    try:
        if hasattr(args, 'func'):
            result = args.func(args)
            if logger:
                logger.info(f"命令 {args.command} 执行完成")
            return result
        else:
            print(f"❌ 未知命令: {args.command}")
            parser.print_help()
            if logger:
                logger.error(f"未知命令: {args.command}")
            return 1
    except Exception as e:
        print(f"❌ 命令执行失败: {e}")
        if logger:
            logger.error(f"命令 {args.command} 执行失败: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())