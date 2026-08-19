"""Write and merge readable soft-category lookup evidence."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from src.core.catalog import ProcessingItem, ProductCatalog
from src.core.payload_contract import payload_json_bytes
from src.core.soft_category import SoftCategoryLookup
from src.incremental.soft_category_changes import CONFIG_USING_STRATEGIES


class UsageEvidenceError(RuntimeError):
    """Configuration usage evidence cannot be trusted or updated safely."""


def build_item_usage_report(
    item: ProcessingItem,
    lookups: Iterable[SoftCategoryLookup],
) -> dict[str, object]:
    """Build one item-level report, including an explicitly empty lookup list."""

    return {
        "schema_version": "1.0",
        "product_key": item.product_key,
        "language": item.language,
        "semantic_strategy": item.semantic_strategy,
        "uses_soft_category": item.semantic_strategy in CONFIG_USING_STRATEGIES,
        "lookups": [lookup.as_dict() for lookup in lookups],
    }


def validate_item_usage_report(
    value: Any,
    *,
    item: ProcessingItem,
) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_version") != "1.0":
        raise UsageEvidenceError(
            f"{item.product_key}/{item.language} 的配置查询报告版本无效。"
        )
    expected = {
        "product_key": item.product_key,
        "language": item.language,
        "semantic_strategy": item.semantic_strategy,
        "uses_soft_category": item.semantic_strategy in CONFIG_USING_STRATEGIES,
    }
    for field, expected_value in expected.items():
        if value.get(field) != expected_value:
            raise UsageEvidenceError(
                f"{item.product_key}/{item.language} 的配置查询报告字段 "
                f"{field} 不一致。"
            )
    lookups = value.get("lookups")
    if not isinstance(lookups, list):
        raise UsageEvidenceError(
            f"{item.product_key}/{item.language} 的配置查询报告缺少 lookups。"
        )
    seen: set[tuple[str, str]] = set()
    for lookup in lookups:
        if not isinstance(lookup, dict):
            raise UsageEvidenceError("配置查询记录必须是对象。")
        software = lookup.get("os")
        region = lookup.get("region")
        row_present = lookup.get("row_present")
        table_ids = lookup.get("table_ids")
        if (
            not isinstance(software, str)
            or not software
            or not isinstance(region, str)
            or not region
            or not isinstance(row_present, bool)
            or not isinstance(table_ids, list)
            or any(not isinstance(table_id, str) for table_id in table_ids)
        ):
            raise UsageEvidenceError("配置查询记录字段无效。")
        key = (software, region)
        if key in seen:
            raise UsageEvidenceError("配置查询报告重复记录同一个 os、region。")
        seen.add(key)
    return value


def merge_usage_evidence(
    catalog: ProductCatalog,
    reports: Iterable[dict[str, Any]],
    *,
    evidence_path: Path | None = None,
) -> None:
    """Replace successful item entries while preserving other readable entries."""

    path = (
        evidence_path
        if evidence_path is not None
        else catalog.project_root / "data" / "state" / "soft-category-usage.json"
    ).resolve()
    by_item: dict[tuple[str, str], dict[str, Any]] = {}
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise UsageEvidenceError(
                f"配置查询总表不是普通文件：{path}。"
            )
        try:
            current: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise UsageEvidenceError(
                f"无法读取现有配置查询总表 {path}：{error}"
            ) from error
        if not isinstance(current, dict) or current.get("schema_version") != "1.0":
            raise UsageEvidenceError("现有配置查询总表版本无效。")
        items = current.get("items")
        if not isinstance(items, list):
            raise UsageEvidenceError("现有配置查询总表缺少 items。")
        for row in items:
            if not isinstance(row, dict):
                raise UsageEvidenceError("现有配置查询总表包含无效处理项。")
            product_key = row.get("product_key")
            language = row.get("language")
            if not isinstance(product_key, str) or not isinstance(language, str):
                raise UsageEvidenceError("现有配置查询总表包含无效身份。")
            key = (product_key, language)
            if key in by_item:
                raise UsageEvidenceError("现有配置查询总表包含重复处理项。")
            by_item[key] = row

    for report in reports:
        product_key = report.get("product_key")
        language = report.get("language")
        if not isinstance(product_key, str) or not isinstance(language, str):
            raise UsageEvidenceError("待合并的配置查询报告缺少处理项身份。")
        item = next(
            (
                candidate
                for candidate in catalog.select(product_key=product_key)
                if candidate.language == language
            ),
            None,
        )
        if item is None:
            raise UsageEvidenceError(
                f"配置查询报告引用范围外处理项：{product_key}/{language}。"
            )
        validated = validate_item_usage_report(report, item=item)
        if not validated["uses_soft_category"]:
            by_item.pop((product_key, language), None)
            continue
        by_item[(product_key, language)] = validated

    ordered: list[dict[str, Any]] = []
    for product_key in catalog.scope_product_keys:
        for language in catalog.languages:
            row = by_item.get((product_key, language))
            if row is not None:
                ordered.append(row)
    _atomic_write_json(
        path,
        {
            "schema_version": "1.0",
            "description": (
                "成功生产抽取实际查询过的 soft-category 映射；"
                "空结果查询同样保留。"
            ),
            "items": ordered,
        },
    )


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(payload_json_bytes(value))
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    except OSError as error:
        raise UsageEvidenceError(
            f"无法更新配置查询总表 {path}：{error}"
        ) from error
    finally:
        temporary_path.unlink(missing_ok=True)


__all__ = [
    "UsageEvidenceError",
    "build_item_usage_report",
    "merge_usage_evidence",
    "validate_item_usage_report",
]
