#!/usr/bin/env python3
"""One-shot, deterministic Product Definition 1.0 -> 1.1 calibration.

The migration deliberately refuses unknown legacy fields and bilingual strategy
disagreement.  It is kept in the repository so the 1.1 decisions are
reproducible from the frozen v0.4 baseline instead of being an opaque rewrite.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator, FormatChecker
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.detectors.page_analyzer import PageAnalyzer


PRODUCTS_ROOT = ROOT / "data" / "configs" / "products"
REPORT_PATH = ROOT / "reports" / "v0.4" / "product-definition-1.1-migration.json"
LEGACY_EXTRACTION_FIELDS = {
    "strategy",
    "important_section_titles",
    "priority_sections",
    "enable_region_processing",
    "estimated_size_mb",
    "extra_sections",
}
STRATEGY_MAP = {
    "SimpleStatic": "simple_static",
    "RegionFilter": "region_filter",
    "Complex": "complex",
}


class MigrationError(RuntimeError):
    pass


def _observe(definition: dict[str, Any], language: str) -> str:
    source = definition["sources"][language]
    if source["availability"] != "available":
        return "unavailable"
    path = ROOT / "data" / "current_prod_html" / language / source["snapshot_path"]
    text = path.read_bytes().decode("utf-8", errors="strict")
    # The legacy detectors are intentionally noisy; their result, not their
    # diagnostics, is the migration evidence retained below.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        observed = PageAnalyzer().determine_page_type_v3(
            BeautifulSoup(text, "html.parser")
        )
    try:
        return STRATEGY_MAP[observed]
    except KeyError as error:
        raise MigrationError(
            f"Unknown analyzer result for {definition['product_key']}/{language}: {observed}"
        ) from error


def _calibrate_strategy(definition: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    product_key = definition["product_key"]
    if definition["page_model"] == "SupportArticlePage":
        return "support_article", {
            "product_key": product_key,
            "observed": {"zh-cn": "support_article", "en-us": "support_article"},
            "decision": "support_article",
            "basis": "page_model",
        }

    observed = {language: _observe(definition, language) for language in ("zh-cn", "en-us")}
    legacy = definition.get("extraction", {}).get("strategy")
    if legacy is not None:
        if legacy not in {"simple_static", "region_filter", "complex"}:
            raise MigrationError(f"Unknown legacy strategy for {product_key}: {legacy}")
        decision, basis = legacy, "existing_explicit_decision"
    else:
        available = {value for value in observed.values() if value != "unavailable"}
        if len(available) != 1:
            raise MigrationError(
                f"Bilingual strategy calibration conflict for {product_key}: {observed}"
            )
        decision, basis = next(iter(available)), "bilingual_analyzer_agreement"
    return decision, {
        "product_key": product_key,
        "observed": observed,
        "decision": decision,
        "basis": basis,
    }


def main() -> int:
    logger.remove()
    schema = json.loads(
        (ROOT / "schemas" / "product-definition-1.1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    decisions: list[dict[str, Any]] = []
    migrated: list[tuple[Path, dict[str, Any]]] = []
    removed_counts: Counter[str] = Counter()
    quality_thresholds: dict[str, int] = {}
    applicability_candidates: list[dict[str, Any]] = []

    for path in sorted(PRODUCTS_ROOT.glob("*/*.json")):
        definition = json.loads(path.read_text(encoding="utf-8"))
        if definition.get("schema_version") != "1.0":
            raise MigrationError(f"Expected Product Definition 1.0: {path}")
        extraction = definition.get("extraction", {})
        unknown = set(extraction) - LEGACY_EXTRACTION_FIELDS
        if unknown:
            raise MigrationError(f"Unknown legacy extraction fields in {path}: {sorted(unknown)}")

        strategy, decision = _calibrate_strategy(definition)
        decisions.append(decision)
        for key in extraction:
            if key != "strategy":
                removed_counts[key] += 1
        if extraction.get("extra_sections"):
            applicability_candidates.append({
                "product_key": definition["product_key"],
                "legacy_extra_sections": extraction["extra_sections"],
                "disposition": "migrated_to_applicability_map_candidate",
            })
        quality_thresholds[definition["product_key"]] = int(
            definition.get("quality", {}).get("min_content_length", 0)
        )

        definition["schema_version"] = "1.1"
        definition["extraction"] = {"semantic_strategy": strategy}
        definition.pop("quality", None)
        errors = sorted(
            validator.iter_errors(definition), key=lambda item: list(item.absolute_path)
        )
        if errors:
            rendered = "; ".join(
                f"{'/'.join(map(str, error.absolute_path)) or '$'}: {error.message}"
                for error in errors
            )
            raise MigrationError(f"Migrated definition is invalid ({path}): {rendered}")
        migrated.append((path, definition))

    strategy_counts = Counter(item["decision"] for item in decisions)
    report = {
        "schema_version": "1.0",
        "migration": "product-definition-1.0-to-1.1",
        "status": "completed",
        "source_definition_count": len(migrated),
        "target_definition_count": len(migrated),
        "unresolved_findings": 0,
        "strategy_counts": dict(sorted(strategy_counts.items())),
        "removed_legacy_extraction_fields": dict(sorted(removed_counts.items())),
        "quality_thresholds_migrated_to_validation_profile": quality_thresholds,
        "applicability_map_candidates": applicability_candidates,
        "strategy_calibration": decisions,
    }

    for path, definition in migrated:
        path.write_text(
            json.dumps(definition, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"migrated={len(migrated)} unresolved=0 "
        f"strategies={dict(sorted(strategy_counts.items()))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
