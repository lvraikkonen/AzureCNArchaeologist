"""Dashboard Review Workbench read models for Step 4 Slice D."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.content_sampling.projector import (
    PayloadContentProjector,
    ProjectionError,
    SourceContentProjector,
)
from src.content_sampling.semantic import diff_document, semantic_fingerprint
from src.core.canonical_identity import canonical_sha256
from src.core.canonical_input import CanonicalInputLoader, InputAssuranceError
from src.core.product_catalog import sha256_file
from src.core.source_reachability import (
    SourceReachability,
    SourceReachabilityError,
    SourceReachabilityResolver,
)
from src.core.strict_soft_category_projection import (
    StrictSoftCategoryProjectionError,
)
from src.pipeline.models import BatchItem, items_from_dicts, utc_now
from src.pipeline.state_store import StateStore
from src.release.contracts import ReleaseContractError, evaluate_release_item
from src.review.accounting import finding_summary, merge_item_accounting, summarize_review_items
from src.review.independent_fidelity import build_independent_fidelity_view
from src.review.service import ReviewService, ReviewServiceError


class ReviewWorkbenchError(RuntimeError):
    """A local Dashboard Workbench operation failed with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class WorkbenchBatchSelection:
    batch_ids: tuple[str, ...]
    history_index: Mapping[str, Any] | None = None


def _error(code: str, message: str) -> ReviewWorkbenchError:
    return ReviewWorkbenchError(code, message)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _error("json_read_failed", f"Unable to read JSON document: {path}") from error
    if not isinstance(value, dict):
        raise _error("invalid_json_document", f"JSON document must be an object: {path}")
    return value


