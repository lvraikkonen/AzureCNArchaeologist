"""Deterministic product, Category, and full-scope Batch coordination."""

from __future__ import annotations

import json
import os
import re
import tempfile
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.catalog import ProcessingItem, ProductCatalog
from src.core.payload_contract import (
    load_payload,
    payload_json_bytes,
    validate_pricing_payload,
    validate_support_article_payload,
)
from src.core.soft_category import capture_soft_category_usage
from src.extractors.strategy_extractor import (
    extract_processing_item,
    extract_processing_item_with_usage,
    use_processing_inputs,
)
from src.incremental.change_detection import (
    ChangePlan,
    detect_incremental_changes,
)
from src.incremental.product_definition_changes import (
    build_product_definition_baseline,
)
from src.incremental.reprocessing import (
    IncrementalReprocessingError,
    find_reprocessing_chain,
    resolve_incremental_run_reference,
)
from src.incremental.state import (
    IncrementalStateError,
    find_open_incremental_batch,
)
from src.incremental.usage_evidence import (
    UsageEvidenceError,
    build_item_usage_report,
    merge_usage_evidence,
    validate_item_usage_report,
)
from src.machine_checks.l3a import run_l3a
from src.machine_checks.l3b import run_l3b
from src.pipeline.source_input import SourceInput
from src.review import ReviewError, collect_release_review_snapshot


RUN_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TERMINAL_ITEM_STATUSES = {"passed", "failed", "blocked"}
CHECK_NAMES = ("L3a", "L3b")


class PipelineRunError(RuntimeError):
    """A Batch cannot start, continue, or be written safely."""


@dataclass(frozen=True)
class PipelineRunResult:
    run_name: str
    status: str
    run_directory: Path
    manifest: dict[str, Any]

    @property
    def succeeded(self) -> bool:
        return self.status == "passed"


@dataclass(frozen=True)
class IncrementalRunResult:
    """A complete change plan and its optional non-empty Batch result."""

    change_plan: ChangePlan
    batch: PipelineRunResult | None

    @property
    def created_batch(self) -> bool:
        return self.batch is not None

    @property
    def succeeded(self) -> bool:
        return self.batch is None or self.batch.succeeded


def run_product(
    catalog: ProductCatalog,
    *,
    product_key: str,
    run_name: str,
    runs_root: Path | str | None = None,
    parallel_jobs: int = 4,
) -> PipelineRunResult:
    """Compatibility wrapper for one bilingual product Batch."""

    return run_scope(
        catalog,
        product_key=product_key,
        run_name=run_name,
        runs_root=runs_root,
        parallel_jobs=parallel_jobs,
    )


def run_scope(
    catalog: ProductCatalog,
    *,
    run_name: str,
    product_key: str | None = None,
    category: str | None = None,
    all_products: bool = False,
    runs_root: Path | str | None = None,
    parallel_jobs: int = 4,
) -> PipelineRunResult:
    """Create and execute one immutable-plan Batch."""

    _validate_run_name(run_name)
    _validate_parallel_jobs(parallel_jobs)
    items = catalog.select(
        product_key=product_key,
        category=category,
        all_products=all_products,
    )
    selection, selection_value = _selection_description(
        product_key=product_key,
        category=category,
        all_products=all_products,
    )
    return _start_run(
        catalog,
        run_name=run_name,
        items=items,
        selection=selection,
        selection_value=selection_value,
        runs_root=runs_root,
        parallel_jobs=parallel_jobs,
    )


def run_incremental(
    catalog: ProductCatalog,
    *,
    run_name: str,
    runs_root: Path | str | None = None,
    releases_root: Path | str | None = None,
    closures_root: Path | str | None = None,
    parallel_jobs: int = 4,
) -> IncrementalRunResult:
    """Detect changes and run one non-empty bilingual incremental Batch."""

    _validate_run_name(run_name)
    _validate_parallel_jobs(parallel_jobs)
    try:
        open_batch = find_open_incremental_batch(
            catalog,
            runs_root=runs_root,
            releases_root=releases_root,
            closures_root=closures_root,
        )
    except IncrementalStateError as error:
        raise PipelineRunError(str(error)) from error
    if open_batch is not None:
        raise PipelineRunError(
            f"增量 Batch {open_batch.run_name} 尚未结束；未解决产品："
            + "、".join(open_batch.unresolved_product_keys)
            + "。请先完成、恢复或明确结束这些产品。"
        )

    plan = detect_incremental_changes(catalog)
    if not plan.has_changes:
        _acknowledge_no_product_changes(catalog, plan, run_name=run_name)
        return IncrementalRunResult(plan, None)
    batch = _start_run(
        catalog,
        run_name=run_name,
        items=plan.processing_items,
        selection="changed",
        selection_value=None,
        runs_root=runs_root,
        parallel_jobs=parallel_jobs,
        batch_kind="incremental",
        change_plan=plan,
    )
    return IncrementalRunResult(plan, batch)


