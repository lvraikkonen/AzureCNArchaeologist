#!/usr/bin/env python3
"""Record or replay the one allowlisted v0.5.2 formal L3b item."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.independent_fidelity.recorder import (  # noqa: E402
    record_formal_target,
    verify_formal_target,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="v0.5.2 zh-cn/api-management Independent Fidelity recorder"
    )
    parser.add_argument("action", choices=("record", "verify"))
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--item-id", required=True)
    args = parser.parse_args()

    operation = (
        record_formal_target if args.action == "record" else verify_formal_target
    )
    result = operation(
        ROOT,
        batch_id=args.batch_id,
        item_id=args.item_id,
    )
    for key, value in result.console_fields():
        print(f"{key}={value}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
