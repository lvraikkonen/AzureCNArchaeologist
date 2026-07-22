"""Authoritative seven-stage coordinator for v0.3 batch runs."""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from scripts.auto_copy_html import HTMLFileCopier
from src.batch.process_engine import (
    BatchProcessEngine,
    ResourceProcessingInfo,
    ResourceProcessingResult,
)
from src.core.contract_validator import ContractValidator
from src.core.data_models import ExtractionStrategy
from src.core.extraction_coordinator import ExtractionCoordinator
from src.core.product_catalog import sha256_file
from src.core.product_manager import ProductManager
from src.core.strategy_manager import StrategyManager
from src.pipeline.models import (
    BatchItem,
    InputManifest,
    STAGES,
    derive_batch_availability,
    items_from_dicts,
    summarize_batch_manifest,
    utc_now,
)
from src.pipeline.planner import PipelinePlanner
from src.pipeline.provenance import ProvenanceProvider
from src.pipeline.state_store import (
    RepositoryLock,
    StateStore,
    StateStoreError,
    generate_batch_id,
)
from src.strategies.strategy_factory import StrategyFactory


class PipelineError(RuntimeError):
    """A fatal batch-level error; CLI callers must return exit code 1."""


@dataclass(frozen=True)
class PipelineOutcome:
    batch_id: str
    status: str
    exit_code: int
    summary: Mapping[str, int]
    run_dir: Path


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


def _timestamp_elapsed_ms(started_at: str, completed_at: str) -> int:
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, round((completed - started).total_seconds() * 1000))


def _error(code: str, stage: str, message: str, **details: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"code": code, "stage": stage, "message": message}
    if details:
        value["details"] = details
    return value


