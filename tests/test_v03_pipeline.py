from __future__ import annotations

import argparse
import io
import json
import shutil
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cli
from src.batch.process_engine import BatchProcessEngine
from src.core.data_models import ExtractionStrategy, StrategyType
from src.core.extraction_result import ExtractionResult
from src.core.product_catalog import sha256_file
from src.pipeline.cli_commands import (
    pipeline_run_command,
    pipeline_status_command,
)
from src.pipeline.coordinator import PipelineCoordinator, PipelineError, PipelineOutcome
from src.pipeline.models import BatchItem, PipelinePlan
from src.pipeline.provenance import ProvenanceError
from src.pipeline.state_store import ImmutableManifestError, StateStore


ROOT = Path(__file__).resolve().parents[1]
FIXED_BATCH_ID = "20260721T200000Z-cafebabe"
FIXED_TIME = "2026-07-21T20:00:00Z"


class _Clock:
    def __init__(self) -> None:
        self.current = datetime(2026, 7, 21, 20, 0, tzinfo=timezone.utc)

    def __call__(self) -> str:
        value = self.current.isoformat().replace("+00:00", "Z")
        self.current += timedelta(seconds=1)
        return value


def _provenance() -> dict[str, object]:
    empty_hash = "0" * 64
    return {
        "schema_version": "1.0",
        "captured_at": FIXED_TIME,
        "git_commit": "a" * 40,
        "dirty": False,
        "reproducible": True,
        "worktree_changes": [],
        "worktree_fingerprint": f"sha256:{empty_hash}",
        "immutable_fingerprint": f"sha256:{empty_hash}",
        "immutable_files": {},
    }


class _Planner:
    def __init__(self, plan: PipelinePlan) -> None:
        self.value = plan
        self.calls: list[tuple[str, str | None, str]] = []

    def plan(
        self,
        scope: str = "all",
        *,
        group: str | None = None,
        language: str = "both",
    ) -> PipelinePlan:
        self.calls.append((scope, group, language))
        if scope == "group" and group != "fixture":
            raise ValueError(f"Unknown pipeline group: {group}")
        return self.value


class _Provenance:
    def __init__(self) -> None:
        self.capture_calls: list[bool] = []
        self.verify_calls = 0
        self.verify_error: Exception | None = None

    def capture(self, *, allow_dirty: bool = False) -> dict[str, object]:
        self.capture_calls.append(allow_dirty)
        return _provenance()

    def verify(self, frozen: object) -> None:
        self.verify_calls += 1
        if self.verify_error is not None:
            raise self.verify_error


class _Copier:
    def __init__(self, root: Path, items: tuple[BatchItem, ...]) -> None:
        self.root = root
        self.items = {
            (item.product_key, item.language, item.version_key): item for item in items
        }
        self.calls: Counter[str] = Counter()

    def copy_resource(
        self,
        product_key: str,
        language: str,
        version_key: str | None = None,
    ) -> dict[str, object]:
        item = self.items[(product_key, language, version_key)]
        self.calls[item.resource_key] += 1
        source = self.root / str(item.source_path)
        destination = self.root / item.normalized_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        return {
            "status": "copied",
            "product_key": product_key,
            "resource_key": item.resource_key,
            "language": language,
        }


class _StrategyManager:
    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()

    def determine_extraction_strategy(
        self, html_file_path: str, product_key: str
    ) -> ExtractionStrategy:
        self.calls[product_key] += 1
        return ExtractionStrategy(
            strategy_type=StrategyType.SIMPLE_STATIC,
            processor="FixtureProcessor",
            description="pipeline fixture",
        )


