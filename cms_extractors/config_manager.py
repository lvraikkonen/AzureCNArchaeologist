#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理器模块
提供配置文件管理和区域过滤功能
"""

import json
from typing import Dict, Set

try:
    from utils.enhanced_html_processor import RegionFilterProcessor
except ImportError:
    class RegionFilterProcessor:
        """备用区域过滤器"""
        def __init__(self, config_file: str):
            self.config_file = config_file
            
        def set_active_region(self, region: str, product: str):
            pass
            
        def should_filter_table(self, table_id: str) -> bool:
            return False


class ConfigManager:
    """配置管理器 - 负责配置文件管理和区域设置"""
    
    def __init__(self, config_file: str = "soft-category.json"):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        
        # 标准区域映射
        self.region_names = {
            "north-china": "中国北部",
            "east-china": "中国东部",
            "north-china2": "中国北部2", 
            "east-china2": "中国东部2",
            "north-china3": "中国北部3",
            "east-china3": "中国东部3"
        }
        
        # 初始化区域过滤器
        self.region_filter = RegionFilterProcessor(config_file)
        
        # 产品特定配置缓存
        self._product_configs = {}
    
    def get_region_names(self) -> Dict[str, str]:
        """获取区域名称映射"""
        return self.region_names.copy()
    
    def get_supported_regions(self) -> list:
        """获取支持的区域列表"""
        return list(self.region_names.keys())
    
    def is_valid_region(self, region: str) -> bool:
        """检查区域是否有效"""
        return region in self.region_names
    
    def get_region_display_name(self, region: str) -> str:
        """获取区域显示名称"""
        return self.region_names.get(region, region)
    
    def get_product_config(self, product_name: str) -> Dict:
        """
        获取产品特定配置
        
        Args:
            product_name: 产品名称
            
        Returns:
            产品配置字典
        """
        
        if product_name not in self._product_configs:
            self._product_configs[product_name] = self._load_product_config(product_name)
        
        return self._product_configs[product_name]
    
    def _load_product_config(self, product_name: str) -> Dict:
        """
        加载产品特定配置
        
        Args:
            product_name: 产品名称
            
        Returns:
            产品配置字典
        """
        
        # 默认配置
        default_config = {
            "table_class": "pricing-table",
            "important_section_titles": set(),
            "css_template": "default",
            "extraction_options": {
                "preserve_links": True,
                "simplify_structure": True,
                "remove_empty_containers": True
            }
        }
        
        # MySQL特定配置
        if "mysql" in product_name.lower():
            mysql_config = default_config.copy()
            mysql_config.update({
                "table_class": "pricing-table",
                "important_section_titles": {
                    "定价详细信息", "定价详情", "pricing details",
                    "常见问题", "faq", "frequently asked questions",
                    "服务层", "service tier", "性能层", "performance tier"
                },
                "css_template": "mysql"
            })
            return mysql_config
        
        # Azure Storage Files特定配置
        elif "storage" in product_name.lower() and "files" in product_name.lower():
            storage_config = default_config.copy()
            storage_config.update({
                "table_class": "storage-files-pricing-table",
                "important_section_titles": {
                    "定价详细信息", "定价详情", "pricing details",
                    "了解存储选项", "存储选项", "storage options",
                    "数据存储价格", "存储价格", "data storage pricing", "storage pricing",
                    "事务和数据传输价格", "事务价格", "transaction pricing", "数据传输价格",
                    "文件同步价格", "同步价格", "file sync pricing",
                    "常见问题", "faq", "frequently asked questions",
                    # 存储冗余类型标题
                    "lrs", "grs", "zrs", "ragrs", "gzrs", "ra-grs",
                    "本地冗余存储", "地理冗余存储", "区域冗余存储", 
                    "读取访问地理冗余存储", "地理区域冗余存储"
                },
                "css_template": "storage_files"
            })
            return storage_config
        
        # 其他产品使用默认配置
        return default_config
    
    def get_css_template(self, product_name: str, region_name: str) -> str:
        """
        获取产品特定的CSS模板
        
        Args:
            product_name: 产品名称
            region_name: 区域名称
            
        Returns:
            CSS样式字符串
        """
        
        config = self.get_product_config(product_name)
        template_type = config.get("css_template", "default")
        
        # 基础样式
        base_styles = """
        /* CMS友好的基础样式 */
        .product-banner {
            margin-bottom: 2rem;
            padding: 1rem;
            background-color: #f8f9fa;
            border-left: 4px solid #0078d4;
        }
        
        .product-title {
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 0.5rem;
            color: #0078d4;
        }
        
        .product-description {
            color: #666;
            line-height: 1.5;
        }
        
        .region-info {
            background-color: #e7f3ff;
            padding: 0.5rem 1rem;
            margin-bottom: 1rem;
            border-radius: 4px;
            font-size: 0.9rem;
            color: #0078d4;
        }
        
        .pricing-content {
            margin-bottom: 2rem;
        }
        
        .table-title {
            font-size: 1.2rem;
            margin: 1.5rem 0 0.5rem 0;
            color: #333;
            border-bottom: 1px solid #ddd;
            padding-bottom: 0.5rem;
        }"""
        
        # MySQL特定样式
        if template_type == "mysql":
            table_class = config.get("table_class", "pricing-table")
            return base_styles + f"""
        
        .{table_class} {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1.5rem;
            background-color: white;
        }}
        
        .{table_class} th,
        .{table_class} td {{
            border: 1px solid #ddd;
            padding: 0.75rem;
            text-align: left;
        }}
        
        .{table_class} th {{
            background-color: #f8f9fa;
            font-weight: bold;
            color: #333;
        }}
        
        .{table_class} tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        
        .faq-section {{
            margin-top: 2rem;
        }}
        
        .faq-title {{
            font-size: 1.3rem;
            margin-bottom: 1rem;
            color: #0078d4;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 0.5rem;
        }}
        
        /* FAQ 项目样式 - 只应用于 .faq-list */
        .faq-list li {{
            margin-bottom: 1rem;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 0;
            list-style: none;
        }}
        
        .faq-question {{
            background-color: #f8f9fa;
            padding: 0.75rem;
            font-weight: bold;
            color: #333;
            border-bottom: 1px solid #e0e0e0;
            font-size: 1.05rem;
        }}
        
        .faq-answer {{
            padding: 0.75rem;
            line-height: 1.5;
            color: #666;
            background-color: #ffffff;
        }}
        
        /* 普通列表样式 */
        ul {{
            margin-bottom: 1rem;
            padding-left: 1.5rem;
        }}
        
        ul li {{
            margin-bottom: 0.5rem;
            line-height: 1.5;
        }}"""
        
        # Storage Files特定样式
        elif template_type == "storage_files":
            table_class = config.get("table_class", "storage-files-pricing-table")
            return base_styles + f"""
        
        .{table_class} {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1.5rem;
            background-color: white;
        }}
        
        .{table_class} th,
        .{table_class} td {{
            border: 1px solid #ddd;
            padding: 0.75rem;
            text-align: left;
        }}
        
        .{table_class} th {{
            background-color: #f8f9fa;
            font-weight: bold;
            color: #333;
        }}
        
        .{table_class} tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        
        /* Section标题样式 */
        h2 {{
            font-size: 1.4rem;
            color: #0078d4;
            margin: 2rem 0 1rem 0;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 0.5rem;
        }}
        
        h3 {{
            font-size: 1.2rem;
            color: #333;
            margin: 1.5rem 0 1rem 0;
            border-left: 4px solid #0078d4;
            padding-left: 0.5rem;
        }}
        
        .storage-tier-section {{
            margin-top: 2rem;
            padding: 1rem;
            background-color: #f0f8ff;
            border-radius: 4px;
        }}
        
        .transaction-section {{
            margin-top: 2rem;
        }}
        
        .bandwidth-section {{
            margin-top: 2rem;
            padding: 1rem;
            background-color: #fff8e7;
            border-radius: 4px;
        }}"""
        
        # 默认样式
        else:
            return base_styles + """
        
        .pricing-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1.5rem;
            background-color: white;
        }
        
        .pricing-table th,
        .pricing-table td {
            border: 1px solid #ddd;
            padding: 0.75rem;
            text-align: left;
        }
        
        .pricing-table th {
            background-color: #f8f9fa;
            font-weight: bold;
            color: #333;
        }
        
        .pricing-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }"""
    
    def load_config_file(self) -> Dict:
        """
        加载配置文件
        
        Returns:
            配置文件内容字典
        """
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠ 配置文件不存在: {self.config_file}")
            return {}
        except json.JSONDecodeError as e:
            print(f"⚠ 配置文件格式错误: {e}")
            return {}
    
    def save_config_file(self, config_data: Dict):
        """
        保存配置文件
        
        Args:
            config_data: 要保存的配置数据
        """
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            print(f"✓ 配置文件已保存: {self.config_file}")
        except Exception as e:
            print(f"❌ 保存配置文件失败: {e}")
    
    def get_extraction_options(self, product_name: str) -> Dict:
        """
        获取提取选项
        
        Args:
            product_name: 产品名称
            
        Returns:
            提取选项字典
        """
        
        config = self.get_product_config(product_name)
        return config.get("extraction_options", {})
    
    def update_product_config(self, product_name: str, updates: Dict):
        """
        更新产品配置
        
        Args:
            product_name: 产品名称
            updates: 更新的配置项
        """
        
        if product_name not in self._product_configs:
            self._product_configs[product_name] = self._load_product_config(product_name)
        
        self._product_configs[product_name].update(updates)
        print(f"✓ 产品配置已更新: {product_name}")