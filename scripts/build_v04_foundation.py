#!/usr/bin/env python3
"""Build the frozen v0.4 P1 validation context and planning baseline.

This generator is intentionally fail-closed.  In particular, it will not
create an in-memory capability profile from a failed or incomplete
qualification report, and it will not silently remove an item from the
reviewed v0.3 runnable denominator.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.product_catalog import ProductCatalog, sha256_file
from src.core.validation_context import ValidationContextRegistry
from src.pipeline.planner import PipelinePlanner


MAX_INPUT_BYTES = 5 * 1024 * 1024
BASELINE_COMMIT = "00e6df57dbde82718a60ccfe8b5d9bccbe1c2c98"
CAPABILITY_EVIDENCE_PATH = "reports/v0.4/in-memory-capability-evidence.json"
MIGRATION_REPORT_PATH = "reports/v0.4/product-definition-1.1-migration.json"
STEP_ZERO_REPORT_PATH = "reports/v0.4/step-0-baseline.json"

OUTPUT_SCHEMAS = {
    "data/configs/validation-profiles/v0.4.json": (
        "schemas/validation-profile-1.0.schema.json"
    ),
    "data/configs/rendering-profiles/desktop-v0.4-p1.json": (
        "schemas/rendering-profile-1.0.schema.json"
    ),
    "data/configs/applicability-maps/v0.4-p1-registry.json": (
        "schemas/applicability-map-1.0.schema.json"
    ),
    "data/configs/capability-profiles/in-memory-v0.4.json": (
        "schemas/in-memory-capability-profile-1.0.schema.json"
    ),
    "data/baselines/v0.4/planning-baseline.json": (
        "schemas/planning-baseline-manifest-1.0.schema.json"
    ),
}

CONTRACTS = {
    "product_definition": (
        "1.1",
        "schemas/product-definition-1.1.schema.json",
    ),
    "flexible_content": (
        "1.1",
        "schemas/flexible-content-page-1.1.schema.json",
    ),
    "support_article": (
        "1.0",
        "schemas/support-article-page-1.0.schema.json",
    ),
    "diagnostic_sidecar": (
        "1.2",
        "schemas/diagnostic-sidecar-1.2.schema.json",
    ),
}


class FoundationError(RuntimeError):
    """The reviewed P1 foundation cannot be reproduced exactly."""


def _read_json(relative_path: str) -> dict[str, Any]:
    path = _existing_file(relative_path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FoundationError(f"Unable to read {relative_path}: {error}") from error
    if not isinstance(value, dict):
        raise FoundationError(f"{relative_path} must contain a JSON object")
    return value


def _existing_file(relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise FoundationError(f"Path must be repository-relative: {relative_path}")
    path = ROOT / relative
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(ROOT)
    except (OSError, ValueError) as error:
        raise FoundationError(
            f"Required repository file is missing or unsafe: {relative_path}"
        ) from error
    if path.is_symlink() or not path.is_file():
        raise FoundationError(
            f"Required repository path is not a regular file: {relative_path}"
        )
    return path


def _artifact(relative_path: str) -> dict[str, str]:
    path = _existing_file(relative_path)
    return {"path": relative_path, "sha256": sha256_file(path)}


def _validate_schema(
    value: Mapping[str, Any], *, schema_path: str, document_name: str
) -> None:
    schema = _read_json(schema_path)
    errors = sorted(
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).iter_errors(value),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        details = "; ".join(
            f"{'/'.join(map(str, error.absolute_path)) or '$'}: {error.message}"
            for error in errors
        )
        raise FoundationError(f"Invalid {document_name}: {details}")


def _contract_identity(schema_version: str, relative_path: str) -> dict[str, str]:
    schema = _read_json(relative_path)
    declared_version = (
        schema.get("properties", {}).get("schema_version", {}).get("const")
    )
    expected_suffix = f"-{schema_version}.schema.json"
    declared_id = schema.get("$id")
    version_matches = declared_version == schema_version or (
        declared_version is None
        and relative_path.endswith(expected_suffix)
        and isinstance(declared_id, str)
        and declared_id.endswith(Path(relative_path).name)
    )
    if not version_matches:
        raise FoundationError(
            f"Contract version mismatch for {relative_path}: "
            f"expected {schema_version}, found {declared_version}"
        )
    return {
        "schema_version": schema_version,
        "path": relative_path,
        "sha256": sha256_file(_existing_file(relative_path)),
    }


def _validate_migration(
    migration: Mapping[str, Any], records: Mapping[str, Any]
) -> None:
    if migration.get("schema_version") != "1.0":
        raise FoundationError("Product Definition migration schema_version is not 1.0")
    if migration.get("migration") != "product-definition-1.0-to-1.1":
        raise FoundationError("Unexpected Product Definition migration identity")
    if migration.get("status") != "completed" or migration.get(
        "unresolved_findings"
    ) != 0:
        raise FoundationError("Product Definition 1.1 migration is not complete")
    if migration.get("source_definition_count") != len(records) or migration.get(
        "target_definition_count"
    ) != len(records):
        raise FoundationError("Product Definition migration count drifted")

    thresholds = migration.get("quality_thresholds_migrated_to_validation_profile")
    if not isinstance(thresholds, dict) or set(thresholds) != set(records):
        raise FoundationError(
            "Validation Profile thresholds do not cover exactly all Product Definitions"
        )
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in thresholds.values()
    ):
        raise FoundationError("Validation Profile contains an invalid content threshold")

    actual_strategies = Counter(
        record.definition["extraction"]["semantic_strategy"]
        for record in records.values()
    )
    reported_strategies = migration.get("strategy_counts")
    if reported_strategies != dict(sorted(actual_strategies.items())):
        raise FoundationError("Migrated semantic-strategy counts drifted")


def _validation_profile(migration: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "profile_id": "v0.4-validation-p1",
        "status": "frozen",
        "contracts": {
            key: _contract_identity(version, path)
            for key, (version, path) in CONTRACTS.items()
        },
        "input_assurance": {
            "normalized_input_byte_identical": True,
            "encoding": "utf-8-strict",
            "preserve_utf8_bom": True,
            "reconstruction_parseability": "beautifulsoup-html.parser-vs-lxml.html",
            "material_difference_disposition": "blocking",
        },
        "source_finding_severity": {
            "charset_declaration_not_utf8": "finding",
            "charset_declarations_conflict": "finding",
            "charset_bom_conflict": "finding",
        },
        "min_content_length_by_product": dict(
            sorted(
                migration[
                    "quality_thresholds_migrated_to_validation_profile"
                ].items()
            )
        ),
    }


def _rendering_profile() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "profile_id": "v0.4-desktop-p1",
        "status": "identity_frozen_pending_p4_calibration",
        "viewport": {"width": 1440, "height": 900},
        "zoom_percent": 100,
        "device_scale_factor": 1,
        "approval_use": "prohibited_until_p4_calibration",
        # P1 freezes only the rendering envelope.  These identities cannot be
        # populated truthfully until the controlled P4 renderer exists.
        "pending_p4_identities": ["chromium", "fonts", "template", "css"],
    }


def _applicability_map(migration: Mapping[str, Any]) -> dict[str, Any]:
    candidates = migration.get("applicability_map_candidates")
    if not isinstance(candidates, list):
        raise FoundationError("Applicability Map migration candidates are missing")
    keys: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise FoundationError("Invalid Applicability Map migration candidate")
        product_key = candidate.get("product_key")
        if not isinstance(product_key, str) or not product_key:
            raise FoundationError("Applicability Map candidate has no product_key")
        if candidate.get("disposition") != "migrated_to_applicability_map_candidate":
            raise FoundationError(
                f"Applicability Map candidate is not migrated: {product_key}"
            )
        sections = candidate.get("legacy_extra_sections")
        if not isinstance(sections, list) or not sections:
            raise FoundationError(
                f"Applicability Map candidate has no migrated evidence: {product_key}"
            )
        keys.append(product_key)
    if len(keys) != len(set(keys)):
        raise FoundationError("Duplicate Applicability Map migration candidate")
    expected_keys = {
        "azure-nat-gateway",
        "container-instances",
        "virtual-network",
    }
    if set(keys) != expected_keys:
        raise FoundationError(
            f"Applicability Map candidate set drifted: {sorted(keys)}"
        )
    return {
        "schema_version": "1.0",
        "map_id": "v0.4-applicability-p1",
        "status": "identity_frozen_pending_p3_population",
        "approval_use": "prohibited_until_p3_population",
        "strategy_requirements": {
            "simple_static": "not_applicable",
            "region_filter": "required",
            "complex": "required",
            "support_article": "not_applicable",
        },
        "legacy_candidates": sorted(keys),
    }


def _validate_capability_evidence(evidence: Mapping[str, Any]) -> None:
    required_identity = {
        "schema_version": "1.0",
        "profile_candidate": "v0.4-in-memory-5mib",
        "status": "passed",
        "processing_mode": "in_memory",
        "candidate_max_input_bytes": MAX_INPUT_BYTES,
        "error": None,
    }
    for key, expected in required_identity.items():
        if evidence.get(key) != expected:
            raise FoundationError(
                f"Capability evidence is not approval-ready: {key}="
                f"{evidence.get(key)!r}, expected {expected!r}"
            )

    expected_assertions = {
        "six_workers_exit_zero",
        "per_case_deterministic",
        "semantic_strategy_complex",
        "padding_payload_equivalent",
        "five_mib_accepted",
    }
    assertions = evidence.get("assertions")
    if not isinstance(assertions, dict) or set(assertions) != expected_assertions:
        raise FoundationError("Capability evidence assertions are incomplete")
    if any(value is not True for value in assertions.values()):
        raise FoundationError("Capability evidence contains a failed assertion")

    isolation = evidence.get("isolation")
    if isolation != {
        "runs_per_case": 3,
        "python_hash_seeds": [1, 2, 3],
        "network_required": False,
    }:
        raise FoundationError("Capability evidence isolation controls drifted")
    guard = evidence.get("qualification_guard")
    if guard != {
        "timeout_seconds_per_run": 300,
        "max_peak_rss_bytes_per_run": 1024 * 1024 * 1024,
    }:
        raise FoundationError("Capability evidence resource guards drifted")

    cases = evidence.get("cases")
    if not isinstance(cases, dict) or set(cases) != {
        "largest_real_input",
        "near_limit_5mib",
    }:
        raise FoundationError("Capability evidence cases are incomplete")
    expected_cases = {
        "largest_real_input": (
            4_115_841,
            "f4795e994b0c657a531cbbde8629919ecd264607c081929df7b8ff905191305c",
        ),
        "near_limit_5mib": (
            MAX_INPUT_BYTES,
            "4d8fa7b0397436d3599f928808c542ea06c4fdcb5446ef8634409ad19f7be5d6",
        ),
    }
    deterministic_fields = (
        "input_bytes",
        "input_sha256",
        "strategy",
        "payload_sha256",
        "parseability_fingerprint_sha256",
    )
    payload_hashes: list[str] = []
    for case_name, (expected_bytes, expected_sha) in expected_cases.items():
        case = cases[case_name]
        if not isinstance(case, dict):
            raise FoundationError(f"Invalid capability case: {case_name}")
        if case.get("bytes") != expected_bytes or case.get("sha256") != expected_sha:
            raise FoundationError(f"Capability case identity drifted: {case_name}")
        runs = case.get("runs")
        if not isinstance(runs, list) or len(runs) != 3:
            raise FoundationError(
                f"Capability case does not contain three runs: {case_name}"
            )
        if [run.get("hash_seed") for run in runs] != [1, 2, 3]:
            raise FoundationError(f"Capability hash seeds drifted: {case_name}")
        for run in runs:
            if run.get("worker_exit_code") != 0 or run.get("strategy") != "complex":
                raise FoundationError(f"Capability worker failed: {case_name}")
            if run.get("input_bytes") != expected_bytes:
                raise FoundationError(f"Capability worker byte count drifted: {case_name}")
            if run.get("input_sha256") != expected_sha:
                raise FoundationError(f"Capability worker input hash drifted: {case_name}")
            if not isinstance(run.get("peak_rss_bytes"), int) or not (
                0 < run["peak_rss_bytes"] <= guard["max_peak_rss_bytes_per_run"]
            ):
                raise FoundationError(f"Capability worker exceeded RSS guard: {case_name}")
            wall_time = run.get("wall_time_seconds")
            if isinstance(wall_time, bool) or not isinstance(wall_time, (int, float)):
                raise FoundationError(f"Capability worker wall time is invalid: {case_name}")
            if not (0 < wall_time <= guard["timeout_seconds_per_run"]):
                raise FoundationError(f"Capability worker exceeded timeout: {case_name}")
        for field in deterministic_fields:
            if len({run.get(field) for run in runs}) != 1:
                raise FoundationError(
                    f"Capability case is nondeterministic for {field}: {case_name}"
                )
        payload_hashes.append(str(runs[0]["payload_sha256"]))
    if len(set(payload_hashes)) != 1:
        raise FoundationError("5 MiB padding changed the Business Payload")


def _in_memory_profile() -> dict[str, Any]:
    evidence = _read_json(CAPABILITY_EVIDENCE_PATH)
    _validate_capability_evidence(evidence)
    return {
        "schema_version": "1.0",
        "profile_id": "v0.4-in-memory-5mib",
        "status": "frozen",
        "processing_mode": "in_memory",
        "max_normalized_input_bytes": MAX_INPUT_BYTES,
        "semantic_strategies": [
            "simple_static",
            "region_filter",
            "complex",
            "support_article",
        ],
        "over_limit_disposition": "reviewed_planning_delta_required",
        "qualification_evidence": {
            "schema_version": "1.0",
            **_artifact(CAPABILITY_EVIDENCE_PATH),
        },
    }


def _validate_v03_acceptance() -> tuple[str, dict[str, str], dict[str, str]]:
    summary_path = "reports/v0.3/full-run-summary.json"
    acceptance_path = "reports/v0.3/acceptance-status.md"
    summary = _read_json(summary_path)
    expected_summary = {
        "total": 434,
        "runnable": 379,
        "known_unsupported": 54,
        "source_unavailable": 1,
    }
    if summary.get("schema_version") != "1.0" or summary.get("status") != "completed":
        raise FoundationError("v0.3 full-run summary is not a completed 1.0 report")
    if summary.get("exit_code") != 0 or summary.get("reproducible") is not True:
        raise FoundationError("v0.3 acceptance is not reproducible and green")
    actual_summary = summary.get("summary")
    if not isinstance(actual_summary, dict) or any(
        actual_summary.get(key) != expected
        for key, expected in expected_summary.items()
    ):
        raise FoundationError("v0.3 accepted accounting drifted")
    batch_id = summary.get("batch_id")
    if not isinstance(batch_id, str):
        raise FoundationError("v0.3 acceptance has no batch_id")
    acceptance_text = _existing_file(acceptance_path).read_text(encoding="utf-8")
    if batch_id not in acceptance_text or "434 = 379 runnable + 55 skipped" not in acceptance_text:
        raise FoundationError("v0.3 acceptance Markdown and summary report disagree")

    step_zero = _read_json(STEP_ZERO_REPORT_PATH)
    baseline_commit = step_zero.get("git", {}).get("baseline_commit")
    if baseline_commit != BASELINE_COMMIT:
        raise FoundationError("Step 0 baseline commit identity drifted")
    return batch_id, _artifact(acceptance_path), _artifact(summary_path)


def _actual_normalized_artifact(item: Any) -> dict[str, str] | None:
    path = ROOT / item.normalized_path
    if not path.exists():
        if item.runnable:
            raise FoundationError(
                f"Runnable item has no canonical Normalized Input: {item.item_id}"
            )
        return None
    try:
        path.resolve(strict=True).relative_to(ROOT)
    except (OSError, ValueError) as error:
        raise FoundationError(
            f"Normalized Input is missing or unsafe: {item.item_id}"
        ) from error
    if path.is_symlink() or not path.is_file():
        raise FoundationError(
            f"Normalized Input is not a regular file: {item.item_id}"
        )
    digest = sha256_file(path)
    if digest != item.normalized_sha256 or digest != item.source_sha256:
        raise FoundationError(
            f"Normalized Input is not byte-identical to source: {item.item_id}"
        )
    return {"path": item.normalized_path, "sha256": digest}


def _planning_baseline(plan: Any) -> dict[str, Any]:
    batch_id, acceptance_artifact, summary_artifact = _validate_v03_acceptance()
    summary = plan.summary
    expected = {
        "total": 434,
        "runnable": 379,
        "skipped": 55,
        "known_unsupported": 54,
        "source_unavailable": 1,
    }
    if summary != expected:
        raise FoundationError(
            f"Current plan cannot reconstruct v0.3 accounting: {summary}"
        )

    items: list[dict[str, Any]] = []
    for item in sorted(plan.items, key=lambda value: value.item_id):
        if item.runnable:
            state = "runnable"
            skip_reason = None
            disposition = "retained_runnable"
        else:
            code = str(item.skip_reason["code"])
            state_by_code = {
                "KNOWN_UNSUPPORTED": "known_unsupported",
                "SOURCE_UNAVAILABLE": "source_unavailable",
            }
            try:
                state = state_by_code[code]
            except KeyError as error:
                raise FoundationError(
                    f"Unreviewed planning skip code for {item.item_id}: {code}"
                ) from error
            skip_reason = code
            disposition = "outside_denominator"

        if item.source_availability == "available":
            if item.source_path is None or item.source_sha256 is None:
                raise FoundationError(f"Available source is missing: {item.item_id}")
            source = _artifact(item.source_path)
            if source["sha256"] != item.source_sha256:
                raise FoundationError(f"Source identity drifted: {item.item_id}")
        else:
            source = None

        definition = _artifact(item.config_path)
        if definition["sha256"] != item.config_sha256:
            raise FoundationError(
                f"Product Definition identity drifted: {item.item_id}"
            )
        items.append({
            "item_id": item.item_id,
            "identity": {
                "language": item.language,
                "resource_key": item.resource_key,
            },
            "product_key": item.product_key,
            "resource_kind": item.resource_kind,
            "semantic_strategy": item.strategy,
            "v03_state": state,
            "v03_skip_reason": skip_reason,
            "source": source,
            "normalized_input": _actual_normalized_artifact(item),
            "product_definition": definition,
            "v04_disposition": disposition,
            "delta_id": None,
        })

    runnable = [item for item in items if item["v03_state"] == "runnable"]
    over_limit = [
        item
        for item in runnable
        if item["source"] is not None
        and (ROOT / item["source"]["path"]).stat().st_size > MAX_INPUT_BYTES
    ]
    if over_limit:
        item_ids = ", ".join(item["item_id"] for item in over_limit)
        raise FoundationError(
            "Automated capability checks may only propose a planning delta; "
            f"review is required for over-limit runnable items: {item_ids}"
        )

    return {
        "schema_version": "1.0",
        "baseline_id": "v0.4-from-v0.3",
        "source_acceptance": {
            "version": "0.3.0",
            "batch_id": batch_id,
            "acceptance_report": acceptance_artifact,
            "summary_report": summary_artifact,
            "identity_reconstruction_commit": BASELINE_COMMIT,
            "reconstruction_limitation": (
                "The accepted v0.3 run directory and Input Manifest are gitignored "
                "and were not retained in version control. Item membership and v0.3 "
                "state are reconstructed from the Step 0 baseline commit identity, "
                "the deterministic Product Definition 1.1 migration, and immutable "
                "source snapshots; the v0.3 acceptance reports establish the "
                "reviewed aggregate 434/379 accounting."
            ),
        },
        "summary": {
            "total": 434,
            "v03_runnable_denominator": 379,
            "known_unsupported": 54,
            "source_unavailable": 1,
        },
        "items": items,
        "planning_deltas": [],
        "accounting": {
            "denominator": 379,
            "retained_runnable": 379,
            "reviewed_non_runnable": 0,
            "accounted": 379,
            "coverage": "379/379",
        },
    }


def _render(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _write_or_check(documents: Mapping[str, Mapping[str, Any]], *, check: bool) -> None:
    drifted: list[str] = []
    for relative_path, value in documents.items():
        path = ROOT / relative_path
        rendered = _render(value)
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == rendered:
            continue
        if check:
            drifted.append(relative_path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")
    if drifted:
        raise FoundationError(
            "Generated v0.4 foundation is missing or stale: " + ", ".join(drifted)
        )


def build(*, check: bool = False) -> dict[str, Mapping[str, Any]]:
    catalog = ProductCatalog(ROOT)
    records = catalog.load_definitions()
    migration = _read_json(MIGRATION_REPORT_PATH)
    _validate_migration(migration, records)

    plan = PipelinePlanner(ROOT, catalog=catalog).plan()
    documents: dict[str, Mapping[str, Any]] = {
        "data/configs/validation-profiles/v0.4.json": _validation_profile(
            migration
        ),
        "data/configs/rendering-profiles/desktop-v0.4-p1.json": (
            _rendering_profile()
        ),
        "data/configs/applicability-maps/v0.4-p1-registry.json": (
            _applicability_map(migration)
        ),
        "data/configs/capability-profiles/in-memory-v0.4.json": (
            _in_memory_profile()
        ),
        "data/baselines/v0.4/planning-baseline.json": _planning_baseline(plan),
    }
    if set(documents) != set(OUTPUT_SCHEMAS):
        raise FoundationError("Internal foundation output registry is inconsistent")
    for relative_path, value in documents.items():
        _validate_schema(
            value,
            schema_path=OUTPUT_SCHEMAS[relative_path],
            document_name=relative_path,
        )

    _write_or_check(documents, check=check)

    # Replay through the runtime verifier after every output is present.  This
    # checks fixed paths and hashes as well as the 379/379 baseline semantics.
    registry = ValidationContextRegistry(ROOT)
    frozen = registry.freeze()
    registry.verify_frozen(frozen["planning"], frozen["validation_context"])
    registry.assert_plan_matches_baseline(plan)
    if registry.capability_delta_proposals(plan):
        raise FoundationError("Unreviewed capability planning deltas remain")
    return documents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed generated documents without changing them",
    )
    args = parser.parse_args()
    documents = build(check=args.check)
    action = "verified" if args.check else "generated"
    print(
        f"{action}={len(documents)} planning_items=434 "
        "runnable_denominator=379 accounting=379/379"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
