from __future__ import annotations

import copy
import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.batch.process_engine import (
    BatchProcessEngine,
    ResourceProcessingInfo,
    ResourceProcessingResult,
)
from src.core.product_catalog import ProductDefinitionRecord
from src.pipeline.models import InputManifest
from src.pipeline.planner import PipelinePlanner
from src.pipeline.state_store import (
    ImmutableManifestError,
    ManifestConflictError,
    ManifestValidationError,
    RepositoryLock,
    RepositoryLockError,
    StateStore,
    generate_batch_id,
)


ROOT = Path(__file__).resolve().parents[1]
FIXED_BATCH_ID = "20260721T193456Z-deadbeef"
FIXED_TIMESTAMP = "2026-07-21T19:34:56Z"
SHA256_ZERO = "0" * 64


class _MiniCatalog:
    """ProductCatalog-compatible stub backed by files in a temporary root."""

    def __init__(self, records: dict[str, ProductDefinitionRecord]) -> None:
        self._records = records

    def load_definitions(self) -> dict[str, ProductDefinitionRecord]:
        return copy.deepcopy(self._records)

    def build_index(self) -> dict[str, Any]:
        return {
            "products": {key: {} for key in sorted(self._records)},
            "catalog_categories": {
                "integration": {"products": ["event-grid"]},
                "networking": {"products": ["frontdoor"]},
                "websites": {"products": ["frontdoor"]},
            },
            "support_article_types": {
                "SLA": {"products": ["sla-cdn"]},
            },
        }


def _available(snapshot_path: str, url: str, *, cms_path: str | None = None) -> dict[str, str]:
    source = {
        "availability": "available",
        "snapshot_path": snapshot_path,
        "url": url,
    }
    if cms_path is not None:
        source["cms_path"] = cms_path
    return source


def _mini_definitions() -> dict[str, tuple[str, dict[str, Any]]]:
    frontdoor = {
        "schema_version": "1.0",
        "product_key": "frontdoor",
        "display_name": "Azure Front Door",
        "slug": "frontdoor",
        "page_model": "FlexibleContentPage",
        "capability_status": "supported",
        "catalog_categories": ["networking", "websites"],
        "sources": {
            "zh-cn": _available(
                "pricing/details/frontdoor/index.html",
                "https://www.azure.cn/pricing/details/frontdoor/",
            ),
            "en-us": _available(
                "pricing/details/frontdoor/index.html",
                "https://www.azure.cn/en-us/pricing/details/frontdoor/",
            ),
        },
        "extraction": {"strategy": "complex"},
    }
    event_grid = {
        "schema_version": "1.0",
        "product_key": "event-grid",
        "display_name": "Event Grid",
        "slug": "event-grid",
        "page_model": "FlexibleContentPage",
        "capability_status": "known_unsupported",
        "unsupported_reason": "fixture is intentionally unsupported",
        "catalog_categories": ["integration"],
        "sources": {
            "zh-cn": _available(
                "pricing/details/event-grid/index.html",
                "https://www.azure.cn/pricing/details/event-grid/",
            ),
            "en-us": _available(
                "pricing/details/event-grid/index.html",
                "https://www.azure.cn/en-us/pricing/details/event-grid/",
            ),
        },
        "extraction": {"strategy": "simple_static"},
    }
    sla_cdn = {
        "schema_version": "1.0",
        "product_key": "sla-cdn",
        "display_name": "CDN SLA",
        "slug": "cdn",
        "page_model": "SupportArticlePage",
        "capability_status": "supported",
        "support_article_type": "SLA",
        "sources": {
            "zh-cn": _available(
                "SupportArticles/SLA/cdn/index.html",
                "https://www.azure.cn/support/sla/cdn/",
                cms_path="/support/sla/cdn/",
            ),
            "en-us": _available(
                "SupportArticles/SLA/cdn/index.html",
                "https://www.azure.cn/en-us/support/sla/cdn/",
                cms_path="/en-us/support/sla/cdn/",
            ),
        },
        "historical_versions": [
            {
                "version_key": "v1-1",
                "version_label": "1.1",
                "slug": "cdn-v1-1",
                "sources": {
                    "zh-cn": _available(
                        "SupportArticles/SLA/cdn-v1_1/index.html",
                        "https://www.azure.cn/support/sla/cdn-v1_1/",
                        cms_path="/support/sla/cdn-v1-1/",
                    ),
                    "en-us": {
                        "availability": "unavailable",
                        "unavailable_reason": "English 1.1 has no independent historical snapshot",
                    },
                },
            },
            {
                "version_key": "v1-0",
                "version_label": "1.0",
                "slug": "cdn-v1",
                "sources": {
                    "zh-cn": _available(
                        "SupportArticles/SLA/cdn-v1/index.html",
                        "https://www.azure.cn/support/sla/cdn-v1/",
                        cms_path="/support/sla/cdn-v1/",
                    ),
                    "en-us": _available(
                        "SupportArticles/SLA/cdn-v1/index.html",
                        "https://www.azure.cn/en-us/support/sla/cdn-v1/",
                        cms_path="/en-us/support/sla/cdn-v1/",
                    ),
                },
            },
        ],
    }
    return {
        "frontdoor": ("products/pricing/frontdoor.json", frontdoor),
        "event-grid": ("products/pricing/event-grid.json", event_grid),
        "sla-cdn": ("products/support-articles/sla-cdn.json", sla_cdn),
    }


