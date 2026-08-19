"""Build and verify readable, write-once full Releases."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from src.core.catalog import LANGUAGES, ProductCatalog
from src.incremental.reprocessing import (
    IncrementalReprocessingError,
    find_reprocessing_chain,
    resolve_incremental_run_reference,
)
from src.incremental.state import (
    IncrementalStateError,
    find_open_incremental_batch,
)
from src.review.service import (
    ReviewError,
    collect_release_review_snapshot,
)


READABLE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FORBIDDEN_MANIFEST_KEY_PARTS = ("hash", "digest", "fingerprint", "checksum")


class ReleaseError(RuntimeError):
    """A Release cannot be trusted, verified, or safely written."""


@dataclass(frozen=True)
class ReleaseBuildResult:
    release_id: str
    release_directory: Path
    manifest: dict[str, Any]


def build_full_release(
    catalog: ProductCatalog,
    *,
    review_id: str,
    release_id: str,
    reviews_root: Path | str | None = None,
    releases_root: Path | str | None = None,
) -> ReleaseBuildResult:
    """Build all currently approved bilingual products from one review queue."""

    return _build_release(
        catalog,
        review_id=review_id,
        release_id=release_id,
        release_kind="full",
        reviews_root=reviews_root,
        releases_root=releases_root,
    )


def build_delta_release(
    catalog: ProductCatalog,
    *,
    review_id: str,
    release_id: str,
    reviews_root: Path | str | None = None,
    releases_root: Path | str | None = None,
    runs_root: Path | str | None = None,
    closures_root: Path | str | None = None,
) -> ReleaseBuildResult:
    """Build newly approved products from one open incremental Batch."""

    return _build_release(
        catalog,
        review_id=review_id,
        release_id=release_id,
        release_kind="delta",
        reviews_root=reviews_root,
        releases_root=releases_root,
        runs_root=runs_root,
        closures_root=closures_root,
    )


def _build_release(
    catalog: ProductCatalog,
    *,
    review_id: str,
    release_id: str,
    release_kind: str,
    reviews_root: Path | str | None,
    releases_root: Path | str | None,
    runs_root: Path | str | None = None,
    closures_root: Path | str | None = None,
) -> ReleaseBuildResult:
    """Build one write-once full or delta Release."""

    _validate_readable_id(review_id, field="审核 ID")
    _validate_readable_id(release_id, field="Release ID")
    release_root = _root_path(
        catalog.project_root, releases_root, "releases", create=True
    )
    final_directory = release_root / release_id
    building_directory = release_root / f"{release_id}.building"
    if final_directory.exists():
        raise ReleaseError(f"Release 已经存在，不能覆盖：{final_directory}")
    if building_directory.exists():
        raise ReleaseError(
            f"发现未完成的 Release 目录，不能覆盖：{building_directory}"
        )

    try:
        snapshot = collect_release_review_snapshot(
            catalog,
            review_id=review_id,
            reviews_root=reviews_root,
        )
    except ReviewError as error:
        raise ReleaseError(f"审核记录不能用于 Release：{error}") from error
    if not snapshot.approved:
        raise ReleaseError(
            f"审核 {review_id} 当前没有已批准的双语产品，不能创建空 Release。"
        )

    queue = snapshot.queue
    run_directory = _resolve_presented_path(
        queue["batch"]["run_directory"], catalog.project_root
    )
    run_manifest = _read_json_object(run_directory / "run.json")
    incremental_run_name: str | None = None
    incremental_run_directory: Path | None = None
    incremental_manifest: dict[str, Any] | None = None
    already_delivered: set[str] = set()
    ended_without_delivery: set[str] = set()
    delta_eligible: set[str] | None = None
    stale_reprocessed: set[str] = set()
    if release_kind == "delta":
        try:
            reference = resolve_incremental_run_reference(
                catalog,
                processing_run_directory=run_directory,
                processing_manifest=run_manifest,
            )
        except IncrementalReprocessingError as error:
            raise ReleaseError(str(error)) from error
        incremental_run_name = reference.run_name
        incremental_run_directory = reference.run_directory
        incremental_manifest = reference.manifest
        try:
            open_batch = find_open_incremental_batch(
                catalog,
                runs_root=runs_root,
                releases_root=releases_root,
                closures_root=closures_root,
            )
        except IncrementalStateError as error:
            raise ReleaseError(str(error)) from error
        if (
            open_batch is None
            or open_batch.run_name != incremental_run_name
        ):
            raise ReleaseError(
                "审核引用的增量 Batch 已结束或不是当前唯一未结束 Batch。"
            )
        already_delivered = set(open_batch.delivered_product_keys)
        ended_without_delivery = set(
            open_batch.ended_without_delivery_product_keys
        )
        delta_eligible = set(open_batch.unresolved_product_keys)
    elif release_kind != "full":
        raise ReleaseError(f"未知 Release 类型：{release_kind}。")
    products: list[dict[str, Any]] = []
    copy_plan: list[tuple[Path, PurePosixPath]] = []
    decision_copy_plan: list[tuple[Path, PurePosixPath]] = []
    destination_paths: set[PurePosixPath] = set()

    approved_entries = tuple(
        entry
        for entry in snapshot.approved
        if entry[0]["product_key"] not in already_delivered
        and (
            delta_eligible is None
            or entry[0]["product_key"] in delta_eligible
        )
    )
    if release_kind == "delta":
        assert incremental_run_name is not None
        assert incremental_run_directory is not None
        latest_entries = []
        chain_root = (
            Path(runs_root).resolve()
            if runs_root is not None
            else incremental_run_directory.parent
        )
        for entry in approved_entries:
            product_key = entry[0]["product_key"]
            try:
                chain = find_reprocessing_chain(
                    catalog,
                    incremental_run_name=incremental_run_name,
                    product_key=product_key,
                    runs_root=chain_root,
                )
            except IncrementalReprocessingError as error:
                raise ReleaseError(str(error)) from error
            if chain.latest_run_name != queue["batch"]["run_name"]:
                stale_reprocessed.add(product_key)
                continue
            latest_entries.append(entry)
        approved_entries = tuple(latest_entries)
    if not approved_entries:
        raise ReleaseError(
            "当前没有尚未解决且可交付的批准产品，"
            "不能创建空、重复或已明确结束的 Delta Release。"
        )

    for product, decision, decision_path in approved_entries:
        product_key = product["product_key"]
        items = product.get("items")
        if not isinstance(items, list) or [
            item.get("language") for item in items if isinstance(item, dict)
        ] != list(LANGUAGES):
            raise ReleaseError(
                f"已批准产品 {product_key} 没有完整且有序的中英文 Payload。"
            )
        release_items: list[dict[str, str]] = []
        for item in items:
            assert isinstance(item, dict)
            source_payload_path = _resolve_presented_path(
                item["payload_path"], catalog.project_root
            )
            try:
                payload_relative = source_payload_path.relative_to(run_directory)
            except ValueError as error:
                raise ReleaseError(
                    f"{item['item_id']} 的 Payload 不在当前 Batch 目录中。"
                ) from error
            destination = PurePosixPath(*payload_relative.parts)
            if not destination.parts or destination.parts[0] != "payloads":
                raise ReleaseError(
                    f"{item['item_id']} 的 Payload 路径不属于 Batch payloads 目录。"
                )
            if destination in destination_paths:
                raise ReleaseError(f"Release Payload 路径重复：{destination}")
            destination_paths.add(destination)
            copy_plan.append((source_payload_path, destination))
            release_items.append(
                {
                    "item_id": item["item_id"],
                    "language": item["language"],
                    "frozen_html_path": item["frozen_html_path"],
                    "source_payload_path": item["payload_path"],
                    "release_payload_path": destination.as_posix(),
                    "l3a_report_path": item["l3a_report_path"],
                    "l3b_report_path": item["l3b_report_path"],
                }
            )
        release_decision_path = PurePosixPath(
            "review-decisions", f"{product_key}.json"
        )
        decision_copy_plan.append((decision_path, release_decision_path))
        product_record: dict[str, Any] = {
            "product_key": product_key,
            "display_name": product["display_name"],
            "page_model": product["page_model"],
            "semantic_strategy": product["semantic_strategy"],
            "review": {
                "reviewer": decision["reviewer"],
                "decision": "approved",
                "inspection_scope": decision["inspection_scope"],
                "notes": decision["notes"],
                "source_decision_path": _present_path(
                    decision_path, catalog.project_root
                ),
                "release_decision_path": release_decision_path.as_posix(),
            },
            "items": release_items,
        }
        if release_kind == "delta":
            assert incremental_manifest is not None
            change_reasons = incremental_manifest.get("change_reasons")
            if not isinstance(change_reasons, dict) or not isinstance(
                change_reasons.get(product_key), dict
            ):
                raise ReleaseError(
                    f"增量 Batch 缺少 {product_key} 的可读变化原因。"
                )
            product_record["change_reasons"] = change_reasons[product_key]
        products.append(product_record)

    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "release_id": release_id,
        "release_kind": release_kind,
        "source_review": {
            "review_id": review_id,
            "review_queue_path": _present_path(
                snapshot.review_directory / "queue.json", catalog.project_root
            ),
            "run_name": queue["batch"]["run_name"],
            "run_manifest_path": queue["batch"]["run_manifest_path"],
        },
        "summary": {
            "approved_products": len(products),
            "payload_items": sum(len(product["items"]) for product in products),
            "rejected_products": len(snapshot.rejected_product_keys),
            "awaiting_decision_products": len(snapshot.pending_product_keys),
            "not_queued_items": len(queue["not_queued_items"]),
        },
        "products": products,
        "excluded": {
            "rejected_product_keys": list(snapshot.rejected_product_keys),
            "awaiting_decision_product_keys": list(snapshot.pending_product_keys),
            "not_queued_items": queue["not_queued_items"],
        },
    }
    if "payload_contract_version" in queue["batch"]:
        manifest["source_review"]["payload_contract_version"] = queue[
            "batch"
        ]["payload_contract_version"]
    if release_kind == "delta":
        assert incremental_run_name is not None
        assert incremental_run_directory is not None
        assert incremental_manifest is not None
        manifest["source_review"]["incremental_run_name"] = (
            incremental_run_name
        )
        manifest["summary"]["already_delivered_products"] = len(
            already_delivered
        )
        manifest["summary"]["stale_reprocessed_products"] = len(
            stale_reprocessed
        )
        manifest["excluded"]["already_delivered_product_keys"] = sorted(
            already_delivered
        )
        manifest["excluded"]["ended_without_delivery_product_keys"] = sorted(
            ended_without_delivery
        )
        manifest["excluded"]["stale_reprocessed_product_keys"] = sorted(
            stale_reprocessed
        )
        manifest["source_review"]["change_plan_path"] = _present_path(
            incremental_run_directory
            / str(incremental_manifest["change_plan_path"]),
            catalog.project_root,
        )
    _reject_encoded_evidence_keys(manifest)

    building_directory.mkdir(parents=True)
    for source, destination in copy_plan:
        _copy_new_file(source, building_directory, destination)
    for source, destination in decision_copy_plan:
        _copy_new_file(source, building_directory, destination)
    _write_new_json(building_directory / "release-manifest.json", manifest)
    _verify_release_directory(
        catalog,
        release_directory=building_directory,
        expected_release_id=release_id,
        reviews_root=reviews_root,
        expected_release_kind=release_kind,
    )
    try:
        building_directory.rename(final_directory)
    except OSError as error:
        raise ReleaseError(
            f"无法封存 Release 目录 {final_directory}：{error}"
        ) from error
    return ReleaseBuildResult(release_id, final_directory, manifest)


def verify_full_release(
    catalog: ProductCatalog,
    *,
    release_id: str,
    reviews_root: Path | str | None = None,
    releases_root: Path | str | None = None,
) -> dict[str, Any]:
    """Verify a sealed Release by direct files and readable references."""

    _validate_readable_id(release_id, field="Release ID")
    release_root = _root_path(catalog.project_root, releases_root, "releases")
    release_directory = release_root / release_id
    if (release_root / f"{release_id}.building").exists():
        raise ReleaseError(f"Release {release_id} 仍有未封存目录。")
    if not release_directory.is_dir():
        raise ReleaseError(f"找不到 Release：{release_directory}")
    manifest = _verify_release_directory(
        catalog,
        release_directory=release_directory,
        expected_release_id=release_id,
        reviews_root=reviews_root,
        expected_release_kind="full",
    )
    return {
        "release_id": release_id,
        "status": "passed",
        "release_directory": _present_path(
            release_directory, catalog.project_root
        ),
        "summary": manifest["summary"],
    }


def verify_release(
    catalog: ProductCatalog,
    *,
    release_id: str,
    reviews_root: Path | str | None = None,
    releases_root: Path | str | None = None,
) -> dict[str, Any]:
    """Verify a sealed full or delta Release from direct readable evidence."""

    _validate_readable_id(release_id, field="Release ID")
    release_root = _root_path(catalog.project_root, releases_root, "releases")
    release_directory = release_root / release_id
    if (release_root / f"{release_id}.building").exists():
        raise ReleaseError(f"Release {release_id} 仍有未封存目录。")
    if not release_directory.is_dir():
        raise ReleaseError(f"找不到 Release：{release_directory}")
    manifest = _verify_release_directory(
        catalog,
        release_directory=release_directory,
        expected_release_id=release_id,
        reviews_root=reviews_root,
        expected_release_kind=None,
    )
    return {
        "release_id": release_id,
        "release_kind": manifest["release_kind"],
        "status": "passed",
        "release_directory": _present_path(
            release_directory,
            catalog.project_root,
        ),
        "summary": manifest["summary"],
    }


def _verify_release_directory(
    catalog: ProductCatalog,
    *,
    release_directory: Path,
    expected_release_id: str,
    reviews_root: Path | str | None,
    expected_release_kind: str | None,
) -> dict[str, Any]:
    manifest = _read_json_object(release_directory / "release-manifest.json")
    if manifest.get("schema_version") != "1.0":
        raise ReleaseError("Release 清单版本无效。")
    if manifest.get("release_id") != expected_release_id:
        raise ReleaseError("Release 目录名与清单中的 Release ID 不一致。")
    release_kind = manifest.get("release_kind")
    if release_kind not in {"full", "delta"}:
        raise ReleaseError("Release 类型必须是 full 或 delta。")
    if (
        expected_release_kind is not None
        and release_kind != expected_release_kind
    ):
        raise ReleaseError(
            f"期望 {expected_release_kind} Release，实际为 {release_kind}。"
        )
    _reject_encoded_evidence_keys(manifest)
    source_review = manifest.get("source_review")
    if not isinstance(source_review, dict):
        raise ReleaseError("Release 清单缺少审核来源。")
    review_id = source_review.get("review_id")
    if not isinstance(review_id, str):
        raise ReleaseError("Release 清单缺少审核 ID。")
    try:
        snapshot = collect_release_review_snapshot(
            catalog,
            review_id=review_id,
            reviews_root=reviews_root,
        )
    except ReviewError as error:
        raise ReleaseError(f"Release 引用的审核记录无效：{error}") from error
    if source_review.get("run_name") != snapshot.queue["batch"]["run_name"]:
        raise ReleaseError("Release 引用的 Batch 与审核清单不一致。")
    declared_contract_version = source_review.get("payload_contract_version")
    queue_has_contract_version = (
        "payload_contract_version" in snapshot.queue["batch"]
    )
    if (
        (declared_contract_version is not None) != queue_has_contract_version
        or (
            queue_has_contract_version
            and declared_contract_version
            != snapshot.queue["batch"]["payload_contract_version"]
        )
    ):
        raise ReleaseError("Release 引用的 Payload 合同版本与审核清单不一致。")
    run_directory = _resolve_presented_path(
        snapshot.queue["batch"]["run_directory"],
        catalog.project_root,
    )
    run_manifest = _read_json_object(run_directory / "run.json")
    incremental_run_name: str | None = None
    incremental_run_directory: Path | None = None
    incremental_manifest: dict[str, Any] | None = None
    if release_kind == "delta":
        try:
            reference = resolve_incremental_run_reference(
                catalog,
                processing_run_directory=run_directory,
                processing_manifest=run_manifest,
            )
        except IncrementalReprocessingError as error:
            raise ReleaseError(str(error)) from error
        incremental_run_name = reference.run_name
        incremental_run_directory = reference.run_directory
        incremental_manifest = reference.manifest
        declared_incremental_run = source_review.get(
            "incremental_run_name",
            source_review.get("run_name"),
        )
        if declared_incremental_run != incremental_run_name:
            raise ReleaseError("Delta Release 引用的原增量 Batch 不一致。")
        change_plan_path = _resolve_presented_path(
            source_review.get("change_plan_path"),
            catalog.project_root,
        )
        expected_change_plan = incremental_run_directory / str(
            incremental_manifest.get("change_plan_path", "")
        )
        if change_plan_path != expected_change_plan or not change_plan_path.is_file():
            raise ReleaseError("Delta Release 引用的变化计划与 Batch 不一致。")

    approved_by_key = {
        product["product_key"]: (product, decision, decision_path)
        for product, decision, decision_path in snapshot.approved
    }
    products = manifest.get("products")
    if not isinstance(products, list) or not products:
        raise ReleaseError("Release 清单没有已批准产品。")
    expected_payload_paths: set[Path] = set()
    expected_decision_paths: set[Path] = set()
    seen_products: set[str] = set()
    for product_record in products:
        if not isinstance(product_record, dict):
            raise ReleaseError("Release 产品记录必须是对象。")
        product_key = product_record.get("product_key")
        if not isinstance(product_key, str) or product_key in seen_products:
            raise ReleaseError("Release 产品名称为空或重复。")
        seen_products.add(product_key)
        approved_entry = approved_by_key.get(product_key)
        if approved_entry is None:
            raise ReleaseError(f"产品 {product_key} 当前没有有效批准决定。")
        queue_product, decision, source_decision_path = approved_entry
        if release_kind == "delta":
            assert incremental_manifest is not None
            assert incremental_run_name is not None
            assert incremental_run_directory is not None
            change_reasons = incremental_manifest.get("change_reasons")
            if (
                not isinstance(change_reasons, dict)
                or product_record.get("change_reasons")
                != change_reasons.get(product_key)
            ):
                raise ReleaseError(
                    f"产品 {product_key} 的变化原因与增量 Batch 不一致。"
                )
            try:
                chain = find_reprocessing_chain(
                    catalog,
                    incremental_run_name=incremental_run_name,
                    product_key=product_key,
                    runs_root=incremental_run_directory.parent,
                )
            except IncrementalReprocessingError as error:
                raise ReleaseError(str(error)) from error
            if chain.latest_run_name != source_review.get("run_name"):
                raise ReleaseError(
                    f"产品 {product_key} 的审核结果不是最新重新处理记录。"
                )
        review = product_record.get("review")
        if not isinstance(review, dict):
            raise ReleaseError(f"产品 {product_key} 缺少审核信息。")
        if review.get("decision") != "approved":
            raise ReleaseError(f"产品 {product_key} 不是批准状态。")
        for field in ("reviewer", "inspection_scope", "notes"):
            if review.get(field) != decision.get(field):
                raise ReleaseError(f"产品 {product_key} 的 {field} 与审核决定不一致。")
        if _resolve_presented_path(
            review.get("source_decision_path"), catalog.project_root
        ) != source_decision_path.resolve():
            raise ReleaseError(f"产品 {product_key} 的审核决定路径不一致。")
        release_decision_path = _release_relative_path(
            release_directory,
            review.get("release_decision_path"),
            label=f"{product_key} Release 审核决定",
        )
        expected_decision_paths.add(release_decision_path)
        _compare_files(
            source_decision_path,
            release_decision_path,
            label=f"{product_key} 审核决定",
        )

        items = product_record.get("items")
        queue_items = queue_product.get("items")
        if not isinstance(items, list) or not isinstance(queue_items, list):
            raise ReleaseError(f"产品 {product_key} 缺少双语处理项。")
        if [item.get("language") for item in items if isinstance(item, dict)] != list(
            LANGUAGES
        ):
            raise ReleaseError(f"产品 {product_key} 没有同时交付中文和英文。")
        queue_by_id = {item["item_id"]: item for item in queue_items}
        for item in items:
            if not isinstance(item, dict):
                raise ReleaseError(f"产品 {product_key} 的处理项必须是对象。")
            item_id = item.get("item_id")
            queued_item = queue_by_id.get(item_id)
            if queued_item is None:
                raise ReleaseError(f"{item_id} 不在当前审核清单中。")
            for manifest_field, queue_field in (
                ("frozen_html_path", "frozen_html_path"),
                ("source_payload_path", "payload_path"),
                ("l3a_report_path", "l3a_report_path"),
                ("l3b_report_path", "l3b_report_path"),
            ):
                if item.get(manifest_field) != queued_item.get(queue_field):
                    raise ReleaseError(f"{item_id} 的 {manifest_field} 与审核清单不一致。")
            source_payload = _resolve_presented_path(
                item.get("source_payload_path"), catalog.project_root
            )
            release_payload = _release_relative_path(
                release_directory,
                item.get("release_payload_path"),
                label=f"{item_id} Release Payload",
            )
            expected_payload_paths.add(release_payload)
            _compare_files(source_payload, release_payload, label=f"{item_id} Payload")

    summary = manifest.get("summary")
    if not isinstance(summary, dict):
        raise ReleaseError("Release 清单缺少结果汇总。")
    payload_count = sum(len(product["items"]) for product in products)
    if summary.get("approved_products") != len(products):
        raise ReleaseError("Release 汇总的批准产品数与清单不一致。")
    if summary.get("payload_items") != payload_count:
        raise ReleaseError("Release 汇总的 Payload 数与清单不一致。")
    if payload_count != len(products) * len(LANGUAGES):
        raise ReleaseError("Release 中存在不完整的双语产品。")
    if release_kind == "delta":
        assert incremental_run_name is not None
        _verify_no_duplicate_delta_products(
            release_directory,
            run_name=incremental_run_name,
            product_keys=seen_products,
        )

    actual_payload_paths = {
        path.resolve()
        for path in (release_directory / "payloads").rglob("*.json")
        if path.is_file()
    }
    if actual_payload_paths != expected_payload_paths:
        raise ReleaseError("Release payloads 目录与清单列出的文件不完全一致。")
    decision_root = release_directory / "review-decisions"
    actual_decision_paths = {
        path.resolve() for path in decision_root.glob("*.json") if path.is_file()
    }
    if actual_decision_paths != expected_decision_paths:
        raise ReleaseError("Release 审核决定目录与清单列出的文件不完全一致。")
    return manifest


def _verify_no_duplicate_delta_products(
    release_directory: Path,
    *,
    run_name: str,
    product_keys: set[str],
) -> None:
    for sibling in sorted(
        path for path in release_directory.parent.iterdir() if path.is_dir()
    ):
        if sibling.resolve() == release_directory.resolve() or sibling.name.endswith(
            ".building"
        ):
            continue
        manifest_path = sibling / "release-manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = _read_json_object(manifest_path)
        source_review = manifest.get("source_review")
        if (
            manifest.get("release_kind") != "delta"
            or not isinstance(source_review, dict)
            or source_review.get(
                "incremental_run_name",
                source_review.get("run_name"),
            )
            != run_name
        ):
            continue
        products = manifest.get("products")
        if not isinstance(products, list):
            raise ReleaseError(f"既有 Delta Release 清单无效：{manifest_path}。")
        existing = {
            product.get("product_key")
            for product in products
            if isinstance(product, dict)
            and isinstance(product.get("product_key"), str)
        }
        overlap = sorted(product_keys & existing)
        if overlap:
            raise ReleaseError(
                "同一增量 Batch 不能重复交付产品："
                + "、".join(overlap)
                + "。"
            )


def _copy_new_file(source: Path, root: Path, destination: PurePosixPath) -> None:
    if not source.is_file():
        raise ReleaseError(f"找不到 Release 源文件：{source}")
    target = _release_relative_path(root, destination.as_posix(), label="Release 文件")
    target.parent.mkdir(parents=True, exist_ok=True)
    data = source.read_bytes()
    try:
        with target.open("xb") as stream:
            stream.write(data)
    except FileExistsError as error:
        raise ReleaseError(f"Release 文件路径重复，不能覆盖：{target}") from error
    if target.read_bytes() != data:
        raise ReleaseError(f"Release 文件复制后与来源字节不一致：{target}")


def _compare_files(source: Path, target: Path, *, label: str) -> None:
    if not source.is_file():
        raise ReleaseError(f"{label} 的来源文件不存在：{source}")
    if not target.is_file():
        raise ReleaseError(f"{label} 的 Release 文件不存在：{target}")
    if source.read_bytes() != target.read_bytes():
        raise ReleaseError(f"{label} 的 Release 文件与来源字节不一致。")


def _release_relative_path(root: Path, value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ReleaseError(f"{label} 路径必须是非空文本。")
    relative = PurePosixPath(value)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ReleaseError(f"{label} 使用了不安全路径：{value}")
    root = root.resolve()
    path = root.joinpath(*relative.parts).resolve()
    if not path.is_relative_to(root):
        raise ReleaseError(f"{label} 路径越出 Release 目录：{value}")
    return path


def _reject_encoded_evidence_keys(value: Any, path: str = "$manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in FORBIDDEN_MANIFEST_KEY_PARTS):
                raise ReleaseError(
                    f"Release 清单不得使用摘要类字段：{path}.{key}"
                )
            _reject_encoded_evidence_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_encoded_evidence_keys(child, f"{path}[{index}]")


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


def _present_path(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _resolve_presented_path(value: Any, project_root: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ReleaseError("Release 引用路径必须是非空文本。")
    path = Path(value)
    return (path if path.is_absolute() else project_root / path).resolve()


def _validate_readable_id(value: str, *, field: str) -> None:
    if not isinstance(value, str) or not READABLE_ID_PATTERN.fullmatch(value):
        raise ReleaseError(f"{field} 必须由小写字母、数字和连字符组成。")


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ReleaseError(f"找不到 JSON 文件：{path}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseError(f"无法读取 JSON 文件 {path}：{error}") from error
    if not isinstance(value, dict):
        raise ReleaseError(f"JSON 文件必须包含对象：{path}")
    return value


def _write_new_json(path: Path, value: dict[str, Any]) -> None:
    data = (
        json.dumps(value, ensure_ascii=False, indent=2, separators=(",", ": "))
        + "\n"
    ).encode("utf-8")
    try:
        with path.open("xb") as stream:
            stream.write(data)
    except FileExistsError as error:
        raise ReleaseError(f"文件已经存在，不能覆盖：{path}") from error
