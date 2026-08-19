"""Build the CMS FlexibleContentPage shape for production Strategies."""

from __future__ import annotations

import json
from typing import Any

from src.utils.html.normalization import normalize_html


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class FlexibleBuilder:
    def build_flexible_page(
        self,
        base_metadata: dict[str, Any],
        common_sections: list[dict[str, Any]],
        strategy_content: dict[str, Any],
    ) -> dict[str, Any]:
        strategy_type = strategy_content.get("strategy_type")
        return {
            "title": base_metadata.get("Title", ""),
            "metaTitle": base_metadata.get("MetaTitle", ""),
            "metaDescription": base_metadata.get("MetaDescription", ""),
            "metaKeywords": base_metadata.get("MetaKeywords", ""),
            "slug": base_metadata.get("Slug", ""),
            "language": base_metadata.get("Language", ""),
            "baseContent": strategy_content.get("baseContent", ""),
            "contentGroups": strategy_content.get("contentGroups", []),
            "commonSections": common_sections,
            "pageConfig": self._page_config(
                strategy_type=strategy_type,
                base_metadata=base_metadata,
                filter_analysis=strategy_content.get("filter_analysis", {}),
                tab_analysis=strategy_content.get("tab_analysis", {}),
            ),
        }

    @staticmethod
    def build_simple_content_groups(base_content: str) -> list[dict[str, Any]]:
        del base_content
        return []

    def build_region_content_groups(
        self,
        region_content: dict[str, str],
        filter_analysis: dict[str, Any],
    ) -> list[dict[str, Any]]:
        options = self._options(filter_analysis, "region")
        if set(region_content) != {option["value"] for option in options}:
            raise ValueError("区域内容与源区域选项不是同一个完整集合。")
        return [
            {
                "groupName": option["label"],
                "filterCriteriaJson": _compact_json(
                    [
                        {
                            "filterKey": "region",
                            "matchValues": option["value"],
                        }
                    ]
                ),
                "content": normalize_html(region_content[option["value"]]),
                "sortOrder": index,
                "isActive": True,
            }
            for index, option in enumerate(options, start=1)
        ]

    @staticmethod
    def build_complex_content_groups(
        states: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not states:
            raise ValueError("Complex 页面没有源页面可选择状态。")
        groups: list[dict[str, Any]] = []
        seen_criteria: set[tuple[tuple[str, str], ...]] = set()
        for state in states:
            criteria = tuple(state["criteria"])
            if not criteria or criteria in seen_criteria:
                raise ValueError("Complex 页面状态为空或重复。")
            seen_criteria.add(criteria)
            labels = tuple(state["labels"])
            if len(labels) != len(criteria) or any(
                not label or " - " in label for label in labels
            ):
                raise ValueError("Complex 状态名称与筛选条件不一致。")
            content = normalize_html(state.get("content", ""))
            shared_content = normalize_html(state.get("sharedContent", ""))
            if not content and not shared_content:
                raise ValueError("Complex 页面状态没有任何源内容。")
            group: dict[str, Any] = {
                "groupName": " - ".join(labels),
                "filterCriteriaJson": _compact_json(
                    [
                        {"filterKey": key, "matchValues": value}
                        for key, value in criteria
                    ]
                ),
                "content": content,
                "sortOrder": len(groups) + 1,
                "isActive": True,
            }
            if shared_content:
                group["sharedContent"] = shared_content
            groups.append(group)
        return groups

    def _page_config(
        self,
        *,
        strategy_type: str,
        base_metadata: dict[str, Any],
        filter_analysis: dict[str, Any],
        tab_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        common = {
            "displayTitle": base_metadata.get("Title", ""),
            "pageIcon": "{base_url}/Static/Favicon/favicon.ico",
            "leftNavigationIdentifier": base_metadata.get("MSServiceName", ""),
        }
        if strategy_type == "simple_static":
            return {
                **common,
                "pageType": "Simple",
                "enableFilters": False,
                "filtersJsonConfig": _compact_json({"filterDefinitions": []}),
            }
        if strategy_type == "region_filter":
            definitions = [
                self._filter_definition(
                    filter_analysis,
                    key="region",
                    filter_type="dropdown",
                )
            ]
            return {
                **common,
                "pageType": "RegionFilter",
                "enableFilters": True,
                "filtersJsonConfig": _compact_json(
                    {"filterDefinitions": definitions}
                ),
            }
        if strategy_type == "complex":
            definitions = []
            if filter_analysis.get("software_visible"):
                definitions.append(
                    self._filter_definition(
                        filter_analysis,
                        key="software",
                        filter_type="dropdown",
                    )
                )
            definitions.extend(
                [
                    self._filter_definition(
                        filter_analysis,
                        key="region",
                        filter_type="dropdown",
                    ),
                    self._category_definition(tab_analysis),
                ]
            )
            return {
                **common,
                "pageType": "ComplexFilter",
                "enableFilters": True,
                "filtersJsonConfig": _compact_json(
                    {"filterDefinitions": definitions}
                ),
            }
        raise ValueError(f"未知生产 Strategy：{strategy_type!r}。")

    def _filter_definition(
        self,
        analysis: dict[str, Any],
        *,
        key: str,
        filter_type: str,
    ) -> dict[str, Any]:
        return {
            "filterKey": key,
            "filterType": filter_type,
            "displayName": str(analysis.get(f"{key}_display_name", "")),
            "options": self._options(analysis, key),
        }

    @staticmethod
    def _category_definition(tab_analysis: dict[str, Any]) -> dict[str, Any]:
        tabs = tab_analysis.get("category_tabs")
        if not isinstance(tabs, list) or not tabs:
            raise ValueError("Complex 页面没有 Category 选项。")
        options: list[dict[str, Any]] = []
        for index, tab in enumerate(tabs):
            option: dict[str, Any] = {
                "value": str(tab.get("href", "")).removeprefix("#"),
                "label": " ".join(str(tab.get("label", "")).split()),
                "href": str(tab.get("href", "")),
                "isActive": True,
            }
            if index == 0:
                option["isDefault"] = True
            options.append(option)
        if any(not option["value"] or not option["label"] for option in options):
            raise ValueError("Category 选项缺少名称或目标。")
        return {
            "filterKey": "category",
            "filterType": "tab",
            "displayName": str(tab_analysis.get("category_display_name", "")),
            "options": options,
        }

    @staticmethod
    def _options(analysis: dict[str, Any], key: str) -> list[dict[str, Any]]:
        raw_options = analysis.get(f"{key}_options")
        if not isinstance(raw_options, list) or not raw_options:
            raise ValueError(f"筛选器 {key} 没有选项。")
        options: list[dict[str, Any]] = []
        for index, option in enumerate(raw_options):
            cms_option: dict[str, Any] = {
                "value": str(option.get("value", "")),
                "label": str(option.get("label", "")),
                "href": str(option.get("href", "")),
            }
            cms_option["isActive"] = True
            if index == 0:
                cms_option["isDefault"] = True
            options.append(cms_option)
        if any(not option["value"] or not option["label"] for option in options):
            raise ValueError(f"筛选器 {key} 存在空名称或空值。")
        if len({option["value"] for option in options}) != len(options):
            raise ValueError(f"筛选器 {key} 存在重复值。")
        return options
