"""Product Definition v1 runtime access.

The generated Product Index is the lookup accelerator; Product Definitions remain the
authoritative source for identity, routing, extraction and quality settings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .product_catalog import ProductCatalog, artifact_relative_directory, normalized_input_path
from .settings import settings


class ProductManager:
    def __init__(self, config_dir: str | None = None) -> None:
        self.config_dir = Path(config_dir or settings.CONFIG_BASE_DIR).resolve()
        self.root = self.config_dir.parents[1]
        self._index: dict[str, Any] | None = None
        self._configs: dict[str, dict[str, Any]] = {}

    def load_products_index(self) -> dict[str, Any]:
        if self._index is None:
            path = self.config_dir / "products-index.json"
            self._index = json.loads(path.read_text(encoding="utf-8"))
            if self._index.get("schema_version") != "3.0":
                raise ValueError("products-index.json must be generated as Product Index 3.0")
        return self._index

    def get_all_product_keys(self) -> list[str]:
        return sorted(self.load_products_index()["products"])

    def get_supported_products(self) -> list[str]:
        return sorted(
            key for key, value in self.load_products_index()["products"].items()
            if value["capability_status"] == "supported"
        )

    def get_product_config(self, product_key: str) -> dict[str, Any]:
        if product_key in self._configs:
            return self._configs[product_key]
        item = self.load_products_index()["products"].get(product_key)
        if item is None:
            raise ValueError(f"Product Definition does not exist: {product_key}")
        path = self.config_dir / item["config_path"]
        definition = json.loads(path.read_text(encoding="utf-8"))
        self._configs[product_key] = definition
        return definition

    def require_supported(self, product_key: str) -> dict[str, Any]:
        definition = self.get_product_config(product_key)
        if definition["capability_status"] != "supported":
            raise ValueError(f"{product_key} is known unsupported: {definition['unsupported_reason']}")
        return definition

    def get_product_display_name(self, product_key: str) -> str:
        return self.get_product_config(product_key)["display_name"]

    def get_product_categories(self, product_key: str) -> list[str]:
        return list(self.get_product_config(product_key).get("catalog_categories", []))

    def get_product_category(self, product_key: str) -> Optional[str]:
        categories = self.get_product_categories(product_key)
        return categories[0] if categories else None

    def get_products_by_category(self, category: str | None = None) -> dict[str, list[str]]:
        views = self.load_products_index()["catalog_categories"]
        if category is not None:
            view = views.get(category)
            return {category: list(view["products"])} if view else {}
        return {key: list(value["products"]) for key, value in views.items()}

    def get_products_by_support_type(self, support_type: str | None = None) -> dict[str, list[str]]:
        views = self.load_products_index()["support_article_types"]
        if support_type is not None:
            view = views.get(support_type)
            return {support_type: list(view["products"])} if view else {}
        return {key: list(value["products"]) for key, value in views.items()}

    def get_source(self, product_key: str, language: str) -> dict[str, Any]:
        if language not in ("zh-cn", "en-us"):
            raise ValueError(f"Unsupported language: {language}")
        return self.get_product_config(product_key)["sources"][language]

    def get_product_url(self, product_key: str, language: str = "zh-cn") -> str:
        source = self.get_source(product_key, language)
        return source.get("url", "")

    def get_html_file_path(self, product_key: str, language: str = "zh-cn", html_base_dir: str | None = None) -> Optional[str]:
        definition = self.get_product_config(product_key)
        if html_base_dir is None:
            path = normalized_input_path(self.root, definition, language)
        else:
            base = Path(html_base_dir)
            relative = normalized_input_path(self.root, definition, language).relative_to(self.root / "data" / "prod-html")
            path = base / relative
        return str(path) if path.is_file() else None

    def get_output_directory(self, product_key: str, language: str = "zh-cn", output_base_dir: str | None = None) -> str:
        definition = self.get_product_config(product_key)
        base = Path(output_base_dir or settings.OUTPUT_BASE_DIR) / "payloads"
        return str(base / artifact_relative_directory(definition, language))

    def find_products_for_category(self, category: str, language: str = "zh-cn", html_base_dir: str | None = None) -> list[dict[str, str]]:
        found = []
        for product_key in self.get_products_by_category(category).get(category, []):
            definition = self.get_product_config(product_key)
            if definition["capability_status"] != "supported":
                continue
            html_path = self.get_html_file_path(product_key, language, html_base_dir)
            if html_path:
                found.append({
                    "product_key": product_key,
                    "category": category,
                    "language": language,
                    "html_path": html_path,
                    "output_dir": self.get_output_directory(product_key, language),
                })
        return found

    def get_all_available_products(self, language: str = "zh-cn", html_base_dir: str | None = None) -> list[dict[str, str]]:
        found: list[dict[str, str]] = []
        seen: set[str] = set()
        for category in self.get_products_by_category():
            for item in self.find_products_for_category(category, language, html_base_dir):
                if item["product_key"] not in seen:
                    seen.add(item["product_key"])
                    found.append(item)
        for support_type, products in self.get_products_by_support_type().items():
            for product_key in products:
                if product_key in seen or product_key not in self.get_supported_products():
                    continue
                html_path = self.get_html_file_path(product_key, language, html_base_dir)
                if html_path:
                    found.append({"product_key": product_key, "category": support_type, "language": language, "html_path": html_path, "output_dir": self.get_output_directory(product_key, language)})
                    seen.add(product_key)
        return found

    def get_important_section_titles(self, product_key: str) -> list[str]:
        return list(self.get_product_config(product_key).get("extraction", {}).get("important_section_titles", []))

    def get_extraction_config(self, product_key: str) -> dict[str, Any]:
        return dict(self.get_product_config(product_key).get("extraction", {}))

    def is_large_html_product(self, product_key: str) -> bool:
        return self.get_product_config(product_key).get("extraction", {}).get("processing_type") == "large_file"

    def clear_cache(self) -> None:
        self._index = None
        self._configs.clear()

    def get_cache_stats(self) -> dict[str, Any]:
        return {"cached_products": len(self._configs), "total_products": len(self.get_all_product_keys())}

    def validate_product_config(self, product_key: str) -> dict[str, Any]:
        try:
            ProductCatalog(self.root).load_definitions()
            self.get_product_config(product_key)
            return {"is_valid": True, "errors": [], "warnings": []}
        except Exception as error:
            return {"is_valid": False, "errors": [str(error)], "warnings": []}

    def get_all_validation_results(self) -> dict[str, dict[str, Any]]:
        return {key: self.validate_product_config(key) for key in self.get_all_product_keys()}