def _build_mini_planner(root: Path) -> PipelinePlanner:
    records: dict[str, ProductDefinitionRecord] = {}
    for product_key, (relative_path, definition) in _mini_definitions().items():
        config_path = root / "data" / "configs" / relative_path
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(definition, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        records[product_key] = ProductDefinitionRecord(
            product_key=product_key,
            path=config_path,
            relative_path=relative_path,
            definition=definition,
        )

        sources = [definition["sources"]]
        sources.extend(version["sources"] for version in definition.get("historical_versions", []))
        for by_language in sources:
            for language, source in by_language.items():
                if source["availability"] != "available":
                    continue
                snapshot = (
                    root
                    / "data"
                    / "current_prod_html"
                    / language
                    / source["snapshot_path"]
                )
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                snapshot.write_text(
                    f"<html><body>{product_key}:{language}:{source['snapshot_path']}</body></html>",
                    encoding="utf-8",
                )
    return PipelinePlanner(root, catalog=_MiniCatalog(records))


def _frozen_provenance() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "captured_at": FIXED_TIMESTAMP,
        "git_commit": "a" * 40,
        "dirty": False,
        "reproducible": True,
        "worktree_changes": [],
        "worktree_fingerprint": f"sha256:{SHA256_ZERO}",
        "immutable_fingerprint": f"sha256:{SHA256_ZERO}",
        "immutable_files": {},
    }


class PipelinePlannerTests(unittest.TestCase):
    def test_real_all_inventory_is_fully_accounted(self) -> None:
        plan = PipelinePlanner(ROOT).plan()

        self.assertEqual(
            plan.summary,
            {
                "total": 434,
                "runnable": 379,
                "skipped": 55,
                "known_unsupported": 54,
                "source_unavailable": 1,
            },
        )
        self.assertEqual(plan.summary["total"], plan.summary["runnable"] + plan.summary["skipped"])
        self.assertEqual(len({item.item_id for item in plan.items}), 434)

    def test_real_integration_zh_cn_smoke_scope(self) -> None:
        plan = PipelinePlanner(ROOT).plan(
            scope="group",
            group="integration",
            language="zh-cn",
        )

        self.assertEqual(
            plan.summary,
            {
                "total": 4,
                "runnable": 2,
                "skipped": 2,
                "known_unsupported": 2,
                "source_unavailable": 0,
            },
        )
        runnable = {item.resource_key for item in plan.items if item.runnable}
        unsupported = {item.resource_key for item in plan.items if not item.runnable}
        self.assertEqual(runnable, {"api-management", "service-bus"})
        self.assertEqual(unsupported, {"customer-engagement-fabric", "event-grid"})
        self.assertTrue(
            all(item.skip_reason["code"] == "KNOWN_UNSUPPORTED" for item in plan.items if not item.runnable)
        )

    def test_mini_catalog_expands_current_history_languages_and_skips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = _build_mini_planner(Path(directory)).plan()

        self.assertEqual(
            plan.summary,
            {
                "total": 10,
                "runnable": 7,
                "skipped": 3,
                "known_unsupported": 2,
                "source_unavailable": 1,
            },
        )
        self.assertEqual({item.language for item in plan.items}, {"zh-cn", "en-us"})
        self.assertEqual(sum(item.resource_kind == "current" for item in plan.items), 6)
        self.assertEqual(sum(item.resource_kind == "historical_version" for item in plan.items), 4)

        frontdoor = [item for item in plan.items if item.resource_key == "frontdoor"]
        self.assertEqual(len(frontdoor), 2)
        self.assertTrue(all(item.catalog_categories == ("networking", "websites") for item in frontdoor))
        self.assertEqual(
            {item.output_path for item in frontdoor},
            {"outputs/zh-cn/pricing/frontdoor.json", "outputs/en-us/pricing/frontdoor.json"},
        )

        unavailable = next(item for item in plan.items if item.item_id == "en-us/sla-cdn--v1-1")
        self.assertFalse(unavailable.runnable)
        self.assertEqual(unavailable.skip_reason["code"], "SOURCE_UNAVAILABLE")
        self.assertIsNone(unavailable.source_path)
        self.assertIsNone(unavailable.source_sha256)
        self.assertTrue(
            all(
                item.skip_reason["code"] == "KNOWN_UNSUPPORTED"
                for item in plan.items
                if item.resource_key == "event-grid"
            )
        )


