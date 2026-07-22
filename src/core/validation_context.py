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


ARTIFACT_SPECS = (
    _ArtifactSpec(
        "planning_baseline",
        "baseline_id",
        "data/baselines/v0.4/planning-baseline.json",
        "schemas/planning-baseline-manifest-1.0.schema.json",
    ),
    _ArtifactSpec(
        "validation_profile",
        "profile_id",
        "data/configs/validation-profiles/v0.4.json",
        "schemas/validation-profile-1.0.schema.json",
    ),
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
SPECS_BY_KEY = {spec.key: spec for spec in ARTIFACT_SPECS}


class ValidationContextRegistry:
    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()
        # Validation is reusable only while both the artifact bytes and the
        # schema bytes are unchanged.  Every access still hashes both files,
        # so a warm cache cannot conceal on-disk drift.
        self._documents: dict[
            str, tuple[str, str, dict[str, Any]]
        ] = {}

    def freeze(self) -> dict[str, Any]:
        identities = {spec.key: self._identity(spec) for spec in ARTIFACT_SPECS}
        baseline = self.document("planning_baseline")
        return {
            "planning": {
                "baseline": identities.pop("planning_baseline"),
                "baseline_accounting": dict(baseline["accounting"]),
            },
            "validation_context": identities,
        }

    def verify_frozen(
        self,
        planning: Mapping[str, Any],
        validation_context: Mapping[str, Any],
    ) -> None:
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
        baseline = self._verify_identity(
            SPECS_BY_KEY["planning_baseline"], baseline_identity
        )
        for key in sorted(expected_keys):
            identity = validation_context[key]
            if not isinstance(identity, Mapping):
                raise ValidationContextError(f"Frozen identity is invalid: {key}")
            self._verify_identity(SPECS_BY_KEY[key], identity)
        if dict(planning.get("baseline_accounting", {})) != baseline["accounting"]:
            raise ValidationContextError("Frozen baseline accounting does not match its artifact")

    def document(self, key: str) -> dict[str, Any]:
        if key not in SPECS_BY_KEY:
            raise ValidationContextError(f"Unknown validation context artifact: {key}")
        value, _ = self._validated_document(SPECS_BY_KEY[key])
        return copy.deepcopy(value)

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
        cached = self._documents.get(spec.key)
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
        if spec.key == "planning_baseline":
            self._validate_baseline_semantics(value)
        self._documents[spec.key] = (
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
