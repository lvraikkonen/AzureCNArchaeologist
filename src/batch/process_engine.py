"""
Parallel batch processing engine for flexible JSON content extraction.

This module provides high-performance batch processing capabilities with
ProductGroup support, intelligent retry logic, and real-time monitoring.
"""

import os
import time
from src.core.logging import get_logger
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass

from .models import (
    BatchProcessRecord, BatchProcessStatus, ProcessingResult, 
    BatchProcessReport
)
from .record_manager import BatchProcessRecordManager
from ..core.extraction_coordinator import ExtractionCoordinator
from ..core.product_manager import ProductManager


logger = get_logger(__name__)


@dataclass
class ProductProcessingInfo:
    """Information needed to process a single product."""
    product_key: str
    html_file_path: str
    product_group: str
    output_dir: str
    language: str = "zh-cn"
    url: str = ""


class BatchProcessEngine:
    """
    High-performance batch processing engine with parallel execution.
    
    Features:
    - Configurable parallel workers (4-8 concurrent threads)
    - Intelligent retry logic with exponential backoff
    - Real-time status tracking and progress monitoring
    - ProductGroup-based processing organization
    - Database record integration
    """
    
    def __init__(self, record_manager: Optional[BatchProcessRecordManager] = None,
                 max_workers: int = 4, max_retries: int = 3):
        """
        Initialize the batch processing engine.
        
        Args:
            record_manager: Database record manager for tracking processing
            max_workers: Maximum number of parallel workers
            max_retries: Maximum retry attempts for failed processing
        """
        self.record_manager = record_manager or BatchProcessRecordManager()
        self.product_manager = ProductManager()
        self.max_workers = max_workers
        self.max_retries = max_retries
        
        # Progress tracking
        self.progress_callback: Optional[Callable[[str, int, int], None]] = None
        
        logger.info(f"BatchProcessEngine initialized with {max_workers} workers")
    
    def set_progress_callback(self, callback: Callable[[str, int, int], None]) -> None:
        """
        Set callback function for progress updates.
        
        Args:
            callback: Function that receives (message, current, total) parameters
        """
        self.progress_callback = callback
    
    def process_product_group(self, group_name: str, output_dir: str,
                            force_refresh: bool = False,
                            html_base_dir: str = "data/prod-html",
                            language: str = "zh-cn") -> BatchProcessReport:
        """
        Process all products in a specific ProductGroup.
        
        Args:
            group_name: Name of the product group to process
            output_dir: Base output directory for results
            force_refresh: Force processing even if content hasn't changed
            html_base_dir: Base directory containing HTML files
            language: Language version ("zh-cn" or "en-us")
            
        Returns:
            BatchProcessReport with comprehensive processing results
        """
        batch_id = f"{group_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        report = BatchProcessReport(
            batch_id=batch_id,
            start_time=datetime.now()
        )
        
        logger.info(f"Starting batch processing for group '{group_name}' (batch_id: {batch_id})")
        
        try:
            # Get products for this group
            products = self._get_products_for_group(group_name, html_base_dir, language, output_dir)
            if not products:
                logger.warning(f"No products found for group '{group_name}' in language '{language}'")
                report.finalize()
                return report
            
            report.products_by_group[group_name] = len(products)
            logger.info(f"Found {len(products)} products in group '{group_name}'")
            
            # Filter products that need processing
            if not force_refresh:
                products = self._filter_products_for_processing(products)
                logger.info(f"After change detection: {len(products)} products need processing")
            
            if not products:
                logger.info("No products require processing (content unchanged)")
                report.finalize()
                return report
            
            # Process products in parallel
            results = self._process_products_parallel(products, output_dir, batch_id)
            
            # Compile results into report
            for result in results:
                report.add_result(result)
            
            report.finalize()
            
            # Log summary
            success_rate = report.success_rate
            duration = report.duration_seconds
            logger.info(f"Batch processing completed: {report.successful_products}/{report.total_products} "
                       f"successful ({success_rate:.1f}%), duration: {duration:.1f}s")
            
            return report
            
        except Exception as e:
            logger.error(f"Batch processing failed for group '{group_name}': {e}", exc_info=True)
            report.finalize()
            return report
    
    def process_all_products(self, output_dir: str, force_refresh: bool = False,
                           html_base_dir: str = "data/prod-html",
                           language: str = "zh-cn") -> Dict[str, BatchProcessReport]:
        """
        Process all products across all ProductGroups.
        
        Args:
            output_dir: Base output directory for results
            force_refresh: Force processing even if content hasn't changed
            html_base_dir: Base directory containing HTML files
            language: Language version ("zh-cn" or "en-us")
            
        Returns:
            Dictionary mapping group names to BatchProcessReport instances
        """
        logger.info("Starting batch processing for ALL product groups")
        start_time = datetime.now()
        
        # Get all product groups
        all_groups = self._get_all_product_groups()
        reports = {}
        
        total_products = 0
        total_successful = 0
        
        for group_name in all_groups:
            logger.info(f"Processing group: {group_name}")
            
            report = self.process_product_group(
                group_name, output_dir, force_refresh, html_base_dir, language
            )
            reports[group_name] = report
            
            total_products += report.total_products
            total_successful += report.successful_products
        
        # Log overall summary
        duration = (datetime.now() - start_time).total_seconds()
        overall_success_rate = (total_successful / max(total_products, 1)) * 100
        
        logger.info(f"ALL groups processing completed: {total_successful}/{total_products} "
                   f"successful ({overall_success_rate:.1f}%), total duration: {duration:.1f}s")
        
        return reports
    
    def retry_failed_products(self, output_dir: str, 
                            since_hours: int = 24) -> BatchProcessReport:
        """
        Retry processing for products that failed in recent batches.
        
        Args:
            output_dir: Base output directory for results
            since_hours: Look for failures within this many hours
            
        Returns:
            BatchProcessReport for retry processing
        """
        since_time = datetime.now() - timedelta(hours=since_hours)
        failed_records = self.record_manager.get_failed_records(since=since_time)
        
        if not failed_records:
            logger.info("No recent failures found for retry processing")
            return BatchProcessReport(
                batch_id=f"retry_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                start_time=datetime.now()
            )
        
        logger.info(f"Found {len(failed_records)} failed records for retry")
        
        # Convert failed records to ProductProcessingInfo
        products = []
        for record in failed_records:
            if record.retry_count >= self.max_retries:
                logger.warning(f"Skipping {record.product_key}: max retries exceeded")
                continue
                
            if not record.html_file_path or not os.path.exists(record.html_file_path):
                logger.warning(f"Skipping {record.product_key}: HTML file not found")
                continue
            
            products.append(ProductProcessingInfo(
                product_key=record.product_key,
                html_file_path=record.html_file_path,
                product_group=record.product_group or "unknown",
                output_dir=output_dir
            ))
        
        if not products:
            logger.info("No valid products found for retry processing")
            return BatchProcessReport(
                batch_id=f"retry_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                start_time=datetime.now()
            )
        
        # Process retry products
        batch_id = f"retry_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return self._process_products_with_report(products, output_dir, batch_id)
    
    def _get_products_for_group(self, group_name: str, html_base_dir: str,
                               language: str = "zh-cn",
                               output_base_dir: str = None) -> List[ProductProcessingInfo]:
        """Get list of products for a specific group with language support."""
        products = []

        try:
            # Use ProductManager's new file discovery capability
            found_products = self.product_manager.find_products_for_category(
                group_name, language, html_base_dir
            )

            for product_info in found_products:
                # Use caller-supplied output_base_dir if provided, otherwise use default
                if output_base_dir:
                    resolved_output_dir = self.product_manager.get_output_directory(
                        product_info['product_key'], language, output_base_dir
                    )
                else:
                    resolved_output_dir = product_info['output_dir']

                try:
                    # Get product configuration for URL
                    config = self.product_manager.get_product_config(product_info['product_key'])
                    url = config.get('url', '')

                    products.append(ProductProcessingInfo(
                        product_key=product_info['product_key'],
                        html_file_path=product_info['html_path'],
                        product_group=product_info['category'],
                        output_dir=resolved_output_dir,
                        language=product_info['language'],
                        url=url
                    ))

                except Exception as e:
                    logger.warning(f"Failed to get config for product {product_info['product_key']}: {e}")
                    # Still add product with minimal info
                    products.append(ProductProcessingInfo(
                        product_key=product_info['product_key'],
                        html_file_path=product_info['html_path'],
                        product_group=product_info['category'],
                        output_dir=resolved_output_dir,
                        language=product_info['language'],
                        url=""
                    ))
            
        except Exception as e:
            logger.error(f"Failed to get products for group '{group_name}': {e}")
        
        return products
    
    def _get_all_product_groups(self) -> List[str]:
        """Get list of all available product groups."""
        try:
            # Use ProductManager's category listing capability
            categories = self.product_manager.get_products_by_category()
            return sorted(list(categories.keys()))
        except Exception as e:
            logger.error(f"Failed to get product groups: {e}")
            return []
    
    
    def _filter_products_for_processing(self, 
                                      products: List[ProductProcessingInfo]) -> List[ProductProcessingInfo]:
        """Filter products that need processing based on content changes."""
        filtered = []
        
        for product_info in products:
            should_process, reason = self.record_manager.should_process_product(
                product_info.product_key, product_info.html_file_path
            )
            
            if should_process:
                logger.debug(f"{product_info.product_key}: {reason}")
                filtered.append(product_info)
            else:
                logger.debug(f"Skipping {product_info.product_key}: {reason}")
        
        return filtered
    
    def _process_products_parallel(self, products: List[ProductProcessingInfo],
                                 output_dir: str, batch_id: str) -> List[ProcessingResult]:
        """Process products in parallel using ThreadPoolExecutor."""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_product = {
                executor.submit(self._process_single_product, product, batch_id): product
                for product in products
            }
            
            # Process completed tasks
            completed = 0
            total = len(products)
            
            for future in as_completed(future_to_product):
                product = future_to_product[future]
                completed += 1
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    status = "✅" if result.success else "❌"
                    logger.info(f"{status} ({completed}/{total}) {product.product_key}: "
                              f"{result.processing_time_ms}ms")
                    
                    # Progress callback
                    if self.progress_callback:
                        self.progress_callback(f"Processed {product.product_key}", completed, total)
                        
                except Exception as e:
                    logger.error(f"❌ ({completed}/{total}) {product.product_key}: {e}")
                    
                    # Create failed result
                    results.append(ProcessingResult(
                        product_key=product.product_key,
                        success=False,
                        error_message=str(e)
                    ))
        
        return results
    
    def _process_single_product(self, product_info: ProductProcessingInfo,
                              batch_id: str) -> ProcessingResult:
        """Process a single product with full error handling and database tracking."""
        start_time = time.time()
        
        # Create initial database record
        record = BatchProcessRecord(
            product_key=product_info.product_key,
            product_group=product_info.product_group,
            processing_status=BatchProcessStatus.PROCESSING,
            html_file_path=product_info.html_file_path,
            metadata={'batch_id': batch_id}
        )
        
        record_id = self.record_manager.create_record(record)
        
        try:
            # Initialize extraction coordinator
            coordinator = ExtractionCoordinator(product_info.output_dir)
            
            # Perform extraction
            extracted_data = coordinator.coordinate_extraction(
                product_info.html_file_path, 
                product_info.url
            )
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Check if extraction was successful
            if extracted_data and not extracted_data.get('error'):
                # Export the extracted data using FlexibleContentExporter
                from src.exporters.flexible_content_exporter import FlexibleContentExporter
                exporter = FlexibleContentExporter(product_info.output_dir)
                output_file = exporter.export_flexible_content(extracted_data, product_info.product_key)
                logger.info(f"JSON文件已导出: {output_file}")
                
                # Update record as successful
                
                self.record_manager.update_record(
                    record_id,
                    processing_status=BatchProcessStatus.SUCCESS,
                    processing_time_ms=processing_time_ms,
                    output_file_path=output_file,
                    strategy_used=extracted_data.get('extraction_metadata', {}).get('strategy_used'),
                    extraction_timestamp=datetime.utcnow()
                )
                
                return ProcessingResult(
                    product_key=product_info.product_key,
                    success=True,
                    strategy_used=extracted_data.get('extraction_metadata', {}).get('strategy_used'),
                    processing_time_ms=processing_time_ms,
                    output_file_path=output_file,
                    content_hash=self.record_manager.calculate_file_hash(product_info.html_file_path)
                )
            else:
                # Extraction failed
                error_msg = extracted_data.get('error', 'Unknown extraction error')
                
                self.record_manager.update_record(
                    record_id,
                    processing_status=BatchProcessStatus.FAILED,
                    processing_time_ms=processing_time_ms,
                    error_message=error_msg,
                    extraction_timestamp=datetime.utcnow()
                )
                
                return ProcessingResult(
                    product_key=product_info.product_key,
                    success=False,
                    processing_time_ms=processing_time_ms,
                    error_message=error_msg
                )
                
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Processing exception: {str(e)}"
            
            # Update record as failed
            self.record_manager.update_record(
                record_id,
                processing_status=BatchProcessStatus.FAILED,
                processing_time_ms=processing_time_ms,
                error_message=error_msg,
                extraction_timestamp=datetime.utcnow()
            )
            
            return ProcessingResult(
                product_key=product_info.product_key,
                success=False,
                processing_time_ms=processing_time_ms,
                error_message=error_msg
            )
    
    def _find_output_file(self, product_info: ProductProcessingInfo) -> Optional[str]:
        """Find the generated output file for a product."""
        output_dir = Path(product_info.output_dir)
        if not output_dir.exists():
            return None
        
        # Look for flexible JSON files with the product key
        pattern = f"{product_info.product_key}_flexible_content_*.json"
        matching_files = list(output_dir.glob(pattern))
        
        if matching_files:
            # Return the most recent file
            latest_file = max(matching_files, key=lambda p: p.stat().st_mtime)
            return str(latest_file)
        
        return None
    
    def _process_products_with_report(self, products: List[ProductProcessingInfo],
                                    output_dir: str, batch_id: str) -> BatchProcessReport:
        """Process products and generate a comprehensive report."""
        report = BatchProcessReport(
            batch_id=batch_id,
            start_time=datetime.now()
        )
        
        results = self._process_products_parallel(products, output_dir, batch_id)
        
        for result in results:
            report.add_result(result)
        
        report.finalize()
        return report