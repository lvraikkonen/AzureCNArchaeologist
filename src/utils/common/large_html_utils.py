#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大型HTML文件处理工具
支持大型HTML文件的流式处理和内存优化
"""

import os
import psutil
from typing import Dict, Any, Iterator, Optional
from bs4 import BeautifulSoup


class LargeHTMLProcessor:
    """大型HTML文件处理器"""

    def __init__(self, memory_limit_mb: int = 512):
        self.memory_limit = memory_limit_mb * 1024 * 1024
        self.chunk_size = 1024 * 1024  # 1MB chunks

    def check_file_size(self, file_path: str) -> Dict[str, Any]:
        """检查文件大小并返回处理策略"""
        if not os.path.exists(file_path):
            return {
                "strategy": "error",
                "size_mb": 0,
                "error": f"File not found: {file_path}"
            }
            
        file_size = os.path.getsize(file_path)
        size_mb = file_size / (1024 * 1024)

        if size_mb > 10:  # 超过10MB使用流式处理
            return {
                "strategy": "streaming",
                "size_mb": size_mb,
                "estimated_memory": size_mb * 3,  # HTML解析约需3倍内存
                "use_chunks": True,
                "recommendation": "使用流式处理，分块读取文件"
            }
        elif size_mb > 2:  # 2-10MB使用分块处理
            return {
                "strategy": "chunked",
                "size_mb": size_mb,
                "estimated_memory": size_mb * 2,
                "use_chunks": True,
                "recommendation": "使用分块处理，优化内存使用"
            }
        else:  # 小于2MB正常处理
            return {
                "strategy": "normal",
                "size_mb": size_mb,
                "estimated_memory": size_mb * 2,
                "use_chunks": False,
                "recommendation": "使用标准处理方式"
            }

    def get_memory_usage(self) -> Dict[str, float]:
        """获取当前内存使用情况"""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            return {
                'rss_mb': memory_info.rss / (1024 * 1024),  # 物理内存
                'vms_mb': memory_info.vms / (1024 * 1024),  # 虚拟内存
                'percent': process.memory_percent(),  # 内存使用百分比
            }
        except Exception as e:
            print(f"获取内存信息失败: {e}")
            return {'rss_mb': 0, 'vms_mb': 0, 'percent': 0}

    def monitor_memory_usage(self) -> float:
        """监控内存使用情况"""
        memory_info = self.get_memory_usage()
        return memory_info['rss_mb']

    def check_memory_threshold(self, threshold_mb: int = 512) -> bool:
        """检查是否超过内存阈值"""
        current_memory = self.monitor_memory_usage()
        return current_memory > threshold_mb

    def estimate_parsing_memory(self, file_size_mb: float) -> Dict[str, float]:
        """估算解析所需内存"""
        # 经验值：HTML解析通常需要2-4倍文件大小的内存
        return {
            'minimum_mb': file_size_mb * 2,
            'recommended_mb': file_size_mb * 3,
            'maximum_mb': file_size_mb * 4,
            'safe_threshold_mb': file_size_mb * 2.5
        }

    def should_use_streaming(self, file_path: str, 
                           available_memory_mb: Optional[float] = None) -> bool:
        """判断是否应该使用流式处理"""
        file_info = self.check_file_size(file_path)
        
        if file_info["strategy"] == "error":
            return False
            
        # 如果文件超过10MB，建议使用流式处理
        if file_info["size_mb"] > 10:
            return True
            
        # 如果指定了可用内存，检查是否足够
        if available_memory_mb:
            memory_estimate = self.estimate_parsing_memory(file_info["size_mb"])
            if memory_estimate["recommended_mb"] > available_memory_mb:
                return True
                
        return False

    def create_progress_callback(self, total_size: int, description: str = "处理中"):
        """创建进度回调函数"""
        try:
            from tqdm import tqdm
            pbar = tqdm(total=total_size, desc=description, unit='B', unit_scale=True)
            
            def update_progress(processed: int):
                pbar.update(processed - pbar.n)
            
            def close_progress():
                pbar.close()
                
            return update_progress, close_progress
        except ImportError:
            # 如果没有tqdm，返回空函数
            def dummy_update(processed: int):
                pass
            def dummy_close():
                pass
            return dummy_update, dummy_close

    def read_file_in_chunks(self, file_path: str, chunk_size: int = None) -> Iterator[str]:
        """分块读取文件"""
        if chunk_size is None:
            chunk_size = self.chunk_size
            
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            print(f"读取文件失败: {e}")
            return

    def get_processing_recommendations(self, file_path: str) -> Dict[str, Any]:
        """获取处理建议"""
        file_info = self.check_file_size(file_path)
        memory_estimate = self.estimate_parsing_memory(file_info.get("size_mb", 0))
        current_memory = self.get_memory_usage()
        
        recommendations = {
            'file_info': file_info,
            'memory_estimate': memory_estimate,
            'current_memory': current_memory,
            'processing_advice': []
        }
        
        # 生成处理建议
        if file_info["strategy"] == "streaming":
            recommendations['processing_advice'].append(
                "建议使用流式处理，分批读取和解析文件"
            )
            recommendations['processing_advice'].append(
                "考虑只提取关键部分，延迟处理非关键内容"
            )
            
        elif file_info["strategy"] == "chunked":
            recommendations['processing_advice'].append(
                "建议使用分块处理，控制内存使用"
            )
            recommendations['processing_advice'].append(
                "可以考虑并行处理不同区域"
            )
            
        else:
            recommendations['processing_advice'].append(
                "文件大小适中，可以使用标准处理方式"
            )
        
        # 内存建议
        if memory_estimate["recommended_mb"] > current_memory['rss_mb'] * 2:
            recommendations['processing_advice'].append(
                f"建议至少保留 {memory_estimate['recommended_mb']:.1f}MB 可用内存"
            )
        
        return recommendations


def check_file_processing_strategy(file_path: str) -> Dict[str, Any]:
    """检查文件处理策略（快捷函数）"""
    processor = LargeHTMLProcessor()
    return processor.check_file_size(file_path)


def monitor_memory_usage() -> float:
    """监控内存使用情况（快捷函数）"""
    processor = LargeHTMLProcessor()
    return processor.monitor_memory_usage()


def get_processing_recommendations(file_path: str) -> Dict[str, Any]:
    """获取处理建议（快捷函数）"""
    processor = LargeHTMLProcessor()
    return processor.get_processing_recommendations(file_path)