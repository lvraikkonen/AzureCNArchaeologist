from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from src.core.canonical_input import CanonicalInputLoader
from src.core.cms_state_contract import (
    CmsState,
    validate_bilingual_machine_identity,
    validate_flexible_state_contract,
)
from src.core.product_manager import ProductManager
from src.core.scoped_source_content import (
    ScopedSourceContentError,
    SoftwareScopedPrefixEvidence,
    extract_software_scoped_prefix,
)
from src.core.source_reachability import (
    ReachabilityFilterDefinition,
    ReachabilityOption,
    ReachabilitySourceEvidence,
    ReachableCmsState,
    SourceReachability,
    SourceReachabilityResolver,
)
from src.utils.content.flexible_builder import FlexibleBuilder


ROOT = Path(__file__).resolve().parents[1]

_VMSS_PREFIX_EVIDENCE = {
    "zh-cn": {
        "SQL Server for Windows": (
            "tabContent3",
            1,
            "b60c7beebcf08e1d5cb77dcf2f92857"
            "d91172dc76a76693491f25a36028371b2",
        ),
        "SQL Server Ubuntu Linux": (
            "tabContent4",
            1,
            "8d70e9c744ee206023d22574d79da77a"
            "2c71d1258f36ba3aac7ba3e72edfe82e",
        ),
        "Machine Learning Server": (
            "tabContent5",
            1,
            "5e78bcf9ff182b7971c8ca9c5510aab2"
            "c3af4579fe68be01dd5e848f62700d19",
        ),
    },
    "en-us": {
        "SQL Server for Windows": (
            "tabContent3",
            1,
            "dd9f6ee0b101e9e73f4a794ab9012088"
            "16c8570cd14cf274897720c475a73754",
        ),
        "SQL Server Ubuntu Linux": (
            "tabContent4",
            1,
            "760c4adfeba50dd11dbb0f886416a29b"
            "be2959525f28e7acc0ea2155e0c1f17e",
        ),
        "Machine Learning Server": (
            "tabContent5",
            1,
            "93c8bc3806ec55a1f8b954ea954cc63d"
            "0314dbb70bb00c29ed0b9b0a64df678f",
        ),
    },
}

_VMSS_SOFTWARE_WITHOUT_PREFIX = {
    "Windows",
    "Linux",
    "SUSE Linux Enterprise Basic",
    "SUSE Linux Enterprise Server for SAP Priority",
}


@pytest.fixture(scope="module")
def vmss_reachability() -> dict[str, SourceReachability]:
    manager = ProductManager(str(ROOT / "data" / "configs"))
    loader = CanonicalInputLoader(ROOT, manager)
    resolver = SourceReachabilityResolver()
    return {
        language: resolver.resolve(
            loader.load("virtual-machine-scale-sets", language)
        )
        for language in ("zh-cn", "en-us")
    }


@pytest.mark.parametrize("wrapper_class", ["tab-content", "tabContent"])
def test_prefix_classifier_uses_only_direct_category_wrapper(
    wrapper_class: str,
) -> None:
    soup = BeautifulSoup(
        f"""
        <div class="tab-panel" id="tabContent3">
          <div class="{wrapper_class}">
            <aside data-test="software-prefix">SOFTWARE PREFIX</aside>
            <div class="tab-panel" id="tabContent3-1">
              <div class="tab-content">
                <p>CATEGORY CONTENT MUST NOT BE INHERITED</p>
              </div>
            </div>
          </div>
        </div>
        """,
        "html.parser",
    )

    prefix = extract_software_scoped_prefix(
        soup,
        "tabContent3",
        expected_category_panel_ids=("tabContent3-1",),
    )

    assert prefix is not None
    assert prefix.software_panel_id == "tabContent3"
    assert prefix.fragment_count == 1
    assert "SOFTWARE PREFIX" in prefix.source_html
    assert "CATEGORY CONTENT MUST NOT BE INHERITED" not in prefix.source_html
    assert prefix.source_html_sha256 == hashlib.sha256(
        prefix.source_html.encode("utf-8")
    ).hexdigest()


def test_prefix_classifier_does_not_recurse_to_find_category_wrapper() -> None:
    soup = BeautifulSoup(
        """
        <div class="tab-panel" id="tabContent3">
          <div class="layout-wrapper">
            <div class="tab-content">
              <p>Nested text is not a software-scoped prefix.</p>
              <div class="tab-panel" id="tabContent3-1">Category</div>
            </div>
          </div>
        </div>
        """,
        "html.parser",
    )

    with pytest.raises(
        ScopedSourceContentError,
        match="direct Category wrapper",
    ):
        extract_software_scoped_prefix(
            soup,
            "tabContent3",
            expected_category_panel_ids=("tabContent3-1",),
        )


