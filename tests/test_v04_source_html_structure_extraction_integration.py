from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from src.core.extraction_coordinator import ExtractionCoordinator
from src.core.source_html_structure import AUDITOR_VERSION


ROOT = Path(__file__).resolve().parents[1]


class _FakeAuditResult:
    def __init__(self, value: dict[str, Any]) -> None:
        self._value = copy.deepcopy(value)

    @property
    def blocking_findings(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            finding
            for finding in self._value["findings"]
            if finding["blocking"]
        )

    @property
    def passed(self) -> bool:
        return not self.blocking_findings

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._value)


class _FakeAuditor:
    def __init__(self, finding: dict[str, Any] | None) -> None:
        self.finding = copy.deepcopy(finding)

    def audit(self, canonical_input: Any) -> _FakeAuditResult:
        findings = [copy.deepcopy(self.finding)] if self.finding else []
        return _FakeAuditResult({
            "schema_version": "1.0",
            "auditor_version": AUDITOR_VERSION,
            "source": {
                "product_key": canonical_input.product_key,
                "resource_key": canonical_input.resource_key,
                "language": canonical_input.language,
                "path": canonical_input.source_path.relative_to(ROOT).as_posix(),
                "sha256": canonical_input.source_sha256,
                "size_bytes": canonical_input.size_bytes,
            },
            "passed": not any(item["blocking"] for item in findings),
            "findings": findings,
        })


def _finding(*, blocking: bool) -> dict[str, Any]:
    return {
        "code": (
            "SOURCE_HTML_SELECTOR_EXTENDS_PAST_TAB_CONTROL"
            if blocking
            else "SOURCE_HTML_PRICING_SECTION_OVERWRAPS_SELECTOR_AND_QA"
        ),
        "severity": "error" if blocking else "warning",
        "blocking": blocking,
        "message": (
            "The source section boundary is ambiguous."
            if blocking
            else "A safe upstream wrapper correction is available."
        ),
        "evidence": [{
            "line": 42,
            "dom_path": "div.pricing-page-section",
            "description": "Fixture boundary evidence.",
        }],
        "safety_checks": (
            [
                "dom_exact_qa_or_owned_sla",
                "tab_control_boundary_comment",
            ]
            if blocking
            else [
                "dom_exact_qa_or_owned_sla",
                "intro_precedes_selector",
                "tab_control_boundary_comment",
                "raw_balanced_target_element",
                "standalone_closing_tag_line",
                "relocation_preserves_content_order",
            ]
        ),
        "upstream_suggestion": (
            None
            if blocking
            else {
                "action": "relocate_existing_closing_tag",
                "description": "Move the existing closing tag before pricing controls.",
                "from_line": 84,
                "before_line": 43,
            }
        ),
    }


def _coordinator(tmp_path: Path, *, deferred: bool = True) -> ExtractionCoordinator:
    return ExtractionCoordinator(
        str(tmp_path),
        deferred_validation=deferred,
    )


def test_single_product_freezes_and_replays_structure_audit(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path)

    extracted = coordinator.coordinate_extraction(
        "service-bus",
        "zh-cn",
        strategy="simple_static",
    )

    assert extracted.execution_succeeded
    metadata = extracted.sidecar["input_assurance"]["source_html_structure"]
    evidence_path = Path(metadata["evidence"]["path"])
    assert evidence_path.name == "service-bus.source-structure.json"
    assert evidence_path.is_file()
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert metadata == {
        "schema_version": evidence["schema_version"],
        "auditor_version": evidence["auditor_version"],
        "input_sha256": extracted.sidecar["normalized_input"]["sha256"],
        "evidence": {
            "path": str(evidence_path),
            "sha256": metadata["evidence"]["sha256"],
        },
    }

    validated = coordinator.validate_persisted_payload(extracted)

    assert validated.succeeded
    assert validated.sidecar["status"]["validation"] == "passed"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (
        ("metadata", None),
        ("missing", "source_html_structure_evidence_missing"),
        ("tampered", "source_html_structure_evidence_hash_mismatch"),
        ("identity", "source_html_structure_identity_replay_mismatch"),
    ),
)
def test_persisted_validation_rejects_missing_tampered_or_mismatched_audit(
    tmp_path: Path,
    mutation: str,
    expected_code: str | None,
) -> None:
    coordinator = _coordinator(tmp_path)
    extracted = coordinator.coordinate_extraction(
        "service-bus",
        "zh-cn",
        strategy="simple_static",
    )
    metadata = extracted.sidecar["input_assurance"]["source_html_structure"]
    evidence_path = Path(metadata["evidence"]["path"])

    if mutation == "metadata":
        sidecar = copy.deepcopy(extracted.sidecar)
        sidecar["input_assurance"].pop("source_html_structure")
        extracted.sidecar_path.write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    elif mutation == "missing":
        evidence_path.unlink()
    elif mutation == "tampered":
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["passed"] = not evidence["passed"]
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        sidecar = copy.deepcopy(extracted.sidecar)
        sidecar["input_assurance"]["source_html_structure"][
            "auditor_version"
        ] = "forged-auditor-v9"
        extracted.sidecar_path.write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if expected_code is None:
        with pytest.raises(
            ValueError,
            match="source_html_structure.*required property",
        ):
            coordinator.validate_persisted_payload(
                "service-bus",
                "zh-cn",
                payload_path=extracted.payload_path,
                sidecar_path=extracted.sidecar_path,
            )
        return

    validated = coordinator.validate_persisted_payload(
        "service-bus",
        "zh-cn",
        payload_path=extracted.payload_path,
        sidecar_path=extracted.sidecar_path,
    )
    assert validated.exit_code == 2
    error_codes = {
        issue["code"]
        for issue in validated.sidecar["validation"]["errors"]
    }
    assert expected_code in error_codes


