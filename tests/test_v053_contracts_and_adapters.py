from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path

import pytest
from bs4 import BeautifulSoup, Tag

from src.independent_fidelity.contracts import (
    validate_basis,
    validate_evidence,
    validate_profile,
)
from src.independent_fidelity.targets import (
    PROFILE_PATH_V11,
    TARGET_SET_PATH,
    TargetSetError,
    load_target_set,
)
from src.independent_fidelity.v053_adapters import (
    AdapterError,
    CSS_GENERATED_SEMANTICS_RULE,
    ROOT_RELATIVE_ASSETS_RULE,
    SUPPORT_URL_RESOLUTION_RULE,
    _pricing_wire,
)
from src.independent_fidelity.v053_verifier import (
    reconstruct_bound_target,
    verify_bound_target,
    verify_reconstruction,
)


ROOT = Path(__file__).resolve().parents[1]
CORE_ITEMS = (
    "zh-cn/api-management",
    "en-us/api-management",
    "zh-cn/cloud-services",
    "en-us/cloud-services",
    "zh-cn/service-bus",
    "en-us/service-bus",
    "zh-cn/icp-faq",
    "en-us/icp-faq",
)


def test_profile_and_target_set_are_separate_closed_world_contracts() -> None:
    import json

    profile = json.loads((ROOT / PROFILE_PATH_V11).read_text(encoding="utf-8"))
    assert validate_profile(ROOT, profile) == profile
    targets = load_target_set(ROOT)
    assert len([target for target in targets if target.role == "core"]) == 8
    assert len([target for target in targets if target.role == "carry_over"]) == 2
    assert "item" not in profile and "target" not in profile


