#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML内容清理工具
纯HTML清理函数
"""

import re


def clean_html_content(content: str) -> str:
    """
    清理HTML内容中的多余标签和符号
    
    Args:
        content: 原始HTML内容
        
    Returns:
        清理后的HTML内容
    """
    if not content:
        return content

    # 移除多余的换行符和空白符
    content = re.sub(r'\n+', ' ', content)  # 将多个换行符替换为单个空格
    content = re.sub(r'\s+', ' ', content)  # 将多个空白符替换为单个空格

    # 移除多余的div标签包装（保留有用的class和id）
    # 只移除纯粹的包装div，保留有意义的div
    content = re.sub(r'<div>\s*</div>', '', content)  # 移除空的div标签

    # 清理标签间的多余空白
    content = re.sub(r'>\s+<', '><', content)  # 移除标签间的空白

    # 移除开头和结尾的空白
    content = content.strip()

    return content