"""Read the trusted sparse region-to-table exclusion list."""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator


class SoftCategoryError(ValueError):
    """The trusted region configuration is missing or internally ambiguous."""


@dataclass(frozen=True)
class SoftCategoryLookup:
    """One exact configuration lookup made while processing a source page."""

    software: str
    region: str
    table_ids: tuple[str, ...]
    row_present: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "os": self.software,
            "region": self.region,
            "row_present": self.row_present,
            "table_ids": list(self.table_ids),
        }


class SoftCategoryUsageRecorder:
    """Collect unique readable lookups from one production extraction."""

    def __init__(self) -> None:
        self._lookups: dict[tuple[str, str], SoftCategoryLookup] = {}

    def record(self, lookup: SoftCategoryLookup) -> None:
        self._lookups[(lookup.software, lookup.region)] = lookup

    @property
    def lookups(self) -> tuple[SoftCategoryLookup, ...]:
        return tuple(self._lookups[key] for key in sorted(self._lookups))


_ACTIVE_LOOKUP_RECORDER: ContextVar[
    Callable[[SoftCategoryLookup], None] | None
] = ContextVar("soft_category_lookup_recorder", default=None)


@contextmanager
def capture_soft_category_usage() -> Iterator[SoftCategoryUsageRecorder]:
    """Capture lookups made in the current extraction thread."""

    recorder = SoftCategoryUsageRecorder()
    token = _ACTIVE_LOOKUP_RECORDER.set(recorder.record)
    try:
        yield recorder
    finally:
        _ACTIVE_LOOKUP_RECORDER.reset(token)


@dataclass(frozen=True)
class SoftCategoryRules:
    """Exact sparse `(software, region)` rows from ``soft-category.json``."""

    rows: dict[tuple[str, str], tuple[str, ...]]
    source_path: Path
    lookup_recorder: Callable[[SoftCategoryLookup], None] | None = None

    @classmethod
    def load(
        cls,
        path: Path | str,
        *,
        lookup_recorder: Callable[[SoftCategoryLookup], None] | None = None,
    ) -> "SoftCategoryRules":
        source_path = Path(path).resolve()
        try:
            raw: Any = json.loads(source_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SoftCategoryError(
                f"无法读取可信区域配置 {source_path}：{error}"
            ) from error
        if not isinstance(raw, list):
            raise SoftCategoryError("可信区域配置顶层必须是列表。")

        rows: dict[tuple[str, str], tuple[str, ...]] = {}
        for index, value in enumerate(raw):
            if not isinstance(value, dict):
                raise SoftCategoryError(f"区域配置第 {index + 1} 项必须是对象。")
            software = _required_text(value, "os", index)
            region = _required_text(value, "region", index)
            key = (software, region)
            if key in rows:
                raise SoftCategoryError(
                    f"区域配置重复声明 software={software!r}、region={region!r}。"
                )
            raw_table_ids = value.get("tableIDs")
            if not isinstance(raw_table_ids, list):
                raise SoftCategoryError(
                    f"区域配置 software={software!r}、region={region!r} "
                    "的 tableIDs 必须是列表。"
                )
            table_ids: list[str] = []
            for raw_table_id in raw_table_ids:
                if not isinstance(raw_table_id, str):
                    raise SoftCategoryError(
                        f"区域配置 software={software!r}、region={region!r} "
                        "包含非文本表格名称。"
                    )
                table_id = raw_table_id.strip().removeprefix("#")
                if not table_id:
                    raise SoftCategoryError(
                        f"区域配置 software={software!r}、region={region!r} "
                        "包含空表格名称。"
                    )
                if table_id not in table_ids:
                    table_ids.append(table_id)
            rows[key] = tuple(table_ids)
        effective_recorder = (
            lookup_recorder
            if lookup_recorder is not None
            else _ACTIVE_LOOKUP_RECORDER.get()
        )
        return cls(
            rows=rows,
            source_path=source_path,
            lookup_recorder=effective_recorder,
        )

    def excluded_table_ids(self, software: str, region: str) -> tuple[str, ...]:
        # The upstream file is an exclusion list, not a complete state matrix.
        # A missing exact row means that this region excludes no named table.
        key = (software, region)
        table_ids = self.rows.get(key, ())
        if self.lookup_recorder is not None:
            self.lookup_recorder(
                SoftCategoryLookup(
                    software=software,
                    region=region,
                    table_ids=table_ids,
                    row_present=key in self.rows,
                )
            )
        return table_ids


def _required_text(value: dict[str, Any], field: str, index: int) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result.strip():
        raise SoftCategoryError(
            f"区域配置第 {index + 1} 项的 {field} 必须是非空文本。"
        )
    return result.strip()
