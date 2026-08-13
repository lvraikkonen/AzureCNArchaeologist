from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup, Tag

import src.core.scoped_source_content as scoped
from src.core.extraction_coordinator import ExtractionCoordinator
from src.core.product_manager import ProductManager
from src.utils.html.cleaner import clean_html_content
from src.utils.media.image_processor import preprocess_image_paths


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_BATCH = "20260813T013534Z-b9e91703"
S5_BOUNDARY = "sole_direct_static_business_wrapper_before_common_sections"
S6_BOUNDARY = "sole_inert_singleton_selector_target_before_common_sections"

EXPECTED_REPAIR_IDENTITIES = {
    "service-fabric": {
        "zh-cn": {
            "source": "70b0a22305d1b0f247e2cee58316228dc95097738784746c191a292c12044774",
            "wire": "c3c3545c5ba0d7f89a2e950318a180a40c17c82e90e7cb11843a484d3e0a5709",
        },
        "en-us": {
            "source": "b713ff78c7c33f0ed4eba52f33abd3ab483855283dc697cc4062de91453234e6",
            "wire": "d1c2b91607201cad1430c775d20b72da90e5f8de60f762fc3bb10da48e26e839",
        },
    },
    "azure-defender": {
        "zh-cn": {
            "source": "8c54da45436efad13d21e4dc43d4c1761223521762881758049d2b9aca838878",
            "wire": "bba52ba3d5cd8c271c7664c794d690908df4ea3c2b6f0144e67edb75cbfc39ab",
        },
        "en-us": {
            "source": "52f0906900bfd5471a084cdfbd641feb782afc14a43a6354c39a7fa5e9463e91",
            "wire": "96a0a041c890f322d6a71d77cf835c479f67424ff2ffca4c1f8001b58c3cb9bc",
        },
    },
}

