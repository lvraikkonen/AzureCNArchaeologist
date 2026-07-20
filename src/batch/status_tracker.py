"""
Status tracker and progress monitoring for batch processing operations.

This module provides real-time status tracking, progress monitoring,
and comprehensive reporting capabilities for batch processing sessions.
"""

import time
from src.core.logging import get_logger
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from threading import Lock

from .models import (
    BatchProcessRecord, ExecutionStatus, BatchProcessReport,
    ProcessingResult
)
from .record_manager import BatchProcessRecordManager


logger = get_logger(__name__)


@dataclass
class ProcessingStats:
    """Real-time processing statistics."""
    total_products: int = 0
    completed_products: int = 0
    successful_products: int = 0
    failed_products: int = 0
    in_progress_products: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    
    @property
    def success_rate(self) -> float:
        """Calculate current success rate as percentage."""
        if self.completed_products == 0:
            return 0.0
        return (self.successful_products / self.completed_products) * 100.0
    
    @property
    def completion_rate(self) -> float:
        """Calculate completion rate as percentage."""
        if self.total_products == 0:
            return 0.0
        return (self.completed_products / self.total_products) * 100.0
    
    @property
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()
    
    @property
    def estimated_remaining_seconds(self) -> Optional[float]:
        """Estimate remaining time based on current progress."""
        if self.completed_products == 0 or self.completion_rate >= 100:
            return None
        
        avg_time_per_product = self.elapsed_seconds / self.completed_products
        remaining_products = self.total_products - self.completed_products
        return avg_time_per_product * remaining_products


