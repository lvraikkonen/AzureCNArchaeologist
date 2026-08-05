"""Step 6 Core regression harness.

The public pipeline can plan all products or one catalog group.  Step 6 needs a
small cross-strategy matrix, so this module provides a closed-world planner that
selects exactly the reviewed Core items while leaving execution to the normal
PipelineCoordinator.
"""

from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from src.core.product_catalog import canonical_json, sha256_file
from src.core.validation_context import (
    CONTENT_SAMPLING_PROFILE_SPEC,
    FINDING_CODE_POLICY_SPEC,
    ValidationContextRegistry,
)
from src.pipeline.coordinator import PipelineCoordinator, PipelineOutcome
from src.pipeline.models import BatchItem, PipelinePlan
from src.pipeline.planner import PipelinePlanner
from src.pipeline.state_store import StateStore


CORE_GROUP = "v0.4-core-strategy-matrix"
FIXTURE_MANIFEST_PATH = Path("tests/fixtures/v0.4/core/fixture-manifest.json")
BASELINE_ROOT = Path("tests/fixtures/v0.4/core/baselines")
BASELINE_MANIFEST_PATH = BASELINE_ROOT / "baseline-manifest.json"
CANDIDATE_ROOT = Path("output/v0.4-core-baseline-candidates")
CORE_ITEM_IDS = (
    "zh-cn/api-management",
    "en-us/api-management",
    "zh-cn/cloud-services",
    "en-us/cloud-services",
    "zh-cn/service-bus",
    "en-us/service-bus",
    "zh-cn/icp-faq",
    "en-us/icp-faq",
)
CORE_EXPECTATIONS = {
    "api-management": ("region_filter", "FlexibleContentPage"),
    "cloud-services": ("complex", "FlexibleContentPage"),
    "service-bus": ("simple_static", "FlexibleContentPage"),
    "icp-faq": ("support_article", "SupportArticlePage"),
}
PRICING_FULL_GOLDENS = {"api-management", "cloud-services", "service-bus"}
SAMPLING_BASELINES = {"api-management", "cloud-services"}
FULL_CONTENT_NOT_APPLICABLE = {"service-bus"}
SUPPORT_BASELINES = {"icp-faq"}


class CoreRegressionError(RuntimeError):
    """A Step 6 Core fixture, run, or baseline violated its closed world."""


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CoreRegressionError(f"Expected JSON object: {path}")
    return value


def render_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def json_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_json(value), encoding="utf-8")


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError as error:
        raise CoreRegressionError(f"Path escapes repository root: {path}") from error


def _regular_file(root: Path, relative_path: str) -> Path:
    if relative_path.startswith("/") or ".." in Path(relative_path).parts:
        raise CoreRegressionError(f"Unsafe relative path: {relative_path}")
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise CoreRegressionError(f"Path escapes repository root: {relative_path}") from error
    if path.is_symlink() or not path.is_file():
        raise CoreRegressionError(f"Expected regular file: {relative_path}")
    return path


def _load_schema(root: Path, relative_path: str) -> dict[str, Any]:
    return read_json(root / relative_path)


def _validate_schema(root: Path, schema_relative: str, value: Mapping[str, Any]) -> None:
    schema = _load_schema(root, schema_relative)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        lines = []
        for error in errors:
            location = "/".join(str(part) for part in error.absolute_path) or "$"
            lines.append(f"{location}: {error.message}")
        raise CoreRegressionError(
            f"{schema_relative} validation failed:\n- " + "\n- ".join(lines)
        )