def test_nonblocking_structure_finding_is_a_source_quality_warning(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path, deferred=False)
    coordinator.source_html_structure_auditor = _FakeAuditor(
        _finding(blocking=False)
    )

    result = coordinator.coordinate_extraction(
        "service-bus",
        "zh-cn",
        strategy="simple_static",
    )

    assert result.succeeded
    assert result.sidecar["input_assurance"]["status"] == "passed"
    assert "SOURCE_HTML_PRICING_SECTION_OVERWRAPS_SELECTOR_AND_QA" in {
        issue["code"] for issue in result.sidecar["validation"]["warnings"]
    }


def test_blocking_structure_finding_stops_before_payload_generation(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path)
    coordinator.source_html_structure_auditor = _FakeAuditor(
        _finding(blocking=True)
    )

    result = coordinator.coordinate_extraction(
        "service-bus",
        "zh-cn",
        strategy="simple_static",
    )

    assert not result.execution_succeeded
    assert result.payload_path is None
    assert result.sidecar["payload"] is None
    assert result.sidecar["input_assurance"]["status"] == "failed"
    assert result.sidecar["status"]["validation"] == "failed"
    assert {
        issue["code"] for issue in result.sidecar["validation"]["errors"]
    } == {"SOURCE_HTML_SELECTOR_EXTENDS_PAST_TAB_CONTROL"}
    assert result.sidecar["error"] == {
        "code": "SOURCE_HTML_STRUCTURE_BLOCKED",
        "stage": "input_assurance",
        "message": (
            "Source HTML Structure Audit found an ambiguous "
            "content-ownership boundary"
        ),
    }
    evidence_path = Path(
        result.sidecar["input_assurance"]["source_html_structure"][
            "evidence"
        ]["path"]
    )
    assert evidence_path.is_file()


