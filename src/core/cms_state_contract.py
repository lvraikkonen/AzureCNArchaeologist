"""Strict semantic contract for CMS filter state reconstruction.

The JSON Schemas intentionally preserve the confirmed CMS wire shape.  This
module validates the stronger v0.4 machine semantics without adding fields to
the Business Payload: nested canonical JSON, filter domains, complete state
coverage against a source-proven reachable relation, and the Flexible Page
State Machine.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup

from src.core.html_price_bearing import is_price_bearing_html
from src.utils.html.cleaner import clean_html_content

_FILTER_DEFINITION_FIELDS = {"filterKey", "filterType", "displayName", "options"}
_FILTER_OPTION_FIELDS = {"value", "label", "href"}
_FILTER_CRITERION_FIELDS = {"filterKey", "matchValues"}
_REQUIRED_CONTENT_GROUP_FIELDS = {
    "groupName",
    "filterCriteriaJson",
    "content",
    "sortOrder",
    "isActive",
}
_OPTIONAL_CONTENT_GROUP_FIELDS = {"sharedContent"}
_STRATEGY_PAGE_TYPES = {
    "simple_static": "Simple",
    "region_filter": "RegionFilter",
    "complex": "ComplexFilter",
}
_PLACEHOLDER_PATTERN = re.compile(
    r"(?:未找到\s*(?:tab|选项卡)?\s*内容|no\s+(?:tab\s+)?content\s+found|"
    r"\bplaceholder\b|\btodo\b|\btbd\b)",
    re.IGNORECASE,
)
_PLACEHOLDER_MARKUP_PATTERN = re.compile(
    r"(?:tab-content-missing|data-placeholder\s*=|"
    r"class\s*=\s*['\"][^'\"]*\bplaceholder\b)",
    re.IGNORECASE,
)
_STALE_MARKUP_PATTERN = re.compile(
    r"(?:data-stale\s*=|is-stale\s*=|class\s*=\s*['\"][^'\"]*\bstale\b)",
    re.IGNORECASE,
)
_MULTIVALUE_PATTERN = re.compile(r"(?:^\s*\[|[,;|])")
_GROUP_NAME_DELIMITER = " - "


def canonical_cms_nested_json(value: Any) -> str:
    """Serialize nested CMS JSON using contract-defined field order.

    Object keys are not alphabetically sorted: filter and criterion field
    order is part of the confirmed wire contract, while array order is
    behavior-bearing and must remain unchanged.
    """

    ordered = _order_cms_nested_value(value)
    return json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True, order=True)
class CmsState:
    """Exact ordered machine identity for one CMS selection state."""

    criteria: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.criteria, tuple):
            raise TypeError("CmsState.criteria must be a tuple of (filterKey, value) pairs")
        seen_keys: set[str] = set()
        for pair in self.criteria:
            if (
                not isinstance(pair, tuple)
                or len(pair) != 2
                or not all(isinstance(value, str) for value in pair)
            ):
                raise TypeError("CmsState criteria must contain only (str, str) tuples")
            key, value = pair
            if not key.strip() or not value.strip():
                raise ValueError("CmsState keys and values must be non-empty")
            if key in seen_keys:
                raise ValueError(f"CmsState contains duplicate filterKey {key!r}")
            seen_keys.add(key)

    @classmethod
    def from_keys_and_values(
        cls,
        keys: Sequence[str],
        values: Sequence[str],
    ) -> "CmsState":
        return cls(tuple(zip(keys, values, strict=True)))

    def to_dict(self) -> dict[str, str]:
        return dict(self.criteria)


@dataclass(frozen=True)
class CmsStateIssue:
    code: str
    path: str
    message: str


@dataclass(frozen=True, order=True)
class ExpectedFilter:
    """One source-proven CMS filter axis for one language.

    Display names and labels are localized source truth and are validated
    independently per language.  Option values and order are bilingual machine
    identity.  A tab href is normalized to ``#<value>`` by contract; a dropdown
    href remains the exact language-specific source-proven href.
    """

    key: str
    filter_type: str
    display_name: str
    option_values: tuple[str, ...]
    option_labels: tuple[str, ...]
    option_hrefs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("ExpectedFilter.key must be a non-empty string")
        if self.filter_type not in {"dropdown", "tab"}:
            raise ValueError("ExpectedFilter.filter_type must be dropdown or tab")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError(
                "ExpectedFilter.display_name must be a non-empty string"
            )
        if not isinstance(self.option_values, tuple) or not self.option_values:
            raise ValueError(
                "ExpectedFilter.option_values must be a non-empty tuple"
            )
        if not isinstance(self.option_labels, tuple):
            raise TypeError("ExpectedFilter.option_labels must be a tuple")
        if not isinstance(self.option_hrefs, tuple):
            raise TypeError("ExpectedFilter.option_hrefs must be a tuple")
        if not (
            len(self.option_values)
            == len(self.option_labels)
            == len(self.option_hrefs)
        ):
            raise ValueError(
                "ExpectedFilter option values, labels, and hrefs must align"
            )
        if (
            any(
                not isinstance(value, str)
                or not value.strip()
                or _is_wildcard_or_multivalue(value)
                for value in self.option_values
            )
            or len(self.option_values) != len(set(self.option_values))
        ):
            raise ValueError(
                "ExpectedFilter option values must be unique exact strings"
            )
        if any(
            not isinstance(label, str)
            or not label.strip()
            or _GROUP_NAME_DELIMITER in label
            for label in self.option_labels
        ):
            raise ValueError(
                "ExpectedFilter option labels must be non-empty strings without "
                f"the reserved delimiter {_GROUP_NAME_DELIMITER!r}"
            )
        if any(not isinstance(href, str) for href in self.option_hrefs):
            raise TypeError("ExpectedFilter option hrefs must be strings")
        if self.filter_type == "tab":
            expected_hrefs = tuple(f"#{value}" for value in self.option_values)
            if self.option_hrefs != expected_hrefs:
                raise ValueError(
                    "ExpectedFilter tab hrefs must equal #<option value>"
                )


@dataclass(frozen=True)
class ExpectedSoftwareScopedPrefix:
    """Exact source prefix expected at the start of one descendant state."""

    software_value: str
    software_panel_id: str
    category_panel_ids: tuple[str, ...]
    fragment_count: int
    source_html: str
    source_html_sha256: str

    def __post_init__(self) -> None:
        if not self.software_value.strip():
            raise ValueError("software_value must be non-empty")
        if not self.software_panel_id.strip():
            raise ValueError("software_panel_id must be non-empty")
        if (
            not isinstance(self.category_panel_ids, tuple)
            or not self.category_panel_ids
            or any(
                not isinstance(value, str) or not value.strip()
                for value in self.category_panel_ids
            )
            or len(self.category_panel_ids)
            != len(set(self.category_panel_ids))
        ):
            raise ValueError(
                "category_panel_ids must be unique non-empty strings"
            )
        if self.fragment_count < 1:
            raise ValueError("fragment_count must be positive")
        if not self.source_html.strip():
            raise ValueError("source_html must be non-empty")
        actual = hashlib.sha256(self.source_html.encode("utf-8")).hexdigest()
        if actual != self.source_html_sha256:
            raise ValueError(
                "source_html does not match source_html_sha256"
            )

    @property
    def projected_html(self) -> str:
        return clean_html_content(self.source_html)


@dataclass(frozen=True)
class ExpectedRegionProjectedSharedContent:
    """Exact source/config-bound shared content for one Region state."""

    projection_algorithm: str
    internal_software_value: str
    software_panel_id: str
    category_panel_ids: tuple[str, ...]
    region_value: str
    source_html_sha256: str
    source_table_ids: tuple[str, ...]
    soft_category_path: str
    soft_category_sha256: str
    config_entry_index: int
    config_rule_table_ids: tuple[str, ...]
    removed_table_ids: tuple[str, ...]
    retained_table_ids: tuple[str, ...]
    projected_html: str
    projected_html_sha256: str

    def __post_init__(self) -> None:
        if (
            self.projection_algorithm
            != "exact-table-id-nearest-scroll-table-v1"
        ):
            raise ValueError(
                "projection_algorithm must identify the fail-closed projector"
            )
        for field_name, value in (
            ("internal_software_value", self.internal_software_value),
            ("software_panel_id", self.software_panel_id),
            ("region_value", self.region_value),
            ("soft_category_path", self.soft_category_path),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be non-empty")
        for field_name, values in (
            ("category_panel_ids", self.category_panel_ids),
            ("source_table_ids", self.source_table_ids),
            ("config_rule_table_ids", self.config_rule_table_ids),
            ("removed_table_ids", self.removed_table_ids),
            ("retained_table_ids", self.retained_table_ids),
        ):
            if (
                not isinstance(values, tuple)
                or not values
                or any(
                    not isinstance(value, str) or not value.strip()
                    for value in values
                )
                or len(values) != len(set(values))
            ):
                raise ValueError(
                    f"{field_name} must be unique non-empty strings"
                )
        if self.config_entry_index < 0:
            raise ValueError("config_entry_index must be non-negative")
        if (
            set(self.removed_table_ids)
            | set(self.retained_table_ids)
        ) != set(self.source_table_ids) or set(
            self.removed_table_ids
        ).intersection(
            self.retained_table_ids
        ):
            raise ValueError(
                "Removed and retained tables must partition source_table_ids"
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
        for field_name, value in (
            ("source_html_sha256", self.source_html_sha256),
            ("soft_category_sha256", self.soft_category_sha256),
            ("projected_html_sha256", self.projected_html_sha256),
        ):
            if not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError(
                    f"{field_name} must be lowercase SHA-256"
                )
        if not self.projected_html.strip():
            raise ValueError("projected_html must be non-empty")
        if hashlib.sha256(
            self.projected_html.encode("utf-8")
        ).hexdigest() != self.projected_html_sha256:
            raise ValueError(
                "projected_html does not match projected_html_sha256"
            )

    @property
    def projected_wire_html(self) -> str:
        return clean_html_content(self.projected_html)


@dataclass(frozen=True)
class ExpectedCmsReachability:
    """Source-proven ordered relation used as formal completeness authority.

    ``ordered_states`` is a sparse relation, not a global Cartesian product.
    A state may omit a filter dimension when the source path omits it.  The
    remaining criteria must preserve ``filters`` order.
    """

    filters: tuple[ExpectedFilter, ...]
    ordered_states: tuple[CmsState, ...]
    default_state: CmsState
    software_scoped_prefixes_by_state: tuple[
        ExpectedSoftwareScopedPrefix | None, ...
    ] = ()
    region_projected_shared_content_by_state: tuple[
        ExpectedRegionProjectedSharedContent | None, ...
    ] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.filters, tuple):
            raise TypeError("ExpectedCmsReachability.filters must be a tuple")
        if not isinstance(self.ordered_states, tuple):
            raise TypeError(
                "ExpectedCmsReachability.ordered_states must be a tuple"
            )
        if not isinstance(self.default_state, CmsState):
            raise TypeError(
                "ExpectedCmsReachability.default_state must be a CmsState"
            )
        if not isinstance(self.software_scoped_prefixes_by_state, tuple):
            raise TypeError(
                "ExpectedCmsReachability.software_scoped_prefixes_by_state "
                "must be a tuple"
            )
        if not isinstance(
            self.region_projected_shared_content_by_state, tuple
        ):
            raise TypeError(
                "ExpectedCmsReachability."
                "region_projected_shared_content_by_state must be a tuple"
            )
        if not all(isinstance(value, ExpectedFilter) for value in self.filters):
            raise TypeError(
                "ExpectedCmsReachability.filters must contain ExpectedFilter values"
            )
        if not all(isinstance(value, CmsState) for value in self.ordered_states):
            raise TypeError(
                "ExpectedCmsReachability.ordered_states must contain CmsState values"
            )
        if (
            not self.region_projected_shared_content_by_state
            and self.ordered_states
        ):
            object.__setattr__(
                self,
                "region_projected_shared_content_by_state",
                (None,) * len(self.ordered_states),
            )
        if len(self.software_scoped_prefixes_by_state) != len(
            self.ordered_states
        ):
            raise ValueError(
                "Software-scoped prefix expectations must align one-for-one "
                "with ordered_states"
            )
        if not all(
            value is None
            or isinstance(value, ExpectedSoftwareScopedPrefix)
            for value in self.software_scoped_prefixes_by_state
        ):
            raise TypeError(
                "software_scoped_prefixes_by_state must contain only "
                "ExpectedSoftwareScopedPrefix or None"
            )
        if len(self.region_projected_shared_content_by_state) != len(
            self.ordered_states
        ):
            raise ValueError(
                "Region-projected shared-content expectations must align "
                "one-for-one with ordered_states"
            )
        if not all(
            value is None
            or isinstance(value, ExpectedRegionProjectedSharedContent)
            for value in self.region_projected_shared_content_by_state
        ):
            raise TypeError(
                "region_projected_shared_content_by_state must contain only "
                "ExpectedRegionProjectedSharedContent or None"
            )
        for state, prefix, shared in zip(
            self.ordered_states,
            self.software_scoped_prefixes_by_state,
            self.region_projected_shared_content_by_state,
            strict=True,
        ):
            if prefix is not None and shared is not None:
                raise ValueError(
                    "A state cannot expect both Software-scoped Prefix Content "
                    "and Region-Projected Shared Content"
                )
            if shared is None:
                continue
            criteria = state.to_dict()
            if (
                criteria.get("region") != shared.region_value
                or criteria.get("category")
                not in shared.category_panel_ids
            ):
                raise ValueError(
                    "Region-Projected Shared Content scope must match the "
                    "state's exact Region and Category identities"
                )
            if (
                "software" in criteria
                and criteria["software"]
                != shared.internal_software_value
            ):
                raise ValueError(
                    "Visible software state differs from the internal "
                    "shared-content software identity"
                )

    @property
    def filter_keys(self) -> tuple[str, ...]:
        return tuple(value.key for value in self.filters)

    @property
    def filter_types(self) -> tuple[str, ...]:
        return tuple(value.filter_type for value in self.filters)

    @property
    def option_values(self) -> tuple[tuple[str, ...], ...]:
        """Return the source-proven option machine order for each filter."""

        return tuple(value.option_values for value in self.filters)

    @property
    def display_names(self) -> tuple[str, ...]:
        return tuple(value.display_name for value in self.filters)

    @property
    def option_labels(self) -> tuple[tuple[str, ...], ...]:
        return tuple(value.option_labels for value in self.filters)

    @property
    def option_hrefs(self) -> tuple[tuple[str, ...], ...]:
        return tuple(value.option_hrefs for value in self.filters)

    @property
    def software_scoped_prefix_scopes(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                value.software_value
                for value in self.software_scoped_prefixes_by_state
                if value is not None
            )
        )

    @property
    def region_projected_shared_content_scopes(
        self,
    ) -> tuple[tuple[object, ...], ...]:
        return tuple(
            (
                state.criteria,
                value.projection_algorithm,
                value.internal_software_value,
                value.software_panel_id,
                value.region_value,
                value.category_panel_ids,
                tuple(sorted(value.source_table_ids)),
                value.soft_category_path,
                value.soft_category_sha256,
                value.config_entry_index,
                tuple(sorted(value.config_rule_table_ids)),
                tuple(sorted(value.removed_table_ids)),
                tuple(sorted(value.retained_table_ids)),
            )
            for state, value in zip(
                self.ordered_states,
                self.region_projected_shared_content_by_state,
                strict=True,
            )
            if value is not None
        )

    @property
    def relation_option_values(self) -> tuple[tuple[str, ...], ...]:
        """Derive each filter's first-occurrence union from the relation."""

        values_by_key = {key: [] for key in self.filter_keys}
        for state in self.ordered_states:
            for key, value in state.criteria:
                values = values_by_key.get(key)
                if values is not None and value not in values:
                    values.append(value)
        return tuple(tuple(values_by_key[key]) for key in self.filter_keys)