def test_prefix_classifier_rejects_nested_panel_before_direct_boundary() -> None:
    soup = BeautifulSoup(
        """
        <div class="tab-panel" id="tabContent3">
          <div class="tab-content">
            <section>
              <div class="tab-panel" id="nested-panel">Ambiguous scope</div>
            </section>
            <div class="tab-panel" id="tabContent3-1">Category</div>
          </div>
        </div>
        """,
        "html.parser",
    )

    with pytest.raises(
        ScopedSourceContentError,
        match="nested Category panel",
    ):
        extract_software_scoped_prefix(
            soup,
            "tabContent3",
            expected_category_panel_ids=("tabContent3-1",),
        )


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_real_vmss_freezes_software_scoped_prefix_evidence(
    vmss_reachability: dict[str, SourceReachability],
    language: str,
) -> None:
    result = vmss_reachability[language]
    expected = _VMSS_PREFIX_EVIDENCE[language]
    seen_scoped_software: set[str] = set()
    seen_unscoped_software: set[str] = set()

    for state in result.ordered_states:
        source = state.source_evidence
        software_value = source.software_value
        assert software_value is not None
        prefix = source.software_scoped_prefix
        if software_value in expected:
            panel_id, fragment_count, source_sha256 = expected[software_value]
            assert prefix is not None
            assert prefix.software_value == software_value
            assert prefix.software_panel_id == panel_id
            assert prefix.fragment_count == fragment_count
            assert prefix.source_html_sha256 == source_sha256
            assert prefix.to_dict()["scope"] == {
                "filter_key": "software",
                "match_value": software_value,
            }
            seen_scoped_software.add(software_value)
        else:
            assert software_value in _VMSS_SOFTWARE_WITHOUT_PREFIX
            assert prefix is None
            seen_unscoped_software.add(software_value)

    assert seen_scoped_software == set(expected)
    assert seen_unscoped_software == _VMSS_SOFTWARE_WITHOUT_PREFIX
    assert len(result.ordered_states) == 104
    assert sum(
        state.source_evidence.software_scoped_prefix is not None
        for state in result.ordered_states
    ) == 40
    assert sum(
        state.source_evidence.software_scoped_prefix is None
        for state in result.ordered_states
    ) == 64


def test_vmss_bilingual_prefix_scopes_have_same_machine_identity(
    vmss_reachability: dict[str, SourceReachability],
) -> None:
    def machine_scopes(
        result: SourceReachability,
    ) -> set[tuple[str, str]]:
        return {
            (
                prefix.software_value,
                prefix.software_panel_id,
            )
            for state in result.ordered_states
            if (
                prefix
                := state.source_evidence.software_scoped_prefix
            )
            is not None
        }

    expected = {
        ("SQL Server for Windows", "tabContent3"),
        ("SQL Server Ubuntu Linux", "tabContent4"),
        ("Machine Learning Server", "tabContent5"),
    }
    assert machine_scopes(vmss_reachability["zh-cn"]) == expected
    assert machine_scopes(vmss_reachability["en-us"]) == expected


_PREFIX_HTML = (
    '<div class="software-scoped-prefix">SOFTWARE PREFIX</div>'
)
_CATEGORY_HTML = (
    "<table><tr><td>CATEGORY PRICE ￥ 1 / hour</td></tr></table>"
)


def _builder_reachability(
    prefix_evidence: SoftwareScopedPrefixEvidence | None,
) -> SourceReachability:
    cms_state = CmsState((
        ("software", "SQL Server for Windows"),
        ("category", "tabContent3-1"),
    ))
    state = ReachableCmsState(
        cms_state=cms_state,
        state_label_segments=(
            "SQL Server for Windows",
            "General purpose",
        ),
        mapping_key="SQL Server for Windows_tabContent3-1",
        source_evidence=ReachabilitySourceEvidence(
            region_value=None,
            region_href=None,
            software_value="SQL Server for Windows",
            software_href="#tabContent3",
            software_panel_id="tabContent3",
            software_visible=True,
            category_value="tabContent3-1",
            category_href="#tabContent3-1",
            category_panel_id="tabContent3-1",
            software_scoped_prefix=prefix_evidence,
        ),
        is_default=True,
    )
    return SourceReachability(
        product_key="sample",
        language="en-us",
        source_path="sample.html",
        normalized_path="sample.html",
        source_sha256="a" * 64,
        normalized_sha256="a" * 64,
        filter_definitions_union=(
            ReachabilityFilterDefinition(
                filter_key="software",
                filter_type="dropdown",
                display_name="Software",
                options=(
                    ReachabilityOption(
                        value="SQL Server for Windows",
                        label="SQL Server for Windows",
                        href="#tabContent3",
                        is_default=True,
                    ),
                ),
            ),
            ReachabilityFilterDefinition(
                filter_key="category",
                filter_type="tab",
                display_name="Category",
                options=(
                    ReachabilityOption(
                        value="tabContent3-1",
                        label="General purpose",
                        href="#tabContent3-1",
                        is_default=True,
                        parent_value="SQL Server for Windows",
                        parent_panel_id="tabContent3",
                    ),
                ),
            ),
        ),
        ordered_states=(state,),
        default_state=cms_state,
        suppressed_options=(),
        unreachable_panel_ids=(),
        findings=(),
    )


