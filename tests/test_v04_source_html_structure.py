from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.core.canonical_input import CanonicalHtmlInput
from src.core.source_html_structure import SourceHtmlStructureAuditor


ROOT = Path(__file__).resolve().parents[1]


def _canonical(tmp_path: Path, html: str, product: str = "example") -> CanonicalHtmlInput:
    raw = html.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    source = tmp_path / "data" / "prod-html" / "zh-cn" / "pricing" / f"{product}.html"
    return CanonicalHtmlInput(
        product_key=product,
        resource_key=product,
        language="zh-cn",
        source_path=source,
        normalized_path=source,
        source_sha256=digest,
        normalized_sha256=digest,
        expected_sha256=digest,
        raw_bytes=raw,
        text=html,
        has_utf8_bom=False,
        source_findings=(),
    )


def _audit(tmp_path: Path, html: str, product: str = "example"):
    return SourceHtmlStructureAuditor(tmp_path).audit(
        _canonical(tmp_path, html, product)
    )


def _canonical_repo_source(
    product: str,
    language: str,
) -> CanonicalHtmlInput:
    source = ROOT / "data" / "prod-html" / language / "pricing" / f"{product}.html"
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    return CanonicalHtmlInput(
        product_key=product,
        resource_key=product,
        language=language,
        source_path=source,
        normalized_path=source,
        source_sha256=digest,
        normalized_sha256=digest,
        expected_sha256=digest,
        raw_bytes=raw,
        text=raw.decode("utf-8", errors="strict"),
        has_utf8_bom=False,
        source_findings=(),
    )


@pytest.mark.parametrize(
    ("product", "language"),
    (
        ("dns", "zh-cn"),
        ("dns", "en-us"),
        ("service-fabric", "zh-cn"),
        ("service-fabric", "en-us"),
        ("virtual-wan", "zh-cn"),
        ("virtual-wan", "en-us"),
    ),
)
def test_real_repaired_static_page_global_ids_are_no_longer_blocking(
    product: str,
    language: str,
) -> None:
    result = SourceHtmlStructureAuditor(ROOT).audit(
        _canonical_repo_source(product, language)
    )

    assert result.passed is True
    assert "SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT" not in {
        finding.code for finding in result.findings
    }


@pytest.mark.parametrize("product", ("route-server", "sql-edge"))
@pytest.mark.parametrize("language", ("zh-cn", "en-us"))
def test_unproven_simple_boundaries_are_not_misclassified_as_confirmed(
    product: str,
    language: str,
) -> None:
    result = SourceHtmlStructureAuditor(ROOT).audit(
        _canonical_repo_source(product, language)
    )

    assert "SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT" not in {
        finding.code for finding in result.findings
    }


