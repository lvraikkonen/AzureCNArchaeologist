#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utils模块 - 纯工具函数集合
提供HTML处理、FAQ处理、内容清理等通用功能
"""

from .html_utils import (
    create_simple_element,
    copy_table_structure,
    is_navigation_element,
    clean_html_content,
    preprocess_image_paths
)

from .faq_utils import (
    is_faq_item,
    process_faq_item,
    extract_qa_content
)

from .content_utils import (
    find_main_content_area,
    is_important_section_title,
    extract_banner_text_content,
    standardize_banner_images
)

from .validation_utils import (
    validate_extracted_data,
    check_required_fields,
    estimate_content_quality
)

from .large_html_utils import (
    LargeHTMLProcessor,
    check_file_processing_strategy,
    monitor_memory_usage
)

__all__ = [
    # HTML处理
    'create_simple_element', 'copy_table_structure', 'is_navigation_element',
    'clean_html_content', 'preprocess_image_paths',

    # FAQ处理
    'is_faq_item', 'process_faq_item', 'extract_qa_content',

    # 内容处理 
    'find_main_content_area', 'is_important_section_title',
    'extract_banner_text_content', 'standardize_banner_images',

    # 验证工具
    'validate_extracted_data', 'check_required_fields', 'estimate_content_quality',

    # 大型文件处理
    'LargeHTMLProcessor', 'check_file_processing_strategy', 'monitor_memory_usage'
]