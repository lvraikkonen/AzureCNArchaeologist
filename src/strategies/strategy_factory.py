"""Create one of the four copied production Strategies by its readable name."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from src.strategies.base_strategy import BaseStrategy


class StrategyFactory:
    _strategy_classes = {
        "simple_static": (
            "src.strategies.simple_static_strategy",
            "SimpleStaticStrategy",
        ),
        "region_filter": (
            "src.strategies.region_filter_strategy",
            "RegionFilterStrategy",
        ),
        "complex": (
            "src.strategies.complex_content_strategy",
            "ComplexContentStrategy",
        ),
        "support_article": (
            "src.strategies.support_article_strategy",
            "SupportArticleStrategy",
        ),
    }

    @classmethod
    def create_strategy(
        cls,
        strategy_name: str,
        product_config: dict[str, Any],
        html_file_path: str = "",
    ) -> BaseStrategy:
        location = cls._strategy_classes.get(strategy_name)
        if location is None:
            available = ", ".join(cls._strategy_classes)
            raise ValueError(
                f"未知 Strategy {strategy_name!r}；当前可选值：{available}。"
            )
        module_name, class_name = location
        strategy_class = getattr(import_module(module_name), class_name)
        if not isinstance(strategy_class, type) or not issubclass(
            strategy_class, BaseStrategy
        ):
            raise TypeError(f"{class_name} 不是 BaseStrategy 的实现。")
        return strategy_class(
            product_config=product_config,
            html_file_path=html_file_path,
        )

    @classmethod
    def get_registration_status(cls) -> dict[str, Any]:
        names = list(cls._strategy_classes)
        return {
            "total_strategies": len(names),
            "registered_strategies": len(names),
            "strategies": names,
        }


def create_strategy(
    strategy_name: str,
    product_config: dict[str, Any],
    html_file_path: str = "",
) -> BaseStrategy:
    return StrategyFactory.create_strategy(
        strategy_name,
        product_config,
        html_file_path,
    )