class _Extractor:
    def __init__(self, run_dir: Path, items: tuple[BatchItem, ...]) -> None:
        self.run_dir = run_dir
        self.items = {
            (item.product_key, item.language, item.version_key): item for item in items
        }
        self.extract_calls: Counter[str] = Counter()
        self.validation_calls: Counter[str] = Counter()
        self.extract_failures_remaining: Counter[str] = Counter()
        self.validation_failures: set[str] = set()
        self.validation_exceptions: set[str] = set()

    def coordinate_extraction(
        self,
        product_key: str,
        language: str,
        html_file_path: str,
        version_key: str | None = None,
        **options: object,
    ) -> ExtractionResult:
        item = self.items[(product_key, language, version_key)]
        self.extract_calls[item.resource_key] += 1
        if self.extract_failures_remaining[item.resource_key] > 0:
            self.extract_failures_remaining[item.resource_key] -= 1
            raise RuntimeError(f"fixture extraction failed for {item.resource_key}")

        payload = {
            "title": item.resource_key,
            "slug": item.slug,
            "language": item.language,
        }
        sidecar = self._sidecar(item, validation="not_run")
        payload_path = self.run_dir / item.output_path
        sidecar_path = self.run_dir / item.diagnostic_path
        self._write_json(payload_path, payload)
        self._write_json(sidecar_path, sidecar)
        return ExtractionResult(
            product_key=item.product_key,
            language=item.language,
            payload=payload,
            sidecar=sidecar,
            payload_path=payload_path,
            sidecar_path=sidecar_path,
        )

    def validate_persisted_payload(
        self,
        product_key: str,
        language: str,
        *,
        payload_path: Path,
        sidecar_path: Path,
        html_file_path: str | Path,
        version_key: str | None = None,
    ) -> ExtractionResult:
        item = self.items[(product_key, language, version_key)]
        self.validation_calls[item.resource_key] += 1
        if item.resource_key in self.validation_exceptions:
            raise RuntimeError(f"fixture validator crashed for {item.resource_key}")
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        failed = item.resource_key in self.validation_failures
        sidecar = self._sidecar(item, validation="failed" if failed else "passed")
        if failed:
            sidecar["validation"]["errors"] = [
                {
                    "code": "FIXTURE_VALIDATION_FAILED",
                    "path": "$",
                    "message": f"fixture validation failed for {item.resource_key}",
                }
            ]
        self._write_json(sidecar_path, sidecar)
        return ExtractionResult(
            product_key=item.product_key,
            language=item.language,
            payload=payload,
            sidecar=sidecar,
            payload_path=payload_path,
            sidecar_path=sidecar_path,
        )

    @staticmethod
    def _sidecar(item: BatchItem, *, validation: str) -> dict[str, object]:
        return {
            "schema_version": "1.1",
            "product_key": item.product_key,
            "resource": {
                "kind": item.resource_kind,
                "resource_key": item.resource_key,
                "slug": item.slug,
                "version_key": item.version_key,
                "version_label": item.version_label,
            },
            "language": item.language,
            "page_model": item.page_model,
            "contract": {
                "name": item.page_model,
                "version": "1.1",
                "schema_sha256": "0" * 64,
            },
            "source": {"path": item.source_path, "sha256": item.source_sha256},
            "normalized_input": {
                "path": item.normalized_path,
                "sha256": item.normalized_sha256,
            },
            "payload": {"path": item.output_path, "sha256": None},
            "strategy": {"type": "simple_static", "processor": "FixtureProcessor"},
            "status": {
                "execution": "succeeded",
                "validation": validation,
                "review": "not_requested",
                "publication": "not_published",
            },
            "validation": {"errors": [], "warnings": []},
            "timing": {
                "started_at": FIXED_TIME,
                "completed_at": FIXED_TIME,
                "duration_ms": 1,
            },
            "error": None,
        }

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


