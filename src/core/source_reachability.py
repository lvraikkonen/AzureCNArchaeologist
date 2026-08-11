"""Source-proven CMS reachability for Flexible Content pages."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

from bs4 import BeautifulSoup, Tag

from src.core.canonical_input import CanonicalHtmlInput
from src.core.cms_state_contract import CmsState
from src.core.region_projected_shared_content import (
    RegionProjectedSharedContentError,
    RegionProjectedSharedContentEvidence,
    RegionProjectedSharedContentResolver,
)
from src.core.scoped_source_content import (
    ScopedSourceContentError,
    SoftwareScopedPrefixEvidence,
    SoftwareScopedPrefixFragment,
    extract_category_ancestor_fragment,
)
from src.core.strict_soft_category_projection import (
    StrictSoftCategoryProjectionError,
    StrictSoftCategoryProjectionEvidence,
    StrictSoftCategoryProjector,
)

if TYPE_CHECKING:
    from src.core.cms_state_contract import ExpectedCmsReachability


GROUP_NAME_DELIMITER = " - "
AGGREGATE_LABELS = frozenset({"all", "全部"})
_PANEL_ID = re.compile(r"^tabContent\d+$")


class SourceReachabilityError(ValueError):
    """A stable, machine-classifiable source reachability failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.evidence = dict(evidence or {})


@dataclass(frozen=True)
class ReachabilityOption:
    value: str
    label: str
    href: str
    is_default: bool
    parent_value: str | None = None
    parent_panel_id: str | None = None

    def to_cms_dict(self) -> dict[str, str]:
        return {"value": self.value, "label": self.label, "href": self.href}

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.to_cms_dict(),
            "is_default": self.is_default,
            "parent_value": self.parent_value,
            "parent_panel_id": self.parent_panel_id,
        }


@dataclass(frozen=True)
class ReachabilityFilterDefinition:
    filter_key: str
    filter_type: str
    display_name: str
    options: tuple[ReachabilityOption, ...]

    def to_cms_dict(self) -> dict[str, Any]:
        return {
            "filterKey": self.filter_key,
            "filterType": self.filter_type,
            "displayName": self.display_name,
            "options": [option.to_cms_dict() for option in self.options],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "filterKey": self.filter_key,
            "filterType": self.filter_type,
            "displayName": self.display_name,
            "options": [option.to_dict() for option in self.options],
        }


@dataclass(frozen=True)
class SuppressedReachabilityOption:
    value: str
    label: str
    href: str
    parent_value: str | None
    parent_panel_id: str | None
    reason: str
    was_default: bool
    replacement_default_value: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "label": self.label,
            "href": self.href,
            "parent_value": self.parent_value,
            "parent_panel_id": self.parent_panel_id,
            "reason": self.reason,
            "was_default": self.was_default,
            "replacement_default_value": self.replacement_default_value,
        }


@dataclass(frozen=True)
class ReachabilitySourceEvidence:
    region_value: str | None
    region_href: str | None
    software_value: str | None
    software_href: str | None
    software_panel_id: str | None
    software_visible: bool
    category_value: str | None
    category_href: str | None
    category_panel_id: str | None
    software_scoped_prefix: SoftwareScopedPrefixEvidence | None = None
    region_projected_shared_content: (
        RegionProjectedSharedContentEvidence | None
    ) = None
    strict_soft_category_projection: (
        StrictSoftCategoryProjectionEvidence | None
    ) = None

    def __post_init__(self) -> None:
        if (
            self.software_scoped_prefix is not None
            and self.region_projected_shared_content is not None
        ):
            raise ValueError(
                "A reachable state cannot use both Software-scoped Prefix "
                "Content and Region-Projected Shared Content"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_value": self.region_value,
            "region_href": self.region_href,
            "software_value": self.software_value,
            "software_href": self.software_href,
            "software_panel_id": self.software_panel_id,
            "software_visible": self.software_visible,
            "category_value": self.category_value,
            "category_href": self.category_href,
            "category_panel_id": self.category_panel_id,
            "software_scoped_prefix": (
                self.software_scoped_prefix.to_dict()
                if self.software_scoped_prefix is not None
                else None
            ),
            "region_projected_shared_content": (
                self.region_projected_shared_content.to_dict()
                if self.region_projected_shared_content is not None
                else None
            ),
            "strict_soft_category_projection": (
                self.strict_soft_category_projection.to_dict()
                if self.strict_soft_category_projection is not None
                else None
            ),
        }


@dataclass(frozen=True)
class SourceReachabilityFinding:
    code: str
    message: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class ReachableCmsState:
    cms_state: CmsState
    state_label_segments: tuple[str, ...]
    mapping_key: str
    source_evidence: ReachabilitySourceEvidence
    is_default: bool

    @property
    def group_name(self) -> str:
        return " - ".join(self.state_label_segments)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cms_state": self.cms_state.to_dict(),
            "state_label_segments": list(self.state_label_segments),
            "group_name": self.group_name,
            "mapping_key": self.mapping_key,
            "source_evidence": self.source_evidence.to_dict(),
            "is_default": self.is_default,
        }