@dataclass(frozen=True)
class CmsMachineIdentity:
    page_type: str
    enable_filters: bool
    filter_keys: tuple[str, ...]
    filter_types: tuple[str, ...]
    option_values: tuple[tuple[str, ...], ...]
    option_hrefs: tuple[tuple[str, ...], ...]
    default_state: CmsState
    relation: tuple[CmsState, ...]

    @property
    def state_order(self) -> tuple[CmsState, ...]:
        """Backward-compatible name for the ordered reachable relation."""

        return self.relation


@dataclass(frozen=True)
class CmsStateContractResult:
    errors: tuple[CmsStateIssue, ...]
    source_findings: tuple[CmsStateIssue, ...]
    machine_identity: CmsMachineIdentity | None


@dataclass(frozen=True)
class _FilterDefinition:
    key: str
    filter_type: str
    display_name: str
    values: tuple[str, ...]
    labels: tuple[str, ...]
    hrefs: tuple[str, ...]


@dataclass(frozen=True)
class _ParsedGroup:
    index: int
    state: CmsState | None
    content: str | None
    shared_content: str | None


def validate_flexible_state_contract(
    payload: Any,
    *,
    expected_semantic_strategy: str | None = None,
    expected_reachability: ExpectedCmsReachability | None = None,
    source_confirmed_empty_states: Collection[CmsState] = (),
) -> CmsStateContractResult:
    """Validate one FlexibleContent payload against source-proven reachability."""

    errors: list[CmsStateIssue] = []
    findings: list[CmsStateIssue] = []
    if not isinstance(payload, Mapping):
        return CmsStateContractResult(
            (CmsStateIssue("invalid_flexible_payload", "$", "FlexibleContent payload must be an object."),),
            (),
            None,
        )

    expected = _validate_expected_reachability(expected_reachability, errors)
    exceptions = _validate_empty_state_exceptions(
        source_confirmed_empty_states, errors
    )
    page_config = payload.get("pageConfig")
    if not isinstance(page_config, Mapping):
        errors.append(CmsStateIssue(
            "invalid_page_config",
            "$.pageConfig",
            "pageConfig must be an object.",
        ))
        page_config = {}

    page_type = page_config.get("pageType")
    enable_filters = page_config.get("enableFilters")
    definitions = _parse_filter_definitions(page_config, errors)
    filter_keys = tuple(definition.key for definition in definitions)
    filter_types = tuple(definition.filter_type for definition in definitions)
    option_values = tuple(definition.values for definition in definitions)
    option_hrefs = tuple(definition.hrefs for definition in definitions)
    if expected is not None:
        _validate_filter_identity(definitions, expected, errors)
        _validate_scoped_option_labels(definitions, expected, errors)

    groups_value = payload.get("contentGroups")
    if not isinstance(groups_value, list):
        errors.append(CmsStateIssue(
            "invalid_content_groups",
            "$.contentGroups",
            "contentGroups must be an array.",
        ))
        groups: list[Any] = []
    else:
        groups = groups_value

    _validate_ordered_items(groups, "$.contentGroups", errors)
    common_sections = payload.get("commonSections")
    if isinstance(common_sections, list):
        _validate_ordered_items(common_sections, "$.commonSections", errors)
        _validate_common_sections(common_sections, errors)
    elif common_sections is not None:
        errors.append(CmsStateIssue(
            "invalid_common_sections",
            "$.commonSections",
            "commonSections must be an array.",
        ))

    parsed_groups = [
        _parse_content_group(group, index, definitions, expected, errors)
        for index, group in enumerate(groups)
    ]

    _validate_page_state_machine(
        payload,
        page_type,
        enable_filters,
        definitions,
        parsed_groups,
        expected_semantic_strategy,
        errors,
    )

    relation = tuple(
        parsed.state for parsed in parsed_groups if parsed.state is not None
    )
    if enable_filters is True and definitions:
        if expected is not None:
            _validate_reachable_coverage(
                expected.ordered_states, parsed_groups, errors
            )
            _validate_default_state(
                expected, definitions, relation, errors
            )
            _validate_software_scoped_prefix_projection(
                expected, parsed_groups, errors
            )
            _validate_region_projected_shared_content_projection(
                payload, expected, parsed_groups, errors
            )
        _validate_price_bearing_groups(
            parsed_groups,
            exceptions,
            findings,
            errors,
            expected=expected,
        )
    elif exceptions:
        for state in sorted(exceptions):
            errors.append(CmsStateIssue(
                "invalid_source_confirmed_empty_state",
                "$.source_confirmed_empty_states",
                f"Source-confirmed empty state {state.to_dict()!r} is invalid for a page without active filters.",
            ))

    expected_set = set(expected.ordered_states) if expected is not None else set()
    for state in sorted(exceptions - expected_set):
        errors.append(CmsStateIssue(
            "invalid_source_confirmed_empty_state",
            "$.source_confirmed_empty_states",
            f"Source-confirmed empty state {state.to_dict()!r} is outside the source-proven reachable relation.",
        ))

    default_state = relation[0] if relation else CmsState(())
    identity = None
    if isinstance(page_type, str) and isinstance(enable_filters, bool):
        identity = CmsMachineIdentity(
            page_type=page_type,
            enable_filters=enable_filters,
            filter_keys=filter_keys,
            filter_types=filter_types,
            option_values=option_values,
            option_hrefs=option_hrefs,
            default_state=default_state,
            relation=relation,
        )

    return CmsStateContractResult(tuple(errors), tuple(findings), identity)


