"""
Batch processing module for Azure CN Archaeologist.

This module provides production-grade batch processing capabilities for
flexible JSON content extraction, including database record management,
parallel processing engines, and progress monitoring.

Components:
- models: Data models for batch processing records
- record_manager: SQLite database operations and lifecycle management  
- process_engine: Parallel batch processing engine with ProductGroup support
- status_tracker: Real-time progress monitoring and status updates
- cli_commands: CLI command integration for batch operations
"""

from .models import (
    BatchProcessRecord, ExecutionStatus, ValidationStatus,
    ReviewStatus, PublicationStatus, ProcessingResult,
)
from .record_manager import BatchProcessRecordManager
from .process_engine import BatchProcessEngine
from .status_tracker import BatchStatusTracker

__version__ = "1.0.0"
__all__ = [
    "BatchProcessRecord",
    "ExecutionStatus",
    "ValidationStatus",
    "ReviewStatus",
    "PublicationStatus",
    "ProcessingResult",
    "BatchProcessRecordManager",
    "BatchProcessEngine", 
    "BatchStatusTracker",
]
