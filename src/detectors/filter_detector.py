#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
筛选器检测器

基于实际HTML结构检测Azure中国区页面的筛选器，专门检测：
- 软件类别筛选器：.dropdown-container.software-kind-container
- 地区筛选器：.dropdown-container.region-container
- 桌面端选项集合、顺序、标签、默认项和内容目标的精确提取
- Software 移动端 option.value 到桌面端 target 的语义键映射
"""

import logging
import re
from typing import Dict, Any
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


class FilterDetector:
    """
    Azure中国区页面筛选器检测器。
    
    基于实际HTML结构精确检测：
    - 软件类别筛选器：桌面导航 + #software-box option.value 语义键
    - 地区筛选器：仅桌面导航
    - 检测隐藏状态：style="display:none;"
    - 移动端控件不参与选项集合、顺序、标签或默认项验证
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
        
        options = self._desktop_options(
            software_container,
            kind="software",
        )
        options, default_value = self._order_options(options, software_container)
        
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
        
        options = self._desktop_options(region_container, kind="region")
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
    def _desktop_options(container: Tag, *, kind: str) -> list[dict[str, Any]]:
        """Read the option domain from the desktop navigation only.

        Region values are the desktop targets themselves.  Software keeps its
        business value in the responsive ``option.value`` source, so that one
        field is joined to each desktop option by target.  No other mobile
        field is read or compared.
        """

        desktop_links = container.select(
            ".dropdown-box.os-tab-nav.hidden-xs.hidden-sm "
            ".tab-items a[data-href]"
        )
        if not desktop_links:
            raise ValueError(f"{kind} 筛选器没有桌面端选项。")

        software_values_by_target: dict[str, list[str]] = {}
        if kind == "software":
            mobile_selects = container.select(
                "select#software-box.hidden-lg.hidden-md"
            )
            if len(mobile_selects) != 1:
                raise ValueError(
                    "Software 需要唯一的移动端 select 提供 option.value 语义键。"
                )
            for option in mobile_selects[0].find_all("option", recursive=False):
                target = str(option.get("data-href", "")).strip()
                value = str(option.get("value", "")).strip()
                if target and value:
                    software_values_by_target.setdefault(target, []).append(value)
        elif kind != "region":
            raise ValueError(f"未知筛选器类型：{kind}。")

        rows: list[dict[str, Any]] = []
        for link in desktop_links:
            href = str(link.get("data-href", "")).strip()
            label = " ".join(link.get_text(" ", strip=True).split())
            if not href.startswith("#") or not href.removeprefix("#") or not label:
                raise ValueError(
                    f"{kind} 桌面端选项缺少内容目标或显示名称。"
                )
            if kind == "software":
                semantic_values = software_values_by_target.get(href, [])
                if len(semantic_values) != 1:
                    raise ValueError(
                        "Software 桌面端选项无法按 target 唯一取得 "
                        "移动端 option.value 语义键。"
                    )
                value = semantic_values[0]
            else:
                value = href.removeprefix("#")
            parent = link.find_parent("li")
            rows.append(
                {
                    "value": value,
                    "href": href,
                    "label": label,
                    "desktop_default": bool(
                        parent is not None
                        and {
                            "active",
                            "selected",
                            "selected-item",
                        }.intersection(parent.get("class", []))
                    ),
                }
            )
        return rows

    @staticmethod
    def _order_options(
        options: list[dict[str, Any]], container: Tag
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Keep desktop order and move its proven default to the first slot."""

        values = [str(option.get("value", "")) for option in options]
        labels = [" ".join(str(option.get("label", "")).split()) for option in options]
        hrefs = [str(option.get("href", "")) for option in options]
        if any(not value for value in values) or len(values) != len(set(values)):
            raise ValueError("筛选器桌面端选项包含空或重复机器值。")
        if any(not label for label in labels) or len(labels) != len(set(labels)):
            raise ValueError("筛选器桌面端选项包含空或重复显示名称。")
        if any(not href for href in hrefs) or len(hrefs) != len(set(hrefs)):
            raise ValueError("筛选器桌面端选项包含空或重复内容目标。")

        desktop_defaults = [
            option["value"]
            for option in options
            if option.pop("desktop_default", False)
        ]
        selected_item = container.select_one("span.selected-item")
        selected_label = (
            " ".join(selected_item.get_text(" ", strip=True).split())
            if selected_item is not None
            else ""
        )
        # Some sources leave the visible summary stale.  One explicit desktop
        # marker is therefore authoritative; the summary is only a fallback
        # or a way to disambiguate multiple stale markers.
        distinct_defaults = list(dict.fromkeys(desktop_defaults))
        if len(distinct_defaults) == 1:
            default_value = distinct_defaults[0]
        elif not distinct_defaults and len(options) == 1:
            default_value = options[0]["value"]
        else:
            summary_matches = [
                option["value"]
                for option in options
                if selected_label and option["label"] == selected_label
            ]
            if len(summary_matches) != 1:
                raise ValueError("桌面端筛选器的当前项摘要无法唯一对应选项。")
            summary_default = summary_matches[0]
            if distinct_defaults and summary_default not in distinct_defaults:
                raise ValueError("桌面端筛选器声明了多个无法消歧的默认项。")
            default_value = summary_default
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
