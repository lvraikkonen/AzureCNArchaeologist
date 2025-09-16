"""
SQLite database record manager for batch processing operations.

This module provides comprehensive database operations for tracking
batch processing records, including lifecycle management, querying,
and reporting capabilities.
"""

import sqlite3
import hashlib
from src.core.logging import get_logger
from src.core.settings import settings
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from contextlib import contextmanager

from .models import BatchProcessRecord, BatchProcessStatus, BatchProcessReport


logger = get_logger(__name__)


class BatchProcessRecordManager:
    """
    SQLite-based record manager for batch processing operations.
    
    Provides complete lifecycle management for batch processing records,
    including creation, updates, queries, and reporting functionality.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the record manager with SQLite database.
        
        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            # Use configured database path
            db_path = settings.BATCH_DB_PATH
            # Ensure parent directories exist
            db_file = Path(db_path)
            db_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.db_path = db_path
        self._initialize_database()
        
        logger.info(f"BatchProcessRecordManager initialized with database: {self.db_path}")
    
    def _initialize_database(self) -> None:
        """Initialize the SQLite database with required tables and indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create batch_process_records table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS batch_process_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_key VARCHAR(100) NOT NULL,
                    product_group VARCHAR(50),
                    strategy_used VARCHAR(20),
                    processing_status VARCHAR(20) NOT NULL CHECK (
                        processing_status IN ('pending', 'processing', 'success', 'failed', 'retry')
                    ),
                    error_message TEXT,
                    processing_time_ms INTEGER,
                    output_file_path TEXT,
                    html_file_path TEXT,
                    content_hash VARCHAR(64),
                    retry_count INTEGER DEFAULT 0,
                    extraction_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT  -- JSON string for additional metadata
                )
            ''')
            
            # Create indexes for performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_batch_product_key 
                ON batch_process_records(product_key)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_batch_product_group 
                ON batch_process_records(product_group)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_batch_processing_status 
                ON batch_process_records(processing_status)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_batch_extraction_timestamp 
                ON batch_process_records(extraction_timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_batch_content_hash 
                ON batch_process_records(content_hash)
            ''')
            
            conn.commit()
            logger.debug("Database schema initialized successfully")
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections with proper cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        finally:
            conn.close()
    
    def calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA256 hash of a file for content change detection.
        
        Args:
            file_path: Path to the file to hash
            
        Returns:
            SHA256 hash string
        """
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to calculate hash for {file_path}: {e}")
            return ""
    
    def create_record(self, record: BatchProcessRecord) -> int:
        """
        Create a new batch processing record in the database.
        
        Args:
            record: BatchProcessRecord instance to create
            
        Returns:
            ID of the created record
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Calculate content hash if HTML file path is provided
            if record.html_file_path and not record.content_hash:
                record.content_hash = self.calculate_file_hash(record.html_file_path)
            
            cursor.execute('''
                INSERT INTO batch_process_records (
                    product_key, product_group, strategy_used, processing_status,
                    error_message, processing_time_ms, output_file_path, html_file_path,
                    content_hash, retry_count, extraction_timestamp, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.product_key,
                record.product_group,
                record.strategy_used,
                record.processing_status.value,
                record.error_message,
                record.processing_time_ms,
                record.output_file_path,
                record.html_file_path,
                record.content_hash,
                record.retry_count,
                record.extraction_timestamp,
                str(record.metadata) if record.metadata else None
            ))
            
            record_id = cursor.lastrowid
            conn.commit()
            
            logger.debug(f"Created batch record {record_id} for product {record.product_key}")
            return record_id
    
    def update_record(self, record_id: int, **updates) -> bool:
        """
        Update an existing batch processing record.
        
        Args:
            record_id: ID of the record to update
            **updates: Fields to update
            
        Returns:
            True if record was updated, False if not found
        """
        if not updates:
            return False
        
        # Always update the updated_at timestamp
        updates['updated_at'] = datetime.utcnow()
        
        # Convert enum values to strings
        if 'processing_status' in updates and hasattr(updates['processing_status'], 'value'):
            updates['processing_status'] = updates['processing_status'].value
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Build dynamic UPDATE query
            set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
            values = list(updates.values())
            values.append(record_id)
            
            cursor.execute(f'''
                UPDATE batch_process_records 
                SET {set_clause}
                WHERE id = ?
            ''', values)
            
            updated = cursor.rowcount > 0
            conn.commit()
            
            if updated:
                logger.debug(f"Updated batch record {record_id} with fields: {list(updates.keys())}")
            else:
                logger.warning(f"No record found with ID {record_id}")
            
            return updated
    
    def get_record(self, record_id: int) -> Optional[BatchProcessRecord]:
        """
        Retrieve a batch processing record by ID.
        
        Args:
            record_id: ID of the record to retrieve
            
        Returns:
            BatchProcessRecord instance or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM batch_process_records WHERE id = ?
            ''', (record_id,))
            
            row = cursor.fetchone()
            if row:
                return self._row_to_record(row)
            return None
    
    def get_latest_record_for_product(self, product_key: str, 
                                    status: Optional[BatchProcessStatus] = None) -> Optional[BatchProcessRecord]:
        """
        Get the most recent record for a specific product.
        
        Args:
            product_key: Product key to search for
            status: Optional status filter
            
        Returns:
            Most recent BatchProcessRecord or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if status:
                cursor.execute('''
                    SELECT * FROM batch_process_records 
                    WHERE product_key = ? AND processing_status = ?
                    ORDER BY extraction_timestamp DESC LIMIT 1
                ''', (product_key, status.value))
            else:
                cursor.execute('''
                    SELECT * FROM batch_process_records 
                    WHERE product_key = ?
                    ORDER BY extraction_timestamp DESC LIMIT 1
                ''', (product_key,))
            
            row = cursor.fetchone()
            if row:
                return self._row_to_record(row)
            return None
    
    def get_records_by_group(self, product_group: str, 
                           status: Optional[BatchProcessStatus] = None,
                           limit: Optional[int] = None) -> List[BatchProcessRecord]:
        """
        Get records for a specific product group.
        
        Args:
            product_group: Product group to filter by
            status: Optional status filter
            limit: Optional limit on number of records
            
        Returns:
            List of BatchProcessRecord instances
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT * FROM batch_process_records 
                WHERE product_group = ?
            '''
            params = [product_group]
            
            if status:
                query += ' AND processing_status = ?'
                params.append(status.value)
            
            query += ' ORDER BY extraction_timestamp DESC'
            
            if limit:
                query += ' LIMIT ?'
                params.append(limit)
            
            cursor.execute(query, params)
            return [self._row_to_record(row) for row in cursor.fetchall()]
    
    def get_failed_records(self, since: Optional[datetime] = None) -> List[BatchProcessRecord]:
        """
        Get all failed processing records, optionally since a specific time.
        
        Args:
            since: Optional datetime to filter records after
            
        Returns:
            List of failed BatchProcessRecord instances
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if since:
                cursor.execute('''
                    SELECT * FROM batch_process_records 
                    WHERE processing_status = 'failed' AND extraction_timestamp >= ?
                    ORDER BY extraction_timestamp DESC
                ''', (since,))
            else:
                cursor.execute('''
                    SELECT * FROM batch_process_records 
                    WHERE processing_status = 'failed'
                    ORDER BY extraction_timestamp DESC
                ''')
            
            return [self._row_to_record(row) for row in cursor.fetchall()]
    
    def should_process_product(self, product_key: str, html_file_path: str, 
                             force: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Determine if a product should be processed based on content changes.
        
        Args:
            product_key: Product key to check
            html_file_path: Path to HTML file
            force: If True, always return True to process
            
        Returns:
            Tuple of (should_process: bool, reason: str)
        """
        if force:
            return True, "Force processing requested"
        
        # Calculate current file hash
        current_hash = self.calculate_file_hash(html_file_path)
        if not current_hash:
            return True, "Could not calculate file hash, processing as new"
        
        # Get the most recent successful record
        latest_success = self.get_latest_record_for_product(
            product_key, BatchProcessStatus.SUCCESS
        )
        
        if not latest_success:
            return True, "No previous successful processing found"
        
        if latest_success.content_hash != current_hash:
            return True, f"Content has changed (hash: {current_hash[:8]}...)"
        
        # Check if enough time has passed for periodic refresh (e.g., 7 days)
        if latest_success.extraction_timestamp:
            days_since = (datetime.utcnow() - latest_success.extraction_timestamp).days
            if days_since >= 7:
                return True, f"Periodic refresh needed ({days_since} days since last success)"
        
        return False, f"Content unchanged since {latest_success.extraction_timestamp}"
    
    def get_processing_statistics(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get comprehensive processing statistics.
        
        Args:
            since: Optional datetime to filter records after
            
        Returns:
            Dictionary with processing statistics
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            time_filter = ""
            params = []
            if since:
                time_filter = "WHERE extraction_timestamp >= ?"
                params = [since]
            
            # Total counts by status
            cursor.execute(f'''
                SELECT processing_status, COUNT(*) as count
                FROM batch_process_records {time_filter}
                GROUP BY processing_status
            ''', params)
            status_counts = dict(cursor.fetchall())
            
            # Product group statistics
            cursor.execute(f'''
                SELECT product_group, processing_status, COUNT(*) as count
                FROM batch_process_records {time_filter}
                GROUP BY product_group, processing_status
            ''', params)
            group_stats = {}
            for product_group, status, count in cursor.fetchall():
                if product_group not in group_stats:
                    group_stats[product_group] = {}
                group_stats[product_group][status] = count
            
            # Strategy performance
            cursor.execute(f'''
                SELECT strategy_used, processing_status, COUNT(*) as count,
                       AVG(processing_time_ms) as avg_time
                FROM batch_process_records 
                WHERE strategy_used IS NOT NULL {time_filter and 'AND ' + time_filter.replace('WHERE ', '') or ''}
                GROUP BY strategy_used, processing_status
            ''', params)
            strategy_stats = {}
            for strategy, status, count, avg_time in cursor.fetchall():
                if strategy not in strategy_stats:
                    strategy_stats[strategy] = {}
                strategy_stats[strategy][status] = {
                    'count': count,
                    'avg_processing_time_ms': avg_time
                }
            
            return {
                'status_counts': status_counts,
                'group_statistics': group_stats,
                'strategy_performance': strategy_stats,
                'total_records': sum(status_counts.values()),
                'success_rate': (status_counts.get('success', 0) / 
                               max(sum(status_counts.values()), 1)) * 100
            }
    
    def cleanup_old_records(self, older_than_days: int = 30) -> int:
        """
        Clean up old processing records to maintain database performance.
        
        Args:
            older_than_days: Remove records older than this many days
            
        Returns:
            Number of records removed
        """
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM batch_process_records 
                WHERE extraction_timestamp < ? AND processing_status != 'success'
            ''', (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"Cleaned up {deleted_count} old batch processing records")
            return deleted_count
    
    def _row_to_record(self, row: sqlite3.Row) -> BatchProcessRecord:
        """Convert a database row to a BatchProcessRecord instance."""
        import json
        
        record = BatchProcessRecord()
        record.id = row['id']
        record.product_key = row['product_key']
        record.product_group = row['product_group']
        record.strategy_used = row['strategy_used']
        record.processing_status = BatchProcessStatus(row['processing_status'])
        record.error_message = row['error_message']
        record.processing_time_ms = row['processing_time_ms']
        record.output_file_path = row['output_file_path']
        record.html_file_path = row['html_file_path']
        record.content_hash = row['content_hash']
        record.retry_count = row['retry_count']
        
        # Parse datetime fields
        if row['extraction_timestamp']:
            record.extraction_timestamp = datetime.fromisoformat(row['extraction_timestamp'])
        if row['created_at']:
            record.created_at = datetime.fromisoformat(row['created_at'])
        if row['updated_at']:
            record.updated_at = datetime.fromisoformat(row['updated_at'])
        
        # Parse metadata JSON
        if row['metadata']:
            try:
                record.metadata = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
            except (json.JSONDecodeError, TypeError):
                record.metadata = {}
        else:
            record.metadata = {}
        
        return record