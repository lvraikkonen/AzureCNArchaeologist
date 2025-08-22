#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlexibleContent导出器 - 纯IO操作版本
专注于文件格式化和IO操作，不再承担数据构建职责
数据构建由FlexibleBuilder负责，确保单一数据流：Strategy → Builder → Exporter
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

class FlexibleContentExporter:
    """FlexibleContentPage JSON导出器 - 纯IO操作专用"""
    
    def __init__(self, output_dir: str = "output"):
        """
        初始化FlexibleContent导出器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export_flexible_content(self, flexible_data: Dict[str, Any], product_name: str) -> str:
        """
        导出已构建的FlexibleContentPage数据为JSON文件（纯IO操作）
        
        Args:
            flexible_data: 已构建的flexible JSON数据（由FlexibleBuilder提供）
            product_name: 产品名称
            
        Returns:
            str: 导出文件路径
        """
        # 生成时间戳文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{product_name}_flexible_content_{timestamp}.json"
        
        # 确保产品目录存在
        product_dir = self.output_dir
        product_dir.mkdir(parents=True, exist_ok=True)
        
        # 完整文件路径
        filepath = product_dir / filename
        
        # 写入JSON文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(flexible_data, f, ensure_ascii=False, indent=2)
        
        return str(filepath)