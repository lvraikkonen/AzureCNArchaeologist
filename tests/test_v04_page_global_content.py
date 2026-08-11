from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator

from src.core.extraction_coordinator import ExtractionCoordinator
from src.core.product_manager import ProductManager
from src.core.scoped_source_content import (
    POST_SELECTOR_PAGE_GLOBAL_BOUNDARY,
    STATIC_FORMAL_SELECTOR_PAGE_GLOBAL_BOUNDARY,
    ScopedSourceContentError,
    extract_post_selector_page_global_content,
    extract_static_formal_selector_page_global_content,
    resolve_page_global_base_content,
)
from src.strategies.complex_content_strategy import ComplexContentStrategy
from src.utils.content.section_extractor import SectionExtractor
from src.utils.html.cleaner import clean_html_content


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CLOUD = {
    "zh-cn": {
        "text": "IP 地址选项 为您的云服务部署保留公共 IP 地址。",
        "source_html_sha256": (
            "722632961a14e2820de2dc94b396877eaa253c18a19d779c2461bf4f0332afee"
        ),
        "wire_html_sha256": (
            "6f33121990b29b5c3197790202be399bf2fde8e68b7f593bd552e6ccd8accb4e"
        ),
    },
    "en-us": {
        "text": (
            "IP Address Options Reserve public IP addresses for your "
            "Azure Cloud Services deployments."
        ),
        "source_html_sha256": (
            "872768eb38de2257d1d56fd6aa2b9b895497885a3c17ebc22947f1b41fff6819"
        ),
        "wire_html_sha256": (
            "0ab769fa88a4d9d8578d73f612bd43b92cde53c39d0a3ffb8a8640384655c2fb"
        ),
    },
}
EXPECTED_SERVICE_BUS = {
    "zh-cn": {
        "source_html_sha256": (
            "95f29033d0c710e71260fdc926f96c885c124dabb16672939a5a832fd7b9ede5"
        ),
        "wire_html_sha256": (
            "9d9cce97d44e236e58d7461aa4c5425f061afabcdfbcacab8c65bae7ae725374"
        ),
        "cms_html_sha256": (
            "be16aa693da63b364093256528454a1f16b96fdca711b7be20523f243bcd83e4"
        ),
        "live_tick_count": 22,
    },
    "en-us": {
        "source_html_sha256": (
            "8f05d669c13e2daa02d968b50dcf5ec31f6f342f2c9e1d8f67131682637488ea"
        ),
        "wire_html_sha256": (
            "aa02090d85e9bac31e7c23e3f7d2863c2e6d39db78d7443f2d80d28f5b3e2cca"
        ),
        "cms_html_sha256": (
            "8833f9a6b4746d7bfc4747a9d42d82698c93e96fa5551f89de0e5a87d287639e"
        ),
        "live_tick_count": 21,
    },
}
EXPECTED_VMSS = {
    "zh-cn": {
        "source_html_sha256": (
            "04036263e4cbf1b248e4cea6b5cd74daaf6f343f3958ddd991e85611aa73fdc6"
        ),
        "wire_html_sha256": (
            "b575343117569fd82ad5507c811407b8cb14ad7dff5838d500b722e6df1e8464"
        ),
    },
    "en-us": {
        "source_html_sha256": (
            "b25cbaed9350dc78c6b4c28b8453da371f5d7d5dc48ae70201cfa47d5caabc5d"
        ),
        "wire_html_sha256": (
            "d520cd0ddcd5eb83c0e629666aaae239ce0ee9c5a09705ffefe22da293d508f7"
        ),
    },
}
EXPECTED_MACHINE_LEARNING = {
    "zh-cn": {
        "heading": "其他信息",
        "source_html_sha256": (
            "602acf7a66f99a06baa640ecb7874fc33f6d747225d108d970d9a1a373aa3e73"
        ),
        "wire_html_sha256": (
            "1e630cd1326d8978b3eceaf922cdeb095d1183be6bcbed7d5647c8956d94042b"
        ),
    },
    "en-us": {
        "heading": "Additional Information",
        "source_html_sha256": (
            "6cc3b2aa0e551ae0303e39be6a152d02435aa9750dcf9da974ea15fbba9f6095"
        ),
        "wire_html_sha256": (
            "0be010ea99529cc4d3311e3dc2de71c8bb422b6a92a01f4267a3aed5cff91249"
        ),
    },
}


