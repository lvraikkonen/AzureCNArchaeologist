#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON导出器
负责将提取的数据导出为JSON格式
从enhanced_cms_extractor.py中分离出来的JSON导出功能
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class JSONExporter:
    """JSON数据导出器"""
    
    def __init__(self, output_dir: str = "output"):
        """
        初始化JSON导出器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def export_enhanced_cms_data(self, data: Dict[str, Any], product_name: str) -> str:
        """
        导出增强CMS数据为JSON格式
        
        Args:
            data: 要导出的数据
            product_name: 产品名称
            
        Returns:
            str: 导出文件路径
        """
        # 直接使用指定的输出目录，不创建额外的产品子目录
        # 生成时间戳文件名，包含产品名称
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{product_name}_enhanced_cms_content_{timestamp}.json"
        filepath = self.output_dir / filename
        
        # 转换为CMS兼容格式
        cms_data = self._convert_to_cms_format(data, product_name)
        
        # 写入JSON文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cms_data, f, ensure_ascii=False, indent=2)
        
        return str(filepath)
    
    def _convert_to_cms_format(self, data: Dict[str, Any], product_name: str) -> Dict[str, Any]:
        """
        将提取的数据转换为CMS兼容的格式（对齐重构前的字段结构）
        
        Args:
            data: 原始提取数据
            product_name: 产品名称
            
        Returns:
            Dict[str, Any]: CMS格式的数据
        """
        # 直接使用重构前的字段结构，不再进行额外转换
        # 这确保了与重构前完全一致的字段名称和结构
        
        # 优先使用已提取的字段，如果没有则使用默认值
        title = data.get("Title", "")
        meta_description = data.get("MetaDescription", "")
        meta_keywords = data.get("MetaKeywords", "")
        ms_service_name = data.get("MSServiceName", product_name)
        slug = data.get("Slug", product_name)
        language = data.get("Language", "zh-CN")
        navigation_title = data.get("NavigationTitle", title)
        
        # 保持与重构前完全一致的字段结构
        cms_data = {
            "Title": title,
            "MetaDescription": meta_description,
            "MetaKeywords": meta_keywords,
            "MSServiceName": ms_service_name,
            "Slug": slug,
            "DescriptionContent": data.get("DescriptionContent", ""),
            "Language": language,
            "NavigationTitle": navigation_title,
            "BannerContent": data.get("BannerContent", ""),
            "QaContent": data.get("QaContent", ""),  # 使用QaContent字段
            "HasRegion": data.get("HasRegion", False),
            "NoRegionContent": data.get("NoRegionContent", ""),
            # 直接使用具体的区域字段
            "NorthChinaContent": data.get("NorthChinaContent", ""),
            "NorthChina2Content": data.get("NorthChina2Content", ""),
            "NorthChina3Content": data.get("NorthChina3Content", ""),
            "EastChinaContent": data.get("EastChinaContent", ""),
            "EastChina2Content": data.get("EastChina2Content", ""),
            "EastChina3Content": data.get("EastChina3Content", ""),
            "extraction_metadata": {
                "extracted_at": data.get("extraction_timestamp", datetime.now().isoformat()),
                "source_file": data.get("source_file", ""),
                "extractor_version": "enhanced_cms_v2.0",
                "field_structure": "pre_refactor_compatible"
            }
        }
        
        return cms_data
    
    def export_pricing_data(self, data: Dict[str, Any], product_name: str, 
                           region: str = None) -> str:
        """
        导出价格数据为JSON格式
        
        Args:
            data: 价格数据
            product_name: 产品名称
            region: 区域名称(可选)
            
        Returns:
            str: 导出文件路径
        """
        # 生成文件名
        filename_parts = [product_name, "pricing"]
        if region:
            filename_parts.append(region)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = "_".join(filename_parts) + f"_{timestamp}.json"
        filepath = self.output_dir / filename
        
        # 添加导出元数据
        export_data = {
            **data,
            "export_metadata": {
                "export_time": datetime.now().isoformat(),
                "product_name": product_name,
                "region": region,
                "data_type": "pricing",
                "exporter": "JSONExporter",
                "version": "1.0"
            }
        }
        
        # 写入JSON文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return str(filepath)
    
    def export_batch_results(self, results: List[Dict[str, Any]], 
                           batch_name: str = "batch") -> str:
        """
        导出批处理结果
        
        Args:
            results: 批处理结果列表
            batch_name: 批处理名称
            
        Returns:
            str: 导出文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{batch_name}_results_{timestamp}.json"
        filepath = self.output_dir / filename
        
        # 准备导出数据
        export_data = {
            "batch_name": batch_name,
            "total_results": len(results),
            "results": results,
            "export_metadata": {
                "export_time": datetime.now().isoformat(),
                "data_type": "batch_results",
                "exporter": "JSONExporter",
                "version": "1.0"
            }
        }
        
        # 写入JSON文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return str(filepath)