def reprocess_incremental_product(
    catalog: ProductCatalog,
    *,
    incremental_run_name: str,
    product_key: str,
    reprocessing_run_name: str,
    requested_by: str,
    reason: str,
    rejected_review_id: str | None = None,
    runs_root: Path | str | None = None,
    reviews_root: Path | str | None = None,
    releases_root: Path | str | None = None,
    closures_root: Path | str | None = None,
    parallel_jobs: int = 4,
) -> PipelineRunResult:
    """Add a write-once bilingual processing record to one open Batch."""

    _validate_run_name(incremental_run_name)
    _validate_run_name(reprocessing_run_name)
    _validate_parallel_jobs(parallel_jobs)
    operator = " ".join(requested_by.split())
    explanation = "\n".join(line.rstrip() for line in reason.strip().splitlines())
    if not operator:
        raise PipelineRunError("重新处理必须记录实际发起人。")
    if not explanation:
        raise PipelineRunError("重新处理必须记录可读原因。")

    try:
        open_batch = find_open_incremental_batch(
            catalog,
            runs_root=runs_root,
            releases_root=releases_root,
            closures_root=closures_root,
        )
    except IncrementalStateError as error:
        raise PipelineRunError(str(error)) from error
    if open_batch is None or open_batch.run_name != incremental_run_name:
        raise PipelineRunError(
            f"找不到当前未结束的增量 Batch {incremental_run_name}。"
        )
    if not open_batch.sealed:
        raise PipelineRunError(
            f"增量 Batch {incremental_run_name} 尚未封存，请先恢复原运行。"
        )
    if product_key not in open_batch.unresolved_product_keys:
        raise PipelineRunError(
            f"产品 {product_key} 不是当前 Batch 的未解决产品。"
        )

    root = _runs_root(catalog, runs_root, create=True)
    try:
        chain = find_reprocessing_chain(
            catalog,
            incremental_run_name=incremental_run_name,
            product_key=product_key,
            runs_root=root,
        )
    except IncrementalReprocessingError as error:
        raise PipelineRunError(str(error)) from error
    if not chain.latest_sealed:
        raise PipelineRunError(
            f"重新处理记录 {chain.latest_run_name} 尚未封存，请先恢复它。"
        )
    latest_manifest = _read_json_object(
        chain.latest_run_directory / "run.json"
    )
    items = catalog.select(product_key=product_key)
    _validate_reprocessing_items(
        latest_manifest,
        items=items,
        product_key=product_key,
    )

    latest_rows = [
        row
        for row in latest_manifest.get("items", [])
        if isinstance(row, dict) and row.get("product_key") == product_key
    ]
    machine_passed = (
        len(latest_rows) == len(catalog.languages)
        and all(row.get("status") == "passed" for row in latest_rows)
    )
    rejected_decision_path: Path | None = None
    if machine_passed:
        if rejected_review_id is None:
            raise PipelineRunError(
                "最新双语结果已经通过机器检查；重新处理前必须提供拒绝它的审核 ID。"
            )
        try:
            snapshot = collect_release_review_snapshot(
                catalog,
                review_id=rejected_review_id,
                reviews_root=reviews_root,
            )
        except ReviewError as error:
            raise PipelineRunError(f"无法确认拒绝决定：{error}") from error
        if snapshot.queue["batch"]["run_name"] != chain.latest_run_name:
            raise PipelineRunError(
                "拒绝决定没有引用该产品最新的处理记录。"
            )
        if product_key not in snapshot.rejected_product_keys:
            raise PipelineRunError(
                f"审核 {rejected_review_id} 没有拒绝产品 {product_key}。"
            )
        rejected_decision_path = (
            snapshot.review_directory / "decisions" / f"{product_key}.json"
        )
        reprocessing_basis = "human_rejection"
    else:
        if rejected_review_id is not None:
            raise PipelineRunError(
                "最新结果没有通过机器检查，不应提供人工拒绝审核 ID。"
            )
        reprocessing_basis = "machine_result_not_passed"

    final_directory = root / reprocessing_run_name
    building_directory = root / f"{reprocessing_run_name}.building"
    if final_directory.exists():
        raise PipelineRunError(
            f"重新处理目录已经存在，不能覆盖：{final_directory}"
        )
    if building_directory.exists():
        raise PipelineRunError(
            f"发现未封存的重新处理记录，请使用 resume 继续：{building_directory}"
        )

    parent_directory = open_batch.run_directory
    parent_manifest = _read_json_object(parent_directory / "run.json")
    change_reasons = parent_manifest.get("change_reasons")
    if not isinstance(change_reasons, dict) or not isinstance(
        change_reasons.get(product_key), dict
    ):
        raise PipelineRunError(
            f"原增量 Batch 缺少 {product_key} 的可读变化原因。"
        )
    manifest = _new_manifest(
        run_name=reprocessing_run_name,
        selection="reprocessing",
        selection_value=product_key,
        items=items,
        catalog=catalog,
        parallel_jobs=parallel_jobs,
        batch_kind="incremental_reprocessing",
        update_project_usage_evidence=runs_root is None,
    )
    manifest["change_reasons"] = {
        product_key: json.loads(json.dumps(change_reasons[product_key]))
    }
    manifest["incremental_reprocessing"] = {
        "incremental_run_name": incremental_run_name,
        "incremental_run_directory": _present_path(
            parent_directory,
            catalog.project_root,
        ),
        "incremental_run_manifest_path": _present_path(
            parent_directory / "run.json",
            catalog.project_root,
        ),
        "product_key": product_key,
        "previous_processing_run_name": chain.latest_run_name,
        "previous_processing_run_directory": _present_path(
            chain.latest_run_directory,
            catalog.project_root,
        ),
        "basis": reprocessing_basis,
        "rejected_review_id": rejected_review_id,
        "rejected_decision_path": (
            _present_path(rejected_decision_path, catalog.project_root)
            if rejected_decision_path is not None
            else None
        ),
        "requested_by": operator,
        "reason": explanation,
    }

    building_directory.mkdir(parents=True)
    _save_manifest(building_directory, manifest)
    _prepare_reprocessing_input_files(
        catalog,
        manifest,
        items=items,
        parent_directory=parent_directory,
        parent_manifest=parent_manifest,
        building_directory=building_directory,
    )
    return _execute(
        catalog,
        manifest=manifest,
        items=items,
        building_directory=building_directory,
        final_directory=final_directory,
        parallel_jobs=parallel_jobs,
    )


def _start_run(
    catalog: ProductCatalog,
    *,
    run_name: str,
    items: tuple[ProcessingItem, ...],
    selection: str,
    selection_value: str | None,
    runs_root: Path | str | None,
    parallel_jobs: int,
    batch_kind: str = "standard",
    change_plan: ChangePlan | None = None,
) -> PipelineRunResult:
    root = _runs_root(catalog, runs_root, create=True)
    final_directory = root / run_name
    building_directory = root / f"{run_name}.building"
    if final_directory.exists():
        raise PipelineRunError(f"运行目录已经存在，不能覆盖：{final_directory}")
    if building_directory.exists():
        raise PipelineRunError(
            f"发现尚未封存的运行，请使用 resume 继续：{building_directory}"
        )
    building_directory.mkdir(parents=True)
    manifest = _new_manifest(
        run_name=run_name,
        selection=selection,
        selection_value=selection_value,
        items=items,
        catalog=catalog,
        parallel_jobs=parallel_jobs,
        batch_kind=batch_kind,
        change_plan=change_plan,
        update_project_usage_evidence=runs_root is None,
    )
    _save_manifest(building_directory, manifest)
    if change_plan is not None:
        _write_new_json(
            building_directory / "change-plan.json",
            change_plan.as_dict(),
        )
        _prepare_incremental_input_files(
            catalog,
            manifest,
            building_directory=building_directory,
        )
    return _execute(
        catalog,
        manifest=manifest,
        items=items,
        building_directory=building_directory,
        final_directory=final_directory,
        parallel_jobs=parallel_jobs,
    )


def _prepare_incremental_input_files(
    catalog: ProductCatalog,
    manifest: dict[str, Any],
    *,
    building_directory: Path,
) -> None:
    """Fix shared configuration before any incremental extraction starts."""

    source_config = (
        catalog.project_root
        / "data"
        / "current_prod_html"
        / "soft-category.json"
    )
    content = _read_stable_file(source_config, label="上游 soft-category.json")
    batch_config = (
        building_directory / "inputs" / "configs" / "soft-category.json"
    )
    _write_new_bytes(batch_config, content)
    definition_baseline = build_product_definition_baseline(
        catalog,
        source_run_name=str(manifest["run_name"]),
    )
    batch_definitions = (
        building_directory
        / "inputs"
        / "configs"
        / "product-definitions.json"
    )
    _write_new_json(batch_definitions, definition_baseline)
    manifest["fixed_inputs"] = {
        "frozen_html_root": "inputs/prod-html",
        "soft_category_path": "inputs/configs/soft-category.json",
        "product_definitions_path": "inputs/configs/product-definitions.json",
    }
    _save_manifest(building_directory, manifest)

    _atomic_write_bytes(
        catalog.project_root / "data" / "configs" / "soft-category.json",
        content,
    )
    _write_replace_json(
        catalog.project_root / "data" / "state" / "product-definitions.json",
        definition_baseline,
    )


