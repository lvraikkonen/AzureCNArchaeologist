"""Build deterministic CMS FlexibleContentPage 1.1 business payloads."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from src.core.cms_state_contract import (
    CmsState,
    _visible_text,
)
from src.core.html_price_bearing import is_price_bearing_html
from src.core.logging import get_logger
from src.core.source_reachability import (
    SourceReachability,
    SourceReachabilityError,
)
from src.utils.html.cleaner import clean_html_content


logger = get_logger(__name__)


def _compact_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


class FlexibleBuilder:
    """Construct the fixed CMS wire shape and its page-state projection."""

    def __init__(self) -> None:
        logger.info("🔧 初始化FlexibleBuilder")

    def build_flexible_page(
        self,
        base_metadata: dict[str, Any],
        common_sections: list[dict[str, Any]],
        strategy_content: dict[str, Any],
    ) -> dict[str, Any]:
        logger.info("🏗️ 构建完整的flexible JSON页面...")
        flexible_data = {
            "title": base_metadata.get("Title", ""),
            "metaTitle": base_metadata.get("MetaTitle", ""),
            "metaDescription": base_metadata.get("MetaDescription", ""),
            "metaKeywords": base_metadata.get("MetaKeywords", ""),
            "slug": base_metadata.get("Slug", ""),
            "language": base_metadata.get("Language", "zh-cn"),
            "baseContent": strategy_content.get("baseContent", ""),
            "contentGroups": strategy_content.get("contentGroups", []),
            "commonSections": common_sections,
            "pageConfig": self._build_page_config(
                strategy_content, base_metadata
            ),
        }
        logger.info(
            f"✓ 构建完成，包含 {len(common_sections)} 个commonSections, "
            f"{len(flexible_data['contentGroups'])} 个contentGroups"
        )
        return flexible_data

    @staticmethod
    def build_simple_content_groups(base_content: str) -> list[dict[str, Any]]:
        del base_content
        return []

    def build_region_content_groups(
        self,
        region_content: dict[str, Any],
        filter_analysis: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Build exactly one active group for every visible region state."""

        domains = self._cms_domains(
            filter_analysis, {}, allowed_keys=("region",)
        )
        region_domain = domains[0]
        expected_values = {
            option["value"] for option in region_domain["options"]
        }
        extra_values = sorted(set(region_content) - expected_values)
        if extra_values:
            raise ValueError(
                f"Region content contains states outside the CMS domain: {extra_values}"
            )

        content_groups: list[dict[str, Any]] = []
        for option in region_domain["options"]:
            region_id = option["value"]
            content = region_content.get(region_id)
            if not isinstance(content, str) or not content.strip():
                raise ValueError(
                    f"Missing non-empty content for region state {region_id!r}"
                )
            content_groups.append(
                {
                    "groupName": option["label"],
                    "filterCriteriaJson": _compact_json(
                        [
                            {
                                "filterKey": "region",
                                "matchValues": region_id,
                            }
                        ]
                    ),
                    "content": clean_html_content(content),
                    "sortOrder": len(content_groups) + 1,
                    "isActive": True,
                }
            )
        return content_groups

    def build_complex_content_groups(
        self,
        source_reachability: SourceReachability,
        content_mapping: dict[CmsState, Any],
    ) -> list[dict[str, Any]]:
        """Materialize exactly the source-proven ordered CMS relation."""

        if not isinstance(source_reachability, SourceReachability):
            raise TypeError(
                "Formal complex groups require SourceReachability"
            )
        ordered_states = source_reachability.ordered_states
        if not ordered_states:
            raise ValueError("Source reachability contains no CMS states")
        expected_states = [state.cms_state for state in ordered_states]
        if len(expected_states) != len(set(expected_states)):
            raise ValueError("Source reachability contains duplicate CMS states")
        if set(content_mapping) != set(expected_states):
            missing = [
                state.criteria
                for state in expected_states
                if state not in content_mapping
            ]
            extra = [
                state.criteria
                for state in content_mapping
                if state not in set(expected_states)
            ]
            raise ValueError(
                "Content mapping must equal the source-proven CMS relation; "
                f"missing={missing!r}, extra={extra!r}"
            )
        defaults = [
            state.cms_state for state in ordered_states if state.is_default
        ]
        if defaults != [source_reachability.default_state]:
            raise ValueError(
                "Source reachability must identify exactly its declared default"
            )

        content_groups: list[dict[str, Any]] = []
        for reachable_state in ordered_states:
            cms_state = reachable_state.cms_state
            content_result = content_mapping[cms_state]
            if not isinstance(content_result, dict):
                raise ValueError(
                    "Invalid content mapping for CMS state "
                    f"{cms_state.criteria!r}"
                )
            shared = content_result.get("shared_content", "")
            software_scoped_prefix = content_result.get(
                "software_scoped_prefix", ""
            )
            region_projected_shared_content = content_result.get(
                "region_projected_shared_content", ""
            )
            specific = content_result.get("content", "")
            if (
                not isinstance(shared, str)
                or not isinstance(software_scoped_prefix, str)
                or not isinstance(
                    region_projected_shared_content, str
                )
                or not isinstance(specific, str)
            ):
                raise ValueError(
                    f"Non-string content for CMS state {cms_state.criteria!r}"
                )
            if shared.strip():
                raise ValueError(
                    "Unclassified shared content cannot be copied into "
                    f"state-specific CMS group {cms_state.criteria!r}"
                )
            expected_prefix = (
                reachable_state.source_evidence.software_scoped_prefix
            )
            if bool(software_scoped_prefix.strip()) != bool(expected_prefix):
                raise ValueError(
                    "Software-scoped prefix presence must equal its frozen "
                    f"source evidence for CMS state {cms_state.criteria!r}"
                )
            if expected_prefix is not None:
                source_evidence = reachable_state.source_evidence
                if (
                    expected_prefix.software_value
                    != source_evidence.software_value
                    or expected_prefix.software_panel_id
                    != source_evidence.software_panel_id
                    or source_evidence.category_panel_id
                    not in expected_prefix.category_panel_ids
                ):
                    raise ValueError(
                        "Software-scoped prefix scope differs from the "
                        "reachable state's frozen source evidence for CMS "
                        f"state {cms_state.criteria!r}"
                    )
                actual_prefix_sha256 = hashlib.sha256(
                    software_scoped_prefix.encode("utf-8")
                ).hexdigest()
                if actual_prefix_sha256 != expected_prefix.source_html_sha256:
                    raise ValueError(
                        "Software-scoped prefix SHA-256 differs from its "
                        "frozen source evidence for CMS state "
                        f"{cms_state.criteria!r}"
                    )
            combined = clean_html_content(
                software_scoped_prefix + specific
            )
            if "tab-content-missing" in combined:
                raise SourceReachabilityError(
                    "missing_cms_state_content",
                    "Missing or placeholder content for CMS state "
                    f"{cms_state.criteria!r}"
                )

            expected_shared = (
                reachable_state.source_evidence
                .region_projected_shared_content
            )
            if bool(
                region_projected_shared_content.strip()
            ) != bool(expected_shared):
                raise ValueError(
                    "Region-Projected Shared Content presence must equal its "
                    "frozen source/config evidence for CMS state "
                    f"{cms_state.criteria!r}"
                )
            shared_wire = ""
            if expected_shared is not None:
                source_evidence = reachable_state.source_evidence
                if (
                    source_evidence.region_value is None
                    or source_evidence.category_panel_id is None
                    or source_evidence.software_panel_id
                    != expected_shared.software_panel_id
                    or source_evidence.software_value
                    != expected_shared.internal_software_value
                    or source_evidence.category_panel_id
                    not in expected_shared.category_panel_ids
                ):
                    raise ValueError(
                        "Region-Projected Shared Content scope differs from "
                        "the reachable state's frozen source evidence for CMS "
                        f"state {cms_state.criteria!r}"
                    )
                projection = expected_shared.projection_for(
                    source_evidence.region_value
                )
                actual_shared_sha256 = hashlib.sha256(
                    region_projected_shared_content.encode("utf-8")
                ).hexdigest()
                if (
                    actual_shared_sha256
                    != projection.projected_html_sha256
                ):
                    raise ValueError(
                        "Region-Projected Shared Content SHA-256 differs from "
                        "its frozen source/config projection for CMS state "
                        f"{cms_state.criteria!r}"
                    )
                shared_wire = clean_html_content(
                    region_projected_shared_content
                )
                if not shared_wire.strip():
                    raise ValueError(
                        "Region-Projected Shared Content must remain visible "
                        f"for CMS state {cms_state.criteria!r}"
                    )
                if not is_price_bearing_html(shared_wire):
                    raise ValueError(
                        "Region-Projected Shared Content must remain "
                        "price-bearing for CMS state "
                        f"{cms_state.criteria!r}"
                    )
                if shared_wire in combined:
                    raise ValueError(
                        "Region-Projected Shared Content cannot be duplicated "
                        f"inside content for CMS state {cms_state.criteria!r}"
                    )
            if not _visible_text(combined) and not shared_wire:
                raise SourceReachabilityError(
                    "missing_cms_state_content",
                    "Missing or placeholder content for CMS state "
                    f"{cms_state.criteria!r}"
                )

            criteria = [
                {
                    "filterKey": filter_key,
                    "matchValues": match_value,
                }
                for filter_key, match_value in cms_state.criteria
            ]
            label_segments = reachable_state.state_label_segments
            if len(label_segments) != len(criteria):
                raise ValueError(
                    "State label segments must align exactly with criteria"
                )
            if any(
                not segment.strip() or " - " in segment
                for segment in label_segments
            ):
                raise ValueError(
                    "State label segments must be non-empty and cannot contain "
                    "the CMS group-name delimiter"
                )
            content_group = {
                "groupName": reachable_state.group_name,
                "filterCriteriaJson": _compact_json(criteria),
                "content": combined,
                "sortOrder": len(content_groups) + 1,
                "isActive": True,
            }
            if shared_wire:
                content_group["sharedContent"] = shared_wire
            content_groups.append(content_group)
        return content_groups

    def build_unvalidated_experimental_complex_content_groups(
        self,
        filter_analysis: dict[str, Any],
        tab_analysis: dict[str, Any],
        content_mapping: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Frozen skip-unmapped builder used only by the quarantined P0 worker."""

        region_options = filter_analysis.get("region_options", [])
        software_options = filter_analysis.get("software_options", [])
        category_tabs = tab_analysis.get("category_tabs", [])
        content_groups: list[dict[str, Any]] = []
        for region in region_options:
            region_id = str(region.get("value", ""))
            region_name = str(region.get("label", region_id))
            if software_options:
                for software in software_options:
                    software_id = str(software.get("value", ""))
                    software_name = str(
                        software.get("label", software_id)
                    )
                    if category_tabs:
                        for tab in category_tabs:
                            tab_id = str(
                                tab.get("href", "")
                            ).removeprefix("#")
                            tab_name = str(tab.get("label", tab_id))
                            self._append_unvalidated_experimental_group(
                                content_groups,
                                content_mapping,
                                f"{region_id}_{software_id}_{tab_id}",
                                (
                                    region_name,
                                    software_name,
                                    tab_name,
                                ),
                                (
                                    ("region", region_id),
                                    ("software", software_id),
                                    ("category", tab_id),
                                ),
                            )
                    else:
                        self._append_unvalidated_experimental_group(
                            content_groups,
                            content_mapping,
                            f"{region_id}_{software_id}",
                            (region_name, software_name),
                            (
                                ("region", region_id),
                                ("software", software_id),
                            ),
                        )
            elif category_tabs:
                for tab in category_tabs:
                    tab_id = str(
                        tab.get("href", "")
                    ).removeprefix("#")
                    tab_name = str(tab.get("label", tab_id))
                    self._append_unvalidated_experimental_group(
                        content_groups,
                        content_mapping,
                        f"{region_id}_{tab_id}",
                        (region_name, tab_name),
                        (
                            ("region", region_id),
                            ("category", tab_id),
                        ),
                    )
        return content_groups

    @staticmethod
    def _append_unvalidated_experimental_group(
        content_groups: list[dict[str, Any]],
        content_mapping: dict[str, Any],
        mapping_key: str,
        label_segments: tuple[str, ...],
        criteria: tuple[tuple[str, str], ...],
    ) -> None:
        """Append a P0 group only when the legacy source walk produced it."""

        if mapping_key not in content_mapping:
            return
        content_result = content_mapping[mapping_key]
        if not isinstance(content_result, dict):
            raise ValueError(
                f"Invalid content mapping for CMS state {mapping_key!r}"
            )
        content_group = {
            "groupName": " - ".join(label_segments),
            "filterCriteriaJson": json.dumps(
                [
                    {"filterKey": key, "matchValues": value}
                    for key, value in criteria
                ],
                ensure_ascii=False,
            ),
            "content": clean_html_content(
                content_result.get("content", "")
            ),
            "sortOrder": len(content_groups) + 1,
            "isActive": True,
        }
        shared_content = content_result.get("shared_content", "")
        if shared_content:
            content_group["sharedContent"] = clean_html_content(
                shared_content
            )
        content_groups.append(content_group)

    def _build_page_config(
        self,
        strategy_content: dict[str, Any],
        base_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        strategy_type = strategy_content.get("strategy_type")
        filter_analysis = strategy_content.get("filter_analysis", {})
        tab_analysis = strategy_content.get("tab_analysis", {})
        page_config = {
            "displayTitle": base_metadata.get("Title", ""),
            "pageIcon": "{base_url}/Static/Favicon/favicon.ico",
            "leftNavigationIdentifier": base_metadata.get(
                "MSServiceName", ""
            ),
        }

        if strategy_type == "simple_static":
            page_config.update(
                {
                    "pageType": "Simple",
                    "enableFilters": False,
                    "filtersJsonConfig": _compact_json(
                        {"filterDefinitions": []}
                    ),
                }
            )
        elif strategy_type == "region_filter":
            page_config.update(
                {
                    "pageType": "RegionFilter",
                    "enableFilters": True,
                    "filtersJsonConfig": self._build_filters_json_config(
                        filter_analysis,
                        tab_analysis,
                        allowed_keys=("region",),
                    ),
                }
            )
        elif strategy_type == "complex":
            source_reachability = strategy_content.get(
                "source_reachability"
            )
            if isinstance(source_reachability, SourceReachability):
                filters_json_config = (
                    self._build_source_reachability_filters_json_config(
                        source_reachability
                    )
                )
            elif strategy_content.get(
                "unvalidated_experimental_legacy"
            ) is True:
                filters_json_config = (
                    self._build_unvalidated_experimental_filters_json_config(
                        filter_analysis, tab_analysis
                    )
                )
            else:
                raise ValueError(
                    "Formal ComplexFilter pageConfig requires "
                    "SourceReachability"
                )
            page_config.update(
                {
                    "pageType": "ComplexFilter",
                    "enableFilters": True,
                    "filtersJsonConfig": filters_json_config,
                }
            )
        else:
            raise ValueError(
                f"Unknown semantic strategy for page state machine: {strategy_type!r}"
            )
        return page_config

    def _build_unvalidated_experimental_filters_json_config(
        self,
        filter_analysis: dict[str, Any],
        tab_analysis: dict[str, Any],
    ) -> str:
        """Serialize the frozen P0 filter projection, including hidden axes."""

        definitions: list[dict[str, Any]] = []
        region_options = filter_analysis.get("region_options", [])
        if region_options:
            definitions.append(
                {
                    "filterKey": "region",
                    "filterType": "dropdown",
                    "displayName": "区域",
                    "options": [
                        {
                            "value": option.get("value", ""),
                            "label": option.get("label", ""),
                            "href": option.get("href", ""),
                        }
                        for option in region_options
                    ],
                }
            )
        software_options = filter_analysis.get("software_options", [])
        if software_options:
            definitions.append(
                {
                    "filterKey": "software",
                    "filterType": "dropdown",
                    "displayName": "软件类别",
                    "options": [
                        {
                            "value": option.get("value", ""),
                            "label": option.get("label", ""),
                            "href": option.get("href", ""),
                        }
                        for option in software_options
                    ],
                }
            )
        category_tabs = tab_analysis.get("category_tabs", [])
        if category_tabs:
            definitions.append(
                {
                    "filterKey": "category",
                    "filterType": "tab",
                    "displayName": "类别",
                    "options": [
                        {
                            "value": str(
                                tab.get("href", "")
                            ).removeprefix("#"),
                            "label": tab.get("label", ""),
                            "href": tab.get("href", ""),
                        }
                        for tab in category_tabs
                    ],
                }
            )
        return json.dumps(
            {"filterDefinitions": definitions},
            ensure_ascii=False,
        )

    @staticmethod
    def _build_source_reachability_filters_json_config(
        source_reachability: SourceReachability,
    ) -> str:
        definitions = [
            definition.to_cms_dict()
            for definition in source_reachability.filter_definitions_union
        ]
        if not definitions:
            raise ValueError(
                "Complex source reachability has no filter definitions"
            )
        return _compact_json({"filterDefinitions": definitions})

    def _build_filters_json_config(
        self,
        filter_analysis: dict[str, Any] | None = None,
        tab_analysis: dict[str, Any] | None = None,
        *,
        allowed_keys: tuple[str, ...] = ("region", "software", "category"),
    ) -> str:
        definitions = self._cms_domains(
            filter_analysis or {},
            tab_analysis or {},
            allowed_keys=allowed_keys,
        )
        return _compact_json({"filterDefinitions": definitions})

    def _cms_domains(
        self,
        filter_analysis: dict[str, Any],
        tab_analysis: dict[str, Any],
        *,
        allowed_keys: tuple[str, ...] = ("region", "software", "category"),
    ) -> list[dict[str, Any]]:
        definitions: list[dict[str, Any]] = []
        if "region" in allowed_keys and filter_analysis.get("region_visible"):
            definitions.append(
                self._filter_definition(
                    "region",
                    "dropdown",
                    filter_analysis.get("region_display_name", "Region"),
                    filter_analysis.get("region_options", []),
                )
            )
        if "software" in allowed_keys and filter_analysis.get(
            "software_visible"
        ):
            definitions.append(
                self._filter_definition(
                    "software",
                    "dropdown",
                    filter_analysis.get(
                        "software_display_name", "Software category"
                    ),
                    filter_analysis.get("software_options", []),
                )
            )
        if "category" in allowed_keys and tab_analysis.get("category_tabs"):
            definitions.append(
                self._filter_definition(
                    "category",
                    "tab",
                    tab_analysis.get("category_display_name", "Category"),
                    tab_analysis.get("category_tabs", []),
                    tab_options=True,
                )
            )

        missing_requested = [
            key
            for key in allowed_keys
            if key == "region"
            and filter_analysis.get("has_region")
            and filter_analysis.get("region_visible")
            and not any(item["filterKey"] == key for item in definitions)
        ]
        if missing_requested:
            raise ValueError(
                f"Visible CMS domains have no options: {missing_requested}"
            )
        if not definitions and allowed_keys != ():
            raise ValueError("Filtered page has no visible CMS filter domain")
        return definitions

    def _filter_definition(
        self,
        key: str,
        filter_type: str,
        display_name: str,
        raw_options: list[dict[str, Any]],
        *,
        tab_options: bool = False,
    ) -> dict[str, Any]:
        options = self._normalized_options(
            raw_options, key, tab_options=tab_options
        )
        return {
            "filterKey": key,
            "filterType": filter_type,
            "displayName": str(display_name).strip() or key,
            "options": [
                {
                    "value": option["value"],
                    "label": option["label"],
                    "href": option["href"],
                }
                for option in options
            ],
        }

    @staticmethod
    def _normalized_options(
        raw_options: list[dict[str, Any]],
        key: str,
        *,
        tab_options: bool = False,
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for raw in raw_options:
            href = str(raw.get("href", "")).strip()
            value = href.removeprefix("#") if tab_options else str(
                raw.get("value", "")
            ).strip()
            label = str(raw.get("label", "")).strip()
            if not value or not label:
                raise ValueError(f"{key} filter options require value and label")
            normalized.append(
                {
                    "value": value,
                    "label": label,
                    "href": href,
                    "is_default": bool(raw.get("is_default", False)),
                }
            )

        values = [option["value"] for option in normalized]
        if len(values) != len(set(values)):
            raise ValueError(f"Duplicate values in {key} filter domain")
        if not normalized:
            raise ValueError(f"{key} filter domain must be non-empty")
        defaults = [option for option in normalized if option["is_default"]]
        if len(defaults) != 1:
            raise ValueError(
                f"{key} filter domain must have exactly one proven default"
            )
        default_index = normalized.index(defaults[0])
        return (
            [normalized[default_index]]
            + normalized[:default_index]
            + normalized[default_index + 1:]
        )

    def _complex_mapping_key(
        self,
        state: dict[str, dict[str, Any]],
        filter_analysis: dict[str, Any],
        tab_analysis: dict[str, Any],
    ) -> str:
        del tab_analysis
        region_value = (
            state["region"]["value"]
            if "region" in state
            else self._internal_option_value(
                filter_analysis.get("region_options", []), "region"
            )
            or "default"
        )
        software_value = (
            state["software"]["value"]
            if "software" in state
            else self._internal_option_value(
                filter_analysis.get("software_options", []), "software"
            )
        )
        category_value = (
            state["category"]["value"] if "category" in state else None
        )
        return "_".join(
            value
            for value in (region_value, software_value, category_value)
            if value is not None
        )

    def _internal_option_value(
        self, raw_options: list[dict[str, Any]], key: str
    ) -> str | None:
        if not raw_options:
            return None
        options = self._normalized_options(raw_options, key)
        return options[0]["value"]


__all__ = ["FlexibleBuilder"]
