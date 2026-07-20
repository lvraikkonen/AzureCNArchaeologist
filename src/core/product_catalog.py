"""Authoritative Product Definition loading, derived index building and snapshot audit."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker


LANGUAGES = ("zh-cn", "en-us")
SUPPORT_TYPE_DIRECTORIES = {
    "SLA": "SLA",
    "LEGAL": "Legal",
    "ICP": "ICP",
    "PSR": "PublicSecurityRegistration",
}


class CatalogError(RuntimeError):
    """Raised when Product Definitions or source accounting are inconsistent."""


@dataclass(frozen=True)
class ProductDefinitionRecord:
    product_key: str
    path: Path
    relative_path: str
    definition: dict[str, Any]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ProductCatalog:
    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()
        self.config_root = self.root / "data" / "configs"
        self.products_root = self.config_root / "products"
        self.index_path = self.config_root / "products-index.json"
        self.exclusions_path = self.config_root / "source-snapshot-exclusions.json"
        self.schema_root = self.root / "schemas"

    def load_definitions(self) -> dict[str, ProductDefinitionRecord]:
        schema = json.loads((self.schema_root / "product-definition-1.0.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        records: dict[str, ProductDefinitionRecord] = {}
        errors: list[str] = []
        primary_sources: dict[tuple[str, str], str] = {}
        all_sources: dict[tuple[str, str], str] = {}
        slugs: dict[tuple[str, str], str] = {}

        for path in sorted(self.products_root.glob("*/*.json")):
            definition = json.loads(path.read_text(encoding="utf-8"))
            relative = path.relative_to(self.config_root).as_posix()
            for error in sorted(validator.iter_errors(definition), key=lambda item: list(item.path)):
                location = "/".join(str(part) for part in error.absolute_path) or "$"
                errors.append(f"{relative}:{location}: {error.message}")
            product_key = definition.get("product_key", path.stem)
            if product_key in records:
                errors.append(f"duplicate product_key {product_key}: {records[product_key].relative_path}, {relative}")
                continue
            if path.stem != product_key:
                errors.append(f"{relative}: filename must equal product_key ({product_key}.json)")
            record = ProductDefinitionRecord(product_key, path, relative, definition)
            records[product_key] = record

            page_model = definition.get("page_model", "")
            slug_key = (page_model, definition.get("slug", ""))
            if slug_key in slugs:
                errors.append(f"duplicate slug in {page_model}: {slug_key[1]} ({slugs[slug_key]}, {product_key})")
            else:
                slugs[slug_key] = product_key

            for language, source in definition.get("sources", {}).items():
                if source.get("availability") != "available":
                    continue
                snapshot_path = source.get("snapshot_path", "")
                key = (language, snapshot_path)
                if key in primary_sources:
                    errors.append(f"duplicate primary source {language}/{snapshot_path}: {primary_sources[key]}, {product_key}")
                primary_sources[key] = product_key
                if key in all_sources:
                    errors.append(f"duplicate source route {language}/{snapshot_path}: {all_sources[key]}, {product_key}")
                all_sources[key] = product_key
                for alias in source.get("aliases", []):
                    alias_path = alias.get("snapshot_path", "")
                    alias_key = (language, alias_path)
                    if alias.get("canonical_product_key") != product_key:
                        errors.append(f"{relative}: alias {alias_path} canonical_product_key must be {product_key}")
                    if alias_key in all_sources:
                        errors.append(f"duplicate source route {language}/{alias_path}: {all_sources[alias_key]}, {product_key}")
                    all_sources[alias_key] = product_key

        if errors:
            raise CatalogError("Product Definition validation failed:\n- " + "\n- ".join(errors))
        return records

    def build_index(self) -> dict[str, Any]:
        self.validate_contract_lock()
        records = self.load_definitions()
        digest_input = "\n".join(
            f"{record.relative_path}\0{canonical_json(record.definition)}"
            for record in sorted(records.values(), key=lambda item: item.relative_path)
        )
        source_digest = "sha256:" + hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
        products: dict[str, Any] = {}
        category_members: dict[str, list[str]] = defaultdict(list)
        support_members: dict[str, list[str]] = defaultdict(list)

        for key, record in sorted(records.items()):
            definition = record.definition
            item: dict[str, Any] = {
                "config_path": record.relative_path,
                "page_model": definition["page_model"],
                "slug": definition["slug"],
                "capability_status": definition["capability_status"],
            }
            if definition["page_model"] == "FlexibleContentPage":
                categories = sorted(definition["catalog_categories"])
                item["catalog_categories"] = categories
                for category in categories:
                    category_members[category].append(key)
            else:
                support_type = definition["support_article_type"]
                item["support_article_type"] = support_type
                support_members[support_type].append(key)
            products[key] = item

        supported = sum(item["capability_status"] == "supported" for item in products.values())
        index = {
            "schema_version": "3.0",
            "source_digest": source_digest,
            "total_products": len(products),
            "supported_products": supported,
            "known_unsupported_products": len(products) - supported,
            "products": products,
            "catalog_categories": {
                key: {"count": len(values), "products": sorted(values)}
                for key, values in sorted(category_members.items())
            },
            "support_article_types": {
                key: {"count": len(values), "products": sorted(values)}
                for key, values in sorted(support_members.items())
            },
        }
        schema = json.loads((self.schema_root / "product-index-3.0.schema.json").read_text(encoding="utf-8"))
        schema_errors = sorted(Draft202012Validator(schema).iter_errors(index), key=lambda item: list(item.absolute_path))
        if schema_errors:
            raise CatalogError("Product Index schema validation failed:\n- " + "\n- ".join(error.message for error in schema_errors))
        return index

    def validate_contract_lock(self) -> None:
        lock_path = self.schema_root / "contracts.lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        errors = []
        for item in lock.get("upstream_contracts", []):
            path = self.root / item["path"]
            if not path.is_file():
                errors.append(f"missing upstream contract: {item['path']}")
            elif sha256_file(path) != item["sha256"]:
                errors.append(f"upstream contract digest changed: {item['path']}")
        if errors:
            raise CatalogError("Contract lock validation failed:\n- " + "\n- ".join(errors))

    def write_index(self, check: bool = False) -> tuple[bool, dict[str, Any]]:
        index = self.build_index()
        rendered = json.dumps(index, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
        current = self.index_path.read_text(encoding="utf-8") if self.index_path.exists() else ""
        changed = rendered != current
        if changed and not check:
            self.index_path.write_text(rendered, encoding="utf-8")
        return changed, index

    def audit_snapshots(self, languages: Iterable[str] = LANGUAGES) -> dict[str, Any]:
        records = self.load_definitions()
        explanations: dict[tuple[str, str], dict[str, str]] = {}
        duplicate_explanations: list[dict[str, str]] = []
        missing_primary: list[dict[str, str]] = []
        missing_aliases: list[dict[str, str]] = []
        normalized_input_issues: list[dict[str, str]] = []

        for key, record in records.items():
            for language, source in record.definition["sources"].items():
                if source["availability"] != "available":
                    continue
                raw_path = self.root / "data" / "current_prod_html" / language / source["snapshot_path"]
                if not raw_path.is_file():
                    missing_primary.append({"language": language, "snapshot_path": source["snapshot_path"], "product_key": key})
                if record.definition["capability_status"] == "supported":
                    normalized = normalized_input_path(self.root, record.definition, language)
                    if not normalized.is_file():
                        normalized_input_issues.append({"language": language, "product_key": key, "reason": "missing_normalized_input"})
                    elif raw_path.is_file() and sha256_file(raw_path) != sha256_file(normalized):
                        normalized_input_issues.append({"language": language, "product_key": key, "reason": "source_normalized_hash_mismatch"})
                self._add_explanation(explanations, duplicate_explanations, language, source["snapshot_path"], "primary", key)
                for alias in source.get("aliases", []):
                    alias_path = self.root / "data" / "current_prod_html" / language / alias["snapshot_path"]
                    if not alias_path.is_file():
                        missing_aliases.append({"language": language, "snapshot_path": alias["snapshot_path"], "product_key": key})
                    self._add_explanation(explanations, duplicate_explanations, language, alias["snapshot_path"], "alias", key)

        exclusions = self._load_exclusions()
        stale_exclusions: list[dict[str, str]] = []
        for item in exclusions:
            path = self.root / "data" / "current_prod_html" / item["language"] / item["snapshot_path"]
            if not path.is_file():
                stale_exclusions.append(item)
            self._add_explanation(explanations, duplicate_explanations, item["language"], item["snapshot_path"], "exclusion", item["reason_code"])

        unknown: list[dict[str, str]] = []
        counts: dict[str, dict[str, int]] = {}
        for language in languages:
            raw_root = self.root / "data" / "current_prod_html" / language
            snapshots = sorted(path.relative_to(raw_root).as_posix() for path in raw_root.rglob("*.html"))
            unexplained = [path for path in snapshots if (language, path) not in explanations]
            unknown.extend({"language": language, "snapshot_path": path} for path in unexplained)
            counts[language] = {
                "snapshots": len(snapshots),
                "explained": len(snapshots) - len(unexplained),
                "unknown": len(unexplained),
            }

        passed = not (unknown or stale_exclusions or duplicate_explanations or missing_primary or missing_aliases or normalized_input_issues)
        return {
            "schema_version": "1.0",
            "passed": passed,
            "counts": counts,
            "unknown_snapshots": unknown,
            "stale_exclusions": stale_exclusions,
            "duplicate_explanations": duplicate_explanations,
            "missing_primary_sources": missing_primary,
            "missing_source_aliases": missing_aliases,
            "normalized_input_issues": normalized_input_issues,
        }

    @staticmethod
    def _add_explanation(target: dict, duplicates: list, language: str, path: str, kind: str, owner: str) -> None:
        key = (language, path)
        if key in target:
            duplicates.append({
                "language": language,
                "snapshot_path": path,
                "first": f"{target[key]['kind']}:{target[key]['owner']}",
                "second": f"{kind}:{owner}",
            })
        else:
            target[key] = {"kind": kind, "owner": owner}

    def _load_exclusions(self) -> list[dict[str, str]]:
        if not self.exclusions_path.exists():
            return []
        value = json.loads(self.exclusions_path.read_text(encoding="utf-8"))
        items = value.get("exclusions", [])
        seen: set[tuple[str, str]] = set()
        for item in items:
            required = {"language", "snapshot_path", "reason_code", "reason"}
            if set(item) != required or item["language"] not in LANGUAGES or not all(item.values()):
                raise CatalogError(f"Invalid exact exclusion: {item}")
            key = (item["language"], item["snapshot_path"])
            if key in seen:
                raise CatalogError(f"Duplicate exclusion: {item['language']}/{item['snapshot_path']}")
            seen.add(key)
        return items

    def write_coverage_report(self, audit: dict[str, Any], output_dir: str | Path = "reports/v0.2") -> tuple[Path, Path]:
        directory = self.root / output_dir
        directory.mkdir(parents=True, exist_ok=True)
        json_path = directory / "coverage-baseline.json"
        markdown_path = directory / "coverage-baseline.md"
        json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = ["# v0.2 Source Snapshot Coverage", "", f"Status: **{'PASS' if audit['passed'] else 'FAIL'}**", "", "| Language | Snapshots | Explained | Unknown |", "|---|---:|---:|---:|"]
        for language, counts in audit["counts"].items():
            lines.append(f"| {language} | {counts['snapshots']} | {counts['explained']} | {counts['unknown']} |")
        for title, key in (("Unknown snapshots", "unknown_snapshots"), ("Stale exclusions", "stale_exclusions"), ("Duplicate explanations", "duplicate_explanations"), ("Missing primary sources", "missing_primary_sources"), ("Missing source aliases", "missing_source_aliases"), ("Normalized input issues", "normalized_input_issues")):
            lines.extend(["", f"## {title}", ""])
            values = audit[key]
            lines.extend(f"- `{item}`" for item in values) if values else lines.append("None.")
        markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return json_path, markdown_path

    def build_baseline_manifest(self) -> dict[str, Any]:
        entries = []
        records = self.load_definitions()
        for product_key, record in sorted(records.items()):
            definition = record.definition
            for language in LANGUAGES:
                source = definition["sources"][language]
                raw_path = (
                    self.root / "data" / "current_prod_html" / language / source["snapshot_path"]
                    if source["availability"] == "available" else None
                )
                normalized = normalized_input_path(self.root, definition, language)
                entries.append({
                    "product_key": product_key,
                    "language": language,
                    "page_model": definition["page_model"],
                    "capability_status": definition["capability_status"],
                    "catalog_categories": definition.get("catalog_categories", []),
                    "support_article_type": definition.get("support_article_type"),
                    "source_availability": source["availability"],
                    "source_snapshot_path": source.get("snapshot_path"),
                    "source_exists": bool(raw_path and raw_path.is_file()),
                    "source_sha256": sha256_file(raw_path) if raw_path and raw_path.is_file() else None,
                    "normalized_input_path": normalized.relative_to(self.root).as_posix(),
                    "normalized_exists": normalized.is_file(),
                    "normalized_sha256": sha256_file(normalized) if normalized.is_file() else None,
                    "strategy": "support_article" if definition["page_model"] == "SupportArticlePage" else definition.get("extraction", {}).get("strategy", "auto"),
                })
        return {
            "schema_version": "1.0",
            "total_product_definitions": len(records),
            "total_product_language_entries": len(entries),
            "entries": entries,
        }

    def write_baseline_manifest(self, output_dir: str | Path = "reports/v0.2") -> tuple[Path, Path]:
        manifest = self.build_baseline_manifest()
        directory = self.root / output_dir
        directory.mkdir(parents=True, exist_ok=True)
        json_path = directory / "baseline-manifest.json"
        markdown_path = directory / "baseline-manifest.md"
        json_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = [
            "# v0.2 Product-Language Baseline", "",
            f"Product Definitions: **{manifest['total_product_definitions']}**  ",
            f"Product-language entries: **{manifest['total_product_language_entries']}**", "",
            "| Product Key | Language | Model | Capability | Source | Normalized | Strategy |",
            "|---|---|---|---|---|---|---|",
        ]
        for item in manifest["entries"]:
            lines.append(
                f"| {item['product_key']} | {item['language']} | {item['page_model']} | {item['capability_status']} | "
                f"{'yes' if item['source_exists'] else item['source_availability']} | {'yes' if item['normalized_exists'] else 'no'} | {item['strategy']} |"
            )
        markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return json_path, markdown_path


def normalized_input_path(root: Path, definition: dict[str, Any], language: str) -> Path:
    if definition["page_model"] == "FlexibleContentPage":
        return root / "data" / "prod-html" / language / "pricing" / f"{definition['product_key']}.html"
    type_directory = SUPPORT_TYPE_DIRECTORIES[definition["support_article_type"]]
    return root / "data" / "prod-html" / language / "SupportArticles" / type_directory / f"{definition['product_key']}.html"


def artifact_relative_directory(definition: dict[str, Any], language: str) -> Path:
    if definition["page_model"] == "FlexibleContentPage":
        return Path(language) / "pricing"
    return Path(language) / "SupportArticles" / SUPPORT_TYPE_DIRECTORIES[definition["support_article_type"]]
