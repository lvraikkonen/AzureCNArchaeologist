#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略管理器

负责根据页面复杂度分析结果选择合适的提取策略，整合了原本分散在
ProductManager中的策略决策逻辑。
"""

from typing import Dict, Any, Optional

from bs4 import BeautifulSoup

from .data_models import (
    PageComplexity, ExtractionStrategy, PageType, StrategyType
)
from .product_manager import ProductManager
from ..detectors.page_analyzer import PageAnalyzer


class StrategyManager:
    """
    策略管理器。
    
    根据页面结构分析和产品配置选择语义提取策略。输入大小属于独立的
    processing capability，不得影响这里的内容策略。
    """
    
    def __init__(self, product_manager: Optional[ProductManager] = None):
        """
        初始化策略管理器。
        
        Args:
            product_manager: 产品管理器实例，如果不提供会自动创建
        """
        self.product_manager = product_manager or ProductManager()
        self.page_analyzer = PageAnalyzer()
        
        # 策略注册表
        self.strategy_registry = self._initialize_strategy_registry()
        
        print("✓ 策略管理器初始化完成")
        print(f"📊 支持策略类型: {len(self.strategy_registry)}种")
    
    def determine_extraction_strategy(
        self,
        soup: BeautifulSoup,
        product_key: str,
        *,
        input_bytes: int | None = None,
    ) -> ExtractionStrategy:
        """
        确定提取策略。
        
        Args:
            soup: 已由正式 strict UTF-8 输入路径解析的 HTML
            product_key: 产品标识符
            input_bytes: 可选诊断数据；不参与语义策略选择
            
        Returns:
            ExtractionStrategy对象，包含完整的策略信息
        """
        if not isinstance(soup, BeautifulSoup):
            raise TypeError("soup must be a parsed BeautifulSoup document")
        if input_bytes is not None:
            if (
                isinstance(input_bytes, bool)
                or not isinstance(input_bytes, int)
                or input_bytes < 0
            ):
                raise ValueError("input_bytes must be a non-negative integer")
            print(f"📏 输入大小（仅诊断）: {input_bytes} bytes")
        print(f"🎯 策略决策: {product_key}")

        # SupportArticle is selected by the explicit page model. Its CMS type is
        # independent from catalog categories and source directories.
        product_config = self.product_manager.get_product_config(product_key)
        page_model = product_config.get("page_model")
        configured_strategy = product_config.get("extraction", {}).get(
            "semantic_strategy"
        )
        if page_model == "SupportArticlePage":
            if configured_strategy != "support_article":
                raise ValueError(
                    "SupportArticlePage must declare semantic_strategy=support_article"
                )
            support_type = product_config["support_article_type"]
            print(f"📄 支持文章策略: support_article_type={support_type}")
            return self._create_support_article_strategy(product_key, support_type)
        if page_model != "FlexibleContentPage":
            raise ValueError(f"Unknown Product Definition page_model: {page_model!r}")

        # A Product Definition may pin a stable strategy when source controls are
        # present but intentionally belong in static content (for example Event Grid).
        configured_page_types = {
            "simple_static": PageType.SIMPLE_STATIC,
            "region_filter": PageType.REGION_FILTER,
            "complex": PageType.COMPLEX,
        }
        if configured_strategy not in configured_page_types:
            raise ValueError(
                "Product Definition must declare a known semantic_strategy; "
                f"found {configured_strategy!r}"
            )
        print(f"📌 Product Definition semantic strategy: {configured_strategy}")
        return self._select_strategy_by_page_type(
            configured_page_types[configured_strategy], product_key, None
        )
    
    def _initialize_strategy_registry(self) -> Dict[StrategyType, Dict[str, Any]]:
        """初始化语义策略注册表。"""
        return {
            StrategyType.SIMPLE_STATIC: {
                "processor": "SimpleStaticProcessor",
                "description": "简单静态页面处理",
                "features": ["基础内容提取", "FAQ提取", "Banner提取"],
                "complexity_threshold": 0.3
            },
            StrategyType.REGION_FILTER: {
                "processor": "RegionFilterProcessor", 
                "description": "区域筛选页面处理",
                "features": ["区域检测", "区域内容提取", "区域筛选器配置", "地区内容组生成"],
                "complexity_threshold": 0.5
            },
            StrategyType.COMPLEX: {
                "processor": "ComplexContentProcessor",
                "description": "复杂内容页面处理",
                "features": ["多筛选器检测", "Tab结构处理", "复合内容提取", "动态筛选器配置"],
                "complexity_threshold": 0.8
            },
            StrategyType.SUPPORT_ARTICLE: {
                "processor": "SupportArticleProcessor",
                "description": "支持文章页面处理 (SLA/ICP/Legal/公安备案)",
                "features": ["文章内容提取", "元数据提取", "扁平JSON输出"],
                "complexity_threshold": 0.1
            }
        }
    
    def _select_strategy_by_page_type(self, page_type: PageType, 
                                    product_key: str,
                                    complexity: Optional[PageComplexity]) -> ExtractionStrategy:
        """根据页面类型选择策略。"""
        
        # 页面类型到语义策略类型的一对一映射。
        page_to_strategy_mapping = {
            PageType.SIMPLE_STATIC: StrategyType.SIMPLE_STATIC,
            PageType.REGION_FILTER: StrategyType.REGION_FILTER,
            PageType.COMPLEX: StrategyType.COMPLEX,
            PageType.SUPPORT_ARTICLE: StrategyType.SUPPORT_ARTICLE
        }

        try:
            strategy_type = page_to_strategy_mapping[page_type]
        except (KeyError, TypeError) as error:
            raise ValueError(f"Unknown semantic page type: {page_type!r}") from error
        
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
    
    def _create_support_article_strategy(self, product_key: str,
                                        support_type: str) -> ExtractionStrategy:
        """创建支持文章处理策略。"""
        strategy_config = self.strategy_registry[StrategyType.SUPPORT_ARTICLE]

        return ExtractionStrategy(
            strategy_type=StrategyType.SUPPORT_ARTICLE,
            processor=strategy_config["processor"],
            description=strategy_config["description"],
            features=strategy_config["features"],
            priority_features=["articleDescription", "mainContent"],
            config_overrides={"support_article_type": support_type},
            complexity_score=0.0,
            recommended_page_type=PageType.SUPPORT_ARTICLE
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
        
        # 根据语义策略类型添加特定优先级。
        strategy_priority_map = {
            StrategyType.SIMPLE_STATIC: ["基础内容提取", "FAQ处理"],
            StrategyType.REGION_FILTER: ["区域检测", "区域内容提取", "地区内容组生成"],
            StrategyType.COMPLEX: ["多筛选器处理", "Tab结构解析", "复合内容提取", "动态筛选器配置"],
        }
        
        strategy_priorities = strategy_priority_map.get(strategy_type, [])
        priority_features.extend(strategy_priorities)
        
        return list(dict.fromkeys(priority_features))
    
    def _get_product_config_overrides(self, product_key: str, 
                                    strategy_type: StrategyType) -> Dict[str, Any]:
        """获取产品特定的配置覆盖。"""
        overrides = {}
        
        # Product Definition failures are fatal; an empty/default override must
        # never conceal a missing or invalid definition.
        product_config = self.product_manager.get_product_config(product_key)
        overrides.update(product_config.get('extraction', {}))
        
        # 产品特定的硬编码覆盖（临时）
        product_specific_overrides = {
            'api-management': {
                StrategyType.REGION_FILTER: {
                    'region_detection_mode': 'aggressive',
                    'fallback_regions': ['china-north', 'china-east'],
                    'enable_flexible_json': True
                }
            },
            'cloud-services': {
                StrategyType.COMPLEX: {
                    'filter_detection_threshold': 2,
                    'enable_dynamic_content': True,
                    'tab_processing_mode': 'category_tabs'
                }
            },
            'event-grid': {
                StrategyType.SIMPLE_STATIC: {
                    'content_extraction_mode': 'pricing_page_section',
                    'qa_deduplication': True
                }
            }
        }
        
        if product_key in product_specific_overrides:
            product_overrides = product_specific_overrides[product_key].get(strategy_type, {})
            overrides.update(product_overrides)
        
        return overrides
    
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
