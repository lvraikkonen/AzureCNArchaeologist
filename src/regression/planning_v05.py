"""Reviewed-candidate tooling for the v0.5 Planning Baseline successor."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from src.core.product_catalog import canonical_json, sha256_file
from src.core.validation_context import (
    P2_PLANNING_BASELINE_SPEC,
    ValidationContextRegistry,
)
from src.pipeline.planner import PipelinePlanner


BASELINE_ID = "v0.5.1-planning-baseline"
BASELINE_SCHEMA = "schemas/planning-baseline-manifest-2.0.schema.json"
CANDIDATE_SCHEMA = "schemas/planning-baseline-candidate-1.0.schema.json"
TARGET_PATH = Path("data/baselines/v0.5/planning-baseline.json")
CANDIDATE_ROOT = Path("output/v0.5-planning-baseline-candidates")
ACCEPTED_BATCH_REPORT = Path("reports/v0.4.1/full-acceptance-batch-summary.json")
QUALIFICATION_REPORT = Path(
    "reports/post-v0.4/v041-upstream-source-fix-regression-20260811.md"
)
ENTRY_DECISION = Path("reports/post-v0.4/v050-entry-decision.md")
EXPECTED_CHANGED_ITEM_IDS = (
    "en-us/cdn",
    "en-us/data-transfer",
    "zh-cn/cdn",
    "zh-cn/data-transfer",
)


class PlanningBaselineError(RuntimeError):
    """The v0.5 Planning Baseline candidate is invalid or unsafe to promote."""


def _render_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _semantic_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _artifact(root: Path, relative_path: Path) -> dict[str, str]:
    path = root / relative_path
    if path.is_symlink() or not path.is_file():
        raise PlanningBaselineError(f"Required artifact is missing: {relative_path}")
    return {"path": relative_path.as_posix(), "sha256": sha256_file(path)}


def _validate(root: Path, schema_path: str, value: Mapping[str, Any]) -> None:
    schema = json.loads((root / schema_path).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
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
        raise PlanningBaselineError(f"{schema_path} validation failed: {details}")


def _planned_state(item: Any) -> str:
    if item.runnable:
        return "runnable"
    return str(item.skip_reason["code"]).lower()


def _reason_code(state: str) -> str:
    return {
        "runnable": "reviewed_supported",
        "known_unsupported": "known_unsupported",
        "source_unavailable": "source_unavailable",
    }[state]


def _change_id(item_id: str) -> str:
    language, resource = item_id.split("/", 1)
    return f"V051-PLAN-DELTA-{language.upper()}-{resource.upper()}"


def _qualification_rationale(resource_key: str) -> str:
    if resource_key == "cdn":
        return (
            "The current bilingual sources each expose one uniquely bounded formal "
            "static selector and one pricing table; production replay and independent "
            "source-to-payload comparison both passed."
        )
    if resource_key == "data-transfer":
        return (
            "The current bilingual sources expose one closed Pricing Details section "
            "before exact FAQ/SLA common sections; the strict boundary excludes adjacent "
            "sections and independently matches the persisted payload."
        )
    raise PlanningBaselineError(f"Unexpected capability delta: {resource_key}")


def build_planning_baseline(root: str | Path = ".") -> dict[str, Any]:
    """Build the deterministic, identity-light v0.5 Planning successor."""

    root = Path(root).resolve()
    plan = PipelinePlanner(root).plan(language="both")
    predecessor_path = root / P2_PLANNING_BASELINE_SPEC.relative_path
    predecessor_authority = json.loads(
        predecessor_path.read_text(encoding="utf-8")
    )
    predecessor_identity = {
        "id": predecessor_authority["baseline_id"],
        "schema_version": predecessor_authority["schema_version"],
        "path": P2_PLANNING_BASELINE_SPEC.relative_path,
        "sha256": sha256_file(predecessor_path),
    }
    predecessor = ValidationContextRegistry(
        root
    ).planning_baseline_for_identity(predecessor_identity)
    predecessor_by_id = {item["item_id"]: item for item in predecessor["items"]}
    current_ids = [item.item_id for item in plan.items]
    if len(current_ids) != 434 or len(set(current_ids)) != 434:
        raise PlanningBaselineError("Current bilingual plan is not the 434-item closed world")
    if set(current_ids) != set(predecessor_by_id):
        raise PlanningBaselineError("Current and predecessor plan membership differ")

    qualification_artifact = _artifact(root, QUALIFICATION_REPORT)
    items: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    changed_ids: list[str] = []
    for item in plan.items:
        state = _planned_state(item)
        predecessor_state = predecessor_by_id[item.item_id]["v03_state"]
        changed = state != predecessor_state
        change_id = _change_id(item.item_id) if changed else None
        if changed:
            changed_ids.append(item.item_id)
            if predecessor_state != "known_unsupported" or state != "runnable":
                raise PlanningBaselineError(
                    f"Unreviewed state transition: {item.item_id} "
                    f"{predecessor_state}->{state}"
                )
            if item.capability_status != "supported":
                raise PlanningBaselineError(
                    f"Changed item is not supported: {item.item_id}"
                )
            changes.append(
                {
                    "change_id": change_id,
                    "item_id": item.item_id,
                    "prior_state": predecessor_state,
                    "proposed_state": state,
                    "reason_code": (
                        "independently_qualified_bilingual_source_boundary"
                    ),
                    "qualification_evidence": {
                        "artifact": qualification_artifact,
                        "section": f"{item.product_key} 重新准入",
                    },
                    "product_definition_decision": {
                        "path": item.config_path,
                        "capability_status": "supported",
                        "decision": "accepted_for_v0.5_successor",
                    },
                    "denominator_impact": 1,
                    "rationale": _qualification_rationale(item.product_key),
                    "review": {
                        "status": "accepted",
                        "decision_id": "V050-ENTRY-20260811",
                        "accepted_at": "2026-08-11",
                    },
                }
            )
        items.append(
            {
                "item_id": item.item_id,
                "language": item.language,
                "resource_key": item.resource_key,
                "product_key": item.product_key,
                "resource_kind": item.resource_kind,
                "semantic_strategy": item.strategy,
                "planned_state": state,
                "state_reason_code": _reason_code(state),
                "predecessor_state": predecessor_state,
                "change_id": change_id,
            }
        )

    if tuple(changed_ids) != EXPECTED_CHANGED_ITEM_IDS:
        raise PlanningBaselineError(
            f"State delta is not the reviewed four-item set: {changed_ids}"
        )
    summary = dict(plan.summary)
    expected_summary = {
        "total": 434,
        "runnable": 383,
        "skipped": 51,
        "known_unsupported": 50,
        "source_unavailable": 1,
    }
    if summary != expected_summary:
        raise PlanningBaselineError(
            f"Current plan accounting differs: {summary}"
        )

    document = {
        "schema_version": "2.0",
        "baseline_id": BASELINE_ID,
        "predecessor": {
            "accepted_version": "0.4.1",
            "accepted_tag": "v0.4.1",
            "planning_baseline": predecessor_identity,
            "accepted_batch_id": "20260809T030936Z-ce23e678",
            "accepted_batch_report": _artifact(root, ACCEPTED_BATCH_REPORT),
            "qualification_report": qualification_artifact,
            "entry_decision": _artifact(root, ENTRY_DECISION),
        },
        "scope": {
            "kind": "all",
            "languages": ["zh-cn", "en-us"],
            "item_count": 434,
        },
        "summary": summary,
        "items": items,
        "changes": changes,
        "accounting": {
            "reviewed_items": 434,
            "coverage": "434/434",
            "runnable": 383,
            "skipped": 51,
        },
    }
    _validate(root, BASELINE_SCHEMA, document)
    return document


def _state_diff(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "predecessor_baseline_id": document["predecessor"][
            "planning_baseline"
        ]["id"],
        "successor_baseline_id": document["baseline_id"],
        "before": {
            "total": 434,
            "runnable": 379,
            "skipped": 55,
            "known_unsupported": 54,
            "source_unavailable": 1,
        },
        "after": dict(document["summary"]),
        "changed_items": list(document["changes"]),
        "unchanged_item_count": 430,
    }


def _rationale(document: Mapping[str, Any]) -> str:
    lines = [
        "# v0.5.1 Planning Baseline candidate rationale",
        "",
        "This candidate keeps the 434-item closed world and changes only four "
        "reviewed language items from `known_unsupported` to `runnable`.",
        "",
        "It intentionally stores plan membership, state, denominator, predecessor, "
        "and change rationale only. Per-run Source, Product Definition, config, route "
        "map, and payload identities remain owned by the existing input/batch manifests.",
        "",
        "Reviewed changes:",
        "",
    ]
    for change in document["changes"]:
        lines.append(
            f"- `{change['item_id']}`: {change['prior_state']} → "
            f"{change['proposed_state']}; {change['rationale']}"
        )
    lines.extend(
        [
            "",
            "Promotion requires explicit acceptance of the exact candidate SHA-256.",
            "",
        ]
    )
    return "\n".join(lines)


def create_planning_candidate(
    root: str | Path = ".",
    *,
    candidate_root: str | Path = CANDIDATE_ROOT,
) -> tuple[Path, dict[str, Any]]:
    """Write a deterministic candidate bundle outside canonical baselines."""

    root = Path(root).resolve()
    candidate_root = Path(candidate_root)
    if not candidate_root.is_absolute():
        candidate_root = root / candidate_root
    document = build_planning_baseline(root)
    proposed_bytes = _render_json(document).encode("utf-8")
    proposed_sha = _bytes_sha256(proposed_bytes)
    candidate_id = f"v0.5.1-planning-{proposed_sha[:12]}"
    candidate_dir = candidate_root / candidate_id
    if candidate_dir.exists():
        shutil.rmtree(candidate_dir)
    proposed_path = candidate_dir / "proposed" / "planning-baseline.json"
    proposed_path.parent.mkdir(parents=True, exist_ok=True)
    proposed_path.write_bytes(proposed_bytes)

    state_diff = _state_diff(document)
    state_diff_bytes = _render_json(state_diff).encode("utf-8")
    state_diff_path = candidate_dir / "planning-state-diff.json"
    state_diff_path.write_bytes(state_diff_bytes)
    rationale_bytes = _rationale(document).encode("utf-8")
    rationale_path = candidate_dir / "rationale.md"
    rationale_path.write_bytes(rationale_bytes)

    predecessor = document["predecessor"]["planning_baseline"]
    candidate = {
        "schema_version": "1.0",
        "candidate_id": candidate_id,
        "baseline_id": BASELINE_ID,
        "target_path": TARGET_PATH.as_posix(),
        "predecessor": predecessor,
        "proposed_sha256": proposed_sha,
        "state_diff": {
            "path": "planning-state-diff.json",
            "sha256": _bytes_sha256(state_diff_bytes),
        },
        "rationale": {
            "path": "rationale.md",
            "sha256": _bytes_sha256(rationale_bytes),
        },
        "candidate_sha256": "",
    }
    candidate["candidate_sha256"] = _semantic_sha256(
        {
            key: value
            for key, value in candidate.items()
            if key != "candidate_sha256"
        }
    )
    _validate(root, CANDIDATE_SCHEMA, candidate)
    (candidate_dir / "candidate-manifest.json").write_text(
        _render_json(candidate), encoding="utf-8"
    )
    return candidate_dir, candidate


def promote_planning_candidate(
    root: str | Path,
    *,
    candidate_dir: str | Path,
    expected_sha256: str,
) -> dict[str, Any]:
    """Promote only the exact reviewed candidate into the v0.5 namespace."""

    root = Path(root).resolve()
    candidate_dir = Path(candidate_dir).resolve()
    candidate = json.loads(
        (candidate_dir / "candidate-manifest.json").read_text(encoding="utf-8")
    )
    _validate(root, CANDIDATE_SCHEMA, candidate)
    computed_candidate_sha = _semantic_sha256(
        {
            key: value
            for key, value in candidate.items()
            if key != "candidate_sha256"
        }
    )
    if (
        candidate["candidate_sha256"] != computed_candidate_sha
        or computed_candidate_sha != expected_sha256
    ):
        raise PlanningBaselineError("Candidate SHA does not match expected SHA")

    proposed = candidate_dir / "proposed" / "planning-baseline.json"
    if proposed.is_symlink() or not proposed.is_file():
        raise PlanningBaselineError("Proposed Planning Baseline is missing")
    proposed_bytes = proposed.read_bytes()
    if _bytes_sha256(proposed_bytes) != candidate["proposed_sha256"]:
        raise PlanningBaselineError("Proposed Planning Baseline SHA drifted")
    proposed_document = json.loads(proposed_bytes)
    _validate(root, BASELINE_SCHEMA, proposed_document)
    if proposed_document["predecessor"]["planning_baseline"] != candidate[
        "predecessor"
    ]:
        raise PlanningBaselineError("Candidate predecessor identity drifted")

    for reference_name in ("state_diff", "rationale"):
        reference = candidate[reference_name]
        artifact = candidate_dir / reference["path"]
        if artifact.is_symlink() or not artifact.is_file():
            raise PlanningBaselineError(
                f"Candidate {reference_name} artifact is missing"
            )
        if sha256_file(artifact) != reference["sha256"]:
            raise PlanningBaselineError(
                f"Candidate {reference_name} artifact SHA drifted"
            )

    target = root / candidate["target_path"]
    if target.exists():
        if target.is_symlink() or not target.is_file():
            raise PlanningBaselineError("Planning Baseline target is not a regular file")
        if target.read_bytes() != proposed_bytes:
            raise PlanningBaselineError("A different v0.5 Planning Baseline already exists")
        return candidate
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(proposed_bytes)
    return candidate
