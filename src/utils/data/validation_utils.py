#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证工具函数
用于验证提取的数据质量和完整性
"""

from typing import Dict, List, Any, Optional
import json
import re


def validate_extracted_data(data: Dict[str, Any], 
                          product_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    验证提取的数据质量
    
    Args:
        data: 提取的数据
        product_config: 产品配置
        
    Returns:
        验证结果字典
    """
    validation_result = {
        'is_valid': True,
        'errors': [],
        'warnings': [],
        'quality_score': 0.0,
        'completeness': {}
    }
    
    # 检查必需字段
    validation_rules = product_config.get('validation_rules', {})
    required_fields = validation_rules.get('required_fields', [])
    
    completeness = check_required_fields(data, required_fields)
    validation_result['completeness'] = completeness
    
    # 检查内容最小长度
    min_content_length = validation_rules.get('min_content_length', 50)
    content_quality = estimate_content_quality(data, min_content_length)
    validation_result['quality_score'] = content_quality
    
    # 检查错误和警告
    if completeness['missing_fields']:
        validation_result['errors'].extend([
            f"Missing required field: {field}" for field in completeness['missing_fields']
        ])
        validation_result['is_valid'] = False
    
    if content_quality < 0.5:
        validation_result['warnings'].append(
            f"Low content quality score: {content_quality:.2f}"
        )
    
    # 检查JSON结构
    try:
        json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        validation_result['errors'].append(f"JSON serialization error: {str(e)}")
        validation_result['is_valid'] = False
    
    return validation_result


def check_required_fields(data: Dict[str, Any], 
                         required_fields: List[str]) -> Dict[str, Any]:
    """
    检查必需字段的完整性
    
    Args:
        data: 待检查的数据
        required_fields: 必需字段列表
        
    Returns:
        完整性检查结果
    """
    result = {
        'total_fields': len(required_fields),
        'present_fields': [],
        'missing_fields': [],
        'completeness_ratio': 0.0
    }
    
    for field in required_fields:
        if _check_field_exists(data, field):
            result['present_fields'].append(field)
        else:
            result['missing_fields'].append(field)
    
    if result['total_fields'] > 0:
        result['completeness_ratio'] = len(result['present_fields']) / result['total_fields']
    
    return result


def _check_field_exists(data: Dict[str, Any], field_path: str) -> bool:
    """
    检查嵌套字段是否存在且有值
    
    Args:
        data: 数据字典
        field_path: 字段路径（支持点号分隔的嵌套字段）
        
    Returns:
        字段是否存在且有值
    """
    if not isinstance(data, dict):
        return False
    
    # 支持嵌套字段路径，如 "product_info.title"
    if '.' in field_path:
        parts = field_path.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False
        
        # 检查最终值是否有意义
        return _has_meaningful_value(current)
    else:
        # 简单字段
        if field_path in data:
            return _has_meaningful_value(data[field_path])
        return False


def _has_meaningful_value(value: Any) -> bool:
    """检查值是否有意义（非空、非None等）"""
    if value is None:
        return False
    
    if isinstance(value, (str, bytes)):
        return len(value.strip()) > 0
    
    if isinstance(value, (list, dict)):
        return len(value) > 0
    
    if isinstance(value, (int, float)):
        return True
    
    return bool(value)