def _prepare_reprocessing_input_files(
    catalog: ProductCatalog,
    manifest: dict[str, Any],
    *,
    items: tuple[ProcessingItem, ...],
    parent_directory: Path,
    parent_manifest: dict[str, Any],
    building_directory: Path,
) -> None:
    """Copy the original Batch inputs without advancing project baselines."""

    fixed = parent_manifest.get("fixed_inputs")
    if not isinstance(fixed, dict):
        raise PipelineRunError("原增量 Batch 缺少固定输入路径。")
    parent_frozen_root = _safe_run_relative_path(
        parent_directory,
        fixed.get("frozen_html_root"),
        label="原 Batch Frozen HTML 根目录",
    )
    parent_soft_category = _safe_run_relative_path(
        parent_directory,
        fixed.get("soft_category_path"),
        label="原 Batch soft-category.json",
    )
    parent_definitions = _safe_run_relative_path(
        parent_directory,
        fixed.get("product_definitions_path"),
        label="原 Batch Product Definition 投影",
    )
    target_soft_category = (
        building_directory / "inputs" / "configs" / "soft-category.json"
    )
    target_definitions = (
        building_directory
        / "inputs"
        / "configs"
        / "product-definitions.json"
    )
    _copy_or_confirm_new_bytes(parent_soft_category, target_soft_category)
    _copy_or_confirm_new_bytes(parent_definitions, target_definitions)

    stored = _manifest_items_by_id(manifest)
    for item in items:
        source = parent_frozen_root.joinpath(*item.frozen_relative_path.parts)
        relative = Path(
            "inputs", "prod-html", *item.frozen_relative_path.parts
        )
        target = building_directory / relative
        byte_count = _copy_or_confirm_new_bytes(source, target)
        row = stored[_item_id(item)]
        row["frozen_html_path"] = relative.as_posix()
        row["input"].update(
            {
                "status": "passed",
                "action": "reused_incremental_batch_input",
                "byte_count": byte_count,
                "error": None,
            }
        )
    manifest["fixed_inputs"] = {
        "frozen_html_root": "inputs/prod-html",
        "soft_category_path": "inputs/configs/soft-category.json",
        "product_definitions_path": "inputs/configs/product-definitions.json",
    }
    _refresh_manifest(manifest)
    _save_manifest(building_directory, manifest)


def _validate_reprocessing_items(
    previous_manifest: dict[str, Any],
    *,
    items: tuple[ProcessingItem, ...],
    product_key: str,
) -> None:
    """Keep Product Definition inputs fixed across reprocessing records."""

    previous_rows = {
        row.get("item_id"): row
        for row in previous_manifest.get("items", [])
        if isinstance(row, dict) and row.get("product_key") == product_key
    }
    expected_ids = [_item_id(item) for item in items]
    if list(previous_rows) != expected_ids:
        raise PipelineRunError(
            f"最新处理记录没有 {product_key} 的完整有序中英文两项。"
        )
    for item in items:
        expected = {
            "product_key": item.product_key,
            "language": item.language,
            "page_model": item.page_model,
            "semantic_strategy": item.semantic_strategy,
            "source_relative_path": item.source_relative_path.as_posix(),
            "frozen_relative_path": item.frozen_relative_path.as_posix(),
        }
        row = previous_rows[_item_id(item)]
        changed = [
            field for field, value in expected.items() if row.get(field) != value
        ]
        if changed:
            raise PipelineRunError(
                f"{item.product_key}/{item.language} 的处理相关 Product Definition "
                "已经变化，不能作为同一固定输入的重新处理："
                + "、".join(changed)
                + "。"
            )


def _acknowledge_no_product_changes(
    catalog: ProductCatalog,
    plan: ChangePlan,
    *,
    run_name: str,
) -> None:
    """Advance harmless textual configuration changes without an empty Batch."""

    soft_category = plan.soft_category
    if soft_category is None:
        raise PipelineRunError("完整变化计划缺少 soft-category 比较结果。")
    if soft_category.text_changed:
        source = (
            catalog.project_root
            / "data"
            / "current_prod_html"
            / "soft-category.json"
        )
        _atomic_write_bytes(
            catalog.project_root / "data" / "configs" / "soft-category.json",
            _read_stable_file(source, label="上游 soft-category.json"),
        )
    _write_replace_json(
        catalog.project_root / "data" / "state" / "product-definitions.json",
        build_product_definition_baseline(
            catalog,
            source_run_name=f"{run_name}-no-product-changes",
        ),
    )


def resume_run(
    catalog: ProductCatalog,
    *,
    run_name: str,
    runs_root: Path | str | None = None,
    parallel_jobs: int = 4,
) -> PipelineRunResult:
    """Continue pending work without regenerating a completed Payload."""

    _validate_run_name(run_name)
    _validate_parallel_jobs(parallel_jobs)
    root = _runs_root(catalog, runs_root)
    final_directory = root / run_name
    building_directory = root / f"{run_name}.building"
    if final_directory.exists():
        raise PipelineRunError(f"运行 {run_name} 已封存，不能再继续。")
    if not building_directory.is_dir():
        raise PipelineRunError(f"找不到可继续的运行：{building_directory}")
    manifest = _read_json_object(building_directory / "run.json")
    items = _items_for_stored_plan(catalog, manifest)
    if manifest.get("batch_kind") == "incremental_reprocessing" and any(
        row.get("input", {}).get("status") == "pending"
        for row in manifest.get("items", [])
        if isinstance(row, dict)
    ):
        try:
            reference = resolve_incremental_run_reference(
                catalog,
                processing_run_directory=building_directory,
                processing_manifest=manifest,
            )
        except IncrementalReprocessingError as error:
            raise PipelineRunError(str(error)) from error
        _prepare_reprocessing_input_files(
            catalog,
            manifest,
            items=items,
            parent_directory=reference.run_directory,
            parent_manifest=reference.manifest,
            building_directory=building_directory,
        )
    _verify_completed_inputs_unchanged(
        catalog,
        manifest,
        items,
        building_directory=building_directory,
    )
    manifest["parallel_jobs"] = parallel_jobs
    manifest["resume_count"] = int(manifest.get("resume_count", 0)) + 1
    _save_manifest(building_directory, manifest)
    return _execute(
        catalog,
        manifest=manifest,
        items=items,
        building_directory=building_directory,
        final_directory=final_directory,
        parallel_jobs=parallel_jobs,
    )


