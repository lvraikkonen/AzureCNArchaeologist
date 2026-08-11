"""Deterministic JSON artifact bytes for Step 4 runtime files."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


def artifact_json_text(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def artifact_json_bytes(value: Mapping[str, Any]) -> bytes:
    return artifact_json_text(value).encode("utf-8")


def artifact_json_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(artifact_json_bytes(value)).hexdigest()
