#!/usr/bin/env python3
"""Build or verify the reviewed v0.4 P2 Validation Profile.

The default mode is read-only verification. Writing requires the explicit
``--write-reviewed`` flag and never modifies the frozen P1 profile.
"""

from __future__ import annotations

import argparse
import copy
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


P1_PROFILE_PATH = "data/configs/validation-profiles/v0.4.json"
P1_PROFILE_SCHEMA_PATH = "schemas/validation-profile-1.0.schema.json"
P1_PROFILE_SHA256 = (
    "dd66c001235ea9c5f488adbe4e61800ce7bbc7bfaf488cc44d7b3934f5e1191f"
)
P2_PROFILE_PATH = "data/configs/validation-profiles/v0.4-p2.json"
P2_PROFILE_SCHEMA_PATH = "schemas/validation-profile-1.1.schema.json"

CONTRACTS = {
    "product_definition": {
        "schema_version": "1.1",
        "path": "schemas/product-definition-1.1.schema.json",
        "sha256": (
            "57a1fa0c49c07d021da2fed1f0b777fbb7f9534d68076ee35d496a2d2c2e42e4"
        ),
    },
    "flexible_content": {
        "schema_version": "1.1",
        "path": "schemas/flexible-content-page-1.1.schema.json",
        "sha256": (
            "a3f42c073c12de3a75a3a3db36bd51f9d74d3a024cda33cb73ee2ea52bcc9fb7"
        ),
    },
    "support_article": {
        "schema_version": "1.0",
        "path": "schemas/support-article-page-1.0.schema.json",
        "sha256": (
            "4495a399c1abd18ef1c6a9b012af4b666d577d543d7006ae0937420c9bc455ac"
        ),
    },
    "diagnostic_sidecar": {
        "schema_version": "1.2",
        "path": "schemas/diagnostic-sidecar-1.2.schema.json",
        "sha256": (
            "6d73b4fd334b2d4b61cf5c6009384e870b6ae7873e148dbf1e162448835b97c4"
        ),
    },
    "source_html_structure_audit": {
        "schema_version": "1.0",
        "path": "schemas/source-html-structure-audit-1.0.schema.json",
        "sha256": (
            "23432adcd1b7b5d3a528249b1c7ac9ec91f5885205c51b7dbf98a8cdc09bded3"
        ),
    },
}

SEMANTIC_ASSURANCE = {
    "cms_state_reachability": {
        "authority": "source-proven-reachable-condition-states",
        "state_space": "non-cartesian",
    },
    "strict_soft_category_projection": {
        "algorithm": "strict-soft-category-leaf-state-v1",
        "evidence_schema_version": "1.1",
        "lookup_key": "source-software-value-and-region-value",
        "duplicate_mapping_disposition": "report-and-fail-closed",
        "idless_table_policy": "unconditional-preserve",
        "idless_table_replay": (
            "physical-order-and-normalized-html-sha256"
        ),
    },
    "source_html_structure_audit": {
        "schema_version": "1.0",
        "auditor_version": (
            "exact-owned-boundaries-static-page-global-ids-and-"
            "post-selector-scope-v4"
        ),
        "blocking_finding_disposition": "fail-extraction",
        "source_repair": "forbidden",
    },
}


class ValidationProfileBuildError(RuntimeError):
    """The reviewed P2 Validation Profile cannot be reproduced exactly."""


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


def _validate_schema(value: Mapping[str, Any]) -> None:
    schema = _read_json(P2_PROFILE_SCHEMA_PATH)
    errors = sorted(
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        details = "; ".join(
            f"{'/'.join(map(str, error.absolute_path)) or '$'}: {error.message}"
            for error in errors
        )
        raise ValidationProfileBuildError(
            f"Invalid P2 Validation Profile: {details}"
        )


def build_document() -> dict[str, Any]:
    p1_path = ROOT / P1_PROFILE_PATH
    if sha256_file(p1_path) != P1_PROFILE_SHA256:
        raise ValidationProfileBuildError(
            "Frozen P1 Validation Profile SHA-256 drifted"
        )
    p1 = _read_json(P1_PROFILE_PATH)
    if (
        p1.get("schema_version") != "1.0"
        or p1.get("profile_id") != "v0.4-validation-p1"
        or p1.get("status") != "frozen"
    ):
        raise ValidationProfileBuildError(
            "Frozen P1 Validation Profile identity drifted"
        )

    contracts = copy.deepcopy(CONTRACTS)
    for name, identity in contracts.items():
        path = str(identity["path"])
        actual_sha256 = sha256_file(ROOT / path)
        if actual_sha256 != identity["sha256"]:
            raise ValidationProfileBuildError(
                f"Reviewed P2 contract SHA-256 drifted: {name} ({path})"
            )

    value = {
        "schema_version": "1.1",
        "profile_id": "v0.4-validation-p2",
        "status": "frozen",
        "base_profile": {
            "id": p1["profile_id"],
            "schema_version": p1["schema_version"],
            "path": P1_PROFILE_PATH,
            "sha256": P1_PROFILE_SHA256,
        },
        "contracts": contracts,
        "input_assurance": copy.deepcopy(p1["input_assurance"]),
        "source_finding_severity": copy.deepcopy(
            p1["source_finding_severity"]
        ),
        "semantic_assurance": copy.deepcopy(SEMANTIC_ASSURANCE),
        "min_content_length_by_product": copy.deepcopy(
            p1["min_content_length_by_product"]
        ),
    }
    _validate_schema(value)
    return value


def _atomic_write(path: Path, rendered: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(
            descriptor, "w", encoding="utf-8", newline="\n"
        ) as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build(*, write_reviewed: bool = False) -> dict[str, Any]:
    p1_before = sha256_file(ROOT / P1_PROFILE_PATH)
    expected = build_document()
    rendered = _render(expected)
    path = ROOT / P2_PROFILE_PATH
    current = path.read_text(encoding="utf-8") if path.is_file() else None
    if current != rendered:
        if not write_reviewed:
            raise ValidationProfileBuildError(
                "Reviewed P2 Validation Profile is missing or stale; "
                "use --write-reviewed only after explicit review"
            )
        _atomic_write(path, rendered)
    if sha256_file(ROOT / P1_PROFILE_PATH) != p1_before:
        raise ValidationProfileBuildError(
            "P2 profile build modified the frozen P1 profile"
        )
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-reviewed",
        action="store_true",
        help="write the already reviewed deterministic P2 profile",
    )
    args = parser.parse_args()
    value = build(write_reviewed=args.write_reviewed)
    action = "written" if args.write_reviewed else "verified"
    print(
        f"{action}=1 profile_id={value['profile_id']} "
        f"contracts={len(value['contracts'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