def validate_bilingual_machine_identity(
    zh_cn_payload: Any,
    en_us_payload: Any,
    *,
    zh_cn_expected_reachability: ExpectedCmsReachability | None = None,
    en_us_expected_reachability: ExpectedCmsReachability | None = None,
    expected_semantic_strategy: str | None = None,
    zh_cn_source_confirmed_empty_states: Collection[CmsState] = (),
    en_us_source_confirmed_empty_states: Collection[CmsState] = (),
) -> CmsStateContractResult:
    """Validate bilingual machine identities while allowing localized labels."""

    errors: list[CmsStateIssue] = []
    findings: list[CmsStateIssue] = []
    zh_result = validate_flexible_state_contract(
        zh_cn_payload,
        expected_semantic_strategy=expected_semantic_strategy,
        expected_reachability=zh_cn_expected_reachability,
        source_confirmed_empty_states=zh_cn_source_confirmed_empty_states,
    )
    en_result = validate_flexible_state_contract(
        en_us_payload,
        expected_semantic_strategy=expected_semantic_strategy,
        expected_reachability=en_us_expected_reachability,
        source_confirmed_empty_states=en_us_source_confirmed_empty_states,
    )
    errors.extend(_prefix_issues(zh_result.errors, "zh-cn"))
    errors.extend(_prefix_issues(en_result.errors, "en-us"))
    findings.extend(_prefix_issues(zh_result.source_findings, "zh-cn"))
    findings.extend(_prefix_issues(en_result.source_findings, "en-us"))

    if isinstance(zh_cn_payload, Mapping) and zh_cn_payload.get("language") != "zh-cn":
        errors.append(CmsStateIssue(
            "bilingual_language_identity_mismatch",
            "$.zh-cn.language",
            "The zh-cn payload must declare language=zh-cn.",
        ))
    if isinstance(en_us_payload, Mapping) and en_us_payload.get("language") != "en-us":
        errors.append(CmsStateIssue(
            "bilingual_language_identity_mismatch",
            "$.en-us.language",
            "The en-us payload must declare language=en-us.",
        ))

    zh_identity = zh_result.machine_identity
    en_identity = en_result.machine_identity
    if zh_identity is None or en_identity is None:
        return CmsStateContractResult(tuple(errors), tuple(findings), None)

    comparisons = (
        ("page_type", "bilingual_page_type_mismatch", "pageType"),
        ("enable_filters", "bilingual_enable_filters_mismatch", "enableFilters"),
    )
    source_drift_dimensions = _bilingual_source_drift_dimensions(
        zh_cn_expected_reachability,
        en_us_expected_reachability,
    )
    if source_drift_dimensions:
        findings.append(CmsStateIssue(
            "bilingual_source_reachability_drift",
            "$.expected_reachability",
            (
                "The independently source-proven bilingual reachability differs "
                "in "
                f"{', '.join(source_drift_dimensions)}. Each language remains "
                "validated against its own frozen source; approval requires a "
                "controlled source-finding disposition."
            ),
        ))
    else:
        comparisons += (
            ("filter_keys", "bilingual_filter_keys_mismatch", "filter keys"),
            ("filter_types", "bilingual_filter_types_mismatch", "filter types"),
            (
                "option_values",
                "bilingual_option_values_mismatch",
                "ordered option values",
            ),
            (
                "default_state",
                "bilingual_default_state_mismatch",
                "Default CMS State",
            ),
            (
                "relation",
                "bilingual_reachability_relation_mismatch",
                "ordered reachable relation",
            ),
        )
    for attribute, code, label in comparisons:
        if getattr(zh_identity, attribute) != getattr(en_identity, attribute):
            errors.append(CmsStateIssue(
                code,
                "$",
                f"Bilingual {label} must have identical machine identities and order.",
            ))

    return CmsStateContractResult(tuple(errors), tuple(findings), zh_identity)


def _bilingual_source_drift_dimensions(
    zh_cn_expected: ExpectedCmsReachability | None,
    en_us_expected: ExpectedCmsReachability | None,
) -> tuple[str, ...]:
    """Return deterministic source-machine differences, excluding presentation.

    Localized display names, option labels, and raw hrefs are intentionally not
    bilingual machine identity.  Each remains validated against the source for
    its own language.
    """

    if not isinstance(zh_cn_expected, ExpectedCmsReachability) or not isinstance(
        en_us_expected, ExpectedCmsReachability
    ):
        return ()
    comparisons = (
        ("filter keys", zh_cn_expected.filter_keys, en_us_expected.filter_keys),
        (
            "filter types",
            zh_cn_expected.filter_types,
            en_us_expected.filter_types,
        ),
        (
            "ordered option values",
            zh_cn_expected.option_values,
            en_us_expected.option_values,
        ),
        (
            "Default CMS State",
            zh_cn_expected.default_state,
            en_us_expected.default_state,
        ),
        (
            "ordered Reachability Relation",
            zh_cn_expected.ordered_states,
            en_us_expected.ordered_states,
        ),
        (
            "software-scoped prefix scopes",
            zh_cn_expected.software_scoped_prefix_scopes,
            en_us_expected.software_scoped_prefix_scopes,
        ),
        (
            "Region-Projected Shared Content scopes",
            zh_cn_expected.region_projected_shared_content_scopes,
            en_us_expected.region_projected_shared_content_scopes,
        ),
    )
    return tuple(
        label for label, zh_value, en_value in comparisons
        if zh_value != en_value
    )