def _frozen_prefix_evidence() -> SoftwareScopedPrefixEvidence:
    return SoftwareScopedPrefixEvidence(
        software_value="SQL Server for Windows",
        software_panel_id="tabContent3",
        category_panel_ids=("tabContent3-1",),
        fragment_count=1,
        source_html=_PREFIX_HTML,
        source_html_sha256=hashlib.sha256(
            _PREFIX_HTML.encode("utf-8")
        ).hexdigest(),
    )


def _builder_reachability_with_unscoped_state() -> SourceReachability:
    base = _builder_reachability(_frozen_prefix_evidence())
    second_state = CmsState((
        ("software", "Linux"),
        ("category", "tabContent2-1"),
    ))
    second = ReachableCmsState(
        cms_state=second_state,
        state_label_segments=("Linux", "Compute"),
        mapping_key="Linux_tabContent2-1",
        source_evidence=ReachabilitySourceEvidence(
            region_value=None,
            region_href=None,
            software_value="Linux",
            software_href="#tabContent2",
            software_panel_id="tabContent2",
            software_visible=True,
            category_value="tabContent2-1",
            category_href="#tabContent2-1",
            category_panel_id="tabContent2-1",
            software_scoped_prefix=None,
        ),
        is_default=False,
    )
    software, category = base.filter_definitions_union
    return replace(
        base,
        filter_definitions_union=(
            replace(
                software,
                options=software.options + (
                    ReachabilityOption(
                        value="Linux",
                        label="Linux",
                        href="#tabContent2",
                        is_default=False,
                    ),
                ),
            ),
            replace(
                category,
                options=category.options + (
                    ReachabilityOption(
                        value="tabContent2-1",
                        label="Compute",
                        href="#tabContent2-1",
                        is_default=False,
                        parent_value="Linux",
                        parent_panel_id="tabContent2",
                    ),
                ),
            ),
        ),
        ordered_states=base.ordered_states + (second,),
    )


def test_builder_prepends_only_sha_bound_prefix_without_shared_content() -> None:
    reachability = _builder_reachability(_frozen_prefix_evidence())
    state = reachability.ordered_states[0]
    groups = FlexibleBuilder().build_complex_content_groups(
        reachability,
        {
            state.cms_state: {
                "shared_content": "",
                "software_scoped_prefix": _PREFIX_HTML,
                "content": _CATEGORY_HTML,
            }
        },
    )

    assert len(groups) == 1
    group = groups[0]
    assert "sharedContent" not in group
    assert group["content"].index("SOFTWARE PREFIX") < group[
        "content"
    ].index("CATEGORY PRICE")


def test_builder_rejects_prefix_without_frozen_state_evidence() -> None:
    reachability = _builder_reachability(None)
    state = reachability.ordered_states[0]

    with pytest.raises(ValueError, match="presence must equal"):
        FlexibleBuilder().build_complex_content_groups(
            reachability,
            {
                state.cms_state: {
                    "shared_content": "",
                    "software_scoped_prefix": _PREFIX_HTML,
                    "content": _CATEGORY_HTML,
                }
            },
        )


def test_builder_rejects_missing_prefix_required_by_frozen_evidence() -> None:
    reachability = _builder_reachability(_frozen_prefix_evidence())
    state = reachability.ordered_states[0]

    with pytest.raises(ValueError, match="presence must equal"):
        FlexibleBuilder().build_complex_content_groups(
            reachability,
            {
                state.cms_state: {
                    "shared_content": "",
                    "content": _CATEGORY_HTML,
                }
            },
        )


def test_builder_rejects_software_scoped_prefix_hash_drift() -> None:
    reachability = _builder_reachability(_frozen_prefix_evidence())
    state = reachability.ordered_states[0]

    with pytest.raises(ValueError, match="SHA-256 differs"):
        FlexibleBuilder().build_complex_content_groups(
            reachability,
            {
                state.cms_state: {
                    "shared_content": "",
                    "software_scoped_prefix": _PREFIX_HTML.replace(
                        "SOFTWARE PREFIX", "TAMPERED PREFIX"
                    ),
                    "content": _CATEGORY_HTML,
                }
            },
        )