def _core_items_from_full_plan(full_plan: PipelinePlan) -> tuple[BatchItem, ...]:
    by_id = {item.item_id: item for item in full_plan.items}
    missing = [item_id for item_id in CORE_ITEM_IDS if item_id not in by_id]
    if missing:
        raise CoreRegressionError(f"Core item(s) missing from full plan: {missing}")

    selected = tuple(by_id[item_id] for item_id in CORE_ITEM_IDS)
    for item in selected:
        expected = CORE_EXPECTATIONS[item.product_key]
        if item.resource_kind != "current":
            raise CoreRegressionError(f"Core item is not current: {item.item_id}")
        if not item.runnable:
            raise CoreRegressionError(f"Core item is not runnable: {item.item_id}")
        if (item.strategy, item.page_model) != expected:
            raise CoreRegressionError(
                f"Core item shape drifted for {item.item_id}: "
                f"{item.strategy}/{item.page_model}"
            )
        for relative_path in (
            item.config_path,
            item.source_path,
            item.normalized_path,
        ):
            if relative_path is None:
                raise CoreRegressionError(f"Core item lacks path: {item.item_id}")
            _regular_file(full_plan_root(full_plan), relative_path)
    return selected


def full_plan_root(_plan: PipelinePlan) -> Path:
    # PipelinePlan intentionally has no root.  This helper is patched by callers
    # through the global CURRENT_ROOT while preserving a small pure selection API.
    return CURRENT_ROOT


CURRENT_ROOT = Path(".").resolve()


def _item_fixture(root: Path, item: BatchItem) -> dict[str, Any]:
    source_path = item.source_path
    if source_path is None:
        raise CoreRegressionError(f"Core item has no source path: {item.item_id}")
    source = _regular_file(root, source_path)
    normalized = _regular_file(root, item.normalized_path)
    actual_source_sha = sha256_file(source)
    actual_normalized_sha = sha256_file(normalized)
    if actual_source_sha != item.source_sha256:
        raise CoreRegressionError(f"Source hash drifted while planning {item.item_id}")
    if actual_normalized_sha != item.normalized_sha256:
        raise CoreRegressionError(
            f"Normalized input hash drifted while planning {item.item_id}"
        )
    if actual_source_sha != actual_normalized_sha:
        raise CoreRegressionError(
            f"Source and normalized input differ for {item.item_id}"
        )
    value = {
        "item_id": item.item_id,
        "language": item.language,
        "resource_key": item.resource_key,
        "product_key": item.product_key,
        "resource_kind": item.resource_kind,
        "strategy": item.strategy,
        "page_model": item.page_model,
        "capability_status": item.capability_status,
        "slug": item.slug,
        "catalog_categories": list(item.catalog_categories),
        "support_article_type": item.support_article_type,
        "config": {"path": item.config_path, "sha256": item.config_sha256},
        "source": {
            "availability": item.source_availability,
            "path": item.source_path,
            "sha256": item.source_sha256,
            "url": item.source_url,
            "cms_path": item.cms_path,
        },
        "normalized_input": {
            "path": item.normalized_path,
            "sha256": item.normalized_sha256,
        },
        "artifacts": {
            "payload": {"path": item.output_path},
            "diagnostic": {"path": item.diagnostic_path},
            "parseability": {"path": item.parseability_path},
            "validation": {"path": item.validation_path},
        },
    }
    if item.product_key == "icp-faq":
        value["controlled_source_reuse"] = {
            "applies_to": ["zh-cn/icp-faq", "en-us/icp-faq"],
            "source_content_language": "zh-cn",
            "claim": "separate_language_batch_items_without_english_translation_assertion",
        }
    return value


def build_fixture_manifest(root: Path) -> dict[str, Any]:
    global CURRENT_ROOT
    root = root.resolve()
    CURRENT_ROOT = root
    full_plan = PipelinePlanner(root).plan(language="both")
    selected = _core_items_from_full_plan(full_plan)
    registry = ValidationContextRegistry(root)
    frozen = registry.freeze()
    return {
        "schema_version": "1.0",
        "manifest_id": "v0.4-step6-core-fixture",
        "matrix_id": CORE_GROUP,
        "description": "Step 6 Slice A bilingual Core matrix fixture.",
        "languages": ["zh-cn", "en-us"],
        "expected_item_ids": list(CORE_ITEM_IDS),
        "items": [_item_fixture(root, item) for item in selected],
        "frozen_inputs": {
            **copy.deepcopy(full_plan.frozen_inputs or {}),
            "planning_baseline": copy.deepcopy(frozen["planning"]["baseline"]),
            "validation_profile": copy.deepcopy(
                frozen["validation_context"]["validation_profile"]
            ),
            "content_sampling_profile": _identity_for_spec(
                root, CONTENT_SAMPLING_PROFILE_SPEC.relative_path
            ),
            "finding_code_policy": _identity_for_spec(
                root, FINDING_CODE_POLICY_SPEC.relative_path
            ),
        },
        "notes": [
            "en-us/icp-faq intentionally reuses the Chinese source snapshot.",
            "The reuse is a language-routing workaround, not English translation validation.",
        ],
    }


