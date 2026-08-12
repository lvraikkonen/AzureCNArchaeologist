"""Read-only acceptance audit for the v0.5.1 full reference Batch.

This module does not participate in Pipeline execution.  It reads the existing
Pipeline authorities after a run completes, verifies their current bindings,
and produces one deterministic comparison against the accepted v0.4.1 Batch.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.core.product_catalog import canonical_json, sha256_file
from src.pipeline.state_store import StateStore


SCHEMA_VERSION = "v0.5.1-reference-batch-summary-1.0"
PLANNING_BASELINE_PATH = Path("data/baselines/v0.5/planning-baseline.json")
EXPECTED_PLANNING_BASELINE_ID = "v0.5.1-planning-baseline"
EXPECTED_PLANNING_SUMMARY = {
    "total": 434,
    "runnable": 383,
    "skipped": 51,
    "known_unsupported": 50,
    "source_unavailable": 1,
}
EXPECTED_PLANNING_TRANSITIONS = {
    "en-us/cdn",
    "en-us/data-transfer",
    "zh-cn/cdn",
    "zh-cn/data-transfer",
}


class ReferenceBatchError(RuntimeError):
    """A reference Batch or its acceptance evidence is incomplete or unsafe."""


class _DuplicateJsonKey(ValueError):
    pass


def render_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def semantic_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise _DuplicateJsonKey(key)
            result[key] = value
        return result

    if path.is_symlink() or not path.is_file():
        raise ReferenceBatchError(f"{label} is missing or symlinked: {path}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonKey) as error:
        raise ReferenceBatchError(f"{label} is not strict JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ReferenceBatchError(f"{label} must be a JSON object: {path}")
    return value


def _safe_path(base: Path, relative_path: str, *, label: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts or relative_path == "":
        raise ReferenceBatchError(f"{label} path is not repository-relative: {relative_path}")
    base = base.resolve()
    candidate = base / relative
    resolved = candidate.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as error:
        raise ReferenceBatchError(f"{label} path escapes its owner: {relative_path}") from error
    if candidate.is_symlink() or not candidate.is_file():
        raise ReferenceBatchError(f"{label} is missing or symlinked: {relative_path}")
    return candidate


def _artifact(root: Path, relative_path: Path) -> dict[str, str]:
    path = _safe_path(root, relative_path.as_posix(), label="artifact")
    return {
        "path": relative_path.as_posix(),
        "sha256": sha256_file(path),
    }


def _verify_artifact(
    base: Path,
    artifact: Mapping[str, Any] | None,
    *,
    label: str,
    required: bool,
) -> bool:
    if artifact is None:
        if required:
            raise ReferenceBatchError(f"{label} binding is required")
        return False
    if set(artifact) != {"path", "sha256"}:
        raise ReferenceBatchError(f"{label} binding keys are not closed-world")
    path = artifact.get("path")
    digest = artifact.get("sha256")
    if not isinstance(path, str) or not path:
        raise ReferenceBatchError(f"{label} path is invalid")
    if digest is None and not required:
        return False
    if not isinstance(digest, str) or len(digest) != 64:
        raise ReferenceBatchError(f"{label} SHA-256 is missing or invalid")
    absolute = _safe_path(base, path, label=label)
    actual = sha256_file(absolute)
    if actual != digest:
        raise ReferenceBatchError(
            f"{label} SHA-256 drifted: expected {digest}, observed {actual}"
        )
    return True


def _materialize_planned_artifact(
    base: Path,
    artifact: Mapping[str, Any] | None,
    *,
    label: str,
) -> dict[str, Any]:
    """Bind a failure artifact whose planned record legitimately has no SHA."""

    if artifact is None or set(artifact) != {"path", "sha256"}:
        raise ReferenceBatchError(f"{label} planned binding is invalid")
    path = artifact.get("path")
    bound_digest = artifact.get("sha256")
    if not isinstance(path, str) or not path:
        raise ReferenceBatchError(f"{label} planned path is invalid")
    absolute = _safe_path(base, path, label=label)
    actual_digest = sha256_file(absolute)
    if bound_digest is not None and bound_digest != actual_digest:
        raise ReferenceBatchError(f"{label} bound SHA-256 drifted")
    return {
        "path": path,
        "batch_manifest_sha256": bound_digest,
        "observed_sha256": actual_digest,
    }


def _load_jsonl(path: Path, *, batch_id: str) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise ReferenceBatchError(f"Pipeline JSONL is missing or symlinked: {path}")
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line:
            raise ReferenceBatchError(f"Pipeline JSONL has an empty line: {line_number}")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ReferenceBatchError(
                f"Pipeline JSONL line {line_number} is invalid: {error}"
            ) from error
        if not isinstance(event, dict) or event.get("batch_id") != batch_id:
            raise ReferenceBatchError(
                f"Pipeline JSONL line {line_number} has a foreign batch identity"
            )
        events.append(event)
    if not events:
        raise ReferenceBatchError("Pipeline JSONL is empty")
    return events


def _item_map(values: Sequence[Mapping[str, Any]], *, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in values:
        item_id = value.get("item_id")
        if not isinstance(item_id, str) or not item_id or item_id in result:
            raise ReferenceBatchError(f"{label} contains an invalid or duplicate item_id")
        result[item_id] = dict(value)
    return result


def _planning_state(item: Mapping[str, Any]) -> str:
    reason = item.get("skip_reason")
    if reason is None:
        return "runnable"
    if not isinstance(reason, Mapping):
        raise ReferenceBatchError(f"Invalid skip reason for {item.get('item_id')}")
    code = reason.get("code")
    if not isinstance(code, str) or not code:
        raise ReferenceBatchError(f"Invalid skip code for {item.get('item_id')}")
    return code.lower()


def _input_identity(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "capability_status": item.get("capability_status"),
        "config": item.get("config"),
        "normalized_input": item.get("normalized_input"),
        "page_model": item.get("page_model"),
        "product_key": item.get("product_key"),
        "resource": item.get("resource"),
        "skip_reason": item.get("skip_reason"),
        "source": item.get("source"),
        "strategy": item.get("strategy"),
        "support_article_type": item.get("support_article_type"),
    }


def _outcome(item: Mapping[str, Any]) -> dict[str, Any]:
    status = item.get("status")
    if not isinstance(status, Mapping):
        raise ReferenceBatchError(f"Missing status for {item.get('item_id')}")
    return {
        "execution": status.get("execution"),
        "validation": status.get("validation"),
        "error": item.get("error"),
    }


def _machine_passed(item: Mapping[str, Any]) -> bool:
    status = item.get("status", {})
    return (
        isinstance(status, Mapping)
        and status.get("execution") == "succeeded"
        and status.get("validation") == "passed"
    )


def _payload_sha(item: Mapping[str, Any]) -> str | None:
    artifacts = item.get("artifacts")
    if not isinstance(artifacts, Mapping):
        return None
    payload = artifacts.get("payload")
    if not isinstance(payload, Mapping):
        return None
    digest = payload.get("sha256")
    return digest if isinstance(digest, str) else None


def failure_groups(items: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for item_id, item in items.items():
        status = item.get("status")
        if not isinstance(status, Mapping) or status.get("execution") != "failed":
            continue
        error = item.get("error")
        if not isinstance(error, Mapping):
            raise ReferenceBatchError(f"Failed item has no stable error: {item_id}")
        stage = error.get("stage")
        code = error.get("code")
        message = error.get("message")
        if not all(isinstance(value, str) and value for value in (stage, code, message)):
            raise ReferenceBatchError(f"Failed item has incomplete stable error: {item_id}")
        grouped[(stage, code, message)].append(item_id)
    return [
        {
            "stage": stage,
            "code": code,
            "message": message,
            "count": len(item_ids),
            "item_ids": sorted(item_ids),
        }
        for (stage, code, message), item_ids in sorted(grouped.items())
    ]


def verify_review_queue_projection(
    review_queue: Mapping[str, Any],
    batch_manifest: Mapping[str, Any],
    *,
    expected_item_ids: set[str],
) -> None:
    """Prove an earlier queue projection still matches current item authorities."""

    queue_revision = review_queue.get("manifest_revision")
    batch_revision = batch_manifest.get("revision")
    if (
        not isinstance(queue_revision, int)
        or not isinstance(batch_revision, int)
        or queue_revision > batch_revision
    ):
        raise ReferenceBatchError("Review Queue revision is invalid or ahead of Batch")
    queue_items = _item_map(review_queue["items"], label="Review Queue")
    if set(queue_items) != expected_item_ids:
        raise ReferenceBatchError("Review Queue has a missing or extra machine-passed item")
    batch_items = batch_manifest["items"]
    for item_id, projected in queue_items.items():
        current = batch_items[item_id]
        if projected.get("status") != current.get("status"):
            raise ReferenceBatchError(f"Review Queue item status is stale: {item_id}")
        projected_artifacts = projected.get("artifacts")
        current_artifacts = current.get("artifacts")
        if not isinstance(projected_artifacts, Mapping) or not isinstance(
            current_artifacts, Mapping
        ):
            raise ReferenceBatchError(f"Review Queue item artifacts are invalid: {item_id}")
        for key, binding in projected_artifacts.items():
            if current_artifacts.get(key) != binding:
                raise ReferenceBatchError(
                    f"Review Queue item artifact is stale: {item_id}/{key}"
                )


def _changed_fields(old: Mapping[str, Any], new: Mapping[str, Any]) -> list[str]:
    return sorted(key for key in set(old) | set(new) if old.get(key) != new.get(key))


def compare_batch_documents(
    predecessor_input: Mapping[str, Any],
    predecessor_batch: Mapping[str, Any],
    current_input: Mapping[str, Any],
    current_batch: Mapping[str, Any],
    *,
    regression_rationales: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Compare immutable inputs, outcomes, and current output records item by item."""

    old_inputs = _item_map(predecessor_input["items"], label="predecessor input")
    new_inputs = _item_map(current_input["items"], label="current input")
    old_items = {key: dict(value) for key, value in predecessor_batch["items"].items()}
    new_items = {key: dict(value) for key, value in current_batch["items"].items()}
    old_ids = set(old_inputs)
    new_ids = set(new_inputs)
    if set(old_items) != old_ids or set(new_items) != new_ids:
        raise ReferenceBatchError("Input and Batch item membership differ during comparison")

    common_ids = sorted(old_ids & new_ids)
    input_changes: list[dict[str, Any]] = []
    planning_transitions: list[dict[str, Any]] = []
    outcome_changes: list[dict[str, Any]] = []
    payload_changes: list[dict[str, Any]] = []
    improvements: list[str] = []
    regressions: list[dict[str, Any]] = []
    rationale_map = dict(regression_rationales or {})

    for item_id in common_ids:
        old_input_identity = _input_identity(old_inputs[item_id])
        new_input_identity = _input_identity(new_inputs[item_id])
        fields = _changed_fields(old_input_identity, new_input_identity)
        if fields:
            input_changes.append(
                {
                    "item_id": item_id,
                    "changed_fields": fields,
                    "old": {key: old_input_identity[key] for key in fields},
                    "new": {key: new_input_identity[key] for key in fields},
                }
            )

        old_state = _planning_state(old_inputs[item_id])
        new_state = _planning_state(new_inputs[item_id])
        if old_state != new_state:
            planning_transitions.append(
                {"item_id": item_id, "old": old_state, "new": new_state}
            )

        old_outcome = _outcome(old_items[item_id])
        new_outcome = _outcome(new_items[item_id])
        if old_outcome != new_outcome:
            outcome_changes.append(
                {"item_id": item_id, "old": old_outcome, "new": new_outcome}
            )

        old_payload = _payload_sha(old_items[item_id])
        new_payload = _payload_sha(new_items[item_id])
        if old_payload != new_payload:
            payload_changes.append(
                {
                    "item_id": item_id,
                    "old_payload_sha256": old_payload,
                    "new_payload_sha256": new_payload,
                }
            )

        old_passed = _machine_passed(old_items[item_id])
        new_passed = _machine_passed(new_items[item_id])
        if not old_passed and new_passed:
            improvements.append(item_id)
        elif old_passed and not new_passed:
            regressions.append(
                {
                    "item_id": item_id,
                    "old": old_outcome,
                    "new": new_outcome,
                    "explanation": rationale_map.get(item_id),
                }
            )

    regression_ids = {item["item_id"] for item in regressions}
    unknown_rationales = sorted(set(rationale_map) - regression_ids)
    if unknown_rationales:
        raise ReferenceBatchError(
            "Regression rationales name non-regressions: " + ", ".join(unknown_rationales)
        )
    unexplained = sorted(
        item["item_id"] for item in regressions if item["explanation"] is None
    )
    return {
        "predecessor_batch_id": predecessor_batch["batch_id"],
        "current_batch_id": current_batch["batch_id"],
        "membership": {
            "predecessor_count": len(old_ids),
            "current_count": len(new_ids),
            "common_count": len(common_ids),
            "added_item_ids": sorted(new_ids - old_ids),
            "removed_item_ids": sorted(old_ids - new_ids),
        },
        "planning_transitions": planning_transitions,
        "input_identity_changes": input_changes,
        "outcome_changes": outcome_changes,
        "payload_sha_changes": payload_changes,
        "improvements": sorted(improvements),
        "regressions": regressions,
        "unexplained_regression_item_ids": unexplained,
    }


