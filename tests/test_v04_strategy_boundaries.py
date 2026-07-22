"""v0.4 semantic-strategy boundaries and fail-closed selection tests."""

from __future__ import annotations

import argparse
import contextlib
import io
import inspect
from dataclasses import fields
from typing import Any

import pytest
from bs4 import BeautifulSoup

import cli
from src.core.extraction_coordinator import ExtractionCoordinator
from src.core.data_models import ExtractionStrategy, PageComplexity, PageType, StrategyType
from src.core.product_manager import ProductManager
from src.core.strategy_manager import StrategyManager
from src.detectors.page_analyzer import PageAnalyzer
from src.strategies.strategy_factory import StrategyFactory


def _soup() -> BeautifulSoup:
    return BeautifulSoup("<html><body><main>fixture</main></body></html>", "html.parser")


class _ProductManager:
    def __init__(self, definition: dict[str, Any]) -> None:
        self.definition = definition
        self.calls = 0

    def get_product_config(self, product_key: str) -> dict[str, Any]:
        self.calls += 1
        assert product_key == "fixture"
        return self.definition

    def get_cache_stats(self) -> dict[str, int]:
        return {"cached_products": 1, "total_products": 1}


class _Analyzer:
    def __init__(
        self,
        strategy_name: str = "Complex",
        complexity: PageComplexity | None = None,
    ) -> None:
        self.strategy_name = strategy_name
        self.complexity = complexity or PageComplexity(
            has_region_filter=True,
            has_tabs=True,
            has_multiple_filters=True,
            interactive_elements=11,
        )
        self.determine_calls = 0
        self.complexity_calls = 0

    def determine_page_type_v3(self, soup: BeautifulSoup) -> str:
        self.determine_calls += 1
        return self.strategy_name

    def analyze_page_complexity(self, soup: BeautifulSoup) -> PageComplexity:
        self.complexity_calls += 1
        return self.complexity


class _ForbiddenAnalyzer:
    def determine_page_type_v3(self, soup: BeautifulSoup) -> str:
        raise AssertionError("semantic analysis must not run")

    def analyze_page_complexity(self, soup: BeautifulSoup) -> PageComplexity:
        raise AssertionError("semantic analysis must not run")


def _manager(
    definition: dict[str, Any], analyzer: object | None = None
) -> tuple[StrategyManager, _ProductManager]:
    product_manager = _ProductManager(definition)
    manager = StrategyManager(product_manager)  # type: ignore[arg-type]
    manager.page_analyzer = analyzer or _Analyzer()  # type: ignore[assignment]
    return manager, product_manager


def test_large_file_is_not_a_semantic_page_or_strategy_type() -> None:
    assert {item.value for item in PageType} == {
        "simple_static",
        "region_filter",
        "complex",
        "support_article",
    }
    assert {item.value for item in StrategyType} == {
        "simple_static",
        "region_filter",
        "complex",
        "support_article",
    }
    assert "file_size_mb" not in {item.name for item in fields(PageComplexity)}
    assert "is_large_file" not in {item.name for item in fields(PageComplexity)}
    assert "requires_large_file_optimization" not in {
        item.name for item in fields(ExtractionStrategy)
    }
    assert not hasattr(ProductManager, "is_large_html_product")


def test_factory_has_no_simple_fallback_constructor() -> None:
    assert not hasattr(StrategyFactory, "create_fallback_strategy")
    assert set(StrategyFactory._strategy_descriptions) == set(StrategyType)


def test_strategy_manager_accepts_parsed_html_not_a_file_path() -> None:
    parameters = inspect.signature(
        StrategyManager.determine_extraction_strategy
    ).parameters
    assert list(parameters) == ["self", "soup", "product_key", "input_bytes"]
    assert list(inspect.signature(PageAnalyzer.analyze_page_complexity).parameters) == [
        "self",
        "soup",
    ]

    manager, _ = _manager(
        {
            "page_model": "FlexibleContentPage",
            "extraction": {"semantic_strategy": "complex"},
        }
    )
    with pytest.raises(TypeError, match="parsed BeautifulSoup"):
        manager.determine_extraction_strategy("fixture.html", "fixture")  # type: ignore[arg-type]


def test_formal_extract_surface_has_no_arbitrary_input_override() -> None:
    parameters = inspect.signature(ExtractionCoordinator.coordinate_extraction).parameters
    assert "html_file_path" not in parameters
    assert "html_file" not in parameters

    parser = cli.create_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    extract_parser = subparsers.choices["extract"]
    assert "--html-file" not in extract_parser._option_string_actions
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(
        io.StringIO()
    ):
        with pytest.raises(SystemExit) as captured:
            parser.parse_args(
                [
                    "extract",
                    "service-bus",
                    "--language",
                    "zh-cn",
                    "--html-file",
                    "fixture.html",
                ]
            )
    assert captured.value.code != 0