def _identity_for_spec(root: Path, relative_path: str) -> dict[str, Any]:
    path = root / relative_path
    document = read_json(path)
    identifier = (
        document.get("profile_id")
        or document.get("policy_id")
        or document.get("baseline_id")
        or document.get("map_id")
    )
    return {
        "id": identifier,
        "schema_version": document["schema_version"],
        "path": relative_path,
        "sha256": sha256_file(path),
    }


def load_fixture_manifest(root: Path, fixture_path: Path | None = None) -> dict[str, Any]:
    path = root / (fixture_path or FIXTURE_MANIFEST_PATH)
    if not path.is_file():
        raise CoreRegressionError(f"Core fixture manifest is missing: {path}")
    value = read_json(path)
    _validate_schema(root, "schemas/step6-core-fixture-manifest-1.0.schema.json", value)
    return value


def verify_fixture_manifest(root: Path, fixture_path: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    expected = load_fixture_manifest(root, fixture_path)
    actual = build_fixture_manifest(root)
    if expected != actual:
        raise CoreRegressionError("Core fixture manifest drifted from repository inputs")
    return expected


class CorePlanner:
    """PipelinePlanner-compatible Step 6 closed-world planner."""

    def __init__(
        self,
        root: str | Path = ".",
        fixture_path: str | Path = FIXTURE_MANIFEST_PATH,
    ) -> None:
        self.root = Path(root).resolve()
        self.fixture_path = Path(fixture_path)
        self._planner = PipelinePlanner(self.root)

    def plan(
        self,
        scope: str = "group",
        *,
        group: str | None = CORE_GROUP,
        language: str = "both",
    ) -> PipelinePlan:
        if scope != "group" or group != CORE_GROUP:
            raise CoreRegressionError(
                f"CorePlanner only supports group={CORE_GROUP!r}"
            )
        if language != "both":
            raise CoreRegressionError("CorePlanner requires language='both'")
        fixture = verify_fixture_manifest(self.root, self.fixture_path)
        full_plan = self._planner.plan(language="both")
        by_id = {item.item_id: item for item in full_plan.items}
        items = tuple(by_id[item_id] for item_id in fixture["expected_item_ids"])
        if len(items) != len(CORE_ITEM_IDS) or not items:
            raise CoreRegressionError("CorePlanner selected an invalid item count")
        return PipelinePlan(
            scope={"kind": "group", "group": CORE_GROUP},
            languages=("zh-cn", "en-us"),
            items=items,
            frozen_inputs=full_plan.frozen_inputs,
        )


def run_core_batch(
    root: Path,
    *,
    runs_dir: Path,
    parallel_jobs: int,
) -> PipelineOutcome:
    coordinator = PipelineCoordinator(
        root,
        runs_dir,
        planner=CorePlanner(root),
    )
    return coordinator.run(
        group=CORE_GROUP,
        language="both",
        parallel_jobs=parallel_jobs,
    )


def _load_run(root: Path, runs_dir: Path, batch_id: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    store = StateStore(root, runs_dir=runs_dir)
    run_dir = store.run_dir(batch_id)
    manifest = store.read_manifest(batch_id)
    input_manifest = store.read_input_manifest(batch_id)
    return run_dir, manifest, input_manifest


def _artifact(root: Path, run_dir: Path, reference: Mapping[str, Any]) -> dict[str, Any]:
    path = run_dir / str(reference["path"])
    if path.is_symlink() or not path.is_file():
        raise CoreRegressionError(f"Run artifact is missing: {path}")
    digest = sha256_file(path)
    expected = reference.get("sha256")
    if expected and digest != expected:
        raise CoreRegressionError(f"Run artifact hash drifted: {path}")
    return {"path": _relative(root, path), "sha256": digest, "document": read_json(path)}


def _baseline_relative(item_id: str, kind: str) -> Path:
    language, resource_key = item_id.split("/", 1)
    return Path(language) / f"{resource_key}.{kind}.json"


def _trim_support_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: payload.get(key)
        for key in ("title", "slug", "pageType", "articleDescription", "mainContent")
    }


def _sampling_summary(
    item_id: str,
    item: Mapping[str, Any],
    validation: Mapping[str, Any],
    sampled_evidence: Mapping[str, Any] | None,
    sampling_plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    language, resource_key = item_id.split("/", 1)
    strategy = item["strategy"]
    validation_evidence = validation["evidence"]
    bindings = validation_evidence["bindings"]
    validation_summary = {
        "schema_version": validation["schema_version"],
        "validation_profile": bindings["validation_profile"],
        "finding_code_policy": bindings.get("finding_code_policy_identity"),
        "verdict": validation_evidence["verdict"],
        "status": validation["status"],
        "evidence_sha256": validation["evidence_sha256"],
        "approval_preconditions": validation_evidence["approval_preconditions"],
    }
    if resource_key in SAMPLING_BASELINES:
        if sampled_evidence is None:
            raise CoreRegressionError(f"Sampling evidence missing for {item_id}")
        if sampling_plan is None:
            raise CoreRegressionError(f"Sampling plan document missing for {item_id}")
        plan_ref = item["artifacts"].get("sampling_plan")
        if not plan_ref:
            raise CoreRegressionError(f"Sampling plan missing for {item_id}")
        evidence = copy.deepcopy(sampled_evidence)
        return {
            "schema_version": "1.0",
            "item_id": item_id,
            "language": language,
            "resource_key": resource_key,
            "strategy": strategy,
            "sampling_semantics": "curated_stratified_sample",
            "sampling_plan": {
                "path": plan_ref["path"],
                "sha256": plan_ref["sha256"],
                "plan_sha256": evidence["bindings"]["sampling_plan"]["plan_sha256"],
                "document": copy.deepcopy(sampling_plan),
                "coverage": evidence["coverage"],
            },
            "state_universe": {
                "universe_id": sampling_plan["state_universe"]["universe_id"],
                "default_state_id": sampling_plan["state_universe"]["default_state_id"],
                "states": sampling_plan["state_universe"]["states"],
                "universe_count": evidence["coverage"]["universe_count"],
                "selected_count": evidence["coverage"]["selected_count"],
                "untested_count": evidence["coverage"]["untested_count"],
                "selected_state_ids": evidence["coverage"]["selected_state_ids"],
            },
            "page_global_comparison": evidence["page_global_comparison"],
            "samples": evidence["samples"],
            "validation": validation_summary,
        }
    if resource_key in FULL_CONTENT_NOT_APPLICABLE:
        return {
            "schema_version": "1.0",
            "item_id": item_id,
            "language": language,
            "resource_key": resource_key,
            "strategy": strategy,
            "sampling_semantics": "not_applicable",
            "sampling_plan": None,
            "content_mode": "full_content",
            "sampled_evidence_mode": sampled_evidence["mode"] if sampled_evidence else None,
            "full_content_comparison": (
                sampled_evidence.get("full_content_comparison")
                if sampled_evidence
                else None
            ),
            "validation": validation_summary,
        }
    if resource_key in SUPPORT_BASELINES:
        return {
            "schema_version": "1.0",
            "item_id": item_id,
            "language": language,
            "resource_key": resource_key,
            "strategy": strategy,
            "sampling_semantics": "full_support_article",
            "sampling_plan": None,
            "content_mode": "support_article_main_content",
            "sampled_evidence_mode": sampled_evidence["mode"] if sampled_evidence else None,
            "full_content_comparison": (
                sampled_evidence.get("full_content_comparison")
                if sampled_evidence
                else None
            ),
            "validation": validation_summary,
        }
    raise CoreRegressionError(f"Unsupported Core baseline item: {item_id}")


def build_baseline_documents(
    root: Path,
    *,
    runs_dir: Path,
    batch_id: str,
    reason: str,
) -> dict[str, dict[str, Any]]:
    root = root.resolve()
    run_dir, manifest, input_manifest = _load_run(root, runs_dir, batch_id)
    fixture = verify_fixture_manifest(root)
    if input_manifest["scope"] != {"kind": "group", "group": CORE_GROUP}:
        raise CoreRegressionError(f"Batch is not a Core batch: {batch_id}")
    if list(input_manifest["languages"]) != ["zh-cn", "en-us"]:
        raise CoreRegressionError(f"Batch is not bilingual: {batch_id}")
    if list(item["item_id"] for item in input_manifest["items"]) != list(CORE_ITEM_IDS):
        raise CoreRegressionError(f"Batch item set is not the Core closed world: {batch_id}")
    frozen_items = {
        item["item_id"]: item for item in input_manifest["items"]
    }

    files: dict[str, dict[str, Any]] = {}
    manifest_entries = []
    for item_id in CORE_ITEM_IDS:
        item = manifest["items"][item_id]
        frozen_item = frozen_items[item_id]
        if item["status"]["execution"] != "succeeded":
            raise CoreRegressionError(f"Core item execution did not succeed: {item_id}")
        if item["status"]["validation"] != "passed":
            raise CoreRegressionError(f"Core item validation did not pass: {item_id}")
        payload_artifact = _artifact(root, run_dir, item["artifacts"]["payload"])
        validation_artifact = _artifact(root, run_dir, item["artifacts"]["validation"])
        sampled_ref = item["artifacts"].get("sampled_content_evidence")
        sampled = _artifact(root, run_dir, sampled_ref)["document"] if sampled_ref else None
        plan_ref = item["artifacts"].get("sampling_plan")
        sampling_plan = (
            _artifact(root, run_dir, plan_ref)["document"] if plan_ref else None
        )
        payload = payload_artifact["document"]
        validation = validation_artifact["document"]

        language, resource_key = item_id.split("/", 1)
        payload_path = _baseline_relative(item_id, "payload")
        content_path = _baseline_relative(item_id, "content")
        if resource_key in PRICING_FULL_GOLDENS:
            files[payload_path.as_posix()] = payload
        elif resource_key in SUPPORT_BASELINES:
            files[payload_path.as_posix()] = _trim_support_payload(payload)
        files[content_path.as_posix()] = _sampling_summary(
            item_id, item, validation, sampled, sampling_plan
        )
        manifest_entries.append(
            {
                "item_id": item_id,
                "language": language,
                "resource_key": resource_key,
                "strategy": item["strategy"],
                "payload_baseline": payload_path.as_posix(),
                "content_baseline": content_path.as_posix(),
                "source_sha256": frozen_item["source"]["sha256"],
                "payload_sha256": payload_artifact["sha256"],
                "validation_sha256": validation_artifact["sha256"],
            }
        )

    baseline_manifest = {
        "schema_version": "1.0",
        "baseline_id": "v0.4-step6-core-baseline",
        "matrix_id": CORE_GROUP,
        "source_batch_id": batch_id,
        "reason": reason,
        "generated_at": input_manifest["created_at"],
        "fixture_manifest_sha256": sha256_file(root / FIXTURE_MANIFEST_PATH),
        "planning": copy.deepcopy(input_manifest["planning"]),
        "validation_context": copy.deepcopy(input_manifest["validation_context"]),
        "frozen_inputs": copy.deepcopy(fixture["frozen_inputs"]),
        "items": manifest_entries,
    }
    files["baseline-manifest.json"] = baseline_manifest
    return files


def _unified_diff(old: str, new: str, *, fromfile: str, tofile: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=fromfile,
            tofile=tofile,
        )
    )


def create_baseline_candidate(
    root: Path,
    *,
    runs_dir: Path,
    batch_id: str,
    reason: str,
    candidate_root: Path = CANDIDATE_ROOT,
) -> dict[str, Any]:
    documents = build_baseline_documents(
        root, runs_dir=runs_dir, batch_id=batch_id, reason=reason
    )
    file_entries = []
    diff_parts = []
    proposed_root = candidate_root / f"{batch_id}-{json_sha256(documents['baseline-manifest.json'])[:12]}"
    if proposed_root.exists():
        shutil.rmtree(proposed_root)
    for relative_path, document in sorted(documents.items()):
        rendered = render_json(document)
        target = root / BASELINE_ROOT / relative_path
        old = target.read_text(encoding="utf-8") if target.exists() else ""
        old_sha = hashlib.sha256(old.encode("utf-8")).hexdigest() if old else None
        new_sha = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
        proposed = proposed_root / "proposed" / relative_path
        proposed.parent.mkdir(parents=True, exist_ok=True)
        proposed.write_text(rendered, encoding="utf-8")
        diff = _unified_diff(
            old,
            rendered,
            fromfile=f"baseline/{relative_path}",
            tofile=f"candidate/{relative_path}",
        )
        if diff:
            diff_parts.append(diff)
        file_entries.append(
            {
                "path": relative_path,
                "old_sha256": old_sha,
                "new_sha256": new_sha,
                "status": "modified" if old_sha else "added",
            }
        )

    candidate = {
        "schema_version": "1.0",
        "candidate_id": proposed_root.name,
        "baseline_id": "v0.4-step6-core-baseline",
        "source_batch_id": batch_id,
        "reason": reason,
        "generated_at": documents["baseline-manifest.json"]["generated_at"],
        "baseline_root": BASELINE_ROOT.as_posix(),
        "files": file_entries,
        "candidate_sha256": "",
    }
    candidate["candidate_sha256"] = json_sha256(
        {key: value for key, value in candidate.items() if key != "candidate_sha256"}
    )
    _validate_schema(
        root,
        "schemas/step6-core-baseline-candidate-1.0.schema.json",
        candidate,
    )
    write_json(proposed_root / "candidate-manifest.json", candidate)
    (proposed_root / "baseline.diff").write_text("".join(diff_parts), encoding="utf-8")
    return candidate


def promote_baseline_candidate(
    root: Path,
    *,
    candidate_dir: Path,
    expected_sha256: str,
) -> dict[str, Any]:
    manifest_path = candidate_dir / "candidate-manifest.json"
    candidate = read_json(manifest_path)
    _validate_schema(root, "schemas/step6-core-baseline-candidate-1.0.schema.json", candidate)
    if candidate["candidate_sha256"] != expected_sha256:
        raise CoreRegressionError("Candidate SHA does not match expected SHA")
    proposed_root = candidate_dir / "proposed"
    for entry in candidate["files"]:
        relative_path = entry["path"]
        proposed = proposed_root / relative_path
        target = root / BASELINE_ROOT / relative_path
        if proposed.is_symlink() or not proposed.is_file():
            raise CoreRegressionError(f"Missing proposed baseline file: {relative_path}")
        new_sha = hashlib.sha256(proposed.read_bytes()).hexdigest()
        if new_sha != entry["new_sha256"]:
            raise CoreRegressionError(f"Proposed file hash drifted: {relative_path}")
        if target.exists():
            old_sha = hashlib.sha256(target.read_bytes()).hexdigest()
            if old_sha != entry["old_sha256"]:
                raise CoreRegressionError(f"Current baseline hash drifted: {relative_path}")
        elif entry["old_sha256"] is not None:
            raise CoreRegressionError(f"Expected existing baseline is missing: {relative_path}")

    for entry in candidate["files"]:
        relative_path = entry["path"]
        proposed = proposed_root / relative_path
        target = root / BASELINE_ROOT / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(proposed.read_bytes())
    return candidate


def verify_baseline(root: Path) -> dict[str, Any]:
    fixture = verify_fixture_manifest(root)
    manifest_path = root / BASELINE_MANIFEST_PATH
    if not manifest_path.is_file():
        raise CoreRegressionError(f"Core baseline manifest is missing: {manifest_path}")
    manifest = read_json(manifest_path)
    _validate_schema(root, "schemas/step6-core-baseline-manifest-1.0.schema.json", manifest)
    expected_ids = list(CORE_ITEM_IDS)
    if [item["item_id"] for item in manifest["items"]] != expected_ids:
        raise CoreRegressionError("Core baseline manifest item order drifted")
    if manifest["fixture_manifest_sha256"] != sha256_file(root / FIXTURE_MANIFEST_PATH):
        raise CoreRegressionError("Core baseline is bound to a different fixture manifest")
    fixture_by_id = {item["item_id"]: item for item in fixture["items"]}
    for item in manifest["items"]:
        fixture_item = fixture_by_id[item["item_id"]]
        if item["source_sha256"] != fixture_item["source"]["sha256"]:
            raise CoreRegressionError(f"Baseline source hash drifted: {item['item_id']}")
        payload_path = root / BASELINE_ROOT / item["payload_baseline"]
        if payload_path.is_symlink() or not payload_path.is_file():
            raise CoreRegressionError(f"Baseline file is missing: {payload_path}")
        read_json(payload_path)

        for key in ("content_baseline",):
            path = root / BASELINE_ROOT / item[key]
            if path.is_symlink() or not path.is_file():
                raise CoreRegressionError(f"Baseline file is missing: {path}")
            read_json(path)
    return manifest


def make_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Step 6 Core regression tooling")
    parser.add_argument("--root", default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("verify-fixture")
    subparsers.add_parser("fixture-candidate")

    run = subparsers.add_parser("run")
    run.add_argument("--parallel-jobs", type=int, default=4)
    run.add_argument("--runs-dir", default="runs")

    candidate = subparsers.add_parser("baseline-candidate")
    candidate.add_argument("--batch-id", required=True)
    candidate.add_argument("--reason", required=True)
    candidate.add_argument("--runs-dir", default="runs")

    promote = subparsers.add_parser("baseline-promote")
    promote.add_argument("--candidate", required=True)
    promote.add_argument("--expected-sha256", required=True)

    subparsers.add_parser("verify-baseline")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = make_arg_parser().parse_args(list(argv) if argv is not None else None)
    root = Path(args.root).resolve()
    if args.command == "verify-fixture":
        manifest = verify_fixture_manifest(root)
        print(f"fixture ok: {manifest['manifest_id']} items={len(manifest['items'])}")
        return 0
    if args.command == "fixture-candidate":
        manifest = build_fixture_manifest(root)
        output = root / CANDIDATE_ROOT / "fixture-manifest.candidate.json"
        write_json(output, manifest)
        print(f"fixture candidate: {output}")
        print(f"sha256={json_sha256(manifest)}")
        return 0
    if args.command == "run":
        outcome = run_core_batch(
            root,
            runs_dir=Path(args.runs_dir),
            parallel_jobs=args.parallel_jobs,
        )
        print(
            f"batch_id={outcome.batch_id} status={outcome.status} "
            f"total={outcome.summary['total']} runnable={outcome.summary['runnable']} "
            f"execution_failed={outcome.summary['execution_failed']} "
            f"validation_failed={outcome.summary['validation_failed']}"
        )
        print(f"run_dir: {outcome.run_dir}")
        return outcome.exit_code
    if args.command == "baseline-candidate":
        candidate = create_baseline_candidate(
            root,
            runs_dir=Path(args.runs_dir),
            batch_id=args.batch_id,
            reason=args.reason,
        )
        print(f"candidate: {root / CANDIDATE_ROOT / candidate['candidate_id']}")
        print(f"candidate_sha256={candidate['candidate_sha256']}")
        print(f"files={len(candidate['files'])}")
        return 0
    if args.command == "baseline-promote":
        candidate = promote_baseline_candidate(
            root,
            candidate_dir=Path(args.candidate).resolve(),
            expected_sha256=args.expected_sha256,
        )
        print(f"promoted: {candidate['candidate_id']}")
        return 0
    if args.command == "verify-baseline":
        manifest = verify_baseline(root)
        print(f"baseline ok: {manifest['baseline_id']} items={len(manifest['items'])}")
        return 0
    raise AssertionError(args.command)