class _Harness:
    def __init__(self, root: Path, products: tuple[str, ...] = ("alpha", "beta")) -> None:
        self.root = root
        shutil.copytree(ROOT / "schemas", root / "schemas")
        self.items = tuple(self._make_item(product) for product in products)
        self.plan = PipelinePlan(
            scope={"kind": "all"}, languages=("zh-cn",), items=self.items
        )
        self.planner = _Planner(self.plan)
        self.provenance = _Provenance()
        self.copier = _Copier(root, self.items)
        self.strategy_manager = _StrategyManager()
        self.extractor: _Extractor | None = None
        self.store = StateStore(root)
        self.clock = _Clock()
        self.coordinator = PipelineCoordinator(
            root,
            planner=self.planner,
            state_store=self.store,
            provenance=self.provenance,
            copier_factory=lambda unused_root: self.copier,
            extraction_factory=self._extractor_factory,
            engine_factory=lambda workers: BatchProcessEngine(
                max_workers=workers, persist_records=False
            ),
            strategy_manager_factory=lambda unused_root: self.strategy_manager,
            batch_id_factory=lambda: FIXED_BATCH_ID,
            now=self.clock,
        )

    def _make_item(self, product_key: str) -> BatchItem:
        config_path = Path("data/configs/products/pricing") / f"{product_key}.json"
        source_path = (
            Path("data/current_prod_html/zh-cn/pricing/details")
            / product_key
            / "index.html"
        )
        config = self.root / config_path
        source = self.root / source_path
        config.parent.mkdir(parents=True, exist_ok=True)
        source.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(
            json.dumps({"product_key": product_key}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        source.write_text(
            f"<html><body>{product_key}</body></html>\n", encoding="utf-8"
        )
        source_hash = sha256_file(source)
        return BatchItem(
            language="zh-cn",
            resource_key=product_key,
            product_key=product_key,
            resource_kind="current",
            page_model="FlexibleContentPage",
            capability_status="supported",
            config_path=config_path.as_posix(),
            config_sha256=sha256_file(config),
            source_availability="available",
            source_path=source_path.as_posix(),
            source_sha256=source_hash,
            normalized_path=f"data/prod-html/zh-cn/pricing/{product_key}.html",
            normalized_sha256=source_hash,
            output_path=f"outputs/zh-cn/pricing/{product_key}.json",
            diagnostic_path=(
                f"diagnostics/zh-cn/pricing/{product_key}.sidecar.json"
            ),
            validation_path=(
                f"validation/zh-cn/pricing/{product_key}.validation.json"
            ),
            slug=product_key,
            strategy="simple_static",
            catalog_categories=("fixture",),
            source_url=f"https://example.invalid/{product_key}",
        )

    def _extractor_factory(self, run_dir: Path) -> _Extractor:
        if self.extractor is None:
            self.extractor = _Extractor(run_dir, self.items)
        return self.extractor

    def run(self) -> PipelineOutcome:
        return self.coordinator.run(
            all_products=True,
            language="zh-cn",
            parallel_jobs=2,
            allow_dirty=False,
        )


class PipelineCoordinatorTests(unittest.TestCase):
    def test_successful_run_returns_zero_and_writes_all_authoritative_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = _Harness(Path(directory))
            outcome = harness.run()

            self.assertEqual(outcome.exit_code, 0)
            self.assertEqual(outcome.status, "completed")
            self.assertEqual(outcome.summary["execution_succeeded"], 2)
            self.assertEqual(outcome.summary["validation_passed"], 2)
            self.assertEqual(outcome.summary["review_pending"], 2)
            manifest = harness.store.read_manifest(FIXED_BATCH_ID)
            for item in harness.items:
                state = manifest["items"][item.item_id]
                self.assertEqual(
                    state["status"],
                    {
                        "execution": "succeeded",
                        "validation": "passed",
                        "review": "pending",
                        "publication": "not_published",
                    },
                )
                for relative in (
                    item.output_path,
                    item.diagnostic_path,
                    item.validation_path,
                ):
                    self.assertTrue((outcome.run_dir / relative).is_file(), relative)
                sidecar = json.loads(
                    (outcome.run_dir / item.diagnostic_path).read_text(encoding="utf-8")
                )
                self.assertEqual(sidecar["status"], state["status"])
                self.assertEqual(
                    sha256_file(outcome.run_dir / item.diagnostic_path),
                    state["artifacts"]["diagnostic"]["sha256"],
                )
                validation = json.loads(
                    (outcome.run_dir / item.validation_path).read_text(encoding="utf-8")
                )
                self.assertEqual(
                    validation["diagnostic"], {"path": item.diagnostic_path}
                )
            self.assertTrue((outcome.run_dir / "review/review-queue.json").is_file())
            self.assertTrue((outcome.run_dir / "batch-report.json").is_file())

            events = [
                json.loads(line)
                for line in (outcome.run_dir / "logs/pipeline.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            required = {
                "batch_id",
                "item_id",
                "product_key",
                "language",
                "stage",
                "strategy",
                "status",
                "error_code",
            }
            self.assertTrue(events)
            self.assertTrue(all(required <= event.keys() for event in events))

    def test_one_future_failure_is_isolated_and_returns_two(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = _Harness(Path(directory))
            extractor = harness._extractor_factory(
                harness.store.run_dir(FIXED_BATCH_ID)
            )
            extractor.extract_failures_remaining["beta"] = 1

            outcome = harness.run()

            self.assertEqual(outcome.exit_code, 2)
            self.assertEqual(outcome.status, "completed_with_failures")
            manifest = harness.store.read_manifest(FIXED_BATCH_ID)
            self.assertEqual(
                manifest["items"]["zh-cn/alpha"]["status"]["validation"], "passed"
            )
            beta = manifest["items"]["zh-cn/beta"]
            self.assertEqual(beta["status"]["execution"], "failed")
            self.assertEqual(beta["status"]["validation"], "not_run")
            self.assertEqual(beta["error"]["code"], "EXTRACTION_FAILED")
            self.assertEqual(extractor.extract_calls, Counter({"alpha": 1, "beta": 1}))

    def test_resume_appends_failed_attempt_and_does_not_rerun_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = _Harness(Path(directory))
            extractor = harness._extractor_factory(
                harness.store.run_dir(FIXED_BATCH_ID)
            )
            extractor.extract_failures_remaining["beta"] = 1
            first = harness.run()
            self.assertEqual(first.exit_code, 2)

            resumed = harness.coordinator.resume(FIXED_BATCH_ID, parallel_jobs=2)

            self.assertEqual(resumed.exit_code, 0)
            self.assertEqual(extractor.extract_calls, Counter({"beta": 2, "alpha": 1}))
            self.assertEqual(extractor.validation_calls, Counter({"alpha": 1, "beta": 1}))
            manifest = harness.store.read_manifest(FIXED_BATCH_ID)
            alpha_attempts = manifest["items"]["zh-cn/alpha"]["checkpoints"]["extract"]["attempts"]
            beta_attempts = manifest["items"]["zh-cn/beta"]["checkpoints"]["extract"]["attempts"]
            self.assertEqual(len(alpha_attempts), 1)
            self.assertEqual([attempt["status"] for attempt in beta_attempts], ["failed", "succeeded"])

    def test_resume_completes_discovery_after_creation_is_interrupted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = _Harness(Path(directory))
            with patch.object(
                harness.coordinator,
                "_complete_discovery",
                side_effect=KeyboardInterrupt(),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    harness.run()

            status = harness.coordinator.status(FIXED_BATCH_ID)
            self.assertEqual(status["stored_status"], "created")
            self.assertEqual(status["status"], "interrupted")
            self.assertTrue(status["resumable"])
            with self.assertRaises(PipelineError):
                harness.coordinator.validate(FIXED_BATCH_ID)

            resumed = harness.coordinator.resume(FIXED_BATCH_ID, parallel_jobs=2)

            self.assertEqual(resumed.exit_code, 0)
            manifest = harness.store.read_manifest(FIXED_BATCH_ID)
            self.assertEqual(
                manifest["checkpoints"]["discovery"]["status"], "succeeded"
            )
            self.assertTrue(
                all(
                    item["checkpoints"]["discovery"]["status"] == "succeeded"
                    for item in manifest["items"].values()
                )
            )

    def test_resume_finishes_an_interrupted_explicit_validation_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = _Harness(Path(directory))
            harness.run()
            extractor = harness.extractor
            assert extractor is not None
            initial_calls = extractor.validation_calls.copy()

            class _InterruptingEngine:
                @staticmethod
                def process_resource_items(*args: object, **kwargs: object) -> None:
                    raise KeyboardInterrupt()

            original_factory = harness.coordinator._engine_factory
            harness.coordinator._engine_factory = lambda workers: _InterruptingEngine()
            try:
                with self.assertRaises(KeyboardInterrupt):
                    harness.coordinator.validate(FIXED_BATCH_ID, parallel_jobs=2)
            finally:
                harness.coordinator._engine_factory = original_factory

            interrupted = harness.store.read_manifest(FIXED_BATCH_ID)
            self.assertTrue(
                all(
                    item["status"]["validation"] == "not_run"
                    and item["checkpoints"]["validate"]["status"] == "running"
                    and item["artifacts"]["validation"]["sha256"] is None
                    for item in interrupted["items"].values()
                )
            )

            resumed = harness.coordinator.resume(FIXED_BATCH_ID, parallel_jobs=2)

            self.assertEqual(resumed.exit_code, 0)
            self.assertEqual(
                extractor.validation_calls,
                Counter({key: value + 1 for key, value in initial_calls.items()}),
            )
            finished = harness.store.read_manifest(FIXED_BATCH_ID)
            for item in finished["items"].values():
                self.assertEqual(item["status"]["validation"], "passed")
                self.assertEqual(
                    [attempt["status"] for attempt in item["checkpoints"]["validate"]["attempts"]],
                    ["succeeded", "failed", "succeeded"],
                )

    def test_resume_does_not_retry_a_completed_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = _Harness(Path(directory))
            extractor = harness._extractor_factory(
                harness.store.run_dir(FIXED_BATCH_ID)
            )
            extractor.validation_failures.add("beta")
            first = harness.run()
            self.assertEqual(first.exit_code, 2)
            before = harness.store.read_manifest(FIXED_BATCH_ID)
            attempts_before = list(
                before["items"]["zh-cn/beta"]["checkpoints"]["validate"]["attempts"]
            )

            resumed = harness.coordinator.resume(FIXED_BATCH_ID, parallel_jobs=2)

            self.assertEqual(resumed.exit_code, 2)
            self.assertEqual(extractor.extract_calls["beta"], 1)
            self.assertEqual(extractor.validation_calls["beta"], 1)
            after = harness.store.read_manifest(FIXED_BATCH_ID)
            self.assertEqual(
                after["items"]["zh-cn/beta"]["checkpoints"]["validate"]["attempts"],
                attempts_before,
            )

    def test_resume_deterministically_rebuilds_validator_exception_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = _Harness(Path(directory))
            extractor = harness._extractor_factory(
                harness.store.run_dir(FIXED_BATCH_ID)
            )
            extractor.validation_exceptions.add("beta")
            outcome = harness.run()
            self.assertEqual(outcome.exit_code, 2)
            manifest_path = outcome.run_dir / "batch-manifest.json"
            manifest_before = manifest_path.read_bytes()
            before = harness.store.read_manifest(FIXED_BATCH_ID)
            beta = next(item for item in harness.items if item.resource_key == "beta")
            expected_hash = before["items"][beta.item_id]["artifacts"]["validation"]["sha256"]
            validation_path = outcome.run_dir / beta.validation_path
            validation_path.unlink()
            calls_before = extractor.validation_calls.copy()

            resumed = harness.coordinator.resume(FIXED_BATCH_ID, parallel_jobs=2)

            self.assertEqual(resumed.exit_code, 2)
            self.assertEqual(extractor.validation_calls, calls_before)
            self.assertEqual(sha256_file(validation_path), expected_hash)
            self.assertEqual(manifest_path.read_bytes(), manifest_before)

    def test_explicit_validate_only_revalidates_existing_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = _Harness(Path(directory))
            harness.run()
            extractor = harness.extractor
            assert extractor is not None
            copies = harness.copier.calls.copy()
            preflights = harness.strategy_manager.calls.copy()
            extractions = extractor.extract_calls.copy()
            validations = extractor.validation_calls.copy()

            outcome = harness.coordinator.validate(FIXED_BATCH_ID, parallel_jobs=2)

            self.assertEqual(outcome.exit_code, 0)
            self.assertEqual(harness.copier.calls, copies)
            self.assertEqual(harness.strategy_manager.calls, preflights)
            self.assertEqual(extractor.extract_calls, extractions)
            self.assertEqual(
                extractor.validation_calls,
                Counter({key: value + 1 for key, value in validations.items()}),
            )

    def test_tampered_payload_fails_revalidation_without_replacing_frozen_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = _Harness(Path(directory))
            outcome = harness.run()
            before = harness.store.read_manifest(FIXED_BATCH_ID)
            expected = before["items"]["zh-cn/alpha"]["artifacts"]["payload"]["sha256"]
            item = harness.items[0]
            payload = outcome.run_dir / item.output_path
            payload.write_text('{"tampered": true}\n', encoding="utf-8")
            extractor = harness.extractor
            assert extractor is not None
            validation_calls = extractor.validation_calls["alpha"]

            validated = harness.coordinator.validate(FIXED_BATCH_ID, parallel_jobs=2)

            self.assertEqual(validated.exit_code, 2)
            after = harness.store.read_manifest(FIXED_BATCH_ID)
            alpha = after["items"]["zh-cn/alpha"]
            self.assertEqual(alpha["artifacts"]["payload"]["sha256"], expected)
            self.assertEqual(alpha["status"]["validation"], "failed")
            self.assertEqual(alpha["status"]["review"], "not_requested")
            self.assertEqual(alpha["error"]["code"], "PAYLOAD_HASH_MISMATCH")
            self.assertEqual(extractor.validation_calls["alpha"], validation_calls)

    def test_tampered_sidecar_fails_revalidation_without_advancing_frozen_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = _Harness(Path(directory))
            outcome = harness.run()
            item = harness.items[0]
            before = harness.store.read_manifest(FIXED_BATCH_ID)
            expected = before["items"][item.item_id]["artifacts"]["diagnostic"]["sha256"]
            sidecar_path = outcome.run_dir / item.diagnostic_path
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            sidecar["status"]["review"] = "rejected"
            _Extractor._write_json(sidecar_path, sidecar)
            observed = sha256_file(sidecar_path)
            self.assertNotEqual(observed, expected)

            validated = harness.coordinator.validate(FIXED_BATCH_ID, parallel_jobs=2)

            self.assertEqual(validated.exit_code, 2)
            after = harness.store.read_manifest(FIXED_BATCH_ID)
            alpha = after["items"][item.item_id]
            self.assertEqual(alpha["artifacts"]["diagnostic"]["sha256"], expected)
            self.assertEqual(sha256_file(sidecar_path), observed)
            self.assertEqual(alpha["status"]["validation"], "failed")
            self.assertEqual(alpha["status"]["review"], "not_requested")
            self.assertEqual(alpha["error"]["code"], "DIAGNOSTIC_HASH_MISMATCH")

    def test_completed_resume_is_a_byte_stable_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = _Harness(Path(directory))
            outcome = harness.run()
            manifest_path = outcome.run_dir / "batch-manifest.json"
            review_path = outcome.run_dir / "review/review-queue.json"
            report_path = outcome.run_dir / "batch-report.json"
            log_path = outcome.run_dir / "logs/pipeline.jsonl"
            before = {
                path: path.read_bytes()
                for path in (manifest_path, review_path, report_path, log_path)
            }
            extractor = harness.extractor
            assert extractor is not None
            calls = (
                harness.copier.calls.copy(),
                harness.strategy_manager.calls.copy(),
                extractor.extract_calls.copy(),
                extractor.validation_calls.copy(),
            )

            resumed = harness.coordinator.resume(FIXED_BATCH_ID, parallel_jobs=2)

            self.assertEqual(resumed.exit_code, 0)
            self.assertEqual(
                before,
                {
                    path: path.read_bytes()
                    for path in (manifest_path, review_path, report_path, log_path)
                },
            )
            self.assertEqual(
                calls,
                (
                    harness.copier.calls,
                    harness.strategy_manager.calls,
                    extractor.extract_calls,
                    extractor.validation_calls,
                ),
            )

    def test_resume_rebuilds_missing_projections_without_rerunning_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = _Harness(Path(directory))
            outcome = harness.run()
            extractor = harness.extractor
            assert extractor is not None
            calls = (
                harness.copier.calls.copy(),
                harness.strategy_manager.calls.copy(),
                extractor.extract_calls.copy(),
                extractor.validation_calls.copy(),
            )
            manifest_before = (outcome.run_dir / "batch-manifest.json").read_bytes()
            expected_validation_hash = harness.store.read_manifest(FIXED_BATCH_ID)[
                "items"
            ][harness.items[0].item_id]["artifacts"]["validation"]["sha256"]
            validation = outcome.run_dir / harness.items[0].validation_path
            review = outcome.run_dir / "review/review-queue.json"
            report = outcome.run_dir / "batch-report.json"
            validation.unlink()
            review.unlink()
            report.unlink()

            resumed = harness.coordinator.resume(FIXED_BATCH_ID, parallel_jobs=2)

            self.assertEqual(resumed.exit_code, 0)
            self.assertTrue(validation.is_file())
            self.assertTrue(review.is_file())
            self.assertTrue(report.is_file())
            self.assertEqual(
                (outcome.run_dir / "batch-manifest.json").read_bytes(), manifest_before
            )
            self.assertEqual(sha256_file(validation), expected_validation_hash)
            self.assertEqual(
                calls,
                (
                    harness.copier.calls,
                    harness.strategy_manager.calls,
                    extractor.extract_calls,
                    extractor.validation_calls,
                ),
            )

    def test_resume_replaces_corrupt_review_and_report_projections_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = _Harness(Path(directory))
            outcome = harness.run()
            manifest_path = outcome.run_dir / "batch-manifest.json"
            manifest_before = manifest_path.read_bytes()
            review_path = outcome.run_dir / "review/review-queue.json"
            report_path = outcome.run_dir / "batch-report.json"
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review["batch_id"] = "different-batch"
            review["summary"] = {"pending": 999}
            _Extractor._write_json(review_path, review)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["batch_id"] = "different-batch"
            _Extractor._write_json(report_path, report)

            resumed = harness.coordinator.resume(FIXED_BATCH_ID, parallel_jobs=2)

            self.assertEqual(resumed.exit_code, 0)
            rebuilt_review = json.loads(review_path.read_text(encoding="utf-8"))
            rebuilt_report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(rebuilt_review["batch_id"], FIXED_BATCH_ID)
            self.assertEqual(rebuilt_review["summary"], {"pending": 2})
            self.assertEqual(rebuilt_report["batch_id"], FIXED_BATCH_ID)
            self.assertEqual(manifest_path.read_bytes(), manifest_before)

    def test_resume_rejects_provenance_and_input_manifest_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = _Harness(Path(directory))
            harness.run()
            revision = harness.store.read_manifest(FIXED_BATCH_ID)["revision"]
            harness.provenance.verify_error = ProvenanceError("fixture commit drift")

            with self.assertRaises(ProvenanceError):
                harness.coordinator.resume(FIXED_BATCH_ID)
            self.assertEqual(
                harness.store.read_manifest(FIXED_BATCH_ID)["revision"], revision
            )

        with tempfile.TemporaryDirectory() as directory:
            harness = _Harness(Path(directory))
            outcome = harness.run()
            frozen_path = outcome.run_dir / "input-manifest.json"
            frozen_path.write_text(
                frozen_path.read_text(encoding="utf-8") + "\n", encoding="utf-8"
            )
            with self.assertRaises(ImmutableManifestError):
                harness.coordinator.resume(FIXED_BATCH_ID)


class PipelineCliTests(unittest.TestCase):
    @staticmethod
    def _run_args() -> argparse.Namespace:
        return argparse.Namespace(
            all_products=True,
            group=None,
            language="both",
            parallel_jobs=4,
            runs_dir="runs",
            allow_dirty=False,
        )

    @staticmethod
    def _pipeline_outcome(exit_code: int) -> PipelineOutcome:
        summary = {
            "total": 2,
            "runnable": 2,
            "skipped": 0,
            "execution_succeeded": 2 if exit_code == 0 else 1,
            "execution_failed": 0 if exit_code == 0 else 1,
            "execution_pending": 0,
            "validation_passed": 2 if exit_code == 0 else 1,
            "validation_failed": 0,
            "validation_not_run": 0 if exit_code == 0 else 1,
            "review_pending": 2 if exit_code == 0 else 1,
            "not_published": 2,
        }
        return PipelineOutcome(
            batch_id=FIXED_BATCH_ID,
            status="completed" if exit_code == 0 else "completed_with_failures",
            exit_code=exit_code,
            summary=summary,
            run_dir=Path("runs") / FIXED_BATCH_ID,
        )

    def test_parser_exposes_pipeline_commands_and_removes_legacy_batch_commands(self) -> None:
        parser = cli.create_parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        legacy = {
            "batch-process",
            "batch-status",
            "batch-retry",
            "batch-history",
            "batch-cleanup",
        }
        self.assertTrue(
            {
                "pipeline-run",
                "pipeline-status",
                "pipeline-resume",
                "pipeline-validate",
            }
            <= set(subparsers.choices)
        )
        self.assertTrue(legacy.isdisjoint(subparsers.choices))
        self.assertTrue(all(command not in parser.format_help() for command in legacy))
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                parser.parse_args(["batch-process"])
        self.assertEqual(stopped.exception.code, 1)

    def test_run_command_maps_success_partial_fatal_and_interrupt_exit_codes(self) -> None:
        scenarios = (
            (Mock(run=Mock(return_value=self._pipeline_outcome(0))), 0),
            (Mock(run=Mock(return_value=self._pipeline_outcome(2))), 2),
            (Mock(run=Mock(side_effect=RuntimeError("fatal"))), 1),
            (Mock(run=Mock(side_effect=KeyboardInterrupt())), 130),
        )
        for coordinator, expected in scenarios:
            with self.subTest(exit_code=expected):
                with patch(
                    "src.pipeline.cli_commands._coordinator", return_value=coordinator
                ), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    self.assertEqual(pipeline_run_command(self._run_args()), expected)

    def test_unknown_group_and_batch_are_fatal_cli_errors(self) -> None:
        unknown_group = Mock(run=Mock(side_effect=ValueError("unknown group")))
        with patch(
            "src.pipeline.cli_commands._coordinator", return_value=unknown_group
        ), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(pipeline_run_command(self._run_args()), 1)

        args = SimpleNamespace(
            batch_id="20260721T200000Z-deadbeef", runs_dir="runs", json=False
        )
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(pipeline_status_command(args), 1)


if __name__ == "__main__":
    unittest.main()
