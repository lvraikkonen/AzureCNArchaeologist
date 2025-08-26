#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片处理工具
保留CMS兼容的{base_url}占位符
"""

import re
from bs4 import BeautifulSoup


def preprocess_image_paths(soup: BeautifulSoup) -> BeautifulSoup:
    """
    预处理图片路径，添加{base_url}占位符
    
    Args:
        soup: BeautifulSoup对象
        
    Returns:
        处理后的BeautifulSoup对象
    """
    print("🖼️ 预处理图片路径...")

    # 处理img标签的src属性
    img_count = 0
    for img in soup.find_all('img'):
        src = img.get('src')
        if src and src.startswith('/') and not src.startswith('{base_url}'):
            img['src'] = f"{{base_url}}{src}"
            img_count += 1

    # 处理style属性中的background-image
    style_count = 0
    for element in soup.find_all(style=True):
        style = element.get('style', '')
        if 'background-image:' in style and 'url(' in style:
            # 匹配 url("/path/to/image") 或 url('/path/to/image')
            pattern = r'url\(["\']?(/[^"\']*?)["\']?\)'
            def replace_url(match):
                path = match.group(1)
                return f'url("{{base_url}}{path}")'

            new_style = re.sub(pattern, replace_url, style)
            if new_style != style:
                element['style'] = new_style
                style_count += 1

    # 处理data-config属性中的图片路径
    data_config_count = 0
    for element in soup.find_all(attrs={'data-config': True}):
        data_config = element.get('data-config', '')
        if data_config and ('backgroundImage' in data_config or 'background-image' in data_config):
            # 匹配 backgroundImage 或 background-image 后面的图片路径
            pattern = r'(["\'](backgroundImage|background-image)["\']:\s*["\'])(/[^"\']*?)(["\'])'
            def replace_bg_image(match):
                prefix = match.group(1)
                path = match.group(3)
                suffix = match.group(4)
                return f'{prefix}{{base_url}}{path}{suffix}'

            new_data_config = re.sub(pattern, replace_bg_image, data_config)
            if new_data_config != data_config:
                element['data-config'] = new_data_config
                data_config_count += 1

    print(f"  ✓ 处理了 {img_count} 个img标签、{style_count} 个style属性和 {data_config_count} 个data-config属性")

    return soup