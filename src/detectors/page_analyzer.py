"""
Page structure and complexity analyzer.

This module provides the core PageAnalyzer class for analyzing page complexity
and structure to determine appropriate extraction strategies.
"""

import os
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

from ..core.data_models import (
    PageComplexity, PageType
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
        pass
    
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
        
        # Region filter pages
        if complexity.has_region_filter:
            return PageType.REGION_FILTER
        
        # Simple static pages
        return PageType.SIMPLE_STATIC