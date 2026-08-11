"""Source-driven evidence for intentionally empty CMS selection states.

An empty-state exception is derived only from the already frozen strict
soft-category projection attached to one source-proven reachable state.  This
module never re-reads or re-selects a ``soft-category.json`` rule, so the
projection and the empty-state decision cannot drift into two competing
sources of truth.

The predicate here is intentionally source-side and independent from payload
validation.  A projected state is considered price-bearing when it retains a
visible table, structured price markup, an explicit monetary amount/rate, or
an explicit free-price statement.  Only a successful, applicable projection
whose output lacks all of those signals can establish an empty-state finding.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.core.canonical_input import CanonicalHtmlInput
from src.core.html_price_bearing import (
    PRICE_BEARING_CLASSIFIER_VERSION,
    is_price_bearing_html,
)

if TYPE_CHECKING:
    from src.core.source_reachability import (
        ReachabilitySourceEvidence,
        SourceReachability,
    )


SOFT_CATEGORY_RELATIVE_PATH = Path("data/configs/soft-category.json")
PRICE_BEARING_PREDICATE = PRICE_BEARING_CLASSIFIER_VERSION
RENDERED_COMPOSITION_ALGORITHM = (
    "software-prefix+strict-leaf+region-shared-v1"
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


class SourceStateEvidenceError(RuntimeError):
    """Frozen source-state evidence is missing or internally inconsistent."""


@dataclass(frozen=True)
class StateCriterion:
    filter_key: str
    match_value: str

    def to_dict(self) -> dict[str, str]:
        return {
            "filterKey": self.filter_key,
            "matchValues": self.match_value,
        }


@dataclass(frozen=True)
class SelectorContext:
    filter_key: str
    match_value: str
    source_panel_id: str
    active_cms_key: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "filterKey": self.filter_key,
            "matchValues": self.match_value,
            "source_panel_id": self.source_panel_id,
            "active_cms_key": self.active_cms_key,
        }


@dataclass(frozen=True)
class RenderedPrefixIdentity:
    software_value: str
    software_panel_id: str
    category_panel_ids: tuple[str, ...]
    fragment_count: int
    source_html_sha256: str

    def identity_dict(self) -> dict[str, Any]:
        return {
            "software_value": self.software_value,
            "software_panel_id": self.software_panel_id,
            "category_panel_ids": list(self.category_panel_ids),
            "fragment_count": self.fragment_count,
            "source_html_sha256": self.source_html_sha256,
        }

    def to_participant_dict(self) -> dict[str, Any]:
        identity = self.identity_dict()
        return {
            "role": "software_scoped_prefix",
            **identity,
            "identity_sha256": _sha256_json(identity),
            "html_sha256": self.source_html_sha256,
        }


@dataclass(frozen=True)
class RenderedSharedProjectionIdentity:
    projection_algorithm: str
    evidence_sha256: str
    source_html_sha256: str
    internal_software_value: str
    software_panel_id: str
    category_panel_ids: tuple[str, ...]
    region_value: str
    projected_html_sha256: str
    wire_html_sha256: str
    config_path: str
    config_sha256: str
    config_entry_index: int
    config_rule_table_ids: tuple[str, ...]
    removed_table_ids: tuple[str, ...]
    retained_table_ids: tuple[str, ...]

    def to_participant_dict(self) -> dict[str, Any]:
        return {
            "role": "region_projected_shared_content",
            "projection_algorithm": self.projection_algorithm,
            "evidence_sha256": self.evidence_sha256,
            "source_html_sha256": self.source_html_sha256,
            "scope": {
                "internal_software_value": self.internal_software_value,
                "software_panel_id": self.software_panel_id,
                "category_panel_ids": list(self.category_panel_ids),
                "region_value": self.region_value,
            },
            "projected_html_sha256": self.projected_html_sha256,
            "wire_html_sha256": self.wire_html_sha256,
            "applicability_config": {
                "path": self.config_path,
                "sha256": self.config_sha256,
                "entry_index": self.config_entry_index,
                "rule_table_ids": list(self.config_rule_table_ids),
                "removed_table_ids": list(self.removed_table_ids),
                "retained_table_ids": list(self.retained_table_ids),
            },
            "html_sha256": self.projected_html_sha256,
        }


@dataclass(frozen=True)
class SourceConfirmedEmptyState:
    """One replayable empty-state finding derived from strict projection."""

    product_key: str
    language: str
    state_tuple: tuple[StateCriterion, ...]
    source_selector_context: tuple[SelectorContext, ...]
    source_path: str
    source_sha256: str
    source_panel_id: str
    source_table_ids: tuple[str, ...]
    config_path: str
    config_sha256: str
    config_entry_index: int
    config_entry_table_ids: tuple[str, ...]
    config_os: str
    config_region: str
    covering_removal_table_ids: tuple[str, ...]
    retained_table_ids: tuple[str, ...]
    projection_algorithm: str
    projection_evidence_sha256: str
    projection_input_html_sha256: str
    projected_html_sha256: str
    rendered_prefix_identity: RenderedPrefixIdentity | None
    rendered_shared_projection_identity: (
        RenderedSharedProjectionIdentity | None
    )
    rendered_composition_sha256: str
    rendered_composition_identity_sha256: str

    def to_cms_state(self) -> Any:
        """Return the validator's exact ordered state identity."""

        from src.core.cms_state_contract import CmsState

        return CmsState(
            tuple(
                (criterion.filter_key, criterion.match_value)
                for criterion in self.state_tuple
            )
        )

    def to_dict(self) -> dict[str, Any]:
        rendered_participants = self._rendered_participants()
        return {
            "schema_version": "1.0",
            "code": "SOURCE_CONFIRMED_EMPTY_STATE",
            "category": "cms_state",
            "severity": "warning",
            "product_key": self.product_key,
            "language": self.language,
            "state_tuple": [
                criterion.to_dict() for criterion in self.state_tuple
            ],
            "source_selector_context": [
                selector.to_dict() for selector in self.source_selector_context
            ],
            "source": {
                "path": self.source_path,
                "sha256": self.source_sha256,
                "panel_id": self.source_panel_id,
                "table_ids": list(self.source_table_ids),
            },
            "configuration": {
                "path": self.config_path,
                "sha256": self.config_sha256,
                "entry_index": self.config_entry_index,
                "entry_table_ids": list(self.config_entry_table_ids),
                "os": self.config_os,
                "region": self.config_region,
                "covering_removal_table_ids": list(
                    self.covering_removal_table_ids
                ),
                "retained_table_ids": list(self.retained_table_ids),
            },
            "projection": {
                "algorithm": self.projection_algorithm,
                "evidence_sha256": self.projection_evidence_sha256,
                "input_html_sha256": self.projection_input_html_sha256,
                "output_html_sha256": self.projected_html_sha256,
            },
            "rendered_content": {
                "composition_algorithm": RENDERED_COMPOSITION_ALGORITHM,
                "participants": rendered_participants,
                "combined_html_sha256": (
                    self.rendered_composition_sha256
                ),
                "identity_sha256": (
                    self.rendered_composition_identity_sha256
                ),
            },
            "proof": {
                "rule": (
                    "rendered_state_composition_has_no_price_bearing_content"
                ),
                "price_bearing_predicate": PRICE_BEARING_PREDICATE,
                "rendered_composition_price_bearing": False,
            },
        }

    def _rendered_participants(self) -> list[dict[str, Any]]:
        participants: list[dict[str, Any]] = []
        if self.rendered_prefix_identity is not None:
            participants.append(
                self.rendered_prefix_identity.to_participant_dict()
            )
        participants.append({
            "role": "strict_soft_category_projection",
            "projection_algorithm": self.projection_algorithm,
            "evidence_sha256": self.projection_evidence_sha256,
            "input_html_sha256": self.projection_input_html_sha256,
            "output_html_sha256": self.projected_html_sha256,
            "html_sha256": self.projected_html_sha256,
        })
        if self.rendered_shared_projection_identity is not None:
            participants.append(
                self.rendered_shared_projection_identity
                .to_participant_dict()
            )
        return participants


