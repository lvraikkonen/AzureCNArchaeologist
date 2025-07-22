#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML导出器
负责将提取的数据导出为HTML格式
支持清洗后的HTML内容导出
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup


class HTMLExporter:
    """HTML数据导出器"""
    
    def __init__(self, output_dir: str = "output"):
        """
        初始化HTML导出器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def export_cleaned_html(self, html_content: str, product_name: str, 
                           region: str = None) -> str:
        """
        导出清洗后的HTML内容
        
        Args:
            html_content: 清洗后的HTML内容
            product_name: 产品名称
            region: 区域名称(可选)
            
        Returns:
            str: 导出文件路径
        """
        # 生成文件名
        filename_parts = [product_name, "cleaned"]
        if region:
            filename_parts.append(region)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = "_".join(filename_parts) + f"_{timestamp}.html"
        filepath = self.output_dir / filename
        
        # 添加HTML元数据注释
        metadata_comment = f"""
<!-- 
导出信息:
- 产品名称: {product_name}
- 区域: {region or 'N/A'}
- 导出时间: {datetime.now().isoformat()}
- 导出器: HTMLExporter v1.0
-->
"""
        
        # 组合完整HTML内容
        full_html = metadata_comment + html_content
        
        # 写入HTML文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_html)
        
        return str(filepath)
    
    def export_structured_html(self, data: Dict[str, Any], product_name: str) -> str:
        """
        将结构化数据导出为格式化HTML
        
        Args:
            data: 结构化数据
            product_name: 产品名称
            
        Returns:
            str: 导出文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{product_name}_structured_{timestamp}.html"
        filepath = self.output_dir / filename
        
        # 生成HTML内容
        html_content = self._generate_structured_html(data, product_name)
        
        # 写入HTML文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(filepath)
    
    def _generate_structured_html(self, data: Dict[str, Any], product_name: str) -> str:
        """
        生成结构化HTML内容
        
        Args:
            data: 结构化数据
            product_name: 产品名称
            
        Returns:
            str: HTML内容
        """
        html_parts = [
            '<!DOCTYPE html>',
            '<html lang="zh-CN">',
            '<head>',
            '    <meta charset="UTF-8">',
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            f'    <title>{product_name} - Azure中国定价详情</title>',
            '    <style>',
            '        body { font-family: "Microsoft YaHei", Arial, sans-serif; line-height: 1.6; margin: 20px; }',
            '        .header { background-color: #0078d4; color: white; padding: 20px; border-radius: 5px; }',
            '        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }',
            '        .pricing-table { width: 100%; border-collapse: collapse; margin: 10px 0; }',
            '        .pricing-table th, .pricing-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }',
            '        .pricing-table th { background-color: #f2f2f2; }',
            '        .faq-item { margin: 10px 0; }',
            '        .faq-question { font-weight: bold; color: #0078d4; }',
            '        .metadata { background-color: #f9f9f9; padding: 10px; font-size: 0.9em; color: #666; }',
            '    </style>',
            '</head>',
            '<body>',
            f'    <div class="header">',
            f'        <h1>{product_name} - Azure中国定价详情</h1>',
            f'        <p>导出时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>',
            f'    </div>'
        ]
        
        # 添加产品信息
        if 'product_info' in data:
            html_parts.extend([
                '    <div class="section">',
                '        <h2>产品信息</h2>',
                f'        <p><strong>产品名称:</strong> {data["product_info"].get("name", "N/A")}</p>',
                f'        <p><strong>描述:</strong> {data["product_info"].get("description", "N/A")}</p>',
                '    </div>'
            ])
        
        # 添加价格表
        if 'pricing_tables' in data and data['pricing_tables']:
            html_parts.extend([
                '    <div class="section">',
                '        <h2>定价信息</h2>'
            ])
            
            for i, table in enumerate(data['pricing_tables']):
                html_parts.append(f'        <h3>价格表 {i+1}</h3>')
                html_parts.append('        <table class="pricing-table">')
                
                # 表头
                if table.get('headers'):
                    html_parts.append('            <thead><tr>')
                    for header in table['headers']:
                        html_parts.append(f'                <th>{header}</th>')
                    html_parts.append('            </tr></thead>')
                
                # 表体
                if table.get('rows'):
                    html_parts.append('            <tbody>')
                    for row in table['rows']:
                        html_parts.append('                <tr>')
                        for cell in row:
                            html_parts.append(f'                    <td>{cell}</td>')
                        html_parts.append('                </tr>')
                    html_parts.append('            </tbody>')
                
                html_parts.append('        </table>')
            
            html_parts.append('    </div>')
        
        # 添加FAQ
        if 'faqs' in data and data['faqs']:
            html_parts.extend([
                '    <div class="section">',
                '        <h2>常见问题</h2>'
            ])
            
            for faq in data['faqs']:
                html_parts.extend([
                    '        <div class="faq-item">',
                    f'            <div class="faq-question">{faq.get("question", "")}</div>',
                    f'            <div class="faq-answer">{faq.get("answer", "")}</div>',
                    '        </div>'
                ])
            
            html_parts.append('    </div>')
        
        # 添加元数据
        html_parts.extend([
            '    <div class="metadata">',
            '        <h3>导出元数据</h3>',
            f'        <p>导出工具: HTMLExporter v1.0</p>',
            f'        <p>数据来源: AzureCNArchaeologist</p>',
            '    </div>',
            '</body>',
            '</html>'
        ])
        
        return '\n'.join(html_parts)