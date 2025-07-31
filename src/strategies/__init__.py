"""
Strategies module for extraction strategy implementations.

This module will contain different extraction strategies for various page types:
- BaseStrategy: Abstract base strategy
- SimpleStaticStrategy: For simple static pages
- RegionFilterStrategy: For pages with region filtering
- TabStrategy: For tab-controlled pages
- RegionTabStrategy: For combined region+tab pages
- MultiFilterStrategy: For multi-filter pages
- LargeFileStrategy: For large file optimization
"""

# Strategy registry will be populated in Phase 3
STRATEGY_REGISTRY = {
    # Will be populated as strategies are implemented
}

# Imports will be added as strategies are implemented
# from .base_strategy import BaseStrategy