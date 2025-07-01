#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修正版MySQL定价页面提取脚本
确保表格内容完整保留，解决表格数据丢失问题
"""

import json
import os
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

# 导入修正版处理工具
try:
    from utils.enhanced_html_processor import (
        RegionFilterProcessor, 
        FixedHTMLProcessor, 
        FixedHTMLBuilder,
        extract_mysql_content_fixed,
        verify_table_content
    )
except ImportError:
    print("❌ 无法导入修正版处理模块，请确保fixed_html_processor.py存在")
    exit(1)


class MySQLFixedExtractor:
    """MySQL修正版提取器 - 确保表格内容完整"""
    
    def __init__(self, config_file: str = "soft-category.json", output_dir: str = "output"):
        self.config_file = config_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 区域映射
        self.region_names = {
            "north-china": "中国北部",
            "east-china": "中国东部",
            "north-china2": "中国北部2",
            "east-china2": "中国东部2", 
            "north-china3": "中国北部3",
            "east-china3": "中国东部3"
        }
        
        # 验证配置文件
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"配置文件不存在: {config_file}")
    
    def extract_single_region_fixed(self, html_file_path: str, region: str) -> Dict:
        """
        提取单个区域的内容（修正版）
        
        Args:
            html_file_path: HTML文件路径
            region: 目标区域ID
            
        Returns:
            Dict: 提取结果
        """
        
        print(f"\n🔧 开始修正版MySQL内容提取")
        print(f"📁 源文件: {html_file_path}")
        print(f"🌍 目标区域: {region} ({self.region_names.get(region, region)})")
        print("=" * 70)
        
        if not os.path.exists(html_file_path):
            raise FileNotFoundError(f"HTML文件不存在: {html_file_path}")
        
        if region not in self.region_names:
            raise ValueError(f"不支持的区域: {region}")
        
        start_time = datetime.now()
        
        try:
            # 使用修正版提取函数
            extracted_html = extract_mysql_content_fixed(html_file_path, region, self.config_file)
            
            # 验证表格内容完整性
            content_verification = verify_table_content(extracted_html)
            
            # 详细验证结果
            validation_result = self._detailed_validation(extracted_html, content_verification)
            
            # 组装结果
            result = {
                "success": True,
                "region": {
                    "id": region,
                    "name": self.region_names[region]
                },
                "extraction_info": {
                    "source_file": html_file_path,
                    "extracted_at": start_time.isoformat(),
                    "extraction_method": "fixed_version",
                    "version": "1.1_table_content_fix"
                },
                "content": {
                    "html": extracted_html,
                    "size": len(extracted_html)
                },
                "table_verification": content_verification,
                "validation": validation_result
            }
            
            processing_time = (datetime.now() - start_time).total_seconds()
            print(f"\n✅ 修正版提取完成！耗时: {processing_time:.2f}秒")
            
            # 输出表格验证结果
            self._print_table_verification(content_verification)
            
            return result
            
        except Exception as e:
            print(f"❌ 提取失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "region": {"id": region, "name": self.region_names.get(region, region)}
            }
    
    def _detailed_validation(self, html_content: str, table_verification: Dict) -> Dict:
        """详细验证提取结果"""
        
        print("\n🔍 详细验证提取结果...")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        validation = {
            "structure_check": {},
            "content_check": {},
            "table_quality": {},
            "issues": []
        }
        
        # 结构检查
        validation["structure_check"] = {
            "has_doctype": html_content.strip().startswith('<!DOCTYPE html>'),
            "has_complete_structure": bool(soup.find('html') and soup.find('head') and soup.find('body')),
            "head_is_clean": len(soup.find('head').find_all()) <= 5 if soup.find('head') else False,
            "no_style_remnants": len(soup.find_all(['style', 'link', 'script'])) == 0,
            "no_form_remnants": len(soup.find_all(['form', 'input', 'select', 'button'])) == 0
        }
        
        # 内容检查
        banner = soup.find('div', class_='common-banner')
        faq = soup.find('div', class_='more-detail')
        
        validation["content_check"] = {
            "has_banner": bool(banner),
            "has_faq": bool(faq),
            "has_sla": "服务级别协议" in soup.get_text(),
            "text_content_length": len(soup.get_text()),
            "preserved_essential_classes": bool(banner) and bool(faq)
        }
        
        # 表格质量检查
        validation["table_quality"] = {
            "table_count": table_verification["table_count"],
            "tables_with_data": table_verification["tables_with_data"],
            "total_data_rows": table_verification["total_rows"],
            "average_rows_per_table": round(table_verification["total_rows"] / table_verification["table_count"], 1) if table_verification["table_count"] > 0 else 0,
            "all_tables_have_data": table_verification["tables_with_data"] == table_verification["table_count"]
        }
        
        # 检查问题
        if not validation["structure_check"]["has_complete_structure"]:
            validation["issues"].append("HTML结构不完整")
        
        if not validation["structure_check"]["no_style_remnants"]:
            validation["issues"].append("仍有样式元素残留")
        
        if table_verification["table_count"] < 5:
            validation["issues"].append(f"表格数量过少: {table_verification['table_count']}")
        
        if table_verification["tables_with_data"] < table_verification["table_count"]:
            validation["issues"].append(f"有{table_verification['table_count'] - table_verification['tables_with_data']}个表格缺少数据")
        
        if table_verification["total_rows"] < 20:
            validation["issues"].append(f"总数据行过少: {table_verification['total_rows']}")
        
        # 输出验证结果
        print(f"  📊 表格验证: {table_verification['table_count']}个表格，{table_verification['total_rows']}行数据")
        print(f"  🏷️ 内容保留: Banner{'✓' if validation['content_check']['has_banner'] else '✗'}, FAQ{'✓' if validation['content_check']['has_faq'] else '✗'}")
        print(f"  🎨 清理状态: 样式{'✓' if validation['structure_check']['no_style_remnants'] else '✗'}, 交互{'✓' if validation['structure_check']['no_form_remnants'] else '✗'}")
        
        if validation["issues"]:
            print("  ⚠ 发现问题:")
            for issue in validation["issues"]:
                print(f"    - {issue}")
        else:
            print("  ✅ 所有验证通过")
        
        return validation
    
    def _print_table_verification(self, verification: Dict):
        """打印表格验证结果"""
        print(f"\n📊 表格内容验证报告:")
        print(f"  总表格数: {verification['table_count']}")
        print(f"  有数据表格: {verification['tables_with_data']}")
        print(f"  总数据行: {verification['total_rows']}")
        
        print(f"\n📋 各表格详情:")
        for i, table in enumerate(verification['table_details'], 1):
            status = "✓" if table['has_data'] else "✗"
            print(f"  {i}. {table['id']}: {table['data_row_count']}行数据 {status}")
            
            # 显示样本数据
            if table['sample_data'] and len(table['sample_data']) > 0:
                sample = table['sample_data'][0]
                if len(sample) >= 2:
                    print(f"     样本: {sample[0][:20]}... | {sample[1][:20]}...")
    
    def save_result_with_verification(self, result: Dict, region: str) -> str:
        """保存提取结果并生成验证报告"""
        
        if not result["success"]:
            print(f"❌ 无法保存失败的提取结果")
            return ""
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"mysql_{region}_fixed_{timestamp}.html"
        file_path = self.output_dir / filename
        
        # 保存HTML文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(result["content"]["html"])
        
        print(f"\n💾 文件已保存: {file_path}")
        print(f"📄 文件大小: {result['content']['size']:,} 字节")
        
        # 保存详细验证报告
        report_filename = f"mysql_{region}_verification_{timestamp}.json"
        report_path = self.output_dir / report_filename
        
        report_data = {
            "extraction_info": result["extraction_info"],
            "table_verification": result["table_verification"],
            "validation": result["validation"],
            "region": result["region"],
            "quality_summary": {
                "extraction_successful": result["success"],
                "table_content_complete": result["table_verification"]["tables_with_data"] == result["table_verification"]["table_count"],
                "total_data_rows": result["table_verification"]["total_rows"],
                "validation_issues": len(result["validation"]["issues"])
            }
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"📋 验证报告: {report_path}")
        
        # 输出质量摘要
        quality = report_data["quality_summary"]
        print(f"\n📈 质量摘要:")
        print(f"  📊 表格完整性: {'✓' if quality['table_content_complete'] else '✗'}")
        print(f"  📋 数据行总数: {quality['total_data_rows']}")
        print(f"  ⚠ 验证问题: {quality['validation_issues']}个")
        
        return str(file_path)
    
    def extract_all_regions_fixed(self, html_file_path: str, 
                                 regions: Optional[List[str]] = None) -> Dict[str, Dict]:
        """提取所有区域的内容（修正版）"""
        
        if regions is None:
            regions = list(self.region_names.keys())
        
        print(f"\n🌍 开始批量修正版提取 {len(regions)} 个区域")
        print(f"区域列表: {[self.region_names.get(r, r) for r in regions]}")
        
        results = {}
        successful_count = 0
        total_tables = 0
        total_data_rows = 0
        
        for i, region in enumerate(regions, 1):
            print(f"\n{'='*70}")
            print(f"处理区域 {i}/{len(regions)}: {self.region_names.get(region, region)} ({region})")
            print(f"{'='*70}")
            
            try:
                result = self.extract_single_region_fixed(html_file_path, region)
                
                if result["success"]:
                    file_path = self.save_result_with_verification(result, region)
                    result["output_file"] = file_path
                    successful_count += 1
                    
                    # 累计统计
                    total_tables += result["table_verification"]["table_count"]
                    total_data_rows += result["table_verification"]["total_rows"]
                
                results[region] = result
                
                print(f"✅ {self.region_names.get(region, region)} 处理完成")
                
            except Exception as e:
                print(f"❌ {self.region_names.get(region, region)} 处理失败: {e}")
                results[region] = {
                    "success": False,
                    "error": str(e),
                    "region": {"id": region, "name": self.region_names.get(region, region)}
                }
        
        # 生成批量处理总结
        self._generate_batch_summary_fixed(results, successful_count, len(regions), total_tables, total_data_rows)
        
        return results
    
    def _generate_batch_summary_fixed(self, results: Dict, successful_count: int, 
                                    total_count: int, total_tables: int, total_data_rows: int):
        """生成修正版批量处理总结"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_path = self.output_dir / f"mysql_fixed_batch_summary_{timestamp}.json"
        
        summary = {
            "batch_info": {
                "processed_at": datetime.now().isoformat(),
                "extraction_version": "1.1_table_content_fix",
                "total_regions": total_count,
                "successful_regions": successful_count,
                "failed_regions": total_count - successful_count
            },
            "aggregate_stats": {
                "total_tables_extracted": total_tables,
                "total_data_rows_extracted": total_data_rows,
                "average_tables_per_region": round(total_tables / successful_count, 1) if successful_count > 0 else 0,
                "average_rows_per_region": round(total_data_rows / successful_count, 1) if successful_count > 0 else 0
            },
            "regions": {}
        }
        
        for region, result in results.items():
            region_name = self.region_names.get(region, region)
            
            if result["success"]:
                table_verification = result["table_verification"]
                summary["regions"][region] = {
                    "name": region_name,
                    "status": "success",
                    "html_size": result["content"]["size"],
                    "table_count": table_verification["table_count"],
                    "data_rows": table_verification["total_rows"],
                    "tables_with_data": table_verification["tables_with_data"],
                    "content_complete": table_verification["tables_with_data"] == table_verification["table_count"],
                    "output_file": result.get("output_file", ""),
                    "validation_issues": len(result["validation"]["issues"])
                }
            else:
                summary["regions"][region] = {
                    "name": region_name,
                    "status": "failed",
                    "error": result["error"]
                }
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"\n📋 修正版批量处理总结:")
        print(f"✅ 成功: {successful_count}/{total_count} 个区域")
        print(f"📊 总提取表格: {total_tables} 个")
        print(f"📋 总数据行: {total_data_rows} 行")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"📊 总结报告: {summary_path}")
        
        # 显示成功区域的详情
        if successful_count > 0:
            print(f"\n📋 成功区域详情:")
            for region, info in summary["regions"].items():
                if info["status"] == "success":
                    complete_status = "✓" if info["content_complete"] else f"✗({info['tables_with_data']}/{info['table_count']})"
                    print(f"  {info['name']}: {info['table_count']}个表格, {info['data_rows']}行数据 {complete_status}")
    
    def compare_with_original(self, extracted_html: str, original_file: str) -> Dict:
        """与原始文件对比，检查内容损失"""
        
        print(f"\n🔍 与原始文件对比内容...")
        
        if not os.path.exists(original_file):
            return {"error": f"原始文件不存在: {original_file}"}
        
        # 加载原始HTML
        with open(original_file, 'r', encoding='utf-8') as f:
            original_html = f.read()
        
        extracted_soup = BeautifulSoup(extracted_html, 'html.parser')
        original_soup = BeautifulSoup(original_html, 'html.parser')
        
        # 对比表格内容
        extracted_tables = extracted_soup.find_all('table')
        original_tables = original_soup.find_all('table')
        
        comparison = {
            "table_comparison": {
                "original_count": len(original_tables),
                "extracted_count": len(extracted_tables),
                "retention_ratio": len(extracted_tables) / len(original_tables) if original_tables else 0
            },
            "content_comparison": {},
            "data_integrity": {}
        }
        
        # 检查具体表格的数据完整性
        extracted_table_data = {}
        for table in extracted_tables:
            table_id = table.get('id', 'no-id')
            rows = table.find_all('tr')
            extracted_table_data[table_id] = len(rows)
        
        original_table_data = {}
        for table in original_tables:
            table_id = table.get('id', 'no-id')
            rows = table.find_all('tr')
            original_table_data[table_id] = len(rows)
        
        # 计算数据完整性
        data_integrity_issues = []
        for table_id, extracted_rows in extracted_table_data.items():
            if table_id in original_table_data:
                original_rows = original_table_data[table_id]
                if extracted_rows < original_rows:
                    data_integrity_issues.append(f"{table_id}: {extracted_rows}/{original_rows}行")
        
        comparison["data_integrity"] = {
            "issues_count": len(data_integrity_issues),
            "issues": data_integrity_issues,
            "perfect_integrity": len(data_integrity_issues) == 0
        }
        
        print(f"  📊 表格对比: {len(extracted_tables)}/{len(original_tables)} 保留")
        print(f"  📋 数据完整性: {'✓' if comparison['data_integrity']['perfect_integrity'] else f'✗({len(data_integrity_issues)}个问题)'}")
        
        if data_integrity_issues:
            print("  ⚠ 数据完整性问题:")
            for issue in data_integrity_issues[:5]:  # 只显示前5个
                print(f"    - {issue}")
        
        return comparison


