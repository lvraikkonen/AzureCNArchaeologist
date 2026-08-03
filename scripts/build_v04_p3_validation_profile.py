#!/usr/bin/env python3
"""Build or verify the reviewed v0.4 P3 validation artifacts.

The default mode is read-only verification. Writing the deterministic Content
Sampling Profile and Validation Profile requires the explicit
``--write-reviewed`` flag and never modifies the frozen P2 profile.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.product_catalog import sha256_file


P2_PROFILE_PATH = "data/configs/validation-profiles/v0.4-p2.json"
P2_PROFILE_SHA256 = (
    "090565500134e970bd831785b7640d80f23ce49cb130e26858be8fa33d9c234c"
)
CONTENT_SAMPLING_PROFILE_PATH = (
    "data/configs/content-sampling-profiles/v0.4-p3.json"
)
CONTENT_SAMPLING_PROFILE_SCHEMA_PATH = (
    "schemas/content-sampling-profile-1.0.schema.json"
)
CONTENT_SAMPLING_PROFILE_SHA256 = (
    "2e2c33cd964ea73435a3f83c076dcdc114ee73c88e2d00c7c3c8cd4c6dd75cb0"
)
P3_PROFILE_PATH = "data/configs/validation-profiles/v0.4-p3.json"
P3_PROFILE_SCHEMA_PATH = "schemas/validation-profile-1.2.schema.json"

NEW_CONTRACTS = {
    "content_sampling_profile": {
        "schema_version": "1.0",
        "path": CONTENT_SAMPLING_PROFILE_SCHEMA_PATH,
        "sha256": (
            "bd9b877f21d323b518e92cda194411c73b4195c037bed5395f05cff383e6b122"
        ),
    },
    "pipeline_validation": {
        "schema_version": "2.0",
        "path": "schemas/pipeline-validation-2.0.schema.json",
        "sha256": (
            "8cec1c71778d6b7317139557157bf2aadb5df4fe0e93f1db0bf8cff0620b3e09"
        ),
    },
    "batch_item_sampling_plan": {
        "schema_version": "1.0",
        "path": "schemas/batch-item-sampling-plan-1.0.schema.json",
        "sha256": (
            "c6e3f6bb5448bdf299462c90e3832d8aa97d46b42169f05baad25a0ff39d3b7b"
        ),
    },
    "sampled_content_evidence": {
        "schema_version": "1.0",
        "path": "schemas/sampled-content-evidence-1.0.schema.json",
        "sha256": (
            "d8107443584d9602a3fcb77e3c9cc98af6f44439af1707c21a80fd57c89f1e94"
        ),
    },
}

SAMPLED_CONTENT_ASSURANCE = {
    "claim": "sampled_state_content_consistency",
    "structure_scope": "all_source_proven_reachable_states",
    "full_content_strategies": [
        "simple_static",
        "support_article",
    ],
    "sampled_content_strategies": [
        "region_filter",
        "complex",
    ],
    "target_budget": 12,
    "selected_state_failure": "fail_validation",
    "replacement_draw": "forbidden",
}


class ValidationProfileBuildError(RuntimeError):
    """The reviewed P3 profiles cannot be reproduced exactly."""


def _read_json(relative_path: str) -> dict[str, Any]:
    path = ROOT / relative_path
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationProfileBuildError(
            f"Unable to read {relative_path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise ValidationProfileBuildError(
            f"{relative_path} must contain a JSON object"
        )
    return value


def _render(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _rendered_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_render(value).encode("utf-8")).hexdigest()


def _validate_schema(
    value: Mapping[str, Any],
    *,
    schema_path: str,
    document_name: str,
) -> None:
    schema = _read_json(schema_path)
    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        details = "; ".join(
            f"{'/'.join(map(str, error.absolute_path)) or '$'}: "
            f"{error.message}"
            for error in errors
        )
        raise ValidationProfileBuildError(
            f"Invalid {document_name}: {details}"
        )


def build_content_sampling_profile_document() -> dict[str, Any]:
    value = {
        "schema_version": "1.0",
        "profile_id": "v0.4-content-sampling-p3",
        "status": "frozen",
        "algorithm_version": "source-ordered-stratified-sampling-v1",
        "target_budget": 12,
        "mandatory_anchors": ["default_state"],
        "strategy_rules": {
            "simple_static": {
                "coverage_mode": "full",
                "sampling_plan": "not_applicable",
            },
            "support_article": {
                "coverage_mode": "full",
                "sampling_plan": "not_applicable",
            },
            "region_filter": {
                "coverage_mode": "stratified_sample",
                "sampling_plan": "required",
                "stratum_dimension": "source_proven_region",
                "minimum_per_stratum": 1,
            },
            "complex": {
                "coverage_mode": "stratified_sample",
                "sampling_plan": "required",
                "stratum_dimension": "actual_parent_branch",
                "parent_branch_definition": (
                    "ordered_criteria_prefix_excluding_leaf"
                ),
                "minimum_per_stratum": 1,
                "cartesian_expansion": "forbidden",
            },
        },
        "selection_policy": {
            "small_universe": (
                "select_all_when_universe_lte_effective_budget"
            ),
            "forced_coverage_over_budget": "expand_effective_budget",
            "first_pass": "one_per_stratum_by_seed_state_hash",
            "stratum_order": "source_first_appearance",
            "within_stratum_rank": (
                "sha256-canonical-json-array-seed-state-id"
            ),
            "remainder": "stable_stratum_round_robin",
            "output_order": "source_order",
        },
        "seed_derivation": {
            "digest": "sha256",
            "serialization": "canonical-json-utf8-sorted-keys-compact",
            "ordered_inputs": [
                "algorithm_version",
                "source_sha256",
                "item_id",
                "profile_sha256",
            ],
            "excluded_inputs": [
                "payload_sha256",
                "batch_id",
                "time",
                "process_random_state",
            ],
        },
        "comparison_policy": {
            "page_global": "full",
            "selected_state": "complete_rendered_content",
            "selected_state_failure": "fail_validation",
            "replacement_draw": "forbidden",
        },
    }
    _validate_schema(
        value,
        schema_path=CONTENT_SAMPLING_PROFILE_SCHEMA_PATH,
        document_name="P3 Content Sampling Profile",
    )
    if _rendered_sha256(value) != CONTENT_SAMPLING_PROFILE_SHA256:
        raise ValidationProfileBuildError(
            "Reviewed Content Sampling Profile rendering drifted"
        )
    return value


def build_validation_profile_document(
    content_sampling_profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if sha256_file(ROOT / P2_PROFILE_PATH) != P2_PROFILE_SHA256:
        raise ValidationProfileBuildError(
            "Frozen P2 Validation Profile SHA-256 drifted"
        )
    p2 = _read_json(P2_PROFILE_PATH)
    if (
        p2.get("schema_version") != "1.1"
        or p2.get("profile_id") != "v0.4-validation-p2"
        or p2.get("status") != "frozen"
    ):
        raise ValidationProfileBuildError(
            "Frozen P2 Validation Profile identity drifted"
        )

    sampling_profile = (
        build_content_sampling_profile_document()
        if content_sampling_profile is None
        else dict(content_sampling_profile)
    )
    if _rendered_sha256(sampling_profile) != CONTENT_SAMPLING_PROFILE_SHA256:
        raise ValidationProfileBuildError(
            "Nested Content Sampling Profile identity drifted"
        )

    contracts = copy.deepcopy(p2["contracts"])
    contracts.update(copy.deepcopy(NEW_CONTRACTS))
    for name, identity in contracts.items():
        path = str(identity["path"])
        actual_sha256 = sha256_file(ROOT / path)
        if actual_sha256 != identity["sha256"]:
            raise ValidationProfileBuildError(
                f"Reviewed P3 contract SHA-256 drifted: {name} ({path})"
            )

    semantic_assurance = copy.deepcopy(p2["semantic_assurance"])
    semantic_assurance["sampled_content_consistency"] = copy.deepcopy(
        SAMPLED_CONTENT_ASSURANCE
    )
    value = {
        "schema_version": "1.2",
        "profile_id": "v0.4-validation-p3",
        "status": "frozen",
        "base_profile": {
            "id": p2["profile_id"],
            "schema_version": p2["schema_version"],
            "path": P2_PROFILE_PATH,
            "sha256": P2_PROFILE_SHA256,
        },
        "content_sampling_profile": {
            "id": sampling_profile["profile_id"],
            "schema_version": sampling_profile["schema_version"],
            "path": CONTENT_SAMPLING_PROFILE_PATH,
            "sha256": CONTENT_SAMPLING_PROFILE_SHA256,
        },
        "contracts": contracts,
        "input_assurance": copy.deepcopy(p2["input_assurance"]),
        "source_finding_severity": copy.deepcopy(
            p2["source_finding_severity"]
        ),
        "semantic_assurance": semantic_assurance,
        "min_content_length_by_product": copy.deepcopy(
            p2["min_content_length_by_product"]
        ),
    }
    _validate_schema(
        value,
        schema_path=P3_PROFILE_SCHEMA_PATH,
        document_name="P3 Validation Profile",
    )
    return value


def build_document() -> dict[str, Any]:
    """Return the deterministic P3 Validation Profile document."""

    return build_validation_profile_document()


def _atomic_write(path: Path, rendered: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build(*, write_reviewed: bool = False) -> dict[str, Any]:
    p2_before = sha256_file(ROOT / P2_PROFILE_PATH)
    sampling_profile = build_content_sampling_profile_document()
    validation_profile = build_validation_profile_document(sampling_profile)
    documents = {
        CONTENT_SAMPLING_PROFILE_PATH: sampling_profile,
        P3_PROFILE_PATH: validation_profile,
    }
    stale: list[str] = []
    for relative_path, value in documents.items():
        path = ROOT / relative_path
        rendered = _render(value)
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == rendered:
            continue
        if write_reviewed:
            _atomic_write(path, rendered)
        else:
            stale.append(relative_path)
    if stale:
        raise ValidationProfileBuildError(
            "Reviewed P3 profile artifacts are missing or stale: "
            + ", ".join(stale)
            + "; use --write-reviewed only after explicit review"
        )
    if sha256_file(ROOT / P2_PROFILE_PATH) != p2_before:
        raise ValidationProfileBuildError(
            "P3 profile build modified the frozen P2 profile"
        )
    return validation_profile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-reviewed",
        action="store_true",
        help="write the already reviewed deterministic P3 profile artifacts",
    )
    args = parser.parse_args()
    value = build(write_reviewed=args.write_reviewed)
    action = "written" if args.write_reviewed else "verified"
    print(
        f"{action}=2 profile_id={value['profile_id']} "
        f"contracts={len(value['contracts'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
