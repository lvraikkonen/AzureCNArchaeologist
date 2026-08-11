"""One strict loader for the historical soft-category applicability map."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SOFT_CATEGORY_RELATIVE_PATH = Path("data/configs/soft-category.json")


class SoftCategoryConfigError(ValueError):
    """The applicability configuration cannot be interpreted exactly."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        evidence: dict[str, Any],
    ) -> None:
        super().__init__(message)
        self.code = code
        self.evidence = evidence


class _DuplicateObjectKey(ValueError):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


@dataclass(frozen=True)
class SoftCategoryConfigEntry:
    entry_index: int
    software_value: str
    region_value: str
    raw_table_ids: tuple[str, ...]
    table_ids: tuple[str, ...]

    @property
    def unique_table_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(self.table_ids))

    @property
    def duplicate_table_ids(self) -> tuple[str, ...]:
        seen: set[str] = set()
        duplicates: list[str] = []
        for table_id in self.table_ids:
            if table_id in seen and table_id not in duplicates:
                duplicates.append(table_id)
            seen.add(table_id)
        return tuple(duplicates)


@dataclass(frozen=True)
class SoftCategoryConfig:
    relative_path: str
    absolute_path: Path
    size_bytes: int
    sha256: str
    entries: tuple[SoftCategoryConfigEntry, ...]

    def matching_entries(
        self,
        software_value: str,
        region_value: str,
    ) -> tuple[SoftCategoryConfigEntry, ...]:
        return tuple(
            entry
            for entry in self.entries
            if (
                entry.software_value == software_value
                and entry.region_value == region_value
            )
        )

    @property
    def identity(self) -> dict[str, Any]:
        return {
            "path": self.relative_path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


def normalize_soft_category_table_id(value: str) -> str:
    """Normalize one historical selector to its exact HTML ``id`` value."""

    return value.strip().removeprefix("#").strip()


def load_soft_category_config(
    root: str | Path,
    *,
    relative_path: str | Path = SOFT_CATEGORY_RELATIVE_PATH,
) -> SoftCategoryConfig:
    """Read and validate the applicability map without last-write-wins."""

    root_path = Path(root).resolve()
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(
            "soft-category config path must be repository-relative"
        )
    path = (root_path / relative).resolve()
    try:
        path.relative_to(root_path)
    except ValueError as error:
        raise ValueError(
            "soft-category configuration must remain inside root"
        ) from error

    relative_name = relative.as_posix()
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise SoftCategoryConfigError(
            "soft_category_config_unreadable",
            f"Unable to read soft-category configuration: {error}",
            evidence={
                "configuration": {
                    "path": relative_name,
                    "size_bytes": None,
                    "sha256": None,
                }
            },
        ) from error
    identity = {
        "path": relative_name,
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }

    def unique_object(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise _DuplicateObjectKey(key)
            result[key] = value
        return result

    try:
        text = raw.decode("utf-8-sig", errors="strict")
        value = json.loads(text, object_pairs_hook=unique_object)
    except _DuplicateObjectKey as error:
        raise SoftCategoryConfigError(
            "soft_category_config_duplicate_json_key",
            (
                "soft-category configuration contains duplicate JSON "
                f"object key {error.key!r}"
            ),
            evidence={
                "configuration": identity,
                "duplicate_object_key": error.key,
            },
        ) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SoftCategoryConfigError(
            "soft_category_config_invalid",
            f"Invalid strict UTF-8 JSON soft-category configuration: {error}",
            evidence={"configuration": identity},
        ) from error
    if not isinstance(value, list):
        raise SoftCategoryConfigError(
            "soft_category_config_invalid",
            "soft-category configuration must be an array",
            evidence={"configuration": identity},
        )

    entries: list[SoftCategoryConfigEntry] = []
    for index, item in enumerate(value):
        row_evidence = {
            "configuration": identity,
            "entry_index": index,
        }
        if not isinstance(item, dict):
            raise SoftCategoryConfigError(
                "soft_category_config_invalid",
                f"soft-category row {index} must be an object",
                evidence=row_evidence,
            )
        if set(item) != {"os", "region", "tableIDs"}:
            raise SoftCategoryConfigError(
                "soft_category_config_invalid",
                (
                    f"soft-category row {index} must contain exactly "
                    "os, region, and tableIDs"
                ),
                evidence={
                    **row_evidence,
                    "observed_keys": sorted(str(key) for key in item),
                },
            )
        software = item["os"]
        region = item["region"]
        raw_table_ids = item["tableIDs"]
        if (
            not isinstance(software, str)
            or not software
            or software != software.strip()
        ):
            raise SoftCategoryConfigError(
                "soft_category_config_invalid",
                (
                    f"soft-category row {index} has a noncanonical os "
                    "identity"
                ),
                evidence=row_evidence,
            )
        if (
            not isinstance(region, str)
            or not region
            or region != region.strip()
        ):
            raise SoftCategoryConfigError(
                "soft_category_config_invalid",
                (
                    f"soft-category row {index} has a noncanonical region "
                    "identity"
                ),
                evidence=row_evidence,
            )
        if not isinstance(raw_table_ids, list):
            raise SoftCategoryConfigError(
                "soft_category_config_invalid",
                f"soft-category row {index} tableIDs must be an array",
                evidence=row_evidence,
            )
        normalized: list[str] = []
        for table_index, raw_table_id in enumerate(raw_table_ids):
            if not isinstance(raw_table_id, str):
                raise SoftCategoryConfigError(
                    "soft_category_config_invalid",
                    (
                        f"soft-category row {index} tableIDs[{table_index}] "
                        "must be a string"
                    ),
                    evidence={
                        **row_evidence,
                        "table_id_index": table_index,
                    },
                )
            table_id = normalize_soft_category_table_id(raw_table_id)
            if not table_id:
                raise SoftCategoryConfigError(
                    "soft_category_config_invalid",
                    (
                        f"soft-category row {index} tableIDs[{table_index}] "
                        "has an empty normalized identity"
                    ),
                    evidence={
                        **row_evidence,
                        "table_id_index": table_index,
                    },
                )
            normalized.append(table_id)
        entries.append(SoftCategoryConfigEntry(
            entry_index=index,
            software_value=software,
            region_value=region,
            raw_table_ids=tuple(raw_table_ids),
            table_ids=tuple(normalized),
        ))

    return SoftCategoryConfig(
        relative_path=relative_name,
        absolute_path=path,
        size_bytes=len(raw),
        sha256=identity["sha256"],
        entries=tuple(entries),
    )


__all__ = [
    "SOFT_CATEGORY_RELATIVE_PATH",
    "SoftCategoryConfig",
    "SoftCategoryConfigEntry",
    "SoftCategoryConfigError",
    "load_soft_category_config",
    "normalize_soft_category_table_id",
]
