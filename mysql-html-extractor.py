#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL定价页面内容提取脚本
支持多区域、配置化、模块化处理、tab容器展开、内容清理
"""

import json
import os
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

# 导入自定义工具模块
try:
    from utils.html_processor import (
        RegionFilterProcessor, 
        HTMLProcessor, 
        HTMLBuilder,
        validate_html_structure
    )
except ImportError:
    print("❌ 无法导入utils模块，请确保utils/html_processor.py存在")
    print("提示: 将改进的HTML处理工具保存为 utils/html_processor.py")
    exit(1)


class MySQLHTMLExtractor:
    """MySQL HTML提取器 v2.0"""
    
    def __init__(self, config_file: str = "soft-category.json", output_dir: str = "output"):
        """
        初始化提取器
        
        Args:
            config_file: 区域配置文件路径
            output_dir: 输出目录
        """
        self.config_file = config_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 初始化处理器
        self.region_filter = RegionFilterProcessor(config_file)
        self.html_processor = HTMLProcessor(self.region_filter)
        
        # 支持的区域映射
        self.region_names = {
            "north-china": "中国北部",
            "east-china": "中国东部",
            "north-china2": "中国北部2",
            "east-china2": "中国东部2", 
            "north-china3": "中国北部3",
            "east-china3": "中国东部3"
        }
        
        # 产品信息
        self.product_info = {
            "name": "Azure Database for MySQL",
            "name_en": "Azure Database for MySQL",
            "description": "面向应用开发人员的托管 MySQL 数据库服务"
        }
    
    def load_html_file(self, html_file_path: str) -> BeautifulSoup:
        """
        加载HTML文件
        
        Args:
            html_file_path: HTML文件路径
            
        Returns:
            BeautifulSoup: 解析后的HTML对象
        """
        if not os.path.exists(html_file_path):
            raise FileNotFoundError(f"HTML文件不存在: {html_file_path}")
        
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            print(f"✓ 成功加载HTML文件: {html_file_path}")
            print(f"  文件大小: {len(html_content):,} 字符")
            
            # 显示原始HTML结构信息
            self._print_html_structure_info(soup, "原始HTML结构")
            
            return soup
            
        except Exception as e:
            raise Exception(f"加载HTML文件失败: {e}")
    
    def _print_html_structure_info(self, soup: BeautifulSoup, title: str):
        """打印HTML结构信息"""
        print(f"\n📋 {title}:")
        print(f"  总元素数: {len(soup.find_all()):,}")
        print(f"  表格数量: {len(soup.find_all('table'))}")
        print(f"  tab-content: {len(soup.find_all('div', class_='tab-content'))}")
        print(f"  tab-panel: {len(soup.find_all('div', class_='tab-panel'))}")
        print(f"  标题数量: {len(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']))}")
        print(f"  段落数量: {len(soup.find_all('p'))}")
    
    def extract_for_region(self, html_file_path: str, region: str, 
                          validate: bool = True, 
                          keep_structure: bool = False) -> Dict:
        """
        为指定区域提取HTML内容
        
        Args:
            html_file_path: HTML文件路径
            region: 目标区域ID
            validate: 是否验证HTML结构
            keep_structure: 是否保留原始结构（调试用）
            
        Returns:
            Dict: 提取结果
        """
        print(f"\n🚀 开始提取 {self.region_names.get(region, region)} 的MySQL定价内容")
        print("=" * 60)
        
        # 1. 加载HTML
        soup = self.load_html_file(html_file_path)
        original_soup = BeautifulSoup(str(soup), 'html.parser')  # 保存原始副本用于统计
        
        # 2. 移除不需要的元素（包括tab展开）
        print("\n📝 第一步：清理不需要的HTML元素和展开tab结构")
        removed_count = self.html_processor.remove_unwanted_elements(soup)
        print(f"✓ 处理了 {removed_count} 个元素/容器")
        
        # 显示展开后的结构
        self._print_html_structure_info(soup, "tab展开后的HTML结构")
        
        # 3. 按区域过滤表格
        print(f"\n📊 第二步：按区域 '{region}' 过滤表格")
        total_original_tables = len(original_soup.find_all('table'))
        filtered_count, retained_count, retained_table_ids = self.html_processor.filter_tables_by_region(
            soup, region, self.product_info["name"]
        )
        
        # 4. 清理HTML属性
        print("\n🧹 第三步：清理HTML属性")
        cleaned_attrs = self.html_processor.clean_attributes(soup)
        print(f"✓ 清理了 {cleaned_attrs} 个不需要的属性")
        
        # 5. 验证HTML结构（可选）
        validation_issues = []
        if validate:
            print("\n🔍 第四步：验证HTML结构")
            validation_issues = validate_html_structure(soup)
            if validation_issues:
                print("⚠ 发现以下问题:")
                for issue in validation_issues:
                    print(f"  - {issue}")
            else:
                print("✓ HTML结构验证通过")
        
        # 6. 生成统计信息
        print("\n📈 第五步：生成统计信息")
        statistics = self.html_processor.generate_statistics(
            soup, retained_table_ids, filtered_count, total_original_tables
        )
        
        # 7. 构建最终HTML
        print("\n🏗️ 第六步：构建最终HTML")
        region_name = self.region_names.get(region, region)
        title = f"{self.product_info['name']}定价"
        
        # 获取body内容
        body_content = str(soup.body) if soup.body else str(soup)
        cleaned_html = HTMLBuilder.build_clean_html(body_content, title, region_name)
        
        # 显示最终结构
        final_soup = BeautifulSoup(cleaned_html, 'html.parser')
        self._print_html_structure_info(final_soup, "最终HTML结构")
        
        # 8. 组装结果
        result = {
            "success": True,
            "region": {
                "id": region,
                "name": region_name
            },
            "product": self.product_info,
            "processing_info": {
                "original_file": html_file_path,
                "processed_at": datetime.now().isoformat(),
                "removed_elements": removed_count,
                "cleaned_attributes": cleaned_attrs,
                "validation_issues": validation_issues,
                "tab_containers_flattened": True
            },
            "content": {
                "html": cleaned_html,
                "length": len(cleaned_html)
            },
            "statistics": statistics,
            "extracted_sections": self.html_processor.extract_content_sections(soup)
        }
        
        print(f"\n✅ 提取完成！")
        print(f"📄 最终HTML大小: {len(cleaned_html):,} 字符")
        print(f"📋 保留表格: {retained_count} 个")
        print(f"🗑️ 过滤表格: {filtered_count} 个")
        print(f"📂 Tab容器已展开，内容已平铺")
        
        return result
    
    def save_result(self, result: Dict, region: str, save_sections: bool = False) -> Tuple[str, str]:
        """
        保存提取结果
        
        Args:
            result: 提取结果
            region: 区域ID
            save_sections: 是否保存独立的内容区块文件
            
        Returns:
            Tuple[str, str]: (HTML文件路径, 报告文件路径)
        """
        region_name = self.region_names.get(region, region)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存HTML文件
        html_filename = f"mysql_{region}_extracted_v2_{timestamp}.html"
        html_path = self.output_dir / html_filename
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(result["content"]["html"])
        
        # 保存独立的内容区块（可选）
        if save_sections and "extracted_sections" in result:
            sections_dir = self.output_dir / f"mysql_{region}_sections_{timestamp}"
            sections_dir.mkdir(exist_ok=True)
            
            for section_name, section_soup in result["extracted_sections"].items():
                if section_soup:
                    section_file = sections_dir / f"{section_name}.html"
                    with open(section_file, 'w', encoding='utf-8') as f:
                        f.write(str(section_soup))
            
            print(f"📁 内容区块已保存到: {sections_dir}")
        
        # 保存统计报告
        report_filename = f"mysql_{region}_report_v2_{timestamp}.json"
        report_path = self.output_dir / report_filename
        
        # 准备报告数据（移除HTML内容以减小文件大小）
        report_data = result.copy()
        del report_data["content"]["html"]  # 移除HTML内容
        # 转换BeautifulSoup对象为字符串
        if "extracted_sections" in report_data:
            report_data["extracted_sections"] = {
                k: str(v) if v else None 
                for k, v in report_data["extracted_sections"].items()
            }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 文件保存完成:")
        print(f"📄 HTML文件: {html_path}")
        print(f"📊 统计报告: {report_path}")
        
        return str(html_path), str(report_path)
    
    def extract_all_regions(self, html_file_path: str, regions: Optional[List[str]] = None, 
                           save_sections: bool = False) -> Dict[str, Dict]:
        """
        提取所有区域的内容
        
        Args:
            html_file_path: HTML文件路径
            regions: 要提取的区域列表，None表示提取所有支持的区域
            save_sections: 是否保存独立的内容区块文件
            
        Returns:
            Dict[str, Dict]: 每个区域的提取结果
        """
        if regions is None:
            # 获取配置文件中支持的区域
            available_regions = self.region_filter.get_available_regions(self.product_info["name"])
            regions = [r for r in available_regions if r in self.region_names]
        
        print(f"\n🌍 开始批量提取 {len(regions)} 个区域的内容")
        print(f"区域列表: {[self.region_names.get(r, r) for r in regions]}")
        
        results = {}
        
        for i, region in enumerate(regions, 1):
            print(f"\n{'='*60}")
            print(f"处理区域 {i}/{len(regions)}: {self.region_names.get(region, region)} ({region})")
            print(f"{'='*60}")
            
            try:
                result = self.extract_for_region(html_file_path, region)
                html_path, report_path = self.save_result(result, region, save_sections)
                
                results[region] = {
                    "result": result,
                    "files": {
                        "html": html_path,
                        "report": report_path
                    }
                }
                
                print(f"✅ {self.region_names.get(region, region)} 处理完成")
                
            except Exception as e:
                print(f"❌ {self.region_names.get(region, region)} 处理失败: {e}")
                import traceback
                print(f"错误详情: {traceback.format_exc()}")
                results[region] = {
                    "error": str(e),
                    "files": {}
                }
        
        # 生成总结报告
        self._generate_summary_report(results)
        
        return results
    
    def _generate_summary_report(self, results: Dict[str, Dict]):
        """生成总结报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_path = self.output_dir / f"mysql_extraction_summary_v2_{timestamp}.json"
        
        summary = {
            "extraction_info": {
                "version": "2.0",
                "extraction_time": datetime.now().isoformat(),
                "features": [
                    "tab容器展开",
                    "智能内容清理", 
                    "区域表格过滤",
                    "HTML结构验证"
                ]
            },
            "statistics": {
                "total_regions": len(results),
                "successful_regions": len([r for r in results.values() if "result" in r]),
                "failed_regions": len([r for r in results.values() if "error" in r])
            },
            "regions": {}
        }
        
        for region, data in results.items():
            region_name = self.region_names.get(region, region)
            
            if "result" in data:
                stats = data["result"]["statistics"]
                summary["regions"][region] = {
                    "name": region_name,
                    "status": "success",
                    "tables_retained": stats["表格信息"]["保留表格数"],
                    "tables_filtered": stats["表格信息"]["过滤表格数"],
                    "html_size": data["result"]["content"]["length"],
                    "content_blocks": stats["内容区块"],
                    "files": data["files"]
                }
            else:
                summary["regions"][region] = {
                    "name": region_name,
                    "status": "failed",
                    "error": data["error"]
                }
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"\n📋 总结报告已保存: {summary_path}")
        
        # 打印总结
        print(f"\n🎯 批量提取总结:")
        print(f"✅ 成功: {summary['statistics']['successful_regions']} 个区域")
        print(f"❌ 失败: {summary['statistics']['failed_regions']} 个区域")
        print(f"📁 输出目录: {self.output_dir}")
        
        # 打印成功区域的详细信息
        if summary['statistics']['successful_regions'] > 0:
            print(f"\n📊 成功区域详情:")
            for region, info in summary["regions"].items():
                if info["status"] == "success":
                    print(f"  {info['name']}: {info['tables_retained']}个表格, {info['html_size']:,}字符")
    
    def compare_regions(self, html_file_path: str) -> Dict:
        """
        对比所有区域的表格差异
        
        Args:
            html_file_path: HTML文件路径
            
        Returns:
            Dict: 区域对比结果
        """
        print(f"\n🔍 开始区域对比分析...")
        
        available_regions = self.region_filter.get_available_regions(self.product_info["name"])
        comparison = {
            "analysis_time": datetime.now().isoformat(),
            "total_regions": len(available_regions),
            "regions": {}
        }
        
        for region in available_regions:
            if region in self.region_names:
                excluded_tables = self.region_filter.get_excluded_tables_for_region(
                    region, self.product_info["name"]
                )
                
                comparison["regions"][region] = {
                    "name": self.region_names[region],
                    "excluded_tables_count": len(excluded_tables),
                    "excluded_tables": excluded_tables
                }
        
        # 保存对比报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        comparison_path = self.output_dir / f"mysql_regions_comparison_{timestamp}.json"
        
        with open(comparison_path, 'w', encoding='utf-8') as f:
            json.dump(comparison, f, ensure_ascii=False, indent=2)
        
        print(f"📋 区域对比报告已保存: {comparison_path}")
        
        # 打印对比摘要
        print(f"\n📊 区域对比摘要:")
        for region, info in comparison["regions"].items():
            print(f"  {info['name']}: 排除{info['excluded_tables_count']}个表格")
        
        return comparison


