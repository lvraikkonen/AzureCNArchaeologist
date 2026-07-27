"""Fail-closed, replayable ``soft-category.json`` state projection.

The historical :class:`RegionProcessor` is intentionally permissive: missing
tables and partial removals are logged and the remaining HTML is returned.
That behaviour is unsuitable for the formal v0.4 complex extraction path.
This module projects one source-proven leaf state at a time and freezes enough
identity to replay the exact decision during persisted-payload validation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from bs4 import BeautifulSoup, Tag

from src.core.soft_category_config import (
    SOFT_CATEGORY_RELATIVE_PATH,
    SoftCategoryConfig,
    SoftCategoryConfigEntry,
    SoftCategoryConfigError,
    load_soft_category_config,
)

PROJECTION_ALGORITHM = "strict-soft-category-leaf-state-v1"
EVIDENCE_SCHEMA_VERSION = "1.1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FILTER_CONTROL_SELECTOR = (
    ".region-container, .software-kind-container, .category-container, "
    "select#region-box, select#software-box, select.category-tabs, "
    "ul.category-tabs"
)
_NESTED_PANEL_SELECTOR = (
    ".tab-panel[id], .tab-content[id], [role='tabpanel'][id]"
)


class StrictSoftCategoryProjectionError(ValueError):
    """A stable, fail-closed soft-category projection failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        evidence: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.evidence = dict(evidence or {})