def read_run_status(
    catalog: ProductCatalog,
    *,
    run_name: str,
    runs_root: Path | str | None = None,
) -> dict[str, Any]:
    """Read a sealed or in-progress Batch without changing it."""

    _validate_run_name(run_name)
    root = _runs_root(catalog, runs_root)
    final_directory = root / run_name
    building_directory = root / f"{run_name}.building"
    if final_directory.is_dir() and building_directory.exists():
        raise PipelineRunError(
            f"运行 {run_name} 同时存在封存目录和未完成目录，需要人工检查。"
        )
    if final_directory.is_dir():
        directory = final_directory
        sealed = True
    elif building_directory.is_dir():
        directory = building_directory
        sealed = False
    else:
        raise PipelineRunError(f"找不到运行 {run_name}。")
    manifest = _read_json_object(directory / "run.json")
    return {
        "run_name": run_name,
        "status": manifest.get("status", "unknown"),
        "sealed": sealed,
        "resumable": not sealed,
        "run_directory": directory.as_posix(),
        "scope": manifest.get("scope", {}),
        "summary": manifest.get("summary", {}),
        "stages": manifest.get("stages", {}),
    }


def _execute(
    catalog: ProductCatalog,
    *,
    manifest: dict[str, Any],
    items: tuple[ProcessingItem, ...],
    building_directory: Path,
    final_directory: Path,
    parallel_jobs: int,
) -> PipelineRunResult:
    _freeze_pending_inputs(
        catalog, manifest, items, building_directory=building_directory
    )
    _reconcile_payloads(
        catalog, manifest, items, building_directory=building_directory
    )
    _run_extraction_stage(
        catalog,
        manifest,
        items,
        building_directory=building_directory,
        parallel_jobs=parallel_jobs,
    )
    _write_unavailable_check_reports(
        manifest, building_directory=building_directory
    )
    _reconcile_checks(manifest, building_directory=building_directory)
    _run_machine_checks(
        catalog,
        manifest,
        items,
        building_directory=building_directory,
        parallel_jobs=parallel_jobs,
    )
    _merge_successful_usage_evidence(
        catalog,
        manifest,
        building_directory=building_directory,
    )
    _refresh_manifest(manifest, final=True)
    if manifest["summary"]["pending"]:
        _save_manifest(building_directory, manifest)
        raise PipelineRunError("运行结束时仍有未对账的处理项。")
    report = _build_report(manifest)
    manifest["report_path"] = "report.json"
    _save_manifest(building_directory, manifest)
    report_path = building_directory / "report.json"
    if report_path.exists():
        if _read_json_object(report_path) != report:
            raise PipelineRunError("已存在的 Batch 报告与当前对账结果不一致。")
    else:
        _write_new_json(report_path, report)
    try:
        building_directory.rename(final_directory)
    except OSError as error:
        raise PipelineRunError(
            f"无法封存运行目录 {final_directory}：{error}"
        ) from error
    return PipelineRunResult(
        run_name=str(manifest["run_name"]),
        status=str(manifest["status"]),
        run_directory=final_directory,
        manifest=manifest,
    )


def _freeze_pending_inputs(
    catalog: ProductCatalog,
    manifest: dict[str, Any],
    items: tuple[ProcessingItem, ...],
    *,
    building_directory: Path,
) -> None:
    stored = _manifest_items_by_id(manifest)
    pending_products = {
        item.product_key
        for item in items
        if stored[_item_id(item)]["input"]["status"] == "pending"
    }
    pending_items = tuple(
        item for item in items if item.product_key in pending_products
    )
    if not pending_items:
        return
    report = SourceInput(catalog).freeze(pending_items)
    current_by_pair = {
        (item.product_key, item.language): item for item in items
    }
    for product_result in report.results:
        product_items = [
            item for item in items if item.product_key == product_result.product_key
        ]
        if product_result.status == "blocked":
            reason = product_result.error or "双语输入无法完整固定。"
            for item in product_items:
                row = stored[_item_id(item)]
                row["input"].update({"status": "blocked", "error": reason})
                row["extraction"].update(
                    {"status": "not_run", "error": "双语输入阻断。"}
                )
                for check in row["checks"].values():
                    check["status"] = "not_run"
            continue
        for frozen in product_result.items:
            item = current_by_pair[(frozen.product_key, frozen.language)]
            row = stored[_item_id(item)]
            if manifest.get("batch_kind") == "incremental":
                global_frozen = (
                    catalog.project_root / "data" / "prod-html"
                ).joinpath(*item.frozen_relative_path.parts)
                relative = Path(
                    "inputs", "prod-html", *item.frozen_relative_path.parts
                )
                batch_frozen = building_directory / relative
                _copy_or_confirm_new_bytes(global_frozen, batch_frozen)
                row["frozen_html_path"] = relative.as_posix()
            row["input"].update(
                {
                    "status": "passed",
                    "action": frozen.action,
                    "byte_count": frozen.byte_count,
                    "error": None,
                }
            )
    _refresh_manifest(manifest)
    _save_manifest(building_directory, manifest)


def _reconcile_payloads(
    catalog: ProductCatalog,
    manifest: dict[str, Any],
    items: tuple[ProcessingItem, ...],
    *,
    building_directory: Path,
) -> None:
    stored = _manifest_items_by_id(manifest)
    frozen_root, soft_category_path = _fixed_processing_inputs(
        catalog,
        manifest,
        building_directory=building_directory,
    )
    changed = False
    for item in items:
        row = stored[_item_id(item)]
        if row["input"]["status"] != "passed":
            continue
        if row["extraction"]["status"] not in {"pending", "passed"}:
            continue
        if (
            row["extraction"]["status"] == "passed"
            and row["configuration_usage"]["status"] == "passed"
        ):
            continue
        payload_path = building_directory / row["payload_path"]
        usage_path = building_directory / row["configuration_usage"]["path"]
        if not payload_path.exists() and not usage_path.exists():
            continue
        try:
            result = extract_processing_item_with_usage(
                catalog,
                item,
                frozen_root=frozen_root,
                soft_category_path=soft_category_path,
            )
            expected_usage = build_item_usage_report(
                item,
                result.soft_category_lookups,
            )
            if payload_path.exists():
                payload = load_payload(payload_path)
                _validate_persisted_payload(catalog, item, payload)
                if payload != result.payload:
                    raise PipelineRunError(
                        "恢复时已写 Payload 与相同输入重新抽取结果不同。"
                    )
            else:
                _write_new_json(payload_path, result.payload)
            if usage_path.exists():
                usage = _read_json_object(usage_path)
                validate_item_usage_report(usage, item=item)
                if usage != expected_usage:
                    raise PipelineRunError(
                        "恢复时已写配置查询报告与重新抽取结果不同。"
                    )
            else:
                _write_new_json(usage_path, expected_usage)
        except Exception as error:
            row["extraction"].update(
                {
                    "status": "blocked",
                    "error": f"恢复时发现已写 Payload 无效：{error}",
                }
            )
            row["configuration_usage"].update(
                {"status": "blocked", "error": str(error)}
            )
        else:
            row["extraction"].update(
                {"status": "passed", "error": None}
            )
            row["configuration_usage"].update(
                {"status": "passed", "error": None}
            )
        changed = True
    if changed:
        _refresh_manifest(manifest)
        _save_manifest(building_directory, manifest)


