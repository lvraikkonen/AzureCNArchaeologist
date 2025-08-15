#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专门提取结果验证器
将BaseStrategy中的验证逻辑移至此处，支持flexible JSON格式验证，提供统一的数据质量评估接口
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

from src.core.logging import get_logger
from src.utils.data.validation_utils import validate_extracted_data

logger = get_logger(__name__)


class ExtractionValidator:
    """专门提取结果验证器 - 验证传统CMS格式和flexible JSON格式"""

    def __init__(self):
        """初始化提取结果验证器"""
        logger.info("🔧 初始化ExtractionValidator")

    def validate_cms_extraction(self, data: Dict[str, Any], product_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证传统CMS格式提取结果
        
        Args:
            data: 提取的CMS数据
            product_config: 产品配置信息
            
        Returns:
            包含validation字段的验证后数据
        """
        logger.info("✅ 验证传统CMS格式提取结果...")
        
        try:
            validation_result = validate_extracted_data(data, product_config)
            data["validation"] = validation_result
            
            # 添加传统CMS提取元数据
            data["extraction_metadata"] = {
                "extractor_version": "enhanced_v3.0",
                "extraction_timestamp": datetime.now().isoformat(),
                "format_type": "cms",
                "processing_mode": "strategy_based"
            }
            
        except Exception as e:
            logger.info(f"⚠ 传统CMS验证失败: {e}")
            data["validation"] = {
                "is_valid": False,
                "errors": [str(e)],
                "warnings": []
            }
        
        return data

    def validate_flexible_json(self, flexible_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证flexible JSON格式提取结果
        
        Args:
            flexible_data: flexible JSON数据
            
        Returns:
            包含validation字段的验证后数据
        """
        logger.info("✅ 验证flexible JSON格式提取结果...")
        
        validation_result = self._validate_flexible_structure(flexible_data)
        
        # 添加验证结果到数据中
        flexible_data["validation"] = validation_result
        
        return flexible_data

    def _validate_flexible_structure(self, flexible_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证flexible JSON结构完整性
        
        Args:
            flexible_data: flexible JSON数据
            
        Returns:
            验证结果字典
        """
        errors = []
        warnings = []
        
        # 1. 验证必需字段
        required_fields = ["title", "baseContent", "contentGroups", "commonSections", "pageConfig"]
        for field in required_fields:
            if field not in flexible_data:
                errors.append(f"缺少必需字段: {field}")
            elif flexible_data[field] is None:
                warnings.append(f"字段为空: {field}")
        
        # 2. 验证title
        title = flexible_data.get("title", "")
        if not title or len(title.strip()) == 0:
            warnings.append("标题为空")
        elif len(title) < 5:
            warnings.append("标题过短")
        
        # 3. 验证contentGroups结构
        content_groups = flexible_data.get("contentGroups", [])
        if not isinstance(content_groups, list):
            errors.append("contentGroups必须是列表")
        else:
            for i, group in enumerate(content_groups):
                if not isinstance(group, dict):
                    errors.append(f"contentGroups[{i}]必须是字典")
                    continue
                
                # 验证contentGroup必需字段
                group_required = ["groupName", "filterCriteriaJson", "content"]
                for field in group_required:
                    if field not in group:
                        errors.append(f"contentGroups[{i}]缺少字段: {field}")
                
                # 验证filterCriteriaJson格式
                if "filterCriteriaJson" in group:
                    try:
                        import json
                        json.loads(group["filterCriteriaJson"])
                    except json.JSONDecodeError:
                        errors.append(f"contentGroups[{i}].filterCriteriaJson不是有效JSON")
        
        # 4. 验证commonSections结构
        common_sections = flexible_data.get("commonSections", [])
        if not isinstance(common_sections, list):
            errors.append("commonSections必须是列表")
        else:
            valid_section_types = ["Banner", "Description", "Qa"]
            for i, section in enumerate(common_sections):
                if not isinstance(section, dict):
                    errors.append(f"commonSections[{i}]必须是字典")
                    continue
                
                # 验证section必需字段
                if "sectionType" not in section:
                    errors.append(f"commonSections[{i}]缺少sectionType")
                elif section["sectionType"] not in valid_section_types:
                    warnings.append(f"commonSections[{i}].sectionType未知: {section['sectionType']}")
                
                if "content" not in section:
                    errors.append(f"commonSections[{i}]缺少content")
                elif not section["content"]:
                    warnings.append(f"commonSections[{i}].content为空")
        
        # 5. 验证pageConfig结构
        page_config = flexible_data.get("pageConfig", {})
        if not isinstance(page_config, dict):
            errors.append("pageConfig必须是字典")
        else:
            if "enableFilters" not in page_config:
                warnings.append("pageConfig缺少enableFilters字段")
            
            if "filtersJsonConfig" in page_config:
                try:
                    import json
                    json.loads(page_config["filtersJsonConfig"])
                except json.JSONDecodeError:
                    errors.append("pageConfig.filtersJsonConfig不是有效JSON")
        
        # 6. 验证元数据
        extraction_metadata = flexible_data.get("extractionMetadata", {})
        if not isinstance(extraction_metadata, dict):
            warnings.append("extractionMetadata应该是字典")
        else:
            if "schemaVersion" not in extraction_metadata:
                warnings.append("缺少schemaVersion")
            elif extraction_metadata["schemaVersion"] != "1.1":
                warnings.append(f"schemaVersion不是1.1: {extraction_metadata['schemaVersion']}")
        
        # 计算质量分数
        quality_score = self._calculate_quality_score(flexible_data, len(errors), len(warnings))
        
        validation_result = {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "quality_score": quality_score,
            "content_groups_count": len(content_groups),
            "common_sections_count": len(common_sections),
            "has_filters": page_config.get("enableFilters", False),
            "validation_timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"✓ flexible JSON验证完成: {'有效' if validation_result['is_valid'] else '无效'}, "
                   f"质量分数: {quality_score:.2f}, "
                   f"错误: {len(errors)}, 警告: {len(warnings)}")
        
        return validation_result

    def _calculate_quality_score(self, flexible_data: Dict[str, Any], error_count: int, warning_count: int) -> float:
        """
        计算flexible JSON质量分数
        
        Args:
            flexible_data: flexible JSON数据
            error_count: 错误数量
            warning_count: 警告数量
            
        Returns:
            质量分数 (0.0-1.0)
        """
        # 基础分数
        base_score = 1.0
        
        # 错误扣分 (每个错误扣0.2分)
        error_penalty = error_count * 0.2
        
        # 警告扣分 (每个警告扣0.1分)
        warning_penalty = warning_count * 0.1
        
        # 内容完整性加分
        completeness_bonus = 0.0
        
        # 标题完整性
        title = flexible_data.get("title", "")
        if title and len(title.strip()) > 5:
            completeness_bonus += 0.1
        
        # baseContent完整性
        base_content = flexible_data.get("baseContent", "")
        if base_content and len(base_content.strip()) > 100:
            completeness_bonus += 0.1
        
        # contentGroups完整性
        content_groups = flexible_data.get("contentGroups", [])
        if content_groups:
            completeness_bonus += 0.1
        
        # commonSections完整性
        common_sections = flexible_data.get("commonSections", [])
        if len(common_sections) >= 2:  # 至少有Banner和Description
            completeness_bonus += 0.1
        
        # 计算最终分数
        final_score = base_score - error_penalty - warning_penalty + completeness_bonus
        
        # 确保分数在0.0-1.0范围内
        return max(0.0, min(1.0, final_score))

    def get_validation_summary(self, validation_result: Dict[str, Any]) -> str:
        """
        获取验证结果摘要
        
        Args:
            validation_result: 验证结果
            
        Returns:
            验证摘要字符串
        """
        is_valid = validation_result.get("is_valid", False)
        quality_score = validation_result.get("quality_score", 0.0)
        error_count = len(validation_result.get("errors", []))
        warning_count = len(validation_result.get("warnings", []))
        
        status = "✅ 有效" if is_valid else "❌ 无效"
        
        return (f"{status} | 质量分数: {quality_score:.2f} | "
                f"错误: {error_count} | 警告: {warning_count}")