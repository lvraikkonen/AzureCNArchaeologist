"""Read models for the local, product-level human Review Workbench.

The Workbench deliberately reconstructs Source fragments with the independent
L3b locators.  It never asks a production Strategy which fragment ought to be
shown to a reviewer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from src.core.catalog import ProductCatalog
from src.core.payload_contract import load_payload
from src.machine_checks.independent_source import (
    locate_pricing_source,
    locate_support_source,
)
from src.machine_checks.readable_diff import text_difference
from src.review.service import (
    ReviewDecisionResult,
    create_review_decision,
    read_review_materials,
    read_review_status,
)
from src.utils.html.normalization import normalize_html, parse_html_bytes


class ReviewWorkbenchService:
    """Build review projections and submit explicit product decisions."""

    def __init__(
        self,
        catalog: ProductCatalog,
        *,
        review_id: str,
        reviews_root: Path | str | None = None,
    ) -> None:
        self.catalog = catalog
        self.review_id = review_id
        self.reviews_root = reviews_root

    def projection(self) -> dict[str, Any]:
        """Return the complete product queue with its current decision state."""

        status = read_review_status(
            self.catalog,
            review_id=self.review_id,
            reviews_root=self.reviews_root,
        )
        products: list[dict[str, Any]] = []
        for status_product in status["products"]:
            product_key = status_product["product_key"]
            materials = read_review_materials(
                self.catalog,
                review_id=self.review_id,
                product_key=product_key,
                reviews_root=self.reviews_root,
            )
            languages = []
            for item in materials["items"]:
                languages.append(
                    {
                        "language": item["language"],
                        "l3a_status": item["l3a_result"].get(
                            "status", "unknown"
                        ),
                        "l3b_status": item["l3b_result"].get(
                            "status", "unknown"
                        ),
                        "comparison_count": len(
                            item["l3b_result"].get("fields", [])
                        ),
                    }
                )
            products.append(
                {
                    "product_key": product_key,
                    "display_name": materials["display_name"],
                    "page_model": materials["page_model"],
                    "semantic_strategy": materials["semantic_strategy"],
                    "status": status_product["status"],
                    "reviewer": status_product["reviewer"],
                    "decision_path": status_product["decision_path"],
                    "languages": languages,
                }
            )

        return {
            "schema_version": "1.0",
            "review_id": self.review_id,
            "run_name": status["run_name"],
            "batch_kind": status["batch_kind"],
            "incremental_run_name": status["incremental_run_name"],
            "review_directory": status["review_directory"],
            "instructions": [
                "审核以产品为单位，中文和英文必须一起查看、一起决定。",
                "页面并排内容来自 L3b 独立源定位器和已封存 Payload，不调用生产 Strategy。",
                "人工决定不能覆盖机器检查失败；已经提交的决定不能覆盖。",
            ],
            "summary": {
                "queued_products": status["summary"]["queued_products"],
                "queued_items": status["summary"]["queued_items"],
                "approved_products": status["summary"]["approved_products"],
                "rejected_products": status["summary"]["rejected_products"],
                "pending_products": status["summary"]["pending_products"],
                "not_queued_items": len(status["not_queued_items"]),
            },
            "products": products,
            "not_queued_items": status["not_queued_items"],
        }

    def product_evidence(self, product_key: str) -> dict[str, Any]:
        """Return exact bilingual Source/Payload comparisons for one product."""

        materials = read_review_materials(
            self.catalog,
            review_id=self.review_id,
            product_key=product_key,
            reviews_root=self.reviews_root,
        )
        definition = self.catalog.get_definition(product_key)
        languages = []
        for item in materials["items"]:
            frozen_html_path = Path(item["frozen_html_path"])
            payload_path = Path(item["payload_path"])
            soup = parse_html_bytes(
                frozen_html_path.read_bytes(), source_name=str(frozen_html_path)
            )
            payload = load_payload(payload_path)
            if materials["page_model"] == "SupportArticlePage":
                source = locate_support_source(soup)
                comparisons = _support_comparisons(source, payload)
            else:
                source = locate_pricing_source(
                    soup,
                    semantic_strategy=materials["semantic_strategy"],
                    language=item["language"],
                    soft_category_path=(
                        self.catalog.project_root
                        / "data"
                        / "configs"
                        / "soft-category.json"
                    ),
                    page_global_source_boundary=(
                        definition.page_global_source_boundary
                    ),
                )
                comparisons = _pricing_comparisons(source, payload)
            languages.append(
                {
                    "language": item["language"],
                    "paths": {
                        "frozen_html": item["frozen_html_path"],
                        "payload": item["payload_path"],
                        "l3a_report": item["l3a_report_path"],
                        "l3b_report": item["l3b_report_path"],
                    },
                    "l3a": item["l3a_result"],
                    "l3b": item["l3b_result"],
                    "comparisons": comparisons,
                    "summary": {
                        "comparisons": len(comparisons),
                        "matched": sum(
                            comparison["status"] == "matched"
                            for comparison in comparisons
                        ),
                        "mismatched": sum(
                            comparison["status"] == "mismatched"
                            for comparison in comparisons
                        ),
                    },
                }
            )

        status = read_review_status(
            self.catalog,
            review_id=self.review_id,
            reviews_root=self.reviews_root,
        )
        product_status = next(
            product
            for product in status["products"]
            if product["product_key"] == product_key
        )
        return {
            "schema_version": "1.0",
            "review_id": self.review_id,
            "run_name": materials["run_name"],
            "batch_kind": materials["batch_kind"],
            "incremental_run_name": materials["incremental_run_name"],
            "product": {
                "product_key": product_key,
                "display_name": materials["display_name"],
                "page_model": materials["page_model"],
                "semantic_strategy": materials["semantic_strategy"],
                "status": product_status["status"],
                "reviewer": product_status["reviewer"],
                "decision_path": product_status["decision_path"],
            },
            "evidence_method": (
                "Frozen HTML 由 L3b 独立源定位器重新读取；Source 与 Payload "
                "使用同一 HTML 规范化规则后逐字段比较。"
            ),
            "languages": languages,
        }

    def submit_decision(
        self,
        product_key: str,
        *,
        reviewer: str,
        decision: str,
        inspected_languages: Sequence[str],
        inspected_materials: Sequence[str],
        notes: str,
    ) -> ReviewDecisionResult:
        """Submit through the existing write-once product decision service."""

        return create_review_decision(
            self.catalog,
            review_id=self.review_id,
            product_key=product_key,
            reviewer=reviewer,
            decision=decision,
            inspected_languages=inspected_languages,
            inspected_materials=inspected_materials,
            notes=notes,
            reviews_root=self.reviews_root,
        )


def _support_comparisons(
    source: dict[str, str], payload: dict[str, Any]
) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    _html_comparison(
        comparisons,
        payload_path="articleDescription",
        label="文章说明",
        source_boundary="h1 与首个 h2 之间的直接说明段落",
        source=source["articleDescription"],
        payload=payload.get("articleDescription"),
    )
    _html_comparison(
        comparisons,
        payload_path="mainContent",
        label="文章主体",
        source_boundary="首个直接 h2 至反馈控件之前的完整文章主体",
        source=source["mainContent"],
        payload=payload.get("mainContent"),
    )
    return comparisons


def _pricing_comparisons(
    source: dict[str, Any], payload: dict[str, Any]
) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    _html_comparison(
        comparisons,
        payload_path="baseContent",
        label="页面定价主体",
        source_boundary=(
            "完整静态定价主体"
            if source["baseContent"]
            else "筛选页面没有单独的全局正文"
        ),
        source=source["baseContent"],
        payload=payload.get("baseContent"),
    )
    _content_group_comparisons(
        comparisons,
        source=source["contentGroups"],
        payload=payload.get("contentGroups"),
    )
    _common_section_comparisons(
        comparisons,
        source=source["commonSections"],
        payload=payload.get("commonSections"),
    )
    if "filtersJsonConfig" in source:
        page_config = payload.get("pageConfig")
        payload_filters = (
            page_config.get("filtersJsonConfig")
            if isinstance(page_config, dict)
            else None
        )
        _value_comparison(
            comparisons,
            payload_path="pageConfig.filtersJsonConfig",
            label="筛选器配置",
            source_boundary="独立读取的筛选器名称、顺序、默认项和值域",
            source=source["filtersJsonConfig"],
            payload=payload_filters,
        )
    return comparisons


def _content_group_comparisons(
    comparisons: list[dict[str, Any]],
    *,
    source: list[dict[str, Any]],
    payload: Any,
) -> None:
    if not source:
        _value_comparison(
            comparisons,
            payload_path="contentGroups",
            label="可选择状态",
            source_boundary="静态定价主体没有可选择页面状态",
            source=[],
            payload=payload,
        )
        return
    _value_comparison(
        comparisons,
        payload_path="contentGroups",
        label="可选择状态数量",
        source_boundary="独立读取的全部源页面可选择状态",
        source=len(source),
        payload=len(payload) if isinstance(payload, list) else type(payload).__name__,
    )
    for index, source_group in enumerate(source):
        payload_group = (
            payload[index]
            if isinstance(payload, list) and index < len(payload)
            else None
        )
        group_label = source_group.get("groupName") or f"状态 {index + 1}"
        for field_name, field_label in (
            ("groupName", "状态名称"),
            ("filterCriteriaJson", "状态筛选条件"),
        ):
            _value_comparison(
                comparisons,
                payload_path=f"contentGroups[{index}].{field_name}",
                label=f"{group_label} · {field_label}",
                source_boundary="源筛选控件声明的状态名称与机器条件",
                source=source_group[field_name],
                payload=(
                    payload_group.get(field_name)
                    if isinstance(payload_group, dict)
                    else None
                ),
            )
        _html_comparison(
            comparisons,
            payload_path=f"contentGroups[{index}].content",
            label=f"{group_label} · 定价内容",
            source_boundary="该状态对应的完整定价内容面板",
            source=source_group["content"],
            payload=(
                payload_group.get("content")
                if isinstance(payload_group, dict)
                else None
            ),
        )
        if "sharedContent" in source_group or (
            isinstance(payload_group, dict) and "sharedContent" in payload_group
        ):
            _html_comparison(
                comparisons,
                payload_path=f"contentGroups[{index}].sharedContent",
                label=f"{group_label} · 公共定价内容",
                source_boundary=(
                    "Category 面板之前、按当前区域配置投影的公共定价内容"
                ),
                source=source_group.get("sharedContent", ""),
                payload=(
                    payload_group.get("sharedContent")
                    if isinstance(payload_group, dict)
                    else None
                ),
            )


def _common_section_comparisons(
    comparisons: list[dict[str, Any]],
    *,
    source: list[dict[str, str]],
    payload: Any,
) -> None:
    if not isinstance(payload, list) or len(payload) != len(source):
        _value_comparison(
            comparisons,
            payload_path="commonSections",
            label="公共区块数量",
            source_boundary="Banner、产品说明、FAQ 与 SLA",
            source=len(source),
            payload=len(payload) if isinstance(payload, list) else type(payload).__name__,
        )
    for index, source_section in enumerate(source):
        payload_section = (
            payload[index]
            if isinstance(payload, list) and index < len(payload)
            else None
        )
        section_type = source_section["sectionType"]
        if not isinstance(payload_section, dict) or (
            payload_section.get("sectionType") != section_type
        ):
            _value_comparison(
                comparisons,
                payload_path=f"commonSections[{index}].sectionType",
                label=f"公共区块 {index + 1} 类型",
                source_boundary=source_section["source_boundary"],
                source=section_type,
                payload=(
                    payload_section.get("sectionType")
                    if isinstance(payload_section, dict)
                    else None
                ),
            )
        _html_comparison(
            comparisons,
            payload_path=f"commonSections[{index}].content",
            label=f"{section_type} 公共区块",
            source_boundary=source_section["source_boundary"],
            source=source_section["content"],
            payload=(
                payload_section.get("content")
                if isinstance(payload_section, dict)
                else None
            ),
        )


def _html_comparison(
    comparisons: list[dict[str, Any]],
    *,
    payload_path: str,
    label: str,
    source_boundary: str,
    source: str,
    payload: Any,
) -> None:
    normalized_source = normalize_html(source)
    normalized_payload = normalize_html(payload) if isinstance(payload, str) else payload
    matched = isinstance(normalized_payload, str) and (
        normalized_source == normalized_payload
    )
    comparison: dict[str, Any] = {
        "comparison_key": payload_path,
        "payload_path": payload_path,
        "label": label,
        "source_boundary": source_boundary,
        "kind": "html",
        "status": "matched" if matched else "mismatched",
        "source": normalized_source,
        "payload": normalized_payload,
        "difference": None,
    }
    if not matched:
        comparison["difference"] = (
            text_difference(normalized_source, normalized_payload)
            if isinstance(normalized_payload, str)
            else {
                "source": "HTML 文本",
                "payload": type(normalized_payload).__name__,
            }
        )
    comparisons.append(comparison)


def _value_comparison(
    comparisons: list[dict[str, Any]],
    *,
    payload_path: str,
    label: str,
    source_boundary: str,
    source: Any,
    payload: Any,
) -> None:
    matched = source == payload
    comparisons.append(
        {
            "comparison_key": payload_path,
            "payload_path": payload_path,
            "label": label,
            "source_boundary": source_boundary,
            "kind": "value",
            "status": "matched" if matched else "mismatched",
            "source": source,
            "payload": payload,
            "difference": None
            if matched
            else {"source": source, "payload": payload},
        }
    )


__all__ = ["ReviewWorkbenchService"]
