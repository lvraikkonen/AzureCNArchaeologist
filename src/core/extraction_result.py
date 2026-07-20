"""Extraction result separates the CMS candidate payload from diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class ExtractionResult:
    product_key: str
    language: str
    payload: Optional[dict[str, Any]]
    sidecar: dict[str, Any]
    payload_path: Optional[Path]
    sidecar_path: Path

    @property
    def exit_code(self) -> int:
        execution = self.sidecar["status"]["execution"]
        validation = self.sidecar["status"]["validation"]
        if execution != "succeeded":
            return 1
        return 0 if validation == "passed" else 2

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0
