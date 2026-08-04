"""Controlled Review Decision service for Step 4 Slice C."""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from src.content_sampling.artifacts import artifact_json_sha256
from src.core.product_catalog import sha256_file
from src.pipeline.models import (
    BatchItem,
    items_from_dicts,
    summarize_batch_manifest,
    utc_now,
)
from src.pipeline.state_store import (
    ManifestConflictError,
    RepositoryLock,
    StateStore,
)
from src.review.contracts import (
    ApprovalBlocker,
    EvidenceBindings,
    LEGACY_P3_PROFILE_IDENTITY,
    ReviewContractError,
    SUCCESSOR_P3_PROFILE_IDENTITY,
    derive_approval_eligibility,
    derive_evidence_binding,
    derive_review_decision_id,
    machine_approval_preconditions,
    precondition_result_from_mapping,
    validate_inspected_states,
    validate_review_transition,
)


ReviewStatusFilter = Literal["pending", "approved", "rejected", "all"]


class ReviewServiceError(RuntimeError):
    """A controlled review operation failed with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ReviewDecisionRequest:
    batch_id: str
    item_id: str
    expected_revision: int
    reviewer: str
    verdict: str
    reason: str | None = None
    notes: str = ""
    inspected_states: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class ReviewDecisionResult:
    batch_id: str
    item_id: str
    decision_id: str
    decision_path: str
    decision_sha256: str
    committed_revision: int
    current_revision: int
    review: str
    evidence_binding: str
    approval_eligibility: str
    projection_status: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "item_id": self.item_id,
            "decision_id": self.decision_id,
            "decision_path": self.decision_path,
            "decision_sha256": self.decision_sha256,
            "committed_revision": self.committed_revision,
            "current_revision": self.current_revision,
            "review": self.review,
            "evidence_binding": self.evidence_binding,
            "approval_eligibility": self.approval_eligibility,
            "projection_status": self.projection_status,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ReviewEvidenceSnapshot:
    batch_id: str
    item: BatchItem
    manifest_item: Mapping[str, Any]
    validation: Mapping[str, Any]
    sampled_evidence: Mapping[str, Any]
    sampling_plan: Mapping[str, Any] | None
    current_bindings: EvidenceBindings
    coverage: Mapping[str, Any]
    source_quality_findings: tuple[Mapping[str, Any], ...]
    source_preconditions: Mapping[str, Any]
    allowed_state_ids: tuple[str, ...]
    state_universe: tuple[Mapping[str, Any], ...]
    current_decision: Mapping[str, Any] | None
    current_decision_reference: Mapping[str, Any] | None

    @property
    def inspection_mode(self) -> Literal["interactive", "full"]:
        return "interactive" if self.sampling_plan is not None else "full"


def _error(code: str, message: str) -> ReviewServiceError:
    return ReviewServiceError(code, message)


def _artifact_reference(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    return copy.deepcopy(dict(value)) if value is not None else None


def _decision_path(decision: Mapping[str, Any]) -> str:
    return (
        Path(
            "review",
            "decisions",
            str(decision["language"]),
            str(decision["resource_key"]),
            f"{decision['decision_id']}.json",
        )
        .as_posix()
    )


class ReviewService:
    """UI-independent authority for review queue projection and decisions."""

    def __init__(
        self,
        root: str | Path = ".",
        runs_dir: str | Path = "runs",
        *,
        state_store: StateStore | None = None,
        now: Callable[[], str] = utc_now,
    ) -> None:
        self.root = Path(root).resolve()
        self.store = state_store or StateStore(self.root, runs_dir)
        self._now = now

    def list_items(
        self,
        batch_id: str,
        *,
        status: ReviewStatusFilter = "pending",
        item_id: str | None = None,
    ) -> dict[str, Any]:
        queue = self.build_queue(batch_id)
        return self._filtered_queue(queue, status=status, item_id=item_id)

    def get_item_evidence(
        self,
        batch_id: str,
        item_id: str,
    ) -> dict[str, Any]:
        frozen = self.store.read_input_manifest(batch_id)
        manifest = self.store.read_manifest(batch_id)
        if not self._is_supported_review_profile(manifest):
            raise _error(
                "unsupported_review_profile",
                "Review evidence snapshots require Validation Profile P3",
            )
        items = {item.item_id: item for item in items_from_dicts(frozen["items"])}
        if item_id not in items:
            raise _error("unknown_item", f"Unknown Batch Item: {item_id}")
        snapshot = self._snapshot(batch_id, manifest, items[item_id])
        return {
            "batch_id": batch_id,
            "item_id": item_id,
            "manifest_revision": manifest["revision"],
            "validation": copy.deepcopy(dict(snapshot.validation)),
            "sampled_content_evidence": copy.deepcopy(
                dict(snapshot.sampled_evidence)
            ),
            "sampling_plan": (
                copy.deepcopy(dict(snapshot.sampling_plan))
                if snapshot.sampling_plan is not None
                else None
            ),
            "bindings": snapshot.current_bindings.to_dict(),
            "source_quality_findings": [
                dict(finding) for finding in snapshot.source_quality_findings
            ],
            "allowed_state_ids": list(snapshot.allowed_state_ids),
            "inspection_mode": snapshot.inspection_mode,
        }

    def evidence_snapshot(
        self,
        batch_id: str,
        item_id: str,
        *,
        manifest: Mapping[str, Any] | None = None,
    ) -> ReviewEvidenceSnapshot:
        """Return the authoritative current evidence snapshot for one item."""

        current_manifest = (
            copy.deepcopy(dict(manifest))
            if manifest is not None
            else self.store.read_manifest(batch_id)
        )
        frozen = self.store.read_input_manifest(batch_id)
        items = {item.item_id: item for item in items_from_dicts(frozen["items"])}
        item = items.get(item_id)
        if item is None:
            raise _error("unknown_item", f"Unknown Batch Item: {item_id}")
        return self._snapshot(batch_id, current_manifest, item)

    def decide(self, request: ReviewDecisionRequest) -> ReviewDecisionResult:
        reviewer = request.reviewer.strip()
        if not reviewer:
            raise _error("invalid_reviewer", "reviewer must be non-empty")
        if not isinstance(request.expected_revision, int):
            raise _error(
                "invalid_expected_revision",
                "expected_revision must be an integer",
            )
        with RepositoryLock(
            self.store.lock_root,
            batch_id=request.batch_id,
            command="pipeline-review-decide",
        ):
            manifest = self.store.read_manifest(request.batch_id)
            if manifest["revision"] != request.expected_revision:
                raise ManifestConflictError(
                    f"Batch {request.batch_id} revision is {manifest['revision']}, "
                    f"expected {request.expected_revision}"
                )
            if not self._is_supported_review_profile(manifest):
                raise _error(
                    "unsupported_review_profile",
                    "Review Decisions require Validation Profile P3",
                )
            if manifest["status"] not in ("completed", "completed_with_failures"):
                raise _error(
                    "batch_not_terminal",
                    "Review Decisions require a completed Batch",
                )
            frozen = self.store.read_input_manifest(request.batch_id)
            items = {
                item.item_id: item for item in items_from_dicts(frozen["items"])
            }
            item = items.get(request.item_id)
            if item is None:
                raise _error("unknown_item", f"Unknown Batch Item: {request.item_id}")
            snapshot = self._snapshot(request.batch_id, manifest, item)
            self._assert_decidable(snapshot)

            current_decision_id = (
                str(snapshot.current_decision["decision_id"])
                if snapshot.current_decision is not None
                else None
            )
            inspected = tuple(copy.deepcopy(dict(value)) for value in request.inspected_states)
            try:
                transition = validate_review_transition(
                    execution_status=snapshot.manifest_item["status"]["execution"],
                    validation_status=snapshot.manifest_item["status"]["validation"],
                    current_bindings=snapshot.current_bindings,
                    decision_bindings=snapshot.current_bindings,
                    source_quality_findings=snapshot.source_quality_findings,
                    source_preconditions=snapshot.source_preconditions,
                    inspection_mode=snapshot.inspection_mode,
                    inspected_states=inspected,
                    allowed_state_ids=snapshot.allowed_state_ids,
                    verdict=request.verdict,
                    reason=request.reason,
                    current_decision_id=current_decision_id,
                    supersedes_decision_id=current_decision_id,
                )
            except ReviewContractError as error:
                raise _error(error.code, str(error)) from error

            decision_body: dict[str, Any] = {
                "schema_version": "1.0",
                "decision_id": "0" * 64,
                "batch_id": request.batch_id,
                "item_id": item.item_id,
                "resource_key": item.resource_key,
                "language": item.language,
                "reviewer": reviewer,
                "decided_at": self._now(),
                "verdict": transition.verdict,
                "reason": transition.reason,
                "notes": request.notes,
                "bindings": snapshot.current_bindings.to_dict(),
                "inspected_states": [
                    state.to_dict() for state in transition.inspected_states
                ],
                "supersedes_decision_id": current_decision_id,
            }
            decision_body["decision_id"] = derive_review_decision_id(decision_body)
            relative_path = _decision_path(decision_body)
            decision_path = self.store.write_review_decision(
                request.batch_id,
                decision_body,
                relative_path=relative_path,
            )
            decision_sha256 = sha256_file(decision_path)

            def mutate(value: dict[str, Any]) -> None:
                current = value["items"][item.item_id]
                current["artifacts"]["current_review_decision"] = {
                    "path": relative_path,
                    "sha256": decision_sha256,
                }
                current["status"]["review"] = transition.verdict
                current["status"]["evidence_binding"] = "bound"
                current["status"]["approval_eligibility"] = (
                    transition.approval_eligibility.status
                )
                value["summary"] = summarize_batch_manifest(value)

            updated = self.store.update_manifest(
                request.batch_id,
                mutate,
                expected_revision=request.expected_revision,
                changed_item_ids=(item.item_id,),
            )
            warnings: list[str] = []
            projection_status = "rebuilt"
            try:
                self.rebuild_queue(request.batch_id)
                current_manifest = self.store.read_manifest(request.batch_id)
            except Exception as error:  # pragma: no cover - covered by service callers
                projection_status = "projection_rebuild_pending"
                warnings.append(str(error))
                current_manifest = updated
            current_item = current_manifest["items"][item.item_id]
            return ReviewDecisionResult(
                batch_id=request.batch_id,
                item_id=item.item_id,
                decision_id=str(decision_body["decision_id"]),
                decision_path=relative_path,
                decision_sha256=decision_sha256,
                committed_revision=int(updated["revision"]),
                current_revision=int(current_manifest["revision"]),
                review=str(current_item["status"]["review"]),
                evidence_binding=str(current_item["status"]["evidence_binding"]),
                approval_eligibility=str(
                    current_item["status"]["approval_eligibility"]
                ),
                projection_status=projection_status,
                warnings=tuple(warnings),
            )

    def rebuild_queue(self, batch_id: str) -> dict[str, Any]:
        projection = self.build_queue(batch_id)
        self.store.write_projection(batch_id, "review", projection)
        return projection

    def build_queue(self, batch_id: str) -> dict[str, Any]:
        manifest = self.store.read_manifest(batch_id)
        if not self._is_supported_review_profile(manifest):
            return self.store.read_projection(batch_id, "review")
        frozen = self.store.read_input_manifest(batch_id)
        items = items_from_dicts(frozen["items"])
        queue_items: list[dict[str, Any]] = []
        for item in items:
            current = manifest["items"][item.item_id]
            if (
                current["status"]["execution"] != "succeeded"
                or current["status"]["validation"] != "passed"
            ):
                continue
            snapshot = self._snapshot(batch_id, manifest, item)
            queue_items.append(self._queue_item(snapshot))
        summary = self._queue_summary(queue_items)
        return {
            "schema_version": "2.0",
            "batch_id": batch_id,
            "manifest_revision": manifest["revision"],
            "generated_at": (
                manifest["checkpoints"]["review"].get("completed_at")
                or manifest["updated_at"]
            ),
            "summary": summary,
            "items": queue_items,
        }

    def lifecycle_after_validation(
        self,
        *,
        batch_id: str,
        item: BatchItem,
        manifest_item: Mapping[str, Any],
        validation_projection: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Derive post-validation review state without mutating artifacts."""

        machine = machine_approval_preconditions(
            str(manifest_item["status"]["execution"]),
            str(manifest_item["status"]["validation"]),
        )
        try:
            source = precondition_result_from_mapping(
                validation_projection["evidence"]["approval_preconditions"]["source"]
            )
            eligibility = derive_approval_eligibility(
                machine=machine,
                source=source,
            )
        except ReviewContractError as error:
            raise _error(error.code, str(error)) from error

        reference = manifest_item["artifacts"].get("current_review_decision")
        if reference is None:
            return {
                "review": (
                    "pending"
                    if validation_projection.get("status") == "passed"
                    else "not_requested"
                ),
                "evidence_binding": "not_applicable",
                "approval_eligibility": eligibility.status,
            }
        decision = self._read_current_decision(batch_id, item, reference)
        if validation_projection.get("status") != "passed":
            return {
                "review": "pending",
                "evidence_binding": "stale",
                "approval_eligibility": eligibility.status,
            }
        bindings = self._bindings_from_validation(
            validation_projection,
            validation_artifact_sha256=str(
                manifest_item["artifacts"]["validation"]["sha256"]
            ),
        )
        binding = derive_evidence_binding(bindings, decision["bindings"])
        if binding != "bound":
            return {
                "review": "pending",
                "evidence_binding": "stale",
                "approval_eligibility": eligibility.status,
            }
        inspection_mode = (
            "interactive" if bindings.sampling_plan_sha256 is not None else "full"
        )
        allowed_state_ids: tuple[str, ...] = ()
        if inspection_mode == "interactive":
            plan_ref = manifest_item["artifacts"].get("sampling_plan")
            if plan_ref is None or plan_ref.get("sha256") is None:
                return {
                    "review": "pending",
                    "evidence_binding": "bound",
                    "approval_eligibility": eligibility.status,
                }
            plan = self.store.read_step4_artifact(
                batch_id,
                "sampling_plan",
                relative_path=plan_ref["path"],
            )
            allowed_state_ids = tuple(
                str(state["state_id"])
                for state in plan["state_universe"]["states"]
            )
        try:
            validate_inspected_states(
                decision["inspected_states"],
                inspection_mode=inspection_mode,
                allowed_state_ids=allowed_state_ids,
            )
        except ReviewContractError:
            return {
                "review": "pending",
                "evidence_binding": "bound",
                "approval_eligibility": eligibility.status,
            }
        return {
            "review": str(decision["verdict"]),
            "evidence_binding": "bound",
            "approval_eligibility": eligibility.status,
        }

    @staticmethod
    def _profile_id(manifest: Mapping[str, Any]) -> str:
        validation_context = manifest.get("validation_context")
        if isinstance(validation_context, Mapping):
            validation_profile = validation_context.get("validation_profile")
            if (
                isinstance(validation_profile, Mapping)
                and isinstance(validation_profile.get("id"), str)
            ):
                return str(validation_profile["id"])
        if isinstance(manifest.get("validation_profile_id"), str):
            return str(manifest["validation_profile_id"])
        return "legacy-profile-unrecorded"

    @staticmethod
    def _profile_identity(manifest: Mapping[str, Any]) -> Mapping[str, Any] | None:
        validation_context = manifest.get("validation_context")
        if isinstance(validation_context, Mapping):
            validation_profile = validation_context.get("validation_profile")
            if isinstance(validation_profile, Mapping):
                return validation_profile
        return None

    @classmethod
    def _is_supported_review_profile(cls, manifest: Mapping[str, Any]) -> bool:
        profile = cls._profile_identity(manifest)
        if profile is None:
            return False
        return dict(profile) in (
            LEGACY_P3_PROFILE_IDENTITY,
            SUCCESSOR_P3_PROFILE_IDENTITY,
        )

    def _snapshot(
        self,
        batch_id: str,
        manifest: Mapping[str, Any],
        item: BatchItem,
    ) -> ReviewEvidenceSnapshot:
        current = manifest["items"][item.item_id]
        validation_ref = current["artifacts"]["validation"]
        validation_sha = validation_ref["sha256"]
        if not validation_sha:
            raise _error(
                "missing_validation_artifact",
                f"Validation artifact SHA is missing for {item.item_id}",
            )
        validation_path = validation_ref["path"]
        validation_file = self.store.run_dir(batch_id) / validation_path
        if not validation_file.is_file() or sha256_file(validation_file) != validation_sha:
            raise _error(
                "validation_artifact_untrusted",
                f"Validation artifact is missing or hash-drifted for {item.item_id}",
            )
        validation = self.store.read_projection(
            batch_id,
            "validation",
            relative_path=validation_path,
        )
        if validation.get("schema_version") not in ("2.0", "2.1"):
            raise _error(
                "unsupported_validation_projection",
                "Review Decisions require Validation Projection 2.0 or 2.1",
            )
        manifest_profile = self._profile_identity(manifest)
        validation_profile = validation["evidence"]["bindings"]["validation_profile"]
        if manifest_profile is None or dict(manifest_profile) != dict(validation_profile):
            raise _error(
                "validation_profile_mismatch",
                "Validation Projection profile identity differs from the Batch",
            )
        if validation.get("item_id") != item.item_id:
            raise _error(
                "validation_item_mismatch",
                f"Validation Projection item_id does not match {item.item_id}",
            )

        evidence_ref = current["artifacts"]["sampled_content_evidence"]
        if evidence_ref is None or not evidence_ref["sha256"]:
            raise _error(
                "missing_sampled_content_evidence",
                f"Sampled Content Evidence is missing for {item.item_id}",
            )
        sampled = self.store.read_step4_artifact(
            batch_id,
            "sampled_content_evidence",
            relative_path=evidence_ref["path"],
        )
        if artifact_json_sha256(sampled) != evidence_ref["sha256"]:
            raise _error(
                "sampled_content_evidence_untrusted",
                f"Sampled Content Evidence hash drifted for {item.item_id}",
            )
        content_binding = validation["evidence"]["content_validation"][
            "sampled_content_evidence"
        ]
        if (
            content_binding["path"] != evidence_ref["path"]
            or content_binding["artifact_sha256"] != evidence_ref["sha256"]
            or content_binding["evidence_sha256"] != sampled["evidence_sha256"]
        ):
            raise _error(
                "validation_evidence_binding_mismatch",
                f"Validation evidence binding does not match sampled evidence for {item.item_id}",
            )

        plan = None
        state_universe: tuple[Mapping[str, Any], ...] = ()
        allowed_state_ids: tuple[str, ...] = ()
        plan_ref = current["artifacts"].get("sampling_plan")
        plan_binding = validation["evidence"]["bindings"]["sampling_plan"]
        if plan_binding is None:
            if plan_ref is not None and plan_ref.get("sha256") is not None:
                raise _error(
                    "unexpected_sampling_plan",
                    f"Full-mode item unexpectedly has a Sampling Plan for {item.item_id}",
                )
        else:
            if plan_ref is None or not plan_ref["sha256"]:
                raise _error(
                    "missing_sampling_plan",
                    f"Sampling Plan is missing for {item.item_id}",
                )
            if (
                plan_binding["path"] != plan_ref["path"]
                or plan_binding["artifact_sha256"] != plan_ref["sha256"]
            ):
                raise _error(
                    "sampling_plan_binding_mismatch",
                    f"Validation evidence binding does not match Sampling Plan for {item.item_id}",
                )
            plan = self.store.read_step4_artifact(
                batch_id,
                "sampling_plan",
                relative_path=plan_ref["path"],
            )
            if artifact_json_sha256(plan) != plan_ref["sha256"]:
                raise _error(
                    "sampling_plan_untrusted",
                    f"Sampling Plan hash drifted for {item.item_id}",
                )
            if plan["plan_sha256"] != plan_binding["plan_sha256"]:
                raise _error(
                    "sampling_plan_identity_mismatch",
                    f"Sampling Plan semantic identity drifted for {item.item_id}",
                )
            state_universe = tuple(
                copy.deepcopy(dict(state))
                for state in plan["state_universe"]["states"]
            )
            allowed_state_ids = tuple(str(state["state_id"]) for state in state_universe)

        bindings = self._bindings_from_validation(
            validation,
            validation_artifact_sha256=str(validation_sha),
        )
        decision_ref = current["artifacts"].get("current_review_decision")
        decision = (
            self._read_current_decision(batch_id, item, decision_ref)
            if decision_ref is not None
            else None
        )
        return ReviewEvidenceSnapshot(
            batch_id=batch_id,
            item=item,
            manifest_item=copy.deepcopy(dict(current)),
            validation=validation,
            sampled_evidence=sampled,
            sampling_plan=plan,
            current_bindings=bindings,
            coverage=validation["evidence"]["content_validation"]["coverage"],
            source_quality_findings=tuple(
                copy.deepcopy(dict(finding))
                for finding in validation["evidence"]["source_quality_findings"]
            ),
            source_preconditions=copy.deepcopy(dict(
                validation["evidence"]["approval_preconditions"]["source"]
            )),
            allowed_state_ids=allowed_state_ids,
            state_universe=state_universe,
            current_decision=decision,
            current_decision_reference=(
                copy.deepcopy(dict(decision_ref))
                if decision_ref is not None
                else None
            ),
        )

    def _read_current_decision(
        self,
        batch_id: str,
        item: BatchItem,
        reference: Mapping[str, Any],
    ) -> dict[str, Any]:
        decision = self.store.read_review_decision(
            batch_id,
            relative_path=reference["path"],
        )
        path = self.store.run_dir(batch_id) / reference["path"]
        if sha256_file(path) != reference["sha256"]:
            raise _error(
                "current_review_decision_untrusted",
                f"Current Review Decision hash drifted for {item.item_id}",
            )
        if decision["item_id"] != item.item_id:
            raise _error(
                "current_review_decision_item_mismatch",
                f"Current Review Decision item_id does not match {item.item_id}",
            )
        expected_path = _decision_path(decision)
        if expected_path != reference["path"]:
            raise _error(
                "current_review_decision_path_mismatch",
                "Current Review Decision path is not canonical",
            )
        return decision

    @staticmethod
    def _bindings_from_validation(
        validation: Mapping[str, Any],
        *,
        validation_artifact_sha256: str,
    ) -> EvidenceBindings:
        bindings = validation["evidence"]["bindings"]
        plan = bindings["sampling_plan"]
        return EvidenceBindings(
            source_sha256=bindings["source"]["sha256"],
            payload_sha256=bindings["payload"]["sha256"],
            validation_artifact_sha256=validation_artifact_sha256,
            validation_evidence_sha256=validation["evidence_sha256"],
            sampling_plan_sha256=(
                plan["plan_sha256"] if plan is not None else None
            ),
        )

    @staticmethod
    def _assert_decidable(snapshot: ReviewEvidenceSnapshot) -> None:
        status = snapshot.manifest_item["status"]
        if status["execution"] != "succeeded" or status["validation"] != "passed":
            raise _error(
                "machine_preconditions_failed",
                "Machine failure cannot be overridden by a Review Decision",
            )
        if status["publication"] == "published" or status["release"] == "released":
            raise _error(
                "item_already_released",
                "Released or published items require a new Batch for review changes",
            )

    def _queue_item(self, snapshot: ReviewEvidenceSnapshot) -> dict[str, Any]:
        status = snapshot.manifest_item["status"]
        machine = machine_approval_preconditions(
            status["execution"],
            status["validation"],
        )
        source = precondition_result_from_mapping(snapshot.source_preconditions)
        blockers: list[ApprovalBlocker] = [*machine.blockers, *source.blockers]
        return {
            "item_id": snapshot.item.item_id,
            "product_key": snapshot.item.product_key,
            "resource_key": snapshot.item.resource_key,
            "language": snapshot.item.language,
            "page_model": snapshot.item.page_model,
            "strategy": snapshot.manifest_item["strategy"],
            "status": {
                key: status[key]
                for key in (
                    "execution",
                    "validation",
                    "review",
                    "publication",
                    "evidence_binding",
                    "approval_eligibility",
                    "release",
                )
            },
            "artifacts": {
                key: _artifact_reference(snapshot.manifest_item["artifacts"].get(key))
                for key in (
                    "payload",
                    "diagnostic",
                    "validation",
                    "sampling_plan",
                    "sampled_content_evidence",
                    "current_review_decision",
                )
            },
            "bindings": snapshot.current_bindings.to_dict(),
            "coverage": {
                "mode": snapshot.coverage["mode"],
                "universe_count": snapshot.coverage["universe_count"],
                "selected_count": snapshot.coverage["selected_count"],
                "untested_count": snapshot.coverage["untested_count"],
                "selected_state_ids": list(snapshot.coverage["selected_state_ids"]),
            },
            "inspection": {
                "mode": snapshot.inspection_mode,
                "state_universe": [
                    copy.deepcopy(dict(state)) for state in snapshot.state_universe
                ],
                "full_content_scope": snapshot.inspection_mode == "full",
            },
            "source_quality_findings": [
                {
                    "code": str(finding["code"]),
                    "message": str(finding["message"]),
                    "path": str(finding["path"]),
                }
                for finding in snapshot.source_quality_findings
            ],
            "approval_blockers": [
                blocker.to_dict() for blocker in blockers
            ],
            "current_decision": self._decision_summary(snapshot),
        }

    @staticmethod
    def _decision_summary(
        snapshot: ReviewEvidenceSnapshot,
    ) -> dict[str, Any] | None:
        if snapshot.current_decision is None or snapshot.current_decision_reference is None:
            return None
        decision = snapshot.current_decision
        return {
            "decision_id": decision["decision_id"],
            "path": snapshot.current_decision_reference["path"],
            "sha256": snapshot.current_decision_reference["sha256"],
            "reviewer": decision["reviewer"],
            "decided_at": decision["decided_at"],
            "verdict": decision["verdict"],
            "reason": decision["reason"],
            "supersedes_decision_id": decision["supersedes_decision_id"],
        }

    @staticmethod
    def _queue_summary(queue_items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
        return {
            "total": len(queue_items),
            "reviewable": sum(
                item["status"]["evidence_binding"] != "stale"
                for item in queue_items
            ),
            "pending": sum(
                item["status"]["review"] == "pending" for item in queue_items
            ),
            "approved": sum(
                item["status"]["review"] == "approved" for item in queue_items
            ),
            "rejected": sum(
                item["status"]["review"] == "rejected" for item in queue_items
            ),
            "evidence_bound": sum(
                item["status"]["evidence_binding"] == "bound"
                for item in queue_items
            ),
            "evidence_stale": sum(
                item["status"]["evidence_binding"] == "stale"
                for item in queue_items
            ),
            "evidence_not_applicable": sum(
                item["status"]["evidence_binding"] == "not_applicable"
                for item in queue_items
            ),
            "approval_eligible": sum(
                item["status"]["approval_eligibility"] == "eligible"
                for item in queue_items
            ),
            "approval_blocked": sum(
                item["status"]["approval_eligibility"] == "blocked"
                for item in queue_items
            ),
            "source_blocked": sum(
                bool(item["source_quality_findings"]) for item in queue_items
            ),
        }

    @classmethod
    def _filtered_queue(
        cls,
        queue: Mapping[str, Any],
        *,
        status: ReviewStatusFilter,
        item_id: str | None,
    ) -> dict[str, Any]:
        if status not in ("pending", "approved", "rejected", "all"):
            raise _error("invalid_status_filter", f"Invalid review status: {status}")

        def review_status(value: Mapping[str, Any]) -> str:
            current = value["status"]
            if isinstance(current, Mapping):
                return str(current["review"])
            return str(current)

        items = [
            copy.deepcopy(dict(item))
            for item in queue["items"]
            if (status == "all" or review_status(item) == status)
            and (item_id is None or item["item_id"] == item_id)
        ]
        result = copy.deepcopy(dict(queue))
        result["items"] = items
        if queue.get("schema_version") == "2.0":
            result["summary"] = cls._queue_summary(items)
        else:
            result["summary"] = {"pending": len(items)}
        return result


__all__ = [
    "ReviewDecisionRequest",
    "ReviewDecisionResult",
    "ReviewEvidenceSnapshot",
    "ReviewService",
    "ReviewServiceError",
]
