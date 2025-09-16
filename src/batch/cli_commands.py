"""
CLI commands integration for batch processing operations.

This module provides command-line interface integration for the batch
processing system, including all necessary commands for production use.
"""

import json
from src.core.logging import get_logger
from src.core.settings import settings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

from .models import BatchProcessStatus
from .record_manager import BatchProcessRecordManager  
from .process_engine import BatchProcessEngine
from .status_tracker import BatchStatusTracker, create_simple_progress_tracker


logger = get_logger(__name__)


def batch_process_command(args):
    """Execute batch processing command."""
    try:
        print("🚀 启动批量处理系统...")
        
        # Initialize components
        record_manager = BatchProcessRecordManager()
        engine = BatchProcessEngine(
            record_manager=record_manager,
            max_workers=args.parallel_jobs,
            max_retries=getattr(args, 'max_retries', 3)
        )
        
        # Setup progress tracking
        if not args.quiet:
            tracker = create_simple_progress_tracker(print_progress=True)
            engine.set_progress_callback(
                lambda msg, current, total: tracker.update_product_status(
                    f"batch_product_{current}", msg
                )
            )
        
        # Execute batch processing based on arguments
        if args.all:
            languages = _get_languages_to_process(args.language)
            print(f"📦 处理所有产品组 (语言: {', '.join(languages)})...")
            
            all_reports = {}
            for language in languages:
                print(f"\n🌐 处理语言版本: {language}")
                reports = engine.process_all_products(
                    output_dir=args.output_dir,
                    force_refresh=args.force_refresh,
                    html_base_dir=args.html_base_dir,
                    language=language
                )
                
                # Merge reports with language prefix
                for group_name, report in reports.items():
                    all_reports[f"{language}-{group_name}"] = report
            
            # Print summary for all groups and languages
            print("\n📊 批量处理完成摘要:")
            print("="*70)
            
            total_products = 0
            total_successful = 0
            
            for group_name, report in all_reports.items():
                print(f"{group_name:30s}: {report.successful_products:3d}/{report.total_products:3d} "
                      f"({report.success_rate:5.1f}%) - {report.duration_seconds:.1f}s")
                total_products += report.total_products
                total_successful += report.successful_products
            
            overall_success_rate = (total_successful / max(total_products, 1)) * 100
            print("-" * 70)
            print(f"{'总计':30s}: {total_successful:3d}/{total_products:3d} "
                  f"({overall_success_rate:5.1f}%)")
            
            reports = all_reports  # For consistent variable naming
            
        elif args.group:
            languages = _get_languages_to_process(args.language)
            print(f"📦 处理产品组: {args.group} (语言: {', '.join(languages)})")
            
            for language in languages:
                print(f"\n🌐 处理语言版本: {language}")
                report = engine.process_product_group(
                    group_name=args.group,
                    output_dir=args.output_dir, 
                    force_refresh=args.force_refresh,
                    html_base_dir=args.html_base_dir,
                    language=language
                )
                
                # Print detailed report for each language
                print(f"\n📊 {language.upper()} 处理报告:")
                print_batch_report(report)
            
        elif args.failed_only:
            print("🔄 重试失败的产品...")
            report = engine.retry_failed_products(
                output_dir=args.output_dir,
                since_hours=getattr(args, 'since_hours', 24)
            )
            
            print_batch_report(report)
            
        else:
            print("❌ 请指定处理范围: --all, --group <name>, 或 --failed-only")
            return 1
        
        print("\n✅ 批量处理命令执行完成")
        return 0
        
    except Exception as e:
        print(f"❌ 批量处理失败: {e}")
        logger.error(f"批量处理命令失败: {e}", exc_info=True)
        return 1


