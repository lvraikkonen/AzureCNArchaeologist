#!/usr/bin/env python3
"""Build or verify the reviewed v0.4 P2 planning identity overlay.

The default mode is read-only verification. Writing requires the explicit
``--write-reviewed`` flag and never modifies the frozen P1 baseline.
"""

from __future__ import annotations

import argparse
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


P1_BASELINE_PATH = "data/baselines/v0.4/planning-baseline.json"
P1_BASELINE_SHA256 = (
    "86e2f8836c94a9c0a063ce9a8da7efe445137c4e63d99f7b0cf0d9350b20d3d3"
)
OVERLAY_PATH = (
    "data/baselines/v0.4/p2-product-definition-identity-overlay.json"
)
OVERLAY_SCHEMA_PATH = (
    "schemas/planning-baseline-identity-overlay-1.0.schema.json"
)
ALLOWED_ITEM_IDS = (
    "en-us/cloud-services",
    "en-us/service-bus",
    "zh-cn/cloud-services",
    "zh-cn/service-bus",
)
NEW_DEFINITION_SHA256 = {
    "data/configs/products/pricing/cloud-services.json": (
        "3ff681615ef5a65b426b4cf9648ff9ddd6ad11d8090adec544ed2754e8bc094b"
    ),
    "data/configs/products/pricing/service-bus.json": (
        "28a1cbbff20a82abf675721bb8bf4ba6c4261c9100817d0db6efbb4af4bfbca2"
    ),
}


class OverlayBuildError(RuntimeError):
    """The reviewed P2 overlay cannot be reproduced exactly."""


def _read_json(relative_path: str) -> dict[str, Any]:
    path = ROOT / relative_path
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OverlayBuildError(
            f"Unable to read {relative_path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise OverlayBuildError(f"{relative_path} must contain a JSON object")
    return value


def _render(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _validate_schema(value: Mapping[str, Any]) -> None:
    schema = _read_json(OVERLAY_SCHEMA_PATH)
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
        raise OverlayBuildError(f"Invalid P2 planning overlay: {details}")


def build_document() -> dict[str, Any]:
    baseline_path = ROOT / P1_BASELINE_PATH
    if sha256_file(baseline_path) != P1_BASELINE_SHA256:
        raise OverlayBuildError("Frozen P1 Planning Baseline SHA-256 drifted")
    baseline = _read_json(P1_BASELINE_PATH)
    indexed = {item["item_id"]: item for item in baseline["items"]}
    if len(indexed) != 434 or len(baseline["items"]) != 434:
        raise OverlayBuildError("Frozen P1 Planning Baseline is not exactly 434 items")

    amendments: list[dict[str, Any]] = []
    for item_id in ALLOWED_ITEM_IDS:
        try:
            frozen = indexed[item_id]
        except KeyError as error:
            raise OverlayBuildError(
                f"Frozen P1 Planning Baseline is missing {item_id}"
            ) from error
        definition = frozen["product_definition"]
        path = definition["path"]
        try:
            approved_new_sha256 = NEW_DEFINITION_SHA256[path]
        except KeyError as error:
            raise OverlayBuildError(
                f"Unexpected Product Definition path for {item_id}: {path}"
            ) from error
        actual_new_sha256 = sha256_file(ROOT / path)
        if actual_new_sha256 != approved_new_sha256:
            raise OverlayBuildError(
                f"Reviewed Product Definition SHA-256 drifted: {path}"
            )
        amendments.append({
            "item_id": item_id,
            "product_definition": {
                "path": path,
                "old_sha256": definition["sha256"],
                "new_sha256": approved_new_sha256,
            },
            "reason_code": "approved_p2_page_global_content_identity",
        })

    value = {
        "schema_version": "1.0",
        "baseline_id": "v0.4-p2-product-definition-identity-overlay",
        "status": "approved",
        "base_baseline": {
            "id": baseline["baseline_id"],
            "schema_version": baseline["schema_version"],
            "path": P1_BASELINE_PATH,
            "sha256": P1_BASELINE_SHA256,
        },
        "change_policy": {
            "mutable_field": "product_definition.sha256",
            "product_definition_path_must_match": True,
            "all_other_item_fields_must_match_base": True,
        },
        "allowed_item_ids": list(ALLOWED_ITEM_IDS),
        "amendments": amendments,
        "effective_summary": dict(baseline["summary"]),
        "accounting": dict(baseline["accounting"]),
        "review": {
            "verdict": "approved",
            "reviewer": "repository-owner",
            "rationale": (
                "Authorize only the four bilingual Product Definition SHA "
                "transitions required by the reviewed P2 page-global content "
                "contract."
            ),
        },
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
    p1_before = sha256_file(ROOT / P1_BASELINE_PATH)
    expected = build_document()
    rendered = _render(expected)
    path = ROOT / OVERLAY_PATH
    current = path.read_text(encoding="utf-8") if path.is_file() else None
    if current != rendered:
        if not write_reviewed:
            raise OverlayBuildError(
                "Reviewed P2 planning overlay is missing or stale; "
                "use --write-reviewed only after explicit review"
            )
        _atomic_write(path, rendered)
    if sha256_file(ROOT / P1_BASELINE_PATH) != p1_before:
        raise OverlayBuildError("P2 overlay build modified the frozen P1 baseline")
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-reviewed",
        action="store_true",
        help="write the already reviewed deterministic overlay",
    )
    args = parser.parse_args()
    value = build(write_reviewed=args.write_reviewed)
    action = "written" if args.write_reviewed else "verified"
    print(
        f"{action}=1 overlay_items={len(value['amendments'])} "
        "planning_items=434 accounting=379/379"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
