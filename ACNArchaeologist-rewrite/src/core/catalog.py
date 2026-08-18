"""Read reference Product Definitions and build a deterministic processing list."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


LANGUAGES = ("zh-cn", "en-us")
PAGE_MODELS = {"FlexibleContentPage", "SupportArticlePage"}
SEMANTIC_STRATEGIES = {
    "simple_static",
    "region_filter",
    "complex",
    "support_article",
}
SUPPORT_ARTICLE_TYPES = {"SLA", "LEGAL", "ICP", "PSR"}
PRODUCT_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class CatalogError(ValueError):
    """The reference catalog or processing scope is invalid."""


class UnknownProductError(CatalogError):
    """A requested product does not exist in the current processing scope."""


class UnknownCategoryError(CatalogError):
    """A requested category has no products in the current processing scope."""


@dataclass(frozen=True)
class ProductSource:
    """One language-specific source declared by a Product Definition."""

    language: str
    snapshot_path: str
    url: str | None


@dataclass(frozen=True)
class ProductDefinition:
    """The small, validated subset of a reference Product Definition we use."""

    product_key: str
    display_name: str
    slug: str
    page_model: str
    catalog_categories: tuple[str, ...]
    support_article_type: str | None
    semantic_strategy: str
    page_global_source_boundary: str | None
    sources: tuple[ProductSource, ...]
    config_path: Path

    @property
    def content_family(self) -> str:
        return "pricing" if self.page_model == "FlexibleContentPage" else "support-article"

    @property
    def selectable_categories(self) -> tuple[str, ...]:
        if self.content_family == "pricing":
            return self.catalog_categories
        assert self.support_article_type is not None
        return (self.support_article_type.lower(),)

    def source_for(self, language: str) -> ProductSource:
        for source in self.sources:
            if source.language == language:
                return source
        raise CatalogError(
            f"产品 {self.product_key} 没有声明 {language} 源文件；中英文必须同时存在。"
        )

    def frozen_relative_path(self, language: str) -> PurePosixPath:
        if self.content_family == "pricing":
            return PurePosixPath(language, "pricing", f"{self.product_key}.html")

        assert self.support_article_type is not None
        return PurePosixPath(
            language,
            "support-articles",
            self.support_article_type,
            f"{self.product_key}.html",
        )


@dataclass(frozen=True)
class ProcessingItem:
    """One language of one selected product."""

    product_key: str
    display_name: str
    language: str
    page_model: str
    semantic_strategy: str
    source_relative_path: PurePosixPath
    frozen_relative_path: PurePosixPath

    def as_dict(self) -> dict[str, str]:
        return {
            "product_key": self.product_key,
            "display_name": self.display_name,
            "language": self.language,
            "page_model": self.page_model,
            "semantic_strategy": self.semantic_strategy,
            "source_relative_path": self.source_relative_path.as_posix(),
            "frozen_relative_path": self.frozen_relative_path.as_posix(),
        }


class ProductCatalog:
    """Validated reference catalog restricted by the rewrite processing scope."""

    def __init__(
        self,
        project_root: Path,
        definitions: dict[str, ProductDefinition],
        scope_product_keys: tuple[str, ...],
        languages: tuple[str, ...],
        strategy_overrides: dict[str, str] | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.definitions = definitions
        self.scope_product_keys = scope_product_keys
        self.languages = languages
        self.strategy_overrides = dict(strategy_overrides or {})

    @classmethod
    def load(cls, project_root: Path | str) -> "ProductCatalog":
        root = Path(project_root).resolve()
        config_root = root / "data" / "configs"
        product_root = config_root / "products-config"
        locations = (
            (product_root / "pricing", "pricing"),
            (product_root / "support-articles", "support-article"),
        )

        definitions: dict[str, ProductDefinition] = {}
        for directory, content_family in locations:
            if not directory.is_dir():
                raise CatalogError(f"参考产品配置目录不存在：{directory}")
            for config_path in sorted(directory.glob("*.json")):
                definition = _read_product_definition(config_path, content_family)
                previous = definitions.get(definition.product_key)
                if previous is not None:
                    raise CatalogError(
                        "Product Key 重复："
                        f"{definition.product_key} 同时出现在 {previous.config_path} "
                        f"和 {definition.config_path}。"
                    )
                definitions[definition.product_key] = definition

        if not definitions:
            raise CatalogError(f"没有在 {product_root} 找到参考产品配置。")

        scope_path = config_root / "processing-scope.json"
        scope_data = _read_json_object(scope_path)
        languages = _read_scope_languages(scope_data, scope_path)
        product_keys = _read_scope_product_keys(scope_data, scope_path)
        strategy_overrides = _read_scope_strategy_overrides(
            scope_data,
            scope_path,
            product_keys=product_keys,
            definitions=definitions,
        )

        missing = [key for key in product_keys if key not in definitions]
        if missing:
            raise CatalogError(
                f"处理范围引用了不存在的 Product Key：{', '.join(missing)}。"
            )

        return cls(
            root,
            definitions,
            product_keys,
            languages,
            strategy_overrides,
        )

    def get_definition(self, product_key: str) -> ProductDefinition:
        definition = self.definitions.get(product_key)
        if definition is None:
            raise UnknownProductError(f"未知 Product Key：{product_key}。")
        return definition

    def effective_strategy(self, product_key: str) -> str:
        definition = self.get_definition(product_key)
        return self.strategy_overrides.get(product_key, definition.semantic_strategy)

    @property
    def available_categories(self) -> tuple[str, ...]:
        categories: set[str] = set()
        for product_key in self.scope_product_keys:
            categories.update(self.definitions[product_key].selectable_categories)
        return tuple(sorted(categories))

    def select(
        self,
        *,
        product_key: str | None = None,
        category: str | None = None,
        all_products: bool = False,
    ) -> tuple[ProcessingItem, ...]:
        """Select products and always expand each one to both configured languages."""

        selected_option_count = sum(
            (product_key is not None, category is not None, all_products)
        )
        if selected_option_count != 1:
            raise CatalogError("必须且只能选择 product、category 或 all 中的一种范围。")

        if product_key is not None:
            if product_key not in self.definitions:
                raise UnknownProductError(f"未知 Product Key：{product_key}。")
            if product_key not in self.scope_product_keys:
                raise UnknownProductError(
                    f"产品 {product_key} 不在当前重写处理范围中。"
                )
            selected_keys = (product_key,)
        elif category is not None:
            normalized_category = category.strip().lower()
            if not normalized_category:
                raise UnknownCategoryError("Category 不能为空。")
            selected_keys = tuple(
                key
                for key in self.scope_product_keys
                if normalized_category
                in self.definitions[key].selectable_categories
            )
            if not selected_keys:
                available = ", ".join(self.available_categories)
                raise UnknownCategoryError(
                    f"当前处理范围中没有 Category {category}；可选值：{available}。"
                )
        else:
            selected_keys = self.scope_product_keys

        items: list[ProcessingItem] = []
        for key in selected_keys:
            definition = self.definitions[key]
            for language in self.languages:
                source = definition.source_for(language)
                items.append(
                    ProcessingItem(
                        product_key=key,
                        display_name=definition.display_name,
                        language=language,
                        page_model=definition.page_model,
                        semantic_strategy=self.effective_strategy(key),
                        source_relative_path=PurePosixPath(
                            language, *PurePosixPath(source.snapshot_path).parts
                        ),
                        frozen_relative_path=definition.frozen_relative_path(language),
                    )
                )
        return tuple(items)


def _read_product_definition(
    config_path: Path, content_family: str
) -> ProductDefinition:
    data = _read_json_object(config_path)

    product_key = _required_string(data, "product_key", config_path)
    if not PRODUCT_KEY_PATTERN.fullmatch(product_key):
        raise CatalogError(
            f"{config_path} 的 product_key 不是小写字母、数字和连字符组成的可读名称。"
        )
    if config_path.stem != product_key:
        raise CatalogError(
            f"配置文件名 {config_path.name} 与 Product Key {product_key} 不一致。"
        )

    display_name = _required_string(data, "display_name", config_path)
    slug = _required_string(data, "slug", config_path)
    page_model = _required_string(data, "page_model", config_path)
    if page_model not in PAGE_MODELS:
        raise CatalogError(f"{config_path} 使用未知页面类型：{page_model}。")

    extraction = data.get("extraction")
    if not isinstance(extraction, dict):
        raise CatalogError(f"{config_path} 缺少 extraction 配置。")
    semantic_strategy = _required_string(
        extraction, "semantic_strategy", config_path
    )
    if semantic_strategy not in SEMANTIC_STRATEGIES:
        raise CatalogError(f"{config_path} 使用未知 Strategy：{semantic_strategy}。")

    page_global_source_boundary: str | None = None
    page_global_content = extraction.get("page_global_content")
    if page_global_content is not None:
        if not isinstance(page_global_content, dict):
            raise CatalogError(f"{config_path} 的 page_global_content 必须是对象。")
        page_global_source_boundary = _required_string(
            page_global_content, "source_boundary", config_path
        )

    support_article_type: str | None = None
    catalog_categories: tuple[str, ...]
    if content_family == "pricing":
        if page_model != "FlexibleContentPage":
            raise CatalogError(f"Pricing 配置 {config_path} 的页面类型必须是 FlexibleContentPage。")
        if semantic_strategy == "support_article":
            raise CatalogError(f"Pricing 配置 {config_path} 不能使用 support_article Strategy。")
        catalog_categories = _required_string_list(
            data, "catalog_categories", config_path
        )
    else:
        if page_model != "SupportArticlePage":
            raise CatalogError(
                f"Support Article 配置 {config_path} 的页面类型必须是 SupportArticlePage。"
            )
        if semantic_strategy != "support_article":
            raise CatalogError(
                f"Support Article 配置 {config_path} 必须使用 support_article Strategy。"
            )
        support_article_type = _required_string(
            data, "support_article_type", config_path
        )
        if support_article_type not in SUPPORT_ARTICLE_TYPES:
            raise CatalogError(
                f"{config_path} 使用未知 Support Article 类型：{support_article_type}。"
            )
        catalog_categories = ()

    sources_data = data.get("sources")
    if not isinstance(sources_data, dict):
        raise CatalogError(f"{config_path} 缺少 sources 配置。")
    sources: list[ProductSource] = []
    for language in LANGUAGES:
        source_data = sources_data.get(language)
        if not isinstance(source_data, dict):
            raise CatalogError(
                f"{config_path} 缺少 {language} 源配置；中英文必须同时声明。"
            )
        snapshot_path = _required_string(source_data, "snapshot_path", config_path)
        _validate_snapshot_path(snapshot_path, config_path, language)
        url_value = source_data.get("url")
        if url_value is not None and not isinstance(url_value, str):
            raise CatalogError(f"{config_path} 的 {language} url 必须是文本。")
        sources.append(ProductSource(language, snapshot_path, url_value))

    return ProductDefinition(
        product_key=product_key,
        display_name=display_name,
        slug=slug,
        page_model=page_model,
        catalog_categories=catalog_categories,
        support_article_type=support_article_type,
        semantic_strategy=semantic_strategy,
        page_global_source_boundary=page_global_source_boundary,
        sources=tuple(sources),
        config_path=config_path,
    )


def _read_scope_languages(data: dict[str, Any], path: Path) -> tuple[str, ...]:
    languages = _required_string_list(data, "languages", path)
    if languages != LANGUAGES:
        raise CatalogError(
            f"{path} 的 languages 必须按顺序明确写为 zh-cn、en-us。"
        )
    return languages


def _read_scope_product_keys(data: dict[str, Any], path: Path) -> tuple[str, ...]:
    product_keys = _required_string_list(data, "product_keys", path)
    if product_keys != tuple(sorted(product_keys)):
        raise CatalogError(f"{path} 的 product_keys 必须按 Product Key 排序。")
    return product_keys


def _read_scope_strategy_overrides(
    data: dict[str, Any],
    path: Path,
    *,
    product_keys: tuple[str, ...],
    definitions: dict[str, ProductDefinition],
) -> dict[str, str]:
    value = data.get("strategy_overrides", {})
    if not isinstance(value, dict):
        raise CatalogError(f"{path} 的 strategy_overrides 必须是对象。")
    result: dict[str, str] = {}
    for product_key, decision in value.items():
        if product_key not in product_keys or product_key not in definitions:
            raise CatalogError(
                f"{path} 的 Strategy 决定引用了范围外产品：{product_key}。"
            )
        if not isinstance(decision, dict):
            raise CatalogError(
                f"{path} 的 {product_key} Strategy 决定必须是对象。"
            )
        strategy = _required_string(decision, "strategy", path)
        reason = _required_string(decision, "reason", path)
        del reason
        if strategy not in SEMANTIC_STRATEGIES or strategy == "support_article":
            raise CatalogError(
                f"{path} 的 {product_key} 使用无效 Pricing Strategy：{strategy}。"
            )
        if definitions[product_key].page_model != "FlexibleContentPage":
            raise CatalogError(
                f"{path} 不能覆盖 Support Article {product_key} 的 Strategy。"
            )
        result[product_key] = strategy
    return result


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as error:
        raise CatalogError(f"配置文件不存在：{path}") from error
    except UnicodeDecodeError as error:
        raise CatalogError(f"配置文件不是有效 UTF-8：{path}") from error
    except json.JSONDecodeError as error:
        raise CatalogError(
            f"配置文件不是有效 JSON：{path}（第 {error.lineno} 行）。"
        ) from error
    except OSError as error:
        raise CatalogError(f"无法读取配置文件 {path}：{error}") from error

    if not isinstance(data, dict):
        raise CatalogError(f"配置文件顶层必须是对象：{path}")
    return data


def _required_string(data: dict[str, Any], field: str, path: Path) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{path} 缺少非空文本字段 {field}。")
    return value


def _required_string_list(
    data: dict[str, Any], field: str, path: Path
) -> tuple[str, ...]:
    value = data.get(field)
    if not isinstance(value, list) or not value:
        raise CatalogError(f"{path} 缺少非空列表字段 {field}。")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise CatalogError(f"{path} 的 {field} 只能包含非空文本。")
    if len(value) != len(set(value)):
        raise CatalogError(f"{path} 的 {field} 包含重复值。")
    return tuple(value)


def _validate_snapshot_path(path_value: str, config_path: Path, language: str) -> None:
    if "\\" in path_value:
        raise CatalogError(
            f"{config_path} 的 {language} snapshot_path 必须使用正斜杠。"
        )
    path = PurePosixPath(path_value)
    if path.is_absolute() or ".." in path.parts or path_value in {"", "."}:
        raise CatalogError(
            f"{config_path} 的 {language} snapshot_path 不能是绝对路径或越出输入目录："
            f"{path_value}。"
        )