def batch_status_command(args):
    """Show batch processing status and statistics."""
    try:
        print("📊 批量处理状态查询...")
        
        record_manager = BatchProcessRecordManager()
        
        # Determine time range
        if args.since:
            since_time = _parse_time_string(args.since)
        else:
            since_time = datetime.now() - timedelta(hours=24)  # Last 24 hours
        
        # Get processing statistics
        stats = record_manager.get_processing_statistics(since=since_time)
        
        print(f"\n📈 处理统计 (自 {since_time.strftime('%Y-%m-%d %H:%M:%S')})")
        print("="*60)
        
        # Overall statistics
        status_counts = stats.get('status_counts', {})
        total_records = stats.get('total_records', 0)
        success_rate = stats.get('success_rate', 0)
        
        print(f"总记录数:        {total_records}")
        print(f"成功率:          {success_rate:.1f}%")
        print()
        
        # Status breakdown
        print("状态分布:")
        for status, count in status_counts.items():
            percentage = (count / max(total_records, 1)) * 100
            print(f"  {status:12s}: {count:4d} ({percentage:5.1f}%)")
        
        # Product group statistics
        if args.detailed and stats.get('group_statistics'):
            print("\n📦 产品组统计:")
            print("-" * 60)
            
            group_stats = stats['group_statistics']
            for group_name, group_data in group_stats.items():
                total_group = sum(group_data.values())
                successful_group = group_data.get('success', 0)
                group_success_rate = (successful_group / max(total_group, 1)) * 100
                
                print(f"{group_name:20s}: {successful_group:3d}/{total_group:3d} "
                      f"({group_success_rate:5.1f}%)")
        
        # Strategy performance
        if args.detailed and stats.get('strategy_performance'):
            print("\n🎯 策略性能:")
            print("-" * 60)
            
            strategy_stats = stats['strategy_performance']
            for strategy_name, strategy_data in strategy_stats.items():
                total_strategy = sum(data.get('count', 0) for data in strategy_data.values())
                successful_strategy = strategy_data.get('success', {}).get('count', 0)
                avg_time = strategy_data.get('success', {}).get('avg_processing_time_ms', 0)
                strategy_success_rate = (successful_strategy / max(total_strategy, 1)) * 100
                
                print(f"{strategy_name:20s}: {successful_strategy:3d}/{total_strategy:3d} "
                      f"({strategy_success_rate:5.1f}%) - 平均: {avg_time:.0f}ms")
        
        return 0
        
    except Exception as e:
        print(f"❌ 状态查询失败: {e}")
        logger.error(f"批量状态查询失败: {e}", exc_info=True)
        return 1


def batch_retry_command(args):
    """Retry failed batch processing operations."""
    try:
        print("🔄 重试失败的批量处理...")
        
        record_manager = BatchProcessRecordManager()
        engine = BatchProcessEngine(record_manager=record_manager)
        
        # Setup progress tracking if not quiet
        if not args.quiet:
            tracker = create_simple_progress_tracker(print_progress=True)
            engine.set_progress_callback(
                lambda msg, current, total: tracker.update_product_status(
                    f"retry_product_{current}", msg
                )
            )
        
        # Execute retry
        report = engine.retry_failed_products(
            output_dir=args.output_dir,
            since_hours=getattr(args, 'since_hours', 24)
        )
        
        print_batch_report(report)
        
        return 0
        
    except Exception as e:
        print(f"❌ 重试操作失败: {e}")
        logger.error(f"批量重试失败: {e}", exc_info=True)
        return 1


def batch_history_command(args):
    """Show processing history for specific products or groups."""
    try:
        print("📜 批量处理历史查询...")
        
        record_manager = BatchProcessRecordManager()
        
        if args.product:
            # Show history for specific product
            records = []
            latest_record = record_manager.get_latest_record_for_product(args.product)
            if latest_record:
                records = [latest_record]
                
            if not records:
                print(f"🔍 未找到产品 '{args.product}' 的处理记录")
                return 0
                
            print(f"\n📋 产品 '{args.product}' 的处理历史:")
            
        elif args.group:
            # Show history for product group
            records = record_manager.get_records_by_group(
                args.group, 
                limit=args.limit
            )
            
            if not records:
                print(f"🔍 未找到产品组 '{args.group}' 的处理记录")
                return 0
                
            print(f"\n📋 产品组 '{args.group}' 的处理历史:")
            
        else:
            print("❌ 请指定 --product <name> 或 --group <name>")
            return 1
        
        # Print records table
        print("-" * 120)
        print(f"{'产品':15s} {'状态':8s} {'策略':15s} {'时间(ms)':8s} {'处理时间':16s} {'错误信息':30s}")
        print("-" * 120)
        
        for record in records[:args.limit]:
            status_symbol = {
                BatchProcessStatus.SUCCESS: "✅",
                BatchProcessStatus.FAILED: "❌", 
                BatchProcessStatus.PROCESSING: "🔄",
                BatchProcessStatus.PENDING: "⏳",
                BatchProcessStatus.RETRY: "🔄"
            }.get(record.processing_status, "❓")
            
            processing_time = f"{record.processing_time_ms}" if record.processing_time_ms else "-"
            timestamp = record.extraction_timestamp.strftime('%Y-%m-%d %H:%M') if record.extraction_timestamp else "-"
            error_msg = (record.error_message[:27] + "...") if record.error_message and len(record.error_message) > 30 else (record.error_message or "-")
            
            print(f"{record.product_key:15s} {status_symbol:>8s} {record.strategy_used or '-':15s} "
                  f"{processing_time:>8s} {timestamp:16s} {error_msg:30s}")
        
        return 0
        
    except Exception as e:
        print(f"❌ 历史查询失败: {e}")
        logger.error(f"批量历史查询失败: {e}", exc_info=True)
        return 1