@pytest.mark.parametrize(
    ("product", "language", "expected"),
    (
        (
            "data-lake-storage",
            "zh-cn",
            {
                "SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT": (
                    8167,
                    8168,
                    8207,
                ),
            },
        ),
        (
            "event-hubs",
            "zh-cn",
            {
                "SOURCE_HTML_SELECTOR_EXTENDS_PAST_TAB_CONTROL": (
                    141,
                    465,
                    468,
                    699,
                ),
            },
        ),
        (
            "storage-files",
            "zh-cn",
            {
                "SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION": (
                    499,
                    521,
                    522,
                    541,
                    542,
                    562,
                ),
            },
        ),
        (
            "container-apps",
            "zh-cn",
            {
                "SOURCE_HTML_CONTENT_WITHOUT_EXACT_COMMON_BOUNDARY": (
                    214,
                    294,
                    319,
                    329,
                    390,
                    398,
                    434,
                    444,
                ),
                "SOURCE_HTML_PRICING_TABLE_SECTION_WITHOUT_OWN_HEADING": (
                    319,
                    329,
                    390,
                    398,
                    434,
                    444,
                ),
            },
        ),
        (
            "sql-edge",
            "en-us",
            {
                "SOURCE_HTML_POST_SELECTOR_SUPPORT_SECTION_UNCLASSIFIED": (
                    364,
                    370,
                    371,
                    376,
                ),
            },
        ),
    ),
)
def test_real_blocking_source_structure_findings_are_exact(
    product: str,
    language: str,
    expected: dict[str, tuple[int, ...]],
) -> None:
    result = SourceHtmlStructureAuditor(ROOT).audit(
        _canonical_repo_source(product, language)
    )
    findings = {
        finding.code: finding
        for finding in result.blocking_findings
        if finding.code in expected
    }

    assert set(findings) == set(expected)
    assert result.passed is False
    for code, expected_lines in expected.items():
        finding = findings[code]
        assert tuple(item.line for item in finding.evidence) == expected_lines
        assert finding.upstream_suggestion is not None
        assert finding.upstream_suggestion.description
        assert len(finding.safety_checks) >= 2

    schema = json.loads(
        (ROOT / "schemas/source-html-structure-audit-1.0.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(result.to_dict())


def test_event_hubs_en_common_sections_are_outside_formal_selector() -> None:
    result = SourceHtmlStructureAuditor(ROOT).audit(
        _canonical_repo_source("event-hubs", "en-us")
    )

    assert result.passed is True
    assert result.findings == ()


@pytest.mark.parametrize(
    "product",
    ("managed-instance", "sql-database"),
)
@pytest.mark.parametrize("language", ("zh-cn", "en-us"))
def test_real_faq_documentation_link_wrapper_is_exact(
    product: str,
    language: str,
) -> None:
    result = SourceHtmlStructureAuditor(ROOT).audit(
        _canonical_repo_source(product, language)
    )

    assert result.passed is True
    assert result.findings == ()


@pytest.mark.parametrize(
    "additional_material",
    (
        "<p>Arbitrary release notes outside the FAQ.</p>",
        "<style>.more-detail { color: black; }</style>",
        (
            "<p>See the <a href='/docs/product-faq/'>product FAQ</a>.</p>"
            "<div class='pricing-page-section'><h2>Support and SLA</h2>"
            "<p>Support terms.</p></div>"
        ),
        (
            "<p>See the <a href='/docs/notfaq/'>product FAQ</a>.</p>"
        ),
    ),
)
def test_faq_documentation_wrapper_lookalikes_fail_closed(
    additional_material: str,
    tmp_path: Path,
) -> None:
    html = f"""<html><body><div class="pure-content">
<div class="technical-azure-selector"><div>Pricing</div></div>
<div class="pricing-page-section">
  <div class="more-detail"><h2>FAQ</h2><p>One answer.</p></div>
  {additional_material}
</div>
</div></body></html>"""

    result = _audit(tmp_path, html, "faq-wrapper-negative-control")

    assert result.passed is False
    assert "SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT" in {
        finding.code for finding in result.blocking_findings
    }


@pytest.mark.parametrize(
    ("html", "forbidden_codes"),
    (
        (
            """<html><body><div class="pure-content">
<div class="technical-azure-selector"><div>Pricing</div></div>
<style>.faq { color: black; }</style>
<div class="pricing-page-section"><div class="more-detail">
<h2>FAQ</h2><p><a href="/docs/faq">FAQ docs</a></p>
</div></div></div></body></html>""",
            {"SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT"},
        ),
        (
            """<html><body><div class="pure-content">
<div class="technical-azure-selector">
<div class="tags-date"><div class="ms-date">Table footnote</div></div>
</div>
<div class="more-detail"><h2>FAQ</h2></div>
</div></body></html>""",
            {"SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION"},
        ),
        (
            """<html><body><div class="pure-content">
<div class="technical-azure-selector"><div>Pricing</div></div>
<div class="pricing-page-section"><h2>Requests</h2>
<table><tr><td>price</td></tr></table></div>
<div class="more-detail"><h2>FAQ</h2></div>
</div></body></html>""",
            {
                "SOURCE_HTML_CONTENT_WITHOUT_EXACT_COMMON_BOUNDARY",
                "SOURCE_HTML_PRICING_TABLE_SECTION_WITHOUT_OWN_HEADING",
            },
        ),
        (
            """<html><body><div class="pure-content">
<div class="technical-azure-selector"><div>Pricing</div></div>
<div class="pricing-page-section"><h2>Support and SLA</h2>
<p><a href="/support/contact">Support</a></p></div>
</div></body></html>""",
            {"SOURCE_HTML_POST_SELECTOR_SUPPORT_SECTION_UNCLASSIFIED"},
        ),
        (
            """<html><body><div class="pure-content">
<div class="technical-azure-selector"><div>Pricing</div></div>
<div class="pricing-page-section"><h2>Support</h2>
<p>General product support statement without a contact target.</p></div>
</div></body></html>""",
            {"SOURCE_HTML_POST_SELECTOR_SUPPORT_SECTION_UNCLASSIFIED"},
        ),
    ),
)
def test_narrow_structure_rules_do_not_accept_broader_lookalikes(
    html: str,
    forbidden_codes: set[str],
    tmp_path: Path,
) -> None:
    result = _audit(tmp_path, html, "negative-control")

    assert forbidden_codes.isdisjoint(
        {finding.code for finding in result.findings}
    )


@pytest.mark.parametrize(
    "product",
    ("service-bus", "api-management", "cloud-services"),
)
@pytest.mark.parametrize("language", ("zh-cn", "en-us"))
def test_duplicate_id_audit_does_not_cross_filter_state_panels(
    product: str,
    language: str,
) -> None:
    result = SourceHtmlStructureAuditor(ROOT).audit(
        _canonical_repo_source(product, language)
    )

    assert result.passed is True
    assert "SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT" not in {
        finding.code for finding in result.findings
    }


def test_duplicate_id_audit_excludes_site_templates_and_empty_ids(
    tmp_path: Path,
) -> None:
    html = """<html>
<body>
<nav><a id="site-template-id">Site navigation</a></nav>
<div class="pure-content">
  <div class="technical-azure-selector tab-control-selector">
    <div id="unique-business-id">Static pricing body</div>
    <div id="">Empty id is outside the non-empty-id rule.</div>
  </div>
  <div class="more-detail"><h2>FAQ</h2></div>
</div>
<footer id="site-template-id">Site footer</footer>
</body>
</html>
"""
    result = _audit(tmp_path, html, "static-template-scope")

    assert result.passed is True
    assert "SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT" not in {
        finding.code for finding in result.findings
    }


def test_duplicate_id_audit_skips_filtered_state_panels(
    tmp_path: Path,
) -> None:
    html = """<html>
<body>
<div class="pure-content">
  <div class="technical-azure-selector pricing-detail-tab">
    <select class="region-container"><option>Region</option></select>
    <div id="state-panel">Region one</div>
    <div id="state-panel">Region two</div>
  </div>
  <div class="more-detail"><h2>FAQ</h2></div>
</div>
</body>
</html>
"""
    result = _audit(tmp_path, html, "filtered-panels")

    assert result.passed is True
    assert "SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT" not in {
        finding.code for finding in result.findings
    }


def test_old_databricks_overwrapped_pricing_section_is_reported(
    tmp_path: Path,
) -> None:
    html = """<html>
<body>
<div class="pricing-page-section">
  <p>Introductory pricing explanation.</p>
  <!-- BEGIN: TAB-CONTROL -->
  <div class="technical-azure-selector pricing-detail-tab">
    <table><tr><td>price</td></tr></table>
  </div>
  <!-- END: TAB-CONTROL -->
  <div class="more-detail"><h2>FAQ</h2></div>
  <div class="pricing-page-section"><h2>支持和服务级别协议</h2></div>
</div>
</body>
</html>
"""
    result = _audit(tmp_path, html, "databricks")

    assert result.passed is True
    assert not result.blocking_findings
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.code == "SOURCE_HTML_PRICING_SECTION_OVERWRAPS_SELECTOR_AND_QA"
    assert finding.upstream_suggestion is not None
    assert finding.upstream_suggestion.from_line == 12
    assert finding.upstream_suggestion.before_line == 5


def test_fixed_databricks_and_ssis_structures_pass(tmp_path: Path) -> None:
    fixed_databricks = """<html>
<body>
<div class="pricing-page-section"><p>Introductory content.</p></div>
<!-- BEGIN: TAB-CONTROL -->
<div class="technical-azure-selector pricing-detail-tab"><table></table></div>
<!-- END: TAB-CONTROL -->
<div class="more-detail"><h2>FAQ</h2></div>
<div class="pricing-page-section"><h2>Support and SLA</h2></div>
</body>
</html>
"""
    fixed_ssis = """<html>
<body>
<!-- BEGIN: TAB-CONTROL -->
<div class="technical-azure-selector pricing-detail-tab">
  <table></table>
</div>
<!-- END: TAB-CONTROL -->
<div class="pricing-page-section">
  <div class="more-detail"><h2>常见问题</h2></div>
</div>
<div class="pricing-page-section"><h2>支持和服务级别协议</h2></div>
</body>
</html>
"""
    assert _audit(tmp_path, fixed_databricks).findings == ()
    assert _audit(tmp_path, fixed_ssis).findings == ()


def test_old_ssis_selector_past_end_boundary_is_reported(
    tmp_path: Path,
) -> None:
    html = """<html>
<body>
<!-- BEGIN: TAB-CONTROL -->
<div class="technical-azure-selector pricing-detail-tab">
  <table></table>
  <!-- END: TAB-CONTROL -->
  <div class="pricing-page-section">
    <div class="more-detail"><h2>FAQ</h2></div>
  </div>
  <div class="pricing-page-section"><h2>Service Level Agreement</h2></div>
</div>
</body>
</html>
"""
    result = _audit(tmp_path, html, "ssis")

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.code == "SOURCE_HTML_SELECTOR_EXTENDS_PAST_TAB_CONTROL"
    assert finding.upstream_suggestion is not None
    assert finding.upstream_suggestion.from_line == 11
    assert finding.upstream_suggestion.before_line == 7


def test_api_management_sla_table_cells_are_not_headings(
    tmp_path: Path,
) -> None:
    html = """<html>
<body>
<!-- BEGIN: TAB-CONTROL -->
<div class="technical-azure-selector pricing-detail-tab">
  <div class="pricing-page-section">
    <table><tr><th>SLA</th><td>99.95%</td></tr></table>
  </div>
</div>
<!-- END: TAB-CONTROL -->
<div class="more-detail"><h2>FAQ</h2></div>
<div class="pricing-page-section"><h2>Support and SLA</h2></div>
</body>
</html>
"""
    result = _audit(tmp_path, html, "api-management")

    assert result.passed is True
    assert result.findings == ()


def test_result_is_deterministic_and_matches_strict_schema(tmp_path: Path) -> None:
    html = """<html>
<body>
<!-- BEGIN: TAB-CONTROL -->
<div class="technical-azure-selector pricing-detail-tab">
  <table></table>
  <!-- END: TAB-CONTROL -->
  <div class="more-detail"><h2>FAQ</h2></div>
</div>
</body>
</html>
"""
    canonical = _canonical(tmp_path, html, "ssis")
    auditor = SourceHtmlStructureAuditor(tmp_path)
    first = auditor.audit(canonical).to_dict()
    second = auditor.audit(canonical).to_dict()
    schema = json.loads(
        (ROOT / "schemas/source-html-structure-audit-1.0.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert first == second
    assert "timestamp" not in json.dumps(first)
    assert "run_id" not in json.dumps(first)
    Draft202012Validator(schema).validate(first)
