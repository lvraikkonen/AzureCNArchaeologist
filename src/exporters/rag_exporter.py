#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG导出器
负责将提取的数据导出为RAG系统可用格式
未来用于知识库构建和智能检索系统
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


class RAGExporter:
    """RAG系统数据导出器"""
    
    def __init__(self, output_dir: str = "rag_output"):
        """
        初始化RAG导出器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def export_for_rag(self, data: Dict[str, Any], product_name: str) -> Dict[str, str]:
        """
        将数据导出为RAG系统格式
        
        Args:
            data: 原始数据
            product_name: 产品名称
            
        Returns:
            Dict[str, str]: 导出文件路径字典
        """
        # 直接使用指定的输出目录，不创建额外的产品子目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 导出文档片段
        documents_path = self._export_documents(data, self.output_dir, timestamp, product_name)
        
        # 导出元数据
        metadata_path = self._export_metadata(data, self.output_dir, timestamp, product_name)
        
        # 导出知识图谱数据
        knowledge_graph_path = self._export_knowledge_graph(data, self.output_dir, timestamp, product_name)
        
        return {
            "documents": documents_path,
            "metadata": metadata_path,
            "knowledge_graph": knowledge_graph_path
        }
    
    def _export_documents(self, data: Dict[str, Any], output_dir: Path, 
                         timestamp: str, product_name: str) -> str:
        """
        导出文档片段供RAG检索使用
        
        Args:
            data: 原始数据
            output_dir: 输出目录
            timestamp: 时间戳
            product_name: 产品名称
            
        Returns:
            str: 文档导出路径
        """
        documents = []
        
        # 产品描述文档
        if 'product_info' in data:
            product_info = data['product_info']
            documents.append({
                "id": f"product_desc_{timestamp}",
                "type": "product_description",
                "title": f"{product_info.get('name', 'Unknown')} - 产品描述",
                "content": product_info.get('description', ''),
                "metadata": {
                    "product_name": product_info.get('name', ''),
                    "section": "description",
                    "language": "zh-CN"
                }
            })
        
        # 价格信息文档
        if 'pricing_tables' in data:
            for i, table in enumerate(data['pricing_tables']):
                # 将价格表转换为文本描述
                content = self._pricing_table_to_text(table)
                documents.append({
                    "id": f"pricing_table_{i}_{timestamp}",
                    "type": "pricing_information",
                    "title": f"价格表 {i+1}",
                    "content": content,
                    "metadata": {
                        "table_index": i,
                        "section": "pricing",
                        "language": "zh-CN"
                    }
                })
        
        # FAQ文档
        if 'faqs' in data:
            for i, faq in enumerate(data['faqs']):
                documents.append({
                    "id": f"faq_{i}_{timestamp}",
                    "type": "faq",
                    "title": faq.get('question', f'FAQ {i+1}'),
                    "content": f"问题: {faq.get('question', '')}\n答案: {faq.get('answer', '')}",
                    "metadata": {
                        "faq_index": i,
                        "section": "faq",
                        "language": "zh-CN"
                    }
                })
        
        # 保存文档
        documents_file = output_dir / f"{product_name}_rag_documents_{timestamp}.json"
        with open(documents_file, 'w', encoding='utf-8') as f:
            json.dump({
                "documents": documents,
                "total_count": len(documents),
                "export_time": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
        
        return str(documents_file)
    
    def _export_metadata(self, data: Dict[str, Any], output_dir: Path, 
                        timestamp: str, product_name: str) -> str:
        """
        导出元数据信息
        
        Args:
            data: 原始数据
            output_dir: 输出目录
            timestamp: 时间戳
            product_name: 产品名称
            
        Returns:
            str: 元数据导出路径
        """
        metadata = {
            "product_metadata": {
                "name": data.get('product_info', {}).get('name', ''),
                "description": data.get('product_info', {}).get('description', ''),
                "regions": data.get('regions', []),
                "service_tiers": len(data.get('service_tiers', [])),
                "pricing_tables_count": len(data.get('pricing_tables', [])),
                "faqs_count": len(data.get('faqs', []))
            },
            "extraction_metadata": data.get('extraction_metadata', {}),
            "rag_export_metadata": {
                "export_time": datetime.now().isoformat(),
                "exporter_version": "1.0",
                "format_version": "rag_v1"
            }
        }
        
        metadata_file = output_dir / f"{product_name}_rag_metadata_{timestamp}.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        return str(metadata_file)
    
    def _export_knowledge_graph(self, data: Dict[str, Any], output_dir: Path, 
                               timestamp: str, product_name: str) -> str:
        """
        导出知识图谱数据
        
        Args:
            data: 原始数据
            output_dir: 输出目录
            timestamp: 时间戳
            product_name: 产品名称
            
        Returns:
            str: 知识图谱导出路径
        """
        # 构建简单的知识图谱结构
        entities = []
        relationships = []
        
        # 产品实体
        product_name = data.get('product_info', {}).get('name', 'Unknown Product')
        entities.append({
            "id": f"product_{product_name.lower().replace(' ', '_')}",
            "type": "Product",
            "name": product_name,
            "properties": data.get('product_info', {})
        })
        
        # 区域实体和关系
        for region in data.get('regions', []):
            region_id = f"region_{region.lower().replace(' ', '_')}"
            entities.append({
                "id": region_id,
                "type": "Region",
                "name": region,
                "properties": {"region_name": region}
            })
            
            # 产品-区域关系
            relationships.append({
                "source": f"product_{product_name.lower().replace(' ', '_')}",
                "target": region_id,
                "relationship": "AVAILABLE_IN",
                "properties": {}
            })
        
        # 服务层级实体
        for i, tier in enumerate(data.get('service_tiers', [])):
            tier_id = f"tier_{i}"
            entities.append({
                "id": tier_id,
                "type": "ServiceTier",
                "name": tier.get('name', f'Tier {i}'),
                "properties": tier
            })
            
            # 产品-服务层级关系
            relationships.append({
                "source": f"product_{product_name.lower().replace(' ', '_')}",
                "target": tier_id,
                "relationship": "HAS_TIER",
                "properties": {}
            })
        
        knowledge_graph = {
            "entities": entities,
            "relationships": relationships,
            "metadata": {
                "total_entities": len(entities),
                "total_relationships": len(relationships),
                "export_time": datetime.now().isoformat()
            }
        }
        
        kg_file = output_dir / f"{product_name}_rag_knowledge_graph_{timestamp}.json"
        with open(kg_file, 'w', encoding='utf-8') as f:
            json.dump(knowledge_graph, f, ensure_ascii=False, indent=2)
        
        return str(kg_file)
    
    def _pricing_table_to_text(self, table: Dict[str, Any]) -> str:
        """
        将价格表转换为文本描述
        
        Args:
            table: 价格表数据
            
        Returns:
            str: 文本描述
        """
        text_parts = []
        
        if table.get('title'):
            text_parts.append(f"价格表: {table['title']}")
        
        if table.get('headers') and table.get('rows'):
            headers = table['headers']
            text_parts.append(f"列名: {', '.join(headers)}")
            
            for i, row in enumerate(table['rows'][:5]):  # 只取前5行作为示例
                row_text = []
                for j, cell in enumerate(row):
                    if j < len(headers):
                        row_text.append(f"{headers[j]}: {cell}")
                text_parts.append(f"第{i+1}行 - {'; '.join(row_text)}")
        
        return '\n'.join(text_parts)