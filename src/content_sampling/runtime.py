"""Pure preparation for P3 sampled content validation artifacts."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from src.content_sampling.artifacts import artifact_json_sha256
from src.content_sampling.projector import (
    PayloadContentProjector,
    ProjectionError,
    SourceContentProjector,
)
from src.content_sampling.semantic import (
    diff_document,
    semantic_fingerprint,
)
from src.content_sampling.state_sampler import build_sampling_plan
from src.core.canonical_identity import (
    sampled_content_evidence_sha256,
    validation_evidence_sha256,
)
from src.core.canonical_input import CanonicalInputLoader, InputAssuranceError
from src.core.contract_validator import ContractIssue, ContractValidator
from src.core.product_catalog import sha256_file
from src.core.product_manager import ProductManager
from src.core.reconstruction_parseability import ReconstructionParseabilityValidator
from src.core.scoped_source_content import ScopedSourceContentError
from src.core.source_html_structure import (
    SourceHtmlStructureAuditError,
    SourceHtmlStructureAuditor,
)
from src.core.source_reachability import (
    SourceReachability,
    SourceReachabilityError,
    SourceReachabilityResolver,
)
from src.core.source_state_evidence import (
    SourceStateEvidenceError,
    SourceStateEvidenceResolver,
    source_finding_warning,
)
from src.core.strict_soft_category_projection import StrictSoftCategoryProjectionError
from src.core.validation_context import (
    ValidationContextRegistry,
)
from src.pipeline.models import BatchItem
from src.review.contracts import (
    classify_source_quality_findings,
    evaluate_source_findings,
    machine_approval_preconditions,
    source_approval_preconditions,
)


INTERACTIVE_STRATEGIES = {"region_filter", "complex"}
FULL_STRATEGIES = {"simple_static", "support_article"}


@dataclass(frozen=True)
class DiffArtifact:
    relative_path: str
    value: dict[str, Any]
    sha256: str


@dataclass(frozen=True)
class PreparedSampledValidation:
    item_id: str
    status: str
    error: dict[str, str] | None
    sampling_plan: dict[str, Any] | None
    sampling_plan_path: str | None
    sampling_plan_artifact_sha256: str | None
    sampled_content_evidence: dict[str, Any]
    sampled_content_evidence_path: str
    sampled_content_evidence_artifact_sha256: str
    validation_projection: dict[str, Any]
    validation_path: str
    validation_artifact_sha256: str
    diff_artifacts: tuple[DiffArtifact, ...]


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _issues(values: list[ContractIssue] | list[dict[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for value in values:
        if isinstance(value, ContractIssue):
            result.append(value.to_dict())
        else:
            result.append(
                {
                    "code": str(value.get("code", "validation_failed")),
                    "path": str(value.get("path", "$")),
                    "message": str(value.get("message", "Validation failed")),
                }
            )
    return result


def _state_ids(states: list[Mapping[str, Any]]) -> list[str]:
    return [str(state["state_id"]) for state in states]


def _full_coverage() -> dict[str, Any]:
    return {
        "mode": "full",
        "universe_count": 1,
        "selected_count": 1,
        "untested_count": 0,
        "seed": None,
        "strata": [],
        "selected_state_ids": [],
        "assurance": "sampled_state_content_consistency",
    }


def _coverage_from_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    coverage = copy.deepcopy(dict(plan["coverage"]))
    coverage["seed"] = plan["seed"]
    coverage["strata"] = [
        str(stratum["stratum_id"]) for stratum in plan["strata"]
    ]
    coverage["selected_state_ids"] = _state_ids(plan["selected_states"])
    return coverage


def _artifact(path: str, sha256: str) -> dict[str, str]:
    return {"path": path, "sha256": sha256}


def _profile_identity(
    registry: ValidationContextRegistry,
    manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    validation_profile = dict(manifest["validation_context"]["validation_profile"])
    sampling_identity = registry.content_sampling_profile_identity_for(
        validation_profile
    )
    if sampling_identity is None:
        raise ValueError("P3 sampled validation requires a content sampling profile")
    finding_policy_identity = registry.finding_code_policy_identity_for(
        validation_profile
    )
    return validation_profile, sampling_identity, finding_policy_identity


class SampledValidationRuntime:
    """Prepare P3 artifacts without mutating run state."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.product_manager = ProductManager(str(self.root / "data" / "configs"))
        self.input_loader = CanonicalInputLoader(self.root, self.product_manager)
        self.contract_validator = ContractValidator(self.root)
        self.validation_context = ValidationContextRegistry(self.root)
        self.parseability_validator = ReconstructionParseabilityValidator()
        self.source_html_structure_auditor = SourceHtmlStructureAuditor(self.root)
        self.source_reachability = SourceReachabilityResolver(self.root)
        self.source_state_evidence = SourceStateEvidenceResolver(self.root)
        self.source_projector = SourceContentProjector(self.root)
        self.payload_projector = PayloadContentProjector()

    def prepare(
        self,
        *,
        batch_id: str,
        run_dir: Path,
        item: BatchItem,
        manifest: Mapping[str, Any],
        manifest_item: Mapping[str, Any],
    ) -> PreparedSampledValidation:
        validation_profile, sampling_profile, finding_policy_identity = _profile_identity(
            self.validation_context,
            manifest,
        )
        finding_policy = (
            self.validation_context.finding_code_policy_for(validation_profile)
            if finding_policy_identity is not None
            else None
        )
        sampling_plan: dict[str, Any] | None = None
        sampling_plan_path: str | None = None
        sampling_plan_artifact_sha256: str | None = None
        source_reachability: SourceReachability | None = None
        source_findings: list[dict[str, Any]] = []
        structure_errors: list[dict[str, str]] = []
        content_errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []

        payload_path = run_dir / item.output_path
        payload = self._read_payload(payload_path, manifest_item, content_errors)
        canonical_input = None
        parseability_ok = False
        try:
            canonical_input = self.input_loader.load(
                item.product_key,
                item.language,
                version_key=item.version_key,
                expected_sha256=item.normalized_sha256,
            )
            source_findings.extend(
                {
                    "code": finding.code,
                    "path": f"$.input_assurance.source_findings[{index}]",
                    "message": finding.message,
                }
                for index, finding in enumerate(canonical_input.source_findings)
            )
            parseability = self.parseability_validator.validate(canonical_input)
            parseability_contract = (
                self.contract_validator.validate_reconstruction_parseability(
                    dict(parseability.evidence)
                )
            )
            structure_errors.extend(_issues(parseability_contract.errors))
            parseability_ok = parseability.passed and parseability.production_soup is not None
            if not parseability_ok:
                structure_errors.append(
                    _issue(
                        "reconstruction_parseability_failed",
                        "$.input_assurance.reconstruction_parseability",
                        "Independent HTML parsers materially disagree during replay.",
                    )
                )
            audit = self.source_html_structure_auditor.audit(canonical_input)
            audit_dict = audit.to_dict()
            for finding in audit_dict["findings"]:
                target = structure_errors if finding["blocking"] else source_findings
                target.append(
                    {
                        "code": finding["code"],
                        "path": "$.input_assurance.source_html_structure",
                        "message": finding["message"],
                    }
                )
        except (InputAssuranceError, SourceHtmlStructureAuditError) as error:
            structure_errors.append(
                _issue(
                    getattr(error, "code", "input_assurance_failed"),
                    "$.normalized_input",
                    str(error),
                )
            )

        if canonical_input is not None and item.page_model == "FlexibleContentPage":
            try:
                source_reachability = self.source_reachability.resolve(canonical_input)
                if item.strategy == "complex":
                    source_reachability = (
                        self.source_reachability.attach_strict_soft_category_projections(
                            canonical_input,
                            source_reachability,
                        )
                    )
                source_empty_states = self.source_state_evidence.resolve(
                    canonical_input,
                    source_reachability=source_reachability,
                )
                source_findings.extend(
                    source_finding_warning(finding)
                    for finding in source_empty_states
                )
                source_findings.extend(
                    {
                        "code": finding.code,
                        "path": "$.expected_reachability",
                        "message": finding.message,
                    }
                    for finding in source_reachability.findings
                )
                source_findings.extend(
                    {
                        "code": "non_materialized_aggregate_tab_suppressed",
                        "path": "$.pageConfig.filtersJsonConfig",
                        "message": (
                            "Source aggregate option "
                            f"{option.label!r} ({option.href}) has no target panel "
                            "and was omitted from the reachable relation."
                        ),
                    }
                    for option in source_reachability.suppressed_options
                )
                if payload is not None and parseability_ok:
                    contract = self.contract_validator.validate(
                        payload,
                        item.page_model,
                        expected_semantic_strategy=item.strategy,
                        expected_reachability=source_reachability.to_expected_reachability(),
                        expected_base_content=(
                            self.payload_projector.page_global(
                                self.source_projector.project_payload(
                                    product_key=item.product_key,
                                    language=item.language,
                                    version_key=item.version_key,
                                    canonical_input=canonical_input,
                                    strategy=item.strategy,
                                    source_reachability=source_reachability,
                                ),
                                item.strategy,
                            ).get("baseContent")
                        ),
                        source_confirmed_empty_states=tuple(
                            finding.to_cms_state() for finding in source_empty_states
                        ),
                    )
                    structure_errors.extend(_issues(contract.errors))
                    warnings.extend(_issues(contract.warnings))
            except (
                SourceReachabilityError,
                SourceStateEvidenceError,
                StrictSoftCategoryProjectionError,
                ScopedSourceContentError,
                ProjectionError,
            ) as error:
                structure_errors.append(
                    _issue(
                        getattr(error, "code", "source_projection_failed"),
                        "$.expected_reachability",
                        str(error),
                    )
                )
        elif canonical_input is not None and payload is not None and parseability_ok:
            definition = self.product_manager.get_product_config(item.product_key)
            contract = self.contract_validator.validate(
                payload,
                definition["page_model"],
                expected_semantic_strategy=item.strategy,
            )
            structure_errors.extend(_issues(contract.errors))
            warnings.extend(_issues(contract.warnings))

        if item.strategy in INTERACTIVE_STRATEGIES:
            if source_reachability is None:
                raise ProjectionError(
                    "P3 interactive validation cannot derive Sampling Plan "
                    "without source reachability"
                )
            sampling_plan = build_sampling_plan(
                item_id=item.item_id,
                strategy=item.strategy,
                source_sha256=str(item.source_sha256),
                source_reachability=source_reachability,
                content_sampling_profile=sampling_profile,
            )
            sampling_plan_path = manifest_item["artifacts"]["sampling_plan"]["path"]
            sampling_plan_artifact_sha256 = artifact_json_sha256(sampling_plan)

        plan_binding = (
            {
                "path": str(sampling_plan_path),
                "artifact_sha256": str(sampling_plan_artifact_sha256),
                "plan_sha256": str(sampling_plan["plan_sha256"]),
            }
            if sampling_plan is not None
            else None
        )
        sampled_bindings = {
            "source": _artifact(str(item.source_path), str(item.source_sha256)),
            "normalized_input": _artifact(
                item.normalized_path,
                str(item.normalized_sha256),
            ),
            "payload": dict(manifest_item["artifacts"]["payload"]),
            "soft_category": dict(manifest["frozen_inputs"]["soft_category"]),
            "validation_profile": validation_profile,
            "content_sampling_profile": sampling_profile,
            "sampling_plan": plan_binding,
        }
        validation_bindings = copy.deepcopy(sampled_bindings)
        if finding_policy_identity is not None:
            validation_bindings["finding_code_policy_identity"] = (
                finding_policy_identity
            )

        coverage = (
            _coverage_from_plan(sampling_plan)
            if sampling_plan is not None
            else _full_coverage()
        )
        diff_base = item.validation_path.removesuffix(".validation.json")
        comparisons, diffs = self._compare_content(
            item=item,
            canonical_input=canonical_input,
            payload=payload,
            source_reachability=source_reachability,
            sampling_plan=sampling_plan,
            diff_base=diff_base,
            content_errors=content_errors,
        )
        evidence_errors = [*structure_errors, *content_errors]
        content_status = "failed" if content_errors else "passed"
        structure_status = "failed" if structure_errors else "passed"
        evidence = {
            "schema_version": "1.0",
            "evidence_sha256": "0" * 64,
            "item_id": item.item_id,
            "mode": coverage["mode"],
            "bindings": sampled_bindings,
            "coverage": coverage,
            "structure_validation": {
                "status": structure_status,
                "universe_count": coverage["universe_count"],
                "checked_count": (
                    coverage["universe_count"] if not structure_errors else 0
                ),
                "errors": structure_errors,
            },
            "page_global_comparison": comparisons["page_global"],
            "full_content_comparison": comparisons["full_content"],
            "samples": comparisons["samples"],
            "errors": evidence_errors,
            "warnings": warnings,
        }
        evidence["evidence_sha256"] = sampled_content_evidence_sha256(evidence)
        evidence_path = manifest_item["artifacts"]["sampled_content_evidence"]["path"]
        evidence_artifact_sha256 = artifact_json_sha256(evidence)
        source_quality_findings = self._source_quality_findings(source_findings)
        source_preconditions = source_approval_preconditions(
            source_quality_findings
        )
        validation_schema_version = "2.0"
        if finding_policy is not None:
            source_quality_findings = classify_source_quality_findings(
                source_quality_findings,
                finding_policy,
            )
            source_preconditions = evaluate_source_findings(
                source_quality_findings,
                finding_policy,
            )
            validation_schema_version = "2.1"
        validation_status = (
            "failed"
            if structure_status == "failed" or content_status == "failed"
            else "passed"
        )
        validation = {
            "schema_version": validation_schema_version,
            "batch_id": batch_id,
            "item_id": item.item_id,
            "status": validation_status,
            "evidence_sha256": "0" * 64,
            "evidence": {
                "verdict": validation_status,
                "bindings": validation_bindings,
                "structure_validation": {
                    "status": structure_status,
                    "checked_count": (
                        coverage["universe_count"] if not structure_errors else 0
                    ),
                    "total_count": coverage["universe_count"],
                },
                "content_validation": {
                    "status": content_status,
                    "sampled_content_evidence": {
                        "path": evidence_path,
                        "artifact_sha256": evidence_artifact_sha256,
                        "evidence_sha256": evidence["evidence_sha256"],
                    },
                    "coverage": coverage,
                    "claim": "sampled_state_content_consistency",
                },
                "source_quality_findings": source_quality_findings,
                "approval_preconditions": {
                    "machine": machine_approval_preconditions(
                        "succeeded",
                        validation_status,
                    ).to_dict(),
                    "source": source_preconditions.to_dict(),
                },
                "errors": evidence_errors,
                "warnings": warnings,
            },
        }
        validation["evidence_sha256"] = validation_evidence_sha256(validation)
        validation_artifact_sha256 = artifact_json_sha256(validation)
        first_error = evidence_errors[0] if evidence_errors else None
        return PreparedSampledValidation(
            item_id=item.item_id,
            status=validation_status,
            error=(
                {
                    "code": first_error["code"],
                    "stage": "validate",
                    "message": first_error["message"],
                }
                if first_error
                else None
            ),
            sampling_plan=sampling_plan,
            sampling_plan_path=sampling_plan_path,
            sampling_plan_artifact_sha256=sampling_plan_artifact_sha256,
            sampled_content_evidence=evidence,
            sampled_content_evidence_path=evidence_path,
            sampled_content_evidence_artifact_sha256=evidence_artifact_sha256,
            validation_projection=validation,
            validation_path=item.validation_path,
            validation_artifact_sha256=validation_artifact_sha256,
            diff_artifacts=tuple(diffs),
        )

    @staticmethod
    def _read_payload(
        payload_path: Path,
        manifest_item: Mapping[str, Any],
        content_errors: list[dict[str, str]],
    ) -> dict[str, Any] | None:
        expected_sha256 = manifest_item["artifacts"]["payload"]["sha256"]
        if not payload_path.is_file():
            content_errors.append(
                _issue("payload_missing", "$.payload.path", f"Payload does not exist: {payload_path}")
            )
            return None
        if expected_sha256 and sha256_file(payload_path) != expected_sha256:
            content_errors.append(
                _issue(
                    "payload_hash_mismatch",
                    "$.payload.sha256",
                    "Persisted payload SHA-256 does not match the frozen extraction hash.",
                )
            )
            return None
        try:
            value = json.loads(payload_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            content_errors.append(_issue("invalid_payload_json", "$", str(error)))
            return None
        if not isinstance(value, dict):
            content_errors.append(
                _issue("invalid_payload_json", "$", "Business Payload must be a JSON object")
            )
            return None
        return value

    def _compare_content(
        self,
        *,
        item: BatchItem,
        canonical_input: Any,
        payload: dict[str, Any] | None,
        source_reachability: SourceReachability | None,
        sampling_plan: Mapping[str, Any] | None,
        diff_base: str,
        content_errors: list[dict[str, str]],
    ) -> tuple[dict[str, Any], list[DiffArtifact]]:
        diffs: list[DiffArtifact] = []
        failed = {
            "status": "failed",
            "source_fingerprint": None,
            "payload_fingerprint": None,
            "diff_reference": None,
        }
        if canonical_input is None or payload is None:
            return {
                "page_global": dict(failed),
                "full_content": dict(failed) if item.strategy in FULL_STRATEGIES else None,
                "samples": [
                    {
                        "state": copy.deepcopy(state),
                        "source_fingerprint": None,
                        "payload_fingerprint": None,
                        "status": "failed",
                        "diff_reference": None,
                    }
                    for state in (sampling_plan or {}).get("selected_states", [])
                ],
            }, diffs
        try:
            source_payload = self.source_projector.project_payload(
                product_key=item.product_key,
                language=item.language,
                version_key=item.version_key,
                canonical_input=canonical_input,
                strategy=item.strategy,
                source_reachability=source_reachability,
            )
        except (ProjectionError, ValueError) as error:
            content_errors.append(
                _issue(
                    "source_content_projection_failed",
                    "$.source",
                    str(error),
                )
            )
            return {
                "page_global": dict(failed),
                "full_content": dict(failed) if item.strategy in FULL_STRATEGIES else None,
                "samples": [
                    {
                        "state": copy.deepcopy(state),
                        "source_fingerprint": None,
                        "payload_fingerprint": None,
                        "status": "failed",
                        "diff_reference": None,
                    }
                    for state in (sampling_plan or {}).get("selected_states", [])
                ],
            }, diffs

        page_global = self._comparison(
            scope="page-global",
            diff_path=f"{diff_base}.content-diffs/page-global.json",
            source_value=self.payload_projector.page_global(source_payload, item.strategy),
            payload_value=self.payload_projector.page_global(payload, item.strategy),
            error_code="page_global_content_mismatch",
            error_path="$.page_global_comparison",
            content_errors=content_errors,
            diffs=diffs,
        )
        full_content = None
        if item.strategy in FULL_STRATEGIES:
            full_content = self._comparison(
                scope="full-content",
                diff_path=f"{diff_base}.content-diffs/full-content.json",
                source_value=self.payload_projector.full_content(source_payload, item.strategy),
                payload_value=self.payload_projector.full_content(payload, item.strategy),
                error_code="full_content_mismatch",
                error_path="$.full_content_comparison",
                content_errors=content_errors,
                diffs=diffs,
            )
        samples = []
        for state in (sampling_plan or {}).get("selected_states", []):
            try:
                sample = self._comparison(
                    scope=f"state:{state['state_id']}",
                    diff_path=(
                        f"{diff_base}.content-diffs/state-{state['state_id']}.json"
                    ),
                    source_value=self.payload_projector.state_content(source_payload, state),
                    payload_value=self.payload_projector.state_content(payload, state),
                    error_code="sampled_state_content_mismatch",
                    error_path=f"$.samples[{len(samples)}]",
                    content_errors=content_errors,
                    diffs=diffs,
                )
                sample["state"] = copy.deepcopy(dict(state))
            except ProjectionError as error:
                content_errors.append(
                    _issue(
                        "selected_state_evaluation_failed",
                        f"$.samples[{len(samples)}]",
                        str(error),
                    )
                )
                sample = {
                    "state": copy.deepcopy(dict(state)),
                    "source_fingerprint": None,
                    "payload_fingerprint": None,
                    "status": "failed",
                    "diff_reference": None,
                }
            samples.append(sample)
        return {
            "page_global": page_global,
            "full_content": full_content,
            "samples": samples,
        }, diffs

    @staticmethod
    def _comparison(
        *,
        scope: str,
        diff_path: str,
        source_value: Any,
        payload_value: Any,
        error_code: str,
        error_path: str,
        content_errors: list[dict[str, str]],
        diffs: list[DiffArtifact],
    ) -> dict[str, Any]:
        source_fingerprint = semantic_fingerprint(source_value)
        payload_fingerprint = semantic_fingerprint(payload_value)
        if source_fingerprint == payload_fingerprint:
            return {
                "status": "matched",
                "source_fingerprint": source_fingerprint,
                "payload_fingerprint": payload_fingerprint,
                "diff_reference": None,
            }
        diff_value = diff_document(
            scope=scope,
            source_value=source_value,
            payload_value=payload_value,
            source_fingerprint=source_fingerprint,
            payload_fingerprint=payload_fingerprint,
        )
        diff_sha256 = artifact_json_sha256(diff_value)
        diffs.append(DiffArtifact(diff_path, diff_value, diff_sha256))
        content_errors.append(
            _issue(error_code, error_path, f"{scope} content differs from Source projection")
        )
        return {
            "status": "mismatched",
            "source_fingerprint": source_fingerprint,
            "payload_fingerprint": payload_fingerprint,
            "diff_reference": {"path": diff_path, "sha256": diff_sha256},
        }

    @staticmethod
    def _source_quality_findings(
        findings: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for finding in findings:
            code = str(finding.get("code", "source_quality_finding"))
            message = str(finding.get("message", code))
            path = str(finding.get("path", "$.source"))
            candidate = {
                "code": code,
                "message": message,
                "path": path,
                "severity": "finding",
                "disposition": "unresolved",
            }
            if candidate not in result:
                result.append(candidate)
        return result