def load_regression_rationales(
    root: Path,
    relative_path: Path | None,
    *,
    predecessor_batch_id: str,
    reference_batch_id: str,
) -> tuple[dict[str, str], dict[str, str] | None]:
    if relative_path is None:
        return {}, None
    document = _read_json(root / relative_path, label="regression rationale")
    if set(document) != {
        "schema_version",
        "predecessor_batch_id",
        "reference_batch_id",
        "regressions",
    }:
        raise ReferenceBatchError("Regression rationale document keys are not closed-world")
    if document["schema_version"] != "1.0":
        raise ReferenceBatchError("Unsupported regression rationale schema_version")
    if document["predecessor_batch_id"] != predecessor_batch_id:
        raise ReferenceBatchError("Regression rationale predecessor binding differs")
    if document["reference_batch_id"] != reference_batch_id:
        raise ReferenceBatchError("Regression rationale reference binding differs")
    rationales: dict[str, str] = {}
    for row in document["regressions"]:
        if not isinstance(row, dict) or set(row) != {"item_id", "explanation"}:
            raise ReferenceBatchError("Regression rationale row keys are not closed-world")
        item_id = row["item_id"]
        explanation = row["explanation"]
        if (
            not isinstance(item_id, str)
            or not item_id
            or item_id in rationales
            or not isinstance(explanation, str)
            or not explanation.strip()
        ):
            raise ReferenceBatchError("Regression rationale row is invalid or duplicate")
        rationales[item_id] = explanation
    return rationales, _artifact(root, relative_path)