PROTECTED_PRODUCTS = (
    "ip-addresses",
    "service-bus",
    "site-recovery",
    "scheduler",
    "traffic-manager",
    "azure-policy",
    "advisor",
    "azure-update-management-center",
    "azure-migrate",
    "cdn",
    "active-directory-b2c",
    "multi-factor-authentication",
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _s5_page(
    wrapper: str = (
        "<div><h2>Pricing</h2><p>Business body</p>"
        "<table><tr><td>1</td></tr></table></div>"
    ),
    *,
    description: str = (
        '<div class="pricing-page-section"><p>Description</p></div>'
    ),
    common: str = (
        '<div class="pricing-page-section">'
        "<h2>Support &amp; SLA</h2><p>Terms</p></div>"
    ),
    before_wrapper: str = "",
    after_wrapper: str = "",
) -> BeautifulSoup:
    return BeautifulSoup(
        (
            '<div class="pure-content">'
            '<div class="common-banner"><h1>Banner</h1></div>'
            f"{description}{before_wrapper}{wrapper}{after_wrapper}{common}"
            "</div>"
        ),
        "html.parser",
    )


def _s6_page() -> BeautifulSoup:
    return BeautifulSoup(
        """
        <div class="pure-content">
          <div class="common-banner"><h1>Banner</h1></div>
          <div class="pricing-page-section"><p>Description</p></div>
          <div class="technical-azure-selector pricing-detail-tab tab-dropdown">
            <div class="tab-container-container">
              <div class="dropdown-container software-kind-container">
                <div class="dropdown-box os-tab-nav hidden-sm hidden-xs">
                  <ol class="tab-items">
                    <li class="active"><a href="javascript:void(0)" data-href="#tabContent1">One</a></li>
                  </ol>
                </div>
                <select id="software-box">
                  <option value="one" data-href="#tabContent1" selected>One</option>
                </select>
              </div>
            </div>
            <div class="tab-content">
              <div id="tabContent1" class="tab-control-container tab-active">
                <h2>Pricing</h2><table id="price"><tr><td>1</td></tr></table>
              </div>
            </div>
          </div>
          <div class="pricing-page-section"><h2>Support &amp; SLA</h2><p>Terms</p></div>
        </div>
        """,
        "html.parser",
    )


def _fragment_policy(boundary: str, source_html: str) -> dict[str, object]:
    identity = {
        "fragment_count": 1,
        "source_html_sha256": _sha(source_html),
        "wire_html_sha256": _sha(clean_html_content(source_html)),
    }
    return {
        "product_key": "fixture",
        "extraction": {
            "semantic_strategy": "simple_static",
            "page_global_content": {
                "source_boundary": boundary,
                "expected_by_language": {
                    "zh-cn": copy.deepcopy(identity),
                    "en-us": copy.deepcopy(identity),
                },
            },
        },
    }


def _extract_s5(soup: BeautifulSoup):
    return scoped.extract_direct_static_business_wrapper_page_global_content(
        soup
    )


def _extract_s6(soup: BeautifulSoup):
    return scoped.extract_inert_singleton_selector_target_page_global_content(
        soup
    )


def test_s5_exact_wrapper_and_direct_scan_noise() -> None:
    soup = _s5_page(
        before_wrapper=(
            "<!-- before --><script>ignored()</script><style>.x{}</style>"
            "<template><p>ignored</p></template><tags></tags>"
        ),
        after_wrapper="<!-- after --><script>ignored()</script>",
    )
    fragment = _extract_s5(soup)
    wrapper = soup.select_one(".pure-content > div:not([class])")
    assert isinstance(wrapper, Tag)
    assert fragment.source_boundary == S5_BOUNDARY
    assert fragment.fragment_count == 1
    assert fragment.source_html == str(wrapper)

    definition = _fragment_policy(S5_BOUNDARY, str(wrapper))
    assert scoped.resolve_page_global_base_content(
        soup, definition, language="en-us"
    ) == clean_html_content(str(wrapper))


@pytest.mark.parametrize(
    ("soup",),
    [
        (_s5_page(wrapper=""),),
        (_s5_page(wrapper="<div>one</div><div>two</div>"),),
        (_s5_page(wrapper='<section><div>nested</div></section>'),),
        (
            _s5_page(
                wrapper=(
                    "<div><h2>Pricing</h2>"
                    '<div class="more-detail"><h2>FAQ</h2></div></div>'
                )
            ),
        ),
        (_s5_page(description='<div class="description">Description</div>'),),
        (_s5_page(common='<div class="pricing-page-section"><p>Other</p></div>'),),
        (_s5_page(wrapper='<div><select><option>One</option></select></div>'),),
        (
            _s5_page(
                wrapper=(
                    '<div><div class="technical-azure-selector">body</div></div>'
                )
            ),
        ),
        (_s5_page(wrapper='<div><input type="radio"/></div>'),),
    ],
)
def test_s5_rejects_ambiguous_ownership_and_active_controls(
    soup: BeautifulSoup,
) -> None:
    with pytest.raises(scoped.ScopedSourceContentError):
        _extract_s5(soup)


@pytest.mark.parametrize(
    "wrapper",
    [
        '<div><p id="">body</p></div>',
        '<div><p id="dup">one</p><p id="dup">two</p></div>',
        '<div id="outside"><p>body</p></div>',
    ],
)
def test_s5_rejects_empty_duplicate_or_page_colliding_ids(
    wrapper: str,
) -> None:
    soup = _s5_page(wrapper=wrapper)
    if 'id="outside"' in wrapper:
        outside = soup.new_tag("span", id="outside")
        soup.select_one(".common-banner").append(outside)
    with pytest.raises(scoped.ScopedSourceContentError):
        _extract_s5(soup)


def test_s5_frozen_identity_rejects_narrow_wide_and_internal_drift() -> None:
    soup = _s5_page()
    fragment = _extract_s5(soup)
    definition = _fragment_policy(S5_BOUNDARY, fragment.source_html)

    for replacement in (
        "<div><h2>Pricing</h2></div>",
        (
            '<div class="pricing-page-section"><p>Description</p></div>'
            + fragment.source_html
        ),
        fragment.source_html.replace("</div>", "<script>x()</script></div>", 1),
    ):
        drifted = _s5_page(wrapper=replacement)
        with pytest.raises(scoped.ScopedSourceContentError):
            scoped.resolve_page_global_base_content(
                drifted, definition, language="en-us"
            )

    for key, value in (
        ("fragment_count", 2),
        ("source_html_sha256", "0" * 64),
        ("wire_html_sha256", "0" * 64),
    ):
        drifted_definition = copy.deepcopy(definition)
        drifted_definition["extraction"]["page_global_content"][
            "expected_by_language"
        ]["en-us"][key] = value
        with pytest.raises(scoped.ScopedSourceContentError):
            scoped.resolve_page_global_base_content(
                soup, drifted_definition, language="en-us"
            )


def test_s6_singleton_presentations_emit_only_the_owned_target() -> None:
    soup = _s6_page()
    fragment = _extract_s6(soup)
    target = soup.find(id="tabContent1")
    assert isinstance(target, Tag)
    assert fragment.source_boundary == S6_BOUNDARY
    assert fragment.fragment_count == 1
    assert fragment.source_html == str(target)

    definition = _fragment_policy(S6_BOUNDARY, str(target))
    wire = scoped.resolve_page_global_base_content(
        soup, definition, language="en-us"
    )
    assert wire == clean_html_content(str(target))
    assert "software-box" not in wire
    assert "tab-items" not in wire
    assert "Support &amp; SLA" not in wire
    assert "Description" not in wire


@pytest.mark.parametrize(
    "mutation",
    [
        "desktop_zero",
        "desktop_two",
        "desktop_unselected",
        "mobile_zero",
        "mobile_two",
        "mobile_unselected",
        "identity_disagreement",
        "target_disagreement",
        "external_ref",
        "target_outside",
        "second_target",
        "region_control",
        "nested_radio",
        "target_id_missing",
        "target_id_empty",
        "target_id_mismatch",
        "target_id_duplicate",
        "descendant_id_empty",
        "descendant_id_duplicate",
        "ui_target_id_collision",
        "common_not_adjacent",
    ],
)
def test_s6_rejects_non_singleton_or_cross_boundary_shapes(
    mutation: str,
) -> None:
    soup = _s6_page()
    selector = soup.select_one("div.technical-azure-selector")
    assert isinstance(selector, Tag)
    desktop = selector.select_one("ol.tab-items")
    mobile = selector.select_one("select")
    target = selector.find(id="tabContent1")
    assert isinstance(desktop, Tag)
    assert isinstance(mobile, Tag)
    assert isinstance(target, Tag)

    if mutation == "desktop_zero":
        desktop.find("li").decompose()
    elif mutation == "desktop_two":
        desktop.append(BeautifulSoup('<li><a data-href="#tabContent2">Two</a></li>', "html.parser").li)
    elif mutation == "desktop_unselected":
        desktop.find("li").attrs.pop("class", None)
    elif mutation == "mobile_zero":
        mobile.find("option").decompose()
    elif mutation == "mobile_two":
        mobile.append(BeautifulSoup('<option data-href="#tabContent2">Two</option>', "html.parser").option)
    elif mutation == "mobile_unselected":
        mobile.find("option").attrs.pop("selected", None)
    elif mutation == "identity_disagreement":
        mobile.find("option").string = "Different"
    elif mutation == "target_disagreement":
        mobile.find("option")["data-href"] = "#different"
    elif mutation == "external_ref":
        desktop.find("a")["data-href"] = "https://example.test/x"
        mobile.find("option")["data-href"] = "https://example.test/x"
    elif mutation == "target_outside":
        target.extract()
        soup.select_one(".pure-content").append(target)
    elif mutation == "second_target":
        target.parent.append(BeautifulSoup('<div id="tabContent2" class="tab-control-container">Two</div>', "html.parser").div)
    elif mutation == "region_control":
        selector.append(BeautifulSoup('<div class="region-container"><select><option selected>One</option></select></div>', "html.parser").div)
    elif mutation == "nested_radio":
        selector.append(BeautifulSoup('<input type="radio" checked/>', "html.parser").input)
    elif mutation == "target_id_missing":
        target.attrs.pop("id")
    elif mutation == "target_id_empty":
        target["id"] = ""
    elif mutation == "target_id_mismatch":
        target["id"] = "different"
    elif mutation == "target_id_duplicate":
        target.parent.append(BeautifulSoup('<div id="tabContent1"></div>', "html.parser").div)
    elif mutation == "descendant_id_empty":
        target.append(BeautifulSoup('<span id="">bad</span>', "html.parser").span)
    elif mutation == "descendant_id_duplicate":
        target.append(BeautifulSoup('<span id="dup">one</span><span id="dup">two</span>', "html.parser"))
    elif mutation == "ui_target_id_collision":
        desktop["id"] = "price"
    elif mutation == "common_not_adjacent":
        common = selector.find_next_sibling("div")
        common.insert_before(BeautifulSoup('<div>unowned</div>', "html.parser").div)
    else:  # pragma: no cover - parameter list is closed-world
        raise AssertionError(mutation)

    with pytest.raises(scoped.ScopedSourceContentError):
        _extract_s6(soup)


def test_s6_frozen_identity_rejects_fragment_and_hash_drift() -> None:
    soup = _s6_page()
    fragment = _extract_s6(soup)
    definition = _fragment_policy(S6_BOUNDARY, fragment.source_html)
    target = soup.find(id="tabContent1")
    assert isinstance(target, Tag)
    target.find("table").decompose()
    with pytest.raises(scoped.ScopedSourceContentError):
        scoped.resolve_page_global_base_content(
            soup, definition, language="en-us"
        )

    pristine = _s6_page()
    for key, value in (
        ("fragment_count", 2),
        ("source_html_sha256", "0" * 64),
        ("wire_html_sha256", "0" * 64),
    ):
        drifted_definition = copy.deepcopy(
            _fragment_policy(
                S6_BOUNDARY, str(pristine.find(id="tabContent1"))
            )
        )
        drifted_definition["extraction"]["page_global_content"][
            "expected_by_language"
        ]["en-us"][key] = value
        with pytest.raises(scoped.ScopedSourceContentError):
            scoped.resolve_page_global_base_content(
                pristine, drifted_definition, language="en-us"
            )


@pytest.mark.parametrize("product_key", ["service-fabric", "azure-defender"])
@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_real_repair_boundaries_are_exact_and_payloads_validate(
    product_key: str,
    language: str,
    tmp_path: Path,
) -> None:
    manager = ProductManager()
    definition = manager.get_product_config(product_key)
    source_path = manager.get_html_file_path(product_key, language)
    assert source_path is not None
    soup = BeautifulSoup(
        Path(source_path).read_bytes().decode("utf-8-sig"), "html.parser"
    )
    preprocess_image_paths(soup)
    fragment = _extract_s5(soup) if product_key == "service-fabric" else _extract_s6(soup)
    expected = EXPECTED_REPAIR_IDENTITIES[product_key][language]
    assert fragment.fragment_count == 1
    assert fragment.source_html_sha256 == expected["source"]
    assert _sha(clean_html_content(fragment.source_html)) == expected["wire"]
    assert definition["extraction"]["page_global_content"]["source_boundary"] == (
        S5_BOUNDARY if product_key == "service-fabric" else S6_BOUNDARY
    )

    result = ExtractionCoordinator(str(tmp_path)).coordinate_extraction(
        product_key, language
    )
    assert result.exit_code == 0
    assert result.payload is not None
    assert result.sidecar["status"]["validation"] == "passed"
    assert _sha(result.payload["baseContent"]) == expected["wire"]


@pytest.mark.parametrize("product_key", PROTECTED_PRODUCTS)
@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_protected_v054_payloads_remain_exact(
    product_key: str,
    language: str,
    tmp_path: Path,
) -> None:
    reference_path = (
        ROOT
        / "runs"
        / REFERENCE_BATCH
        / "outputs"
        / language
        / "pricing"
        / f"{product_key}.json"
    )
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    result = ExtractionCoordinator(str(tmp_path)).coordinate_extraction(
        product_key, language
    )
    assert result.exit_code == 0
    assert result.payload == reference


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_virtual_wan_and_event_grid_dispositions_do_not_change(
    language: str,
    tmp_path: Path,
) -> None:
    virtual_wan = ExtractionCoordinator(str(tmp_path / "vw")).coordinate_extraction(
        "virtual-wan", language
    )
    assert virtual_wan.exit_code != 0
    assert virtual_wan.sidecar["error"]["code"] == "SOURCE_HTML_STRUCTURE_BLOCKED"
    assert virtual_wan.sidecar["error"]["message"] == (
        "Source HTML Structure Audit found an ambiguous content-ownership boundary"
    )
    structure = json.loads(
        (
            tmp_path
            / "vw"
            / "diagnostics"
            / language
            / "pricing"
            / "virtual-wan.source-structure.json"
        ).read_text(encoding="utf-8")
    )
    finding = structure["findings"][0]
    assert finding["code"] == "SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT"
    assert "'tabContent1' on 2 elements" in finding["message"]
    assert len(finding["evidence"]) == 2

    event_grid = ExtractionCoordinator(str(tmp_path / "eg")).coordinate_extraction(
        "event-grid", language
    )
    assert event_grid.exit_code != 0
    assert event_grid.sidecar["error"]["code"] == "known_unsupported"
