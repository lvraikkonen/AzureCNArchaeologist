#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
复杂内容策略 - 基于新架构创建
处理复杂的多筛选器和tab组合，如Cloud Services类型页面
全新实现，基于新工具类架构
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup, Tag

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.strategies.base_strategy import BaseStrategy
from src.core.cms_state_contract import CmsState
from src.core.region_projected_shared_content import (
    RegionProjectedSharedContentError,
    RegionProjectedSharedContentEvidence,
    RegionProjectedSharedContentResolver,
)
from src.core.region_processor import RegionProcessor
from src.core.scoped_source_content import (
    ScopedSourceContentError,
    extract_category_ancestor_fragment,
    extract_software_scoped_prefix,
    resolve_page_global_base_content,
)
from src.core.source_reachability import (
    ReachableCmsState,
    SourceReachability,
)
from src.core.strict_soft_category_projection import (
    StrictSoftCategoryProjectionError,
)
from src.utils.content.content_extractor import ContentExtractor
from src.utils.content.section_extractor import SectionExtractor
from src.utils.content.flexible_builder import FlexibleBuilder
from src.detectors.filter_detector import FilterDetector
from src.detectors.tab_detector import TabDetector
from src.utils.content.content_utils import classify_pricing_section, filter_sections_by_type
from src.utils.html.cleaner import clean_html_content
from src.utils.media.image_processor import preprocess_image_paths
from src.core.logging import get_logger

logger = get_logger(__name__)


