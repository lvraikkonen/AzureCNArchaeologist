#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
产品配置管理器
支持120+产品的分布式配置管理，懒加载和缓存机制
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# 使用相对导入
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from .logging import get_logger

logger = get_logger(__name__)


class ProductManager:
    """产品配置管理器 - 支持大规模产品和懒加载"""

    def __init__(self, config_dir: str = "data/configs"):
        self.config_dir = Path(config_dir)
        self.products_index = None
        self.categories_config = None
        self.cached_configs = {}        # 配置缓存
        self.cache_timestamps = {}      # 缓存时间戳
        self.cache_ttl_minutes = 30     # 缓存TTL

        logger.info("产品管理器初始化完成")
        logger.info(f"配置目录: {self.config_dir}")

    def load_products_index(self) -> Dict[str, Any]:
        """加载产品主索引，支持120+产品"""
        if not self.products_index:
            index_file = self.config_dir / "products-index.json"
            if not index_file.exists():
                raise FileNotFoundError(f"产品索引文件不存在: {index_file}")

            with open(index_file, 'r', encoding='utf-8') as f:
                self.products_index = json.load(f)

            # 更新缓存配置
            load_strategy = self.products_index.get("load_strategy", {})
            self.cache_ttl_minutes = load_strategy.get("cache_ttl_minutes", 30)

            logger.info(f"加载产品索引: {self.products_index['total_products']} 个产品")

        return self.products_index

    def load_categories_config(self) -> Dict[str, Any]:
        """加载产品分类配置"""
        if not self.categories_config:
            categories_file = self.config_dir / "categories.json"
            if categories_file.exists():
                with open(categories_file, 'r', encoding='utf-8') as f:
                    self.categories_config = json.load(f)

        return self.categories_config or {}

    def get_supported_products(self) -> List[str]:
        """获取支持的产品列表"""
        index = self.load_products_index()
        products = []

        for category_info in index.get("categories", {}).values():
            products.extend(category_info.get("products", []))

        return sorted(products)

    def get_product_config(self, product_key: str) -> Dict[str, Any]:
        """懒加载产品配置"""
        # 检查缓存
        if product_key in self.cached_configs:
            cached_time = self.cache_timestamps.get(product_key)
            if cached_time and datetime.now() - cached_time < timedelta(minutes=self.cache_ttl_minutes):
                return self.cached_configs[product_key]

        # 从索引查找产品位置
        index = self.load_products_index()
        product_path = self._find_product_config_path(product_key, index)

        if product_path:
            try:
                config = self._load_single_product_config(product_path)
                # 缓存配置
                self.cached_configs[product_key] = config
                self.cache_timestamps[product_key] = datetime.now()
                return config
            except FileNotFoundError:
                # 配置文件不存在，抛出 ValueError 而不是 FileNotFoundError
                raise ValueError(f"产品配置文件不存在: {product_key}")

        raise ValueError(f"产品配置不存在: {product_key}")

    def _find_product_config_path(self, product_key: str, index: Dict[str, Any]) -> Optional[str]:
        """查找产品配置文件路径"""
        for category_name, category_info in index.get("categories", {}).items():
            if product_key in category_info.get("products", []):
                config_path = category_info.get("config_path", "")
                return f"{config_path}{product_key}.json"

        return None

    def _load_single_product_config(self, relative_path: str) -> Dict[str, Any]:
        """加载单个产品配置文件"""
        full_path = self.config_dir / relative_path

        if not full_path.exists():
            raise FileNotFoundError(f"产品配置文件不存在: {full_path}")

        with open(full_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 添加元数据
        config["_meta"] = {
            "config_file": str(full_path),
            "loaded_at": datetime.now().isoformat()
        }

        return config

    def detect_product_from_filename(self, filename: str) -> Optional[str]:
        """从文件名检测产品类型"""
        # 提取文件名（不含路径）
        basename = Path(filename).name

        # 遍历所有产品配置查找匹配
        for product_key in self.get_supported_products():
            try:
                config = self.get_product_config(product_key)
                if config.get("filename") == basename:
                    logger.info(f"检测到产品: {basename} -> {product_key}")
                    return product_key
            except (ValueError, FileNotFoundError):
                # 静默跳过配置不存在的产品
                continue

        return None

    def is_large_html_product(self, product_key: str) -> bool:
        """检查是否为大型HTML产品"""
        try:
            config = self.get_product_config(product_key)
            return config.get("html_processing", {}).get("type") == "large_file"
        except ValueError:
            return False

    def get_product_display_name(self, product_key: str) -> str:
        """获取产品显示名称"""
        try:
            config = self.get_product_config(product_key)
            return config.get("display_name", product_key.title())
        except ValueError:
            return product_key.title()

    def get_product_url(self, product_key: str) -> str:
        """获取产品URL"""
        try:
            config = self.get_product_config(product_key)
            return config.get("url", "")
        except ValueError:
            # 默认URL生成逻辑
            return f"https://www.azure.cn/pricing/details/{product_key}/"

    def get_important_section_titles(self, product_key: str) -> List[str]:
        """获取产品的重要section标题"""
        try:
            config = self.get_product_config(product_key)
            return config.get("important_section_titles", [])
        except ValueError:
            # 默认的重要section标题
            return [
                "定价详细信息", "定价详情", "pricing details",
                "常见问题", "faq", "frequently asked questions"
            ]

    def get_extraction_config(self, product_key: str) -> Dict[str, Any]:
        """获取提取配置"""
        try:
            config = self.get_product_config(product_key)
            return config.get("extraction_config", {})
        except ValueError:
            # 默认提取配置
            return {
                "priority_sections": ["pricing-tables", "banner", "description"],
                "enable_region_processing": True
            }

    def clear_cache(self):
        """清理缓存"""
        self.cached_configs.clear()
        self.cache_timestamps.clear()
        logger.info("产品配置缓存已清理")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "cached_products": len(self.cached_configs),
            "cache_hit_rate": len(self.cached_configs) / max(len(self.get_supported_products()), 1),
            "cache_ttl_minutes": self.cache_ttl_minutes,
            "last_cache_time": max(self.cache_timestamps.values()) if self.cache_timestamps else None
        }

    def get_products_by_category(self, category: str = None) -> Dict[str, List[str]]:
        """按分类获取产品列表"""
        index = self.load_products_index()
        categories = index.get("categories", {})
        
        if category:
            # 返回指定分类的产品
            if category in categories:
                return {category: categories[category].get("products", [])}
            else:
                return {}
        else:
            # 返回所有分类的产品
            result = {}
            for cat_name, cat_info in categories.items():
                result[cat_name] = cat_info.get("products", [])
            return result

    def validate_product_config(self, product_key: str) -> Dict[str, Any]:
        """验证产品配置的完整性"""
        try:
            config = self.get_product_config(product_key)
            
            validation_result = {
                "is_valid": True,
                "missing_fields": [],
                "warnings": []
            }
            
            # 检查必需字段
            required_fields = ["display_name", "filename", "url", "slug", "category"]
            
            for field in required_fields:
                if field not in config or not config[field]:
                    validation_result["missing_fields"].append(field)
                    validation_result["is_valid"] = False
            
            # 检查文件名是否有效
            if config.get("filename"):
                if not config["filename"].endswith(".html"):
                    validation_result["warnings"].append("文件名应以.html结尾")
            
            # 检查URL格式
            if config.get("url"):
                if not config["url"].startswith("https://"):
                    validation_result["warnings"].append("URL应使用HTTPS协议")
            
            return validation_result
            
        except ValueError as e:
            return {
                "is_valid": False,
                "error": str(e),
                "missing_fields": [],
                "warnings": []
            }
            
    def get_all_validation_results(self) -> Dict[str, Dict[str, Any]]:
        """获取所有产品配置的验证结果"""
        results = {}
        
        for product_key in self.get_supported_products():
            results[product_key] = self.validate_product_config(product_key)
            
        return results