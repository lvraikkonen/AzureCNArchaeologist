"""Prepare human review material and record explicit human decisions."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from src.core.catalog import LANGUAGES, ProductCatalog
from src.core.payload_contract import (
    PayloadContractError,
    load_payload,
    validate_pricing_payload,
    validate_support_article_payload,
)


READABLE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CHECK_NAMES = ("L3a", "L3b")
DECISIONS = {"approved", "rejected"}
MATERIAL_LABELS = {
    "frozen-html": "Frozen HTML",
    "payload": "Business Payload",
    "l3a-report": "L3a 检查报告",
    "l3b-report": "L3b 检查报告",
}
ALL_MATERIALS = tuple(MATERIAL_LABELS)


class ReviewError(RuntimeError):
    """A review queue or decision cannot be trusted or safely written."""


@dataclass(frozen=True)
class ReviewQueueResult:
    review_id: str
    review_directory: Path
    queue: dict[str, Any]


@dataclass(frozen=True)
class ReviewDecisionResult:
    review_id: str
    product_key: str
    decision_path: Path
    decision: dict[str, Any]


@dataclass(frozen=True)
class ReleaseReviewSnapshot:
    review_directory: Path
    queue: dict[str, Any]
    approved: tuple[tuple[dict[str, Any], dict[str, Any], Path], ...]
    rejected_product_keys: tuple[str, ...]
    pending_product_keys: tuple[str, ...]


def prepare_review_queue(
    catalog: ProductCatalog,
    *,
    run_name: str,
    review_id: str,
    runs_root: Path | str | None = None,
    reviews_root: Path | str | None = None,
) -> ReviewQueueResult:
    """Create one immutable queue from a sealed Batch.

    Queue items are language-specific and enter only when extraction, L3a, and
    L3b all passed. Decisions are intentionally absent from this operation.
    """

    _validate_readable_id(run_name, field="Batch 名称")
    _validate_readable_id(review_id, field="审核 ID")
    project_root = catalog.project_root
    run_root = _root_path(project_root, runs_root, "runs")
    review_root = _root_path(project_root, reviews_root, "reviews", create=True)
    run_directory, manifest = _load_sealed_run(run_root, run_name)

    final_directory = review_root / review_id
    building_directory = review_root / f"{review_id}.building"
    if final_directory.exists():
        raise ReviewError(f"审核目录已经存在，不能覆盖：{final_directory}")
    if building_directory.exists():
        raise ReviewError(
            f"发现未完成的审核清单目录，不能覆盖：{building_directory}"
        )

    queued_by_product: dict[str, list[dict[str, Any]]] = {}
    product_order: list[str] = []
    not_queued_items: list[dict[str, str]] = []
    items = manifest.get("items")
    if not isinstance(items, list):
        raise ReviewError("Batch 清单缺少可读的处理项列表。")

    for row in items:
        if not isinstance(row, dict):
            raise ReviewError("Batch 清单包含不是对象的处理项。")
        product_key = _required_string(row, "product_key", "Batch 处理项")
        language = _required_string(row, "language", f"{product_key} 处理项")
        item_id = _required_string(row, "item_id", f"{product_key} 处理项")
        if language not in LANGUAGES:
            raise ReviewError(f"{item_id} 使用未知语言：{language}。")
        if product_key not in product_order:
            product_order.append(product_key)
        queued_item, reasons = _build_queue_item(
            catalog,
            run_directory=run_directory,
            row=row,
        )
        if queued_item is None:
            not_queued_items.append(
                {"item_id": item_id, "reason": "；".join(reasons)}
            )
            continue
        queued_by_product.setdefault(product_key, []).append(queued_item)

    products: list[dict[str, Any]] = []
    for product_key in product_order:
        queued_items = queued_by_product.get(product_key, [])
        if not queued_items:
            continue
        queued_languages = tuple(item["language"] for item in queued_items)
        if queued_languages != tuple(catalog.languages):
            for item in queued_items:
                not_queued_items.append(
                    {
                        "item_id": item["item_id"],
                        "reason": (
                            "同一产品没有完整的中文和英文机器检查通过项，"
                            "不能进入产品级人工审核"
                        ),
                    }
                )
            continue
        page_models = {item["page_model"] for item in queued_items}
        semantic_strategies = {
            item["semantic_strategy"] for item in queued_items
        }
        if len(page_models) != 1 or len(semantic_strategies) != 1:
            for item in queued_items:
                not_queued_items.append(
                    {
                        "item_id": item["item_id"],
                        "reason": (
                            "同一产品的中英文 Batch 页面模型或 Strategy 不一致，"
                            "不能进入产品级人工审核"
                        ),
                    }
                )
            continue
        definition = catalog.get_definition(product_key)
        material_path = final_directory / "materials" / f"{product_key}.md"
        products.append(
            {
                "product_key": product_key,
                "display_name": definition.display_name,
                "page_model": next(iter(page_models)),
                "semantic_strategy": next(iter(semantic_strategies)),
                "bilingual_ready": True,
                "review_material_path": _present_path(material_path, project_root),
                "items": queued_items,
            }
        )

    queued_item_count = sum(len(product["items"]) for product in products)
    bilingual_product_count = sum(
        1 for product in products if product["bilingual_ready"]
    )
    batch_reference: dict[str, Any] = {
        "run_name": run_name,
        "run_directory": _present_path(run_directory, project_root),
        "run_manifest_path": _present_path(
            run_directory / "run.json", project_root
        ),
        "batch_kind": manifest.get("batch_kind", "standard"),
    }
    if manifest.get("batch_kind") == "incremental_reprocessing":
        reprocessing = manifest.get("incremental_reprocessing")
        if not isinstance(reprocessing, dict):
            raise ReviewError("重新处理记录缺少原增量 Batch 绑定。")
        batch_reference["incremental_run_name"] = _required_string(
            reprocessing,
            "incremental_run_name",
            "重新处理记录",
        )
        batch_reference["previous_processing_run_name"] = _required_string(
            reprocessing,
            "previous_processing_run_name",
            "重新处理记录",
        )
    queue: dict[str, Any] = {
        "schema_version": "1.0",
        "review_id": review_id,
        "batch": batch_reference,
        "review_instructions": [
            "审核决定只能由真实审核人通过本地人工审核台页面记录。",
            "批准前必须检查同一产品的中文和英文 Frozen HTML、Business Payload、L3a 与 L3b 报告。",
            "人工决定不能覆盖机器检查失败或阻断。",
        ],
        "summary": {
            "batch_items": len(items),
            "queued_items": queued_item_count,
            "not_queued_items": len(not_queued_items),
            "queued_products": len(products),
            "bilingual_ready_products": bilingual_product_count,
        },
        "products": products,
        "not_queued_items": not_queued_items,
    }

    building_directory.mkdir(parents=True)
    (building_directory / "decisions").mkdir()
    materials_directory = building_directory / "materials"
    materials_directory.mkdir()
    _write_new_json(building_directory / "queue.json", queue)
    for product in products:
        material_path = materials_directory / f"{product['product_key']}.md"
        material_path.write_text(
            _build_material_markdown(
                product,
                material_path=final_directory / "materials" / material_path.name,
                project_root=project_root,
            ),
            encoding="utf-8",
        )
    try:
        building_directory.rename(final_directory)
    except OSError as error:
        raise ReviewError(
            f"无法封存审核清单目录 {final_directory}：{error}"
        ) from error
    return ReviewQueueResult(review_id, final_directory, queue)


def create_review_decision(
    catalog: ProductCatalog,
    *,
    review_id: str,
    product_key: str,
    reviewer: str,
    decision: str,
    inspected_languages: Sequence[str],
    inspected_materials: Sequence[str],
    notes: str,
    reviews_root: Path | str | None = None,
) -> ReviewDecisionResult:
    """Record one product-level human decision without overwriting history."""

    _validate_readable_id(review_id, field="审核 ID")
    _validate_readable_id(product_key, field="Product Key")
    normalized_reviewer = _human_text(reviewer, field="审核人", single_line=True)
    normalized_notes = _human_text(notes, field="审核说明")
    if decision not in DECISIONS:
        raise ReviewError("审核决定必须是 approved 或 rejected。")
    languages = _ordered_unique(
        inspected_languages,
        allowed=tuple(catalog.languages),
        field="已检查语言",
    )
    materials = _ordered_unique(
        inspected_materials,
        allowed=ALL_MATERIALS,
        field="已检查材料",
    )
    if decision == "approved":
        if languages != tuple(catalog.languages):
            raise ReviewError("批准前必须明确检查中文和英文两个处理项。")
        if materials != ALL_MATERIALS:
            raise ReviewError(
                "批准前必须明确检查 Frozen HTML、Business Payload、L3a 和 L3b 报告。"
            )

    project_root = catalog.project_root
    review_root = _root_path(project_root, reviews_root, "reviews")
    review_directory, queue = _load_review_queue(review_root, review_id)
    product = _queue_product(queue, product_key)
    if not product.get("bilingual_ready"):
        raise ReviewError(
            f"产品 {product_key} 没有两个语言均通过机器检查，不能记录批准或拒绝决定。"
        )
    _verify_queue_product(
        queue,
        product,
        catalog=catalog,
    )

    reviewed_items = [
        {
            "item_id": item["item_id"],
            "language": item["language"],
            "frozen_html_path": item["frozen_html_path"],
            "payload_path": item["payload_path"],
            "l3a_report_path": item["l3a_report_path"],
            "l3b_report_path": item["l3b_report_path"],
        }
        for item in product["items"]
    ]
    decision_record: dict[str, Any] = {
        "schema_version": "1.0",
        "review_id": review_id,
        "run_name": queue["batch"]["run_name"],
        "batch_kind": queue["batch"].get("batch_kind", "standard"),
        "incremental_run_name": queue["batch"].get("incremental_run_name"),
        "product_key": product_key,
        "reviewer": normalized_reviewer,
        "decision": decision,
        "inspection_scope": {
            "languages": list(languages),
            "materials": [MATERIAL_LABELS[material] for material in materials],
        },
        "notes": normalized_notes,
        "reviewed_items": reviewed_items,
    }
    decision_path = review_directory / "decisions" / f"{product_key}.json"
    if decision_path.exists():
        raise ReviewError(
            f"产品 {product_key} 已有审核决定，不能覆盖；需要重审时请创建新的审核 ID。"
        )
    _write_new_json(decision_path, decision_record)
    return ReviewDecisionResult(
        review_id,
        product_key,
        decision_path,
        decision_record,
    )


def read_review_status(
    catalog: ProductCatalog,
    *,
    review_id: str,
    reviews_root: Path | str | None = None,
) -> dict[str, Any]:
    """Return a live projection of write-once decision files."""

    _validate_readable_id(review_id, field="审核 ID")
    review_root = _root_path(catalog.project_root, reviews_root, "reviews")
    review_directory, queue = _load_review_queue(review_root, review_id)
    products: list[dict[str, str | None]] = []
    counts = {"approved": 0, "rejected": 0, "pending": 0}
    for product in queue["products"]:
        product_key = product["product_key"]
        decision_path = review_directory / "decisions" / f"{product_key}.json"
        if decision_path.is_file():
            record = _read_decision(
                decision_path,
                review_id=review_id,
                product_key=product_key,
            )
            status = record["decision"]
            reviewer = record["reviewer"]
        else:
            status = "pending"
            reviewer = None
        counts[status] += 1
        products.append(
            {
                "product_key": product_key,
                "status": status,
                "reviewer": reviewer,
                "decision_path": (
                    _present_path(decision_path, catalog.project_root)
                    if decision_path.is_file()
                    else None
                ),
            }
        )
    return {
        "review_id": review_id,
        "run_name": queue["batch"]["run_name"],
        "batch_kind": queue["batch"].get("batch_kind", "standard"),
        "incremental_run_name": queue["batch"].get("incremental_run_name"),
        "review_directory": _present_path(review_directory, catalog.project_root),
        "summary": {
            "queued_products": len(products),
            "queued_items": queue["summary"]["queued_items"],
            "approved_products": counts["approved"],
            "rejected_products": counts["rejected"],
            "pending_products": counts["pending"],
        },
        "products": products,
        "not_queued_items": queue["not_queued_items"],
    }


def read_review_materials(
    catalog: ProductCatalog,
    *,
    review_id: str,
    product_key: str,
    reviews_root: Path | str | None = None,
) -> dict[str, Any]:
    """Resolve the exact files a reviewer must inspect for one product."""

    _validate_readable_id(review_id, field="审核 ID")
    review_root = _root_path(catalog.project_root, reviews_root, "reviews")
    _, queue = _load_review_queue(review_root, review_id)
    product = _queue_product(queue, product_key)
    _verify_queue_product(queue, product, catalog=catalog)
    items: list[dict[str, Any]] = []
    for item in product["items"]:
        l3a_path = _resolve_presented_path(
            item["l3a_report_path"], catalog.project_root
        )
        l3b_path = _resolve_presented_path(
            item["l3b_report_path"], catalog.project_root
        )
        items.append(
            {
                "item_id": item["item_id"],
                "language": item["language"],
                "frozen_html_path": _resolve_presented_path(
                    item["frozen_html_path"], catalog.project_root
                ).as_posix(),
                "payload_path": _resolve_presented_path(
                    item["payload_path"], catalog.project_root
                ).as_posix(),
                "l3a_report_path": l3a_path.as_posix(),
                "l3b_report_path": l3b_path.as_posix(),
                "l3a_result": _read_json_object(l3a_path),
                "l3b_result": _read_json_object(l3b_path),
            }
        )
    return {
        "review_id": review_id,
        "run_name": queue["batch"]["run_name"],
        "batch_kind": queue["batch"].get("batch_kind", "standard"),
        "incremental_run_name": queue["batch"].get("incremental_run_name"),
        "product_key": product_key,
        "display_name": product["display_name"],
        "page_model": product["page_model"],
        "semantic_strategy": product["semantic_strategy"],
        "bilingual_ready": product["bilingual_ready"],
        "review_material_path": _resolve_presented_path(
            product["review_material_path"], catalog.project_root
        ).as_posix(),
        "items": items,
    }


def collect_release_review_snapshot(
    catalog: ProductCatalog,
    *,
    review_id: str,
    reviews_root: Path | str | None = None,
) -> ReleaseReviewSnapshot:
    """Read and strictly validate the current decisions for Release building."""

    _validate_readable_id(review_id, field="审核 ID")
    review_root = _root_path(catalog.project_root, reviews_root, "reviews")
    review_directory, queue = _load_review_queue(review_root, review_id)
    approved: list[tuple[dict[str, Any], dict[str, Any], Path]] = []
    rejected: list[str] = []
    pending: list[str] = []
    for product in queue["products"]:
        if not isinstance(product, dict):
            raise ReviewError("审核清单包含不是对象的产品。")
        product_key = _required_string(product, "product_key", "审核产品")
        decision_path = review_directory / "decisions" / f"{product_key}.json"
        if not decision_path.is_file():
            pending.append(product_key)
            continue
        record = _read_decision(
            decision_path,
            review_id=review_id,
            product_key=product_key,
        )
        _verify_queue_product(queue, product, catalog=catalog)
        _validate_decision_binding(queue, product, record)
        if record["decision"] == "approved":
            approved.append((product, record, decision_path))
        else:
            rejected.append(product_key)
    return ReleaseReviewSnapshot(
        review_directory=review_directory,
        queue=queue,
        approved=tuple(approved),
        rejected_product_keys=tuple(rejected),
        pending_product_keys=tuple(pending),
    )


def _build_queue_item(
    catalog: ProductCatalog,
    *,
    run_directory: Path,
    row: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    item_id = _required_string(row, "item_id", "Batch 处理项")
    product_key = _required_string(row, "product_key", item_id)
    language = _required_string(row, "language", item_id)
    page_model = _required_string(row, "page_model", item_id)
    semantic_strategy = _required_string(row, "semantic_strategy", item_id)
    reasons: list[str] = []
    if row.get("status") != "passed":
        reason = row.get("error") or f"Batch 结果为 {row.get('status', 'unknown')}"
        reasons.append(str(reason))
    source_input = row.get("input")
    if not isinstance(source_input, dict) or source_input.get("status") != "passed":
        reasons.append("Frozen HTML 固定没有通过")
    extraction = row.get("extraction")
    if not isinstance(extraction, dict) or extraction.get("status") != "passed":
        reasons.append("抽取没有通过")
    checks = row.get("checks")
    if not isinstance(checks, dict):
        reasons.append("缺少 L3a、L3b 检查结果")
    else:
        for check_name in CHECK_NAMES:
            check = checks.get(check_name)
            if not isinstance(check, dict) or check.get("status") != "passed":
                reasons.append(f"{check_name} 没有通过")
    if reasons:
        return None, reasons

    assert isinstance(checks, dict)
    payload_path = _run_artifact_path(
        run_directory,
        _required_string(row, "payload_path", item_id),
        item_id,
    )
    batch_frozen = row.get("frozen_html_path")
    if batch_frozen is not None:
        frozen_path = _run_artifact_path(
            run_directory,
            _required_string(row, "frozen_html_path", item_id),
            f"{item_id} Batch Frozen HTML",
        )
    else:
        frozen_relative = _required_string(
            row,
            "frozen_relative_path",
            item_id,
        )
        frozen_path = _safe_relative_path(
            catalog.project_root / "data" / "prod-html",
            frozen_relative,
            label=f"{item_id} Frozen HTML",
        )
    check_paths: dict[str, Path] = {}
    check_reports: dict[str, dict[str, Any]] = {}
    for check_name in CHECK_NAMES:
        check = checks[check_name]
        check_path = _run_artifact_path(
            run_directory,
            _required_string(check, "path", f"{item_id} {check_name}"),
            f"{item_id} {check_name}",
        )
        check_paths[check_name] = check_path

    missing = [
        label
        for label, path in (
            ("Frozen HTML", frozen_path),
            ("Business Payload", payload_path),
            ("L3a 报告", check_paths["L3a"]),
            ("L3b 报告", check_paths["L3b"]),
        )
        if not path.is_file()
    ]
    if missing:
        return None, [f"缺少审核材料：{', '.join(missing)}"]
    try:
        _validate_business_payload(
            catalog,
            product_key=product_key,
            language=language,
            payload_path=payload_path,
            page_model=page_model,
            semantic_strategy=semantic_strategy,
        )
        for check_name in CHECK_NAMES:
            report = _read_json_object(check_paths[check_name])
            _validate_passed_check(
                report,
                check_name=check_name,
                product_key=product_key,
                language=language,
            )
            check_reports[check_name] = report
    except ReviewError as error:
        return None, [str(error)]

    return (
        {
            "item_id": item_id,
            "language": language,
            "page_model": page_model,
            "semantic_strategy": semantic_strategy,
            "frozen_html_path": _present_path(frozen_path, catalog.project_root),
            "payload_path": _present_path(payload_path, catalog.project_root),
            "l3a_report_path": _present_path(
                check_paths["L3a"], catalog.project_root
            ),
            "l3b_report_path": _present_path(
                check_paths["L3b"], catalog.project_root
            ),
            "machine_results": {
                "L3a": {
                    "status": "passed",
                    "scope": check_reports["L3a"].get("scope", "完整 Business Payload"),
                    "difference_count": len(
                        check_reports["L3a"].get("differences", [])
                    ),
                },
                "L3b": {
                    "status": "passed",
                    "scope": check_reports["L3b"].get("scope", "全部业务 HTML 字段"),
                    "verified_field_count": len(
                        check_reports["L3b"].get("fields", [])
                    ),
                },
            },
        },
        [],
    )


def _verify_queue_product(
    queue: dict[str, Any],
    product: dict[str, Any],
    *,
    catalog: ProductCatalog,
) -> None:
    project_root = catalog.project_root
    run_name = _required_string(queue["batch"], "run_name", "审核清单 Batch")
    run_directory = _resolve_presented_path(
        _required_string(queue["batch"], "run_directory", "审核清单 Batch"),
        project_root,
    )
    manifest_path = _resolve_presented_path(
        _required_string(
            queue["batch"], "run_manifest_path", "审核清单 Batch"
        ),
        project_root,
    )
    if manifest_path != run_directory / "run.json":
        raise ReviewError("审核清单引用的 Batch 清单路径与运行目录不一致。")
    if (run_directory.parent / f"{run_name}.building").exists():
        raise ReviewError(f"Batch {run_name} 仍有未封存目录，不能用于人工决定。")
    manifest = _read_json_object(manifest_path)
    if manifest.get("run_name") != run_name:
        raise ReviewError("审核清单引用的 Batch 名称与 run.json 不一致。")
    stored_kind = queue["batch"].get("batch_kind")
    if stored_kind is not None and stored_kind != manifest.get(
        "batch_kind", "standard"
    ):
        raise ReviewError("审核清单引用的处理记录类型与 run.json 不一致。")
    if manifest.get("batch_kind") == "incremental_reprocessing":
        reprocessing = manifest.get("incremental_reprocessing")
        if not isinstance(reprocessing, dict):
            raise ReviewError("重新处理记录缺少原增量 Batch 绑定。")
        for queue_field, manifest_field in (
            ("incremental_run_name", "incremental_run_name"),
            ("previous_processing_run_name", "previous_processing_run_name"),
        ):
            if queue["batch"].get(queue_field) != reprocessing.get(
                manifest_field
            ):
                raise ReviewError(
                    f"审核清单中的 {queue_field} 与重新处理记录不一致。"
                )
    rows = {
        row.get("item_id"): row
        for row in manifest.get("items", [])
        if isinstance(row, dict)
    }
    page_model = _required_string(product, "page_model", "审核清单产品")
    semantic_strategy = _required_string(
        product,
        "semantic_strategy",
        "审核清单产品",
    )
    expected_languages = tuple(item["language"] for item in product["items"])
    if expected_languages != tuple(LANGUAGES):
        raise ReviewError(
            f"产品 {product['product_key']} 的审核材料不是完整中英文两项。"
        )
    for item in product["items"]:
        row = rows.get(item["item_id"])
        if not isinstance(row, dict):
            raise ReviewError(f"Batch 不再包含 {item['item_id']}。")
        if row.get("status") != "passed":
            raise ReviewError(f"{item['item_id']} 当前 Batch 结果不是 passed。")
        if row.get("page_model") != page_model:
            raise ReviewError(
                f"{item['item_id']} 的页面模型与审核清单不一致。"
            )
        if row.get("semantic_strategy") != semantic_strategy:
            raise ReviewError(
                f"{item['item_id']} 的 Strategy 与审核清单不一致。"
            )
        if item.get("page_model", page_model) != page_model:
            raise ReviewError(
                f"{item['item_id']} 保存的页面模型与产品审核清单不一致。"
            )
        if item.get("semantic_strategy", semantic_strategy) != semantic_strategy:
            raise ReviewError(
                f"{item['item_id']} 保存的 Strategy 与产品审核清单不一致。"
            )
        checks = row.get("checks")
        if not isinstance(checks, dict):
            raise ReviewError(f"{item['item_id']} 缺少机器检查记录。")
        source_input = row.get("input")
        if not isinstance(source_input, dict) or source_input.get("status") != "passed":
            raise ReviewError(f"{item['item_id']} 的 Frozen HTML 固定没有通过。")
        for check_name in CHECK_NAMES:
            if not isinstance(checks.get(check_name), dict):
                raise ReviewError(f"{item['item_id']} 缺少 {check_name} 检查记录。")
        expected_paths = {
            "payload_path": _run_artifact_path(
                run_directory,
                _required_string(row, "payload_path", item["item_id"]),
                item["item_id"],
            ),
            "l3a_report_path": _run_artifact_path(
                run_directory,
                _required_string(checks["L3a"], "path", item["item_id"]),
                item["item_id"],
            ),
            "l3b_report_path": _run_artifact_path(
                run_directory,
                _required_string(checks["L3b"], "path", item["item_id"]),
                item["item_id"],
            ),
        }
        if row.get("frozen_html_path") is not None:
            frozen_path = _run_artifact_path(
                run_directory,
                _required_string(
                    row,
                    "frozen_html_path",
                    item["item_id"],
                ),
                f"{item['item_id']} Batch Frozen HTML",
            )
        else:
            frozen_path = _safe_relative_path(
                project_root / "data" / "prod-html",
                _required_string(
                    row,
                    "frozen_relative_path",
                    item["item_id"],
                ),
                label=f"{item['item_id']} Frozen HTML",
            )
        expected_paths["frozen_html_path"] = frozen_path
        for field, expected in expected_paths.items():
            stored = _resolve_presented_path(item[field], project_root)
            if stored != expected:
                raise ReviewError(
                    f"{item['item_id']} 的 {field} 与当前 Batch 不一致。"
                )
            if not stored.is_file():
                raise ReviewError(f"{item['item_id']} 缺少材料：{stored}")
        for check_name, field in (
            ("L3a", "l3a_report_path"),
            ("L3b", "l3b_report_path"),
        ):
            report = _read_json_object(
                _resolve_presented_path(item[field], project_root)
            )
            _validate_passed_check(
                report,
                check_name=check_name,
                product_key=product["product_key"],
                language=item["language"],
            )
        _validate_business_payload(
            catalog,
            product_key=product["product_key"],
            language=item["language"],
            payload_path=_resolve_presented_path(
                item["payload_path"], project_root
            ),
            page_model=page_model,
            semantic_strategy=semantic_strategy,
        )


def _validate_business_payload(
    catalog: ProductCatalog,
    *,
    product_key: str,
    language: str,
    payload_path: Path,
    page_model: str,
    semantic_strategy: str,
) -> None:
    definition = catalog.get_definition(product_key)
    try:
        payload = load_payload(payload_path)
        if page_model == "FlexibleContentPage":
            validate_pricing_payload(
                payload,
                product_key=product_key,
                language=language,
                semantic_strategy=semantic_strategy,
            )
        else:
            assert definition.support_article_type is not None
            validate_support_article_payload(
                payload,
                product_key=product_key,
                expected_slug=definition.slug,
                support_article_type=definition.support_article_type,
            )
    except (PayloadContractError, ValueError) as error:
        raise ReviewError(
            f"{product_key}/{language} 的 Business Payload 契约无效：{error}"
        ) from error


def _load_sealed_run(
    runs_root: Path,
    run_name: str,
) -> tuple[Path, dict[str, Any]]:
    run_directory = runs_root / run_name
    building_directory = runs_root / f"{run_name}.building"
    if building_directory.exists():
        raise ReviewError(f"Batch {run_name} 尚未封存，不能准备人工审核。")
    if not run_directory.is_dir():
        raise ReviewError(f"找不到已封存 Batch：{run_directory}")
    manifest = _read_json_object(run_directory / "run.json")
    if manifest.get("run_name") != run_name:
        raise ReviewError("Batch 目录名与 run.json 中的名称不一致。")
    summary = manifest.get("summary")
    if not isinstance(summary, dict) or summary.get("pending") != 0:
        raise ReviewError(f"Batch {run_name} 仍有未处理项，不能准备人工审核。")
    return run_directory.resolve(), manifest


def _load_review_queue(
    reviews_root: Path,
    review_id: str,
) -> tuple[Path, dict[str, Any]]:
    review_directory = reviews_root / review_id
    if (reviews_root / f"{review_id}.building").exists():
        raise ReviewError(f"审核清单 {review_id} 尚未封存。")
    if not review_directory.is_dir():
        raise ReviewError(f"找不到审核清单：{review_directory}")
    queue = _read_json_object(review_directory / "queue.json")
    if queue.get("review_id") != review_id:
        raise ReviewError("审核目录名与 queue.json 中的审核 ID 不一致。")
    if not isinstance(queue.get("batch"), dict):
        raise ReviewError("审核清单缺少 Batch 引用。")
    if not isinstance(queue.get("products"), list):
        raise ReviewError("审核清单缺少产品列表。")
    if not isinstance(queue.get("not_queued_items"), list):
        raise ReviewError("审核清单缺少未入队处理项对账。")
    return review_directory.resolve(), queue


def _queue_product(queue: dict[str, Any], product_key: str) -> dict[str, Any]:
    for product in queue["products"]:
        if isinstance(product, dict) and product.get("product_key") == product_key:
            if not isinstance(product.get("items"), list):
                raise ReviewError(f"产品 {product_key} 的审核项列表无效。")
            return product
    raise ReviewError(
        f"产品 {product_key} 不在审核清单中；机器检查未通过或该产品不属于当前 Batch。"
    )


def _read_decision(
    path: Path,
    *,
    review_id: str,
    product_key: str,
) -> dict[str, Any]:
    record = _read_json_object(path)
    if record.get("review_id") != review_id:
        raise ReviewError(f"审核决定 {path} 引用了其他审核 ID。")
    if record.get("product_key") != product_key:
        raise ReviewError(f"审核决定 {path} 引用了其他产品。")
    if record.get("decision") not in DECISIONS:
        raise ReviewError(f"审核决定 {path} 的结论无效。")
    _human_text(record.get("reviewer"), field=f"{path} 审核人", single_line=True)
    _human_text(record.get("notes"), field=f"{path} 审核说明")
    return record


def _validate_decision_binding(
    queue: dict[str, Any],
    product: dict[str, Any],
    record: dict[str, Any],
) -> None:
    product_key = product["product_key"]
    if record.get("run_name") != queue["batch"]["run_name"]:
        raise ReviewError(f"产品 {product_key} 的审核决定引用了其他 Batch。")
    for field in ("batch_kind", "incremental_run_name"):
        if field in record and record.get(field) != queue["batch"].get(field):
            raise ReviewError(
                f"产品 {product_key} 的审核决定 {field} 与审核清单不一致。"
            )
    reviewed_items = [
        {
            "item_id": item["item_id"],
            "language": item["language"],
            "frozen_html_path": item["frozen_html_path"],
            "payload_path": item["payload_path"],
            "l3a_report_path": item["l3a_report_path"],
            "l3b_report_path": item["l3b_report_path"],
        }
        for item in product["items"]
    ]
    if record.get("reviewed_items") != reviewed_items:
        raise ReviewError(f"产品 {product_key} 的审核决定与当前审核材料不一致。")
    scope = record.get("inspection_scope")
    if not isinstance(scope, dict):
        raise ReviewError(f"产品 {product_key} 的审核决定缺少检查范围。")
    languages = scope.get("languages")
    materials = scope.get("materials")
    if not isinstance(languages, list) or not isinstance(materials, list):
        raise ReviewError(f"产品 {product_key} 的审核决定检查范围无效。")
    if record["decision"] == "approved":
        if languages != list(LANGUAGES):
            raise ReviewError(f"产品 {product_key} 的批准决定没有覆盖中英文。")
        expected_materials = [MATERIAL_LABELS[value] for value in ALL_MATERIALS]
        if materials != expected_materials:
            raise ReviewError(f"产品 {product_key} 的批准决定没有覆盖全部审核材料。")


def _validate_passed_check(
    report: dict[str, Any],
    *,
    check_name: str,
    product_key: str,
    language: str,
) -> None:
    if report.get("check") != check_name:
        raise ReviewError(f"{product_key}/{language} 的 {check_name} 报告名称不一致。")
    if report.get("product_key") != product_key:
        raise ReviewError(f"{product_key}/{language} 的 {check_name} 报告产品不一致。")
    if report.get("language") != language:
        raise ReviewError(f"{product_key}/{language} 的 {check_name} 报告语言不一致。")
    if report.get("status") != "passed":
        raise ReviewError(f"{product_key}/{language} 的 {check_name} 报告没有通过。")


def _build_material_markdown(
    product: dict[str, Any],
    *,
    material_path: Path,
    project_root: Path,
) -> str:
    lines = [
        f"# {product['display_name']}（{product['product_key']}）人工审核材料",
        "",
        f"- 页面类型：{product['page_model']}",
        f"- Strategy：{product['semantic_strategy']}",
        f"- 双语材料完整：{'是' if product['bilingual_ready'] else '否'}",
        "",
        "批准前请分别打开中文和英文的 Frozen HTML、Business Payload、L3a 与 L3b 报告。",
        "",
        "| 语言 | Frozen HTML | Business Payload | L3a | L3b |",
        "|---|---|---|---|---|",
    ]
    for item in product["items"]:
        links = [
            _markdown_link("打开", item[field], material_path, project_root)
            for field in (
                "frozen_html_path",
                "payload_path",
                "l3a_report_path",
                "l3b_report_path",
            )
        ]
        lines.append(
            f"| {item['language']} | {links[0]} | {links[1]} | {links[2]} | {links[3]} |"
        )
    lines.extend(
        [
            "",
            "机器检查通过只表示结果稳定且 Payload 与 Frozen HTML 对应；它不替代人工批准，也不证明上游内容本身正确。",
            "",
        ]
    )
    return "\n".join(lines)


def _markdown_link(
    label: str,
    presented_path: str,
    material_path: Path,
    project_root: Path,
) -> str:
    target = _resolve_presented_path(presented_path, project_root)
    relative = os.path.relpath(target, start=material_path.parent)
    return f"[{label}](<{Path(relative).as_posix()}>)"


def _root_path(
    project_root: Path,
    value: Path | str | None,
    default_name: str,
    *,
    create: bool = False,
) -> Path:
    root = (
        Path(value).resolve()
        if value is not None
        else (project_root / default_name).resolve()
    )
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def _run_artifact_path(run_directory: Path, relative: str, label: str) -> Path:
    return _safe_relative_path(run_directory, relative, label=label)


def _safe_relative_path(root: Path, relative: str, *, label: str) -> Path:
    candidate = PurePosixPath(relative)
    if candidate.is_absolute() or not candidate.parts or ".." in candidate.parts:
        raise ReviewError(f"{label} 使用了不安全路径：{relative}")
    root = root.resolve()
    path = root.joinpath(*candidate.parts).resolve()
    if not path.is_relative_to(root):
        raise ReviewError(f"{label} 路径越出允许目录：{relative}")
    return path


def _present_path(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _resolve_presented_path(value: Any, project_root: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ReviewError("审核材料路径必须是非空文本。")
    path = Path(value)
    return (path if path.is_absolute() else project_root / path).resolve()


def _validate_readable_id(value: str, *, field: str) -> None:
    if not isinstance(value, str) or not READABLE_ID_PATTERN.fullmatch(value):
        raise ReviewError(f"{field} 必须由小写字母、数字和连字符组成。")


def _required_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReviewError(f"{context} 缺少非空字段 {key}。")
    return value


def _human_text(value: Any, *, field: str, single_line: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewError(f"{field}不能为空。")
    normalized = value.strip()
    if single_line and ("\n" in normalized or "\r" in normalized):
        raise ReviewError(f"{field}必须写在一行内。")
    return normalized


def _ordered_unique(
    values: Sequence[str],
    *,
    allowed: Sequence[str],
    field: str,
) -> tuple[str, ...]:
    if not values:
        raise ReviewError(f"{field}不能为空。")
    unknown = [value for value in values if value not in allowed]
    if unknown:
        raise ReviewError(f"{field}包含未知值：{', '.join(unknown)}。")
    if len(set(values)) != len(values):
        raise ReviewError(f"{field}不能包含重复值。")
    selected = set(values)
    return tuple(value for value in allowed if value in selected)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ReviewError(f"找不到 JSON 文件：{path}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReviewError(f"无法读取 JSON 文件 {path}：{error}") from error
    if not isinstance(value, dict):
        raise ReviewError(f"JSON 文件必须包含对象：{path}")
    return value


def _write_new_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (
        json.dumps(value, ensure_ascii=False, indent=2, separators=(",", ": "))
        + "\n"
    ).encode("utf-8")
    try:
        with path.open("xb") as stream:
            stream.write(data)
    except FileExistsError as error:
        raise ReviewError(f"文件已经存在，不能覆盖：{path}") from error