class ComplexContentStrategy(BaseStrategy):
    """
    复杂内容策略 - 新架构实现
    Type C: 复杂页面处理 - Cloud Services类型
    
    特点：
    - 具有多种筛选器组合：软件类别、地区、category tabs等
    - 复杂的交互和内容映射关系
    - 需要处理多维度内容组合
    - 使用新工具类架构：ContentExtractor + SectionExtractor + FlexibleBuilder + FilterDetector + TabDetector
    """

    def __init__(self, product_config: Dict[str, Any], html_file_path: str = ""):
        """
        初始化复杂内容策略
        
        Args:
            product_config: 产品配置信息
            html_file_path: HTML文件路径
        """
        super().__init__(product_config, html_file_path)
        self.strategy_name = "complex_content"
        
        # 初始化工具类
        self.content_extractor = ContentExtractor()
        self.section_extractor = SectionExtractor()
        self.flexible_builder = FlexibleBuilder()
        
        # 初始化检测器
        self.filter_detector = FilterDetector()
        self.tab_detector = TabDetector()
        
        # Legacy RegionProcessor belongs only to the quarantined experiment.
        # Formal strategy construction must not initialize it.
        self._unvalidated_experimental_region_processor: (
            RegionProcessor | None
        ) = None
        self.region_projected_shared_content = (
            RegionProjectedSharedContentResolver(project_root)
        )
        logger.info(f"🔧 初始化复杂内容策略: {self._get_product_key()}")

    def extract_flexible_content(
        self,
        soup: BeautifulSoup,
        url: str = "",
        *,
        source_reachability: SourceReachability,
    ) -> Dict[str, Any]:
        """Extract one formal ComplexFilter payload from source-proven states.

        Formal extraction never derives a state space from the payload or from
        globally flattened filter options.  The independently resolved source
        relation is mandatory and every content mapping is keyed by
        :class:`CmsState`.
        """

        if not isinstance(source_reachability, SourceReachability):
            raise TypeError(
                "Formal complex extraction requires SourceReachability"
            )
        logger.info("🔧 开始复杂内容策略提取（source-proven relation）...")
        base_metadata = self.content_extractor.extract_base_metadata(
            soup, url, self.html_file_path
        )
        base_content = self._extract_page_global_base_content(
            soup,
            language=source_reachability.language,
        )
        common_sections = self.section_extractor.extract_all_sections(soup)
        content_mapping = self._extract_reachable_content_mapping(
            soup, source_reachability
        )
        content_groups = self.flexible_builder.build_complex_content_groups(
            source_reachability, content_mapping
        )
        strategy_content = {
            "baseContent": base_content,
            "contentGroups": content_groups,
            "strategy_type": "complex",
            "source_reachability": source_reachability,
        }
        flexible_data = self.flexible_builder.build_flexible_page(
            base_metadata, common_sections, strategy_content
        )
        logger.info("✅ 复杂内容策略提取完成（flexible JSON格式）")
        return flexible_data

    def _extract_page_global_base_content(
        self,
        soup: BeautifulSoup,
        *,
        language: str,
    ) -> str:
        """Emit only Product-Definition-authorized page-global content."""

        return resolve_page_global_base_content(
            soup,
            self.product_config,
            language=language,
        )

    def extract_unvalidated_experimental_content(
        self, soup: BeautifulSoup, url: str = ""
    ) -> Dict[str, Any]:
        """Preserve the frozen P0 experimental extraction behavior.

        The quarantined VM experiment predates formal v0.4 source reachability.
        It is intentionally isolated under an explicitly unvalidated method so
        the formal extraction entry point cannot silently fall back to it.
        """

        logger.info("🔧 开始P0实验性复杂内容提取（unvalidated legacy）...")
        base_metadata = self.content_extractor.extract_base_metadata(
            soup, url, self.html_file_path
        )
        common_sections = self.section_extractor.extract_all_sections(soup)
        filter_analysis = self._detect_unvalidated_experimental_filters(soup)
        self._unvalidated_experimental_software_panels = {
            str(option.get("value", "")): str(
                option.get("href", "")
            ).removeprefix("#")
            for option in filter_analysis.get("software_options", [])
            if option.get("value") and option.get("href")
        }
        tab_analysis = self.tab_detector.detect_tabs(soup)
        grouped_tabs = self.tab_detector.detect_grouped_tabs(soup)
        self._remove_missing_aggregate_tabs_for_unvalidated_experiment(
            soup, tab_analysis, grouped_tabs
        )
        content_mapping = self._extract_complex_content_mapping(
            soup, filter_analysis, tab_analysis, grouped_tabs
        )
        content_groups = (
            self.flexible_builder
            .build_unvalidated_experimental_complex_content_groups(
                filter_analysis, tab_analysis, content_mapping
            )
        )
        base_content = (
            self._extract_main_content(soup) if not content_groups else ""
        )
        strategy_content = {
            "baseContent": base_content,
            "contentGroups": content_groups,
            "strategy_type": "complex",
            "filter_analysis": filter_analysis,
            "tab_analysis": tab_analysis,
            "unvalidated_experimental_legacy": True,
        }
        payload = self.flexible_builder.build_flexible_page(
            base_metadata, common_sections, strategy_content
        )
        logger.info("✅ P0实验性复杂内容提取完成（unvalidated legacy）")
        return payload

    def _get_unvalidated_experimental_region_processor(
        self,
    ) -> RegionProcessor:
        """Construct the legacy processor only inside the quarantined path."""

        processor = self._unvalidated_experimental_region_processor
        if processor is None:
            processor = RegionProcessor()
            self._unvalidated_experimental_region_processor = processor
        return processor

    @staticmethod
    def _detect_unvalidated_experimental_filters(
        soup: BeautifulSoup,
    ) -> Dict[str, Any]:
        """Use the frozen P0 mobile-select projection without v0.4 gates."""

        def detect(
            container_selector: str,
            select_id: str,
        ) -> Dict[str, Any]:
            container = soup.select_one(container_selector)
            if not isinstance(container, Tag):
                return {
                    "exists": False,
                    "visible": False,
                    "options": [],
                }
            style = str(container.get("style", ""))
            compact_style = "".join(style.casefold().split())
            select = soup.find("select", id=select_id)
            options: list[dict[str, str]] = []
            if isinstance(select, Tag):
                for option in select.find_all("option"):
                    value = str(option.get("value", "")).strip()
                    href = str(option.get("data-href", "")).strip()
                    label = option.get_text().strip()
                    if (
                        value
                        and label
                        and "加载中" not in label
                        and "请选择" not in label
                    ):
                        options.append(
                            {
                                "value": value,
                                "href": href,
                                "label": label,
                            }
                        )
            return {
                "exists": True,
                "visible": "display:none" not in compact_style,
                "options": options,
            }

        software = detect(
            "div.dropdown-container.software-kind-container",
            "software-box",
        )
        region = detect(
            "div.dropdown-container.region-container",
            "region-box",
        )
        return {
            "has_region": region["exists"],
            "has_software": software["exists"],
            "region_visible": region["visible"],
            "software_visible": software["visible"],
            "region_options": region["options"],
            "software_options": software["options"],
        }

    def _remove_missing_aggregate_tabs_for_unvalidated_experiment(
        self,
        soup: BeautifulSoup,
        tab_analysis: Dict[str, Any],
        grouped_tabs: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        """Suppress only non-materialized All/全部 tabs on the P0 legacy path.

        Missing aggregate targets are a general source pattern.  Any other
        missing target remains in the relation and therefore fails extraction.
        """

        def keep(tab: Dict[str, Any]) -> bool:
            target_id = str(tab.get("href", "")).removeprefix("#")
            label = " ".join(str(tab.get("label", "")).split()).casefold()
            is_aggregate = label in {"all", "全部"}
            target_missing = soup.find(id=target_id) is None
            return not (is_aggregate and target_missing)

        original = list(tab_analysis.get("category_tabs", []))
        filtered = [tab for tab in original if keep(tab)]
        if len(filtered) == len(original):
            return
        if filtered and not any(tab.get("is_default") for tab in filtered):
            filtered[0]["is_default"] = True
        tab_analysis["category_tabs"] = filtered
        tab_analysis["total_category_tabs"] = len(filtered)
        tab_analysis["has_tabs"] = bool(filtered)
        tab_analysis["has_complex_tabs"] = bool(filtered)
        tab_analysis["category_default_value"] = (
            str(filtered[0].get("href", "")).removeprefix("#")
            if filtered
            else None
        )

        for group_id, tabs in list(grouped_tabs.items()):
            kept = [tab for tab in tabs if keep(tab)]
            if kept and not any(tab.get("is_default") for tab in kept):
                kept[0]["is_default"] = True
            if kept:
                grouped_tabs[group_id] = kept
            else:
                grouped_tabs.pop(group_id)
        logger.info("✓ 移除缺失target的All/全部 aggregate tab（P0 legacy）")

    def extract_common_sections(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        提取通用sections（Banner、Description、QA等）
        
        Args:
            soup: BeautifulSoup解析的HTML对象
            
        Returns:
            commonSections列表
        """
        return self.section_extractor.extract_all_sections(soup)

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """
        提取复杂页面的主要内容 - 使用智能分类逻辑
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            主要内容HTML字符串
        """
        logger.info("📝 提取复杂页面主要内容（智能分类模式）...")
        
        try:
            # 方案1: 查找technical-azure-selector内的pricing-page-section，使用智能分类
            logger.info("🔍 查找technical-azure-selector内容（智能分类）...")
            technical_selector = soup.find('div', class_='technical-azure-selector')
            if technical_selector:
                pricing_sections = technical_selector.find_all('div', class_='pricing-page-section')
                if pricing_sections:
                    # 使用智能分类过滤，只保留content类型的section
                    content_sections = filter_sections_by_type(
                        pricing_sections, 
                        include_types=['content']
                    )
                    
                    if content_sections:
                        main_content = ""
                        for section in content_sections:
                            main_content += str(section)
                            section_type = classify_pricing_section(section)
                            logger.info(f"✓ 添加复杂策略technical-azure-selector section (类型: {section_type})")
                        
                        logger.info(f"✓ 找到复杂策略technical-azure-selector内容，共{len(content_sections)}个content sections")
                        return clean_html_content(main_content)
                
                # 如果没有分类为content的section，返回整个主容器但过滤FAQ/SLA
                logger.info("🔍 返回整个technical-azure-selector容器...")
                all_sections = technical_selector.find_all('div', class_='pricing-page-section')
                
                filtered_main_content = ""
                for section in all_sections:
                    section_type = classify_pricing_section(section)
                    if section_type in ['content', 'other']:  # 包含other类型以确保不遗漏内容
                        filtered_main_content += str(section)
                        logger.info(f"✓ 添加{section_type}类型section到复杂策略内容")
                
                if filtered_main_content:
                    return clean_html_content(filtered_main_content)
                else:
                    # 最后fallback：返回完整主容器
                    return clean_html_content(str(technical_selector))
            
            # 方案2: 查找所有pricing-page-section，智能分类后处理
            logger.info("🔍 查找所有pricing-page-section（智能分类）...")
            all_pricing_sections = soup.find_all('div', class_='pricing-page-section')
            
            if all_pricing_sections:
                main_content = ""
                processed_sections = 0
                
                # 跳过第一个section（通常是Description），从第二个开始智能分类
                for section in all_pricing_sections[1:]:
                    section_type = classify_pricing_section(section)
                    
                    if section_type == 'content':
                        main_content += str(section)
                        processed_sections += 1
                        logger.info(f"✓ 添加复杂策略content section #{processed_sections}")
                    elif section_type in ['faq', 'sla']:
                        logger.info(f"⏩ 跳过{section_type} section（将由SectionExtractor处理）")
                    else:
                        logger.info(f"⏩ 跳过{section_type} section")
                
                if main_content:
                    logger.info(f"✓ 复杂策略智能分类完成，处理了{processed_sections}个content sections")
                    return clean_html_content(main_content)
            
            # 方案3: 使用ContentExtractor的主要内容提取
            logger.info("🔍 使用ContentExtractor主要内容提取...")
            main_content = self.content_extractor.extract_main_content(soup)
            if main_content:
                return clean_html_content(main_content)
            
            logger.info("⚠ 未找到合适的复杂页面主要内容")
            return ""
            
        except Exception as e:
            logger.info(f"⚠ 复杂页面主要内容提取失败: {e}")
            return ""

    def _extract_reachable_content_mapping(
        self,
        soup: BeautifulSoup,
        source_reachability: SourceReachability,
    ) -> Dict[CmsState, Dict[str, str]]:
        """Extract only the ordered states proven reachable by the source."""

        if not source_reachability.ordered_states:
            raise ValueError("Source reachability contains no CMS states")
        category_panels_by_software: dict[str, list[str]] = {}
        expected_shared_by_software: dict[
            str, RegionProjectedSharedContentEvidence
        ] = {}
        for reachable_state in source_reachability.ordered_states:
            evidence = reachable_state.source_evidence
            if (
                evidence.software_panel_id
                and evidence.category_panel_id
            ):
                category_ids = category_panels_by_software.setdefault(
                    evidence.software_panel_id, []
                )
                if evidence.category_panel_id not in category_ids:
                    category_ids.append(evidence.category_panel_id)
            shared = evidence.region_projected_shared_content
            if shared is not None:
                panel_id = evidence.software_panel_id
                if not panel_id or panel_id != shared.software_panel_id:
                    raise ValueError(
                        "Region-Projected Shared Content has no exact "
                        "software-panel scope"
                    )
                prior = expected_shared_by_software.setdefault(
                    panel_id, shared
                )
                if prior != shared:
                    raise ValueError(
                        "Reachable states disagree on Region-Projected Shared "
                        f"Content evidence for {panel_id!r}"
                    )

        resolved_shared_by_software: dict[
            str, RegionProjectedSharedContentEvidence
        ] = {}
        for panel_id, expected in expected_shared_by_software.items():
            category_panel_ids = tuple(
                category_panels_by_software.get(panel_id, ())
            )
            if category_panel_ids != expected.category_panel_ids:
                raise ValueError(
                    "Region-Projected Shared Content Category scope differs "
                    f"from the reachable relation for {panel_id!r}"
                )
            try:
                fragment = extract_category_ancestor_fragment(
                    soup,
                    panel_id,
                    expected_category_panel_ids=category_panel_ids,
                )
                if fragment is None:
                    raise RegionProjectedSharedContentError(
                        "Expected ancestor content is missing"
                    )
                resolved = self.region_projected_shared_content.resolve(
                    fragment,
                    internal_software_value=(
                        expected.internal_software_value
                    ),
                    region_values=tuple(
                        projection.region_value
                        for projection in expected.projections
                    ),
                )
            except (
                ScopedSourceContentError,
                RegionProjectedSharedContentError,
            ) as error:
                raise ValueError(
                    "Unable to replay Region-Projected Shared Content: "
                    f"{error}"
                ) from error
            if resolved != expected:
                raise ValueError(
                    "Region-Projected Shared Content replay differs from "
                    f"SourceReachability for {panel_id!r}"
                )
            resolved_shared_by_software[panel_id] = resolved

        content_mapping: Dict[CmsState, Dict[str, str]] = {}
        for reachable_state in source_reachability.ordered_states:
            if reachable_state.cms_state in content_mapping:
                raise ValueError(
                    "Source reachability contains duplicate CmsState "
                    f"{reachable_state.cms_state.criteria!r}"
                )
            content_mapping[reachable_state.cms_state] = (
                self._find_reachable_content(
                    soup,
                    reachable_state,
                    expected_category_panel_ids=tuple(
                        category_panels_by_software.get(
                            (
                                reachable_state.source_evidence
                                .software_panel_id
                                or ""
                            ),
                            (),
                        )
                    ),
                    region_projected_shared_content_by_software=(
                        resolved_shared_by_software
                    ),
                )
            )
        return content_mapping

    def _find_reachable_content(
        self,
        soup: BeautifulSoup,
        reachable_state: ReachableCmsState,
        *,
        expected_category_panel_ids: tuple[str, ...],
        region_projected_shared_content_by_software: dict[
            str, RegionProjectedSharedContentEvidence
        ],
    ) -> Dict[str, str]:
        """Resolve one exact source locator without rereads or fallback panels."""

        evidence = reachable_state.source_evidence
        state_values = reachable_state.cms_state.to_dict()
        evidence_values = {
            "region": evidence.region_value,
            "software": evidence.software_value,
            "category": evidence.category_value,
        }
        for key, value in state_values.items():
            if evidence_values.get(key) != value:
                raise ValueError(
                    "Reachable CmsState does not match its source evidence: "
                    f"{reachable_state.cms_state.criteria!r}"
                )
        if len(reachable_state.state_label_segments) != len(
            reachable_state.cms_state.criteria
        ):
            raise ValueError(
                "Reachable state labels do not align with CMS criteria"
            )

        panel_id = (
            evidence.category_panel_id or evidence.software_panel_id
        )
        if not panel_id:
            raise ValueError(
                "Reachable complex state has no exact source panel locator"
            )
        base_content = soup.find(id=panel_id)
        if not isinstance(base_content, Tag):
            raise ValueError(
                f"Missing source-proven target panel {panel_id!r}"
            )

        software_scoped_prefix = ""
        region_projected_shared_content = ""
        if evidence.software_panel_id and evidence.category_panel_id:
            expected_shared = (
                evidence.region_projected_shared_content
            )
            if expected_shared is not None:
                if evidence.software_scoped_prefix is not None:
                    raise ValueError(
                        "A state cannot use both Software-scoped Prefix "
                        "Content and Region-Projected Shared Content"
                    )
                resolved_shared = (
                    region_projected_shared_content_by_software.get(
                        evidence.software_panel_id
                    )
                )
                if (
                    resolved_shared is None
                    or resolved_shared != expected_shared
                    or evidence.region_value is None
                ):
                    raise ValueError(
                        "Region-Projected Shared Content is absent or differs "
                        "from SourceReachability for "
                        f"{reachable_state.cms_state.criteria!r}"
                    )
                region_projected_shared_content = (
                    resolved_shared.projection_for(
                        evidence.region_value
                    ).projected_html
                )
            else:
                try:
                    prefix_fragment = extract_software_scoped_prefix(
                        soup,
                        evidence.software_panel_id,
                        expected_category_panel_ids=(
                            expected_category_panel_ids
                        ),
                    )
                except ScopedSourceContentError as error:
                    raise ValueError(
                        "Unable to resolve source-proven software-scoped "
                        f"prefix: {error}"
                    ) from error

                expected_prefix = evidence.software_scoped_prefix
                if (prefix_fragment is None) != (expected_prefix is None):
                    raise ValueError(
                        "Software-scoped prefix presence differs from "
                        "SourceReachability for "
                        f"{reachable_state.cms_state.criteria!r}"
                    )
                if (
                    prefix_fragment is not None
                    and expected_prefix is not None
                ):
                    if (
                        expected_prefix.software_value
                        != evidence.software_value
                        or expected_prefix.software_panel_id
                        != evidence.software_panel_id
                        or expected_prefix.category_panel_ids
                        != expected_category_panel_ids
                        or expected_prefix.fragment_count
                        != prefix_fragment.fragment_count
                        or expected_prefix.source_html_sha256
                        != prefix_fragment.source_html_sha256
                    ):
                        raise ValueError(
                            "Software-scoped prefix identity differs from "
                            "SourceReachability for "
                            f"{reachable_state.cms_state.criteria!r}"
                        )
                    software_scoped_prefix = prefix_fragment.source_html
        elif (
            evidence.software_scoped_prefix is not None
            or evidence.region_projected_shared_content is not None
        ):
            raise ValueError(
                "Ancestor-scoped content evidence requires both software and "
                "Category panel identities"
            )

        region_value = evidence.region_value
        internal_software_value = evidence.software_value
        strict_projection = evidence.strict_soft_category_projection
        if region_value and internal_software_value:
            if strict_projection is None:
                raise ValueError(
                    "Reachable complex state has no frozen strict "
                    "soft-category projection"
                )
            if (
                strict_projection.region_value != region_value
                or strict_projection.software_value
                != internal_software_value
                or strict_projection.source_panel_id != panel_id
            ):
                raise ValueError(
                    "Strict soft-category projection scope differs from "
                    f"SourceReachability for {reachable_state.cms_state.criteria!r}"
                )
            replay_error_evidence = {
                "state_scope": {
                    "region": region_value,
                    "software": internal_software_value,
                    "source_panel_id": panel_id,
                },
                "configuration": {
                    "path": strict_projection.config_path,
                    "sha256": strict_projection.config_sha256,
                },
                "source_inventory": {
                    "source_panel_id": strict_projection.source_panel_id,
                    "source_table_count": (
                        strict_projection.source_table_count
                    ),
                    "source_idless_table_count": (
                        strict_projection.source_idless_table_count
                    ),
                    "source_table_ids": list(
                        strict_projection.source_table_ids
                    ),
                    "input_html_sha256": (
                        strict_projection.input_html_sha256
                    ),
                },
            }
            # SourceReachability was resolved from the canonical input. Formal
            # extraction receives the deterministic image-path projection of
            # that input, so compare the same projection before emitting the
            # frozen table projection.
            expected_input_soup = BeautifulSoup(
                strict_projection.input_html,
                "html.parser",
            )
            preprocess_image_paths(expected_input_soup)
            expected_input = expected_input_soup.find(id=panel_id)
            if (
                not isinstance(expected_input, Tag)
                or str(expected_input) != str(base_content)
            ):
                raise StrictSoftCategoryProjectionError(
                    "soft_category_projection_replay_mismatch",
                    (
                        "Extraction input differs from the frozen strict "
                        f"projection source for panel {panel_id!r}"
                    ),
                    evidence=replay_error_evidence,
                )
            projected_soup = BeautifulSoup(
                strict_projection.output_html,
                "html.parser",
            )
            preprocess_image_paths(projected_soup)
            projected_panel = projected_soup.find(id=panel_id)
            if not isinstance(projected_panel, Tag):
                raise StrictSoftCategoryProjectionError(
                    "soft_category_projection_replay_mismatch",
                    "Frozen projection output lost its source panel",
                    evidence=replay_error_evidence,
                )
            final_content = str(projected_panel)
        else:
            if strict_projection is not None:
                raise ValueError(
                    "Strict soft-category projection exists outside an exact "
                    "Region × Software × Category state"
                )
            final_content = str(base_content)

        return {
            "content": final_content,
            "software_scoped_prefix": software_scoped_prefix,
            "region_projected_shared_content": (
                region_projected_shared_content
            ),
        }

    def _extract_complex_content_mapping(self, soup: BeautifulSoup,
                                       filter_analysis: Dict[str, Any],
                                       tab_analysis: Dict[str, Any],
                                       grouped_tabs: Dict[str, List[Dict[str, Any]]] = None) -> Dict[str, Dict[str, str]]:
        """
        提取复杂页面的内容映射关系（带区域筛选和共享内容）
        
        Args:
            soup: BeautifulSoup对象
            filter_analysis: 筛选器分析结果
            tab_analysis: Tab分析结果
            
        Returns:
            增强的内容映射字典，包含具体内容和共享内容
            格式: {content_key: {"content": "...", "shared_content": "..."}}
        """
        logger.info("🗺️ 提取复杂页面内容映射（支持区域筛选）...")
        
        content_mapping = {}
        
        try:
            # 获取用于区域筛选的所有OS名称（支持多软件选项）
            region_processor = (
                self._get_unvalidated_experimental_region_processor()
            )
            all_os_names = (
                region_processor.get_os_names_for_region_filtering(
                    filter_analysis
                )
            )

            if not all_os_names:
                logger.warning("⚠ 无法获取有效的OS名称，将跳过区域表格筛选")
            else:
                logger.info(f"🎯 获取到 {len(all_os_names)} 个OS名称用于区域筛选: {all_os_names}")

            # 获取region选项
            region_options = filter_analysis.get("region_options", [])
            software_options = filter_analysis.get("software_options", [])
            category_tabs = tab_analysis.get("category_tabs", [])

            # 如果没有区域选项，使用默认
            if not region_options:
                region_options = [{"value": "default", "label": "默认"}]

            # 构建软件ID到OS名称的映射
            software_to_os_mapping = {}
            if software_options and all_os_names:
                for i, software in enumerate(software_options):
                    software_id = software.get("value", "")
                    # 使用对应索引的OS名称，如果索引超出范围则使用第一个
                    os_name = all_os_names[i] if i < len(all_os_names) else all_os_names[0]
                    software_to_os_mapping[software_id] = os_name
                    logger.info(f"🔗 软件映射: '{software_id}' -> OS名称 '{os_name}'")

            # 使用按组分类的tabs而非全局tabs
            if software_options and grouped_tabs:
                logger.info("🎯 使用软件组内独立tabs进行映射（修复后逻辑）")
                
                # 按软件进行分组映射
                for software in software_options:
                    software_id = software.get("value", "")
                    current_os_name = software_to_os_mapping.get(software_id, all_os_names[0] if all_os_names else "")
                    
                    # 获取当前软件对应的tabContent ID
                    target_tab_content_id = self._get_software_tab_content_id(software_id)
                    if not target_tab_content_id:
                        logger.warning(f"⚠ 无法获取软件'{software_id}'对应的tabContent ID")
                        continue
                    
                    # 获取当前软件组内的独立tabs
                    software_tabs = grouped_tabs.get(target_tab_content_id, [])
                    logger.info(f"🔍 软件'{software_id}'({target_tab_content_id})有 {len(software_tabs)} 个独立tabs")
                    
                    for region in region_options:
                        region_id = region.get("value", "")
                        
                        if software_tabs:
                            # 只与当前软件组内的tabs组合
                            for tab in software_tabs:
                                tab_id = tab.get("href", "").replace("#", "")
                                content_key = f"{region_id}_{software_id}_{tab_id}"
                                
                                content_result = self._find_content_by_mapping(soup, region_id, software_id, tab_id, current_os_name)
                                if content_result and (content_result.get("content") or content_result.get("shared_content")):
                                    content_mapping[content_key] = content_result
                                    logger.info(f"✓ 创建映射: {content_key} (软件组内独立tab)")
                        else:
                            # 软件组内没有tabs，只做region + software二维映射
                            content_key = f"{region_id}_{software_id}"
                            content_result = self._find_content_by_mapping(soup, region_id, software_id, None, current_os_name)
                            if content_result and (content_result.get("content") or content_result.get("shared_content")):
                                content_mapping[content_key] = content_result
                                logger.info(f"✓ 创建映射: {content_key} (无tabs的软件组)")
                                
            else:
                # 🔄 回退逻辑：使用原来的映射方式（保持兼容性）
                logger.info("🔄 使用回退映射逻辑（原有逻辑）")
                
                # 构建多维度映射
                for region in region_options:
                    region_id = region.get("value", "")

                    if software_options:
                        # 有软件筛选器的情况
                        for software in software_options:
                            software_id = software.get("value", "")
                            # 获取当前软件对应的OS名称
                            current_os_name = software_to_os_mapping.get(software_id, all_os_names[0] if all_os_names else "")

                            if category_tabs:
                                # 有category tabs的情况 - 三维映射
                                for tab in category_tabs:
                                    tab_id = tab.get("href", "").replace("#", "")
                                    content_key = f"{region_id}_{software_id}_{tab_id}"

                                    # 使用当前软件对应的OS名称进行区域筛选
                                    content_result = self._find_content_by_mapping(soup, region_id, software_id, tab_id, current_os_name)
                                    if content_result and (content_result.get("content") or content_result.get("shared_content")):
                                        content_mapping[content_key] = content_result
                            else:
                                # 只有region + software - 二维映射
                                content_key = f"{region_id}_{software_id}"
                                content_result = self._find_content_by_mapping(soup, region_id, software_id, None, current_os_name)
                                if content_result and (content_result.get("content") or content_result.get("shared_content")):
                                    content_mapping[content_key] = content_result
                    elif category_tabs:
                        # 只有region + category tabs - 二维映射
                        # 使用第一个OS名称（如果有的话）
                        fallback_os_name = all_os_names[0] if all_os_names else ""
                        for tab in category_tabs:
                            tab_id = tab.get("href", "").replace("#", "")
                            content_key = f"{region_id}_{tab_id}"
                            content_result = self._find_content_by_mapping(soup, region_id, None, tab_id, fallback_os_name)
                            if content_result and (content_result.get("content") or content_result.get("shared_content")):
                                content_mapping[content_key] = content_result
                    else:
                        # 只有region - 一维映射
                        # 使用第一个OS名称（如果有的话）
                        fallback_os_name = all_os_names[0] if all_os_names else ""
                        content_key = region_id
                        content_result = self._find_content_by_mapping(soup, region_id, None, None, fallback_os_name)
                        if content_result and (content_result.get("content") or content_result.get("shared_content")):
                            content_mapping[content_key] = content_result
            
            logger.info(f"✓ 构建了 {len(content_mapping)} 个内容映射")
            return content_mapping
            
        except Exception as e:
            logger.error(f"❌ 内容映射提取失败: {e}")
            raise

    def _extract_unvalidated_experimental_shared_content_for_tab_container(
        self,
        soup: BeautifulSoup,
        container_id: str,
    ) -> str:
        """
        提取指定Tab容器中的共享内容区域
        
        共享内容区域位于Tab导航之后、具体Tab内容之前，通常包含：
        - 定价说明标题 
        - 计费模式说明
        - 价格总览表
        - 重要注释和说明
        
        Args:
            soup: BeautifulSoup对象
            container_id: Tab容器ID（如'tabContent1', 'tabContent2'等）
            
        Returns:
            共享内容区域的HTML字符串
        """
        logger.info(f"🔍 提取Tab容器 '{container_id}' 的共享内容区域...")
        
        try:
            # 查找指定的Tab容器
            tab_container = soup.find('div', id=container_id)
            if not tab_container:
                logger.warning(f"⚠ 未找到Tab容器: {container_id}")
                return ""
            
            shared_content = ""
            
            # 方法1: 查找Tab导航后、第一个tab-panel前的内容
            # 这是最常见的共享内容位置
            tab_content_div = tab_container.find('div', class_='tab-content')
            if tab_content_div:
                # 遍历tab-content下的直接子元素
                for child in tab_content_div.children:
                    if hasattr(child, 'name') and child.name:
                        # 如果遇到第一个tab-panel，停止收集
                        if child.name == 'div' and child.get('class') and 'tab-panel' in child.get('class'):
                            break
                        # 否则收集这个元素作为共享内容
                        shared_content += str(child)
                        
                        # 特别处理：查找重要的定价表格和说明
                        if child.name in ['h2', 'h3', 'table', 'div']:
                            element_text = child.get_text(strip=True).lower()
                            if any(keyword in element_text for keyword in ['定价详细信息', 'dbu价格', '现用现付', '价格总览']):
                                logger.info(f"✓ 找到重要共享内容元素: {child.name} - {element_text[:50]}...")
            
            # # 方法2: 如果没找到tab-content结构，查找容器内非tab-panel的直接内容
            # if not shared_content:
            #     logger.info(f"🔄 使用备选方法提取 '{container_id}' 的共享内容...")
            #
            #     # 查找容器内的直接子元素，但跳过导航和tab-panel
            #     for child in tab_container.children:
            #         if hasattr(child, 'name') and child.name:
            #             # 跳过导航相关元素
            #             if child.get('class'):
            #                 classes = ' '.join(child.get('class', []))
            #                 if any(nav_class in classes for nav_class in ['category-container', 'tab-nav', 'category-tabs']):
            #                     continue
            #
            #             # 如果是tab-panel，停止收集（开始进入具体tab内容）
            #             if child.name == 'div' and child.get('class') and 'tab-panel' in child.get('class'):
            #                 break
            #
            #             # 收集非导航、非tab-panel的内容作为共享内容
            #             if child.name in ['h1', 'h2', 'h3', 'p', 'div', 'table', 'ul', 'ol']:
            #                 shared_content += str(child)
            #                 logger.info(f"✓ 备选方法收集共享内容: {child.name}")
            
            # 内容质量验证
            if shared_content:
                # 简单清理
                shared_content = clean_html_content(shared_content)
                content_text = BeautifulSoup(shared_content, 'html.parser').get_text(strip=True)
                
                if len(content_text) > 20:  # 确保不是空内容
                    logger.info(f"✅ 成功提取 '{container_id}' 共享内容，长度: {len(content_text)} 字符")
                    return shared_content
                else:
                    logger.warning(f"⚠ '{container_id}' 共享内容过短，可能提取不完整")
            else:
                logger.warning(f"⚠ 未在 '{container_id}' 中找到共享内容区域")
            
            return shared_content
            
        except Exception as e:
            logger.error(f"❌ 提取 '{container_id}' 共享内容失败: {e}")
            return ""

    def _get_software_tab_content_id(self, software_id: str) -> Optional[str]:
        """
        根据软件ID获取对应的tabContent ID

        Args:
            software_id: 软件ID（如'App Windows', 'App Linux'）

        Returns:
            对应的tabContent ID（如'tabContent1', 'tabContent2'），如果未找到则返回None
        """
        panels = getattr(
            self, "_unvalidated_experimental_software_panels", {}
        )
        target_id = panels.get(software_id)
        if isinstance(target_id, str) and target_id:
            logger.info(
                f"🔗 软件'{software_id}'对应的tabContent ID: {target_id}"
            )
            return target_id
        logger.warning(f"⚠ 未找到软件'{software_id}'对应的tabContent ID")
        return None

    def _find_content_by_mapping(self, soup: BeautifulSoup,
                               region_id: Optional[str] = None,
                               software_id: Optional[str] = None,
                               tab_id: Optional[str] = None,
                               os_name: Optional[str] = None) -> Dict[str, str]:
        """
        根据映射关系查找对应内容（支持区域表格筛选和共享内容提取）

        Args:
            soup: BeautifulSoup对象
            region_id: 区域ID
            software_id: 软件ID
            tab_id: Tab ID
            os_name: OS名称，用于区域筛选

        Returns:
            包含具体内容和共享内容的字典: {"content": "...", "shared_content": "..."}
        """
        try:
            # 首先从原始soup中找到基础内容
            base_content = None
            main_container_id = None  # 跟踪主容器ID以便提取共享内容

            # 1. 如果有tab_id，优先查找tab对应内容
            if tab_id:
                base_content = soup.find('div', id=tab_id)
                if base_content:
                    logger.info(f"✓ 找到tab内容: {tab_id}")
                    # 推断主容器ID (如tabContent1-1的主容器是tabContent1)
                    if '-' in tab_id:
                        main_container_id = tab_id.split('-')[0]
                else:
                    raise ValueError(f"Missing target panel for tab {tab_id!r}")

            # 2. 如果有software_id，根据软件选项的data-href查找对应的tabContent分组
            if not base_content and software_id:
                # 从filter_analysis中获取软件选项的data-href信息
                target_tab_content_id = self._get_software_tab_content_id(software_id)
                main_container_id = target_tab_content_id  # 保存主容器ID

                if target_tab_content_id:
                    # 根据data-href查找对应的tabContent
                    base_content = soup.find('div', id=target_tab_content_id)
                    if base_content:
                        logger.info(f"✓ 根据软件选项'{software_id}'的data-href找到内容组: {target_tab_content_id}")
                    else:
                        logger.warning(f"⚠ 未找到软件选项'{software_id}'对应的内容组: {target_tab_content_id}")

                # 如果还是没找到，回退到原来的逻辑
                if not base_content:
                    logger.info(f"🔄 回退到通用查找逻辑，软件ID: {software_id}")
                    content_groups = soup.find_all('div', class_='tab-panel')
                    for group in content_groups:
                        if hasattr(group, 'attrs') and group.attrs:
                            group_id = group.attrs.get('id', '')
                            if group_id and 'tabContent' in group_id:
                                base_content = group
                                main_container_id = group_id
                                logger.info(f"✓ 找到软件内容组（回退）: {group_id}")
                                break
            
            # 3. 默认返回主要内容区域
            if not base_content:
                base_content = soup.find('div', class_='technical-azure-selector')
                if base_content:
                    logger.info("✓ 使用主要内容区域")
                    main_container_id = "technical-azure-selector"  # 标记为技术选择器
            
            if not base_content:
                logger.warning("⚠ 未找到任何基础内容")
                return {"content": "", "shared_content": ""}
            
            # 提取共享内容（如果有主容器ID）
            shared_content = ""
            if main_container_id and main_container_id != "technical-azure-selector":
                shared_content = (
                    self
                    ._extract_unvalidated_experimental_shared_content_for_tab_container(
                        soup, main_container_id
                    )
                )

            # 准备返回的具体内容
            final_content = ""
            final_shared_content = ""

            # 应用区域筛选（如果有region_id和os_name）
            if region_id and os_name:
                logger.info(f"🔍 对内容应用区域筛选: region={region_id}, os={os_name}")
                # 创建包含找到内容的临时soup
                temp_soup = BeautifulSoup(str(base_content), 'html.parser')
                # 应用区域筛选
                filtered_soup = (
                    self
                    ._get_unvalidated_experimental_region_processor()
                    .apply_region_filtering(temp_soup, region_id, os_name)
                )
                final_content = str(filtered_soup)

                # 对共享内容也应用区域筛选
                if shared_content:
                    logger.info(f"🔍 对共享内容应用区域筛选: region={region_id}, os={os_name}")
                    temp_shared_soup = BeautifulSoup(str(shared_content), 'html.parser')
                    filtered_shared_soup = (
                        self
                        ._get_unvalidated_experimental_region_processor()
                        .apply_region_filtering(
                            temp_shared_soup, region_id, os_name
                        )
                    )
                    final_shared_content = str(filtered_shared_soup)
                else:
                    final_shared_content = shared_content
            else:
                # 没有区域信息，直接返回原始内容
                if not region_id:
                    logger.info("ℹ 无区域ID，跳过区域筛选")
                if not os_name:
                    logger.info("ℹ 无OS名称，跳过区域筛选")
                final_content = str(base_content)
                final_shared_content = shared_content

            return {
                "content": final_content,
                "shared_content": final_shared_content
            }
            
        except Exception as e:
            logger.error(f"❌ 内容查找失败: {e}")
            raise

    def _get_product_key(self) -> str:
        """获取产品键"""
        if hasattr(self, 'product_config') and 'product_key' in self.product_config:
            return self.product_config['product_key']
        
        # 从文件路径推断
        if self.html_file_path:
            file_name = Path(self.html_file_path).stem
            if file_name.endswith('-index'):
                return file_name[:-6]
        
        return "unknown"
