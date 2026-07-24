from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import pytest

from src.core.cms_state_contract import (
    CmsState,
    ExpectedCmsReachability,
    ExpectedFilter,
    canonical_cms_nested_json,
)
from src.core.contract_validator import ContractValidationResult, ContractValidator


ROOT = Path(__file__).resolve().parents[1]
PRICE_CONTENT = "<table><tr><th>Price</th><td>￥1/hour</td></tr></table>"


def _option(value: str, label: str | None = None) -> dict[str, str]:
    return {"value": value, "label": label or value, "href": f"#{value}"}


def _definition(
    key: str,
    values: tuple[str, ...],
    *,
    filter_type: str = "dropdown",
    display_name: str | None = None,
) -> dict[str, Any]:
    return {
        "filterKey": key,
        "filterType": filter_type,
        "displayName": display_name or key.title(),
        "options": [_option(value) for value in values],
    }


def _criteria(state: tuple[tuple[str, str], ...]) -> str:
    return canonical_cms_nested_json([
        {"filterKey": key, "matchValues": value} for key, value in state
    ])


def _group(
    state: tuple[tuple[str, str], ...],
    order: int,
    *,
    content: str = PRICE_CONTENT,
    labels: dict[tuple[str, str], str] | None = None,
) -> dict[str, Any]:
    labels = labels or {}
    return {
        "groupName": " - ".join(
            labels.get((key, value), value) for key, value in state
        ),
        "filterCriteriaJson": _criteria(state),
        "content": content,
        "sortOrder": order,
        "isActive": True,
    }


def _payload(
    page_type: str,
    definitions: list[dict[str, Any]],
    states: list[tuple[tuple[str, str], ...]],
    *,
    language: str = "zh-cn",
) -> dict[str, Any]:
    simple = page_type == "Simple"
    labels = {
        (definition["filterKey"], option["value"]): option["label"]
        for definition in definitions
        for option in definition["options"]
    }
    return {
        "title": "CMS contract fixture",
        "metaTitle": "",
        "metaDescription": "",
        "metaKeywords": "",
        "slug": "cms-contract-fixture",
        "language": language,
        "baseContent": "<p>Static pricing content</p>" if simple else "",
        "contentGroups": [
            _group(state, index + 1, labels=labels)
            for index, state in enumerate(states)
        ],
        "commonSections": [
            {
                "sectionType": "Banner",
                "sectionTitle": "",
                "content": "<p>Banner</p>",
                "sortOrder": 1,
                "isActive": True,
            }
        ],
        "pageConfig": {
            "displayTitle": "CMS contract fixture",
            "pageIcon": "{base_url}/favicon.ico",
            "leftNavigationIdentifier": "cms-contract-fixture",
            "pageType": page_type,
            "enableFilters": not simple,
            "filtersJsonConfig": canonical_cms_nested_json({
                "filterDefinitions": definitions
            }),
        },
    }


def _simple_payload(*, language: str = "zh-cn") -> dict[str, Any]:
    return _payload("Simple", [], [], language=language)


def _region_payload(*, language: str = "zh-cn") -> dict[str, Any]:
    definition = _definition("region", ("east", "north"))
    states = [
        (("region", "east"),),
        (("region", "north"),),
    ]
    return _payload("RegionFilter", [definition], states, language=language)


def _complex_payload(*, language: str = "zh-cn") -> dict[str, Any]:
    definitions = [
        _definition("region", ("east", "north")),
        _definition("tier", ("basic", "premium"), filter_type="tab"),
    ]
    states = [
        (("region", region), ("tier", tier))
        for region in ("east", "north")
        for tier in ("basic", "premium")
    ]
    return _payload("ComplexFilter", definitions, states, language=language)


def _sparse_payload(*, language: str = "zh-cn") -> dict[str, Any]:
    definitions = [
        _definition("region", ("east", "north")),
        _definition("software", ("elastic", "single")),
        _definition(
            "category",
            ("elastic-general", "elastic-premium", "single-general"),
            filter_type="tab",
        ),
    ]
    labels = {
        "east": "East",
        "north": "North",
        "elastic": "Elastic",
        "single": "Single",
        "elastic-general": "General",
        "elastic-premium": "Premium",
        "single-general": "General",
    }
    for definition in definitions:
        for option in definition["options"]:
            option["label"] = labels[option["value"]]
    states = [
        (
            ("region", "east"),
            ("software", "elastic"),
            ("category", "elastic-general"),
        ),
        (
            ("region", "east"),
            ("software", "elastic"),
            ("category", "elastic-premium"),
        ),
        (
            ("region", "east"),
            ("software", "single"),
            ("category", "single-general"),
        ),
        (("region", "north"),),
    ]
    return _payload("ComplexFilter", definitions, states, language=language)


def _expected_filter(
    key: str,
    values: tuple[str, ...],
    *,
    filter_type: str = "dropdown",
    display_name: str | None = None,
    labels: tuple[str, ...] | None = None,
    hrefs: tuple[str, ...] | None = None,
) -> ExpectedFilter:
    return ExpectedFilter(
        key=key,
        filter_type=filter_type,
        display_name=display_name or key.title(),
        option_values=values,
        option_labels=labels or values,
        option_hrefs=hrefs or tuple(f"#{value}" for value in values),
    )


def _expectation(
    filters: tuple[ExpectedFilter, ...],
    states: tuple[tuple[tuple[str, str], ...], ...],
) -> ExpectedCmsReachability:
    relation = tuple(CmsState(state) for state in states)
    return ExpectedCmsReachability(
        filters=filters,
        ordered_states=relation,
        default_state=relation[0] if relation else CmsState(()),
        software_scoped_prefixes_by_state=tuple(None for _ in relation),
    )


