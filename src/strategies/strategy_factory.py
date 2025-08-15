#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略工厂
负责注册、创建和管理所有提取策略实例
"""

import os
import sys
from pathlib import Path
from typing import Dict, Type, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.core.data_models import StrategyType, ExtractionStrategy
from src.strategies.base_strategy import BaseStrategy
from src.core.logging import get_logger

logger = get_logger(__name__)


class StrategyFactory:
    """策略工厂类，实现策略模式的工厂模式"""
    
    # 策略注册表：策略类型 -> 策略类
    _strategies: Dict[StrategyType, Type[BaseStrategy]] = {}
    
    # 策略描述信息 - 3+1架构
    _strategy_descriptions: Dict[StrategyType, str] = {
        StrategyType.SIMPLE_STATIC: "简单静态页面处理策略",
        StrategyType.REGION_FILTER: "区域筛选页面处理策略",
        StrategyType.COMPLEX: "复杂多筛选器页面处理策略",
        StrategyType.LARGE_FILE: "大文件优化处理策略"
    }

    @classmethod
    def register_strategy(cls, strategy_type: StrategyType, strategy_class: Type[BaseStrategy]) -> None:
        """
        注册策略类
        
        Args:
            strategy_type: 策略类型
            strategy_class: 策略类
        """
        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError(f"策略类 {strategy_class.__name__} 必须继承自 BaseStrategy")
        
        cls._strategies[strategy_type] = strategy_class
        logger.info(f"✓ 注册策略: {strategy_type.value} -> {strategy_class.__name__}")

    @classmethod
    def create_strategy(cls, extraction_strategy: ExtractionStrategy, 
                       product_config: Dict[str, Any], 
                       html_file_path: str = "") -> BaseStrategy:
        """
        创建策略实例
        
        Args:
            extraction_strategy: StrategyManager返回的策略配置
            product_config: 产品配置信息
            html_file_path: HTML文件路径
            
        Returns:
            策略实例
            
        Raises:
            ValueError: 未知的策略类型或策略未注册
        """
        strategy_type = extraction_strategy.strategy_type
        
        if strategy_type not in cls._strategies:
            available_strategies = list(cls._strategies.keys())
            raise ValueError(
                f"未知的策略类型: {strategy_type.value}. "
                f"已注册的策略: {[s.value for s in available_strategies]}"
            )
        
        strategy_class = cls._strategies[strategy_type]
        
        try:
            # 创建策略实例
            strategy_instance = strategy_class(
                product_config=product_config,
                html_file_path=html_file_path
            )
            
            # 设置策略相关信息
            strategy_instance.strategy_name = strategy_type.value
            strategy_instance.extraction_strategy = extraction_strategy
            
            logger.info(f"✓ 创建策略实例: {strategy_type.value} -> {strategy_class.__name__}")
            return strategy_instance
            
        except Exception as e:
            raise ValueError(f"创建策略实例失败 ({strategy_type.value}): {e}")

    @classmethod
    def create_fallback_strategy(cls, product_config: Dict[str, Any], 
                                html_file_path: str = "") -> BaseStrategy:
        """
        创建回退策略实例（当策略选择失败时使用）
        
        Args:
            product_config: 产品配置信息
            html_file_path: HTML文件路径
            
        Returns:
            简单静态策略实例作为回退
        """
        logger.info("⚠ 使用回退策略: SimpleStaticStrategy")
        
        # 创建默认的提取策略配置
        from src.core.data_models import ExtractionStrategy
        fallback_extraction_strategy = ExtractionStrategy(
            strategy_type=StrategyType.SIMPLE_STATIC,
            processor="SimpleStaticProcessor",
            description="回退策略",
            features=["基础内容提取"],
            priority_features=["Title", "DescriptionContent"],
            config_overrides={}
        )
        
        return cls.create_strategy(
            fallback_extraction_strategy, 
            product_config, 
            html_file_path
        )

    @classmethod
    def get_registered_strategies(cls) -> Dict[StrategyType, Type[BaseStrategy]]:
        """
        获取所有已注册的策略
        
        Returns:
            策略类型到策略类的映射
        """
        return cls._strategies.copy()

    @classmethod
    def get_strategy_description(cls, strategy_type: StrategyType) -> str:
        """
        获取策略描述
        
        Args:
            strategy_type: 策略类型
            
        Returns:
            策略描述信息
        """
        return cls._strategy_descriptions.get(strategy_type, "未知策略")

    @classmethod
    def is_strategy_registered(cls, strategy_type: StrategyType) -> bool:
        """
        检查策略是否已注册
        
        Args:
            strategy_type: 策略类型
            
        Returns:
            是否已注册
        """
        return strategy_type in cls._strategies

    @classmethod
    def get_registration_status(cls) -> Dict[str, Any]:
        """
        获取策略注册状态报告
        
        Returns:
            注册状态信息
        """
        all_strategy_types = list(StrategyType)
        registered_count = len(cls._strategies)
        total_count = len(all_strategy_types)
        
        status = {
            "total_strategies": total_count,
            "registered_strategies": registered_count,
            "completion_rate": registered_count / total_count * 100,
            "registered": {
                strategy_type.value: {
                    "class_name": strategy_class.__name__,
                    "description": cls.get_strategy_description(strategy_type)
                }
                for strategy_type, strategy_class in cls._strategies.items()
            },
            "missing": [
                {
                    "strategy_type": strategy_type.value,
                    "description": cls.get_strategy_description(strategy_type)
                }
                for strategy_type in all_strategy_types
                if strategy_type not in cls._strategies
            ]
        }
        
        return status

    @classmethod
    def validate_strategy_registration(cls) -> bool:
        """
        验证所有必需的策略是否已注册
        
        Returns:
            是否所有策略都已注册
        """
        all_strategy_types = set(StrategyType)
        registered_strategy_types = set(cls._strategies.keys())
        
        missing_strategies = all_strategy_types - registered_strategy_types
        
        if missing_strategies:
            logger.warning(f"⚠ 缺少策略注册: {[s.value for s in missing_strategies]}")
            return False
        
        logger.info("✓ 所有策略已完整注册")
        return True

    @classmethod
    def clear_registrations(cls) -> None:
        """清除所有注册的策略（主要用于测试）"""
        cls._strategies.clear()
        logger.info("🧹 清除所有策略注册")


# 便捷函数，用于在其他模块中快速访问工厂功能
def register_strategy(strategy_type: StrategyType, strategy_class: Type[BaseStrategy]) -> None:
    """便捷函数：注册策略"""
    StrategyFactory.register_strategy(strategy_type, strategy_class)


def create_strategy(extraction_strategy: ExtractionStrategy, 
                   product_config: Dict[str, Any], 
                   html_file_path: str = "") -> BaseStrategy:
    """便捷函数：创建策略实例"""
    return StrategyFactory.create_strategy(extraction_strategy, product_config, html_file_path)


def get_strategy_status() -> Dict[str, Any]:
    """便捷函数：获取策略注册状态"""
    return StrategyFactory.get_registration_status()