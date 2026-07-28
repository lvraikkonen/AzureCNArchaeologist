#!/usr/bin/env python3
"""Build the read-only capability Dashboard and Markdown projections.

The three source layers are explicit, versioned JSON documents:

* a frozen 105-entry pricing scope;
* an explicitly selected, SHA-bound machine-evidence report;
* manually maintained Manual Content Inspection records.

Neither generated output is an authority. The build never discovers a
"latest" report by filesystem time and never turns inspection into approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCOPE_PATH = "data/tracking/pricing-capability-scope.json"
MACHINE_SOURCE_PATH = "data/tracking/capability-machine-source.json"
MANUAL_PATH = "data/tracking/manual-content-inspections.json"
PROJECTION_PATH = "dashboard/app/generated/capability-dashboard.json"
MARKDOWN_PATH = "azure-product-list.md"

SCOPE_SCHEMA_PATH = "schemas/capability-tracking-scope-1.0.schema.json"
MACHINE_SOURCE_SCHEMA_PATH = "schemas/capability-machine-source-1.0.schema.json"
MANUAL_SCHEMA_PATH = "schemas/manual-content-inspection-1.1.schema.json"
PROJECTION_SCHEMA_PATH = (
    "schemas/capability-dashboard-projection-1.0.schema.json"
)
STEP3_PROBE_SCHEMA_PATH = "schemas/step3-capability-probe-1.0.schema.json"

LANGUAGES = ("zh-cn", "en-us")
class CapabilityDashboardBuildError(RuntimeError):
    """A stable, fail-closed capability projection failure."""


def _read_json(root: Path, relative_path: str) -> dict[str, Any]:
    path = root / relative_path
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CapabilityDashboardBuildError(
            f"Unable to read {relative_path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CapabilityDashboardBuildError(
            f"{relative_path} must contain a JSON object"
        )
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _render_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _validate_schema(
    value: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    label: str,
) -> None:
    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(value),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if not errors:
        return
    details = "; ".join(
        (
            f"{'/'.join(map(str, error.absolute_path)) or '$'}: "
            f"{error.message}"
        )
        for error in errors[:20]
    )
    raise CapabilityDashboardBuildError(f"Invalid {label}: {details}")


def _assert_unique(
    values: Iterable[str],
    *,
    label: str,
) -> None:
    counter = Counter(values)
    duplicates = sorted(key for key, count in counter.items() if count > 1)
    if duplicates:
        raise CapabilityDashboardBuildError(
            f"Duplicate {label}: {', '.join(duplicates)}"
        )


def _assert_no_quality_score(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "quality_score":
                raise CapabilityDashboardBuildError(
                    f"Forbidden quality_score at {path}.{key}"
                )
            _assert_no_quality_score(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_quality_score(child, path=f"{path}[{index}]")


def _safe_evidence_path(root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise CapabilityDashboardBuildError(
            "Machine evidence path must be repository-relative"
        )
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise CapabilityDashboardBuildError(
            "Machine evidence path escapes repository root"
        ) from error
    return resolved


def load_source_documents(
    root: Path = ROOT,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    """Load, schema-check, and SHA-check the three source layers."""

    scope = _read_json(root, SCOPE_PATH)
    machine_source = _read_json(root, MACHINE_SOURCE_PATH)
    manual = _read_json(root, MANUAL_PATH)

    _validate_schema(
        scope,
        _read_json(root, SCOPE_SCHEMA_PATH),
        label=SCOPE_PATH,
    )
    _validate_schema(
        machine_source,
        _read_json(root, MACHINE_SOURCE_SCHEMA_PATH),
        label=MACHINE_SOURCE_PATH,
    )
    _validate_schema(
        manual,
        _read_json(root, MANUAL_SCHEMA_PATH),
        label=MANUAL_PATH,
    )

    evidence_identity = machine_source["evidence"]
    if evidence_identity["schema_path"] != STEP3_PROBE_SCHEMA_PATH:
        raise CapabilityDashboardBuildError(
            "Selected machine evidence schema path is not supported: "
            f"{evidence_identity['schema_path']}"
        )
    evidence_schema_path = _safe_evidence_path(
        root,
        evidence_identity["schema_path"],
    )
    actual_schema_sha256 = _sha256_file(evidence_schema_path)
    if actual_schema_sha256 != evidence_identity["schema_sha256"]:
        raise CapabilityDashboardBuildError(
            "Selected machine evidence schema SHA-256 drifted: "
            f"expected {evidence_identity['schema_sha256']}, "
            f"got {actual_schema_sha256}"
        )
    evidence_path = _safe_evidence_path(root, evidence_identity["path"])
    actual_sha256 = _sha256_file(evidence_path)
    if actual_sha256 != evidence_identity["sha256"]:
        raise CapabilityDashboardBuildError(
            "Selected machine evidence SHA-256 drifted: "
            f"expected {evidence_identity['sha256']}, got {actual_sha256}"
        )
    evidence = _read_json(root, evidence_identity["path"])
    if evidence.get("schema_version") != evidence_identity["schema_version"]:
        raise CapabilityDashboardBuildError(
            "Selected machine evidence schema_version differs from pointer"
        )
    if evidence.get("report_id") != evidence_identity["report_id"]:
        raise CapabilityDashboardBuildError(
            "Selected machine evidence report_id differs from pointer"
        )
    if evidence_identity["kind"] != "step3_probe":
        raise CapabilityDashboardBuildError(
            f"Unknown machine evidence kind: {evidence_identity['kind']}"
        )
    if evidence_identity["schema_version"] != "1.0":
        raise CapabilityDashboardBuildError(
            "Unknown step3_probe schema version: "
            f"{evidence_identity['schema_version']}"
        )
    _validate_schema(
        evidence,
        _read_json(root, evidence_identity["schema_path"]),
        label=evidence_identity["path"],
    )

    _assert_no_quality_score(scope)
    _assert_no_quality_score(machine_source)
    _assert_no_quality_score(manual)
    _assert_no_quality_score(evidence)
    return scope, machine_source, manual, evidence


def _machine_status(
    *,
    capability_status: str,
    language: Mapping[str, Any],
) -> str:
    if capability_status == "known_unsupported":
        return "not_applicable"
    return "pass" if language.get("machine_passed") is True else "fail"


def _normalise_issue(issue: Mapping[str, Any]) -> dict[str, str]:
    return {
        "code": str(issue.get("code") or ""),
        "path": str(issue.get("path") or ""),
        "message": str(issue.get("message") or ""),
    }


def _normalise_error(
    error: Mapping[str, Any] | None,
) -> dict[str, str] | None:
    if error is None:
        return None
    return {
        "code": str(error.get("code") or ""),
        "stage": str(error.get("stage") or ""),
        "message": str(error.get("message") or ""),
    }


def _machine_language_projection(
    *,
    capability_status: str,
    language: Mapping[str, Any],
) -> dict[str, Any]:
    payload = language.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}
    return {
        "status": _machine_status(
            capability_status=capability_status,
            language=language,
        ),
        "execution": str(language.get("execution") or "not_run"),
        "validation": str(language.get("validation") or "not_run"),
        "source_path": language.get("source_path"),
        "source_sha256": language.get("source_sha256"),
        "payload_path": payload_mapping.get("path"),
        "payload_sha256": payload_mapping.get("sha256"),
        "content_group_count": language.get("content_group_count"),
        "error": _normalise_error(language.get("error")),
        "validation_errors": [
            _normalise_issue(issue)
            for issue in language.get("validation_errors", [])
        ],
        "validation_warnings": [
            _normalise_issue(issue)
            for issue in language.get("validation_warnings", [])
        ],
    }


def _manual_language_projection(
    *,
    machine: Mapping[str, Any],
    inspection: Mapping[str, Any] | None,
    derived_binding_status: str | None,
) -> dict[str, Any]:
    applicable = machine["status"] == "pass"
    if inspection is None:
        return {
            "is_applicable": applicable,
            "verdict": "pending",
            "binding_status": None,
            "reviewer": None,
            "reviewed_at": None,
            "source_sha256": None,
            "payload_sha256": None,
            "notes": [],
            "findings": [],
        }
    return {
        "is_applicable": applicable,
        "verdict": inspection["verdict"],
        "binding_status": derived_binding_status,
        "reviewer": inspection["reviewer"],
        "reviewed_at": inspection["reviewed_at"],
        "source_sha256": inspection["source_sha256"],
        "payload_sha256": inspection["payload_sha256"],
        "notes": list(inspection["notes"]),
        "findings": list(inspection["findings"]),
    }


def _derive_binding_statuses(
    *,
    manual_product: Mapping[str, Any],
    machine_languages: Mapping[str, Mapping[str, Any]],
) -> tuple[str | None, dict[str, str]]:
    product_declared = manual_product.get("binding_status")
    if product_declared not in (None, "bound", "legacy_unbound"):
        raise CapabilityDashboardBuildError(
            f"Unknown binding_status for {manual_product['product_key']}: "
            f"{product_declared}"
        )

    inspections = manual_product["languages"]
    if not inspections and product_declared == "bound":
        raise CapabilityDashboardBuildError(
            f"Bound inspection {manual_product['product_key']} requires "
            "at least one language"
        )
    language_statuses: dict[str, str] = {}
    for language, inspection in inspections.items():
        declared = inspection.get("binding_status", product_declared)
        if declared not in ("bound", "legacy_unbound"):
            raise CapabilityDashboardBuildError(
                f"Manual inspection {manual_product['product_key']}/"
                f"{language} requires binding_status"
            )
        if declared == "legacy_unbound":
            language_statuses[language] = "legacy_unbound"
            continue
        verdict = inspection["verdict"]
        if verdict == "pending":
            raise CapabilityDashboardBuildError(
                f"Bound inspection {manual_product['product_key']}/"
                f"{language} cannot be pending"
            )
        for field in (
            "reviewer",
            "reviewed_at",
            "source_sha256",
            "payload_sha256",
        ):
            if not inspection[field]:
                raise CapabilityDashboardBuildError(
                    f"Bound inspection {manual_product['product_key']}/"
                    f"{language} requires {field}"
                )
        machine = machine_languages[language]
        if (
            machine["status"] != "pass"
            or inspection["source_sha256"] != machine["source_sha256"]
            or inspection["payload_sha256"] != machine["payload_sha256"]
        ):
            language_statuses[language] = "stale"
        else:
            language_statuses[language] = "bound"
    if "stale" in language_statuses.values():
        product_status = "stale"
    elif "legacy_unbound" in language_statuses.values():
        product_status = "legacy_unbound"
    elif language_statuses:
        product_status = "bound"
    else:
        product_status = product_declared
    return product_status, language_statuses


def _validate_manual_applicability(
    *,
    manual_product: Mapping[str, Any],
    machine_languages: Mapping[str, Mapping[str, Any]],
    language_binding_statuses: Mapping[str, str],
    product_binding_status: str | None,
) -> None:
    product_key = manual_product["product_key"]
    for language, inspection in manual_product["languages"].items():
        if language not in LANGUAGES:
            raise CapabilityDashboardBuildError(
                f"Unknown manual language {product_key}/{language}"
            )
        verdict = inspection["verdict"]
        machine_passed = machine_languages[language]["status"] == "pass"
        if verdict == "passed" and not machine_passed:
            if language_binding_statuses.get(language) != "stale":
                raise CapabilityDashboardBuildError(
                    f"Manual pass is illegal on machine-failed language: "
                    f"{product_key}/{language}"
                )
        elif verdict != "pending" and not machine_passed:
            if language_binding_statuses.get(language) != "stale":
                raise CapabilityDashboardBuildError(
                    "Manual verdict is illegal on machine-failed language: "
                    f"{product_key}/{language}"
                )
        if verdict == "findings" and not inspection["findings"]:
            raise CapabilityDashboardBuildError(
                f"findings verdict requires findings: {product_key}/{language}"
            )
    has_open_unscoped_findings = any(
        finding["status"] == "open"
        for finding in manual_product["unscoped_findings"]
    )
    if has_open_unscoped_findings and not any(
        language["status"] == "pass"
        for language in machine_languages.values()
    ):
        if product_binding_status != "stale":
            raise CapabilityDashboardBuildError(
                "Unscoped findings require a machine-passed payload: "
                f"{product_key}"
            )


def _derive_manual_outcome(
    *,
    machine_languages: Mapping[str, Mapping[str, Any]],
    manual_languages: Mapping[str, Mapping[str, Any]],
    unscoped_findings: Sequence[Mapping[str, Any]],
    binding_status: str | None,
) -> str:
    if binding_status == "stale":
        return "stale"
    applicable = [
        language
        for language in LANGUAGES
        if machine_languages[language]["status"] == "pass"
    ]
    if not applicable:
        return "not_applicable"
    if any(
        finding["status"] == "open"
        for finding in unscoped_findings
    ):
        return "findings"
    if any(
        finding["status"] == "open"
        for language in applicable
        for finding in manual_languages[language]["findings"]
    ):
        return "findings"
    verdicts = []
    for language in applicable:
        inspection = manual_languages[language]
        verdict = inspection["verdict"]
        if verdict == "findings":
            if any(
                finding["status"] == "open"
                for finding in inspection["findings"]
            ):
                verdicts.append("findings")
            else:
                verdicts.append("pending")
        else:
            verdicts.append(verdict)
    if "findings" in verdicts:
        return "findings"
    if "failed" in verdicts:
        return "failed"
    if "pending" in verdicts:
        return "pending"
    if verdicts and all(verdict == "passed" for verdict in verdicts):
        return "passed"
    raise CapabilityDashboardBuildError(
        f"Unable to derive manual outcome from verdicts: {verdicts}"
    )


def _product_has_open_findings(product: Mapping[str, Any]) -> bool:
    return any(
        finding["status"] == "open"
        for finding in product["unscoped_findings"]
    ) or any(
        finding["status"] == "open"
        for language in LANGUAGES
        for finding in product["languages"][language]["manual"]["findings"]
    )


def _machine_outcome(product: Mapping[str, Any]) -> str:
    if product["capability_status"] == "known_unsupported":
        return "known_unsupported"
    passed = sum(
        1
        for language in LANGUAGES
        if product["languages"][language]["machine_passed"] is True
    )
    if passed == 2:
        return "bilingual_pass"
    if passed == 1:
        return "single_language_pass"
    return "bilingual_fail"


def _validate_probe_summary(
    evidence: Mapping[str, Any],
    *,
    scope_summary: Mapping[str, int],
    machine_summary: Mapping[str, int],
) -> None:
    probe_summary = evidence.get("summary")
    if not isinstance(probe_summary, Mapping):
        raise CapabilityDashboardBuildError(
            "Selected machine evidence has no summary object"
        )
    expected_probe_fields = {
        "supported": scope_summary["supported"],
        "known_unsupported": scope_summary["known_unsupported"],
        "bilingual_machine_pass": machine_summary["bilingual_pass"],
        "single_language_machine_pass": machine_summary[
            "single_language_pass"
        ],
        "bilingual_machine_fail": machine_summary["bilingual_fail"],
        "machine_passed_language_items": machine_summary[
            "passed_language_items"
        ],
        "manual_review_product_count": (
            machine_summary["bilingual_pass"]
            + machine_summary["single_language_pass"]
        ),
        "manual_review_language_item_count": machine_summary[
            "passed_language_items"
        ],
        "zh-cn_pass": machine_summary["zh_cn_pass"],
        "zh-cn_fail": machine_summary["zh_cn_fail"],
        "en-us_pass": machine_summary["en_us_pass"],
        "en-us_fail": machine_summary["en_us_fail"],
    }
    mismatches = {
        field: (probe_summary.get(field), expected)
        for field, expected in expected_probe_fields.items()
        if probe_summary.get(field) != expected
    }
    if mismatches:
        raise CapabilityDashboardBuildError(
            f"Machine evidence summary is inconsistent: {mismatches}"
        )


def build_projection(
    scope: Mapping[str, Any],
    machine_source: Mapping[str, Any],
    manual: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Merge the source layers and derive the canonical read-only projection."""

    _validate_schema(
        evidence,
        _read_json(root, STEP3_PROBE_SCHEMA_PATH),
        label="selected Step 3 probe evidence",
    )
    scope_products = list(scope["products"])
    evidence_products = list(evidence.get("products") or [])
    manual_products = list(manual["products"])

    _assert_unique(
        (product["product_key"] for product in scope_products),
        label="scope Product Key",
    )
    _assert_unique(
        (product["url"] for product in scope_products),
        label="scope URL",
    )
    _assert_unique(
        (product["product_key"] for product in evidence_products),
        label="machine-evidence Product Key",
    )
    _assert_unique(
        (product["product_key"] for product in manual_products),
        label="manual-inspection Product Key",
    )
    if len(scope_products) != 105:
        raise CapabilityDashboardBuildError(
            f"Capability scope must contain exactly 105 products, got "
            f"{len(scope_products)}"
        )

    evidence_by_key = {
        product["product_key"]: product for product in evidence_products
    }
    manual_by_key = {
        product["product_key"]: product for product in manual_products
    }
    scope_keys = [product["product_key"] for product in scope_products]
    if set(evidence_by_key) != set(scope_keys):
        raise CapabilityDashboardBuildError(
            "Machine-evidence Product Keys differ from frozen scope"
        )
    unknown_manual = sorted(set(manual_by_key) - set(scope_keys))
    if unknown_manual:
        raise CapabilityDashboardBuildError(
            f"Manual inspection references unknown products: {unknown_manual}"
        )

    projected_products: list[dict[str, Any]] = []
    for scope_product in scope_products:
        product_key = scope_product["product_key"]
        machine_product = evidence_by_key[product_key]
        for field in (
            "display_name",
            "slug",
            "catalog_categories",
            "url",
        ):
            if machine_product.get(field) != scope_product[field]:
                raise CapabilityDashboardBuildError(
                    f"Frozen scope differs from machine evidence for "
                    f"{product_key}.{field}"
                )

        capability_status = machine_product["capability_status"]
        machine_languages = {
            language: _machine_language_projection(
                capability_status=capability_status,
                language=machine_product["languages"][language],
            )
            for language in LANGUAGES
        }
        manual_product = manual_by_key.get(product_key)
        binding_status: str | None = None
        language_binding_statuses: dict[str, str] = {}
        unscoped_findings: list[dict[str, Any]] = []
        manual_notes: list[str] = []
        raw_legacy: dict[str, str] | None = None
        inspection_languages: Mapping[str, Mapping[str, Any]] = {}
        if manual_product is not None:
            (
                binding_status,
                language_binding_statuses,
            ) = _derive_binding_statuses(
                manual_product=manual_product,
                machine_languages=machine_languages,
            )
            _validate_manual_applicability(
                manual_product=manual_product,
                machine_languages=machine_languages,
                language_binding_statuses=language_binding_statuses,
                product_binding_status=binding_status,
            )
            unscoped_findings = list(manual_product["unscoped_findings"])
            manual_notes = list(manual_product["notes"])
            raw_legacy_value = manual_product.get("raw_legacy")
            raw_legacy = (
                dict(raw_legacy_value)
                if isinstance(raw_legacy_value, Mapping)
                else None
            )
            inspection_languages = manual_product["languages"]

        manual_languages = {
            language: _manual_language_projection(
                machine=machine_languages[language],
                inspection=inspection_languages.get(language),
                derived_binding_status=language_binding_statuses.get(language),
            )
            for language in LANGUAGES
        }
        manual_outcome = _derive_manual_outcome(
            machine_languages=machine_languages,
            manual_languages=manual_languages,
            unscoped_findings=unscoped_findings,
            binding_status=binding_status,
        )
        projected_products.append(
            {
                "product_key": product_key,
                "display_name": scope_product["display_name"],
                "slug": scope_product["slug"],
                "catalog_categories": list(
                    scope_product["catalog_categories"]
                ),
                "url": scope_product["url"],
                "semantic_strategy": scope_product["semantic_strategy"],
                "capability_status": capability_status,
                "unsupported_reason": machine_product["unsupported_reason"],
                "machine_outcome": _machine_outcome(machine_product),
                "manual_outcome": manual_outcome,
                "binding_status": binding_status,
                "languages": {
                    language: {
                        "machine": machine_languages[language],
                        "manual": manual_languages[language],
                    }
                    for language in LANGUAGES
                },
                "unscoped_findings": unscoped_findings,
                "manual_notes": manual_notes,
                "raw_legacy": raw_legacy,
            }
        )

    scope_counter = Counter(
        product["capability_status"] for product in projected_products
    )
    scope_summary = {
        "total": len(projected_products),
        "supported": scope_counter["supported"],
        "known_unsupported": scope_counter["known_unsupported"],
    }
    outcome_counter = Counter(
        product["machine_outcome"] for product in projected_products
    )
    language_counts = {
        language: Counter(
            product["languages"][language]["machine"]["status"]
            for product in projected_products
            if product["capability_status"] == "supported"
        )
        for language in LANGUAGES
    }
    machine_summary = {
        "bilingual_pass": outcome_counter["bilingual_pass"],
        "single_language_pass": outcome_counter["single_language_pass"],
        "bilingual_fail": outcome_counter["bilingual_fail"],
        "zh_cn_pass": language_counts["zh-cn"]["pass"],
        "zh_cn_fail": language_counts["zh-cn"]["fail"],
        "en_us_pass": language_counts["en-us"]["pass"],
        "en_us_fail": language_counts["en-us"]["fail"],
        "passed_language_items": (
            language_counts["zh-cn"]["pass"]
            + language_counts["en-us"]["pass"]
        ),
    }
    _validate_probe_summary(
        evidence,
        scope_summary=scope_summary,
        machine_summary=machine_summary,
    )

    manual_counter = Counter(
        product["manual_outcome"] for product in projected_products
    )
    manual_summary = {
        "reviewable_products": (
            machine_summary["bilingual_pass"]
            + machine_summary["single_language_pass"]
        ),
        "clear_conclusions": (
            manual_counter["passed"] + manual_counter["failed"]
        ),
        "passed_products": manual_counter["passed"],
        "failed_products": manual_counter["failed"],
        "findings_products": manual_counter["findings"],
        "pending_products": manual_counter["pending"],
    }
    binding_counter = Counter(
        product["binding_status"]
        for product in projected_products
        if product["binding_status"] is not None
    )
    binding_summary = {
        "bound": binding_counter["bound"],
        "legacy_unbound": binding_counter["legacy_unbound"],
        "stale": binding_counter["stale"],
    }

    scope_sha256 = _sha256_file(root / SCOPE_PATH)
    manual_sha256 = _sha256_file(root / MANUAL_PATH)
    evidence_identity = machine_source["evidence"]
    generated_at = str(evidence["generated_at"])
    projection = {
        "schema_version": "1.0",
        "projection_id": (
            f"{scope['scope_id']}--{evidence['report_id']}--"
            f"{manual['dataset_id']}"
        ),
        "generated_at": generated_at,
        "data_date": generated_at[:10],
        "source": {
            "scope": {
                "id": scope["scope_id"],
                "path": SCOPE_PATH,
                "sha256": scope_sha256,
            },
            "machine_evidence": {
                "kind": evidence_identity["kind"],
                "schema_version": evidence_identity["schema_version"],
                "path": evidence_identity["path"],
                "sha256": evidence_identity["sha256"],
                "report_id": evidence_identity["report_id"],
                "formal_batch_created": bool(
                    evidence["probe"]["formal_batch_created"]
                ),
            },
            "manual_inspection": {
                "id": manual["dataset_id"],
                "path": MANUAL_PATH,
                "sha256": manual_sha256,
            },
        },
        "summary": {
            "scope": scope_summary,
            "machine": machine_summary,
            "manual": manual_summary,
            "binding": binding_summary,
        },
        "attention": {
            "findings_product_keys": [
                product["product_key"]
                for product in projected_products
                if _product_has_open_findings(product)
            ],
            "pending_product_keys": [
                product["product_key"]
                for product in projected_products
                if product["manual_outcome"] == "pending"
            ],
            "stale_product_keys": [
                product["product_key"]
                for product in projected_products
                if product["manual_outcome"] == "stale"
            ],
        },
        "products": projected_products,
    }
    _assert_no_quality_score(projection)
    _validate_schema(
        projection,
        _read_json(root, PROJECTION_SCHEMA_PATH),
        label=PROJECTION_PATH,
    )
    return projection


