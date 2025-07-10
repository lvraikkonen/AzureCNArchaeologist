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
        elif "postgresql" in product_name.lower():
            verification.update(self._verify_postgresql_specific(html_content, verification_soup))
        elif "异常检测" in product_name or "anomaly detector" in product_name.lower():
            verification.update(self._verify_anomaly_detector_specific(html_content, verification_soup))
        elif "power bi embedded" in product_name.lower():
            verification.update(self._verify_power_bi_embedded_specific(html_content, verification_soup))
        elif "ssis" in product_name.lower() or "data factory ssis" in product_name.lower():
            verification.update(self._verify_ssis_specific(html_content, verification_soup))
        
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
    
    def _verify_postgresql_specific(self, html_content: str, soup: BeautifulSoup) -> Dict[str, Any]:
        """PostgreSQL产品特定验证"""
        
        postgresql_verification = {}
        
        # 检查PostgreSQL特定的表格类
        postgresql_tables = soup.find_all('table', class_='postgresql-pricing-table')
        postgresql_verification["postgresql_table_count"] = len(postgresql_tables)
        postgresql_verification["has_postgresql_tables"] = len(postgresql_tables) > 0
        
        # 检查PostgreSQL特定关键词
        postgresql_keywords = ['postgresql', 'postgres', 'database', '数据库', '定价']
        found_keywords = []
        for keyword in postgresql_keywords:
            if keyword.lower() in html_content.lower():
                found_keywords.append(keyword)
        
        postgresql_verification["postgresql_keywords_found"] = found_keywords
        postgresql_verification["has_postgresql_keywords"] = len(found_keywords) > 0
        
        # 检查服务器类型
        server_types_found = []
        for server_type in ['单个服务器', '灵活服务器']:
            if server_type in html_content:
                server_types_found.append(server_type)
        
        postgresql_verification["server_types_found"] = server_types_found
        postgresql_verification["has_server_types"] = len(server_types_found) > 0
        
        # 检查定价层
        pricing_tiers_found = []
        for tier in ['可突发', '常规用途', '内存优化', '基本']:
            if tier in html_content:
                pricing_tiers_found.append(tier)
        
        postgresql_verification["pricing_tiers_found"] = pricing_tiers_found
        postgresql_verification["has_pricing_tiers"] = len(pricing_tiers_found) > 0
        
        # 检查实例系列
        instance_series_found = []
        series_keywords = ['Dsv3', 'Ddsv4', 'Ddsv5', 'Esv3', 'Edsv4', 'Edsv5', 'B1ms', 'B2s']
        for series in series_keywords:
            if series in html_content:
                instance_series_found.append(series)
        
        postgresql_verification["instance_series_found"] = instance_series_found
        postgresql_verification["has_instance_series"] = len(instance_series_found) > 0
        
        # 检查存储和备份相关内容
        storage_keywords = ['存储', 'storage', '备份', 'backup', 'GiB/月']
        storage_found = []
        for keyword in storage_keywords:
            if keyword in html_content:
                storage_found.append(keyword)
        
        postgresql_verification["storage_keywords_found"] = storage_found
        postgresql_verification["has_storage_info"] = len(storage_found) > 0
        
        # 检查FAQ内容
        faq_indicators = ['常见问题', 'FAQ', '账单', '计费', '停止/启动']
        faq_found = []
        for indicator in faq_indicators:
            if indicator in html_content:
                faq_found.append(indicator)
        
        postgresql_verification["faq_indicators_found"] = faq_found
        postgresql_verification["has_faq_content"] = len(faq_found) > 0
        
        return postgresql_verification
    
    def _verify_anomaly_detector_specific(self, html_content: str, soup: BeautifulSoup) -> Dict[str, Any]:
        """Anomaly Detector产品特定验证"""
        
        anomaly_detector_verification = {}
        
        # 检查Anomaly Detector特定的表格类
        anomaly_detector_tables = soup.find_all('table', class_='anomaly-detector-pricing-table')
        if not anomaly_detector_tables:
            # 如果没有找到特定class的表格，检查所有表格
            anomaly_detector_tables = soup.find_all('table')
        
        anomaly_detector_verification["anomaly_detector_table_count"] = len(anomaly_detector_tables)
        anomaly_detector_verification["has_anomaly_detector_tables"] = len(anomaly_detector_tables) > 0
        
        # 检查Anomaly Detector特定关键词
        anomaly_detector_keywords = [
            'anomaly detector', '异常检测', 'ai异常检测器', 
            '事务', 'transaction', '时序数据', 'time series',
            '数据点', 'data points', '认知服务', 'cognitive services'
        ]
        found_keywords = []
        for keyword in anomaly_detector_keywords:
            if keyword.lower() in html_content.lower():
                found_keywords.append(keyword)
        
        anomaly_detector_verification["anomaly_detector_keywords_found"] = found_keywords
        anomaly_detector_verification["has_anomaly_detector_keywords"] = len(found_keywords) > 0
        
        # 检查定价层
        pricing_tiers_found = []
        pricing_tiers = [
            '免费实例', '标准实例', 'free tier', 'standard tier',
            '免费', 'free', '标准', 'standard'
        ]
        for tier in pricing_tiers:
            if tier.lower() in html_content.lower():
                pricing_tiers_found.append(tier)
        
        anomaly_detector_verification["pricing_tiers_found"] = list(set(pricing_tiers_found))
        anomaly_detector_verification["has_pricing_tiers"] = len(pricing_tiers_found) > 0
        
        # 检查事务信息
        transaction_keywords = [
            '事务', 'transaction', '数据点', 'data points', 
            '1000', '1,000', '20000', '20,000', 'api调用', 'api call'
        ]
        transaction_found = any(keyword.lower() in html_content.lower() for keyword in transaction_keywords)
        anomaly_detector_verification["transaction_info_found"] = transaction_found
        
        # 检查技术特性
        technical_features = [
            '单变量', 'univariate', '多变量', 'multivariate',
            '时间序列', 'time series', '机器学习', 'machine learning',
            'web', '容器', 'container'
        ]
        features_found = []
        for feature in technical_features:
            if feature.lower() in html_content.lower():
                features_found.append(feature)
        
        anomaly_detector_verification["technical_features_found"] = features_found
        anomaly_detector_verification["has_technical_features"] = len(features_found) > 0
        
        # 检查定价模式
        pricing_patterns = ['每月', '免费事务', '每 1,000 个事务', '/每']
        pricing_pattern_found = any(pattern in html_content for pattern in pricing_patterns)
        anomaly_detector_verification["has_pricing_patterns"] = pricing_pattern_found
        
        # 检查FAQ相关内容
        faq_topics = [
            '事务', '免费层级', '限制', '超出', 'api',
            '有效负载', 'payload', '增量', 'increment'
        ]
        faq_found = []
        for topic in faq_topics:
            if topic.lower() in html_content.lower():
                faq_found.append(topic)
        
        anomaly_detector_verification["faq_topics_found"] = faq_found
        anomaly_detector_verification["has_faq_content"] = len(faq_found) > 0
        
        return anomaly_detector_verification

    def _verify_power_bi_embedded_specific(self, html_content: str, soup: BeautifulSoup) -> Dict[str, Any]:
        """Power BI Embedded产品特定验证"""
        
        power_bi_verification = {}
        
        # 检查Power BI Embedded特定的表格类
        power_bi_tables = soup.find_all('table', class_='power-bi-embedded-pricing-table')
        if not power_bi_tables:
            # 检查包含Power BI相关ID的表格
            power_bi_tables = soup.find_all('table', id=lambda x: x and 'power-bi' in x.lower())
            if not power_bi_tables:
                power_bi_tables = soup.find_all('table')
        
        power_bi_verification["power_bi_table_count"] = len(power_bi_tables)
        power_bi_verification["has_power_bi_tables"] = len(power_bi_tables) > 0
        
        # 检查Power BI特定关键词
        power_bi_keywords = [
            'power bi', 'embedded', '嵌入', '仪表板', 'dashboard', 
            '报表', 'report', '可视化', 'visualization', '数据分析', 'data analysis',
            '交互式', 'interactive', '应用程序', 'application'
        ]
        found_keywords = []
        for keyword in power_bi_keywords:
            if keyword.lower() in html_content.lower():
                found_keywords.append(keyword)
        
        power_bi_verification["power_bi_keywords_found"] = found_keywords
        power_bi_verification["has_power_bi_keywords"] = len(found_keywords) > 0
        
        # 检查节点类型
        node_types_found = []
        for node in ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8']:
            if node in html_content:
                node_types_found.append(node)
        
        power_bi_verification["node_types_found"] = node_types_found
        power_bi_verification["has_node_types"] = len(node_types_found) > 0
        
        # 检查定价组件
        pricing_components = [
            '虚拟内核', 'virtual core', 'vcore', 'v核心',
            '内存', 'memory', 'ram', 'gb ram',
            '前端', 'frontend', '后端', 'backend',
            '专用容量', 'dedicated capacity', '峰值呈现', 'peak rendering'
        ]
        components_found = []
        for component in pricing_components:
            if component.lower() in html_content.lower():
                components_found.append(component)
        
        power_bi_verification["pricing_components_found"] = components_found
        power_bi_verification["has_pricing_components"] = len(components_found) > 0
        
        # 检查容量信息
        capacity_info = [
            '节点类型', 'node type', '容量', 'capacity',
            '小时', '/小时', 'hour', '/month', '月'
        ]
        capacity_found = []
        for info in capacity_info:
            if info.lower() in html_content.lower():
                capacity_found.append(info)
        
        power_bi_verification["capacity_info_found"] = capacity_found
        power_bi_verification["has_capacity_info"] = len(capacity_found) > 0
        
        # 检查BI特定功能
        bi_features = [
            '嵌入', 'embed', '发布', 'publish', '许可证', 'license',
            'pro', '查看', 'view', '暂停', 'pause', '服务', 'service'
        ]
        features_found = []
        for feature in bi_features:
            if feature.lower() in html_content.lower():
                features_found.append(feature)
        
        power_bi_verification["bi_features_found"] = features_found
        power_bi_verification["has_bi_features"] = len(features_found) > 0
        
        # 检查FAQ主题
        faq_topics = [
            '节点类型', '账单', '许可证', '嵌入', '暂停',
            '服务', '应用程序', '内部', '关系'
        ]
        faq_found = []
        for topic in faq_topics:
            if topic in html_content:
                faq_found.append(topic)
        
        power_bi_verification["faq_topics_found"] = faq_found
        power_bi_verification["has_faq_content"] = len(faq_found) > 0
        
        # 检查价格模式
        pricing_patterns = ['￥', '¥', '/小时', '约￥', '/月']
        pricing_pattern_found = any(pattern in html_content for pattern in pricing_patterns)
        power_bi_verification["has_pricing_patterns"] = pricing_pattern_found
        
        return power_bi_verification

    def _verify_ssis_specific(self, html_content: str, soup: BeautifulSoup) -> Dict[str, Any]:
        """SSIS产品特定验证"""
        
        ssis_verification = {}
        
        # 检查SSIS特定的表格类
        ssis_tables = soup.find_all('table', class_='ssis-pricing-table')
        if not ssis_tables:
            # 检查包含SSIS相关ID的表格
            ssis_tables = soup.find_all('table', id=lambda x: x and 'ssis' in x.lower())
            if not ssis_tables:
                # 检查包含data-factory相关ID的表格
                ssis_tables = soup.find_all('table', id=lambda x: x and 'data-factory' in x.lower())
                if not ssis_tables:
                    ssis_tables = soup.find_all('table')
        
        ssis_verification["ssis_table_count"] = len(ssis_tables)
        ssis_verification["has_ssis_tables"] = len(ssis_tables) > 0
        
        # 检查SSIS特定关键词
        ssis_keywords = [
            'ssis', 'sql server integration services', '数据工厂', 'data factory',
            'etl', '集成运行时', 'integration runtime', '数据集成', 'data integration',
            '云托管', 'cloud hosted', 'sql server', '包', 'package'
        ]
        found_keywords = []
        for keyword in ssis_keywords:
            if keyword.lower() in html_content.lower():
                found_keywords.append(keyword)
        
        ssis_verification["ssis_keywords_found"] = found_keywords
        ssis_verification["has_ssis_keywords"] = len(found_keywords) > 0
        
        # 检查VM系列
        vm_series_found = []
        vm_series = [
            'Av2', 'A v2', 'Dv2', 'D v2', 'Dv3', 'D v3', 
            'Ev3', 'E v3', 'Ev4', 'E v4', 'A1', 'A2', 'A4', 'A8',
            'D1', 'D2', 'D3', 'D4', 'D16', 'D32', 'D64',
            'E2', 'E4', 'E8', 'E16', 'E32', 'E64', 'E80ids'
        ]
        for series in vm_series:
            if series in html_content:
                vm_series_found.append(series)
        
        ssis_verification["vm_series_found"] = list(set(vm_series_found))
        ssis_verification["has_vm_series"] = len(vm_series_found) > 0
        
        # 检查版本
        editions_found = []
        editions = ['标准', 'standard', '企业', 'enterprise', 'Standard', 'Enterprise']
        for edition in editions:
            if edition in html_content:
                editions_found.append(edition)
        
        ssis_verification["editions_found"] = list(set(editions_found))
        ssis_verification["has_editions"] = len(editions_found) > 0
        
        # 检查Azure混合优惠
        hybrid_keywords = [
            'azure混合优惠', 'azure hybrid benefit', '混合权益', 'hybrid benefit',
            '软件保障', 'software assurance', '许可证', 'license',
            '节省率', '节省', 'savings'
        ]
        hybrid_found = []
        for keyword in hybrid_keywords:
            if keyword.lower() in html_content.lower():
                hybrid_found.append(keyword)
        
        ssis_verification["hybrid_benefit_keywords"] = hybrid_found
        ssis_verification["hybrid_benefit_found"] = len(hybrid_found) > 0
        
        # 检查虚拟机配置
        vm_config = [
            'vcore', '虚拟核心', '内存', 'memory', 'gb',
            '临时存储', 'temp storage', 'temporary storage',
            '包含许可证', 'license included'
        ]
        config_found = []
        for config in vm_config:
            if config.lower() in html_content.lower():
                config_found.append(config)
        
        ssis_verification["vm_config_found"] = config_found
        ssis_verification["has_vm_config"] = len(config_found) > 0
        
        # 检查定价相关
        pricing_elements = [
            '小时', '/小时', 'hour', '月', '/月', 'month',
            '￥', '¥', '约￥', '含税', '估算'
        ]
        pricing_found = []
        for element in pricing_elements:
            if element in html_content:
                pricing_found.append(element)
        
        ssis_verification["pricing_elements_found"] = pricing_found
        ssis_verification["has_pricing_elements"] = len(pricing_found) > 0
        
        # 检查技术特性
        technical_features = [
            'sql 数据库', 'sql database', 'ssis 目录', 'ssis catalog',
            '预配', 'provision', '托管', 'managed', '完全托管', 'fully managed',
            'a-series', 'd-series', 'e-series'
        ]
        tech_found = []
        for feature in technical_features:
            if feature.lower() in html_content.lower():
                tech_found.append(feature)
        
        ssis_verification["technical_features_found"] = tech_found
        ssis_verification["has_technical_features"] = len(tech_found) > 0
        
        # 检查FAQ主题
        faq_topics = [
            'sql server integration services', '集成运行时', 'sql 数据库',
            '混合权益', '软件保障', '追溯', '到期', '本地', '云'
        ]
        faq_found = []
        for topic in faq_topics:
            if topic.lower() in html_content.lower():
                faq_found.append(topic)
        
        ssis_verification["faq_topics_found"] = faq_found
        ssis_verification["has_faq_content"] = len(faq_found) > 0
        
        # 检查Azure Synapse相关
        synapse_keywords = ['synapse', 'azure synapse', 'E80ids']
        synapse_found = any(keyword.lower() in html_content.lower() for keyword in synapse_keywords)
        ssis_verification["has_synapse_content"] = synapse_found
        
        return ssis_verification
    
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