from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.core.canonical_input import CanonicalHtmlInput, CanonicalInputLoader
from src.core.cms_state_contract import CmsState
from src.core.product_manager import ProductManager
from src.core.source_reachability import (
    SourceReachability,
    SourceReachabilityError,
    SourceReachabilityResolver,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def real_reachability() -> dict[tuple[str, str], SourceReachability]:
    manager = ProductManager(str(ROOT / "data" / "configs"))
    loader = CanonicalInputLoader(ROOT, manager)
    resolver = SourceReachabilityResolver()
    return {
        (product, language): resolver.resolve(loader.load(product, language))
        for product in (
            "api-management",
            "app-service",
            "sql-database",
            "virtual-machine-scale-sets",
            "machine-learning",
        )
        for language in ("zh-cn", "en-us")
    }


def _canonical(tmp_path: Path, html: str) -> CanonicalHtmlInput:
    raw = html.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    path = tmp_path / "sample.html"
    return CanonicalHtmlInput(
        product_key="sample",
        resource_key="sample",
        language="en-us",
        source_path=path,
        normalized_path=path,
        source_sha256=digest,
        normalized_sha256=digest,
        expected_sha256=digest,
        raw_bytes=raw,
        text=html,
        has_utf8_bom=False,
        source_findings=(),
    )


def _option(
    value: str,
    label: str,
    href: str,
    *,
    selected: bool = False,
) -> str:
    marker = ' selected="selected"' if selected else ""
    return (
        f'<option value="{value}" data-href="{href}"{marker}>'
        f"{label}</option>"
    )


def _dropdown(
    css_class: str,
    select_id: str,
    options: list[tuple[str, str, str]],
    *,
    default_href: str,
    label: str,
    mobile_options: list[tuple[str, str, str]] | None = None,
    mobile_default_hrefs: set[str] | None = None,
    desktop_default_hrefs: set[str] | None = None,
    selected_item_label: str | None = None,
) -> str:
    active_hrefs = (
        desktop_default_hrefs
        if desktop_default_hrefs is not None
        else {default_href}
    )
    links = "".join(
        (
            f'<li class="{"active" if href in active_hrefs else ""}">'
            f'<a data-href="{href}">{text}</a></li>'
        )
        for _, text, href in options
    )
    mobile = "".join(
        _option(
            value,
            text,
            href,
            selected=href in (
                mobile_default_hrefs
                if mobile_default_hrefs is not None
                else {default_href}
            ),
        )
        for value, text, href in (mobile_options or options)
    )
    display_label = (
        selected_item_label
        if selected_item_label is not None
        else next(
            text for _, text, href in options if href == default_href
        )
    )
    return f"""
    <div class="dropdown-container {css_class}">
      <label>{label}:</label>
      <div class="dropdown-box os-tab-nav">
        <span class="selected-item">
          {display_label}
        </span>
        <ol class="tab-items">{links}</ol>
      </div>
      <select id="{select_id}">{mobile}</select>
    </div>
    """


def _category(
    parent: str,
    options: list[tuple[str, str]],
    *,
    mobile_options: list[tuple[str, str]] | None = None,
) -> str:
    desktop = "".join(
        (
            f'<li class="{"active" if index == 0 else ""}">'
            f'<a data-href="{href}">{label}</a></li>'
        )
        for index, (href, label) in enumerate(options)
    )
    mobile = "".join(
        f'<option data-href="{href}">{label}</option>'
        for href, label in (mobile_options or options)
    )
    panels = "".join(
        (
            f'<div class="tab-panel" id="{href.removeprefix("#")}">'
            "<table><tr><td>1</td></tr></table></div>"
        )
        for href, label in options
        if label.casefold() not in {"all", "全部"}
    )
    return f"""
    <div class="tab-panel" id="{parent}">
      <div class="category-container">
        <span class="category-title">Category:</span>
        <ul class="os-tab-nav category-tabs hidden-xs hidden-sm">
          {desktop}
        </ul>
        <select class="category-tabs">{mobile}</select>
      </div>
      <div class="tab-content">{panels}</div>
    </div>
    """


def test_source_reachability_public_api_exists() -> None:
    assert callable(SourceReachabilityResolver().resolve)


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_sql_database_resolves_24_scoped_states(
    real_reachability: dict[tuple[str, str], SourceReachability],
    language: str,
) -> None:
    result = real_reachability[("sql-database", language)]

    assert tuple(
        value.filter_key for value in result.filter_definitions_union
    ) == ("region", "software", "category")
    assert tuple(
        len(value.options) for value in result.filter_definitions_union
    ) == (6, 2, 4)
    assert len(result.ordered_states) == 24
    assert result.default_state == CmsState((
        ("region", "east-china3"),
        ("software", "Elastic Database"),
        ("category", "tabContent1-1"),
    ))
    assert (
        result.ordered_states[0].mapping_key
        == "east-china3_Elastic Database_tabContent1-1"
    )
    assert result.suppressed_options == ()
    assert result.unreachable_panel_ids == ()


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_vmss_resolves_104_concrete_states_and_suppresses_all(
    real_reachability: dict[tuple[str, str], SourceReachability],
    language: str,
) -> None:
    result = real_reachability[
        ("virtual-machine-scale-sets", language)
    ]

    assert tuple(
        len(value.options) for value in result.filter_definitions_union
    ) == (4, 7, 26)
    assert len(result.ordered_states) == 104
    assert len(result.suppressed_options) == 7
    assert all(
        option.reason == "missing_aggregate_target"
        and option.was_default
        and option.replacement_default_value is not None
        for option in result.suppressed_options
    )
    assert result.default_state == CmsState((
        ("region", "east-china2"),
        ("software", "Windows"),
        ("category", "tabContent1-1"),
    ))
    assert result.unreachable_panel_ids == ()


def test_vmss_stale_display_summary_is_frozen_as_finding(
    real_reachability: dict[tuple[str, str], SourceReachability],
) -> None:
    zh = real_reachability[("virtual-machine-scale-sets", "zh-cn")]
    en = real_reachability[("virtual-machine-scale-sets", "en-us")]

    assert zh.findings == ()
    assert [finding.code for finding in en.findings] == [
        "display_summary_default_drift"
    ]
    assert en.findings[0].evidence["selected_item_label"] == "China North 2"
    assert en.findings[0].evidence["proven_default_href"] == "#east-china2"


def test_api_management_uses_same_language_desktop_display_labels(
    real_reachability: dict[tuple[str, str], SourceReachability],
) -> None:
    zh = real_reachability[("api-management", "zh-cn")]
    en = real_reachability[("api-management", "en-us")]

    zh_groups = {
        state.cms_state: state.group_name for state in zh.ordered_states
    }
    en_groups = {
        state.cms_state: state.group_name for state in en.ordered_states
    }
    east_2 = CmsState((("region", "east-china2"),))
    north_3 = CmsState((("region", "north-china3"),))

    assert zh_groups[east_2] == "中国东部 2"
    assert en_groups[east_2] == "China East 2"
    assert en_groups[north_3] == "China North 3"
    assert zh.state_relation == en.state_relation
    assert zh.findings == ()
    assert [finding.code for finding in en.findings] == [
        "responsive_filter_label_drift"
    ]
    assert en.findings[0].evidence == {
        "filter_key": "region",
        "href": "#north-china3",
        "value": "north-china3",
        "desktop_label": "China North 3",
        "mobile_label": "China North3",
    }


def test_app_service_zh_uses_unambiguous_desktop_default(
    real_reachability: dict[tuple[str, str], SourceReachability],
) -> None:
    result = real_reachability[("app-service", "zh-cn")]

    assert len(result.ordered_states) == 12
    assert result.default_state == CmsState((
        ("region", "east-china3"),
        ("software", "App Windows"),
    ))
    assert [finding.code for finding in result.findings] == [
        "responsive_filter_label_drift",
    ]


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_machine_learning_only_traverses_linux_panel(
    real_reachability: dict[tuple[str, str], SourceReachability],
    language: str,
) -> None:
    result = real_reachability[("machine-learning", language)]

    assert tuple(
        len(value.options) for value in result.filter_definitions_union
    ) == (5, 1, 4)
    assert len(result.ordered_states) == 20
    assert len(result.suppressed_options) == 1
    assert result.default_state == CmsState((
        ("region", "north-china3"),
        ("software", "Linux"),
        ("category", "tabContent2-1"),
    ))
    if language == "zh-cn":
        assert result.unreachable_panel_ids == (
            "tabContent1",
            "tabContent3",
            "tabContent4",
            "tabContent5",
            "tabContent6",
            "tabContent7",
        )
    else:
        assert result.unreachable_panel_ids == ()


def test_bilingual_machine_relations_match(
    real_reachability: dict[tuple[str, str], SourceReachability],
) -> None:
    for product in (
        "api-management",
        "app-service",
        "sql-database",
        "virtual-machine-scale-sets",
        "machine-learning",
    ):
        zh = real_reachability[(product, "zh-cn")]
        en = real_reachability[(product, "en-us")]
        assert zh.state_relation == en.state_relation
        assert zh.default_state == en.default_state


def test_every_union_option_is_used_by_the_relation(
    real_reachability: dict[tuple[str, str], SourceReachability],
) -> None:
    for result in real_reachability.values():
        used: dict[str, set[str]] = {}
        for state in result.state_relation:
            for key, value in state.criteria:
                used.setdefault(key, set()).add(value)
        for definition in result.filter_definitions_union:
            assert {
                option.value for option in definition.options
            } <= used[definition.filter_key]


def test_result_converts_to_formal_contract_expectation(
    real_reachability: dict[tuple[str, str], SourceReachability],
) -> None:
    result = real_reachability[("sql-database", "en-us")]

    expected = result.to_expected_reachability()

    assert expected.filter_keys == ("region", "software", "category")
    assert expected.ordered_states == result.state_relation
    assert expected.default_state == result.default_state


def test_simple_source_has_empty_relation(tmp_path: Path) -> None:
    result = SourceReachabilityResolver().resolve(
        _canonical(tmp_path, "<html><body><h1>Simple</h1></body></html>")
    )

    assert result.filter_definitions_union == ()
    assert result.state_relation == ()
    assert result.default_state == CmsState(())


def test_region_only_source_uses_desktop_order(tmp_path: Path) -> None:
    region = _dropdown(
        "region-container",
        "region-box",
        [
            ("west", "West", "#west"),
            ("east", "East", "#east"),
        ],
        default_href="#east",
        label="Region",
    )
    html = (
        '<div class="technical-azure-selector pricing-detail-tab">'
        f"{region}</div>"
    )

    result = SourceReachabilityResolver().resolve(
        _canonical(tmp_path, html)
    )

    assert result.state_relation == (
        CmsState((("region", "east"),)),
        CmsState((("region", "west"),)),
    )
    assert [
        state.group_name for state in result.ordered_states
    ] == ["East", "West"]


def test_unambiguous_desktop_default_ignores_stale_mobile_defaults(
    tmp_path: Path,
) -> None:
    region = _dropdown(
        "region-container",
        "region-box",
        [
            ("west", "West", "#west"),
            ("east", "East", "#east"),
        ],
        default_href="#east",
        label="Region",
        mobile_default_hrefs={"#west", "#east"},
    )
    html = (
        '<div class="technical-azure-selector pricing-detail-tab">'
        f"{region}</div>"
    )

    result = SourceReachabilityResolver().resolve(
        _canonical(tmp_path, html)
    )

    assert result.default_state == CmsState((("region", "east"),))
    assert result.findings == ()


def test_unambiguous_desktop_default_ignores_different_mobile_default(
    tmp_path: Path,
) -> None:
    region = _dropdown(
        "region-container",
        "region-box",
        [
            ("west", "West", "#west"),
            ("east", "East", "#east"),
        ],
        default_href="#east",
        label="Region",
        mobile_default_hrefs={"#west"},
    )
    html = (
        '<div class="technical-azure-selector pricing-detail-tab">'
        f"{region}</div>"
    )

    result = SourceReachabilityResolver().resolve(
        _canonical(tmp_path, html)
    )

    assert result.default_state == CmsState((("region", "east"),))
    assert result.findings == ()


def test_mobile_default_cannot_replace_missing_desktop_default(
    tmp_path: Path,
) -> None:
    region = _dropdown(
        "region-container",
        "region-box",
        [
            ("west", "West", "#west"),
            ("east", "East", "#east"),
        ],
        default_href="#east",
        label="Region",
        desktop_default_hrefs=set(),
        selected_item_label="",
    )
    html = (
        '<div class="technical-azure-selector pricing-detail-tab">'
        f"{region}</div>"
    )

    with pytest.raises(SourceReachabilityError) as captured:
        SourceReachabilityResolver().resolve(_canonical(tmp_path, html))

    assert captured.value.code == "missing_filter_default"
    assert str(captured.value) == (
        "region desktop control has no unambiguous default"
    )


def test_multiple_mobile_defaults_still_fail_when_desktop_is_ambiguous(
    tmp_path: Path,
) -> None:
    region = _dropdown(
        "region-container",
        "region-box",
        [
            ("west", "West", "#west"),
            ("east", "East", "#east"),
        ],
        default_href="#east",
        label="Region",
        mobile_default_hrefs={"#west", "#east"},
        desktop_default_hrefs={"#west", "#east"},
    )
    html = (
        '<div class="technical-azure-selector pricing-detail-tab">'
        f"{region}</div>"
    )

    with pytest.raises(SourceReachabilityError) as captured:
        SourceReachabilityResolver().resolve(_canonical(tmp_path, html))

    assert captured.value.code == "multiple_filter_defaults"
    assert str(captured.value) == (
        "region desktop control declares multiple defaults"
    )


def test_desktop_display_label_wins_over_mobile_label_drift(
    tmp_path: Path,
) -> None:
    region = _dropdown(
        "region-container",
        "region-box",
        [("north-3", "China North 3", "#north-3")],
        default_href="#north-3",
        label="Region",
        mobile_options=[
            ("north-3", "China North3", "#north-3"),
        ],
    )
    html = (
        '<div class="technical-azure-selector pricing-detail-tab">'
        f"{region}</div>"
    )

    result = SourceReachabilityResolver().resolve(
        _canonical(tmp_path, html)
    )

    assert result.ordered_states[0].group_name == "China North 3"
    assert result.filter_definitions_union[0].options[0].label == (
        "China North 3"
    )
    assert [finding.code for finding in result.findings] == [
        "responsive_filter_label_drift"
    ]


def test_region_target_is_canonical_when_mobile_machine_value_drifts(
    tmp_path: Path,
) -> None:
    region = _dropdown(
        "region-container",
        "region-box",
        [
            ("north-china3", "China East 3", "#east-china3"),
            ("north-china3", "China North 3", "#north-china3"),
        ],
        default_href="#east-china3",
        label="Region",
    )
    html = (
        '<div class="technical-azure-selector pricing-detail-tab">'
        f"{region}</div>"
    )

    result = SourceReachabilityResolver().resolve(
        _canonical(tmp_path, html)
    )

    assert result.state_relation == (
        CmsState((("region", "east-china3"),)),
        CmsState((("region", "north-china3"),)),
    )
    assert [finding.to_dict() for finding in result.findings] == [{
        "code": "filter_machine_value_target_drift",
        "message": (
            "region mobile machine value disagrees with its interaction "
            "target; the target fragment is authoritative."
        ),
        "evidence": {
            "filter_key": "region",
            "href": "#east-china3",
            "source_value": "north-china3",
            "canonical_value": "east-china3",
        },
    }]


def test_hidden_software_is_internal_scope_not_active_cms_dimension(
    tmp_path: Path,
) -> None:
    region = _dropdown(
        "region-container",
        "region-box",
        [("east", "East", "#east")],
        default_href="#east",
        label="Region",
    )
    software = _dropdown(
        "software-kind-container",
        "software-box",
        [("Cloud", "Cloud", "#tabContent1")],
        default_href="#tabContent1",
        label="Software",
    ).replace(
        'class="dropdown-container software-kind-container"',
        (
            'class="dropdown-container software-kind-container" '
            'style="display: none"'
        ),
    )
    category = _category(
        "tabContent1",
        [
            ("#tabContent1-0", "All"),
            ("#tabContent1-1", "General"),
        ],
    )
    html = f"""
    <div class="technical-azure-selector pricing-detail-tab">
      {region}{software}<div class="tab-content">{category}</div>
    </div>
    """

    result = SourceReachabilityResolver().resolve(
        _canonical(tmp_path, html)
    )

    assert tuple(
        value.filter_key for value in result.filter_definitions_union
    ) == ("region", "category")
    assert result.state_relation == (
        CmsState((
            ("region", "east"),
            ("category", "tabContent1-1"),
        )),
    )
    state = result.ordered_states[0]
    assert state.group_name == "East - General"
    assert state.mapping_key == "east_Cloud_tabContent1-1"
    assert state.source_evidence.software_value == "Cloud"
    assert state.source_evidence.software_visible is False


def test_mixed_software_branches_may_omit_category(tmp_path: Path) -> None:
    region = _dropdown(
        "region-container",
        "region-box",
        [("east", "East", "#east")],
        default_href="#east",
        label="Region",
    )
    software = _dropdown(
        "software-kind-container",
        "software-box",
        [
            ("one", "One", "#tabContent1"),
            ("two", "Two", "#tabContent2"),
        ],
        default_href="#tabContent1",
        label="Software",
    )
    category = _category(
        "tabContent1",
        [("#tabContent1-1", "General")],
    )
    html = f"""
    <div class="technical-azure-selector pricing-detail-tab">
      {region}{software}
      <div class="tab-content">
        {category}
        <div class="tab-panel" id="tabContent2"><p>Leaf</p></div>
      </div>
    </div>
    """

    result = SourceReachabilityResolver().resolve(
        _canonical(tmp_path, html)
    )

    assert result.state_relation == (
        CmsState((
            ("region", "east"),
            ("software", "one"),
            ("category", "tabContent1-1"),
        )),
        CmsState((
            ("region", "east"),
            ("software", "two"),
        )),
    )
    assert [
        state.group_name for state in result.ordered_states
    ] == ["East - One - General", "East - Two"]


def test_nonaggregate_missing_category_target_fails(tmp_path: Path) -> None:
    region = _dropdown(
        "region-container",
        "region-box",
        [("east", "East", "#east")],
        default_href="#east",
        label="Region",
    )
    software = _dropdown(
        "software-kind-container",
        "software-box",
        [("linux", "Linux", "#tabContent1")],
        default_href="#tabContent1",
        label="Software",
    )
    category = _category(
        "tabContent1",
        [("#tabContent1-1", "General")],
    ).replace(
        (
            '<div class="tab-panel" id="tabContent1-1">'
            "<table><tr><td>1</td></tr></table></div>"
        ),
        "",
    )
    html = f"""
    <div class="technical-azure-selector pricing-detail-tab">
      {region}{software}<div class="tab-content">{category}</div>
    </div>
    """

    with pytest.raises(SourceReachabilityError) as captured:
        SourceReachabilityResolver().resolve(_canonical(tmp_path, html))

    assert captured.value.code == "missing_category_target"


def test_responsive_category_domain_mismatch_fails(tmp_path: Path) -> None:
    region = _dropdown(
        "region-container",
        "region-box",
        [("east", "East", "#east")],
        default_href="#east",
        label="Region",
    )
    software = _dropdown(
        "software-kind-container",
        "software-box",
        [("linux", "Linux", "#tabContent1")],
        default_href="#tabContent1",
        label="Software",
    )
    category = _category(
        "tabContent1",
        [("#tabContent1-1", "General")],
        mobile_options=[("#tabContent1-2", "Other")],
    )
    html = f"""
    <div class="technical-azure-selector pricing-detail-tab">
      {region}{software}<div class="tab-content">{category}</div>
    </div>
    """

    with pytest.raises(SourceReachabilityError) as captured:
        SourceReachabilityResolver().resolve(_canonical(tmp_path, html))

    assert captured.value.code == "responsive_category_domain_mismatch"


def test_category_desktop_display_label_wins_over_mobile_drift(
    tmp_path: Path,
) -> None:
    region = _dropdown(
        "region-container",
        "region-box",
        [("east", "China East 2", "#east")],
        default_href="#east",
        label="Region",
    )
    software = _dropdown(
        "software-kind-container",
        "software-box",
        [("linux", "Linux", "#tabContent1")],
        default_href="#tabContent1",
        label="Software",
    )
    category = _category(
        "tabContent1",
        [("#tabContent1-1", "General purpose")],
        mobile_options=[("#tabContent1-1", "Generalpurpose")],
    )
    html = f"""
    <div class="technical-azure-selector pricing-detail-tab">
      {region}{software}<div class="tab-content">{category}</div>
    </div>
    """

    result = SourceReachabilityResolver().resolve(
        _canonical(tmp_path, html)
    )

    assert result.ordered_states[0].group_name == (
        "China East 2 - Linux - General purpose"
    )
    assert [finding.code for finding in result.findings] == [
        "responsive_filter_label_drift"
    ]


def test_group_name_delimiter_in_active_label_fails(tmp_path: Path) -> None:
    region = _dropdown(
        "region-container",
        "region-box",
        [("east", "East - Ambiguous", "#east")],
        default_href="#east",
        label="Region",
    )
    html = (
        '<div class="technical-azure-selector pricing-detail-tab">'
        f"{region}</div>"
    )

    with pytest.raises(SourceReachabilityError) as captured:
        SourceReachabilityResolver().resolve(_canonical(tmp_path, html))

    assert captured.value.code == "ambiguous_group_label_segment"
