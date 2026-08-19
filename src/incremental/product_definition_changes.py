"""Readable comparison of Product Definition fields that affect processing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.catalog import ProductCatalog


class ProductDefinitionChangeError(RuntimeError):
    """The accepted Product Definition projection cannot be compared."""


@dataclass(frozen=True)
class ProductDefinitionChange:
    product_key: str
    changed_fields: tuple[str, ...]
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "product_key": self.product_key,
            "changed_fields": list(self.changed_fields),
            "reasons": list(self.reasons),
        }


def build_product_definition_baseline(
    catalog: ProductCatalog,
    *,
    source_run_name: str,
) -> dict[str, object]:
    """Build the human-readable processing projection stored as a baseline."""

    return {
        "schema_version": "1.0",
        "source_run_name": source_run_name,
        "ignored_fields": [
            "capability_status",
            "display_name",
            "slug",
            "catalog_categories",
        ],
        "products": [
            _current_projection(catalog, product_key)
            for product_key in catalog.scope_product_keys
        ],
    }


def compare_product_definitions(
    catalog: ProductCatalog,
    *,
    baseline_path: Path | None = None,
) -> tuple[ProductDefinitionChange, ...]:
    """Compare only source location and extraction-shaping fields."""

    path = (
        baseline_path
        if baseline_path is not None
        else catalog.project_root / "data" / "state" / "product-definitions.json"
    ).resolve()
    if path.is_symlink() or not path.is_file():
        raise ProductDefinitionChangeError(
            f"Product Definition 对比基准不存在或不是普通文件：{path}。"
        )
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProductDefinitionChangeError(
            f"无法读取 Product Definition 对比基准 {path}：{error}"
        ) from error
    if not isinstance(value, dict) or value.get("schema_version") != "1.0":
        raise ProductDefinitionChangeError("Product Definition 对比基准版本无效。")
    products = value.get("products")
    if products is None:
        source_manifest = value.get("source_run_manifest")
        if not isinstance(source_manifest, str) or not source_manifest:
            raise ProductDefinitionChangeError(
                "Product Definition 对比基准缺少产品列表或来源 Batch。"
            )
        products = _products_from_run_manifest(
            catalog,
            baseline_path=path,
            source_manifest=source_manifest,
        )
    if not isinstance(products, list):
        raise ProductDefinitionChangeError("Product Definition 对比基准缺少产品列表。")
    previous_by_key: dict[str, dict[str, Any]] = {}
    for row in products:
        if not isinstance(row, dict) or not isinstance(row.get("product_key"), str):
            raise ProductDefinitionChangeError(
                "Product Definition 对比基准包含无效产品记录。"
            )
        product_key = row["product_key"]
        if product_key in previous_by_key:
            raise ProductDefinitionChangeError(
                f"Product Definition 对比基准重复声明 {product_key}。"
            )
        previous_by_key[product_key] = row

    expected_keys = set(catalog.scope_product_keys)
    actual_keys = set(previous_by_key)
    if expected_keys != actual_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        details: list[str] = []
        if missing:
            details.append("缺少 " + "、".join(missing))
        if extra:
            details.append("多出 " + "、".join(extra))
        raise ProductDefinitionChangeError(
            "Product Definition 对比基准的产品范围与当前范围不一致："
            + "；".join(details)
            + "。"
        )

    changes: list[ProductDefinitionChange] = []
    for product_key in catalog.scope_product_keys:
        previous = previous_by_key[product_key]
        current = _current_projection(catalog, product_key)
        changed_fields: list[str] = []
        reasons: list[str] = []
        for field, label in (
            ("page_model", "页面类型"),
            ("semantic_strategy", "Strategy"),
            ("sources", "中英文源路径"),
        ):
            if previous.get(field) == current.get(field):
                continue
            changed_fields.append(field)
            reasons.append(
                f"{label}由 {previous.get(field)!r} 变为 {current.get(field)!r}。"
            )
        if changed_fields:
            changes.append(
                ProductDefinitionChange(
                    product_key=product_key,
                    changed_fields=tuple(changed_fields),
                    reasons=tuple(reasons),
                )
            )
    return tuple(changes)


def _current_projection(
    catalog: ProductCatalog,
    product_key: str,
) -> dict[str, object]:
    definition = catalog.get_definition(product_key)
    return {
        "product_key": product_key,
        "page_model": definition.page_model,
        "semantic_strategy": catalog.effective_strategy(product_key),
        "sources": {
            language: definition.source_for(language).snapshot_path
            for language in catalog.languages
        },
    }


def _products_from_run_manifest(
    catalog: ProductCatalog,
    *,
    baseline_path: Path,
    source_manifest: str,
) -> list[dict[str, object]]:
    relative = Path(source_manifest)
    if relative.is_absolute() or ".." in relative.parts:
        raise ProductDefinitionChangeError(
            "Product Definition 来源 Batch 路径必须位于项目内。"
        )
    manifest_path = catalog.project_root.joinpath(*relative.parts).resolve()
    try:
        manifest_path.relative_to(catalog.project_root)
    except ValueError as error:
        raise ProductDefinitionChangeError(
            "Product Definition 来源 Batch 路径越出项目目录。"
        ) from error
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ProductDefinitionChangeError(
            f"Product Definition 来源 Batch 不存在：{manifest_path}。"
        )
    try:
        manifest: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProductDefinitionChangeError(
            f"无法读取 Product Definition 来源 Batch {manifest_path}：{error}"
        ) from error
    if not isinstance(manifest, dict) or not isinstance(manifest.get("items"), list):
        raise ProductDefinitionChangeError(
            f"Product Definition 来源 Batch 无效：{baseline_path}。"
        )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in manifest["items"]:
        if not isinstance(row, dict) or not isinstance(row.get("product_key"), str):
            raise ProductDefinitionChangeError("来源 Batch 包含无效处理项。")
        grouped.setdefault(row["product_key"], []).append(row)
    products: list[dict[str, object]] = []
    for product_key in catalog.scope_product_keys:
        rows = grouped.get(product_key, [])
        if [row.get("language") for row in rows] != list(catalog.languages):
            raise ProductDefinitionChangeError(
                f"来源 Batch 中 {product_key} 不是完整且有序的中英文计划。"
            )
        page_models = {row.get("page_model") for row in rows}
        strategies = {row.get("semantic_strategy") for row in rows}
        if len(page_models) != 1 or len(strategies) != 1:
            raise ProductDefinitionChangeError(
                f"来源 Batch 中 {product_key} 的页面类型或 Strategy 不一致。"
            )
        sources: dict[str, str] = {}
        for row in rows:
            language = str(row["language"])
            source_relative = row.get("source_relative_path")
            if not isinstance(source_relative, str):
                raise ProductDefinitionChangeError(
                    f"来源 Batch 中 {product_key}/{language} 缺少源路径。"
                )
            parts = Path(source_relative).parts
            if not parts or parts[0] != language:
                raise ProductDefinitionChangeError(
                    f"来源 Batch 中 {product_key}/{language} 的源路径无效。"
                )
            sources[language] = Path(*parts[1:]).as_posix()
        products.append(
            {
                "product_key": product_key,
                "page_model": next(iter(page_models)),
                "semantic_strategy": next(iter(strategies)),
                "sources": sources,
            }
        )
    extra = sorted(set(grouped) - set(catalog.scope_product_keys))
    if extra:
        raise ProductDefinitionChangeError(
            "来源 Batch 包含范围外产品：" + "、".join(extra) + "。"
        )
    return products


__all__ = [
    "ProductDefinitionChange",
    "ProductDefinitionChangeError",
    "build_product_definition_baseline",
    "compare_product_definitions",
]