def _simple_expectation() -> ExpectedCmsReachability:
    return _expectation((), ())


def _region_expectation() -> ExpectedCmsReachability:
    return _expectation(
        (_expected_filter("region", ("east", "north")),),
        (
            (("region", "east"),),
            (("region", "north"),),
        ),
    )


def _complex_expectation() -> ExpectedCmsReachability:
    return _expectation(
        (
            _expected_filter("region", ("east", "north")),
            _expected_filter(
                "tier",
                ("basic", "premium"),
                filter_type="tab",
            ),
        ),
        tuple(
            (("region", region), ("tier", tier))
            for region in ("east", "north")
            for tier in ("basic", "premium")
        ),
    )


def _sparse_expectation() -> ExpectedCmsReachability:
    return _expectation(
        (
            _expected_filter(
                "region",
                ("east", "north"),
                labels=("East", "North"),
            ),
            _expected_filter(
                "software",
                ("elastic", "single"),
                labels=("Elastic", "Single"),
            ),
            _expected_filter(
                "category",
                ("elastic-general", "elastic-premium", "single-general"),
                filter_type="tab",
                labels=("General", "Premium", "General"),
            ),
        ),
        (
            (
                ("region", "east"),
                ("software", "elastic"),
                ("category", "elastic-general"),
            ),
            (
                ("region", "east"),
                ("software", "elastic"),
                ("category", "elastic-premium"),
            ),
            (
                ("region", "east"),
                ("software", "single"),
                ("category", "single-general"),
            ),
            (("region", "north"),),
        ),
    )


def _default_expectation(payload: Any) -> ExpectedCmsReachability:
    if isinstance(payload, dict):
        page_config = payload.get("pageConfig")
        if isinstance(page_config, dict):
            page_type = page_config.get("pageType")
            if page_type == "Simple":
                return _simple_expectation()
            if page_type == "ComplexFilter":
                return _complex_expectation()
    return _region_expectation()


_USE_DEFAULT_EXPECTATION = object()


def _validate(
    validator: ContractValidator,
    payload: Any,
    expected_ms_service: str | None = None,
    *,
    expected_semantic_strategy: str | None = None,
    expected_reachability: ExpectedCmsReachability
    | None
    | object = _USE_DEFAULT_EXPECTATION,
    expected_base_content: str | None = None,
    source_confirmed_empty_states: set[CmsState] | tuple[CmsState, ...] = (),
) -> ContractValidationResult:
    if expected_reachability is _USE_DEFAULT_EXPECTATION:
        expected_reachability = _default_expectation(payload)
    return validator.validate(
        payload,
        "FlexibleContentPage",
        expected_ms_service,
        expected_semantic_strategy=expected_semantic_strategy,
        expected_reachability=expected_reachability,
        expected_base_content=expected_base_content,
        source_confirmed_empty_states=source_confirmed_empty_states,
    )


def _validate_pair(
    validator: ContractValidator,
    zh: Any,
    en: Any,
    *,
    zh_expected: ExpectedCmsReachability | None = None,
    en_expected: ExpectedCmsReachability | None = None,
    expected_semantic_strategy: str | None = None,
    zh_empty_states: set[CmsState] | tuple[CmsState, ...] = (),
    en_empty_states: set[CmsState] | tuple[CmsState, ...] = (),
) -> ContractValidationResult:
    return validator.validate_bilingual_pair(
        zh,
        en,
        zh_cn_expected_reachability=zh_expected or _default_expectation(zh),
        en_us_expected_reachability=en_expected or _default_expectation(en),
        expected_semantic_strategy=expected_semantic_strategy,
        zh_cn_source_confirmed_empty_states=zh_empty_states,
        en_us_source_confirmed_empty_states=en_empty_states,
    )


def _set_filter_config(payload: dict[str, Any], config: Any) -> None:
    payload["pageConfig"]["filtersJsonConfig"] = canonical_cms_nested_json(config)


def _refresh_group_names(payload: dict[str, Any]) -> None:
    config = json.loads(payload["pageConfig"]["filtersJsonConfig"])
    labels = {
        (definition["filterKey"], option["value"]): option["label"]
        for definition in config["filterDefinitions"]
        for option in definition["options"]
    }
    for group in payload["contentGroups"]:
        state = json.loads(group["filterCriteriaJson"])
        group["groupName"] = " - ".join(
            labels[(criterion["filterKey"], criterion["matchValues"])]
            for criterion in state
        )


def _codes(result: ContractValidationResult) -> set[str]:
    return {issue.code for issue in result.errors}


@pytest.fixture
def validator() -> ContractValidator:
    return ContractValidator(ROOT)


@pytest.mark.parametrize(
    ("factory", "strategy"),
    [
        (_simple_payload, "simple_static"),
        (_region_payload, "region_filter"),
        (_complex_payload, "complex"),
    ],
)
def test_valid_page_state_machines(
    validator: ContractValidator,
    factory: Callable[[], dict[str, Any]],
    strategy: str,
) -> None:
    result = _validate(
        validator,
        factory(),
        "cms-contract-fixture",
        expected_semantic_strategy=strategy,
    )
    assert result.passed, result.to_dict(include_source_findings=True)


def test_result_projection_is_backward_compatible() -> None:
    result = ContractValidationResult([], [])
    assert result.to_dict() == {"errors": [], "warnings": []}
    assert result.source_findings == []
    assert result.to_dict(include_source_findings=True) == {
        "errors": [],
        "warnings": [],
        "source_findings": [],
    }


def test_flexible_contract_fails_closed_without_source_reachability(
    validator: ContractValidator,
) -> None:
    result = validator.validate(_region_payload(), "FlexibleContentPage")
    assert "missing_expected_reachability" in _codes(result)


