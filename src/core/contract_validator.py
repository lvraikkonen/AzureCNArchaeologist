"""Executable CMS contracts: JSON Schema plus rules for nested JSON-string fields."""

from __future__ import annotations

import json
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .cms_state_contract import (
    CmsState,
    CmsStateIssue,
    ExpectedCmsReachability,
    validate_bilingual_machine_identity,
    validate_flexible_state_contract,
)
from .product_catalog import sha256_file


_HTML_ELEMENT_START = re.compile(r"<[A-Za-z][A-Za-z0-9:_-]*(?:\s[^<>]*?)?/?>")
_MATERIAL_PLAIN_TEXT_FRAGMENT_LENGTH = 32


def _contains_complete_business_fragment(
    container: str,
    fragment: str,
) -> bool:
    """Return whether ``container`` owns a complete, material field fragment.

    Payload fields are serialized independently, so exact field-string
    containment is the stable fragment boundary.  A short plain-text label can
    legitimately recur in unrelated content, however, and is not enough by
    itself to prove duplicate ownership.  Complete HTML fragments and
    substantial plain-text fields remain blocking.
    """

    normalized_container = container.strip()
    normalized_fragment = fragment.strip()
    if not normalized_container or not normalized_fragment:
        return False
    if normalized_fragment not in normalized_container:
        return False
    if normalized_fragment == normalized_container:
        return True
    return (
        len(normalized_fragment) >= _MATERIAL_PLAIN_TEXT_FRAGMENT_LENGTH
        or _HTML_ELEMENT_START.search(normalized_fragment) is not None
    )


@dataclass(frozen=True)
class ContractIssue:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


