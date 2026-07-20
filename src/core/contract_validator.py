"""Executable CMS contracts: JSON Schema plus rules for nested JSON-string fields."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .product_catalog import sha256_file


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

    @property
    def passed(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, list[dict[str, str]]]:
        return {
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


CONTRACTS = {
    "FlexibleContentPage": ("flexible-content-page-1.1.schema.json", "1.1"),
    "SupportArticlePage": ("support-article-page-1.0.schema.json", "1.0"),
    "DiagnosticSidecar": ("diagnostic-sidecar-1.1.schema.json", "1.1"),
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
        payload: dict[str, Any],
        page_model: str,
        expected_ms_service: str | None = None,
    ) -> ContractValidationResult:
        if page_model not in ("FlexibleContentPage", "SupportArticlePage"):
            raise ValueError(f"Unsupported page model: {page_model}")
        errors = self._schema_errors(payload, page_model)
        warnings: list[ContractIssue] = []
        if page_model == "FlexibleContentPage":
            errors.extend(self._validate_flexible_semantics(payload, expected_ms_service))
        else:
            errors.extend(self._validate_support_semantics(payload))
            warnings.extend(self._support_quality_warnings(payload))
        return ContractValidationResult(errors, warnings)

    def validate_sidecar(self, sidecar: dict[str, Any]) -> ContractValidationResult:
        return ContractValidationResult(self._schema_errors(sidecar, "DiagnosticSidecar"), [])

    def _schema_errors(self, value: dict[str, Any], contract_name: str) -> list[ContractIssue]:
        filename, _ = CONTRACTS[contract_name]
        schema = json.loads((self.schema_root / filename).read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        issues = []
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path)):
            path = "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path)
            issues.append(ContractIssue("schema_validation", path, error.message))
        return issues

    def _validate_flexible_semantics(
        self,
        payload: dict[str, Any],
        expected_ms_service: str | None,
    ) -> list[ContractIssue]:
        issues: list[ContractIssue] = []
        forbidden = {"validation", "extraction_metadata", "error", "source_file", "source_url", "quality_score"}
        for key in sorted(forbidden.intersection(payload)):
            issues.append(ContractIssue("diagnostic_field_in_payload", f"$.{key}", "Diagnostic fields are forbidden in a Business Payload."))

        page_config = payload.get("pageConfig", {})
        navigation_identifier = str(page_config.get("leftNavigationIdentifier", "")).strip()
        if not navigation_identifier:
            issues.append(ContractIssue("missing_ms_service", "$.pageConfig.leftNavigationIdentifier", "leftNavigationIdentifier must be the non-empty ms.service value."))
        if expected_ms_service is not None:
            if not expected_ms_service.strip():
                issues.append(ContractIssue("missing_source_ms_service", "$.pageConfig.leftNavigationIdentifier", "The source HTML does not declare a non-empty ms.service value."))
            elif navigation_identifier != expected_ms_service.strip():
                issues.append(ContractIssue("ms_service_mismatch", "$.pageConfig.leftNavigationIdentifier", "leftNavigationIdentifier does not match the source ms.service value."))

        definitions: dict[str, set[str]] = {}
        raw_filters = page_config.get("filtersJsonConfig", "")
        try:
            filters = json.loads(raw_filters)
        except (TypeError, json.JSONDecodeError) as error:
            issues.append(ContractIssue("invalid_nested_json", "$.pageConfig.filtersJsonConfig", str(error)))
            filters = {}
        if isinstance(filters, dict):
            if set(filters) != {"filterDefinitions"} or not isinstance(filters.get("filterDefinitions"), list):
                issues.append(ContractIssue("invalid_filter_config", "$.pageConfig.filtersJsonConfig", "Expected only a filterDefinitions array."))
            for index, definition in enumerate(filters.get("filterDefinitions", [])):
                path = f"$.pageConfig.filtersJsonConfig.filterDefinitions[{index}]"
                if not isinstance(definition, dict):
                    issues.append(ContractIssue("invalid_filter_definition", path, "Filter definition must be an object."))
                    continue
                allowed = {"filterKey", "filterType", "displayName", "options"}
                extras = set(definition) - allowed
                missing = allowed - set(definition)
                if extras or missing:
                    issues.append(ContractIssue("invalid_filter_fields", path, f"Only filterKey/filterType/displayName/options are allowed; missing={sorted(missing)}, extra={sorted(extras)}"))
                filter_key = definition.get("filterKey")
                filter_type = definition.get("filterType")
                if not isinstance(filter_type, str) or filter_type != filter_type.lower() or filter_type not in {"dropdown", "tab"}:
                    issues.append(ContractIssue("invalid_filter_type", f"{path}.filterType", "filterType must be lowercase dropdown or tab."))
                values: set[str] = set()
                options = definition.get("options", [])
                if not isinstance(options, list):
                    issues.append(ContractIssue("invalid_filter_options", f"{path}.options", "options must be an array."))
                    continue
                for option_index, option in enumerate(options):
                    option_path = f"{path}.options[{option_index}]"
                    if not isinstance(option, dict) or set(option) - {"value", "label", "href"} or not {"value", "label"}.issubset(option):
                        issues.append(ContractIssue("invalid_filter_option_fields", option_path, "Only value/label/href are permitted and value/label are required."))
                        continue
                    if not all(isinstance(option.get(field, ""), str) for field in ("value", "label", "href")):
                        issues.append(ContractIssue("invalid_filter_option_value", option_path, "value/label/href must be strings."))
                    values.add(option.get("value", ""))
                if isinstance(filter_key, str):
                    if filter_key in definitions:
                        issues.append(ContractIssue("duplicate_filter_key", f"{path}.filterKey", f"Duplicate filter key: {filter_key}"))
                    definitions[filter_key] = values

        for group_index, group in enumerate(payload.get("contentGroups", [])):
            path = f"$.contentGroups[{group_index}].filterCriteriaJson"
            try:
                criteria = json.loads(group.get("filterCriteriaJson", ""))
            except (TypeError, json.JSONDecodeError) as error:
                issues.append(ContractIssue("invalid_nested_json", path, str(error)))
                continue
            if not isinstance(criteria, list):
                issues.append(ContractIssue("invalid_filter_criteria", path, "Filter criteria must be an array."))
                continue
            for criterion_index, criterion in enumerate(criteria):
                criterion_path = f"{path}[{criterion_index}]"
                if not isinstance(criterion, dict) or set(criterion) != {"filterKey", "matchValues"}:
                    issues.append(ContractIssue("invalid_filter_criterion_fields", criterion_path, "Criterion must contain only filterKey and matchValues."))
                    continue
                key, value = criterion.get("filterKey"), criterion.get("matchValues")
                if not isinstance(value, str):
                    issues.append(ContractIssue("match_values_not_string", f"{criterion_path}.matchValues", "matchValues must be a string."))
                    continue
                if key not in definitions:
                    issues.append(ContractIssue("unknown_filter_key", f"{criterion_path}.filterKey", f"No filter definition for {key!r}."))
                elif value not in definitions[key]:
                    issues.append(ContractIssue("unknown_filter_value", f"{criterion_path}.matchValues", f"{value!r} is not an option for {key!r}."))
        return issues

    @staticmethod
    def _validate_support_semantics(payload: dict[str, Any]) -> list[ContractIssue]:
        return [
            ContractIssue("empty_required_content", f"$.{key}", f"{key} must contain non-whitespace content.")
            for key in ("title", "slug", "pageType", "mainContent")
            if isinstance(payload.get(key), str) and not payload[key].strip()
        ]

    @staticmethod
    def _support_quality_warnings(payload: dict[str, Any]) -> list[ContractIssue]:
        optional = ("metaTitle", "metaDescription", "metaKeywords", "lastModifiedDate", "articleDescription")
        return [
            ContractIssue("empty_optional_content", f"$.{key}", f"{key} is empty in the source content.")
            for key in optional if key in payload and not payload[key].strip()
        ]
