#!/usr/bin/env python3
"""Run one product through the explicit v0.2 extraction interface."""

from __future__ import annotations

import argparse

from src.core.extraction_coordinator import ExtractionCoordinator


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug one v0.2 extraction")
    parser.add_argument("product_key", nargs="?", default="event-grid")
    parser.add_argument("--language", choices=("zh-cn", "en-us"), default="zh-cn")
    parser.add_argument("--html-file", help="Optional explicit HTML override")
    parser.add_argument("--output-dir", default="debug_output")
    args = parser.parse_args()

    result = ExtractionCoordinator(args.output_dir).coordinate_extraction(
        args.product_key,
        args.language,
        args.html_file,
    )
    status = result.sidecar["status"]
    print(
        f"{args.product_key}/{args.language}: "
        f"execution={status['execution']} validation={status['validation']}"
    )
    if result.payload_path:
        print(f"payload: {result.payload_path}")
    print(f"sidecar: {result.sidecar_path}")
    for issue in result.sidecar["validation"]["errors"]:
        print(f"ERROR {issue['code']} {issue['path']}: {issue['message']}")
    for issue in result.sidecar["validation"]["warnings"]:
        print(f"WARN {issue['code']} {issue['path']}: {issue['message']}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