class BatchStatusTracker:
    """
    Real-time status tracker for batch processing operations.
    
    Features:
    - Real-time progress monitoring with thread-safe updates
    - Comprehensive statistics and performance metrics
    - Configurable progress callbacks for UI integration
    - Database integration for persistent status tracking
    - Automatic performance analysis and bottleneck detection
    """
    
    def __init__(self, record_manager: Optional[BatchProcessRecordManager] = None):
        """
        Initialize the status tracker.
        
        Args:
            record_manager: Database record manager for persistent tracking
        """
        self.record_manager = record_manager or BatchProcessRecordManager()
        
        # Thread-safe tracking
        self._lock = Lock()
        self._stats = ProcessingStats()
        self._active_sessions: Dict[str, ProcessingStats] = {}
        
        # Progress callbacks
        self._progress_callbacks: List[Callable[[ProcessingStats], None]] = []
        self._status_callbacks: List[Callable[[str, str], None]] = []
        
        logger.info("BatchStatusTracker initialized")
    
    def register_progress_callback(self, callback: Callable[[ProcessingStats], None]) -> None:
        """
        Register a callback function for progress updates.
        
        Args:
            callback: Function that receives ProcessingStats updates
        """
        self._progress_callbacks.append(callback)
        logger.debug(f"Registered progress callback: {callback.__name__}")
    
    def register_status_callback(self, callback: Callable[[str, str], None]) -> None:
        """
        Register a callback function for status updates.
        
        Args:
            callback: Function that receives (product_key, status_message) updates
        """
        self._status_callbacks.append(callback)
        logger.debug(f"Registered status callback: {callback.__name__}")
    
    def start_batch_session(self, batch_id: str, total_products: int) -> None:
        """
        Start tracking a new batch processing session.
        
        Args:
            batch_id: Unique identifier for the batch
            total_products: Total number of products to process
        """
        with self._lock:
            self._stats = ProcessingStats(
                total_products=total_products,
                start_time=datetime.now()
            )
            self._active_sessions[batch_id] = self._stats
        
        logger.info(f"Started batch session '{batch_id}' with {total_products} products")
        self._notify_progress_callbacks()
    
    def update_product_status(self, product_key: str, status: str, 
                            success: Optional[bool] = None,
                            processing_time_ms: Optional[int] = None,
                            error_message: Optional[str] = None) -> None:
        """
        Update status for a specific product.
        
        Args:
            product_key: Product identifier
            status: Current status message
            success: Whether processing was successful (if completed)
            processing_time_ms: Processing time in milliseconds
            error_message: Error message if failed
        """
        with self._lock:
            # Update completion status
            if success is not None:
                self._stats.completed_products += 1
                
                if success:
                    self._stats.successful_products += 1
                else:
                    self._stats.failed_products += 1
                
                # Decrease in-progress count
                if self._stats.in_progress_products > 0:
                    self._stats.in_progress_products -= 1
            
            # Update in-progress count for starting products
            elif "started" in status.lower() or "processing" in status.lower():
                self._stats.in_progress_products += 1
        
        # Log status update
        status_symbol = "✅" if success is True else "❌" if success is False else "🔄"
        time_info = f" ({processing_time_ms}ms)" if processing_time_ms else ""
        logger.info(f"{status_symbol} {product_key}: {status}{time_info}")
        
        if error_message:
            logger.error(f"   Error: {error_message}")
        
        # Notify callbacks
        self._notify_status_callbacks(product_key, status)
        self._notify_progress_callbacks()
    
    def complete_batch_session(self, batch_id: str) -> ProcessingStats:
        """
        Complete a batch processing session and return final statistics.
        
        Args:
            batch_id: Batch identifier to complete
            
        Returns:
            Final processing statistics
        """
        with self._lock:
            final_stats = self._stats
            if batch_id in self._active_sessions:
                del self._active_sessions[batch_id]
        
        duration = final_stats.elapsed_seconds
        success_rate = final_stats.success_rate
        
        logger.info(f"Completed batch session '{batch_id}': "
                   f"{final_stats.successful_products}/{final_stats.total_products} successful "
                   f"({success_rate:.1f}%), duration: {duration:.1f}s")
        
        return final_stats
    
    def get_current_stats(self) -> ProcessingStats:
        """Get current processing statistics."""
        with self._lock:
            return self._stats
    
    def get_session_stats(self, batch_id: str) -> Optional[ProcessingStats]:
        """
        Get statistics for a specific batch session.
        
        Args:
            batch_id: Batch identifier
            
        Returns:
            ProcessingStats for the session or None if not found
        """
        with self._lock:
            return self._active_sessions.get(batch_id)
    
    def generate_progress_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive progress report.
        
        Returns:
            Dictionary with detailed progress information
        """
        with self._lock:
            stats = self._stats
            
            return {
                'current_time': datetime.now().isoformat(),
                'batch_progress': {
                    'total_products': stats.total_products,
                    'completed_products': stats.completed_products,
                    'successful_products': stats.successful_products,
                    'failed_products': stats.failed_products,
                    'in_progress_products': stats.in_progress_products,
                    'success_rate': stats.success_rate,
                    'completion_rate': stats.completion_rate
                },
                'timing': {
                    'start_time': stats.start_time.isoformat(),
                    'elapsed_seconds': stats.elapsed_seconds,
                    'estimated_remaining_seconds': stats.estimated_remaining_seconds
                },
                'performance': {
                    'products_per_second': stats.completed_products / max(stats.elapsed_seconds, 1),
                    'average_processing_time': stats.elapsed_seconds / max(stats.completed_products, 1)
                }
            }
    
    def get_historical_performance(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get historical performance data from database records.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with historical performance metrics
        """
        since_time = datetime.now() - timedelta(hours=hours)
        stats = self.record_manager.get_processing_statistics(since=since_time)
        
        return {
            'time_period': f'last_{hours}_hours',
            'since': since_time.isoformat(),
            'database_statistics': stats,
            'performance_analysis': self._analyze_performance(stats)
        }
    
    def print_progress_table(self) -> None:
        """Print a formatted progress table to console."""
        with self._lock:
            stats = self._stats
        
        print("\n" + "="*60)
        print(f"{'BATCH PROCESSING PROGRESS':^60}")
        print("="*60)
        
        print(f"Total Products:      {stats.total_products:>6}")
        print(f"Completed:          {stats.completed_products:>6} ({stats.completion_rate:>5.1f}%)")
        print(f"Successful:         {stats.successful_products:>6} ({stats.success_rate:>5.1f}%)")
        print(f"Failed:             {stats.failed_products:>6}")
        print(f"In Progress:        {stats.in_progress_products:>6}")
        
        print("-"*60)
        
        elapsed = stats.elapsed_seconds
        remaining = stats.estimated_remaining_seconds
        
        print(f"Elapsed Time:       {self._format_duration(elapsed):>10}")
        if remaining:
            print(f"Est. Remaining:     {self._format_duration(remaining):>10}")
        
        if stats.completed_products > 0:
            avg_time = elapsed / stats.completed_products
            print(f"Avg per Product:    {self._format_duration(avg_time):>10}")
        
        print("="*60)
    
    def _notify_progress_callbacks(self) -> None:
        """Notify all registered progress callbacks."""
        if not self._progress_callbacks:
            return
        
        try:
            for callback in self._progress_callbacks:
                callback(self._stats)
        except Exception as e:
            logger.warning(f"Progress callback failed: {e}")
    
    def _notify_status_callbacks(self, product_key: str, status: str) -> None:
        """Notify all registered status callbacks."""
        if not self._status_callbacks:
            return
        
        try:
            for callback in self._status_callbacks:
                callback(product_key, status)
        except Exception as e:
            logger.warning(f"Status callback failed: {e}")
    
    def _analyze_performance(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze performance statistics and identify potential issues.
        
        Args:
            stats: Database statistics from record manager
            
        Returns:
            Performance analysis results
        """
        analysis = {
            'overall_health': 'good',
            'issues': [],
            'recommendations': []
        }
        
        # Check success rate
        success_rate = stats.get('success_rate', 0)
        if success_rate < 80:
            analysis['overall_health'] = 'poor' if success_rate < 50 else 'fair'
            analysis['issues'].append(f"Low success rate: {success_rate:.1f}%")
            analysis['recommendations'].append("Review failed products and common error patterns")
        
        # Check strategy performance
        strategy_stats = stats.get('strategy_performance', {})
        if strategy_stats:
            for strategy, strategy_data in strategy_stats.items():
                strategy_success_rate = (
                    strategy_data.get('succeeded', {}).get('count', 0) /
                    max(sum(status_data.get('count', 0) for status_data in strategy_data.values()), 1) * 100
                )
                
                if strategy_success_rate < 70:
                    analysis['issues'].append(f"Strategy '{strategy}' has low success rate: {strategy_success_rate:.1f}%")
                    analysis['recommendations'].append(f"Review and optimize {strategy} strategy implementation")
        
        # Check for processing time anomalies
        if strategy_stats:
            avg_times = []
            for strategy_data in strategy_stats.values():
                for status_data in strategy_data.values():
                    if isinstance(status_data, dict) and status_data.get('avg_processing_time_ms'):
                        avg_times.append(status_data['avg_processing_time_ms'])
            
            if avg_times:
                max_time = max(avg_times)
                avg_time = sum(avg_times) / len(avg_times)
                
                if max_time > avg_time * 3:  # If any strategy takes 3x longer than average
                    analysis['issues'].append("Significant performance variation between strategies")
                    analysis['recommendations'].append("Investigate slow strategies for optimization opportunities")
        
        return analysis
    
    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"


# Convenience function for simple progress tracking
def create_simple_progress_tracker(print_progress: bool = True) -> BatchStatusTracker:
    """
    Create a simple status tracker with console output.
    
    Args:
        print_progress: Whether to print progress updates to console
        
    Returns:
        Configured BatchStatusTracker instance
    """
    tracker = BatchStatusTracker()
    
    if print_progress:
        def print_progress_callback(stats: ProcessingStats):
            if stats.total_products > 0:
                print(f"\rProgress: {stats.completed_products}/{stats.total_products} "
                      f"({stats.completion_rate:.1f}%) - "
                      f"Success: {stats.success_rate:.1f}%", end='', flush=True)
        
        tracker.register_progress_callback(print_progress_callback)
    
    return tracker
