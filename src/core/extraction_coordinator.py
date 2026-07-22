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

from src.core.canonical_input import (
    CanonicalHtmlInput,
    CanonicalInputLoader,
    InputAssuranceError,
)
from src.core.contract_validator import ContractIssue, ContractValidationResult, ContractValidator
from src.core.data_models import ExtractionStrategy, StrategyType
from src.core.extraction_result import ExtractionResult
from src.core.logging import get_logger
from src.core.product_catalog import artifact_relative_directory, normalized_input_path, sha256_file
from src.core.product_manager import ProductManager
from src.core.reconstruction_parseability import (
    ParseabilityResult,
    ReconstructionParseabilityValidator,
)
from src.core.strategy_manager import StrategyManager
from src.core.validation_context import ValidationContextRegistry
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
        self.validation_context = ValidationContextRegistry(self.root)
        self.input_loader = CanonicalInputLoader(
            self.root,
            self.product_manager,
            max_input_bytes=self.validation_context.max_input_bytes,
        )
        self.parseability_validator = ReconstructionParseabilityValidator()

    def coordinate_extraction(
        self,
        product_key: str,
        language: str,
        *,
        version_key: str | None = None,
        expected_input_sha256: str | None = None,
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
        input_path = default_input_path
        relative_dir = artifact_relative_directory(definition, language)
        payload_target_path = self.payload_root / relative_dir / f"{resource_key}.json"
        payload_path: Optional[Path] = payload_target_path
        sidecar_path = self.diagnostic_root / relative_dir / f"{resource_key}.sidecar.json"
        parseability_path = (
            self.diagnostic_root
            / relative_dir
            / f"{resource_key}.parseability.json"
        )
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
        canonical_input: CanonicalHtmlInput | None = None
        parseability: ParseabilityResult | None = None
        parseability_path.unlink(missing_ok=True)

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
                canonical_input = self.input_loader.load(
                    product_key,
                    language,
                    version_key=version_key,
                    expected_sha256=expected_input_sha256,
                )
                input_path = canonical_input.normalized_path
                parseability = self.parseability_validator.validate(canonical_input)
                evidence_contract = (
                    self.contract_validator.validate_reconstruction_parseability(
                        dict(parseability.evidence)
                    )
                )
                if not evidence_contract.passed:
                    messages = "; ".join(
                        issue.message for issue in evidence_contract.errors
                    )
                    raise RuntimeError(
                        f"Reconstruction Parseability evidence contract failure: {messages}"
                    )
                self._write_json_atomic(
                    parseability_path, dict(parseability.evidence)
                )
                if not parseability.passed or parseability.production_soup is None:
                    raise InputAssuranceError(
                        "RECONSTRUCTION_PARSEABILITY_FAILED",
                        "Independent HTML parsers materially disagree on reconstruction content",
                    )
                if strategy is not None and preselected_strategy is not None:
                    raise ValueError("Specify only one of strategy or preselected_strategy")
                selected_strategy = self._resolve_strategy(
                    preselected_strategy if preselected_strategy is not None else strategy,
                    parseability.production_soup,
                    product_key,
                    input_bytes=canonical_input.size_bytes,
                )
                strategy_metadata = self._strategy_metadata(selected_strategy)
                strategy_instance = StrategyFactory.create_strategy(selected_strategy, runtime_definition, str(input_path))
                soup = preprocess_image_paths(parseability.production_soup)
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
            structured_error = {
                "code": error.code if isinstance(error, InputAssuranceError) else type(error).__name__,
                "stage": "input_assurance" if isinstance(error, InputAssuranceError) else "extraction",
                "message": str(error),
            }

        completed = datetime.now(timezone.utc)
        duration_ms = max(0, round((time.perf_counter() - started_clock) * 1000))
        sidecar = {
            "schema_version": "1.2",
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
            "input_assurance": self._input_assurance_metadata(
                canonical_input, parseability, parseability_path
            ),
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
            return self.validate_persisted_payload(result)
        return result

    def validate_persisted_payload(
        self,
        product_key: ExtractionResult | str,
        language: str | None = None,
        payload_path: str | Path | None = None,
        sidecar_path: str | Path | None = None,
        *,
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
            sidecar.get("normalized_input", {}).get("path")
        )
        self._append_artifact_hash_issue(
            errors, sidecar.get("normalized_input"), input_file, "normalized_input"
        )
        source_file = self._artifact_path(sidecar.get("source", {}).get("path"))
        self._append_artifact_hash_issue(errors, sidecar.get("source"), source_file, "source")

        canonical_input: CanonicalHtmlInput | None = None
        parseability: ParseabilityResult | None = None
        try:
            canonical_input = self.input_loader.load(
                product_key,
                language,
                version_key=version_key,
                expected_sha256=sidecar.get("normalized_input", {}).get("sha256"),
            )
            if input_file != canonical_input.normalized_path.resolve():
                errors.append(ContractIssue(
                    "normalized_input_path_mismatch",
                    "$.normalized_input.path",
                    "Diagnostic Sidecar does not reference the canonical Normalized Input.",
                ))
            if source_file != canonical_input.source_path.resolve():
                errors.append(ContractIssue(
                    "source_path_mismatch",
                    "$.source.path",
                    "Diagnostic Sidecar does not reference the canonical Source Snapshot.",
                ))
            parseability = self.parseability_validator.validate(canonical_input)
            replay_contract = (
                self.contract_validator.validate_reconstruction_parseability(
                    dict(parseability.evidence)
                )
            )
            errors.extend(replay_contract.errors)
            if not parseability.passed or parseability.production_soup is None:
                errors.append(ContractIssue(
                    "reconstruction_parseability_failed",
                    "$.input_assurance.reconstruction_parseability",
                    "Independent HTML parsers materially disagree during replay.",
                ))
            frozen_parseability = sidecar.get("input_assurance", {}).get(
                "reconstruction_parseability"
            ) or {}
            frozen_assurance = sidecar.get("input_assurance", {})
            expected_assurance = {
                "status": "passed" if parseability.passed else "failed",
                "encoding": "utf-8-strict",
                "has_utf8_bom": canonical_input.has_utf8_bom,
                "source_normalized_byte_identical": True,
                "source_findings": [
                    finding.to_dict()
                    for finding in canonical_input.source_findings
                ],
            }
            for field, expected in expected_assurance.items():
                if frozen_assurance.get(field) != expected:
                    errors.append(ContractIssue(
                        "input_assurance_replay_mismatch",
                        f"$.input_assurance.{field}",
                        "Frozen input-assurance metadata differs from canonical replay.",
                    ))
            expected_reconstruction = {
                "verdict": parseability.evidence["verdict"],
                "input_sha256": canonical_input.normalized_sha256,
                "profile_sha256": parseability.evidence["profile"]["sha256"],
            }
            for field, expected in expected_reconstruction.items():
                if frozen_parseability.get(field) != expected:
                    errors.append(ContractIssue(
                        "parseability_replay_mismatch",
                        f"$.input_assurance.reconstruction_parseability.{field}",
                        "Frozen parseability metadata differs from canonical replay.",
                    ))
            evidence_artifact = frozen_parseability.get("evidence")
            evidence_file = self._artifact_path(
                evidence_artifact.get("path") if evidence_artifact else None
            )
            expected_evidence_file = sidecar_file.with_name(
                sidecar_file.name.removesuffix(".sidecar.json")
                + ".parseability.json"
            )
            if evidence_file != expected_evidence_file:
                errors.append(ContractIssue(
                    "parseability_evidence_path_mismatch",
                    "$.input_assurance.reconstruction_parseability.evidence.path",
                    "Parseability evidence is not at the canonical diagnostic path.",
                ))
            self._append_artifact_hash_issue(
                errors,
                evidence_artifact,
                evidence_file,
                "parseability_evidence",
            )
            if evidence_file.is_file():
                try:
                    frozen_evidence = json.loads(
                        evidence_file.read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError) as error:
                    errors.append(ContractIssue(
                        "invalid_parseability_evidence",
                        "$.input_assurance.reconstruction_parseability.evidence",
                        str(error),
                    ))
                else:
                    frozen_contract = (
                        self.contract_validator.validate_reconstruction_parseability(
                            frozen_evidence
                        )
                    )
                    errors.extend(frozen_contract.errors)
                    if parseability is not None and frozen_evidence != parseability.evidence:
                        errors.append(ContractIssue(
                            "parseability_replay_mismatch",
                            "$.input_assurance.reconstruction_parseability.evidence",
                            "Replayed parseability evidence differs from frozen evidence.",
                        ))
        except InputAssuranceError as error:
            errors.append(ContractIssue(
                error.code.lower(),
                "$.normalized_input",
                str(error),
            ))

        if payload is not None:
            expected_ms_service = None
            if (
                definition["page_model"] == "FlexibleContentPage"
                and parseability is not None
                and parseability.production_soup is not None
            ):
                expected_ms_service = self._extract_ms_service(
                    parseability.production_soup
                )
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
        soup: BeautifulSoup,
        product_key: str,
        *,
        input_bytes: int,
    ) -> ExtractionStrategy:
        configured = self.strategy_manager.determine_extraction_strategy(
            soup, product_key, input_bytes=input_bytes
        )
        if strategy is None:
            return configured
        strategy_type = (
            strategy.strategy_type
            if isinstance(strategy, ExtractionStrategy)
            else strategy if isinstance(strategy, StrategyType) else StrategyType(strategy)
        )
        if strategy_type is not configured.strategy_type:
            raise ValueError(
                "Preselected strategy differs from the Product Definition "
                f"semantic_strategy for {product_key}"
            )
        # A caller may preflight the semantic type, but it cannot substitute
        # arbitrary processor metadata or bypass the frozen Product Definition.
        return configured

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
    def _input_assurance_metadata(
        canonical_input: CanonicalHtmlInput | None,
        parseability: ParseabilityResult | None,
        evidence_path: Path,
    ) -> dict[str, Any]:
        findings = (
            [finding.to_dict() for finding in canonical_input.source_findings]
            if canonical_input is not None
            else []
        )
        reconstruction = None
        if canonical_input is not None and parseability is not None:
            reconstruction = {
                "verdict": parseability.evidence["verdict"],
                "input_sha256": canonical_input.normalized_sha256,
                "profile_sha256": parseability.evidence["profile"]["sha256"],
                "evidence": ExtractionCoordinator._artifact(evidence_path),
            }
        return {
            "status": (
                "passed"
                if canonical_input is not None
                and parseability is not None
                and parseability.passed
                else "failed"
            ),
            "encoding": "utf-8-strict",
            "has_utf8_bom": (
                canonical_input.has_utf8_bom if canonical_input is not None else None
            ),
            "source_normalized_byte_identical": (
                True if canonical_input is not None else None
            ),
            "source_findings": findings,
            "reconstruction_parseability": reconstruction,
        }

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

    def _quality_warnings(
        self, payload: dict[str, Any], definition: dict[str, Any]
    ) -> list[dict[str, str]]:
        minimum = self.validation_context.min_content_length(
            definition["product_key"]
        )
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