def _parse_filter_definitions(
    page_config: Mapping[str, Any],
    errors: list[CmsStateIssue],
) -> tuple[_FilterDefinition, ...]:
    path = "$.pageConfig.filtersJsonConfig"
    filters = _load_canonical_nested_json(page_config.get("filtersJsonConfig"), path, errors)
    if filters is None:
        return ()
    if not isinstance(filters, Mapping):
        errors.append(CmsStateIssue(
            "invalid_filter_config",
            path,
            "filtersJsonConfig must encode an object.",
        ))
        return ()
    if set(filters) != {"filterDefinitions"} or not isinstance(filters.get("filterDefinitions"), list):
        errors.append(CmsStateIssue(
            "invalid_filter_config",
            path,
            "filtersJsonConfig must contain only a filterDefinitions array.",
        ))
        return ()

    parsed: list[_FilterDefinition] = []
    seen_keys: set[str] = set()
    for index, value in enumerate(filters["filterDefinitions"]):
        definition_path = f"{path}.filterDefinitions[{index}]"
        if not isinstance(value, Mapping):
            errors.append(CmsStateIssue(
                "invalid_filter_definition",
                definition_path,
                "Filter definition must be an object.",
            ))
            continue
        if set(value) != _FILTER_DEFINITION_FIELDS:
            errors.append(CmsStateIssue(
                "invalid_filter_fields",
                definition_path,
                "Filter definition must contain only filterKey/filterType/displayName/options.",
            ))

        key = value.get("filterKey")
        filter_type = value.get("filterType")
        display_name = value.get("displayName")
        options = value.get("options")
        valid_key = isinstance(key, str) and bool(key.strip())
        if not valid_key:
            errors.append(CmsStateIssue(
                "empty_filter_key",
                f"{definition_path}.filterKey",
                "filterKey must be a non-empty string.",
            ))
        elif key in seen_keys:
            errors.append(CmsStateIssue(
                "duplicate_filter_key",
                f"{definition_path}.filterKey",
                f"Duplicate filterKey {key!r}.",
            ))
        if valid_key:
            seen_keys.add(key)

        if filter_type not in {"dropdown", "tab"}:
            errors.append(CmsStateIssue(
                "invalid_filter_type",
                f"{definition_path}.filterType",
                "filterType must be lowercase dropdown or tab.",
            ))
        if not isinstance(display_name, str) or not display_name.strip():
            errors.append(CmsStateIssue(
                "empty_filter_display_name",
                f"{definition_path}.displayName",
                "displayName must be a non-empty string.",
            ))
        if not isinstance(options, list) or not options:
            errors.append(CmsStateIssue(
                "empty_filter_domain",
                f"{definition_path}.options",
                "Every filter domain must contain at least one option.",
            ))
            options = []

        option_values: list[str] = []
        option_labels: list[str] = []
        option_hrefs: list[str] = []
        seen_values: set[str] = set()
        for option_index, option in enumerate(options):
            option_path = f"{definition_path}.options[{option_index}]"
            if not isinstance(option, Mapping):
                errors.append(CmsStateIssue(
                    "invalid_filter_option",
                    option_path,
                    "Filter option must be an object.",
                ))
                continue
            if not {"value", "label"}.issubset(option) or set(option) - _FILTER_OPTION_FIELDS:
                errors.append(CmsStateIssue(
                    "invalid_filter_option_fields",
                    option_path,
                    "Only value/label/href are permitted; value and label are required.",
                ))
            option_value = option.get("value")
            label = option.get("label")
            href = option.get("href", "")
            if not isinstance(option_value, str) or not option_value.strip():
                errors.append(CmsStateIssue(
                    "empty_filter_option_value",
                    f"{option_path}.value",
                    "Option value must be a non-empty string.",
                ))
                continue
            if _is_wildcard_or_multivalue(option_value):
                errors.append(CmsStateIssue(
                    "invalid_filter_option_value_encoding",
                    f"{option_path}.value",
                    "Option values must identify one exact state and cannot encode wildcard or multiple values.",
                ))
            if option_value in seen_values:
                errors.append(CmsStateIssue(
                    "duplicate_filter_option_value",
                    f"{option_path}.value",
                    f"Duplicate option value {option_value!r} in filter {key!r}.",
                ))
            seen_values.add(option_value)
            option_values.append(option_value)
            if not isinstance(label, str) or not label.strip():
                errors.append(CmsStateIssue(
                    "empty_filter_option_label",
                    f"{option_path}.label",
                    "Option label must be a non-empty string.",
                ))
                option_labels.append("")
            else:
                option_labels.append(label)
            if isinstance(label, str) and _GROUP_NAME_DELIMITER in label:
                errors.append(CmsStateIssue(
                    "filter_option_label_contains_group_delimiter",
                    f"{option_path}.label",
                    (
                        "Option labels cannot contain the reserved groupName "
                        f"delimiter {_GROUP_NAME_DELIMITER!r}."
                    ),
                ))
            if not isinstance(href, str):
                errors.append(CmsStateIssue(
                    "invalid_filter_option_href",
                    f"{option_path}.href",
                    "Option href must be a string when present.",
                ))
                option_hrefs.append("")
            else:
                option_hrefs.append(href)

        if valid_key and isinstance(filter_type, str):
            parsed.append(_FilterDefinition(
                key,
                filter_type,
                display_name if isinstance(display_name, str) else "",
                tuple(option_values),
                tuple(option_labels),
                tuple(option_hrefs),
            ))

    return tuple(parsed)


