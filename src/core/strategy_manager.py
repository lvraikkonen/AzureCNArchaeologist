#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略管理器

负责根据页面复杂度分析结果选择合适的提取策略，整合了原本分散在
ProductManager中的策略决策逻辑。
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

from .data_models import (
    PageComplexity, ExtractionStrategy, PageType, StrategyType
)
from .product_manager import ProductManager
from ..detectors.page_analyzer import PageAnalyzer


class StrategyManager:
    """
    策略管理器。
    
    根据页面复杂度分析和产品配置，智能选择最适合的提取策略。
    整合了文件大小检测、页面类型判断、策略匹配等功能。
    """
    
    def __init__(self, product_manager: Optional[ProductManager] = None):
        """
        初始化策略管理器。
        
        Args:
            product_manager: 产品管理器实例，如果不提供会自动创建
        """
        self.product_manager = product_manager or ProductManager()
        self.page_analyzer = PageAnalyzer()
        
        # 大文件阈值 (MB)
        self.large_file_threshold_mb = 5.0
        
        # 策略注册表
        self.strategy_registry = self._initialize_strategy_registry()
        
        print("✓ 策略管理器初始化完成")
        print(f"📊 支持策略类型: {len(self.strategy_registry)}种")
    
    def determine_extraction_strategy(self, html_file_path: str, 
                                    product_key: str) -> ExtractionStrategy:
        """
        确定提取策略。
        
        Args:
            html_file_path: HTML文件路径
            product_key: 产品标识符
            
        Returns:
            ExtractionStrategy对象，包含完整的策略信息
        """
        print(f"🎯 策略决策: {os.path.basename(html_file_path)}")
        
        # 1. 文件大小检测
        file_size_mb = self._get_file_size_mb(html_file_path)
        is_large_file = file_size_mb > self.large_file_threshold_mb
        
        print(f"📏 文件大小: {file_size_mb:.2f} MB")
        
        # 2. 大文件优先处理
        if is_large_file:
            print(f"🔥 大文件策略: 文件大小超过 {self.large_file_threshold_mb} MB")
            return self._create_large_file_strategy(file_size_mb, product_key)
        
        # 3. 页面复杂度分析
        try:
            from bs4 import BeautifulSoup
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            complexity = self.page_analyzer.analyze_page_complexity(soup, html_file_path)
            recommended_page_type = self.page_analyzer.get_recommended_page_type(complexity)
            
            print(f"📊 页面类型: {recommended_page_type}")
            print(f"🌏 区域筛选: {complexity.has_region_filter}")
            print(f"📂 Tab结构: {complexity.has_tabs}")
            print(f"🔧 多重筛选: {complexity.has_multiple_filters}")
            
        except Exception as e:
            print(f"⚠ 页面分析失败: {e}")
            # 降级到简单策略
            recommended_page_type = PageType.SIMPLE_STATIC
            complexity = None
        
        # 4. 根据页面类型选择策略
        strategy = self._select_strategy_by_page_type(
            recommended_page_type, product_key, complexity
        )
        
        print(f"✅ 选择策略: {strategy.strategy_type}")
        return strategy
    
    def _initialize_strategy_registry(self) -> Dict[StrategyType, Dict[str, Any]]:
        """初始化策略注册表。"""
        return {
            StrategyType.SIMPLE_STATIC: {
                "processor": "SimpleStaticProcessor",
                "description": "简单静态页面处理",
                "features": ["基础内容提取", "FAQ提取"],
                "complexity_threshold": 0.3
            },
            StrategyType.REGION_FILTER: {
                "processor": "RegionFilterProcessor", 
                "description": "区域筛选页面处理",
                "features": ["区域检测", "区域内容提取", "区域筛选"],
                "complexity_threshold": 0.5
            },
            StrategyType.TAB: {
                "processor": "TabProcessor",
                "description": "Tab结构页面处理", 
                "features": ["Tab导航检测", "Tab内容提取"],
                "complexity_threshold": 0.6
            },
            StrategyType.REGION_TAB: {
                "processor": "RegionTabProcessor",
                "description": "区域+Tab组合页面处理",
                "features": ["区域检测", "Tab检测", "组合内容提取"],
                "complexity_threshold": 0.8
            },
            StrategyType.MULTI_FILTER: {
                "processor": "MultiFilterProcessor",
                "description": "多重筛选器页面处理",
                "features": ["多筛选器检测", "动态内容提取", "状态管理"],
                "complexity_threshold": 0.9
            },
            StrategyType.LARGE_FILE: {
                "processor": "LargeFileProcessor",
                "description": "大文件优化处理",
                "features": ["流式处理", "内存优化", "分块处理"],
                "complexity_threshold": 1.0
            }
        }
    
    def _select_strategy_by_page_type(self, page_type: PageType, 
                                    product_key: str,
                                    complexity: Optional[PageComplexity]) -> ExtractionStrategy:
        """根据页面类型选择策略。"""
        
        # 页面类型到策略类型的映射
        page_to_strategy_mapping = {
            PageType.SIMPLE_STATIC: StrategyType.SIMPLE_STATIC,
            PageType.REGION_FILTER: StrategyType.REGION_FILTER,
            PageType.TAB: StrategyType.TAB,
            PageType.REGION_TAB: StrategyType.REGION_TAB,
            PageType.MULTI_FILTER: StrategyType.MULTI_FILTER,
            PageType.LARGE_FILE: StrategyType.LARGE_FILE
        }
        
        strategy_type = page_to_strategy_mapping.get(page_type, StrategyType.SIMPLE_STATIC)
        
        # 获取策略配置
        strategy_config = self.strategy_registry[strategy_type]
        
        # 获取产品特定的配置覆盖
        product_overrides = self._get_product_config_overrides(product_key, strategy_type)
        
        # 创建策略对象
        return ExtractionStrategy(
            strategy_type=strategy_type,
            processor=strategy_config["processor"],
            description=strategy_config["description"],
            features=strategy_config["features"],
            priority_features=self._determine_priority_features(complexity, strategy_type),
            config_overrides=product_overrides,
            complexity_score=complexity.estimated_complexity_score if complexity else 0.0,
            recommended_page_type=page_type
        )
    
    def _create_large_file_strategy(self, file_size_mb: float, 
                                  product_key: str) -> ExtractionStrategy:
        """创建大文件处理策略。"""
        strategy_config = self.strategy_registry[StrategyType.LARGE_FILE]
        
        # 根据文件大小确定处理模式
        if file_size_mb > 20.0:
            processing_mode = "streaming"
        elif file_size_mb > 10.0:
            processing_mode = "chunked"
        else:
            processing_mode = "optimized"
        
        config_overrides = {
            "file_size_mb": file_size_mb,
            "processing_mode": processing_mode,
            "memory_limit_mb": min(file_size_mb * 2, 200),  # 动态内存限制
            "chunk_size": 1024 * 1024 if processing_mode == "chunked" else None
        }
        
        # 获取产品特定配置
        product_overrides = self._get_product_config_overrides(product_key, StrategyType.LARGE_FILE)
        config_overrides.update(product_overrides)
        
        return ExtractionStrategy(
            strategy_type=StrategyType.LARGE_FILE,
            processor=strategy_config["processor"],
            description=f"大文件处理 ({file_size_mb:.1f}MB)",
            features=strategy_config["features"] + [f"{processing_mode}模式"],
            priority_features=["内存优化", "性能优化"],
            config_overrides=config_overrides,
            complexity_score=1.0,  # 大文件总是最高复杂度
            recommended_page_type=PageType.LARGE_FILE
        )
    
    def _determine_priority_features(self, complexity: Optional[PageComplexity], 
                                   strategy_type: StrategyType) -> list[str]:
        """确定优先特性。"""
        if not complexity:
            return []
        
        priority_features = []
        
        # 根据复杂度特征确定优先级
        if complexity.has_region_filter:
            priority_features.append("区域处理")
        
        if complexity.has_tabs:
            priority_features.append("Tab处理")
        
        if complexity.has_multiple_filters:
            priority_features.append("多筛选器处理")
        
        if complexity.interactive_elements > 10:
            priority_features.append("交互元素处理")
        
        # 根据策略类型添加特定优先级
        strategy_priority_map = {
            StrategyType.REGION_FILTER: ["区域检测", "区域内容提取"],
            StrategyType.TAB: ["Tab导航解析", "Tab内容提取"],
            StrategyType.REGION_TAB: ["区域Tab联合解析", "复合内容提取"],
            StrategyType.MULTI_FILTER: ["筛选器状态管理", "动态内容更新"],
            StrategyType.LARGE_FILE: ["内存优化", "流式处理"]
        }
        
        strategy_priorities = strategy_priority_map.get(strategy_type, [])
        priority_features.extend(strategy_priorities)
        
        return list(set(priority_features))  # 去重
    
    def _get_product_config_overrides(self, product_key: str, 
                                    strategy_type: StrategyType) -> Dict[str, Any]:
        """获取产品特定的配置覆盖。"""
        overrides = {}
        
        # 从ProductManager获取产品配置
        try:
            product_config = self.product_manager.get_product_config(product_key)
            if product_config:
                # 提取策略相关的配置
                strategy_config = product_config.get('extraction_strategy', {})
                strategy_specific = strategy_config.get(strategy_type.value, {})
                overrides.update(strategy_specific)
                
                # 通用配置覆盖
                common_overrides = strategy_config.get('common', {})
                overrides.update(common_overrides)
                
        except Exception as e:
            print(f"⚠ 获取产品配置失败: {e}")
        
        # 产品特定的硬编码覆盖（临时）
        product_specific_overrides = {
            'api-management': {
                StrategyType.REGION_FILTER: {
                    'region_detection_mode': 'aggressive',
                    'fallback_regions': ['china-north', 'china-east']
                }
            },
            'sql-database': {
                StrategyType.MULTI_FILTER: {
                    'filter_detection_threshold': 2,
                    'enable_dynamic_content': True
                }
            }
        }
        
        if product_key in product_specific_overrides:
            product_overrides = product_specific_overrides[product_key].get(strategy_type, {})
            overrides.update(product_overrides)
        
        return overrides
    
    def _get_file_size_mb(self, file_path: str) -> float:
        """获取文件大小（MB）。"""
        try:
            if os.path.exists(file_path):
                size_bytes = os.path.getsize(file_path)
                return size_bytes / (1024 * 1024)
            else:
                print(f"⚠ 文件不存在: {file_path}")
                return 0.0
        except OSError as e:
            print(f"⚠ 获取文件大小失败: {e}")
            return 0.0
    
    def get_strategy_info(self, strategy_type: StrategyType) -> Dict[str, Any]:
        """获取策略信息。"""
        return self.strategy_registry.get(strategy_type, {})
    
    def list_available_strategies(self) -> Dict[StrategyType, str]:
        """列出所有可用策略。"""
        return {
            strategy_type: config["description"] 
            for strategy_type, config in self.strategy_registry.items()
        }
    
    def validate_strategy(self, strategy: ExtractionStrategy) -> bool:
        """验证策略配置的有效性。"""
        try:
            # 检查策略类型是否注册
            if strategy.strategy_type not in self.strategy_registry:
                return False
            
            # 检查处理器是否指定
            if not strategy.processor:
                return False
            
            # 检查配置覆盖是否合理
            if strategy.config_overrides:
                # 检查大文件策略的特殊要求
                if strategy.strategy_type == StrategyType.LARGE_FILE:
                    required_keys = ['file_size_mb', 'processing_mode']
                    if not all(key in strategy.config_overrides for key in required_keys):
                        return False
            
            return True
            
        except Exception:
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息。"""
        return {
            "strategy_registry_size": len(self.strategy_registry),
            "page_analyzer_initialized": self.page_analyzer is not None,
            "product_manager_stats": self.product_manager.get_cache_stats() if self.product_manager else {}
        }