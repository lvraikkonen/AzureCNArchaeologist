"""Parallel batch client for the v0.2 explicit extraction coordinator."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from src.core.extraction_coordinator import ExtractionCoordinator
from src.core.extraction_result import ExtractionResult
from src.core.product_catalog import sha256_file
from src.core.product_manager import ProductManager

from .models import BatchProcessRecord, BatchProcessReport, ExecutionStatus, ProcessingResult, ValidationStatus
from .record_manager import BatchProcessRecordManager


@dataclass
class ProductProcessingInfo:
    product_key: str
    html_file_path: str
    product_group: str
    output_dir: str
    language: str = "zh-cn"


@dataclass
class ResourceProcessingInfo:
    """One independently executable current or historical batch resource."""

    batch_id: str
    product_key: str
    resource_key: str
    version_key: str | None
    language: str
    html_file_path: str
    payload_root: str
    diagnostic_root: str
    strategy: Any | None = None
    defer_validation: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceProcessingResult:
    """Resource outcome with orthogonal execution and validation state."""

    item: ResourceProcessingInfo
    execution: str
    validation: str
    strategy: str = "not_selected"
    processing_time_ms: int = 0
    extraction_result: ExtractionResult | None = None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def product_key(self) -> str:
        return self.item.product_key

    @property
    def resource_key(self) -> str:
        return self.item.resource_key

    @property
    def language(self) -> str:
        return self.item.language

    @property
    def execution_succeeded(self) -> bool:
        return self.execution == "succeeded"


class BatchProcessEngine:
    def __init__(
        self,
        record_manager: Optional[BatchProcessRecordManager] = None,
        max_workers: int = 4,
        max_retries: int = 3,
        *,
        persist_records: bool = True,
    ) -> None:
        self.record_manager = (
            record_manager
            if record_manager is not None
            else (BatchProcessRecordManager() if persist_records else None)
        )
        self.product_manager = ProductManager()
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.progress_callback: Optional[Callable[[str, int, int], None]] = None

    def set_progress_callback(self, callback: Callable[[str, int, int], None]) -> None:
        self.progress_callback = callback

    def process_resource_items(
        self,
        items: list[ResourceProcessingInfo],
        worker: Callable[[ResourceProcessingInfo], ExtractionResult | ResourceProcessingResult] | None = None,
        result_callback: Callable[[ResourceProcessingResult, int, int], None] | None = None,
    ) -> list[ResourceProcessingResult]:
        """Process independent resources without consulting or writing SQLite.

        Futures are collected on the calling thread.  Consequently
        ``result_callback`` is also invoked on that thread and can safely be the
        sole committer for a JSON batch manifest.  Every worker exception is
        converted into a failed resource result and cannot abort sibling work.
        """
        if not items:
            return []
        resource_worker = worker or self._process_single_resource
        results: list[ResourceProcessingResult] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(resource_worker, item): item for item in items}
            for completed, future in enumerate(as_completed(futures), 1):
                item = futures[future]
                try:
                    outcome = future.result()
                    result = self._resource_result(item, outcome)
                except Exception as error:
                    result = ResourceProcessingResult(
                        item=item,
                        execution="failed",
                        validation="not_run",
                        error_code=type(error).__name__,
                        error_message=str(error),
                    )
                results.append(result)
                if result_callback:
                    result_callback(result, completed, len(items))
                if self.progress_callback:
                    self.progress_callback(
                        f"Processed {result.resource_key}", completed, len(items)
                    )
        return results

    def _process_single_resource(self, info: ResourceProcessingInfo) -> ExtractionResult:
        output_root = Path(info.payload_root).resolve().parent
        coordinator = ExtractionCoordinator(
            str(output_root),
            payload_root=info.payload_root,
            diagnostic_root=info.diagnostic_root,
            deferred_validation=info.defer_validation,
        )
        result = coordinator.coordinate_extraction(
            info.product_key,
            info.language,
            info.html_file_path,
            info.version_key,
            strategy=info.strategy,
        )
        actual_resource_key = result.sidecar["resource"]["resource_key"]
        if actual_resource_key != info.resource_key:
            raise ValueError(
                f"Resource Key mismatch: planned {info.resource_key}, extracted {actual_resource_key}"
            )
        return result

    @staticmethod
    def _resource_result(
        item: ResourceProcessingInfo,
        outcome: ExtractionResult | ResourceProcessingResult,
    ) -> ResourceProcessingResult:
        if isinstance(outcome, ResourceProcessingResult):
            return outcome
        if not isinstance(outcome, ExtractionResult):
            raise TypeError(
                "Resource worker must return ExtractionResult or ResourceProcessingResult"
            )
        sidecar = outcome.sidecar
        structured_error = sidecar.get("error")
        return ResourceProcessingResult(
            item=item,
            execution=sidecar["status"]["execution"],
            validation=sidecar["status"]["validation"],
            strategy=sidecar["strategy"]["type"],
            processing_time_ms=sidecar["timing"]["duration_ms"],
            extraction_result=outcome,
            error_code=structured_error["code"] if structured_error else None,
            error_message=structured_error["message"] if structured_error else None,
        )

    def process_product_group(self, group_name: str, output_dir: str, force_refresh: bool = False, html_base_dir: str | None = None, language: str = "zh-cn") -> BatchProcessReport:
        products = self._get_products_for_group(group_name, html_base_dir, output_dir, language)
        if not force_refresh:
            records = self._require_record_manager()
            products = [item for item in products if records.should_process_product(item.product_key, item.html_file_path)[0]]
        report = BatchProcessReport(f"{language}-{group_name}-{datetime.now():%Y%m%d%H%M%S}", datetime.now())
        report.products_by_group[group_name] = len(products)
        for result in self._process_products_parallel(products):
            report.add_result(result)
        report.finalize()
        return report

    def process_all_products(self, output_dir: str, force_refresh: bool = False, html_base_dir: str | None = None, language: str = "zh-cn") -> dict[str, BatchProcessReport]:
        reports = {}
        seen: set[str] = set()
        groups = [*self.product_manager.get_products_by_category(), *self.product_manager.get_products_by_support_type()]
        for group in groups:
            products = [item for item in self._get_products_for_group(group, html_base_dir, output_dir, language) if item.product_key not in seen]
            seen.update(item.product_key for item in products)
            report = BatchProcessReport(f"{language}-{group}-{datetime.now():%Y%m%d%H%M%S}", datetime.now())
            report.products_by_group[group] = len(products)
            if not force_refresh:
                records = self._require_record_manager()
                products = [item for item in products if records.should_process_product(item.product_key, item.html_file_path)[0]]
            for result in self._process_products_parallel(products):
                report.add_result(result)
            report.finalize()
            reports[group] = report
        return reports

    def retry_failed_products(self, output_dir: str, since_hours: int = 24) -> BatchProcessReport:
        records = self._require_record_manager().get_failed_records(datetime.now() - timedelta(hours=since_hours))
        latest: dict[tuple[str, str], BatchProcessRecord] = {}
        for record in records:
            latest.setdefault((record.product_key, record.language), record)
        products = [
            ProductProcessingInfo(record.product_key, record.html_file_path or "", record.product_group or "unknown", output_dir, record.language)
            for record in latest.values() if record.html_file_path and Path(record.html_file_path).is_file()
        ]
        report = BatchProcessReport(f"retry-{datetime.now():%Y%m%d%H%M%S}", datetime.now())
        for result in self._process_products_parallel(products):
            report.add_result(result)
        report.finalize()
        return report

    def _get_products_for_group(self, group: str, html_base_dir: str | None, output_dir: str, language: str) -> list[ProductProcessingInfo]:
        keys = self.product_manager.get_products_by_category(group).get(group)
        if keys is None:
            keys = self.product_manager.get_products_by_support_type(group).get(group, [])
        products = []
        for key in keys:
            definition = self.product_manager.get_product_config(key)
            if definition["capability_status"] != "supported":
                continue
            html_path = self.product_manager.get_html_file_path(key, language, html_base_dir)
            if html_path:
                products.append(ProductProcessingInfo(key, html_path, group, output_dir, language))
        return products

    def _process_products_parallel(self, products: list[ProductProcessingInfo]) -> list[ProcessingResult]:
        if not products:
            return []
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._process_single_product, item): item for item in products}
            for completed, future in enumerate(as_completed(futures), 1):
                item = futures[future]
                try:
                    result = future.result()
                except Exception as error:
                    result = ProcessingResult(
                        item.product_key,
                        False,
                        error_message=str(error),
                        metadata={
                            "execution": "failed",
                            "validation": "not_run",
                            "language": item.language,
                            "error_code": type(error).__name__,
                        },
                    )
                results.append(result)
                if self.progress_callback:
                    self.progress_callback(f"Processed {result.product_key}", completed, len(products))
        return results

    def _process_single_product(self, info: ProductProcessingInfo) -> ProcessingResult:
        started = datetime.now()
        records = self._require_record_manager()
        record_id: int | None = None
        try:
            record = BatchProcessRecord(
                product_key=info.product_key, product_group=info.product_group, language=info.language,
                execution_status=ExecutionStatus.RUNNING, html_file_path=info.html_file_path,
                content_hash=records.calculate_file_hash(info.html_file_path),
            )
            record_id = records.create_record(record)
            result = ExtractionCoordinator(info.output_dir).coordinate_extraction(info.product_key, info.language, info.html_file_path)
            status = result.sidecar["status"]
            execution = ExecutionStatus(status["execution"])
            validation = ValidationStatus(status["validation"])
            elapsed = result.sidecar["timing"]["duration_ms"]
            errors = result.sidecar["validation"]["errors"]
            error_message = result.sidecar["error"]["message"] if result.sidecar["error"] else ("; ".join(item["message"] for item in errors) or None)
            records.update_record(
                record_id, strategy_used=result.sidecar["strategy"]["type"], execution_status=execution,
                validation_status=validation, error_message=error_message, processing_time_ms=elapsed,
                output_file_path=str(result.payload_path) if result.payload_path else None,
                sidecar_file_path=str(result.sidecar_path), metadata={"language": info.language},
            )
            return ProcessingResult(
                info.product_key, result.exit_code == 0, result.sidecar["strategy"]["type"], elapsed,
                str(result.payload_path) if result.payload_path else None, str(result.sidecar_path), error_message,
                sha256_file(result.payload_path) if result.payload_path else None,
                {"execution": execution.value, "validation": validation.value, "language": info.language},
            )
        except Exception as error:
            elapsed = round((datetime.now() - started).total_seconds() * 1000)
            if record_id is not None:
                records.update_record(record_id, execution_status=ExecutionStatus.FAILED, validation_status=ValidationStatus.NOT_RUN, error_message=str(error), processing_time_ms=elapsed)
            return ProcessingResult(info.product_key, False, processing_time_ms=elapsed, error_message=str(error), metadata={"execution": "failed", "validation": "not_run", "language": info.language})

    def _require_record_manager(self) -> BatchProcessRecordManager:
        if self.record_manager is None:
            raise RuntimeError(
                "SQLite persistence is disabled; use process_resource_items or enable persist_records"
            )
        return self.record_manager
