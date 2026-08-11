#!/usr/bin/env python3
"""Internal v0.5 Core successor regression commands."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.regression.core import (
    V05_CORE_SPEC,
    CoreRegressionError,
    main,
)


if __name__ == "__main__":
    try:
        raise SystemExit(main(specification=V05_CORE_SPEC))
    except CoreRegressionError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