def estimate_content_quality(data: Dict[str, Any], 
                           min_content_length: int = 50) -> float:
    """
    估算内容质量分数
    
    Args:
        data: 提取的数据
        min_content_length: 最小内容长度
        
    Returns:
        质量分数 (0.0 - 1.0)
    """
    quality_metrics = {
        'content_length': 0.0,
        'structure_completeness': 0.0,
        'text_quality': 0.0,
        'data_richness': 0.0
    }
    
    # 1. 内容长度质量
    total_text_length = 0
    text_fields = ['Title', 'BannerContent', 'DescriptionContent', 'FAQ']
    
    for field in text_fields:
        if field in data:
            field_content = str(data[field])
            total_text_length += len(field_content)
    
    # 按总长度评分
    if total_text_length >= min_content_length * 5:
        quality_metrics['content_length'] = 1.0
    elif total_text_length >= min_content_length * 2:
        quality_metrics['content_length'] = 0.8
    elif total_text_length >= min_content_length:
        quality_metrics['content_length'] = 0.6
    else:
        quality_metrics['content_length'] = total_text_length / min_content_length
    
    # 2. 结构完整性
    expected_sections = ['Title', 'BannerContent', 'DescriptionContent', 'PricingTables', 'FAQ']
    present_sections = [section for section in expected_sections if section in data]
    
    quality_metrics['structure_completeness'] = len(present_sections) / len(expected_sections)
    
    # 3. 文本质量（检查是否包含有意义的内容）
    if 'Title' in data and data['Title']:
        title_quality = _assess_text_quality(str(data['Title']))
        quality_metrics['text_quality'] += title_quality * 0.3
    
    if 'DescriptionContent' in data and data['DescriptionContent']:
        desc_quality = _assess_text_quality(str(data['DescriptionContent']))
        quality_metrics['text_quality'] += desc_quality * 0.5
    
    if 'FAQ' in data and data['FAQ']:
        faq_quality = _assess_text_quality(str(data['FAQ']))
        quality_metrics['text_quality'] += faq_quality * 0.2
    
    # 4. 数据丰富性
    data_elements = ['PricingTables', 'RegionalContent', 'ServiceTiers']
    rich_elements = [elem for elem in data_elements if elem in data and data[elem]]
    
    quality_metrics['data_richness'] = len(rich_elements) / len(data_elements)
    
    # 计算总体质量分数
    weights = {
        'content_length': 0.3,
        'structure_completeness': 0.3,
        'text_quality': 0.25,
        'data_richness': 0.15
    }
    
    total_score = sum(
        quality_metrics[metric] * weights[metric] 
        for metric in quality_metrics
    )
    
    return min(1.0, max(0.0, total_score))


def _assess_text_quality(text: str) -> float:
    """
    评估文本质量
    
    Args:
        text: 待评估的文本
        
    Returns:
        质量分数 (0.0 - 1.0)
    """
    if not text or len(text.strip()) == 0:
        return 0.0
    
    text = text.strip()
    quality_score = 0.0
    
    # 长度分数
    if len(text) >= 100:
        quality_score += 0.4
    elif len(text) >= 50:
        quality_score += 0.2
    else:
        quality_score += len(text) / 125.0  # 比例分数
    
    # 多样性分数（检查是否有多样的内容）
    sentences = re.split(r'[.!?。！？]', text)
    if len(sentences) > 1:
        quality_score += 0.2
    
    # 信息密度分数（检查是否包含有用信息）
    info_keywords = [
        '价格', '定价', '功能', '特性', '服务', '支持', '配置', '规格',
        'price', 'pricing', 'feature', 'service', 'support', 'configuration'
    ]
    
    keyword_count = sum(1 for keyword in info_keywords if keyword in text.lower())
    if keyword_count > 0:
        quality_score += min(0.4, keyword_count * 0.1)
    
    return min(1.0, quality_score)


def generate_validation_report(validation_result: Dict[str, Any]) -> str:
    """
    生成验证报告
    
    Args:
        validation_result: 验证结果
        
    Returns:
        格式化的验证报告
    """
    report_lines = []
    report_lines.append("=== 数据验证报告 ===")
    report_lines.append(f"整体状态: {'✓ 通过' if validation_result['is_valid'] else '✗ 失败'}")
    report_lines.append(f"质量分数: {validation_result['quality_score']:.2f}/1.0")
    
    # 完整性信息
    completeness = validation_result.get('completeness', {})
    if completeness:
        ratio = completeness.get('completeness_ratio', 0)
        report_lines.append(f"字段完整性: {ratio:.1%} ({len(completeness.get('present_fields', []))}/{completeness.get('total_fields', 0)})")
    
    # 错误信息
    errors = validation_result.get('errors', [])
    if errors:
        report_lines.append("\n错误:")
        for error in errors:
            report_lines.append(f"  ✗ {error}")
    
    # 警告信息
    warnings = validation_result.get('warnings', [])
    if warnings:
        report_lines.append("\n警告:")
        for warning in warnings:
            report_lines.append(f"  ⚠ {warning}")
    
    # 缺失字段
    missing_fields = completeness.get('missing_fields', [])
    if missing_fields:
        report_lines.append(f"\n缺失字段: {', '.join(missing_fields)}")
    
    return '\n'.join(report_lines)