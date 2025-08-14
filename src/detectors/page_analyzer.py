"""
Page structure and complexity analyzer.

This module provides the core PageAnalyzer class for analyzing page complexity
and structure to determine appropriate extraction strategies.
"""

import os
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

from ..core.data_models import (
    PageComplexity, FilterAnalysis, TabAnalysis, RegionAnalysis,
    PageType, FilterType
)
from .filter_detector import FilterDetector
from .tab_detector import TabDetector
from ..core.logging import get_logger

logger = get_logger(__name__)


class PageAnalyzer:
    """
    Core page complexity analyzer.
    
    Analyzes HTML pages to determine their structural complexity and
    identify key interactive elements for strategy selection.
    """
    
    def __init__(self):
        """Initialize the page analyzer."""
        self.large_file_threshold_mb = 5.0  # 5MB threshold for large files
        self.filter_detector = FilterDetector()
        self.tab_detector = TabDetector()
        logger.info("初始化PageAnalyzer - 基于3策略架构")
        
    def analyze_page_complexity(self, soup: BeautifulSoup, 
                               html_file_path: Optional[str] = None) -> PageComplexity:
        """
        Analyze page complexity and structure.
        
        Args:
            soup: BeautifulSoup object of the HTML page
            html_file_path: Optional path to HTML file for size analysis
            
        Returns:
            PageComplexity object with analysis results
        """
        # File size analysis
        file_size_mb = 0.0
        is_large_file = False
        if html_file_path and os.path.exists(html_file_path):
            file_size_mb = self._get_file_size_mb(html_file_path)
            is_large_file = file_size_mb > self.large_file_threshold_mb
        
        # Basic structure detection
        has_region_filter = self._detect_region_filters(soup)
        has_tabs = self._detect_tab_structures(soup)
        has_multiple_filters = self._detect_multiple_filters(soup)
        
        # Interactive elements count
        interactive_elements = self._count_interactive_elements(soup)
        
        # Create detailed analysis objects (placeholder for now)
        filter_analysis = self._create_basic_filter_analysis(soup, has_region_filter)
        tab_analysis = self._create_basic_tab_analysis(soup, has_tabs)
        region_analysis = self._create_basic_region_analysis(soup, has_region_filter)
        
        # Create complexity object
        complexity = PageComplexity(
            has_region_filter=has_region_filter,
            has_tabs=has_tabs,
            has_multiple_filters=has_multiple_filters,
            interactive_elements=interactive_elements,
            file_size_mb=file_size_mb,
            is_large_file=is_large_file,
            filter_analysis=filter_analysis,
            tab_analysis=tab_analysis,
            region_analysis=region_analysis
        )
        
        return complexity
    
    def determine_page_type_v3(self, soup: BeautifulSoup) -> str:
        """
        基于3策略架构确定页面类型。
        
        决策逻辑：
        - 无technical-azure-selector OR 所有筛选器都隐藏 → SimpleStatic
        - 只有region-container可见 AND 无复杂tab → RegionFilter  
        - 其他情况 → Complex
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            策略类型: "SimpleStatic", "RegionFilter", "Complex"
        """
        logger.info("🔍 开始3策略页面类型分析...")
        
        # 使用新的检测器获取分析结果
        filter_analysis = self.filter_detector.detect_filters(soup)
        tab_analysis = self.tab_detector.detect_tabs(soup)
        
        logger.info(f"筛选器分析: region={filter_analysis['has_region']}({filter_analysis['region_visible']}), software={filter_analysis['has_software']}({filter_analysis['software_visible']})")
        logger.info(f"Tab分析: container={tab_analysis['has_main_container']}, complex_tabs={tab_analysis.get('has_complex_tabs', False)}")
        
        # 策略1: 无主容器或所有筛选器隐藏 → SimpleStatic
        if not tab_analysis['has_main_container']:
            logger.info("✅ 决策: SimpleStatic (无主容器)")
            return "SimpleStatic"
        
        if not filter_analysis['region_visible'] and not filter_analysis['software_visible']:
            logger.info("✅ 决策: SimpleStatic (所有筛选器隐藏)")
            return "SimpleStatic"
        
        # 策略2: 只有region可见且无复杂tab → RegionFilter  
        if (filter_analysis['region_visible'] and 
            not filter_analysis['software_visible'] and
            not tab_analysis.get('has_complex_tabs', False)):
            logger.info("✅ 决策: RegionFilter (只有region可见且无复杂tab)")
            return "RegionFilter"
        
        # 策略3: 其他情况 → Complex
        logger.info("✅ 决策: Complex (其他复杂情况)")
        return "Complex"
    
    def _get_file_size_mb(self, file_path: str) -> float:
        """Get file size in MB."""
        try:
            size_bytes = os.path.getsize(file_path)
            return size_bytes / (1024 * 1024)
        except OSError:
            return 0.0
    
    def _detect_region_filters(self, soup: BeautifulSoup) -> bool:
        """
        Detect if page has region filtering capabilities.
        
        Looks for common region filter patterns used in Azure China pages.
        """
        # Common region filter selectors
        region_selectors = [
            # Dropdown selectors
            'select[name*="region"]',
            'select[id*="region"]',
            'select[class*="region"]',
            
            # Radio button groups
            'input[type="radio"][name*="region"]',
            'input[type="radio"][value*="china"]',
            
            # Custom dropdowns and buttons
            '.region-selector',
            '.region-dropdown',
            '#region-select',
            '[data-region]',
            
            # Azure-specific patterns
            '.pricing-dropdown',
            '.region-pricing-dropdown',
            'button[data-toggle*="region"]',
            
            # Text-based indicators
            'div:contains("选择区域")',
            'label:contains("区域")',
            'span:contains("中国北部")',
            'span:contains("中国东部")'
        ]
        
        for selector in region_selectors:
            try:
                if soup.select(selector):
                    return True
            except Exception:
                # Invalid selector, continue
                continue
        
        # Check for text-based region indicators
        page_text = soup.get_text().lower()
        region_keywords = [
            '选择区域', '区域选择', '中国北部', '中国东部', 
            'china north', 'china east', 'region selector'
        ]
        
        return any(keyword in page_text for keyword in region_keywords)
    
    def _detect_tab_structures(self, soup: BeautifulSoup) -> bool:
        """
        Detect if page has tab-based content organization.
        
        Distinguishes between region-based tabs and content-organization tabs.
        Only returns True for genuine content organization tabs.
        """
        # Azure China specific tab navigation (primary indicators)
        azure_tab_nav_selectors = [
            '.tab-items',           # Azure custom tab navigation
            'ol.tab-items',         # Ordered list tab items
            '.category-tabs',       # Category tab navigation
            '.os-tab-nav'          # OS tab navigation
        ]
        
        # Standard tab navigation selectors
        standard_tab_nav_selectors = [
            '.nav-tabs',
            '.nav-pills', 
            '.tab-nav',
            '.tabs',
            'ul[role="tablist"]',
            '.pricing-tabs',
            '.service-tabs',
            '.product-tabs'
        ]
        
        # Check for Azure custom tab navigation
        has_genuine_azure_tabs = False
        for selector in azure_tab_nav_selectors:
            nav_elements = soup.select(selector)
            for nav in nav_elements:
                # Skip if navigation is hidden on medium/large screens
                nav_classes = nav.get('class', [])
                if any(cls in nav_classes for cls in ['hidden-md', 'hidden-lg']):
                    continue
                
                tab_items = nav.select('li, option')
                if len(tab_items) > 1:
                    # Check if tabs are region-based (should be excluded)
                    tab_texts = [item.get_text().strip().lower() for item in tab_items]
                    region_keywords = ['中国', 'china', '北部', 'north', '东部', 'east', '华北', '华东']
                    
                    # If most tabs contain region keywords, consider it region filtering, not content tabs
                    region_tab_count = sum(1 for text in tab_texts 
                                         if any(keyword in text for keyword in region_keywords))
                    
                    # If less than 80% are region-related, consider it genuine content tabs
                    if region_tab_count / len(tab_texts) < 0.8:
                        has_genuine_azure_tabs = True
                        break
        
        # Check for standard tab navigation
        has_standard_tab_nav = False
        for selector in standard_tab_nav_selectors:
            if soup.select(selector):
                has_standard_tab_nav = True
                break
        
        # Interactive tab elements (strong indicators)
        interactive_tab_selectors = [
            'button[role="tab"]',
            'a[role="tab"]',
            '[data-toggle="tab"]'
        ]
        
        has_interactive_tabs = False
        for selector in interactive_tab_selectors:
            if soup.select(selector):
                has_interactive_tabs = True
                break
        
        # Azure tab content areas
        azure_content_selectors = ['.tab-content', '.tab-panel']
        azure_content_count = 0
        for selector in azure_content_selectors:
            azure_content_count += len(soup.select(selector))
        
        # Standard content areas
        standard_content_selectors = ['.tab-pane', '[role="tabpanel"]']
        standard_content_count = 0
        for selector in standard_content_selectors:
            standard_content_count += len(soup.select(selector))
        
        # Detection logic:
        # 1. Azure custom tabs: genuine navigation + multiple content panels
        if has_genuine_azure_tabs and azure_content_count > 1:
            return True
        
        # 2. Standard tabs: navigation + content areas  
        if (has_standard_tab_nav or has_interactive_tabs) and (standard_content_count > 1 or azure_content_count > 1):
            return True
        
        return False
    
    def _detect_multiple_filters(self, soup: BeautifulSoup) -> bool:
        """
        Detect if page has multiple filtering options beyond region.
        
        Looks for OS/Software filters, service tier filters, etc.
        Only returns True if there are actual interactive filter elements beyond region.
        """
        # Azure China specific filter patterns
        azure_filter_selectors = [
            # Software/service type filters
            'select[id*="software"]',
            'select.software-box',
            
            # Category/tier filters  
            'select.category-tabs',
            'select[class*="category"]',
            
            # Storage/tier type filters
            'select[id*="tier"]',
            'select[id*="storage"]',
            'select[id*="type"]'
        ]
        
        # Standard filter element selectors (non-region)
        standard_filter_selectors = [
            # Dropdown selectors (non-region)
            'select[name*="os"]:not([name*="region"])',
            'select[name*="software"]:not([name*="region"])', 
            'select[name*="tier"]:not([name*="region"])',
            'select[name*="plan"]:not([name*="region"])',
            'select[name*="type"]:not([name*="region"])',
            
            # Radio button groups (non-region)
            'input[type="radio"][name*="os"]',
            'input[type="radio"][name*="software"]',
            'input[type="radio"][name*="tier"]',
            
            # Custom interactive filters
            '.filter-dropdown select',
            '.pricing-filter select',
            '.service-filter select',
            
            # Filter groups with interactive elements
            '.filter-group select',
            '.filter-group input[type="radio"]',
            '.pricing-options select'
        ]
        
        # Count Azure-specific filters (avoid double-counting same elements)
        azure_filter_elements = set()  # Use set to avoid duplicates
        for selector in azure_filter_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    # Check if this is a functional filter (has multiple options)
                    options = element.select('option')
                    if len(options) > 1:  # More than just placeholder/loading
                        option_texts = [opt.get_text().strip() for opt in options]
                        # Skip if it's just loading or empty options
                        non_empty_options = [text for text in option_texts if text and '加载中' not in text]
                        if len(non_empty_options) > 1:
                            # Use element's position as unique identifier
                            element_id = str(element)
                            azure_filter_elements.add(element_id)
            except Exception:
                continue
        
        azure_filter_count = len(azure_filter_elements)
        
        # Count standard filters
        standard_filter_count = 0
        for selector in standard_filter_selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    standard_filter_count += len(elements)
            except Exception:
                continue
        
        total_non_region_filters = azure_filter_count + standard_filter_count
        
        # Return True if we find MULTIPLE (>=2) functional filter types beyond region
        # Single category filters are common but don't constitute "multi-filter" complexity
        return total_non_region_filters >= 2
    
    def _count_interactive_elements(self, soup: BeautifulSoup) -> int:
        """
        Count interactive elements on the page.
        
        Counts buttons, inputs, dropdowns, and other interactive components.
        """
        interactive_selectors = [
            'button',
            'input',
            'select',
            'textarea',
            '[onclick]',
            '[data-toggle]',
            '.btn',
            '.button'
        ]
        
        total_count = 0
        for selector in interactive_selectors:
            elements = soup.select(selector)
            total_count += len(elements)
        
        return total_count
    
    def _create_basic_filter_analysis(self, soup: BeautifulSoup, 
                                    has_region_filter: bool) -> FilterAnalysis:
        """Create basic filter analysis (detailed implementation will be in FilterDetector)."""
        if has_region_filter:
            return FilterAnalysis(
                has_filters=True,
                filters=[],  # Will be populated by FilterDetector
                primary_filter_type=FilterType.REGION
            )
        else:
            return FilterAnalysis(has_filters=False)
    
    def _create_basic_tab_analysis(self, soup: BeautifulSoup, has_tabs: bool) -> TabAnalysis:
        """Create basic tab analysis (detailed implementation will be in TabDetector)."""
        if has_tabs:
            # Basic tab count estimation
            tab_elements = soup.select('.nav-tabs li, .tabs > li, [role="tab"]')
            return TabAnalysis(
                has_tabs=True,
                tabs=[],  # Will be populated by TabDetector
                tab_count=len(tab_elements)
            )
        else:
            return TabAnalysis(has_tabs=False)
    
    def _create_basic_region_analysis(self, soup: BeautifulSoup, 
                                    has_region_filter: bool) -> RegionAnalysis:
        """Create basic region analysis (detailed implementation will be in RegionDetector)."""
        if has_region_filter:
            return RegionAnalysis(
                has_regions=True,
                regions=[],  # Will be populated by RegionDetector
                region_selector_found=True
            )
        else:
            return RegionAnalysis(has_regions=False)
    
    def get_recommended_page_type(self, complexity: PageComplexity) -> PageType:
        """
        Recommend page type based on complexity analysis.
        
        Args:
            complexity: PageComplexity analysis result
            
        Returns:
            Recommended PageType for strategy selection
        """
        # Large file takes precedence
        if complexity.is_large_file:
            return PageType.LARGE_FILE
        
        # Multi-filter pages
        if complexity.has_multiple_filters and complexity.has_tabs:
            return PageType.MULTI_FILTER
        
        # Region + Tab combination
        if complexity.has_region_filter and complexity.has_tabs:
            return PageType.REGION_TAB
        
        # Simple tab pages
        if complexity.has_tabs and not complexity.has_region_filter:
            return PageType.TAB
        
        # Region filter pages
        if complexity.has_region_filter:
            return PageType.REGION_FILTER
        
        # Simple static pages
        return PageType.SIMPLE_STATIC