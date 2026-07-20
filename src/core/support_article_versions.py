"""Explicit identities, paths and routes for publishable historical SLA versions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from src.utils.html.url_rewriter import normalize_route_path


def historical_versions(definition: dict[str, Any]) -> list[dict[str, Any]]:
    return list(definition.get("historical_versions", []))


def get_historical_version(definition: dict[str, Any], version_key: str) -> dict[str, Any]:
    for version in historical_versions(definition):
        if version["version_key"] == version_key:
            return version
    raise ValueError(f"Historical SLA version does not exist: {definition['product_key']}--{version_key}")


def available_historical_versions(
    definition: dict[str, Any],
    language: str,
) -> Iterable[dict[str, Any]]:
    return (
        version
        for version in historical_versions(definition)
        if version["sources"][language]["availability"] == "available"
    )


def historical_resource_key(product_key: str, version_key: str) -> str:
    return f"{product_key}--{version_key}"


def historical_normalized_input_path(
    root: Path,
    definition: dict[str, Any],
    language: str,
    version_key: str,
) -> Path:
    if definition.get("support_article_type") != "SLA":
        raise ValueError("Historical versions are only supported for SLA Product Definitions")
    resource_key = historical_resource_key(definition["product_key"], version_key)
    return root / "data" / "prod-html" / language / "SupportArticles" / "SLA" / f"{resource_key}.html"


def build_support_url_route_map(definition: dict[str, Any], language: str) -> dict[str, str]:
    """Return explicit source URL -> CMS path mappings for one product-language."""
    routes: dict[str, str] = {}
    current = definition["sources"][language]
    if current["availability"] == "available" and current.get("cms_path"):
        routes[normalize_route_path(current["url"])] = current["cms_path"]
    for version in available_historical_versions(definition, language):
        source = version["sources"][language]
        routes[normalize_route_path(source["url"])] = source["cms_path"]
        for alias in source.get("url_aliases", []):
            routes[normalize_route_path(alias)] = source["cms_path"]
    return routes