def _page(
    candidate: str = (
        '<div class="pricing-page-section">'
        "<h2>Global pricing note</h2><p>Applies to every state.</p>"
        "</div>"
    ),
    boundary: str = (
        '<div class="pricing-page-section">'
        '<div class="more-detail"><h2>FAQ</h2><p>Answer</p></div>'
        "</div>"
    ),
    include_sla: bool = True,
) -> BeautifulSoup:
    sla = (
        '<div class="pricing-page-section">'
        "<h2>Support &amp; SLA</h2><p>Terms</p>"
        "</div>"
        if include_sla
        else ""
    )
    return BeautifulSoup(
        (
            '<div class="pure-content">'
            '<div class="technical-azure-selector pricing-detail-tab">'
            '<div class="tab-panel" id="tabContent1">￥1</div>'
            "</div>"
            f"{candidate}{boundary}"
            f"{sla}"
            "</div>"
        ),
        "html.parser",
    )


def _policy_for(soup: BeautifulSoup, language: str = "en-us") -> dict:
    fragment = extract_post_selector_page_global_content(soup)
    assert fragment is not None
    wire_html = clean_html_content(fragment.source_html)
    return {
        "source_boundary": POST_SELECTOR_PAGE_GLOBAL_BOUNDARY,
        "expected_by_language": {
            "zh-cn": {
                "fragment_count": fragment.fragment_count,
                "source_html_sha256": fragment.source_html_sha256,
                "wire_html_sha256": hashlib.sha256(
                    wire_html.encode("utf-8")
                ).hexdigest(),
            },
            "en-us": {
                "fragment_count": fragment.fragment_count,
                "source_html_sha256": fragment.source_html_sha256,
                "wire_html_sha256": hashlib.sha256(
                    wire_html.encode("utf-8")
                ).hexdigest(),
            },
        },
    }


def _strategy(policy: dict | None) -> ComplexContentStrategy:
    strategy = object.__new__(ComplexContentStrategy)
    extraction: dict[str, object] = {"semantic_strategy": "complex"}
    if policy is not None:
        extraction["page_global_content"] = policy
    strategy.product_config = {
        "product_key": "example",
        "extraction": extraction,
    }
    return strategy


def test_post_selector_global_content_uses_exact_sibling_boundaries() -> None:
    soup = _page()
    fragment = extract_post_selector_page_global_content(soup)

    assert fragment is not None
    assert fragment.source_boundary == POST_SELECTOR_PAGE_GLOBAL_BOUNDARY
    assert fragment.fragment_count == 1
    assert "Global pricing note" in fragment.source_html
    assert "FAQ" not in fragment.source_html
    assert "Support &amp; SLA" not in fragment.source_html
    assert fragment.source_html_sha256 == hashlib.sha256(
        fragment.source_html.encode("utf-8")
    ).hexdigest()


def test_complex_strategy_requires_closed_world_product_authority() -> None:
    soup = _page()
    with pytest.raises(
        ScopedSourceContentError,
        match="Unclassified visible content",
    ):
        _strategy(None)._extract_page_global_base_content(
            soup,
            language="en-us",
        )

    policy = _policy_for(soup)
    wire_html = _strategy(policy)._extract_page_global_base_content(
        soup,
        language="en-us",
    )
    assert "Global pricing note" in wire_html
    assert "FAQ" not in wire_html

    drifted = copy.deepcopy(policy)
    drifted["expected_by_language"]["en-us"][
        "source_html_sha256"
    ] = "0" * 64
    with pytest.raises(
        ScopedSourceContentError,
        match="source HTML differs",
    ):
        _strategy(drifted)._extract_page_global_base_content(
            soup,
            language="en-us",
        )


