#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
筛选器检测器

基于实际HTML结构检测Azure中国区页面的筛选器，专门检测：
- 软件类别筛选器：.dropdown-container.software-kind-container
- 地区筛选器：.dropdown-container.region-container
- 隐藏状态和选项映射的精确提取
"""

import re
from typing import Dict, Any
from bs4 import BeautifulSoup, Tag

from ..core.data_models import (
    FilterType, Filter
)
from ..core.logging import get_logger

logger = get_logger(__name__)


class FilterDetector:
    """
    Azure中国区页面筛选器检测器。
    
    基于实际HTML结构精确检测：
    - 软件类别筛选器：.dropdown-container.software-kind-container + #software-box
    - 地区筛选器：.dropdown-container.region-container + #region-box
    - 检测隐藏状态：style="display:none;"
    - 提取选项映射：data-href和value属性
    """
    
    def __init__(self):
        """初始化筛选器检测器。"""
        logger.info("初始化FilterDetector - 基于实际HTML结构")
    
    def detect_filters(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        检测页面中的筛选器（基于实际HTML结构）。
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            筛选器分析结果字典
        """
        logger.info("🔍 开始检测筛选器...")
        
        # 检测软件类别筛选器
        software_result = self._detect_software_kind_filter(soup)
        
        # 检测地区筛选器
        region_result = self._detect_region_filter(soup)
        
        result = {
            "has_region": region_result["exists"],
            "has_software": software_result["exists"],
            "region_visible": region_result["visible"],
            "software_visible": software_result["visible"],
            "region_display_name": region_result["display_name"],
            "software_display_name": software_result["display_name"],
            "region_default_value": region_result["default_value"],
            "software_default_value": software_result["default_value"],
            "region_options": region_result["options"],
            "software_options": software_result["options"]
        }
        
        logger.info(f"✅ 筛选器检测完成: region={result['has_region']}({result['region_visible']}), software={result['has_software']}({result['software_visible']})")
        return result
    
    def _detect_software_kind_filter(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        检测软件类别筛选器：.dropdown-container.software-kind-container
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            {
                "exists": bool,
                "visible": bool,
                "options": [{"value": str, "href": str, "label": str}]
            }
        """
        logger.info("🔍 检测软件类别筛选器...")
        
        software_container = soup.select_one(
            "div.dropdown-container.software-kind-container"
        )
        
        if not software_container:
            logger.info("⚠ 未找到 software-kind-container")
            return {
                "exists": False,
                "visible": False,
                "display_name": "Software category",
                "default_value": None,
                "options": [],
            }
        
        logger.info("✅ 找到 software-kind-container")
        
        # 检查是否隐藏
        is_visible = self._is_visible(software_container)
        
        # 查找 #software-box select
        software_select = soup.find('select', id='software-box')
        options = []
        
        if software_select:
            logger.info("✅ 找到 #software-box")
            option_elements = software_select.find_all('option', recursive=False)
            
            for option in option_elements:
                value = option.get('value', '').strip()
                href = option.get('data-href', '').strip()
                label = option.get_text().strip()
                
                if value and href:
                    options.append({
                        "value": value,
                        "href": href,
                        "label": label,
                        "selected": option.has_attr("selected"),
                    })

        options, default_value = self._order_options(
            options, software_container
        )
        
        logger.info(f"✅ 软件类别筛选器: visible={is_visible}, options={len(options)}")
        
        return {
            "exists": True,
            "visible": is_visible,
            "display_name": self._display_name(
                software_container, "Software category"
            ),
            "default_value": default_value,
            "options": options,
        }
    
    def _detect_region_filter(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        检测地区筛选器：.dropdown-container.region-container
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            {
                "exists": bool,
                "visible": bool,
                "options": [{"value": str, "href": str, "label": str}]
            }
        """
        logger.info("🔍 检测地区筛选器...")
        
        region_container = soup.select_one("div.dropdown-container.region-container")
        
        if not region_container:
            logger.info("⚠ 未找到 region-container")
            return {
                "exists": False,
                "visible": False,
                "display_name": "Region",
                "default_value": None,
                "options": [],
            }
        
        logger.info("✅ 找到 region-container")
        
        # 检查是否隐藏
        is_visible = self._is_visible(region_container)
        
        # 查找 #region-box select
        region_select = soup.find('select', id='region-box')
        options = []
        
        if region_select:
            logger.info("✅ 找到 #region-box")
            option_elements = region_select.find_all('option', recursive=False)
            
            for option in option_elements:
                raw_value = option.get('value', '').strip()
                href = option.get('data-href', '').strip()
                label = option.get_text().strip()
                value = href.removeprefix("#") if href else raw_value
                
                if raw_value and value and href:
                    options.append({
                        "value": value,
                        "href": href,
                        "label": label,
                        "selected": option.has_attr("selected"),
                    })

        options, default_value = self._order_options(options, region_container)
        
        logger.info(f"✅ 地区筛选器: visible={is_visible}, options={len(options)}")
        
        return {
            "exists": True,
            "visible": is_visible,
            "display_name": self._display_name(region_container, "Region"),
            "default_value": default_value,
            "options": options,
        }

    @staticmethod
    def _is_visible(container: Tag) -> bool:
        style = re.sub(r"\s+", "", str(container.get("style", "")).casefold())
        return "display:none" not in style

    @staticmethod
    def _display_name(container: Tag, fallback: str) -> str:
        label = container.find("label")
        if label is None:
            return fallback
        value = label.get_text(" ", strip=True).rstrip(":：").strip()
        return value or fallback

    @staticmethod
    def _order_options(
        options: list[dict[str, Any]], container: Tag
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Use desktop source order, then move the proven default to first."""

        selected_values = [
            option["value"] for option in options if option.pop("selected", False)
        ]
        if len(selected_values) > 1:
            raise ValueError("Filter declares more than one selected option")

        values = [option["value"] for option in options]
        if len(values) != len(set(values)):
            raise ValueError("Filter declares duplicate machine values")

        by_value = {option["value"]: option for option in options}
        by_href = {
            option["href"]: option
            for option in options
            if option["href"]
        }
        desktop_links = container.select(
            ".dropdown-box.os-tab-nav .tab-items a"
        )
        desktop_values: list[str] = []
        desktop_labels: dict[str, str] = {}
        desktop_defaults: list[str] = []
        for link in desktop_links:
            link_id = str(link.get("id", "")).strip()
            link_href = str(link.get("data-href", "")).strip()
            option = by_value.get(link_id) or by_href.get(link_href)
            if option is None:
                raise ValueError(
                    "Desktop filter option does not resolve to the mobile domain"
                )
            desktop_label = " ".join(link.get_text(" ", strip=True).split())
            if not desktop_label:
                raise ValueError(
                    "Desktop filter option requires a display label"
                )
            desktop_values.append(option["value"])
            desktop_labels[option["value"]] = desktop_label
            parent = link.find_parent("li")
            if parent is not None and {
                "active",
                "selected",
                "selected-item",
            }.intersection(parent.get("class", [])):
                desktop_defaults.append(option["value"])

        if desktop_values:
            if (
                len(desktop_values) != len(set(desktop_values))
                or set(desktop_values) != set(values)
            ):
                raise ValueError(
                    "Desktop and mobile filter controls expose different domains"
                )
            if len(desktop_labels.values()) != len(
                set(desktop_labels.values())
            ):
                raise ValueError(
                    "Desktop filter declares duplicate display labels"
                )
            for value, label in desktop_labels.items():
                by_value[value]["label"] = label
            options = [by_value[value] for value in desktop_values]

        explicit_defaults = list(dict.fromkeys(
            selected_values + desktop_defaults
        ))
        if explicit_defaults:
            distinct_defaults = explicit_defaults
        else:
            selected_item = container.select_one(".selected-item")
            selected_label = (
                selected_item.get_text(" ", strip=True)
                if selected_item
                else ""
            )
            label_matches = [
                option["value"]
                for option in options
                if selected_label
                and " ".join(option["label"].split()) == selected_label
            ]
            distinct_defaults = (
                label_matches if len(label_matches) == 1 else []
            )
        if len(distinct_defaults) > 1:
            raise ValueError(
                "Desktop and mobile filter controls declare different defaults"
            )
        default_value = (
            distinct_defaults[0] if distinct_defaults else None
        )

        if options and default_value is None:
            raise ValueError("Filter source does not establish a default option")
        default_index = next(
            (
                index
                for index, option in enumerate(options)
                if option["value"] == default_value
            ),
            0,
        )
        ordered = (
            [options[default_index]]
            + options[:default_index]
            + options[default_index + 1:]
        )
        for option in ordered:
            option["is_default"] = option["value"] == default_value
        return ordered, default_value