def _formal_payload_with_prefix() -> tuple[
    SourceReachability,
    dict[str, object],
]:
    reachability = _builder_reachability(_frozen_prefix_evidence())
    state = reachability.ordered_states[0]
    builder = FlexibleBuilder()
    groups = builder.build_complex_content_groups(
        reachability,
        {
            state.cms_state: {
                "software_scoped_prefix": _PREFIX_HTML,
                "content": _CATEGORY_HTML,
            }
        },
    )
    payload = builder.build_flexible_page(
        {
            "Title": "Sample",
            "MetaTitle": "",
            "MetaDescription": "",
            "MetaKeywords": "",
            "Slug": "sample",
            "Language": "en-us",
            "MSServiceName": "sample",
        },
        [],
        {
            "baseContent": "",
            "contentGroups": groups,
            "strategy_type": "complex",
            "source_reachability": reachability,
        },
    )
    return reachability, payload


def test_persisted_validator_rechecks_source_bound_prefix_projection() -> None:
    reachability, payload = _formal_payload_with_prefix()
    expected = reachability.to_expected_reachability()

    valid = validate_flexible_state_contract(
        payload,
        expected_semantic_strategy="complex",
        expected_reachability=expected,
    )
    assert not valid.errors, valid.errors

    original = payload["contentGroups"][0]["content"]
    mutations = {
        "deleted": original.replace(_PREFIX_HTML, ""),
        "modified": original.replace(
            "SOFTWARE PREFIX", "TAMPERED PREFIX"
        ),
        "duplicated": _PREFIX_HTML + original,
    }
    expected_codes = {
        "deleted": "missing_or_modified_software_scoped_prefix",
        "modified": "missing_or_modified_software_scoped_prefix",
        "duplicated": "duplicate_software_scoped_prefix",
    }
    for name, content in mutations.items():
        candidate = {
            **payload,
            "contentGroups": [
                {
                    **payload["contentGroups"][0],
                    "content": content,
                }
            ],
        }
        result = validate_flexible_state_contract(
            candidate,
            expected_semantic_strategy="complex",
            expected_reachability=expected,
        )
        assert expected_codes[name] in {
            issue.code for issue in result.errors
        }


def test_expected_reachability_cannot_omit_prefix_expectations() -> None:
    reachability = _builder_reachability(_frozen_prefix_evidence())
    state = reachability.ordered_states[0].cms_state

    with pytest.raises(ValueError, match="align one-for-one"):
        type(reachability.to_expected_reachability())(
            filters=reachability.to_expected_reachability().filters,
            ordered_states=(state,),
            default_state=state,
        )


def test_persisted_validator_rejects_prefix_scope_leakage() -> None:
    reachability = _builder_reachability_with_unscoped_state()
    first, second = reachability.ordered_states
    builder = FlexibleBuilder()
    groups = builder.build_complex_content_groups(
        reachability,
        {
            first.cms_state: {
                "software_scoped_prefix": _PREFIX_HTML,
                "content": _CATEGORY_HTML,
            },
            second.cms_state: {"content": _CATEGORY_HTML},
        },
    )
    payload = builder.build_flexible_page(
        {
            "Title": "Sample",
            "MetaTitle": "",
            "MetaDescription": "",
            "MetaKeywords": "",
            "Slug": "sample",
            "Language": "en-us",
            "MSServiceName": "sample",
        },
        [],
        {
            "baseContent": "",
            "contentGroups": groups,
            "strategy_type": "complex",
            "source_reachability": reachability,
        },
    )
    leaked_group = payload["contentGroups"][1]
    leaked_group["content"] = _PREFIX_HTML + leaked_group["content"]

    result = validate_flexible_state_contract(
        payload,
        expected_semantic_strategy="complex",
        expected_reachability=reachability.to_expected_reachability(),
    )

    assert "software_scoped_prefix_scope_leakage" in {
        issue.code for issue in result.errors
    }


def test_bilingual_prefix_scope_drift_is_a_source_finding() -> None:
    reachability, en_payload = _formal_payload_with_prefix()
    zh_payload = {
        **en_payload,
        "language": "zh-cn",
    }
    zh_expected = reachability.to_expected_reachability()
    en_expected = type(zh_expected)(
        filters=zh_expected.filters,
        ordered_states=zh_expected.ordered_states,
        default_state=zh_expected.default_state,
        software_scoped_prefixes_by_state=(None,),
    )

    result = validate_bilingual_machine_identity(
        zh_payload,
        en_payload,
        zh_cn_expected_reachability=zh_expected,
        en_us_expected_reachability=en_expected,
        expected_semantic_strategy="complex",
    )

    assert "bilingual_source_reachability_drift" in {
        issue.code for issue in result.source_findings
    }
