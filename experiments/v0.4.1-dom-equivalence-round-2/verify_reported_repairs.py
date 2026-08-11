#!/usr/bin/env python3
"""Supplement the frozen round-two oracle for three unsupported page shapes.

The first-round comparison algorithm remains unchanged.  This program reads
its saved, independent source fragments for Azure Monitor and inspects the
frozen source HTML directly for Azure Migrate and Event Hubs.  It deliberately
does not import production extraction, reachability, cleaning, or payload
assembly code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LANGUAGE = "zh-cn"
PRODUCTS = ("monitor", "azure-migrate", "event-hubs")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected one JSON object: {path}")
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compact_html(value: str) -> str:
    value = re.sub(r"\n+", " ", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"<div>\s*</div>", "", value)
    value = re.sub(r">\s+<", "><", value)
    return value.strip()


def _text(node: Tag | BeautifulSoup | None) -> str:
    if node is None:
        return ""
    return " ".join(node.get_text(" ", strip=True).split())


def _apply_asset_paths(soup: BeautifulSoup) -> None:
    """Apply the public fragment path contract without production code."""

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


def _source_soup(product_key: str) -> tuple[Path, BeautifulSoup]:
    path = (
        PROJECT_ROOT
        / "data"
        / "prod-html"
        / LANGUAGE
        / "pricing"
        / f"{product_key}.html"
    )
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    _apply_asset_paths(soup)
    return path, soup


def _criteria_key(group: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    raw = json.loads(str(group.get("filterCriteriaJson") or "[]"))
    if not isinstance(raw, list):
        raise ValueError("filterCriteriaJson must be an array")
    key = tuple(
        (
            str(item.get("filterKey") or ""),
            str(item.get("matchValues") or ""),
        )
        for item in raw
        if isinstance(item, dict)
    )
    if not key or any(not all(pair) for pair in key):
        raise ValueError(f"Incomplete content-group criteria: {key!r}")
    return key


def _payload_groups(
    payload: dict[str, Any],
) -> dict[tuple[tuple[str, str], ...], dict[str, Any]]:
    groups: dict[tuple[tuple[str, str], ...], dict[str, Any]] = {}
    for group in payload.get("contentGroups", []):
        if not isinstance(group, dict):
            raise ValueError("contentGroups must contain objects")
        key = _criteria_key(group)
        if key in groups:
            raise ValueError(f"Duplicate payload state: {key!r}")
        groups[key] = group
    return groups


def _one(items: list[Any], description: str) -> Any:
    if len(items) != 1:
        raise ValueError(
            f"Expected exactly one {description}; observed {len(items)}"
        )
    return items[0]


def _monitor_verification(
    extractor_output: Path,
    frozen_comparison: Path,
    frozen_report: dict[str, Any],
) -> dict[str, Any]:
    source_path, soup = _source_soup("monitor")
    payload_path = (
        extractor_output / "payloads/zh-cn/pricing/monitor.json"
    )
    payload = _read_json(payload_path)
    payload_groups = _payload_groups(payload)

    selector = _one(
        soup.select("div.technical-azure-selector.tab-control-selector"),
        "Monitor static selector",
    )
    software_panel = _one(
        [
            panel
            for panel in selector.find_all(
                "div", class_="tab-panel", recursive=False
            )
            if str(panel.get("id") or "") == "tabContent1"
        ],
        "Monitor software panel",
    )
    content_root = _one(
        software_panel.find_all(
            "div", class_="tab-content", recursive=False
        ),
        "Monitor category content root",
    )
    pricing_heading = _one(
        [
            heading
            for heading in content_root.find_all("h2", recursive=False)
            if _text(heading) == "定价详细信息"
        ],
        "Monitor persistent pricing heading",
    )
    category_panels = {
        str(panel.get("id") or ""): panel
        for panel in content_root.find_all(
            "div", class_="tab-panel", recursive=False
        )
        if str(panel.get("id") or "")
    }
    empty_panel_ids = sorted(
        panel_id
        for panel_id, panel in category_panels.items()
        if not _text(panel)
        and panel.find(["table", "img", "video", "audio", "iframe"])
        is None
    )
    if empty_panel_ids not in ([], ["tabContent1-6"]):
        raise ValueError(
            "Monitor may have only the previously reported empty source "
            "category panel: "
            f"{empty_panel_ids!r}"
        )

    product_report = _one(
        [
            item
            for item in frozen_report.get("products", [])
            if item.get("product_key") == "monitor"
        ],
        "Monitor frozen comparison result",
    )
    comparisons = product_report.get("comparisons", [])
    if len(comparisons) != 30 or len(payload_groups) != 30:
        raise ValueError(
            "Monitor must have 30 comparable non-empty region/category states"
        )

    heading_html = _compact_html(str(pricing_heading))
    state_results: list[dict[str, Any]] = []
    compared_keys: set[tuple[tuple[str, str], ...]] = set()
    for comparison in comparisons:
        key = tuple(tuple(pair) for pair in comparison.get("state", []))
        if key in compared_keys:
            raise ValueError(f"Duplicate Monitor comparison state: {key!r}")
        compared_keys.add(key)
        group = payload_groups.get(key)
        if group is None:
            raise ValueError(f"Missing Monitor payload state: {key!r}")

        fragment_name = (
            comparison.get("expected_source_fragment")
            or comparison.get("source_fragment")
        )
        fragment_path = frozen_comparison / str(fragment_name)
        source_fragment = fragment_path.read_text(encoding="utf-8")
        if _sha256_text(source_fragment) != comparison["expected_source"][
            "sha256"
        ]:
            raise ValueError(
                "Saved Monitor source fragment no longer matches the frozen "
                f"oracle report: {fragment_path}"
            )
        expected = _compact_html(heading_html + source_fragment)
        actual = str(group.get("content") or "")
        state_results.append({
            "state": [list(pair) for pair in key],
            "source_fragment": str(fragment_path),
            "expected_sha256": _sha256_text(expected),
            "payload_sha256": _sha256_text(actual),
            "exact_equal": expected == actual,
        })

    expected_empty_states = {
        (
            ("region", dict(key)["region"]),
            ("category", panel_id),
        )
        for panel_id in empty_panel_ids
        for key in payload_groups
    }
    frozen_empty_states = {
        tuple(tuple(pair) for pair in state)
        for state in product_report.get("extra_source_states", [])
    }
    if frozen_empty_states != expected_empty_states:
        raise ValueError(
            "Monitor frozen-only states must be the empty category projected "
            "once per region"
        )

    return {
        "product_key": "monitor",
        "source": str(source_path),
        "source_sha256": _sha256_file(source_path),
        "payload": str(payload_path),
        "payload_sha256": _sha256_file(payload_path),
        "qualification": (
            "The frozen oracle source panel plus the persistent direct pricing "
            "heading is the complete payload fragment; the current source "
            + (
                "still contains the previously reported empty category panel."
                if empty_panel_ids
                else "no longer contains the previously reported empty category panel."
            )
        ),
        "regions": sorted({dict(key)["region"] for key in payload_groups}),
        "non_empty_category_ids": sorted(
            set(category_panels) - set(empty_panel_ids)
        ),
        "suppressed_empty_category_ids": empty_panel_ids,
        "state_count": len(state_results),
        "exact_equal_count": sum(
            item["exact_equal"] for item in state_results
        ),
        "states": state_results,
        "passed": all(item["exact_equal"] for item in state_results),
    }


def _azure_migrate_verification(extractor_output: Path) -> dict[str, Any]:
    source_path, soup = _source_soup("azure-migrate")
    payload_path = (
        extractor_output / "payloads/zh-cn/pricing/azure-migrate.json"
    )
    payload = _read_json(payload_path)

    pricing_heading = _one(
        [
            heading
            for heading in soup.find_all("h2")
            if _text(heading) == "定价详细信息"
        ],
        "Azure Migrate pricing heading",
    )
    following_tags = [
        sibling
        for sibling in pricing_heading.next_siblings
        if isinstance(sibling, Tag)
    ]
    if (
        len(following_tags) < 2
        or following_tags[0].name != "h3"
        or following_tags[1].name != "div"
        or "tab-content" not in following_tags[1].get("class", [])
    ):
        raise ValueError(
            "Azure Migrate pricing boundary must be h2 + h3 + tab-content"
        )
    source_nodes = [pricing_heading, following_tags[0], following_tags[1]]
    expected = _compact_html("".join(str(node) for node in source_nodes))
    actual = str(payload.get("baseContent") or "")
    table_count = len(
        BeautifulSoup(expected, "html.parser").find_all("table")
    )
    return {
        "product_key": "azure-migrate",
        "source": str(source_path),
        "source_sha256": _sha256_file(source_path),
        "payload": str(payload_path),
        "payload_sha256": _sha256_file(payload_path),
        "qualification": (
            "The unique root pricing heading and its adjacent h3 and "
            "tab-content form the independently proven Simple body."
        ),
        "source_node_sequence": [node.name for node in source_nodes],
        "table_count": table_count,
        "expected_sha256": _sha256_text(expected),
        "payload_sha256_fragment": _sha256_text(actual),
        "state_count": 1,
        "exact_equal_count": int(expected == actual),
        "passed": expected == actual and table_count == 1,
    }


def _event_hubs_verification(extractor_output: Path) -> dict[str, Any]:
    source_path, soup = _source_soup("event-hubs")
    payload_path = (
        extractor_output / "payloads/zh-cn/pricing/event-hubs.json"
    )
    payload = _read_json(payload_path)
    payload_groups = _payload_groups(payload)

    selector = _one(
        soup.select("div.technical-azure-selector.pricing-detail-tab"),
        "Event Hubs pricing selector",
    )
    static_content = _one(
        selector.find_all(
            "div", class_="tab-control-container", recursive=False
        ),
        "Event Hubs direct static content container",
    )
    expected = _compact_html(str(static_content))

    mobile = _one(selector.select("select#region-box"), "Event Hubs region")
    mobile_options = mobile.find_all("option", recursive=False)
    mobile_regions = [
        str(option.get("value") or "").strip()
        for option in mobile_options
    ]
    mobile_targets = [
        str(option.get("data-href") or "").strip()
        for option in mobile_options
    ]
    if (
        len(mobile_regions) != 6
        or len(set(mobile_regions)) != 6
        or any(not value for value in mobile_regions + mobile_targets)
    ):
        raise ValueError("Event Hubs must expose six unique mobile regions")

    payload_regions = {
        dict(key)["region"]
        for key in payload_groups
        if set(dict(key)) == {"region"}
    }
    if payload_regions != set(mobile_regions) or len(payload_groups) != 6:
        raise ValueError(
            "Event Hubs payload region domain must equal the mobile source "
            "control"
        )

    software = _one(
        selector.select("select#software-box > option"),
        "Event Hubs hidden software option",
    )
    soft_category_path = PROJECT_ROOT / "data/configs/soft-category.json"
    soft_category = json.loads(
        soft_category_path.read_text(encoding="utf-8-sig")
    )
    product_projection_rows = [
        row
        for row in soft_category
        if isinstance(row, dict) and row.get("os") == "event-hubs"
    ]
    if product_projection_rows:
        raise ValueError(
            "Event Hubs unexpectedly has product-specific soft-category rows"
        )

    state_results = []
    for key, group in sorted(payload_groups.items()):
        actual = str(group.get("content") or "")
        state_results.append({
            "state": [list(pair) for pair in key],
            "expected_sha256": _sha256_text(expected),
            "payload_sha256": _sha256_text(actual),
            "exact_equal": expected == actual,
        })
    table_count = len(
        BeautifulSoup(expected, "html.parser").find_all("table")
    )
    return {
        "product_key": "event-hubs",
        "source": str(source_path),
        "source_sha256": _sha256_file(source_path),
        "payload": str(payload_path),
        "payload_sha256": _sha256_file(payload_path),
        "qualification": (
            "The unique direct id-less static content container is shared by "
            "the six independently observed mobile region states."
        ),
        "mobile_regions": mobile_regions,
        "mobile_targets": mobile_targets,
        "hidden_software_raw_value": str(software.get("value") or ""),
        "hidden_software_label": _text(software),
        "soft_category_product_row_count": len(product_projection_rows),
        "table_count_per_state": table_count,
        "state_count": len(state_results),
        "exact_equal_count": sum(
            item["exact_equal"] for item in state_results
        ),
        "states": state_results,
        "passed": (
            table_count >= 1
            and all(item["exact_equal"] for item in state_results)
        ),
    }


def _render_markdown(report: dict[str, Any]) -> str:
    products = report["products"]
    rows = [
        "| 产品 | 补充状态 | 精确一致 | 结果 |",
        "|---|---:|---:|---|",
    ]
    for product in products:
        rows.append(
            "| `{}` | {} | {}/{} | {} |".format(
                product["product_key"],
                product["state_count"],
                product["exact_equal_count"],
                product["state_count"],
                "通过" if product["passed"] else "失败",
            )
        )
    details: list[str] = []
    by_key = {product["product_key"]: product for product in products}
    if monitor := by_key.get("monitor"):
        empty_ids = monitor["suppressed_empty_category_ids"]
        details.extend([
            "- `monitor`：30 个非空 Region × Category 状态全部为“冻结 oracle",
            "  源 panel + 源中持久定价标题”的精确线格式；"
            + (
                "空的 `tabContent1-6` 按 6 个地区分别排除。"
                if empty_ids
                else "最新版源已移除原先空的 `tabContent1-6`。"
            ),
        ])
    if "azure-migrate" in by_key:
        details.extend([
            "- `azure-migrate`：唯一根级 `h2 + h3 + div.tab-content` 与",
            "  `baseContent` 精确一致，保留 1 张表。",
        ])
    if "event-hubs" in by_key:
        details.extend([
            "- `event-hubs`：移动端源控件的 6 个地区都映射到唯一直属、无 ID 的",
            "  静态内容容器；6 个 payload 片段全部精确一致并各保留定价表。",
        ])

    return "\n".join([
        "# 第二轮已报告问题产品补充 DOM 复核",
        "",
        "本报告不修改提交 `048cf07` 冻结的第一轮比较算法。它只补充该算法",
        "对 `monitor` 持久标题、`azure-migrate` 根级 Simple 主体和",
        "`event-hubs` 无 ID 静态容器三个页面形态的覆盖盲区。程序不导入生产",
        "抽取、可达性、清洗或 payload 组装代码。",
        "",
        *rows,
        "",
        *details,
        "",
        "补充复核总结果：{}；{}/{} 个状态精确一致。".format(
            "通过" if report["all_passed"] else "失败",
            report["summary"]["exact_equal_states"],
            report["summary"]["checked_states"],
        ),
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor-output", type=Path, required=True)
    parser.add_argument("--frozen-comparison", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--product",
        action="append",
        choices=PRODUCTS,
        dest="products",
        help=(
            "Verify only this product; repeat for multiple products. "
            "Defaults to all three original supplemental products."
        ),
    )
    args = parser.parse_args()

    frozen_report_path = args.frozen_comparison / "report.json"
    frozen_report = _read_json(frozen_report_path)
    verifiers = {
        "monitor": lambda: _monitor_verification(
            args.extractor_output,
            args.frozen_comparison,
            frozen_report,
        ),
        "azure-migrate": lambda: _azure_migrate_verification(
            args.extractor_output
        ),
        "event-hubs": lambda: _event_hubs_verification(
            args.extractor_output
        ),
    }
    requested_products = tuple(dict.fromkeys(args.products or PRODUCTS))
    products = [verifiers[product_key]() for product_key in requested_products]
    report = {
        "schema_version": "1.0",
        "experiment": "v0.4.1-round-2-reported-repairs-supplement",
        "language": LANGUAGE,
        "method_relation": (
            "Additive qualification for three frozen-oracle coverage gaps; "
            "the 048cf07 comparison algorithm is unchanged."
        ),
        "inputs": {
            "extractor_output": str(args.extractor_output),
            "frozen_comparison": str(args.frozen_comparison),
            "frozen_report_sha256": _sha256_file(frozen_report_path),
            "requested_products": list(requested_products),
        },
        "products": products,
        "summary": {
            "products": len(products),
            "products_passed": sum(item["passed"] for item in products),
            "checked_states": sum(item["state_count"] for item in products),
            "exact_equal_states": sum(
                item["exact_equal_count"] for item in products
            ),
        },
        "all_passed": all(item["passed"] for item in products),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "report.md").write_text(
        _render_markdown(report),
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
