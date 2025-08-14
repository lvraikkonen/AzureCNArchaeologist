#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证PageAnalyzer的3策略决策逻辑
基于文档中的预期测试结果进行验证
"""

import sys
import os
from pathlib import Path
from bs4 import BeautifulSoup

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.detectors.page_analyzer import PageAnalyzer

def load_html_file(file_path: str) -> BeautifulSoup:
    """加载HTML文件并返回BeautifulSoup对象"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return BeautifulSoup(content, 'html.parser')
    except Exception as e:
        print(f"❌ 加载文件失败 {file_path}: {e}")
        return None

def test_page_analyzer_v3():
    """测试PageAnalyzer的3策略决策逻辑"""
    print("=" * 80)
    print("🧪 测试 PageAnalyzer 3策略决策逻辑")
    print("=" * 80)
    
    analyzer = PageAnalyzer()
    
    # 测试用例定义（基于文档预期结果）
    test_cases = [
        {
            "file": "data/prod-html/integration/event-grid.html",
            "description": "event-grid.html → SimpleStaticStrategy",
            "expected": "SimpleStatic"
        },
        {
            "file": "data/prod-html/integration/service-bus.html", 
            "description": "service-bus.html → SimpleStaticStrategy",
            "expected": "SimpleStatic"
        },
        {
            "file": "data/prod-html/integration/api-management.html",
            "description": "api-management.html → RegionFilterStrategy", 
            "expected": "RegionFilter"
        },
        {
            "file": "data/prod-html/compute/cloud-services.html",
            "description": "cloud-services.html → ComplexContentStrategy",
            "expected": "Complex"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 测试 {i}: {test_case['description']}")
        
        # 检查文件是否存在
        if not os.path.exists(test_case['file']):
            print(f"⚠ 文件不存在: {test_case['file']}")
            continue
            
        # 加载HTML
        soup = load_html_file(test_case['file'])
        if not soup:
            continue
            
        # 执行策略决策
        try:
            strategy_type = analyzer.determine_page_type_v3(soup)
            expected = test_case['expected']
            
            if strategy_type == expected:
                print(f"🎉 测试 {i} 通过! 策略: {strategy_type}")
            else:
                print(f"❌ 测试 {i} 失败! 期望: {expected}, 实际: {strategy_type}")
                
        except Exception as e:
            print(f"❌ 测试执行出错: {e}")
            import traceback
            traceback.print_exc()

def test_additional_files():
    """测试额外的文件以验证策略决策的准确性"""
    print("\n\n" + "=" * 80)
    print("🧪 测试额外文件的策略决策")
    print("=" * 80)
    
    analyzer = PageAnalyzer()
    
    # 查找所有HTML文件进行测试
    html_files = []
    for root in ["data/prod-html/integration", "data/prod-html/compute"]:
        if os.path.exists(root):
            for file in os.listdir(root):
                if file.endswith('.html'):
                    html_files.append(os.path.join(root, file))
    
    print(f"找到 {len(html_files)} 个HTML文件进行测试")
    
    strategy_counts = {"SimpleStatic": 0, "RegionFilter": 0, "Complex": 0}
    
    for file_path in html_files:
        file_name = os.path.basename(file_path)
        print(f"\n🔍 分析: {file_name}")
        
        soup = load_html_file(file_path)
        if not soup:
            continue
            
        try:
            strategy_type = analyzer.determine_page_type_v3(soup)
            strategy_counts[strategy_type] += 1
            print(f"   策略: {strategy_type}")
        except Exception as e:
            print(f"   ❌ 错误: {e}")
    
    print(f"\n📊 策略分布统计:")
    for strategy, count in strategy_counts.items():
        print(f"   {strategy}: {count} 个文件")

def main():
    """主函数"""
    print("🔍 开始验证PageAnalyzer的3策略决策逻辑")
    print("基于 docs/flexible-content-implementation.md 中的预期结果")
    
    # 测试核心决策逻辑
    test_page_analyzer_v3()
    
    # 测试额外文件
    test_additional_files()
    
    print("\n\n" + "=" * 80)
    print("✅ PageAnalyzer 验证完成")
    print("=" * 80)

if __name__ == "__main__":
    main()