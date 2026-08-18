"""维护同一增量 Batch 中多次处理记录的明确先后顺序。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.catalog import LANGUAGES, ProductCatalog


class IncrementalReprocessingError(RuntimeError):
    """重新处理记录的先后关系缺失或相互矛盾。"""


@dataclass(frozen=True)
class IncrementalRunReference:
    """某次处理记录所属的原增量 Batch。"""

    run_name: str
    run_directory: Path
    manifest: dict[str, Any]


@dataclass(frozen=True)
class ReprocessingChain:
    """一个受影响产品的有序处理记录。"""

    incremental_run_name: str
    product_key: str
    processing_run_names: tuple[str, ...]
    latest_run_name: str
    latest_run_directory: Path
    latest_sealed: bool


def resolve_incremental_run_reference(
    catalog: ProductCatalog,
    *,
    processing_run_directory: Path,
    processing_manifest: dict[str, Any],
) -> IncrementalRunReference:
    """从处理记录找到其原增量 Batch。"""

    kind = processing_manifest.get("batch_kind")
    if kind == "incremental":
        run_name = _required_text(
            processing_manifest,
            "run_name",
            "增量 Batch",
        )
        return IncrementalRunReference(
            run_name,
            processing_run_directory.resolve(),
            processing_manifest,
        )
    if kind != "incremental_reprocessing":
        raise IncrementalReprocessingError(
            "处理记录既不是增量 Batch，也不是其重新处理记录。"
        )

    metadata = _reprocessing_metadata(processing_manifest)
    parent_name = _required_text(
        metadata,
        "incremental_run_name",
        "重新处理记录",
    )
    parent_directory = _resolve_presented_path(
        metadata.get("incremental_run_directory"),
        catalog.project_root,
        label="原增量 Batch 目录",
    )
    expected_parent_directory = (
        processing_run_directory.resolve().parent / parent_name
    )
    if parent_directory != expected_parent_directory:
        raise IncrementalReprocessingError(
            "重新处理记录引用的原增量 Batch 不在同一运行目录中。"
        )
    parent_manifest_path = _resolve_presented_path(
        metadata.get("incremental_run_manifest_path"),
        catalog.project_root,
        label="原增量 Batch 清单",
    )
    if parent_manifest_path != parent_directory / "run.json":
        raise IncrementalReprocessingError(
            "重新处理记录引用的原增量 Batch 清单与目录不一致。"
        )
    parent_manifest = _read_json_object(
        parent_manifest_path,
        label="原增量 Batch 清单",
    )
    if (
        parent_manifest.get("batch_kind") != "incremental"
        or parent_manifest.get("run_name") != parent_name
    ):
        raise IncrementalReprocessingError(
            "重新处理记录引用的原增量 Batch 身份无效。"
        )
    return IncrementalRunReference(
        parent_name,
        parent_directory,
        parent_manifest,
    )


def find_reprocessing_chain(
    catalog: ProductCatalog,
    *,
    incremental_run_name: str,
    product_key: str,
    runs_root: Path | str | None = None,
) -> ReprocessingChain:
    """返回唯一且没有分叉的处理记录顺序。"""

    run_root = Path(
        runs_root if runs_root is not None else catalog.project_root / "runs"
    ).resolve()
    parent_directory = run_root / incremental_run_name
    parent_manifest = _read_json_object(
        parent_directory / "run.json",
        label="原增量 Batch 清单",
    )
    if (
        parent_manifest.get("batch_kind") != "incremental"
        or parent_manifest.get("run_name") != incremental_run_name
    ):
        raise IncrementalReprocessingError(
            f"找不到增量 Batch {incremental_run_name}。"
        )
    scope = parent_manifest.get("scope")
    if (
        not isinstance(scope, dict)
        or not isinstance(scope.get("product_keys"), list)
        or product_key not in scope["product_keys"]
    ):
        raise IncrementalReprocessingError(
            f"产品 {product_key} 不属于增量 Batch {incremental_run_name}。"
        )

    records: dict[str, tuple[str, Path, bool]] = {}
    if run_root.is_dir():
        for directory in sorted(
            candidate for candidate in run_root.iterdir() if candidate.is_dir()
        ):
            manifest_path = directory / "run.json"
            if not manifest_path.is_file():
                continue
            manifest = _read_json_object(
                manifest_path,
                label="Batch 清单",
            )
            if manifest.get("batch_kind") != "incremental_reprocessing":
                continue
            metadata = _reprocessing_metadata(manifest)
            if (
                metadata.get("incremental_run_name") != incremental_run_name
                or metadata.get("product_key") != product_key
            ):
                continue
            reference = resolve_incremental_run_reference(
                catalog,
                processing_run_directory=directory,
                processing_manifest=manifest,
            )
            if (
                reference.run_name != incremental_run_name
                or reference.run_directory != parent_directory.resolve()
            ):
                raise IncrementalReprocessingError(
                    "重新处理记录引用了其他增量 Batch 目录。"
                )
            run_name = _required_text(manifest, "run_name", "重新处理记录")
            expected_directory_name = (
                f"{run_name}.building"
                if directory.name.endswith(".building")
                else run_name
            )
            if directory.name != expected_directory_name:
                raise IncrementalReprocessingError(
                    f"重新处理记录目录与运行名称不一致：{directory}。"
                )
            previous = _required_text(
                metadata,
                "previous_processing_run_name",
                "重新处理记录",
            )
            if previous in records:
                raise IncrementalReprocessingError(
                    f"{previous} 之后存在多份相互冲突的重新处理记录。"
                )
            records[previous] = (
                run_name,
                directory.resolve(),
                not directory.name.endswith(".building"),
            )

    ordered = [incremental_run_name]
    latest_directory = parent_directory.resolve()
    latest_sealed = True
    current = incremental_run_name
    visited_previous: set[str] = set()
    while current in records:
        if current in visited_previous:
            raise IncrementalReprocessingError("重新处理记录形成了循环引用。")
        visited_previous.add(current)
        next_name, next_directory, next_sealed = records[current]
        if next_name in ordered:
            raise IncrementalReprocessingError("重新处理记录形成了循环引用。")
        ordered.append(next_name)
        latest_directory = next_directory
        latest_sealed = next_sealed
        current = next_name
    if len(visited_previous) != len(records):
        raise IncrementalReprocessingError(
            "重新处理记录没有形成从原增量 Batch 开始的唯一顺序。"
        )
    return ReprocessingChain(
        incremental_run_name=incremental_run_name,
        product_key=product_key,
        processing_run_names=tuple(ordered),
        latest_run_name=ordered[-1],
        latest_run_directory=latest_directory,
        latest_sealed=latest_sealed,
    )


def _reprocessing_metadata(manifest: dict[str, Any]) -> dict[str, Any]:
    value = manifest.get("incremental_reprocessing")
    if not isinstance(value, dict):
        raise IncrementalReprocessingError(
            "重新处理记录缺少原增量 Batch 绑定。"
        )
    scope = manifest.get("scope")
    product_key = value.get("product_key")
    if (
        not isinstance(product_key, str)
        or not product_key
        or not isinstance(scope, dict)
        or scope.get("product_keys") != [product_key]
        or scope.get("languages") != list(LANGUAGES)
    ):
        raise IncrementalReprocessingError(
            "重新处理记录必须只包含一个完整双语产品。"
        )
    return value


def _required_text(
    value: dict[str, Any],
    field: str,
    label: str,
) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result.strip():
        raise IncrementalReprocessingError(f"{label}缺少 {field}。")
    return result


def _resolve_presented_path(
    value: Any,
    project_root: Path,
    *,
    label: str,
) -> Path:
    if not isinstance(value, str) or not value:
        raise IncrementalReprocessingError(f"{label}必须是非空路径。")
    path = Path(value)
    return (path if path.is_absolute() else project_root / path).resolve()


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IncrementalReprocessingError(
            f"无法读取{label} {path}：{error}"
        ) from error
    if not isinstance(value, dict):
        raise IncrementalReprocessingError(f"{label}必须包含 JSON 对象：{path}。")
    return value


__all__ = [
    "IncrementalReprocessingError",
    "IncrementalRunReference",
    "ReprocessingChain",
    "find_reprocessing_chain",
    "resolve_incremental_run_reference",
]
