"""
Strategies module for extraction strategy implementations.

This module contains different extraction strategies for various page types:
- BaseStrategy: Abstract base strategy
- RegionFilterStrategy: For pages with region filtering (implemented)
- SimpleStaticStrategy: For simple static pages (planned)
- TabStrategy: For tab-controlled pages (planned)
- RegionTabStrategy: For combined region+tab pages (planned)
- MultiFilterStrategy: For multi-filter pages (planned)
- LargeFileStrategy: For large file optimization (planned)
"""

# Import base classes
from .base_strategy import BaseStrategy
from .strategy_factory import StrategyFactory

# Import data models for proper typing
from src.core.data_models import StrategyType

# Import implemented strategies
from .region_filter_strategy import RegionFilterStrategy
from .simple_static_strategy import SimpleStaticStrategy

from src.core.logging import get_logger

logger = get_logger(__name__)

# Register implemented strategies
logger.info("📋 注册策略到StrategyFactory...")

try:
    StrategyFactory.register_strategy(StrategyType.REGION_FILTER, RegionFilterStrategy)
    logger.info("✅ RegionFilterStrategy 已注册")
except Exception as e:
    logger.error(f"⚠️ RegionFilterStrategy 注册失败: {e}")

try:
    StrategyFactory.register_strategy(StrategyType.SIMPLE_STATIC, SimpleStaticStrategy)
    logger.info("✅ SimpleStaticStrategy 已注册")
except Exception as e:
    logger.error(f"⚠️ SimpleStaticStrategy 注册失败: {e}")

# Strategy registry for tracking (using enum as key for consistency)
STRATEGY_REGISTRY = {
    StrategyType.REGION_FILTER: RegionFilterStrategy,
    StrategyType.SIMPLE_STATIC: SimpleStaticStrategy,
    # More strategies will be added as they are implemented
}

logger.info(f"📊 已注册策略数量: {len(STRATEGY_REGISTRY)}")

# Export main classes and factory
__all__ = [
    'BaseStrategy',
    'StrategyFactory', 
    'RegionFilterStrategy',
    'SimpleStaticStrategy',
    'STRATEGY_REGISTRY'
]