def _root_relative(root: Path, path: Path, *, label: str) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise ReferenceBatchError(f"{label} must remain inside the repository") from error


def _load_batch_authorities(
    root: Path,
    runs_dir: str | Path,
    batch_id: str,
    *,
    verify_current_inputs: bool = True,
) -> dict[str, Any]:
    store = StateStore(root, runs_dir=runs_dir)
    run_dir = store.run_dir(batch_id)
    if verify_current_inputs:
        input_manifest = store.read_input_manifest(batch_id)
        batch_manifest = store.read_manifest(batch_id)
    else:
        # Historical evidence remains valid for its frozen bytes even when those
        # bytes are no longer the active inputs.  Reuse StateStore's full schema
        # and semantic validation without its intentionally current-only replay.
        input_manifest = store._read(  # noqa: SLF001
            run_dir / "input-manifest.json",
            "input",
            verify_context=False,
        )
        batch_manifest = store._read(  # noqa: SLF001
            run_dir / "batch-manifest.json",
            "batch",
            verify_context=False,
        )
        if input_manifest.get("batch_id") != batch_id:
            raise ReferenceBatchError("Historical Input Manifest identity differs")
        if batch_manifest.get("batch_id") != batch_id:
            raise ReferenceBatchError("Historical Batch Manifest identity differs")
        input_binding = batch_manifest.get("input_manifest")
        if not isinstance(input_binding, Mapping):
            raise ReferenceBatchError("Historical input binding is missing")
        if input_binding.get("path") != "input-manifest.json":
            raise ReferenceBatchError("Historical input binding path differs")
        if input_binding.get("sha256") != sha256_file(
            run_dir / "input-manifest.json"
        ):
            raise ReferenceBatchError("Historical input binding SHA-256 drifted")
        if input_manifest.get("schema_version") != batch_manifest.get(
            "schema_version"
        ):
            raise ReferenceBatchError("Historical Input/Batch schemas differ")
        for key in ("planning", "validation_context", "frozen_inputs"):
            if input_manifest.get(key) != batch_manifest.get(key):
                raise ReferenceBatchError(
                    f"Historical Input/Batch frozen binding differs: {key}"
                )
    batch_report_path = run_dir / "batch-report.json"
    review_queue_path = run_dir / "review" / "review-queue.json"
    jsonl_path = run_dir / "logs" / "pipeline.jsonl"
    batch_report = _read_json(batch_report_path, label="Batch Report")
    review_queue = _read_json(review_queue_path, label="Review Queue")
    store._validate(  # noqa: SLF001
        batch_report,
        "report",
        verify_context=verify_current_inputs,
    )
    store._validate(  # noqa: SLF001
        review_queue,
        "review",
        verify_context=verify_current_inputs,
    )
    if batch_report.get("batch_id") != batch_id:
        raise ReferenceBatchError("Batch Report identity differs from its directory")
    if review_queue.get("batch_id") != batch_id:
        raise ReferenceBatchError("Review Queue identity differs from its directory")
    return {
        "store": store,
        "run_dir": run_dir,
        "input": input_manifest,
        "batch": batch_manifest,
        "report": batch_report,
        "review": review_queue,
        "events": _load_jsonl(jsonl_path, batch_id=batch_id),
        "paths": {
            "input": run_dir / "input-manifest.json",
            "batch": run_dir / "batch-manifest.json",
            "report": batch_report_path,
            "review": review_queue_path,
            "jsonl": jsonl_path,
        },
    }


