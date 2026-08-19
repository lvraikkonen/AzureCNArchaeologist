"""Locate and freeze bilingual HTML inputs without changing their bytes."""

from __future__ import annotations

import os
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from src.core.catalog import LANGUAGES, ProcessingItem, ProductCatalog


class SourceInputError(RuntimeError):
    """A source file cannot be safely frozen."""


@dataclass(frozen=True)
class FrozenItem:
    """One source file that was copied or confirmed unchanged."""

    product_key: str
    language: str
    action: str
    source_relative_path: str
    frozen_relative_path: str
    byte_count: int

    def as_dict(self) -> dict[str, str | int]:
        return {
            "product_key": self.product_key,
            "language": self.language,
            "action": self.action,
            "source_relative_path": self.source_relative_path,
            "frozen_relative_path": self.frozen_relative_path,
            "byte_count": self.byte_count,
        }


@dataclass(frozen=True)
class ProductFreezeResult:
    """Bilingual input result for one product."""

    product_key: str
    status: str
    items: tuple[FrozenItem, ...]
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "product_key": self.product_key,
            "status": self.status,
            "items": [item.as_dict() for item in self.items],
        }
        if self.error is not None:
            result["error"] = self.error
        return result


@dataclass(frozen=True)
class FreezeReport:
    """Complete, readable result of one input-freezing operation."""

    selected_product_count: int
    selected_item_count: int
    results: tuple[ProductFreezeResult, ...]

    @property
    def passed_product_count(self) -> int:
        return sum(result.status == "passed" for result in self.results)

    @property
    def blocked_product_count(self) -> int:
        return sum(result.status == "blocked" for result in self.results)

    @property
    def passed_item_count(self) -> int:
        return sum(len(result.items) for result in self.results if result.status == "passed")

    @property
    def blocked_item_count(self) -> int:
        return self.selected_item_count - self.passed_item_count

    @property
    def succeeded(self) -> bool:
        return self.blocked_product_count == 0

    def as_dict(self) -> dict[str, object]:
        return {
            "summary": {
                "selected_products": self.selected_product_count,
                "selected_items": self.selected_item_count,
                "passed_products": self.passed_product_count,
                "passed_items": self.passed_item_count,
                "blocked_products": self.blocked_product_count,
                "blocked_items": self.blocked_item_count,
            },
            "products": [result.as_dict() for result in self.results],
        }


@dataclass(frozen=True)
class _PreparedItem:
    item: ProcessingItem
    source_path: Path
    destination_path: Path
    source_bytes: bytes
    previous_bytes: bytes | None
    action: str