def _parse_content_group(
    group: Any,
    index: int,
    definitions: tuple[_FilterDefinition, ...],
    expected: ExpectedCmsReachability | None,
    errors: list[CmsStateIssue],
) -> _ParsedGroup:
    group_path = f"$.contentGroups[{index}]"
    if not isinstance(group, Mapping):
        errors.append(CmsStateIssue(
            "invalid_content_group",
            group_path,
            "Content group must be an object.",
        ))
        return _ParsedGroup(index, None, None, None)

    group_fields = set(group)
    if not (
        group_fields == _REQUIRED_CONTENT_GROUP_FIELDS
        or group_fields
        == _REQUIRED_CONTENT_GROUP_FIELDS | _OPTIONAL_CONTENT_GROUP_FIELDS
    ):
        errors.append(CmsStateIssue(
            "invalid_content_group_fields",
            group_path,
            (
                "Content group must contain the required groupName/"
                "filterCriteriaJson/content/sortOrder/isActive fields and may "
                "contain only source-proven sharedContent."
            ),
        ))
    stale_fields = sorted(key for key in group if "stale" in str(key).lower())
    for key in stale_fields:
        errors.append(CmsStateIssue(
            "stale_group_field",
            f"{group_path}.{key}",
            "Stale lifecycle fields are forbidden in generated content groups.",
        ))
    if group.get("isActive") is not True:
        errors.append(CmsStateIssue(
            "inactive_content_group",
            f"{group_path}.isActive",
            "Every generated content group must be active.",
        ))
    group_name = group.get("groupName")
    if not isinstance(group_name, str) or not group_name.strip():
        errors.append(CmsStateIssue(
            "empty_content_group_name",
            f"{group_path}.groupName",
            "groupName must be non-empty.",
        ))
    content = group.get("content")
    if isinstance(content, str) and _visible_text(content) and (
        _PLACEHOLDER_PATTERN.search(_visible_text(content))
        or _PLACEHOLDER_MARKUP_PATTERN.search(content)
    ):
        errors.append(CmsStateIssue(
            "placeholder_content_group",
            f"{group_path}.content",
            "Placeholder content is forbidden in generated content groups.",
        ))
    if isinstance(content, str) and _STALE_MARKUP_PATTERN.search(content):
        errors.append(CmsStateIssue(
            "stale_content_group",
            f"{group_path}.content",
            "Stale marked content is forbidden in generated content groups.",
        ))
    shared_content: str | None = None
    if "sharedContent" in group:
        shared_value = group.get("sharedContent")
        if not isinstance(shared_value, str) or not _visible_text(
            shared_value
        ):
            errors.append(CmsStateIssue(
                "empty_shared_content",
                f"{group_path}.sharedContent",
                (
                    "Present sharedContent must contain non-empty visible "
                    "Region-Projected Shared Content."
                ),
            ))
        else:
            shared_content = shared_value
            if (
                _PLACEHOLDER_PATTERN.search(_visible_text(shared_value))
                or _PLACEHOLDER_MARKUP_PATTERN.search(shared_value)
            ):
                errors.append(CmsStateIssue(
                    "placeholder_shared_content",
                    f"{group_path}.sharedContent",
                    "Placeholder sharedContent is forbidden.",
                ))
            if _STALE_MARKUP_PATTERN.search(shared_value):
                errors.append(CmsStateIssue(
                    "stale_shared_content",
                    f"{group_path}.sharedContent",
                    "Stale marked sharedContent is forbidden.",
                ))

    criteria_path = f"{group_path}.filterCriteriaJson"
    criteria = _load_canonical_nested_json(group.get("filterCriteriaJson"), criteria_path, errors)
    if criteria is None:
        _validate_rendered_state_content(
            group_path,
            content,
            shared_content,
            None,
            expected,
            errors,
        )
        return _ParsedGroup(
            index,
            None,
            content if isinstance(content, str) else None,
            shared_content,
        )
    if not isinstance(criteria, list):
        errors.append(CmsStateIssue(
            "invalid_filter_criteria",
            criteria_path,
            "filterCriteriaJson must encode an array.",
        ))
        _validate_rendered_state_content(
            group_path,
            content,
            shared_content,
            None,
            expected,
            errors,
        )
        return _ParsedGroup(
            index,
            None,
            content if isinstance(content, str) else None,
            shared_content,
        )

    parsed_pairs: list[tuple[str, str]] = []
    for criterion_index, criterion in enumerate(criteria):
        criterion_path = f"{criteria_path}[{criterion_index}]"
        if not isinstance(criterion, Mapping) or set(criterion) != _FILTER_CRITERION_FIELDS:
            errors.append(CmsStateIssue(
                "invalid_filter_criterion_fields",
                criterion_path,
                "Criterion must contain only filterKey and matchValues.",
            ))
            continue
        key = criterion.get("filterKey")
        value = criterion.get("matchValues")
        if not isinstance(key, str):
            errors.append(CmsStateIssue(
                "invalid_filter_criterion_key",
                f"{criterion_path}.filterKey",
                "filterKey must be a string.",
            ))
            continue
        if not isinstance(value, str):
            errors.append(CmsStateIssue(
                "match_values_not_string",
                f"{criterion_path}.matchValues",
                "matchValues must be one string value.",
            ))
            continue
        if _is_wildcard_or_multivalue(value):
            errors.append(CmsStateIssue(
                "invalid_match_value_encoding",
                f"{criterion_path}.matchValues",
                "matchValues cannot encode wildcard or multiple values.",
            ))
        parsed_pairs.append((key, value))

    filter_keys = tuple(definition.key for definition in definitions)
    definition_by_key = {definition.key: definition for definition in definitions}
    expected_labels_by_key = {
        definition.key: dict(zip(
            definition.option_values,
            definition.option_labels,
            strict=True,
        ))
        for definition in expected.filters
    } if expected is not None else {}
    positions = {key: index for index, key in enumerate(filter_keys)}
    actual_keys = tuple(key for key, _ in parsed_pairs)
    valid_state = True
    if len(actual_keys) != len(set(actual_keys)):
        errors.append(CmsStateIssue(
            "incomplete_or_misordered_filter_criteria",
            criteria_path,
            "Criteria keys must occur at most once in each reachable state.",
        ))
        valid_state = False
    known_positions = [positions[key] for key in actual_keys if key in positions]
    if (
        len(known_positions) != len(actual_keys)
        or any(left >= right for left, right in itertools.pairwise(known_positions))
    ):
        errors.append(CmsStateIssue(
            "incomplete_or_misordered_filter_criteria",
            criteria_path,
            (
                "Criteria keys must be a unique ordered subsequence of "
                f"{filter_keys!r}; found {actual_keys!r}."
            ),
        ))
        valid_state = False

    localized_segments: list[str] = []
    for criterion_index, (key, value) in enumerate(parsed_pairs):
        criterion_path = f"{criteria_path}[{criterion_index}]"
        definition = definition_by_key.get(key)
        if definition is None:
            errors.append(CmsStateIssue(
                "unknown_filter_key",
                f"{criterion_path}.filterKey",
                f"No filter definition exists for {key!r}.",
            ))
            valid_state = False
            continue
        if value not in definition.values:
            errors.append(CmsStateIssue(
                "unknown_filter_value",
                f"{criterion_path}.matchValues",
                f"{value!r} is not a declared option for {key!r}.",
            ))
            valid_state = False
            continue
        source_label = expected_labels_by_key.get(key, {}).get(value)
        if source_label is not None:
            localized_segments.append(source_label)
        else:
            value_index = definition.values.index(value)
            localized_segments.append(definition.labels[value_index])

    if isinstance(group_name, str) and parsed_pairs:
        segments = group_name.split(_GROUP_NAME_DELIMITER)
        if len(segments) != len(parsed_pairs):
            errors.append(CmsStateIssue(
                "group_name_segment_count_mismatch",
                f"{group_path}.groupName",
                (
                    "groupName segment count must equal the exact criteria "
                    f"count {len(parsed_pairs)}."
                ),
            ))
        if len(localized_segments) == len(parsed_pairs):
            expected_group_name = _GROUP_NAME_DELIMITER.join(localized_segments)
            if group_name != expected_group_name:
                errors.append(CmsStateIssue(
                    "group_name_state_label_mismatch",
                    f"{group_path}.groupName",
                    (
                        "groupName must exactly equal the localized state labels "
                        f"joined by {_GROUP_NAME_DELIMITER!r}: "
                        f"{expected_group_name!r}."
                    ),
                ))

    state = CmsState(tuple(parsed_pairs)) if valid_state else None
    _validate_rendered_state_content(
        group_path,
        content,
        shared_content,
        state,
        expected,
        errors,
    )
    return _ParsedGroup(
        index,
        state,
        content if isinstance(content, str) else None,
        shared_content,
    )


def _validate_page_state_machine(
    payload: Mapping[str, Any],
    page_type: Any,
    enable_filters: Any,
    definitions: tuple[_FilterDefinition, ...],
    groups: list[_ParsedGroup],
    expected_semantic_strategy: str | None,
    errors: list[CmsStateIssue],
) -> None:
    if expected_semantic_strategy is not None:
        expected_page_type = _STRATEGY_PAGE_TYPES.get(expected_semantic_strategy)
        if expected_page_type is None:
            errors.append(CmsStateIssue(
                "unknown_semantic_strategy",
                "$.pageConfig.pageType",
                f"Unknown semantic strategy {expected_semantic_strategy!r}.",
            ))
        elif page_type != expected_page_type:
            errors.append(CmsStateIssue(
                "semantic_strategy_page_type_mismatch",
                "$.pageConfig.pageType",
                f"Strategy {expected_semantic_strategy!r} requires pageType={expected_page_type!r}.",
            ))

    base_content = payload.get("baseContent")
    if isinstance(base_content, str) and _visible_text(base_content):
        if (
            _PLACEHOLDER_PATTERN.search(_visible_text(base_content))
            or _PLACEHOLDER_MARKUP_PATTERN.search(base_content)
        ):
            errors.append(CmsStateIssue(
                "placeholder_base_content",
                "$.baseContent",
                "Placeholder baseContent is forbidden.",
            ))
        if _STALE_MARKUP_PATTERN.search(base_content):
            errors.append(CmsStateIssue(
                "stale_base_content",
                "$.baseContent",
                "Stale marked baseContent is forbidden.",
            ))
    if page_type == "Simple":
        if enable_filters is not False:
            errors.append(CmsStateIssue(
                "simple_filters_enabled",
                "$.pageConfig.enableFilters",
                "Simple pages must disable filters.",
            ))
        if definitions:
            errors.append(CmsStateIssue(
                "simple_filter_definitions_present",
                "$.pageConfig.filtersJsonConfig",
                "Simple pages must have no filter definitions.",
            ))
        if groups:
            errors.append(CmsStateIssue(
                "simple_content_groups_present",
                "$.contentGroups",
                "Simple pages must have no content groups.",
            ))
        if not isinstance(base_content, str) or not _visible_text(base_content):
            errors.append(CmsStateIssue(
                "simple_base_content_empty",
                "$.baseContent",
                "Simple pages must carry non-empty visible baseContent.",
            ))
        return

    if page_type == "RegionFilter":
        if enable_filters is not True:
            errors.append(CmsStateIssue(
                "region_filter_disabled",
                "$.pageConfig.enableFilters",
                "RegionFilter pages must enable filters.",
            ))
        if not (
            len(definitions) == 1
            and definitions[0].key == "region"
            and definitions[0].filter_type == "dropdown"
        ):
            errors.append(CmsStateIssue(
                "invalid_region_filter_topology",
                "$.pageConfig.filtersJsonConfig",
                "RegionFilter requires exactly one region dropdown domain.",
            ))
        if not groups:
            errors.append(CmsStateIssue(
                "filtered_page_has_no_groups",
                "$.contentGroups",
                "Filter-enabled pages require complete content groups.",
            ))
        return

    if page_type == "ComplexFilter":
        if enable_filters is not True:
            errors.append(CmsStateIssue(
                "complex_filter_disabled",
                "$.pageConfig.enableFilters",
                "ComplexFilter pages must enable filters.",
            ))
        complex_topology = bool(definitions) and (
            len(definitions) > 1
            or definitions[0].key != "region"
            or definitions[0].filter_type == "tab"
        )
        if not complex_topology:
            errors.append(CmsStateIssue(
                "invalid_complex_filter_topology",
                "$.pageConfig.filtersJsonConfig",
                "ComplexFilter requires tab, software, or multidimensional filter topology.",
            ))
        if not groups:
            errors.append(CmsStateIssue(
                "filtered_page_has_no_groups",
                "$.contentGroups",
                "Filter-enabled pages require complete content groups.",
            ))
        return

    errors.append(CmsStateIssue(
        "unknown_page_type",
        "$.pageConfig.pageType",
        "pageType must be Simple, RegionFilter, or ComplexFilter.",
    ))


