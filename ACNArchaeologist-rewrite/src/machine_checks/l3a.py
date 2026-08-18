"""L3a: repeat production extraction and compare the complete Payload."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.core.payload_contract import load_payload
from src.machine_checks.readable_diff import json_differences


def run_l3a(
    *,
    payload_path: Path,
    extract_again: Callable[[], dict[str, Any]],
    product_key: str,
    language: str,
) -> dict[str, Any]:
    """Read the persisted Payload, extract afresh, and compare every field."""

    try:
        persisted_payload = load_payload(payload_path)
        repeated_payload = extract_again()
    except Exception as error:
        return {
            "check": "L3a",
            "status": "blocked",
            "product_key": product_key,
            "language": language,
            "scope": "完整 Business Payload",
            "differences": [],
            "error": f"无法完成第二次独立抽取：{error}",
        }

    differences = json_differences(persisted_payload, repeated_payload)
    return {
        "check": "L3a",
        "status": "passed" if not differences else "failed",
        "product_key": product_key,
        "language": language,
        "scope": "完整 Business Payload",
        "differences": differences,
    }

