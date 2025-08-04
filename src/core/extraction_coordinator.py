#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提取协调器
负责协调整个提取流程，集成策略管理器、策略工厂和各种处理组件
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.core.product_manager import ProductManager
from src.core.strategy_manager import StrategyManager
from src.core.data_models import StrategyType, ExtractionStrategy
from src.strategies.strategy_factory import StrategyFactory
from src.utils.media.image_processor import preprocess_image_paths
from src.utils.data.validation_utils import validate_extracted_data


class ExtractionCoordinator:
    """提取流程协调器 - Phase 3架构的核心组件"""

    def __init__(self, output_dir: str):
        """
        初始化提取协调器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化核心组件
        self.product_manager = ProductManager()
        self.strategy_manager = StrategyManager(self.product_manager)
        
        print(f"🎯 提取协调器初始化完成")
        print(f"📁 输出目录: {self.output_dir}")
        
        # 验证策略注册状态
        self._validate_strategy_setup()

    def coordinate_extraction(self, html_file_path: str, url: str = "") -> Dict[str, Any]:
        """
        协调整个提取流程
        
        Args:
            html_file_path: HTML文件路径
            url: 源URL
            
        Returns:
            提取的CMS内容数据
            
        Raises:
            Exception: 提取过程中的各种异常
        """
        print(f"\n🚀 开始协调提取流程")
        print(f"📄 源文件: {html_file_path}")
        print(f"🔗 源URL: {url}")
        
        try:
            # 阶段1: 检测产品类型
            product_key = self._detect_product_key(html_file_path)
            print(f"📦 检测到产品: {product_key}")
            
            # 阶段2: 获取产品配置
            product_config = self._get_product_config(product_key)
            
            # 阶段3: 策略决策
            extraction_strategy = self._determine_extraction_strategy(html_file_path, product_key)
            print(f"🎯 选择策略: {extraction_strategy.strategy_type.value}")
            print(f"🔧 处理器: {extraction_strategy.processor}")
            
            # 阶段4: 创建策略实例
            strategy_instance = self._create_strategy_instance(
                extraction_strategy, product_config, html_file_path
            )
            
            # 阶段5: 准备HTML内容
            soup = self._prepare_html_content(html_file_path)
            
            # 阶段6: 执行提取
            extracted_data = self._execute_extraction(strategy_instance, soup, url)
            
            # 阶段7: 后处理和验证
            final_data = self._post_process_and_validate(
                extracted_data, product_config, extraction_strategy
            )
            
            print(f"✅ 提取流程完成")
            return final_data
            
        except Exception as e:
            print(f"❌ 提取流程失败: {e}")
            return self._create_error_result(str(e), html_file_path, url)

    def _detect_product_key(self, html_file_path: str) -> str:
        """
        检测产品类型
        
        Args:
            html_file_path: HTML文件路径
            
        Returns:
            产品键
        """
        try:
            product_key = self.product_manager.detect_product_from_filename(html_file_path)
            if product_key:
                return product_key
        except Exception as e:
            print(f"⚠ 产品类型检测失败: {e}")
        
        # 如果检测失败，尝试从文件名推断
        file_name = Path(html_file_path).stem
        if file_name.endswith('-index'):
            return file_name[:-6]  # 移除'-index'后缀
        
        print("⚠ 无法检测产品类型，使用unknown")
        return "unknown"

    def _get_product_config(self, product_key: str) -> Dict[str, Any]:
        """
        获取产品配置
        
        Args:
            product_key: 产品键
            
        Returns:
            产品配置信息
        """
        try:
            config = self.product_manager.get_product_config(product_key)
            print(f"📋 获取产品配置: {len(config)} 个配置项")
            return config
        except Exception as e:
            print(f"⚠ 无法获取产品配置 ({product_key}): {e}")
            # 返回默认配置
            return {
                "product_key": product_key,
                "default_url": f"https://www.azure.cn/pricing/details/{product_key}/",
                "service_name": product_key
            }

    def _determine_extraction_strategy(self, html_file_path: str, product_key: str) -> ExtractionStrategy:
        """
        确定提取策略
        
        Args:
            html_file_path: HTML文件路径
            product_key: 产品键
            
        Returns:
            提取策略配置
        """
        try:
            strategy = self.strategy_manager.determine_extraction_strategy(html_file_path, product_key)
            print(f"💡 策略决策成功: {strategy.strategy_type.value}")
            return strategy
        except Exception as e:
            print(f"⚠ 策略决策失败，使用回退策略: {e}")
            # 返回回退策略
            from src.core.data_models import ExtractionStrategy
            return ExtractionStrategy(
                strategy_type=StrategyType.SIMPLE_STATIC,
                processor="SimpleStaticProcessor",
                description="回退策略",
                features=["基础内容提取"],
                priority_features=["Title", "DescriptionContent"],
                config_overrides={}
            )

    def _create_strategy_instance(self, extraction_strategy: ExtractionStrategy, 
                                 product_config: Dict[str, Any], 
                                 html_file_path: str):
        """
        创建策略实例
        
        Args:
            extraction_strategy: 提取策略配置
            product_config: 产品配置
            html_file_path: HTML文件路径
            
        Returns:
            策略实例
        """
        try:
            strategy = StrategyFactory.create_strategy(
                extraction_strategy, product_config, html_file_path
            )
            print(f"🏭 策略实例创建成功: {strategy.__class__.__name__}")
            return strategy
        except Exception as e:
            print(f"⚠ 策略实例创建失败，使用回退策略: {e}")
            # 使用回退策略
            return StrategyFactory.create_fallback_strategy(product_config, html_file_path)

    def _prepare_html_content(self, html_file_path: str) -> BeautifulSoup:
        """
        准备HTML内容
        
        Args:
            html_file_path: HTML文件路径
            
        Returns:
            BeautifulSoup对象
            
        Raises:
            Exception: 文件读取或解析失败
        """
        print("📖 读取和解析HTML文件...")
        
        # 检查文件是否存在
        if not os.path.exists(html_file_path):
            raise FileNotFoundError(f"HTML文件不存在: {html_file_path}")
        
        # 读取HTML文件
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(html_file_path, 'r', encoding='gbk') as f:
                    html_content = f.read()
            except UnicodeDecodeError:
                with open(html_file_path, 'r', encoding='iso-8859-1') as f:
                    html_content = f.read()
        
        # 解析HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 预处理图片路径
        soup = preprocess_image_paths(soup)
        
        print(f"📊 HTML解析完成: {len(html_content)} 字符")
        return soup

    def _execute_extraction(self, strategy, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        执行提取
        
        Args:
            strategy: 策略实例
            soup: BeautifulSoup对象
            url: 源URL
            
        Returns:
            提取的数据
        """
        print(f"⚙️ 执行提取策略: {strategy.__class__.__name__}")
        
        try:
            extracted_data = strategy.extract(soup, url)
            print(f"✅ 策略提取完成")
            return extracted_data
        except Exception as e:
            print(f"❌ 策略提取失败: {e}")
            raise

    def _post_process_and_validate(self, data: Dict[str, Any], 
                                  product_config: Dict[str, Any],
                                  extraction_strategy: ExtractionStrategy) -> Dict[str, Any]:
        """
        后处理和验证
        
        Args:
            data: 提取的数据
            product_config: 产品配置
            extraction_strategy: 提取策略
            
        Returns:
            处理后的数据
        """
        print("🔍 后处理和验证...")
        
        # 添加提取元数据
        data["extraction_metadata"] = {
            "extractor_version": "enhanced_v3.0",
            "extraction_timestamp": datetime.now().isoformat(),
            "strategy_used": extraction_strategy.strategy_type.value,
            "processor_used": extraction_strategy.processor,
            "processing_mode": "strategy_coordinated",
            "page_complexity_score": getattr(extraction_strategy, 'complexity_score', 0.0),
            "strategy_features": extraction_strategy.features,
            "priority_features": extraction_strategy.priority_features
        }
        
        # 数据验证
        try:
            validation_result = validate_extracted_data(data, product_config)
            data["validation"] = validation_result
            print(f"✅ 数据验证完成: {'有效' if validation_result.get('is_valid') else '无效'}")
        except Exception as e:
            print(f"⚠ 数据验证失败: {e}")
            data["validation"] = {
                "is_valid": False,
                "errors": [str(e)],
                "warnings": []
            }
        
        return data

    def _create_error_result(self, error_message: str, html_file_path: str, url: str) -> Dict[str, Any]:
        """
        创建错误结果
        
        Args:
            error_message: 错误信息
            html_file_path: HTML文件路径
            url: 源URL
            
        Returns:
            错误结果数据
        """
        return {
            "error": error_message,
            "source_file": str(html_file_path),
            "source_url": url,
            "extraction_timestamp": datetime.now().isoformat(),
            "extraction_metadata": {
                "extractor_version": "enhanced_v3.0",
                "status": "failed",
                "error_message": error_message
            },
            "validation": {
                "is_valid": False,
                "errors": [error_message],
                "warnings": []
            }
        }

    def _validate_strategy_setup(self) -> None:
        """验证策略设置"""
        print("🔧 验证策略设置...")
        
        # 检查策略注册状态
        status = StrategyFactory.get_registration_status()
        registered_count = status["registered_strategies"]
        total_count = status["total_strategies"]
        
        print(f"📊 策略注册状态: {registered_count}/{total_count} "
              f"({status['completion_rate']:.1f}%)")
        
        if status["missing"]:
            print(f"⚠ 缺少策略: {[s['strategy_type'] for s in status['missing']]}")
        
        # 如果没有注册任何策略，给出警告
        if registered_count == 0:
            print("⚠ 警告: 没有注册任何策略，将只能使用回退策略")

    def get_coordinator_status(self) -> Dict[str, Any]:
        """
        获取协调器状态
        
        Returns:
            协调器状态信息
        """
        strategy_status = StrategyFactory.get_registration_status()
        
        return {
            "coordinator_version": "v3.0",
            "output_dir": str(self.output_dir),
            "components": {
                "product_manager": {
                    "status": "active",
                    "supported_products": len(self.product_manager.get_supported_products())
                },
                "strategy_manager": {
                    "status": "active"
                },
                "strategy_factory": {
                    "status": "active",
                    "registered_strategies": strategy_status["registered_strategies"],
                    "total_strategies": strategy_status["total_strategies"],
                    "completion_rate": strategy_status["completion_rate"]
                }
            },
            "strategy_details": strategy_status
        }