@pytest.mark.parametrize(
    ("candidate", "boundary", "include_sla", "message"),
    [
        (
            '<div class="pricing-page-section" style="display:none">'
            "<h2>Hidden</h2><p>Not visible</p></div>",
            (
                '<div class="pricing-page-section">'
                '<div class="more-detail"><h2>FAQ</h2></div></div>'
            ),
            True,
            "Hidden pricing-page-section",
        ),
        (
            '<div class="pricing-page-section">'
            "<h2>Global</h2><nav>Navigation</nav></div>",
            (
                '<div class="pricing-page-section">'
                '<div class="more-detail"><h2>FAQ</h2></div></div>'
            ),
            True,
            "interactive, or navigation",
        ),
        (
            '<div class="pricing-page-section">'
            "<p>No owned heading</p></div>",
            (
                '<div class="pricing-page-section">'
                '<div class="more-detail"><h2>FAQ</h2></div></div>'
            ),
            True,
            "must begin with its own",
        ),
        (
            '<div class="pricing-page-section">'
            "<h2>Global</h2><p>Note</p></div>",
            (
                '<div class="pricing-page-section">'
                "<p>Unclassified prefix</p>"
                '<div class="more-detail"><h2>FAQ</h2></div></div>'
            ),
            True,
            "also contains unclassified",
        ),
        (
            '<div class="pricing-page-section">'
            "<h2>Global</h2><p>Note</p></div>",
            "",
            False,
            "no exact following FAQ/SLA",
        ),
    ],
)
def test_post_selector_global_content_fails_closed(
    candidate: str,
    boundary: str,
    include_sla: bool,
    message: str,
) -> None:
    with pytest.raises(ScopedSourceContentError, match=message):
        extract_post_selector_page_global_content(
            _page(candidate, boundary, include_sla)
        )


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_cloud_services_bilingual_fragment_is_exact_and_not_qa(
    language: str,
) -> None:
    source = (
        ROOT
        / "data"
        / "prod-html"
        / language
        / "pricing"
        / "cloud-services.html"
    )
    soup = BeautifulSoup(source.read_bytes(), "html.parser")
    fragment = extract_post_selector_page_global_content(soup)
    expected = EXPECTED_CLOUD[language]

    assert fragment is not None
    assert fragment.fragment_count == 1
    assert fragment.source_html_sha256 == expected["source_html_sha256"]
    wire_html = clean_html_content(fragment.source_html)
    assert (
        hashlib.sha256(wire_html.encode("utf-8")).hexdigest()
        == expected["wire_html_sha256"]
    )
    assert (
        " ".join(
            BeautifulSoup(wire_html, "html.parser")
            .get_text(" ", strip=True)
            .split()
        )
        == expected["text"]
    )
    assert "more-detail" not in wire_html
    assert "Support &amp; SLA" not in wire_html
    assert "支持和服务级别协议" not in wire_html


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_machine_learning_page_global_content_is_frozen(
    language: str,
) -> None:
    manager = ProductManager()
    definition = manager.get_product_config("machine-learning")
    source_path = manager.get_html_file_path("machine-learning", language)
    assert source_path is not None
    soup = BeautifulSoup(Path(source_path).read_bytes(), "html.parser")

    fragment = extract_post_selector_page_global_content(soup)
    expected = EXPECTED_MACHINE_LEARNING[language]
    assert fragment is not None
    assert fragment.source_boundary == POST_SELECTOR_PAGE_GLOBAL_BOUNDARY
    assert fragment.fragment_count == 1
    assert fragment.source_html_sha256 == expected["source_html_sha256"]

    wire_html = resolve_page_global_base_content(
        soup,
        definition,
        language=language,
    )
    assert (
        hashlib.sha256(wire_html.encode("utf-8")).hexdigest()
        == expected["wire_html_sha256"]
    )
    wire_soup = BeautifulSoup(wire_html, "html.parser")
    heading = wire_soup.find(["h1", "h2", "h3", "h4", "h5", "h6"])
    assert heading is not None
    assert heading.get_text(" ", strip=True) == expected["heading"]
    assert "more-detail" not in wire_html


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_vmss_page_global_content_is_frozen(language: str) -> None:
    manager = ProductManager()
    definition = manager.get_product_config("virtual-machine-scale-sets")
    source_path = manager.get_html_file_path(
        "virtual-machine-scale-sets",
        language,
    )
    assert source_path is not None
    soup = BeautifulSoup(Path(source_path).read_bytes(), "html.parser")

    fragment = extract_post_selector_page_global_content(soup)
    assert fragment is not None
    assert fragment.source_boundary == POST_SELECTOR_PAGE_GLOBAL_BOUNDARY
    assert fragment.fragment_count == 1
    assert (
        fragment.source_html_sha256
        == EXPECTED_VMSS[language]["source_html_sha256"]
    )
    wire_html = resolve_page_global_base_content(
        soup,
        definition,
        language=language,
    )
    assert (
        hashlib.sha256(wire_html.encode("utf-8")).hexdigest()
        == EXPECTED_VMSS[language]["wire_html_sha256"]
    )


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_service_bus_static_page_global_content_is_frozen(
    language: str,
) -> None:
    manager = ProductManager()
    definition = manager.get_product_config("service-bus")
    source_path = manager.get_html_file_path("service-bus", language)
    assert source_path is not None
    soup = BeautifulSoup(Path(source_path).read_bytes(), "html.parser")

    fragment = extract_static_formal_selector_page_global_content(soup)
    assert fragment is not None
    assert (
        fragment.source_boundary
        == STATIC_FORMAL_SELECTOR_PAGE_GLOBAL_BOUNDARY
    )
    assert (
        fragment.source_html_sha256
        == EXPECTED_SERVICE_BUS[language]["source_html_sha256"]
    )
    source_wire_html = clean_html_content(fragment.source_html)
    assert hashlib.sha256(source_wire_html.encode("utf-8")).hexdigest() == (
        EXPECTED_SERVICE_BUS[language]["wire_html_sha256"]
    )
    assert "✓" not in source_wire_html
    assert len(BeautifulSoup(source_wire_html, "html.parser").select(
        "i.icon-tick"
    )) == EXPECTED_SERVICE_BUS[language]["live_tick_count"]

    wire_html = resolve_page_global_base_content(
        soup,
        definition,
        language=language,
    )
    assert (
        hashlib.sha256(wire_html.encode("utf-8")).hexdigest()
        == EXPECTED_SERVICE_BUS[language]["cms_html_sha256"]
    )
    assert wire_html.count("✓") == (
        EXPECTED_SERVICE_BUS[language]["live_tick_count"]
    )
    assert not BeautifulSoup(wire_html, "html.parser").select(
        "i.icon-tick"
    )
    assert wire_html.count("icon-tick") == 4


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_service_bus_final_cms_payload_materializes_tick_semantics(
    language: str,
    tmp_path: Path,
) -> None:
    result = ExtractionCoordinator(str(tmp_path)).coordinate_extraction(
        "service-bus",
        language,
    )

    assert result.exit_code == 0
    assert result.payload is not None
    assert result.sidecar["status"]["validation"] == "passed"
    base_content = result.payload["baseContent"]
    assert base_content.count("✓") == (
        EXPECTED_SERVICE_BUS[language]["live_tick_count"]
    )
    assert not BeautifulSoup(base_content, "html.parser").select(
        "i.icon-tick"
    )
    assert base_content.count("icon-tick") == 4


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_api_management_current_page_global_content_is_empty(
    language: str,
) -> None:
    manager = ProductManager()
    definition = manager.get_product_config("api-management")
    source_path = manager.get_html_file_path("api-management", language)
    assert source_path is not None
    soup = BeautifulSoup(Path(source_path).read_bytes(), "html.parser")

    assert (
        resolve_page_global_base_content(
            soup,
            definition,
            language=language,
        )
        == ""
    )


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_dns_static_page_global_content_has_globally_unique_source_ids(
    language: str,
) -> None:
    manager = ProductManager()
    definition = manager.get_product_config("dns")
    source_path = manager.get_html_file_path("dns", language)
    assert source_path is not None
    soup = BeautifulSoup(Path(source_path).read_bytes(), "html.parser")

    identified = soup.select("[id]")
    assert len(identified) == len(
        {str(node.get("id", "")).strip() for node in identified}
    )
    assert resolve_page_global_base_content(
        soup,
        definition,
        language=language,
    )


