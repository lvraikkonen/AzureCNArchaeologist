#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理器
简化版配置管理，保留现有接口的兼容性
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from .logging import get_logger

logger = get_logger(__name__)


class ConfigManager:
    """简化的配置管理器，保持向后兼容"""

    def __init__(self, config_dir: str = "data/configs"):
        self.config_dir = Path(config_dir)
        self.soft_category_file = self.config_dir / "soft-category.json"
        self.soft_category_config = None

        logger.info("配置管理器初始化完成")
        logger.info(f"配置目录: {self.config_dir}")

    def load_soft_category_config(self) -> Dict[str, Any]:
        """加载软件分类配置（保持兼容性）"""
        if self.soft_category_config is None:
            if self.soft_category_file.exists():
                try:
                    with open(self.soft_category_file, 'r', encoding='utf-8') as f:
                        self.soft_category_config = json.load(f)
                    logger.info(f"加载软件分类配置: {len(self.soft_category_config)} 项")
                except Exception as e:
                    logger.warning(f"加载软件分类配置失败: {e}")
                    self.soft_category_config = {}
            else:
                logger.warning(f"软件分类配置文件不存在: {self.soft_category_file}")
                self.soft_category_config = {}
        
        return self.soft_category_config

    def get_region_config_for_product(self, product_key: str) -> Dict[str, List[str]]:
        """获取产品的区域配置"""
        soft_config = self.load_soft_category_config()
        return soft_config.get(product_key, {})

    def get_table_exclusions_for_region(self, product_key: str, region_id: str) -> List[str]:
        """获取特定区域的表格排除列表"""
        region_config = self.get_region_config_for_product(product_key)
        return region_config.get(region_id, [])

    def should_exclude_table(self, product_key: str, region_id: str, table_id: str) -> bool:
        """检查是否应该排除特定表格"""
        exclusion_list = self.get_table_exclusions_for_region(product_key, region_id)
        return table_id in exclusion_list

    def get_all_configured_products(self) -> List[str]:
        """获取所有已配置的产品列表"""
        soft_config = self.load_soft_category_config()
        return list(soft_config.keys())

    def get_all_configured_regions(self, product_key: str = None) -> List[str]:
        """获取所有配置的区域列表"""
        if product_key:
            region_config = self.get_region_config_for_product(product_key)
            return list(region_config.keys())
        else:
            # 获取所有产品的所有区域
            soft_config = self.load_soft_category_config()
            all_regions = set()
            for product_config in soft_config.values():
                all_regions.update(product_config.keys())
            return sorted(list(all_regions))