def _run_extraction_stage(
    catalog: ProductCatalog,
    manifest: dict[str, Any],
    items: tuple[ProcessingItem, ...],
    *,
    building_directory: Path,
    parallel_jobs: int,
) -> None:
    stored = _manifest_items_by_id(manifest)
    frozen_root, soft_category_path = _fixed_processing_inputs(
        catalog,
        manifest,
        building_directory=building_directory,
    )
    pending = [
        item
        for item in items
        if stored[_item_id(item)]["input"]["status"] == "passed"
        and stored[_item_id(item)]["extraction"]["status"] == "pending"
    ]
    if not pending:
        return
    futures: dict[Future[None], ProcessingItem] = {}
    with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
        for item in pending:
            payload_path = (
                building_directory / stored[_item_id(item)]["payload_path"]
            )
            futures[
                executor.submit(
                    _extract_with_fixed_inputs,
                    catalog,
                    item,
                    payload_path,
                    frozen_root,
                    soft_category_path,
                )
            ] = item
        for future in as_completed(futures):
            item = futures[future]
            row = stored[_item_id(item)]
            try:
                future.result()
            except Exception as error:
                row["extraction"].update(
                    {"status": "blocked", "error": str(error)}
                )
                row["configuration_usage"].update(
                    {"status": "blocked", "error": str(error)}
                )
            else:
                row["extraction"].update(
                    {"status": "passed", "error": None}
                )
                row["configuration_usage"].update(
                    {"status": "passed", "error": None}
                )
            _refresh_manifest(manifest)
            _save_manifest(building_directory, manifest)


def _extract_write_and_reload(
    catalog: ProductCatalog,
    item: ProcessingItem,
    payload_path: Path,
) -> None:
    with capture_soft_category_usage() as recorder:
        payload = extract_processing_item(catalog, item)
    _write_new_json(payload_path, payload)
    usage_path = _usage_path_for_payload(payload_path)
    usage = build_item_usage_report(item, recorder.lookups)
    _write_new_json(usage_path, usage)
    persisted = load_payload(payload_path)
    _validate_persisted_payload(catalog, item, persisted)
    validate_item_usage_report(_read_json_object(usage_path), item=item)


def _extract_with_fixed_inputs(
    catalog: ProductCatalog,
    item: ProcessingItem,
    payload_path: Path,
    frozen_root: Path,
    soft_category_path: Path,
) -> None:
    with use_processing_inputs(
        frozen_root=frozen_root,
        soft_category_path=soft_category_path,
    ):
        _extract_write_and_reload(catalog, item, payload_path)


def _usage_path_for_payload(payload_path: Path) -> Path:
    payload_root = next(
        (parent for parent in payload_path.parents if parent.name == "payloads"),
        None,
    )
    if payload_root is None:
        raise PipelineRunError(
            f"Payload 路径不在 Batch payloads 目录中：{payload_path}。"
        )
    relative = payload_path.relative_to(payload_root)
    return (
        payload_root.parent
        / "diagnostics"
        / relative.parent
        / f"{payload_path.stem}.soft-category-usage.json"
    )


def _reconcile_checks(
    manifest: dict[str, Any], *, building_directory: Path
) -> None:
    changed = False
    for row in manifest["items"]:
        if row["extraction"]["status"] != "passed":
            continue
        for check_name in CHECK_NAMES:
            check = row["checks"][check_name]
            if check["status"] != "pending":
                continue
            path = building_directory / check["path"]
            if not path.exists():
                continue
            try:
                report = _read_json_object(path)
                _validate_check_report(report, row, check_name)
            except Exception as error:
                check.update(
                    {
                        "status": "blocked",
                        "error": f"恢复时发现已写检查报告无效：{error}",
                    }
                )
            else:
                check.update(
                    {"status": report["status"], "error": report.get("error")}
                )
            changed = True
    if changed:
        _refresh_manifest(manifest)
        _save_manifest(building_directory, manifest)


def _write_unavailable_check_reports(
    manifest: dict[str, Any], *, building_directory: Path
) -> None:
    """Give items without a Payload explicit blocked machine-check results."""

    changed = False
    for row in manifest["items"]:
        if row["extraction"]["status"] == "passed":
            continue
        if row["input"]["status"] == "pending" or row["extraction"]["status"] == "pending":
            continue
        reason = (
            row["input"].get("error")
            or row["extraction"].get("error")
            or "没有可供机器检查读取的正式 Payload。"
        )
        for check_name in CHECK_NAMES:
            check = row["checks"][check_name]
            if check["status"] not in {"pending", "not_run"}:
                continue
            report = {
                "check": check_name,
                "status": "blocked",
                "product_key": row["product_key"],
                "language": row["language"],
                "error": f"抽取阶段未产生正式 Payload：{reason}",
            }
            path = building_directory / check["path"]
            if path.exists():
                existing = _read_json_object(path)
                _validate_check_report(existing, row, check_name)
                report = existing
            else:
                _write_new_json(path, report)
            check.update(
                {"status": report["status"], "error": report.get("error")}
            )
            changed = True
    if changed:
        _refresh_manifest(manifest)
        _save_manifest(building_directory, manifest)


def _run_machine_checks(
    catalog: ProductCatalog,
    manifest: dict[str, Any],
    items: tuple[ProcessingItem, ...],
    *,
    building_directory: Path,
    parallel_jobs: int,
) -> None:
    stored = _manifest_items_by_id(manifest)
    frozen_root, soft_category_path = _fixed_processing_inputs(
        catalog,
        manifest,
        building_directory=building_directory,
    )
    futures: dict[Future[dict[str, Any]], tuple[ProcessingItem, str]] = {}
    with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
        for item in items:
            row = stored[_item_id(item)]
            if row["extraction"]["status"] != "passed":
                continue
            for check_name in CHECK_NAMES:
                if row["checks"][check_name]["status"] != "pending":
                    continue
                futures[
                    executor.submit(
                        _run_one_check,
                        catalog,
                        item,
                        check_name,
                        building_directory / row["payload_path"],
                        frozen_root,
                        soft_category_path,
                    )
                ] = (item, check_name)
        for future in as_completed(futures):
            item, check_name = futures[future]
            row = stored[_item_id(item)]
            try:
                report = future.result()
                _validate_check_report(report, row, check_name)
            except Exception as error:
                report = {
                    "check": check_name,
                    "status": "blocked",
                    "product_key": item.product_key,
                    "language": item.language,
                    "error": f"机器检查异常停止：{error}",
                }
            check_path = building_directory / row["checks"][check_name]["path"]
            _write_new_json(check_path, report)
            row["checks"][check_name].update(
                {"status": report["status"], "error": report.get("error")}
            )
            _refresh_manifest(manifest)
            _save_manifest(building_directory, manifest)


