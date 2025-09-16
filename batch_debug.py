#!/usr/bin/env python3
"""
Batch Debug entry point for AzureCNArchaeologist
Provides easy single-step debugging interface for batch processing system
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import batch processing components for debugging
from src.batch.process_engine import BatchProcessEngine
from src.batch.record_manager import BatchProcessRecordManager
from src.batch.status_tracker import BatchStatusTracker
from src.batch.models import BatchProcessStatus, BatchProcessRecord
from src.core.product_manager import ProductManager
from src.core.extraction_coordinator import ExtractionCoordinator


# Configuration for debugging
debug_category = "ai-ml"  # Change this to test different categories
debug_language = "zh-cn" # Change this to test different languages
html_base_dir = "data/prod-html"
output_dir = "batch_debug_output"


def debug_product_discovery():
    """Debug the product discovery system"""
    print("=== Debug: Product Discovery System ===")

    # Step 1: Initialize ProductManager
    print("\n--- Step 1: Initialize ProductManager ---")
    try:
        pm = ProductManager()
        print("✅ ProductManager initialized")
        print(f"Config directory: {pm.config_dir}")
    except Exception as e:
        print(f"❌ ProductManager initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 2: Load and examine products index
    print("\n--- Step 2: Load Products Index ---")
    try:
        products_index = pm.load_products_index()
        print(f"✅ Products index loaded")
        print(f"Total products: {products_index.get('total_products', 'N/A')}")
        print(f"Categories: {list(products_index.get('categories', {}).keys())}")

        # Check if debug_category exists
        categories = products_index.get('categories', {})
        if debug_category in categories:
            category_info = categories[debug_category]
            print(f"✅ Category '{debug_category}' found")
            print(f"Products in category: {category_info.get('products', [])}")
        else:
            print(f"❌ Category '{debug_category}' not found in index")
            print(f"Available categories: {list(categories.keys())}")
    except Exception as e:
        print(f"❌ Products index loading failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 3: Test category-based product discovery
    print("\n--- Step 3: Test Category-based Product Discovery ---")
    try:
        products_by_category = pm.get_products_by_category(debug_category)
        print(f"✅ Product discovery completed")
        print(f"Products by category result: {products_by_category}")

        if debug_category in products_by_category:
            products_list = products_by_category[debug_category]
            print(f"Products in '{debug_category}': {products_list}")
        else:
            print(f"❌ No products found in category '{debug_category}'")
    except Exception as e:
        print(f"❌ Category-based discovery failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 4: Test HTML file discovery
    print("\n--- Step 4: Test HTML File Discovery ---")
    try:
        found_products = pm.find_products_for_category(debug_category, debug_language, html_base_dir)
        print(f"✅ HTML file discovery completed")
        print(f"Found {len(found_products)} products with HTML files")

        for product_info in found_products:
            print(f"  - {product_info['product_key']}: {product_info['html_path']}")
    except Exception as e:
        print(f"❌ HTML file discovery failed: {e}")
        import traceback
        traceback.print_exc()

    # Step 5: Check HTML directory structure
    print("\n--- Step 5: Check HTML Directory Structure ---")
    try:
        html_path = Path(html_base_dir)
        print(f"HTML base directory: {html_path}")
        print(f"Directory exists: {html_path.exists()}")

        if html_path.exists():
            print(f"Contents: {list(html_path.iterdir())[:10]}")  # Show first 10 items

            # Check language-specific directories
            lang_dir = html_path / debug_language
            print(f"Language directory ({debug_language}): {lang_dir}")
            print(f"Language directory exists: {lang_dir.exists()}")

            if lang_dir.exists():
                category_dir = lang_dir / debug_category
                print(f"Category directory: {category_dir}")
                print(f"Category directory exists: {category_dir.exists()}")

                if category_dir.exists():
                    html_files = list(category_dir.glob("*.html"))
                    print(f"HTML files in category: {[f.name for f in html_files]}")
    except Exception as e:
        print(f"❌ Directory structure check failed: {e}")
        import traceback
        traceback.print_exc()


def debug_batch_engine():
    """Debug the batch processing engine"""
    print("=== Debug: Batch Processing Engine ===")

    # Step 1: Initialize BatchProcessEngine
    print("\n--- Step 1: Initialize BatchProcessEngine ---")
    try:
        record_manager = BatchProcessRecordManager()
        engine = BatchProcessEngine(record_manager=record_manager, max_workers=1)
        print("✅ BatchProcessEngine initialized")
        print(f"Max workers: {engine.max_workers}")
        print(f"Max retries: {engine.max_retries}")
    except Exception as e:
        print(f"❌ BatchProcessEngine initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 2: Test product group discovery
    print("\n--- Step 2: Test Product Group Discovery ---")
    try:
        products = engine._get_products_for_group(debug_category, html_base_dir, debug_language)
        print(f"✅ Product group discovery completed")
        print(f"Found {len(products)} products for group '{debug_category}'")

        for product_info in products:
            print(f"  - {product_info.product_key}")
            print(f"    HTML: {product_info.html_file_path}")
            print(f"    Output: {product_info.output_dir}")
            print(f"    Group: {product_info.product_group}")
            print(f"    Language: {product_info.language}")
    except Exception as e:
        print(f"❌ Product group discovery failed: {e}")
        import traceback
        traceback.print_exc()

    # Step 3: Test all product groups
    print("\n--- Step 3: Test All Product Groups ---")
    try:
        all_groups = engine._get_all_product_groups()
        print(f"✅ All product groups discovery completed")
        print(f"Available groups: {all_groups}")

        if debug_category not in all_groups:
            print(f"❌ Debug category '{debug_category}' not in available groups")
        else:
            print(f"✅ Debug category '{debug_category}' found in available groups")
    except Exception as e:
        print(f"❌ All product groups discovery failed: {e}")
        import traceback
        traceback.print_exc()


def debug_record_manager():
    """Debug the batch record management system"""
    print("=== Debug: Batch Record Management ===")

    # Step 1: Initialize Record Manager
    print("\n--- Step 1: Initialize Record Manager ---")
    try:
        record_manager = BatchProcessRecordManager()
        print("✅ Record Manager initialized")
        print(f"Database path: {getattr(record_manager, 'db_path', 'N/A')}")
    except Exception as e:
        print(f"❌ Record Manager initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 2: Test database connection
    print("\n--- Step 2: Test Database Connection ---")
    try:
        # Try to get statistics to test connection
        since_time = datetime.now() - timedelta(hours=24)
        stats = record_manager.get_processing_statistics(since=since_time)
        print("✅ Database connection successful")
        print(f"Recent statistics: {stats}")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        import traceback
        traceback.print_exc()

    # Step 3: Test record creation
    print("\n--- Step 3: Test Record Creation ---")
    try:
        test_record = BatchProcessRecord(
            product_key="test-product",
            product_group="test-group",
            processing_status=BatchProcessStatus.PENDING,
            html_file_path="/test/path.html",
            metadata={'test': True}
        )

        record_id = record_manager.create_record(test_record)
        print(f"✅ Test record created with ID: {record_id}")

        # Clean up test record
        # record_manager.delete_record(record_id)  # If this method exists
        print("✅ Record creation test completed")
    except Exception as e:
        print(f"❌ Record creation failed: {e}")
        import traceback
        traceback.print_exc()


def debug_configuration():
    """Debug configuration and environment setup"""
    print("=== Debug: Configuration and Environment ===")

    # Step 1: Check directory structure
    print("\n--- Step 1: Check Directory Structure ---")

    required_dirs = [
        html_base_dir,
        output_dir,
        "data/configs",
        "src/batch",
        "src/core"
    ]

    for dir_path in required_dirs:
        path = Path(dir_path)
        exists = path.exists()
        is_dir = path.is_dir() if exists else False
        print(f"  {dir_path}: {'✅' if exists and is_dir else '❌'} {'Directory' if is_dir else 'Missing or not a directory'}")

        if exists and is_dir:
            try:
                contents = list(path.iterdir())[:5]  # Show first 5 items
                print(f"    Contents (first 5): {[item.name for item in contents]}")
            except PermissionError:
                print(f"    ❌ Permission denied accessing directory")

    # Step 2: Check configuration files
    print("\n--- Step 2: Check Configuration Files ---")

    config_files = [
        "data/configs/products-index.json",
        "data/configs/categories.json",
        "CLAUDE.md"
    ]

    for config_file in config_files:
        path = Path(config_file)
        exists = path.exists()
        print(f"  {config_file}: {'✅' if exists else '❌'}")

        if exists:
            try:
                if config_file.endswith('.json'):
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    print(f"    JSON valid, keys: {list(data.keys())[:5]}")
                else:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    print(f"    File size: {len(content)} characters")
            except Exception as e:
                print(f"    ❌ Error reading file: {e}")

    # Step 3: Check Python environment
    print("\n--- Step 3: Check Python Environment ---")
    print(f"Python version: {sys.version}")
    print(f"Python path: {sys.path[:3]}...")  # Show first 3 paths

    # Check critical imports
    critical_modules = [
        "src.batch.process_engine",
        "src.core.product_manager",
        "src.core.extraction_coordinator"
    ]

    for module_name in critical_modules:
        try:
            __import__(module_name)
            print(f"  {module_name}: ✅")
        except ImportError as e:
            print(f"  {module_name}: ❌ {e}")


def debug_end_to_end_batch():
    """Debug end-to-end batch processing"""
    print("=== Debug: End-to-End Batch Processing ===")

    # Step 1: Create debug output directory
    print("\n--- Step 1: Setup Debug Environment ---")
    try:
        os.makedirs(output_dir, exist_ok=True)
        print(f"✅ Debug output directory created: {output_dir}")
    except Exception as e:
        print(f"❌ Failed to create output directory: {e}")
        return

    # Step 2: Initialize components
    print("\n--- Step 2: Initialize All Components ---")
    try:
        record_manager = BatchProcessRecordManager()
        engine = BatchProcessEngine(record_manager=record_manager, max_workers=1)
        pm = ProductManager()
        print("✅ All components initialized")
    except Exception as e:
        print(f"❌ Component initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 3: Test specific category processing
    print(f"\n--- Step 3: Test Category '{debug_category}' Processing ---")
    try:
        report = engine.process_product_group(
            group_name=debug_category,
            output_dir=output_dir,
            force_refresh=True,
            html_base_dir=html_base_dir,
            language=debug_language
        )

        print("✅ Category processing completed")
        print(f"Batch ID: {report.batch_id}")
        print(f"Total products: {report.total_products}")
        print(f"Successful: {report.successful_products}")
        print(f"Failed: {report.failed_products}")
        print(f"Success rate: {report.success_rate:.1f}%")
        print(f"Duration: {report.duration_seconds:.1f}s")

        if report.processing_results:
            print("\nProcessing results:")
            for result in report.processing_results:
                status = "✅" if result.success else "❌"
                print(f"  {status} {result.product_key}: {result.processing_time_ms}ms")
                if not result.success:
                    print(f"    Error: {result.error_message}")
    except Exception as e:
        print(f"❌ Category processing failed: {e}")
        import traceback
        traceback.print_exc()


def debug_specific_product():
    """Debug processing of a specific product"""
    print("=== Debug: Specific Product Processing ===")

    # Step 1: Find a product to test
    print("\n--- Step 1: Find Test Product ---")
    try:
        pm = ProductManager()
        found_products = pm.find_products_for_category(debug_category, debug_language, html_base_dir)

        if not found_products:
            print(f"❌ No products found for category '{debug_category}'")
            return

        test_product = found_products[0]  # Use first product
        print(f"✅ Using test product: {test_product['product_key']}")
        print(f"HTML file: {test_product['html_path']}")
    except Exception as e:
        print(f"❌ Product discovery failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 2: Test extraction coordinator
    print("\n--- Step 2: Test Extraction Coordinator ---")
    try:
        coordinator = ExtractionCoordinator(output_dir)
        print("✅ Extraction coordinator initialized")

        # Test coordinate_extraction
        result = coordinator.coordinate_extraction(
            test_product['html_path'],
            url=""
        )

        print("✅ Extraction completed")
        print(f"Result type: {type(result)}")
        if isinstance(result, dict):
            print(f"Result keys: {list(result.keys())}")
            if 'extraction_metadata' in result:
                metadata = result['extraction_metadata']
                print(f"Strategy used: {metadata.get('strategy_used')}")
                print(f"Processing mode: {metadata.get('processing_mode')}")
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main debug entry point"""
    print("AzureCNArchaeologist Batch Processing Debug Interface")
    print("=" * 60)
    print(f"Debug Configuration:")
    print(f"  Category: {debug_category}")
    print(f"  Language: {debug_language}")
    print(f"  HTML Base Dir: {html_base_dir}")
    print(f"  Output Dir: {output_dir}")
    print("=" * 60)

    # Create debug output directory
    os.makedirs(output_dir, exist_ok=True)

    # Choose what to debug
    debug_options = {
        "1": ("Product Discovery System", debug_product_discovery),
        "2": ("Batch Processing Engine", debug_batch_engine),
        "3": ("Record Management System", debug_record_manager),
        "4": ("Configuration and Environment", debug_configuration),
        "5": ("End-to-End Batch Processing", debug_end_to_end_batch),
        "6": ("Specific Product Processing", debug_specific_product),
    }

    print("\nAvailable debug options:")
    for key, (desc, _) in debug_options.items():
        print(f"  {key}: {desc}")
    print(f"  a: Run all debug modules")

    # Auto-run product discovery for debugging (you can change this)
    selected = "1"  # Change this to debug different components

    print(f"\nRunning debug option: {selected}")
    if selected == "a":
        # Run all debug modules
        for key in sorted(debug_options.keys()):
            desc, debug_func = debug_options[key]
            print(f"\n{'='*60}")
            print(f"Running: {desc}")
            print(f"{'='*60}")
            try:
                debug_func()
            except Exception as e:
                print(f"Debug module '{desc}' failed: {e}")
                import traceback
                traceback.print_exc()
    elif selected in debug_options:
        _, debug_func = debug_options[selected]
        try:
            debug_func()
        except Exception as e:
            print(f"Debug failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Invalid option selected")

    print(f"\nDebug completed. Check {output_dir}/ for results.")


if __name__ == "__main__":
    # Set breakpoint here for debugging
    main()