def test_bilingual_contract_fails_closed_without_both_source_expectations(
    validator: ContractValidator,
) -> None:
    result = validator.validate_bilingual_pair(
        _region_payload(language="zh-cn"),
        _region_payload(language="en-us"),
    )

    assert not result.passed
    missing_paths = {
        issue.path
        for issue in result.errors
        if issue.code == "missing_expected_reachability"
    }
    assert missing_paths == {
        "$.zh-cn.expected_reachability",
        "$.en-us.expected_reachability",
    }


def test_payload_cannot_self_authorize_a_shrunken_relation(
    validator: ContractValidator,
) -> None:
    payload = _region_payload()
    config = {
        "filterDefinitions": [_definition("region", ("east",))]
    }
    _set_filter_config(payload, config)
    payload["contentGroups"].pop()

    result = _validate(
        validator,
        payload,
        expected_reachability=_region_expectation(),
    )
    assert {
        "missing_reachable_filter_option",
        "missing_cms_state",
        "reachable_state_order_mismatch",
    } <= _codes(result)


def test_sparse_source_relation_is_authoritative_not_cartesian(
    validator: ContractValidator,
) -> None:
    payload = _sparse_payload()
    expected = _sparse_expectation()
    valid = _validate(
        validator,
        payload,
        expected_reachability=expected,
    )
    assert valid.passed, valid.to_dict(include_source_findings=True)
    assert json.loads(payload["contentGroups"][-1]["filterCriteriaJson"]) == [
        {"filterKey": "region", "matchValues": "north"}
    ]

    impossible = deepcopy(payload)
    impossible["contentGroups"].append(
        _group(
            (
                ("region", "east"),
                ("software", "single"),
                ("category", "elastic-premium"),
            ),
            5,
            labels={
                ("region", "east"): "East",
                ("software", "single"): "Single",
                ("category", "elastic-premium"): "Premium",
            },
        )
    )
    result = _validate(
        validator,
        impossible,
        expected_reachability=expected,
    )
    assert "unexpected_unreachable_state" in _codes(result)


def test_non_materialized_aggregate_option_and_group_are_rejected(
    validator: ContractValidator,
) -> None:
    payload = _complex_payload()
    config = json.loads(payload["pageConfig"]["filtersJsonConfig"])
    config["filterDefinitions"][1]["options"].append(_option("all", "All"))
    _set_filter_config(payload, config)
    payload["contentGroups"].append(
        _group(
            (("region", "east"), ("tier", "all")),
            5,
            labels={
                ("region", "east"): "east",
                ("tier", "all"): "All",
            },
        )
    )

    result = _validate(
        validator,
        payload,
        expected_reachability=_complex_expectation(),
    )

    assert {
        "unreachable_filter_option",
        "unexpected_unreachable_state",
    } <= _codes(result)


def test_expected_option_union_must_equal_sparse_relation_union(
    validator: ContractValidator,
) -> None:
    invalid_expected = _expectation(
        (
            _expected_filter("region", ("north", "east")),
        ),
        (
            (("region", "east"),),
            (("region", "north"),),
        ),
    )
    result = _validate(
        validator,
        _region_payload(),
        expected_reachability=invalid_expected,
    )
    assert "expected_option_union_mismatch" in _codes(result)


def test_filter_option_order_and_hrefs_are_source_authoritative(
    validator: ContractValidator,
) -> None:
    payload = _region_payload()
    config = {
        "filterDefinitions": [_definition("region", ("east", "north"))]
    }
    config["filterDefinitions"][0]["options"][0]["href"] = "/pricing/east"
    config["filterDefinitions"][0]["options"][1]["href"] = "/pricing/north"
    _set_filter_config(payload, config)
    expected = _expectation(
        (
            _expected_filter(
                "region",
                ("east", "north"),
                hrefs=("/pricing/east", "/pricing/north"),
            ),
        ),
        (
            (("region", "east"),),
            (("region", "north"),),
        ),
    )
    assert _validate(
        validator,
        payload,
        expected_reachability=expected,
    ).passed

    wrong_href = deepcopy(payload)
    wrong_config = deepcopy(config)
    wrong_config["filterDefinitions"][0]["options"][1]["href"] = "/wrong"
    _set_filter_config(wrong_href, wrong_config)
    assert "filter_option_href_mismatch" in _codes(_validate(
        validator,
        wrong_href,
        expected_reachability=expected,
    ))

    wrong_order = deepcopy(payload)
    wrong_config = {
        "filterDefinitions": [_definition("region", ("north", "east"))]
    }
    wrong_config["filterDefinitions"][0]["options"][0]["href"] = "/pricing/north"
    wrong_config["filterDefinitions"][0]["options"][1]["href"] = "/pricing/east"
    _set_filter_config(wrong_order, wrong_config)
    assert "filter_option_order_mismatch" in _codes(_validate(
        validator,
        wrong_order,
        expected_reachability=expected,
    ))


def test_localized_filter_labels_and_display_name_are_source_authoritative(
    validator: ContractValidator,
) -> None:
    payload = _region_payload()
    config = json.loads(payload["pageConfig"]["filtersJsonConfig"])
    definition = config["filterDefinitions"][0]
    definition["displayName"] = "Fabricated Region"
    definition["options"][0]["label"] = "Fabricated East"
    _set_filter_config(payload, config)
    _refresh_group_names(payload)

    result = _validate(
        validator,
        payload,
        expected_reachability=_region_expectation(),
    )

    assert {
        "filter_display_name_mismatch",
        "filter_option_label_mismatch",
        "group_name_state_label_mismatch",
    } <= _codes(result)