@pytest.mark.parametrize(
    ("product", "language"),
    (
        ("virtual-wan", "zh-cn"),
        ("virtual-wan", "en-us"),
    ),
)
def test_latest_static_duplicate_ids_stop_payload_generation(
    tmp_path: Path,
    product: str,
    language: str,
) -> None:
    coordinator = _coordinator(tmp_path)

    result = coordinator.coordinate_extraction(
        product,
        language,
        strategy="simple_static",
    )

    assert not result.execution_succeeded
    assert result.exit_code == 1
    assert result.payload is None
    assert result.payload_path is None
    assert result.sidecar["payload"] is None
    assert result.sidecar["input_assurance"]["status"] == "failed"
    assert result.sidecar["status"]["validation"] == "failed"
    assert "SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT" in {
        issue["code"] for issue in result.sidecar["validation"]["errors"]
    }
    assert result.sidecar["error"]["code"] == "SOURCE_HTML_STRUCTURE_BLOCKED"

    evidence_path = Path(
        result.sidecar["input_assurance"]["source_html_structure"][
            "evidence"
        ]["path"]
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert "SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT" in {
        finding["code"] for finding in evidence["findings"]
    }


@pytest.mark.parametrize("language", ("zh-cn", "en-us"))
def test_latest_dns_fixed_source_generates_payload(
    tmp_path: Path,
    language: str,
) -> None:
    result = _coordinator(tmp_path).coordinate_extraction(
        "dns",
        language,
        strategy="simple_static",
    )

    assert result.execution_succeeded
    assert result.payload is not None
    assert result.payload_path is not None
    assert result.sidecar["input_assurance"]["status"] == "passed"
    assert result.sidecar["status"]["validation"] == "not_run"


@pytest.mark.parametrize("language", ("zh-cn", "en-us"))
def test_service_fabric_without_configured_boundary_fails_closed(
    tmp_path: Path,
    language: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = _coordinator(tmp_path)
    get_product_config = coordinator.product_manager.get_product_config

    def without_page_global_content(product_key: str) -> dict[str, Any]:
        definition = copy.deepcopy(get_product_config(product_key))
        definition["extraction"].pop("page_global_content", None)
        return definition

    monkeypatch.setattr(
        coordinator.product_manager,
        "get_product_config",
        without_page_global_content,
    )

    result = coordinator.coordinate_extraction(
        "service-fabric",
        language,
        strategy="simple_static",
    )

    assert not result.execution_succeeded
    assert result.exit_code == 1
    assert result.payload is None
    assert result.payload_path is None
    assert result.sidecar["payload"] is None
    assert result.sidecar["input_assurance"]["status"] == "passed"
    assert result.sidecar["status"]["validation"] == "not_run"
    assert result.sidecar["error"] == {
        "code": "ScopedSourceContentError",
        "stage": "extraction",
        "message": (
            "Unable to prove an intrinsic Simple page-global "
            "business-content boundary"
        ),
    }


@pytest.mark.parametrize(
    ("product", "language", "expected_codes"),
    (
        (
            "data-lake-storage",
            "zh-cn",
            {"SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT"},
        ),
        (
            "storage-files",
            "zh-cn",
            {"SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION"},
        ),
        (
            "container-apps",
            "zh-cn",
            {
                "SOURCE_HTML_CONTENT_WITHOUT_EXACT_COMMON_BOUNDARY",
                "SOURCE_HTML_PRICING_TABLE_SECTION_WITHOUT_OWN_HEADING",
            },
        ),
        (
            "sql-edge",
            "en-us",
            {"SOURCE_HTML_POST_SELECTOR_SUPPORT_SECTION_UNCLASSIFIED"},
        ),
    ),
)
def test_real_blocking_structure_finding_exits_without_payload(
    tmp_path: Path,
    product: str,
    language: str,
    expected_codes: set[str],
) -> None:
    coordinator = _coordinator(tmp_path)

    result = coordinator.coordinate_extraction(product, language)

    assert not result.execution_succeeded
    assert result.exit_code == 1
    assert result.payload is None
    assert result.payload_path is None
    assert result.sidecar["payload"] is None
    assert result.sidecar["input_assurance"]["status"] == "failed"
    assert result.sidecar["status"]["validation"] == "failed"
    assert expected_codes.issubset(
        {
            issue["code"]
            for issue in result.sidecar["validation"]["errors"]
        }
    )
    assert result.sidecar["error"]["code"] == "SOURCE_HTML_STRUCTURE_BLOCKED"
    assert not any(
        path.name == f"{product}.json" for path in tmp_path.rglob("*.json")
    )

    evidence_path = Path(
        result.sidecar["input_assurance"]["source_html_structure"][
            "evidence"
        ]["path"]
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence_codes = {
        finding["code"]
        for finding in evidence["findings"]
        if finding["blocking"]
    }
    assert expected_codes.issubset(evidence_codes)
    assert all(
        finding["upstream_suggestion"] is not None
        for finding in evidence["findings"]
        if finding["code"] in expected_codes
    )


@pytest.mark.parametrize("language", ("zh-cn", "en-us"))
def test_latest_event_hubs_footnote_stops_payload_generation(
    tmp_path: Path,
    language: str,
) -> None:
    coordinator = _coordinator(tmp_path)

    result = coordinator.coordinate_extraction("event-hubs", language)

    assert not result.execution_succeeded
    assert result.exit_code == 1
    assert result.payload is None
    assert result.payload_path is None
    assert result.sidecar["payload"] is None
    assert result.sidecar["input_assurance"]["status"] == "failed"
    assert result.sidecar["status"]["validation"] == "failed"
    assert {
        issue["code"] for issue in result.sidecar["validation"]["errors"]
    } == {"SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION"}
    assert result.sidecar["error"]["code"] == "SOURCE_HTML_STRUCTURE_BLOCKED"


def test_persisted_replay_cannot_bypass_a_new_blocking_finding(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path)
    coordinator.source_html_structure_auditor = _FakeAuditor(
        _finding(blocking=False)
    )
    extracted = coordinator.coordinate_extraction(
        "service-bus",
        "zh-cn",
        strategy="simple_static",
    )
    assert extracted.execution_succeeded

    coordinator.source_html_structure_auditor = _FakeAuditor(
        _finding(blocking=True)
    )
    validated = coordinator.validate_persisted_payload(extracted)

    assert validated.exit_code == 2
    assert "SOURCE_HTML_SELECTOR_EXTENDS_PAST_TAB_CONTROL" in {
        issue["code"]
        for issue in validated.sidecar["validation"]["errors"]
    }