class SourceInput:
    """Freeze selected products as indivisible Chinese-and-English pairs."""

    def __init__(
        self,
        catalog: ProductCatalog,
        *,
        source_root: Path | str | None = None,
        frozen_root: Path | str | None = None,
    ) -> None:
        self.catalog = catalog
        self.source_root = Path(
            source_root
            if source_root is not None
            else catalog.project_root / "data" / "current_prod_html"
        ).resolve()
        self.frozen_root = Path(
            frozen_root
            if frozen_root is not None
            else catalog.project_root / "data" / "prod-html"
        ).resolve()
        if self.source_root == self.frozen_root:
            raise SourceInputError("上游输入目录与 Frozen HTML 目录不能是同一个目录。")

    def freeze(self, items: Iterable[ProcessingItem]) -> FreezeReport:
        planned_items = tuple(items)
        grouped: dict[str, list[ProcessingItem]] = defaultdict(list)
        for item in planned_items:
            grouped[item.product_key].append(item)

        results: list[ProductFreezeResult] = []
        for product_key in sorted(grouped):
            product_items = tuple(grouped[product_key])
            language_order = tuple(item.language for item in product_items)
            if language_order != LANGUAGES:
                results.append(
                    ProductFreezeResult(
                        product_key=product_key,
                        status="blocked",
                        items=(),
                        error=(
                            "计划中的语言必须且只能按 zh-cn、en-us 各出现一次；"
                            f"实际为 {', '.join(language_order) or '空'}。"
                        ),
                    )
                )
                continue
            results.append(self._freeze_product(product_key, product_items))

        return FreezeReport(
            selected_product_count=len(grouped),
            selected_item_count=len(planned_items),
            results=tuple(results),
        )

    def _freeze_product(
        self, product_key: str, items: tuple[ProcessingItem, ...]
    ) -> ProductFreezeResult:
        try:
            prepared_items = tuple(self._prepare_item(item) for item in items)
        except (OSError, SourceInputError) as error:
            return ProductFreezeResult(
                product_key=product_key,
                status="blocked",
                items=(),
                error=str(error),
            )

        changed: list[_PreparedItem] = []
        try:
            for prepared in prepared_items:
                if prepared.action == "unchanged":
                    continue
                self._write_destination(
                    prepared.destination_path, prepared.source_bytes
                )
                changed.append(prepared)
                if prepared.destination_path.read_bytes() != prepared.source_bytes:
                    raise SourceInputError(
                        f"复制后字节不同：{prepared.item.frozen_relative_path.as_posix()}。"
                    )

            frozen_items: list[FrozenItem] = []
            for prepared in prepared_items:
                try:
                    current_source = prepared.source_path.read_bytes()
                    current_destination = prepared.destination_path.read_bytes()
                except OSError as error:
                    raise SourceInputError(
                        f"无法完成复制后字节比较：{prepared.item.product_key}/"
                        f"{prepared.item.language}：{error}"
                    ) from error
                if current_source != current_destination:
                    raise SourceInputError(
                        "复制前后字节不同，或上游文件在复制过程中发生了变化："
                        f"{prepared.item.product_key}/{prepared.item.language}。"
                    )
                frozen_items.append(
                    FrozenItem(
                        product_key=prepared.item.product_key,
                        language=prepared.item.language,
                        action=prepared.action,
                        source_relative_path=prepared.item.source_relative_path.as_posix(),
                        frozen_relative_path=prepared.item.frozen_relative_path.as_posix(),
                        byte_count=len(current_destination),
                    )
                )

            return ProductFreezeResult(
                product_key=product_key,
                status="passed",
                items=tuple(frozen_items),
            )
        except (OSError, SourceInputError) as error:
            rollback_errors = self._rollback(changed)
            message = str(error)
            if rollback_errors:
                message += " 回退失败：" + "；".join(rollback_errors)
            return ProductFreezeResult(
                product_key=product_key,
                status="blocked",
                items=(),
                error=message,
            )

    def _prepare_item(self, item: ProcessingItem) -> _PreparedItem:
        source_path = _safe_path(
            self.source_root,
            item.source_relative_path,
            label="上游源文件",
        )
        if source_path.is_symlink():
            raise SourceInputError(
                f"上游源文件不能是符号链接：{item.source_relative_path.as_posix()}。"
            )
        if not source_path.exists():
            raise SourceInputError(
                f"上游源文件不存在：{item.source_relative_path.as_posix()}。"
            )
        if not source_path.is_file():
            raise SourceInputError(
                f"上游源路径不是普通文件：{item.source_relative_path.as_posix()}。"
            )

        destination_path = _safe_path(
            self.frozen_root,
            item.frozen_relative_path,
            label="Frozen HTML",
        )
        if destination_path.is_symlink():
            raise SourceInputError(
                f"Frozen HTML 目标不能是符号链接："
                f"{item.frozen_relative_path.as_posix()}。"
            )
        if destination_path.exists() and not destination_path.is_file():
            raise SourceInputError(
                f"Frozen HTML 目标不是普通文件："
                f"{item.frozen_relative_path.as_posix()}。"
            )

        try:
            source_bytes = source_path.read_bytes()
            previous_bytes = (
                destination_path.read_bytes() if destination_path.exists() else None
            )
        except OSError as error:
            raise SourceInputError(
                f"无法读取 {item.product_key}/{item.language}：{error}"
            ) from error

        if previous_bytes == source_bytes:
            action = "unchanged"
        elif previous_bytes is None:
            action = "copied"
        else:
            action = "updated"

        return _PreparedItem(
            item=item,
            source_path=source_path,
            destination_path=destination_path,
            source_bytes=source_bytes,
            previous_bytes=previous_bytes,
            action=action,
        )

    def _write_destination(self, path: Path, content: bytes) -> None:
        _atomic_write(path, content)

    def _rollback(self, changed: list[_PreparedItem]) -> list[str]:
        errors: list[str] = []
        for prepared in reversed(changed):
            try:
                if prepared.previous_bytes is None:
                    prepared.destination_path.unlink(missing_ok=True)
                else:
                    _atomic_write(
                        prepared.destination_path, prepared.previous_bytes
                    )
            except OSError as error:
                errors.append(
                    f"{prepared.item.frozen_relative_path.as_posix()}：{error}"
                )
        return errors


def _safe_path(root: Path, relative: PurePosixPath, *, label: str) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise SourceInputError(
            f"{label}路径不能是绝对路径或越出规定目录：{relative.as_posix()}。"
        )
    candidate = root.joinpath(*relative.parts)
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(root)
    except ValueError as error:
        raise SourceInputError(
            f"{label}路径越出规定目录：{relative.as_posix()}。"
        ) from error
    return candidate


def _atomic_write(path: Path, content: bytes) -> None:
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
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
