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
        logger.info("🔍 开始页面复杂度分析...")
        
        # 获取文件大小信息
        file_size_mb = 0.0
        is_large_file = False
        if html_file_path:
            file_size_mb = self._get_file_size_mb(html_file_path)
            is_large_file = file_size_mb > self.large_file_threshold_mb
            
        # 使用新的检测器进行分析
        filter_analysis = self.filter_detector.detect_filters(soup)
        tab_analysis = self.tab_detector.detect_tabs(soup)
        
        # 基于3+1策略架构的复杂度判断
        has_region_filter = filter_analysis.get('has_region', False) and filter_analysis.get('region_visible', False)
        has_tabs = tab_analysis.get('has_complex_tabs', False)  # 使用复杂tab判断
        has_multiple_filters = (
            filter_analysis.get('has_region', False) and 
            filter_analysis.get('has_software', False) and 
            filter_analysis.get('software_visible', False)
        )
        
        # 计算交互元素数量
        interactive_elements = 0
        if filter_analysis.get('region_options'):
            interactive_elements += len(filter_analysis['region_options'])
        if filter_analysis.get('software_options'):
            interactive_elements += len(filter_analysis['software_options'])
        if tab_analysis.get('total_category_tabs'):
            interactive_elements += tab_analysis['total_category_tabs']
            
        logger.info(f"复杂度分析结果: region_filter={has_region_filter}, tabs={has_tabs}, multiple_filters={has_multiple_filters}")
        logger.info(f"文件大小: {file_size_mb:.2f}MB, 大文件: {is_large_file}, 交互元素: {interactive_elements}")
        
        return PageComplexity(
            has_region_filter=has_region_filter,
            has_tabs=has_tabs,
            has_multiple_filters=has_multiple_filters,
            file_size_mb=file_size_mb,
            is_large_file=is_large_file,
            interactive_elements=interactive_elements,
            filter_analysis=None,  # 简化架构，不需要详细分析对象
            tab_analysis=None,     # 简化架构，不需要详细分析对象
            region_analysis=None   # 简化架构，不需要详细分析对象
        )
    
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
        Recommend page type based on complexity analysis for 3+1 strategy architecture.
        
        Args:
            complexity: PageComplexity analysis result
            
        Returns:
            Recommended PageType for strategy selection
        """
        logger.info("📋 根据复杂度分析推荐页面类型...")
        
        # Large file takes precedence
        if complexity.is_large_file:
            logger.info("✅ 推荐: LARGE_FILE (文件大小超过阈值)")
            return PageType.LARGE_FILE
        
        # Complex pages: multiple filters + tabs
        if complexity.has_multiple_filters or complexity.has_tabs:
            logger.info("✅ 推荐: COMPLEX (多筛选器或复杂tab结构)")
            return PageType.COMPLEX
        
        # Region filter pages: only region filter visible
        if complexity.has_region_filter:
            logger.info("✅ 推荐: REGION_FILTER (只有区域筛选器)")
            return PageType.REGION_FILTER
        
        # Simple static pages: no visible filters or tabs
        logger.info("✅ 推荐: SIMPLE_STATIC (无可见筛选器)")
        return PageType.SIMPLE_STATIC