class PipelineCoordinator:
    """Run, resume and explicitly revalidate manifest-authoritative batches.

    Workers only return outcomes. All mutations of ``batch-manifest.json`` and
    all projection writes happen on the calling thread.
    """

    def __init__(
        self,
        root: str | Path = ".",
        runs_dir: str | Path = "runs",
        *,
        planner: PipelinePlanner | None = None,
        state_store: StateStore | None = None,
        provenance: ProvenanceProvider | None = None,
        copier_factory: Callable[[Path], HTMLFileCopier] | None = None,
        extraction_factory: Callable[[Path], ExtractionCoordinator] | None = None,
        engine_factory: Callable[[int], BatchProcessEngine] | None = None,
        strategy_manager_factory: Callable[[Path], StrategyManager] | None = None,
        batch_id_factory: Callable[[], str] | None = None,
        now: Callable[[], str] = utc_now,
    ) -> None:
        self.root = Path(root).resolve()
        self.store = state_store or StateStore(self.root, runs_dir)
        self.planner = planner or PipelinePlanner(self.root)
        self.provenance = provenance or ProvenanceProvider(self.root)
        self._copier_factory = copier_factory or (lambda root: HTMLFileCopier(root))
        self._extraction_factory = extraction_factory or self._default_extraction_factory
        self._engine_factory = engine_factory or (
            lambda workers: BatchProcessEngine(max_workers=workers, persist_records=False)
        )
        self._strategy_manager_factory = strategy_manager_factory or self._default_strategy_manager
        self._batch_id_factory = batch_id_factory or generate_batch_id
        self._now = now
        self._contract_validator = ContractValidator(self.root)

    def run(
        self,
        *,
        all_products: bool = False,
        group: str | None = None,
        language: str = "both",
        parallel_jobs: int = 4,
        allow_dirty: bool = False,
    ) -> PipelineOutcome:
        """Create and execute a new immutable batch scope."""
        if all_products == bool(group):
            raise PipelineError("Exactly one of all_products or group is required")
        self._validate_parallel_jobs(parallel_jobs)
        scope = "all" if all_products else "group"

        # The clean/index/contract gates intentionally run before create_run.
        # The repository lock may create its ignored lock parent, never a batch
        # directory or an input manifest.
        with RepositoryLock(self.root):
            frozen_provenance = self.provenance.capture(allow_dirty=allow_dirty)
            plan = self.planner.plan(scope, group=group, language=language)
            batch_id = self._batch_id_factory()
            frozen = InputManifest.from_plan(
                batch_id,
                plan,
                frozen_provenance,
                created_at=self._now(),
            )
            run_dir = self.store.create_run(frozen)
            try:
                self._complete_discovery(batch_id)
                return self._execute(batch_id, parallel_jobs, resume=False)
            except KeyboardInterrupt:
                self._log_event(batch_id, "discovery", "interrupted", error_code="USER_INTERRUPTED")
                raise
            except Exception as exc:
                self._mark_batch_failed(batch_id, exc)
                raise

    def resume(self, batch_id: str, *, parallel_jobs: int = 4) -> PipelineOutcome:
        """Resume operationally failed or interrupted stages without redoing success."""
        self._validate_parallel_jobs(parallel_jobs)
        with RepositoryLock(self.root):
            frozen = self.store.read_input_manifest(batch_id)
            self.provenance.verify(frozen["provenance"])
            manifest = self.store.read_manifest(batch_id)
            try:
                if manifest["checkpoints"]["discovery"]["status"] != "succeeded":
                    self._complete_discovery(batch_id)
                self._reconcile_for_resume(batch_id, frozen)
                return self._execute(batch_id, parallel_jobs, resume=True)
            except KeyboardInterrupt:
                self._log_event(batch_id, "discovery", "interrupted", error_code="USER_INTERRUPTED")
                raise
            except Exception as exc:
                self._mark_batch_failed(batch_id, exc)
                raise

    def validate(self, batch_id: str, *, parallel_jobs: int = 4) -> PipelineOutcome:
        """Revalidate existing successful extractions without invoking earlier stages."""
        self._validate_parallel_jobs(parallel_jobs)
        with RepositoryLock(self.root):
            frozen = self.store.read_input_manifest(batch_id)
            self.provenance.verify(frozen["provenance"])
            manifest = self.store.read_manifest(batch_id)
            if manifest["status"] not in ("completed", "completed_with_failures"):
                raise PipelineError(
                    "pipeline-validate requires a completed batch; resume interrupted work first"
                )
            try:
                items = items_from_dicts(frozen["items"])
                candidates = [
                    item for item in items
                    if manifest["items"][item.item_id]["status"]["execution"] == "succeeded"
                ]
                self._run_validation_stage(batch_id, candidates, parallel_jobs, explicit=True)
                self._rebuild_review(batch_id, items)
                return self._finish_report(batch_id, items)
            except KeyboardInterrupt:
                self._log_event(batch_id, "validate", "interrupted", error_code="USER_INTERRUPTED")
                raise
            except Exception as exc:
                self._mark_batch_failed(batch_id, exc)
                raise

    def status(self, batch_id: str) -> dict[str, Any]:
        """Read status without taking or mutating the repository lock."""
        manifest = self.store.read_manifest(batch_id)
        summary = self._status_summary(manifest)
        stored_status = manifest["status"]
        display_status, resumable = derive_batch_availability(
            manifest, lock_is_held=RepositoryLock.is_locked(self.root)
        )
        return {
            "batch_id": batch_id,
            "status": display_status,
            "stored_status": stored_status,
            "revision": manifest["revision"],
            "resumable": resumable,
            "summary": summary,
            "run_dir": self.store.run_dir(batch_id).as_posix(),
        }

    def _execute(self, batch_id: str, parallel_jobs: int, *, resume: bool) -> PipelineOutcome:
        frozen = self.store.read_input_manifest(batch_id)
        items = items_from_dicts(frozen["items"])

        manifest = self.store.read_manifest(batch_id)
        normalize = [
            item
            for item in items
            if item.runnable
            and manifest["items"][item.item_id]["checkpoints"]["normalize"]["status"]
            != "succeeded"
        ]
        self._run_normalize_stage(batch_id, normalize, parallel_jobs)

        manifest = self.store.read_manifest(batch_id)
        preflight = [
            item for item in items
            if item.runnable
            and manifest["items"][item.item_id]["checkpoints"]["normalize"]["status"]
            == "succeeded"
            and manifest["items"][item.item_id]["checkpoints"]["preflight"]["status"]
            != "succeeded"
        ]
        self._run_preflight_stage(batch_id, preflight, parallel_jobs)

        manifest = self.store.read_manifest(batch_id)
        extract = [
            item for item in items
            if item.runnable
            and manifest["items"][item.item_id]["checkpoints"]["preflight"]["status"]
            == "succeeded"
            and manifest["items"][item.item_id]["checkpoints"]["extract"]["status"]
            != "succeeded"
        ]
        self._run_extract_stage(batch_id, extract, parallel_jobs)

        manifest = self.store.read_manifest(batch_id)
        validate = [
            item for item in items
            if item.runnable
            and manifest["items"][item.item_id]["status"]["execution"] == "succeeded"
            and manifest["items"][item.item_id]["status"]["validation"] == "not_run"
        ]
        self._run_validation_stage(batch_id, validate, parallel_jobs, explicit=False)
        self._rebuild_missing_validation_projections(batch_id, items)
        self._rebuild_review(batch_id, items)
        return self._finish_report(batch_id, items)

    # ---- stage implementations -------------------------------------------------

    def _run_normalize_stage(
        self, batch_id: str, items: list[BatchItem], parallel_jobs: int
    ) -> None:
        if not items and self._batch_stage_complete(batch_id, "normalize"):
            return
        self._start_stage(batch_id, "normalize", items)
        copier = self._copier_factory(self.root)
        infos = [self._resource_info(batch_id, item) for item in items]

        def worker(info: ResourceProcessingInfo) -> ResourceProcessingResult:
            started = time.perf_counter()
            item = info.metadata["batch_item"]
            try:
                result = copier.copy_resource(item.product_key, item.language, item.version_key)
                if result.get("status") != "copied":
                    raise RuntimeError(result.get("reason") or "Resource was not copied")
                target = self.root / item.normalized_path
                expected = item.normalized_sha256
                actual = sha256_file(target) if target.is_file() else None
                if expected is None:
                    raise RuntimeError("Frozen Source Snapshot hash is unavailable")
                if actual != expected:
                    raise RuntimeError("Normalized Input hash does not match frozen Source Snapshot")
                return ResourceProcessingResult(
                    info, "succeeded", "not_run", strategy=item.strategy,
                    processing_time_ms=_elapsed_ms(started),
                )
            except Exception as exc:
                return ResourceProcessingResult(
                    info, "failed", "not_run", strategy=item.strategy,
                    processing_time_ms=_elapsed_ms(started),
                    error_code="NORMALIZE_FAILED", error_message=str(exc),
                )

        self._engine_factory(parallel_jobs).process_resource_items(
            infos,
            worker=worker,
            result_callback=lambda result, completed, total: self._commit_stage_result(
                batch_id, "normalize", result
            ),
        )
        self._finish_stage(batch_id, "normalize")

    def _run_preflight_stage(
        self, batch_id: str, items: list[BatchItem], parallel_jobs: int
    ) -> None:
        if not items and self._batch_stage_complete(batch_id, "preflight"):
            return
        self._start_stage(batch_id, "preflight", items)
        strategy_manager = self._strategy_manager_factory(self.root)
        infos = [self._resource_info(batch_id, item) for item in items]

        def worker(info: ResourceProcessingInfo) -> ResourceProcessingResult:
            started = time.perf_counter()
            item = info.metadata["batch_item"]
            try:
                self._check_preflight_artifacts(item)
                selected = strategy_manager.determine_extraction_strategy(
                    str(self.root / item.normalized_path), item.product_key
                )
                if not StrategyFactory.is_strategy_registered(selected.strategy_type):
                    raise RuntimeError(
                        f"Strategy is not registered: {selected.strategy_type.value}"
                    )
                return ResourceProcessingResult(
                    info, "succeeded", "not_run",
                    strategy=selected.strategy_type.value,
                    processing_time_ms=_elapsed_ms(started),
                )
            except Exception as exc:
                return ResourceProcessingResult(
                    info, "failed", "not_run", strategy=item.strategy,
                    processing_time_ms=_elapsed_ms(started),
                    error_code="PREFLIGHT_FAILED", error_message=str(exc),
                )

        self._engine_factory(parallel_jobs).process_resource_items(
            infos,
            worker=worker,
            result_callback=lambda result, completed, total: self._commit_stage_result(
                batch_id, "preflight", result
            ),
        )
        self._finish_stage(batch_id, "preflight")

    def _run_extract_stage(
        self, batch_id: str, items: list[BatchItem], parallel_jobs: int
    ) -> None:
        if not items and self._batch_stage_complete(batch_id, "extract"):
            return
        self._start_stage(batch_id, "extract", items)
        run_dir = self.store.run_dir(batch_id)
        extractor = self._extraction_factory(run_dir)
        manifest = self.store.read_manifest(batch_id)
        infos = []
        for item in items:
            current = manifest["items"][item.item_id]
            info = self._resource_info(batch_id, item)
            info.strategy = current["strategy"]
            infos.append(info)

        def worker(info: ResourceProcessingInfo) -> Any:
            result = extractor.coordinate_extraction(
                info.product_key,
                info.language,
                info.html_file_path,
                info.version_key,
                preselected_strategy=info.strategy,
                defer_validation=True,
            )
            actual_resource_key = result.sidecar.get("resource", {}).get("resource_key")
            if actual_resource_key != info.resource_key:
                raise ValueError(
                    f"Resource Key mismatch: planned {info.resource_key}, "
                    f"extracted {actual_resource_key}"
                )
            expected_payload = (run_dir / info.metadata["batch_item"].output_path).resolve()
            expected_sidecar = (
                run_dir / info.metadata["batch_item"].diagnostic_path
            ).resolve()
            if result.payload_path is None or result.payload_path.resolve() != expected_payload:
                raise ValueError(
                    f"Payload path mismatch for {info.resource_key}: {result.payload_path}"
                )
            if result.sidecar_path.resolve() != expected_sidecar:
                raise ValueError(
                    f"Diagnostic path mismatch for {info.resource_key}: {result.sidecar_path}"
                )
            return result

        def callback(result: ResourceProcessingResult, completed: int, total: int) -> None:
            if not result.execution_succeeded:
                result.error_code = "EXTRACTION_FAILED"
            self._commit_stage_result(batch_id, "extract", result)

        self._engine_factory(parallel_jobs).process_resource_items(
            infos, worker=worker, result_callback=callback
        )
        self._finish_stage(batch_id, "extract")

    def _run_validation_stage(
        self,
        batch_id: str,
        items: list[BatchItem],
        parallel_jobs: int,
        *,
        explicit: bool,
    ) -> None:
        if not items and self._batch_stage_complete(batch_id, "validate"):
            return
        self._start_stage(batch_id, "validate", items)
        run_dir = self.store.run_dir(batch_id)
        extractor = self._extraction_factory(run_dir)
        manifest = self.store.read_manifest(batch_id)
        infos = []
        for item in items:
            info = self._resource_info(batch_id, item)
            info.metadata["manifest_item"] = manifest["items"][item.item_id]
            infos.append(info)

        def worker(info: ResourceProcessingInfo) -> ResourceProcessingResult:
            started = time.perf_counter()
            item = info.metadata["batch_item"]
            state = info.metadata["manifest_item"]
            try:
                integrity_error = self._validate_frozen_extraction_artifacts_from_state(
                    batch_id, item, state
                )
                if integrity_error is not None:
                    return ResourceProcessingResult(
                        info, "succeeded", "failed",
                        strategy=state["strategy"],
                        processing_time_ms=_elapsed_ms(started),
                        error_code=integrity_error["code"],
                        error_message=integrity_error["message"],
                    )
                result = extractor.validate_persisted_payload(
                    item.product_key,
                    item.language,
                    payload_path=run_dir / item.output_path,
                    sidecar_path=run_dir / item.diagnostic_path,
                    html_file_path=self.root / item.normalized_path,
                    version_key=item.version_key,
                )
                sidecar_status = result.sidecar["status"]["validation"]
                first_error = next(iter(result.sidecar["validation"]["errors"]), None)
                return ResourceProcessingResult(
                    info,
                    "succeeded",
                    sidecar_status,
                    strategy=result.sidecar["strategy"]["type"],
                    processing_time_ms=_elapsed_ms(started),
                    extraction_result=result,
                    error_code=(first_error or {}).get("code"),
                    error_message=(first_error or {}).get("message"),
                )
            except Exception as exc:
                return ResourceProcessingResult(
                    info, "succeeded", "failed",
                    strategy=state["strategy"],
                    processing_time_ms=_elapsed_ms(started),
                    error_code="VALIDATION_FAILED", error_message=str(exc),
                )

        def callback(result: ResourceProcessingResult, completed: int, total: int) -> None:
            current = self._commit_stage_result(batch_id, "validate", result)
            self._write_validation_projection(
                batch_id,
                result.item.metadata["batch_item"],
                result,
                current=current,
            )

        self._engine_factory(parallel_jobs).process_resource_items(
            infos, worker=worker, result_callback=callback
        )
        self._finish_stage(batch_id, "validate")
        self._log_event(
            batch_id,
            "validate",
            "succeeded",
            error_code=None,
            explicit=explicit,
        )

    # ---- manifest mutation ------------------------------------------------------

    def _complete_discovery(self, batch_id: str) -> None:
        now = self._now()

        def mutate(manifest: dict[str, Any]) -> None:
            manifest["status"] = "running"
            checkpoint = manifest["checkpoints"]["discovery"]
            if checkpoint["status"] == "succeeded":
                return
            self._start_checkpoint(checkpoint, now)
            self._complete_checkpoint(checkpoint, "succeeded", now, now, None)
            for item in manifest["items"].values():
                item_checkpoint = item["checkpoints"]["discovery"]
                if (
                    item["status"]["execution"] == "skipped"
                    or item_checkpoint["status"] == "succeeded"
                ):
                    continue
                self._start_checkpoint(item_checkpoint, now)
                self._complete_checkpoint(
                    item_checkpoint, "succeeded", now, now, None
                )

        self.store.update_manifest(batch_id, mutate)
        self._log_event(batch_id, "discovery", "succeeded")

    def _start_stage(self, batch_id: str, stage: str, items: Iterable[BatchItem]) -> None:
        selected = tuple(item.item_id for item in items)
        now = self._now()

        def mutate(manifest: dict[str, Any]) -> None:
            manifest["status"] = "running"
            self._start_checkpoint(manifest["checkpoints"][stage], now)
            for item_id in selected:
                item = manifest["items"][item_id]
                self._start_checkpoint(item["checkpoints"][stage], now)
                if stage in ("normalize", "preflight", "extract"):
                    item["status"]["execution"] = "running"
                    item["status"]["validation"] = "not_run"
                    item["status"]["review"] = "not_requested"
                    item["error"] = None
                elif stage == "validate":
                    item["status"]["validation"] = "not_run"
                    item["status"]["review"] = "not_requested"
                    item["error"] = None
                    item["artifacts"]["validation"]["sha256"] = None
                    for downstream in ("review", "report"):
                        checkpoint = item["checkpoints"][downstream]
                        if checkpoint["status"] != "skipped":
                            checkpoint.update({
                                "status": "pending",
                                "started_at": None,
                                "completed_at": None,
                                "duration_ms": None,
                                "error": None,
                            })

        self.store.update_manifest(batch_id, mutate)
        self._log_event(batch_id, stage, "running")

    def _finish_stage(self, batch_id: str, stage: str) -> None:
        now = self._now()

        def mutate(manifest: dict[str, Any]) -> None:
            checkpoint = manifest["checkpoints"][stage]
            failed = sum(
                item["checkpoints"][stage]["status"] == "failed"
                for item in manifest["items"].values()
                if item["checkpoints"][stage]["status"] != "skipped"
            )
            error = (
                _error("ITEM_FAILURES", stage, f"{failed} item(s) failed in {stage}")
                if failed else None
            )
            # A stage can complete despite isolated item failures. Its batch
            # checkpoint records completion while the error/count remains visible.
            self._complete_checkpoint(
                checkpoint, "succeeded", checkpoint.get("started_at") or now, now, error
            )

        self.store.update_manifest(batch_id, mutate, changed_item_ids=())
        self._log_event(batch_id, stage, "succeeded")

    def _commit_stage_result(
        self, batch_id: str, stage: str, result: ResourceProcessingResult
    ) -> dict[str, Any]:
        item = result.item.metadata["batch_item"]
        succeeded = (
            result.validation == "passed" if stage == "validate" else result.execution_succeeded
        )
        status = "succeeded" if succeeded else "failed"
        error = None
        if not succeeded:
            default_code = {
                "normalize": "NORMALIZE_FAILED",
                "preflight": "PREFLIGHT_FAILED",
                "extract": "EXTRACTION_FAILED",
                "validate": "VALIDATION_FAILED",
            }[stage]
            error = _error(
                result.error_code or default_code,
                stage,
                result.error_message or f"{stage} failed",
            )
        completed_at = self._now()

        def mutate(manifest: dict[str, Any]) -> None:
            current = manifest["items"][item.item_id]
            checkpoint = current["checkpoints"][stage]
            started_at = checkpoint.get("started_at") or completed_at
            self._complete_checkpoint(
                checkpoint,
                status,
                started_at,
                completed_at,
                error,
                duration_ms=result.processing_time_ms,
            )
            if result.strategy and result.strategy != "not_selected":
                current["strategy"] = result.strategy

            if stage == "normalize":
                if succeeded:
                    current["artifacts"]["normalized_input"]["sha256"] = sha256_file(
                        self.root / item.normalized_path
                    )
                    current["status"]["execution"] = "pending"
                    current["error"] = None
                else:
                    self._set_item_failed(current, error)
            elif stage == "preflight":
                if succeeded:
                    current["status"]["execution"] = "pending"
                    current["error"] = None
                else:
                    self._set_item_failed(current, error)
            elif stage == "extract":
                if succeeded and result.extraction_result is not None:
                    current["status"]["execution"] = "succeeded"
                    current["status"]["validation"] = "not_run"
                    current["status"]["review"] = "not_requested"
                    current["error"] = None
                    self._capture_run_artifact_hashes(batch_id, current, item, include_validation=False)
                else:
                    self._set_item_failed(current, error)
            elif stage == "validate":
                current["status"]["execution"] = "succeeded"
                current["status"]["validation"] = "passed" if succeeded else "failed"
                current["status"]["review"] = "not_requested"
                current["error"] = error
                # Only a validator-controlled sidecar rewrite may advance the
                # expected sidecar hash. Tampered/unreadable sidecars have no
                # ExtractionResult and keep their previous frozen expectation.
                if result.extraction_result is not None:
                    diagnostic = self.store.run_dir(batch_id) / item.diagnostic_path
                    if diagnostic.is_file():
                        current["artifacts"]["diagnostic"]["sha256"] = sha256_file(diagnostic)

        updated = self.store.update_manifest(
            batch_id, mutate, changed_item_ids=(item.item_id,)
        )
        self._log_item_event(batch_id, item, stage, status, result.strategy, error)
        return updated["items"][item.item_id]

    @staticmethod
    def _set_item_failed(item: dict[str, Any], error: Mapping[str, Any] | None) -> None:
        item["status"]["execution"] = "failed"
        item["status"]["validation"] = "not_run"
        item["status"]["review"] = "not_requested"
        item["error"] = dict(error) if error else None

    @staticmethod
    def _start_checkpoint(checkpoint: dict[str, Any], now: str) -> None:
        if checkpoint["status"] == "running":
            started = checkpoint.get("started_at") or now
            checkpoint["attempts"].append({
                "attempt": len(checkpoint["attempts"]) + 1,
                "started_at": started,
                "completed_at": now,
                "duration_ms": 0,
                "status": "failed",
                "error": _error(
                    "PIPELINE_INTERRUPTED", "pipeline", "Previous attempt did not complete"
                ),
            })
        checkpoint.update({
            "status": "running",
            "started_at": now,
            "completed_at": None,
            "duration_ms": None,
            "error": None,
        })

    @staticmethod
    def _complete_checkpoint(
        checkpoint: dict[str, Any],
        status: str,
        started_at: str,
        completed_at: str,
        error: Mapping[str, Any] | None,
        *,
        duration_ms: int | None = None,
    ) -> None:
        duration = (
            _timestamp_elapsed_ms(started_at, completed_at)
            if duration_ms is None
            else max(0, duration_ms)
        )
        checkpoint.update({
            "status": status,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration,
            "error": dict(error) if error else None,
        })
        checkpoint["attempts"].append({
            "attempt": len(checkpoint["attempts"]) + 1,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration,
            "status": status,
            "error": dict(error) if error else None,
        })

    # ---- reconciliation and projections ----------------------------------------

    def _reconcile_for_resume(
        self, batch_id: str, frozen: Mapping[str, Any]
    ) -> None:
        items = items_from_dicts(frozen["items"])
        current_manifest = self.store.read_manifest(batch_id)
        resets: dict[str, str] = {}
        for item in items:
            if not item.runnable:
                continue
            current = current_manifest["items"][item.item_id]
            normalized = self.root / item.normalized_path
            normalized_ok = (
                item.normalized_sha256 is not None
                and normalized.is_file()
                and sha256_file(normalized) == item.normalized_sha256
            )
            if current["checkpoints"]["normalize"]["status"] == "succeeded" and not normalized_ok:
                resets[item.item_id] = "normalize"
                continue
            if (
                current["checkpoints"]["extract"]["status"] == "succeeded"
                and self._validate_frozen_extraction_artifacts_from_state(
                    batch_id, item, current
                )
            ):
                resets[item.item_id] = "extract"

        if not resets:
            return

        def mutate(manifest: dict[str, Any]) -> None:
            for item_id, stage in resets.items():
                self._reset_item_from(manifest["items"][item_id], stage)

        self.store.update_manifest(
            batch_id, mutate, changed_item_ids=resets.keys()
        )

    @staticmethod
    def _reset_item_from(item: dict[str, Any], stage: str) -> None:
        index = STAGES.index(stage)
        for downstream in STAGES[index:]:
            checkpoint = item["checkpoints"][downstream]
            if checkpoint["status"] != "skipped":
                checkpoint.update({
                    "status": "pending",
                    "started_at": None,
                    "completed_at": None,
                    "duration_ms": None,
                    "error": None,
                })
        item["status"].update({
            "execution": "pending",
            "validation": "not_run",
            "review": "not_requested",
            "publication": "not_published",
        })
        item["error"] = None
        if stage in ("normalize", "extract"):
            for artifact_name in (
                ("normalized_input", "payload", "diagnostic", "validation")
                if stage == "normalize" else ("payload", "diagnostic", "validation")
            ):
                item["artifacts"][artifact_name]["sha256"] = None

    def _rebuild_missing_validation_projections(
        self, batch_id: str, items: Iterable[BatchItem]
    ) -> None:
        run_dir = self.store.run_dir(batch_id)
        manifest = self.store.read_manifest(batch_id)
        for item in items:
            current = manifest["items"][item.item_id]
            validation_status = current["status"]["validation"]
            target = run_dir / item.validation_path
            if validation_status not in ("passed", "failed"):
                continue
            projection_valid = False
            if target.is_file():
                try:
                    existing = json.loads(target.read_text(encoding="utf-8"))
                    self.store.validate_document(existing, "validation")
                    expected = current["artifacts"]["validation"]["sha256"]
                    projection_valid = bool(expected and sha256_file(target) == expected)
                except (OSError, ValueError, StateStoreError):
                    projection_valid = False
            if projection_valid:
                continue
            errors: list[dict[str, Any]] = []
            warnings: list[dict[str, Any]] = []
            sidecar = run_dir / item.diagnostic_path
            value = self._read_trusted_sidecar(
                sidecar, current["artifacts"]["diagnostic"]["sha256"]
            )
            validation = value.get("validation", {}) if value else {}
            sidecar_errors = list(validation.get("errors", []))
            sidecar_status = value.get("status", {}).get("validation") if value else None
            manifest_error = current.get("error")
            error_matches = bool(
                manifest_error
                and sidecar_errors
                and sidecar_errors[0].get("code") == manifest_error.get("code")
                and sidecar_errors[0].get("message") == manifest_error.get("message")
            )
            if validation_status == "passed" and sidecar_status == "passed":
                errors = sidecar_errors
                warnings = list(validation.get("warnings", []))
            elif validation_status == "failed" and error_matches:
                errors = sidecar_errors
                warnings = list(validation.get("warnings", []))
            elif manifest_error:
                errors = [self._validation_issue_from_error(manifest_error)]
            projection = self._validation_projection(
                batch_id,
                item,
                validation_status,
                errors,
                warnings,
                current=current,
            )
            self.store.write_projection(
                batch_id, "validation", projection, relative_path=item.validation_path
            )
            self._set_validation_artifact_hash(
                batch_id,
                item,
                allow_replace=False,
                expected=current["artifacts"]["validation"]["sha256"],
            )

    def _rebuild_review(self, batch_id: str, items: Iterable[BatchItem]) -> None:
        items = tuple(items)
        manifest = self.store.read_manifest(batch_id)
        target = self.store.run_dir(batch_id) / "review" / "review-queue.json"
        checkpoints_complete = (
            manifest["checkpoints"]["review"]["status"] == "succeeded"
            and all(
                manifest["items"][item.item_id]["checkpoints"]["review"]["status"]
                == "succeeded"
                for item in items
                if item.runnable
            )
        )
        statuses_current = all(
            manifest["items"][item.item_id]["status"]["review"]
            == (
                "pending"
                if manifest["items"][item.item_id]["status"]["execution"] == "succeeded"
                and manifest["items"][item.item_id]["status"]["validation"] == "passed"
                else "not_requested"
            )
            for item in items
            if item.runnable
        )
        stage_needed = not checkpoints_complete or not statuses_current
        if stage_needed:
            self._start_stage(batch_id, "review", [item for item in items if item.runnable])
            completed_at = self._now()

            def mutate(value: dict[str, Any]) -> None:
                for item in items:
                    current = value["items"][item.item_id]
                    if current["status"]["execution"] == "skipped":
                        continue
                    eligible = (
                        current["status"]["execution"] == "succeeded"
                        and current["status"]["validation"] == "passed"
                    )
                    current["status"]["review"] = "pending" if eligible else "not_requested"
                    checkpoint = current["checkpoints"]["review"]
                    self._complete_checkpoint(
                        checkpoint,
                        "succeeded",
                        checkpoint.get("started_at") or completed_at,
                        completed_at,
                        None,
                    )

            self.store.update_manifest(batch_id, mutate)

        self._sync_sidecar_statuses(batch_id, items)
        if stage_needed:
            self._finish_stage(batch_id, "review")
        manifest = self.store.read_manifest(batch_id)
        queue_items = self._review_queue_items(manifest, items)
        generated_at = (
            manifest["checkpoints"]["review"].get("completed_at")
            or manifest["updated_at"]
        )
        projection = {
            "schema_version": "1.0",
            "batch_id": batch_id,
            "generated_at": generated_at,
            "summary": {"pending": len(queue_items)},
            "items": queue_items,
        }
        if target.is_file():
            try:
                existing = json.loads(target.read_text(encoding="utf-8"))
                self.store.validate_document(existing, "review")
                if (
                    existing == projection
                    and self._sidecars_match_manifest(batch_id, items, manifest)
                ):
                    return
            except (OSError, ValueError, StateStoreError):
                pass

        self.store.write_projection(batch_id, "review", projection)

    def _finish_report(
        self, batch_id: str, items: Iterable[BatchItem]
    ) -> PipelineOutcome:
        items = tuple(items)
        manifest = self.store.read_manifest(batch_id)
        summary = self._status_summary(manifest)
        desired_status = self._completed_status(summary)
        target = self.store.run_dir(batch_id) / "batch-report.json"
        checkpoints_complete = (
            manifest["checkpoints"]["report"]["status"] == "succeeded"
            and all(
                manifest["items"][item.item_id]["checkpoints"]["report"]["status"]
                == "succeeded"
                for item in items
                if item.runnable
            )
        )
        stage_needed = not checkpoints_complete or manifest["status"] != desired_status
        if stage_needed:
            self._start_stage(batch_id, "report", [item for item in items if item.runnable])
            completed_at = self._now()

            def mutate(value: dict[str, Any]) -> None:
                for item in items:
                    current = value["items"][item.item_id]
                    if current["status"]["execution"] == "skipped":
                        continue
                    checkpoint = current["checkpoints"]["report"]
                    self._complete_checkpoint(
                        checkpoint,
                        "succeeded",
                        checkpoint.get("started_at") or completed_at,
                        completed_at,
                        None,
                    )
                current_summary = self._status_summary(value)
                value["status"] = self._completed_status(current_summary)
                value["summary"] = current_summary

            self.store.update_manifest(batch_id, mutate)
            self._finish_stage(batch_id, "report")

        manifest = self.store.read_manifest(batch_id)
        summary = self._status_summary(manifest)
        report_items = self._report_items(manifest)
        generated_at = (
            manifest["checkpoints"]["report"].get("completed_at")
            or manifest["updated_at"]
        )
        report = {
            "schema_version": "1.0",
            "batch_id": batch_id,
            "generated_at": generated_at,
            "status": manifest["status"],
            "revision": manifest["revision"],
            "summary": summary,
            "items": report_items,
        }
        if target.is_file():
            try:
                existing = json.loads(target.read_text(encoding="utf-8"))
                self.store.validate_document(existing, "report")
                if existing == report:
                    if stage_needed:
                        self._log_event(batch_id, "report", manifest["status"])
                    return self._outcome_from_manifest(batch_id, manifest)
            except (OSError, ValueError, StateStoreError):
                pass
        self.store.write_projection(batch_id, "report", report)
        if stage_needed:
            self._log_event(batch_id, "report", manifest["status"])
        return self._outcome_from_manifest(batch_id, manifest)

    @staticmethod
    def _completed_status(summary: Mapping[str, int]) -> str:
        failures = (
            summary["execution_failed"]
            + summary["execution_pending"]
            + summary["validation_failed"]
            + summary["validation_not_run"]
        )
        return "completed_with_failures" if failures else "completed"

    @staticmethod
    def _review_queue_items(
        manifest: Mapping[str, Any], items: Iterable[BatchItem]
    ) -> list[dict[str, Any]]:
        queue_items: list[dict[str, Any]] = []
        for item in items:
            current = manifest["items"][item.item_id]
            eligible = (
                current["status"]["execution"] == "succeeded"
                and current["status"]["validation"] == "passed"
            )
            if not eligible:
                continue
            queue_items.append({
                "item_id": item.item_id,
                "product_key": item.product_key,
                "resource_key": item.resource_key,
                "language": item.language,
                "strategy": current["strategy"],
                "status": "pending",
                "payload": dict(current["artifacts"]["payload"]),
                "diagnostic": dict(current["artifacts"]["diagnostic"]),
                "validation": dict(current["artifacts"]["validation"]),
            })
        return queue_items

    @staticmethod
    def _report_items(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "item_id": item_id,
                "product_key": current["product_key"],
                "identity": current["identity"],
                "strategy": current["strategy"],
                "status": current["status"],
                "error": current["error"],
                "artifacts": current["artifacts"],
            }
            for item_id, current in sorted(manifest["items"].items())
        ]

    def _outcome_from_manifest(
        self, batch_id: str, manifest: Mapping[str, Any]
    ) -> PipelineOutcome:
        summary = self._status_summary(manifest)
        return PipelineOutcome(
            batch_id=batch_id,
            status=str(manifest["status"]),
            exit_code=2 if manifest["status"] == "completed_with_failures" else 0,
            summary=summary,
            run_dir=self.store.run_dir(batch_id),
        )

    def _sidecars_match_manifest(
        self,
        batch_id: str,
        items: Iterable[BatchItem],
        manifest: Mapping[str, Any],
    ) -> bool:
        run_dir = self.store.run_dir(batch_id)
        for item in items:
            current = manifest["items"][item.item_id]
            if current["status"]["execution"] != "succeeded":
                continue
            path = run_dir / item.diagnostic_path
            expected_hash = current["artifacts"]["diagnostic"]["sha256"]
            sidecar = self._read_trusted_sidecar(path, expected_hash)
            if sidecar is None:
                return False
            if sidecar.get("status") != current["status"]:
                return False
        return True

    def _sync_sidecar_statuses(
        self, batch_id: str, items: Iterable[BatchItem]
    ) -> None:
        run_dir = self.store.run_dir(batch_id)
        manifest = self.store.read_manifest(batch_id)
        hashes: dict[str, str] = {}
        for item in items:
            current = manifest["items"][item.item_id]
            if current["status"]["execution"] != "succeeded":
                continue
            path = run_dir / item.diagnostic_path
            expected_hash = current["artifacts"]["diagnostic"]["sha256"]
            sidecar = self._read_trusted_sidecar(path, expected_hash)
            # Invalid or hash-mismatched sidecars are evidence for validation
            # and resume. They must never become authority for a new hash.
            if sidecar is None:
                continue
            sidecar_changed = False
            manifest_error = current.get("error")
            if (
                current["status"]["validation"] == "failed"
                and manifest_error
                and manifest_error.get("stage") == "validate"
            ):
                sidecar_errors = sidecar.get("validation", {}).get("errors", [])
                first_error = sidecar_errors[0] if sidecar_errors else None
                if (
                    not first_error
                    or first_error.get("code") != manifest_error.get("code")
                    or first_error.get("message") != manifest_error.get("message")
                ):
                    sidecar["validation"] = {
                        "errors": [self._validation_issue_from_error(manifest_error)],
                        "warnings": [],
                    }
                    sidecar_changed = True
            if sidecar["status"] != current["status"]:
                sidecar["status"] = dict(current["status"])
                sidecar_changed = True
            if sidecar_changed:
                contract = self._contract_validator.validate_sidecar(sidecar)
                if not contract.passed:
                    messages = "; ".join(issue.message for issue in contract.errors)
                    raise PipelineError(
                        f"Diagnostic Sidecar projection is invalid for {item.item_id}: {messages}"
                    )
                self._write_json_atomic(path, sidecar)
            hashes[item.item_id] = sha256_file(path)

        if not hashes or all(
            manifest["items"][item_id]["artifacts"]["diagnostic"]["sha256"] == digest
            for item_id, digest in hashes.items()
        ):
            return

        def mutate(value: dict[str, Any]) -> None:
            for item_id, digest in hashes.items():
                value["items"][item_id]["artifacts"]["diagnostic"]["sha256"] = digest

        self.store.update_manifest(
            batch_id, mutate, changed_item_ids=hashes.keys()
        )

    def _read_trusted_sidecar(
        self, path: Path, expected_hash: str | None
    ) -> dict[str, Any] | None:
        if not expected_hash or not path.is_file() or sha256_file(path) != expected_hash:
            return None
        try:
            sidecar = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(sidecar, dict):
            return None
        contract = self._contract_validator.validate_sidecar(sidecar)
        if not contract.passed:
            return None
        return sidecar

    # ---- validation helpers -----------------------------------------------------

    @staticmethod
    def _validation_issue_from_error(error: Mapping[str, Any]) -> dict[str, str]:
        return {
            "code": str(error.get("code") or "VALIDATION_FAILED"),
            "path": "$",
            "message": str(error.get("message") or "Validation failed"),
        }

    def _write_validation_projection(
        self,
        batch_id: str,
        item: BatchItem,
        result: ResourceProcessingResult,
        *,
        current: Mapping[str, Any],
    ) -> None:
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        if result.extraction_result is not None:
            validation = result.extraction_result.sidecar.get("validation", {})
            errors = list(validation.get("errors", []))
            warnings = list(validation.get("warnings", []))
        elif result.validation == "failed":
            errors = [{
                "code": result.error_code or "VALIDATION_FAILED",
                "path": "$",
                "message": result.error_message or "Validation failed",
            }]
        projection = self._validation_projection(
            batch_id, item, result.validation, errors, warnings, current=current
        )
        self.store.write_projection(
            batch_id, "validation", projection, relative_path=item.validation_path
        )
        self._set_validation_artifact_hash(
            batch_id,
            item,
            allow_replace=True,
            expected=current["artifacts"]["validation"]["sha256"],
        )

    def _validation_projection(
        self,
        batch_id: str,
        item: BatchItem,
        status: str,
        errors: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
        *,
        current: Mapping[str, Any],
    ) -> dict[str, Any]:
        validated_at = current["checkpoints"]["validate"].get("completed_at")
        if not validated_at:
            raise PipelineError(
                f"Validation checkpoint has no completion time for {item.item_id}"
            )
        return {
            "schema_version": "1.0",
            "batch_id": batch_id,
            "item_id": item.item_id,
            "product_key": item.product_key,
            "resource_key": item.resource_key,
            "language": item.language,
            "validated_at": validated_at,
            "status": status,
            "strategy": current["strategy"],
            "payload": dict(current["artifacts"]["payload"]),
            "diagnostic": {"path": current["artifacts"]["diagnostic"]["path"]},
            "errors": errors,
            "warnings": warnings,
        }

    def _set_validation_artifact_hash(
        self,
        batch_id: str,
        item: BatchItem,
        *,
        allow_replace: bool,
        expected: str | None,
    ) -> None:
        path = self.store.run_dir(batch_id) / item.validation_path
        digest = sha256_file(path)
        if expected == digest:
            return
        if expected and not allow_replace:
            raise PipelineError(
                f"Rebuilt validation projection differs from its frozen hash for {item.item_id}"
            )

        def mutate(manifest: dict[str, Any]) -> None:
            manifest["items"][item.item_id]["artifacts"]["validation"]["sha256"] = digest

        self.store.update_manifest(
            batch_id, mutate, changed_item_ids=(item.item_id,)
        )

    def _validate_frozen_extraction_artifacts_from_state(
        self, batch_id: str, item: BatchItem, current: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        run_dir = self.store.run_dir(batch_id)
        for name, relative in (
            ("payload", item.output_path),
            ("diagnostic", item.diagnostic_path),
        ):
            path = run_dir / relative
            expected = current["artifacts"][name]["sha256"]
            if not path.is_file():
                return _error(
                    f"{name.upper()}_MISSING", "validate", f"{name} artifact is missing: {relative}"
                )
            if not expected:
                return _error(
                    f"{name.upper()}_HASH_MISSING", "validate", f"Frozen {name} hash is missing"
                )
            if sha256_file(path) != expected:
                return _error(
                    f"{name.upper()}_HASH_MISMATCH",
                    "validate",
                    f"{name} artifact does not match its frozen extraction hash",
                )
        return None

    # ---- generic helpers --------------------------------------------------------

    @staticmethod
    def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory_descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except Exception:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            raise

    def _resource_info(self, batch_id: str, item: BatchItem) -> ResourceProcessingInfo:
        run_dir = self.store.run_dir(batch_id)
        return ResourceProcessingInfo(
            batch_id=batch_id,
            product_key=item.product_key,
            resource_key=item.resource_key,
            version_key=item.version_key,
            language=item.language,
            html_file_path=str(self.root / item.normalized_path),
            payload_root=str(run_dir / "outputs"),
            diagnostic_root=str(run_dir / "diagnostics"),
            strategy=None,
            defer_validation=True,
            metadata={"batch_item": item},
        )

    def _default_extraction_factory(self, run_dir: Path) -> ExtractionCoordinator:
        return ExtractionCoordinator(
            str(run_dir),
            payload_root=run_dir / "outputs",
            diagnostic_root=run_dir / "diagnostics",
            deferred_validation=True,
        )

    @staticmethod
    def _default_strategy_manager(root: Path) -> StrategyManager:
        return StrategyManager(ProductManager(str(root / "data" / "configs")))

    def _check_preflight_artifacts(self, item: BatchItem) -> None:
        checks = (
            ("Product Definition", self.root / item.config_path, item.config_sha256),
            ("Source Snapshot", self.root / item.source_path if item.source_path else None, item.source_sha256),
            ("Normalized Input", self.root / item.normalized_path, item.normalized_sha256),
        )
        for label, path, expected in checks:
            if path is None or not path.is_file():
                raise FileNotFoundError(f"{label} is missing: {path}")
            if expected is None:
                raise ValueError(f"{label} has no frozen SHA-256")
            if sha256_file(path) != expected:
                raise ValueError(f"{label} SHA-256 differs from input-manifest.json")

    def _capture_run_artifact_hashes(
        self,
        batch_id: str,
        current: dict[str, Any],
        item: BatchItem,
        *,
        include_validation: bool,
    ) -> None:
        run_dir = self.store.run_dir(batch_id)
        pairs = [
            ("payload", item.output_path),
            ("diagnostic", item.diagnostic_path),
        ]
        if include_validation:
            pairs.append(("validation", item.validation_path))
        for name, relative in pairs:
            path = run_dir / relative
            current["artifacts"][name]["sha256"] = sha256_file(path) if path.is_file() else None

    def _batch_stage_complete(self, batch_id: str, stage: str) -> bool:
        return self.store.read_manifest(batch_id)["checkpoints"][stage]["status"] == "succeeded"

    @staticmethod
    def _status_summary(manifest: Mapping[str, Any]) -> dict[str, int]:
        return summarize_batch_manifest(manifest)

    def _mark_batch_failed(self, batch_id: str, exc: Exception) -> None:
        try:
            self.store.update_manifest(
                batch_id,
                lambda manifest: manifest.update({"status": "failed"}),
                changed_item_ids=(),
            )
            self._log_event(
                batch_id,
                "report",
                "failed",
                error_code="PIPELINE_FATAL",
                message=str(exc),
            )
        except Exception:
            # Preserve the original fatal error if state itself is unreadable.
            pass

    def _log_item_event(
        self,
        batch_id: str,
        item: BatchItem,
        stage: str,
        status: str,
        strategy: str,
        error: Mapping[str, Any] | None,
    ) -> None:
        self._log_event(
            batch_id,
            stage,
            status,
            item_id=item.item_id,
            product_key=item.product_key,
            resource_key=item.resource_key,
            language=item.language,
            strategy=strategy or item.strategy,
            error_code=error.get("code") if error else None,
        )

    def _log_event(
        self,
        batch_id: str,
        stage: str,
        status: str,
        *,
        item_id: str | None = None,
        product_key: str | None = None,
        resource_key: str | None = None,
        language: str | None = None,
        strategy: str | None = None,
        error_code: str | None = None,
        **details: Any,
    ) -> None:
        path = self.store.run_dir(batch_id) / "logs" / "pipeline.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": self._now(),
            "batch_id": batch_id,
            "item_id": item_id,
            "product_key": product_key,
            "resource_key": resource_key,
            "language": language,
            "stage": stage,
            "strategy": strategy,
            "status": status,
            "error_code": error_code,
            **details,
        }
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _validate_parallel_jobs(value: int) -> None:
        if value < 1 or value > 8:
            raise PipelineError("parallel_jobs must be between 1 and 8")


__all__ = ["PipelineCoordinator", "PipelineError", "PipelineOutcome"]
