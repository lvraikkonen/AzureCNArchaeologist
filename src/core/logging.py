#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志框架模块
基于loguru的统一日志管理系统
"""

import json
import sys
import time
from datetime import datetime
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, Dict, Optional, Callable

from loguru import logger

from .settings import settings


@lru_cache
def get_logger(name: str):
    """
    获取指定名称的日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        logger: 配置好的日志记录器
    """
    return logger.bind(name=name)


def setup_logging():
    """配置应用日志系统"""
    # 确保日志目录存在
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台输出处理器
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format=settings.LOG_FORMAT,
        colorize=True,
        filter=lambda record: record["extra"].get("name") != "user_operation"
    )
    
    # 添加主日志文件处理器
    logger.add(
        settings.LOG_FILE,
        level=settings.LOG_LEVEL,
        format=settings.LOG_FORMAT,
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        filter=lambda record: record["extra"].get("name") != "user_operation"
    )
    
    # 添加用户操作日志处理器
    logger.add(
        settings.USER_OPERATION_LOG_FILE,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        filter=lambda record: record["extra"].get("name") == "user_operation"
    )
    
    # 添加错误日志处理器
    logger.add(
        settings.ERROR_LOG_FILE,
        level="ERROR",
        format=settings.LOG_FORMAT,
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip"
    )
    
    # 添加性能日志处理器
    logger.add(
        settings.PERFORMANCE_LOG_FILE,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        filter=lambda record: record["extra"].get("name") == "performance"
    )
    
    # 添加数据处理日志处理器
    logger.add(
        settings.DATA_PROCESSING_LOG_FILE,
        level="INFO",
        format=settings.LOG_FORMAT,
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        filter=lambda record: record["extra"].get("name") == "data_processing"
    )
    
    logger.info(f"日志系统已初始化，日志级别: {settings.LOG_LEVEL}")
    logger.info(f"日志目录: {settings.LOG_DIR}")


def log_user_operation(
    user: Optional[str],
    action: str,
    details: Dict[str, Any],
    status: str = "成功",
):
    """
    记录用户操作日志
    
    Args:
        user: 用户名
        action: 操作类型
        details: 操作详情
        status: 操作状态
    """
    operation_logger = get_logger("user_operation")
    
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user": user or "系统用户",
            "action": action,
            "status": status,
            "details": details,
        }
        
        operation_logger.info(f"用户操作: {json.dumps(log_entry, ensure_ascii=False)}")
        
    except Exception as e:
        logger.error(f"记录用户操作日志失败: {e}")


def log_performance(operation: str, duration: float, details: Optional[Dict[str, Any]] = None):
    """
    记录性能日志
    
    Args:
        operation: 操作名称
        duration: 执行时间（秒）
        details: 额外详情
    """
    performance_logger = get_logger("performance")
    
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "duration_seconds": round(duration, 3),
            "details": details or {}
        }
        
        performance_logger.info(f"性能统计: {json.dumps(log_entry, ensure_ascii=False)}")
        
    except Exception as e:
        logger.error(f"记录性能日志失败: {e}")


def log_data_processing(
    operation: str,
    input_count: int,
    output_count: int,
    success_count: int,
    error_count: int,
    details: Optional[Dict[str, Any]] = None
):
    """
    记录数据处理日志
    
    Args:
        operation: 处理操作名称
        input_count: 输入数据量
        output_count: 输出数据量
        success_count: 成功处理数量
        error_count: 错误数量
        details: 额外详情
    """
    data_logger = get_logger("data_processing")
    
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "input_count": input_count,
            "output_count": output_count,
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": round(success_count / max(input_count, 1) * 100, 2),
            "details": details or {}
        }
        
        data_logger.info(f"数据处理: {json.dumps(log_entry, ensure_ascii=False)}")
        
    except Exception as e:
        logger.error(f"记录数据处理日志失败: {e}")


def performance_monitor(operation_name: str = None):
    """
    性能监控装饰器
    
    Args:
        operation_name: 操作名称，如果不提供则使用函数名
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                log_performance(op_name, duration, {"status": "success"})
                return result
            except Exception as e:
                duration = time.time() - start_time
                log_performance(op_name, duration, {"status": "error", "error": str(e)})
                raise
                
        return wrapper
    return decorator


def get_app_logger(name: str = None):
    """
    获取应用日志记录器的便捷函数
    
    Args:
        name: 日志记录器名称，如果不提供则使用调用模块名
        
    Returns:
        logger: 配置好的日志记录器
    """
    if name is None:
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    return get_logger(name)


# 导出常用的日志记录器
app_logger = get_app_logger("app")
extraction_logger = get_app_logger("extraction")
export_logger = get_app_logger("export")
config_logger = get_app_logger("config")
