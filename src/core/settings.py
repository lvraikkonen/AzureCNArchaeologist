#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用设置配置
包含日志系统和其他核心配置
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()


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

    # 文件路径配置
    HTML_BASE_DIR = os.getenv("HTML_BASE_DIR", "data/prod-html")
    OUTPUT_BASE_DIR = os.getenv("OUTPUT_BASE_DIR", "output")
    CONFIG_BASE_DIR = os.getenv("CONFIG_BASE_DIR", "data/configs")
    
    # 批处理配置
    DEFAULT_PARALLEL_JOBS = int(os.getenv("DEFAULT_PARALLEL_JOBS", "4"))
    DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "zh-cn")
    BATCH_DB_PATH = os.getenv("BATCH_DB_PATH", "data/batch_records.db")
    DEFAULT_MAX_RETRIES = int(os.getenv("DEFAULT_MAX_RETRIES", "3"))
    
    # 输出格式配置
    DEFAULT_OUTPUT_FORMAT = os.getenv("DEFAULT_OUTPUT_FORMAT", "flexible")
    ENABLE_VALIDATION = os.getenv("ENABLE_VALIDATION", "true").lower() == "true"

    # Azure Storage配置
    AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_BLOB_CONTAINER_NAME = os.getenv("AZURE_BLOB_CONTAINER_NAME", "cms-output")


# 创建全局设置实例
settings = Settings()
