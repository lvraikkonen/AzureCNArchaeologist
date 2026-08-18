"""Two-stage comparison and readable impact analysis for soft-category.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.catalog import LANGUAGES, ProductCatalog
from src.core.soft_category import SoftCategoryError, SoftCategoryRules
from src.incremental.file_comparison import FileComparisonError, files_differ


CONFIG_USING_STRATEGIES = {"region_filter", "complex"}


class SoftCategoryChangeError(RuntimeError):
    """The trusted configuration or its usage evidence cannot be compared."""


@dataclass(frozen=True)
class SoftCategoryMappingChange:
    """One changed `(os, region) -> tableIDs` business mapping."""

    software: str
    region: str
    change_type: str
    previous_table_ids: tuple[str, ...]
    current_table_ids: tuple[str, ...]

    @property
    def reason(self) -> str:
        key = f"os={self.software!r}、region={self.region!r}"
        if self.change_type == "added":
            return f"新增配置映射 {key}。"
        if self.change_type == "removed":
            return f"删除配置映射 {key}。"
        return f"配置映射 {key} 的 tableIDs 成员发生变化。"

    def as_dict(self) -> dict[str, object]:
        return {
            "os": self.software,
            "region": self.region,
            "change_type": self.change_type,
            "previous_table_ids": list(self.previous_table_ids),
            "current_table_ids": list(self.current_table_ids),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SoftCategoryChangeReport:
    """Text comparison, business comparison, and resolved product impact."""

    previous_path: str
    current_path: str
    text_changed: bool
    business_mapping_changed: bool
    mapping_changes: tuple[SoftCategoryMappingChange, ...]
    affected_product_keys: tuple[str, ...]
    impact_resolution: str
    impact_reason: str
    usage_evidence_path: str

    def as_dict(self) -> dict[str, object]:
        return {
            "previous_path": self.previous_path,
            "current_path": self.current_path,
            "text_changed": self.text_changed,
            "business_mapping_changed": self.business_mapping_changed,
            "mapping_changes": [change.as_dict() for change in self.mapping_changes],
            "affected_product_keys": list(self.affected_product_keys),
            "impact_resolution": self.impact_resolution,
            "impact_reason": self.impact_reason,
            "usage_evidence_path": self.usage_evidence_path,
        }


@dataclass(frozen=True)
class _UsageEvidence:
    lookups_by_product: dict[str, frozenset[tuple[str, str]]]
    incomplete_product_keys: tuple[str, ...]
    complete: bool
    reason: str


def compare_soft_category(
    catalog: ProductCatalog,
    *,
    source_root: Path,
    previous_path: Path | None = None,
    usage_evidence_path: Path | None = None,
) -> SoftCategoryChangeReport:
    """Compare text first, then compare normalized business mappings."""

    current = source_root / "soft-category.json"
    previous = (
        previous_path
        if previous_path is not None
        else catalog.project_root / "data" / "configs" / "soft-category.json"
    ).resolve()
    usage_path = (
        usage_evidence_path
        if usage_evidence_path is not None
        else catalog.project_root / "data" / "state" / "soft-category-usage.json"
    ).resolve()
    _require_regular_file(previous, label="上一次可信配置")
    _require_regular_file(current, label="上游新快照可信配置")
    try:
        text_changed = files_differ(previous, current)
        previous_rules = SoftCategoryRules.load(previous)
        current_rules = SoftCategoryRules.load(current)
    except (FileComparisonError, SoftCategoryError) as error:
        raise SoftCategoryChangeError(str(error)) from error

    mapping_changes = _mapping_changes(previous_rules, current_rules)
    if not mapping_changes:
        reason = (
            "配置文件文本发生变化，但解析后的业务映射相同。"
            if text_changed
            else "配置文件文本和业务映射都没有变化。"
        )
        return SoftCategoryChangeReport(
            previous_path=_present(previous, catalog.project_root),
            current_path=_present(current, catalog.project_root),
            text_changed=text_changed,
            business_mapping_changed=False,
            mapping_changes=(),
            affected_product_keys=(),
            impact_resolution="no_business_change",
            impact_reason=reason,
            usage_evidence_path=_present(usage_path, catalog.project_root),
        )

    possible_consumers = tuple(
        product_key
        for product_key in catalog.scope_product_keys
        if catalog.effective_strategy(product_key) in CONFIG_USING_STRATEGIES
    )
    usage = _load_usage_evidence(
        usage_path,
        catalog=catalog,
        possible_consumers=possible_consumers,
    )
    changed_keys = {
        (change.software, change.region) for change in mapping_changes
    }
    if usage.complete:
        affected = tuple(
            product_key
            for product_key in possible_consumers
            if usage.lookups_by_product.get(product_key, frozenset())
            & changed_keys
        )
        resolution = "actual_usage"
        reason = (
            "使用已记录的实际配置查询确定受影响产品。"
            if affected
            else "变化的业务映射没有被当前支持产品实际查询。"
        )
    else:
        incomplete = set(usage.incomplete_product_keys)
        affected = tuple(
            product_key
            for product_key in possible_consumers
            if product_key in incomplete
            or usage.lookups_by_product.get(product_key, frozenset())
            & changed_keys
        )
        resolution = "actual_usage_with_unknown_consumers"
        reason = (
            f"{usage.reason} 已有完整记录的产品按实际查询判断；"
            "缺少完整记录的产品为避免静默漏处理，仍加入处理范围。"
        )

    return SoftCategoryChangeReport(
        previous_path=_present(previous, catalog.project_root),
        current_path=_present(current, catalog.project_root),
        text_changed=text_changed,
        business_mapping_changed=True,
        mapping_changes=mapping_changes,
        affected_product_keys=affected,
        impact_resolution=resolution,
        impact_reason=reason,
        usage_evidence_path=_present(usage_path, catalog.project_root),
    )


def _mapping_changes(
    previous: SoftCategoryRules,
    current: SoftCategoryRules,
) -> tuple[SoftCategoryMappingChange, ...]:
    changes: list[SoftCategoryMappingChange] = []
    for software, region in sorted(set(previous.rows) | set(current.rows)):
        key = (software, region)
        old = tuple(sorted(set(previous.rows.get(key, ()))))
        new = tuple(sorted(set(current.rows.get(key, ()))))
        if old == new and (key in previous.rows) == (key in current.rows):
            continue
        if key not in previous.rows:
            change_type = "added"
        elif key not in current.rows:
            change_type = "removed"
        else:
            change_type = "table_ids_changed"
        changes.append(
            SoftCategoryMappingChange(
                software=software,
                region=region,
                change_type=change_type,
                previous_table_ids=old,
                current_table_ids=new,
            )
        )
    return tuple(changes)


def _load_usage_evidence(
    path: Path,
    *,
    catalog: ProductCatalog,
    possible_consumers: tuple[str, ...],
) -> _UsageEvidence:
    if not path.is_file():
        return _UsageEvidence(
            {},
            possible_consumers,
            False,
            "尚无完整的实际配置查询记录。",
        )
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return _UsageEvidence(
            {},
            possible_consumers,
            False,
            f"实际配置查询记录无法读取：{error}。",
        )
    if not isinstance(value, dict) or value.get("schema_version") != "1.0":
        return _UsageEvidence(
            {},
            possible_consumers,
            False,
            "实际配置查询记录的格式无效。",
        )
    items = value.get("items")
    if not isinstance(items, list):
        return _UsageEvidence(
            {},
            possible_consumers,
            False,
            "实际配置查询记录缺少处理项列表。",
        )

    by_item: dict[tuple[str, str], frozenset[tuple[str, str]]] = {}
    try:
        for row in items:
            if not isinstance(row, dict):
                raise ValueError("处理项不是对象")
            product_key = row.get("product_key")
            language = row.get("language")
            lookups = row.get("lookups")
            if (
                not isinstance(product_key, str)
                or language not in LANGUAGES
                or not isinstance(lookups, list)
            ):
                raise ValueError("处理项身份或查询列表无效")
            item_key = (product_key, language)
            if item_key in by_item:
                raise ValueError("处理项重复")
            keys: set[tuple[str, str]] = set()
            for lookup in lookups:
                if not isinstance(lookup, dict):
                    raise ValueError("查询记录不是对象")
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
                    or any(not isinstance(item, str) for item in table_ids)
                ):
                    raise ValueError("查询记录字段无效")
                keys.add((software, region))
            by_item[item_key] = frozenset(keys)
    except ValueError as error:
        return _UsageEvidence(
            {},
            possible_consumers,
            False,
            f"实际配置查询记录不完整：{error}。",
        )

    missing_items = [
        (product_key, language)
        for product_key in possible_consumers
        for language in catalog.languages
        if (product_key, language) not in by_item
    ]
    incomplete_products = tuple(
        product_key
        for product_key in possible_consumers
        if any(key == product_key for key, _ in missing_items)
    )
    lookups_by_product = {
        product_key: frozenset().union(
            *(by_item[(product_key, language)] for language in catalog.languages)
        )
        for product_key in possible_consumers
        if product_key not in incomplete_products
    }
    if incomplete_products:
        missing_labels = [
            f"{product_key}/{language}"
            for product_key, language in missing_items
        ]
        return _UsageEvidence(
            lookups_by_product,
            incomplete_products,
            False,
            "实际配置查询记录缺少 " + "、".join(missing_labels) + "。",
        )
    return _UsageEvidence(
        lookups_by_product,
        (),
        True,
        "实际配置查询记录完整。",
    )


def _require_regular_file(path: Path, *, label: str) -> None:
    if path.is_symlink():
        raise SoftCategoryChangeError(f"{label}不能是符号链接：{path}。")
    if not path.is_file():
        raise SoftCategoryChangeError(f"{label}不存在或不是普通文件：{path}。")


def _present(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


__all__ = [
    "CONFIG_USING_STRATEGIES",
    "SoftCategoryChangeError",
    "SoftCategoryChangeReport",
    "SoftCategoryMappingChange",
    "compare_soft_category",
]
