#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证管理器模块
提供内容验证和统计功能
"""

from typing import Dict, Any
from bs4 import BeautifulSoup

try:
    from utils.enhanced_html_processor import verify_table_content
except ImportError:
    def verify_table_content(html_content: str) -> Dict[str, Any]:
        """备用表格验证函数"""
        return {
            "table_verification": "模块不可用",
            "table_structure_valid": False
        }


class VerificationManager:
    """验证管理器 - 负责内容验证和统计"""
    
    def __init__(self):
        """初始化验证管理器"""
        pass
    
    def verify_extraction(self, html_content: str, product_name: str = "") -> Dict[str, Any]:
        """
        验证提取结果
        
        Args:
            html_content: 生成的HTML内容
            product_name: 产品名称
            
        Returns:
            验证结果字典
        """
        
        verification_soup = BeautifulSoup(html_content, 'html.parser')
        
        # 基础验证
        verification = {
            "has_main_content": bool(verification_soup.find('p', class_='region-info')),
            "has_region_info": bool(verification_soup.find('p', class_='region-info')), 
            "table_count": len(verification_soup.find_all('table')),
            "paragraph_count": len(verification_soup.find_all('p')),
            "heading_count": len(verification_soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])),
            "list_count": len(verification_soup.find_all(['ul', 'ol'])),
            "link_count": len(verification_soup.find_all('a')),
            "text_length": len(verification_soup.get_text(strip=True)),
            "html_size": len(html_content),
            "is_valid_html": html_content.strip().startswith('<!DOCTYPE html>')
        }
        
        # 产品特定验证
        if "mysql" in product_name.lower():
            verification.update(self._verify_mysql_specific(html_content, verification_soup))
        elif "storage" in product_name.lower() and "files" in product_name.lower():
            verification.update(self._verify_storage_files_specific(html_content, verification_soup))
        
        # 验证表格内容
        table_verification = verify_table_content(html_content)
        verification.update(table_verification)
        
        # 内容完整性检查
        verification["content_completeness"] = self._check_content_completeness(verification)
        
        return verification
    
    def _verify_mysql_specific(self, html_content: str, soup: BeautifulSoup) -> Dict[str, Any]:
        """MySQL产品特定验证"""
        
        mysql_verification = {}
        
        # 检查MySQL特定的表格类
        mysql_tables = soup.find_all('table', class_='pricing-table')
        mysql_verification["mysql_table_count"] = len(mysql_tables)
        mysql_verification["has_mysql_tables"] = len(mysql_tables) > 0
        
        # 检查MySQL特定关键词
        mysql_keywords = ['mysql', 'database', '数据库', '定价']
        found_keywords = []
        for keyword in mysql_keywords:
            if keyword.lower() in html_content.lower():
                found_keywords.append(keyword)
        
        mysql_verification["mysql_keywords_found"] = found_keywords
        mysql_verification["has_mysql_keywords"] = len(found_keywords) > 0
        
        return mysql_verification
    
    def _verify_storage_files_specific(self, html_content: str, soup: BeautifulSoup) -> Dict[str, Any]:
        """Azure Storage Files产品特定验证"""
        
        storage_verification = {}
        
        # 检查Storage Files特定的表格类
        storage_tables = soup.find_all('table', class_='storage-files-pricing-table')
        storage_verification["storage_table_count"] = len(storage_tables)
        storage_verification["has_storage_tables"] = len(storage_tables) > 0
        
        # 检查重要的section标题
        important_titles_found = []
        for title in ['定价详细信息', '了解存储选项', '数据存储价格', '事务和数据传输价格']:
            if title in html_content:
                important_titles_found.append(title)
        
        # 检查存储冗余类型标题
        redundancy_titles_found = []
        for redundancy in ['LRS', 'GRS', 'ZRS', 'GZRS', 'RA-GRS']:
            if f'>{redundancy}<' in html_content or f'>{redundancy.lower()}<' in html_content:
                redundancy_titles_found.append(redundancy)
        
        storage_verification["important_section_titles"] = important_titles_found
        storage_verification["redundancy_type_titles"] = redundancy_titles_found
        storage_verification["has_section_structure"] = len(important_titles_found) > 0
        storage_verification["has_redundancy_structure"] = len(redundancy_titles_found) > 0
        
        # 检查Storage Files特定关键词
        storage_keywords = ['storage', 'files', '存储', '文件', '定价']
        found_keywords = []
        for keyword in storage_keywords:
            if keyword.lower() in html_content.lower():
                found_keywords.append(keyword)
        
        storage_verification["storage_keywords_found"] = found_keywords
        storage_verification["has_storage_keywords"] = len(found_keywords) > 0
        
        return storage_verification
    
    def _check_content_completeness(self, verification: Dict[str, Any]) -> Dict[str, bool]:
        """检查内容完整性"""
        
        completeness = {
            "has_text_content": verification["text_length"] > 1000,  # 至少1000字符
            "has_structured_content": verification["table_count"] > 0 and verification["paragraph_count"] > 0,
            "has_navigation_structure": verification["heading_count"] > 0,
            "has_interactive_content": verification["link_count"] > 0
        }
        
        # 添加产品特定完整性检查
        if "has_section_structure" in verification:
            completeness["has_section_titles"] = verification["has_section_structure"]
        
        if "has_redundancy_structure" in verification:
            completeness["has_redundancy_titles"] = verification["has_redundancy_structure"]
        
        return completeness
    
    def generate_statistics_summary(self, verification: Dict[str, Any], 
                                  processing_time: float,
                                  original_size: int,
                                  final_size: int) -> Dict[str, Any]:
        """
        生成统计摘要
        
        Args:
            verification: 验证结果
            processing_time: 处理时间
            original_size: 原始文件大小
            final_size: 最终文件大小
            
        Returns:
            统计摘要字典
        """
        
        statistics = {
            "processing_time": processing_time,
            "original_size": original_size,
            "final_size": final_size,
            "compression_ratio": round(final_size / original_size, 3) if original_size > 0 else 0,
            "content_statistics": {
                "total_elements": (verification.get("table_count", 0) + 
                                 verification.get("paragraph_count", 0) + 
                                 verification.get("heading_count", 0) + 
                                 verification.get("list_count", 0)),
                "tables": verification.get("table_count", 0),
                "paragraphs": verification.get("paragraph_count", 0),
                "headings": verification.get("heading_count", 0),
                "lists": verification.get("list_count", 0),
                "links": verification.get("link_count", 0),
                "text_length": verification.get("text_length", 0)
            },
            "quality_metrics": {
                "has_valid_structure": verification.get("is_valid_html", False),
                "content_density": round(verification.get("text_length", 0) / final_size, 4) if final_size > 0 else 0,
                "compression_efficiency": round((1 - final_size / original_size) * 100, 2) if original_size > 0 else 0
            }
        }
        
        # 添加完整性评分
        completeness = verification.get("content_completeness", {})
        completeness_score = sum(1 for v in completeness.values() if v) / len(completeness) if completeness else 0
        statistics["quality_metrics"]["completeness_score"] = round(completeness_score * 100, 1)
        
        return statistics
    
    def validate_output_quality(self, verification: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证输出质量
        
        Args:
            verification: 验证结果
            
        Returns:
            质量评估结果
        """
        
        quality_assessment = {
            "overall_quality": "good",
            "issues": [],
            "recommendations": [],
            "score": 0
        }
        
        score = 0
        max_score = 10
        
        # 基础结构检查 (3分)
        if verification.get("is_valid_html", False):
            score += 1
        else:
            quality_assessment["issues"].append("HTML结构无效")
        
        if verification.get("has_main_content", False):
            score += 1
        else:
            quality_assessment["issues"].append("缺少主要内容")
        
        if verification.get("has_region_info", False):
            score += 1
        else:
            quality_assessment["issues"].append("缺少区域信息")
        
        # 内容丰富度检查 (4分)
        if verification.get("table_count", 0) > 0:
            score += 1
        else:
            quality_assessment["issues"].append("缺少定价表格")
        
        if verification.get("paragraph_count", 0) > 3:
            score += 1
        else:
            quality_assessment["recommendations"].append("建议增加更多描述性段落")
        
        if verification.get("heading_count", 0) > 0:
            score += 1
        else:
            quality_assessment["issues"].append("缺少标题结构")
        
        if verification.get("text_length", 0) > 1000:
            score += 1
        else:
            quality_assessment["recommendations"].append("内容过于简短，建议增加更多信息")
        
        # 完整性检查 (3分)
        completeness = verification.get("content_completeness", {})
        if completeness.get("has_structured_content", False):
            score += 1
        
        if completeness.get("has_navigation_structure", False):
            score += 1
        
        if completeness.get("has_interactive_content", False):
            score += 1
        
        # 确定整体质量等级
        percentage = (score / max_score) * 100
        
        if percentage >= 90:
            quality_assessment["overall_quality"] = "excellent"
        elif percentage >= 75:
            quality_assessment["overall_quality"] = "good"
        elif percentage >= 60:
            quality_assessment["overall_quality"] = "fair"
        else:
            quality_assessment["overall_quality"] = "poor"
        
        quality_assessment["score"] = score
        quality_assessment["max_score"] = max_score
        quality_assessment["percentage"] = round(percentage, 1)
        
        return quality_assessment