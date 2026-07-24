"""Source-bound Region-Projected Shared Content evidence."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from bs4 import BeautifulSoup

from src.core.html_price_bearing import is_price_bearing_html
from src.core.scoped_source_content import CategoryAncestorFragment
from src.core.soft_category_config import (
    SOFT_CATEGORY_RELATIVE_PATH,
    SoftCategoryConfigError,
    load_soft_category_config,
)
from src.core.strict_soft_category_projection import (
    ExactTableRemovalError,
    remove_exact_owned_tables,
)
from src.utils.html.cleaner import clean_html_content


PROJECTION_ALGORITHM = "exact-table-id-nearest-scroll-table-v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class RegionProjectedSharedContentError(ValueError):
    """Region projection cannot be proved without guessing applicability."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "invalid_region_projected_shared_content",
        evidence: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.evidence = dict(evidence or {})


@dataclass(frozen=True)
class RegionProjectedSharedContentProjection:
    """Exact ancestor-content projection for one active Region."""

    region_value: str
    config_entry_index: int
    config_rule_table_ids: tuple[str, ...]
    removed_table_ids: tuple[str, ...]
    retained_table_ids: tuple[str, ...]
    projected_html: str
    projected_html_sha256: str

    def __post_init__(self) -> None:
        if not self.region_value.strip():
            raise ValueError("region_value must be non-empty")
        if self.config_entry_index < 0:
            raise ValueError("config_entry_index must be non-negative")
        for field_name, values in (
            ("config_rule_table_ids", self.config_rule_table_ids),
            ("removed_table_ids", self.removed_table_ids),
            ("retained_table_ids", self.retained_table_ids),
        ):
            if (
                not isinstance(values, tuple)
                or not values
                or any(not value.strip() for value in values)
                or len(values) != len(set(values))
            ):
                raise ValueError(
                    f"{field_name} must be unique non-empty strings"
                )
        if set(self.removed_table_ids).intersection(
            self.retained_table_ids
        ):
            raise ValueError(
                "removed_table_ids and retained_table_ids must be disjoint"
            )
        configured = set(self.config_rule_table_ids)
        if (
            not set(self.removed_table_ids).issubset(configured)
            or set(self.retained_table_ids).intersection(configured)
        ):
            raise ValueError(
                "Removed/retained source tables must exactly reflect the "
                "applicable soft-category rule"
            )
        if not self.projected_html.strip():
            raise ValueError("projected_html must be non-empty")
        if not _SHA256.fullmatch(self.projected_html_sha256):
            raise ValueError(
                "projected_html_sha256 must be lowercase SHA-256"
            )
        actual = hashlib.sha256(
            self.projected_html.encode("utf-8")
        ).hexdigest()
        if actual != self.projected_html_sha256:
            raise ValueError(
                "projected_html does not match projected_html_sha256"
            )

    @property
    def wire_html(self) -> str:
        return clean_html_content(self.projected_html)

    @property
    def wire_html_sha256(self) -> str:
        return hashlib.sha256(self.wire_html.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_value": self.region_value,
            "config_entry_index": self.config_entry_index,
            "config_rule_table_ids": list(self.config_rule_table_ids),
            "removed_table_ids": list(self.removed_table_ids),
            "retained_table_ids": list(self.retained_table_ids),
            "projected_html": self.projected_html,
            "projected_html_sha256": self.projected_html_sha256,
            "wire_html_sha256": self.wire_html_sha256,
        }


