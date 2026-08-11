"""Command-line entry point for v0.5 Planning Baseline candidates."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.regression.planning_v05 import (
    PlanningBaselineError,
    create_planning_candidate,
    promote_planning_candidate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="v0.5 Planning Baseline reviewed-candidate tooling"
    )
    parser.add_argument("--root", default=".")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("candidate")
    promote = commands.add_parser("promote")
    promote.add_argument("--candidate", required=True)
    promote.add_argument("--expected-sha256", required=True)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    root = Path(args.root).resolve()
    if args.command == "candidate":
        candidate_dir, manifest = create_planning_candidate(root)
        print(f"candidate={candidate_dir}")
        print(f"candidate_sha256={manifest['candidate_sha256']}")
        print(f"proposed_sha256={manifest['proposed_sha256']}")
        return 0
    if args.command == "promote":
        manifest = promote_planning_candidate(
            root,
            candidate_dir=args.candidate,
            expected_sha256=args.expected_sha256,
        )
        print(f"promoted={manifest['target_path']}")
        print(f"candidate_sha256={manifest['candidate_sha256']}")
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PlanningBaselineError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