def test_tab_option_href_is_fixed_to_fragment_identity() -> None:
    with pytest.raises(ValueError, match="tab hrefs"):
        ExpectedFilter(
            key="tier",
            filter_type="tab",
            display_name="Tier",
            option_values=("basic",),
            option_labels=("Basic",),
            option_hrefs=("/basic",),
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update({"pageConfig": []}),
        lambda payload: payload.update({"contentGroups": "not-an-array"}),
        lambda payload: payload["contentGroups"].__setitem__(0, "not-an-object"),
        lambda payload: payload["contentGroups"][0].update(
            {"filterCriteriaJson": canonical_cms_nested_json({"filterKey": "region"})}
        ),
        lambda payload: payload["contentGroups"][0].update(
            {"filterCriteriaJson": 7}
        ),
        lambda payload: payload["pageConfig"].update(
            {"filtersJsonConfig": canonical_cms_nested_json([])}
        ),
    ],
)
def test_malformed_flexible_payloads_return_issues_without_raising(
    validator: ContractValidator,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    payload = _region_payload()
    mutate(payload)
    result = _validate(validator, payload)
    assert not result.passed
    assert result.errors


@pytest.mark.parametrize("payload", [None, [], "payload", 7])
def test_non_object_payloads_return_issues(
    validator: ContractValidator,
    payload: Any,
) -> None:
    result = _validate(validator, payload)
    assert not result.passed
    assert "invalid_flexible_payload" in _codes(result)


def test_support_optional_wrong_type_does_not_crash(
    validator: ContractValidator,
) -> None:
    payload = {
        "title": "Title",
        "slug": "title",
        "metaTitle": 7,
        "metaDescription": "",
        "metaKeywords": "",
        "pageType": "ICP",
        "lastModifiedDate": "",
        "articleDescription": "",
        "mainContent": "<p>Body</p>",
    }
    result = validator.validate(payload, "SupportArticlePage")
    assert not result.passed
    assert "schema_validation" in _codes(result)


def test_reachability_is_not_applicable_to_support_article(
    validator: ContractValidator,
) -> None:
    payload = {
        "title": "Title",
        "slug": "title",
        "metaTitle": "",
        "metaDescription": "",
        "metaKeywords": "",
        "pageType": "ICP",
        "lastModifiedDate": "",
        "articleDescription": "",
        "mainContent": "<p>Body</p>",
    }
    result = validator.validate(
        payload,
        "SupportArticlePage",
        expected_reachability=_simple_expectation(),
    )
    assert "reachability_not_applicable" in _codes(result)


def test_nested_json_requires_contract_field_order_and_compact_encoding(
    validator: ContractValidator,
) -> None:
    payload = _region_payload()
    payload["pageConfig"]["filtersJsonConfig"] = (
        '{"filterDefinitions": [{"displayName": "Region", '
        '"filterKey": "region", "filterType": "dropdown", '
        '"options": [{"label": "east", "value": "east", "href": "#east"}, '
        '{"label": "north", "value": "north", "href": "#north"}]}]}'
    )
    payload["contentGroups"][0]["filterCriteriaJson"] = (
        '[{"matchValues":"east","filterKey":"region"}]'
    )
    result = _validate(validator, payload)
    assert "noncanonical_nested_json" in _codes(result)


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("empty_key", "empty_filter_key"),
        ("duplicate_key", "duplicate_filter_key"),
        ("empty_domain", "empty_filter_domain"),
        ("duplicate_value", "duplicate_filter_option_value"),
        ("duplicate_label", "duplicate_filter_option_label_in_scope"),
        ("blank_value", "empty_filter_option_value"),
        ("blank_label", "empty_filter_option_label"),
        ("blank_display", "empty_filter_display_name"),
        ("wildcard_value", "invalid_filter_option_value_encoding"),
    ],
)
def test_filter_domain_contracts(
    validator: ContractValidator,
    mutation: str,
    expected_code: str,
) -> None:
    payload = _complex_payload()
    config = {
        "filterDefinitions": [
            _definition("region", ("east", "north")),
            _definition("tier", ("basic", "premium"), filter_type="tab"),
        ]
    }
    definitions = config["filterDefinitions"]
    if mutation == "empty_key":
        definitions[0]["filterKey"] = " "
    elif mutation == "duplicate_key":
        definitions[1]["filterKey"] = "region"
    elif mutation == "empty_domain":
        definitions[0]["options"] = []
    elif mutation == "duplicate_value":
        definitions[0]["options"][1]["value"] = "east"
    elif mutation == "duplicate_label":
        definitions[0]["options"][1]["label"] = "east"
    elif mutation == "blank_value":
        definitions[0]["options"][0]["value"] = " "
    elif mutation == "blank_label":
        definitions[0]["options"][0]["label"] = " "
    elif mutation == "blank_display":
        definitions[0]["displayName"] = " "
    elif mutation == "wildcard_value":
        definitions[0]["options"][0]["value"] = "*"
    _set_filter_config(payload, config)

    result = _validate(validator, payload)
    assert expected_code in _codes(result)


def test_duplicate_labels_are_scoped_by_reachable_source_path(
    validator: ContractValidator,
) -> None:
    payload = _sparse_payload()
    expected = _sparse_expectation()
    across_mutually_exclusive_scopes = _validate(
        validator,
        payload,
        expected_reachability=expected,
    )
    assert across_mutually_exclusive_scopes.passed

    same_scope = deepcopy(payload)
    config = json.loads(same_scope["pageConfig"]["filtersJsonConfig"])
    category = config["filterDefinitions"][2]
    category["options"][1]["label"] = "General"
    _set_filter_config(same_scope, config)
    _refresh_group_names(same_scope)
    result = _validate(
        validator,
        same_scope,
        expected_reachability=expected,
    )
    assert "duplicate_filter_option_label_in_scope" in _codes(result)