@pytest.mark.parametrize("product_key", ["advisor", "azure-policy"])
@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_simple_pages_without_proven_business_boundary_fail_closed(
    product_key: str,
    language: str,
) -> None:
    manager = ProductManager()
    definition = manager.get_product_config(product_key)
    source_path = manager.get_html_file_path(product_key, language)
    assert source_path is not None
    soup = BeautifulSoup(Path(source_path).read_bytes(), "html.parser")

    # These historical pages expose only a broad page container. Treating it
    # as baseContent would duplicate common Banner/ProductDescription/Qa data.
    assert soup.select_one(".common-banner") is not None
    with pytest.raises(
        ScopedSourceContentError,
        match=(
            "^Unable to prove an intrinsic Simple page-global "
            "business-content boundary$"
        ),
    ):
        resolve_page_global_base_content(
            soup,
            definition,
            language=language,
        )


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_ip_addresses_uses_direct_pricing_body_without_common_duplication(
    language: str,
) -> None:
    manager = ProductManager()
    definition = manager.get_product_config("ip-addresses")
    source_path = manager.get_html_file_path("ip-addresses", language)
    assert source_path is not None
    soup = BeautifulSoup(Path(source_path).read_bytes(), "html.parser")

    pricing_sections = soup.select(
        ".pure-content > div.pricing-page-section"
    )
    assert len(pricing_sections) == 3
    expected = clean_html_content(str(pricing_sections[0]))

    base_content = resolve_page_global_base_content(
        soup,
        definition,
        language=language,
    )
    assert base_content == expected
    assert "more-detail" not in base_content
    assert "支持和服务级别协议" not in base_content
    assert "Support &amp; SLA" not in base_content

    common_sections = SectionExtractor().extract_all_sections(soup)
    assert [section["sectionType"] for section in common_sections] == [
        "Banner",
        "Qa",
    ]
    assert all(
        section["content"] != base_content
        for section in common_sections
    )


