#!/usr/bin/env python3
"""
Debug entry point for AzureCNArchaeologist
Provides easy single-step debugging interface similar to cli.py
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import core components for debugging
from src.core.extraction_coordinator import ExtractionCoordinator
from src.core.strategy_manager import StrategyManager
from src.core.product_manager import ProductManager
from src.detectors.page_analyzer import PageAnalyzer
from src.strategies.strategy_factory import StrategyFactory
from src.extractors.enhanced_cms_extractor import EnhancedCMSExtractor


# Configuration
product_key = "app-service"
html_file = "data/prod-html/compute/app-service.html"
output_dir = "debug_output"


def debug_extraction_pipeline():
    """Debug the full extraction pipeline"""
    print("=== Debug: Full Extraction Pipeline ===")
    
    print(f"Product: {product_key}")
    print(f"HTML File: {html_file}")
    print(f"Output Dir: {output_dir}")
    
    # Step 1: Initialize coordinator
    print("\n--- Step 1: Initialize ExtractionCoordinator ---")
    coordinator = ExtractionCoordinator(output_dir)
    print("✅ ExtractionCoordinator initialized")

    # Step 2: Run extraction
    print("\n--- Step 2: Execute Extraction ---")
    try:
        result = coordinator.coordinate_extraction(html_file, url="")
        print("✅ Extraction completed successfully")
        print(f"Result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")

        # Save result to output directory
        import json
        output_file = os.path.join(output_dir, f"{product_key}_extraction_result.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✅ Result saved to: {output_file}")

    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        import traceback
        traceback.print_exc()


def debug_strategy_system():
    """Debug the strategy management system"""
    print("=== Debug: Strategy System ===")
    
    # Step 1: Initialize components
    print("\n--- Step 1: Initialize Components ---")
    product_manager = ProductManager()
    strategy_manager = StrategyManager(product_manager)
    page_analyzer = PageAnalyzer()
    print("✅ Components initialized")
    
    # Step 2: Test page analysis
    print("\n--- Step 2: Page Analysis ---")
    if os.path.exists(html_file):
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Convert HTML string to BeautifulSoup object
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        analysis_result = page_analyzer.analyze_page_complexity(soup, html_file)
        print(f"Page complexity: {analysis_result}")
    else:
        print(f"❌ HTML file not found: {html_file}")
    
    # Step 3: Test strategy determination
    print("\n--- Step 3: Strategy Determination ---")
    try:
        strategy = strategy_manager.determine_extraction_strategy(html_file, "api-management")
        print(f"Selected strategy: {strategy.strategy_type.value}")
        print(f"Strategy processor: {strategy.processor}")
        print(f"Strategy features: {strategy.features}")
    except Exception as e:
        print(f"❌ Strategy determination failed: {e}")
        import traceback
        traceback.print_exc()


def debug_strategy_factory():
    """Debug the strategy factory system"""
    print("=== Debug: Strategy Factory ===")
    
    # Step 1: Check registration status
    print("\n--- Step 1: Strategy Registration Status ---")
    status = StrategyFactory.get_registration_status()
    print(f"Registered strategies: {status['registered_strategies']}")
    print(f"Total strategies: {status['total_strategies']}")
    print(f"Available strategies: {list(status['available_strategies'].keys())}")
    
    # Step 2: Test strategy creation
    print("\n--- Step 2: Test Strategy Creation ---")
    try:
        from src.core.data_models import StrategyDecision, StrategyType
        
        decision = StrategyDecision(
            strategy_type=StrategyType.REGION_FILTER,
            processor="region_filter_processor",
            features=["region_processing", "pricing_extraction"]
        )
        
        product_manager = ProductManager()
        strategy = StrategyFactory.create_strategy(decision, product_manager, "api-management")
        print(f"✅ Strategy created: {type(strategy).__name__}")
        print(f"Strategy type: {strategy.strategy_type.value}")
        
    except Exception as e:
        print(f"❌ Strategy creation failed: {e}")
        import traceback
        traceback.print_exc()


def debug_enhanced_extractor():
    """Debug the enhanced CMS extractor"""
    print("=== Debug: Enhanced CMS Extractor ===")
    
    # Step 1: Initialize extractor
    print("\n--- Step 1: Initialize Extractor ---")
    extractor = EnhancedCMSExtractor("api-management")
    print("✅ EnhancedCMSExtractor initialized")
    
    # Step 2: Test extraction
    print("\n--- Step 2: Test Extraction ---")
    
    if os.path.exists(html_file):
        try:
            result = extractor.extract_cms_content(html_file, output_dir, format="json")
            print("✅ Extraction completed")
            print(f"Output file: {result.get('output_file', 'N/A')}")
        except Exception as e:
            print(f"❌ Extraction failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"❌ HTML file not found: {html_file}")


def debug_product_manager():
    """Debug the product manager"""
    print("=== Debug: Product Manager ===")
    
    # Step 1: Initialize and test
    print("\n--- Step 1: Initialize ProductManager ---")
    pm = ProductManager()
    print("✅ ProductManager initialized")
    
    # Step 2: Test product operations
    print("\n--- Step 2: Test Product Operations ---")
    supported_products = pm.get_supported_products()
    print(f"Supported products count: {len(supported_products)}")
    
    # Step 3: Test specific product config
    print("\n--- Step 3: Test Product Config ---")
    try:
        config = pm.get_product_config("api-management")
        print(f"✅ API Management config loaded")
        print(f"Config keys: {list(config.keys())}")
    except Exception as e:
        print(f"❌ Config loading failed: {e}")
    
    # Step 4: Cache stats
    print("\n--- Step 4: Cache Stats ---")
    cache_stats = pm.get_cache_stats()
    print(f"Cache stats: {cache_stats}")


def main():
    """Main debug entry point"""
    print("AzureCNArchaeologist Debug Interface")
    print("=" * 50)
    
    # Create debug output directory
    os.makedirs("debug_output", exist_ok=True)
    
    # Choose what to debug
    debug_options = {
        "1": ("Full Extraction Pipeline", debug_extraction_pipeline),
        "2": ("Strategy System", debug_strategy_system),
        "3": ("Strategy Factory", debug_strategy_factory),
        "4": ("Enhanced Extractor", debug_enhanced_extractor),
        "5": ("Product Manager", debug_product_manager),
    }
    
    print("\nAvailable debug options:")
    for key, (desc, _) in debug_options.items():
        if key != "a":
            print(f"  {key}: {desc}")
    print(f"  a: Run all components")
    
    # Auto-run full pipeline for debugging (you can change this)
    selected = "1"  # Change this to debug different components
    
    print(f"\nRunning debug option: {selected}")
    if selected in debug_options:
        _, debug_func = debug_options[selected]
        try:
            debug_func()
        except Exception as e:
            print(f"Debug failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Invalid option selected")
    
    print(f"\nDebug completed. Check debug_output/ for results.")


if __name__ == "__main__":
    # Set breakpoint here for debugging
    main()