@pytest.mark.parametrize(
    ("group_name", "expected_code"),
    [
        ("east/basic", "group_name_segment_count_mismatch"),
        ("basic - east", "group_name_state_label_mismatch"),
        ("east - basic - extra", "group_name_segment_count_mismatch"),
    ],
)
def test_group_name_exactly_encodes_localized_criteria_labels(
    validator: ContractValidator,
    group_name: str,
    expected_code: str,
) -> None:
    payload = _complex_payload()
    payload["contentGroups"][0]["groupName"] = group_name
    result = _validate(validator, payload)
    assert expected_code in _codes(result)


def test_filter_label_cannot_contain_group_name_delimiter(
    validator: ContractValidator,
) -> None:
    payload = _region_payload()
    config = json.loads(payload["pageConfig"]["filtersJsonConfig"])
    config["filterDefinitions"][0]["options"][0]["label"] = "East - China"
    _set_filter_config(payload, config)
    _refresh_group_names(payload)
    result = _validate(validator, payload)
    assert "filter_option_label_contains_group_delimiter" in _codes(result)


@pytest.mark.parametrize(
    ("criteria", "expected_code"),
    [
        (
            [{"filterKey": "region", "matchValues": "east"}],
            "unexpected_unreachable_state",
        ),
        (
            [
                {"filterKey": "tier", "matchValues": "basic"},
                {"filterKey": "region", "matchValues": "east"},
            ],
            "incomplete_or_misordered_filter_criteria",
        ),
        (
            [
                {"filterKey": "region", "matchValues": "east"},
                {"filterKey": "region", "matchValues": "east"},
            ],
            "incomplete_or_misordered_filter_criteria",
        ),
        (
            [
                {"filterKey": "region", "matchValues": "*"},
                {"filterKey": "tier", "matchValues": "basic"},
            ],
            "invalid_match_value_encoding",
        ),
        (
            [
                {"filterKey": "region", "matchValues": "east,north"},
                {"filterKey": "tier", "matchValues": "basic"},
            ],
            "invalid_match_value_encoding",
        ),
        (
            [
                {"filterKey": "region", "matchValues": ["east"]},
                {"filterKey": "tier", "matchValues": "basic"},
            ],
            "match_values_not_string",
        ),
    ],
)
def test_group_criteria_must_be_reachable_single_value_and_ordered(
    validator: ContractValidator,
    criteria: list[dict[str, Any]],
    expected_code: str,
) -> None:
    payload = _complex_payload()
    payload["contentGroups"][0]["filterCriteriaJson"] = canonical_cms_nested_json(criteria)
    result = _validate(validator, payload)
    assert expected_code in _codes(result)


def test_source_proven_reachable_relation_is_exact_and_ordered(
    validator: ContractValidator,
) -> None:
    missing = _complex_payload()
    missing["contentGroups"].pop()
    missing_result = _validate(validator, missing)
    assert "missing_cms_state" in _codes(missing_result)
    assert "reachable_state_order_mismatch" in _codes(missing_result)

    duplicate = _complex_payload()
    duplicate["contentGroups"][-1]["filterCriteriaJson"] = duplicate["contentGroups"][0]["filterCriteriaJson"]
    duplicate_result = _validate(validator, duplicate)
    assert "duplicate_cms_state" in _codes(duplicate_result)
    assert "missing_cms_state" in _codes(duplicate_result)

    reordered = _complex_payload()
    reordered["contentGroups"][0], reordered["contentGroups"][1] = (
        reordered["contentGroups"][1],
        reordered["contentGroups"][0],
    )
    reordered_result = _validate(validator, reordered)
    assert "reachable_state_order_mismatch" in _codes(reordered_result)


def test_source_default_controls_first_group_and_first_filter_option(
    validator: ContractValidator,
) -> None:
    groups_reordered = _region_payload()
    groups_reordered["contentGroups"].reverse()
    result = _validate(validator, groups_reordered)
    assert {
        "default_state_mismatch",
        "reachable_state_order_mismatch",
    } <= _codes(result)

    options_reordered = _region_payload()
    config = {
        "filterDefinitions": [_definition("region", ("north", "east"))]
    }
    _set_filter_config(options_reordered, config)
    result = _validate(validator, options_reordered)
    assert {
        "filter_option_order_mismatch",
        "default_filter_option_mismatch",
    } <= _codes(result)


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("inactive", "inactive_content_group"),
        ("empty", "empty_content_group"),
        ("placeholder", "placeholder_content_group"),
        ("placeholder_markup", "placeholder_content_group"),
        ("shared", "unproven_shared_content"),
        ("extra_group_field", "invalid_content_group_fields"),
        ("stale_field", "stale_group_field"),
        ("stale_markup", "stale_content_group"),
        ("zero_order", "invalid_sort_order"),
        ("duplicate_order", "duplicate_sort_order"),
        ("inactive_section", "inactive_common_section"),
        ("empty_section", "empty_common_section"),
    ],
)
def test_generated_payload_rejects_inactive_empty_placeholder_stale_and_bad_order(
    validator: ContractValidator,
    mutation: str,
    expected_code: str,
) -> None:
    payload = _region_payload()
    if mutation == "inactive":
        payload["contentGroups"][0]["isActive"] = False
    elif mutation == "empty":
        payload["contentGroups"][0]["content"] = "<!-- empty -->"
    elif mutation == "placeholder":
        payload["contentGroups"][0]["content"] = "<p>未找到tab内容 (ID: x)</p>"
    elif mutation == "placeholder_markup":
        payload["contentGroups"][0]["content"] = (
            '<div class="tab-content-missing">Unavailable</div>'
        )
    elif mutation == "shared":
        payload["contentGroups"][0]["sharedContent"] = "legacy"
    elif mutation == "extra_group_field":
        payload["contentGroups"][0]["extension"] = "not-confirmed"
    elif mutation == "stale_field":
        payload["contentGroups"][0]["isStale"] = True
    elif mutation == "stale_markup":
        payload["contentGroups"][0]["content"] = '<table data-stale="true"><td>￥1</td></table>'
    elif mutation == "zero_order":
        payload["contentGroups"][0]["sortOrder"] = 0
    elif mutation == "duplicate_order":
        payload["contentGroups"][1]["sortOrder"] = 1
    elif mutation == "inactive_section":
        payload["commonSections"][0]["isActive"] = False
    elif mutation == "empty_section":
        payload["commonSections"][0]["content"] = ""
    result = _validate(validator, payload)
    assert expected_code in _codes(result)


