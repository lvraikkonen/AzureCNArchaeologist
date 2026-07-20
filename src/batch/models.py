"""Orthogonal batch lifecycle models used by v0.2."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class ValidationStatus(Enum):
    NOT_RUN = "not_run"
    PASSED = "passed"
    FAILED = "failed"


class ReviewStatus(Enum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PublicationStatus(Enum):
    NOT_PUBLISHED = "not_published"
    PUBLISHED = "published"


@dataclass
class BatchProcessRecord:
    id: Optional[int] = None
    product_key: str = ""
    product_group: Optional[str] = None
    language: str = "zh-cn"
    strategy_used: Optional[str] = None
    execution_status: ExecutionStatus = ExecutionStatus.PENDING
    validation_status: ValidationStatus = ValidationStatus.NOT_RUN
    review_status: ReviewStatus = ReviewStatus.NOT_REQUESTED
    publication_status: PublicationStatus = PublicationStatus.NOT_PUBLISHED
    error_message: Optional[str] = None
    processing_time_ms: Optional[int] = None
    output_file_path: Optional[str] = None
    sidecar_file_path: Optional[str] = None
    html_file_path: Optional[str] = None
    content_hash: Optional[str] = None
    extraction_timestamp: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "product_key": self.product_key, "product_group": self.product_group,
            "language": self.language, "strategy_used": self.strategy_used,
            "execution_status": self.execution_status.value, "validation_status": self.validation_status.value,
            "review_status": self.review_status.value, "publication_status": self.publication_status.value,
            "error_message": self.error_message, "processing_time_ms": self.processing_time_ms,
            "output_file_path": self.output_file_path, "sidecar_file_path": self.sidecar_file_path,
            "html_file_path": self.html_file_path, "content_hash": self.content_hash,
            "extraction_timestamp": self.extraction_timestamp.isoformat() if self.extraction_timestamp else None,
            "created_at": self.created_at.isoformat(), "updated_at": self.updated_at.isoformat(), "metadata": self.metadata,
        }


@dataclass
class ProcessingResult:
    product_key: str
    success: bool
    strategy_used: Optional[str] = None
    processing_time_ms: Optional[int] = None
    output_file_path: Optional[str] = None
    sidecar_file_path: Optional[str] = None
    error_message: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class BatchProcessReport:
    batch_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_products: int = 0
    successful_products: int = 0
    failed_products: int = 0
    products_by_group: dict[str, int] = field(default_factory=dict)
    products_by_strategy: dict[str, int] = field(default_factory=dict)
    processing_results: list[ProcessingResult] = field(default_factory=list)
    total_processing_time_ms: int = 0
    average_processing_time_ms: Optional[float] = None

    @property
    def success_rate(self) -> float:
        return self.successful_products / self.total_products * 100 if self.total_products else 0.0

    @property
    def duration_seconds(self) -> Optional[float]:
        return (self.end_time - self.start_time).total_seconds() if self.end_time else None

    def add_result(self, result: ProcessingResult) -> None:
        self.processing_results.append(result)
        self.total_products += 1
        self.successful_products += int(result.success)
        self.failed_products += int(not result.success)
        if result.processing_time_ms is not None:
            self.total_processing_time_ms += result.processing_time_ms
            self.average_processing_time_ms = self.total_processing_time_ms / self.total_products
        if result.strategy_used:
            self.products_by_strategy[result.strategy_used] = self.products_by_strategy.get(result.strategy_used, 0) + 1

    def finalize(self) -> None:
        self.end_time = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        value = self.__dict__.copy()
        value["start_time"] = self.start_time.isoformat()
        value["end_time"] = self.end_time.isoformat() if self.end_time else None
        value["success_rate"] = self.success_rate
        value["duration_seconds"] = self.duration_seconds
        value["processing_results"] = [item.to_dict() for item in self.processing_results]
        return value

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