class PipelineStateFoundationTests(unittest.TestCase):
    def test_generate_batch_id_uses_utc_clock_and_fixed_suffix(self) -> None:
        pacific_time = datetime(
            2026,
            7,
            21,
            12,
            34,
            56,
            tzinfo=timezone(-timedelta(hours=7)),
        )
        self.assertEqual(generate_batch_id(pacific_time, "deadbeef"), FIXED_BATCH_ID)
        with self.assertRaises(ValueError):
            generate_batch_id(pacific_time, "DEADBEEF")

    def test_state_store_is_write_once_revisioned_validated_and_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as catalog_directory, tempfile.TemporaryDirectory() as run_directory:
            plan = _build_mini_planner(Path(catalog_directory)).plan(language="zh-cn")
            frozen = InputManifest.from_plan(
                FIXED_BATCH_ID,
                plan,
                _frozen_provenance(),
                created_at=FIXED_TIMESTAMP,
            )
            store = StateStore(ROOT, runs_dir=Path(run_directory) / "runs")
            batch_directory = store.create_run(frozen)

            initial = store.read_manifest(FIXED_BATCH_ID)
            self.assertEqual(initial["revision"], 0)
            self.assertEqual(store.read_input_manifest(FIXED_BATCH_ID), frozen.to_dict())
            with self.assertRaises(ImmutableManifestError):
                store.write_input_manifest(FIXED_BATCH_ID, frozen)

            updated = store.update_manifest(
                FIXED_BATCH_ID,
                lambda value: value.update({"status": "running"}),
                expected_revision=0,
            )
            self.assertEqual(updated["revision"], 1)
            self.assertEqual(updated["status"], "running")
            with self.assertRaises(ManifestConflictError):
                store.update_manifest(
                    FIXED_BATCH_ID,
                    lambda value: value.update({"status": "completed"}),
                    expected_revision=0,
                )

            with self.assertRaises(ManifestValidationError):
                store.update_manifest(
                    FIXED_BATCH_ID,
                    lambda value: value.update({"status": "invalid-state"}),
                    expected_revision=1,
                )
            self.assertEqual(store.read_manifest(FIXED_BATCH_ID)["revision"], 1)
            with self.assertRaises(ManifestValidationError):
                store.validate_document({"schema_version": "1.0"}, "input")

            temporary_files = [
                path for path in batch_directory.rglob("*") if path.name.endswith(".tmp")
            ]
            self.assertEqual(temporary_files, [])

            input_path = batch_directory / "input-manifest.json"
            input_path.write_text(input_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(ImmutableManifestError, "hash mismatch"):
                store.read_manifest(FIXED_BATCH_ID)

    def test_repository_lock_rejects_a_competing_mutator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = RepositoryLock(directory)
            with first:
                self.assertTrue(first.acquired)
                self.assertTrue(RepositoryLock.is_locked(directory))
                with self.assertRaises(RepositoryLockError):
                    RepositoryLock(directory).acquire()

            self.assertFalse(first.acquired)
            self.assertFalse(RepositoryLock.is_locked(directory))

    def test_incremental_manifest_validation_covers_only_declared_item_changes(self) -> None:
        with tempfile.TemporaryDirectory() as catalog_directory, tempfile.TemporaryDirectory() as run_directory:
            plan = _build_mini_planner(Path(catalog_directory)).plan(language="zh-cn")
            frozen = InputManifest.from_plan(
                FIXED_BATCH_ID,
                plan,
                _frozen_provenance(),
                created_at=FIXED_TIMESTAMP,
            )
            store = StateStore(ROOT, runs_dir=Path(run_directory) / "runs")
            store.create_run(frozen)
            item_id = next(item.item_id for item in plan.items if item.runnable)

            updated = store.update_manifest(
                FIXED_BATCH_ID,
                lambda value: value["items"][item_id].update(
                    {"strategy": "simple_static"}
                ),
                changed_item_ids=(item_id,),
            )
            self.assertEqual(updated["revision"], 1)

            with self.assertRaisesRegex(
                ManifestValidationError, "undeclared Batch Items"
            ):
                store.update_manifest(
                    FIXED_BATCH_ID,
                    lambda value: value["items"][item_id].update(
                        {"strategy": "complex"}
                    ),
                    changed_item_ids=(),
                )

            with self.assertRaises(ManifestValidationError):
                store.update_manifest(
                    FIXED_BATCH_ID,
                    lambda value: value["items"][item_id]["status"].update(
                        {"execution": "invalid"}
                    ),
                    changed_item_ids=(item_id,),
                )
            self.assertEqual(store.read_manifest(FIXED_BATCH_ID)["revision"], 1)


class ResourceParallelEngineTests(unittest.TestCase):
    def test_future_exception_is_isolated_and_callback_runs_on_caller_thread(self) -> None:
        caller_thread = threading.get_ident()
        worker_threads: set[int] = set()
        callback_threads: list[int] = []
        callback_progress: list[tuple[int, int]] = []
        thread_guard = threading.Lock()

        def item(resource_key: str) -> ResourceProcessingInfo:
            return ResourceProcessingInfo(
                batch_id=FIXED_BATCH_ID,
                product_key=resource_key,
                resource_key=resource_key,
                version_key=None,
                language="zh-cn",
                html_file_path=f"/fixture/{resource_key}.html",
                payload_root="/fixture/outputs",
                diagnostic_root="/fixture/diagnostics",
            )

        def worker(resource: ResourceProcessingInfo) -> ResourceProcessingResult:
            with thread_guard:
                worker_threads.add(threading.get_ident())
            if resource.resource_key == "explode":
                raise RuntimeError("worker boom")
            return ResourceProcessingResult(
                item=resource,
                execution="succeeded",
                validation="not_run",
                strategy="simple_static",
            )

        def callback(result: ResourceProcessingResult, completed: int, total: int) -> None:
            callback_threads.append(threading.get_ident())
            callback_progress.append((completed, total))

        engine = BatchProcessEngine(max_workers=2, persist_records=False)
        results = engine.process_resource_items(
            [item("alpha"), item("explode"), item("omega")],
            worker=worker,
            result_callback=callback,
        )

        by_key = {result.resource_key: result for result in results}
        self.assertEqual(set(by_key), {"alpha", "explode", "omega"})
        self.assertTrue(by_key["alpha"].execution_succeeded)
        self.assertTrue(by_key["omega"].execution_succeeded)
        self.assertEqual(by_key["explode"].execution, "failed")
        self.assertEqual(by_key["explode"].validation, "not_run")
        self.assertEqual(by_key["explode"].error_code, "RuntimeError")
        self.assertEqual(by_key["explode"].error_message, "worker boom")
        self.assertEqual(callback_progress, [(1, 3), (2, 3), (3, 3)])
        self.assertEqual(callback_threads, [caller_thread, caller_thread, caller_thread])
        self.assertNotIn(caller_thread, worker_threads)


if __name__ == "__main__":
    unittest.main()
