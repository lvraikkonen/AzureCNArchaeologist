#!/usr/bin/env python3
"""Copy exact configured Source Snapshots into canonical normalized input paths."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path
from typing import Iterable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.product_catalog import LANGUAGES, normalized_input_path
from src.core.product_manager import ProductManager
from src.core.support_article_versions import (
    historical_normalized_input_path,
    historical_resource_key,
    historical_versions,
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class HTMLFileCopier:
    def __init__(self, base_dir: str = ".") -> None:
        self.root = Path(base_dir).resolve()
        self.raw_root = self.root / "data" / "current_prod_html"
        self.manager = ProductManager(str(self.root / "data" / "configs"))

    def select_products(
        self,
        products: Optional[Iterable[str]] = None,
        categories: Optional[Iterable[str]] = None,
        support_types: Optional[Iterable[str]] = None,
    ) -> list[str]:
        selected = set(products or [])
        for category in categories or []:
            selected.update(self.manager.get_products_by_category(category).get(category, []))
        for support_type in support_types or []:
            selected.update(self.manager.get_products_by_support_type(support_type).get(support_type, []))
        if not selected:
            selected.update(self.manager.get_supported_products())
        unknown = selected - set(self.manager.get_all_product_keys())
        if unknown:
            raise ValueError(f"Unknown Product Keys: {', '.join(sorted(unknown))}")
        return sorted(selected)

    def _copy_resource(
        self,
        resource_key: str,
        language: str,
        source: dict,
        target_path: Path,
    ) -> dict[str, str]:
        source_path = self.raw_root / language / source["snapshot_path"]
        if not source_path.is_file():
            raise FileNotFoundError(f"Configured Source Snapshot is missing: {source_path}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        source_hash = file_sha256(source_path)
        target_hash = file_sha256(target_path)
        if source_hash != target_hash:
            raise IOError(f"SHA-256 mismatch after copy: {source_path} -> {target_path}")
        return {
            "resource_key": resource_key,
            "language": language,
            "status": "copied",
            "source": str(source_path),
            "target": str(target_path),
            "sha256": source_hash,
        }

    def copy_product(self, product_key: str, language: str) -> dict:
        definition = self.manager.require_supported(product_key)
        source = definition["sources"][language]
        if source["availability"] != "available":
            return {"product_key": product_key, "language": language, "status": "skipped", "reason": source["unavailable_reason"]}
        primary = self._copy_resource(
            product_key,
            language,
            source,
            normalized_input_path(self.root, definition, language),
        )
        resources = [primary]
        for version in historical_versions(definition):
            version_source = version["sources"][language]
            resource_key = historical_resource_key(product_key, version["version_key"])
            if version_source["availability"] != "available":
                resources.append({
                    "resource_key": resource_key,
                    "language": language,
                    "status": "skipped",
                    "reason": version_source["unavailable_reason"],
                })
                continue
            resources.append(self._copy_resource(
                resource_key,
                language,
                version_source,
                historical_normalized_input_path(
                    self.root, definition, language, version["version_key"]
                ),
            ))
        return {
            "product_key": product_key,
            "language": language,
            "status": "copied",
            "source": primary["source"],
            "target": primary["target"],
            "sha256": primary["sha256"],
            "copied_files": sum(item["status"] == "copied" for item in resources),
            "resources": resources,
        }

    def run(
        self,
        language: str = "zh-cn",
        categories: Optional[Iterable[str]] = None,
        products: Optional[Iterable[str]] = None,
        support_types: Optional[Iterable[str]] = None,
    ) -> dict:
        if language not in LANGUAGES:
            raise ValueError(f"Unsupported language: {language}")
        results = []
        for product_key in self.select_products(products, categories, support_types):
            try:
                results.append(self.copy_product(product_key, language))
            except Exception as error:
                results.append({"product_key": product_key, "language": language, "status": "failed", "reason": str(error)})
        return {
            "language": language,
            "total_success": sum(item["status"] == "copied" for item in results),
            "total_skipped": sum(item["status"] == "skipped" for item in results),
            "total_fail": sum(item["status"] == "failed" for item in results),
            "total_files_copied": sum(item.get("copied_files", 0) for item in results),
            "results": results,
        }

    def run_both_languages(
        self,
        categories: Optional[Iterable[str]] = None,
        products: Optional[Iterable[str]] = None,
        support_types: Optional[Iterable[str]] = None,
    ) -> dict[str, dict]:
        return {
            language: self.run(language, categories, products, support_types)
            for language in LANGUAGES
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy configured snapshots to canonical normalized inputs")
    parser.add_argument("--language", choices=(*LANGUAGES, "both"), default="both")
    parser.add_argument("--product", action="append", help="Product Key; repeatable")
    parser.add_argument("--category", action="append", help="Catalog category; repeatable")
    parser.add_argument(
        "--support-type",
        action="append",
        choices=("SLA", "LEGAL", "ICP", "PSR"),
        help="Support Article Type; repeatable",
    )
    parser.add_argument("--base-dir", default=".")
    args = parser.parse_args()

    copier = HTMLFileCopier(args.base_dir)
    kwargs = {
        "categories": args.category,
        "products": args.product,
        "support_types": args.support_type,
    }
    results = (
        copier.run_both_languages(**kwargs)
        if args.language == "both"
        else {args.language: copier.run(args.language, **kwargs)}
    )
    failures = 0
    for language, result in results.items():
        failures += result["total_fail"]
        print(
            f"{language}: copied={result['total_success']} "
            f"files={result['total_files_copied']} "
            f"skipped={result['total_skipped']} failed={result['total_fail']}"
        )
        for item in result["results"]:
            if item["status"] == "failed":
                print(f"FAIL {item['product_key']}: {item['reason']}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
