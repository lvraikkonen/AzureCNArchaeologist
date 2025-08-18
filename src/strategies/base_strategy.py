#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础策略抽象类 - 纯抽象基类，定义所有提取策略的核心接口
Phase 2重构：精简为<50行，移除具体实现，添加flexible JSON支持
"""

import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))


class BaseStrategy(ABC):
    """基础策略抽象类 - 纯抽象接口定义"""

    def __init__(self, product_config: Dict[str, Any], html_file_path: str = ""):
        """
        初始化基础策略
        
        Args:
            product_config: 产品配置信息
            html_file_path: HTML文件路径
        """
        self.product_config = product_config
        self.html_file_path = html_file_path
        
        # 工具类注入点（由具体策略或工厂负责注入）
        self.content_extractor = None
        self.section_extractor = None
        self.flexible_builder = None
        self.extraction_validator = None

    # @abstractmethod
    # def extract(self, soup: BeautifulSoup, url: str = "") -> Dict[str, Any]:
    #     """
    #     执行传统CMS格式提取逻辑（向后兼容）
    #
    #     Args:
    #         soup: BeautifulSoup解析的HTML对象
    #         url: 源URL
    #
    #     Returns:
    #         传统CMS格式的提取数据
    #     """
    #     pass

    @abstractmethod
    def extract_flexible_content(self, soup: BeautifulSoup, url: str = "") -> Dict[str, Any]:
        """
        执行flexible JSON格式提取逻辑
        
        Args:
            soup: BeautifulSoup解析的HTML对象
            url: 源URL
            
        Returns:
            flexible JSON格式的提取数据
        """
        pass

    @abstractmethod
    def extract_common_sections(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        提取通用sections（Banner、Description、QA等）
        
        Args:
            soup: BeautifulSoup解析的HTML对象
            
        Returns:
            commonSections列表
        """
        pass