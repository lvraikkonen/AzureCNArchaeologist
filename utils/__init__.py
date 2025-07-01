#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML处理工具包
用于Azure定价页面的HTML内容提取和处理
"""

from .html_processor import (
    RegionFilterProcessor,
    HTMLProcessor, 
    HTMLBuilder,
    validate_html_structure
)

__version__ = "1.0.0"
__author__ = "Azure Pricing Extractor Team"

__all__ = [
    "RegionFilterProcessor",
    "HTMLProcessor", 
    "HTMLBuilder",
    "validate_html_structure"
]