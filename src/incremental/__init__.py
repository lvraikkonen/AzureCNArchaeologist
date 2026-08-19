"""Upstream snapshot change detection and incremental processing scope."""

from src.incremental.change_detection import (
    AffectedProduct,
    ChangeDetectionError,
    ChangePlan,
    LanguageChange,
    detect_html_changes,
    detect_incremental_changes,
)
from src.incremental.reprocessing import (
    IncrementalReprocessingError,
    ReprocessingChain,
    find_reprocessing_chain,
)

__all__ = [
    "AffectedProduct",
    "ChangeDetectionError",
    "ChangePlan",
    "LanguageChange",
    "IncrementalReprocessingError",
    "ReprocessingChain",
    "detect_html_changes",
    "detect_incremental_changes",
    "find_reprocessing_chain",
]