def _expected_planning_identity(root: Path) -> dict[str, str]:
    path = root / PLANNING_BASELINE_PATH
    document = _read_json(path, label="v0.5 Planning Baseline")
    if document.get("baseline_id") != EXPECTED_PLANNING_BASELINE_ID:
        raise ReferenceBatchError("The active Planning Baseline ID drifted")
    return {
        "id": EXPECTED_PLANNING_BASELINE_ID,
        "schema_version": str(document["schema_version"]),
        "path": PLANNING_BASELINE_PATH.as_posix(),
        "sha256": sha256_file(path),
    }


def _verify_post_v051_successor_namespace(run_dir: Path) -> None:
    """Keep the v0.5.1 audit historical while rejecting unsafe successor paths.

    The accepted v0.5.1 report truthfully records zero formal L3b artifacts at
    its acceptance point.  Later versions are explicitly allowed to add their
    own evidence below ``independent-fidelity/`` without mutating any v0.5.1
    authority.  The historical accounting therefore ignores that successor
    namespace, but still requires it and every descendant to be a real
    directory or regular file rather than a symbolic-link escape.
    """

    successor = run_dir / "independent-fidelity"
    if not successor.exists() and not successor.is_symlink():
        return
    if successor.is_symlink() or not successor.is_dir():
        raise ReferenceBatchError(
            "Post-v0.5.1 independent-fidelity successor namespace is unsafe"
        )
    for path in successor.rglob("*"):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise ReferenceBatchError(
                "Post-v0.5.1 independent-fidelity successor path is unsafe: "
                f"{path.relative_to(run_dir).as_posix()}"
            )


