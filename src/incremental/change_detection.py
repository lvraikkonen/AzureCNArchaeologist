"""Read-only comparison of an upstream input snapshot and fixed baselines."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from src.core.catalog import LANGUAGES, ProcessingItem, ProductCatalog
from src.incremental.file_comparison import FileComparisonError, files_differ
from src.incremental.product_definition_changes import (
    ProductDefinitionChange,
    ProductDefinitionChangeError,
    compare_product_definitions,
)
from src.incremental.soft_category_changes import (
    SoftCategoryChangeError,
    SoftCategoryChangeReport,
    compare_soft_category,
)


class ChangeDetectionError(RuntimeError):
    """The new snapshot cannot be compared safely with fixed inputs."""


@dataclass(frozen=True)
class LanguageChange:
    """A readable HTML change found for one language of one product."""

    language: str
    change_type: str
    new_snapshot_path: str
    previous_frozen_path: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {
            "language": self.language,
            "change_type": self.change_type,
            "new_snapshot_path": self.new_snapshot_path,
            "previous_frozen_path": self.previous_frozen_path,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class AffectedProduct:
    """One affected product expanded to complete Chinese-and-English work."""

    product_key: str
    changed_languages: tuple[str, ...]
    changes: tuple[LanguageChange, ...]
    soft_category_reasons: tuple[str, ...]
    product_definition_reasons: tuple[str, ...]
    processing_items: tuple[ProcessingItem, ...]
    bilingual_processing_reason: str

    @property
    def change_sources(self) -> tuple[str, ...]:
        result: list[str] = []
        if self.changes:
            result.append("html")
        if self.soft_category_reasons:
            result.append("soft_category")
        if self.product_definition_reasons:
            result.append("product_definition")
        return tuple(result)

    def as_dict(self) -> dict[str, object]:
        return {
            "product_key": self.product_key,
            "change_sources": list(self.change_sources),
            "changed_languages": list(self.changed_languages),
            "html_changes": [change.as_dict() for change in self.changes],
            "soft_category_reasons": list(self.soft_category_reasons),
            "product_definition_reasons": list(
                self.product_definition_reasons
            ),
            "processing_item_ids": [
                f"{item.product_key}/{item.language}"
                for item in self.processing_items
            ],
            "bilingual_processing_reason": self.bilingual_processing_reason,
        }


@dataclass(frozen=True)
class ChangePlan:
    """Complete read-only result of comparing the current processing scope."""

    inspected_product_count: int
    inspected_item_count: int
    affected_products: tuple[AffectedProduct, ...]
    unchanged_product_keys: tuple[str, ...]
    included_comparisons: tuple[str, ...]
    not_yet_included_comparisons: tuple[str, ...]
    soft_category: SoftCategoryChangeReport | None = None
    product_definition_changes: tuple[ProductDefinitionChange, ...] = ()

    @property
    def has_changes(self) -> bool:
        return bool(self.affected_products)

    @property
    def affected_product_count(self) -> int:
        return len(self.affected_products)

    @property
    def affected_item_count(self) -> int:
        return sum(
            len(product.processing_items) for product in self.affected_products
        )

    @property
    def processing_items(self) -> tuple[ProcessingItem, ...]:
        return tuple(
            item
            for product in self.affected_products
            for item in product.processing_items
        )

    def as_dict(self) -> dict[str, object]:
        html_only = self.included_comparisons == (
            "upstream_html_vs_frozen_html",
        )
        if html_only:
            status = (
                "html_changes_found" if self.has_changes else "no_html_changes"
            )
        else:
            status = "changes_found" if self.has_changes else "no_changes"
        result: dict[str, object] = {
            "schema_version": "2.0",
            "status": status,
            "comparison_scope": {
                "included": list(self.included_comparisons),
                "not_yet_included": list(
                    self.not_yet_included_comparisons
                ),
            },
            "summary": {
                "inspected_products": self.inspected_product_count,
                "inspected_items": self.inspected_item_count,
                "affected_products": self.affected_product_count,
                "planned_items": self.affected_item_count,
                "unchanged_products": len(self.unchanged_product_keys),
            },
            "affected_products": [
                product.as_dict() for product in self.affected_products
            ],
            "unchanged_product_keys": list(self.unchanged_product_keys),
        }
        if self.soft_category is not None:
            result["soft_category"] = self.soft_category.as_dict()
        if "product_definitions" in self.included_comparisons:
            result["product_definition_changes"] = [
                change.as_dict()
                for change in self.product_definition_changes
            ]
        return result


def detect_html_changes(
    catalog: ProductCatalog,
    *,
    source_root: Path | str | None = None,
    frozen_root: Path | str | None = None,
) -> ChangePlan:
    """Compare scoped HTML inputs without modifying either directory."""

    current_root, previous_root = _comparison_roots(
        catalog,
        source_root=source_root,
        frozen_root=frozen_root,
    )
    items, grouped, html_changes = _detect_html(
        catalog,
        source_root=current_root,
        frozen_root=previous_root,
    )
    affected: list[AffectedProduct] = []
    unchanged: list[str] = []
    for product_key in catalog.scope_product_keys:
        changes = html_changes.get(product_key, ())
        if not changes:
            unchanged.append(product_key)
            continue
        product_items = grouped[product_key]
        changed_languages = tuple(change.language for change in changes)
        affected.append(
            AffectedProduct(
                product_key=product_key,
                changed_languages=changed_languages,
                changes=changes,
                soft_category_reasons=(),
                product_definition_reasons=(),
                processing_items=product_items,
                bilingual_processing_reason=_bilingual_reason(
                    changed_languages=changed_languages,
                    soft_category_changed=False,
                    product_definition_changed=False,
                ),
            )
        )
    return ChangePlan(
        inspected_product_count=len(grouped),
        inspected_item_count=len(items),
        affected_products=tuple(affected),
        unchanged_product_keys=tuple(unchanged),
        included_comparisons=("upstream_html_vs_frozen_html",),
        not_yet_included_comparisons=(
            "product_definitions",
            "soft_category",
        ),
    )


def detect_incremental_changes(
    catalog: ProductCatalog,
    *,
    source_root: Path | str | None = None,
    frozen_root: Path | str | None = None,
    previous_soft_category_path: Path | str | None = None,
    usage_evidence_path: Path | str | None = None,
    product_definition_baseline_path: Path | str | None = None,
) -> ChangePlan:
    """Combine HTML, trusted configuration, and Product Definition changes."""

    current_root, previous_root = _comparison_roots(
        catalog,
        source_root=source_root,
        frozen_root=frozen_root,
    )
    items, grouped, html_changes = _detect_html(
        catalog,
        source_root=current_root,
        frozen_root=previous_root,
    )
    try:
        soft_category = compare_soft_category(
            catalog,
            source_root=current_root,
            previous_path=(
                Path(previous_soft_category_path).resolve()
                if previous_soft_category_path is not None
                else None
            ),
            usage_evidence_path=(
                Path(usage_evidence_path).resolve()
                if usage_evidence_path is not None
                else None
            ),
        )
        definition_changes = compare_product_definitions(
            catalog,
            baseline_path=(
                Path(product_definition_baseline_path).resolve()
                if product_definition_baseline_path is not None
                else None
            ),
        )
    except (SoftCategoryChangeError, ProductDefinitionChangeError) as error:
        raise ChangeDetectionError(str(error)) from error

    config_affected = set(soft_category.affected_product_keys)
    definitions_by_product = {
        change.product_key: change for change in definition_changes
    }
    config_reasons = tuple(
        [change.reason for change in soft_category.mapping_changes]
        + [soft_category.impact_reason]
    )
    affected: list[AffectedProduct] = []
    unchanged: list[str] = []
    for product_key in catalog.scope_product_keys:
        changes = html_changes.get(product_key, ())
        definition_change = definitions_by_product.get(product_key)
        soft_reasons = config_reasons if product_key in config_affected else ()
        definition_reasons = (
            definition_change.reasons if definition_change is not None else ()
        )
        if not changes and not soft_reasons and not definition_reasons:
            unchanged.append(product_key)
            continue
        changed_languages = tuple(change.language for change in changes)
        affected.append(
            AffectedProduct(
                product_key=product_key,
                changed_languages=changed_languages,
                changes=changes,
                soft_category_reasons=soft_reasons,
                product_definition_reasons=definition_reasons,
                processing_items=grouped[product_key],
                bilingual_processing_reason=_bilingual_reason(
                    changed_languages=changed_languages,
                    soft_category_changed=bool(soft_reasons),
                    product_definition_changed=bool(definition_reasons),
                ),
            )
        )

    return ChangePlan(
        inspected_product_count=len(grouped),
        inspected_item_count=len(items),
        affected_products=tuple(affected),
        unchanged_product_keys=tuple(unchanged),
        included_comparisons=(
            "upstream_html_vs_frozen_html",
            "soft_category_text_and_business_mapping",
            "product_definitions",
        ),
        not_yet_included_comparisons=(),
        soft_category=soft_category,
        product_definition_changes=definition_changes,
    )


def _detect_html(
    catalog: ProductCatalog,
    *,
    source_root: Path,
    frozen_root: Path,
) -> tuple[
    tuple[ProcessingItem, ...],
    dict[str, tuple[ProcessingItem, ...]],
    dict[str, tuple[LanguageChange, ...]],
]:
    items = catalog.select(all_products=True)
    mutable_grouped: dict[str, list[ProcessingItem]] = defaultdict(list)
    for item in items:
        mutable_grouped[item.product_key].append(item)
    grouped: dict[str, tuple[ProcessingItem, ...]] = {}
    changes_by_product: dict[str, tuple[LanguageChange, ...]] = {}
    for product_key in catalog.scope_product_keys:
        product_items = tuple(mutable_grouped[product_key])
        language_order = tuple(item.language for item in product_items)
        if language_order != LANGUAGES:
            raise ChangeDetectionError(
                f"产品 {product_key} 必须且只能按 zh-cn、en-us 各比较一次；"
                f"实际为 {', '.join(language_order) or '空'}。"
            )
        grouped[product_key] = product_items
        changes = tuple(
            change
            for item in product_items
            if (
                change := _compare_item(
                    item,
                    source_root=source_root,
                    frozen_root=frozen_root,
                )
            )
            is not None
        )
        if changes:
            changes_by_product[product_key] = changes
    return items, grouped, changes_by_product


def _compare_item(
    item: ProcessingItem,
    *,
    source_root: Path,
    frozen_root: Path,
) -> LanguageChange | None:
    current = _safe_path(
        source_root,
        item.source_relative_path,
        label="上游新快照",
    )
    previous = _safe_path(
        frozen_root,
        item.frozen_relative_path,
        label="Frozen HTML",
    )
    current_exists = _regular_file_state(current, label="上游新快照")
    previous_exists = _regular_file_state(previous, label="Frozen HTML")
    paths = {
        "language": item.language,
        "new_snapshot_path": _project_relative_source_path(item),
        "previous_frozen_path": _project_relative_frozen_path(item),
    }

    if current_exists and previous_exists:
        try:
            different = files_differ(previous, current)
        except FileComparisonError as error:
            raise ChangeDetectionError(str(error)) from error
        if not different:
            return None
        return LanguageChange(
            **paths,
            change_type="modified",
            reason=(
                f"{item.language} 上游 HTML 的文件内容与当前 Frozen HTML 不同。"
            ),
        )
    if current_exists:
        return LanguageChange(
            **paths,
            change_type="added",
            reason=(
                f"{item.language} 上游 HTML 已出现，但当前没有对应 Frozen HTML。"
            ),
        )
    if previous_exists:
        return LanguageChange(
            **paths,
            change_type="removed",
            reason=(
                f"{item.language} 上游新快照缺少文件，但当前 Frozen HTML 仍存在。"
            ),
        )
    return LanguageChange(
        **paths,
        change_type="missing_in_both",
        reason=(
            f"{item.language} 上游新快照和当前 Frozen HTML 都缺少文件，"
            "无法建立比较基准。"
        ),
    )


def _comparison_roots(
    catalog: ProductCatalog,
    *,
    source_root: Path | str | None,
    frozen_root: Path | str | None,
) -> tuple[Path, Path]:
    current_root = Path(
        source_root
        if source_root is not None
        else catalog.project_root / "data" / "current_prod_html"
    ).resolve()
    previous_root = Path(
        frozen_root
        if frozen_root is not None
        else catalog.project_root / "data" / "prod-html"
    ).resolve()
    if current_root == previous_root:
        raise ChangeDetectionError(
            "上游新快照目录与 Frozen HTML 目录不能是同一个目录。"
        )
    return current_root, previous_root


def _safe_path(root: Path, relative: PurePosixPath, *, label: str) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ChangeDetectionError(
            f"{label}路径不能是绝对路径或越出规定目录：{relative.as_posix()}。"
        )
    candidate = root.joinpath(*relative.parts)
    try:
        candidate.resolve().relative_to(root)
    except (OSError, ValueError) as error:
        raise ChangeDetectionError(
            f"{label}路径越出规定目录：{relative.as_posix()}。"
        ) from error
    if candidate.is_symlink():
        raise ChangeDetectionError(
            f"{label}文件不能是符号链接：{relative.as_posix()}。"
        )
    return candidate


def _regular_file_state(path: Path, *, label: str) -> bool:
    try:
        exists = path.exists()
        if exists and not path.is_file():
            raise ChangeDetectionError(f"{label}路径不是普通文件：{path}。")
        return exists
    except OSError as error:
        raise ChangeDetectionError(f"无法检查{label}文件 {path}：{error}") from error


def _project_relative_source_path(item: ProcessingItem) -> str:
    return PurePosixPath(
        "data", "current_prod_html", *item.source_relative_path.parts
    ).as_posix()


def _project_relative_frozen_path(item: ProcessingItem) -> str:
    return PurePosixPath(
        "data", "prod-html", *item.frozen_relative_path.parts
    ).as_posix()


def _bilingual_reason(
    *,
    changed_languages: tuple[str, ...],
    soft_category_changed: bool,
    product_definition_changed: bool,
) -> str:
    reasons: list[str] = []
    if changed_languages:
        reasons.append("、".join(changed_languages) + " 的 HTML 发生变化")
    if soft_category_changed:
        reasons.append("该产品实际依赖的 soft-category 业务映射发生变化")
    if product_definition_changed:
        reasons.append("该产品的处理相关 Product Definition 字段发生变化")
    return "；".join(reasons) + "；按照双语一致原则，本次同时处理 zh-cn 和 en-us。"


__all__ = [
    "AffectedProduct",
    "ChangeDetectionError",
    "ChangePlan",
    "LanguageChange",
    "detect_html_changes",
    "detect_incremental_changes",
]