class ExactTableRemovalError(ValueError):
    """One source fragment cannot be projected by exact DOM ownership."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        evidence: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.evidence = dict(evidence or {})


@dataclass(frozen=True)
class SoftCategoryConfigEntryEvidence:
    """One physically indexed matching configuration row."""

    entry_index: int
    table_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.entry_index < 0:
            raise ValueError("entry_index must be non-negative")
        if (
            any(not value.strip() for value in self.table_ids)
            or len(self.table_ids) != len(set(self.table_ids))
        ):
            raise ValueError(
                "table_ids must contain unique non-empty normalized IDs"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_index": self.entry_index,
            "table_ids": list(self.table_ids),
        }


@dataclass(frozen=True)
class IdlessSourceTableEvidence:
    """One unconditional idless table in physical source-table order."""

    physical_table_index: int
    normalized_html_sha256: str

    def __post_init__(self) -> None:
        if self.physical_table_index < 0:
            raise ValueError("physical_table_index must be non-negative")
        if not _SHA256.fullmatch(self.normalized_html_sha256):
            raise ValueError(
                "normalized_html_sha256 must be lowercase SHA-256"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "physical_table_index": self.physical_table_index,
            "normalized_html_sha256": self.normalized_html_sha256,
        }


@dataclass(frozen=True)
class SoftCategoryConfigurationFinding:
    """One reportable blocking error or nonblocking redundancy."""

    code: str
    software_value: str
    region_value: str
    entry_indices: tuple[int, ...]
    duplicate_table_ids: tuple[str, ...]
    difference_table_ids: tuple[str, ...]
    entry_table_ids: tuple[tuple[str, ...], ...]
    config_path: str
    config_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "software_value": self.software_value,
            "region_value": self.region_value,
            "entry_indices": list(self.entry_indices),
            "duplicate_table_ids": list(self.duplicate_table_ids),
            "difference_table_ids": list(self.difference_table_ids),
            "entries": [
                {
                    "entry_index": entry_index,
                    "table_ids": list(table_ids),
                }
                for entry_index, table_ids in zip(
                    self.entry_indices,
                    self.entry_table_ids,
                    strict=True,
                )
            ],
            "configuration": {
                "path": self.config_path,
                "sha256": self.config_sha256,
            },
        }


@dataclass(frozen=True)
class RemovalOwnershipEvidence:
    """Exact DOM ownership unit removed for one configured table."""

    table_id: str
    ownership_kind: str
    ownership_html_sha256: str
    ownership_table_ids: tuple[str, ...]
    filter_control_count: int
    nested_panel_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.table_id.strip():
            raise ValueError("table_id must be non-empty")
        if self.ownership_kind not in {"table", "scroll_table_wrapper"}:
            raise ValueError("ownership_kind is invalid")
        if not _SHA256.fullmatch(self.ownership_html_sha256):
            raise ValueError(
                "ownership_html_sha256 must be lowercase SHA-256"
            )
        if (
            self.ownership_table_ids != (self.table_id,)
            or self.filter_control_count != 0
            or self.nested_panel_ids
        ):
            raise ValueError(
                "A removal ownership unit must contain exactly the target "
                "table and no filter controls or nested panels"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_id": self.table_id,
            "ownership_kind": self.ownership_kind,
            "ownership_html_sha256": self.ownership_html_sha256,
            "ownership_table_ids": list(self.ownership_table_ids),
            "filter_control_count": self.filter_control_count,
            "nested_panel_ids": list(self.nested_panel_ids),
        }


def remove_exact_owned_tables(
    input_html: str,
    *,
    removed_table_ids: tuple[str, ...],
    retained_table_ids: tuple[str, ...],
    source_scope_id: str | None = None,
) -> tuple[str, tuple[RemovalOwnershipEvidence, ...]]:
    """Remove exact tables using one shared, fail-closed ownership primitive.

    ``source_scope_id`` selects one exact serialized state panel for the leaf
    projector.  ``None`` treats the complete serialized fragment as the
    ownership scope used by Region-Projected Shared Content.
    """

    if not isinstance(input_html, str):
        raise ExactTableRemovalError(
            "soft_category_projection_input_drift",
            "Serialized projection input must be a string",
        )
    projected = BeautifulSoup(input_html, "html.parser")
    if source_scope_id is None:
        scope: BeautifulSoup | Tag = projected
        scope_label = "<fragment>"
    else:
        scope_matches = projected.find_all(id=source_scope_id)
        if len(scope_matches) != 1 or not isinstance(scope_matches[0], Tag):
            raise ExactTableRemovalError(
                "soft_category_projection_input_drift",
                "Serialized state panel cannot be reconstructed exactly",
            )
        scope = scope_matches[0]
        scope_label = source_scope_id

    source_idless_table_html_sha256s = tuple(
        _normalized_table_html_sha256(table)
        for table in scope.find_all("table")
        if not str(table.get("id") or "").strip()
    )
    targets: list[Tag] = []
    ownership_units: list[RemovalOwnershipEvidence] = []
    for table_id in removed_table_ids:
        matches = scope.find_all(id=table_id)
        if len(matches) != 1 or matches[0].name != "table":
            raise ExactTableRemovalError(
                "soft_category_required_table_missing",
                (
                    f"Expected one exact removable table {table_id!r}, "
                    f"found {len(matches)}"
                ),
            )
        table = matches[0]
        target: Tag = table
        ownership_kind = "table"
        for parent in table.parents:
            if parent is scope:
                break
            if not isinstance(parent, Tag):
                continue
            classes = {
                str(value).strip()
                for value in parent.get("class", ())
            }
            if "scroll-table" in classes:
                target = parent
                ownership_kind = "scroll_table_wrapper"
                break
        if (
            not isinstance(scope, BeautifulSoup)
            and scope not in tuple(target.parents)
            and target is not scope
        ):
            raise ExactTableRemovalError(
                "soft_category_selector_crosses_state",
                (
                    f"Removal selector for {table_id!r} crosses the "
                    f"projection scope {scope_label!r}"
                ),
            )

        ownership_tables = (
            [target, *target.find_all("table")]
            if target is table
            else target.find_all("table")
        )
        ownership_table_ids = tuple(
            str(value.get("id") or "").strip()
            for value in ownership_tables
        )
        filter_controls = target.select(_FILTER_CONTROL_SELECTOR)
        nested_state_panels = target.select(_NESTED_PANEL_SELECTOR)
        nested_panel_ids = tuple(
            str(value.get("id") or "").strip()
            for value in nested_state_panels
        )
        ownership_inventory = {
            "ownership_kind": ownership_kind,
            "ownership_html_sha256": _sha256_text(str(target)),
            "ownership_table_count": len(ownership_tables),
            "ownership_table_ids": list(ownership_table_ids),
            "filter_control_count": len(filter_controls),
            "filter_control_tags": [
                value.name for value in filter_controls
            ],
            "nested_panel_ids": list(nested_panel_ids),
        }
        exact_table_ownership = (
            len(ownership_tables) == 1
            and ownership_tables[0] is table
            and ownership_table_ids == (table_id,)
            and not filter_controls
            and not nested_state_panels
        )
        if not exact_table_ownership:
            raise ExactTableRemovalError(
                "soft_category_ambiguous_removal_ownership",
                (
                    f"{ownership_kind} for configured table "
                    f"{table_id!r} is not an exact ownership unit"
                ),
                evidence={
                    "removal_table_id": table_id,
                    "wrapper_inventory": ownership_inventory,
                },
            )
        if all(target is not existing for existing in targets):
            targets.append(target)
        ownership_units.append(
            RemovalOwnershipEvidence(
                table_id=table_id,
                ownership_kind=ownership_kind,
                ownership_html_sha256=ownership_inventory[
                    "ownership_html_sha256"
                ],
                ownership_table_ids=ownership_table_ids,
                filter_control_count=len(filter_controls),
                nested_panel_ids=nested_panel_ids,
            )
        )

    for target in targets:
        target.decompose()
    output_html = str(scope)
    remaining: list[str] = []
    remaining_idless_table_html_sha256s: list[str] = []
    for table in scope.find_all("table"):
        table_id = str(table.get("id") or "").strip()
        if not table_id:
            remaining_idless_table_html_sha256s.append(
                _normalized_table_html_sha256(table)
            )
            continue
        if table_id in remaining:
            raise ExactTableRemovalError(
                "soft_category_projection_verification_failed",
                "Projected HTML contains duplicate identified table IDs",
            )
        remaining.append(table_id)
    if tuple(remaining) != retained_table_ids:
        raise ExactTableRemovalError(
            "soft_category_projection_verification_failed",
            (
                "Projected state did not retain the exact source table "
                f"order: expected={retained_table_ids!r}, "
                f"actual={tuple(remaining)!r}"
            ),
        )
    if (
        tuple(remaining_idless_table_html_sha256s)
        != source_idless_table_html_sha256s
    ):
        raise ExactTableRemovalError(
            "soft_category_projection_verification_failed",
            (
                "Projection changed unconditional idless tables or their "
                "physical order"
            ),
            evidence={
                "expected_idless_table_html_sha256s": list(
                    source_idless_table_html_sha256s
                ),
                "actual_idless_table_html_sha256s": list(
                    remaining_idless_table_html_sha256s
                ),
            },
        )
    for table_id in removed_table_ids:
        if scope.find_all(id=table_id):
            raise ExactTableRemovalError(
                "soft_category_projection_verification_failed",
                f"Configured table {table_id!r} remains after projection",
            )
    return output_html, tuple(ownership_units)


@dataclass(frozen=True)
class StrictSoftCategoryProjectionEvidence:
    """Frozen input/config/output identity for one reachable leaf state."""

    projection_algorithm: str
    region_value: str
    software_value: str
    source_panel_id: str
    source_table_count: int
    source_idless_table_count: int
    source_idless_tables: tuple[IdlessSourceTableEvidence, ...]
    source_idless_tables_aggregate_sha256: str
    source_table_ids: tuple[str, ...]
    matching_entries: tuple[SoftCategoryConfigEntryEvidence, ...]
    configured_union_table_ids: tuple[str, ...]
    configured_relevant_table_ids: tuple[str, ...]
    removed_table_ids: tuple[str, ...]
    retained_table_ids: tuple[str, ...]
    removal_ownership_units: tuple[RemovalOwnershipEvidence, ...]
    config_path: str
    config_sha256: str
    input_html: str
    input_html_sha256: str
    output_html: str
    output_html_sha256: str

    def __post_init__(self) -> None:
        if self.projection_algorithm != PROJECTION_ALGORITHM:
            raise ValueError("projection_algorithm is not the formal projector")
        for field_name, value in (
            ("region_value", self.region_value),
            ("software_value", self.software_value),
            ("source_panel_id", self.source_panel_id),
            ("config_path", self.config_path),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must be non-empty")
        if (
            self.source_table_count < 0
            or self.source_idless_table_count < 0
            or self.source_idless_table_count > self.source_table_count
            or len(self.source_table_ids)
            != self.source_table_count - self.source_idless_table_count
        ):
            raise ValueError(
                "source table counts must agree with source_table_ids"
            )
        if len(self.source_idless_tables) != self.source_idless_table_count:
            raise ValueError(
                "source_idless_tables must agree with "
                "source_idless_table_count"
            )
        idless_indices = tuple(
            value.physical_table_index
            for value in self.source_idless_tables
        )
        if (
            idless_indices != tuple(sorted(idless_indices))
            or len(idless_indices) != len(set(idless_indices))
            or any(
                value >= self.source_table_count
                for value in idless_indices
            )
        ):
            raise ValueError(
                "source_idless_tables must retain unique physical source order"
            )
        expected_idless_aggregate = _sha256_json([
            value.to_dict() for value in self.source_idless_tables
        ])
        if (
            self.source_idless_tables_aggregate_sha256
            != expected_idless_aggregate
        ):
            raise ValueError(
                "source_idless_tables_aggregate_sha256 does not match "
                "source_idless_tables"
            )
        for field_name, values in (
            ("source_table_ids", self.source_table_ids),
            ("configured_union_table_ids", self.configured_union_table_ids),
            (
                "configured_relevant_table_ids",
                self.configured_relevant_table_ids,
            ),
            ("removed_table_ids", self.removed_table_ids),
            ("retained_table_ids", self.retained_table_ids),
        ):
            if (
                any(not value.strip() for value in values)
                or len(values) != len(set(values))
            ):
                raise ValueError(
                    f"{field_name} must contain unique non-empty IDs"
                )
        if tuple(
            sorted(entry.entry_index for entry in self.matching_entries)
        ) != tuple(entry.entry_index for entry in self.matching_entries):
            raise ValueError("matching_entries must retain physical row order")
        source = set(self.source_table_ids)
        configured = set(self.configured_union_table_ids)
        relevant = set(self.configured_relevant_table_ids)
        removed = set(self.removed_table_ids)
        retained = set(self.retained_table_ids)
        if relevant != source.intersection(configured):
            raise ValueError(
                "configured_relevant_table_ids must be the source/config "
                "intersection"
            )
        if removed != relevant:
            raise ValueError(
                "removed_table_ids must equal configured relevant IDs"
            )
        if removed.intersection(retained) or removed.union(retained) != source:
            raise ValueError(
                "removed/retained table IDs must partition source_table_ids"
            )
        if tuple(
            unit.table_id for unit in self.removal_ownership_units
        ) != self.removed_table_ids:
            raise ValueError(
                "removal_ownership_units must exactly follow removed_table_ids"
            )
        for field_name, value in (
            ("config_sha256", self.config_sha256),
            (
                "source_idless_tables_aggregate_sha256",
                self.source_idless_tables_aggregate_sha256,
            ),
            ("input_html_sha256", self.input_html_sha256),
            ("output_html_sha256", self.output_html_sha256),
        ):
            if not _SHA256.fullmatch(value):
                raise ValueError(f"{field_name} must be lowercase SHA-256")
        if _sha256_text(self.input_html) != self.input_html_sha256:
            raise ValueError("input_html does not match input_html_sha256")
        if _sha256_text(self.output_html) != self.output_html_sha256:
            raise ValueError("output_html does not match output_html_sha256")
        if not removed and self.output_html != self.input_html:
            raise ValueError("A no-op projection must preserve exact input HTML")

    @property
    def matching_entry_indices(self) -> tuple[int, ...]:
        return tuple(entry.entry_index for entry in self.matching_entries)

    @property
    def is_noop(self) -> bool:
        return not self.removed_table_ids

    def identity_dict(self) -> dict[str, Any]:
        """Return the compact deterministic identity frozen in a sidecar."""

        return {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "projection_algorithm": self.projection_algorithm,
            "state_scope": {
                "region": self.region_value,
                "software": self.software_value,
                "source_panel_id": self.source_panel_id,
            },
            "applicability_config": {
                "path": self.config_path,
                "sha256": self.config_sha256,
                "matching_entries": [
                    entry.to_dict() for entry in self.matching_entries
                ],
            },
            "source_table_ids": list(self.source_table_ids),
            "source_table_count": self.source_table_count,
            "source_idless_table_count": self.source_idless_table_count,
            "source_idless_tables": [
                value.to_dict() for value in self.source_idless_tables
            ],
            "source_idless_tables_aggregate_sha256": (
                self.source_idless_tables_aggregate_sha256
            ),
            "configured_union_table_ids": list(
                self.configured_union_table_ids
            ),
            "configured_relevant_table_ids": list(
                self.configured_relevant_table_ids
            ),
            "removed_table_ids": list(self.removed_table_ids),
            "retained_table_ids": list(self.retained_table_ids),
            "removal_ownership_units": [
                unit.to_dict() for unit in self.removal_ownership_units
            ],
            "input_html_sha256": self.input_html_sha256,
            "output_html_sha256": self.output_html_sha256,
            "is_noop": self.is_noop,
        }

    @property
    def evidence_sha256(self) -> str:
        encoded = json.dumps(
            self.identity_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_dict(),
            "evidence_sha256": self.evidence_sha256,
            "input_html": self.input_html,
            "output_html": self.output_html,
        }


class StrictSoftCategoryProjector:
    """Project one exact source state with strict, replayable semantics."""

    def __init__(
        self,
        root: str | Path,
        *,
        config_relative_path: str | Path = SOFT_CATEGORY_RELATIVE_PATH,
    ) -> None:
        self.root = Path(root).resolve()
        relative = Path(config_relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(
                "soft-category config path must be repository-relative"
            )
        self.config_relative_path = relative
        self.config_path = (self.root / relative).resolve()
        try:
            self.config_path.relative_to(self.root)
        except ValueError as error:
            raise ValueError(
                "soft-category configuration must remain inside root"
            ) from error

    def project(
        self,
        source_soup: BeautifulSoup,
        *,
        source_panel_id: str,
        region_value: str,
        software_value: str,
    ) -> StrictSoftCategoryProjectionEvidence:
        """Return an exact projection or raise before emitting any content."""

        state_scope = {
            "region": region_value,
            "software": software_value,
            "source_panel_id": source_panel_id,
        }
        source_inventory = self._survey_source_inventory(
            source_soup,
            source_panel_id,
        )
        base_evidence: dict[str, Any] = {
            "state_scope": state_scope,
            "source_inventory": source_inventory,
        }
        try:
            config = load_soft_category_config(
                self.root,
                relative_path=self.config_relative_path,
            )
        except SoftCategoryConfigError as error:
            raise StrictSoftCategoryProjectionError(
                error.code,
                str(error),
                evidence={
                    **base_evidence,
                    **error.evidence,
                },
            ) from error
        base_evidence["configuration"] = config.identity

        try:
            if not isinstance(source_soup, BeautifulSoup):
                self._fail(
                    "soft_category_invalid_source_soup",
                    "source_soup must be BeautifulSoup",
                )
            if (
                not isinstance(source_panel_id, str)
                or not source_panel_id.strip()
            ):
                self._fail(
                    "soft_category_missing_state_panel",
                    "A strict soft-category projection requires a panel ID",
                )
            global_panels = source_soup.find_all(id=source_panel_id)
            if (
                len(global_panels) != 1
                or not isinstance(global_panels[0], Tag)
            ):
                self._fail(
                    "soft_category_ambiguous_state_panel",
                    (
                        f"Expected one exact source state panel "
                        f"{source_panel_id!r}, found {len(global_panels)}"
                    ),
                )
            panel = global_panels[0]
            input_html = str(panel)
            entries = self._matching_entries(
                config,
                software_value,
                region_value,
            )
            configured_union = tuple(dict.fromkeys(
                table_id
                for entry in entries
                for table_id in entry.table_ids
            ))
            (
                source_table_ids,
                source_table_count,
                source_idless_table_count,
                source_idless_tables,
                source_idless_tables_aggregate_sha256,
            ) = self._source_table_inventory(
                panel,
                source_panel_id=source_panel_id,
            )
            source_table_set = set(source_table_ids)
            configured_relevant = tuple(
                table_id
                for table_id in configured_union
                if table_id in source_table_set
            )
            removed = tuple(
                table_id
                for table_id in source_table_ids
                if table_id in set(configured_relevant)
            )
            retained = tuple(
                table_id
                for table_id in source_table_ids
                if table_id not in set(removed)
            )
            if removed:
                (
                    output_html,
                    removal_ownership_units,
                ) = self._remove_exact_tables(
                    input_html,
                    removed_table_ids=removed,
                    retained_table_ids=retained,
                    source_panel_id=source_panel_id,
                )
            else:
                output_html = input_html
                removal_ownership_units = ()
            evidence = StrictSoftCategoryProjectionEvidence(
                projection_algorithm=PROJECTION_ALGORITHM,
                region_value=region_value,
                software_value=software_value,
                source_panel_id=source_panel_id,
                source_table_count=source_table_count,
                source_idless_table_count=source_idless_table_count,
                source_idless_tables=source_idless_tables,
                source_idless_tables_aggregate_sha256=(
                    source_idless_tables_aggregate_sha256
                ),
                source_table_ids=source_table_ids,
                matching_entries=entries,
                configured_union_table_ids=configured_union,
                configured_relevant_table_ids=configured_relevant,
                removed_table_ids=removed,
                retained_table_ids=retained,
                removal_ownership_units=removal_ownership_units,
                config_path=config.relative_path,
                config_sha256=config.sha256,
                input_html=input_html,
                input_html_sha256=_sha256_text(input_html),
                output_html=output_html,
                output_html_sha256=_sha256_text(output_html),
            )
            self._verify_evidence_output(evidence)
            return evidence
        except StrictSoftCategoryProjectionError as error:
            error.evidence = {
                **base_evidence,
                **error.evidence,
            }
            raise

    def replay(
        self,
        source_soup: BeautifulSoup,
        expected: StrictSoftCategoryProjectionEvidence,
    ) -> StrictSoftCategoryProjectionEvidence:
        """Recompute an expected projection and reject any identity drift."""

        if not isinstance(expected, StrictSoftCategoryProjectionEvidence):
            try:
                configuration = load_soft_category_config(
                    self.root,
                    relative_path=self.config_relative_path,
                ).identity
            except SoftCategoryConfigError as error:
                raise StrictSoftCategoryProjectionError(
                    error.code,
                    str(error),
                    evidence={
                        "state_scope": None,
                        "source_inventory": (
                            self._survey_source_inventory(source_soup, "")
                        ),
                        **error.evidence,
                    },
                ) from error
            raise StrictSoftCategoryProjectionError(
                "soft_category_invalid_replay_evidence",
                "expected must be StrictSoftCategoryProjectionEvidence",
                evidence={
                    "state_scope": None,
                    "configuration": configuration,
                    "source_inventory": (
                        self._survey_source_inventory(source_soup, "")
                    ),
                },
            )
        replayed = self.project(
            source_soup,
            source_panel_id=expected.source_panel_id,
            region_value=expected.region_value,
            software_value=expected.software_value,
        )
        if replayed != expected:
            self._fail(
                "soft_category_projection_replay_mismatch",
                (
                    "Strict soft-category projection differs from frozen "
                    f"evidence for panel {expected.source_panel_id!r}"
                ),
                evidence={
                    "state_scope": {
                        "region": expected.region_value,
                        "software": expected.software_value,
                        "source_panel_id": expected.source_panel_id,
                    },
                    "configuration": {
                        "path": replayed.config_path,
                        "sha256": replayed.config_sha256,
                    },
                    "source_inventory": {
                        "source_panel_id": replayed.source_panel_id,
                        "source_table_count": replayed.source_table_count,
                        "source_idless_table_count": (
                            replayed.source_idless_table_count
                        ),
                        "source_idless_tables": [
                            value.to_dict()
                            for value in replayed.source_idless_tables
                        ],
                        "source_idless_tables_aggregate_sha256": (
                            replayed
                            .source_idless_tables_aggregate_sha256
                        ),
                        "source_table_ids": list(
                            replayed.source_table_ids
                        ),
                        "input_html_sha256": (
                            replayed.input_html_sha256
                        ),
                    },
                    "expected_evidence_sha256": expected.evidence_sha256,
                    "replayed_evidence_sha256": replayed.evidence_sha256,
                },
            )
        return replayed

    def configuration_findings(
        self,
    ) -> tuple[SoftCategoryConfigurationFinding, ...]:
        """Return every duplicate-pair/row-ID finding for upstream reporting.

        This is deliberately broader than formal projection.  A reachable
        state is blocked only by duplicate rows for its exact Software/Region
        key.  Repeated table IDs inside one row remain a nonblocking hygiene
        finding because runtime projection uses ordered unique IDs by physical
        first occurrence.
        """

        try:
            config = load_soft_category_config(
                self.root,
                relative_path=self.config_relative_path,
            )
        except SoftCategoryConfigError as error:
            raise StrictSoftCategoryProjectionError(
                error.code,
                str(error),
                evidence=error.evidence,
            ) from error
        return self._configuration_findings(config)

    @staticmethod
    def _configuration_findings(
        config: SoftCategoryConfig,
    ) -> tuple[SoftCategoryConfigurationFinding, ...]:
        grouped: dict[
            tuple[str, str], list[SoftCategoryConfigEntry]
        ] = {}
        for entry in config.entries:
            grouped.setdefault(
                (entry.software_value, entry.region_value), []
            ).append(entry)
        findings: list[SoftCategoryConfigurationFinding] = []
        for (software_value, region_value), values in grouped.items():
            entry_sets = [set(value.table_ids) for value in values]
            counts: dict[str, int] = {}
            for value in values:
                for table_id in set(value.unique_table_ids):
                    counts[table_id] = counts.get(table_id, 0) + 1
            duplicate_ids = tuple(
                table_id
                for table_id in dict.fromkeys(
                    table_id
                    for value in values
                    for table_id in value.unique_table_ids
                )
                if counts[table_id] > 1
            )
            union = set().union(*entry_sets) if entry_sets else set()
            intersection = (
                set.intersection(*entry_sets) if entry_sets else set()
            )
            difference = tuple(
                table_id
                for table_id in dict.fromkeys(
                    table_id
                    for value in values
                    for table_id in value.unique_table_ids
                )
                if table_id in union.difference(intersection)
            )
            if len(values) > 1:
                findings.append(SoftCategoryConfigurationFinding(
                    code="SOFT_CATEGORY_DUPLICATE_EXACT_PAIR",
                    software_value=software_value,
                    region_value=region_value,
                    entry_indices=tuple(
                        value.entry_index for value in values
                    ),
                    duplicate_table_ids=duplicate_ids,
                    difference_table_ids=difference,
                    entry_table_ids=tuple(
                        value.unique_table_ids for value in values
                    ),
                    config_path=config.relative_path,
                    config_sha256=config.sha256,
                ))
            for value in values:
                row_duplicates = value.duplicate_table_ids
                if row_duplicates:
                    findings.append(SoftCategoryConfigurationFinding(
                        code="SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW",
                        software_value=software_value,
                        region_value=region_value,
                        entry_indices=(value.entry_index,),
                        duplicate_table_ids=row_duplicates,
                        difference_table_ids=(),
                        entry_table_ids=(value.unique_table_ids,),
                        config_path=config.relative_path,
                        config_sha256=config.sha256,
                    ))
        return tuple(findings)

    def _matching_entries(
        self,
        config: SoftCategoryConfig,
        software_value: str,
        region_value: str,
    ) -> tuple[SoftCategoryConfigEntryEvidence, ...]:
        if (
            not isinstance(software_value, str)
            or not software_value.strip()
            or not isinstance(region_value, str)
            or not region_value.strip()
        ):
            self._fail(
                "soft_category_missing_state_identity",
                "Region and Software identities must be non-empty",
            )
        matching = config.matching_entries(
            software_value,
            region_value,
        )
        if len(matching) > 1:
            finding = next(
                finding
                for finding in self._configuration_findings(config)
                if (
                    finding.code == "SOFT_CATEGORY_DUPLICATE_EXACT_PAIR"
                    and finding.software_value == software_value
                    and finding.region_value == region_value
                )
            )
            self._fail(
                "soft_category_duplicate_exact_pair",
                (
                    "soft-category contains duplicate exact Software/Region "
                    f"rows for {software_value!r}/{region_value!r}: "
                    f"indices={finding.entry_indices!r}"
                ),
                evidence=finding.to_dict(),
            )
        return tuple(
            SoftCategoryConfigEntryEvidence(
                entry.entry_index,
                entry.unique_table_ids,
            )
            for entry in matching
        )

    @staticmethod
    def _survey_source_inventory(
        source_soup: Any,
        source_panel_id: Any,
    ) -> dict[str, Any]:
        inventory: dict[str, Any] = {
            "source_soup_type": type(source_soup).__name__,
            "source_panel_id": source_panel_id,
            "panel_match_count": 0,
        }
        if not isinstance(source_soup, BeautifulSoup):
            return inventory
        source_html = str(source_soup)
        inventory["source_html_sha256"] = _sha256_text(source_html)
        if not isinstance(source_panel_id, str) or not source_panel_id:
            return inventory
        panels = source_soup.find_all(id=source_panel_id)
        inventory["panel_match_count"] = len(panels)
        panel_inventories: list[dict[str, Any]] = []
        for panel in panels:
            panel_html = str(panel)
            tables = panel.find_all("table")
            table_ids = [
                str(table.get("id") or "").strip()
                for table in tables
            ]
            counts: dict[str, int] = {}
            for table_id in table_ids:
                if table_id:
                    counts[table_id] = counts.get(table_id, 0) + 1
            panel_inventories.append({
                "panel_html_sha256": _sha256_text(panel_html),
                "table_count": len(tables),
                "idless_table_count": sum(
                    1 for table_id in table_ids if not table_id
                ),
                "table_ids": table_ids,
                "duplicate_table_ids": [
                    table_id
                    for table_id in dict.fromkeys(table_ids)
                    if table_id and counts.get(table_id, 0) > 1
                ],
                "filter_control_count": len(
                    panel.select(_FILTER_CONTROL_SELECTOR)
                ),
                "nested_panel_ids": [
                    str(value.get("id") or "").strip()
                    for value in panel.select(_NESTED_PANEL_SELECTOR)
                    if value is not panel
                ],
            })
        inventory["panels"] = panel_inventories
        return inventory

    def _source_table_inventory(
        self,
        panel: Tag,
        *,
        source_panel_id: str,
    ) -> tuple[
        tuple[str, ...],
        int,
        int,
        tuple[IdlessSourceTableEvidence, ...],
        str,
    ]:
        values: list[str] = []
        idless_tables: list[IdlessSourceTableEvidence] = []
        tables = panel.find_all("table")
        for physical_table_index, table in enumerate(tables):
            table_id = str(table.get("id") or "").strip()
            if not table_id:
                idless_tables.append(IdlessSourceTableEvidence(
                    physical_table_index=physical_table_index,
                    normalized_html_sha256=(
                        _normalized_table_html_sha256(table)
                    ),
                ))
                continue
            if table_id in values:
                self._fail(
                    "soft_category_duplicate_source_table_id",
                    (
                        f"Source state panel {source_panel_id!r} contains "
                        f"duplicate table id {table_id!r}"
                    ),
                )
            values.append(table_id)
        frozen_idless_tables = tuple(idless_tables)
        return (
            tuple(values),
            len(tables),
            len(frozen_idless_tables),
            frozen_idless_tables,
            _sha256_json([
                value.to_dict() for value in frozen_idless_tables
            ]),
        )

    def _remove_exact_tables(
        self,
        input_html: str,
        *,
        removed_table_ids: tuple[str, ...],
        retained_table_ids: tuple[str, ...],
        source_panel_id: str,
    ) -> tuple[str, tuple[RemovalOwnershipEvidence, ...]]:
        try:
            return remove_exact_owned_tables(
                input_html,
                removed_table_ids=removed_table_ids,
                retained_table_ids=retained_table_ids,
                source_scope_id=source_panel_id,
            )
        except ExactTableRemovalError as error:
            self._fail(
                error.code,
                str(error),
                evidence=error.evidence,
            )

    def _verify_evidence_output(
        self,
        evidence: StrictSoftCategoryProjectionEvidence,
    ) -> None:
        (
            actual_table_ids,
            actual_idless_table_html_sha256s,
        ) = self._table_inventory_from_html(evidence.output_html)
        if actual_table_ids != evidence.retained_table_ids:
            self._fail(
                "soft_category_projection_verification_failed",
                (
                    "Frozen output table IDs differ from retained evidence: "
                    f"expected={evidence.retained_table_ids!r}, "
                    f"actual={actual_table_ids!r}"
                ),
            )
        expected_idless_table_html_sha256s = tuple(
            value.normalized_html_sha256
            for value in evidence.source_idless_tables
        )
        if (
            actual_idless_table_html_sha256s
            != expected_idless_table_html_sha256s
        ):
            self._fail(
                "soft_category_projection_verification_failed",
                (
                    "Frozen output changed unconditional idless tables or "
                    "their physical order"
                ),
                evidence={
                    "expected_idless_table_html_sha256s": list(
                        expected_idless_table_html_sha256s
                    ),
                    "actual_idless_table_html_sha256s": list(
                        actual_idless_table_html_sha256s
                    ),
                },
            )

    @staticmethod
    def _table_inventory_from_html(
        value: str,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        soup = BeautifulSoup(value, "html.parser")
        values: list[str] = []
        idless_table_html_sha256s: list[str] = []
        for table in soup.find_all("table"):
            table_id = str(table.get("id") or "").strip()
            if not table_id:
                idless_table_html_sha256s.append(
                    _normalized_table_html_sha256(table)
                )
                continue
            if table_id in values:
                raise StrictSoftCategoryProjectionError(
                    "soft_category_projection_verification_failed",
                    "Projected HTML contains duplicate identified table IDs",
                )
            values.append(table_id)
        return tuple(values), tuple(idless_table_html_sha256s)

    @staticmethod
    def _fail(
        code: str,
        message: str,
        *,
        evidence: Mapping[str, Any] | None = None,
    ) -> None:
        raise StrictSoftCategoryProjectionError(
            code,
            message,
            evidence=evidence,
        )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalized_table_html_sha256(table: Tag) -> str:
    """Hash BeautifulSoup's deterministic normalized table serialization."""

    return _sha256_text(str(table))


__all__ = [
    "EVIDENCE_SCHEMA_VERSION",
    "ExactTableRemovalError",
    "IdlessSourceTableEvidence",
    "PROJECTION_ALGORITHM",
    "RemovalOwnershipEvidence",
    "SOFT_CATEGORY_RELATIVE_PATH",
    "SoftCategoryConfigEntryEvidence",
    "SoftCategoryConfigurationFinding",
    "StrictSoftCategoryProjectionError",
    "StrictSoftCategoryProjectionEvidence",
    "StrictSoftCategoryProjector",
    "remove_exact_owned_tables",
]
