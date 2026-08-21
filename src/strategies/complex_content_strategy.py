"""Complex pricing extraction adapted from the v0.5.5 core Strategy."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from src.core.complex_table_index import (
    IndexedFragmentProjector,
    applicable_exclusions_for_software,
)
from src.core.region_processor import RegionProcessor
from src.core.scoped_source_content import (
    locate_formal_pricing_boundary,
    resolve_page_global_base_content,
)
from src.detectors.filter_detector import FilterDetector
from src.detectors.tab_detector import TabDetector
from src.strategies.base_strategy import BaseStrategy
from src.utils.content.content_extractor import ContentExtractor
from src.utils.content.flexible_builder import FlexibleBuilder
from src.utils.content.section_extractor import SectionExtractor


logger = logging.getLogger(__name__)


class ComplexContentStrategy(BaseStrategy):
    """Extract source-declared Region × Category states without inventing states."""

    def __init__(self, product_config: dict[str, Any], html_file_path: str = ""):
        super().__init__(product_config, html_file_path)
        self.strategy_name = "complex"
        self.content_extractor = ContentExtractor(
            expected_language=str(product_config.get("language", "")) or None
        )
        self.section_extractor = SectionExtractor()
        self.flexible_builder = FlexibleBuilder()
        self.filter_detector = FilterDetector()
        self.tab_detector = TabDetector()
        soft_category_path = product_config.get("soft_category_path")
        if not isinstance(soft_category_path, str) or not soft_category_path:
            raise ValueError("ComplexContentStrategy 缺少可信区域配置路径。")
        lookup_recorder = product_config.get("soft_category_lookup_recorder")
        if lookup_recorder is not None and not callable(lookup_recorder):
            raise ValueError("soft_category_lookup_recorder 必须可以被调用。")
        self.region_processor = RegionProcessor(
            soft_category_path,
            lookup_recorder=lookup_recorder,
        )

    def extract_flexible_content(
        self,
        soup: BeautifulSoup,
        url: str = "",
    ) -> dict[str, Any]:
        base_metadata = self.content_extractor.extract_base_metadata(
            soup, url, self.html_file_path
        )
        pricing_boundary = locate_formal_pricing_boundary(soup)
        common_sections = self.section_extractor.extract_all_sections(
            soup, pricing_boundary
        )
        filter_analysis = self.filter_detector.detect_filters(soup)
        tab_analysis = self.tab_detector.detect_tabs(soup)
        grouped_tabs = self.tab_detector.detect_grouped_tabs(soup)

        pricing_root = pricing_boundary.formal_root
        if pricing_root is None or "pricing-detail-tab" not in pricing_root.get(
            "class", []
        ):
            raise ValueError("Complex 页面缺少正式 pricing-detail-tab 选择器。")
        software_scopes = self._software_scopes(pricing_root, filter_analysis)
        software_trailing_fragments = (
            self._single_software_trailing_fragments(software_scopes[0][1])
            if len(software_scopes) == 1
            else []
        )

        region_options = filter_analysis.get("region_options")
        if not filter_analysis.get("region_visible") or not isinstance(
            region_options, list
        ) or not region_options:
            raise ValueError("Complex 页面必须声明可见且非空的区域筛选器。")
        regions: list[tuple[str, str]] = []
        seen_regions: set[str] = set()
        for region_option in region_options:
            region = str(region_option.get("value", "")).strip()
            region_label = str(region_option.get("label", "")).strip()
            if not region or not region_label or region in seen_regions:
                raise ValueError("区域选项缺少名称、值或包含重复值。")
            seen_regions.add(region)
            regions.append((region, region_label))

        states: list[dict[str, Any]] = []
        category_catalog: list[dict[str, str]] = []
        category_by_target: dict[str, dict[str, str]] = {}
        software_is_visible = bool(filter_analysis.get("software_visible"))
        prepared_scopes: list[
            tuple[
                dict[str, str],
                list[tuple[dict[str, str] | None, IndexedFragmentProjector]],
                IndexedFragmentProjector,
                dict[str, tuple[str, ...]],
            ]
        ] = []
        for software_option, software_panel in software_scopes:
            software = software_option["value"]
            category_tabs = self._category_tabs(
                software_panel,
                grouped_tabs,
            )
            leaves, shared_fragments = self._content_leaves(
                software_panel,
                category_tabs,
            )
            shared_fragments = [
                *shared_fragments,
                *software_trailing_fragments,
            ]
            exclusions_by_region = {
                region: self.region_processor.rules.excluded_table_ids(
                    software, region
                )
                for region, _region_label in regions
            }
            relevant_table_ids = frozenset(
                table_id
                for exclusions in exclusions_by_region.values()
                for table_id in exclusions
            )
            indexed_leaves = [
                (
                    category,
                    IndexedFragmentProjector.build(
                        [panel],
                        relevant_table_ids=relevant_table_ids,
                    ),
                )
                for category, panel in leaves
            ]
            shared_projector = IndexedFragmentProjector.build(
                shared_fragments,
                relevant_table_ids=relevant_table_ids,
            )
            all_projectors = [
                shared_projector,
                *(projector for _category, projector in indexed_leaves),
            ]
            applicable_by_region = {
                region: applicable_exclusions_for_software(
                    all_projectors,
                    exclusions,
                )
                for region, exclusions in exclusions_by_region.items()
            }
            prepared_scopes.append(
                (
                    software_option,
                    indexed_leaves,
                    shared_projector,
                    applicable_by_region,
                )
            )
            for category in category_tabs:
                option = {
                    "href": f"#{category['target_id']}",
                    "label": category["label"],
                }
                existing = category_by_target.get(category["target_id"])
                if existing is not None:
                    if existing != option:
                        raise ValueError(
                            "相同 Category target 在不同 Software 中使用了不同名称。"
                        )
                    continue
                category_by_target[category["target_id"]] = option
                category_catalog.append(option)

        for (
            software_option,
            indexed_leaves,
            shared_projector,
            applicable_by_region,
        ) in prepared_scopes:
            software = software_option["value"]
            for region, region_label in regions:
                applicable_exclusions = applicable_by_region[region]
                shared_content = shared_projector.project(
                    applicable_exclusions
                )
                for category, projector in indexed_leaves:
                    content = projector.project(
                        applicable_exclusions
                    )
                    criteria: tuple[tuple[str, str], ...] = (("region", region),)
                    labels = (region_label,)
                    if software_is_visible:
                        criteria = (("software", software),) + criteria
                        labels = (software_option["label"],) + labels
                    if category is not None:
                        criteria += (("category", category["target_id"]),)
                        labels += (category["label"],)
                    state: dict[str, Any] = {
                        "criteria": criteria,
                        "labels": labels,
                        "content": content,
                    }
                    if shared_content:
                        state["sharedContent"] = shared_content
                    states.append(state)

        selected_tab_analysis = {
            **tab_analysis,
            "category_tabs": category_catalog,
        }

        content_groups = self.flexible_builder.build_complex_content_groups(states)
        return self.flexible_builder.build_flexible_page(
            base_metadata,
            common_sections,
            {
                "baseContent": resolve_page_global_base_content(
                    soup,
                    self.product_config,
                    language=str(base_metadata.get("Language", "")),
                ),
                "contentGroups": content_groups,
                "strategy_type": "complex",
                "filter_analysis": filter_analysis,
                "tab_analysis": selected_tab_analysis,
            },
        )

    def extract_common_sections(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        boundary = locate_formal_pricing_boundary(soup)
        return self.section_extractor.extract_all_sections(  # type: ignore[return-value]
            soup, boundary
        )

    def _software_scopes(
        self,
        pricing_root: Tag,
        filter_analysis: dict[str, Any],
    ) -> list[tuple[dict[str, str], Tag]]:
        options = filter_analysis.get("software_options")
        if not isinstance(options, list) or not options:
            raise ValueError("Complex 页面必须有非空的软件选项。")
        if not filter_analysis.get("software_visible") and len(options) != 1:
            raise ValueError("隐藏软件筛选器必须恰好声明一个选项。")

        dynamic_content = [
            child
            for child in pricing_root.children
            if isinstance(child, Tag)
            and "tab-content" in child.get("class", [])
        ]
        static_content = [
            child
            for child in pricing_root.children
            if isinstance(child, Tag)
            and "technical-azure-selector" in child.get("class", [])
            and "tab-control-selector" in child.get("class", [])
        ]
        top_content = self._exactly_one(
            dynamic_content + static_content,
            "软件内容容器",
        )
        scopes: list[tuple[dict[str, str], Tag]] = []
        seen_values: set[str] = set()
        seen_targets: set[str] = set()
        for raw_option in options:
            software = str(raw_option.get("value", "")).strip()
            label = " ".join(str(raw_option.get("label", "")).split())
            href = str(raw_option.get("href", "")).strip()
            target_id = href.removeprefix("#")
            if not software or not label or not href.startswith("#") or not target_id:
                raise ValueError("软件选项缺少名称、值或内容目标。")
            if software in seen_values or target_id in seen_targets:
                raise ValueError("软件选项包含重复值或重复内容目标。")
            seen_values.add(software)
            seen_targets.add(target_id)
            panel = self._exactly_one(
                top_content.find_all("div", id=target_id, recursive=False),
                f"软件内容面板 {target_id}",
            )
            scopes.append(
                (
                    {"value": software, "label": label, "href": href},
                    panel,
                )
            )
        return scopes

    @staticmethod
    def _single_software_trailing_fragments(software_panel: Tag) -> list[Tag]:
        container = software_panel.parent
        if not isinstance(container, Tag):
            return []
        direct_panels = [
            child
            for child in container.children
            if isinstance(child, Tag) and "tab-panel" in child.get("class", [])
        ]
        if len(direct_panels) != 1 or direct_panels[0] is not software_panel:
            return []

        fragments: list[Tag] = []
        after_panel = False
        for child in container.children:
            if child is software_panel:
                after_panel = True
                continue
            if after_panel and isinstance(child, Tag):
                fragments.append(child)
        return fragments

    def _category_tabs(
        self,
        software_panel: Tag,
        grouped_tabs: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, str]]:
        panel_id = str(software_panel.get("id", ""))
        raw_grouped = grouped_tabs.get(panel_id)
        if raw_grouped is None:
            raw_grouped = []
        if not isinstance(raw_grouped, list):
            raise ValueError("软件内容面板的 Category 选项不是列表。")
        if not raw_grouped:
            if software_panel.select_one(
                "ul.os-tab-nav.category-tabs, select.category-tabs"
            ) is not None:
                raise ValueError("软件内容面板声明了 Category 控件但没有可识别选项。")
            return []
        result = [
            {
                "target_id": str(tab.get("href", "")).removeprefix("#"),
                "label": " ".join(str(tab.get("label", "")).split()),
                "target_exists": bool(tab.get("target_exists")),
                "is_default": bool(tab.get("is_default")),
            }
            for tab in raw_grouped
        ]
        if any(not tab["target_id"] or not tab["label"] for tab in result):
            raise ValueError("Category 选项缺少目标或名称。")
        if len({tab["target_id"] for tab in result}) != len(result):
            raise ValueError("Category 选项包含重复目标。")
        missing = [index for index, tab in enumerate(result) if not tab["target_exists"]]
        if missing:
            aggregate = result[0]
            if (
                missing != [0]
                or aggregate["label"].casefold() not in {"all", "全部"}
                or not aggregate["is_default"]
                or len(result) == 1
            ):
                raise ValueError(
                    "Category 选项指向不存在的内容面板，且不是唯一的首项 All/全部汇总控件。"
                )
            result = result[1:]
        return [
            {"target_id": tab["target_id"], "label": tab["label"]}
            for tab in result
        ]

    def _content_leaves(
        self,
        software_panel: Tag,
        category_tabs: list[dict[str, str]],
    ) -> tuple[list[tuple[dict[str, str] | None, Tag]], list[Tag]]:
        if not category_tabs:
            bodies = [
                child
                for child in software_panel.children
                if isinstance(child, Tag)
                and (
                    "tab-content" in child.get("class", [])
                    or "tabContent" in child.get("class", [])
                )
            ]
            body = self._exactly_one(bodies, "无 Category 软件内容主体")
            return [(None, body)], []

        panels: list[Tag] = []
        for category in category_tabs:
            target_id = category["target_id"]
            panels.append(
                self._exactly_one(
                    software_panel.find_all(id=target_id),
                    f"Category 内容面板 {target_id}",
                )
            )

        parent = panels[0].parent
        if not isinstance(parent, Tag) or any(
            panel.parent is not parent for panel in panels
        ):
            raise ValueError("Category target 没有唯一共同直接父节点。")
        expected_ids = [category["target_id"] for category in category_tabs]
        actual_panels = [
            child
            for child in parent.children
            if isinstance(child, Tag)
            and "tab-panel" in child.get("class", [])
            and child.get("id")
        ]
        actual_ids = [str(panel.get("id")) for panel in actual_panels]
        if actual_ids != expected_ids or any(
            actual is not expected
            for actual, expected in zip(actual_panels, panels)
        ):
            raise ValueError(
                "Category 控件与共同父节点的直接内容面板不是同一个完整有序集合。"
            )
        return list(zip(category_tabs, panels)), self._shared_fragments(
            parent, panels[0]
        )

    @staticmethod
    def _shared_fragments(inner_content: Tag, first_panel: Tag) -> list[Tag]:
        fragments: list[Tag] = []
        for child in inner_content.children:
            if child is first_panel:
                break
            if isinstance(child, Tag) and child.select_one(
                "ul.os-tab-nav.category-tabs, select.category-tabs"
            ) is None:
                fragments.append(child)
        return fragments

    @staticmethod
    def _exactly_one(candidates: list[Tag], name: str) -> Tag:
        if len(candidates) != 1:
            raise ValueError(
                f"源页面必须恰好包含一个{name}，实际为 {len(candidates)} 个。"
            )
        return candidates[0]

    def _get_product_key(self) -> str:
        value = self.product_config.get("product_key")
        if isinstance(value, str) and value:
            return value
        if self.html_file_path:
            return Path(self.html_file_path).stem
        return "unknown"