def _validate_expected_reachability(
    value: ExpectedCmsReachability | None,
    errors: list[CmsStateIssue],
) -> ExpectedCmsReachability | None:
    path = "$.expected_reachability"
    if value is None:
        errors.append(CmsStateIssue(
            "missing_expected_reachability",
            path,
            (
                "FlexibleContent validation requires a source-proven expected "
                "reachable relation; Payload fields cannot authorize completeness."
            ),
        ))
        return None
    if not isinstance(value, ExpectedCmsReachability):
        errors.append(CmsStateIssue(
            "invalid_expected_reachability",
            path,
            "expected_reachability must be an ExpectedCmsReachability value.",
        ))
        return None

    filter_keys = value.filter_keys
    if len(filter_keys) != len(set(filter_keys)):
        errors.append(CmsStateIssue(
            "invalid_expected_reachability",
            f"{path}.filters",
            "Source-proven filter keys must be unique.",
        ))
    if len(value.ordered_states) != len(set(value.ordered_states)):
        errors.append(CmsStateIssue(
            "duplicate_expected_reachable_state",
            f"{path}.ordered_states",
            "Source-proven reachable states must be unique.",
        ))

    positions = {key: index for index, key in enumerate(filter_keys)}
    for index, state in enumerate(value.ordered_states):
        keys = tuple(key for key, _ in state.criteria)
        known_positions = [positions[key] for key in keys if key in positions]
        if (
            not keys
            or len(known_positions) != len(keys)
            or any(
                left >= right
                for left, right in itertools.pairwise(known_positions)
            )
        ):
            errors.append(CmsStateIssue(
                "invalid_expected_reachable_state",
                f"{path}.ordered_states[{index}]",
                (
                    "Each expected state must contain a non-empty, unique "
                    "ordered subsequence of the source-proven filter keys."
                ),
            ))

    if value.filters and not value.ordered_states:
        errors.append(CmsStateIssue(
            "empty_expected_reachable_relation",
            f"{path}.ordered_states",
            "A filtered page must prove at least one reachable state.",
        ))
    if not value.filters and value.ordered_states:
        errors.append(CmsStateIssue(
            "unexpected_unfiltered_reachable_state",
            f"{path}.ordered_states",
            "An unfiltered page cannot declare reachable filter states.",
        ))
    if value.option_values != value.relation_option_values:
        errors.append(CmsStateIssue(
            "expected_option_union_mismatch",
            f"{path}.filters",
            (
                "Source-proven filter option values/order must equal the "
                "first-occurrence union of the source-proven reachable relation."
            ),
        ))
    for key, values in zip(
        value.filter_keys, value.relation_option_values, strict=True
    ):
        if not values:
            errors.append(CmsStateIssue(
                "unused_expected_filter",
                f"{path}.filters",
                (
                    f"Source-proven filter {key!r} does not participate in any "
                    "reachable state."
                ),
            ))

    if value.ordered_states:
        if value.default_state not in value.ordered_states:
            errors.append(CmsStateIssue(
                "expected_default_state_not_reachable",
                f"{path}.default_state",
                "The source-proven default must be a reachable state.",
            ))
        elif value.default_state != value.ordered_states[0]:
            errors.append(CmsStateIssue(
                "expected_default_state_not_first",
                f"{path}.default_state",
                "The source-proven default must be first in relation order.",
            ))
    elif value.default_state != CmsState(()):
        errors.append(CmsStateIssue(
            "invalid_unfiltered_default_state",
            f"{path}.default_state",
            "An unfiltered relation must use the empty default state.",
        ))
    return value


def _validate_filter_identity(
    definitions: tuple[_FilterDefinition, ...],
    expected: ExpectedCmsReachability,
    errors: list[CmsStateIssue],
) -> None:
    path = "$.pageConfig.filtersJsonConfig"
    actual_keys = tuple(value.key for value in definitions)
    actual_types = tuple(value.filter_type for value in definitions)
    if actual_keys != expected.filter_keys:
        errors.append(CmsStateIssue(
            "filter_keys_do_not_match_expected_reachability",
            path,
            (
                f"Payload filter keys {actual_keys!r} do not equal the "
                f"source-proven order {expected.filter_keys!r}."
            ),
        ))
    if actual_types != expected.filter_types:
        errors.append(CmsStateIssue(
            "filter_types_do_not_match_expected_reachability",
            path,
            (
                f"Payload filter types {actual_types!r} do not equal the "
                f"source-proven types {expected.filter_types!r}."
            ),
        ))

    definitions_by_key = {value.key: value for value in definitions}
    expected_by_key = {value.key: value for value in expected.filters}
    for definition_index, (key, expected_values) in enumerate(zip(
        expected.filter_keys, expected.option_values, strict=True
    )):
        definition = definitions_by_key.get(key)
        if definition is None:
            continue
        actual_values = definition.values
        expected_set = set(expected_values)
        actual_set = set(actual_values)
        for value in actual_values:
            if value not in expected_set:
                errors.append(CmsStateIssue(
                    "unreachable_filter_option",
                    path,
                    (
                        f"Filter option {key}={value!r} participates in no "
                        "source-proven reachable state."
                    ),
                ))
        expected_filter = expected_by_key[key]
        definition_path = (
            f"{path}.filterDefinitions[{definition_index}]"
        )
        if definition.labels != expected_filter.option_labels:
            errors.append(CmsStateIssue(
                "filter_option_label_mismatch",
                f"{definition_path}.options",
                (
                    f"Filter {key!r} option labels {definition.labels!r} do not "
                    "equal the source-proven localized labels "
                    f"{expected_filter.option_labels!r}."
                ),
            ))
        if definition.display_name != expected_filter.display_name:
            errors.append(CmsStateIssue(
                "filter_display_name_mismatch",
                f"{definition_path}.displayName",
                (
                    f"Filter {key!r} displayName "
                    f"{definition.display_name!r} does not equal the "
                    "source-proven localized display name "
                    f"{expected_filter.display_name!r}."
                ),
            ))
        if definition.hrefs != expected_filter.option_hrefs:
            errors.append(CmsStateIssue(
                "filter_option_href_mismatch",
                f"{definition_path}.options",
                (
                    f"Filter {key!r} option hrefs {definition.hrefs!r} do not "
                    "equal the source-proven machine hrefs "
                    f"{expected_filter.option_hrefs!r}."
                ),
            ))
        for value in expected_values:
            if value not in actual_set:
                errors.append(CmsStateIssue(
                    "missing_reachable_filter_option",
                    path,
                    (
                        f"Source-proven reachable option {key}={value!r} is "
                        "missing from the Payload filter union."
                    ),
                ))
        if actual_set == expected_set and actual_values != expected_values:
            errors.append(CmsStateIssue(
                "filter_option_order_mismatch",
                path,
                (
                    f"Filter {key!r} option union must preserve source-proven "
                    f"first-reachable order {expected_values!r}."
                ),
            ))


def _validate_scoped_option_labels(
    definitions: tuple[_FilterDefinition, ...],
    expected: ExpectedCmsReachability,
    errors: list[CmsStateIssue],
) -> None:
    labels_by_key = {
        definition.key: dict(zip(
            definition.values, definition.labels, strict=True
        ))
        for definition in definitions
    }
    scoped_values: dict[
        tuple[str, tuple[tuple[str, str], ...]], list[str]
    ] = {}
    for state in expected.ordered_states:
        for index, (key, value) in enumerate(state.criteria):
            scope = (key, state.criteria[:index])
            values = scoped_values.setdefault(scope, [])
            if value not in values:
                values.append(value)

    reported: set[tuple[str, tuple[tuple[str, str], ...], str]] = set()
    for (key, prefix), values in scoped_values.items():
        label_map = labels_by_key.get(key, {})
        seen_labels: dict[str, str] = {}
        for value in values:
            label = label_map.get(value)
            if not label:
                continue
            prior = seen_labels.get(label)
            if prior is not None and prior != value:
                identity = (key, prefix, label)
                if identity in reported:
                    continue
                reported.add(identity)
                errors.append(CmsStateIssue(
                    "duplicate_filter_option_label_in_scope",
                    "$.pageConfig.filtersJsonConfig",
                    (
                        f"Sibling options {prior!r} and {value!r} for filter "
                        f"{key!r} share localized label {label!r} in scope "
                        f"{dict(prefix)!r}."
                    ),
                ))
            else:
                seen_labels[label] = value