@pytest.mark.parametrize(
    ("factory", "mutation", "expected_code"),
    [
        (_simple_payload, "enable", "simple_filters_enabled"),
        (_simple_payload, "groups", "simple_content_groups_present"),
        (_simple_payload, "base", "simple_base_content_empty"),
        (_region_payload, "disable", "region_filter_disabled"),
        (_region_payload, "software", "invalid_region_filter_topology"),
        (_complex_payload, "single_region", "invalid_complex_filter_topology"),
    ],
)
def test_strict_flexible_page_state_machine(
    validator: ContractValidator,
    factory: Callable[[], dict[str, Any]],
    mutation: str,
    expected_code: str,
) -> None:
    payload = factory()
    if mutation == "enable":
        payload["pageConfig"]["enableFilters"] = True
    elif mutation == "groups":
        payload["contentGroups"] = [_group((), 1)]
    elif mutation == "base":
        payload["baseContent"] = ""
    elif mutation == "disable":
        payload["pageConfig"]["enableFilters"] = False
    elif mutation == "software":
        config = {
            "filterDefinitions": [
                _definition("region", ("east", "north")),
                _definition("software", ("one",)),
            ]
        }
        _set_filter_config(payload, config)
    elif mutation == "single_region":
        config = {"filterDefinitions": [_definition("region", ("east", "north"))]}
        _set_filter_config(payload, config)
        payload["contentGroups"] = [
            _group((("region", "east"),), 1),
            _group((("region", "north"),), 2),
        ]
    result = _validate(validator, payload)
    assert expected_code in _codes(result)


def test_simple_base_content_rejects_placeholder_and_stale_markup(
    validator: ContractValidator,
) -> None:
    placeholder = _simple_payload()
    placeholder["baseContent"] = "<p>TODO</p>"
    assert "placeholder_base_content" in _codes(_validate(
        validator,
        placeholder,
    ))

    stale = _simple_payload()
    stale["baseContent"] = '<div data-stale="true">Static pricing</div>'
    assert "stale_base_content" in _codes(_validate(validator, stale))


def test_filtered_base_content_rejects_placeholder_and_stale_markup(
    validator: ContractValidator,
) -> None:
    placeholder = _complex_payload()
    placeholder["baseContent"] = "<p>TODO</p>"
    assert "placeholder_base_content" in _codes(_validate(
        validator,
        placeholder,
    ))

    stale = _complex_payload()
    stale["baseContent"] = '<div data-stale="true">Global pricing</div>'
    assert "stale_base_content" in _codes(_validate(validator, stale))


def test_expected_page_global_base_content_is_exact_and_not_duplicated(
    validator: ContractValidator,
) -> None:
    expected = (
        '<div class="pricing-page-section">'
        "<h2>Global pricing</h2><p>Applies to every state.</p>"
        "</div>"
    )
    payload = _complex_payload()
    payload["baseContent"] = expected
    assert _validate(
        validator,
        payload,
        expected_base_content=expected,
    ).passed

    missing = deepcopy(payload)
    missing["baseContent"] = ""
    assert "page_global_base_content_mismatch" in _codes(_validate(
        validator,
        missing,
        expected_base_content=expected,
    ))

    duplicated = deepcopy(payload)
    duplicated["contentGroups"][0]["content"] = (
        expected + duplicated["contentGroups"][0]["content"]
    )
    assert "page_global_base_content_duplicated" in _codes(_validate(
        validator,
        duplicated,
        expected_base_content=expected,
    ))


@pytest.mark.parametrize(
    ("section_type", "fragment", "index"),
    [
        (
            "Banner",
            '<div class="common-banner"><h1>Pricing banner</h1></div>',
            0,
        ),
        (
            "ProductDescription",
            "<section><p>Product description for every visitor.</p></section>",
            1,
        ),
        (
            "Qa",
            '<div class="more-detail"><h2>Questions and answers</h2></div>',
            2,
        ),
    ],
)
def test_page_global_base_content_rejects_complete_common_section_fragments(
    validator: ContractValidator,
    section_type: str,
    fragment: str,
    index: int,
) -> None:
    payload = _complex_payload()
    section_fragments = [
        '<div class="common-banner"><h1>Pricing banner</h1></div>',
        "<section><p>Product description for every visitor.</p></section>",
        '<div class="more-detail"><h2>Questions and answers</h2></div>',
    ]
    payload["commonSections"] = [
        {
            "sectionType": current_type,
            "sectionTitle": "",
            "content": current_fragment,
            "sortOrder": current_index + 1,
            "isActive": True,
        }
        for current_index, (current_type, current_fragment) in enumerate(zip(
            ("Banner", "ProductDescription", "Qa"),
            section_fragments,
            strict=True,
        ))
    ]
    expected = f'<main class="incorrect-page-global">{fragment}</main>'
    payload["baseContent"] = expected

    result = _validate(
        validator,
        payload,
        expected_base_content=expected,
    )
    assert (
        "page_global_base_content_duplicated",
        f"$.commonSections[{index}].content",
    ) in {(issue.code, issue.path) for issue in result.errors}


