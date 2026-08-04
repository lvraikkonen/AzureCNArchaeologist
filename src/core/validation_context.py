"""Frozen v0.4 planning and validation context identities.

New batches bind the exact baseline/profile/map bytes that governed planning.
Historical replay verifies those frozen references instead of silently loading
whatever configuration happens to be current later.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from src.core.product_catalog import sha256_file


class ValidationContextError(RuntimeError):
    """A frozen planning/profile identity is missing, invalid, or drifted."""


@dataclass(frozen=True)
class _ArtifactSpec:
    key: str
    identifier_field: str
    relative_path: str
    schema_path: str


@dataclass(frozen=True)
class _ContractArtifactSpec:
    name: str
    schema_version: str
    relative_path: str


P1_PLANNING_BASELINE_SPEC = _ArtifactSpec(
    "planning_baseline",
    "baseline_id",
    "data/baselines/v0.4/planning-baseline.json",
    "schemas/planning-baseline-manifest-1.0.schema.json",
)
P2_PLANNING_BASELINE_SPEC = _ArtifactSpec(
    "planning_baseline",
    "baseline_id",
    "data/baselines/v0.4/p2-product-definition-identity-overlay.json",
    "schemas/planning-baseline-identity-overlay-1.0.schema.json",
)
P1_VALIDATION_PROFILE_SPEC = _ArtifactSpec(
    "validation_profile",
    "profile_id",
    "data/configs/validation-profiles/v0.4.json",
    "schemas/validation-profile-1.0.schema.json",
)
P2_VALIDATION_PROFILE_SPEC = _ArtifactSpec(
    "validation_profile",
    "profile_id",
    "data/configs/validation-profiles/v0.4-p2.json",
    "schemas/validation-profile-1.1.schema.json",
)
CONTENT_SAMPLING_PROFILE_SPEC = _ArtifactSpec(
    "content_sampling_profile",
    "profile_id",
    "data/configs/content-sampling-profiles/v0.4-p3.json",
    "schemas/content-sampling-profile-1.0.schema.json",
)
P3_VALIDATION_PROFILE_SPEC = _ArtifactSpec(
    "validation_profile",
    "profile_id",
    "data/configs/validation-profiles/v0.4-p3.json",
    "schemas/validation-profile-1.2.schema.json",
)
P3_SUCCESSOR_VALIDATION_PROFILE_SPEC = _ArtifactSpec(
    "validation_profile",
    "profile_id",
    "data/configs/validation-profiles/v0.4-p3-successor.json",
    "schemas/validation-profile-1.3.schema.json",
)
FINDING_CODE_POLICY_SPEC = _ArtifactSpec(
    "finding_code_policy",
    "policy_id",
    "data/configs/finding-code-policies/v0.4-p4.json",
    "schemas/finding-code-policy-1.0.schema.json",
)
ACTIVE_VALIDATION_PROFILE_SPEC = P3_SUCCESSOR_VALIDATION_PROFILE_SPEC
NON_PROFILE_CONTEXT_ARTIFACT_SPECS = (
    _ArtifactSpec(
        "applicability_map",
        "map_id",
        "data/configs/applicability-maps/v0.4-p1-registry.json",
        "schemas/applicability-map-1.0.schema.json",
    ),
    _ArtifactSpec(
        "rendering_profile",
        "profile_id",
        "data/configs/rendering-profiles/desktop-v0.4-p1.json",
        "schemas/rendering-profile-1.0.schema.json",
    ),
    _ArtifactSpec(
        "in_memory_capability_profile",
        "profile_id",
        "data/configs/capability-profiles/in-memory-v0.4.json",
        "schemas/in-memory-capability-profile-1.0.schema.json",
    ),
)
CONTEXT_ARTIFACT_SPECS = (
    ACTIVE_VALIDATION_PROFILE_SPEC,
    *NON_PROFILE_CONTEXT_ARTIFACT_SPECS,
)
ARTIFACT_SPECS = (
    P1_PLANNING_BASELINE_SPEC,
    P2_PLANNING_BASELINE_SPEC,
    P1_VALIDATION_PROFILE_SPEC,
    P2_VALIDATION_PROFILE_SPEC,
    P3_VALIDATION_PROFILE_SPEC,
    P3_SUCCESSOR_VALIDATION_PROFILE_SPEC,
    CONTENT_SAMPLING_PROFILE_SPEC,
    FINDING_CODE_POLICY_SPEC,
    *NON_PROFILE_CONTEXT_ARTIFACT_SPECS,
)
SPECS_BY_KEY = {spec.key: spec for spec in CONTEXT_ARTIFACT_SPECS}
SPECS_BY_KEY["planning_baseline"] = P2_PLANNING_BASELINE_SPEC
SPECS_BY_KEY["content_sampling_profile"] = CONTENT_SAMPLING_PROFILE_SPEC
SPECS_BY_KEY["finding_code_policy"] = FINDING_CODE_POLICY_SPEC

P1_PLANNING_IDENTITY = (
    "v0.4-from-v0.3",
    "1.0",
    P1_PLANNING_BASELINE_SPEC.relative_path,
)
P2_PLANNING_IDENTITY = (
    "v0.4-p2-product-definition-identity-overlay",
    "1.0",
    P2_PLANNING_BASELINE_SPEC.relative_path,
)
P1_VALIDATION_PROFILE_IDENTITY = (
    "v0.4-validation-p1",
    "1.0",
    P1_VALIDATION_PROFILE_SPEC.relative_path,
)
P2_VALIDATION_PROFILE_IDENTITY = (
    "v0.4-validation-p2",
    "1.1",
    P2_VALIDATION_PROFILE_SPEC.relative_path,
)
P3_VALIDATION_PROFILE_IDENTITY = (
    "v0.4-validation-p3",
    "1.2",
    P3_VALIDATION_PROFILE_SPEC.relative_path,
)
P3_SUCCESSOR_VALIDATION_PROFILE_IDENTITY = (
    "v0.4-validation-p3-successor",
    "1.3",
    P3_SUCCESSOR_VALIDATION_PROFILE_SPEC.relative_path,
)
CONTENT_SAMPLING_PROFILE_IDENTITY = (
    "v0.4-content-sampling-p3",
    "1.0",
    CONTENT_SAMPLING_PROFILE_SPEC.relative_path,
)
FINDING_CODE_POLICY_IDENTITY = (
    "v0.4-finding-code-policy-p4",
    "1.0",
    FINDING_CODE_POLICY_SPEC.relative_path,
)
P3_VALIDATION_CONTRACT_SPECS = (
    _ContractArtifactSpec(
        "product_definition",
        "1.1",
        "schemas/product-definition-1.1.schema.json",
    ),
    _ContractArtifactSpec(
        "flexible_content",
        "1.1",
        "schemas/flexible-content-page-1.1.schema.json",
    ),
    _ContractArtifactSpec(
        "support_article",
        "1.0",
        "schemas/support-article-page-1.0.schema.json",
    ),
    _ContractArtifactSpec(
        "diagnostic_sidecar",
        "1.2",
        "schemas/diagnostic-sidecar-1.2.schema.json",
    ),
    _ContractArtifactSpec(
        "source_html_structure_audit",
        "1.0",
        "schemas/source-html-structure-audit-1.0.schema.json",
    ),
    _ContractArtifactSpec(
        "content_sampling_profile",
        "1.0",
        "schemas/content-sampling-profile-1.0.schema.json",
    ),
    _ContractArtifactSpec(
        "pipeline_validation",
        "2.0",
        "schemas/pipeline-validation-2.0.schema.json",
    ),
    _ContractArtifactSpec(
        "batch_item_sampling_plan",
        "1.0",
        "schemas/batch-item-sampling-plan-1.0.schema.json",
    ),
    _ContractArtifactSpec(
        "sampled_content_evidence",
        "1.0",
        "schemas/sampled-content-evidence-1.0.schema.json",
    ),
)
P3_SUCCESSOR_VALIDATION_CONTRACT_SPECS = (
    *tuple(
        _ContractArtifactSpec(
            specification.name,
            "2.1" if specification.name == "pipeline_validation" else specification.schema_version,
            "schemas/pipeline-validation-2.1.schema.json"
            if specification.name == "pipeline_validation"
            else specification.relative_path,
        )
        for specification in P3_VALIDATION_CONTRACT_SPECS
    ),
    _ContractArtifactSpec(
        "finding_code_policy",
        "1.0",
        "schemas/finding-code-policy-1.0.schema.json",
    ),
)
P2_AMENDED_ITEM_IDS = (
    "en-us/cloud-services",
    "en-us/service-bus",
    "zh-cn/cloud-services",
    "zh-cn/service-bus",
)


class ValidationContextRegistry:
    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()
        # Validation is reusable only while both the artifact bytes and the
        # schema bytes are unchanged.  Every access still hashes both files,
        # so a warm cache cannot conceal on-disk drift.
        self._documents: dict[
            tuple[str, str], tuple[str, str, dict[str, Any]]
        ] = {}

    def freeze(
        self,
        *,
        validation_profile_id: str | None = None,
    ) -> dict[str, Any]:
        """Freeze the active context, or an explicitly requested profile.

        Historical P1/P2 replay remains available by explicit selector even
        after the active default advances to P3.
        """

        baseline_identity = self._identity(P2_PLANNING_BASELINE_SPEC)
        baseline = self._effective_planning_baseline(
            P2_PLANNING_BASELINE_SPEC
        )
        validation_profile_spec = self._validation_profile_spec_for_id(
            validation_profile_id
        )
        context_specs = (
            validation_profile_spec,
            *NON_PROFILE_CONTEXT_ARTIFACT_SPECS,
        )
        identities = {
            spec.key: self._identity(spec)
            for spec in context_specs
        }
        if validation_profile_spec in (
            P3_VALIDATION_PROFILE_SPEC,
            P3_SUCCESSOR_VALIDATION_PROFILE_SPEC,
        ):
            self._verify_p3_family_profile(
                self._validated_document(validation_profile_spec)[0]
            )
        return {
            "planning": {
                "baseline": baseline_identity,
                "baseline_accounting": dict(baseline["accounting"]),
            },
            "validation_context": identities,
        }

    def verify_frozen(
        self,
        planning: Mapping[str, Any],
        validation_context: Mapping[str, Any],
    ) -> None:
        if set(planning) != {"baseline", "baseline_accounting"}:
            raise ValidationContextError(
                f"Frozen planning keys differ: {sorted(planning)}"
            )
        expected_keys = {
            "validation_profile",
            "applicability_map",
            "rendering_profile",
            "in_memory_capability_profile",
        }
        if set(validation_context) != expected_keys:
            raise ValidationContextError(
                f"Frozen validation context keys differ: {sorted(validation_context)}"
            )
        baseline_identity = planning.get("baseline")
        if not isinstance(baseline_identity, Mapping):
            raise ValidationContextError("Frozen planning baseline identity is missing")
        baseline_spec = self._planning_spec_for_identity(baseline_identity)
        baseline_document = self._verify_identity(
            baseline_spec, baseline_identity
        )
        baseline = self._effective_planning_baseline(
            baseline_spec, document=baseline_document
        )
        for key in sorted(expected_keys):
            identity = validation_context[key]
            if not isinstance(identity, Mapping):
                raise ValidationContextError(f"Frozen identity is invalid: {key}")
            context_spec = self._context_spec_for_identity(key, identity)
            document = self._verify_identity(context_spec, identity)
            if context_spec in (
                P3_VALIDATION_PROFILE_SPEC,
                P3_SUCCESSOR_VALIDATION_PROFILE_SPEC,
            ):
                self._verify_p3_family_profile(document)
        if dict(planning.get("baseline_accounting", {})) != baseline["accounting"]:
            raise ValidationContextError("Frozen baseline accounting does not match its artifact")

    def document(self, key: str) -> dict[str, Any]:
        if key == "planning_baseline":
            return self._effective_planning_baseline(
                P2_PLANNING_BASELINE_SPEC
            )
        if key not in SPECS_BY_KEY:
            raise ValidationContextError(f"Unknown validation context artifact: {key}")
        value, _ = self._validated_document(SPECS_BY_KEY[key])
        return copy.deepcopy(value)

    def document_for_identity(
        self,
        key: str,
        identity: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Resolve one registered frozen artifact without using active defaults."""

        spec = self._context_spec_for_identity(key, identity)
        value = self._verify_identity(spec, identity)
        if spec in (
            P3_VALIDATION_PROFILE_SPEC,
            P3_SUCCESSOR_VALIDATION_PROFILE_SPEC,
        ):
            self._verify_p3_family_profile(value)
        return copy.deepcopy(value)

    def content_sampling_profile_for(
        self,
        validation_profile_identity: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Return P3's nested sampling profile; P1/P2 have no such contract."""

        spec = self._context_spec_for_identity(
            "validation_profile", validation_profile_identity
        )
        profile = self._verify_identity(spec, validation_profile_identity)
        if spec not in (
            P3_VALIDATION_PROFILE_SPEC,
            P3_SUCCESSOR_VALIDATION_PROFILE_SPEC,
        ):
            return None
        return copy.deepcopy(self._verify_p3_family_profile(profile))

    def content_sampling_profile_identity_for(
        self,
        validation_profile_identity: Mapping[str, Any],
    ) -> dict[str, str] | None:
        """Return the frozen Content Sampling Profile identity for P3."""

        profile = self.content_sampling_profile_for(validation_profile_identity)
        if profile is None:
            return None
        return {
            "id": str(profile["profile_id"]),
            "schema_version": str(profile["schema_version"]),
            "path": CONTENT_SAMPLING_PROFILE_SPEC.relative_path,
            "sha256": str(self._identity(CONTENT_SAMPLING_PROFILE_SPEC)["sha256"]),
        }

    def finding_code_policy_for(
        self,
        validation_profile_identity: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Return the successor profile's frozen Finding Code Policy."""

        spec = self._context_spec_for_identity(
            "validation_profile", validation_profile_identity
        )
        profile = self._verify_identity(spec, validation_profile_identity)
        if spec != P3_SUCCESSOR_VALIDATION_PROFILE_SPEC:
            return None
        self._verify_p3_family_profile(profile)
        identity = profile["finding_code_policy_identity"]
        return copy.deepcopy(self._verify_identity(FINDING_CODE_POLICY_SPEC, identity))

    def finding_code_policy_identity_for(
        self,
        validation_profile_identity: Mapping[str, Any],
    ) -> dict[str, str] | None:
        """Return the frozen Finding Code Policy identity for successor P3."""

        policy = self.finding_code_policy_for(validation_profile_identity)
        if policy is None:
            return None
        return {
            "id": str(policy["policy_id"]),
            "schema_version": str(policy["schema_version"]),
            "path": FINDING_CODE_POLICY_SPEC.relative_path,
            "sha256": str(self._identity(FINDING_CODE_POLICY_SPEC)["sha256"]),
        }

    def effective_planning_baseline(self) -> dict[str, Any]:
        """Return the current approved baseline after applying its overlay."""
        return self._effective_planning_baseline(
            P2_PLANNING_BASELINE_SPEC
        )

    @property
    def max_input_bytes(self) -> int:
        return int(
            self.document("in_memory_capability_profile")[
                "max_normalized_input_bytes"
            ]
        )

    def min_content_length(self, product_key: str) -> int:
        values = self.document("validation_profile")[
            "min_content_length_by_product"
        ]
        try:
            return int(values[product_key])
        except KeyError as error:
            raise ValidationContextError(
                f"Validation Profile has no content threshold for {product_key}"
            ) from error

    def assert_plan_matches_baseline(self, plan: Any) -> None:
        baseline = self.document("planning_baseline")
        indexed = {item["item_id"]: item for item in baseline["items"]}
        errors: list[str] = []
        current_item_ids = [item.item_id for item in plan.items]
        current_ids = set(current_item_ids)
        baseline_ids = set(indexed)
        if len(current_item_ids) != len(current_ids):
            errors.append("current plan contains duplicate item_id values")
        if plan.scope.get("kind") == "all":
            selected_languages = set(plan.languages)
            expected_ids = {
                item["item_id"]
                for item in baseline["items"]
                if item["identity"]["language"] in selected_languages
            }
            for item_id in sorted(expected_ids - current_ids):
                errors.append(f"{item_id}: missing from current plan")
        for item_id in sorted(current_ids - baseline_ids):
            errors.append(f"{item_id}: absent from v0.4 Planning Baseline")
        for item in plan.items:
            frozen = indexed.get(item.item_id)
            if frozen is None:
                continue
            current_state = (
                "runnable"
                if item.runnable
                else str(item.skip_reason["code"]).lower()
            )
            expected_state = frozen["v03_state"]
            if current_state != expected_state:
                errors.append(
                    f"{item.item_id}: baseline={expected_state}, current={current_state}"
                )
            if item.strategy != frozen["semantic_strategy"]:
                errors.append(
                    f"{item.item_id}: strategy baseline={frozen['semantic_strategy']}, "
                    f"current={item.strategy}"
                )
            current_source = (
                {
                    "path": item.source_path,
                    "sha256": item.source_sha256,
                }
                if item.source_path is not None and item.source_sha256 is not None
                else None
            )
            current_normalized = (
                {
                    "path": item.normalized_path,
                    "sha256": item.normalized_sha256,
                }
                if (
                    frozen["normalized_input"] is not None
                    and item.normalized_sha256 is not None
                )
                else None
            )
            current_definition = {
                "path": item.config_path,
                "sha256": item.config_sha256,
            }
            for label, current, expected in (
                ("source", current_source, frozen["source"]),
                ("normalized input", current_normalized, frozen["normalized_input"]),
                ("Product Definition", current_definition, frozen["product_definition"]),
            ):
                if current != expected:
                    errors.append(f"{item.item_id}: {label} identity drifted")
            if (
                item.product_key != frozen["product_key"]
                or item.resource_kind != frozen["resource_kind"]
            ):
                errors.append(f"{item.item_id}: resource identity drifted")
        if errors:
            raise ValidationContextError(
                "Plan differs from the reviewed v0.4 Planning Baseline:\n- "
                + "\n- ".join(errors)
            )

    def capability_delta_proposals(self, plan: Any) -> list[dict[str, Any]]:
        proposals: list[dict[str, Any]] = []
        limit = self.max_input_bytes
        profile_identity = self._identity(
            SPECS_BY_KEY["in_memory_capability_profile"]
        )
        for item in plan.items:
            if not item.runnable or item.source_path is None:
                continue
            source = self._safe_file(item.source_path)
            size = source.stat().st_size
            if size <= limit:
                continue
            proposals.append({
                "item_id": item.item_id,
                "prior_state": "runnable",
                "proposed_state": "planned_non_runnable",
                "reason_code": "input_exceeds_in_memory_profile",
                "evidence": {
                    "source_bytes": size,
                    "profile_max_input_bytes": limit,
                    "source_sha256": sha256_file(source),
                    "profile_sha256": profile_identity["sha256"],
                },
                "review_status": "proposed",
                "capability_decision": None,
            })
        return proposals

    def _identity(self, spec: _ArtifactSpec) -> dict[str, str]:
        document, artifact_sha256 = self._validated_document(spec)
        return {
            "id": str(document[spec.identifier_field]),
            "schema_version": str(document["schema_version"]),
            "path": spec.relative_path,
            "sha256": artifact_sha256,
        }

    def _verify_identity(
        self, spec: _ArtifactSpec, identity: Mapping[str, Any]
    ) -> dict[str, Any]:
        if set(identity) != {"id", "schema_version", "path", "sha256"}:
            raise ValidationContextError(f"Frozen {spec.key} identity is not closed-world")
        path_value = identity.get("path")
        if not isinstance(path_value, str):
            raise ValidationContextError(f"Frozen {spec.key} path is invalid")
        if path_value != spec.relative_path:
            raise ValidationContextError(
                f"Frozen {spec.key} path differs from its closed-world registry path"
            )
        value, _ = self._validated_document(
            spec, expected_sha256=identity.get("sha256")
        )
        if value.get(spec.identifier_field) != identity.get("id"):
            raise ValidationContextError(f"Frozen {spec.key} id drifted")
        if value.get("schema_version") != identity.get("schema_version"):
            raise ValidationContextError(f"Frozen {spec.key} schema version drifted")
        return value

    @staticmethod
    def _planning_spec_for_identity(
        identity: Mapping[str, Any],
    ) -> _ArtifactSpec:
        if set(identity) != {"id", "schema_version", "path", "sha256"}:
            raise ValidationContextError(
                "Frozen planning_baseline identity is not closed-world"
            )
        discriminator = (
            identity.get("id"),
            identity.get("schema_version"),
            identity.get("path"),
        )
        if discriminator == P1_PLANNING_IDENTITY:
            return P1_PLANNING_BASELINE_SPEC
        if discriminator == P2_PLANNING_IDENTITY:
            return P2_PLANNING_BASELINE_SPEC
        raise ValidationContextError(
            "Frozen planning_baseline identity is not in the closed-world registry"
        )

    @staticmethod
    def _context_spec_for_identity(
        key: str,
        identity: Mapping[str, Any],
    ) -> _ArtifactSpec:
        if key != "validation_profile":
            return SPECS_BY_KEY[key]
        if set(identity) != {"id", "schema_version", "path", "sha256"}:
            raise ValidationContextError(
                "Frozen validation_profile identity is not closed-world"
            )
        discriminator = (
            identity.get("id"),
            identity.get("schema_version"),
            identity.get("path"),
        )
        if discriminator == P1_VALIDATION_PROFILE_IDENTITY:
            return P1_VALIDATION_PROFILE_SPEC
        if discriminator == P2_VALIDATION_PROFILE_IDENTITY:
            return P2_VALIDATION_PROFILE_SPEC
        if discriminator == P3_VALIDATION_PROFILE_IDENTITY:
            return P3_VALIDATION_PROFILE_SPEC
        if discriminator == P3_SUCCESSOR_VALIDATION_PROFILE_IDENTITY:
            return P3_SUCCESSOR_VALIDATION_PROFILE_SPEC
        raise ValidationContextError(
            "Frozen validation_profile identity is not in the closed-world registry"
        )

    @staticmethod
    def _validation_profile_spec_for_id(
        profile_id: str | None,
    ) -> _ArtifactSpec:
        if profile_id is None:
            return ACTIVE_VALIDATION_PROFILE_SPEC
        specifications = {
            P1_VALIDATION_PROFILE_IDENTITY[0]: P1_VALIDATION_PROFILE_SPEC,
            P2_VALIDATION_PROFILE_IDENTITY[0]: P2_VALIDATION_PROFILE_SPEC,
            P3_VALIDATION_PROFILE_IDENTITY[0]: P3_VALIDATION_PROFILE_SPEC,
            P3_SUCCESSOR_VALIDATION_PROFILE_IDENTITY[0]: (
                P3_SUCCESSOR_VALIDATION_PROFILE_SPEC
            ),
        }
        try:
            return specifications[profile_id]
        except KeyError as error:
            raise ValidationContextError(
                f"Unknown Validation Profile id: {profile_id}"
            ) from error

    def _verify_p3_family_profile(
        self,
        validation_profile: Mapping[str, Any],
    ) -> dict[str, Any]:
        if validation_profile.get("profile_id") == P3_SUCCESSOR_VALIDATION_PROFILE_IDENTITY[0]:
            return self._verify_p3_successor_profile(validation_profile)
        base_identity = validation_profile.get("base_profile")
        if not isinstance(base_identity, Mapping):
            raise ValidationContextError(
                "P3 Validation Profile has no P2 base identity"
            )
        base_spec = self._context_spec_for_identity(
            "validation_profile", base_identity
        )
        if base_spec != P2_VALIDATION_PROFILE_SPEC:
            raise ValidationContextError(
                "P3 Validation Profile must directly bind the frozen P2 profile"
            )
        self._verify_identity(base_spec, base_identity)
        self._verify_p3_contract_artifacts(validation_profile)

        identity = validation_profile.get("content_sampling_profile")
        if not isinstance(identity, Mapping):
            raise ValidationContextError(
                "P3 Validation Profile has no Content Sampling Profile identity"
            )
        discriminator = (
            identity.get("id"),
            identity.get("schema_version"),
            identity.get("path"),
        )
        if discriminator != CONTENT_SAMPLING_PROFILE_IDENTITY:
            raise ValidationContextError(
                "P3 Content Sampling Profile identity is not in the closed-world registry"
            )
        return self._verify_identity(CONTENT_SAMPLING_PROFILE_SPEC, identity)

    def _verify_p3_successor_profile(
        self,
        validation_profile: Mapping[str, Any],
    ) -> dict[str, Any]:
        base_identity = validation_profile.get("base_profile")
        if not isinstance(base_identity, Mapping):
            raise ValidationContextError(
                "Successor P3 Validation Profile has no P3 base identity"
            )
        base_spec = self._context_spec_for_identity(
            "validation_profile", base_identity
        )
        if base_spec != P3_VALIDATION_PROFILE_SPEC:
            raise ValidationContextError(
                "Successor P3 Validation Profile must directly bind frozen P3"
            )
        base_profile = self._verify_identity(base_spec, base_identity)
        self._verify_p3_family_profile(base_profile)

        self._verify_p3_contract_artifacts(
            validation_profile,
            contract_specs=P3_SUCCESSOR_VALIDATION_CONTRACT_SPECS,
        )

        policy_identity = validation_profile.get("finding_code_policy_identity")
        if not isinstance(policy_identity, Mapping):
            raise ValidationContextError(
                "Successor P3 Validation Profile has no Finding Code Policy identity"
            )
        discriminator = (
            policy_identity.get("id"),
            policy_identity.get("schema_version"),
            policy_identity.get("path"),
        )
        if discriminator != FINDING_CODE_POLICY_IDENTITY:
            raise ValidationContextError(
                "Successor Finding Code Policy identity is not in the closed-world registry"
            )
        self._verify_identity(FINDING_CODE_POLICY_SPEC, policy_identity)

        identity = validation_profile.get("content_sampling_profile")
        if not isinstance(identity, Mapping):
            raise ValidationContextError(
                "Successor P3 Validation Profile has no Content Sampling Profile identity"
            )
        discriminator = (
            identity.get("id"),
            identity.get("schema_version"),
            identity.get("path"),
        )
        if discriminator != CONTENT_SAMPLING_PROFILE_IDENTITY:
            raise ValidationContextError(
                "Successor Content Sampling Profile identity is not in the closed-world registry"
            )
        return self._verify_identity(CONTENT_SAMPLING_PROFILE_SPEC, identity)

    def _verify_p3_contract_artifacts(
        self,
        validation_profile: Mapping[str, Any],
        *,
        contract_specs: tuple[_ContractArtifactSpec, ...] = P3_VALIDATION_CONTRACT_SPECS,
    ) -> None:
        contracts = validation_profile.get("contracts")
        if not isinstance(contracts, Mapping):
            raise ValidationContextError(
                "P3 Validation Profile contracts are invalid"
            )
        expected_names = {
            specification.name
            for specification in contract_specs
        }
        if set(contracts) != expected_names:
            raise ValidationContextError(
                "P3 Validation Profile contracts are not closed-world"
            )

        for specification in contract_specs:
            identity = contracts.get(specification.name)
            if not isinstance(identity, Mapping) or set(identity) != {
                "schema_version",
                "path",
                "sha256",
            }:
                raise ValidationContextError(
                    f"P3 contract {specification.name} identity is not closed-world"
                )
            if identity.get("schema_version") != specification.schema_version:
                raise ValidationContextError(
                    f"P3 contract {specification.name} schema version drifted"
                )
            if identity.get("path") != specification.relative_path:
                raise ValidationContextError(
                    f"P3 contract {specification.name} path drifted"
                )

            path = self._safe_file(specification.relative_path)
            artifact_sha256 = sha256_file(path)
            if artifact_sha256 != identity.get("sha256"):
                raise ValidationContextError(
                    f"P3 contract {specification.name} SHA-256 drifted"
                )
            if sha256_file(path) != artifact_sha256:
                raise ValidationContextError(
                    f"P3 contract {specification.name} changed while it was replayed"
                )

    def _effective_planning_baseline(
        self,
        spec: _ArtifactSpec,
        *,
        document: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        raw = (
            copy.deepcopy(dict(document))
            if document is not None
            else copy.deepcopy(self._validated_document(spec)[0])
        )
        if spec == P1_PLANNING_BASELINE_SPEC:
            self._validate_baseline_semantics(raw)
            return raw
        if spec != P2_PLANNING_BASELINE_SPEC:
            raise ValidationContextError(
                "Unknown planning baseline authority"
            )
        return self._apply_product_definition_overlay(raw)

    def _apply_product_definition_overlay(
        self, overlay: Mapping[str, Any]
    ) -> dict[str, Any]:
        base_identity = overlay.get("base_baseline")
        if not isinstance(base_identity, Mapping):
            raise ValidationContextError(
                "P2 Planning Baseline overlay has no base identity"
            )
        base_spec = self._planning_spec_for_identity(base_identity)
        if base_spec != P1_PLANNING_BASELINE_SPEC:
            raise ValidationContextError(
                "P2 Planning Baseline overlay must directly bind the frozen P1 baseline"
            )
        base = copy.deepcopy(
            self._verify_identity(base_spec, base_identity)
        )
        self._validate_baseline_semantics(base)

        allowed = overlay.get("allowed_item_ids")
        if (
            not isinstance(allowed, list)
            or tuple(allowed) != P2_AMENDED_ITEM_IDS
        ):
            raise ValidationContextError(
                "P2 Planning Baseline allowed item set drifted"
            )
        amendments = overlay.get("amendments")
        if not isinstance(amendments, list):
            raise ValidationContextError(
                "P2 Planning Baseline amendments are missing"
            )
        amendment_ids = [
            amendment.get("item_id")
            for amendment in amendments
            if isinstance(amendment, Mapping)
        ]
        if (
            len(amendment_ids) != len(amendments)
            or tuple(amendment_ids) != P2_AMENDED_ITEM_IDS
        ):
            raise ValidationContextError(
                "P2 Planning Baseline amendments must be the exact ordered four-item set"
            )

        indexed = {item["item_id"]: item for item in base["items"]}
        changes_by_path: dict[str, set[tuple[str, str]]] = {}
        amended_ids_by_path: dict[str, set[str]] = {}
        for amendment in amendments:
            item_id = amendment["item_id"]
            frozen = indexed.get(item_id)
            if frozen is None:
                raise ValidationContextError(
                    f"P2 Planning Baseline amendment is absent from P1: {item_id}"
                )
            transition = amendment["product_definition"]
            expected = frozen["product_definition"]
            prior = {
                "path": transition["path"],
                "sha256": transition["old_sha256"],
            }
            if prior != expected:
                raise ValidationContextError(
                    f"P2 Planning Baseline old Product Definition identity drifted: {item_id}"
                )
            if transition["new_sha256"] == transition["old_sha256"]:
                raise ValidationContextError(
                    f"P2 Planning Baseline transition is not a change: {item_id}"
                )
            path = transition["path"]
            change = (
                transition["old_sha256"],
                transition["new_sha256"],
            )
            changes_by_path.setdefault(path, set()).add(change)
            amended_ids_by_path.setdefault(path, set()).add(item_id)
            frozen["product_definition"]["sha256"] = transition[
                "new_sha256"
            ]

        for path, transitions in changes_by_path.items():
            if len(transitions) != 1:
                raise ValidationContextError(
                    f"P2 bilingual Product Definition transition differs by language: {path}"
                )
            base_references = {
                item["item_id"]
                for item in base["items"]
                if item["product_definition"]["path"] == path
            }
            if base_references != amended_ids_by_path[path]:
                raise ValidationContextError(
                    f"P2 Product Definition path has unamended baseline items: {path}"
                )

        if overlay.get("effective_summary") != base["summary"]:
            raise ValidationContextError(
                "P2 Planning Baseline effective summary differs from P1"
            )
        if overlay.get("accounting") != base["accounting"]:
            raise ValidationContextError(
                "P2 Planning Baseline accounting differs from P1"
            )
        self._validate_baseline_semantics(base)
        return base

    def _validated_document(
        self,
        spec: _ArtifactSpec,
        *,
        expected_sha256: Any = None,
    ) -> tuple[dict[str, Any], str]:
        """Hash-gate an artifact, revalidating only when bytes changed."""
        path = self._safe_file(spec.relative_path)
        artifact_sha256 = sha256_file(path)
        if (
            expected_sha256 is not None
            and artifact_sha256 != expected_sha256
        ):
            raise ValidationContextError(f"Frozen {spec.key} SHA-256 drifted")

        schema_path = self._safe_file(spec.schema_path)
        schema_sha256 = sha256_file(schema_path)
        cache_key = (spec.key, spec.relative_path)
        cached = self._documents.get(cache_key)
        if (
            cached is not None
            and cached[0] == artifact_sha256
            and cached[1] == schema_sha256
        ):
            return cached[2], artifact_sha256

        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValidationContextError(
                f"Unable to read {spec.key}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise ValidationContextError(f"{spec.key} must be a JSON object")
        self._validate_schema(value, spec, schema_path=schema_path)
        if sha256_file(path) != artifact_sha256:
            raise ValidationContextError(
                f"{spec.key} changed while it was being validated"
            )
        if sha256_file(schema_path) != schema_sha256:
            raise ValidationContextError(
                f"{spec.key} schema changed while it was being validated"
            )
        if spec == P1_PLANNING_BASELINE_SPEC:
            self._validate_baseline_semantics(value)
        self._documents[cache_key] = (
            artifact_sha256,
            schema_sha256,
            value,
        )
        return value, artifact_sha256

    def _safe_file(self, relative_path: str) -> Path:
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValidationContextError(
                f"Validation context path must be repository-relative: {relative_path}"
            )
        path = self.root / relative
        try:
            path.resolve(strict=True).relative_to(self.root)
        except (OSError, ValueError) as error:
            raise ValidationContextError(
                f"Validation context path is missing or escapes the repository: {relative_path}"
            ) from error
        if path.is_symlink() or not path.is_file():
            raise ValidationContextError(
                f"Validation context path must be a regular non-symlink file: {relative_path}"
            )
        return path

    def _validate_schema(
        self,
        value: Mapping[str, Any],
        spec: _ArtifactSpec,
        *,
        schema_path: Path | None = None,
    ) -> None:
        schema_path = schema_path or self._safe_file(spec.schema_path)
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = sorted(
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).iter_errors(value),
            key=lambda item: list(item.absolute_path),
        )
        if errors:
            details = "; ".join(
                f"{'/'.join(map(str, error.absolute_path)) or '$'}: {error.message}"
                for error in errors
            )
            raise ValidationContextError(f"Invalid {spec.key}: {details}")

    @staticmethod
    def _validate_baseline_semantics(value: Mapping[str, Any]) -> None:
        items = value["items"]
        item_ids = [item["item_id"] for item in items]
        if len(item_ids) != len(set(item_ids)):
            raise ValidationContextError("Planning Baseline contains duplicate item_id values")
        runnable = [item for item in items if item["v03_state"] == "runnable"]
        retained = [
            item for item in runnable if item["v04_disposition"] == "retained_runnable"
        ]
        reviewed = [
            item for item in runnable if item["v04_disposition"] == "reviewed_non_runnable"
        ]
        accounting = value["accounting"]
        expected = {
            "denominator": len(runnable),
            "retained_runnable": len(retained),
            "reviewed_non_runnable": len(reviewed),
            "accounted": len(retained) + len(reviewed),
            "coverage": f"{len(retained) + len(reviewed)}/{len(runnable)}",
        }
        if accounting != expected or len(runnable) != 379:
            raise ValidationContextError(
                f"Planning Baseline accounting mismatch: expected {expected}, found {accounting}"
            )