def test_target_set_reader_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    target_path = tmp_path / TARGET_SET_PATH
    target_path.parent.mkdir(parents=True)
    source = (ROOT / TARGET_SET_PATH).read_text(encoding="utf-8")
    target_path.write_text(
        source.replace(
            '"schema_version": "1.0",',
            '"schema_version": "1.0", "schema_version": "1.0",',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(TargetSetError, match="Duplicate JSON key"):
        load_target_set(tmp_path)


@pytest.mark.parametrize("item_id", CORE_ITEMS)
def test_four_family_core_reconstructs_reference_payload_directly(
    item_id: str, v053_reference_target_factory
) -> None:
    target = v053_reference_target_factory(item_id)
    run = verify_bound_target(target)
    expected_verdict = "failed" if item_id.endswith("/icp-faq") else "passed"
    assert run.evidence["verdict"] == expected_verdict
    assert run.evidence["coverage"]["required"] == len(
        run.evidence["scopes"]
    )
    assert run.evidence["coverage"][expected_verdict] == len(
        run.evidence["scopes"]
    )
    if expected_verdict == "passed":
        assert not run.evidence["mismatches"]
    else:
        assert any(
            mismatch["dimension"] == "visible_text"
            for mismatch in run.evidence["mismatches"]
        )
    assert not run.evidence["blocking_errors"]
    validate_basis(ROOT, run.evidence["reconstruction_basis"])
    validate_evidence(ROOT, run.evidence)


def test_preflight_scope_counts_and_carry_over_qualification(
    v053_reference_target_factory,
) -> None:
    expected = {
        "zh-cn/api-management": 5,
        "en-us/api-management": 5,
        "zh-cn/cloud-services": 16,
        "en-us/cloud-services": 16,
        "zh-cn/service-bus": 1,
        "en-us/service-bus": 1,
        "zh-cn/icp-faq": 1,
        "en-us/icp-faq": 1,
        "zh-cn/sla-sql-data": 1,
    }
    assert sum(expected[item] for item in CORE_ITEMS) == 46
    for item_id, count in expected.items():
        target = v053_reference_target_factory(item_id)
        assert len(reconstruct_bound_target(target).scopes) == count
    with pytest.raises(AdapterError) as raised:
        reconstruct_bound_target(
            v053_reference_target_factory("en-us/time-series-insights")
        )
    assert raised.value.qualification is True
    assert raised.value.code == "soft_category_exact_row_ambiguous"


def test_region_state_swap_fails_and_missing_scope_blocks(
    v053_reference_target_factory,
) -> None:
    target = v053_reference_target_factory("zh-cn/api-management")
    reconstruction = reconstruct_bound_target(target)
    swapped = copy.deepcopy(target.payload)
    swapped["contentGroups"][0]["content"], swapped["contentGroups"][3][
        "content"
    ] = (
        swapped["contentGroups"][3]["content"],
        swapped["contentGroups"][0]["content"],
    )
    failed = verify_reconstruction(target, reconstruction, payload=swapped)
    assert failed.evidence["verdict"] == "failed"
    assert failed.evidence["coverage"]["failed"] == 2

    missing = copy.deepcopy(target.payload)
    missing["contentGroups"].pop()
    blocked = verify_reconstruction(target, reconstruction, payload=missing)
    assert blocked.evidence["coverage"]["blocked"] == 1
    assert any(
        error["code"] == "payload_scope_missing"
        for error in blocked.evidence["blocking_errors"]
    )


def test_region_mobile_domain_and_duplicate_config_rows_stop_the_claim(
    v053_reference_target_factory,
) -> None:
    target = v053_reference_target_factory("zh-cn/api-management")
    soup = BeautifulSoup(target.source_html, "html.parser")
    option = soup.select_one("select#region-box > option")
    assert isinstance(option, Tag)
    option["data-href"] = "#not-a-desktop-target"
    with pytest.raises(AdapterError) as raised:
        reconstruct_bound_target(replace(target, source_html=str(soup)))
    assert raised.value.code == "mobile_region_domain_target_mismatch"

    assert target.soft_category is not None
    duplicated = [copy.deepcopy(row) for row in target.soft_category]
    duplicated.extend(copy.deepcopy(row) for row in target.soft_category)
    with pytest.raises(AdapterError) as raised:
        reconstruct_bound_target(replace(target, soft_category=duplicated))
    assert raised.value.code == "soft_category_exact_row_ambiguous"
    assert raised.value.qualification is True


def test_complex_swap_and_page_global_boundary_counterexamples(
    v053_reference_target_factory,
) -> None:
    target = v053_reference_target_factory("zh-cn/cloud-services")
    reconstruction = reconstruct_bound_target(target)
    swapped = copy.deepcopy(target.payload)
    swapped["contentGroups"][0]["content"], swapped["contentGroups"][1][
        "content"
    ] = (
        swapped["contentGroups"][1]["content"],
        swapped["contentGroups"][0]["content"],
    )
    run = verify_reconstruction(target, reconstruction, payload=swapped)
    assert run.evidence["verdict"] == "failed"
    assert run.evidence["coverage"]["failed"] == 2

    overwide = target.source_html.replace(
        '<div class="pricing-page-section">',
        '<div class="pricing-page-section"><p>unfrozen boundary</p>',
        1,
    )
    from dataclasses import replace

    with pytest.raises(AdapterError) as raised:
        reconstruct_bound_target(replace(target, source_html=overwide))
    assert raised.value.code in {
        "page_global_identity_mismatch",
        "source_container_ambiguous",
    }


def test_simple_boundary_and_support_route_map_counterexamples(
    v053_reference_target_factory,
) -> None:
    simple = v053_reference_target_factory("zh-cn/service-bus")
    narrowed = simple.source_html.replace("消息数", "", 1)
    with pytest.raises(AdapterError) as raised:
        reconstruct_bound_target(replace(simple, source_html=narrowed))
    assert raised.value.code == "simple_content_identity_mismatch"

    soup = BeautifulSoup(simple.source_html, "html.parser")
    selector = soup.select_one("div.pure-content > div.technical-azure-selector")
    assert isinstance(selector, Tag)
    extra = soup.new_tag("p")
    extra.string = "unfrozen business content outside the static boundary"
    selector.insert_after(extra)
    with pytest.raises(AdapterError) as raised:
        reconstruct_bound_target(replace(simple, source_html=str(soup)))
    assert raised.value.code == "simple_content_boundary_ambiguous"

    support = v053_reference_target_factory("zh-cn/sla-sql-data")
    reconstruction = reconstruct_bound_target(support)
    wrong_route = copy.deepcopy(support.payload)
    wrong_route["mainContent"] = wrong_route["mainContent"].replace(
        "/support/sla/sql-data-v1-5/",
        "/support/sla/wrong-version/",
        1,
    )
    run = verify_reconstruction(
        support, reconstruction, payload=wrong_route
    )
    assert run.evidence["verdict"] == "failed"
    dimensions = {
        mismatch["dimension"] for mismatch in run.evidence["mismatches"]
    }
    assert "business_semantics" in dimensions

    soup = BeautifulSoup(support.source_html, "html.parser")
    first_h2 = soup.select_one("div.pure-content h2")
    assert isinstance(first_h2, Tag)
    first_h2.name = "h3"
    drifted = replace(support, source_html=str(soup))
    drifted_reconstruction = reconstruct_bound_target(drifted)
    drifted_run = verify_reconstruction(
        drifted, drifted_reconstruction, payload=support.payload
    )
    assert drifted_run.evidence["verdict"] == "failed"
    assert any(
        mismatch["dimension"] == "visible_text"
        for mismatch in drifted_run.evidence["mismatches"]
    )


def test_independent_asset_css_and_support_url_transforms(
    v053_reference_target_factory,
) -> None:
    transformed, rules = _pricing_wire(
        """
        <div data-config="{'backgroundImage':'/images/card.png'}"
             style="background-image:url('/images/background.png')">
          <img src="/images/icon.png">
          <i class="icon icon-tick"></i>
        </div>
        """
    )
    assert rules == (
        ROOT_RELATIVE_ASSETS_RULE,
        CSS_GENERATED_SEMANTICS_RULE,
    )
    soup = BeautifulSoup(transformed, "html.parser")
    image = soup.select_one("img")
    container = soup.select_one("div")
    assert isinstance(image, Tag) and isinstance(container, Tag)
    assert image["src"] == "{base_url}/images/icon.png"
    assert "{base_url}/images/background.png" in container["style"]
    assert "{base_url}/images/card.png" in container["data-config"]
    assert soup.select_one("i.icon-tick") is None
    assert "✓" in soup.get_text()

    support = v053_reference_target_factory("zh-cn/sla-sql-data")
    reconstruction = reconstruct_bound_target(support)
    scope = reconstruction.scopes[0]
    assert SUPPORT_URL_RESOLUTION_RULE in scope.applied_transform_rule_ids
    assert "{base_url}/support/sla/sql-data-v1-5/" in scope.expected_fragment


def test_en_us_icp_claim_limitation_does_not_change_content_verdict(
    v053_reference_target_factory,
) -> None:
    zh_run = verify_bound_target(
        v053_reference_target_factory("zh-cn/icp-faq")
    )
    en_run = verify_bound_target(
        v053_reference_target_factory("en-us/icp-faq")
    )
    assert en_run.evidence["verdict"] == zh_run.evidence["verdict"] == "failed"
    assert len(en_run.evidence["claim_limitations"]) == 1
    assert "language correctness" in en_run.evidence["claim_limitations"][0]
    assert zh_run.evidence["claim_limitations"] == []


def test_support_boundary_preserves_visible_direct_text(
    v053_reference_target_factory,
) -> None:
    target = v053_reference_target_factory("zh-cn/icp-faq")
    reconstruction = reconstruct_bound_target(target)
    scope = reconstruction.scopes[0]
    text = "域名证书一般在域名注册平台下载"
    assert text in scope.source_fragment
    assert text in scope.expected_fragment
    assert text not in target.payload["mainContent"]
    run = verify_reconstruction(target, reconstruction)
    assert run.evidence["verdict"] == "failed"
    assert any(
        mismatch["dimension"] == "visible_text"
        for mismatch in run.evidence["mismatches"]
    )
