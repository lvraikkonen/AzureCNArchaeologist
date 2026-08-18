"""Production extraction strategies copied from the v0.5.5 baseline.

Strategy modules are loaded only when requested. This lets each rewrite
milestone adapt and prove one Strategy without silently importing unfinished
dependencies from the other three.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_STRATEGY_MODULES = {
    "BaseStrategy": "src.strategies.base_strategy",
    "SimpleStaticStrategy": "src.strategies.simple_static_strategy",
    "RegionFilterStrategy": "src.strategies.region_filter_strategy",
    "ComplexContentStrategy": "src.strategies.complex_content_strategy",
    "SupportArticleStrategy": "src.strategies.support_article_strategy",
    "StrategyFactory": "src.strategies.strategy_factory",
}

__all__ = list(_STRATEGY_MODULES)


def __getattr__(name: str) -> Any:
    module_name = _STRATEGY_MODULES.get(name)
    if module_name is None:
        raise AttributeError(name)
    return getattr(import_module(module_name), name)
