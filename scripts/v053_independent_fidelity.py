#!/usr/bin/env python3
"""Preflight and canonical record/verify commands for v0.5.3 L3b."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    for action in ("record", "verify"):
        command = subparsers.add_parser(action)
        command.add_argument("--batch-id", required=True)
        command.add_argument("--item-id", required=True)
    for action in ("record-set", "verify-set"):
        command = subparsers.add_parser(action)
        command.add_argument("--batch-id", required=True)
    args = parser.parse_args()

    from src.independent_fidelity.v053_recorder import (
        operate_target_set,
        record_target,
        verify_target,
    )

    if args.action == "record":
        result = record_target(
            ROOT,
            batch_id=args.batch_id,
            item_id=args.item_id,
        )
    elif args.action == "verify":
        result = verify_target(
            ROOT,
            batch_id=args.batch_id,
            item_id=args.item_id,
        )
    else:
        result = operate_target_set(
            ROOT,
            action="record" if args.action == "record-set" else "verify",
            batch_id=args.batch_id,
        )
    _print(result.as_dict())
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

