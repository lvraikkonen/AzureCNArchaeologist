"""Complex pricing extraction adapted from the v0.5.5 core Strategy."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from src.core.region_processor import (
    RegionProcessor,
    project_fragment_for_region,
    project_fragments_for_region,
    validate_exclusion_targets,
)
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

        region_options = filter_analysis.get("region_options")
        if not filter_analysis.get("region_visible") or not isinstance(
            region_options, list
        ) or not region_options:
            raise ValueError("Complex 页面必须声明可见且非空的区域筛选器。")

        states: list[dict[str, Any]] = []
        category_domain: list[dict[str, str]] | None = None
        software_is_visible = bool(filter_analysis.get("software_visible"))
        for software_option, software_panel in software_scopes:
            software = software_option["value"]
            category_tabs = self._category_tabs(
                software_panel,
                grouped_tabs,
            )
            current_domain = [
                {
                    "href": f"#{category['target_id']}",
                    "label": category["label"],
                }
                for category in category_tabs
            ]
            if category_domain is None:
                category_domain = current_domain
            elif current_domain != category_domain:
                raise ValueError(
                    "可见软件选项的 Category 名称与目标必须完全一致。"
                )

            inner_content = self._exactly_one(
                [
                    child
                    for child in software_panel.children
                    if isinstance(child, Tag)
                    and "tab-content" in child.get("class", [])
                ],
                "Category 内容容器",
            )
            panel_by_id = self._category_panels(inner_content, category_tabs)
            shared_fragments = self._shared_fragments(
                inner_content, panel_by_id[category_tabs[0]["target_id"]]
            )

            for region_option in region_options:
                region = str(region_option.get("value", "")).strip()
                region_label = str(region_option.get("label", "")).strip()
                if not region or not region_label:
                    raise ValueError("区域选项缺少名称或值。")
                exclusions = self.region_processor.rules.excluded_table_ids(
                    software, region
                )
                applicable_exclusions = validate_exclusion_targets(
                    pricing_root, exclusions
                )
                shared_content = project_fragments_for_region(
                    shared_fragments,
                    source_scope=pricing_root,
                    excluded_table_ids=applicable_exclusions,
                    validate_targets=False,
                )
                for category in category_tabs:
                    target_id = category["target_id"]
                    content = project_fragment_for_region(
                        panel_by_id[target_id],
                        source_scope=pricing_root,
                        excluded_table_ids=applicable_exclusions,
                        validate_targets=False,
                    )
                    criteria: tuple[tuple[str, str], ...] = (
                        ("region", region),
                        ("category", target_id),
                    )
                    labels = (region_label, category["label"])
                    if software_is_visible:
                        criteria = (("software", software),) + criteria
                        labels = (software_option["label"],) + labels
                    state: dict[str, Any] = {
                        "criteria": criteria,
                        "labels": labels,
                        "content": content,
                    }
                    if shared_content:
                        state["sharedContent"] = shared_content
                    states.append(state)

        assert category_domain is not None
        selected_tab_analysis = {
            **tab_analysis,
            "category_tabs": category_domain,
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

    def _category_tabs(
        self,
        software_panel: Tag,
        grouped_tabs: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, str]]:
        panel_id = str(software_panel.get("id", ""))
        raw_grouped = grouped_tabs.get(panel_id)
        if not isinstance(raw_grouped, list) or not raw_grouped:
            raise ValueError("软件内容面板没有 Category 选项。")
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

    def _category_panels(
        self,
        inner_content: Tag,
        category_tabs: list[dict[str, str]],
    ) -> dict[str, Tag]:
        expected_ids = [tab["target_id"] for tab in category_tabs]
        panels = [
            child
            for child in inner_content.children
            if isinstance(child, Tag)
            and "tab-panel" in child.get("class", [])
            and child.get("id")
        ]
        actual_ids = [str(panel.get("id")) for panel in panels]
        if actual_ids != expected_ids:
            raise ValueError(
                "Category 控件与直接内容面板不是同一个完整有序集合。"
            )
        return dict(zip(actual_ids, panels))

    @staticmethod
    def _shared_fragments(inner_content: Tag, first_panel: Tag) -> list[Tag]:
        fragments: list[Tag] = []
        for child in inner_content.children:
            if child is first_panel:
                break
            if isinstance(child, Tag):
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
