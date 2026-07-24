from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from src.pipeline.coordinator import PipelineCoordinator


def _item(*, page_model: str = "FlexibleContentPage") -> SimpleNamespace:
    return SimpleNamespace(
        page_model=page_model,
        product_key="databricks",
        language="zh-cn",
        version_key=None,
        normalized_sha256="a" * 64,
    )


def _coordinator(
    canonical: object,
    audit_document: dict[str, object],
) -> PipelineCoordinator:
    coordinator = object.__new__(PipelineCoordinator)
    coordinator._input_loader = Mock()
    coordinator._input_loader.load.return_value = canonical
    coordinator._source_html_structure_auditor = Mock()
    coordinator._source_html_structure_auditor.audit.return_value = (
        SimpleNamespace(to_dict=lambda: deepcopy(audit_document))
    )
    coordinator._source_reachability = Mock()
    coordinator._source_reachability.resolve.return_value = SimpleNamespace(
        findings=(),
        suppressed_options=(),
        unreachable_panel_ids=(),
    )
    coordinator._source_state_evidence = Mock()
    coordinator._source_state_evidence.resolve_dicts.return_value = ({
        "schema_version": "1.0",
        "code": "SOURCE_CONFIRMED_EMPTY_STATE",
        "category": "cms_state",
        "severity": "warning",
    },)
    return coordinator


def test_pipeline_projects_structure_findings_without_reinterpreting_them() -> None:
    canonical = object()
    source = {
        "product_key": "databricks",
        "resource_key": "databricks",
        "language": "zh-cn",
        "path": "data/prod-html/zh-cn/pricing/databricks.html",
        "sha256": "b" * 64,
        "size_bytes": 1234,
    }
    warning_suggestion = {
        "action": "relocate_existing_closing_tag",
        "description": "Move the existing closing tag before the selector.",
        "from_line": 22076,
        "before_line": 784,
    }
    audit_document: dict[str, object] = {
        "schema_version": "1.0",
        "auditor_version": "exact-owned-section-boundaries-v1",
        "source": source,
        "passed": False,
        "findings": [
            {
                "code": "SOURCE_SECTION_HIERARCHY_OVERWRAPPED",
                "severity": "warning",
                "blocking": False,
                "message": "A pricing section overwraps the selector.",
                "evidence": [{
                    "line": 215,
                    "dom_path": "html > body > div.pricing-page-section",
                    "description": "The section owns the selector.",
                }],
                "safety_checks": [
                    "visible_text_unchanged",
                    "table_identity_unchanged",
                ],
                "upstream_suggestion": warning_suggestion,
            },
            {
                "code": "SOURCE_SECTION_OWNERSHIP_AMBIGUOUS",
                "severity": "error",
                "blocking": True,
                "message": "Section ownership cannot be proven.",
                "evidence": [{
                    "line": 100,
                    "dom_path": "html > body > div",
                    "description": "Multiple boundaries are plausible.",
                }],
                "safety_checks": [],
                "upstream_suggestion": None,
            },
        ],
    }
    coordinator = _coordinator(canonical, audit_document)

    findings = coordinator._source_findings_for_item(_item())

    assert findings[0]["code"] == "SOURCE_CONFIRMED_EMPTY_STATE"
    assert findings[1:] == [
        {
            "schema_version": "1.0",
            "category": "source_html_structure",
            "auditor_version": "exact-owned-section-boundaries-v1",
            "source": source,
            "code": "SOURCE_SECTION_HIERARCHY_OVERWRAPPED",
            "severity": "warning",
            "blocking": False,
            "message": "A pricing section overwraps the selector.",
            "evidence": [{
                "line": 215,
                "dom_path": "html > body > div.pricing-page-section",
                "description": "The section owns the selector.",
            }],
            "safety_checks": [
                "visible_text_unchanged",
                "table_identity_unchanged",
            ],
            "upstream_suggestion": warning_suggestion,
        },
        {
            "schema_version": "1.0",
            "category": "source_html_structure",
            "auditor_version": "exact-owned-section-boundaries-v1",
            "source": source,
            "code": "SOURCE_SECTION_OWNERSHIP_AMBIGUOUS",
            "severity": "error",
            "blocking": True,
            "message": "Section ownership cannot be proven.",
            "evidence": [{
                "line": 100,
                "dom_path": "html > body > div",
                "description": "Multiple boundaries are plausible.",
            }],
            "safety_checks": [],
            "upstream_suggestion": None,
        },
    ]
    assert audit_document["findings"][0]["severity"] == "warning"
    assert audit_document["findings"][1]["blocking"] is True
    coordinator._source_html_structure_auditor.audit.assert_called_once_with(
        canonical
    )


def test_pipeline_replays_structure_audit_for_non_flexible_content() -> None:
    canonical = object()
    audit_document: dict[str, object] = {
        "schema_version": "1.0",
        "auditor_version": "exact-owned-section-boundaries-v1",
        "source": {
            "product_key": "icp-faq",
            "resource_key": "icp-faq",
            "language": "zh-cn",
            "path": "data/prod-html/zh-cn/SupportArticles/ICP/icp-faq.html",
            "sha256": "c" * 64,
            "size_bytes": 500,
        },
        "passed": False,
        "findings": [{
            "code": "SOURCE_SECTION_OWNERSHIP_AMBIGUOUS",
            "severity": "error",
            "blocking": True,
            "message": "Section ownership cannot be proven.",
            "evidence": [{
                "line": 42,
                "dom_path": "html > body > article > section",
                "description": "Multiple boundaries are plausible.",
            }],
            "safety_checks": [],
            "upstream_suggestion": None,
        }],
    }
    coordinator = _coordinator(canonical, audit_document)

    findings = coordinator._source_findings_for_item(
        _item(page_model="SupportArticlePage")
    )

    assert len(findings) == 1
    assert findings[0]["category"] == "source_html_structure"
    assert findings[0]["blocking"] is True
    coordinator._source_html_structure_auditor.audit.assert_called_once_with(
        canonical
    )
    coordinator._source_reachability.resolve.assert_not_called()
    coordinator._source_state_evidence.resolve_dicts.assert_not_called()