def build_from_root(root: Path = ROOT) -> dict[str, Any]:
    scope, machine_source, manual, evidence = load_source_documents(root)
    return build_projection(
        scope,
        machine_source,
        manual,
        evidence,
        root=root,
    )


def _markdown_escape(value: Any) -> str:
    text = str(value)
    return (
        text.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\r", " ")
        .replace("\n", " ")
        .strip()
    )


def _machine_language_label(machine: Mapping[str, Any]) -> str:
    status = machine["status"]
    if status == "pass":
        return "PASS"
    if status == "not_applicable":
        return "—"
    error = machine["error"]
    if error:
        return f"FAIL ({error['code']})"
    if machine["validation_errors"]:
        return f"FAIL ({machine['validation_errors'][0]['code']})"
    return "FAIL"


def _machine_issue_text(product: Mapping[str, Any]) -> str:
    if product["capability_status"] == "known_unsupported":
        return (
            "Product Definition："
            f"{product['unsupported_reason'] or 'known_unsupported'}"
        )
    parts: list[str] = []
    for language in LANGUAGES:
        machine = product["languages"][language]["machine"]
        if machine["error"]:
            error = machine["error"]
            parts.append(
                f"{language} `{error['code']}`：{error['message']}"
            )
        for issue in machine["validation_errors"]:
            parts.append(
                f"{language} `{issue['code']}`：{issue['message']}"
            )
        for issue in machine["validation_warnings"]:
            parts.append(
                f"{language} 警告 `{issue['code']}`：{issue['message']}"
            )
    return "；".join(parts) or "—"