def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description="MySQL定价页面HTML提取工具 v2.0")
    parser.add_argument("html_file", help="HTML源文件路径")
    parser.add_argument("-r", "--region", help="目标区域 (如: north-china3)")
    parser.add_argument("-a", "--all-regions", action="store_true", help="提取所有区域")
    parser.add_argument("-c", "--config", default="soft-category.json", help="配置文件路径")
    parser.add_argument("-o", "--output", default="output", help="输出目录")
    parser.add_argument("--no-validate", action="store_true", help="跳过HTML结构验证")
    parser.add_argument("--save-sections", action="store_true", help="保存独立的内容区块文件")
    parser.add_argument("--compare-regions", action="store_true", help="对比区域差异")
    parser.add_argument("--keep-structure", action="store_true", help="保留原始结构（调试用）")
    
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
        # 创建提取器
        extractor = MySQLHTMLExtractor(args.config, args.output)
        
        # 显示版本信息
        print("🚀 MySQL定价页面HTML提取工具 v2.0")
        print("✨ 新特性: tab容器展开、智能内容清理、增强验证")
        
        if args.compare_regions:
            # 区域对比分析
            extractor.compare_regions(args.html_file)
            
        elif args.all_regions:
            # 提取所有区域
            results = extractor.extract_all_regions(args.html_file, save_sections=args.save_sections)
            
        elif args.region:
            # 提取指定区域
            if args.region not in extractor.region_names:
                print(f"❌ 不支持的区域: {args.region}")
                print(f"支持的区域: {list(extractor.region_names.keys())}")
                return 1
            
            result = extractor.extract_for_region(
                args.html_file, 
                args.region, 
                validate=not args.no_validate,
                keep_structure=args.keep_structure
            )
            extractor.save_result(result, args.region, args.save_sections)
            
        else:
            # 默认提取 north-china3
            print("未指定区域，默认提取 north-china3")
            result = extractor.extract_for_region(
                args.html_file, 
                "north-china3", 
                validate=not args.no_validate,
                keep_structure=args.keep_structure
            )
            extractor.save_result(result, "north-china3", args.save_sections)
        
        print("\n🎉 提取任务完成！")
        print("📝 查看生成的HTML文件，确认tab内容已正确展开")
        return 0
        
    except Exception as e:
        print(f"❌ 提取过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())