@dataclass(frozen=True)
class SourceReachability:
    product_key: str
    language: str
    source_path: str
    normalized_path: str
    source_sha256: str
    normalized_sha256: str
    filter_definitions_union: tuple[ReachabilityFilterDefinition, ...]
    ordered_states: tuple[ReachableCmsState, ...]
    default_state: CmsState
    suppressed_options: tuple[SuppressedReachabilityOption, ...]
    unreachable_panel_ids: tuple[str, ...]
    findings: tuple[SourceReachabilityFinding, ...]

    @property
    def state_relation(self) -> tuple[CmsState, ...]:
        return tuple(state.cms_state for state in self.ordered_states)

    @property
    def region_projected_shared_states(self) -> tuple[CmsState, ...]:
        """Return rendered states made price-bearing by proven shared content."""

        return tuple(
            state.cms_state
            for state in self.ordered_states
            if (
                state.source_evidence
                .region_projected_shared_content
                is not None
            )
        )

    @property
    def region_projected_shared_content_summary(
        self,
    ) -> dict[str, Any] | None:
        """Return compact extraction-time evidence identities for the sidecar."""

        identities_by_digest: dict[str, dict[str, Any]] = {}
        evidence_by_digest: dict[
            str, RegionProjectedSharedContentEvidence
        ] = {}
        for state in self.ordered_states:
            evidence = (
                state.source_evidence.region_projected_shared_content
            )
            if evidence is None:
                continue
            identity = evidence.identity_dict()
            digest = evidence.evidence_sha256
            prior = identities_by_digest.setdefault(digest, identity)
            if prior != identity:
                raise SourceReachabilityError(
                    "region_projected_shared_content_digest_collision",
                    "Distinct shared-content evidence has the same SHA-256",
                )
            evidence_by_digest.setdefault(digest, evidence)
        if not identities_by_digest:
            return None

        ordered_digests = tuple(sorted(identities_by_digest))
        canonical_identities = [
            identities_by_digest[digest] for digest in ordered_digests
        ]
        aggregate_bytes = json.dumps(
            canonical_identities,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        applicability_configs = sorted({
            (
                evidence.soft_category_path,
                evidence.soft_category_sha256,
            )
            for evidence in evidence_by_digest.values()
        })
        return {
            "schema_version": "1.0",
            "projection_algorithms": sorted({
                evidence.projection_algorithm
                for evidence in evidence_by_digest.values()
            }),
            "applicability_configs": [
                {"path": path, "sha256": sha256}
                for path, sha256 in applicability_configs
            ],
            "evidence_sha256s": list(ordered_digests),
            "aggregate_sha256": hashlib.sha256(
                aggregate_bytes
            ).hexdigest(),
        }

    @property
    def strict_soft_category_projection_summary(
        self,
    ) -> dict[str, Any] | None:
        """Return ordered state-projection identities for sidecar replay."""

        values = tuple(
            state.source_evidence.strict_soft_category_projection
            for state in self.ordered_states
            if (
                state.source_evidence.strict_soft_category_projection
                is not None
            )
        )
        if not values:
            return None
        identities = [value.identity_dict() for value in values]
        aggregate_bytes = json.dumps(
            identities,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        configs = tuple(dict.fromkeys(
            (value.config_path, value.config_sha256)
            for value in values
        ))
        return {
            "schema_version": "1.0",
            "projection_algorithms": sorted({
                value.projection_algorithm for value in values
            }),
            "applicability_configs": [
                {"path": path, "sha256": sha256}
                for path, sha256 in configs
            ],
            "state_count": len(values),
            "evidence_sha256s": [
                value.evidence_sha256 for value in values
            ],
            "aggregate_sha256": hashlib.sha256(
                aggregate_bytes
            ).hexdigest(),
        }

    def to_expected_reachability(self) -> ExpectedCmsReachability:
        """Convert source evidence to the contract's formal expectation."""

        from src.core.cms_state_contract import (
            ExpectedCmsReachability,
            ExpectedFilter,
            ExpectedRegionProjectedSharedContent,
            ExpectedSoftwareScopedPrefix,
        )

        expected_filters = []
        expected_fields = ExpectedFilter.__dataclass_fields__
        for definition in self.filter_definitions_union:
            by_value: dict[str, tuple[str, str]] = {}
            for option in definition.options:
                presentation = (option.label, option.href)
                previous = by_value.setdefault(option.value, presentation)
                if previous != presentation:
                    raise SourceReachabilityError(
                        "ambiguous_flat_filter_union",
                        (
                            f"{definition.filter_key} value {option.value!r} "
                            "has conflicting localized label or href"
                        ),
                    )
            arguments: dict[str, Any] = {
                "key": definition.filter_key,
                "filter_type": definition.filter_type,
                "option_values": tuple(
                    option.value for option in definition.options
                ),
                "option_hrefs": tuple(
                    option.href for option in definition.options
                ),
            }
            if "display_name" in expected_fields:
                arguments["display_name"] = definition.display_name
            if "option_labels" in expected_fields:
                arguments["option_labels"] = tuple(
                    option.label for option in definition.options
                )
            expected_filters.append(ExpectedFilter(**arguments))
        expected_prefixes = []
        expected_shared_content = []
        for state in self.ordered_states:
            source_evidence = state.source_evidence
            prefix = source_evidence.software_scoped_prefix
            expected_prefixes.append(
                ExpectedSoftwareScopedPrefix(
                    software_value=prefix.software_value,
                    software_panel_id=prefix.software_panel_id,
                    category_panel_ids=prefix.category_panel_ids,
                    fragment_count=prefix.fragment_count,
                    source_html=prefix.source_html,
                    source_html_sha256=prefix.source_html_sha256,
                )
                if prefix is not None
                else None
            )
            shared = source_evidence.region_projected_shared_content
            if shared is None:
                expected_shared_content.append(None)
            else:
                if source_evidence.region_value is None:
                    raise SourceReachabilityError(
                        "missing_region_projected_shared_content_scope",
                        "Region-Projected Shared Content requires a Region state",
                    )
                projection = shared.projection_for(
                    source_evidence.region_value
                )
                expected_shared_content.append(
                    ExpectedRegionProjectedSharedContent(
                        projection_algorithm=(
                            shared.projection_algorithm
                        ),
                        internal_software_value=(
                            shared.internal_software_value
                        ),
                        software_panel_id=shared.software_panel_id,
                        category_panel_ids=shared.category_panel_ids,
                        region_value=projection.region_value,
                        source_html_sha256=shared.source_html_sha256,
                        source_table_ids=shared.source_table_ids,
                        soft_category_path=shared.soft_category_path,
                        soft_category_sha256=(
                            shared.soft_category_sha256
                        ),
                        config_entry_index=(
                            projection.config_entry_index
                        ),
                        config_rule_table_ids=(
                            projection.config_rule_table_ids
                        ),
                        removed_table_ids=(
                            projection.removed_table_ids
                        ),
                        retained_table_ids=(
                            projection.retained_table_ids
                        ),
                        projected_html=projection.projected_html,
                        projected_html_sha256=(
                            projection.projected_html_sha256
                        ),
                    )
                )
        return ExpectedCmsReachability(
            filters=tuple(expected_filters),
            ordered_states=self.state_relation,
            default_state=self.default_state,
            software_scoped_prefixes_by_state=tuple(expected_prefixes),
            region_projected_shared_content_by_state=tuple(
                expected_shared_content
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "product_key": self.product_key,
            "language": self.language,
            "source": {
                "path": self.source_path,
                "sha256": self.source_sha256,
            },
            "normalized_input": {
                "path": self.normalized_path,
                "sha256": self.normalized_sha256,
            },
            "filter_definitions_union": [
                definition.to_dict()
                for definition in self.filter_definitions_union
            ],
            "ordered_states": [
                state.to_dict() for state in self.ordered_states
            ],
            "default_state": self.default_state.to_dict(),
            "suppressed_options": [
                option.to_dict() for option in self.suppressed_options
            ],
            "unreachable_panel_ids": list(self.unreachable_panel_ids),
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class _ParsedControl:
    filter_key: str
    filter_type: str
    display_name: str
    visible: bool
    options: tuple[ReachabilityOption, ...]
    selected_item_label: str

    @property
    def default_option(self) -> ReachabilityOption:
        defaults = tuple(option for option in self.options if option.is_default)
        if len(defaults) != 1:
            raise SourceReachabilityError(
                "invalid_internal_default",
                f"{self.filter_key} does not have exactly one resolved default",
            )
        return defaults[0]

    def definition(self) -> ReachabilityFilterDefinition:
        return ReachabilityFilterDefinition(
            self.filter_key,
            self.filter_type,
            self.display_name,
            self.options,
        )


@dataclass(frozen=True)
class _SoftwareScope:
    option: ReachabilityOption | None
    panel: Tag
    visible: bool


@dataclass(frozen=True)
class _CategoryBranch:
    display_name: str | None
    options: tuple[ReachabilityOption, ...]
    suppressed: tuple[SuppressedReachabilityOption, ...]
    software_scoped_prefix: SoftwareScopedPrefixEvidence | None
    region_projected_shared_content: (
        RegionProjectedSharedContentEvidence | None
    )


class SourceReachabilityResolver:
    """Resolve the ordered CMS relation from canonical source controls."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = (
            Path(root).resolve()
            if root is not None
            else Path(__file__).resolve().parents[2]
        )
        self.region_projected_shared_content = (
            RegionProjectedSharedContentResolver(self.root)
        )
        self.strict_soft_category_projector = (
            StrictSoftCategoryProjector(self.root)
        )

    def resolve(self, canonical_input: CanonicalHtmlInput) -> SourceReachability:
        self._validate_canonical_input(canonical_input)
        soup = BeautifulSoup(canonical_input.text, "html.parser")
        roots = soup.select(
            "div.technical-azure-selector.pricing-detail-tab"
        )
        if not roots:
            if soup.select(
                ".region-container, .software-kind-container, "
                ".category-container"
            ):
                self._fail(
                    "missing_filter_root",
                    "Interactive controls exist outside the pricing selector",
                )
            return self._result(
                canonical_input,
                filter_definitions=(),
                ordered_states=(),
                default_state=CmsState(()),
                suppressed=(),
                unreachable=(),
                findings=(),
            )
        if len(roots) != 1:
            self._fail(
                "ambiguous_filter_root",
                f"Expected one pricing selector, found {len(roots)}",
            )
        root = roots[0]
        findings: list[SourceReachabilityFinding] = []
        region = self._parse_dropdown_control(
            root,
            filter_key="region",
            container_class="region-container",
            select_selector="select#region-box, select.region-box",
            fallback_display_name="Region",
            product_key=canonical_input.product_key,
            findings=findings,
        )
        software = self._parse_dropdown_control(
            root,
            filter_key="software",
            container_class="software-kind-container",
            select_selector="select#software-box, select.software-box",
            fallback_display_name="Software category",
            product_key=canonical_input.product_key,
            findings=findings,
        )

        panels = self._top_level_panels(root)
        scopes = self._software_scopes(
            root,
            panels,
            software,
            findings=findings,
        )
        reachable_panel_ids = {
            panel_id
            for scope in scopes
            if (panel_id := self._tag_id(scope.panel)) is not None
        }
        unreachable = tuple(
            panel_id
            for panel_id in panels
            if panel_id not in reachable_panel_ids
        )

        category_branches: list[
            tuple[_SoftwareScope, _CategoryBranch]
        ] = []
        suppressed: list[SuppressedReachabilityOption] = []
        category_display_names: list[str] = []
        for scope in scopes:
            branch = self._parse_category_branch(
                soup,
                scope.panel,
                region=region,
                software_option=scope.option,
                findings=findings,
            )
            category_branches.append((scope, branch))
            suppressed.extend(branch.suppressed)
            if branch.display_name is not None:
                category_display_names.append(branch.display_name)
        if len(set(category_display_names)) > 1:
            self._fail(
                "category_display_name_mismatch",
                "Software branches declare different category display names",
            )

        category_options = tuple(
            option
            for _, branch in category_branches
            for option in branch.options
        )
        self._require_unique(
            (option.value for option in category_options),
            "duplicate_scoped_category_value",
            "scoped category value",
        )

        definitions: list[ReachabilityFilterDefinition] = []
        if region is not None and region.visible:
            definitions.append(region.definition())
        if software is not None and software.visible:
            definitions.append(software.definition())
        if category_options:
            definitions.append(ReachabilityFilterDefinition(
                filter_key="category",
                filter_type="tab",
                display_name=category_display_names[0],
                options=category_options,
            ))

        if not definitions:
            return self._result(
                canonical_input,
                filter_definitions=(),
                ordered_states=(),
                default_state=CmsState(()),
                suppressed=tuple(suppressed),
                unreachable=unreachable,
                findings=tuple(findings),
            )

        region_options: tuple[ReachabilityOption | None, ...]
        if region is None:
            region_options = (None,)
        elif region.visible:
            region_options = region.options
        else:
            region_options = (region.default_option,)

        states: list[ReachableCmsState] = []
        for region_option in region_options:
            for scope, branch in category_branches:
                local_categories: tuple[
                    ReachabilityOption | None, ...
                ] = branch.options or (None,)
                for category_option in local_categories:
                    state = self._build_state(
                        region=region,
                        region_option=region_option,
                        software=software,
                        software_scope=scope,
                        category_option=category_option,
                        software_scoped_prefix=(
                            branch.software_scoped_prefix
                        ),
                        region_projected_shared_content=(
                            branch.region_projected_shared_content
                        ),
                        is_default=not states,
                    )
                    states.append(state)

        self._validate_relation(tuple(definitions), states)
        default_state = states[0].cms_state if states else CmsState(())
        return self._result(
            canonical_input,
            filter_definitions=tuple(definitions),
            ordered_states=tuple(states),
            default_state=default_state,
            suppressed=tuple(suppressed),
            unreachable=unreachable,
            findings=tuple(findings),
        )

    def attach_strict_soft_category_projections(
        self,
        canonical_input: CanonicalHtmlInput,
        source_reachability: SourceReachability,
    ) -> SourceReachability:
        """Freeze exact leaf-state projection after Complex is selected.

        Structural Source Reachability remains independent from applicability
        projection.  The coordinator invokes this phase only for the formal
        Complex strategy, so RegionFilter/Simple runs cannot accidentally gain
        soft-category semantics.
        """

        self._validate_canonical_input(canonical_input)
        if (
            source_reachability.product_key != canonical_input.product_key
            or source_reachability.language != canonical_input.language
            or source_reachability.source_sha256
            != canonical_input.source_sha256
            or source_reachability.normalized_sha256
            != canonical_input.normalized_sha256
        ):
            raise SourceReachabilityError(
                "strict_soft_category_source_identity_mismatch",
                "Strict projection input differs from SourceReachability",
            )

        resolved: list[ReachableCmsState] = []
        soup = BeautifulSoup(canonical_input.text, "html.parser")
        for state in source_reachability.ordered_states:
            source = state.source_evidence
            source_panel_id = (
                source.category_panel_id or source.software_panel_id
            )
            if (
                source_panel_id is None
                or source.region_value is None
                or source.software_value is None
            ):
                resolved.append(state)
                continue
            try:
                projection = self.strict_soft_category_projector.project(
                    soup,
                    source_panel_id=source_panel_id,
                    region_value=source.region_value,
                    software_value=source.software_value,
                )
            except StrictSoftCategoryProjectionError as error:
                raise SourceReachabilityError(
                    error.code,
                    str(error),
                    evidence=error.evidence,
                ) from error
            resolved.append(replace(
                state,
                source_evidence=replace(
                    source,
                    strict_soft_category_projection=projection,
                ),
            ))
        return replace(
            source_reachability,
            ordered_states=tuple(resolved),
        )

    def _build_state(
        self,
        *,
        region: _ParsedControl | None,
        region_option: ReachabilityOption | None,
        software: _ParsedControl | None,
        software_scope: _SoftwareScope,
        category_option: ReachabilityOption | None,
        software_scoped_prefix: SoftwareScopedPrefixEvidence | None,
        region_projected_shared_content: (
            RegionProjectedSharedContentEvidence | None
        ),
        is_default: bool,
    ) -> ReachableCmsState:
        criteria: list[tuple[str, str]] = []
        labels: list[str] = []
        if (
            region is not None
            and region.visible
            and region_option is not None
        ):
            criteria.append(("region", region_option.value))
            labels.append(region_option.label)
        software_option = software_scope.option
        if (
            software is not None
            and software.visible
            and software_option is not None
        ):
            criteria.append(("software", software_option.value))
            labels.append(software_option.label)
        if category_option is not None:
            criteria.append(("category", category_option.value))
            labels.append(category_option.label)
        for label in labels:
            if GROUP_NAME_DELIMITER in label:
                self._fail(
                    "ambiguous_group_label_segment",
                    (
                        f"Active CMS label {label!r} contains the reserved "
                        f"delimiter {GROUP_NAME_DELIMITER!r}"
                    ),
                )

        region_value = (
            region_option.value if region_option is not None else None
        )
        if region_projected_shared_content is not None:
            if region_value is None or category_option is None:
                self._fail(
                    "invalid_region_projected_shared_content_scope",
                    (
                        "Region-Projected Shared Content requires exact Region "
                        "and Category state identities"
                    ),
                )
            if (
                category_option.value
                not in region_projected_shared_content.category_panel_ids
            ):
                self._fail(
                    "invalid_region_projected_shared_content_scope",
                    (
                        f"Category {category_option.value!r} is outside the "
                        "shared-content descendant scope"
                    ),
                )
            region_projected_shared_content.projection_for(region_value)
        mapping_values = [region_value or "default"]
        if software_option is not None:
            mapping_values.append(software_option.value)
        if category_option is not None:
            mapping_values.append(category_option.value)
        software_panel_id = self._tag_id(software_scope.panel)
        return ReachableCmsState(
            cms_state=CmsState(tuple(criteria)),
            state_label_segments=tuple(labels),
            mapping_key="_".join(mapping_values),
            source_evidence=ReachabilitySourceEvidence(
                region_value=region_value,
                region_href=(
                    region_option.href
                    if region_option is not None
                    else None
                ),
                software_value=(
                    software_option.value
                    if software_option is not None
                    else None
                ),
                software_href=(
                    software_option.href
                    if software_option is not None
                    else None
                ),
                software_panel_id=software_panel_id,
                software_visible=bool(
                    software is not None and software.visible
                ),
                category_value=(
                    category_option.value
                    if category_option is not None
                    else None
                ),
                category_href=(
                    category_option.href
                    if category_option is not None
                    else None
                ),
                category_panel_id=(
                    category_option.value
                    if category_option is not None
                    else None
                ),
                software_scoped_prefix=software_scoped_prefix,
                region_projected_shared_content=(
                    region_projected_shared_content
                ),
            ),
            is_default=is_default,
        )

    def _software_scopes(
        self,
        root: Tag,
        panels: dict[str, Tag],
        software: _ParsedControl | None,
        *,
        findings: list[SourceReachabilityFinding],
    ) -> tuple[_SoftwareScope, ...]:
        if software is not None:
            options = (
                software.options
                if software.visible
                else (software.default_option,)
            )
            scopes: list[_SoftwareScope] = []
            for option in options:
                panel_id = option.href.removeprefix("#")
                panel = panels.get(panel_id)
                if (
                    panel is None
                    and not software.visible
                    and len(software.options) == 1
                ):
                    implicit_panels = [
                        child
                        for child in root.find_all("div", recursive=False)
                        if (
                            "tab-control-container"
                            in (child.get("class") or ())
                            and self._tag_id(child) is None
                            and (
                                self._text(child)
                                or child.find(
                                    [
                                        "img",
                                        "video",
                                        "audio",
                                        "table",
                                        "iframe",
                                    ]
                                )
                                is not None
                            )
                        )
                    ]
                    if len(implicit_panels) == 1:
                        panel = implicit_panels[0]
                        findings.append(SourceReachabilityFinding(
                            code="implicit_hidden_software_scope",
                            message=(
                                "A hidden singleton software control targets "
                                "a missing id, but the selector owns exactly "
                                "one id-less static content container."
                            ),
                            evidence={
                                "software_value": option.value,
                                "declared_href": option.href,
                                "implicit_classes": list(
                                    panel.get("class") or ()
                                ),
                            },
                        ))
                if panel is None:
                    self._fail(
                        "missing_software_target",
                        (
                            f"Reachable software {option.value!r} targets "
                            f"missing top-level panel {option.href}"
                        ),
                    )
                scopes.append(_SoftwareScope(
                    option=option,
                    panel=panel,
                    visible=software.visible,
                ))
            return tuple(scopes)

        category_panels = tuple(
            panel
            for panel in panels.values()
            if panel.select(
                "ul.os-tab-nav.category-tabs.hidden-xs.hidden-sm, "
                "select.category-tabs"
            )
        )
        if len(category_panels) > 1:
            self._fail(
                "ambiguous_unscoped_category",
                "Multiple category panels have no software control scope",
            )
        if category_panels:
            return (_SoftwareScope(None, category_panels[0], False),)
        return (_SoftwareScope(None, root, False),)

    def _top_level_panels(self, root: Tag) -> dict[str, Tag]:
        """Index direct software targets without crossing nested tab scopes."""

        panels: list[tuple[str, Tag]] = []
        # Frozen sources place software targets in one of three equivalent
        # direct scopes: directly under the pricing selector, under its direct
        # tab-content wrapper, or under a direct nested static tab selector.
        # Never search deeper than this: category panels reuse tabContentN
        # prefixes and some pages even duplicate the outer id in a descendant.
        for child in root.find_all("div", recursive=False):
            child_id = self._tag_id(child)
            if child_id is not None and _PANEL_ID.fullmatch(child_id):
                panels.append((child_id, child))

            classes = set(child.get("class") or ())
            owns_direct_software_panels = (
                "tab-content" in classes
                or {
                    "technical-azure-selector",
                    "tab-control-selector",
                }.issubset(classes)
            )
            if not owns_direct_software_panels:
                continue
            for panel in child.find_all("div", recursive=False):
                panel_id = self._tag_id(panel)
                if (
                    panel_id is not None
                    and _PANEL_ID.fullmatch(panel_id)
                ):
                    panels.append((panel_id, panel))
        self._require_unique(
            (panel_id for panel_id, _ in panels),
            "duplicate_software_panel",
            "top-level software panel id",
        )
        return dict(panels)

    def _validate_relation(
        self,
        definitions: tuple[ReachabilityFilterDefinition, ...],
        states: list[ReachableCmsState],
    ) -> None:
        if not states:
            self._fail(
                "empty_reachability_relation",
                "Active filter definitions require at least one state",
            )
        identities = [state.cms_state for state in states]
        if len(identities) != len(set(identities)):
            self._fail(
                "duplicate_reachable_state",
                "Source controls produced duplicate CMS states",
            )
        group_names = [state.group_name for state in states]
        if len(group_names) != len(set(group_names)):
            self._fail(
                "duplicate_group_name",
                "Source controls produced duplicate groupName paths",
            )
        if sum(state.is_default for state in states) != 1:
            self._fail(
                "invalid_default_state_count",
                "Reachability relation must have exactly one default state",
            )

        used: dict[str, set[str]] = {}
        for state in states:
            for key, value in state.cms_state.criteria:
                used.setdefault(key, set()).add(value)
        for definition in definitions:
            unused = [
                option.value
                for option in definition.options
                if option.value not in used.get(definition.filter_key, set())
            ]
            if unused:
                self._fail(
                    "unused_filter_union_option",
                    (
                        f"{definition.filter_key} union contains options "
                        f"unused by ordered states: {unused}"
                    ),
                )

    def _validate_canonical_input(
        self, canonical_input: CanonicalHtmlInput
    ) -> None:
        digest = hashlib.sha256(canonical_input.raw_bytes).hexdigest()
        if digest != canonical_input.normalized_sha256:
            self._fail(
                "canonical_input_hash_mismatch",
                "Canonical input bytes do not match normalized_sha256",
            )
        try:
            encoded = canonical_input.text.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise SourceReachabilityError(
                "canonical_input_not_utf8",
                "Canonical input text is not strict UTF-8",
            ) from error
        if encoded != canonical_input.raw_bytes:
            self._fail(
                "canonical_input_text_mismatch",
                "Canonical input text does not reproduce the canonical bytes",
            )

    @staticmethod
    def _result(
        canonical_input: CanonicalHtmlInput,
        *,
        filter_definitions: tuple[ReachabilityFilterDefinition, ...],
        ordered_states: tuple[ReachableCmsState, ...],
        default_state: CmsState,
        suppressed: tuple[SuppressedReachabilityOption, ...],
        unreachable: tuple[str, ...],
        findings: tuple[SourceReachabilityFinding, ...],
    ) -> SourceReachability:
        return SourceReachability(
            product_key=canonical_input.product_key,
            language=canonical_input.language,
            source_path=str(canonical_input.source_path),
            normalized_path=str(canonical_input.normalized_path),
            source_sha256=canonical_input.source_sha256,
            normalized_sha256=canonical_input.normalized_sha256,
            filter_definitions_union=filter_definitions,
            ordered_states=ordered_states,
            default_state=default_state,
            suppressed_options=suppressed,
            unreachable_panel_ids=unreachable,
            findings=findings,
        )

    def _parse_dropdown_control(
        self,
        root: Tag,
        *,
        filter_key: str,
        container_class: str,
        select_selector: str,
        fallback_display_name: str,
        product_key: str,
        findings: list[SourceReachabilityFinding],
    ) -> _ParsedControl | None:
        containers = root.select(
            f"div.dropdown-container.{container_class}"
        )
        if not containers:
            return None
        if len(containers) != 1:
            self._fail(
                "ambiguous_filter_container",
                f"Expected one {filter_key} container, found {len(containers)}",
            )
        container = containers[0]
        selects = container.select(select_selector)
        if len(selects) != 1:
            self._fail(
                "ambiguous_mobile_filter",
                f"Expected one mobile {filter_key} control, found {len(selects)}",
            )

        control_visible = not self._effectively_hidden(container, root)
        mobile_rows: list[tuple[str, str, str, bool, int]] = []
        for index, option in enumerate(selects[0].find_all(
            "option", recursive=False
        )):
            href = self._fragment_href(option.get("data-href"), filter_key)
            raw_value = self._normalized_attribute(option.get("value"))
            label = self._text(option)
            if not raw_value:
                self._fail(
                    "invalid_filter_option",
                    f"{filter_key} mobile options require a machine value",
                )
            value = (
                href.removeprefix("#")
                if filter_key == "region"
                else raw_value
            )
            if (
                filter_key == "software"
                and not control_visible
                and len(selects[0].find_all("option", recursive=False)) == 1
                and raw_value.casefold() != product_key.casefold()
                and label.casefold() == product_key.casefold()
            ):
                value = product_key
                findings.append(SourceReachabilityFinding(
                    code="hidden_software_machine_value_product_drift",
                    message=(
                        "A hidden singleton software machine value differs "
                        "from the matching Product Definition identity; the "
                        "product identity is authoritative for internal "
                        "applicability lookup."
                    ),
                    evidence={
                        "source_value": raw_value,
                        "canonical_value": product_key,
                        "label": label,
                        "href": href,
                    },
                ))
            if filter_key == "region" and raw_value != value:
                findings.append(SourceReachabilityFinding(
                    code="filter_machine_value_target_drift",
                    message=(
                        "region mobile machine value disagrees with its "
                        "interaction target; the target fragment is "
                        "authoritative."
                    ),
                    evidence={
                        "filter_key": filter_key,
                        "href": href,
                        "source_value": raw_value,
                        "canonical_value": value,
                    },
                ))
            mobile_rows.append(
                (href, value, label, option.has_attr("selected"), index)
            )
        if not mobile_rows:
            self._fail(
                "empty_filter_domain",
                f"{filter_key} mobile control has no options",
            )
        self._require_unique(
            (row[0] for row in mobile_rows),
            "duplicate_filter_target",
            f"{filter_key} mobile href",
        )
        self._require_unique(
            (row[1] for row in mobile_rows),
            "duplicate_filter_value",
            f"{filter_key} mobile value",
        )
        mobile_by_href = {row[0]: row for row in mobile_rows}

        desktop_links = container.select(
            ".dropdown-box.os-tab-nav .tab-items a"
        )
        if not desktop_links:
            self._fail(
                "missing_desktop_filter",
                f"{filter_key} has no desktop interaction options",
            )
        desktop_rows: list[tuple[str, str, bool, int]] = []
        for index, link in enumerate(desktop_links):
            href = self._fragment_href(link.get("data-href"), filter_key)
            label = self._text(link)
            if not label:
                self._fail(
                    "invalid_filter_option",
                    f"{filter_key} desktop options require labels",
                )
            parent = link.find_parent("li")
            is_default = bool(
                parent is not None
                and {
                    "active",
                    "selected",
                    "selected-item",
                }.intersection(parent.get("class", []))
            )
            desktop_rows.append((href, label, is_default, index))

        desktop_rows = self._reconcile_desktop_rows(
            filter_key,
            desktop_rows,
            mobile_rows,
            findings,
        )
        desktop_hrefs = [row[0] for row in desktop_rows]
        desktop_labels = {row[0]: row[1] for row in desktop_rows}
        desktop_defaults = [row[0] for row in desktop_rows if row[2]]

        self._require_unique(
            desktop_hrefs,
            "duplicate_filter_target",
            f"{filter_key} desktop href",
        )
        self._require_unique(
            desktop_labels.values(),
            "duplicate_filter_label",
            f"{filter_key} desktop label",
        )
        if set(desktop_hrefs) != set(mobile_by_href):
            self._fail(
                "responsive_filter_domain_mismatch",
                f"{filter_key} desktop/mobile targets differ",
            )
        for href in desktop_hrefs:
            if desktop_labels[href] != mobile_by_href[href][2]:
                findings.append(SourceReachabilityFinding(
                    code="responsive_filter_label_drift",
                    message=(
                        f"{filter_key} mobile label differs from the "
                        "authoritative desktop display label."
                    ),
                    evidence={
                        "filter_key": filter_key,
                        "href": href,
                        "value": mobile_by_href[href][1],
                        "desktop_label": desktop_labels[href],
                        "mobile_label": mobile_by_href[href][2],
                    },
                ))

        selected_item = container.select_one(".selected-item")
        selected_item_label = (
            self._text(selected_item) if selected_item is not None else ""
        )
        summary_matches = [
            href
            for href, label in desktop_labels.items()
            if selected_item_label and label == selected_item_label
        ]
        mobile_defaults = [row[0] for row in mobile_rows if row[3]]
        unique_mobile_defaults = list(dict.fromkeys(mobile_defaults))
        unique_desktop_defaults = list(dict.fromkeys(desktop_defaults))
        if len(unique_desktop_defaults) > 1:
            corroborated_default = (
                unique_mobile_defaults[0]
                if (
                    len(unique_mobile_defaults) == 1
                    and summary_matches == [unique_mobile_defaults[0]]
                    and unique_mobile_defaults[0]
                    in unique_desktop_defaults
                )
                else None
            )
            if corroborated_default is not None:
                stale_defaults = [
                    href
                    for href in unique_desktop_defaults
                    if href != corroborated_default
                ]
                findings.append(SourceReachabilityFinding(
                    code="stale_desktop_default_marker",
                    message=(
                        f"{filter_key} has extra desktop active markers; "
                        "the unique mobile selection and desktop summary "
                        "agree on the canonical default."
                    ),
                    evidence={
                        "filter_key": filter_key,
                        "canonical_default_href": corroborated_default,
                        "stale_default_hrefs": stale_defaults,
                    },
                ))
                desktop_defaults = [corroborated_default]
        desktop_default = self._declared_default(
            filter_key,
            desktop_defaults,
            desktop_hrefs,
            desktop_labels,
            selected_item_label,
        )
        desktop_is_unambiguous = (
            desktop_default is not None
            and (
                not selected_item_label
                or summary_matches == [desktop_default]
            )
        )
        if desktop_default is None:
            self._fail(
                "missing_filter_default",
                f"{filter_key} desktop control has no unambiguous default",
            )
        if len(unique_mobile_defaults) > 1:
            if not desktop_is_unambiguous:
                self._single_default(
                    filter_key, "mobile", mobile_defaults
                )
            # Mobile default markers are outside the maintained desktop
            # contract.  Domain and target checks above still apply, but stale
            # mobile defaults cannot override an unambiguous desktop default.
            mobile_default = None
        else:
            mobile_default = self._single_default(
                filter_key, "mobile", mobile_defaults
            )
            if (
                mobile_default is not None
                and mobile_default != desktop_default
            ):
                if not desktop_is_unambiguous:
                    self._reconcile_default(
                        filter_key,
                        desktop_default,
                        mobile_default,
                        desktop_hrefs,
                    )
                mobile_default = None
        default_href = self._reconcile_default(
            filter_key,
            desktop_default,
            mobile_default,
            desktop_hrefs,
        )

        if selected_item_label:
            if len(summary_matches) == 1 and summary_matches[0] != default_href:
                findings.append(SourceReachabilityFinding(
                    code="display_summary_default_drift",
                    message=(
                        f"{filter_key} selected-item display disagrees with "
                        "the proven desktop/mobile default."
                    ),
                    evidence={
                        "filter_key": filter_key,
                        "selected_item_label": selected_item_label,
                        "selected_item_href": summary_matches[0],
                        "proven_default_href": default_href,
                    },
                ))

        ordered_hrefs = self._default_first(desktop_hrefs, default_href)
        options = tuple(
            ReachabilityOption(
                value=mobile_by_href[href][1],
                label=desktop_labels[href],
                href=href,
                is_default=href == default_href,
            )
            for href in ordered_hrefs
        )
        label = container.find("label")
        display_name = (
            self._text(label).rstrip(":：").strip()
            if label is not None
            else ""
        ) or fallback_display_name
        return _ParsedControl(
            filter_key=filter_key,
            filter_type="dropdown",
            display_name=display_name,
            visible=control_visible,
            options=options,
            selected_item_label=selected_item_label,
        )

    def _reconcile_desktop_rows(
        self,
        filter_key: str,
        desktop_rows: list[tuple[str, str, bool, int]],
        mobile_rows: list[tuple[str, str, str, bool, int]],
        findings: list[SourceReachabilityFinding],
    ) -> list[tuple[str, str, bool, int]]:
        """Repair only source-proven responsive markup drift.

        The mobile control owns the unique interaction-target domain. Desktop
        labels and ordering remain authoritative. A target can be repaired by
        position only when equal-length controls otherwise align and the raw
        desktop target is duplicated while the mobile target is absent. An
        extra duplicate desktop row can be suppressed only when exactly one
        row in that duplicate group has the mobile label and no dropped row is
        marked as a default.
        """

        reconciled = list(desktop_rows)
        raw_hrefs = [row[0] for row in reconciled]
        if len(reconciled) == len(mobile_rows):
            mismatch_indexes = [
                index
                for index, (desktop, mobile) in enumerate(
                    zip(reconciled, mobile_rows, strict=True)
                )
                if desktop[0] != mobile[0]
            ]
            position_repair_is_proven = bool(mismatch_indexes) and all(
                raw_hrefs.count(reconciled[index][0]) > 1
                and mobile_rows[index][0] not in raw_hrefs
                for index in mismatch_indexes
            )
            if position_repair_is_proven:
                for index in mismatch_indexes:
                    source_href, label, is_default, source_index = (
                        reconciled[index]
                    )
                    canonical_href = mobile_rows[index][0]
                    reconciled[index] = (
                        canonical_href,
                        label,
                        is_default,
                        source_index,
                    )
                    findings.append(SourceReachabilityFinding(
                        code="responsive_filter_target_position_drift",
                        message=(
                            f"{filter_key} desktop target is a duplicated "
                            "stale value; equal-length responsive controls "
                            "prove the mobile target at the same position."
                        ),
                        evidence={
                            "filter_key": filter_key,
                            "source_index": source_index,
                            "source_href": source_href,
                            "canonical_href": canonical_href,
                            "desktop_label": label,
                        },
                    ))

        href_groups: dict[str, list[tuple[str, str, bool, int]]] = {}
        for row in reconciled:
            href_groups.setdefault(row[0], []).append(row)
        mobile_by_href = {row[0]: row for row in mobile_rows}
        suppressed_indexes: set[int] = set()
        for href, rows in href_groups.items():
            if len(rows) < 2 or href not in mobile_by_href:
                continue
            mobile_label = mobile_by_href[href][2]
            label_matches = [
                row
                for row in rows
                if row[1] == mobile_label
            ]
            if len(label_matches) != 1:
                continue
            retained = label_matches[0]
            discarded = [row for row in rows if row[3] != retained[3]]
            if any(row[2] for row in discarded):
                continue
            for row in discarded:
                suppressed_indexes.add(row[3])
                findings.append(SourceReachabilityFinding(
                    code="suppressed_stale_desktop_filter_option",
                    message=(
                        f"{filter_key} has an extra desktop row reusing a "
                        "mobile target; the row whose label matches the "
                        "mobile option is the only reachable presentation."
                    ),
                    evidence={
                        "filter_key": filter_key,
                        "href": href,
                        "suppressed_label": row[1],
                        "retained_label": retained[1],
                        "source_index": row[3],
                    },
                ))
        return [
            row for row in reconciled if row[3] not in suppressed_indexes
        ]

    def _parse_category_branch(
        self,
        soup: BeautifulSoup,
        panel: Tag,
        *,
        region: _ParsedControl | None,
        software_option: ReachabilityOption | None,
        findings: list[SourceReachabilityFinding],
    ) -> _CategoryBranch:
        navs = panel.select(
            "ul.os-tab-nav.category-tabs.hidden-xs.hidden-sm"
        )
        selects = panel.select("select.category-tabs")
        if not navs and not selects:
            return _CategoryBranch(None, (), (), None, None)
        if len(navs) != 1 or len(selects) != 1:
            self._fail(
                "ambiguous_category_control",
                (
                    f"Category control in {panel.get('id', '<root>')} must "
                    "have one desktop nav and one mobile select"
                ),
            )

        mobile_rows: list[tuple[str, str, bool]] = []
        for option in selects[0].find_all("option", recursive=False):
            href = self._fragment_href(option.get("data-href"), "category")
            label = self._text(option)
            mobile_rows.append((href, label, option.has_attr("selected")))
        if not mobile_rows:
            self._fail(
                "empty_category_domain",
                f"Category control in {panel.get('id', '<root>')} is empty",
            )
        self._require_unique(
            (row[0] for row in mobile_rows),
            "duplicate_category_target",
            "category mobile href",
        )
        mobile_by_href = {row[0]: row for row in mobile_rows}

        desktop_links = navs[0].find_all("a")
        if not desktop_links:
            self._fail(
                "empty_category_domain",
                "Category desktop control has no options",
            )
        desktop_hrefs: list[str] = []
        desktop_labels: dict[str, str] = {}
        desktop_defaults: list[str] = []
        for link in desktop_links:
            href = self._fragment_href(link.get("data-href"), "category")
            label = self._text(link)
            if not label:
                self._fail(
                    "invalid_category_option",
                    "Category desktop option requires a label",
                )
            desktop_hrefs.append(href)
            desktop_labels[href] = label
            parent = link.find_parent("li")
            if parent is not None and {
                "active",
                "selected",
                "selected-item",
            }.intersection(parent.get("class", [])):
                desktop_defaults.append(href)
        self._require_unique(
            desktop_hrefs,
            "duplicate_category_target",
            "category desktop href",
        )
        self._require_unique(
            desktop_labels.values(),
            "duplicate_category_label",
            "category desktop label",
        )
        if set(desktop_hrefs) != set(mobile_by_href):
            self._fail(
                "responsive_category_domain_mismatch",
                (
                    f"Category desktop/mobile targets differ in "
                    f"{panel.get('id', '<root>')}"
                ),
            )
        for href in desktop_hrefs:
            if desktop_labels[href] != mobile_by_href[href][1]:
                findings.append(SourceReachabilityFinding(
                    code="responsive_filter_label_drift",
                    message=(
                        "category mobile label differs from the authoritative "
                        "desktop display label."
                    ),
                    evidence={
                        "filter_key": "category",
                        "href": href,
                        "value": href.removeprefix("#"),
                        "desktop_label": desktop_labels[href],
                        "mobile_label": mobile_by_href[href][1],
                        "parent_panel_id": self._tag_id(panel),
                    },
                ))

        category_container = navs[0].find_parent(
            class_="category-container"
        )
        selected_item = (
            category_container.select_one(".selected-item")
            if isinstance(category_container, Tag)
            else None
        )
        selected_item_label = (
            self._text(selected_item) if selected_item is not None else ""
        )
        desktop_default = self._declared_default(
            "category",
            desktop_defaults,
            desktop_hrefs,
            desktop_labels,
            selected_item_label,
        )
        mobile_default = self._single_default(
            "category",
            "mobile",
            [row[0] for row in mobile_rows if row[2]],
        )
        raw_default = self._reconcile_default(
            "category",
            desktop_default,
            mobile_default,
            desktop_hrefs,
        )

        concrete_hrefs: list[str] = []
        layout_hrefs: list[str] = []
        suppressed_rows: list[tuple[str, bool, str]] = []
        for href in desktop_hrefs:
            target_id = href.removeprefix("#")
            global_matches = soup.find_all(id=target_id)
            local_matches = panel.find_all(id=target_id)
            if len(global_matches) > 1:
                self._fail(
                    "ambiguous_category_target",
                    f"Category target {href} is not unique",
                )
            if len(global_matches) == 1 and len(local_matches) != 1:
                self._fail(
                    "category_target_outside_parent",
                    f"Category target {href} is outside its software panel",
                )
            if not global_matches:
                if desktop_labels[href].casefold() in AGGREGATE_LABELS:
                    suppressed_rows.append((
                        href,
                        href == raw_default,
                        "missing_aggregate_target",
                    ))
                    continue
                self._fail(
                    "missing_category_target",
                    f"Category target {href} does not exist",
                )
            layout_hrefs.append(href)
            target = global_matches[0]
            if (
                not self._text(target)
                and target.find(
                    ["img", "video", "audio", "table", "iframe"]
                )
                is None
            ):
                suppressed_rows.append((
                    href,
                    href == raw_default,
                    "empty_category_target",
                ))
                continue
            concrete_hrefs.append(href)

        if not concrete_hrefs:
            self._fail(
                "empty_concrete_category_domain",
                (
                    f"Category branch {panel.get('id', '<root>')} has no "
                    "concrete target after aggregate suppression"
                ),
            )
        default_href = (
            concrete_hrefs[0]
            if raw_default not in concrete_hrefs
            else raw_default
        )
        ordered_hrefs = self._default_first(
            concrete_hrefs, default_href
        )
        parent_value = (
            software_option.value if software_option is not None else None
        )
        parent_panel_id = self._tag_id(panel)
        options = tuple(
            ReachabilityOption(
                value=href.removeprefix("#"),
                label=desktop_labels[href],
                href=href,
                is_default=href == default_href,
                parent_value=parent_value,
                parent_panel_id=parent_panel_id,
            )
            for href in ordered_hrefs
        )
        suppressed = tuple(
            SuppressedReachabilityOption(
                value=href.removeprefix("#"),
                label=desktop_labels[href],
                href=href,
                parent_value=parent_value,
                parent_panel_id=parent_panel_id,
                reason=reason,
                was_default=was_default,
                replacement_default_value=(
                    default_href.removeprefix("#")
                    if was_default
                    else None
                ),
            )
            for href, was_default, reason in suppressed_rows
        )

        if selected_item_label:
            matches = [
                href
                for href, label in desktop_labels.items()
                if label == selected_item_label
            ]
            if len(matches) == 1 and matches[0] != raw_default:
                findings.append(SourceReachabilityFinding(
                    code="display_summary_default_drift",
                    message=(
                        "category selected-item display disagrees with the "
                        "proven desktop/mobile default."
                    ),
                    evidence={
                        "filter_key": "category",
                        "parent_panel_id": parent_panel_id,
                        "selected_item_label": selected_item_label,
                        "selected_item_href": matches[0],
                        "proven_default_href": raw_default,
                    },
                ))

        title = panel.select_one(".category-container .category-title")
        display_name = (
            self._text(title).rstrip(":：").strip()
            if title is not None
            else ""
        ) or "Category"
        panel_id = self._tag_id(panel)
        if panel_id is None:
            self._fail(
                "missing_software_panel_identity",
                "A Category branch requires a software panel id",
            )
        try:
            category_panel_ids = tuple(
                href.removeprefix("#") for href in layout_hrefs
            )
            ancestor_fragment = extract_category_ancestor_fragment(
                soup,
                panel_id,
                expected_category_panel_ids=category_panel_ids,
            )
        except ScopedSourceContentError as error:
            self._fail(
                "invalid_software_scoped_prefix_layout",
                str(error),
            )
        software_scoped_prefix = None
        region_projected_shared_content = None
        if ancestor_fragment is not None:
            if software_option is None:
                self._fail(
                    "unclassified_ancestor_scoped_prefix",
                    (
                        f"Content before Category panels in {panel_id!r} "
                        "has no software scope"
                    ),
                )
            if ancestor_fragment.table_ids:
                if region is None or not region.visible:
                    self._fail(
                        "missing_region_projected_shared_content_scope",
                        (
                            "Price-bearing ancestor content requires an active "
                            f"Region filter in {panel_id!r}"
                        ),
                    )
                try:
                    region_projected_shared_content = (
                        self.region_projected_shared_content.resolve(
                            ancestor_fragment,
                            internal_software_value=(
                                software_option.value
                            ),
                            region_values=tuple(
                                option.value for option in region.options
                            ),
                        )
                    )
                except RegionProjectedSharedContentError as error:
                    evidence = dict(error.evidence)
                    if error.code.startswith(
                        ("soft_category_", "strict_soft_category_")
                    ):
                        evidence.setdefault(
                            "state_scope",
                            {
                                "region": evidence.get("region_value"),
                                "software": (
                                    evidence.get("software_value")
                                    or software_option.value
                                ),
                                "source_panel_id": (
                                    ancestor_fragment.software_panel_id
                                ),
                            },
                        )
                        evidence.setdefault(
                            "source_inventory",
                            {
                                "source_panel_id": (
                                    ancestor_fragment.software_panel_id
                                ),
                                "source_table_count": len(
                                    ancestor_fragment.table_ids
                                ),
                                "source_idless_table_count": 0,
                                "source_table_ids": list(
                                    ancestor_fragment.table_ids
                                ),
                                "input_html_sha256": (
                                    ancestor_fragment.source_html_sha256
                                ),
                            },
                        )
                    raise SourceReachabilityError(
                        error.code,
                        str(error),
                        evidence=evidence,
                    ) from error
            else:
                software_scoped_prefix = (
                    SoftwareScopedPrefixEvidence.from_fragment(
                        software_value=software_option.value,
                        category_panel_ids=category_panel_ids,
                        fragment=SoftwareScopedPrefixFragment(
                            software_panel_id=(
                                ancestor_fragment.software_panel_id
                            ),
                            fragment_count=(
                                ancestor_fragment.fragment_count
                            ),
                            source_html=ancestor_fragment.source_html,
                            source_html_sha256=(
                                ancestor_fragment.source_html_sha256
                            ),
                        ),
                    )
                )
        return _CategoryBranch(
            display_name,
            options,
            suppressed,
            software_scoped_prefix,
            region_projected_shared_content,
        )

    @staticmethod
    def _fail(code: str, message: str) -> None:
        raise SourceReachabilityError(code, message)

    @staticmethod
    def _text(value: Tag | None) -> str:
        if value is None:
            return ""
        return " ".join(value.get_text(" ", strip=True).split())

    @staticmethod
    def _normalized_attribute(value: Any) -> str:
        return " ".join(str(value or "").split())

    def _fragment_href(self, value: Any, filter_key: str) -> str:
        href = self._normalized_attribute(value)
        if (
            not href.startswith("#")
            or len(href) == 1
            or any(character.isspace() for character in href)
        ):
            self._fail(
                "invalid_filter_target",
                f"{filter_key} option has invalid fragment target {href!r}",
            )
        return href

    def _require_unique(
        self,
        values: Iterable[str],
        code: str,
        label: str,
    ) -> None:
        materialized = tuple(values)
        if len(materialized) != len(set(materialized)):
            self._fail(code, f"{label} values must be unique")

    def _single_default(
        self,
        filter_key: str,
        surface: str,
        values: list[str],
    ) -> str | None:
        unique = tuple(dict.fromkeys(values))
        if len(unique) > 1:
            self._fail(
                "multiple_filter_defaults",
                f"{filter_key} {surface} control declares multiple defaults",
            )
        return unique[0] if unique else None

    def _declared_default(
        self,
        filter_key: str,
        explicit_defaults: list[str],
        ordered_hrefs: list[str],
        labels: dict[str, str],
        selected_item_label: str,
    ) -> str | None:
        explicit = self._single_default(
            filter_key, "desktop", explicit_defaults
        )
        if explicit is not None:
            return explicit
        label_matches = [
            href
            for href in ordered_hrefs
            if selected_item_label and labels[href] == selected_item_label
        ]
        if len(label_matches) == 1:
            return label_matches[0]
        if len(ordered_hrefs) == 1:
            return ordered_hrefs[0]
        return None

    def _reconcile_default(
        self,
        filter_key: str,
        desktop_default: str | None,
        mobile_default: str | None,
        ordered_hrefs: list[str],
    ) -> str:
        if (
            desktop_default is not None
            and mobile_default is not None
            and desktop_default != mobile_default
        ):
            self._fail(
                "responsive_filter_default_mismatch",
                f"{filter_key} desktop/mobile defaults differ",
            )
        default = desktop_default or mobile_default
        if default is None and len(ordered_hrefs) == 1:
            default = ordered_hrefs[0]
        if default is None:
            self._fail(
                "missing_filter_default",
                f"{filter_key} has no source-proven default",
            )
        return default

    @staticmethod
    def _default_first(values: list[str], default: str) -> list[str]:
        return [default] + [value for value in values if value != default]

    @staticmethod
    def _effectively_hidden(container: Tag, root: Tag) -> bool:
        current: Tag | None = container
        while current is not None:
            style = re.sub(
                r"\s+",
                "",
                str(current.get("style", "")).casefold(),
            )
            if (
                "display:none" in style
                or current.has_attr("hidden")
                or str(current.get("aria-hidden", "")).casefold() == "true"
            ):
                return True
            if current is root:
                break
            parent = current.parent
            current = parent if isinstance(parent, Tag) else None
        return False

    @staticmethod
    def _tag_id(tag: Tag) -> str | None:
        value = str(tag.get("id", "")).strip()
        return value or None


__all__ = [
    "ReachabilityFilterDefinition",
    "ReachabilityOption",
    "ReachabilitySourceEvidence",
    "ReachableCmsState",
    "SoftwareScopedPrefixEvidence",
    "SourceReachability",
    "SourceReachabilityError",
    "SourceReachabilityFinding",
    "SourceReachabilityResolver",
    "SuppressedReachabilityOption",
]