@pytest.mark.parametrize("field", ["content", "sharedContent"])
def test_page_global_base_content_rejects_complete_state_scoped_fragments(
    validator: ContractValidator,
    field: str,
) -> None:
    payload = _complex_payload()
    fragment = (
        PRICE_CONTENT
        if field == "content"
        else '<div class="shared-price-note">Shared state price note.</div>'
    )
    payload["contentGroups"][0][field] = fragment
    expected = f'<main class="incorrect-page-global">{fragment}</main>'
    payload["baseContent"] = expected

    result = _validate(
        validator,
        payload,
        expected_base_content=expected,
    )
    assert (
        "page_global_base_content_duplicated",
        f"$.contentGroups[0].{field}",
    ) in {(issue.code, issue.path) for issue in result.errors}


def test_page_global_overlap_does_not_infer_from_short_plain_text(
    validator: ContractValidator,
) -> None:
    payload = _complex_payload()
    payload["commonSections"][0]["content"] = "All"
    expected = "<p>All products receive the independently scoped notice.</p>"
    payload["baseContent"] = expected

    result = _validate(
        validator,
        payload,
        expected_base_content=expected,
    )
    assert "page_global_base_content_duplicated" not in _codes(result)


@pytest.mark.parametrize("owner", ["common", "group"])
def test_short_plain_base_content_inside_longer_scoped_text_is_not_overlap(
    validator: ContractValidator,
    owner: str,
) -> None:
    payload = _complex_payload()
    expected = "All"
    payload["baseContent"] = expected
    if owner == "common":
        payload["commonSections"][0]["content"] = (
            "All visitors receive this independently scoped banner."
        )
    else:
        payload["contentGroups"][0]["content"] = (
            PRICE_CONTENT
            + "<p>All states retain this state-scoped pricing table.</p>"
        )

    result = _validate(
        validator,
        payload,
        expected_base_content=expected,
    )
    assert "page_global_base_content_duplicated" not in _codes(result)


@pytest.mark.parametrize(
    ("expected", "common_content"),
    [
        ("All", "All"),
        (
            "This substantial plain-text page-global fragment is duplicated.",
            (
                "Prefix: This substantial plain-text page-global fragment "
                "is duplicated. Suffix."
            ),
        ),
    ],
)
def test_equal_or_material_plain_text_overlap_remains_blocking(
    validator: ContractValidator,
    expected: str,
    common_content: str,
) -> None:
    payload = _complex_payload()
    payload["baseContent"] = expected
    payload["commonSections"][0]["content"] = common_content

    result = _validate(
        validator,
        payload,
        expected_base_content=expected,
    )
    assert (
        "page_global_base_content_duplicated",
        "$.commonSections[0].content",
    ) in {(issue.code, issue.path) for issue in result.errors}


def test_common_section_rejects_placeholder_markup(
    validator: ContractValidator,
) -> None:
    payload = _region_payload()
    payload["commonSections"][0]["content"] = (
        '<div class="placeholder">Loading</div>'
    )
    assert "placeholder_common_section" in _codes(_validate(
        validator,
        payload,
    ))


def test_expected_strategy_must_match_page_state_machine(
    validator: ContractValidator,
) -> None:
    result = _validate(
        validator,
        _region_payload(),
        expected_semantic_strategy="complex",
    )
    assert "semantic_strategy_page_type_mismatch" in _codes(result)


def test_exact_source_confirmed_empty_state_is_a_narrow_non_error_finding(
    validator: ContractValidator,
) -> None:
    payload = _region_payload()
    payload["contentGroups"][0]["content"] = "<p>Not offered in this region.</p>"
    state = CmsState((("region", "east"),))

    without_evidence = _validate(validator, payload)
    assert "content_group_not_price_bearing" in _codes(without_evidence)

    with_evidence = _validate(
        validator,
        payload,
        source_confirmed_empty_states={state},
    )
    assert with_evidence.passed, with_evidence.to_dict(include_source_findings=True)
    assert [finding.code for finding in with_evidence.source_findings] == [
        "source_confirmed_empty_state"
    ]
    assert "source_findings" not in with_evidence.to_dict()
    assert with_evidence.to_dict(include_source_findings=True)["source_findings"]


def test_empty_state_exception_cannot_mask_other_group_failures(
    validator: ContractValidator,
) -> None:
    payload = _region_payload()
    payload["contentGroups"][0]["content"] = "<p>placeholder</p>"
    payload["contentGroups"][0]["isActive"] = False
    state = CmsState((("region", "east"),))
    result = _validate(
        validator,
        payload,
        source_confirmed_empty_states={state},
    )
    assert {"inactive_content_group", "placeholder_content_group"} <= _codes(result)


def test_unused_or_out_of_domain_empty_state_evidence_fails_closed(
    validator: ContractValidator,
) -> None:
    payload = _region_payload()
    unused = _validate(
        validator,
        payload,
        source_confirmed_empty_states={CmsState((("region", "east"),))},
    )
    assert "unused_source_confirmed_empty_state" in _codes(unused)

    outside = _validate(
        validator,
        payload,
        source_confirmed_empty_states={CmsState((("region", "west"),))},
    )
    assert "invalid_source_confirmed_empty_state" in _codes(outside)