@dataclass(frozen=True)
class RegionProjectedSharedContentEvidence:
    """Frozen ancestor identity and every Region-specific projection."""

    projection_algorithm: str
    internal_software_value: str
    software_panel_id: str
    category_panel_ids: tuple[str, ...]
    fragment_count: int
    source_html: str
    source_html_sha256: str
    source_table_ids: tuple[str, ...]
    soft_category_path: str
    soft_category_sha256: str
    projections: tuple[RegionProjectedSharedContentProjection, ...]

    def __post_init__(self) -> None:
        if self.projection_algorithm != PROJECTION_ALGORITHM:
            raise ValueError(
                "projection_algorithm must identify the fail-closed projector"
            )
        if not self.internal_software_value.strip():
            raise ValueError("internal_software_value must be non-empty")
        if not self.software_panel_id.strip():
            raise ValueError("software_panel_id must be non-empty")
        if (
            not self.category_panel_ids
            or any(not value.strip() for value in self.category_panel_ids)
            or len(self.category_panel_ids) != len(set(self.category_panel_ids))
        ):
            raise ValueError(
                "category_panel_ids must be unique non-empty strings"
            )
        if self.fragment_count < 1:
            raise ValueError("fragment_count must be positive")
        if not self.source_html.strip():
            raise ValueError("source_html must be non-empty")
        if not _SHA256.fullmatch(self.source_html_sha256):
            raise ValueError("source_html_sha256 must be lowercase SHA-256")
        if hashlib.sha256(
            self.source_html.encode("utf-8")
        ).hexdigest() != self.source_html_sha256:
            raise ValueError("source_html does not match source_html_sha256")
        if (
            not self.source_table_ids
            or any(not value.strip() for value in self.source_table_ids)
            or len(self.source_table_ids) != len(set(self.source_table_ids))
        ):
            raise ValueError(
                "source_table_ids must be unique non-empty strings"
            )
        if not self.soft_category_path.strip():
            raise ValueError("soft_category_path must be non-empty")
        if not _SHA256.fullmatch(self.soft_category_sha256):
            raise ValueError(
                "soft_category_sha256 must be lowercase SHA-256"
            )
        if (
            not self.projections
            or len({value.region_value for value in self.projections})
            != len(self.projections)
        ):
            raise ValueError(
                "projections must contain unique Region identities"
            )
        source_tables = set(self.source_table_ids)
        for projection in self.projections:
            if (
                set(projection.removed_table_ids)
                | set(projection.retained_table_ids)
            ) != source_tables:
                raise ValueError(
                    "Each Region projection must partition source_table_ids"
                )

    def identity_dict(self) -> dict[str, Any]:
        """Return the compact evidence identity safe to freeze in a sidecar."""

        return {
            "schema_version": "1.0",
            "projection_algorithm": self.projection_algorithm,
            "scope": {
                "projection_filter_key": "region",
                "internal_software_value": self.internal_software_value,
                "software_panel_id": self.software_panel_id,
                "category_panel_ids": list(self.category_panel_ids),
            },
            "fragment_count": self.fragment_count,
            "source_html_sha256": self.source_html_sha256,
            "source_table_ids": sorted(self.source_table_ids),
            "applicability_config": {
                "path": self.soft_category_path,
                "sha256": self.soft_category_sha256,
            },
            "projections": [
                {
                    "region_value": projection.region_value,
                    "config_entry_index": projection.config_entry_index,
                    "config_rule_table_ids": list(
                        projection.config_rule_table_ids
                    ),
                    "removed_table_ids": sorted(
                        projection.removed_table_ids
                    ),
                    "retained_table_ids": sorted(
                        projection.retained_table_ids
                    ),
                    "projected_html_sha256": (
                        projection.projected_html_sha256
                    ),
                    "wire_html_sha256": projection.wire_html_sha256,
                }
                for projection in self.projections
            ],
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

    def projection_for(
        self, region_value: str
    ) -> RegionProjectedSharedContentProjection:
        matches = [
            value
            for value in self.projections
            if value.region_value == region_value
        ]
        if len(matches) != 1:
            raise RegionProjectedSharedContentError(
                f"Expected one shared-content projection for Region "
                f"{region_value!r}, found {len(matches)}"
            )
        return matches[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection_algorithm": self.projection_algorithm,
            "scope": {
                "projection_filter_key": "region",
                "internal_software_value": self.internal_software_value,
            },
            "software_panel_id": self.software_panel_id,
            "category_panel_ids": list(self.category_panel_ids),
            "placement": "content_group.sharedContent",
            "fragment_count": self.fragment_count,
            "source_html": self.source_html,
            "source_html_sha256": self.source_html_sha256,
            "source_table_ids": list(self.source_table_ids),
            "applicability_config": {
                "path": self.soft_category_path,
                "sha256": self.soft_category_sha256,
            },
            "evidence_sha256": self.evidence_sha256,
            "projections": [
                projection.to_dict() for projection in self.projections
            ],
        }


class RegionProjectedSharedContentResolver:
    """Prove price-bearing ancestor content against soft-category rules."""

    def __init__(
        self,
        root: str | Path,
        *,
        config_relative_path: str | Path = SOFT_CATEGORY_RELATIVE_PATH,
    ) -> None:
        self.root = Path(root).resolve()
        relative = Path(config_relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("config_relative_path must be repository-relative")
        self.config_relative_path = relative
        self.config_path = (self.root / relative).resolve()
        try:
            self.config_path.relative_to(self.root)
        except ValueError as error:
            raise ValueError(
                "soft-category configuration must remain inside root"
            ) from error

    def resolve(
        self,
        fragment: CategoryAncestorFragment,
        *,
        internal_software_value: str,
        region_values: tuple[str, ...],
    ) -> RegionProjectedSharedContentEvidence:
        if not isinstance(fragment, CategoryAncestorFragment):
            raise TypeError("fragment must be a CategoryAncestorFragment")
        if not fragment.table_ids:
            raise RegionProjectedSharedContentError(
                "Region-Projected Shared Content requires source tables"
            )
        if not internal_software_value.strip():
            raise RegionProjectedSharedContentError(
                "Region projection requires an internal software identity"
            )
        if (
            not isinstance(region_values, tuple)
            or not region_values
            or any(not value.strip() for value in region_values)
            or len(region_values) != len(set(region_values))
        ):
            raise RegionProjectedSharedContentError(
                "Region projection requires unique active Region values"
            )

        try:
            config = load_soft_category_config(
                self.root,
                relative_path=self.config_relative_path,
            )
        except SoftCategoryConfigError as error:
            raise RegionProjectedSharedContentError(
                str(error),
                code=error.code,
                evidence=error.evidence,
            ) from error
        projections: list[RegionProjectedSharedContentProjection] = []
        source_tables = fragment.table_ids
        self._validate_source_tables(fragment)
        source_table_set = set(source_tables)
        for region_value in region_values:
            matching = config.matching_entries(
                internal_software_value,
                region_value,
            )
            if not matching:
                raise RegionProjectedSharedContentError(
                    "soft-category has no exact rule for "
                    f"{internal_software_value!r}/{region_value!r}",
                    code="soft_category_missing_exact_pair",
                )
            if len(matching) > 1:
                raise RegionProjectedSharedContentError(
                    "Relevant soft-category rule is duplicated for "
                    f"{internal_software_value!r}/{region_value!r}: "
                    f"indices={tuple(entry.entry_index for entry in matching)!r}",
                    code="soft_category_duplicate_exact_pair",
                    evidence={
                        "software_value": internal_software_value,
                        "region_value": region_value,
                        "entry_indices": [
                            entry.entry_index for entry in matching
                        ],
                        "configuration": config.identity,
                    },
                )
            rule = matching[0]
            relevant_duplicate_ids = tuple(
                table_id
                for table_id in rule.duplicate_table_ids
                if table_id in source_table_set
            )
            if relevant_duplicate_ids:
                raise RegionProjectedSharedContentError(
                    "Relevant soft-category rule repeats source table IDs for "
                    f"{internal_software_value!r}/{region_value!r}: "
                    f"{relevant_duplicate_ids!r}",
                    code="soft_category_duplicate_relevant_table_id",
                    evidence={
                        "software_value": internal_software_value,
                        "region_value": region_value,
                        "entry_index": rule.entry_index,
                        "duplicate_table_ids": list(
                            rule.duplicate_table_ids
                        ),
                        "relevant_duplicate_table_ids": list(
                            relevant_duplicate_ids
                        ),
                        "configuration": config.identity,
                    },
                )
            configured_rule_table_ids = rule.unique_table_ids
            configured = frozenset(configured_rule_table_ids)
            removed = tuple(
                table_id
                for table_id in source_tables
                if table_id in configured
            )
            retained = tuple(
                table_id
                for table_id in source_tables
                if table_id not in configured
            )
            if not removed or not retained:
                raise RegionProjectedSharedContentError(
                    "Each Region projection must remove and retain at least one "
                    "ancestor table; "
                    f"{region_value!r} removes={removed!r}, "
                    f"retains={retained!r}"
                )

            try:
                projected_html, _ = remove_exact_owned_tables(
                    fragment.source_html,
                    removed_table_ids=removed,
                    retained_table_ids=retained,
                )
            except ExactTableRemovalError as error:
                raise RegionProjectedSharedContentError(
                    str(error),
                    code=error.code,
                    evidence=error.evidence,
                ) from error
            if not is_price_bearing_html(projected_html):
                raise RegionProjectedSharedContentError(
                    f"Region projection {region_value!r} is not visible and "
                    "price-bearing",
                    code="region_projected_shared_content_not_price_bearing",
                )
            projections.append(
                RegionProjectedSharedContentProjection(
                    region_value=region_value,
                    config_entry_index=rule.entry_index,
                    config_rule_table_ids=configured_rule_table_ids,
                    removed_table_ids=removed,
                    retained_table_ids=retained,
                    projected_html=projected_html,
                    projected_html_sha256=hashlib.sha256(
                        projected_html.encode("utf-8")
                    ).hexdigest(),
                )
            )

        return RegionProjectedSharedContentEvidence(
            projection_algorithm=PROJECTION_ALGORITHM,
            internal_software_value=internal_software_value,
            software_panel_id=fragment.software_panel_id,
            category_panel_ids=fragment.category_panel_ids,
            fragment_count=fragment.fragment_count,
            source_html=fragment.source_html,
            source_html_sha256=fragment.source_html_sha256,
            source_table_ids=fragment.table_ids,
            soft_category_path=config.relative_path,
            soft_category_sha256=config.sha256,
            projections=tuple(projections),
        )

    @staticmethod
    def _validate_source_tables(
        fragment: CategoryAncestorFragment,
    ) -> None:
        soup = BeautifulSoup(fragment.source_html, "html.parser")
        expected = set(fragment.table_ids)
        actual: list[str] = []
        for table in soup.find_all("table"):
            table_id = str(table.get("id", "")).strip()
            if not table_id:
                raise RegionProjectedSharedContentError(
                    "Region-projected source table has no stable id"
                )
            actual.append(table_id)
        if len(actual) != len(set(actual)):
            raise RegionProjectedSharedContentError(
                "Region-projected source table ids are duplicated"
            )
        if set(actual) != expected or len(actual) != len(
            fragment.table_ids
        ):
            raise RegionProjectedSharedContentError(
                "Frozen ancestor table identity differs from source HTML"
            )

__all__ = [
    "PROJECTION_ALGORITHM",
    "RegionProjectedSharedContentError",
    "RegionProjectedSharedContentEvidence",
    "RegionProjectedSharedContentProjection",
    "RegionProjectedSharedContentResolver",
    "SOFT_CATEGORY_RELATIVE_PATH",
]
