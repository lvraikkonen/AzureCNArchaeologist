#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utils模块 - 纯工具函数集合
提供HTML处理、内容处理、数据验证等通用功能
"""

# HTML处理工具
from .html.element_creator import (
    create_simple_element,
    copy_table_structure,
    is_navigation_element
)

from .html.cleaner import clean_html_content

# 媒体处理工具
from .media.image_processor import preprocess_image_paths

# 内容处理工具
from .content.content_utils import (
    find_main_content_area,
    is_important_section_title,
    extract_banner_text_content,
    standardize_banner_images,
    extract_structured_content,
    # FAQ相关功能
    is_faq_item,
    process_faq_item,
    extract_qa_content
)

# 数据验证工具
from .data.validation_utils import (
    validate_extracted_data
)

# 通用工具
from .common.large_html_utils import (
    LargeHTMLProcessor
)

__all__ = [
    # HTML处理
    'create_simple_element', 'copy_table_structure', 'is_navigation_element',
    'clean_html_content', 
    
    # 媒体处理
    'preprocess_image_paths',

    # 内容处理 
    'find_main_content_area', 'is_important_section_title',
    'extract_banner_text_content', 'standardize_banner_images',
    'extract_structured_content',
    
    # FAQ处理
    'is_faq_item', 'process_faq_item', 'extract_qa_content',

    # 数据验证
    'validate_extracted_data',

    # 通用工具
    'LargeHTMLProcessor'
]