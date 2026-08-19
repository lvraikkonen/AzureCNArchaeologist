"""Resolve the single open incremental Batch from readable artifacts."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.catalog import ProductCatalog
from src.core.payload_contract import payload_json_bytes


READABLE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class IncrementalStateError(RuntimeError):
    """Incremental Batch state cannot be resolved or changed safely."""


@dataclass(frozen=True)
class OpenIncrementalBatch:
    run_name: str
    run_directory: Path
    sealed: bool
    affected_product_keys: tuple[str, ...]
    delivered_product_keys: tuple[str, ...]
    ended_without_delivery_product_keys: tuple[str, ...]
    unresolved_product_keys: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "run_name": self.run_name,
            "run_directory": self.run_directory.as_posix(),
            "sealed": self.sealed,
            "affected_product_keys": list(self.affected_product_keys),
            "delivered_product_keys": list(self.delivered_product_keys),
            "ended_without_delivery_product_keys": list(
                self.ended_without_delivery_product_keys
            ),
            "unresolved_product_keys": list(self.unresolved_product_keys),
        }


def find_open_incremental_batch(
    catalog: ProductCatalog,
    *,
    runs_root: Path | str | None = None,
    releases_root: Path | str | None = None,
    closures_root: Path | str | None = None,
) -> OpenIncrementalBatch | None:
    """Return the only unresolved incremental Batch, rejecting ambiguity."""

    run_root = Path(
        runs_root if runs_root is not None else catalog.project_root / "runs"
    ).resolve()
    release_root = Path(
        releases_root
        if releases_root is not None
        else catalog.project_root / "releases"
    ).resolve()
    closure_root = Path(
        closures_root
        if closures_root is not None
        else catalog.project_root / "data" / "state" / "incremental-closures"
    ).resolve()
    if not run_root.exists():
        return None

    open_batches: list[OpenIncrementalBatch] = []
    for directory in sorted(path for path in run_root.iterdir() if path.is_dir()):
        manifest_path = directory / "run.json"
        if not manifest_path.is_file():
            continue
        manifest = _read_json_object(manifest_path, label="Batch 清单")
        if manifest.get("batch_kind") != "incremental":
            continue
        run_name = manifest.get("run_name")
        if not isinstance(run_name, str):
            raise IncrementalStateError(
                f"增量 Batch 清单缺少 run_name：{manifest_path}。"
            )
        expected_name = f"{run_name}.building" if directory.name.endswith(
            ".building"
        ) else run_name
        if directory.name != expected_name:
            raise IncrementalStateError(
                f"增量 Batch 目录与 run_name 不一致：{directory}。"
            )
        affected = _affected_products(manifest)
        delivered = _delivered_products(release_root, run_name)
        closed = _closed_products(closure_root, run_name)
        unknown = (delivered | closed) - set(affected)
        if unknown:
            raise IncrementalStateError(
                f"增量 Batch {run_name} 的结束记录引用范围外产品："
                + "、".join(sorted(unknown))
                + "。"
            )
        unresolved = tuple(
            product_key
            for product_key in affected
            if product_key not in delivered and product_key not in closed
        )
        if not unresolved:
            continue
        open_batches.append(
            OpenIncrementalBatch(
                run_name=run_name,
                run_directory=directory,
                sealed=not directory.name.endswith(".building"),
                affected_product_keys=affected,
                delivered_product_keys=tuple(
                    key for key in affected if key in delivered
                ),
                ended_without_delivery_product_keys=tuple(
                    key for key in affected if key in closed
                ),
                unresolved_product_keys=unresolved,
            )
        )
    if len(open_batches) > 1:
        raise IncrementalStateError(
            "发现多个未结束的增量 Batch："
            + "、".join(batch.run_name for batch in open_batches)
            + "。"
        )
    return open_batches[0] if open_batches else None


def end_product_without_delivery(
    catalog: ProductCatalog,
    *,
    run_name: str,
    product_key: str,
    reviewer: str,
    reason: str,
    runs_root: Path | str | None = None,
    releases_root: Path | str | None = None,
    closures_root: Path | str | None = None,
) -> Path:
    """Write one explicit human end decision without overwriting history."""

    for value, label in ((run_name, "run-name"), (product_key, "Product Key")):
        if not READABLE_ID_PATTERN.fullmatch(value):
            raise IncrementalStateError(
                f"{label} 必须由小写字母、数字和连字符组成。"
            )
    normalized_reviewer = " ".join(reviewer.split())
    normalized_reason = "\n".join(line.rstrip() for line in reason.strip().splitlines())
    if not normalized_reviewer:
        raise IncrementalStateError("结束而不交付必须记录真实审核人。")
    if not normalized_reason:
        raise IncrementalStateError("结束而不交付必须记录可读原因。")
    open_batch = find_open_incremental_batch(
        catalog,
        runs_root=runs_root,
        releases_root=releases_root,
        closures_root=closures_root,
    )
    if open_batch is None or open_batch.run_name != run_name:
        raise IncrementalStateError(f"找不到未结束的增量 Batch {run_name}。")
    if not open_batch.sealed:
        raise IncrementalStateError("增量 Batch 尚未封存，不能结束产品。")
    if product_key not in open_batch.unresolved_product_keys:
        raise IncrementalStateError(
            f"产品 {product_key} 不属于当前未解决范围。"
        )
    root = Path(
        closures_root
        if closures_root is not None
        else catalog.project_root / "data" / "state" / "incremental-closures"
    ).resolve()
    path = root / run_name / f"{product_key}.json"
    _write_new_json(
        path,
        {
            "schema_version": "1.0",
            "run_name": run_name,
            "product_key": product_key,
            "decision": "ended_without_delivery",
            "reviewer": normalized_reviewer,
            "reason": normalized_reason,
        },
    )
    return path


def _affected_products(manifest: dict[str, Any]) -> tuple[str, ...]:
    scope = manifest.get("scope")
    if not isinstance(scope, dict) or not isinstance(scope.get("product_keys"), list):
        raise IncrementalStateError("增量 Batch 缺少产品范围。")
    values = scope["product_keys"]
    if any(not isinstance(value, str) for value in values):
        raise IncrementalStateError("增量 Batch 产品范围无效。")
    result = tuple(values)
    if len(result) != len(set(result)):
        raise IncrementalStateError("增量 Batch 产品范围包含重复值。")
    return result


def _delivered_products(release_root: Path, run_name: str) -> set[str]:
    result: set[str] = set()
    if not release_root.exists():
        return result
    for directory in sorted(path for path in release_root.iterdir() if path.is_dir()):
        if directory.name.endswith(".building"):
            continue
        manifest_path = directory / "release-manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = _read_json_object(manifest_path, label="Release 清单")
        source_review = manifest.get("source_review")
        source_incremental_run = (
            source_review.get(
                "incremental_run_name",
                source_review.get("run_name"),
            )
            if isinstance(source_review, dict)
            else None
        )
        if (
            manifest.get("release_kind") != "delta"
            or not isinstance(source_review, dict)
            or source_incremental_run != run_name
        ):
            continue
        products = manifest.get("products")
        if not isinstance(products, list):
            raise IncrementalStateError(
                f"Delta Release 清单缺少产品：{manifest_path}。"
            )
        for product in products:
            if not isinstance(product, dict) or not isinstance(
                product.get("product_key"), str
            ):
                raise IncrementalStateError(
                    f"Delta Release 清单包含无效产品：{manifest_path}。"
                )
            key = product["product_key"]
            items = product.get("items")
            if not isinstance(items, list) or [
                item.get("language")
                for item in items
                if isinstance(item, dict)
            ] != ["zh-cn", "en-us"]:
                raise IncrementalStateError(
                    f"Delta Release 中 {key} 不是完整中英文交付："
                    f"{manifest_path}。"
                )
            for item in items:
                assert isinstance(item, dict)
                relative_value = item.get("release_payload_path")
                if not isinstance(relative_value, str):
                    raise IncrementalStateError(
                        f"Delta Release 中 {key} 缺少 Payload 路径。"
                    )
                relative = Path(relative_value)
                if relative.is_absolute() or ".." in relative.parts:
                    raise IncrementalStateError(
                        f"Delta Release 中 {key} 的 Payload 路径无效。"
                    )
                payload = directory.joinpath(*relative.parts)
                try:
                    payload.resolve().relative_to(directory.resolve())
                except ValueError as error:
                    raise IncrementalStateError(
                        f"Delta Release 中 {key} 的 Payload 路径越界。"
                    ) from error
                if payload.is_symlink() or not payload.is_file():
                    raise IncrementalStateError(
                        f"Delta Release 中 {key} 缺少 Payload：{payload}。"
                    )
            if key in result:
                raise IncrementalStateError(
                    f"产品 {key} 在同一增量 Batch 的多个 Delta Release 中重复交付。"
                )
            result.add(key)
    return result


def _closed_products(closure_root: Path, run_name: str) -> set[str]:
    directory = closure_root / run_name
    if not directory.exists():
        return set()
    result: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        value = _read_json_object(path, label="结束而不交付决定")
        product_key = value.get("product_key")
        if (
            value.get("schema_version") != "1.0"
            or value.get("run_name") != run_name
            or value.get("decision") != "ended_without_delivery"
            or not isinstance(product_key, str)
            or not isinstance(value.get("reviewer"), str)
            or not value["reviewer"].strip()
            or not isinstance(value.get("reason"), str)
            or not value["reason"].strip()
        ):
            raise IncrementalStateError(f"结束而不交付决定无效：{path}。")
        if path.stem != product_key or product_key in result:
            raise IncrementalStateError(f"结束而不交付决定身份重复或不一致：{path}。")
        result.add(product_key)
    return result


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IncrementalStateError(f"无法读取{label} {path}：{error}") from error
    if not isinstance(value, dict):
        raise IncrementalStateError(f"{label}顶层必须是对象：{path}。")
    return value


def _write_new_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = payload_json_bytes(value)
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
            raise IncrementalStateError(
                f"结束而不交付决定已经存在，不能覆盖：{path}。"
            ) from error
    except OSError as error:
        raise IncrementalStateError(f"无法写入结束决定 {path}：{error}") from error
    finally:
        temporary_path.unlink(missing_ok=True)


__all__ = [
    "IncrementalStateError",
    "OpenIncrementalBatch",
    "end_product_without_delivery",
    "find_open_incremental_batch",
]
