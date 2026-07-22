#!/usr/bin/env python3
"""Generate the additive Input/Batch Manifest 2.0 schemas from 1.0."""

from __future__ import annotations

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"


def _identity_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "schema_version", "path", "sha256"],
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "schema_version": {"type": "string", "minLength": 1},
            "path": {"$ref": "#/$defs/relative_path"},
            "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        },
    }


def _planning_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["baseline", "baseline_accounting"],
        "properties": {
            "baseline": {"$ref": "#/$defs/frozen_identity"},
            "baseline_accounting": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "denominator",
                    "retained_runnable",
                    "reviewed_non_runnable",
                    "accounted",
                    "coverage",
                ],
                "properties": {
                    "denominator": {"type": "integer", "minimum": 0},
                    "retained_runnable": {"type": "integer", "minimum": 0},
                    "reviewed_non_runnable": {"type": "integer", "minimum": 0},
                    "accounted": {"type": "integer", "minimum": 0},
                    "coverage": {"type": "string", "pattern": "^[0-9]+/[0-9]+$"},
                },
            },
        },
    }


def _context_schema() -> dict:
    keys = [
        "validation_profile",
        "applicability_map",
        "rendering_profile",
        "in_memory_capability_profile",
    ]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": keys,
        "properties": {
            key: {"$ref": "#/$defs/frozen_identity"} for key in keys
        },
    }


def _upgrade(filename: str, title: str, schema_id: str) -> None:
    source = json.loads((SCHEMAS / filename.replace("2.0", "1.0")).read_text())
    value = copy.deepcopy(source)
    value["$id"] = f"https://azure.cn/archaeologist/schemas/{schema_id}"
    value["title"] = title
    value["properties"]["schema_version"] = {"const": "2.0"}
    value["required"] = list(value["required"]) + ["planning", "validation_context"]
    value["properties"]["planning"] = _planning_schema()
    value["properties"]["validation_context"] = _context_schema()
    value["$defs"]["frozen_identity"] = _identity_schema()
    artifacts = value["$defs"]["item"]["properties"]["artifacts"]
    artifacts["required"] = list(artifacts["required"]) + ["parseability"]
    artifacts["properties"]["parseability"] = {
        "$ref": "#/$defs/artifact"
    }
    (SCHEMAS / filename).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    _upgrade(
        "pipeline-input-manifest-2.0.schema.json",
        "Pipeline Input Manifest 2.0",
        "pipeline-input-manifest-2.0.schema.json",
    )
    _upgrade(
        "pipeline-batch-manifest-2.0.schema.json",
        "Pipeline Batch Manifest 2.0",
        "pipeline-batch-manifest-2.0.schema.json",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
