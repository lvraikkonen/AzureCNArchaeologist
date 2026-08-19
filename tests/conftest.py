from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any, Callable

import pytest


ProjectBuilder = Callable[[list[dict[str, Any]] | None], Path]


@pytest.fixture
def project_builder(tmp_path: Path) -> ProjectBuilder:
    build_number = 0

    def build(specifications: list[dict[str, Any]] | None = None) -> Path:
        nonlocal build_number
        build_number += 1
        project_root = tmp_path / f"project-{build_number}"
        pricing_config_root = (
            project_root / "data" / "configs" / "products-config" / "pricing"
        )
        support_config_root = (
            project_root
            / "data"
            / "configs"
            / "products-config"
            / "support-articles"
        )
        pricing_config_root.mkdir(parents=True)
        support_config_root.mkdir(parents=True)

        specs = specifications or [{"product_key": "sample-product"}]
        product_keys: list[str] = []
        for spec in specs:
            product_key = spec["product_key"]
            product_keys.append(product_key)
            support_type = spec.get("support_article_type")
            is_support = support_type is not None
            if is_support:
                snapshot_paths = spec.get(
                    "snapshot_paths",
                    {
                        language: f"SupportArticles/{support_type}/{product_key}/index.html"
                        for language in ("zh-cn", "en-us")
                    },
                )
                config = {
                    "schema_version": "1.1",
                    "product_key": product_key,
                    "display_name": spec.get("display_name", product_key),
                    "slug": product_key.removeprefix("sla-"),
                    "page_model": "SupportArticlePage",
                    "capability_status": spec.get(
                        "capability_status", "known_unsupported"
                    ),
                    "support_article_type": support_type,
                    "sources": {
                        language: {
                            "availability": "available",
                            "snapshot_path": snapshot_paths[language],
                            "url": f"https://example.invalid/{language}/{product_key}",
                        }
                        for language in ("zh-cn", "en-us")
                    },
                    "extraction": {"semantic_strategy": "support_article"},
                }
                config_path = support_config_root / f"{product_key}.json"
            else:
                snapshot_paths = spec.get(
                    "snapshot_paths",
                    {
                        language: f"pricing/details/{product_key}/index.html"
                        for language in ("zh-cn", "en-us")
                    },
                )
                config = {
                    "schema_version": "1.1",
                    "product_key": product_key,
                    "display_name": spec.get("display_name", product_key),
                    "slug": product_key,
                    "page_model": "FlexibleContentPage",
                    "capability_status": spec.get(
                        "capability_status", "known_unsupported"
                    ),
                    "catalog_categories": spec.get(
                        "catalog_categories", ["test-category"]
                    ),
                    "sources": {
                        language: {
                            "availability": "available",
                            "snapshot_path": snapshot_paths[language],
                            "url": f"https://example.invalid/{language}/{product_key}",
                        }
                        for language in ("zh-cn", "en-us")
                    },
                    "extraction": {
                        "semantic_strategy": spec.get(
                            "semantic_strategy", "simple_static"
                        )
                    },
                }
                config_path = pricing_config_root / f"{product_key}.json"

            config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            source_contents = spec.get(
                "source_contents",
                {
                    "zh-cn": f"<html>{product_key} 中文</html>".encode(),
                    "en-us": f"<html>{product_key} English</html>".encode(),
                },
            )
            for language, content in source_contents.items():
                relative = PurePosixPath(snapshot_paths[language])
                source_path = (
                    project_root
                    / "data"
                    / "current_prod_html"
                    / language
                ).joinpath(*relative.parts)
                source_path.parent.mkdir(parents=True, exist_ok=True)
                source_path.write_bytes(content)

        scope_path = project_root / "data" / "configs" / "processing-scope.json"
        scope_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "languages": ["zh-cn", "en-us"],
                    "product_keys": sorted(product_keys),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return project_root

    return build