def _verify_reference_accounting(
    current: Mapping[str, Any],
    *,
    root: Path,
    expected_git_commit: str,
) -> dict[str, Any]:
    input_manifest = current["input"]
    batch_manifest = current["batch"]
    batch_report = current["report"]
    review_queue = current["review"]
    events = current["events"]
    run_dir = current["run_dir"]
    batch_id = batch_manifest["batch_id"]

    if input_manifest.get("scope") != {"kind": "all"}:
        raise ReferenceBatchError("Reference Batch scope is not --all")
    if set(input_manifest.get("languages", [])) != {"zh-cn", "en-us"}:
        raise ReferenceBatchError("Reference Batch is not bilingual")
    if input_manifest.get("summary") != EXPECTED_PLANNING_SUMMARY:
        raise ReferenceBatchError(
            f"Reference input accounting differs: {input_manifest.get('summary')}"
        )
    expected_planning = _expected_planning_identity(root)
    if input_manifest.get("planning", {}).get("baseline") != expected_planning:
        raise ReferenceBatchError("Reference Batch does not bind the v0.5 Planning Baseline")
    expected_baseline_accounting = {
        "accounted": 383,
        "coverage": "383/383",
        "denominator": 383,
        "retained_runnable": 383,
        "reviewed_non_runnable": 0,
    }
    if input_manifest["planning"].get("baseline_accounting") != (
        expected_baseline_accounting
    ):
        raise ReferenceBatchError("Reference Batch baseline accounting differs")

    provenance = input_manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ReferenceBatchError("Reference Batch provenance is missing")
    if (
        provenance.get("git_commit") != expected_git_commit
        or provenance.get("dirty") is not False
        or provenance.get("reproducible") is not True
        or provenance.get("worktree_changes") != []
    ):
        raise ReferenceBatchError(
            "Reference Batch was not created from the authorized clean commit"
        )
    if len(expected_git_commit) != 40:
        raise ReferenceBatchError("Expected git commit must be a full 40-character SHA")

    if batch_manifest.get("status") not in {"completed", "completed_with_failures"}:
        raise ReferenceBatchError("Reference Batch is not complete")
    for key, value in EXPECTED_PLANNING_SUMMARY.items():
        if batch_manifest.get("summary", {}).get(key) != value:
            raise ReferenceBatchError(f"Reference Batch summary drifted at {key}")
    if batch_report.get("summary") != batch_manifest.get("summary"):
        raise ReferenceBatchError("Batch Report summary is not current")
    if batch_report.get("status") != batch_manifest.get("status"):
        raise ReferenceBatchError("Batch Report status is not current")
    if batch_report.get("revision") != batch_manifest.get("revision"):
        raise ReferenceBatchError("Batch Report does not bind the current Batch revision")

    input_items = _item_map(input_manifest["items"], label="reference input")
    batch_items = {
        key: dict(value) for key, value in batch_manifest.get("items", {}).items()
    }
    report_items = _item_map(batch_report["items"], label="Batch Report")
    if set(input_items) != set(batch_items) or set(report_items) != set(batch_items):
        raise ReferenceBatchError("Reference Batch has an unexplained item membership gap")
    if len(batch_items) != 434:
        raise ReferenceBatchError("Reference Batch does not contain exactly 434 items")

    execution_counts: Counter[str] = Counter()
    validation_counts: Counter[str] = Counter()
    output_records: list[dict[str, Any]] = []
    stable_failure_count = 0
    diagnostic_log_count = 0
    preflight_parseability_count = 0
    preflight_parseability_artifacts: list[dict[str, Any]] = []
    machine_passed_ids: set[str] = set()

    for item_id in sorted(batch_items):
        frozen = input_items[item_id]
        current_item = batch_items[item_id]
        projected = report_items[item_id]
        if current_item.get("item_id") != item_id:
            raise ReferenceBatchError(f"Batch Item identity differs: {item_id}")
        if (
            projected.get("status") != current_item.get("status")
            or projected.get("error") != current_item.get("error")
            or projected.get("artifacts") != current_item.get("artifacts")
        ):
            raise ReferenceBatchError(f"Batch Report item is stale: {item_id}")

        status = current_item.get("status")
        artifacts = current_item.get("artifacts")
        if not isinstance(status, Mapping) or not isinstance(artifacts, Mapping):
            raise ReferenceBatchError(f"Batch Item status/artifacts are missing: {item_id}")
        execution = status.get("execution")
        validation = status.get("validation")
        if not isinstance(execution, str) or not isinstance(validation, str):
            raise ReferenceBatchError(f"Batch Item status is invalid: {item_id}")
        execution_counts[execution] += 1
        validation_counts[validation] += 1

        skipped = frozen.get("skip_reason") is not None
        if skipped:
            if execution != "skipped" or validation != "not_run":
                raise ReferenceBatchError(f"Skipped item was unexpectedly executed: {item_id}")
        elif execution not in {"succeeded", "failed"}:
            raise ReferenceBatchError(f"Runnable item has a queue gap: {item_id}")
        elif execution == "succeeded" and validation not in {"passed", "failed"}:
            raise ReferenceBatchError(f"Successful item was not validated: {item_id}")
        elif execution == "failed" and validation != "not_run":
            raise ReferenceBatchError(f"Failed extraction has invalid validation state: {item_id}")

        error = current_item.get("error")
        error_stage = error.get("stage") if isinstance(error, Mapping) else None
        if not skipped:
            _verify_artifact(
                run_dir,
                artifacts.get("diagnostic"),
                label=f"{item_id} diagnostic",
                required=error_stage != "preflight",
            )
            _verify_artifact(
                run_dir,
                artifacts.get("parseability"),
                label=f"{item_id} parseability",
                required=error_stage != "preflight",
            )
            if error_stage == "preflight":
                preflight_parseability_artifacts.append(
                    {
                        "item_id": item_id,
                        **_materialize_planned_artifact(
                            run_dir,
                            artifacts.get("parseability"),
                            label=f"{item_id} parseability",
                        ),
                    }
                )
        if execution == "succeeded":
            for artifact_key in ("payload", "validation", "sampled_content_evidence"):
                _verify_artifact(
                    run_dir,
                    artifacts.get(artifact_key),
                    label=f"{item_id} {artifact_key}",
                    required=True,
                )
            _verify_artifact(
                run_dir,
                artifacts.get("sampling_plan"),
                label=f"{item_id} sampling_plan",
                required=False,
            )
        elif execution == "failed":
            if not isinstance(error, Mapping):
                raise ReferenceBatchError(f"Failed item has no error: {item_id}")
            stage = error.get("stage")
            code = error.get("code")
            message = error.get("message")
            if not all(
                isinstance(value, str) and value for value in (stage, code, message)
            ):
                raise ReferenceBatchError(f"Failed item error is unstable: {item_id}")
            stable_failure_count += 1
            diagnostic = artifacts.get("diagnostic")
            diagnostic_path = diagnostic.get("path") if isinstance(diagnostic, Mapping) else None
            matching_events = [
                event
                for event in events
                if event.get("item_id") == item_id
                and event.get("stage") == stage
                and event.get("status") == "failed"
                and event.get("error_code") == code
                and event.get("message") == message
                and event.get("diagnostic_path") == diagnostic_path
            ]
            if not matching_events:
                raise ReferenceBatchError(
                    f"Failed item lacks matching stable JSONL evidence: {item_id}"
                )
            diagnostic_log_count += 1
            if stage == "preflight":
                parseability = artifacts.get("parseability")
                parseability_path = (
                    parseability.get("path") if isinstance(parseability, Mapping) else None
                )
                if not any(
                    event.get("parseability_path") == parseability_path
                    for event in matching_events
                ):
                    raise ReferenceBatchError(
                        f"Preflight failure lacks parseability JSONL evidence: {item_id}"
                    )
                preflight_parseability_count += 1

        if _machine_passed(current_item):
            machine_passed_ids.add(item_id)
        if artifacts.get("current_review_decision") is not None:
            raise ReferenceBatchError(
                f"Reference Batch unexpectedly contains an L4 decision: {item_id}"
            )
        if status.get("release") != "not_released":
            raise ReferenceBatchError(f"Reference Batch item was released: {item_id}")
        if status.get("publication") != "not_published":
            raise ReferenceBatchError(f"Reference Batch item was published: {item_id}")
        output_records.append(
            {
                "item_id": item_id,
                "execution": execution,
                "validation": validation,
                "payload": artifacts.get("payload"),
                "diagnostic": artifacts.get("diagnostic"),
                "parseability": artifacts.get("parseability"),
                "validation_artifact": artifacts.get("validation"),
                "error": current_item.get("error"),
            }
        )

    expected_execution = {
        "skipped": 51,
        "succeeded": batch_manifest["summary"]["execution_succeeded"],
        "failed": batch_manifest["summary"]["execution_failed"],
    }
    if dict(execution_counts) != {key: value for key, value in expected_execution.items() if value}:
        raise ReferenceBatchError("Execution accounting does not match the item closed world")
    expected_validation = {
        "passed": batch_manifest["summary"]["validation_passed"],
        "failed": batch_manifest["summary"]["validation_failed"],
        "not_run": batch_manifest["summary"]["validation_not_run"] + 51,
    }
    if dict(validation_counts) != {
        key: value for key, value in expected_validation.items() if value
    }:
        raise ReferenceBatchError("Validation accounting does not match the item closed world")

    verify_review_queue_projection(
        review_queue,
        batch_manifest,
        expected_item_ids=machine_passed_ids,
    )
    if review_queue.get("summary", {}).get("total") != len(machine_passed_ids):
        raise ReferenceBatchError("Review Queue summary has an accounting gap")
    if batch_manifest.get("release_manifests") != []:
        raise ReferenceBatchError("Reference Batch unexpectedly registered a Release")
    if batch_manifest.get("publication_receipts") != []:
        raise ReferenceBatchError("Reference Batch unexpectedly registered a Publication")
    _verify_post_v051_successor_namespace(run_dir)

    input_records = [
        {"item_id": item_id, "identity": _input_identity(input_items[item_id])}
        for item_id in sorted(input_items)
    ]
    return {
        "accounting": dict(batch_manifest["summary"]),
        "input_binding_semantic_sha256": semantic_sha256(input_records),
        "current_output_record_semantic_sha256": semantic_sha256(output_records),
        "current_output_record_count": len(output_records),
        "failure_evidence": {
            "failed_items": execution_counts.get("failed", 0),
            "stable_code_and_message": stable_failure_count,
            "matching_diagnostic_path_in_jsonl": diagnostic_log_count,
            "preflight_parseability_path_in_jsonl": preflight_parseability_count,
            "preflight_parseability_artifacts": preflight_parseability_artifacts,
        },
        "failure_groups": failure_groups(batch_items),
        "machine_passed_item_count": len(machine_passed_ids),
        "formal_l3b_evidence_count": 0,
    }


