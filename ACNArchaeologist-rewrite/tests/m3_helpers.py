from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.catalog import ProductCatalog
from src.core.payload_contract import payload_json_bytes
from src.extractors.strategy_extractor import extract_processing_item
from src.machine_checks.l3b import run_l3b
from tests.m2_helpers import PROJECT_ROOT, real_catalog


def product_item(product_key: str, language: str):
    return next(
        item
        for item in real_catalog().select(product_key=product_key)
        if item.language == language
    )


def product_payload(product_key: str, language: str = "zh-cn") -> dict[str, Any]:
    catalog = real_catalog()
    return extract_processing_item(catalog, product_item(product_key, language))


def product_source_path(product_key: str, language: str = "zh-cn") -> Path:
    item = product_item(product_key, language)
    return (PROJECT_ROOT / "data" / "prod-html").joinpath(
        *item.frozen_relative_path.parts
    )


def l3b_report(
    tmp_path: Path,
    *,
    product_key: str,
    language: str,
    payload: dict[str, Any],
    source_path: Path | None = None,
    soft_category_path: Path | None = None,
) -> dict[str, Any]:
    catalog: ProductCatalog = real_catalog()
    definition = catalog.get_definition(product_key)
    payload_path = tmp_path / f"{product_key}-{language}.json"
    payload_path.write_bytes(payload_json_bytes(payload))
    return run_l3b(
        frozen_html_path=source_path or product_source_path(product_key, language),
        payload_path=payload_path,
        product_key=product_key,
        language=language,
        page_model=definition.page_model,
        semantic_strategy=definition.semantic_strategy,
        soft_category_path=(
            soft_category_path
            or PROJECT_ROOT / "data" / "configs" / "soft-category.json"
        ),
        page_global_source_boundary=(
            definition.page_global_source_boundary
        ),
    )
