#!/usr/bin/env python3
"""Build the deterministic v0.4 upstream source-HTML findings inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from bs4 import BeautifulSoup, Tag


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.canonical_input import CanonicalHtmlInput, UTF8_BOM
from src.core.product_manager import ProductManager
from src.core.source_html_structure import (
    AUDITOR_VERSION,
    SourceHtmlStructureAuditor,
)


LANGUAGES = ("zh-cn", "en-us")
FINDING_CODE = "SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT"
REVIEW_CODE = "SOURCE_HTML_DUPLICATE_ID_SCOPE_NEEDS_REVIEW"
REPORT_JSON = ROOT / "reports/v0.4/source-html-upstream-findings.json"
REPORT_MARKDOWN = ROOT / "reports/v0.4/source-html-upstream-findings.md"
IGNORED_MARKUP = frozenset({"script", "style", "noscript", "template"})
REFERENCE_ATTRIBUTES = frozenset(
    {"href", "aria-controls", "aria-labelledby", "for"}
)


def _canonical_json(value: Any, *, pretty: bool = False) -> bytes:
    if pretty:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
    else:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    return (rendered + "\n").encode("utf-8")


def _source_input(
    *,
    product_key: str,
    language: str,
    path: Path,
) -> CanonicalHtmlInput:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    return CanonicalHtmlInput(
        product_key=product_key,
        resource_key=product_key,
        language=language,
        source_path=path,
        normalized_path=path,
        source_sha256=digest,
        normalized_sha256=digest,
        expected_sha256=digest,
        raw_bytes=raw,
        text=raw.decode("utf-8", errors="strict"),
        has_utf8_bom=raw.startswith(UTF8_BOM),
        source_findings=(),
    )


def _outermost_formal_selectors(soup: BeautifulSoup) -> tuple[Tag, ...]:
    return tuple(
        selector
        for selector in soup.select("div.technical-azure-selector")
        if not any(
            isinstance(parent, Tag)
            and "technical-azure-selector" in (parent.get("class") or ())
            for parent in selector.parents
        )
    )


def _inside_ignored_markup(node: Tag, root: Tag) -> bool:
    if node.name in IGNORED_MARKUP:
        return True
    for parent in node.parents:
        if parent is root:
            return False
        if isinstance(parent, Tag) and parent.name in IGNORED_MARKUP:
            return True
    return False


def _duplicate_ids_in_formal_selectors(
    soup: BeautifulSoup,
) -> tuple[tuple[str, tuple[Tag, ...], tuple[int, ...]], ...]:
    occurrences: dict[str, list[Tag]] = defaultdict(list)
    selector_indexes: dict[str, list[int]] = defaultdict(list)
    for selector_index, selector in enumerate(
        _outermost_formal_selectors(soup),
        start=1,
    ):
        nodes = (
            ([selector] if selector.has_attr("id") else [])
            + list(selector.find_all(id=True))
        )
        for node in nodes:
            if _inside_ignored_markup(node, selector):
                continue
            raw_identifier = node.get("id")
            if not isinstance(raw_identifier, str):
                continue
            identifier = raw_identifier.strip()
            if not identifier:
                continue
            occurrences[identifier].append(node)
            selector_indexes[identifier].append(selector_index)
    return tuple(
        (
            identifier,
            tuple(occurrences[identifier]),
            tuple(selector_indexes[identifier]),
        )
        for identifier in sorted(occurrences)
        if len(occurrences[identifier]) > 1
    )


def _attribute_values(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value)
    return ()


def _references_identifier(
    *,
    attribute: str,
    value: str,
    identifier: str,
) -> bool:
    normalized = value.strip()
    if attribute in {"aria-controls", "aria-labelledby", "for"}:
        return identifier in normalized.split()
    return (
        normalized == identifier
        or normalized == f"#{identifier}"
        or normalized.endswith(f"#{identifier}")
    )


def _target_references(
    soup: BeautifulSoup,
    identifier: str,
) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for node in soup.find_all(True):
        if node.name in IGNORED_MARKUP:
            continue
        for raw_attribute, raw_value in sorted(node.attrs.items()):
            attribute = str(raw_attribute).casefold()
            if (
                attribute not in REFERENCE_ATTRIBUTES
                and not attribute.startswith("data-")
            ):
                continue
            for value in _attribute_values(raw_value):
                if not _references_identifier(
                    attribute=attribute,
                    value=value,
                    identifier=identifier,
                ):
                    continue
                references.append(
                    {
                        "line": int(node.sourceline or 1),
                        "element": str(node.name),
                        "attribute": attribute,
                        "value": value,
                    }
                )
    return sorted(
        references,
        key=lambda item: (
            item["line"],
            item["element"],
            item["attribute"],
            item["value"],
        ),
    )


def _source_identity(
    canonical: CanonicalHtmlInput,
    root: Path,
) -> dict[str, Any]:
    return {
        "path": canonical.source_path.relative_to(root).as_posix(),
        "sha256": canonical.source_sha256,
        "size_bytes": canonical.size_bytes,
    }


def _confirmed_item(
    *,
    canonical: CanonicalHtmlInput,
    display_name: str,
    finding: Any,
    soup: BeautifulSoup,
    root: Path,
) -> dict[str, Any]:
    identifier = str(finding.evidence[0].description).split("'")[1]
    references = _target_references(soup, identifier)
    return {
        "status": "confirmed_blocking",
        "product_key": canonical.product_key,
        "display_name": display_name,
        "language": canonical.language,
        "source": _source_identity(canonical, root),
        "finding_code": finding.code,
        "duplicate_id": identifier,
        "occurrence_count": len(finding.evidence),
        "lines": [evidence.line for evidence in finding.evidence],
        "reference_count": len(references),
        "references": references,
        "confirmation_basis": [
            "sole_static_formal_selector_scope",
            "no_active_filter_controls",
            "exact_following_common_section_boundary",
            "duplicate_id_occurs_within_one_page_global_fragment",
            (
                "no_dom_target_references_found"
                if not references
                else "dom_target_references_present"
            ),
        ],
        "upstream_suggestion": finding.upstream_suggestion.to_dict(),
        "payload_generation_allowed": False,
    }


def _blocking_structure_item(
    *,
    canonical: CanonicalHtmlInput,
    display_name: str,
    finding: Any,
    root: Path,
) -> dict[str, Any]:
    if finding.upstream_suggestion is None:
        raise ValueError(
            f"Blocking source structure finding {finding.code} must carry "
            "an upstream suggestion"
        )
    return {
        "status": "confirmed_blocking",
        "product_key": canonical.product_key,
        "display_name": display_name,
        "language": canonical.language,
        "source": _source_identity(canonical, root),
        "finding_code": finding.code,
        "message": finding.message,
        "evidence": [item.to_dict() for item in finding.evidence],
        "lines": [item.line for item in finding.evidence],
        "safety_checks": list(finding.safety_checks),
        "upstream_suggestion": finding.upstream_suggestion.to_dict(),
        "payload_generation_allowed": False,
    }


def _review_item(
    *,
    canonical: CanonicalHtmlInput,
    display_name: str,
    identifier: str,
    occurrences: tuple[Tag, ...],
    selector_indexes: tuple[int, ...],
    soup: BeautifulSoup,
    root: Path,
) -> dict[str, Any]:
    references = _target_references(soup, identifier)
    selector_count = len(_outermost_formal_selectors(soup))
    reasons: list[str] = []
    if selector_count != 1:
        reasons.append("multiple_outermost_formal_selectors")
    if len(set(selector_indexes)) != 1:
        reasons.append("duplicate_id_spans_formal_selectors")
    if references:
        reasons.append("duplicate_id_has_dom_target_references")
    reasons.append("single_static_base_content_boundary_not_proven")
    return {
        "status": "needs_upstream_structure_review",
        "product_key": canonical.product_key,
        "display_name": display_name,
        "language": canonical.language,
        "source": _source_identity(canonical, root),
        "finding_code": REVIEW_CODE,
        "duplicate_id": identifier,
        "occurrence_count": len(occurrences),
        "lines": [int(node.sourceline or 1) for node in occurrences],
        "reference_count": len(references),
        "references": references,
        "outermost_formal_selector_count": selector_count,
        "occurrence_selector_indexes": list(selector_indexes),
        "review_reasons": reasons,
        "upstream_suggestion": {
            "action": "clarify_boundary_then_make_id_unique",
            "description": (
                f"Upstream should first confirm which formal selector and element "
                f"owns target #{identifier}, then remove or rename every redundant "
                "id and update all target references. Extraction must not guess "
                "the ownership boundary."
            ),
        },
    }


def build_report(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    manager = ProductManager(str(root / "data" / "configs"))
    index = manager.load_products_index()
    auditor = SourceHtmlStructureAuditor(root)
    supported = manager.get_supported_products()
    confirmed: list[dict[str, Any]] = []
    blocking_structure: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    finding_counts: Counter[str] = Counter()
    source_identities: list[dict[str, str]] = []
    surveyed_sources = 0
    simple_sources = 0

    for product_key in supported:
        definition = manager.get_product_config(product_key)
        display_name = str(definition["display_name"])
        is_simple = (
            definition.get("extraction", {}).get("semantic_strategy")
            == "simple_static"
        )
        for language in LANGUAGES:
            source_definition = definition["sources"][language]
            if source_definition["availability"] != "available":
                continue
            path_value = manager.get_html_file_path(product_key, language)
            if path_value is None:
                raise FileNotFoundError(
                    f"Canonical normalized input is missing: {product_key}/{language}"
                )
            canonical = _source_input(
                product_key=product_key,
                language=language,
                path=Path(path_value),
            )
            surveyed_sources += 1
            simple_sources += int(is_simple)
            source_identities.append(
                {
                    "product_key": product_key,
                    "language": language,
                    "path": canonical.source_path.relative_to(root).as_posix(),
                    "sha256": canonical.source_sha256,
                }
            )
            soup = BeautifulSoup(canonical.text, "html.parser")
            audit = auditor.audit(canonical)
            confirmed_keys: set[tuple[str, tuple[int, ...]]] = set()
            for finding in audit.findings:
                finding_counts[finding.code] += 1
                if finding.code == FINDING_CODE:
                    item = _confirmed_item(
                        canonical=canonical,
                        display_name=display_name,
                        finding=finding,
                        soup=soup,
                        root=root,
                    )
                    confirmed.append(item)
                    confirmed_keys.add(
                        (item["duplicate_id"], tuple(item["lines"]))
                    )
                    continue
                if finding.blocking:
                    blocking_structure.append(
                        _blocking_structure_item(
                            canonical=canonical,
                            display_name=display_name,
                            finding=finding,
                            root=root,
                        )
                    )

            if not is_simple:
                continue
            for identifier, occurrences, selector_indexes in (
                _duplicate_ids_in_formal_selectors(soup)
            ):
                lines = tuple(int(node.sourceline or 1) for node in occurrences)
                if (identifier, lines) in confirmed_keys:
                    continue
                review.append(
                    _review_item(
                        canonical=canonical,
                        display_name=display_name,
                        identifier=identifier,
                        occurrences=occurrences,
                        selector_indexes=selector_indexes,
                        soup=soup,
                        root=root,
                    )
                )

    source_inventory_sha256 = hashlib.sha256(
        _canonical_json(source_identities)
    ).hexdigest()
    confirmed.sort(
        key=lambda item: (
            item["product_key"],
            LANGUAGES.index(item["language"]),
            item["duplicate_id"],
        )
    )
    blocking_structure.sort(
        key=lambda item: (
            item["product_key"],
            LANGUAGES.index(item["language"]),
            item["finding_code"],
        )
    )
    review.sort(
        key=lambda item: (
            item["product_key"],
            LANGUAGES.index(item["language"]),
            item["duplicate_id"],
        )
    )
    blocking_structure_by_code = Counter(
        item["finding_code"] for item in blocking_structure
    )
    return {
        "schema_version": "1.0",
        "report_scope": "v0.4_upstream_source_html_structure_findings_inventory",
        "generator": "scripts/build_v04_source_html_findings.py",
        "auditor_version": AUDITOR_VERSION,
        "product_index_source_digest": index["source_digest"],
        "survey": {
            "supported_product_definitions": len(supported),
            "languages": list(LANGUAGES),
            "canonical_sources_surveyed": surveyed_sources,
            "simple_static_sources_surveyed": simple_sources,
            "source_inventory_sha256": source_inventory_sha256,
            "all_auditor_findings_by_code": dict(sorted(finding_counts.items())),
            "cross_state_duplicate_ids_are_not_treated_as_page_global_duplicates": True,
        },
        "confirmed_blocking_findings": confirmed,
        "blocking_source_structure_findings": blocking_structure,
        "needs_upstream_structure_review": review,
        "summary": {
            "confirmed_product_keys": sorted(
                {item["product_key"] for item in confirmed}
            ),
            "confirmed_language_findings": len(confirmed),
            "blocking_structure_product_keys": sorted(
                {item["product_key"] for item in blocking_structure}
            ),
            "blocking_structure_language_items": len(
                {
                    (item["product_key"], item["language"])
                    for item in blocking_structure
                }
            ),
            "blocking_structure_findings": len(blocking_structure),
            "blocking_structure_findings_by_code": dict(
                sorted(blocking_structure_by_code.items())
            ),
            "needs_review_product_keys": sorted(
                {item["product_key"] for item in review}
            ),
            "needs_review_language_items": len(review),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# v0.4 上游源 HTML 结构问题清单",
        "",
        "本清单只记录源文件事实，不修改或自动修复上游 HTML。"
        "“已确认阻断”表示问题由严格结构谓词证明；“需要结构复核”不能冒充"
        "同类已确认问题。",
        "",
        "## 全量调查",
        "",
        f"- Product Index：`{report['product_index_source_digest']}`",
        (
            "- 已调查 canonical 双语源："
            f"{report['survey']['canonical_sources_surveyed']}；其中 Simple："
            f"{report['survey']['simple_static_sources_surveyed']}"
        ),
        (
            "- 源身份集合 SHA-256："
            f"`{report['survey']['source_inventory_sha256']}`"
        ),
        "- 跨 region/software/category 状态面板的重复 ID 不按静态 "
        "`baseContent` 重复处理。",
        "",
        "## 已确认阻断：静态 baseContent 重复 ID",
        "",
        "| 产品 | 语言 | 重复 ID | 次数 | 行号 | 引用数 | 源 SHA-256 |",
        "| --- | --- | --- | ---: | --- | ---: | --- |",
    ]
    for item in report["confirmed_blocking_findings"]:
        lines.append(
            f"| `{item['product_key']}` ({item['display_name']}) "
            f"| `{item['language']}` | `{item['duplicate_id']}` "
            f"| {item['occurrence_count']} "
            f"| {', '.join(str(line) for line in item['lines'])} "
            f"| {item['reference_count']} | `{item['source']['sha256']}` |"
        )
    lines.extend(
        [
            "",
            "上游建议：这些源文件中没有发现指向重复 `tabContent1` 的 "
            "DOM 引用。请移除多余 ID；如果上游确认 ID 有语义用途，则为每个元素"
            "分配唯一 ID，并同步更新全部引用。",
            "",
            "## 其他已确认阻断结构问题",
            "",
            "下列源文件保持抽取失败且不生成 Payload，直到上游修正并通过同一"
            "结构审计。失败是预期的可信状态，不会由抽取兼容逻辑掩盖。",
            "",
            "| 产品 | 语言 | Finding | 行号 | 源 SHA-256 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for item in report["blocking_source_structure_findings"]:
        lines.append(
            f"| `{item['product_key']}` ({item['display_name']}) "
            f"| `{item['language']}` | `{item['finding_code']}` "
            f"| {', '.join(str(line) for line in item['lines'])} "
            f"| `{item['source']['sha256']}` |"
        )
    lines.extend(
        [
            "",
            "## 需要上游结构复核",
            "",
            "| 产品 | 语言 | 重复 ID | 次数 | 行号 | 引用数 | 复核原因 | 源 SHA-256 |",
            "| --- | --- | --- | ---: | --- | ---: | --- | --- |",
        ]
    )
    for item in report["needs_upstream_structure_review"]:
        reasons = ", ".join(item["review_reasons"])
        lines.append(
            f"| `{item['product_key']}` ({item['display_name']}) "
            f"| `{item['language']}` | `{item['duplicate_id']}` "
            f"| {item['occurrence_count']} "
            f"| {', '.join(str(line) for line in item['lines'])} "
            f"| {item['reference_count']} | `{reasons}` "
            f"| `{item['source']['sha256']}` |"
        )
    lines.extend(
        [
            "",
            "Route Server 的重复 ID 位于含隐藏筛选控件的单个 selector 内，"
            "且有 `data-href` 引用；SQL Edge 同时存在两个外层 selector，重复 "
            "ID 跨 selector 且有引用。两者都应由上游先确认目标所有权，再移除或"
            "重命名重复 ID 并更新引用；抽取逻辑不猜测边界。",
            "",
            "## 源路径与上游动作",
            "",
        ]
    )
    for item in (
        report["confirmed_blocking_findings"]
        + report["blocking_source_structure_findings"]
        + report["needs_upstream_structure_review"]
    ):
        evidence = item.get("evidence", [])
        lines.extend(
            [
                f"### {item['product_key']} / {item['language']}",
                "",
                f"- 源路径：`{item['source']['path']}`",
                f"- 源大小：{item['source']['size_bytes']} bytes",
                f"- Finding：`{item['finding_code']}`",
                (
                    "- 证据："
                    + (
                        "；".join(
                            f"第 {evidence_item['line']} 行："
                            f"{evidence_item['description']}"
                            for evidence_item in evidence
                        )
                        if evidence
                        else "见上表行号与引用信息"
                    )
                ),
                (
                    "- 阻断 Payload："
                    + (
                        "是"
                        if item.get("payload_generation_allowed") is False
                        else "需复核"
                    )
                ),
                f"- 建议动作：`{item['upstream_suggestion']['action']}`",
                f"- 建议：{item['upstream_suggestion']['description']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _write_atomic(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(value)
    temporary.replace(path)


def _check(path: Path, expected: bytes) -> bool:
    return path.is_file() and path.read_bytes() == expected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the checked-in JSON or Markdown report has drifted.",
    )
    args = parser.parse_args(argv)

    report = build_report(ROOT)
    json_bytes = _canonical_json(report, pretty=True)
    markdown_bytes = render_markdown(report).encode("utf-8")
    if args.check:
        stale = [
            path.relative_to(ROOT).as_posix()
            for path, expected in (
                (REPORT_JSON, json_bytes),
                (REPORT_MARKDOWN, markdown_bytes),
            )
            if not _check(path, expected)
        ]
        if stale:
            print("Source HTML upstream findings report drifted:")
            for path in stale:
                print(f"- {path}")
            return 1
        print(
            "Source HTML upstream findings report is current: "
            f"{len(report['confirmed_blocking_findings'])} confirmed, "
            f"{len(report['blocking_source_structure_findings'])} other blocking, "
            f"{len(report['needs_upstream_structure_review'])} needs review"
        )
        return 0

    _write_atomic(REPORT_JSON, json_bytes)
    _write_atomic(REPORT_MARKDOWN, markdown_bytes)
    print(
        "Wrote source HTML upstream findings report: "
        f"{len(report['confirmed_blocking_findings'])} confirmed, "
        f"{len(report['blocking_source_structure_findings'])} other blocking, "
        f"{len(report['needs_upstream_structure_review'])} needs review"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
