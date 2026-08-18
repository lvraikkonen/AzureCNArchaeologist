"""Project exact source fragments for one selected Azure region."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from bs4 import BeautifulSoup, Tag

from src.core.soft_category import SoftCategoryLookup, SoftCategoryRules
from src.utils.html.normalization import normalize_html


class RegionProjectionError(ValueError):
    """A region projection cannot be established from exact source identities."""


class RegionProcessor:
    """Apply trusted table exclusions to source-declared region states."""

    def __init__(
        self,
        config_file: Path | str,
        *,
        lookup_recorder: Callable[[SoftCategoryLookup], None] | None = None,
    ) -> None:
        self.rules = SoftCategoryRules.load(
            config_file,
            lookup_recorder=lookup_recorder,
        )

    def extract_region_contents(
        self,
        soup: BeautifulSoup,
        html_file_path: str,
        *,
        filter_analysis: dict[str, Any],
        product_config: dict[str, Any],
    ) -> dict[str, str]:
        del html_file_path, product_config
        if not filter_analysis.get("region_visible"):
            raise RegionProjectionError("RegionFilter 页面没有可见区域筛选器。")
        region_options = filter_analysis.get("region_options")
        if not isinstance(region_options, list) or not region_options:
            raise RegionProjectionError("区域筛选器没有可处理选项。")
        if filter_analysis.get("software_visible"):
            raise RegionProjectionError(
                "RegionFilter 页面同时暴露了软件筛选器，应由 Complex Strategy 处理。"
            )
        software_options = filter_analysis.get("software_options")
        if not isinstance(software_options, list) or len(software_options) != 1:
            raise RegionProjectionError(
                "RegionFilter 页面必须有且只有一个隐藏软件选项。"
            )
        software = str(software_options[0].get("value", "")).strip()
        if not software:
            raise RegionProjectionError("隐藏软件选项缺少配置名称。")

        pricing_root = _exactly_one(
            [
                root
                for root in soup.select(
                    "div.technical-azure-selector.pricing-detail-tab"
                )
                if not any(
                    isinstance(parent, Tag)
                    and "technical-azure-selector" in parent.get("class", [])
                    for parent in root.parents
                )
            ],
            "定价选择器",
        )
        direct_tab_bodies = [
            child
            for child in pricing_root.children
            if isinstance(child, Tag) and "tab-content" in child.get("class", [])
        ]
        direct_static_bodies = [
            child
            for child in pricing_root.children
            if isinstance(child, Tag)
            and "technical-azure-selector" in child.get("class", [])
            and "tab-control-selector" in child.get("class", [])
        ]
        pricing_body = _exactly_one(
            direct_tab_bodies + direct_static_bodies,
            "区域定价主体",
        )

        result: dict[str, str] = {}
        for option in region_options:
            if not isinstance(option, dict):
                raise RegionProjectionError("区域选项必须是对象。")
            region = str(option.get("value", "")).strip()
            if not region or region in result:
                raise RegionProjectionError("区域选项名称为空或重复。")
            exclusions = self.rules.excluded_table_ids(software, region)
            content = project_fragment_for_region(
                pricing_body,
                source_scope=pricing_root,
                excluded_table_ids=exclusions,
            )
            if not _has_business_content(content):
                raise RegionProjectionError(f"区域 {region!r} 没有可交付定价内容。")
            result[region] = content
        return result


def project_fragment_for_region(
    fragment: Tag,
    *,
    source_scope: Tag,
    excluded_table_ids: tuple[str, ...],
    validate_targets: bool = True,
) -> str:
    """Clone one source fragment and remove exact configured table units."""

    applicable_ids = excluded_table_ids
    if validate_targets:
        applicable_ids = validate_exclusion_targets(
            source_scope, excluded_table_ids
        )
    clone = deepcopy(fragment)
    _remove_excluded_units(clone, applicable_ids)
    return normalize_html(str(clone))


def project_fragments_for_region(
    fragments: list[Tag],
    *,
    source_scope: Tag,
    excluded_table_ids: tuple[str, ...],
    validate_targets: bool = True,
) -> str:
    """Project several adjacent source elements without inventing a wrapper."""

    if not fragments:
        return ""
    applicable_ids = excluded_table_ids
    if validate_targets:
        applicable_ids = validate_exclusion_targets(
            source_scope, excluded_table_ids
        )
    holder_soup = BeautifulSoup("<div></div>", "html.parser")
    holder = holder_soup.div
    assert holder is not None
    for fragment in fragments:
        holder.append(deepcopy(fragment))
    _remove_excluded_units(holder, applicable_ids)
    return normalize_html(holder.decode_contents())


def validate_exclusion_targets(
    source_scope: Tag,
    excluded_table_ids: tuple[str, ...],
) -> tuple[str, ...]:
    matched_count = 0
    applicable_ids: list[str] = []
    for table_id in excluded_table_ids:
        source_units = _matching_table_units(source_scope, table_id)
        if len(source_units) > 1:
            raise RegionProjectionError(
                f"配置表格 {table_id!r} 在源定价范围内最多对应一个物理表格单元，"
                f"实际为 {len(source_units)} 个。"
            )
        if source_units:
            matched_count += 1
            applicable_ids.append(table_id)
    if excluded_table_ids and matched_count == 0:
        raise RegionProjectionError(
            "该配置记录在当前源定价范围内没有对应任何物理表格单元，"
            "实际为 0 个。"
        )
    return tuple(applicable_ids)


def _remove_excluded_units(
    projected_scope: Tag,
    excluded_table_ids: tuple[str, ...],
) -> None:
    for table_id in excluded_table_ids:
        projected_units = _matching_table_units(projected_scope, table_id)
        if len(projected_units) > 1:
            raise RegionProjectionError(
                f"配置表格 {table_id!r} 在待投影片段中对应多个物理表格单元。"
            )
        if projected_units:
            projected_units[0].decompose()


def _matching_table_units(scope: Tag, table_id: str) -> list[Tag]:
    candidates = list(scope.find_all(id=table_id))
    candidates.extend(scope.find_all(attrs={"data-table-id": table_id}))
    units: list[Tag] = []
    for candidate in candidates:
        if not isinstance(candidate, Tag):
            continue
        if "scroll-table" in candidate.get("class", []):
            unit = candidate
        else:
            parent = candidate.find_parent("div", class_="scroll-table")
            unit = parent if isinstance(parent, Tag) else candidate
        if unit.name != "table" and "scroll-table" not in unit.get("class", []):
            raise RegionProjectionError(
                f"名称 {table_id!r} 指向的不是表格或 scroll-table 容器。"
            )
        if not any(unit is existing for existing in units):
            units.append(unit)
    return units


def _has_business_content(content: str) -> bool:
    parsed = BeautifulSoup(content, "html.parser")
    return bool(
        parsed.get_text(" ", strip=True)
        or parsed.select_one("img, video, audio, table, iframe")
    )


def _exactly_one(candidates: list[Tag], name: str) -> Tag:
    if len(candidates) != 1:
        raise RegionProjectionError(
            f"源页面必须恰好包含一个{name}，实际为 {len(candidates)} 个。"
        )
    return candidates[0]