def _run_one_check(
    catalog: ProductCatalog,
    item: ProcessingItem,
    check_name: str,
    payload_path: Path,
    frozen_root: Path,
    soft_category_path: Path,
) -> dict[str, Any]:
    if check_name == "L3a":
        with use_processing_inputs(
            frozen_root=frozen_root,
            soft_category_path=soft_category_path,
        ):
            return run_l3a(
                payload_path=payload_path,
                extract_again=lambda: extract_processing_item(catalog, item),
                product_key=item.product_key,
                language=item.language,
            )
    definition = catalog.get_definition(item.product_key)
    frozen_path = frozen_root.joinpath(
        *item.frozen_relative_path.parts
    )
    return run_l3b(
        frozen_html_path=frozen_path,
        payload_path=payload_path,
        product_key=item.product_key,
        language=item.language,
        page_model=definition.page_model,
        semantic_strategy=item.semantic_strategy,
        soft_category_path=soft_category_path,
        page_global_source_boundary=definition.page_global_source_boundary,
    )


def _validate_check_report(
    report: dict[str, Any], row: dict[str, Any], check_name: str
) -> None:
    if (
        report.get("check") != check_name
        or report.get("product_key") != row["product_key"]
        or report.get("language") != row["language"]
        or report.get("status") not in TERMINAL_ITEM_STATUSES
    ):
        raise PipelineRunError(
            f"{row['item_id']} 的 {check_name} 报告身份或状态不正确。"
        )


def _validate_persisted_payload(
    catalog: ProductCatalog,
    item: ProcessingItem,
    payload: dict[str, Any],
) -> None:
    definition = catalog.get_definition(item.product_key)
    if definition.page_model == "FlexibleContentPage":
        validate_pricing_payload(
            payload,
            product_key=item.product_key,
            language=item.language,
            semantic_strategy=item.semantic_strategy,
        )
        return
    if definition.support_article_type is None:
        raise PipelineRunError(
            f"Support Article {item.product_key} 缺少文章类型。"
        )
    validate_support_article_payload(
        payload,
        product_key=item.product_key,
        expected_slug=definition.slug,
        support_article_type=definition.support_article_type,
    )


def _new_manifest(
    *,
    run_name: str,
    selection: str,
    selection_value: str | None,
    items: tuple[ProcessingItem, ...],
    catalog: ProductCatalog,
    parallel_jobs: int,
    batch_kind: str = "standard",
    change_plan: ChangePlan | None = None,
    update_project_usage_evidence: bool = False,
) -> dict[str, Any]:
    product_keys = list(dict.fromkeys(item.product_key for item in items))
    scope: dict[str, Any] = {
        "selection": selection,
        "product_keys": product_keys,
        "languages": list(catalog.languages),
    }
    if selection_value is not None:
        scope[selection] = selection_value
    manifest = {
        "schema_version": "1.1",
        "run_name": run_name,
        "batch_kind": batch_kind,
        "status": "running",
        "scope": scope,
        "parallel_jobs": parallel_jobs,
        "update_project_usage_evidence": update_project_usage_evidence,
        "resume_count": 0,
        "stages": {
            "source_input": "pending",
            "extraction": "pending",
            "persisted_payload_read": "pending",
            "configuration_usage": "pending",
            "machine_checks": "pending",
            "machine_check_execution": "L3a 与 L3b 并列执行",
        },
        "summary": {},
        "items": [_new_manifest_item(catalog, item) for item in items],
    }
    if change_plan is not None:
        manifest["change_plan_path"] = "change-plan.json"
        manifest["change_summary"] = change_plan.as_dict()["summary"]
        manifest["change_reasons"] = {
            product.product_key: {
                "change_sources": list(product.change_sources),
                "changed_languages": list(product.changed_languages),
                "html_changes": [
                    change.as_dict() for change in product.changes
                ],
                "soft_category_reasons": list(
                    product.soft_category_reasons
                ),
                "product_definition_reasons": list(
                    product.product_definition_reasons
                ),
                "bilingual_processing_reason": (
                    product.bilingual_processing_reason
                ),
            }
            for product in change_plan.affected_products
        }
    _refresh_manifest(manifest)
    return manifest


def _new_manifest_item(
    catalog: ProductCatalog, item: ProcessingItem
) -> dict[str, Any]:
    definition = catalog.get_definition(item.product_key)
    category_parts = _artifact_category_parts(definition)
    payload_path = Path(
        "payloads", item.language, *category_parts, f"{item.product_key}.json"
    )
    check_root = Path("checks", item.language, *category_parts)
    usage_path = Path(
        "diagnostics",
        item.language,
        *category_parts,
        f"{item.product_key}.soft-category-usage.json",
    )
    return {
        "item_id": _item_id(item),
        "product_key": item.product_key,
        "language": item.language,
        "page_model": item.page_model,
        "semantic_strategy": item.semantic_strategy,
        "source_relative_path": item.source_relative_path.as_posix(),
        "frozen_relative_path": item.frozen_relative_path.as_posix(),
        "status": "pending",
        "error": None,
        "input": {
            "status": "pending",
            "action": None,
            "byte_count": None,
            "error": None,
        },
        "extraction": {"status": "pending", "error": None},
        "configuration_usage": {
            "status": "pending",
            "path": usage_path.as_posix(),
            "error": None,
        },
        "payload_path": payload_path.as_posix(),
        "checks": {
            check_name: {
                "status": "pending",
                "path": (
                    check_root / f"{item.product_key}.{check_name.lower()}.json"
                ).as_posix(),
                "error": None,
            }
            for check_name in CHECK_NAMES
        },
    }


def _refresh_manifest(manifest: dict[str, Any], *, final: bool = False) -> None:
    for row in manifest["items"]:
        status, reason = _derive_item_status(row)
        row["status"] = status
        row["error"] = reason
    summary = {
        "planned": len(manifest["items"]),
        "passed": sum(row["status"] == "passed" for row in manifest["items"]),
        "failed": sum(row["status"] == "failed" for row in manifest["items"]),
        "blocked": sum(row["status"] == "blocked" for row in manifest["items"]),
        "pending": sum(row["status"] == "pending" for row in manifest["items"]),
    }
    product_results = _product_results(manifest["items"])
    summary.update(
        {
            "planned_products": len(product_results),
            "passed_products": sum(
                row["status"] == "passed" for row in product_results
            ),
            "failed_products": sum(
                row["status"] == "failed" for row in product_results
            ),
            "blocked_products": sum(
                row["status"] == "blocked" for row in product_results
            ),
            "pending_products": sum(
                row["status"] == "pending" for row in product_results
            ),
        }
    )
    manifest["summary"] = summary
    manifest["stages"].update(_derive_stage_statuses(manifest["items"]))
    if final:
        manifest["status"] = (
            "passed"
            if summary["passed"] == summary["planned"]
            else "completed_with_issues"
        )
    elif summary["pending"]:
        manifest["status"] = "running"


