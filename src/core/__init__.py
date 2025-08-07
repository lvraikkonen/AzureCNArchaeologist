#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core模块 - 核心业务组件
包含产品管理器、区域处理器、日志系统等核心业务逻辑
"""

from .product_manager import ProductManager
from .region_processor import RegionProcessor
from .config_manager import ConfigManager
from .logging import (
    setup_logging,
    get_logger,
    get_app_logger,
    log_user_operation,
    log_performance,
    log_data_processing,
    performance_monitor,
    app_logger,
    extraction_logger,
    export_logger,
    config_logger
)
from .settings import settings

__all__ = [
    'ProductManager',
    'RegionProcessor',
    'ConfigManager',
    'setup_logging',
    'get_logger',
    'get_app_logger',
    'log_user_operation',
    'log_performance',
    'log_data_processing',
    'performance_monitor',
    'app_logger',
    'extraction_logger',
    'export_logger',
    'config_logger',
    'settings'
]