class SourceStateEvidenceResolver:
    """Derive empty states solely from frozen strict projection evidence."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def resolve(
        self,
        canonical_input: CanonicalHtmlInput,
        *,
        source_reachability: SourceReachability,
    ) -> tuple[SourceConfirmedEmptyState, ...]:
        """Return strict-projection-backed non-price-bearing reachable states."""

        from src.core.source_reachability import SourceReachability

        if not isinstance(canonical_input, CanonicalHtmlInput):
            raise TypeError("canonical_input must be CanonicalHtmlInput")
        if not isinstance(source_reachability, SourceReachability):
            raise TypeError("source_reachability must be SourceReachability")
        self._validate_identity(canonical_input, source_reachability)

        source_path = self._relative_path(canonical_input.source_path)
        findings: list[SourceConfirmedEmptyState] = []
        for state in source_reachability.ordered_states:
            source = state.source_evidence
            projection = source.strict_soft_category_projection
            if projection is None:
                continue
            self._validate_projection_scope(source, projection)
            # A no-op or configuration-irrelevant projection is not authority
            # for declaring a source state empty.
            if (
                projection.is_noop
                or not projection.removed_table_ids
                or projection.retained_table_ids
                or projection.source_idless_table_count
                or len(projection.matching_entries) != 1
            ):
                continue
            (
                prefix_identity,
                prefix_html,
            ) = self._rendered_prefix(source)
            (
                shared_identity,
                shared_html,
            ) = self._rendered_shared_projection(source, projection)
            rendered_parts = [
                value
                for value in (
                    prefix_html,
                    projection.output_html,
                    shared_html,
                )
                if value is not None
            ]
            rendered_html = "\n".join(rendered_parts)
            if is_price_bearing_html(rendered_html):
                continue

            entry = projection.matching_entries[0]
            state_tuple = tuple(
                StateCriterion(filter_key, match_value)
                for filter_key, match_value in state.cms_state.criteria
            )
            findings.append(SourceConfirmedEmptyState(
                product_key=canonical_input.product_key,
                language=canonical_input.language,
                state_tuple=state_tuple,
                source_selector_context=self._selector_context(
                    source,
                    active_filter_keys={
                        criterion.filter_key for criterion in state_tuple
                    },
                ),
                source_path=source_path,
                source_sha256=canonical_input.source_sha256,
                source_panel_id=projection.source_panel_id,
                source_table_ids=projection.source_table_ids,
                config_path=projection.config_path,
                config_sha256=projection.config_sha256,
                config_entry_index=entry.entry_index,
                config_entry_table_ids=entry.table_ids,
                config_os=projection.software_value,
                config_region=projection.region_value,
                covering_removal_table_ids=projection.removed_table_ids,
                retained_table_ids=projection.retained_table_ids,
                projection_algorithm=projection.projection_algorithm,
                projection_evidence_sha256=projection.evidence_sha256,
                projection_input_html_sha256=(
                    projection.input_html_sha256
                ),
                projected_html_sha256=projection.output_html_sha256,
                rendered_prefix_identity=prefix_identity,
                rendered_shared_projection_identity=shared_identity,
                rendered_composition_sha256=_sha256_text(
                    rendered_html
                ),
                rendered_composition_identity_sha256=_sha256_json({
                    "composition_algorithm": (
                        RENDERED_COMPOSITION_ALGORITHM
                    ),
                    "participants": self._rendered_participant_dicts(
                        projection,
                        prefix_identity,
                        shared_identity,
                    ),
                }),
            ))
        return tuple(findings)

    def resolve_cms_states(
        self,
        canonical_input: CanonicalHtmlInput,
        *,
        source_reachability: SourceReachability,
    ) -> tuple[Any, ...]:
        """Return the validator's exact ordered ``CmsState`` identities."""

        return tuple(
            finding.to_cms_state()
            for finding in self.resolve(
                canonical_input,
                source_reachability=source_reachability,
            )
        )

    def resolve_dicts(
        self,
        canonical_input: CanonicalHtmlInput,
        *,
        source_reachability: SourceReachability,
    ) -> tuple[dict[str, Any], ...]:
        return tuple(
            item.to_dict()
            for item in self.resolve(
                canonical_input,
                source_reachability=source_reachability,
            )
        )

    def _validate_identity(
        self,
        canonical_input: CanonicalHtmlInput,
        source_reachability: SourceReachability,
    ) -> None:
        if (
            source_reachability.product_key != canonical_input.product_key
            or source_reachability.language != canonical_input.language
            or source_reachability.source_sha256
            != canonical_input.source_sha256
            or source_reachability.normalized_sha256
            != canonical_input.normalized_sha256
            or self._resolved_identity_path(source_reachability.source_path)
            != canonical_input.source_path.resolve()
            or self._resolved_identity_path(
                source_reachability.normalized_path
            )
            != canonical_input.normalized_path.resolve()
        ):
            raise SourceStateEvidenceError(
                "SourceReachability identity differs from the canonical input"
            )

    @staticmethod
    def _validate_projection_scope(
        source: ReachabilitySourceEvidence,
        projection: Any,
    ) -> None:
        expected_panel_id = (
            source.category_panel_id or source.software_panel_id
        )
        if (
            projection.region_value != source.region_value
            or projection.software_value != source.software_value
            or projection.source_panel_id != expected_panel_id
        ):
            raise SourceStateEvidenceError(
                "Strict projection scope differs from its reachable source state"
            )

    @staticmethod
    def _rendered_prefix(
        source: ReachabilitySourceEvidence,
    ) -> tuple[RenderedPrefixIdentity | None, str | None]:
        prefix = source.software_scoped_prefix
        if prefix is None:
            return None, None
        category_panel_id = (
            source.category_panel_id or source.category_value
        )
        if (
            source.software_value is None
            or source.software_panel_id is None
            or category_panel_id is None
            or prefix.software_value != source.software_value
            or prefix.software_panel_id != source.software_panel_id
            or category_panel_id not in prefix.category_panel_ids
        ):
            raise SourceStateEvidenceError(
                "Software-scoped prefix scope differs from its reachable state"
            )
        identity = RenderedPrefixIdentity(
            software_value=prefix.software_value,
            software_panel_id=prefix.software_panel_id,
            category_panel_ids=prefix.category_panel_ids,
            fragment_count=prefix.fragment_count,
            source_html_sha256=prefix.source_html_sha256,
        )
        return identity, prefix.source_html

    @staticmethod
    def _rendered_shared_projection(
        source: ReachabilitySourceEvidence,
        strict_projection: Any,
    ) -> tuple[RenderedSharedProjectionIdentity | None, str | None]:
        shared = source.region_projected_shared_content
        if shared is None:
            return None, None
        category_panel_id = (
            source.category_panel_id or source.category_value
        )
        if (
            source.region_value is None
            or source.software_value is None
            or source.software_panel_id is None
            or category_panel_id is None
            or shared.internal_software_value != source.software_value
            or shared.software_panel_id != source.software_panel_id
            or category_panel_id not in shared.category_panel_ids
            or shared.soft_category_path != strict_projection.config_path
            or shared.soft_category_sha256
            != strict_projection.config_sha256
        ):
            raise SourceStateEvidenceError(
                "Region-projected shared-content scope or config differs "
                "from its reachable strict projection"
            )
        try:
            projected = shared.projection_for(source.region_value)
        except ValueError as error:
            raise SourceStateEvidenceError(
                "Region-projected shared content has no exact current-Region "
                "projection"
            ) from error
        if projected.region_value != source.region_value:
            raise SourceStateEvidenceError(
                "Region-projected shared content selected the wrong Region"
            )
        identity = RenderedSharedProjectionIdentity(
            projection_algorithm=shared.projection_algorithm,
            evidence_sha256=shared.evidence_sha256,
            source_html_sha256=shared.source_html_sha256,
            internal_software_value=shared.internal_software_value,
            software_panel_id=shared.software_panel_id,
            category_panel_ids=shared.category_panel_ids,
            region_value=projected.region_value,
            projected_html_sha256=projected.projected_html_sha256,
            wire_html_sha256=projected.wire_html_sha256,
            config_path=shared.soft_category_path,
            config_sha256=shared.soft_category_sha256,
            config_entry_index=projected.config_entry_index,
            config_rule_table_ids=projected.config_rule_table_ids,
            removed_table_ids=projected.removed_table_ids,
            retained_table_ids=projected.retained_table_ids,
        )
        return identity, projected.projected_html

    @staticmethod
    def _rendered_participant_dicts(
        strict_projection: Any,
        prefix_identity: RenderedPrefixIdentity | None,
        shared_identity: RenderedSharedProjectionIdentity | None,
    ) -> list[dict[str, Any]]:
        participants: list[dict[str, Any]] = []
        if prefix_identity is not None:
            participants.append(prefix_identity.to_participant_dict())
        participants.append({
            "role": "strict_soft_category_projection",
            "projection_algorithm": (
                strict_projection.projection_algorithm
            ),
            "evidence_sha256": strict_projection.evidence_sha256,
            "input_html_sha256": (
                strict_projection.input_html_sha256
            ),
            "output_html_sha256": (
                strict_projection.output_html_sha256
            ),
            "html_sha256": strict_projection.output_html_sha256,
        })
        if shared_identity is not None:
            participants.append(
                shared_identity.to_participant_dict()
            )
        return participants

    @staticmethod
    def _selector_context(
        source: ReachabilitySourceEvidence,
        *,
        active_filter_keys: set[str],
    ) -> tuple[SelectorContext, ...]:
        values: list[SelectorContext] = []
        if source.region_value is not None:
            values.append(SelectorContext(
                "region",
                source.region_value,
                SourceStateEvidenceResolver._fragment_id(
                    source.region_href
                )
                or source.region_value,
                "region" in active_filter_keys,
            ))
        if source.software_value is not None:
            values.append(SelectorContext(
                "software",
                source.software_value,
                source.software_panel_id
                or SourceStateEvidenceResolver._fragment_id(
                    source.software_href
                )
                or source.software_value,
                "software" in active_filter_keys,
            ))
        if source.category_value is not None:
            values.append(SelectorContext(
                "category",
                source.category_value,
                source.category_panel_id
                or SourceStateEvidenceResolver._fragment_id(
                    source.category_href
                )
                or source.category_value,
                "category" in active_filter_keys,
            ))
        return tuple(values)

    @staticmethod
    def _fragment_id(value: str | None) -> str:
        if not isinstance(value, str) or not value.startswith("#"):
            return ""
        fragment = value[1:].strip()
        return fragment if fragment and "#" not in fragment else ""

    def _relative_path(self, path: Path) -> str:
        resolved = path.resolve()
        try:
            return resolved.relative_to(self.root).as_posix()
        except ValueError as error:
            raise SourceStateEvidenceError(
                "Canonical source-state evidence path escapes repository root"
            ) from error

    def _resolved_identity_path(self, value: str) -> Path:
        path = Path(value)
        return (
            path.resolve()
            if path.is_absolute()
            else (self.root / path).resolve()
        )


def source_finding_warning(
    evidence: SourceConfirmedEmptyState,
) -> dict[str, str]:
    """Project a structured finding into the sidecar's legacy issue shape."""

    state = ", ".join(
        f"{item.filter_key}={item.match_value}"
        for item in evidence.state_tuple
    )
    return {
        "code": "source_confirmed_empty_state",
        "path": "$.contentGroups",
        "message": (
            "Frozen strict source projection confirms an intentionally "
            f"non-price-bearing CMS state: {state}."
        ),
    }


def evidence_dicts(
    values: Sequence[SourceConfirmedEmptyState],
) -> list[dict[str, Any]]:
    """Return a JSON-safe deterministic copy for validators and reports."""

    return [value.to_dict() for value in values]


__all__ = [
    "PRICE_BEARING_PREDICATE",
    "RENDERED_COMPOSITION_ALGORITHM",
    "RenderedPrefixIdentity",
    "RenderedSharedProjectionIdentity",
    "SOFT_CATEGORY_RELATIVE_PATH",
    "SelectorContext",
    "SourceConfirmedEmptyState",
    "SourceStateEvidenceError",
    "SourceStateEvidenceResolver",
    "StateCriterion",
    "evidence_dicts",
    "source_finding_warning",
]
