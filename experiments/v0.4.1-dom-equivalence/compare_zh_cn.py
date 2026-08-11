#!/usr/bin/env python3
"""Compare v0.4.1 zh-cn CMS fragments with an independent DOM oracle.

The CMS payloads must be generated beforehand by ``cli.py extract``.  This
program deliberately does not import production extraction, reachability,
strategy, region-processing, cleaning, or payload-assembly code.  It reads the
frozen HTML and ``soft-category.json`` as independent comparison inputs.

The method is a larger, category-aware follow-up to commit 8d85cff's
``v0.5.0-independent-fidelity`` experiment.  Versioned copies are intentional:
an experiment must remain reproducible after later experiment code evolves.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import html as html_lib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Comment, NavigableString, Tag


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LANGUAGE = "zh-cn"
SOFT_CATEGORY_PATH = PROJECT_ROOT / "data/configs/soft-category.json"
EXPERIMENT_NAME = "v0.4.1-dom-equivalence-zh-cn"
CMS_HTML_SEMANTIC_MATERIALIZATION_VERSION = "css-generated-semantics-v1"
ICON_TICK_TEXT = "✓"

_HTML_COMMENT_PATTERN = re.compile(r"(<!--.*?-->)", re.DOTALL)
_EMPTY_ITALIC_PATTERN = re.compile(
    r"<i\b(?P<attributes>[^>]*)>\s*</i\s*>",
    re.IGNORECASE,
)
_CLASS_ATTRIBUTE_PATTERN = re.compile(
    r'''\bclass\s*=\s*(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)')''',
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class ProductSpec:
    product_key: str

    @property
    def source_relative_path(self) -> str:
        return f"data/prod-html/{LANGUAGE}/pricing/{self.product_key}.html"

    @property
    def definition_relative_path(self) -> str:
        return f"data/configs/products/pricing/{self.product_key}.json"

    @property
    def payload_relative_path(self) -> str:
        return f"payloads/{LANGUAGE}/pricing/{self.product_key}.json"

    @property
    def sidecar_relative_path(self) -> str:
        return (
            f"diagnostics/{LANGUAGE}/pricing/"
            f"{self.product_key}.sidecar.json"
        )


PRODUCTS = tuple(
    ProductSpec(product_key)
    for product_key in (
        "cloud-services",
        "form-recognizer",
        "database-migration",
        "sql-database",
        "power-bi-embedded",
        "ip-addresses",
        "hdinsight",
        "time-series-insights",
        "databricks",
        "azure-firewall",
        "backup",
        "application-gateway",
        "machine-learning",
        "service-bus",
    )
)

CriteriaKey = tuple[tuple[str, str], ...]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected one JSON object: {path}")
    return value


def _compact_html(value: str) -> str:
    value = re.sub(r"\n+", " ", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"<div>\s*</div>", "", value)
    value = re.sub(r">\s+<", "><", value)
    return value.strip()


def _expected_cms_wire_html(value: str) -> tuple[str, dict[str, Any]]:
    """Independently materialize the frozen CSS-only tick glyph contract."""

    transformation_count = 0

    def replace_empty_icon(match: re.Match[str]) -> str:
        nonlocal transformation_count
        attributes = match.group("attributes")
        class_match = _CLASS_ATTRIBUTE_PATTERN.search(attributes)
        if class_match is None:
            return match.group(0)
        class_value = (
            class_match.group("double")
            if class_match.group("double") is not None
            else class_match.group("single")
        )
        if "icon-tick" not in str(class_value).split():
            return match.group(0)
        transformation_count += 1
        return ICON_TICK_TEXT

    parts = _HTML_COMMENT_PATTERN.split(value)
    for index in range(0, len(parts), 2):
        parts[index] = _EMPTY_ITALIC_PATTERN.sub(
            replace_empty_icon,
            parts[index],
        )
    return "".join(parts), {
        "algorithm_version": CMS_HTML_SEMANTIC_MATERIALIZATION_VERSION,
        "transformation_count": transformation_count,
        "rules": [
            {
                "source": "live empty i.icon-tick",
                "replacement_text": ICON_TICK_TEXT,
                "count": transformation_count,
            }
        ],
    }


def _clone_tag(tag: Tag) -> Tag:
    clone = BeautifulSoup(str(tag), "html.parser").find()
    if not isinstance(clone, Tag):
        raise ValueError("Unable to clone source DOM node")
    return clone


def _text(node: Tag | BeautifulSoup | None) -> str:
    if node is None:
        return ""
    return " ".join(node.get_text(" ", strip=True).split())


def _apply_asset_paths(soup: BeautifulSoup) -> None:
    """Apply the public pricing fragment path contract without production code."""

    for image in soup.find_all("img"):
        source = str(image.get("src") or "")
        if source.startswith("/"):
            image["src"] = "{base_url}" + source
    style_pattern = re.compile(r"url\([\"']?(/[^\"']*?)[\"']?\)")
    for element in soup.find_all(style=True):
        element["style"] = style_pattern.sub(
            lambda match: f'url("{{base_url}}{match.group(1)}")',
            str(element["style"]),
        )
    data_pattern = re.compile(
        r"([\"'](?:backgroundImage|background-image)[\"']:\s*[\"'])"
        r"(/[^\"']*?)([\"'])"
    )
    for element in soup.find_all(attrs={"data-config": True}):
        element["data-config"] = data_pattern.sub(
            lambda match: (
                f"{match.group(1)}{{base_url}}{match.group(2)}"
                f"{match.group(3)}"
            ),
            str(element["data-config"]),
        )


def _pricing_soup(source_path: Path) -> BeautifulSoup:
    soup = BeautifulSoup(source_path.read_text(encoding="utf-8"), "html.parser")
    _apply_asset_paths(soup)
    return soup


def _load_soft_category() -> tuple[
    dict[tuple[str, str], tuple[str, ...]],
    dict[str, Any],
]:
    raw_bytes = SOFT_CATEGORY_PATH.read_bytes()
    raw = json.loads(raw_bytes.decode("utf-8-sig"))
    if not isinstance(raw, list):
        raise ValueError("soft-category.json must be an array")
    result: dict[tuple[str, str], tuple[str, ...]] = {}
    row_indices: dict[tuple[str, str], int] = {}
    for index, row in enumerate(raw):
        if not isinstance(row, dict):
            continue
        key = (
            str(row.get("os") or "").strip(),
            str(row.get("region") or "").strip(),
        )
        if not all(key):
            continue
        if key in result:
            raise ValueError(
                "Duplicate soft-category state at rows "
                f"{row_indices[key]} and {index}: {key!r}"
            )
        table_ids = tuple(
            dict.fromkeys(
                str(value).strip().removeprefix("#")
                for value in row.get("tableIDs", [])
                if str(value).strip()
            )
        )
        result[key] = table_ids
        row_indices[key] = index
    return result, {
        "path": str(SOFT_CATEGORY_PATH.relative_to(PROJECT_ROOT)),
        "sha256": _sha256_bytes(raw_bytes),
        "size_bytes": len(raw_bytes),
        "row_count": len(raw),
        "state_count": len(result),
        "row_indices": {
            f"{software}|{region}": index
            for (software, region), index in row_indices.items()
        },
    }


def _normalize_comparison_url(value: str, source_url: str) -> str:
    normalized = value.strip().replace("{base_url}", "https://www.azure.cn")
    lowered = normalized.lower()
    if lowered.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
        return normalized
    resolved = urljoin(source_url, normalized)
    parsed = urlparse(resolved)
    host = parsed.hostname or ""
    if host == "azure.cn" or host.endswith(".azure.cn"):
        suffix = parsed.path or "/"
        if parsed.query:
            suffix += f"?{parsed.query}"
        if parsed.fragment:
            suffix += f"#{parsed.fragment}"
        return suffix
    return resolved


def _canonical_node(node: Any, source_url: str, *, structure_only: bool) -> Any:
    if isinstance(node, Comment):
        return None
    if isinstance(node, NavigableString):
        value = " ".join(str(node).replace("\xa0", " ").split())
        if not value or structure_only:
            return None
        return ("#text", value)
    if not isinstance(node, Tag):
        return None
    attributes: list[tuple[str, Any]] = []
    for key, raw in sorted(node.attrs.items()):
        if isinstance(raw, list):
            value: Any = (
                sorted(str(item) for item in raw)
                if key == "class"
                else [str(item) for item in raw]
            )
        else:
            value = str(raw)
            if key in {"href", "src", "poster"}:
                value = _normalize_comparison_url(value, source_url)
            else:
                value = value.replace("{base_url}", "")
        if not structure_only or key in {"id", "class"}:
            attributes.append((key, value))
    children = [
        canonical
        for child in node.children
        if (
            canonical := _canonical_node(
                child,
                source_url,
                structure_only=structure_only,
            )
        )
        is not None
    ]
    return (node.name, attributes, children)


def _canonical_html(value: str, source_url: str, *, structure_only: bool) -> str:
    soup = BeautifulSoup(value, "html.parser")
    nodes = [
        canonical
        for child in soup.contents
        if (
            canonical := _canonical_node(
                child,
                source_url,
                structure_only=structure_only,
            )
        )
        is not None
    ]
    return json.dumps(nodes, ensure_ascii=False, separators=(",", ":"))


def _fragment_inventory(value: str) -> dict[str, Any]:
    soup = BeautifulSoup(value, "html.parser")
    tags = Counter(tag.name for tag in soup.find_all(True))
    table_ids = [str(table.get("id") or "") for table in soup.find_all("table")]
    duplicates = sorted(
        table_id
        for table_id, count in Counter(table_ids).items()
        if table_id and count > 1
    )
    visible_text = _text(soup)
    return {
        "length": len(value),
        "sha256": _sha256_text(value),
        "visible_text_sha256": _sha256_text(visible_text),
        "visible_text_length": len(visible_text),
        "tag_counts": dict(sorted(tags.items())),
        "table_ids": table_ids,
        "duplicate_table_ids": duplicates,
    }


def _safe_key(key: CriteriaKey) -> str:
    if not key:
        return "page"
    value = "--".join(f"{name}-{item}" for name, item in key)
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


def _criteria_key(group: dict[str, Any]) -> CriteriaKey:
    criteria = json.loads(str(group.get("filterCriteriaJson") or "[]"))
    if not isinstance(criteria, list):
        raise ValueError("filterCriteriaJson must be an array")
    result = tuple(
        (
            str(item.get("filterKey") or ""),
            str(item.get("matchValues") or ""),
        )
        for item in criteria
        if isinstance(item, dict)
    )
    if any(not all(pair) for pair in result):
        raise ValueError(f"Incomplete filter criteria: {result!r}")
    return result


def _active(link: Tag) -> bool:
    parent = link.find_parent("li")
    return bool(
        isinstance(parent, Tag)
        and {"active", "selected", "selected-item"}.intersection(
            parent.get("class", [])
        )
    )


def _discover_control(root: Tag, kind: str) -> dict[str, Any]:
    if kind == "region":
        container_class = "region-container"
        select_id = "region-box"
    elif kind == "software":
        container_class = "software-kind-container"
        select_id = "software-box"
    else:
        raise ValueError(f"Unknown control kind: {kind}")

    containers = root.select(f"div.dropdown-container.{container_class}")
    observation: dict[str, Any] = {
        "kind": kind,
        "container_count": len(containers),
        "options": [],
        "findings": [],
    }
    if len(containers) != 1:
        observation["findings"].append({
            "code": "control_container_count",
            "count": len(containers),
        })
        return observation
    container = containers[0]
    style = "".join(str(container.get("style") or "").casefold().split())
    observation["visible"] = "display:none" not in style
    observation["selected_item_label"] = _text(
        container.select_one(".selected-item")
    )

    mobile = container.select_one(f"select#{select_id}")
    mobile_options = (
        mobile.find_all("option", recursive=False)
        if isinstance(mobile, Tag)
        else []
    )
    mobile_by_href: dict[str, list[Tag]] = defaultdict(list)
    for option in mobile_options:
        mobile_by_href[str(option.get("data-href") or "").strip()].append(option)

    desktop_links = container.select(
        ".dropdown-box.os-tab-nav .tab-items a[data-href]"
    )
    options: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for link in desktop_links:
        href = str(link.get("data-href") or "").strip()
        mobile_matches = mobile_by_href.get(href, [])
        mobile_values = tuple(
            dict.fromkeys(
                str(option.get("value") or "").strip()
                for option in mobile_matches
                if str(option.get("value") or "").strip()
            )
        )
        if kind == "region":
            value = href.removeprefix("#")
        elif len(mobile_values) == 1:
            value = mobile_values[0]
        else:
            value = str(link.get("data-value") or "").strip() or _text(link)
        identity = (value, href)
        if identity in seen:
            observation["findings"].append({
                "code": "duplicate_desktop_option",
                "value": value,
                "href": href,
            })
            continue
        seen.add(identity)
        options.append({
            "value": value,
            "label": _text(link),
            "href": href,
            "desktop_active": _active(link),
            "mobile_values": list(mobile_values),
            "mobile_labels": [_text(option) for option in mobile_matches],
            "mobile_selected_count": sum(
                option.has_attr("selected") for option in mobile_matches
            ),
        })

    for option in mobile_options:
        href = str(option.get("data-href") or "").strip()
        value = (
            href.removeprefix("#")
            if kind == "region"
            else str(option.get("value") or "").strip()
        )
        identity = (value, href)
        if not all(identity) or identity in seen:
            continue
        seen.add(identity)
        options.append({
            "value": value,
            "label": _text(option),
            "href": href,
            "desktop_active": False,
            "mobile_values": [str(option.get("value") or "").strip()],
            "mobile_labels": [_text(option)],
            "mobile_selected_count": int(option.has_attr("selected")),
            "mobile_only": True,
        })

    active = [option for option in options if option["desktop_active"]]
    observation["desktop_default_status"] = (
        "unique" if len(active) == 1 else "missing" if not active else "ambiguous"
    )
    observation["desktop_default"] = active[0] if len(active) == 1 else None
    if len(active) == 1:
        options = [active[0], *(item for item in options if item is not active[0])]
        summary = observation["selected_item_label"]
        if summary and summary != active[0]["label"]:
            observation["findings"].append({
                "code": "display_summary_default_drift",
                "summary": summary,
                "desktop_default_label": active[0]["label"],
            })
    else:
        observation["findings"].append({
            "code": "desktop_default_not_unique",
            "active_count": len(active),
        })

    desktop_hrefs = {
        str(link.get("data-href") or "").strip() for link in desktop_links
    }
    mobile_hrefs = set(mobile_by_href)
    if desktop_hrefs != mobile_hrefs:
        observation["findings"].append({
            "code": "responsive_option_domain_drift",
            "desktop_only": sorted(desktop_hrefs - mobile_hrefs),
            "mobile_only": sorted(mobile_hrefs - desktop_hrefs),
        })
    for option in options:
        target_id = str(option["href"]).removeprefix("#")
        matches = root.find_all(id=target_id)
        option["target_match_count"] = len(matches)
        option["target_tags"] = [match.name for match in matches]
        option["target_classes"] = [match.get("class", []) for match in matches]
    observation["options"] = options
    observation["mobile_selected_hrefs"] = [
        str(option.get("data-href") or "").strip()
        for option in mobile_options
        if option.has_attr("selected")
    ]
    return observation


def _selector_observation(soup: BeautifulSoup) -> tuple[Tag | None, dict[str, Any]]:
    roots = soup.select("div.technical-azure-selector.pricing-detail-tab")
    external_scripts = [
        str(script.get("src"))
        for script in soup.find_all("script", src=True)
    ]
    observation: dict[str, Any] = {
        "pricing_selector_count": len(roots),
        "pricing_selector_classes": [root.get("class", []) for root in roots],
        "external_scripts": external_scripts,
        "frozen_script_files_present": {
            value: (PROJECT_ROOT / value.lstrip("/")).is_file()
            for value in external_scripts
            if not value.startswith(("http://", "https://"))
        },
    }
    if len(roots) != 1:
        observation["findings"] = [{
            "code": "pricing_selector_count",
            "count": len(roots),
        }]
        return None, observation
    root = roots[0]
    observation["software"] = _discover_control(root, "software")
    observation["region"] = _discover_control(root, "region")
    return root, observation


def _category_options(panel: Tag) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    options: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for link in panel.select("a[data-href]"):
        href = str(link.get("data-href") or "").strip()
        target_id = href.removeprefix("#")
        if not target_id or target_id == str(panel.get("id") or ""):
            continue
        matches = panel.find_all(id=target_id)
        panel_matches = [
            match
            for match in matches
            if isinstance(match, Tag)
            and "tab-panel" in match.get("class", [])
        ]
        label = _text(link)
        if not panel_matches:
            if label.casefold() in {"all", "全部"}:
                findings.append({
                    "code": "non_materialized_aggregate_tab",
                    "label": label,
                    "href": href,
                })
            continue
        if target_id in seen:
            continue
        seen.add(target_id)
        options.append({
            "value": target_id,
            "label": label,
            "href": href,
            "desktop_active": _active(link),
            "target_match_count": len(panel_matches),
        })
    active = [option for option in options if option["desktop_active"]]
    if len(active) == 1:
        options = [active[0], *(item for item in options if item is not active[0])]
    elif options:
        findings.append({
            "code": "category_default_not_unique",
            "active_count": len(active),
        })
    return options, findings


def _remove_configured_tables(
    scope: Tag,
    table_ids: Iterable[str],
) -> dict[str, Any]:
    removed: list[str] = []
    ambiguous: list[str] = []
    wrapper_ambiguities: list[str] = []
    for table_id in table_ids:
        matches = [
            tag
            for tag in scope.find_all(id=table_id)
            if isinstance(tag, Tag) and tag.name == "table"
        ]
        if not matches:
            continue
        if len(matches) != 1:
            ambiguous.append(table_id)
            continue
        table = matches[0]
        target = table
        for parent in table.parents:
            if parent is scope:
                break
            if isinstance(parent, Tag) and "scroll-table" in parent.get(
                "class", []
            ):
                if parent.find_all("table") != [table]:
                    wrapper_ambiguities.append(table_id)
                    target = table
                else:
                    target = parent
                break
        target.decompose()
        removed.append(table_id)
    return {
        "removed_table_ids": removed,
        "ambiguous_table_ids": ambiguous,
        "multi_table_wrapper_ids": wrapper_ambiguities,
        "projection_complete": not ambiguous and not wrapper_ambiguities,
    }


def _project_fragment(
    source: Tag,
    *,
    software_value: str | None,
    region_value: str | None,
    soft_category: dict[tuple[str, str], tuple[str, ...]],
    soft_evidence: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    clone = _clone_tag(source)
    table_ids = (
        soft_category.get((software_value, region_value), ())
        if software_value and region_value
        else ()
    )
    projection = _remove_configured_tables(clone, table_ids)
    state_name = (
        f"{software_value}|{region_value}"
        if software_value and region_value
        else None
    )
    projection.update({
        "configuration_state": state_name,
        "configuration_row_index": (
            soft_evidence["row_indices"].get(state_name) if state_name else None
        ),
        "configured_table_ids": list(table_ids),
        "source_node_id": str(source.get("id") or ""),
        "source_node_classes": source.get("class", []),
        "source_table_ids": [
            str(table.get("id") or "") for table in source.find_all("table")
        ],
    })
    return _compact_html(str(clone)), projection


def _criteria(
    *,
    region: str | None,
    software: str | None,
    category: str | None,
) -> CriteriaKey:
    result: list[tuple[str, str]] = []
    if region:
        result.append(("region", region))
    if software:
        result.append(("software", software))
    if category:
        result.append(("category", category))
    return tuple(result)


def _candidate(
    key: CriteriaKey,
    html: str,
    *,
    locator: dict[str, Any],
) -> dict[str, Any]:
    return {
        "state": [list(pair) for pair in key],
        "state_key": key,
        "html": html,
        "locator": locator,
    }


def _simple_candidates(
    soup: BeautifulSoup,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    roots = soup.select("div.technical-azure-selector.tab-control-selector")
    observation: dict[str, Any] = {
        "simple_root_count": len(roots),
        "fallback_used": False,
        "findings": [],
    }
    if len(roots) == 1:
        return [
            _candidate(
                (),
                _compact_html(str(roots[0])),
                locator={
                    "kind": "technical_selector",
                    "selector": (
                        "div.technical-azure-selector.tab-control-selector"
                    ),
                },
            )
        ], observation

    fallback = [
        section
        for section in soup.select("div.pricing-page-section")
        if not section.select_one(".more-detail")
        and "支持和服务级别协议" not in _text(section)
    ]
    observation["fallback_used"] = True
    observation["fallback_pricing_section_count"] = len(fallback)
    observation["findings"].append({
        "code": "simple_intrinsic_boundary_unproven",
        "technical_root_count": len(roots),
        "fallback_candidate_count": len(fallback),
    })
    return [
        _candidate(
            (),
            _compact_html(str(section)),
            locator={
                "kind": "unproven_pricing_section_candidate",
                "candidate_index": index,
            },
        )
        for index, section in enumerate(fallback, start=1)
    ], observation


def _region_candidates(
    root: Tag,
    observation: dict[str, Any],
    soft_category: dict[tuple[str, str], tuple[str, ...]],
    soft_evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    regions = observation.get("region", {}).get("options", [])
    software = observation.get("software", {}).get("options", [])
    contents = root.select("div.tab-content")
    if not contents:
        observation.setdefault("findings", []).append({
            "code": "region_content_root_missing",
        })
        return []
    if len(software) != 1:
        observation.setdefault("findings", []).append({
            "code": "region_internal_software_count",
            "count": len(software),
        })
    candidates: list[dict[str, Any]] = []
    for region in regions:
        for internal_software in software or [None]:
            software_value = (
                str(internal_software["value"])
                if isinstance(internal_software, dict)
                else None
            )
            html, projection = _project_fragment(
                contents[0],
                software_value=software_value,
                region_value=str(region["value"]),
                soft_category=soft_category,
                soft_evidence=soft_evidence,
            )
            candidates.append(_candidate(
                _criteria(
                    region=str(region["value"]),
                    software=None,
                    category=None,
                ),
                html,
                locator={
                    "kind": "region_projected_tab_content",
                    "region_control": region,
                    "internal_software_control": internal_software,
                    "tab_content_index": 0,
                    "soft_category_projection": projection,
                },
            ))
    return candidates


def _complex_candidates(
    root: Tag,
    observation: dict[str, Any],
    soft_category: dict[tuple[str, str], tuple[str, ...]],
    soft_evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    regions = observation.get("region", {}).get("options", [])
    software_control = observation.get("software", {})
    software_options = software_control.get("options", [])
    software_visible = bool(software_control.get("visible"))
    candidates: list[dict[str, Any]] = []
    software_observations: list[dict[str, Any]] = []
    for software in software_options:
        panel_id = str(software.get("href") or "").removeprefix("#")
        panels = [
            match
            for match in root.find_all(id=panel_id)
            if isinstance(match, Tag)
            and "tab-panel" in match.get("class", [])
        ]
        panel_observation: dict[str, Any] = {
            "software_value": software.get("value"),
            "software_panel_id": panel_id,
            "software_panel_match_count": len(panels),
            "candidate_panels": [],
        }
        for panel_index, panel in enumerate(panels, start=1):
            categories, findings = _category_options(panel)
            panel_observation["candidate_panels"].append({
                "candidate_index": panel_index,
                "category_options": categories,
                "findings": findings,
            })
            targets: list[tuple[dict[str, Any] | None, Tag]] = []
            if categories:
                for category in categories:
                    target_id = str(category["value"])
                    matches = [
                        match
                        for match in panel.find_all(id=target_id)
                        if isinstance(match, Tag)
                        and "tab-panel" in match.get("class", [])
                    ]
                    for match in matches:
                        targets.append((category, match))
            else:
                targets.append((None, panel))
            for region in regions or [None]:
                region_value = (
                    str(region["value"]) if isinstance(region, dict) else None
                )
                for category, target in targets:
                    category_value = (
                        str(category["value"])
                        if isinstance(category, dict)
                        else None
                    )
                    html, projection = _project_fragment(
                        target,
                        software_value=str(software.get("value") or "") or None,
                        region_value=region_value,
                        soft_category=soft_category,
                        soft_evidence=soft_evidence,
                    )
                    candidates.append(_candidate(
                        _criteria(
                            region=region_value,
                            software=(
                                str(software.get("value"))
                                if software_visible
                                else None
                            ),
                            category=category_value,
                        ),
                        html,
                        locator={
                            "kind": "complex_control_state",
                            "region_control": region,
                            "software_control": software,
                            "software_panel_id": panel_id,
                            "software_panel_candidate_index": panel_index,
                            "category_control": category,
                            "category_panel_id": category_value,
                            "soft_category_projection": projection,
                        },
                    ))
        software_observations.append(panel_observation)
    observation["software_panel_observations"] = software_observations
    return candidates


def _page_global_candidate(
    soup: BeautifulSoup,
    definition: dict[str, Any],
) -> tuple[str | None, dict[str, Any]]:
    config = definition.get("extraction", {}).get("page_global_content")
    evidence: dict[str, Any] = {
        "configured": isinstance(config, dict),
        "source_boundary": (
            config.get("source_boundary") if isinstance(config, dict) else None
        ),
        "candidate_count": 0,
    }
    if not isinstance(config, dict):
        return None, evidence
    if config.get("source_boundary") != "after_final_formal_selector_before_common_sections":
        return None, evidence
    selectors = soup.select("div.technical-azure-selector")
    if not selectors:
        evidence["error"] = "formal_selector_missing"
        return None, evidence
    candidates: list[Tag] = []
    for sibling in selectors[-1].next_siblings:
        if not isinstance(sibling, Tag):
            continue
        if sibling.select_one(".more-detail"):
            break
        text = _text(sibling)
        if "支持和服务级别协议" in text:
            break
        if "pricing-page-section" in sibling.get("class", []):
            candidates.append(sibling)
    evidence["candidate_count"] = len(candidates)
    evidence["candidate_classes"] = [item.get("class", []) for item in candidates]
    if not candidates:
        return None, evidence
    return _compact_html("".join(str(candidate) for candidate in candidates)), evidence


def _payload_fragments(payload: dict[str, Any]) -> tuple[
    dict[CriteriaKey, str],
    str | None,
]:
    groups = payload.get("contentGroups")
    if not isinstance(groups, list):
        raise ValueError("Payload contentGroups must be an array")
    fragments: dict[CriteriaKey, str] = {}
    for group in groups:
        if not isinstance(group, dict):
            continue
        key = _criteria_key(group)
        if key in fragments:
            raise ValueError(f"Duplicate payload state: {key!r}")
        fragments[key] = str(group.get("content") or "")
    base_content = str(payload.get("baseContent") or "")
    return fragments, base_content or None


def _unique_source_fragments(
    candidates: list[dict[str, Any]],
) -> tuple[
    dict[CriteriaKey, dict[str, Any]],
    dict[CriteriaKey, list[dict[str, Any]]],
]:
    grouped: dict[CriteriaKey, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate["state_key"]].append(candidate)
    unique = {
        key: values[0]
        for key, values in grouped.items()
        if len(values) == 1
    }
    ambiguous = {
        key: values
        for key, values in grouped.items()
        if len(values) != 1
    }
    return unique, ambiguous


def _pretty_html(value: str) -> list[str]:
    return BeautifulSoup(value, "html.parser").prettify().splitlines()


def _write_comparison(
    *,
    product_key: str,
    field: str,
    key: CriteriaKey,
    source: dict[str, Any],
    payload_html: str,
    source_url: str,
    fragment_root: Path,
) -> dict[str, Any]:
    source_html = str(source["html"])
    expected_source_html, semantic_materialization = (
        _expected_cms_wire_html(source_html)
    )
    source_raw_canonical = _canonical_html(
        source_html,
        source_url,
        structure_only=False,
    )
    source_canonical = _canonical_html(
        expected_source_html,
        source_url,
        structure_only=False,
    )
    payload_canonical = _canonical_html(
        payload_html,
        source_url,
        structure_only=False,
    )
    source_raw_structure = _canonical_html(
        source_html,
        source_url,
        structure_only=True,
    )
    source_structure = _canonical_html(
        expected_source_html,
        source_url,
        structure_only=True,
    )
    payload_structure = _canonical_html(
        payload_html,
        source_url,
        structure_only=True,
    )
    source_inventory = _fragment_inventory(source_html)
    expected_source_inventory = _fragment_inventory(expected_source_html)
    payload_inventory = _fragment_inventory(payload_html)
    product_root = fragment_root / product_key / field
    product_root.mkdir(parents=True, exist_ok=True)
    name = _safe_key(key)
    source_path = product_root / f"{name}.source.html"
    expected_source_path = product_root / f"{name}.expected.html"
    payload_path = product_root / f"{name}.payload.html"
    diff_path = product_root / f"{name}.diff"
    raw_diff_path = product_root / f"{name}.source-to-payload.diff"
    source_path.write_text(source_html, encoding="utf-8")
    payload_path.write_text(payload_html, encoding="utf-8")
    raw_equal = source_html == payload_html
    wire_equal = expected_source_html == payload_html
    has_semantic_materialization = bool(
        semantic_materialization["transformation_count"]
    )
    if has_semantic_materialization:
        expected_source_path.write_text(
            expected_source_html,
            encoding="utf-8",
        )
        relative_expected_source: str | None = str(
            expected_source_path.relative_to(fragment_root.parent)
        )
    else:
        if expected_source_path.exists():
            expected_source_path.unlink()
        relative_expected_source = None

    if raw_equal:
        if raw_diff_path.exists():
            raw_diff_path.unlink()
        relative_raw_diff: str | None = None
    else:
        raw_diff = "\n".join(difflib.unified_diff(
            _pretty_html(source_html),
            _pretty_html(payload_html),
            fromfile=source_path.name,
            tofile=payload_path.name,
            lineterm="",
        ))
        raw_diff_path.write_text(
            raw_diff + ("\n" if raw_diff else ""),
            encoding="utf-8",
        )
        relative_raw_diff = str(
            raw_diff_path.relative_to(fragment_root.parent)
        )

    if wire_equal:
        if diff_path.exists():
            diff_path.unlink()
        relative_diff: str | None = None
    else:
        diff = "\n".join(difflib.unified_diff(
            _pretty_html(expected_source_html),
            _pretty_html(payload_html),
            fromfile=(
                expected_source_path.name
                if has_semantic_materialization
                else source_path.name
            ),
            tofile=payload_path.name,
            lineterm="",
        ))
        diff_path.write_text(diff + ("\n" if diff else ""), encoding="utf-8")
        relative_diff = str(diff_path.relative_to(fragment_root.parent))
    return {
        "field": field,
        "state": [list(pair) for pair in key],
        "raw_equal": raw_equal,
        "wire_equal": wire_equal,
        "source_raw_dom_equal": (
            source_raw_canonical == payload_canonical
        ),
        "dom_equal": source_canonical == payload_canonical,
        "source_raw_structure_equal": (
            source_raw_structure == payload_structure
        ),
        "structure_equal": source_structure == payload_structure,
        "source_raw_visible_text_equal": (
            source_inventory["visible_text_sha256"]
            == payload_inventory["visible_text_sha256"]
        ),
        "visible_text_equal": (
            expected_source_inventory["visible_text_sha256"]
            == payload_inventory["visible_text_sha256"]
        ),
        "table_ids_equal": (
            expected_source_inventory["table_ids"]
            == payload_inventory["table_ids"]
        ),
        "source": source_inventory,
        "expected_source": expected_source_inventory,
        "payload": payload_inventory,
        "source_raw_dom_sha256": _sha256_text(source_raw_canonical),
        "source_dom_sha256": _sha256_text(source_canonical),
        "payload_dom_sha256": _sha256_text(payload_canonical),
        "source_raw_structure_sha256": _sha256_text(
            source_raw_structure
        ),
        "source_structure_sha256": _sha256_text(source_structure),
        "payload_structure_sha256": _sha256_text(payload_structure),
        "source_fragment": str(source_path.relative_to(fragment_root.parent)),
        "expected_source_fragment": relative_expected_source,
        "payload_fragment": str(payload_path.relative_to(fragment_root.parent)),
        "source_to_payload_diff": relative_raw_diff,
        "diff": relative_diff,
        "semantic_materialization": semantic_materialization,
        "source_locator": source["locator"],
    }


def _write_source_candidates(
    *,
    product_key: str,
    candidates: list[dict[str, Any]],
    fragment_root: Path,
) -> list[dict[str, Any]]:
    root = fragment_root / product_key / "source-candidates"
    root.mkdir(parents=True, exist_ok=True)
    grouped: dict[CriteriaKey, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate["state_key"]].append(candidate)
    records: list[dict[str, Any]] = []
    for key, values in sorted(grouped.items()):
        for index, candidate in enumerate(values, start=1):
            suffix = f"--candidate-{index}" if len(values) > 1 else ""
            path = root / f"{_safe_key(key)}{suffix}.source.html"
            path.write_text(str(candidate["html"]), encoding="utf-8")
            records.append({
                "state": [list(pair) for pair in key],
                "candidate_index": index,
                "candidate_count": len(values),
                "fragment": str(path.relative_to(fragment_root.parent)),
                "inventory": _fragment_inventory(str(candidate["html"])),
                "locator": candidate["locator"],
            })
    return records


def _swap_mutation(
    *,
    product_key: str,
    source_url: str,
    source: dict[CriteriaKey, dict[str, Any]],
    payload: dict[CriteriaKey, str],
) -> dict[str, Any] | None:
    common = sorted(set(source).intersection(payload))
    pair: tuple[CriteriaKey, CriteriaKey] | None = None
    for first_index, first in enumerate(common):
        first_dom = _canonical_html(
            str(source[first]["html"]), source_url, structure_only=False
        )
        for second in common[first_index + 1:]:
            second_dom = _canonical_html(
                str(source[second]["html"]), source_url, structure_only=False
            )
            if first_dom != second_dom:
                pair = (first, second)
                break
        if pair is not None:
            break
    if pair is None:
        return None
    first, second = pair
    mutated = dict(payload)
    mutated[first], mutated[second] = mutated[second], mutated[first]
    detected = [
        key
        for key in pair
        if _canonical_html(
            str(source[key]["html"]), source_url, structure_only=False
        )
        != _canonical_html(mutated[key], source_url, structure_only=False)
    ]
    return {
        "product_key": product_key,
        "kind": "swap_state_content",
        "mutated_states": [[list(item) for item in key] for key in pair],
        "detected_states": [[list(item) for item in key] for key in detected],
        "detected": set(detected) == set(pair),
    }


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# v0.4.1 中文 DOM 与 CMS payload 对比实验",
        "",
        (
            "本实验先使用基于 v0.4.1 的当前工作树 CLI 生成 payload，再以独立"
            "程序读取冻结 HTML。软件／地区内容显式结合 `soft-category.json`；"
            "独立程序不导入生产抽取、状态解析、地区处理、HTML 清洗或 payload "
            "组装代码。对于 CSS-only glyph，独立程序按冻结的 CMS 线格式契约"
            "另行实现语义实体化。"
        ),
        "",
        "## 总结",
        "",
        f"- 产品：{summary['products']} 个。",
        (
            f"- 当前抽取成功：{summary['extractor_succeeded']} 个；失败："
            f"{summary['extractor_failed']} 个。"
        ),
        f"- 可逐项比较片段：{summary['comparisons']} 个。",
        (
            f"- 冻结源原始字符串与 payload 一致：{summary['raw_equal']} 个。"
        ),
        (
            "- 应用预期 CMS 语义转换后的线格式一致："
            f"{summary['wire_equal']} 个。"
        ),
        (
            "- 预期线格式 DOM 归一后一致："
            f"{summary['dom_equal']} 个。"
        ),
        (
            "- 预期线格式可见文本一致："
            f"{summary['visible_text_equal']} 个。"
        ),
        (
            "- CSS-only glyph 语义实体化："
            f"{summary['semantic_materializations']} 个。"
        ),
        (
            f"- 受控错状态检测：{summary['mutation_detected']}/"
            f"{summary['mutation_checks']}。"
        ),
        (
            "- 已成功抽取产品的内容保真结论："
            f"{'通过' if report['comparable_fidelity_passed'] else '存在差异'}。"
        ),
        (
            "- 14 产品完整抽取能力结论："
            f"{'通过' if report['full_extractor_capability_passed'] else '存在能力边界'}。"
        ),
        "",
        "## 产品结果",
        "",
        (
            "| 产品 | 抽取 | 源状态 | payload 状态 | 对比 | 原始一致 | "
            "线格式一致 | DOM 一致 | 结论 |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for product in report["products"]:
        comparisons = product["comparisons"]
        lines.append(
            "| {product} | {execution} | {source_states} | {payload_states} | "
            "{count} | {raw} | {wire} | {dom} | {outcome} |".format(
                product=product["product_key"],
                execution=product["extractor_status"].get("execution", "missing"),
                source_states=product["source_unique_state_count"],
                payload_states=product["payload_state_count"],
                count=len(comparisons),
                raw=sum(item["raw_equal"] for item in comparisons),
                wire=sum(item["wire_equal"] for item in comparisons),
                dom=sum(item["dom_equal"] for item in comparisons),
                outcome=product["outcome"],
            )
        )

    failed = [
        product
        for product in report["products"]
        if product["extractor_status"].get("execution") != "succeeded"
    ]
    lines.extend(["", "## 当前抽取器暴露的能力边界", ""])
    for product in failed:
        error = product.get("extractor_error") or {}
        lines.append(
            f"- `{product['product_key']}` — `{error.get('code', 'unknown')}`："
            f"{error.get('message', '未提供错误消息')}"
        )

    lines.extend([
        "",
        "## 方法边界",
        "",
        (
            "- 地区和软件控件提供状态身份与默认状态；地区链接本身通常不指向"
            "独立内容面板。"
        ),
        (
            "- 因此地区片段使用冻结 DOM 加 `soft-category.json` 的"
            "`软件 + 地区 -> 删除表格 ID` 关系生成。"
        ),
        (
            "- category 页签必须直接指向当前软件面板内唯一的 `tab-panel`；"
            "缺失的“全部”聚合页签被记录但不臆造内容。"
        ),
        (
            "- 原始字符串比较物理冻结 DOM 与 payload；预期 CMS 线格式比较先"
            "按 `css-generated-semantics-v1` 将 live 空 `i.icon-tick` 转为 `✓`，"
            "HTML 注释不变。DOM 比较忽略注释、空白和属性顺序，并统一 Azure "
            "站内 URL。"
        ),
        (
            "- 抽取失败产品仍保存独立 DOM 候选片段，但没有 CMS payload 时"
            "不会声称内容一致。"
        ),
    ])

    browser_probe = report.get("browser_probe")
    if isinstance(browser_probe, dict):
        lines.extend(["", "## 真实浏览器探针", ""])
        lines.append(
            f"- 页面：`{browser_probe.get('page', '')}`。"
        )
        lines.append(
            "- 冻结页原生点击后业务 DOM："
            + (
                "发生变化。"
                if browser_probe.get("business_dom_changed")
                else "未发生变化。"
            )
        )
        lines.append(
            "- 结论："
            + str(browser_probe.get("conclusion") or "未提供")
        )

    lines.extend([
        "",
        "## 人工校验入口",
        "",
        "- `report.json`：逐状态哈希、定位证据、删除表格和比较结果。",
        "- `manual-review.html`：源片段与 payload 片段的本地并排人工复核入口。",
        "- `observations/`：每个产品的控件与 DOM 结构观察。",
        "- `fragments/<product>/content-groups/`：源片段和 payload 片段。",
        "- `fragments/<product>/base-content/`：`baseContent` 对照。",
        (
            "- `*.expected.html`：仅在存在预期 CMS 语义转换时生成的源线格式"
            "投影。"
        ),
        (
            "- `fragments/<product>/source-candidates/`：包括抽取失败产品在内的"
            "全部独立源候选片段。"
        ),
        "- `*.diff`：预期 CMS 线格式与 payload 不一致时生成。",
        (
            "- `*.source-to-payload.diff`：物理冻结源与 payload 不一致时生成，"
            "包括有意的语义实体化。"
        ),
        "",
    ])
    return "\n".join(lines)


def _render_manual_review(report: dict[str, Any]) -> str:
    def escaped(value: Any) -> str:
        return html_lib.escape(str(value), quote=True)

    sections: list[str] = []
    for product in report["products"]:
        comparison_blocks: list[str] = []
        for item in product["comparisons"]:
            state = ", ".join(
                f"{key}={value}" for key, value in item["state"]
            ) or "页面主体"
            source_path = escaped(item["source_fragment"])
            payload_path = escaped(item["payload_fragment"])
            expected_value = item.get("expected_source_fragment")
            expected_path = (
                escaped(expected_value) if expected_value else None
            )
            transformation_count = item["semantic_materialization"][
                "transformation_count"
            ]
            result = (
                "原始串一致"
                if item["raw_equal"]
                else (
                    f"预期 CMS 线格式一致（{transformation_count} 个转换）"
                    if item["wire_equal"] and transformation_count
                    else "CMS 线格式一致"
                    if item["wire_equal"]
                    else "存在差异"
                )
            )
            expected_section = (
                '<section><h3>预期 CMS 线格式投影</h3>'
                f'<a href="{expected_path}" target="_blank">'
                "单独打开线格式投影</a>"
                f'<iframe loading="lazy" src="{expected_path}"></iframe>'
                "</section>"
                if expected_path is not None
                else ""
            )
            pair_class = "pair transformed" if expected_path else "pair"
            comparison_blocks.append(
                "<details>"
                f"<summary>{escaped(item['field'])} · {escaped(state)} · "
                f"{escaped(result)}</summary>"
                f'<div class="{pair_class}">'
                '<section><h3>冻结源 DOM 原始片段</h3>'
                f'<a href="{source_path}" target="_blank">单独打开源片段</a>'
                f'<iframe loading="lazy" src="{source_path}"></iframe></section>'
                + expected_section
                + '<section><h3>CMS payload 片段</h3>'
                f'<a href="{payload_path}" target="_blank">单独打开 payload 片段</a>'
                f'<iframe loading="lazy" src="{payload_path}"></iframe></section>'
                "</div></details>"
            )
        source_only_links = "".join(
            f'<li><a href="{escaped(path)}" target="_blank">'
            f"{escaped(Path(path).name)}</a></li>"
            for path in product["source_candidate_fragments"]
        )
        source_only = (
            "<details><summary>全部独立源候选片段（"
            f"{len(product['source_candidate_fragments'])}）</summary>"
            f"<ul>{source_only_links}</ul></details>"
            if source_only_links
            else ""
        )
        sections.append(
            f'<article id="{escaped(product["product_key"])}">'
            f"<h2>{escaped(product['product_key'])}</h2>"
            f"<p>抽取：{escaped(product['extractor_status'].get('execution'))}；"
            f"结论：{escaped(product['outcome'])}；"
            f"对比片段：{len(product['comparisons'])}。</p>"
            + "".join(comparison_blocks)
            + source_only
            + "</article>"
        )
    return """<!doctype html>
