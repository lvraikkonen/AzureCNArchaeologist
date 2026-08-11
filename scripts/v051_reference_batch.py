#!/usr/bin/env python3
"""Generate or verify the read-only v0.5.1 reference Batch audit."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.regression.reference_batch_v051 import (
    ReferenceBatchError,
    build_reference_batch_summary,
    verify_reference_batch_summary,
    write_reference_batch_summary,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="v0.5.1 full bilingual reference Batch acceptance audit"
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--runs-dir", default="runs")
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate")
    generate.add_argument("--batch-id", required=True)
    generate.add_argument("--expected-git-commit", required=True)
    generate.add_argument(
        "--output",
        default="reports/v0.5.1/reference-batch-summary.json",
    )
    generate.add_argument("--regression-rationales")

    verify = commands.add_parser("verify")
    verify.add_argument(
        "--report",
        default="reports/v0.5.1/reference-batch-summary.json",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    root = Path(args.root).resolve()
    if args.command == "generate":
        report = build_reference_batch_summary(
            root,
            batch_id=args.batch_id,
            expected_git_commit=args.expected_git_commit,
            runs_dir=args.runs_dir,
            regression_rationales_path=args.regression_rationales,
        )
        path = write_reference_batch_summary(
            root,
            report,
            output_path=args.output,
        )
        print(f"report={path}")
        print(f"result={report['result']}")
        print(f"semantic_sha256={report['semantic_sha256']}")
        unexplained = report["acceptance"]["unexplained_regression_count"]
        print(f"unexplained_regressions={unexplained}")
        return 0 if report["result"] == "qualified" else 2
    if args.command == "verify":
        report = verify_reference_batch_summary(
            root,
            report_path=args.report,
            runs_dir=args.runs_dir,
        )
        print(f"reference batch ok: {report['reference_batch']['batch_id']}")
        print(f"semantic_sha256={report['semantic_sha256']}")
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReferenceBatchError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