def test_bilingual_labels_may_localize_but_machine_identity_must_match(
    validator: ContractValidator,
) -> None:
    zh = _complex_payload(language="zh-cn")
    en = _complex_payload(language="en-us")
    en_config = {
        "filterDefinitions": [
            _definition(
                "region",
                ("east", "north"),
                display_name="English Region",
            ),
            _definition(
                "tier",
                ("basic", "premium"),
                filter_type="tab",
                display_name="English Tier",
            ),
        ]
    }
    for definition in en_config["filterDefinitions"]:
        for option in definition["options"]:
            option["label"] = f"English {option['value']}"
    _set_filter_config(en, en_config)
    _refresh_group_names(en)
    en_expected = _expectation(
        (
            _expected_filter(
                "region",
                ("east", "north"),
                display_name="English Region",
                labels=("English east", "English north"),
            ),
            _expected_filter(
                "tier",
                ("basic", "premium"),
                filter_type="tab",
                display_name="English Tier",
                labels=("English basic", "English premium"),
            ),
        ),
        tuple(
            (("region", region), ("tier", tier))
            for region in ("east", "north")
            for tier in ("basic", "premium")
        ),
    )
    assert _validate_pair(
        validator,
        zh,
        en,
        en_expected=en_expected,
    ).passed


def test_bilingual_language_specific_hrefs_validate_independently(
    validator: ContractValidator,
) -> None:
    zh = _region_payload(language="zh-cn")
    en = _region_payload(language="en-us")
    en_config = json.loads(en["pageConfig"]["filtersJsonConfig"])
    en_config["filterDefinitions"][0]["options"][0]["href"] = "/en/east"
    en_config["filterDefinitions"][0]["options"][1]["href"] = "/en/north"
    _set_filter_config(en, en_config)
    en_expected = _expectation(
        (
            _expected_filter(
                "region",
                ("east", "north"),
                hrefs=("/en/east", "/en/north"),
            ),
        ),
        (
            (("region", "east"),),
            (("region", "north"),),
        ),
    )

    result = _validate_pair(
        validator,
        zh,
        en,
        en_expected=en_expected,
    )

    assert result.passed, result.to_dict(include_source_findings=True)
    assert "bilingual_option_hrefs_mismatch" not in _codes(result)


def test_bilingual_machine_value_default_and_state_order_drift_fail(
    validator: ContractValidator,
) -> None:
    zh = _complex_payload(language="zh-cn")
    en = _complex_payload(language="en-us")
    config = {
        "filterDefinitions": [
            _definition("region", ("north", "east")),
            _definition("tier", ("basic", "premium"), filter_type="tab"),
        ]
    }
    _set_filter_config(en, config)
    en["contentGroups"] = [
        _group((("region", region), ("tier", tier)), index + 1)
        for index, (region, tier) in enumerate(
            (product for product in (("north", "basic"), ("north", "premium"), ("east", "basic"), ("east", "premium")))
        )
    ]
    result = _validate_pair(validator, zh, en)
    assert {
        "bilingual_option_values_mismatch",
        "bilingual_default_state_mismatch",
        "bilingual_reachability_relation_mismatch",
    } <= _codes(result)


def test_source_proven_bilingual_reachability_drift_is_a_finding(
    validator: ContractValidator,
) -> None:
    zh = _region_payload(language="zh-cn")
    en = _payload(
        "RegionFilter",
        [_definition("region", ("north", "east"))],
        [
            (("region", "north"),),
            (("region", "east"),),
        ],
        language="en-us",
    )
    en_expected = _expectation(
        (_expected_filter("region", ("north", "east")),),
        (
            (("region", "north"),),
            (("region", "east"),),
        ),
    )

    result = _validate_pair(
        validator,
        zh,
        en,
        en_expected=en_expected,
    )

    assert result.passed, result.to_dict(include_source_findings=True)
    assert [finding.code for finding in result.source_findings] == [
        "bilingual_source_reachability_drift"
    ]
    assert not {
        "bilingual_option_values_mismatch",
        "bilingual_default_state_mismatch",
        "bilingual_reachability_relation_mismatch",
    }.intersection(_codes(result))


def test_bilingual_filter_type_and_sparse_relation_drift_fail(
    validator: ContractValidator,
) -> None:
    zh = _sparse_payload(language="zh-cn")
    en = _sparse_payload(language="en-us")
    en_config = json.loads(en["pageConfig"]["filtersJsonConfig"])
    en_config["filterDefinitions"][1]["filterType"] = "tab"
    for option in en_config["filterDefinitions"][1]["options"]:
        option["href"] = f"#{option['value']}"
    _set_filter_config(en, en_config)

    result = _validate_pair(
        validator,
        zh,
        en,
        zh_expected=_sparse_expectation(),
        en_expected=_sparse_expectation(),
    )
    assert "bilingual_filter_types_mismatch" in _codes(result)

    relation_drift = _sparse_payload(language="en-us")
    relation_drift["contentGroups"][1], relation_drift["contentGroups"][2] = (
        relation_drift["contentGroups"][2],
        relation_drift["contentGroups"][1],
    )
    result = _validate_pair(
        validator,
        zh,
        relation_drift,
        zh_expected=_sparse_expectation(),
        en_expected=_sparse_expectation(),
    )
    assert "bilingual_reachability_relation_mismatch" in _codes(result)


def test_bilingual_empty_state_evidence_is_required_independently(
    validator: ContractValidator,
) -> None:
    zh = _region_payload(language="zh-cn")
    en = _region_payload(language="en-us")
    zh["contentGroups"][0]["content"] = "<p>该区域不提供价格。</p>"
    en["contentGroups"][0]["content"] = "<p>No price is offered in this region.</p>"
    state = CmsState((("region", "east"),))

    no_evidence = _validate_pair(validator, zh, en)
    assert "content_group_not_price_bearing" in _codes(no_evidence)

    one_side = _validate_pair(
        validator,
        zh,
        en,
        zh_empty_states={state},
    )
    assert "content_group_not_price_bearing" in _codes(one_side)
    assert len(one_side.source_findings) == 1

    both = _validate_pair(
        validator,
        zh,
        en,
        zh_empty_states={state},
        en_empty_states={state},
    )
    assert both.passed, both.to_dict(include_source_findings=True)
    assert len(both.source_findings) == 2
