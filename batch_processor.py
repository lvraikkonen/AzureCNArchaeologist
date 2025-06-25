#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Azure 定价数据批量处理器
处理 prod-html 目录中的所有 HTML 文件，应用区域过滤规则，生成结构化 JSON 输出

基于区域的表格过滤规则：
- 规则1：区域不在配置文件中 → 包含所有表格
- 规则2：区域在配置文件中但 tableIDs 为空 → 包含所有表格  
- 规则3：区域在配置文件中且 tableIDs 有内容 → 排除指定表格
"""

import os
import json
import glob
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from azure_general_parser import AzurePricingParser


class AzureBatchProcessor:
    """Azure 定价数据批量处理器"""
    
    def __init__(self, 
                 input_dir: str = "prod-html",
                 output_dir: str = "output", 
                 config_file: str = "soft-category.json",
                 include_region_info: bool = True,
                 region_info_mode: str = "full"):
        """
        初始化批量处理器
        
        Args:
            input_dir: HTML文件输入目录
            output_dir: JSON输出目录
            config_file: 区域过滤配置文件路径
            include_region_info: 是否包含区域信息
            region_info_mode: 区域信息模式 ('minimal', 'hybrid', 'full')
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.config_file = config_file
        self.include_region_info = include_region_info
        self.region_info_mode = region_info_mode
        
        # 确保输出目录存在
        self.output_dir.mkdir(exist_ok=True)
        
        # 处理统计
        self.processing_stats = {
            'total_files': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': None,
            'end_time': None,
            'processed_files': [],
            'failed_files': [],
            'skipped_files': []
        }
        
    def get_html_files(self) -> List[Path]:
        """获取所有HTML文件"""
        html_files = []
        
        # 查找所有HTML文件
        for pattern in ['*.html', '*.htm']:
            html_files.extend(self.input_dir.glob(pattern))
            
        # 按文件名排序
        html_files.sort(key=lambda x: x.name)
        
        print(f"✓ 发现 {len(html_files)} 个HTML文件")
        for file in html_files:
            print(f"  - {file.name}")
            
        return html_files
    
    def detect_product_from_filename(self, filename: str) -> Optional[str]:
        """从文件名检测产品类型"""
        filename_lower = filename.lower()
        
        # 产品类型映射
        product_mappings = {
            'mysql': 'mysql',
            'ssis': 'ssis',
            'cosmos-db': 'cosmos-db',
            'anomaly-detector': 'anomaly-detector',
            'search': 'search',
            'machine-learning': 'machine-learning',
            'postgresql': 'postgresql',
            'power-bi': 'power-bi',
            'sql-database': 'sql-database',
            'entra': 'entra'
        }
        
        for key, product_type in product_mappings.items():
            if key in filename_lower:
                return product_type
                
        return None
    
    def process_single_file(self, html_file: Path) -> Dict[str, Any]:
        """处理单个HTML文件"""
        print(f"\n{'='*60}")
        print(f"处理文件: {html_file.name}")
        print(f"{'='*60}")
        
        try:
            # 读取HTML内容
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # 从文件名预检测产品类型
            filename_product = self.detect_product_from_filename(html_file.name)
            if filename_product:
                print(f"✓ 从文件名检测到产品类型: {filename_product}")
            
            # 创建解析器（使用auto检测或文件名检测结果）
            parser = AzurePricingParser(
                html_content=html_content,
                product_type=filename_product or "auto",
                config_file_path=self.config_file,
                include_region_info=self.include_region_info,
                region_info_mode=self.region_info_mode
            )
            
            # 执行解析
            results = parser.parse_all()
            
            # 添加文件信息到元数据
            results['extraction_metadata'].update({
                'source_file': html_file.name,
                'file_size_bytes': html_file.stat().st_size,
                'filename_detected_product': filename_product
            })
            
            # 生成输出文件名
            detected_product = results['extraction_metadata']['product_type']
            output_filename = f"{detected_product}_{self.region_info_mode}.json"
            output_path = self.output_dir / output_filename
            
            # 保存结果
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            print(f"✓ 解析成功，结果保存到: {output_filename}")
            
            # 返回处理结果摘要
            summary = {
                'status': 'success',
                'source_file': html_file.name,
                'output_file': output_filename,
                'product_type': detected_product,
                'total_tables': len(results['pricing_tables']),
                'total_regions': len(results['regions']),
                'total_faqs': len(results['faqs']),
                'filtered_tables': results['region_filter_info']['total_filtered'],
                'active_region': results['region_filter_info']['active_region']
            }
            
            return summary
            
        except Exception as e:
            error_msg = f"处理文件 {html_file.name} 时出错: {str(e)}"
            print(f"✗ {error_msg}")
            
            return {
                'status': 'failed',
                'source_file': html_file.name,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    def process_all_files(self) -> Dict[str, Any]:
        """处理所有HTML文件"""
        print("🚀 开始批量处理Azure定价HTML文件")
        print(f"输入目录: {self.input_dir}")
        print(f"输出目录: {self.output_dir}")
        print(f"配置文件: {self.config_file}")
        print(f"区域信息模式: {self.region_info_mode}")
        
        self.processing_stats['start_time'] = datetime.now()
        
        # 获取所有HTML文件
        html_files = self.get_html_files()
        self.processing_stats['total_files'] = len(html_files)
        
        if not html_files:
            print("⚠ 未找到HTML文件")
            return self.processing_stats
        
        # 处理每个文件
        for html_file in html_files:
            result = self.process_single_file(html_file)
            
            if result['status'] == 'success':
                self.processing_stats['successful'] += 1
                self.processing_stats['processed_files'].append(result)
            elif result['status'] == 'failed':
                self.processing_stats['failed'] += 1
                self.processing_stats['failed_files'].append(result)
            else:
                self.processing_stats['skipped'] += 1
                self.processing_stats['skipped_files'].append(result)
        
        self.processing_stats['end_time'] = datetime.now()
        
        # 生成处理报告
        self.generate_processing_report()
        
        return self.processing_stats
    
    def generate_processing_report(self):
        """生成处理报告"""
        stats = self.processing_stats
        duration = stats['end_time'] - stats['start_time']
        
        print(f"\n{'='*80}")
        print("📊 批量处理完成报告")
        print(f"{'='*80}")
        print(f"处理时间: {duration}")
        print(f"总文件数: {stats['total_files']}")
        print(f"成功处理: {stats['successful']}")
        print(f"处理失败: {stats['failed']}")
        print(f"跳过文件: {stats['skipped']}")
        
        if stats['successful'] > 0:
            print(f"\n✅ 成功处理的文件:")
            for result in stats['processed_files']:
                print(f"  📄 {result['source_file']} → {result['output_file']}")
                print(f"     产品类型: {result['product_type']}")
                print(f"     表格数: {result['total_tables']} (过滤: {result['filtered_tables']})")
                print(f"     区域数: {result['total_regions']}")
                print(f"     FAQ数: {result['total_faqs']}")
                print(f"     当前区域: {result['active_region']}")
        
        if stats['failed'] > 0:
            print(f"\n❌ 处理失败的文件:")
            for result in stats['failed_files']:
                print(f"  📄 {result['source_file']}: {result['error']}")
        
        # 保存详细报告
        report_file = self.output_dir / f"processing_report_{self.region_info_mode}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            # 转换datetime为字符串
            stats_copy = stats.copy()
            stats_copy['start_time'] = stats['start_time'].isoformat()
            stats_copy['end_time'] = stats['end_time'].isoformat()
            stats_copy['duration_seconds'] = duration.total_seconds()
            
            json.dump(stats_copy, f, ensure_ascii=False, indent=2)
        
        print(f"\n📋 详细报告已保存到: {report_file}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Azure定价数据批量处理器')
    parser.add_argument('--input-dir', default='prod-html', help='HTML文件输入目录')
    parser.add_argument('--output-dir', default='output', help='JSON输出目录')
    parser.add_argument('--config-file', default='soft-category.json', help='区域过滤配置文件')
    parser.add_argument('--region-mode', choices=['minimal', 'hybrid', 'full'], 
                       default='full', help='区域信息模式')
    parser.add_argument('--no-region-info', action='store_true', help='不包含区域信息')
    
    args = parser.parse_args()
    
    # 创建批量处理器
    processor = AzureBatchProcessor(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        config_file=args.config_file,
        include_region_info=not args.no_region_info,
        region_info_mode=args.region_mode
    )
    
    # 执行批量处理
    stats = processor.process_all_files()
    
    # 返回退出码
    if stats['failed'] > 0:
        exit(1)
    else:
        exit(0)


if __name__ == "__main__":
    main()