def _derive_item_status(row: dict[str, Any]) -> tuple[str, str | None]:
    input_status = row["input"]["status"]
    if input_status == "blocked":
        return "blocked", row["input"].get("error")
    if input_status != "passed":
        return "pending", None
    extraction_status = row["extraction"]["status"]
    if extraction_status in {"blocked", "failed"}:
        return "blocked", row["extraction"].get("error")
    if extraction_status != "passed":
        return "pending", None
    usage_status = row["configuration_usage"]["status"]
    if usage_status == "blocked":
        return "blocked", row["configuration_usage"].get("error")
    if usage_status != "passed":
        return "pending", None
    check_statuses = [row["checks"][name]["status"] for name in CHECK_NAMES]
    if any(status in {"pending", "not_run"} for status in check_statuses):
        return "pending", None
    if "blocked" in check_statuses:
        blocked = next(
            name
            for name in CHECK_NAMES
            if row["checks"][name]["status"] == "blocked"
        )
        return (
            "blocked",
            row["checks"][blocked].get("error") or f"{blocked} 阻断。",
        )
    if "failed" in check_statuses:
        failed = [
            name
            for name in CHECK_NAMES
            if row["checks"][name]["status"] == "failed"
        ]
        return "failed", f"{'、'.join(failed)} 未通过。"
    if check_statuses == ["passed", "passed"]:
        return "passed", None
    return "blocked", "机器检查返回了未知状态。"


def _derive_stage_statuses(items: list[dict[str, Any]]) -> dict[str, str]:
    input_status = _stage_status([row["input"]["status"] for row in items])
    extraction_rows = [
        row for row in items if row["input"]["status"] == "passed"
    ]
    extraction_status = _stage_status(
        [row["extraction"]["status"] for row in extraction_rows]
    )
    usage_status = _stage_status(
        [row["configuration_usage"]["status"] for row in extraction_rows]
    )
    check_status = _stage_status(
        [
            row["checks"][name]["status"]
            for row in items
            for name in CHECK_NAMES
        ]
    )
    return {
        "source_input": input_status,
        "extraction": extraction_status,
        "persisted_payload_read": extraction_status,
        "configuration_usage": usage_status,
        "machine_checks": check_status,
    }


def _merge_successful_usage_evidence(
    catalog: ProductCatalog,
    manifest: dict[str, Any],
    *,
    building_directory: Path,
) -> None:
    if not manifest.get("update_project_usage_evidence", False):
        return
    reports: list[dict[str, Any]] = []
    for row in manifest["items"]:
        if (
            row["extraction"]["status"] != "passed"
            or row["configuration_usage"]["status"] != "passed"
        ):
            continue
        path = building_directory / row["configuration_usage"]["path"]
        reports.append(_read_json_object(path))
    if not reports:
        return
    try:
        merge_usage_evidence(catalog, reports)
    except UsageEvidenceError as error:
        raise PipelineRunError(
            f"无法更新实际配置查询记录：{error}"
        ) from error


def _stage_status(statuses: list[str]) -> str:
    if not statuses:
        return "not_run"
    if any(status == "pending" for status in statuses):
        return "in_progress"
    if all(status == "passed" for status in statuses):
        return "passed"
    return "completed_with_issues"


def _build_report(manifest: dict[str, Any]) -> dict[str, Any]:
    items = manifest["items"]
    return {
        "run_name": manifest["run_name"],
        "status": manifest["status"],
        "scope": manifest["scope"],
        "summary": manifest["summary"],
        "plan": [row["item_id"] for row in items],
        "passed_items": [
            row["item_id"] for row in items if row["status"] == "passed"
        ],
        "failed_items": [
            {"item_id": row["item_id"], "reason": row["error"]}
            for row in items
            if row["status"] == "failed"
        ],
        "blocked_items": [
            {"item_id": row["item_id"], "reason": row["error"]}
            for row in items
            if row["status"] == "blocked"
        ],
        "products": _product_results(items),
    }


