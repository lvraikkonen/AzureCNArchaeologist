#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强型CMS提取器 - 重构版本
简化为ExtractionCoordinator的客户端，专注于接口和错误处理
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.core.extraction_coordinator import ExtractionCoordinator


class EnhancedCMSExtractor:
    """增强型CMS提取器 - 简化为协调器的客户端"""

    def __init__(self, output_dir: str, config_file: str = ""):
        """
        初始化提取器
        
        Args:
            output_dir: 输出目录
            config_file: 配置文件（为兼容性保留，现在不使用）
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = config_file
        
        # 初始化提取协调器
        self.extraction_coordinator = ExtractionCoordinator(str(self.output_dir))
        
        print(f"🔧 增强型CMS提取器初始化完成")
        print(f"📁 输出目录: {output_dir}")

    def extract_cms_content(self, html_file_path: str, url: str = "") -> Dict[str, Any]:
        """
        统一提取入口 - 委托给协调器处理
        
        Args:
            html_file_path: HTML文件路径
            url: 源URL（如果为空则使用默认URL）
            
        Returns:
            提取的CMS内容数据
        """
        print(f"\n🔧 开始提取增强型CMS内容")
        print(f"📁 源文件: {html_file_path}")
        
        # 验证文件存在
        if not os.path.exists(html_file_path):
            error_msg = f"HTML文件不存在: {html_file_path}"
            print(f"❌ {error_msg}")
            return self._create_error_result(error_msg)
        
        # 如果URL为空，尝试生成默认URL
        if not url:
            product_key = self._detect_product_key_from_path(html_file_path)
            if product_key:
                url = self._get_default_url(product_key)
                print(f"🔗 使用默认URL: {url}")
        
        # 委托给协调器处理
        try:
            print("🎯 委托给提取协调器处理...")
            result = self.extraction_coordinator.coordinate_extraction(html_file_path, url)
            
            # 添加提取器级别的元数据
            if isinstance(result, dict):
                if "extraction_metadata" not in result:
                    result["extraction_metadata"] = {}
                
                result["extraction_metadata"].update({
                    "extractor_version": "enhanced_v3.0_simplified",
                    "extractor_mode": "coordinator_delegated",
                    "output_dir": str(self.output_dir)
                })
            
            print("✅ 提取完成")
            return result
            
        except Exception as e:
            error_msg = f"提取过程失败: {str(e)}"
            print(f"❌ {error_msg}")
            return self._create_error_result(error_msg, html_file_path, url)

    def _detect_product_key_from_path(self, html_file_path: str) -> Optional[str]:
        """
        从文件路径检测产品类型
        
        Args:
            html_file_path: HTML文件路径
            
        Returns:
            产品key或None
        """
        filename = Path(html_file_path).stem
        
        # 移除常见后缀
        if filename.endswith('-index'):
            return filename
        elif filename.endswith('.html'):
            return filename[:-5]
        else:
            return filename

    def _get_default_url(self, product_key: str) -> str:
        """
        获取产品的默认URL
        
        Args:
            product_key: 产品键名
            
        Returns:
            默认URL
        """
        # 标准化产品键名
        clean_key = product_key.replace('-index', '').replace('_', '-')
        
        return f"https://www.azure.cn/pricing/details/{clean_key}/"

    def _create_error_result(self, error_message: str, html_file_path: str = "", url: str = "") -> Dict[str, Any]:
        """
        创建错误结果
        
        Args:
            error_message: 错误信息
            html_file_path: HTML文件路径
            url: 源URL
            
        Returns:
            错误结果字典
        """
        return {
            "error": error_message,
            "source_file": html_file_path,
            "source_url": url,
            "extraction_timestamp": datetime.now().isoformat(),
            "extraction_metadata": {
                "extractor_version": "enhanced_v3.0_simplified",
                "status": "failed",
                "error_details": error_message,
                "extraction_mode": "coordinator_delegated"
            },
            "validation": {
                "is_valid": False,
                "errors": [error_message],
                "warnings": [],
                "quality_score": 0.0
            }
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取提取器统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "extractor_version": "enhanced_v3.0_simplified",
            "mode": "coordinator_delegated",
            "output_directory": str(self.output_dir),
            "coordinator_initialized": hasattr(self, 'extraction_coordinator'),
            "supported_features": [
                "产品自动检测",
                "智能策略选择",
                "多区域内容提取",
                "CMS格式输出",
                "错误处理和回退",
                "完整数据验证"
            ]
        }

    # 为兼容性保留一些可能被CLI或测试使用的方法
    def _clean_html_content(self, content: str) -> str:
        """
        HTML内容清理 - 兼容性方法
        
        Args:
            content: HTML内容
            
        Returns:
            清理后的内容
        """
        # 简单的HTML清理
        if not content:
            return ""
        
        # 移除多余的空白
        import re
        content = re.sub(r'\s+', ' ', content.strip())
        
        return content