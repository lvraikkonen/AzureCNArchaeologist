"""Explicit v0.2 extraction pipeline with payload/diagnostic isolation."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from bs4 import BeautifulSoup

from src.core.contract_validator import ContractIssue, ContractValidationResult, ContractValidator
from src.core.data_models import ExtractionStrategy, PageType, StrategyType
from src.core.extraction_result import ExtractionResult
from src.core.logging import get_logger
from src.core.product_catalog import artifact_relative_directory, normalized_input_path, sha256_file
from src.core.product_manager import ProductManager
from src.core.strategy_manager import StrategyManager
from src.core.support_article_versions import (
    available_historical_versions,
    build_support_url_route_map,
    get_historical_version,
    historical_normalized_input_path,
    historical_resource_key,
)
from src.strategies.strategy_factory import StrategyFactory
from src.utils.media.image_processor import preprocess_image_paths


logger = get_logger(__name__)


class ExtractionCoordinator:
    def __init__(
        self,
        output_dir: str = "output",
        *,
        payload_root: str | Path | None = None,
        diagnostic_root: str | Path | None = None,
        deferred_validation: bool = False,
        defer_validation: bool | None = None,
    ) -> None:
        self.root = Path(__file__).resolve().parents[2]
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.payload_root = (
            Path(payload_root).resolve()
            if payload_root is not None
            else self.output_dir / "payloads"
        )
        self.diagnostic_root = (
            Path(diagnostic_root).resolve()
            if diagnostic_root is not None
            else self.output_dir / "diagnostics"
        )
        # ``defer_validation`` is retained as a concise constructor alias for
        # pipeline clients; the longer name is the documented spelling.
        self.deferred_validation = (
            defer_validation if defer_validation is not None else deferred_validation
        )
        self.product_manager = ProductManager(str(self.root / "data" / "configs"))
        self.strategy_manager = StrategyManager(self.product_manager)
        self.contract_validator = ContractValidator(self.root)

    def coordinate_extraction(
        self,
        product_key: str,
        language: str,
        html_file_path: str | None = None,
        version_key: str | None = None,
        strategy: ExtractionStrategy | StrategyType | str | None = None,
        defer_validation: bool | None = None,
        preselected_strategy: ExtractionStrategy | StrategyType | str | None = None,
    ) -> ExtractionResult:
        if language not in ("zh-cn", "en-us"):
            raise ValueError(f"Unsupported language: {language}")
        definition = self.product_manager.get_product_config(product_key)
        version = get_historical_version(definition, version_key) if version_key else None
        resource_key = historical_resource_key(product_key, version_key) if version_key else product_key
        resource_kind = "historical_version" if version else "current"
        resource_slug = version["slug"] if version else definition["slug"]
        version_label = version["version_label"] if version else definition["sources"][language].get("document_version")
        source_definition = version["sources"][language] if version else definition["sources"][language]
        default_input_path = (
            historical_normalized_input_path(self.root, definition, language, version_key)
            if version_key else normalized_input_path(self.root, definition, language)
        )
        input_path = Path(html_file_path).resolve() if html_file_path else default_input_path
        relative_dir = artifact_relative_directory(definition, language)
        payload_target_path = self.payload_root / relative_dir / f"{resource_key}.json"
        payload_path: Optional[Path] = payload_target_path
        sidecar_path = self.diagnostic_root / relative_dir / f"{resource_key}.sidecar.json"
        source_path = (
            self.root / "data" / "current_prod_html" / language / source_definition["snapshot_path"]
            if source_definition["availability"] == "available"
            else input_path
        )
        runtime_definition = deepcopy(definition)
        runtime_definition["slug"] = resource_slug
        runtime_definition.setdefault("extraction", {})["url_route_map"] = build_support_url_route_map(
            definition, language
        ) if definition["page_model"] == "SupportArticlePage" else {}
        started = datetime.now(timezone.utc)
        started_clock = time.perf_counter()
        payload: Optional[dict[str, Any]] = None
        strategy_metadata: dict[str, Any] = {"type": "not_selected", "processor": "not_selected"}
        validation_issues = {"errors": [], "warnings": []}
        status = {"execution": "running", "validation": "not_run", "review": "not_requested", "publication": "not_published"}
        structured_error: Optional[dict[str, str]] = None

        try:
            if definition["capability_status"] != "supported":
                status["execution"] = "skipped"
                structured_error = {"code": "known_unsupported", "stage": "catalog", "message": definition["unsupported_reason"]}
                payload_target_path.unlink(missing_ok=True)
                payload_path = None
            elif source_definition["availability"] != "available":
                status["execution"] = "skipped"
                structured_error = {
                    "code": "source_unavailable",
                    "stage": "catalog",
                    "message": source_definition["unavailable_reason"],
                }
                payload_target_path.unlink(missing_ok=True)
                payload_path = None
            else:
                if not input_path.is_file():
                    raise FileNotFoundError(f"Normalized Input does not exist: {input_path}")
                if strategy is not None and preselected_strategy is not None:
                    raise ValueError("Specify only one of strategy or preselected_strategy")
                selected_strategy = self._resolve_strategy(
                    preselected_strategy if preselected_strategy is not None else strategy,
                    input_path,
                    product_key,
                )
                strategy_metadata = self._strategy_metadata(selected_strategy)
                strategy_instance = StrategyFactory.create_strategy(selected_strategy, runtime_definition, str(input_path))
                soup = self._read_html(input_path)
                payload = strategy_instance.extract_flexible_content(soup, source_definition.get("url", ""))
                self._normalize_business_fields(payload, runtime_definition, language)
                status["execution"] = "succeeded"
                self._write_json_atomic(payload_target_path, payload)
        except Exception as error:
            logger.error(f"Extraction failed for {language}/{product_key}: {error}", exc_info=True)
            payload = None
            payload_target_path.unlink(missing_ok=True)
            payload_path = None
            status["execution"] = "failed"
            status["validation"] = "not_run"
            structured_error = {"code": type(error).__name__, "stage": "extraction", "message": str(error)}

        completed = datetime.now(timezone.utc)
        duration_ms = max(0, round((time.perf_counter() - started_clock) * 1000))
        sidecar = {
            "schema_version": "1.1",
            "product_key": product_key,
            "resource": {
                "kind": resource_kind,
                "resource_key": resource_key,
                "slug": resource_slug,
                "version_key": version_key,
                "version_label": version_label,
            },
            "language": language,
            "page_model": definition["page_model"],
            "contract": self.contract_validator.contract_metadata(definition["page_model"]),
            "source": self._artifact(source_path, source_definition.get("url")),
            "normalized_input": self._artifact(input_path),
            "payload": self._artifact(payload_path) if payload_path else None,
            "strategy": strategy_metadata,
            "status": status,
            "validation": validation_issues,
            "timing": {"started_at": started.isoformat(), "completed_at": completed.isoformat(), "duration_ms": duration_ms},
            "error": structured_error,
        }
        sidecar_validation = self.contract_validator.validate_sidecar(sidecar)
        if not sidecar_validation.passed:
            messages = "; ".join(issue.message for issue in sidecar_validation.errors)
            raise RuntimeError(f"Diagnostic Sidecar contract failure: {messages}")
        self._write_json_atomic(sidecar_path, sidecar)
        result = ExtractionResult(product_key, language, payload, sidecar, payload_path, sidecar_path)
        should_defer = self.deferred_validation if defer_validation is None else defer_validation
        if result.execution_succeeded and not should_defer:
            return self.validate_persisted_payload(result, html_file_path=input_path)
        return result

    def validate_persisted_payload(
        self,
        product_key: ExtractionResult | str,
        language: str | None = None,
        payload_path: str | Path | None = None,
        sidecar_path: str | Path | None = None,
        *,
        html_file_path: str | Path | None = None,
        version_key: str | None = None,
    ) -> ExtractionResult:
        """Validate a persisted payload and atomically refresh its sidecar.

        This is the single validation entry point used both by the default
        inline flow and by a deferred pipeline validation stage.  Artifact
        hashes already frozen in the sidecar are treated as expectations and
        are never replaced with hashes from a modified file.
        """
        if isinstance(product_key, ExtractionResult):
            extraction_result = product_key
            product_key = extraction_result.product_key
            language = extraction_result.language
            payload_file = extraction_result.payload_path
            sidecar_file = extraction_result.sidecar_path
        else:
            if language is None:
                raise ValueError("language is required when validating by Product Key")
            definition = self.product_manager.get_product_config(product_key)
            resource_key = historical_resource_key(product_key, version_key) if version_key else product_key
            relative_dir = artifact_relative_directory(definition, language)
            payload_file = (
                Path(payload_path).resolve()
                if payload_path is not None
                else self.payload_root / relative_dir / f"{resource_key}.json"
            )
            sidecar_file = (
                Path(sidecar_path).resolve()
                if sidecar_path is not None
                else self.diagnostic_root / relative_dir / f"{resource_key}.sidecar.json"
            )

        if language not in ("zh-cn", "en-us"):
            raise ValueError(f"Unsupported language: {language}")
        if payload_file is None:
            raise ValueError(f"No persisted payload exists for {language}/{product_key}")
        payload_file = Path(payload_file).resolve()
        sidecar_file = Path(sidecar_file).resolve()
        try:
            sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Unable to read Diagnostic Sidecar {sidecar_file}: {error}") from error
        if not isinstance(sidecar, dict):
            raise ValueError(f"Diagnostic Sidecar must be an object: {sidecar_file}")
        sidecar_contract = self.contract_validator.validate_sidecar(sidecar)
        if not sidecar_contract.passed:
            messages = "; ".join(issue.message for issue in sidecar_contract.errors)
            raise ValueError(f"Invalid Diagnostic Sidecar {sidecar_file}: {messages}")

        sidecar_version_key = sidecar.get("resource", {}).get("version_key")
        if version_key is not None and sidecar_version_key != version_key:
            raise ValueError(
                f"Diagnostic Sidecar version mismatch: expected {version_key}, found {sidecar_version_key}"
            )
        version_key = sidecar_version_key
        definition = self.product_manager.get_product_config(product_key)
        version = get_historical_version(definition, version_key) if version_key else None
        runtime_definition = deepcopy(definition)
        if version:
            runtime_definition["slug"] = version["slug"]

        errors: list[ContractIssue] = []
        warnings: list[ContractIssue] = []
        if sidecar.get("product_key") != product_key or sidecar.get("language") != language:
            errors.append(ContractIssue(
                "sidecar_identity_mismatch",
                "$",
                "Diagnostic Sidecar product_key/language does not match the requested resource.",
            ))

        declared_payload = sidecar.get("payload") or {}
        declared_payload_path = declared_payload.get("path")
        if declared_payload_path and Path(declared_payload_path).resolve() != payload_file:
            errors.append(ContractIssue(
                "payload_path_mismatch",
                "$.payload.path",
                "Persisted payload path does not match the path frozen in the Diagnostic Sidecar.",
            ))

        payload: dict[str, Any] | None = None
        if not payload_file.is_file():
            errors.append(ContractIssue("payload_missing", "$.payload.path", f"Payload does not exist: {payload_file}"))
        else:
            actual_payload_hash = sha256_file(payload_file)
            expected_payload_hash = declared_payload.get("sha256")
            if expected_payload_hash and actual_payload_hash != expected_payload_hash:
                errors.append(ContractIssue(
                    "payload_hash_mismatch",
                    "$.payload.sha256",
                    "Persisted payload SHA-256 does not match the frozen extraction hash.",
                ))
            try:
                loaded_payload = json.loads(payload_file.read_text(encoding="utf-8"))
                if not isinstance(loaded_payload, dict):
                    raise TypeError("Business Payload must be a JSON object")
                payload = loaded_payload
            except (OSError, json.JSONDecodeError, TypeError) as error:
                errors.append(ContractIssue("invalid_payload_json", "$", str(error)))

        input_file = self._artifact_path(
            html_file_path or sidecar.get("normalized_input", {}).get("path")
        )
        self._append_artifact_hash_issue(
            errors, sidecar.get("normalized_input"), input_file, "normalized_input"
        )
        source_file = self._artifact_path(sidecar.get("source", {}).get("path"))
        self._append_artifact_hash_issue(errors, sidecar.get("source"), source_file, "source")

        if payload is not None:
            expected_ms_service = None
            if definition["page_model"] == "FlexibleContentPage" and input_file.is_file():
                expected_ms_service = self._extract_ms_service(self._read_html(input_file))
            contract_result = self.contract_validator.validate(
                payload, definition["page_model"], expected_ms_service
            )
            errors.extend(contract_result.errors)
            warnings.extend(contract_result.warnings)
            warnings.extend(
                ContractIssue(item["code"], item["path"], item["message"])
                for item in self._quality_warnings(payload, runtime_definition)
            )

        validation = ContractValidationResult(errors, warnings)
        sidecar["validation"] = validation.to_dict()
        sidecar["status"]["validation"] = "passed" if validation.passed else "failed"
        updated_contract = self.contract_validator.validate_sidecar(sidecar)
        if not updated_contract.passed:
            messages = "; ".join(issue.message for issue in updated_contract.errors)
            raise RuntimeError(f"Diagnostic Sidecar contract failure: {messages}")
        self._write_json_atomic(sidecar_file, sidecar)
        return ExtractionResult(
            product_key,
            language,
            payload,
            sidecar,
            payload_file,
            sidecar_file,
        )

    def coordinate_product_extractions(
        self,
        product_key: str,
        language: str,
    ) -> list[ExtractionResult]:
        """Extract the current page and every available historical SLA version."""
        definition = self.product_manager.get_product_config(product_key)
        results = [self.coordinate_extraction(product_key, language)]
        results.extend(
            self.coordinate_extraction(product_key, language, version_key=version["version_key"])
            for version in available_historical_versions(definition, language)
        )
        return results

    def _resolve_strategy(
        self,
        strategy: ExtractionStrategy | StrategyType | str | None,
        input_path: Path,
        product_key: str,
    ) -> ExtractionStrategy:
        if strategy is None:
            return self.strategy_manager.determine_extraction_strategy(
                str(input_path), product_key
            )
        if isinstance(strategy, ExtractionStrategy):
            return strategy
        strategy_type = strategy if isinstance(strategy, StrategyType) else StrategyType(strategy)
        return self.strategy_manager._select_strategy_by_page_type(
            PageType(strategy_type.value), product_key, None
        )

    def _artifact_path(self, value: str | Path | None) -> Path:
        if value is None:
            return Path("")
        path = Path(value)
        return path.resolve() if path.is_absolute() else (self.root / path).resolve()

    @staticmethod
    def _append_artifact_hash_issue(
        errors: list[ContractIssue],
        artifact: dict[str, Any] | None,
        path: Path,
        name: str,
    ) -> None:
        artifact = artifact or {}
        expected_hash = artifact.get("sha256")
        if not path.is_file():
            errors.append(ContractIssue(
                f"{name}_missing", f"$.{name}.path", f"Artifact does not exist: {path}"
            ))
        elif expected_hash and sha256_file(path) != expected_hash:
            errors.append(ContractIssue(
                f"{name}_hash_mismatch",
                f"$.{name}.sha256",
                f"Artifact SHA-256 does not match the frozen {name} hash.",
            ))

    @staticmethod
    def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, path)
            try:
                directory_descriptor = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_descriptor)
                finally:
                    os.close(directory_descriptor)
            except OSError:
                # Directory fsync is not available on every supported platform.
                pass
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _read_html(path: Path) -> BeautifulSoup:
        for encoding in ("utf-8", "gbk", "iso-8859-1"):
            try:
                html = path.read_text(encoding=encoding)
                return preprocess_image_paths(BeautifulSoup(html, "html.parser"))
            except UnicodeDecodeError:
                continue
        raise UnicodeError(f"Unable to decode {path}")

    @staticmethod
    def _normalize_business_fields(payload: dict[str, Any], definition: dict[str, Any], language: str) -> None:
        for key in ("validation", "extraction_metadata", "error", "source_file", "source_url", "quality_score"):
            payload.pop(key, None)
        payload["slug"] = definition["slug"]
        if definition["page_model"] == "FlexibleContentPage":
            payload["language"] = language

    @staticmethod
    def _extract_ms_service(soup: BeautifulSoup) -> str:
        metadata_tag = soup.find("tags", attrs={"ms.service": True})
        if metadata_tag:
            return str(metadata_tag.get("ms.service", "")).strip()
        meta = soup.find("meta", attrs={"name": re.compile(r"^ms\.service$", re.I)})
        return str(meta.get("content", "")).strip() if meta else ""

    @staticmethod
    def _quality_warnings(payload: dict[str, Any], definition: dict[str, Any]) -> list[dict[str, str]]:
        minimum = definition.get("quality", {}).get("min_content_length")
        if minimum is None:
            return []
        if definition["page_model"] == "SupportArticlePage":
            fragments = [payload.get("mainContent", "")]
        else:
            fragments = [payload.get("baseContent", "")]
            fragments.extend(group.get("content", "") for group in payload.get("contentGroups", []))
            fragments.extend(section.get("content", "") for section in payload.get("commonSections", []))
        length = len(BeautifulSoup("".join(fragments), "html.parser").get_text(" ", strip=True))
        if length >= minimum:
            return []
        return [{
            "code": "content_below_threshold",
            "path": "$.mainContent" if definition["page_model"] == "SupportArticlePage" else "$",
            "message": f"Extracted text length {length} is below configured minimum {minimum}.",
        }]

    @staticmethod
    def _strategy_metadata(strategy: ExtractionStrategy) -> dict[str, Any]:
        return {
            "type": strategy.strategy_type.value,
            "processor": strategy.processor,
            "complexity_score": strategy.complexity_score,
            "features": strategy.features,
        }

    @staticmethod
    def _artifact(path: Path, url: str | None = None) -> dict[str, Any]:
        value: dict[str, Any] = {"path": str(path), "sha256": sha256_file(path) if path.is_file() else None}
        if url:
            value["url"] = url
        return value
