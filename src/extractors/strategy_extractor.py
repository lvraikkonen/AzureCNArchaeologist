"""Production extraction adapter for the four copied core Strategies."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from src.core.catalog import ProcessingItem, ProductCatalog, ProductDefinition
from src.core.soft_category import SoftCategoryLookup, SoftCategoryUsageRecorder
from src.core.payload_contract import (
    validate_pricing_payload,
    validate_support_article_payload,
)
from src.strategies.strategy_factory import StrategyFactory
from src.utils.html.normalization import parse_html_bytes


class ExtractionError(RuntimeError):
    """Production extraction cannot safely produce a Business Payload."""


@dataclass(frozen=True)
class ExtractionResult:
    """A Business Payload and its readable trusted-configuration usage."""

    payload: dict[str, Any]
    soft_category_lookups: tuple[SoftCategoryLookup, ...]


_ACTIVE_FROZEN_ROOT: ContextVar[Path | None] = ContextVar(
    "processing_frozen_root",
    default=None,
)
_ACTIVE_SOFT_CATEGORY_PATH: ContextVar[Path | None] = ContextVar(
    "processing_soft_category_path",
    default=None,
)


@contextmanager
def use_processing_inputs(
    *,
    frozen_root: Path,
    soft_category_path: Path,
) -> Iterator[None]:
    """Use one Batch's fixed inputs inside the current worker thread."""

    frozen_token = _ACTIVE_FROZEN_ROOT.set(frozen_root.resolve())
    soft_token = _ACTIVE_SOFT_CATEGORY_PATH.set(soft_category_path.resolve())
    try:
        yield
    finally:
        _ACTIVE_SOFT_CATEGORY_PATH.reset(soft_token)
        _ACTIVE_FROZEN_ROOT.reset(frozen_token)


def extract_processing_item(
    catalog: ProductCatalog,
    item: ProcessingItem,
    *,
    frozen_root: Path | str | None = None,
    soft_category_path: Path | str | None = None,
) -> dict[str, Any]:
    return _extract_processing_item(
        catalog,
        item,
        frozen_root=frozen_root,
        soft_category_path=soft_category_path,
        usage_recorder=None,
    )


def extract_processing_item_with_usage(
    catalog: ProductCatalog,
    item: ProcessingItem,
    *,
    frozen_root: Path | str | None = None,
    soft_category_path: Path | str | None = None,
) -> ExtractionResult:
    """Extract once and retain every trusted mapping lookup, including misses."""

    recorder = SoftCategoryUsageRecorder()
    payload = _extract_processing_item(
        catalog,
        item,
        frozen_root=frozen_root,
        soft_category_path=soft_category_path,
        usage_recorder=recorder,
    )
    return ExtractionResult(payload, recorder.lookups)


def _extract_processing_item(
    catalog: ProductCatalog,
    item: ProcessingItem,
    *,
    frozen_root: Path | str | None,
    soft_category_path: Path | str | None,
    usage_recorder: SoftCategoryUsageRecorder | None,
) -> dict[str, Any]:
    definition = catalog.get_definition(item.product_key)
    selected_frozen_root = (
        Path(frozen_root)
        if frozen_root is not None
        else _ACTIVE_FROZEN_ROOT.get()
    )
    resolved_frozen_root = Path(
        selected_frozen_root
        if selected_frozen_root is not None
        else catalog.project_root / "data" / "prod-html"
    ).resolve()
    selected_soft_category_path = (
        Path(soft_category_path)
        if soft_category_path is not None
        else _ACTIVE_SOFT_CATEGORY_PATH.get()
    )
    source_path = resolved_frozen_root.joinpath(*item.frozen_relative_path.parts)
    try:
        source_path.resolve().relative_to(resolved_frozen_root)
    except ValueError as error:
        raise ExtractionError(
            f"Frozen HTML 路径越出规定目录：{item.frozen_relative_path.as_posix()}。"
        ) from error
    if source_path.is_symlink() or not source_path.is_file():
        raise ExtractionError(
            f"Frozen HTML 不存在或不是普通文件："
            f"{item.frozen_relative_path.as_posix()}。"
        )
    try:
        soup = parse_html_bytes(
            source_path.read_bytes(), source_name=str(source_path)
        )
    except OSError as error:
        raise ExtractionError(f"无法读取 Frozen HTML {source_path}：{error}") from error

    source = definition.source_for(item.language)
    if not source.url:
        raise ExtractionError(
            f"产品 {item.product_key} 的 {item.language} 参考配置缺少源 URL。"
        )
    try:
        strategy = StrategyFactory.create_strategy(
            item.semantic_strategy,
            _strategy_config(
                definition,
                semantic_strategy=item.semantic_strategy,
                language=item.language,
                project_root=catalog.project_root,
                soft_category_path=selected_soft_category_path,
                soft_category_lookup_recorder=(
                    usage_recorder.record if usage_recorder is not None else None
                ),
            ),
            str(source_path),
        )
        payload = strategy.extract_flexible_content(soup, source.url)
    except Exception as error:
        raise ExtractionError(
            f"{item.product_key}/{item.language} 生产 Strategy 抽取失败：{error}"
        ) from error
    if not isinstance(payload, dict):
        raise ExtractionError(
            f"{item.product_key}/{item.language} 生产 Strategy 没有返回对象。"
        )

    if definition.page_model == "FlexibleContentPage":
        validate_pricing_payload(
            payload,
            product_key=item.product_key,
            language=item.language,
            semantic_strategy=item.semantic_strategy,
        )
    else:
        if definition.support_article_type is None:
            raise ExtractionError(
                f"Support Article {item.product_key} 缺少文章类型。"
            )
        validate_support_article_payload(
            payload,
            product_key=item.product_key,
            expected_slug=definition.slug,
            support_article_type=definition.support_article_type,
        )
    return payload


def _strategy_config(
    definition: ProductDefinition,
    semantic_strategy: str | None = None,
    language: str | None = None,
    project_root: Path | None = None,
    soft_category_path: Path | str | None = None,
    soft_category_lookup_recorder: Any = None,
) -> dict[str, Any]:
    """Build fresh Strategy input without historical status or encoded evidence."""

    effective_strategy = semantic_strategy or definition.semantic_strategy
    config: dict[str, Any] = {
        "product_key": definition.product_key,
        "display_name": definition.display_name,
        "slug": definition.slug,
        "page_model": definition.page_model,
        "catalog_categories": list(definition.catalog_categories),
        "support_article_type": definition.support_article_type,
        "sources": {
            source.language: {
                "snapshot_path": source.snapshot_path,
                "url": source.url,
            }
            for source in definition.sources
        },
        "extraction": {
            "semantic_strategy": effective_strategy,
        },
    }
    if language is not None:
        config["language"] = language
    if definition.page_global_source_boundary is not None:
        config["extraction"]["page_global_content"] = {
            "source_boundary": definition.page_global_source_boundary,
        }
    if effective_strategy in {"region_filter", "complex"}:
        if project_root is None:
            raise ExtractionError(
                f"产品 {definition.product_key} 需要项目根目录读取可信区域配置。"
            )
        config["soft_category_path"] = str(
            Path(soft_category_path)
            if soft_category_path is not None
            else project_root / "data" / "configs" / "soft-category.json"
        )
        if soft_category_lookup_recorder is not None:
            config["soft_category_lookup_recorder"] = (
                soft_category_lookup_recorder
            )
    return config


__all__ = [
    "ExtractionError",
    "ExtractionResult",
    "extract_processing_item",
    "extract_processing_item_with_usage",
    "use_processing_inputs",
]