def _product_results(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in items:
        grouped.setdefault(row["product_key"], []).append(row)
    results: list[dict[str, Any]] = []
    for product_key, rows in grouped.items():
        statuses = [row["status"] for row in rows]
        if "pending" in statuses:
            status = "pending"
        elif "blocked" in statuses:
            status = "blocked"
        elif "failed" in statuses:
            status = "failed"
        elif statuses and all(item == "passed" for item in statuses):
            status = "passed"
        else:
            status = "blocked"
        result: dict[str, Any] = {
            "product_key": product_key,
            "status": status,
            "items": [
                {"language": row["language"], "status": row["status"]}
                for row in rows
            ],
        }
        reasons = [row["error"] for row in rows if row.get("error")]
        if reasons:
            result["reasons"] = list(dict.fromkeys(reasons))
        results.append(result)
    return results


def _items_for_stored_plan(
    catalog: ProductCatalog, manifest: dict[str, Any]
) -> tuple[ProcessingItem, ...]:
    scope = manifest.get("scope")
    if not isinstance(scope, dict) or not isinstance(
        scope.get("product_keys"), list
    ):
        raise PipelineRunError("未完成运行的 scope 无法读取。")
    items = tuple(
        item
        for key in scope["product_keys"]
        for item in catalog.select(product_key=str(key))
    )
    stored_rows = manifest.get("items")
    if not isinstance(stored_rows, list) or len(stored_rows) != len(items):
        raise PipelineRunError("未完成运行的处理计划数量已改变。")
    for item, row in zip(items, stored_rows):
        expected = {
            "item_id": _item_id(item),
            "product_key": item.product_key,
            "language": item.language,
            "page_model": item.page_model,
            "semantic_strategy": item.semantic_strategy,
            "source_relative_path": item.source_relative_path.as_posix(),
            "frozen_relative_path": item.frozen_relative_path.as_posix(),
        }
        if not isinstance(row, dict) or any(
            row.get(key) != value for key, value in expected.items()
        ):
            raise PipelineRunError(
                f"当前产品配置与未完成计划 {expected['item_id']} 不一致；"
                "请使用新的 run-name 重新运行。"
            )
    return items


def _verify_completed_inputs_unchanged(
    catalog: ProductCatalog,
    manifest: dict[str, Any],
    items: tuple[ProcessingItem, ...],
    *,
    building_directory: Path,
) -> None:
    stored = _manifest_items_by_id(manifest)
    if _uses_batch_fixed_inputs(manifest):
        frozen_root, soft_category_path = _fixed_processing_inputs(
            catalog,
            manifest,
            building_directory=building_directory,
        )
        if not soft_category_path.is_file():
            raise PipelineRunError(
                "未完成增量 Batch 缺少固定的 soft-category.json。"
            )
        for item in items:
            if stored[_item_id(item)]["input"]["status"] != "passed":
                continue
            frozen = frozen_root.joinpath(*item.frozen_relative_path.parts)
            if frozen.is_symlink() or not frozen.is_file():
                raise PipelineRunError(
                    f"未完成增量 Batch 缺少固定输入："
                    f"{item.product_key}/{item.language}。"
                )
        return
    for item in items:
        if stored[_item_id(item)]["input"]["status"] != "passed":
            continue
        source = (catalog.project_root / "data" / "current_prod_html").joinpath(
            *item.source_relative_path.parts
        )
        frozen = (catalog.project_root / "data" / "prod-html").joinpath(
            *item.frozen_relative_path.parts
        )
        try:
            identical = (
                source.is_file()
                and frozen.is_file()
                and source.read_bytes() == frozen.read_bytes()
            )
        except OSError as error:
            raise PipelineRunError(
                f"继续前无法核对 {item.product_key}/{item.language} 的输入：{error}"
            ) from error
        if not identical:
            raise PipelineRunError(
                f"{item.product_key}/{item.language} 的上游 HTML 在运行中断后已变化；"
                "为避免混用两批输入，请使用新的 run-name 重新运行。"
            )


def _fixed_processing_inputs(
    catalog: ProductCatalog,
    manifest: dict[str, Any],
    *,
    building_directory: Path,
) -> tuple[Path, Path]:
    if not _uses_batch_fixed_inputs(manifest):
        return (
            (catalog.project_root / "data" / "prod-html").resolve(),
            (
                catalog.project_root
                / "data"
                / "configs"
                / "soft-category.json"
            ).resolve(),
        )
    fixed = manifest.get("fixed_inputs")
    if not isinstance(fixed, dict):
        raise PipelineRunError("增量 Batch 清单缺少固定输入路径。")
    frozen_root = _safe_run_relative_path(
        building_directory,
        fixed.get("frozen_html_root"),
        label="Batch Frozen HTML 根目录",
    )
    soft_category_path = _safe_run_relative_path(
        building_directory,
        fixed.get("soft_category_path"),
        label="Batch soft-category.json",
    )
    return frozen_root, soft_category_path


def _uses_batch_fixed_inputs(manifest: dict[str, Any]) -> bool:
    return manifest.get("batch_kind") in {
        "incremental",
        "incremental_reprocessing",
    }


def _safe_run_relative_path(
    run_directory: Path,
    value: Any,
    *,
    label: str,
) -> Path:
    if not isinstance(value, str) or not value:
        raise PipelineRunError(f"{label}路径无效。")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise PipelineRunError(f"{label}路径必须位于 Batch 目录中。")
    path = run_directory.joinpath(*relative.parts)
    try:
        path.resolve().relative_to(run_directory.resolve())
    except ValueError as error:
        raise PipelineRunError(f"{label}路径越出 Batch 目录。") from error
    if path.is_symlink():
        raise PipelineRunError(f"{label}不能是符号链接。")
    return path


def _selection_description(
    *,
    product_key: str | None,
    category: str | None,
    all_products: bool,
) -> tuple[str, str | None]:
    if product_key is not None:
        return "product", product_key
    if category is not None:
        return "category", category.strip().lower()
    if all_products:
        return "all", None
    raise PipelineRunError("必须选择 product、category 或 all。")


def _manifest_items_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = manifest.get("items")
    if not isinstance(items, list):
        raise PipelineRunError("运行清单缺少 items 列表。")
    result: dict[str, dict[str, Any]] = {}
    for row in items:
        if not isinstance(row, dict) or not isinstance(row.get("item_id"), str):
            raise PipelineRunError("运行清单包含无效处理项。")
        if row["item_id"] in result:
            raise PipelineRunError(f"运行清单重复声明 {row['item_id']}。")
        result[row["item_id"]] = row
    return result


def _item_id(item: ProcessingItem) -> str:
    return f"{item.product_key}/{item.language}"


def _validate_run_name(run_name: str) -> None:
    if not RUN_NAME_PATTERN.fullmatch(run_name):
        raise PipelineRunError(
            "run-name 必须是由小写字母、数字和连字符组成的可读名称。"
        )


def _validate_parallel_jobs(parallel_jobs: int) -> None:
    if (
        isinstance(parallel_jobs, bool)
        or not isinstance(parallel_jobs, int)
        or not 2 <= parallel_jobs <= 32
    ):
        raise PipelineRunError("parallel-jobs 必须是 2 到 32 之间的整数。")


def _runs_root(
    catalog: ProductCatalog,
    runs_root: Path | str | None,
    *,
    create: bool = False,
) -> Path:
    root = Path(
        runs_root if runs_root is not None else catalog.project_root / "runs"
    ).resolve()
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def _save_manifest(directory: Path, manifest: dict[str, Any]) -> None:
    _write_replace_json(directory / "run.json", manifest)


def _write_new_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = payload_json_bytes(value)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError as error:
            raise PipelineRunError(f"文件已经存在，不能覆盖：{path}") from error
    except OSError as error:
        raise PipelineRunError(f"无法写入文件 {path}：{error}") from error
    finally:
        temporary_path.unlink(missing_ok=True)


def _write_new_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError as error:
            raise PipelineRunError(f"文件已经存在，不能覆盖：{path}") from error
    except OSError as error:
        raise PipelineRunError(f"无法写入文件 {path}：{error}") from error
    finally:
        temporary_path.unlink(missing_ok=True)


def _copy_or_confirm_new_bytes(source: Path, destination: Path) -> int:
    content = _read_stable_file(source, label="Frozen HTML")
    if destination.exists():
        if destination.is_symlink() or not destination.is_file():
            raise PipelineRunError(
                f"Batch 固定输入不是普通文件：{destination}。"
            )
        try:
            existing = destination.read_bytes()
        except OSError as error:
            raise PipelineRunError(
                f"无法读取 Batch 固定输入 {destination}：{error}"
            ) from error
        if existing != content:
            raise PipelineRunError(
                f"Batch 固定输入已存在但内容不同：{destination}。"
            )
        return len(content)
    _write_new_bytes(destination, content)
    try:
        copied = destination.read_bytes()
    except OSError as error:
        raise PipelineRunError(
            f"无法核对 Batch 固定输入 {destination}：{error}"
        ) from error
    if copied != content:
        raise PipelineRunError(f"Batch 固定输入复制前后内容不同：{destination}。")
    return len(content)


def _read_stable_file(path: Path, *, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise PipelineRunError(f"{label}不存在或不是普通文件：{path}。")
    try:
        before = path.stat()
        content = path.read_bytes()
        after = path.stat()
    except OSError as error:
        raise PipelineRunError(f"无法读取{label} {path}：{error}") from error
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if before_identity != after_identity:
        raise PipelineRunError(f"{label}在读取过程中发生变化：{path}。")
    return content


def _present_path(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    except OSError as error:
        raise PipelineRunError(f"无法更新文件 {path}：{error}") from error
    finally:
        temporary_path.unlink(missing_ok=True)


def _write_replace_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(payload_json_bytes(value))
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    except OSError as error:
        raise PipelineRunError(f"无法更新运行清单 {path}：{error}") from error
    finally:
        temporary_path.unlink(missing_ok=True)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PipelineRunError(f"无法读取 JSON 文件 {path}：{error}") from error
    if not isinstance(value, dict):
        raise PipelineRunError(f"JSON 文件顶层必须是对象：{path}")
    return value


def _artifact_category_parts(definition: Any) -> tuple[str, ...]:
    if definition.page_model == "FlexibleContentPage":
        return ("pricing",)
    if definition.support_article_type is None:
        raise PipelineRunError(
            f"Support Article {definition.product_key} 缺少文章类型。"
        )
    return ("support-articles", definition.support_article_type)
