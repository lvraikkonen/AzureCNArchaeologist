#!/usr/bin/env python3
"""Generate Diagnostic Sidecar 1.2 with frozen input-assurance evidence."""

from __future__ import annotations

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"


def main() -> int:
    value = json.loads(
        (SCHEMAS / "diagnostic-sidecar-1.1.schema.json").read_text(encoding="utf-8")
    )
    finding = json.loads(
        (SCHEMAS / "source-finding-1.0.schema.json").read_text(encoding="utf-8")
    )
    finding = {
        key: copy.deepcopy(item)
        for key, item in finding.items()
        if key not in {"$schema", "$id", "title"}
    }
    value["$id"] = (
        "https://azure.cn/archaeologist/schemas/diagnostic-sidecar-1.2.schema.json"
    )
    value["title"] = "Diagnostic Sidecar 1.2"
    value["properties"]["schema_version"] = {"const": "1.2"}
    value["required"].append("input_assurance")
    value["$defs"]["source_finding"] = finding
    value["properties"]["input_assurance"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "status",
            "encoding",
            "has_utf8_bom",
            "source_normalized_byte_identical",
            "source_findings",
            "reconstruction_parseability",
        ],
        "properties": {
            "status": {"enum": ["passed", "failed"]},
            "encoding": {"const": "utf-8-strict"},
            "has_utf8_bom": {"type": ["boolean", "null"]},
            "source_normalized_byte_identical": {"type": ["boolean", "null"]},
            "source_findings": {
                "type": "array",
                "items": {"$ref": "#/$defs/source_finding"},
            },
            "reconstruction_parseability": {
                "oneOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "verdict",
                            "input_sha256",
                            "profile_sha256",
                            "evidence",
                        ],
                        "properties": {
                            "verdict": {"enum": ["passed", "failed"]},
                            "input_sha256": {
                                "type": "string",
                                "pattern": "^[a-f0-9]{64}$",
                            },
                            "profile_sha256": {
                                "type": "string",
                                "pattern": "^[a-f0-9]{64}$",
                            },
                            "evidence": {"$ref": "#/$defs/artifact"},
                        },
                    },
                ]
            },
        },
    }
    (SCHEMAS / "diagnostic-sidecar-1.2.schema.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
