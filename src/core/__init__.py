#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core模块 - 核心业务组件
包含产品管理器、区域处理器等核心业务逻辑
"""

from .product_manager import ProductManager
from .region_processor import RegionProcessor
from .config_manager import ConfigManager

__all__ = [
    'ProductManager',
    'RegionProcessor',
    'ConfigManager'
    ]