def batch_cleanup_command(args):
    """Clean up old batch processing records."""
    try:
        print("🧹 清理旧的批量处理记录...")
        
        record_manager = BatchProcessRecordManager()
        
        # Parse older_than parameter
        if args.older_than:
            days = int(args.older_than.replace(' days', '').replace('days', '').strip())
        else:
            days = 30  # Default 30 days
        
        # Perform cleanup
        if args.dry_run:
            print(f"🔍 试运行: 将清理超过 {days} 天的记录...")
            # Note: We would need to implement a dry-run method in record_manager
            print("   (试运行模式: 不会实际删除记录)")
        else:
            deleted_count = record_manager.cleanup_old_records(older_than_days=days)
            print(f"✅ 已清理 {deleted_count} 条超过 {days} 天的旧记录")
        
        return 0
        
    except Exception as e:
        print(f"❌ 清理操作失败: {e}")
        logger.error(f"批量清理失败: {e}", exc_info=True)
        return 1


def print_batch_report(report):
    """Print a formatted batch processing report."""
    print(f"\n📊 批量处理报告 (批次: {report.batch_id})")
    print("="*60)
    
    print(f"开始时间:        {report.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    if report.end_time:
        print(f"结束时间:        {report.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"总耗时:          {report.duration_seconds:.1f}s")
    
    print(f"处理产品数:      {report.total_products}")
    print(f"成功:            {report.successful_products} ({report.success_rate:.1f}%)")
    print(f"失败:            {report.failed_products}")
    
    if report.average_processing_time_ms:
        print(f"平均处理时间:    {report.average_processing_time_ms:.0f}ms")
    
    # Product groups breakdown
    if report.products_by_group:
        print("\n📦 产品组分布:")
        for group, count in report.products_by_group.items():
            print(f"  {group}: {count} 个产品")
    
    # Strategy performance
    if report.products_by_strategy:
        print("\n🎯 策略使用情况:")
        for strategy, count in report.products_by_strategy.items():
            print(f"  {strategy}: {count} 个产品")
    
    # Show failed products if any
    failed_results = [r for r in report.processing_results if not r.success]
    if failed_results:
        print(f"\n❌ 失败的产品 ({len(failed_results)}):")
        for result in failed_results[:5]:  # Show first 5 failures
            error_msg = result.error_message[:50] + "..." if len(result.error_message) > 50 else result.error_message
            print(f"  - {result.product_key}: {error_msg}")
        
        if len(failed_results) > 5:
            print(f"  ... 还有 {len(failed_results) - 5} 个失败的产品")


def _get_languages_to_process(language_arg: str) -> List[str]:
    """
    Parse language argument and return list of languages to process.
    
    Args:
        language_arg: Language argument ("zh-cn", "en-us", or "both")
        
    Returns:
        List of language codes to process
    """
    if language_arg == "both":
        return ["zh-cn", "en-us"]
    elif language_arg in ["zh-cn", "en-us"]:
        return [language_arg]
    else:
        logger.warning(f"Unknown language '{language_arg}', defaulting to zh-cn")
        return ["zh-cn"]


def _parse_time_string(time_str: str) -> datetime:
    """Parse time strings like '2 hours ago', '1 day ago', etc."""
    import re
    from datetime import datetime, timedelta
    
    # Handle relative time strings
    match = re.match(r'(\d+)\s*(hour|hours|day|days|week|weeks)\s*ago', time_str.lower())
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        
        if unit.startswith('hour'):
            delta = timedelta(hours=amount)
        elif unit.startswith('day'):
            delta = timedelta(days=amount)
        elif unit.startswith('week'):
            delta = timedelta(weeks=amount)
        else:
            raise ValueError(f"Unsupported time unit: {unit}")
        
        return datetime.now() - delta
    
    # Try to parse as ISO format
    try:
        return datetime.fromisoformat(time_str)
    except ValueError:
        pass
    
    # Try to parse as common date format
    try:
        return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        pass
    
    try:
        return datetime.strptime(time_str, '%Y-%m-%d')
    except ValueError:
        pass
    
    raise ValueError(f"Unable to parse time string: {time_str}")


def add_batch_commands(subparsers):
    """
    Add batch processing commands to the CLI argument parser.
    
    Args:
        subparsers: Argparse subparsers object to add commands to
    """
    
    # batch-process command
    batch_parser = subparsers.add_parser(
        'batch-process', 
        help='执行批量处理操作',
        description='批量处理多个产品的flexible JSON内容提取'
    )
    
    # Processing scope options (mutually exclusive)
    scope_group = batch_parser.add_mutually_exclusive_group(required=True)
    scope_group.add_argument('--all', action='store_true',
                           help='处理所有产品组')
    scope_group.add_argument('--group', 
                           help='处理指定的产品组 (如: database, integration, compute)')
    scope_group.add_argument('--failed-only', action='store_true',
                           help='仅重试最近失败的产品')
    
    # Processing options
    batch_parser.add_argument('--output-dir', default=settings.OUTPUT_BASE_DIR,
                            help=f'输出目录 (默认: {settings.OUTPUT_BASE_DIR})')
    batch_parser.add_argument('--html-base-dir', default=settings.HTML_BASE_DIR,
                            help=f'HTML文件基础目录 (默认: {settings.HTML_BASE_DIR})')
    batch_parser.add_argument('--language', choices=['zh-cn', 'en-us', 'both'], 
                            default=settings.DEFAULT_LANGUAGE,
                            help=f'语言版本 (默认: {settings.DEFAULT_LANGUAGE})')
    batch_parser.add_argument('--parallel-jobs', type=int, default=settings.DEFAULT_PARALLEL_JOBS,
                            help=f'并行处理线程数 (默认: {settings.DEFAULT_PARALLEL_JOBS})')
    batch_parser.add_argument('--force-refresh', action='store_true',
                            help='强制重新处理，忽略内容变更检测')
    batch_parser.add_argument('--quiet', action='store_true',
                            help='静默模式，减少输出信息')
    batch_parser.add_argument('--max-retries', type=int, default=settings.DEFAULT_MAX_RETRIES,
                            help=f'最大重试次数 (默认: {settings.DEFAULT_MAX_RETRIES})')
    
    batch_parser.set_defaults(func=batch_process_command)
    
    # batch-status command
    status_parser = subparsers.add_parser(
        'batch-status',
        help='查询批量处理状态和统计信息'
    )
    status_parser.add_argument('--since', 
                             help='查询起始时间 (如: "2 hours ago", "1 day ago", "2023-12-01")')
    status_parser.add_argument('--detailed', action='store_true',
                             help='显示详细的产品组和策略统计')
    status_parser.set_defaults(func=batch_status_command)
    
    # batch-retry command  
    retry_parser = subparsers.add_parser(
        'batch-retry',
        help='重试失败的批量处理操作'
    )
    retry_parser.add_argument('--output-dir', default=settings.OUTPUT_BASE_DIR,
                            help=f'输出目录 (默认: {settings.OUTPUT_BASE_DIR})')
    retry_parser.add_argument('--since-hours', type=int, default=24,
                            help='查找多少小时内的失败记录 (默认: 24)')
    retry_parser.add_argument('--quiet', action='store_true',
                            help='静默模式，减少输出信息')
    retry_parser.set_defaults(func=batch_retry_command)
    
    # batch-history command
    history_parser = subparsers.add_parser(
        'batch-history',
        help='查询批量处理历史记录'
    )
    history_group = history_parser.add_mutually_exclusive_group(required=True)
    history_group.add_argument('--product',
                             help='查询指定产品的处理历史')
    history_group.add_argument('--group',
                             help='查询指定产品组的处理历史')
    history_parser.add_argument('--limit', type=int, default=20,
                               help='限制显示的记录数量 (默认: 20)')
    history_parser.set_defaults(func=batch_history_command)
    
    # batch-cleanup command
    cleanup_parser = subparsers.add_parser(
        'batch-cleanup',
        help='清理旧的批量处理记录'
    )
    cleanup_parser.add_argument('--older-than', default='30 days',
                               help='清理多少天之前的记录 (默认: 30 days)')
    cleanup_parser.add_argument('--dry-run', action='store_true',
                               help='试运行，不实际删除记录')
    cleanup_parser.set_defaults(func=batch_cleanup_command)