<html lang="zh-cn">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>v0.4.1 DOM 与 CMS payload 人工复核</title>
<style>
body{font-family:system-ui,-apple-system,sans-serif;margin:0 auto;max-width:1600px;padding:24px;color:#172033;background:#f5f7fb}
h1,h2{color:#0f3b66}article{background:#fff;border:1px solid #d8e1ec;border-radius:10px;padding:18px;margin:18px 0}
details{border-top:1px solid #e4eaf1;padding:10px 0}summary{cursor:pointer;font-weight:600}.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}.pair.transformed{grid-template-columns:repeat(3,1fr)}
.pair section{min-width:0}.pair iframe{display:block;width:100%;height:520px;margin-top:8px;border:1px solid #b8c7d9;background:#fff}
a{color:#0067b8}code{background:#eaf0f7;padding:2px 4px}@media(max-width:900px){.pair{grid-template-columns:1fr}}
</style>
</head>
<body>
<h1>v0.4.1 中文 DOM 与 CMS payload 人工复核</h1>
<p>每个成功状态把冻结源 DOM 片段和 CMS payload 片段并排显示。完整机器证据见 <a href="report.json">report.json</a>，中文结论见 <a href="report.md">report.md</a>。</p>
""" + "".join(sections) + """
</body>
</html>
"""


def run(
    extractor_output: Path,
    output_dir: Path,
    *,
    browser_probe_path: Path | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fragment_root = output_dir / "fragments"
    observation_root = output_dir / "observations"
    fragment_root.mkdir(parents=True, exist_ok=True)
    observation_root.mkdir(parents=True, exist_ok=True)
    soft_category, soft_evidence = _load_soft_category()
    product_reports: list[dict[str, Any]] = []
    mutation_checks: list[dict[str, Any]] = []

    for spec in PRODUCTS:
        source_path = PROJECT_ROOT / spec.source_relative_path
        definition_path = PROJECT_ROOT / spec.definition_relative_path
        payload_path = extractor_output / spec.payload_relative_path
        sidecar_path = extractor_output / spec.sidecar_relative_path
        definition = _read_json(definition_path)
        sidecar = _read_json(sidecar_path)
        strategy = str(definition["extraction"]["semantic_strategy"])
        source_url = str(definition["sources"][LANGUAGE]["url"])
        soup = _pricing_soup(source_path)

        if strategy == "simple_static":
            candidates, observation = _simple_candidates(soup)
        else:
            selector, observation = _selector_observation(soup)
            if selector is None:
                candidates = []
            elif strategy == "region_filter":
                candidates = _region_candidates(
                    selector,
                    observation,
                    soft_category,
                    soft_evidence,
                )
            elif strategy == "complex":
                candidates = _complex_candidates(
                    selector,
                    observation,
                    soft_category,
                    soft_evidence,
                )
            else:
                raise ValueError(f"Unsupported pricing strategy: {strategy}")

        source_unique, source_ambiguous = _unique_source_fragments(candidates)
        source_candidate_records = _write_source_candidates(
            product_key=spec.product_key,
            candidates=candidates,
            fragment_root=fragment_root,
        )
        payload: dict[str, Any] | None = (
            _read_json(payload_path) if payload_path.is_file() else None
        )
        payload_groups: dict[CriteriaKey, str] = {}
        payload_base: str | None = None
        comparisons: list[dict[str, Any]] = []
        page_global_evidence: dict[str, Any] | None = None
        if payload is not None:
            payload_groups, payload_base = _payload_fragments(payload)
            for key in sorted(set(source_unique).intersection(payload_groups)):
                comparisons.append(_write_comparison(
                    product_key=spec.product_key,
                    field="content-groups",
                    key=key,
                    source=source_unique[key],
                    payload_html=payload_groups[key],
                    source_url=source_url,
                    fragment_root=fragment_root,
                ))
            if payload_base is not None:
                if strategy == "simple_static":
                    base_source = source_unique.get(())
                    page_global_evidence = {
                        "kind": "simple_formal_selector",
                        "source_candidate_count": len(
                            [candidate for candidate in candidates if candidate["state_key"] == ()]
                        ),
                    }
                else:
                    page_global, page_global_evidence = _page_global_candidate(
                        soup,
                        definition,
                    )
                    base_source = (
                        {
                            "html": page_global,
                            "locator": {
                                "kind": "product_definition_page_global_boundary",
                                **page_global_evidence,
                            },
                        }
                        if page_global is not None
                        else None
                    )
                if base_source is not None:
                    comparisons.append(_write_comparison(
                        product_key=spec.product_key,
                        field="base-content",
                        key=(),
                        source=base_source,
                        payload_html=payload_base,
                        source_url=source_url,
                        fragment_root=fragment_root,
                    ))

        missing_source = sorted(set(payload_groups) - set(source_unique))
        extra_source_keys = set(source_unique) - set(payload_groups)
        if payload_base is not None and strategy == "simple_static":
            extra_source_keys.discard(())
        extra_source = sorted(extra_source_keys)
        expected_comparison_count = len(payload_groups) + int(payload_base is not None)
        all_comparable = (
            payload is not None
            and not missing_source
            and len(comparisons) == expected_comparison_count
        )
        fidelity_passed = (
            all_comparable
            and bool(comparisons)
            and all(item["wire_equal"] for item in comparisons)
        )
        execution = sidecar.get("status", {}).get("execution")
        semantic_materialization_count = sum(
            item["semantic_materialization"]["transformation_count"]
            for item in comparisons
        )
        if execution != "succeeded":
            outcome = "抽取失败；已留存源 DOM"
        elif fidelity_passed and all(item["raw_equal"] for item in comparisons):
            outcome = "原始串完全一致"
        elif fidelity_passed and semantic_materialization_count:
            outcome = (
                "CMS 线格式完全一致（"
                f"{semantic_materialization_count} 个预期语义转换）"
            )
        elif fidelity_passed:
            outcome = "CMS 线格式完全一致"
        else:
            outcome = "存在差异或状态缺口"

        observation_record = {
            "product_key": spec.product_key,
            "strategy": strategy,
            "source": spec.source_relative_path,
            "observation": observation,
            "page_global": page_global_evidence,
            "source_candidates": source_candidate_records,
            "ambiguous_states": [
                {
                    "state": [list(pair) for pair in key],
                    "candidate_count": len(values),
                }
                for key, values in sorted(source_ambiguous.items())
            ],
        }
        observation_path = observation_root / f"{spec.product_key}.json"
        observation_path.write_text(
            json.dumps(observation_record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        product_report = {
            "product_key": spec.product_key,
            "language": LANGUAGE,
            "strategy": strategy,
            "source": {
                "path": spec.source_relative_path,
                "sha256": _sha256_bytes(source_path.read_bytes()),
                "size_bytes": source_path.stat().st_size,
                "url": source_url,
            },
            "definition": {
                "path": spec.definition_relative_path,
                "sha256": _sha256_bytes(definition_path.read_bytes()),
            },
            "payload": (
                {
                    "path": str(payload_path),
                    "sha256": _sha256_bytes(payload_path.read_bytes()),
                }
                if payload_path.is_file()
                else None
            ),
            "sidecar": {
                "path": str(sidecar_path),
                "sha256": _sha256_bytes(sidecar_path.read_bytes()),
            },
            "extractor_status": sidecar.get("status", {}),
            "extractor_error": sidecar.get("error"),
            "extractor_warnings": sidecar.get("validation", {}).get(
                "warnings", []
            ),
            "comparison_basis": (
                "冻结源 HTML"
                if strategy == "simple_static"
                else "冻结源 HTML + soft-category.json"
            ),
            "observation": str(observation_path.relative_to(output_dir)),
            "source_candidate_count": len(candidates),
            "source_candidate_fragments": [
                record["fragment"] for record in source_candidate_records
            ],
            "source_unique_state_count": len(source_unique),
            "source_ambiguous_state_count": len(source_ambiguous),
            "payload_state_count": len(payload_groups),
            "missing_source_states": [
                [list(pair) for pair in key] for key in missing_source
            ],
            "extra_source_states": [
                [list(pair) for pair in key] for key in extra_source
            ],
            "comparisons": comparisons,
            "semantic_materialization_count": (
                semantic_materialization_count
            ),
            "fidelity_passed": fidelity_passed,
            "outcome": outcome,
        }
        product_reports.append(product_report)

        if spec.product_key in {
            "application-gateway",
            "cloud-services",
            "sql-database",
        }:
            mutation = _swap_mutation(
                product_key=spec.product_key,
                source_url=source_url,
                source=source_unique,
                payload=payload_groups,
            )
            if mutation is not None:
                mutation_checks.append(mutation)

    comparisons = [
        item
        for product in product_reports
        for item in product["comparisons"]
    ]
    browser_probe = (
        _read_json(browser_probe_path)
        if browser_probe_path is not None and browser_probe_path.is_file()
        else None
    )
    comparable_products = [
        product
        for product in product_reports
        if product["extractor_status"].get("execution") == "succeeded"
    ]
    comparable_fidelity_passed = (
        bool(comparable_products)
        and all(product["fidelity_passed"] for product in comparable_products)
        and bool(mutation_checks)
        and all(check["detected"] for check in mutation_checks)
    )
    report = {
        "schema_version": "1.1",
        "experiment": EXPERIMENT_NAME,
        "language": LANGUAGE,
        "method_reference": {
            "commit": "8d85cff",
            "experiment": "experiments/v0.5.0-independent-fidelity",
        },
        "inputs": {
            "extractor_output": str(extractor_output),
            "cms_html_semantic_materialization": {
                "algorithm_version": (
                    CMS_HTML_SEMANTIC_MATERIALIZATION_VERSION
                ),
                "icon_tick_replacement_text": ICON_TICK_TEXT,
                "implementation": "independent_experiment_projection",
            },
            "soft_category": {
                key: value
                for key, value in soft_evidence.items()
                if key != "row_indices"
            },
        },
        "summary": {
            "products": len(product_reports),
            "extractor_succeeded": sum(
                product["extractor_status"].get("execution") == "succeeded"
                for product in product_reports
            ),
            "extractor_failed": sum(
                product["extractor_status"].get("execution") != "succeeded"
                for product in product_reports
            ),
            "comparisons": len(comparisons),
            "raw_equal": sum(item["raw_equal"] for item in comparisons),
            "wire_equal": sum(item["wire_equal"] for item in comparisons),
            "source_raw_dom_equal": sum(
                item["source_raw_dom_equal"] for item in comparisons
            ),
            "dom_equal": sum(item["dom_equal"] for item in comparisons),
            "structure_equal": sum(
                item["structure_equal"] for item in comparisons
            ),
            "visible_text_equal": sum(
                item["visible_text_equal"] for item in comparisons
            ),
            "semantic_materializations": sum(
                item["semantic_materialization"]["transformation_count"]
                for item in comparisons
            ),
            "mutation_checks": len(mutation_checks),
            "mutation_detected": sum(
                check["detected"] for check in mutation_checks
            ),
            "source_candidates": sum(
                product["source_candidate_count"] for product in product_reports
            ),
        },
        "products": product_reports,
        "mutation_checks": mutation_checks,
        "browser_probe": browser_probe,
        "experiment_completed": True,
        "comparable_fidelity_passed": comparable_fidelity_passed,
        "full_extractor_capability_passed": all(
            product["extractor_status"].get("execution") == "succeeded"
            for product in product_reports
        ),
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(
        _render_markdown(report),
        encoding="utf-8",
    )
    (output_dir / "manual-review.html").write_text(
        _render_manual_review(report),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare v0.4.1 zh-cn frozen DOM fragments with CMS payloads"
        )
    )
    parser.add_argument(
        "--extractor-output",
        type=Path,
        required=True,
        help="Directory containing payloads/ and diagnostics/ from cli.py extract",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for report, observations, fragments, and diffs",
    )
    parser.add_argument(
        "--browser-probe",
        type=Path,
        help="Optional JSON evidence from a local frozen-page browser probe",
    )
    args = parser.parse_args()
    report = run(
        args.extractor_output.resolve(),
        args.output_dir.resolve(),
        browser_probe_path=(
            args.browser_probe.resolve() if args.browser_probe else None
        ),
    )
    summary = report["summary"]
    print(
        "products={products} extractor_succeeded={extractor_succeeded} "
        "comparisons={comparisons} raw_equal={raw_equal} "
        "dom_equal={dom_equal} fidelity_passed={fidelity}".format(
            **summary,
            fidelity=report["comparable_fidelity_passed"],
        )
    )
    print(f"report: {(args.output_dir.resolve() / 'report.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
