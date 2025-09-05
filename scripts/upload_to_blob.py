#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Azure Blob Storage上传脚本
独立脚本，用于将output文件夹中的所有JSON文件上传到Azure Blob Storage
"""

import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core import setup_logging, get_logger, settings
from src.utils.storage import BlobStorageManager

# 初始化日志
setup_logging()
logger = get_logger(__name__)


def upload_output_directory(output_dir: str = "output", blob_prefix: str = None, 
                          dry_run: bool = False) -> List[Dict[str, Any]]:
    """
    上传output目录中的所有JSON文件到Azure Blob Storage
    
    Args:
        output_dir: output目录路径
        blob_prefix: Blob名称前缀
        dry_run: 是否为试运行（不实际上传）
        
    Returns:
        List[Dict[str, Any]]: 上传结果列表
    """
    output_path = Path(output_dir)
    
    if not output_path.exists():
        logger.error(f"❌ Output目录不存在: {output_dir}")
        return []
    
    # 查找所有JSON文件
    json_files = list(output_path.rglob("*.json"))
    
    if not json_files:
        logger.warning(f"⚠️ 在{output_dir}目录中没有找到JSON文件")
        return []
    
    logger.info(f"📁 找到 {len(json_files)} 个JSON文件")
    
    # 按产品分类组织文件
    files_by_category = {}
    for json_file in json_files:
        # 获取相对于output目录的路径
        relative_path = json_file.relative_to(output_path)
        category = relative_path.parent.name if relative_path.parent.name != '.' else 'uncategorized'
        
        if category not in files_by_category:
            files_by_category[category] = []
        files_by_category[category].append(json_file)
    
    # 显示文件分布
    logger.info("📊 文件分布:")
    for category, files in files_by_category.items():
        logger.info(f"  {category}: {len(files)} 个文件")
    
    if dry_run:
        logger.info("🔍 试运行模式，不会实际上传文件")
        results = []
        for json_file in json_files:
            relative_path = json_file.relative_to(output_path)
            blob_name = f"{blob_prefix}/{relative_path}" if blob_prefix else str(relative_path).replace('\\', '/')
            results.append({
                'local_path': str(json_file),
                'blob_name': blob_name,
                'blob_url': f"[DRY_RUN] {blob_name}",
                'status': 'dry_run'
            })
        return results
    
    # 检查Azure Storage配置
    if not settings.AZURE_STORAGE_CONNECTION_STRING:
        logger.error("❌ Azure Storage连接字符串未配置")
        logger.error("请在.env文件中设置AZURE_STORAGE_CONNECTION_STRING")
        return []
    
    try:
        # 初始化Blob Storage管理器
        blob_manager = BlobStorageManager()
        logger.info(f"✅ 已连接到Azure Blob Storage容器: {blob_manager.container_name}")
        
        # 上传文件
        results = blob_manager.upload_directory(str(output_path), blob_prefix)
        
        # 统计结果
        successful = len([r for r in results if r.get('blob_url')])
        failed = len(results) - successful
        
        logger.info(f"📤 上传完成: {successful} 成功, {failed} 失败")
        
        if successful > 0:
            logger.info("✅ 成功上传的文件:")
            for result in results:
                if result.get('blob_url'):
                    logger.info(f"  {result['local_path']} -> {result['blob_name']}")
        
        if failed > 0:
            logger.warning("❌ 上传失败的文件:")
            for result in results:
                if result.get('error'):
                    logger.warning(f"  {result['local_path']}: {result['error']}")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ 上传过程中发生错误: {e}")
        return []


def list_blob_files(name_prefix: str = None) -> None:
    """
    列出Blob Storage中的文件
    
    Args:
        name_prefix: 名称前缀过滤
    """
    try:
        blob_manager = BlobStorageManager()
        blobs = blob_manager.list_blobs(name_starts_with=name_prefix)
        
        if not blobs:
            logger.info("📭 容器中没有找到文件")
            return
        
        logger.info(f"📋 找到 {len(blobs)} 个文件:")
        for blob in blobs:
            size_mb = blob['size'] / (1024 * 1024) if blob['size'] else 0
            logger.info(f"  📄 {blob['name']} ({size_mb:.2f} MB, {blob['last_modified']})")
            
            # 显示元数据
            if blob.get('metadata'):
                for key, value in blob['metadata'].items():
                    logger.info(f"    {key}: {value}")
        
    except Exception as e:
        logger.error(f"❌ 列出文件失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Azure Blob Storage上传工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  %(prog)s upload                                    # 上传output目录中的所有JSON文件
  %(prog)s upload --output-dir output --prefix cms  # 指定目录和前缀
  %(prog)s upload --dry-run                          # 试运行，不实际上传
  %(prog)s list                                      # 列出Blob Storage中的文件
  %(prog)s list --prefix cms                         # 列出指定前缀的文件
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # upload命令
    upload_parser = subparsers.add_parser('upload', help='上传JSON文件到Blob Storage')
    upload_parser.add_argument('--output-dir', '-o', default='output',
                              help='Output目录路径 (默认: output)')
    upload_parser.add_argument('--prefix', '-p', 
                              help='Blob名称前缀')
    upload_parser.add_argument('--dry-run', '-d', action='store_true',
                              help='试运行，不实际上传文件')
    
    # list命令
    list_parser = subparsers.add_parser('list', help='列出Blob Storage中的文件')
    list_parser.add_argument('--prefix', '-p',
                            help='名称前缀过滤')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    logger.info(f"🚀 开始执行 {args.command} 命令")
    
    try:
        if args.command == 'upload':
            results = upload_output_directory(
                output_dir=args.output_dir,
                blob_prefix=args.prefix,
                dry_run=args.dry_run
            )
            
            if results and not args.dry_run:
                logger.info("🔗 CMS团队可以通过以下方式访问文件:")
                logger.info("1. 直接访问Blob URL")
                logger.info("2. 使用Azure Storage Explorer")
                logger.info("3. 通过Azure Portal")
                
        elif args.command == 'list':
            list_blob_files(name_prefix=args.prefix)
            
    except KeyboardInterrupt:
        logger.info("⏹️ 用户中断操作")
    except Exception as e:
        logger.error(f"❌ 执行失败: {e}")
        sys.exit(1)
    
    logger.info("✅ 操作完成")


if __name__ == '__main__':
    main()
