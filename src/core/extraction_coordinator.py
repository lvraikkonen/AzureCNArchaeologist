"""Explicit v0.2 extraction pipeline with payload/diagnostic isolation."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from bs4 import BeautifulSoup

from src.core.contract_validator import ContractIssue, ContractValidator
from src.core.data_models import ExtractionStrategy
from src.core.extraction_result import ExtractionResult
from src.core.logging import get_logger
from src.core.product_catalog import artifact_relative_directory, normalized_input_path, sha256_file
from src.core.product_manager import ProductManager
from src.core.strategy_manager import StrategyManager
from src.strategies.strategy_factory import StrategyFactory
from src.utils.media.image_processor import preprocess_image_paths


logger = get_logger(__name__)


class ExtractionCoordinator:
    def __init__(self, output_dir: str = "output") -> None:
        self.root = Path(__file__).resolve().parents[2]
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.product_manager = ProductManager(str(self.root / "data" / "configs"))
        self.strategy_manager = StrategyManager(self.product_manager)
        self.contract_validator = ContractValidator(self.root)

    def coordinate_extraction(
        self,
        product_key: str,
        language: str,
        html_file_path: str | None = None,
    ) -> ExtractionResult:
        if language not in ("zh-cn", "en-us"):
            raise ValueError(f"Unsupported language: {language}")
        definition = self.product_manager.get_product_config(product_key)
        input_path = Path(html_file_path).resolve() if html_file_path else normalized_input_path(self.root, definition, language)
        relative_dir = artifact_relative_directory(definition, language)
        payload_target_path = self.output_dir / "payloads" / relative_dir / f"{product_key}.json"
        payload_path: Optional[Path] = payload_target_path
        sidecar_path = self.output_dir / "diagnostics" / relative_dir / f"{product_key}.sidecar.json"
        source_definition = definition["sources"][language]
        source_path = (
            self.root / "data" / "current_prod_html" / language / source_definition["snapshot_path"]
            if source_definition["availability"] == "available"
            else input_path
        )
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
            else:
                if not input_path.is_file():
                    raise FileNotFoundError(f"Normalized Input does not exist: {input_path}")
                strategy = self.strategy_manager.determine_extraction_strategy(str(input_path), product_key)
                strategy_metadata = self._strategy_metadata(strategy)
                strategy_instance = StrategyFactory.create_strategy(strategy, definition, str(input_path))
                soup = self._read_html(input_path)
                expected_ms_service = self._extract_ms_service(soup) if definition["page_model"] == "FlexibleContentPage" else None
                payload = strategy_instance.extract_flexible_content(soup, source_definition.get("url", ""))
                self._normalize_business_fields(payload, definition, language)
                validation = self.contract_validator.validate(payload, definition["page_model"], expected_ms_service)
                validation_issues = validation.to_dict()
                validation_issues["warnings"].extend(self._quality_warnings(payload, definition))
                status["execution"] = "succeeded"
                status["validation"] = "passed" if validation.passed else "failed"
                payload_target_path.parent.mkdir(parents=True, exist_ok=True)
                payload_target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
            "schema_version": "1.0",
            "product_key": product_key,
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
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        sidecar_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return ExtractionResult(product_key, language, payload, sidecar, payload_path, sidecar_path)

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