def test_ip_addresses_extracts_and_validates_as_simple_page(
    tmp_path: Path,
) -> None:
    coordinator = ExtractionCoordinator(
        str(tmp_path),
        deferred_validation=True,
    )
    extracted = coordinator.coordinate_extraction(
        "ip-addresses",
        "zh-cn",
        strategy="simple_static",
    )

    assert extracted.execution_succeeded
    assert extracted.payload_path is not None
    payload = json.loads(
        extracted.payload_path.read_text(encoding="utf-8")
    )
    assert payload["baseContent"]
    assert payload["contentGroups"] == []
    assert [
        section["sectionType"] for section in payload["commonSections"]
    ] == ["Banner", "Qa"]
    assert extracted.sidecar["status"]["validation"] == "not_run"

    validated = coordinator.validate_persisted_payload(extracted)
    assert validated.succeeded
    assert validated.sidecar["status"]["validation"] == "passed"


def test_region_filter_can_authorize_nonempty_page_global_content() -> None:
    soup = _page()
    definition = {
        "product_key": "region-example",
        "extraction": {
            "semantic_strategy": "region_filter",
            "page_global_content": _policy_for(soup),
        },
    }

    wire_html = resolve_page_global_base_content(
        soup,
        definition,
        language="en-us",
    )
    assert "Global pricing note" in wire_html
    assert "FAQ" not in wire_html


def test_product_definition_closes_page_global_content_configuration() -> None:
    manager = ProductManager()
    definition = manager.get_product_config("cloud-services")
    policy = definition["extraction"]["page_global_content"]
    assert (
        policy["source_boundary"]
        == POST_SELECTOR_PAGE_GLOBAL_BOUNDARY
    )
    assert set(policy["expected_by_language"]) == {"zh-cn", "en-us"}

    schema = json.loads(
        (
            ROOT / "schemas" / "product-definition-1.1.schema.json"
        ).read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    for semantic_strategy in (
        "simple_static",
        "region_filter",
        "complex",
    ):
        flexible = copy.deepcopy(definition)
        flexible["extraction"][
            "semantic_strategy"
        ] = semantic_strategy
        assert list(validator.iter_errors(flexible)) == []

    support = copy.deepcopy(
        manager.get_product_config("icp-faq")
    )
    support["extraction"]["page_global_content"] = copy.deepcopy(policy)
    assert list(validator.iter_errors(support))

    unknown = copy.deepcopy(definition)
    unknown["extraction"]["page_global_content"]["unknown"] = True
    assert list(validator.iter_errors(unknown))


@pytest.mark.parametrize(
    ("product_key", "strategy", "tampered_base_content"),
    [
        ("service-bus", "simple_static", ""),
        ("api-management", "region_filter", "<p>Injected</p>"),
    ],
)
def test_persisted_validation_rejects_base_content_tampering(
    tmp_path: Path,
    product_key: str,
    strategy: str,
    tampered_base_content: str,
) -> None:
    coordinator = ExtractionCoordinator(
        str(tmp_path),
        deferred_validation=True,
    )
    extracted = coordinator.coordinate_extraction(
        product_key,
        "zh-cn",
        strategy=strategy,
    )
    assert extracted.execution_succeeded
    assert extracted.sidecar["status"]["validation"] == "not_run"
    assert extracted.payload_path is not None

    payload = json.loads(
        extracted.payload_path.read_text(encoding="utf-8")
    )
    if product_key == "api-management":
        assert payload["baseContent"] == ""
    else:
        assert payload["baseContent"]
    payload["baseContent"] = tampered_base_content
    extracted.payload_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    rejected = coordinator.validate_persisted_payload(extracted)

    assert rejected.exit_code == 2
    assert rejected.sidecar["status"]["validation"] == "failed"
    assert "page_global_base_content_mismatch" in {
        issue["code"]
        for issue in rejected.sidecar["validation"]["errors"]
    }
