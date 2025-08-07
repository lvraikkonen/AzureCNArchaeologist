#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用设置配置
包含日志系统和其他核心配置
"""

import os
from pathlib import Path


class Settings:
    """应用设置类"""
    
    # 项目根目录
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    
    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR = PROJECT_ROOT / "logs"
    LOG_FILE = LOG_DIR / "app.log"
    
    # 日志格式
    LOG_FORMAT = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    # 日志轮转配置
    LOG_ROTATION = "10 MB"  # 当日志文件达到10MB时轮转
    LOG_RETENTION = "30 days"  # 保留30天的日志文件
    
    # 用户操作日志配置
    USER_OPERATION_LOG_FILE = LOG_DIR / "user_operations.log"
    
    # 错误日志配置
    ERROR_LOG_FILE = LOG_DIR / "errors.log"
    
    # 性能日志配置
    PERFORMANCE_LOG_FILE = LOG_DIR / "performance.log"
    
    # 数据处理日志配置
    DATA_PROCESSING_LOG_FILE = LOG_DIR / "data_processing.log"


# 创建全局设置实例
settings = Settings()
