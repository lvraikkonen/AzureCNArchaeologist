"""
Detectors module for page structure analysis.

This module contains components for analyzing page complexity and structure:
- PageAnalyzer: Core page complexity analysis
- FilterDetector: Filter element detection
- TabDetector: Tab structure detection  
- RegionDetector: Region selector detection
"""

# Import implemented components
from .page_analyzer import PageAnalyzer

# Will be populated as additional components are implemented
# from .filter_detector import FilterDetector
# from .tab_detector import TabDetector
# from .region_detector import RegionDetector

__all__ = ['PageAnalyzer']