def _problem_map(
    predecessor_batch: Mapping[str, Any],
    current_batch: Mapping[str, Any],
) -> dict[str, Any]:
    old_items = {
        key: dict(value) for key, value in predecessor_batch["items"].items()
    }
    new_items = {key: dict(value) for key, value in current_batch["items"].items()}
    old_failed = {
        item_id
        for item_id, item in old_items.items()
        if item.get("status", {}).get("execution") == "failed"
    }
    new_failed = {
        item_id
        for item_id, item in new_items.items()
        if item.get("status", {}).get("execution") == "failed"
    }
    code_counts = Counter(
        str(new_items[item_id]["error"]["code"]) for item_id in new_failed
    )
    return {
        "current_failure_groups": failure_groups(new_items),
        "failure_code_counts": [
            {"code": code, "count": count}
            for code, count in sorted(code_counts.items())
        ],
        "introduced_failed_item_ids": sorted(new_failed - old_failed),
        "resolved_failed_item_ids": sorted(old_failed - new_failed),
        "retained_failed_item_ids": sorted(old_failed & new_failed),
    }


def _accepted_predecessor(
    root: Path,
    runs_dir: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    planning_path = root / PLANNING_BASELINE_PATH
    planning = _read_json(planning_path, label="v0.5 Planning Baseline")
    predecessor = planning.get("predecessor")
    if not isinstance(predecessor, Mapping):
        raise ReferenceBatchError("Planning Baseline predecessor binding is missing")
    accepted_batch_id = predecessor.get("accepted_batch_id")
    accepted_report_binding = predecessor.get("accepted_batch_report")
    if not isinstance(accepted_batch_id, str) or not accepted_batch_id:
        raise ReferenceBatchError("Accepted predecessor Batch ID is missing")
    if not isinstance(accepted_report_binding, Mapping):
        raise ReferenceBatchError("Accepted predecessor report binding is missing")
    report_path = accepted_report_binding.get("path")
    report_sha = accepted_report_binding.get("sha256")
    if not isinstance(report_path, str) or not isinstance(report_sha, str):
        raise ReferenceBatchError("Accepted predecessor report binding is invalid")
    accepted_report_file = _safe_path(root, report_path, label="accepted v0.4.1 report")
    if sha256_file(accepted_report_file) != report_sha:
        raise ReferenceBatchError("Accepted v0.4.1 report SHA-256 drifted")
    accepted_report = _read_json(
        accepted_report_file,
        label="accepted v0.4.1 report",
    )
    if accepted_report.get("result") != "accepted":
        raise ReferenceBatchError("v0.4.1 predecessor report is not accepted")
    if accepted_report.get("accepted_batch", {}).get("batch_id") != accepted_batch_id:
        raise ReferenceBatchError("v0.4.1 report and Planning predecessor differ")
    predecessor_authorities = _load_batch_authorities(
        root,
        runs_dir,
        accepted_batch_id,
        verify_current_inputs=False,
    )
    accepted_batch_binding = accepted_report.get("artifacts", {}).get(
        "batch_manifest"
    )
    accepted_input_binding = accepted_report.get("artifacts", {}).get(
        "input_manifest"
    )
    for label, binding, actual_path in (
        (
            "accepted v0.4.1 Batch Manifest",
            accepted_batch_binding,
            predecessor_authorities["paths"]["batch"],
        ),
        (
            "accepted v0.4.1 Input Manifest",
            accepted_input_binding,
            predecessor_authorities["paths"]["input"],
        ),
    ):
        if not isinstance(binding, Mapping) or binding.get("sha256") != sha256_file(
            actual_path
        ):
            raise ReferenceBatchError(f"{label} no longer matches its accepted report")
    if accepted_batch_binding.get("revision") != predecessor_authorities["batch"].get(
        "revision"
    ):
        raise ReferenceBatchError("Accepted v0.4.1 Batch revision drifted")
    return (
        predecessor_authorities,
        accepted_report,
        {"path": report_path, "sha256": report_sha},
    )


def _current_artifact_bindings(
    root: Path,
    current: Mapping[str, Any],
) -> dict[str, Any]:
    paths = current["paths"]
    return {
        "input_manifest": _artifact(
            root,
            _root_relative(root, paths["input"], label="Input Manifest"),
        ),
        "batch_manifest": {
            **_artifact(
                root,
                _root_relative(root, paths["batch"], label="Batch Manifest"),
            ),
            "revision": current["batch"]["revision"],
        },
        "batch_report": {
            **_artifact(
                root,
                _root_relative(root, paths["report"], label="Batch Report"),
            ),
            "revision": current["report"]["revision"],
        },
        "review_queue": {
            **_artifact(
                root,
                _root_relative(root, paths["review"], label="Review Queue"),
            ),
            "manifest_revision": current["review"]["manifest_revision"],
        },
        "jsonl": _artifact(
            root,
            _root_relative(root, paths["jsonl"], label="Pipeline JSONL"),
        ),
    }


def build_reference_batch_summary(
    root: str | Path,
    *,
    batch_id: str,
    expected_git_commit: str,
    runs_dir: str | Path = "runs",
    regression_rationales_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build one deterministic, read-only v0.5.1 reference Batch audit."""

    root_path = Path(root).resolve()
    current = _load_batch_authorities(root_path, runs_dir, batch_id)
    current_audit = _verify_reference_accounting(
        current,
        root=root_path,
        expected_git_commit=expected_git_commit,
    )
    predecessor, accepted_report, accepted_report_identity = _accepted_predecessor(
        root_path,
        runs_dir,
    )
    predecessor_batch_id = predecessor["batch"]["batch_id"]
    rationale_relative = (
        Path(regression_rationales_path)
        if regression_rationales_path is not None
        else None
    )
    if rationale_relative is not None and rationale_relative.is_absolute():
        rationale_relative = _root_relative(
            root_path,
            rationale_relative,
            label="regression rationale",
        )
    rationales, rationale_identity = load_regression_rationales(
        root_path,
        rationale_relative,
        predecessor_batch_id=predecessor_batch_id,
        reference_batch_id=batch_id,
    )
    comparison = compare_batch_documents(
        predecessor["input"],
        predecessor["batch"],
        current["input"],
        current["batch"],
        regression_rationales=rationales,
    )
    membership = comparison["membership"]
    if membership["added_item_ids"] or membership["removed_item_ids"]:
        raise ReferenceBatchError("Reference and predecessor Batch membership differ")
    transitions = {
        row["item_id"]
        for row in comparison["planning_transitions"]
        if row["old"] == "known_unsupported" and row["new"] == "runnable"
    }
    if transitions != EXPECTED_PLANNING_TRANSITIONS or len(
        comparison["planning_transitions"]
    ) != 4:
        raise ReferenceBatchError(
            "Reference Batch planning transitions are not the reviewed four-item set"
        )

    unexplained = comparison["unexplained_regression_item_ids"]
    result = "qualified" if not unexplained else "blocked"
    current_artifacts = _current_artifact_bindings(root_path, current)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": current["batch"]["updated_at"],
        "result": result,
        "reference_batch": {
            "batch_id": batch_id,
            "run_dir": _root_relative(
                root_path,
                current["run_dir"],
                label="reference run",
            ).as_posix(),
            "status": current["batch"]["status"],
            "revision": current["batch"]["revision"],
            "provenance": {
                "git_commit": current["input"]["provenance"]["git_commit"],
                "dirty": current["input"]["provenance"]["dirty"],
                "reproducible": current["input"]["provenance"]["reproducible"],
                "worktree_changes": current["input"]["provenance"][
                    "worktree_changes"
                ],
            },
        },
        "scope": {
            "machine_claim": "current_execution_and_l3a",
            "formal_l3b_recorded": False,
            "machine_gate_policy_changed": False,
        },
        "accounting": current_audit["accounting"],
        "bindings": {
            "planning_baseline": current["input"]["planning"]["baseline"],
            "input_binding_semantic_sha256": current_audit[
                "input_binding_semantic_sha256"
            ],
            "current_output_record_semantic_sha256": current_audit[
                "current_output_record_semantic_sha256"
            ],
            "current_output_record_count": current_audit[
                "current_output_record_count"
            ],
        },
        "artifacts": {
            **current_artifacts,
            "accepted_v0_4_1_report": accepted_report_identity,
            "regression_rationales": rationale_identity,
        },
        "failure_evidence": current_audit["failure_evidence"],
        "comparison_to_accepted_v0_4_1": comparison,
        "problem_map": _problem_map(predecessor["batch"], current["batch"]),
        "boundaries": {
            "formal_l3b_evidence_count": current_audit[
                "formal_l3b_evidence_count"
            ],
            "l4_review_decisions_written": 0,
            "release_built": False,
            "upload_executed": False,
            "accepted_v0_4_1_artifacts_modified": False,
        },
        "acceptance": {
            "closed_world_accounting": True,
            "current_input_and_output_bindings": True,
            "stable_failure_diagnostics": True,
            "queue_gap_count": 0,
            "unexplained_regression_count": len(unexplained),
            "accepted_predecessor_result": accepted_report["result"],
        },
    }
    report["semantic_sha256"] = semantic_sha256(report)
    return report


def verify_reference_batch_summary(
    root: str | Path,
    *,
    report_path: str | Path,
    runs_dir: str | Path = "runs",
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    candidate = Path(report_path)
    if candidate.is_absolute():
        candidate = _root_relative(root_path, candidate, label="reference report")
    report = _read_json(root_path / candidate, label="v0.5.1 reference report")
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ReferenceBatchError("Reference report schema_version differs")
    observed_identity = report.get("semantic_sha256")
    body = {key: value for key, value in report.items() if key != "semantic_sha256"}
    if observed_identity != semantic_sha256(body):
        raise ReferenceBatchError("Reference report semantic identity drifted")
    rationale = report.get("artifacts", {}).get("regression_rationales")
    rationale_path = rationale.get("path") if isinstance(rationale, Mapping) else None
    expected = build_reference_batch_summary(
        root_path,
        batch_id=report["reference_batch"]["batch_id"],
        expected_git_commit=report["reference_batch"]["provenance"]["git_commit"],
        runs_dir=runs_dir,
        regression_rationales_path=rationale_path,
    )
    if report != expected:
        raise ReferenceBatchError("Reference report no longer matches current authorities")
    if report["result"] != "qualified":
        raise ReferenceBatchError(
            "Reference report remains blocked by unexplained regressions"
        )
    return report


def write_reference_batch_summary(
    root: str | Path,
    report: Mapping[str, Any],
    *,
    output_path: str | Path,
) -> Path:
    root_path = Path(root).resolve()
    target = Path(output_path)
    if not target.is_absolute():
        target = root_path / target
    try:
        target.resolve().relative_to(root_path)
    except ValueError as error:
        raise ReferenceBatchError("Reference report output must remain in the repository") from error
    if target.is_symlink():
        raise ReferenceBatchError("Reference report output cannot be a symlink")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_json(dict(report)), encoding="utf-8")
    return target


__all__ = [
    "EXPECTED_PLANNING_SUMMARY",
    "EXPECTED_PLANNING_TRANSITIONS",
    "ReferenceBatchError",
    "build_reference_batch_summary",
    "compare_batch_documents",
    "failure_groups",
    "load_regression_rationales",
    "render_json",
    "semantic_sha256",
    "verify_review_queue_projection",
    "verify_reference_batch_summary",
    "write_reference_batch_summary",
]