def _validate_default_state(
    expected: ExpectedCmsReachability,
    definitions: tuple[_FilterDefinition, ...],
    actual_relation: tuple[CmsState, ...],
    errors: list[CmsStateIssue],
) -> None:
    if actual_relation and actual_relation[0] != expected.default_state:
        errors.append(CmsStateIssue(
            "default_state_mismatch",
            "$.contentGroups[0].filterCriteriaJson",
            (
                "The first contentGroup must be the source-proven default "
                f"state {expected.default_state.to_dict()!r}."
            ),
        ))
    definitions_by_key = {value.key: value for value in definitions}
    for key, default_value in expected.default_state.criteria:
        definition = definitions_by_key.get(key)
        if (
            definition is not None
            and definition.values
            and definition.values[0] != default_value
        ):
            errors.append(CmsStateIssue(
                "default_filter_option_mismatch",
                "$.pageConfig.filtersJsonConfig",
                (
                    f"Filter {key!r} must place source-proven default "
                    f"{default_value!r} first."
                ),
            ))


def _validate_reachable_coverage(
    expected_states: tuple[CmsState, ...],
    groups: list[_ParsedGroup],
    errors: list[CmsStateIssue],
) -> None:
    actual_states = tuple(group.state for group in groups if group.state is not None)
    counts: dict[CmsState, int] = {}
    for state in actual_states:
        counts[state] = counts.get(state, 0) + 1
    for state, count in counts.items():
        if count > 1:
            errors.append(CmsStateIssue(
                "duplicate_cms_state",
                "$.contentGroups",
                f"CMS state {state.to_dict()!r} matches {count} content groups; exactly one is required.",
            ))
    expected_set = set(expected_states)
    actual_set = set(actual_states)
    for state in expected_states:
        if state not in actual_set:
            errors.append(CmsStateIssue(
                "missing_cms_state",
                "$.contentGroups",
                f"No content group matches CMS state {state.to_dict()!r}.",
            ))
    for state in sorted(actual_set - expected_set):
        errors.append(CmsStateIssue(
            "unexpected_unreachable_state",
            "$.contentGroups",
            (
                f"Content group state {state.to_dict()!r} is outside the "
                "source-proven reachable relation."
            ),
        ))
    if actual_states != expected_states:
        errors.append(CmsStateIssue(
            "reachable_state_order_mismatch",
            "$.contentGroups",
            (
                "Physical content-group state order must exactly equal the "
                "source-proven ordered reachable relation."
            ),
        ))


def _validate_software_scoped_prefix_projection(
    expected: ExpectedCmsReachability,
    groups: list[_ParsedGroup],
    errors: list[CmsStateIssue],
) -> None:
    """Verify source-bound inherited prefixes in persisted group content."""

    prefixes_by_state = expected.software_scoped_prefixes_by_state
    if not prefixes_by_state:
        return
    known_projected_prefixes = tuple(
        dict.fromkeys(
            prefix.projected_html
            for prefix in prefixes_by_state
            if prefix is not None
        )
    )
    groups_by_state: dict[CmsState, list[_ParsedGroup]] = {}
    for group in groups:
        if group.state is not None:
            groups_by_state.setdefault(group.state, []).append(group)

    for state, expected_prefix in zip(
        expected.ordered_states,
        prefixes_by_state,
        strict=True,
    ):
        matching_groups = groups_by_state.get(state, [])
        if len(matching_groups) != 1:
            # Reachability coverage reports the missing/duplicate group.
            continue
        group = matching_groups[0]
        if not isinstance(group.content, str):
            continue
        content = clean_html_content(group.content)
        path = f"$.contentGroups[{group.index}].content"
        if expected_prefix is None:
            leaked = next(
                (
                    prefix
                    for prefix in known_projected_prefixes
                    if content.startswith(prefix)
                ),
                None,
            )
            if leaked is not None:
                errors.append(CmsStateIssue(
                    "software_scoped_prefix_scope_leakage",
                    path,
                    (
                        "Content begins with a Software-scoped Prefix that "
                        f"is not applicable to CMS state {state.to_dict()!r}."
                    ),
                ))
            continue

        projected = expected_prefix.projected_html
        if not content.startswith(projected):
            errors.append(CmsStateIssue(
                "missing_or_modified_software_scoped_prefix",
                path,
                (
                    "Content must begin with the exact source-bound "
                    "Software-scoped Prefix for CMS state "
                    f"{state.to_dict()!r}."
                ),
            ))
            continue
        if content.count(projected) != 1:
            errors.append(CmsStateIssue(
                "duplicate_software_scoped_prefix",
                path,
                (
                    "The source-bound Software-scoped Prefix must occur "
                    "exactly once in CMS state "
                    f"{state.to_dict()!r}."
                ),
                ))


def _validate_region_projected_shared_content_projection(
    payload: Mapping[str, Any],
    expected: ExpectedCmsReachability,
    groups: list[_ParsedGroup],
    errors: list[CmsStateIssue],
) -> None:
    """Verify exact state-bound sharedContent against source/config replay."""

    expected_by_state = (
        expected.region_projected_shared_content_by_state
    )
    known_wire_values = tuple(
        dict.fromkeys(
            value.projected_wire_html
            for value in expected_by_state
            if value is not None
        )
    )
    known_retained_table_ids = frozenset(
        table_id
        for value in expected_by_state
        if value is not None
        for table_id in value.retained_table_ids
    )
    external_fields: list[tuple[str, str]] = []
    base_content = payload.get("baseContent")
    if isinstance(base_content, str):
        external_fields.append(("$.baseContent", base_content))
    common_sections = payload.get("commonSections")
    if isinstance(common_sections, list):
        for index, section in enumerate(common_sections):
            if (
                isinstance(section, Mapping)
                and isinstance(section.get("content"), str)
            ):
                external_fields.append(
                    (
                        f"$.commonSections[{index}].content",
                        section["content"],
                    )
                )
    for path, raw_value in external_fields:
        cleaned = clean_html_content(raw_value)
        leaked_wire = any(
            wire_value and wire_value in cleaned
            for wire_value in known_wire_values
        )
        leaked_table_ids = (
            _table_ids_in_html(raw_value)
            & known_retained_table_ids
        )
        if leaked_wire or leaked_table_ids:
            errors.append(CmsStateIssue(
                "region_projected_shared_content_outside_shared_field",
                path,
                (
                    "Region-Projected Shared Content may appear only in the "
                    "matching contentGroup.sharedContent field; copied retained "
                    f"table ids={sorted(leaked_table_ids)!r}."
                ),
            ))

    groups_by_state: dict[CmsState, list[_ParsedGroup]] = {}
    for group in groups:
        if group.state is not None:
            groups_by_state.setdefault(group.state, []).append(group)

    for state, expected_shared in zip(
        expected.ordered_states,
        expected_by_state,
        strict=True,
    ):
        matching_groups = groups_by_state.get(state, [])
        if len(matching_groups) != 1:
            continue
        group = matching_groups[0]
        path = f"$.contentGroups[{group.index}].sharedContent"
        actual_raw = group.shared_content
        if isinstance(group.content, str):
            content = clean_html_content(group.content)
            leaked_values = tuple(
                value
                for value in known_wire_values
                if value and value in content
            )
            leaked_table_ids = (
                _table_ids_in_html(group.content)
                & known_retained_table_ids
            )
            if leaked_values or leaked_table_ids:
                expected_retained = (
                    set(expected_shared.retained_table_ids)
                    if expected_shared is not None
                    else set()
                )
                errors.append(CmsStateIssue(
                    (
                        "duplicate_region_projected_shared_content"
                        if expected_shared is not None
                        and (
                            expected_shared.projected_wire_html
                            in leaked_values
                            or bool(
                                expected_retained
                                .intersection(leaked_table_ids)
                            )
                        )
                        else
                        "region_projected_shared_content_scope_leakage"
                    ),
                    f"$.contentGroups[{group.index}].content",
                    (
                        "Region-Projected Shared Content may not be moved or "
                        "duplicated into state-specific content; copied "
                        f"retained table ids={sorted(leaked_table_ids)!r}."
                    ),
                ))
        if expected_shared is None:
            if actual_raw is not None:
                actual = clean_html_content(actual_raw)
                code = (
                    "region_projected_shared_content_scope_leakage"
                    if actual in known_wire_values
                    else "unproven_shared_content"
                )
                errors.append(CmsStateIssue(
                    code,
                    path,
                    (
                        "sharedContent is forbidden unless the exact CMS state "
                        "has source/config-bound Region-Projected Shared "
                        "Content evidence."
                    ),
                ))
            continue

        if actual_raw is None:
            errors.append(CmsStateIssue(
                "missing_region_projected_shared_content",
                path,
                (
                    "The exact source/config-bound Region-Projected Shared "
                    f"Content is required for CMS state {state.to_dict()!r}."
                ),
            ))
            continue

        actual = clean_html_content(actual_raw)
        projected = expected_shared.projected_wire_html
        if not is_price_bearing_html(actual):
            errors.append(CmsStateIssue(
                "region_projected_shared_content_not_price_bearing",
                path,
                (
                    "Region-Projected Shared Content must independently "
                    "contain source-proven pricing content."
                ),
            ))
        if actual == projected:
            continue
        if projected and actual.count(projected) > 1:
            code = "duplicate_region_projected_shared_content"
            message = (
                "Region-Projected Shared Content must occur exactly once in "
                f"CMS state {state.to_dict()!r}."
            )
        elif actual in known_wire_values:
            code = "region_projected_shared_content_scope_leakage"
            message = (
                "sharedContent contains another Region state's projection for "
                f"CMS state {state.to_dict()!r}."
            )
        else:
            code = "modified_region_projected_shared_content"
            message = (
                "sharedContent differs from the exact source/config-bound "
                f"projection for CMS state {state.to_dict()!r}."
            )
        errors.append(CmsStateIssue(code, path, message))