def _artifact(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    return copy.deepcopy(dict(value)) if value is not None else None


def _issue_summary(value: Mapping[str, Any]) -> dict[str, str]:
    return {
        "code": str(value.get("code", "issue")),
        "message": str(value.get("message", value.get("code", "Issue"))),
        "path": str(value.get("path", "$")),
    }


def _comparison(scope: str, source_value: Any, payload_value: Any) -> dict[str, Any]:
    source_fingerprint = semantic_fingerprint(source_value)
    payload_fingerprint = semantic_fingerprint(payload_value)
    if source_fingerprint == payload_fingerprint:
        status = "matched"
        diff = None
    else:
        status = "mismatched"
        diff = diff_document(
            scope=scope,
            source_value=source_value,
            payload_value=payload_value,
            source_fingerprint=source_fingerprint,
            payload_fingerprint=payload_fingerprint,
        )
    return {
        "status": status,
        "source_fingerprint": source_fingerprint,
        "payload_fingerprint": payload_fingerprint,
        "source": source_value,
        "payload": payload_value,
        "diff": diff,
    }


def _decision_path(language: str, resource_key: str, decision_id: str) -> str:
    return Path(
        "review",
        "decisions",
        language,
        resource_key,
        f"{decision_id}.json",
    ).as_posix()


def _validation_profile_id(manifest: Mapping[str, Any]) -> str:
    validation_context = manifest.get("validation_context")
    if isinstance(validation_context, Mapping):
        validation_profile = validation_context.get("validation_profile")
        if (
            isinstance(validation_profile, Mapping)
            and isinstance(validation_profile.get("id"), str)
        ):
            return validation_profile["id"]
    if isinstance(manifest.get("validation_profile_id"), str):
        return str(manifest["validation_profile_id"])
    return "legacy-profile-unrecorded"


class ReviewWorkbenchService:
    """Local-only read model for the Dashboard Review Workbench."""

    def __init__(
        self,
        root: str | Path = ".",
        runs_dir: str | Path = "runs",
        *,
        review_service: ReviewService | None = None,
        now: Any = utc_now,
    ) -> None:
        self.root = Path(root).resolve()
        self.review = review_service or ReviewService(self.root, runs_dir)
        self.store = self.review.store
        self._now = now
        self.input_loader = CanonicalInputLoader(self.root)
        self.source_reachability = SourceReachabilityResolver(self.root)
        self.source_projector = SourceContentProjector(self.root)
        self.payload_projector = PayloadContentProjector()

    def selection(
        self,
        batch_ids: Sequence[str],
        *,
        history_index_path: str | Path | None = None,
    ) -> WorkbenchBatchSelection:
        if not batch_ids:
            raise _error("missing_batch_selection", "At least one Batch ID is required")
        ordered: list[str] = []
        seen: set[str] = set()
        for batch_id in batch_ids:
            run_dir = self.store.run_dir(batch_id)
            if not run_dir.is_dir():
                raise _error("unknown_batch", f"Unknown Batch: {batch_id}")
            if batch_id not in seen:
                ordered.append(batch_id)
                seen.add(batch_id)
        history = (
            self._read_history_index(Path(history_index_path))
            if history_index_path is not None
            else None
        )
        if history is not None:
            history_batch_ids = [entry["batch_id"] for entry in history["batches"]]
            unknown = [value for value in history_batch_ids if value not in seen]
            if unknown:
                raise _error(
                    "history_batch_not_allowed",
                    "History index references a Batch not in the explicit allowlist: "
                    + ", ".join(unknown),
                )
        return WorkbenchBatchSelection(tuple(ordered), history)

    def list_batches(self, selection: WorkbenchBatchSelection) -> dict[str, Any]:
        batches: list[dict[str, Any]] = []
        history_labels = {
            entry["batch_id"]: entry.get("label")
            for entry in (selection.history_index or {}).get("batches", [])
        }
        for batch_id in selection.batch_ids:
            manifest = self.store.read_manifest(batch_id)
            batches.append({
                "batch_id": batch_id,
                "manifest_revision": manifest["revision"],
                "status": manifest["status"],
                "label": history_labels.get(batch_id),
                "run_dir": self.store.run_dir(batch_id).as_posix(),
            })
        return {
            "schema_version": "1.0",
            "generated_at": self._now(),
            "batches": batches,
            "history_configured": selection.history_index is not None,
        }

    def build_projection(
        self,
        batch_id: str,
        *,
        history_index: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        manifest = self.store.read_manifest(batch_id)
        queue = self.review.list_items(batch_id, status="all")
        frozen = self.store.read_input_manifest(batch_id)
        items = items_from_dicts(frozen["items"])
        runnable_item_ids = {item.item_id for item in items if item.runnable}
        product_items: dict[str, set[str]] = {}
        for item in items:
            if item.runnable:
                product_items.setdefault(item.product_key, set()).add(item.item_id)

        enriched_items: list[dict[str, Any]] = []
        release_ready_by_item: dict[str, bool] = {}
        for raw_item in queue["items"]:
            item = copy.deepcopy(dict(raw_item))
            release_eligibility = self._release_eligibility(manifest, item)
            item["release_eligibility"] = release_eligibility
            item = merge_item_accounting(
                item,
                release_ready=bool(release_eligibility["eligible"]),
            )
            release_ready_by_item[item["item_id"]] = item["release_ready"]
            enriched_items.append(item)

        product_ready = sum(
            bool(item_ids) and all(release_ready_by_item.get(item_id, False) for item_id in item_ids)
            for item_ids in product_items.values()
        )
        product_pending_attention = {
            item["product_key"]
            for item in enriched_items
            if item["status"]["review"] == "pending"
        }
        product_rejected_attention = {
            item["product_key"]
            for item in enriched_items
            if item["status"]["review"] == "rejected"
        }
        product_source_warning = {
            item["product_key"]
            for item in enriched_items
            if item.get("source_warning")
        }
        product_approval_blocked = {
            item["product_key"]
            for item in enriched_items
            if item.get("approval_blocked")
        }
        product_machine_failed = {
            current["product_key"]
            for current in manifest["items"].values()
            if current["status"]["validation"] == "failed"
        }
        machine_failed_items = sum(
            current["status"]["validation"] == "failed"
            for current in manifest["items"].values()
        )
        item_summary = summarize_review_items(enriched_items)
        item_summary["runnable"] = len(runnable_item_ids)
        item_summary["machine_failed_count"] = machine_failed_items
        release_manifests = list(manifest.get("release_manifests", []))
        publication_receipts = list(manifest.get("publication_receipts", []))
        projection = {
            "schema_version": "1.0",
            "projection_id": "0" * 64,
            "generated_at": self._now(),
            "batch": {
                "batch_id": batch_id,
                "manifest_revision": manifest["revision"],
                "status": manifest["status"],
                "validation_profile_id": _validation_profile_id(manifest),
                "run_dir": self.store.run_dir(batch_id).as_posix(),
            },
            "summary": {
                "items": item_summary,
                "products": {
                    "total": len(product_items),
                    "release_ready_count": product_ready,
                    "pending_attention": len(product_pending_attention),
                    "rejected_attention": len(product_rejected_attention),
                    "source_warning_count": len(product_source_warning),
                    "approval_blocked_count": len(product_approval_blocked),
                    "machine_failed_count": len(product_machine_failed),
                },
            },
            "history": self._history_summary(history_index),
            "release": {
                "release_manifests": copy.deepcopy(release_manifests),
                "publication_receipts": copy.deepcopy(publication_receipts),
            },
            "items": enriched_items,
        }
        projection["projection_id"] = canonical_sha256({
            "schema_version": projection["schema_version"],
            "batch_id": batch_id,
            "manifest_revision": manifest["revision"],
            "items": [
                {
                    "item_id": item["item_id"],
                    "review": item["status"]["review"],
                    "evidence_binding": item["status"]["evidence_binding"],
                    "approval_eligibility": item["status"]["approval_eligibility"],
                    "release_ready": item["release_ready"],
                }
                for item in enriched_items
            ],
        })
        return projection

    def get_item_evidence(
        self,
        batch_id: str,
        *,
        language: str,
        resource_key: str,
    ) -> dict[str, Any]:
        item_id = f"{language}/{resource_key}"
        frozen = self.store.read_input_manifest(batch_id)
        manifest = self.store.read_manifest(batch_id)
        item_by_id = {item.item_id: item for item in items_from_dicts(frozen["items"])}
        item = item_by_id.get(item_id)
        if item is None:
            raise _error("unknown_item", f"Unknown Batch Item: {item_id}")
        snapshot = self.review.get_item_evidence(batch_id, item_id)
        manifest_item = manifest["items"][item_id]
        preview = self._manual_preview(batch_id, item, snapshot)
        return {
            "schema_version": "1.0",
            "generated_at": self._now(),
            "batch_id": batch_id,
            "item_id": item_id,
            "manifest_revision": manifest["revision"],
            "item": {
                "language": item.language,
                "resource_key": item.resource_key,
                "product_key": item.product_key,
                "page_model": item.page_model,
                "strategy": item.strategy,
                "slug": item.slug,
                "source_url": item.source_url,
            },
            "status": copy.deepcopy(dict(manifest_item["status"])),
            "artifacts": {
                key: _artifact(manifest_item["artifacts"].get(key))
                for key in (
                    "payload",
                    "validation",
                    "sampling_plan",
                    "sampled_content_evidence",
                    "current_review_decision",
                )
            },
            "bindings": copy.deepcopy(dict(snapshot["bindings"])),
            "coverage": copy.deepcopy(dict(snapshot["validation"]["evidence"]["content_validation"]["coverage"])),
            "validation_summary": {
                "status": snapshot["validation"]["status"],
                "evidence_sha256": snapshot["validation"]["evidence_sha256"],
                "errors": copy.deepcopy(snapshot["validation"]["evidence"]["errors"]),
                "warnings": copy.deepcopy(snapshot["validation"]["evidence"]["warnings"]),
                "approval_preconditions": copy.deepcopy(
                    snapshot["validation"]["evidence"]["approval_preconditions"]
                ),
            },
            "source_quality_findings": [
                finding_summary(finding)
                for finding in snapshot["source_quality_findings"]
            ],
            "machine_evidence": {
                "page_global_comparison": copy.deepcopy(
                    snapshot["sampled_content_evidence"]["page_global_comparison"]
                ),
                "full_content_comparison": copy.deepcopy(
                    snapshot["sampled_content_evidence"]["full_content_comparison"]
                ),
                "samples": copy.deepcopy(snapshot["sampled_content_evidence"]["samples"]),
            },
            "inspection": {
                "mode": snapshot["inspection_mode"],
                "allowed_state_ids": copy.deepcopy(snapshot["allowed_state_ids"]),
                "state_universe": (
                    copy.deepcopy(snapshot["sampling_plan"]["state_universe"]["states"])
                    if snapshot["sampling_plan"] is not None
                    else []
                ),
            },
            "manual_preview": preview,
            "decisions": {
                "current": self._current_decision_summary(batch_id, item, manifest_item),
                "history": self._decision_history(batch_id, item, manifest_item),
            },
        }

    def get_independent_fidelity(
        self,
        batch_id: str,
        *,
        language: str,
        resource_key: str,
    ) -> dict[str, Any]:
        """Return the GET-only L3b panel model for one existing Batch item."""

        item_id = f"{language}/{resource_key}"
        manifest = self.store.read_manifest(batch_id)
        manifest_item = manifest["items"].get(item_id)
        if not isinstance(manifest_item, Mapping):
            raise _error("unknown_item", f"Unknown Batch Item: {item_id}")
        payload = manifest_item.get("artifacts", {}).get("payload")
        if not isinstance(payload, Mapping):
            return {
                "schema_version": "1.0",
                "batch_id": batch_id,
                "item_id": item_id,
                "status": "invalid",
                "evidence_identity": None,
                "l3b": {
                    "claim": "independent_source_content_fidelity",
                    "verdict": "invalid",
                    "coverage": None,
                    "reason": "Batch item has no persisted payload binding.",
                    "claim_limitations": [],
                },
                "scopes": [],
            }
        return build_independent_fidelity_view(
            self.root,
            run_dir=self.store.run_dir(batch_id),
            batch_id=batch_id,
            item_id=item_id,
            payload_artifact=payload,
        )

    def _manual_preview(
        self,
        batch_id: str,
        item: BatchItem,
        snapshot: Mapping[str, Any],
    ) -> dict[str, Any]:
        try:
            payload_ref = self.store.read_manifest(batch_id)["items"][item.item_id]["artifacts"]["payload"]
            payload_path = self.store.run_dir(batch_id) / payload_ref["path"]
            if not payload_path.is_file() or sha256_file(payload_path) != payload_ref["sha256"]:
                raise _error(
                    "payload_artifact_untrusted",
                    f"Payload artifact is missing or hash-drifted for {item.item_id}",
                )
            payload = _read_json(payload_path)
            canonical_input = self.input_loader.load(
                item.product_key,
                item.language,
                version_key=item.version_key,
                expected_sha256=item.normalized_sha256,
            )
            reachability = self._reachability_for(item, canonical_input)
            source_payload = self.source_projector.project_payload(
                product_key=item.product_key,
                language=item.language,
                version_key=item.version_key,
                canonical_input=canonical_input,
                strategy=item.strategy,
                source_reachability=reachability,
            )
            page_global = _comparison(
                "page_global",
                self.payload_projector.page_global(source_payload, item.strategy),
                self.payload_projector.page_global(payload, item.strategy),
            )
            full_content = None
            states: list[dict[str, Any]] = []
            if snapshot["inspection_mode"] == "full":
                full_content = _comparison(
                    "full_content",
                    self.payload_projector.full_content(source_payload, item.strategy),
                    self.payload_projector.full_content(payload, item.strategy),
                )
            else:
                selected = set(snapshot["sampled_content_evidence"]["coverage"]["selected_state_ids"])
                for state in snapshot["sampling_plan"]["state_universe"]["states"]:
                    state_comparison = _comparison(
                        f"interactive_state:{state['state_id']}",
                        self.payload_projector.state_content(source_payload, state),
                        self.payload_projector.state_content(payload, state),
                    )
                    states.append({
                        "state_id": state["state_id"],
                        "criteria": copy.deepcopy(state["criteria"]),
                        "machine_selected": state["state_id"] in selected,
                        "comparison": state_comparison,
                    })
            return {
                "status": "available",
                "error": None,
                "page_global": page_global,
                "full_content": full_content,
                "states": states,
            }
        except (
            InputAssuranceError,
            ProjectionError,
            SourceReachabilityError,
            StrictSoftCategoryProjectionError,
            ReviewWorkbenchError,
            OSError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            return {
                "status": "unavailable",
                "error": {
                    "code": getattr(error, "code", "manual_preview_unavailable"),
                    "message": str(error),
                },
                "page_global": None,
                "full_content": None,
                "states": [],
            }

    def _reachability_for(
        self,
        item: BatchItem,
        canonical_input: Any,
    ) -> SourceReachability | None:
        if item.page_model != "FlexibleContentPage":
            return None
        reachability = self.source_reachability.resolve(canonical_input)
        if item.strategy == "complex":
            reachability = self.source_reachability.attach_strict_soft_category_projections(
                canonical_input,
                reachability,
            )
        return reachability

    def _release_eligibility(
        self,
        manifest: Mapping[str, Any],
        queue_item: Mapping[str, Any],
    ) -> dict[str, Any]:
        status = queue_item["status"]
        decision = queue_item.get("current_decision")
        decision_sha = (
            decision.get("sha256")
            if isinstance(decision, Mapping) and decision.get("sha256")
            else "0" * 64
        )
        current_hashes = {
            "payload_sha256": queue_item["bindings"]["payload_sha256"],
            "validation_artifact_sha256": queue_item["bindings"]["validation_artifact_sha256"],
            "validation_evidence_sha256": queue_item["bindings"]["validation_evidence_sha256"],
            "review_decision_sha256": decision_sha,
            "validation_profile_sha256": manifest["validation_context"]["validation_profile"]["sha256"],
            "sampling_plan_sha256": queue_item["bindings"]["sampling_plan_sha256"],
        }
        try:
            return evaluate_release_item(
                execution_status=status["execution"],
                validation_status=status["validation"],
                evidence_binding=status["evidence_binding"],
                approval_eligibility=status["approval_eligibility"],
                review_status=status["review"],
                current_hashes=current_hashes,
                release_hashes=current_hashes,
            ).to_dict()
        except ReleaseContractError as error:
            return {
                "eligible": False,
                "blockers": [{"code": error.code, "message": str(error)}],
            }

    def _current_decision_summary(
        self,
        batch_id: str,
        item: BatchItem,
        manifest_item: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        reference = manifest_item["artifacts"].get("current_review_decision")
        if reference is None:
            return None
        decision = self._read_decision_by_reference(batch_id, item, reference)
        return {
            "decision_id": decision["decision_id"],
            "path": reference["path"],
            "sha256": reference["sha256"],
            "reviewer": decision["reviewer"],
            "decided_at": decision["decided_at"],
            "verdict": decision["verdict"],
            "reason": decision["reason"],
            "supersedes_decision_id": decision["supersedes_decision_id"],
        }

    def _decision_history(
        self,
        batch_id: str,
        item: BatchItem,
        manifest_item: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        reference = manifest_item["artifacts"].get("current_review_decision")
        if reference is None:
            return []
        history: list[dict[str, Any]] = []
        seen: set[str] = set()
        decision = self._read_decision_by_reference(batch_id, item, reference)
        decision_sha = str(reference["sha256"])
        decision_path = str(reference["path"])
        while True:
            decision_id = str(decision["decision_id"])
            if decision_id in seen:
                raise _error(
                    "decision_history_cycle",
                    f"Review Decision supersession cycle at {decision_id}",
                )
            seen.add(decision_id)
            history.append({
                "decision_id": decision_id,
                "path": decision_path,
                "sha256": decision_sha,
                "reviewer": decision["reviewer"],
                "decided_at": decision["decided_at"],
                "verdict": decision["verdict"],
                "reason": decision["reason"],
                "notes": decision["notes"],
                "inspected_states": copy.deepcopy(decision["inspected_states"]),
                "supersedes_decision_id": decision["supersedes_decision_id"],
            })
            supersedes = decision["supersedes_decision_id"]
            if supersedes is None:
                return history
            decision_path = _decision_path(item.language, item.resource_key, str(supersedes))
            decision_file = self.store.run_dir(batch_id) / decision_path
            if not decision_file.is_file():
                raise _error(
                    "decision_history_missing",
                    f"Superseded Review Decision is missing: {decision_path}",
                )
            decision_sha = sha256_file(decision_file)
            decision = self.store.read_review_decision(batch_id, relative_path=decision_path)
            if decision["decision_id"] != supersedes:
                raise _error(
                    "decision_history_identity_mismatch",
                    "Superseded Review Decision identity does not match its path",
                )
            if decision["item_id"] != item.item_id:
                raise _error(
                    "decision_history_item_mismatch",
                    "Superseded Review Decision item does not match the current item",
                )

    def _read_decision_by_reference(
        self,
        batch_id: str,
        item: BatchItem,
        reference: Mapping[str, Any],
    ) -> dict[str, Any]:
        decision = self.store.read_review_decision(
            batch_id,
            relative_path=reference["path"],
        )
        decision_file = self.store.run_dir(batch_id) / reference["path"]
        if sha256_file(decision_file) != reference["sha256"]:
            raise _error(
                "review_decision_hash_drift",
                f"Review Decision hash drifted for {item.item_id}",
            )
        if decision["item_id"] != item.item_id:
            raise _error(
                "review_decision_item_mismatch",
                f"Review Decision item_id does not match {item.item_id}",
            )
        if _decision_path(item.language, item.resource_key, decision["decision_id"]) != reference["path"]:
            raise _error(
                "review_decision_path_mismatch",
                "Review Decision path is not canonical",
            )
        return decision

    def _read_history_index(self, path: Path) -> dict[str, Any]:
        if not path.is_absolute():
            path = (self.root / path).resolve()
        if not path.is_file():
            raise _error("history_index_missing", f"History index is missing: {path}")
        value = _read_json(path)
        if value.get("schema_version") != "1.0" or not isinstance(value.get("batches"), list):
            raise _error(
                "invalid_history_index",
                "History index must use schema_version 1.0 and a batches array",
            )
        seen: set[str] = set()
        for index, entry in enumerate(value["batches"]):
            if not isinstance(entry, Mapping):
                raise _error("invalid_history_index", f"batches[{index}] must be an object")
            if set(entry) - {"batch_id", "label"}:
                raise _error("invalid_history_index", f"batches[{index}] has unknown fields")
            batch_id = entry.get("batch_id")
            if not isinstance(batch_id, str) or not batch_id:
                raise _error("invalid_history_index", f"batches[{index}].batch_id is required")
            if batch_id in seen:
                raise _error("invalid_history_index", f"Duplicate history Batch ID: {batch_id}")
            seen.add(batch_id)
            label = entry.get("label")
            if label is not None and (not isinstance(label, str) or not label):
                raise _error("invalid_history_index", f"batches[{index}].label must be non-empty")
        return value

    @staticmethod
    def _history_summary(history_index: Mapping[str, Any] | None) -> dict[str, Any]:
        if history_index is None:
            return {
                "configured": False,
                "batches": [],
            }
        return {
            "configured": True,
            "batches": copy.deepcopy(list(history_index["batches"])),
        }


__all__ = [
    "ReviewWorkbenchError",
    "ReviewWorkbenchService",
    "WorkbenchBatchSelection",
]
