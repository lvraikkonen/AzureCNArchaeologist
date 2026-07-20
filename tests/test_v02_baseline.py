from __future__ import annotations

import copy
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator

from scripts.auto_copy_html import HTMLFileCopier, file_sha256
from scripts.upload_to_blob import eligible_payloads
from src.batch.models import ExecutionStatus, ValidationStatus
from src.batch.process_engine import BatchProcessEngine, ProductProcessingInfo
from src.batch.record_manager import BatchProcessRecordManager
from src.core.contract_validator import ContractValidator
from src.core.extraction_coordinator import ExtractionCoordinator
from src.core.product_catalog import CatalogError, ProductCatalog
from src.core.product_manager import ProductManager
from src.strategies.support_article_strategy import SupportArticleStrategy


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "regression" / "payloads"


class ProductCatalogTests(unittest.TestCase):
    def test_index_is_deterministic_and_frontdoor_is_multi_category(self):
        catalog = ProductCatalog(ROOT)
        built = catalog.build_index()
        stored = json.loads((ROOT / "data/configs/products-index.json").read_text(encoding="utf-8"))
        self.assertEqual(stored, built)
        self.assertEqual(built["total_products"], len(built["products"]))
        self.assertEqual(built["total_historical_versions"], 6)
        self.assertEqual(built["products"]["sla-cdn"]["historical_version_count"], 2)
        self.assertEqual(built["products"]["sla-sql-data"]["historical_version_count"], 4)
        self.assertEqual(built["products"]["frontdoor"]["catalog_categories"], ["networking", "websites"])
        self.assertEqual(sum("frontdoor" in view["products"] for view in built["catalog_categories"].values()), 2)
        manifest = catalog.build_baseline_manifest()
        self.assertEqual(manifest["total_product_language_entries"], built["total_products"] * 2)
        self.assertEqual(manifest["total_historical_versions"], 6)
        self.assertEqual(manifest["total_historical_version_language_entries"], 12)

    def test_every_raw_snapshot_is_explained_exactly_once(self):
        audit = ProductCatalog(ROOT).audit_snapshots()
        self.assertTrue(audit["passed"], audit)
        self.assertEqual(audit["counts"]["zh-cn"]["unknown"], 0)
        self.assertEqual(audit["counts"]["en-us"]["unknown"], 0)

    def test_definition_conditional_fields_and_slug(self):
        schema = json.loads((ROOT / "schemas/product-definition-1.0.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        definition = ProductManager().get_product_config("service-bus")
        invalid_slug = copy.deepcopy(definition)
        invalid_slug["slug"] = "event_grid"
        self.assertTrue(list(validator.iter_errors(invalid_slug)))
        unsupported = copy.deepcopy(definition)
        unsupported["capability_status"] = "known_unsupported"
        self.assertTrue(list(validator.iter_errors(unsupported)))
        support = ProductManager().get_product_config("icp-faq")
        invalid_support = copy.deepcopy(support)
        invalid_support["catalog_categories"] = ["support"]
        self.assertTrue(list(validator.iter_errors(invalid_support)))
        invalid_history_owner = copy.deepcopy(definition)
        invalid_history_owner["historical_versions"] = copy.deepcopy(
            ProductManager().get_product_config("sla-cdn")["historical_versions"]
        )
        self.assertTrue(list(validator.iter_errors(invalid_history_owner)))

    def test_duplicate_product_key_and_primary_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "schemas").mkdir()
            shutil.copy(ROOT / "schemas/product-definition-1.0.schema.json", root / "schemas")
            pricing = root / "data/configs/products/pricing"
            support = root / "data/configs/products/support-articles"
            pricing.mkdir(parents=True)
            support.mkdir(parents=True)
            first = copy.deepcopy(ProductManager().get_product_config("service-bus"))
            (pricing / "service-bus.json").write_text(json.dumps(first), encoding="utf-8")
            duplicate_key = copy.deepcopy(first)
            (support / "service-bus.json").write_text(json.dumps(duplicate_key), encoding="utf-8")
            with self.assertRaises(CatalogError):
                ProductCatalog(root).load_definitions()
            (support / "service-bus.json").unlink()
            duplicate_source = copy.deepcopy(first)
            duplicate_source["product_key"] = duplicate_source["slug"] = "service-bus-copy"
            (pricing / "service-bus-copy.json").write_text(json.dumps(duplicate_source), encoding="utf-8")
            with self.assertRaises(CatalogError):
                ProductCatalog(root).load_definitions()

    def test_copy_uses_exact_source_and_preserves_hash(self):
        result = HTMLFileCopier(ROOT).copy_product("sla-cognitive-services", "zh-cn")
        self.assertEqual(result["status"], "copied")
        self.assertEqual(file_sha256(Path(result["source"])), file_sha256(Path(result["target"])))
        self.assertIn("SupportArticles/SLA/sla-cognitive-services.html", result["target"])

    def test_sla_current_sources_and_publishable_versions_are_explicit(self):
        manager = ProductManager()
        cdn = manager.get_product_config("sla-cdn")
        sql_data = manager.get_product_config("sla-sql-data")

        self.assertEqual(cdn["sources"]["zh-cn"]["snapshot_path"], "SupportArticles/SLA/cdn/index.html")
        self.assertEqual(cdn["sources"]["en-us"]["snapshot_path"], "SupportArticles/SLA/cdn/index.html")
        self.assertNotIn("aliases", cdn["sources"]["zh-cn"])
        self.assertNotIn("aliases", sql_data["sources"]["zh-cn"])
        self.assertEqual(
            {version["version_key"]: version["slug"] for version in cdn["historical_versions"]},
            {"v1-1": "cdn-v1-1", "v1-0": "cdn-v1"},
        )
        self.assertEqual(
            {version["version_key"]: version["slug"] for version in sql_data["historical_versions"]},
            {
                "v1-5": "sql-data-v1-5",
                "v1-4": "sql-data-v1-4",
                "v1-3": "sql-data-v1-3",
                "v1-0": "sql-data-v1",
            },
        )
        cdn_v11 = next(version for version in cdn["historical_versions"] if version["version_key"] == "v1-1")
        self.assertEqual(cdn_v11["sources"]["en-us"]["availability"], "unavailable")

        copied = HTMLFileCopier(ROOT).copy_product("sla-cdn", "en-us")
        self.assertEqual(copied["status"], "copied")
        self.assertTrue(copied["source"].endswith("SupportArticles/SLA/cdn/index.html"))
        self.assertEqual(file_sha256(Path(copied["source"])), file_sha256(Path(copied["target"])))
        self.assertEqual(copied["copied_files"], 2)
        historical = next(item for item in copied["resources"] if item["resource_key"] == "sla-cdn--v1-0")
        self.assertTrue(historical["target"].endswith("SupportArticles/SLA/sla-cdn--v1-0.html"))
        self.assertEqual(file_sha256(Path(historical["source"])), file_sha256(Path(historical["target"])))

        copied_zh = HTMLFileCopier(ROOT).copy_product("sla-sql-data", "zh-cn")
        self.assertEqual(copied_zh["copied_files"], 5)
        for resource in copied_zh["resources"]:
            self.assertEqual(file_sha256(Path(resource["source"])), file_sha256(Path(resource["target"])))

        for key in (
            "sla-hpc-cache",
            "sla-managed-disks",
            "sla-virtual-desktop",
            "sla-virtual-machine-scale-sets",
        ):
            definition = manager.get_product_config(key)
            self.assertEqual(definition["capability_status"], "known_unsupported")
            self.assertIn("no H2 section", definition["unsupported_reason"])


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.validator = ContractValidator(ROOT)

    def test_flexible_examples_and_nested_semantics(self):
        for key in ("service-bus", "dns", "api-management", "cloud-services"):
            payload = json.loads((FIXTURES / f"{key}.json").read_text(encoding="utf-8"))
            result = self.validator.validate(payload, "FlexibleContentPage")
            self.assertTrue(result.passed, result.to_dict())
            for group in payload["contentGroups"]:
                for criterion in json.loads(group["filterCriteriaJson"]):
                    self.assertIsInstance(criterion["matchValues"], str)

    def test_flexible_extensions_allowed_but_diagnostics_forbidden(self):
        payload = json.loads((FIXTURES / "service-bus.json").read_text(encoding="utf-8"))
        payload["cmsBusinessExtension"] = {"enabled": True}
        self.assertTrue(self.validator.validate(payload, "FlexibleContentPage").passed)
        payload["validation"] = {"is_valid": True}
        result = self.validator.validate(payload, "FlexibleContentPage")
        self.assertFalse(result.passed)
        self.assertIn("diagnostic_field_in_payload", {issue.code for issue in result.errors})
        mismatch = self.validator.validate(payload, "FlexibleContentPage", expected_ms_service="different-service")
        self.assertIn("ms_service_mismatch", {issue.code for issue in mismatch.errors})

    def test_all_four_support_types_and_optional_empty_values(self):
        keys = {"icp-faq": "ICP", "legal-summary": "LEGAL", "psr-summary": "PSR", "sla-summary": "SLA"}
        for key, page_type in keys.items():
            payload = json.loads((FIXTURES / f"{key}.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["pageType"], page_type)
            self.assertTrue(self.validator.validate(payload, "SupportArticlePage").passed)

    def test_support_cleanup_dates_and_url_rewriting(self):
        html = """
        <html><head><title>Example</title></head><body><div class="pure-content">
          <h1>Title</h1><div class="ms-date">Updated: 07/2026</div><p>Intro <a href="../legal/page/">link</a></p>
          <h2>Body</h2><p><img src="/media/a.png" srcset="data:image/png;base64,AAAA 1x, /a.png 2x" style="background:url('images/bg.png')">Text</p>
          <div id="content_feedback"><p>feedback</p></div><div class="tags">tag UI</div><script>bad()</script>
        </div></body></html>
        """
        config = {"slug": "example", "support_article_type": "LEGAL"}
        payload = SupportArticleStrategy(config).extract_flexible_content(BeautifulSoup(html, "html.parser"), "https://www.azure.cn/en-us/support/legal/example/")
        self.assertEqual(payload["lastModifiedDate"], "07/2026")
        self.assertIn("{base_url}/en-us/support/legal/legal/page/", payload["articleDescription"])
        self.assertIn("{base_url}/media/a.png", payload["mainContent"])
        self.assertIn("data:image/png;base64,AAAA 1x", payload["mainContent"])
        self.assertIn("{base_url}/a.png 2x", payload["mainContent"])
        self.assertIn("{base_url}/en-us/support/legal/example/images/bg.png", payload["mainContent"])
        self.assertNotIn("content_feedback", payload["mainContent"])
        self.assertNotIn("tag UI", payload["mainContent"])
        self.assertNotIn("<script", payload["mainContent"])

        for source, expected in (
            ("最后更新时间：2016年03月", "2016年03月"),
            ("最后更新日期：2023 年 1 月", "2023 年 1 月"),
            ("更新时间：2026 年 7 月", "2026 年 7 月"),
        ):
            date_content = BeautifulSoup(f'<div class="wacn-date">{source}</div>', "html.parser")
            self.assertEqual(SupportArticleStrategy._extract_last_modified(date_content), expected)


class ExtractionStateTests(unittest.TestCase):
    def test_historical_sla_versions_have_independent_payloads_and_explicit_routes(self):
        HTMLFileCopier(ROOT).copy_product("sla-cdn", "zh-cn")
        HTMLFileCopier(ROOT).copy_product("sla-sql-data", "zh-cn")
        with tempfile.TemporaryDirectory() as directory:
            coordinator = ExtractionCoordinator(directory)
            cdn_results = coordinator.coordinate_product_extractions("sla-cdn", "zh-cn")
            self.assertEqual(
                [result.sidecar["resource"]["resource_key"] for result in cdn_results],
                ["sla-cdn", "sla-cdn--v1-1", "sla-cdn--v1-0"],
            )
            self.assertTrue(all(result.exit_code == 0 for result in cdn_results))
            current, version_11, version_10 = cdn_results
            self.assertEqual(version_11.payload["slug"], "cdn-v1-1")
            self.assertEqual(version_11.sidecar["schema_version"], "1.1")
            self.assertEqual(version_11.sidecar["product_key"], "sla-cdn")
            self.assertEqual(version_11.sidecar["resource"]["version_label"], "1.1")
            self.assertEqual(version_11.sidecar["source"]["sha256"], version_11.sidecar["normalized_input"]["sha256"])
            self.assertIn("{base_url}/support/sla/cdn-v1-1/", current.payload["mainContent"])
            self.assertIn("{base_url}/support/sla/cdn-v1/", version_11.payload["mainContent"])

            unavailable = coordinator.coordinate_extraction("sla-cdn", "en-us", version_key="v1-1")
            self.assertEqual(unavailable.sidecar["status"]["execution"], "skipped")
            self.assertEqual(unavailable.sidecar["error"]["code"], "source_unavailable")
            self.assertIsNone(unavailable.payload_path)

            sql_current = coordinator.coordinate_extraction("sla-sql-data", "zh-cn")
            sql_v15 = coordinator.coordinate_extraction("sla-sql-data", "zh-cn", version_key="v1-5")
            self.assertEqual(sql_current.exit_code, 0)
            self.assertEqual(sql_v15.exit_code, 0)
            for route in ("sql-data-v1-5", "sql-data-v1-4", "sql-data-v1-3", "sql-data-v1"):
                self.assertIn(f"{{base_url}}/support/sla/{route}/", sql_current.payload["mainContent"])
            self.assertNotIn("sql-data-V1_5", sql_v15.payload["mainContent"])
            self.assertNotIn("sql-data-v1_5", sql_v15.payload["mainContent"])
            self.assertIn("{base_url}/support/sla/sql-data-v1-5/", sql_v15.payload["mainContent"])

            eligible, rejected = eligible_payloads(Path(directory) / "payloads")
            eligible_keys = {path.stem for path, _, _ in eligible}
            self.assertIn("sla-cdn--v1-1", eligible_keys)
            self.assertIn("sla-sql-data--v1-5", eligible_keys)
            self.assertFalse(any(item.get("path", "").endswith("sla-cdn--v1-1.json") for item in rejected))

    def test_success_validation_failure_and_execution_failure_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = ExtractionCoordinator(directory)
            success = coordinator.coordinate_extraction("icp-faq", "zh-cn")
            self.assertEqual(success.exit_code, 0)
            self.assertEqual(success.sidecar["status"]["execution"], "succeeded")
            self.assertEqual(success.sidecar["status"]["validation"], "passed")

            english_route = coordinator.coordinate_extraction("icp-faq", "en-us")
            self.assertEqual(english_route.exit_code, 0)
            self.assertNotIn("language", {issue["code"] for issue in english_route.sidecar["validation"]["warnings"]})

            invalid_html = Path(directory) / "invalid.html"
            invalid_html.write_text("<div class='pure-content'><h1>Only a title</h1></div>", encoding="utf-8")
            invalid = coordinator.coordinate_extraction("icp-faq", "zh-cn", str(invalid_html))
            self.assertEqual(invalid.exit_code, 2)
            self.assertIsNotNone(invalid.payload)
            self.assertTrue(invalid.payload_path.is_file())
            self.assertEqual(invalid.sidecar["status"]["execution"], "succeeded")
            self.assertEqual(invalid.sidecar["status"]["validation"], "failed")
            self.assertIn("content_below_threshold", {issue["code"] for issue in invalid.sidecar["validation"]["warnings"]})

            empty_body_html = Path(directory) / "empty-body.html"
            empty_body_html.write_text("<div class='pure-content'><h1>Title</h1><h2></h2></div>", encoding="utf-8")
            empty_body = coordinator.coordinate_extraction("icp-faq", "zh-cn", str(empty_body_html))
            self.assertEqual(empty_body.exit_code, 2)
            self.assertEqual(empty_body.payload["mainContent"], "")

            missing = coordinator.coordinate_extraction("icp-faq", "zh-cn", str(Path(directory) / "missing.html"))
            self.assertEqual(missing.exit_code, 1)
            self.assertIsNone(missing.payload)
            self.assertIsNone(missing.payload_path)
            self.assertTrue(missing.sidecar_path.is_file())
            self.assertEqual(missing.sidecar["status"]["execution"], "failed")
            self.assertEqual(missing.sidecar["status"]["validation"], "not_run")
            self.assertFalse((Path(directory) / "payloads/zh-cn/SupportArticles/ICP/icp-faq.json").exists())

            stale_event_grid = Path(directory) / "payloads/zh-cn/pricing/event-grid.json"
            stale_event_grid.parent.mkdir(parents=True, exist_ok=True)
            stale_event_grid.write_text('{"stale": true}\n', encoding="utf-8")
            skipped = coordinator.coordinate_extraction("event-grid", "zh-cn")
            self.assertEqual(skipped.sidecar["status"]["execution"], "skipped")
            self.assertEqual(skipped.sidecar["status"]["validation"], "not_run")
            self.assertIsNone(skipped.payload_path)
            self.assertIsNone(skipped.sidecar["payload"])
            self.assertFalse(stale_event_grid.exists())

    def test_regression_payloads_are_deterministic_and_diagnostic_free(self):
        keys = ("service-bus", "dns", "api-management", "cloud-services", "icp-faq", "legal-summary", "psr-summary", "sla-summary", "sla-cognitive-services")
        with tempfile.TemporaryDirectory() as directory:
            coordinator = ExtractionCoordinator(directory)
            for key in keys:
                result = coordinator.coordinate_extraction(key, "zh-cn")
                expected = json.loads((FIXTURES / f"{key}.json").read_text(encoding="utf-8"))
                self.assertEqual(result.exit_code, 0, result.sidecar["validation"])
                self.assertEqual(result.payload, expected)
                self.assertFalse({"validation", "extraction_metadata", "error"}.intersection(result.payload))
                if key in {"service-bus", "dns"}:
                    base_content = result.payload["baseContent"]
                    self.assertIn("technical-azure-selector", base_content)
                    self.assertNotIn("common-banner", base_content)
                    self.assertNotIn("more-detail", base_content)
                    self.assertNotIn("documentation-navigation", base_content)


class UploadAndBatchTests(unittest.TestCase):
    def test_upload_selects_only_validation_passed_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload_root = root / "payloads"
            diagnostics_root = root / "diagnostics"
            for key, validation in (("valid", "passed"), ("invalid", "failed")):
                payload = payload_root / "zh-cn/pricing" / f"{key}.json"
                payload.parent.mkdir(parents=True, exist_ok=True)
                payload.write_text('{"title":"x"}\n', encoding="utf-8")
                sidecar = diagnostics_root / "zh-cn/pricing" / f"{key}.sidecar.json"
                sidecar.parent.mkdir(parents=True, exist_ok=True)
                sidecar.write_text(json.dumps({"status": {"execution": "succeeded", "validation": validation}, "payload": {"sha256": file_sha256(payload)}}), encoding="utf-8")
            eligible, rejected = eligible_payloads(payload_root)
            self.assertEqual([item[0].stem for item in eligible], ["valid"])
            self.assertEqual(rejected[0]["reason"], "execution_or_validation_not_passed")

    def test_legacy_retry_database_status_maps_to_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "legacy.db"
            connection = sqlite3.connect(db)
            connection.execute("""
              CREATE TABLE batch_process_records (
                id INTEGER PRIMARY KEY, product_key TEXT, product_group TEXT, strategy_used TEXT,
                processing_status TEXT, error_message TEXT, processing_time_ms INTEGER,
                output_file_path TEXT, html_file_path TEXT, content_hash TEXT, retry_count INTEGER,
                extraction_timestamp TEXT, created_at TEXT, updated_at TEXT, metadata TEXT
              )
            """)
            connection.execute("INSERT INTO batch_process_records VALUES (1,'event-grid','integration',NULL,'retry',NULL,NULL,NULL,NULL,NULL,1,'2026-01-01','2026-01-01','2026-01-01','{}')")
            connection.commit()
            connection.close()
            manager = BatchProcessRecordManager(str(db))
            record = manager.get_record(1)
            self.assertEqual(record.execution_status, ExecutionStatus.PENDING)
            self.assertEqual(record.validation_status, ValidationStatus.NOT_RUN)
            self.assertEqual(record.metadata["legacy_processing_status"], "retry")

    def test_batch_record_uses_sidecar_orthogonal_statuses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = BatchProcessRecordManager(str(root / "batch.db"))
            manager = ProductManager()
            html_path = manager.get_html_file_path("service-bus", "zh-cn")
            result = BatchProcessEngine(records, max_workers=1)._process_single_product(
                ProductProcessingInfo("service-bus", html_path, "integration", str(root / "output"), "zh-cn")
            )
            self.assertTrue(result.success)
            record = records.get_latest_record_for_product("service-bus")
            self.assertEqual(record.execution_status, ExecutionStatus.SUCCEEDED)
            self.assertEqual(record.validation_status, ValidationStatus.PASSED)
            self.assertEqual(record.review_status.value, "not_requested")
            self.assertEqual(record.publication_status.value, "not_published")


if __name__ == "__main__":
    unittest.main()