def _validate_price_bearing_groups(
    groups: list[_ParsedGroup],
    exceptions: set[CmsState],
    findings: list[CmsStateIssue],
    errors: list[CmsStateIssue],
    *,
    expected: ExpectedCmsReachability | None,
) -> None:
    used_exceptions: set[CmsState] = set()
    for group in groups:
        if group.state is None or group.content is None:
            continue
        if (
            is_price_bearing_html(group.content)
            or _has_exact_price_bearing_shared_content(
                group.state,
                group.shared_content,
                expected,
            )
        ):
            continue
        path = f"$.contentGroups[{group.index}].content"
        if group.state in exceptions:
            used_exceptions.add(group.state)
            findings.append(CmsStateIssue(
                "source_confirmed_empty_state",
                path,
                f"Source evidence confirms that CMS state {group.state.to_dict()!r} has no price-bearing content.",
            ))
        else:
            errors.append(CmsStateIssue(
                "content_group_not_price_bearing",
                path,
                f"CMS state {group.state.to_dict()!r} must contain price-bearing content.",
            ))
    for state in sorted(exceptions - used_exceptions):
        errors.append(CmsStateIssue(
            "unused_source_confirmed_empty_state",
            "$.source_confirmed_empty_states",
            f"Source-confirmed empty state {state.to_dict()!r} did not narrowly exempt one non-price-bearing group.",
        ))


def _validate_ordered_items(
    values: list[Any],
    path: str,
    errors: list[CmsStateIssue],
) -> None:
    orders: list[int] = []
    seen: set[int] = set()
    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            continue
        order = value.get("sortOrder")
        item_path = f"{path}[{index}].sortOrder"
        if type(order) is not int or order <= 0:
            errors.append(CmsStateIssue(
                "invalid_sort_order",
                item_path,
                "sortOrder must be a positive integer.",
            ))
            continue
        if order in seen:
            errors.append(CmsStateIssue(
                "duplicate_sort_order",
                item_path,
                f"sortOrder {order} is duplicated within {path}.",
            ))
        seen.add(order)
        orders.append(order)
    if any(left >= right for left, right in itertools.pairwise(orders)):
        errors.append(CmsStateIssue(
            "sort_order_not_ascending",
            path,
            "Physical array order must be strictly ascending by sortOrder.",
        ))


def _validate_common_sections(
    sections: list[Any],
    errors: list[CmsStateIssue],
) -> None:
    for index, section in enumerate(sections):
        if not isinstance(section, Mapping):
            continue
        path = f"$.commonSections[{index}]"
        if section.get("isActive") is not True:
            errors.append(CmsStateIssue(
                "inactive_common_section",
                f"{path}.isActive",
                "Every generated common section must be active.",
            ))
        content = section.get("content")
        if not isinstance(content, str) or not _visible_text(content):
            errors.append(CmsStateIssue(
                "empty_common_section",
                f"{path}.content",
                "Every generated common section must contain non-empty visible content.",
            ))
        elif (
            _PLACEHOLDER_PATTERN.search(_visible_text(content))
            or _PLACEHOLDER_MARKUP_PATTERN.search(content)
        ):
            errors.append(CmsStateIssue(
                "placeholder_common_section",
                f"{path}.content",
                "Placeholder common-section content is forbidden.",
            ))
        if isinstance(content, str) and _STALE_MARKUP_PATTERN.search(content):
            errors.append(CmsStateIssue(
                "stale_common_section",
                f"{path}.content",
                "Stale marked common-section content is forbidden.",
            ))


def _load_canonical_nested_json(
    raw: Any,
    path: str,
    errors: list[CmsStateIssue],
) -> Any | None:
    if not isinstance(raw, str):
        errors.append(CmsStateIssue(
            "invalid_nested_json",
            path,
            "Nested JSON value must be a string.",
        ))
        return None
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_number,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        errors.append(CmsStateIssue("invalid_nested_json", path, str(error)))
        return None
    if raw != canonical_cms_nested_json(value):
        errors.append(CmsStateIssue(
            "noncanonical_nested_json",
            path,
            "Nested JSON must use deterministic canonical serialization.",
        ))
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _reject_nonfinite_number(value: str) -> None:
    raise ValueError(f"Non-finite JSON number is forbidden: {value}")


def _order_cms_nested_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        if "filterDefinitions" in value:
            field_order = ("filterDefinitions",)
        elif "filterType" in value or "options" in value:
            field_order = ("filterKey", "filterType", "displayName", "options")
        elif "matchValues" in value:
            field_order = ("filterKey", "matchValues")
        elif "value" in value or "label" in value or "href" in value:
            field_order = ("value", "label", "href")
        else:
            field_order = ()
        ordered: dict[str, Any] = {
            key: _order_cms_nested_value(value[key])
            for key in field_order
            if key in value
        }
        for key in sorted(set(value) - set(field_order)):
            ordered[key] = _order_cms_nested_value(value[key])
        return ordered
    if isinstance(value, list):
        return [_order_cms_nested_value(item) for item in value]
    return value


def _validate_empty_state_exceptions(
    values: Collection[CmsState],
    errors: list[CmsStateIssue],
) -> set[CmsState]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Collection):
        errors.append(CmsStateIssue(
            "invalid_source_confirmed_empty_states",
            "$.source_confirmed_empty_states",
            "source_confirmed_empty_states must be a collection of exact CmsState values.",
        ))
        return set()
    result: set[CmsState] = set()
    for value in values:
        if not isinstance(value, CmsState):
            errors.append(CmsStateIssue(
                "invalid_source_confirmed_empty_state",
                "$.source_confirmed_empty_states",
                "Every source-confirmed empty state must be an exact CmsState value.",
            ))
            continue
        if value in result:
            errors.append(CmsStateIssue(
                "duplicate_source_confirmed_empty_state",
                "$.source_confirmed_empty_states",
                f"Duplicate source-confirmed empty state {value.to_dict()!r}.",
            ))
        result.add(value)
    return result


def _is_wildcard_or_multivalue(value: str) -> bool:
    return value.strip() == "*" or bool(_MULTIVALUE_PATTERN.search(value))


def _visible_text(content: str) -> str:
    try:
        return BeautifulSoup(content, "html.parser").get_text(" ", strip=True)
    except (TypeError, ValueError):
        return ""


def _table_ids_in_html(content: str) -> frozenset[str]:
    try:
        soup = BeautifulSoup(content, "html.parser")
    except (TypeError, ValueError):
        return frozenset()
    return frozenset(
        table_id
        for table in soup.find_all("table")
        if (table_id := str(table.get("id", "")).strip())
    )


def _validate_rendered_state_content(
    group_path: str,
    content: Any,
    shared_content: str | None,
    state: CmsState | None,
    expected: ExpectedCmsReachability | None,
    errors: list[CmsStateIssue],
) -> None:
    """Require visible specific content unless exact shared pricing renders it."""

    if isinstance(content, str) and _visible_text(content):
        return
    if _has_exact_price_bearing_shared_content(
        state,
        shared_content,
        expected,
    ):
        return
    errors.append(CmsStateIssue(
        "empty_content_group",
        f"{group_path}.content",
        (
            "A content group with empty category-specific content requires "
            "exact source-proven, same-state, price-bearing sharedContent."
        ),
    ))


def _has_exact_price_bearing_shared_content(
    state: CmsState | None,
    shared_content: str | None,
    expected: ExpectedCmsReachability | None,
) -> bool:
    if (
        state is None
        or not isinstance(shared_content, str)
        or expected is None
    ):
        return False
    expected_by_state = dict(zip(
        expected.ordered_states,
        expected.region_projected_shared_content_by_state,
        strict=True,
    ))
    expected_shared = expected_by_state.get(state)
    return (
        expected_shared is not None
        and clean_html_content(shared_content)
        == expected_shared.projected_wire_html
        and is_price_bearing_html(shared_content)
    )


def _prefix_issues(
    issues: tuple[CmsStateIssue, ...],
    language: str,
) -> tuple[CmsStateIssue, ...]:
    return tuple(
        CmsStateIssue(issue.code, f"$.{language}{issue.path[1:]}", issue.message)
        for issue in issues
    )