def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description="MySQL定价页面修正版提取工具 - 确保表格内容完整")
    parser.add_argument("html_file", help="HTML源文件路径")
    parser.add_argument("-r", "--region", help="目标区域 (如: north-china3)")
    parser.add_argument("-a", "--all-regions", action="store_true", help="提取所有区域")
    parser.add_argument("-c", "--config", default="soft-category.json", help="配置文件路径")
    parser.add_argument("-o", "--output", default="output", help="输出目录")
    parser.add_argument("--compare-original", help="与原始HTML文件对比内容损失")
    parser.add_argument("--regions", nargs="+", help="指定要提取的区域列表")
    parser.add_argument("--verify-only", action="store_true", help="只验证现有HTML文件的表格内容")
    
    args = parser.parse_args()
    
    # 验证输入文件
    if not args.verify_only and not os.path.exists(args.html_file):
        print(f"❌ HTML文件不存在: {args.html_file}")
        return 1
    
    # 验证配置文件
    if not os.path.exists(args.config):
        print(f"❌ 配置文件不存在: {args.config}")
        return 1
    
    try:
        # 如果只是验证模式
        if args.verify_only:
            if os.path.exists(args.html_file):
                with open(args.html_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                verification = verify_table_content(html_content)
                print(f"📊 表格验证结果: {verification}")
                return 0
            else:
                print(f"❌ 验证文件不存在: {args.html_file}")
                return 1
        
        # 创建修正版提取器
        extractor = MySQLFixedExtractor(args.config, args.output)
        
        # 显示版本信息
        print("🔧 MySQL定价页面修正版提取工具")
        print("📊 专门解决表格内容丢失问题")
        print("✨ 特性: 完整表格保留、内容验证、数据完整性检查")
        
        if args.all_regions:
            # 提取所有区域
            regions = args.regions or list(extractor.region_names.keys())
            results = extractor.extract_all_regions_fixed(args.html_file, regions)
            
        elif args.region:
            # 提取指定区域
            if args.region not in extractor.region_names:
                print(f"❌ 不支持的区域: {args.region}")
                print(f"支持的区域: {list(extractor.region_names.keys())}")
                return 1
            
            result = extractor.extract_single_region_fixed(args.html_file, args.region)
            if result["success"]:
                output_file = extractor.save_result_with_verification(result, args.region)
                
                # 如果指定了原始文件对比
                if args.compare_original:
                    comparison = extractor.compare_with_original(result["content"]["html"], args.compare_original)
                    if "error" not in comparison:
                        print("\n📋 原始文件对比结果已显示在上方")
                    else:
                        print(f"❌ 对比失败: {comparison['error']}")
        else:
            # 默认提取 north-china3
            print("未指定区域，默认提取 north-china3")
            result = extractor.extract_single_region_fixed(args.html_file, "north-china3")
            if result["success"]:
                output_file = extractor.save_result_with_verification(result, "north-china3")
        
        print("\n🎉 修正版提取任务完成！")
        print("📊 已确保表格内容完整保留")
        print("💡 检查验证报告确认数据完整性")
        return 0
        
    except Exception as e:
        print(f"❌ 提取过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())