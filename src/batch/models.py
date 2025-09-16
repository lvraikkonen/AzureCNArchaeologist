"""
Data models for batch processing operations.

This module defines the core data structures used for batch processing
of flexible JSON content extraction, including processing records,
status tracking, and result models.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import json


class BatchProcessStatus(Enum):
    """Status enumeration for batch processing records."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class BatchProcessRecord:
    """
    Data model for batch processing records.
    
    Tracks the complete lifecycle of a single product processing operation
    from initial submission through completion or failure.
    """
    id: Optional[int] = None
    product_key: str = ""
    product_group: Optional[str] = None
    strategy_used: Optional[str] = None
    processing_status: BatchProcessStatus = BatchProcessStatus.PENDING
    error_message: Optional[str] = None
    processing_time_ms: Optional[int] = None
    output_file_path: Optional[str] = None
    html_file_path: Optional[str] = None
    content_hash: Optional[str] = None
    retry_count: int = 0
    extraction_timestamp: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize default values after dataclass creation."""
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary representation."""
        return {
            'id': self.id,
            'product_key': self.product_key,
            'product_group': self.product_group,
            'strategy_used': self.strategy_used,
            'processing_status': self.processing_status.value if self.processing_status else None,
            'error_message': self.error_message,
            'processing_time_ms': self.processing_time_ms,
            'output_file_path': self.output_file_path,
            'html_file_path': self.html_file_path,
            'content_hash': self.content_hash,
            'retry_count': self.retry_count,
            'extraction_timestamp': self.extraction_timestamp.isoformat() if self.extraction_timestamp else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BatchProcessRecord':
        """Create record from dictionary representation."""
        record = cls()
        record.id = data.get('id')
        record.product_key = data.get('product_key', '')
        record.product_group = data.get('product_group')
        record.strategy_used = data.get('strategy_used')
        
        status_str = data.get('processing_status')
        if status_str:
            record.processing_status = BatchProcessStatus(status_str)
        
        record.error_message = data.get('error_message')
        record.processing_time_ms = data.get('processing_time_ms')
        record.output_file_path = data.get('output_file_path')
        record.html_file_path = data.get('html_file_path')
        record.content_hash = data.get('content_hash')
        record.retry_count = data.get('retry_count', 0)
        
        # Parse datetime strings
        extraction_ts = data.get('extraction_timestamp')
        if extraction_ts:
            record.extraction_timestamp = datetime.fromisoformat(extraction_ts.replace('Z', '+00:00'))
        
        created_at = data.get('created_at')
        if created_at:
            record.created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        
        updated_at = data.get('updated_at')
        if updated_at:
            record.updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
        
        record.metadata = data.get('metadata', {})
        
        return record


@dataclass
class ProcessingResult:
    """
    Result model for individual product processing operations.
    
    Contains the outcome of processing a single product, including
    success/failure status, timing, and any error information.
    """
    product_key: str
    success: bool
    strategy_used: Optional[str] = None
    processing_time_ms: Optional[int] = None
    output_file_path: Optional[str] = None
    error_message: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize default values after dataclass creation."""
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            'product_key': self.product_key,
            'success': self.success,
            'strategy_used': self.strategy_used,
            'processing_time_ms': self.processing_time_ms,
            'output_file_path': self.output_file_path,
            'error_message': self.error_message,
            'content_hash': self.content_hash,
            'metadata': self.metadata
        }


@dataclass
class BatchProcessReport:
    """
    Comprehensive report for batch processing operations.
    
    Provides summary statistics, performance metrics, and detailed
    results for a batch processing session.
    """
    batch_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_products: int = 0
    successful_products: int = 0
    failed_products: int = 0
    products_by_group: Dict[str, int] = None
    products_by_strategy: Dict[str, int] = None
    processing_results: List[ProcessingResult] = None
    total_processing_time_ms: int = 0
    average_processing_time_ms: Optional[float] = None
    
    def __post_init__(self):
        """Initialize default values after dataclass creation."""
        if self.products_by_group is None:
            self.products_by_group = {}
        if self.products_by_strategy is None:
            self.products_by_strategy = {}
        if self.processing_results is None:
            self.processing_results = []
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_products == 0:
            return 0.0
        return (self.successful_products / self.total_products) * 100.0
    
    @property 
    def duration_seconds(self) -> Optional[float]:
        """Calculate total duration in seconds."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds()
    
    def add_result(self, result: ProcessingResult) -> None:
        """Add a processing result to the report."""
        self.processing_results.append(result)
        self.total_products += 1
        
        if result.success:
            self.successful_products += 1
        else:
            self.failed_products += 1
        
        # Update processing time statistics
        if result.processing_time_ms:
            self.total_processing_time_ms += result.processing_time_ms
            self.average_processing_time_ms = (
                self.total_processing_time_ms / self.total_products
            )
        
        # Update strategy statistics
        if result.strategy_used:
            self.products_by_strategy[result.strategy_used] = (
                self.products_by_strategy.get(result.strategy_used, 0) + 1
            )
    
    def finalize(self) -> None:
        """Mark the batch processing as complete."""
        self.end_time = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary representation."""
        return {
            'batch_id': self.batch_id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'total_products': self.total_products,
            'successful_products': self.successful_products,
            'failed_products': self.failed_products,
            'success_rate': self.success_rate,
            'duration_seconds': self.duration_seconds,
            'products_by_group': self.products_by_group,
            'products_by_strategy': self.products_by_strategy,
            'total_processing_time_ms': self.total_processing_time_ms,
            'average_processing_time_ms': self.average_processing_time_ms,
            'processing_results': [result.to_dict() for result in self.processing_results]
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string representation."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)