def _manual_status_text(product: Mapping[str, Any]) -> str:
    outcome = product["manual_outcome"]
    if outcome == "not_applicable":
        return "不适用（无机器通过 payload）"
    if outcome == "findings":
        return "有人工发现（语言范围未明确）"
    if outcome == "stale":
        return "已过期（证据 SHA 漂移）"
    labels = []
    for language in LANGUAGES:
        manual = product["languages"][language]["manual"]
        if manual["is_applicable"]:
            labels.append(f"{language}: {manual['verdict'].upper()}")
    return "；".join(labels) or "待检查"


def _manual_note_text(product: Mapping[str, Any]) -> str:
    parts: list[str] = []
    if product["binding_status"]:
        parts.append(f"证据绑定：`{product['binding_status']}`")
    parts.extend(product["manual_notes"])
    parts.extend(
        finding["summary"] for finding in product["unscoped_findings"]
    )
    return "；".join(dict.fromkeys(parts)) or "—"


def render_markdown(projection: Mapping[str, Any]) -> str:
    """Render the human-readable projection with no editable authority."""

    summary = projection["summary"]
    source = projection["source"]
    lines = [
        "# Azure 中国定价产品抽取能力清单",
        "",
        "> 此文件由 `npm run data:build` / "
        "`scripts/build_capability_dashboard.py` 确定性生成。"
        "请勿直接编辑产品表；人工进度的权威来源是 "
        "`data/tracking/manual-content-inspections.json`。",
        ">",
        f"> 数据日期：{projection['data_date']}。固定口径为 Azure "
        "中国区定价页的 105 个唯一产品详情 URL；Support Article "
        "不在本表范围内。",
        "",
        "## 状态口径",
        "",
        "- `supported` / `known_unsupported` 只来自所选机器证据中的 "
        "Product Definition 状态，机器运行失败不会改变 capability。",
        "- Machine Validation 与人工内容检查相互独立。人工内容检查"
        "不能覆盖机器失败、改变 capability、清除 Approval Blocker，"
        "也不产生 Review Approval 资格。",
        "- `legacy_unbound` 保留迁移前人工工作的价值，但因缺少 "
        "reviewer、日期和完整双语 SHA，不是正式审批证据。已绑定 "
        "SHA 漂移时自动派生为 `stale`，且不计入当前通过。",
        "- 本投影不提供任何综合质量分。",
        "",
        "## 汇总",
        "",
        "| 范围 | supported | known_unsupported | 双语机器 PASS | "
        "仅单语言 PASS | 双语均 FAIL | 可人工检查 | 明确结论 | "
        "有 findings | 待检查 | stale |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {summary['scope']['total']} | "
            f"{summary['scope']['supported']} | "
            f"{summary['scope']['known_unsupported']} | "
            f"{summary['machine']['bilingual_pass']} | "
            f"{summary['machine']['single_language_pass']} | "
            f"{summary['machine']['bilingual_fail']} | "
            f"{summary['manual']['reviewable_products']} | "
            f"{summary['manual']['clear_conclusions']} | "
            f"{summary['manual']['findings_products']} | "
            f"{summary['manual']['pending_products']} | "
            f"{summary['binding']['stale']} |"
        ),
        "",
        (
            f"单语言机器结果：zh-cn "
            f"{summary['machine']['zh_cn_pass']} PASS / "
            f"{summary['machine']['zh_cn_fail']} FAIL；en-us "
            f"{summary['machine']['en_us_pass']} PASS / "
            f"{summary['machine']['en_us_fail']} FAIL。"
        ),
        "",
        "## 证据选择",
        "",
        "| 层 | 显式来源 | SHA-256 / 状态 |",
        "|---|---|---|",
        (
            f"| 固定 Scope | `{source['scope']['path']}` | "
            f"`{source['scope']['sha256']}` |"
        ),
        (
            f"| Machine Validation | "
            f"`{source['machine_evidence']['path']}` | "
            f"`{source['machine_evidence']['sha256']}`；"
            f"`{source['machine_evidence']['kind']}`；"
            "非 Batch |"
        ),
        (
            f"| 人工内容检查 | `{source['manual_inspection']['path']}` | "
            f"`{source['manual_inspection']['sha256']}` |"
        ),
        "",
        "机器证据只按配置中的路径与 SHA 显式选择；不会按文件"
        "时间自动寻找“最新”报告。",
        "",
        "## 产品明细",
        "",
        "| 产品 | Product Key | Slug | Category | URL | 当前源 SHA（zh-cn） | "
        "capability_status | Step 3（zh-cn / en-us） | "
        "contentGroups（zh-cn / en-us） | 人工内容检查 | "
        "人工发现 / 备注 | 机器问题 / 提示 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for product in projection["products"]:
        zh = product["languages"]["zh-cn"]["machine"]
        en = product["languages"]["en-us"]["machine"]
        machine_status = (
            f"zh-cn: {_machine_language_label(zh)}；"
            f"en-us: {_machine_language_label(en)}"
        )
        content_groups = (
            "zh-cn: "
            f"{zh['content_group_count'] if zh['status'] == 'pass' else '—'}；"
            "en-us: "
            f"{en['content_group_count'] if en['status'] == 'pass' else '—'}"
        )
        row = [
            product["display_name"],
            f"`{product['product_key']}`",
            f"`{product['slug']}`",
            "、".join(product["catalog_categories"]),
            product["url"],
            (
                f"`sha256:{zh['source_sha256']}`"
                if zh["source_sha256"]
                else "—"
            ),
            f"`{product['capability_status']}`",
            machine_status,
            content_groups,
            _manual_status_text(product),
            _manual_note_text(product),
            _machine_issue_text(product),
        ]
        lines.append(
            "| " + " | ".join(_markdown_escape(value) for value in row) + " |"
        )

    lines.extend(
        [
            "",
            "## 更新工作流",
            "",
            "1. 只编辑 `data/tracking/manual-content-inspections.json` "
            "中的人工内容检查记录。",
            "2. 运行 `npm run data:build`，同时刷新 Dashboard JSON 与"
            "本 Markdown 投影。",
            "3. 新机器证据必须先显式更新 "
            "`data/tracking/capability-machine-source.json` 的路径和 SHA；"
            "禁止按磁盘时间自动切换。",
            "",
        ]
    )
    return "\n".join(lines)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def write_outputs(
    projection: Mapping[str, Any],
    *,
    root: Path = ROOT,
    expected_markdown_sha256: str | None = None,
) -> None:
    """Write both projections, optionally CAS-guarding the first migration."""

    markdown_path = root / MARKDOWN_PATH
    if expected_markdown_sha256 is not None:
        actual = _sha256_file(markdown_path)
        if actual != expected_markdown_sha256:
            raise CapabilityDashboardBuildError(
                "Refusing to overwrite changed Markdown migration source: "
                f"expected {expected_markdown_sha256}, got {actual}"
            )
    _atomic_write(root / PROJECTION_PATH, _render_json(projection))
    _atomic_write(markdown_path, render_markdown(projection))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify that both projections exactly match without writing",
    )
    parser.add_argument(
        "--expected-markdown-sha256",
        help="compare-and-swap guard for the initial Markdown migration",
    )
    args = parser.parse_args()

    try:
        projection = build_from_root(ROOT)
        rendered_projection = _render_json(projection)
        rendered_markdown = render_markdown(projection)
        if args.check:
            mismatches = []
            if not (ROOT / PROJECTION_PATH).exists() or (
                ROOT / PROJECTION_PATH
            ).read_text(encoding="utf-8") != rendered_projection:
                mismatches.append(PROJECTION_PATH)
            if not (ROOT / MARKDOWN_PATH).exists() or (
                ROOT / MARKDOWN_PATH
            ).read_text(encoding="utf-8") != rendered_markdown:
                mismatches.append(MARKDOWN_PATH)
            if mismatches:
                raise CapabilityDashboardBuildError(
                    "Generated projections are stale: " + ", ".join(mismatches)
                )
        else:
            write_outputs(
                projection,
                root=ROOT,
                expected_markdown_sha256=args.expected_markdown_sha256,
            )
    except CapabilityDashboardBuildError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        "Capability Dashboard data built: "
        f"{projection['summary']['scope']['total']} products, "
        f"{projection['summary']['manual']['clear_conclusions']} clear "
        "manual conclusions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
