#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础CMS提取器抽象类
提供所有Azure产品页面CMS HTML提取器的通用功能和接口
"""

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from bs4 import BeautifulSoup

from .html_processor import HTMLProcessor
from .content_extractor import ContentExtractor
from .verification_manager import VerificationManager
from .config_manager import ConfigManager


class BaseCMSExtractor(ABC):
    """基础CMS提取器抽象类"""
    
    def __init__(self, config_file: str = "soft-category.json", 
                 output_dir: str = "cms_output",
                 product_name: str = ""):
        """
        初始化基础CMS提取器
        
        Args:
            config_file: 配置文件路径
            output_dir: 输出目录
            product_name: 产品名称
        """
        self.config_file = config_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.product_name = product_name
        
        # 初始化配置管理器
        self.config_manager = ConfigManager(config_file)
        
        # 初始化HTML处理器
        self.html_processor = HTMLProcessor(self.config_manager.region_filter)
        
        # 初始化内容提取器
        self.content_extractor = ContentExtractor()
        
        # 初始化验证管理器
        self.verification_manager = VerificationManager()
        
        # 原始HTML的soup对象
        self.original_soup = None
        
        print(f"✓ {product_name} CMS提取器初始化完成")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"🌍 支持区域: {list(self.config_manager.region_names.keys())}")
    
    @property
    def region_names(self) -> Dict[str, str]:
        """获取区域映射"""
        return self.config_manager.region_names
    
    @property
    @abstractmethod
    def important_section_titles(self) -> set:
        """获取重要的section标题集合（需要子类实现）"""
        pass
    
    @abstractmethod
    def get_product_specific_config(self) -> Dict[str, Any]:
        """获取产品特定配置（需要子类实现）"""
        pass
    
    @abstractmethod
    def extract_product_banner(self, soup: BeautifulSoup, content_soup: BeautifulSoup) -> List:
        """提取产品横幅（需要子类实现）"""
        pass
    
    @abstractmethod
    def get_css_styles(self, region_name: str) -> str:
        """获取产品特定的CSS样式（需要子类实现）"""
        pass
    
    def extract_cms_html_for_region(self, html_file_path: str, region: str) -> Dict[str, Any]:
        """为指定区域提取CMS友好的HTML"""
        
        print(f"\n🔧 开始提取{self.product_name} CMS HTML")
        print(f"📁 源文件: {html_file_path}")
        print(f"🌍 目标区域: {region} ({self.region_names.get(region, region)})")
        print("=" * 70)
        
        if not os.path.exists(html_file_path):
            raise FileNotFoundError(f"HTML文件不存在: {html_file_path}")
        
        if region not in self.region_names:
            raise ValueError(f"不支持的区域: {region}。支持的区域: {list(self.region_names.keys())}")
        
        start_time = datetime.now()
        
        try:
            # 1. 加载和解析HTML
            html_content = self._load_html_file(html_file_path)
            soup = BeautifulSoup(html_content, 'html.parser')
            self.original_soup = BeautifulSoup(html_content, 'html.parser')
            
            # 2. 设置区域过滤器
            self.config_manager.region_filter.set_active_region(region, self.product_name)
            
            # 3. 提取和清洗内容
            cleaned_soup = self._extract_and_clean_content(soup, region)
            
            # 4. 应用区域过滤
            filtered_count, retained_count = self._apply_region_filtering(cleaned_soup, region)
            
            # 5. 进一步清洗以适应CMS
            cms_ready_soup = self._prepare_for_cms(cleaned_soup, region)
            
            # 6. 生成最终HTML
            final_html = self._build_final_html(cms_ready_soup, region)
            
            # 7. 验证结果
            verification = self._verify_extraction_result(final_html)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = {
                "success": True,
                "region": {
                    "id": region,
                    "name": self.region_names[region]
                },
                "html_content": final_html,
                "statistics": {
                    "original_size": len(html_content),
                    "final_size": len(final_html),
                    "compression_ratio": round(len(final_html) / len(html_content), 3),
                    "filtered_tables": filtered_count,
                    "retained_tables": retained_count,
                    "processing_time": processing_time
                },
                "verification": verification,
                "extraction_info": {
                    "source_file": html_file_path,
                    "extracted_at": start_time.isoformat(),
                    "extraction_method": "cms_optimized",
                    "product": self.product_name,
                    "version": "2.0_modular"
                }
            }
            
            print(f"\n✅ {self.product_name} CMS HTML提取完成！")
            print(f"📄 压缩比: {result['statistics']['compression_ratio']*100:.1f}%")
            print(f"📊 保留表格: {retained_count} 个")
            print(f"⏱️ 处理时间: {processing_time:.2f}秒")
            
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
    
    def _load_html_file(self, html_file_path: str) -> str:
        """加载HTML文件"""
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        print(f"✓ HTML文件加载成功，大小: {len(html_content):,} 字符")
        return html_content
    
    def _extract_and_clean_content(self, soup: BeautifulSoup, region: str) -> BeautifulSoup:
        """提取和清洗内容，保留完整的页面内容"""
        
        print(f"🧹 第一步：提取和清洗{self.product_name}完整内容...")
        
        # 使用HTML处理器进行清洗
        cleaned_soup = self.html_processor.clean_html(soup)
        
        # 使用内容提取器提取主要内容
        main_content = self.content_extractor.extract_main_content(
            cleaned_soup, 
            self.important_section_titles,
            self.extract_product_banner
        )
        
        print(f"  ✓ {self.product_name}完整内容提取和清洗完成")
        return main_content
    
    def _apply_region_filtering(self, soup: BeautifulSoup, region: str) -> Tuple[int, int]:
        """应用区域过滤 - 通过设置scroll-table div的display属性"""

        print(f"🔍 第二步：应用区域过滤 (区域: {region})...")

        # 使用HTML处理器的精确过滤方法
        filtered_count, retained_count, retained_table_ids = self.html_processor.filter_tables_precisely(
            soup, region, self.product_name
        )

        print(f"  ✓ 过滤完成: 隐藏 {filtered_count} 个表格，显示 {retained_count} 个表格")

        return filtered_count, retained_count
    
    def _prepare_for_cms(self, soup: BeautifulSoup, region: str) -> BeautifulSoup:
        """为CMS做最后的准备，保持简洁结构"""
        
        print("✨ 第三步：CMS优化（简化结构）...")
        
        # 移除空的容器
        self.html_processor.remove_empty_containers(soup)
        
        # 确保表格有适当的样式类
        product_config = self.get_product_specific_config()
        table_class = product_config.get('table_class', 'pricing-table')
        
        for table in soup.find_all('table'):
            if table_class not in table.get('class', []):
                table['class'] = table_class
        
        # 添加区域信息
        region_p = soup.new_tag('p', **{'class': 'region-info'})
        region_p.string = f"区域: {self.region_names[region]}"
        
        # 将区域信息插入到最前面
        if soup.contents:
            soup.insert(0, region_p)
        else:
            soup.append(region_p)
        
        print("  ✓ CMS优化完成（简洁结构）")
        
        return soup
    
    def _build_final_html(self, soup: BeautifulSoup, region: str) -> str:
        """构建最终的HTML输出"""
        
        print("🏗️ 第四步：构建最终HTML...")
        
        region_name = self.region_names[region]
        css_styles = self.get_css_styles(region_name)
        
        # 构建完整的HTML文档
        html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.product_name} 定价 - {region_name}</title>
    <meta name="description" content="{self.product_name} 在{region_name}的定价信息">
    <style>
{css_styles}
    </style>
</head>
<body>
{str(soup)}
</body>
</html>"""
        
        print("  ✓ HTML文档构建完成")
        
        return html_template
    
    def _verify_extraction_result(self, html_content: str) -> Dict[str, Any]:
        """验证提取结果"""
        return self.verification_manager.verify_extraction(html_content, self.product_name)
    
    def save_cms_html(self, result: Dict[str, Any], region: str, custom_filename: str = "") -> str:
        """保存CMS HTML文件"""
        
        if not result["success"]:
            print(f"❌ 无法保存失败的提取结果")
            return ""
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if custom_filename:
            filename = custom_filename
        else:
            product_safe_name = self.product_name.lower().replace(" ", "_")
            filename = f"{product_safe_name}_{region}_cms_{timestamp}.html"
        
        file_path = self.output_dir / filename
        
        # 保存HTML文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(result["html_content"])
        
        print(f"\n💾 CMS HTML已保存: {file_path}")
        print(f"📄 文件大小: {result['statistics']['final_size']:,} 字节")
        print(f"📊 压缩比: {result['statistics']['compression_ratio']*100:.1f}%")
        
        # 保存统计信息
        stats_path = file_path.with_suffix('.stats.json')
        stats_data = {
            "region": result["region"],
            "statistics": result["statistics"],
            "verification": result["verification"],
            "extraction_info": result["extraction_info"]
        }
        
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f, ensure_ascii=False, indent=2)
        
        print(f"📋 统计信息: {stats_path}")
        
        return str(file_path)
    
    def extract_all_regions_cms(self, html_file_path: str, 
                               regions: Optional[List[str]] = None) -> Dict[str, Dict]:
        """批量提取所有区域的CMS HTML"""
        
        if regions is None:
            regions = list(self.region_names.keys())
        
        print(f"\n🌍 开始批量{self.product_name} CMS HTML提取 {len(regions)} 个区域")
        print(f"区域列表: {[self.region_names.get(r, r) for r in regions]}")
        
        batch_results = {}
        successful_count = 0
        total_size = 0
        
        for i, region in enumerate(regions, 1):
            print(f"\n{'='*70}")
            print(f"处理区域 {i}/{len(regions)}: {self.region_names.get(region, region)} ({region})")
            print(f"{'='*70}")
            
            try:
                result = self.extract_cms_html_for_region(html_file_path, region)
                
                if result["success"]:
                    output_file = self.save_cms_html(result, region)
                    result["output_file"] = output_file
                    successful_count += 1
                    total_size += result["statistics"]["final_size"]
                    
                    print(f"✅ {self.region_names.get(region, region)} CMS HTML提取完成")
                else:
                    print(f"❌ {self.region_names.get(region, region)} 提取失败")
                
                batch_results[region] = result
                
            except Exception as e:
                print(f"❌ {self.region_names.get(region, region)} 处理异常: {e}")
                batch_results[region] = {
                    "success": False,
                    "error": str(e),
                    "region": {"id": region, "name": self.region_names.get(region, region)}
                }
        
        # 生成批量处理总结
        self._generate_batch_cms_summary(batch_results, successful_count, len(regions), total_size)
        
        return batch_results
    
    def _generate_batch_cms_summary(self, results: Dict, successful_count: int, 
                                   total_count: int, total_size: int):
        """生成批量CMS处理总结"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        product_safe_name = self.product_name.lower().replace(" ", "_")
        summary_path = self.output_dir / f"{product_safe_name}_cms_batch_summary_{timestamp}.json"
        
        summary = {
            "batch_info": {
                "processed_at": datetime.now().isoformat(),
                "extraction_version": "2.0_modular",
                "product": self.product_name,
                "total_regions": total_count,
                "successful_regions": successful_count,
                "failed_regions": total_count - successful_count,
                "total_output_size": total_size
            },
            "regions": {}
        }
        
        total_tables = 0
        
        for region, result in results.items():
            region_name = self.region_names.get(region, region)
            
            if result.get("success", False):
                verification = result["verification"]
                statistics = result["statistics"]
                
                total_tables += verification.get("table_count", 0)
                
                summary["regions"][region] = {
                    "name": region_name,
                    "status": "success",
                    "file_size": statistics["final_size"],
                    "compression_ratio": statistics["compression_ratio"],
                    "table_count": verification.get("table_count", 0),
                    "output_file": result.get("output_file", "")
                }
            else:
                summary["regions"][region] = {
                    "name": region_name,
                    "status": "failed",
                    "error": result.get("error", "未知错误")
                }
        
        summary["aggregate_stats"] = {
            "total_tables": total_tables,
            "average_file_size": round(total_size / successful_count, 0) if successful_count > 0 else 0,
            "average_tables_per_region": round(total_tables / successful_count, 1) if successful_count > 0 else 0
        }
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"\n📋 {self.product_name} CMS批量处理总结:")
        print(f"✅ 成功: {successful_count}/{total_count} 个区域")
        print(f"📊 总定价表: {total_tables} 个")
        print(f"📄 总文件大小: {total_size:,} 字节")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"📊 总结报告: {summary_path}")