#!/usr/bin/env python3
"""Compare independently located zh-cn source fragments with CMS payloads.

This experiment deliberately does not import production extraction, strategy,
selection, or assembly code. Production payloads are generated beforehand by
the normal CLI and are treated as read-only comparison inputs here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Comment, NavigableString, Tag


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LANGUAGE = "zh-cn"
SOFT_CATEGORY_PATH = PROJECT_ROOT / "data/configs/soft-category.json"
SKIPPED_URL_PREFIXES = (
    "#",
    "mailto:",
    "tel:",
    "data:",
    "javascript:",
    "{base_url}",
)
SUPPORT_UI_SELECTORS = (
    "#content_feedback",
    ".content-feedback",
    ".select",
    ".left-navigation-select",
    ".bookmark",
    ".loader",
    ".tags",
    "select",
    "script",
    "style",
    "tags",
)


@dataclass(frozen=True)
class ProductSpec:
    product_key: str
    source_relative_path: str
    definition_relative_path: str
    payload_relative_path: str
    sidecar_relative_path: str
    content_field: str
    locator: str


PRODUCTS = (
    ProductSpec(
        "service-bus",
        "data/prod-html/zh-cn/pricing/service-bus.html",
        "data/configs/products/pricing/service-bus.json",
        "payloads/zh-cn/pricing/service-bus.json",
        "diagnostics/zh-cn/pricing/service-bus.sidecar.json",
        "baseContent",
        "simple",
    ),
    ProductSpec(
        "api-management",
        "data/prod-html/zh-cn/pricing/api-management.html",
        "data/configs/products/pricing/api-management.json",
        "payloads/zh-cn/pricing/api-management.json",
        "diagnostics/zh-cn/pricing/api-management.sidecar.json",
        "contentGroups[].content",
        "region",
    ),
    ProductSpec(
        "app-service",
        "data/prod-html/zh-cn/pricing/app-service.html",
        "data/configs/products/pricing/app-service.json",
        "payloads/zh-cn/pricing/app-service.json",
        "diagnostics/zh-cn/pricing/app-service.sidecar.json",
        "contentGroups[].content",
        "complex",
    ),
    ProductSpec(
        "sla-virtual-machines",
        "data/prod-html/zh-cn/SupportArticles/SLA/sla-virtual-machines.html",
        "data/configs/products/support-articles/sla-virtual-machines.json",
        "payloads/zh-cn/SupportArticles/SLA/sla-virtual-machines.json",
        "diagnostics/zh-cn/SupportArticles/SLA/sla-virtual-machines.sidecar.json",
        "mainContent",
        "support",
    ),
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected one JSON object: {path}")
    return value


def _clone_tag(tag: Tag) -> Tag:
    clone = BeautifulSoup(str(tag), "html.parser").find()
    if not isinstance(clone, Tag):
        raise ValueError("Unable to clone source DOM node")
    return clone


def _text(tag: Tag | None) -> str:
    return " ".join(tag.get_text(" ", strip=True).split()) if tag else ""


def _compact_html(value: str) -> str:
    value = re.sub(r"\n+", " ", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"<div>\s*</div>", "", value)
    value = re.sub(r">\s+<", "><", value)
    return value.strip()


def _apply_pricing_asset_paths(soup: BeautifulSoup) -> None:
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
                f"{match.group(1)}{{base_url}}{match.group(2)}{match.group(3)}"
            ),
            str(element["data-config"]),
        )


def _rewrite_support_url(value: str, source_url: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if not normalized or normalized.lower().startswith(SKIPPED_URL_PREFIXES):
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
        return "{base_url}" + (
            suffix if suffix.startswith("/") else f"/{suffix}"
        )
    return normalized if not parsed.scheme else resolved


def _rewrite_support_fragment(fragment: Tag, source_url: str) -> None:
    style_url = re.compile(
        r"url\(\s*([\"']?)(.*?)\1\s*\)",
        flags=re.IGNORECASE,
    )
    for tag in fragment.find_all(True):
        for attribute in ("href", "src"):
            if tag.has_attr(attribute):
                tag[attribute] = _rewrite_support_url(
                    str(tag[attribute]), source_url
                )
        if tag.has_attr("style"):
            tag["style"] = style_url.sub(
                lambda match: (
                    f"url({match.group(1)}"
                    f"{_rewrite_support_url(match.group(2), source_url)}"
                    f"{match.group(1)})"
                ),
                str(tag["style"]),
            )


def _pricing_soup(source_path: Path) -> BeautifulSoup:
    soup = BeautifulSoup(source_path.read_text(encoding="utf-8"), "html.parser")
    _apply_pricing_asset_paths(soup)
    return soup


def _selector_root(soup: BeautifulSoup) -> Tag:
    roots = soup.select("div.technical-azure-selector.pricing-detail-tab")
    if len(roots) != 1:
        raise ValueError(f"Expected one pricing selector, found {len(roots)}")
    return roots[0]


def _desktop_control(
    root: Tag,
    *,
    container_class: str,
    select_id: str,
    value_from_href: bool,
) -> dict[str, Any]:
    containers = root.select(f"div.dropdown-container.{container_class}")
    if len(containers) != 1:
        raise ValueError(
            f"Expected one {container_class}, found {len(containers)}"
        )
    container = containers[0]
    desktop_links = container.select(
        ".dropdown-box.os-tab-nav .tab-items a[data-href]"
    )
    mobile = container.select_one(f"select#{select_id}")
    if not desktop_links or not isinstance(mobile, Tag):
        raise ValueError(f"Incomplete responsive control: {select_id}")
    mobile_by_href = {
        str(option.get("data-href") or "").strip(): option
        for option in mobile.find_all("option", recursive=False)
    }
    options: list[dict[str, Any]] = []
    active_hrefs: list[str] = []
    for link in desktop_links:
        href = str(link.get("data-href") or "").strip()
        if href not in mobile_by_href:
            raise ValueError(f"Desktop/mobile target mismatch: {href}")
        option = mobile_by_href[href]
        parent = link.find_parent("li")
        active = bool(
            isinstance(parent, Tag)
            and {"active", "selected", "selected-item"}.intersection(
                parent.get("class", [])
            )
        )
        if active:
            active_hrefs.append(href)
        options.append({
            "value": (
                href.removeprefix("#")
                if value_from_href
                else str(option.get("value") or "").strip()
            ),
            "label": _text(link),
            "href": href,
            "active": active,
        })
    if set(mobile_by_href) != {item["href"] for item in options}:
        raise ValueError(f"Desktop/mobile option domain mismatch: {select_id}")
    if len(active_hrefs) != 1:
        raise ValueError(
            f"Desktop control must declare one default: {select_id}"
        )
    summary = _text(container.select_one(".selected-item"))
    default = next(item for item in options if item["href"] == active_hrefs[0])
    if summary and summary != default["label"]:
        raise ValueError(
            f"Desktop default summary disagrees for {select_id}: {summary!r}"
        )
    mobile_defaults = [
        href
        for href, option in mobile_by_href.items()
        if option.has_attr("selected")
    ]
    ordered = [default, *(item for item in options if item is not default)]
    return {
        "default": default,
        "options": ordered,
        "mobile_default_hrefs": mobile_defaults,
        "selected_item_label": summary,
    }


def _control_observation(soup: BeautifulSoup) -> dict[str, Any]:
    root = _selector_root(soup)
    result: dict[str, Any] = {}
    for name, container_class, select_id, value_from_href in (
        ("software", "software-kind-container", "software-box", False),
        ("region", "region-container", "region-box", True),
    ):
        control = _desktop_control(
            root,
            container_class=container_class,
            select_id=select_id,
            value_from_href=value_from_href,
        )
        options = []
        for option in control["options"]:
            target_id = str(option["href"]).removeprefix("#")
            matches = soup.find_all(id=target_id)
            direct_panels = [
                tag
                for tag in matches
                if isinstance(tag, Tag)
                and tag.name == "div"
                and "tab-panel" in tag.get("class", [])
            ]
            options.append({
                **option,
                "target_tags": [tag.name for tag in matches],
                "direct_content_panel": len(direct_panels) == 1,
            })
        result[name] = {
            **control,
            "options": options,
            "all_options_point_to_content_panels": all(
                option["direct_content_panel"] for option in options
            ),
        }
    return result


def _load_soft_category() -> dict[tuple[str, str], tuple[str, ...]]:
    raw = json.loads(SOFT_CATEGORY_PATH.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        raise ValueError("soft-category.json must be an array")
    result: dict[tuple[str, str], tuple[str, ...]] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        key = (str(row.get("os") or "").strip(), str(row.get("region") or "").strip())
        if not all(key):
            continue
        if key in result:
            raise ValueError(f"Duplicate soft-category state: {key!r}")
        table_ids = tuple(
            dict.fromkeys(
                str(value).strip().removeprefix("#")
                for value in row.get("tableIDs", [])
                if str(value).strip()
            )
        )
        result[key] = table_ids
    return result


def _remove_configured_tables(scope: Tag, table_ids: Iterable[str]) -> list[str]:
    removed: list[str] = []
    for table_id in table_ids:
        matches = [
            tag
            for tag in scope.find_all(id=table_id)
            if isinstance(tag, Tag) and tag.name == "table"
        ]
        if not matches:
            continue
        if len(matches) != 1:
            raise ValueError(f"Ambiguous removable table: {table_id}")
        table = matches[0]
        target = table
        for parent in table.parents:
            if parent is scope:
                break
            if isinstance(parent, Tag) and "scroll-table" in parent.get(
                "class", []
            ):
                owned_tables = parent.find_all("table")
                if owned_tables != [table]:
                    raise ValueError(
                        f"Table wrapper owns multiple tables: {table_id}"
                    )
                target = parent
                break
        target.decompose()
        removed.append(table_id)
    return removed


def _criteria_key(group: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    criteria = json.loads(str(group.get("filterCriteriaJson") or "[]"))
    if not isinstance(criteria, list):
        raise ValueError("filterCriteriaJson must be an array")
    return tuple(
        (
            str(item.get("filterKey") or ""),
            str(item.get("matchValues") or ""),
        )
        for item in criteria
        if isinstance(item, dict)
    )


def _simple_candidates(source_path: Path) -> dict[tuple[tuple[str, str], ...], str]:
    soup = _pricing_soup(source_path)
    matches = soup.select("div.technical-azure-selector.tab-control-selector")
    if len(matches) != 1:
        raise ValueError(f"Expected one simple content root, found {len(matches)}")
    return {(): _compact_html(str(matches[0]))}


def _region_candidates(
    source_path: Path,
    soft_category: dict[tuple[str, str], tuple[str, ...]],
) -> tuple[
    dict[tuple[tuple[str, str], ...], str],
    dict[str, Any],
]:
    soup = _pricing_soup(source_path)
    observation = _control_observation(soup)
    regions = observation["region"]["options"]
    software = observation["software"]["options"]
    if len(software) != 1:
        raise ValueError("Region page must have one internal software scope")
    content = soup.select_one("div.tab-content")
    if not isinstance(content, Tag):
        raise ValueError("Region page has no tab-content root")
    software_value = str(software[0]["value"])
    result: dict[tuple[tuple[str, str], ...], str] = {}
    removals: dict[str, list[str]] = {}
    for region in regions:
        region_value = str(region["value"])
        clone = _clone_tag(content)
        removed = _remove_configured_tables(
            clone,
            soft_category.get((software_value, region_value), ()),
        )
        result[(("region", region_value),)] = _compact_html(str(clone))
        removals[region_value] = removed
    observation["configuration_assisted_removals"] = removals
    return result, observation


def _complex_candidates(
    source_path: Path,
    soft_category: dict[tuple[str, str], tuple[str, ...]],
) -> tuple[
    dict[tuple[tuple[str, str], ...], str],
    dict[str, Any],
]:
    soup = _pricing_soup(source_path)
    observation = _control_observation(soup)
    regions = observation["region"]["options"]
    software_options = observation["software"]["options"]
    result: dict[tuple[tuple[str, str], ...], str] = {}
    removals: dict[str, list[str]] = {}
    for region in regions:
        region_value = str(region["value"])
        for software in software_options:
            software_value = str(software["value"])
            panel_id = str(software["href"]).removeprefix("#")
            panel = soup.find(id=panel_id)
            if not isinstance(panel, Tag):
                raise ValueError(f"Missing software panel: {panel_id}")
            clone = _clone_tag(panel)
            removed = _remove_configured_tables(
                clone,
                soft_category.get((software_value, region_value), ()),
            )
            key = (
                ("region", region_value),
                ("software", software_value),
            )
            result[key] = _compact_html(str(clone))
            removals[f"{region_value}|{software_value}"] = removed
    observation["configuration_assisted_removals"] = removals
    return result, observation


def _support_candidates(
    source_path: Path,
    source_url: str,
) -> dict[tuple[tuple[str, str], ...], str]:
    soup = BeautifulSoup(source_path.read_text(encoding="utf-8"), "html.parser")
    content = soup.select_one("div.pure-content") or soup.body
    if not isinstance(content, Tag):
        raise ValueError("Support page has no content root")
    first_h2 = content.find("h2")
    if not isinstance(first_h2, Tag):
        raise ValueError("Support page has no h2 content boundary")
    wrapper_soup = BeautifulSoup("<div></div>", "html.parser")
    wrapper = wrapper_soup.div
    if not isinstance(wrapper, Tag):
        raise ValueError("Unable to create support content wrapper")
    current: Any = first_h2
    while current is not None:
        if isinstance(current, Tag):
            wrapper.append(_clone_tag(current))
        current = current.next_sibling
    for selector in SUPPORT_UI_SELECTORS:
        for element in wrapper.select(selector):
            element.decompose()
    _rewrite_support_fragment(wrapper, source_url)
    return {(): wrapper.decode_contents().strip()}


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


def _canonical_node(node: Any, source_url: str) -> Any:
    if isinstance(node, Comment):
        return None
    if isinstance(node, NavigableString):
        value = " ".join(str(node).replace("\xa0", " ").split())
        return ("#text", value) if value else None
    if not isinstance(node, Tag):
        return None
    attributes: list[tuple[str, Any]] = []
    for key, raw in sorted(node.attrs.items()):
        if isinstance(raw, list):
            value: Any = sorted(str(item) for item in raw) if key == "class" else [
                str(item) for item in raw
            ]
        else:
            value = str(raw)
            if key in {"href", "src", "poster"}:
                value = _normalize_comparison_url(value, source_url)
            else:
                value = value.replace("{base_url}", "")
        attributes.append((key, value))
    children = [
        canonical
        for child in node.children
        if (canonical := _canonical_node(child, source_url)) is not None
    ]
    return (node.name, attributes, children)


def _canonical_html(value: str, source_url: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    nodes = [
        canonical
        for child in soup.contents
        if (canonical := _canonical_node(child, source_url)) is not None
    ]
    return json.dumps(nodes, ensure_ascii=False, separators=(",", ":"))


def _fragment_inventory(value: str) -> dict[str, Any]:
    soup = BeautifulSoup(value, "html.parser")
    tags = Counter(tag.name for tag in soup.find_all(True))
    return {
        "visible_text_sha256": _sha256_text(_text(soup)),
        "tag_counts": dict(sorted(tags.items())),
        "table_ids": [
            str(table.get("id") or "") for table in soup.find_all("table")
        ],
    }


def _safe_key(key: tuple[tuple[str, str], ...]) -> str:
    if not key:
        return "page"
    value = "--".join(f"{name}-{item}" for name, item in key)
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


def _payload_fragments(
    payload: dict[str, Any],
    field: str,
) -> dict[tuple[tuple[str, str], ...], str]:
    if field == "contentGroups[].content":
        groups = payload.get("contentGroups")
        if not isinstance(groups, list):
            raise ValueError("Payload contentGroups must be an array")
        return {
            _criteria_key(group): str(group.get("content") or "")
            for group in groups
            if isinstance(group, dict)
        }
    return {(): str(payload.get(field) or "")}


def _compare_fragments(
    *,
    product_key: str,
    source_url: str,
    source_fragments: dict[tuple[tuple[str, str], ...], str],
    payload_fragments: dict[tuple[tuple[str, str], ...], str],
    fragment_root: Path,
) -> tuple[list[dict[str, Any]], list[list[list[str]]], list[list[list[str]]]]:
    source_keys = set(source_fragments)
    payload_keys = set(payload_fragments)
    missing = [list(map(list, key)) for key in sorted(payload_keys - source_keys)]
    extra = [list(map(list, key)) for key in sorted(source_keys - payload_keys)]
    comparisons: list[dict[str, Any]] = []
    product_root = fragment_root / product_key
    product_root.mkdir(parents=True, exist_ok=True)
    for key in sorted(source_keys & payload_keys):
        source_html = source_fragments[key]
        payload_html = payload_fragments[key]
        source_canonical = _canonical_html(source_html, source_url)
        payload_canonical = _canonical_html(payload_html, source_url)
        name = _safe_key(key)
        source_file = product_root / f"{name}.source.html"
        payload_file = product_root / f"{name}.payload.html"
        source_file.write_text(source_html, encoding="utf-8")
        payload_file.write_text(payload_html, encoding="utf-8")
        comparisons.append({
            "state": [list(item) for item in key],
            "raw_equal": source_html == payload_html,
            "dom_equal": source_canonical == payload_canonical,
            "source_length": len(source_html),
            "payload_length": len(payload_html),
            "source_sha256": _sha256_text(source_html),
            "payload_sha256": _sha256_text(payload_html),
            "source_dom_sha256": _sha256_text(source_canonical),
            "payload_dom_sha256": _sha256_text(payload_canonical),
            "source_inventory": _fragment_inventory(source_html),
            "payload_inventory": _fragment_inventory(payload_html),
            "source_fragment": str(source_file.relative_to(fragment_root.parent)),
            "payload_fragment": str(payload_file.relative_to(fragment_root.parent)),
        })
    return comparisons, missing, extra


def _swap_state_mutation(
    *,
    source_url: str,
    source_fragments: dict[tuple[tuple[str, str], ...], str],
    payload_fragments: dict[tuple[tuple[str, str], ...], str],
    first: tuple[tuple[str, str], ...],
    second: tuple[tuple[str, str], ...],
) -> dict[str, Any]:
    if first not in source_fragments or second not in source_fragments:
        raise ValueError("Mutation states are absent from independent source results")
    if first not in payload_fragments or second not in payload_fragments:
        raise ValueError("Mutation states are absent from the CMS payload")
    mutated = dict(payload_fragments)
    mutated[first], mutated[second] = mutated[second], mutated[first]
    detected_states = [
        key
        for key in (first, second)
        if _canonical_html(source_fragments[key], source_url)
        != _canonical_html(mutated[key], source_url)
    ]
    return {
        "kind": "swap_state_content",
        "description": (
            "Swap two persisted region fragments without changing their "
            "filter identities."
        ),
        "mutated_states": [
            [list(item) for item in key] for key in (first, second)
        ],
        "detected_states": [
            [list(item) for item in key] for key in detected_states
        ],
        "detected": set(detected_states) == {first, second},
    }


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# 中文源 HTML 与 CMS payload 对比实验",
        "",
        (
            "本实验只使用仓库中的中文冻结 HTML。payload 由当前 CLI "
            "预先生成；对比程序不调用生产抽取策略或内容组装代码。"
        ),
        "",
        "## 总结",
        "",
        (
            f"- 产品：{summary['products']} 个，当前抽取成功："
            f"{summary['extractor_succeeded']} 个。"
        ),
        f"- 对比片段：{summary['comparisons']} 个。",
        f"- 原始字符串一致：{summary['raw_equal']} 个。",
        f"- DOM 归一后内容一致：{summary['dom_equal']} 个。",
        (
            f"- 受控错状态检查：{summary['mutation_detected']}/"
            f"{summary['mutation_checks']} 被发现。"
        ),
        f"- 总体结果：{'通过' if report['passed'] else '存在差异'}。",
        "",
        "## 产品结果",
        "",
        (
            "| 产品 | 当前抽取 | 对比数 | 原始一致 | DOM 一致 | "
            "定位依据 |"
        ),
        "|---|---:|---:|---:|---:|---|",
    ]
    for product in report["products"]:
        comparisons = product["comparisons"]
        lines.append(
            "| {product} | {execution} | {count} | {raw} | {dom} | {basis} |".format(
                product=product["product_key"],
                execution=product["extractor_status"]["execution"],
                count=len(comparisons),
                raw=sum(item["raw_equal"] for item in comparisons),
                dom=sum(item["dom_equal"] for item in comparisons),
                basis=product["comparison_basis"],
            )
        )
    lines.extend([
        "",
        "## DOM 可直接证明的关系",
        "",
        "- `service-bus`：页面主体可以直接定位，比较 `baseContent`。",
        (
            "- `sla-virtual-machines`：首个 `h2` 到文章结尾可以直接定位，"
            "比较 `mainContent`。"
        ),
        (
            "- `api-management`：地区列表可直接读取，但地区链接只指向"
            "按钮，不指向内容面板。"
        ),
        (
            "- `app-service`：Windows/Linux 链接可直接定位内容面板；"
            "地区链接只指向按钮。"
        ),
        (
            "- 因此两个地区型页面的逐地区内容比较明确使用了 "
            "`soft-category.json`。"
        ),
        "",
        "## 受控错误检查",
        "",
    ])
    for check in report["mutation_checks"]:
        lines.append(
            "- {product}：交换两个地区状态的内容，{result}。".format(
                product=check["product_key"],
                result=(
                    "两个错状态均被发现"
                    if check["detected"]
                    else "未完整发现"
                ),
            )
        )
    lines.extend([
        "",
        "## 逐项结果",
        "",
    ])
    for product in report["products"]:
        lines.append(f"### {product['product_key']}")
        lines.append("")
        for item in product["comparisons"]:
            state = ", ".join(
                f"{key}={value}" for key, value in item["state"]
            ) or "页面主体"
            lines.append(
                f"- {state}：原始={'一致' if item['raw_equal'] else '不同'}；"
                f"DOM={'一致' if item['dom_equal'] else '不同'}。"
            )
        if product["missing_source_states"]:
            lines.append(
                "- payload 中有 "
                f"{len(product['missing_source_states'])} 个状态无法从源依据定位。"
            )
        if product["extra_source_states"]:
            lines.append(
                "- 源依据多出 "
                f"{len(product['extra_source_states'])} 个 payload 未承载状态。"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def run(extractor_output: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fragment_root = output_dir / "fragments"
    fragment_root.mkdir(parents=True, exist_ok=True)
    soft_category = _load_soft_category()
    soft_category_bytes = SOFT_CATEGORY_PATH.read_bytes()
    product_reports: list[dict[str, Any]] = []
    mutation_checks: list[dict[str, Any]] = []

    for spec in PRODUCTS:
        source_path = PROJECT_ROOT / spec.source_relative_path
        definition = _read_json(PROJECT_ROOT / spec.definition_relative_path)
        source_url = str(definition["sources"][LANGUAGE]["url"])
        payload_path = extractor_output / spec.payload_relative_path
        sidecar_path = extractor_output / spec.sidecar_relative_path
        payload = _read_json(payload_path)
        sidecar = _read_json(sidecar_path)
        observation: dict[str, Any] | None = None
        if spec.locator == "simple":
            source_fragments = _simple_candidates(source_path)
            basis = "仅源 HTML"
        elif spec.locator == "region":
            source_fragments, observation = _region_candidates(
                source_path, soft_category
            )
            basis = "源 HTML + soft-category.json"
        elif spec.locator == "complex":
            source_fragments, observation = _complex_candidates(
                source_path, soft_category
            )
            basis = "源 HTML + soft-category.json"
        elif spec.locator == "support":
            source_fragments = _support_candidates(source_path, source_url)
            basis = "仅源 HTML（含允许的站内链接改写）"
        else:
            raise ValueError(f"Unknown locator: {spec.locator}")
        payload_fragments = _payload_fragments(payload, spec.content_field)
        comparisons, missing, extra = _compare_fragments(
            product_key=spec.product_key,
            source_url=source_url,
            source_fragments=source_fragments,
            payload_fragments=payload_fragments,
            fragment_root=fragment_root,
        )
        if spec.product_key == "api-management":
            mutation_checks.append({
                "product_key": spec.product_key,
                **_swap_state_mutation(
                    source_url=source_url,
                    source_fragments=source_fragments,
                    payload_fragments=payload_fragments,
                    first=(("region", "east-china"),),
                    second=(("region", "east-china2"),),
                ),
            })
        product_reports.append({
            "product_key": spec.product_key,
            "language": LANGUAGE,
            "source": {
                "path": spec.source_relative_path,
                "sha256": _sha256_bytes(source_path.read_bytes()),
            },
            "payload": {
                "path": str(payload_path),
                "sha256": _sha256_bytes(payload_path.read_bytes()),
                "field": spec.content_field,
            },
            "extractor_status": sidecar.get("status", {}),
            "extractor_warnings": sidecar.get("validation", {}).get(
                "warnings", []
            ),
            "comparison_basis": basis,
            "dom_observation": observation,
            "comparisons": comparisons,
            "missing_source_states": missing,
            "extra_source_states": extra,
            "passed": (
                not missing
                and not extra
                and bool(comparisons)
                and all(item["dom_equal"] for item in comparisons)
            ),
        })

    comparisons = [
        item
        for product in product_reports
        for item in product["comparisons"]
    ]
    report = {
        "schema_version": "0.1",
        "experiment": "v0.5.0-independent-fidelity-zh-cn",
        "language": LANGUAGE,
        "inputs": {
            "extractor_output": str(extractor_output),
            "soft_category": {
                "path": str(SOFT_CATEGORY_PATH.relative_to(PROJECT_ROOT)),
                "sha256": _sha256_bytes(soft_category_bytes),
            },
        },
        "summary": {
            "products": len(product_reports),
            "extractor_succeeded": sum(
                product["extractor_status"].get("execution") == "succeeded"
                for product in product_reports
            ),
            "comparisons": len(comparisons),
            "raw_equal": sum(item["raw_equal"] for item in comparisons),
            "dom_equal": sum(item["dom_equal"] for item in comparisons),
            "mutation_checks": len(mutation_checks),
            "mutation_detected": sum(
                check["detected"] for check in mutation_checks
            ),
        },
        "products": product_reports,
        "mutation_checks": mutation_checks,
        "passed": (
            all(product["passed"] for product in product_reports)
            and bool(mutation_checks)
            and all(check["detected"] for check in mutation_checks)
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
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare zh-cn source DOM fragments with CMS payloads"
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
        help="Directory for report and compared fragments",
    )
    args = parser.parse_args()
    report = run(args.extractor_output.resolve(), args.output_dir.resolve())
    summary = report["summary"]
    print(
        "products={products} comparisons={comparisons} raw_equal={raw_equal} "
        "dom_equal={dom_equal} passed={passed}".format(
            **summary,
            passed=report["passed"],
        )
    )
    print(f"report: {(args.output_dir.resolve() / 'report.md')}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
