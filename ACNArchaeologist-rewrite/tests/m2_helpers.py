from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.catalog import ProductCatalog
from src.core.payload_contract import payload_json_bytes
from src.extractors.strategy_extractor import extract_processing_item


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def real_catalog() -> ProductCatalog:
    return ProductCatalog.load(PROJECT_ROOT)


def service_bus_item(language: str):
    return next(
        item
        for item in real_catalog().select(product_key="service-bus")
        if item.language == language
    )


def service_bus_payload(language: str = "zh-cn") -> dict[str, Any]:
    catalog = real_catalog()
    item = next(
        item
        for item in catalog.select(product_key="service-bus")
        if item.language == language
    )
    return extract_processing_item(catalog, item)


def service_bus_source_path(language: str = "zh-cn") -> Path:
    return PROJECT_ROOT / "data" / "prod-html" / language / "pricing" / "service-bus.html"


def write_payload(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload_json_bytes(payload))
    return path