def test_support_article_and_configured_strategy_take_priority() -> None:
    support, _ = _manager(
        {
            "page_model": "SupportArticlePage",
            "support_article_type": "ICP",
            "extraction": {"semantic_strategy": "support_article"},
        },
        _ForbiddenAnalyzer(),
    )
    support_strategy = support.determine_extraction_strategy(_soup(), "fixture")
    assert support_strategy.strategy_type is StrategyType.SUPPORT_ARTICLE

    configured, _ = _manager(
        {
            "page_model": "FlexibleContentPage",
            "extraction": {"semantic_strategy": "region_filter"},
        },
        _ForbiddenAnalyzer(),
    )
    configured_strategy = configured.determine_extraction_strategy(
        _soup(), "fixture", input_bytes=10_000_000
    )
    assert configured_strategy.strategy_type is StrategyType.REGION_FILTER


def test_input_bytes_is_diagnostic_only() -> None:
    manager, _ = _manager(
        {
            "page_model": "FlexibleContentPage",
            "extraction": {"semantic_strategy": "complex"},
        },
        _ForbiddenAnalyzer(),
    )
    small = manager.determine_extraction_strategy(
        _soup(), "fixture", input_bytes=1
    )
    large = manager.determine_extraction_strategy(
        _soup(), "fixture", input_bytes=100_000_000
    )
    assert small == large
    assert small.strategy_type is StrategyType.COMPLEX

    with pytest.raises(ValueError, match="non-negative integer"):
        manager.determine_extraction_strategy(_soup(), "fixture", input_bytes=-1)


def test_product_definition_errors_propagate_without_analysis() -> None:
    class _BrokenProductManager:
        def get_product_config(self, product_key: str) -> dict[str, Any]:
            raise RuntimeError("catalog boom")

    manager = StrategyManager(_BrokenProductManager())  # type: ignore[arg-type]
    manager.page_analyzer = _ForbiddenAnalyzer()  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="catalog boom"):
        manager.determine_extraction_strategy(_soup(), "fixture")


@pytest.mark.parametrize(
    ("definition", "message"),
    [
        ({"page_model": "UnknownPage"}, "Unknown Product Definition page_model"),
        (
            {
                "page_model": "FlexibleContentPage",
                "extraction": {"semantic_strategy": "unknown_strategy"},
            },
            "must declare a known semantic_strategy",
        ),
        (
            {"page_model": "FlexibleContentPage"},
            "must declare a known semantic_strategy",
        ),
        (
            {
                "page_model": "SupportArticlePage",
                "support_article_type": "ICP",
                "extraction": {"semantic_strategy": "complex"},
            },
            "must declare semantic_strategy=support_article",
        ),
    ],
)
def test_unknown_product_definition_values_fail_closed(
    definition: dict[str, Any], message: str
) -> None:
    manager, _ = _manager(definition, _ForbiddenAnalyzer())
    with pytest.raises(ValueError, match=message):
        manager.determine_extraction_strategy(_soup(), "fixture")


@pytest.mark.parametrize(
    ("semantic_strategy", "expected"),
    [
        ("simple_static", StrategyType.SIMPLE_STATIC),
        ("region_filter", StrategyType.REGION_FILTER),
        ("complex", StrategyType.COMPLEX),
    ],
)
def test_formal_selection_uses_only_the_frozen_semantic_strategy(
    semantic_strategy: str, expected: StrategyType
) -> None:
    manager, _ = _manager(
        {
            "page_model": "FlexibleContentPage",
            "extraction": {"semantic_strategy": semantic_strategy},
        },
        _ForbiddenAnalyzer(),
    )
    assert (
        manager.determine_extraction_strategy(_soup(), "fixture").strategy_type
        is expected
    )


def test_preselected_strategy_cannot_override_product_definition() -> None:
    manager, _ = _manager(
        {
            "page_model": "FlexibleContentPage",
            "extraction": {"semantic_strategy": "complex"},
        },
        _ForbiddenAnalyzer(),
    )
    coordinator = object.__new__(ExtractionCoordinator)
    coordinator.strategy_manager = manager

    with pytest.raises(ValueError, match="differs from the Product Definition"):
        coordinator._resolve_strategy(
            StrategyType.SIMPLE_STATIC,
            _soup(),
            "fixture",
            input_bytes=100,
        )


def test_unknown_page_type_does_not_select_simple() -> None:
    manager, product_manager = _manager(
        {
            "page_model": "FlexibleContentPage",
            "extraction": {"semantic_strategy": "complex"},
        }
    )
    with pytest.raises(ValueError, match="Unknown semantic page type"):
        manager._select_strategy_by_page_type(object(), "fixture", None)  # type: ignore[arg-type]
    assert product_manager.calls == 0


def test_priority_features_have_a_stable_semantic_order() -> None:
    manager, _ = _manager(
        {
            "page_model": "FlexibleContentPage",
            "extraction": {"semantic_strategy": "complex"},
        }
    )
    complexity = PageComplexity(
        has_region_filter=True,
        has_tabs=True,
        has_multiple_filters=True,
        interactive_elements=11,
    )
    assert manager._determine_priority_features(
        complexity, StrategyType.COMPLEX
    ) == [
        "区域处理",
        "Tab处理",
        "多筛选器处理",
        "交互元素处理",
        "Tab结构解析",
        "复合内容提取",
        "动态筛选器配置",
    ]


def test_extraction_strategy_rejects_page_type_mismatch() -> None:
    with pytest.raises(ValueError, match="must match"):
        ExtractionStrategy(
            strategy_type=StrategyType.COMPLEX,
            processor="ComplexContentProcessor",
            recommended_page_type=PageType.SIMPLE_STATIC,
        )