@dataclass(frozen=True)
class ContractValidationResult:
    errors: list[ContractIssue]
    warnings: list[ContractIssue]
    source_findings: list[ContractIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors

    def to_dict(
        self,
        *,
        include_source_findings: bool = False,
    ) -> dict[str, list[dict[str, str]]]:
        """Project issues without changing the Diagnostic Sidecar 1.2 shape.

        Existing callers receive only ``errors`` and ``warnings``.  Evidence
        writers that own a source-findings field can opt in explicitly.
        """

        result = {
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }
        if include_source_findings:
            result["source_findings"] = [
                issue.to_dict() for issue in self.source_findings
            ]
        return result


CONTRACTS = {
    "FlexibleContentPage": ("flexible-content-page-1.1.schema.json", "1.1"),
    "SupportArticlePage": ("support-article-page-1.0.schema.json", "1.0"),
    "DiagnosticSidecar": ("diagnostic-sidecar-1.2.schema.json", "1.2"),
    "ReconstructionParseability": (
        "reconstruction-parseability-1.0.schema.json",
        "1.0",
    ),
    "SourceHtmlStructureAudit": (
        "source-html-structure-audit-1.0.schema.json",
        "1.0",
    ),
}


class ContractValidator:
    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()
        self.schema_root = self.root / "schemas"

    def contract_metadata(self, page_model: str) -> dict[str, str]:
        filename, version = CONTRACTS[page_model]
        path = self.schema_root / filename
        return {"name": page_model, "version": version, "schema_sha256": sha256_file(path)}

    def validate(
        self,
        payload: Any,
        page_model: str,
        expected_ms_service: str | None = None,
        *,
        expected_semantic_strategy: str | None = None,
        expected_reachability: ExpectedCmsReachability | None = None,
        expected_base_content: str | None = None,
        source_confirmed_empty_states: Collection[CmsState] = (),
    ) -> ContractValidationResult:
        if page_model not in ("FlexibleContentPage", "SupportArticlePage"):
            raise ValueError(f"Unsupported page model: {page_model}")
        errors = self._schema_errors(payload, page_model)
        warnings: list[ContractIssue] = []
        source_findings: list[ContractIssue] = []
        if page_model == "FlexibleContentPage":
            semantic_errors, semantic_findings = self._validate_flexible_semantics(
                payload,
                expected_ms_service,
                expected_semantic_strategy=expected_semantic_strategy,
                expected_reachability=expected_reachability,
                expected_base_content=expected_base_content,
                source_confirmed_empty_states=source_confirmed_empty_states,
            )
            errors.extend(semantic_errors)
            source_findings.extend(semantic_findings)
        else:
            errors.extend(self._validate_support_semantics(payload))
            warnings.extend(self._support_quality_warnings(payload))
            if expected_reachability is not None:
                errors.append(ContractIssue(
                    "reachability_not_applicable",
                    "$.expected_reachability",
                    "CMS reachability applies only to FlexibleContentPage.",
                ))
            if expected_base_content is not None:
                errors.append(ContractIssue(
                    "base_content_expectation_not_applicable",
                    "$.baseContent",
                    "Expected baseContent applies only to FlexibleContentPage.",
                ))
            if source_confirmed_empty_states:
                errors.append(ContractIssue(
                    "source_empty_state_exception_not_applicable",
                    "$.source_confirmed_empty_states",
                    "Source-confirmed empty CMS states apply only to FlexibleContentPage.",
                ))
        return ContractValidationResult(errors, warnings, source_findings)

    def validate_bilingual_pair(
        self,
        zh_cn_payload: Any,
        en_us_payload: Any,
        *,
        zh_cn_expected_reachability: ExpectedCmsReachability | None = None,
        en_us_expected_reachability: ExpectedCmsReachability | None = None,
        expected_semantic_strategy: str | None = None,
        zh_cn_source_confirmed_empty_states: Collection[CmsState] = (),
        en_us_source_confirmed_empty_states: Collection[CmsState] = (),
    ) -> ContractValidationResult:
        """Compare bilingual machine identities, defaults, and state order."""

        result = validate_bilingual_machine_identity(
            zh_cn_payload,
            en_us_payload,
            zh_cn_expected_reachability=zh_cn_expected_reachability,
            en_us_expected_reachability=en_us_expected_reachability,
            expected_semantic_strategy=expected_semantic_strategy,
            zh_cn_source_confirmed_empty_states=(
                zh_cn_source_confirmed_empty_states
            ),
            en_us_source_confirmed_empty_states=(
                en_us_source_confirmed_empty_states
            ),
        )
        return ContractValidationResult(
            [_contract_issue(issue) for issue in result.errors],
            [],
            [_contract_issue(issue) for issue in result.source_findings],
        )

    def validate_sidecar(self, sidecar: dict[str, Any]) -> ContractValidationResult:
        return ContractValidationResult(self._schema_errors(sidecar, "DiagnosticSidecar"), [])

    def validate_reconstruction_parseability(
        self, evidence: dict[str, Any]
    ) -> ContractValidationResult:
        return ContractValidationResult(
            self._schema_errors(evidence, "ReconstructionParseability"), []
        )

    def validate_source_html_structure(
        self, evidence: dict[str, Any]
    ) -> ContractValidationResult:
        return ContractValidationResult(
            self._schema_errors(evidence, "SourceHtmlStructureAudit"), []
        )

    def _schema_errors(self, value: Any, contract_name: str) -> list[ContractIssue]:
        filename, _ = CONTRACTS[contract_name]
        schema = json.loads((self.schema_root / filename).read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        issues = []
        for error in sorted(
            validator.iter_errors(value),
            key=lambda item: tuple(str(part) for part in item.absolute_path),
        ):
            path = "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path)
            issues.append(ContractIssue("schema_validation", path, error.message))
        return issues

    def _validate_flexible_semantics(
        self,
        payload: Any,
        expected_ms_service: str | None,
        *,
        expected_semantic_strategy: str | None,
        expected_reachability: ExpectedCmsReachability | None,
        expected_base_content: str | None,
        source_confirmed_empty_states: Collection[CmsState],
    ) -> tuple[list[ContractIssue], list[ContractIssue]]:
        issues: list[ContractIssue] = []
        if not isinstance(payload, Mapping):
            state_result = validate_flexible_state_contract(
                payload,
                expected_semantic_strategy=expected_semantic_strategy,
                expected_reachability=expected_reachability,
                source_confirmed_empty_states=source_confirmed_empty_states,
            )
            return (
                [_contract_issue(issue) for issue in state_result.errors],
                [_contract_issue(issue) for issue in state_result.source_findings],
            )

        forbidden = {"validation", "extraction_metadata", "error", "source_file", "source_url", "quality_score"}
        for key in sorted(forbidden.intersection(payload)):
            issues.append(ContractIssue("diagnostic_field_in_payload", f"$.{key}", "Diagnostic fields are forbidden in a Business Payload."))

        page_config_value = payload.get("pageConfig", {})
        page_config = page_config_value if isinstance(page_config_value, Mapping) else {}
        navigation_identifier = str(page_config.get("leftNavigationIdentifier", "")).strip()
        if not navigation_identifier:
            issues.append(ContractIssue("missing_ms_service", "$.pageConfig.leftNavigationIdentifier", "leftNavigationIdentifier must be the non-empty ms.service value."))
        if expected_ms_service is not None:
            if not isinstance(expected_ms_service, str) or not expected_ms_service.strip():
                issues.append(ContractIssue("missing_source_ms_service", "$.pageConfig.leftNavigationIdentifier", "The source HTML does not declare a non-empty ms.service value."))
            elif navigation_identifier != expected_ms_service.strip():
                issues.append(ContractIssue("ms_service_mismatch", "$.pageConfig.leftNavigationIdentifier", "leftNavigationIdentifier does not match the source ms.service value."))

        if expected_base_content is not None:
            actual_base_content = payload.get("baseContent")
            if actual_base_content != expected_base_content:
                issues.append(ContractIssue(
                    "page_global_base_content_mismatch",
                    "$.baseContent",
                    "baseContent differs from the exact source- and Product-Definition-authorized page-global wire content.",
                ))
            elif expected_base_content:
                groups_value = payload.get("contentGroups", [])
                groups = (
                    groups_value
                    if isinstance(groups_value, list)
                    else []
                )
                for index, group in enumerate(groups):
                    if not isinstance(group, Mapping):
                        continue
                    for field in ("content", "sharedContent"):
                        value = group.get(field)
                        if (
                            isinstance(value, str)
                            and (
                                _contains_complete_business_fragment(
                                    value,
                                    expected_base_content,
                                )
                                or _contains_complete_business_fragment(
                                    expected_base_content,
                                    value,
                                )
                            )
                        ):
                            issues.append(ContractIssue(
                                "page_global_base_content_duplicated",
                                f"$.contentGroups[{index}].{field}",
                                "Authorized page-global baseContent and state-scoped content must remain fragment-disjoint.",
                            ))
                sections_value = payload.get("commonSections", [])
                sections = (
                    sections_value
                    if isinstance(sections_value, list)
                    else []
                )
                for index, section in enumerate(sections):
                    if not isinstance(section, Mapping):
                        continue
                    value = section.get("content")
                    if (
                        isinstance(value, str)
                        and (
                            _contains_complete_business_fragment(
                                value,
                                expected_base_content,
                            )
                            or _contains_complete_business_fragment(
                                expected_base_content,
                                value,
                            )
                        )
                    ):
                        issues.append(ContractIssue(
                            "page_global_base_content_duplicated",
                            f"$.commonSections[{index}].content",
                            "Authorized page-global baseContent and common-section content must remain fragment-disjoint.",
                        ))

        state_result = validate_flexible_state_contract(
            payload,
            expected_semantic_strategy=expected_semantic_strategy,
            expected_reachability=expected_reachability,
            source_confirmed_empty_states=source_confirmed_empty_states,
        )
        issues.extend(_contract_issue(issue) for issue in state_result.errors)
        findings = [_contract_issue(issue) for issue in state_result.source_findings]
        return issues, findings

    @staticmethod
    def _validate_support_semantics(payload: Any) -> list[ContractIssue]:
        if not isinstance(payload, Mapping):
            return []
        return [
            ContractIssue("empty_required_content", f"$.{key}", f"{key} must contain non-whitespace content.")
            for key in ("title", "slug", "pageType", "mainContent")
            if isinstance(payload.get(key), str) and not payload[key].strip()
        ]

    @staticmethod
    def _support_quality_warnings(payload: Any) -> list[ContractIssue]:
        if not isinstance(payload, Mapping):
            return []
        optional = ("metaTitle", "metaDescription", "metaKeywords", "lastModifiedDate", "articleDescription")
        return [
            ContractIssue("empty_optional_content", f"$.{key}", f"{key} is empty in the source content.")
            for key in optional
            if isinstance(payload.get(key), str) and not payload[key].strip()
        ]


def _contract_issue(issue: CmsStateIssue) -> ContractIssue:
    return ContractIssue(issue.code, issue.path, issue.message)
